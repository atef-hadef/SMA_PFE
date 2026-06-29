# MODULE CONGÉS STANDALONE — Guide complet

## 1. Vue d'ensemble

Le module de gestion des congés fonctionne désormais **sans Odoo** : toutes les
données (demandes, soldes, allocations, types) vivent directement dans
**PostgreSQL**. La couche d'intégration Odoo (3 workflows n8n + endpoints
de callback) reste **conservée intacte** et peut être réactivée (voir
[MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md) et [ODOO_INTEGRATION.md](./ODOO_INTEGRATION.md)).

**Décision stratégique** — remplacer Odoo par PostgreSQL direct :

- **Pas de dépendance externe** : plus besoin d'un serveur Odoo + JSON-RPC pour
  calculer un solde ou approuver une demande.
- **Cohérence de stack** : tout transite par FastAPI + SQLAlchemy + PostgreSQL,
  comme le reste de l'application (CRM, dashboard…).
- **Fiabilité démo / soutenance** : un seul service à lancer, comportement
  déterministe, pas de point de panne réseau vers Odoo.
- **Valeur ajoutée** : conflits d'équipe par rôle, détection de burnout,
  analytics RH et analyse LLM — non présents dans la version Odoo.

---

## 2. Architecture du flux complet

```
Employé → Frontend (LeaveRequestPage) → POST /api/leave-requests/standalone
  → leave_standalone_service.create_leave_request_standalone()
  → Vérifs : solde disponible, chevauchement, conflits équipe (peers même rôle), burnout
  → INSERT leave_requests (status = pending)
  → Webhook n8n FP_LEAVE_STANDALONE_01_Notify_Manager
      → LLM Mistral Large (OpenRouter) analyse la demande
      → Email Gmail au manager avec recommandation IA + conflits + burnout
      → Callback POST /api/n8n/leave-standalone/analysis-complete
           (écrit automation_recommendation + automation_summary)

  → Manager approuve / refuse via ManagerApprovalPage
  → POST /api/leave-requests/{id}/approve-standalone  (ou /reject-standalone)
  → Vérifs : l'approbateur est bien le manager du demandeur, statut encore en attente
  → UPDATE leave_requests (status = approved | rejected, reviewed_by, reviewed_at)
  → Webhook n8n FP_LEAVE_STANDALONE_02_Notify_Employee
      → Email Gmail à l'employé avec la décision (branche approuvé / refusé)
      → Callback POST /api/n8n/leave-standalone/decision-complete (log)

  → RH consulte les soldes + analytics via LeaveAllocationPage
```

Tous les appels n8n sont **best-effort** (try/except silencieux) : si n8n est
indisponible, la demande/décision est tout de même enregistrée en base.

---

## 3. Tables PostgreSQL

### `leave_requests` (existante, enrichie pour l'intégration)

| Colonne | Type | Rôle |
|---|---|---|
| id | VARCHAR(64) PK | `leave_xxxxxxxx` |
| user_id | VARCHAR(64) FK users | demandeur |
| leave_type | VARCHAR(80) | **code** standalone (`vacation`, `sick`…) |
| start_date / end_date | DATE | période |
| reason | TEXT | motif |
| status | VARCHAR(40) | `pending` → `approved` / `rejected` |
| requested_days | NUMERIC(8,2) | jours ouvrables demandés |
| available_days | NUMERIC(8,2) | solde au moment de la demande |
| reviewed_by | VARCHAR(64) FK users | manager décideur |
| reviewed_at | TIMESTAMPTZ | date de décision |
| decision_comment | TEXT | commentaire manager |
| automation_recommendation | VARCHAR(120) | reco LLM (callback n8n) |
| automation_summary | TEXT (JSON) | détails analyse LLM |
| score | INTEGER | score IA optionnel |
| odoo_leave_id / odoo_state / odoo_sync_status | — | **inutilisés en standalone** (réservés Odoo) |

> Remarque : les colonnes `ml_score`, `ml_probability`… concernent **`crm_leads`**
> (module Data Science), **pas** `leave_requests`.

### `leave_allocations` (NOUVELLE — source de vérité des soldes)

| Colonne | Type |
|---|---|
| id | VARCHAR(64) PK (`alloc_{employee}_{type}_{year}`) |
| employee_id | VARCHAR(64) FK users |
| year | INTEGER |
| leave_type | VARCHAR(80) (code) |
| allocated_days | NUMERIC(8,2) |
| created_by | VARCHAR(64) FK users |
| created_at / updated_at | TIMESTAMPTZ |
| **contrainte** | UNIQUE(employee_id, year, leave_type) — `uq_alloc_emp_year_type` |

### `leave_types` (NOUVELLE — 5 types prédéfinis)

| Colonne | Type |
|---|---|
| id | VARCHAR(64) PK |
| code | VARCHAR(40) UNIQUE |
| label_fr / label_en | VARCHAR(120) |
| default_days | INTEGER |
| requires_document | BOOLEAN |
| is_active | BOOLEAN |

Données seedées : `vacation` (25), `sick` (15, justificatif requis),
`personal` (5), `rtt` (10), `unpaid` (0).

### `users` (existante)

Fournit le rôle (`role_id`), le nom (`full_name`), l'email et le département.
La logique de département standalone s'appuie sur `role_id` (voir §4).

---

## 4. Logique de départements (`DEPARTMENT_CONFIG`)

Définie dans `backend/app/services/leave_standalone_service.py`. Elle évite une
table « département » : tout dérive du **rôle** de l'employé.

| Rôle employé | Département | Manager (rôle) | Pairs (peers) |
|---|---|---|---|
| `role_sales` | Commercial | `role_manager` | `role_sales` |
| `role_manager` | Commercial | `role_admin` | `role_manager` |
| `role_hr` | RH | `role_admin` | `role_hr` |
| `role_ai_supervisor` | IA | `role_admin` | `role_ai_supervisor` |
| `role_admin` | Direction | `None` | `role_admin` |

**Exemple concret** — *Commercial 1* (`role_sales`) soumet une demande :
- `get_employee_manager` → premier user actif `role_manager` = **Manager Commercial**.
- `get_department_peers` → autres `role_sales` = **Commercial 2 et 3** (l'employé est exclu).
- `check_team_conflicts` ne vérifie les chevauchements **qu'avec Commercial 2 et 3**
  (jamais RH, IA ni Direction). Taux d'occupation = absents / (peers + 1).

---

## 5. Workflows n8n

### Workflows actifs (standalone)

| Fichier | Webhook | Rôle |
|---|---|---|
| `workflows/leave_standalone/FP_LEAVE_STANDALONE_01_Notify_Manager.json` | `flowpilot/leave-standalone/notify-manager` | Analyse LLM (Mistral Large) + email manager + callback |
| `workflows/leave_standalone/FP_LEAVE_STANDALONE_02_Notify_Employee.json` | `flowpilot/leave-standalone/notify-employee` | Email employé selon décision + callback |

Credential Gmail : `gmailOAuth2` (« Gmail account »). `continueOnFail: true` sur
les nodes LLM et callbacks.

### Workflows désactivés (version Odoo — CONSERVÉS INTACTS)

- `workflows/demande de congée/FP_LEAVE_00_BALANCE_PRECHECK.json`
- `workflows/demande de congée/FP_LEAVE_01_Request_Analysis_FlowPilot_CORRECTED.json`
- `workflows/demande de congée/FP_LEAVE_02_Manager_Decision_Sync_FlowPilot_CORRECTED.json`

Détails dans [ODOO_INTEGRATION.md](./ODOO_INTEGRATION.md).

---

## 6. Endpoints API standalone

Tous montés sous `/api` (les 9 endpoints Odoo existants restent inchangés).

| Méthode + path | Permission | Description |
|---|---|---|
| `GET /api/leave-requests/my-balance` | authentifié | Soldes 2026 de l'utilisateur courant |
| `GET /api/leave-requests/leave-types` | authentifié | Types de congés actifs |
| `POST /api/leave-requests/standalone` | `leave.request.create` | Créer une demande (vérifs + webhook 01) |
| `POST /api/leave-requests/{id}/approve-standalone` | `leave.request.approve` | Approuver (webhook 02) |
| `POST /api/leave-requests/{id}/reject-standalone` | `leave.request.approve` | Refuser (webhook 02) |
| `GET /api/leave-requests/allocations` | `leave.request.view_all` | Allocations groupées par employé |
| `POST /api/leave-requests/allocations` | `leave.request.hr_validate` | Upsert d'une allocation |
| `GET /api/leave-requests/analytics` | `leave.request.view_all` | Dashboard RH (burnout, > 48h…) |
| `POST /api/n8n/leave-standalone/analysis-complete` | `X-FlowPilot-Secret` | Callback analyse LLM |
| `POST /api/n8n/leave-standalone/decision-complete` | `X-FlowPilot-Secret` | Callback notification envoyée |

---

## 7. Variables d'environnement requises

### Backend (`backend/.env`)

```env
FLOWPILOT_N8N_SHARED_SECRET=<secret partagé n8n>
N8N_WEBHOOK_BASE_URL=http://localhost:5678/webhook
FRONTEND_ORIGIN=http://localhost:5173
DATABASE_URL=postgresql+psycopg://flowpilot_user:flowpilot_password@localhost:5432/flowpilot_db
```

### n8n (variables d'environnement du conteneur)

```env
FLOWPILOT_API_BASE_URL=http://host.docker.internal:8000
FLOWPILOT_N8N_SHARED_SECRET=<même secret que le backend>
OPENROUTER_API_KEY=<clé OpenRouter>
```

> Le frontend utilise `VITE_API_BASE_URL` (défaut `http://127.0.0.1:8000/api`).

---

## 8. Comment tester le module

1. **Démarrer l'infra** : Docker (PostgreSQL + n8n).
2. **Seed** : `python -c "from app.db.seed_db import seed_database; seed_database()"`
   (crée users, `leave_types`, et 20 allocations 2026).
3. **Activer** les 2 workflows standalone dans n8n (et renseigner les variables n8n).
4. **Backend** : `uvicorn app.main:app --reload`.
5. **Frontend** : `npm run dev`.
6. **Login Commercial 1** (`commercial1@tac-tic.tn`) → page *Demande de congé* :
   vérifier l'affichage des soldes, soumettre une demande.
7. **Vérifier l'email** reçu par le **Manager Commercial** (recommandation IA).
8. **Login Manager** → *Validations manager* → approuver/refuser.
9. **Vérifier l'email** reçu par **Commercial 1** (décision).
10. **Login HR** (`hr@tac-tic.tn`) → *Allocation Congés* : éditer des allocations
    et consulter l'analytics (burnout, demandes > 48h).

---

## 9. Fichiers créés / modifiés (récap des 7 parties)

### Créés — backend
- `backend/app/models/leave_type.py`
- `backend/app/models/leave_allocation.py`
- `backend/app/services/leave_standalone_service.py`
- `backend/app/schemas/leave_standalone.py`
- `backend/app/db/migrations/2026_06_24_leave_standalone_tables.sql`

### Créés — frontend
- `frontend/src/pages/LeaveAllocationPage.tsx`

### Créés — workflows
- `workflows/leave_standalone/FP_LEAVE_STANDALONE_01_Notify_Manager.json`
- `workflows/leave_standalone/FP_LEAVE_STANDALONE_02_Notify_Employee.json`

### Créés — docs
- `docs/leave_module/ODOO_INTEGRATION.md`
- `docs/leave_module/STANDALONE_SETUP.md`
- `docs/leave_module/MIGRATION_GUIDE.md`

### Modifiés — backend
- `backend/app/models/__init__.py` (exports `LeaveType`, `LeaveAllocation`)
- `backend/app/api/leave_requests.py` (+10 endpoints, anciens intacts)
- `backend/app/db/seed_db.py` (seed des allocations 2026)

### Modifiés — frontend
- `frontend/src/services/leaveService.ts` (+8 fonctions, +9 types)
- `frontend/src/pages/LeaveRequestPage.tsx` (soldes + contrôle insuffisance + flux standalone)
- `frontend/src/layouts/Sidebar.tsx` (entrée « Allocation Congés »)
- `frontend/src/App.tsx` (route `/leave-allocations`)
- `frontend/src/auth/permissions.ts` (route protégée)

### Intacts (non modifiés)
- `workflows/demande de congée/` (3 workflows Odoo)
- Les 9 endpoints Odoo de `leave_requests.py`
- `leave_service.py` (service Odoo)
