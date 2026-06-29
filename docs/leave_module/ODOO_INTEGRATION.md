# ODOO INTEGRATION — Module Congés TAC-TIC

> Ce fichier documente l'intégration Odoo **existante** (workflows dans
> `workflows/demande de congée/`) afin de pouvoir la **réactiver facilement**
> après la mise en place du module standalone (sans Odoo).
>
> ⚠️ Les 3 workflows Odoo et le code backend décrits ici sont **INTACTS** et ne
> doivent pas être modifiés. Ce document est une extraction fidèle de leur
> contenu réel (webhooks, modèles Odoo, domains, fields, states, callbacks).

---

## 1. Prérequis Odoo

- **Odoo 16 ou 17** (les états `confirm` / `validate1` / `validate` / `refuse`
  utilisés correspondent au workflow standard de `hr_holidays`).
- **Modules Odoo** : `hr`, `hr_holidays`.
- **Accès JSON-RPC** activé (endpoint `POST {ODOO_BASE_URL}/jsonrpc`).

### Variables `.env` attendues

Les valeurs ci-dessous sont les **défauts réels** définis dans
[`backend/app/core/config.py`](../../backend/app/core/config.py) :

```env
ODOO_BASE_URL=http://host.docker.internal:8069
ODOO_DB=flowpilot_odoo
ODOO_UID=2
ODOO_PASSWORD=123456789

# Webhooks n8n (côté backend → n8n)
LEAVE_N8N_WEBHOOK_BASE_URL=http://host.docker.internal:5678/webhook
LEAVE_BALANCE_PRECHECK_WEBHOOK_URL=http://localhost:5678/webhook/flowpilot/leave/balance-precheck

# Callback n8n → backend
FLOWPILOT_API_BASE_URL_FOR_N8N=http://host.docker.internal:8000
FLOWPILOT_N8N_SHARED_SECRET=flowpilot-test-secret
```

> Note : le `.env.example` actuel surcharge `LEAVE_N8N_WEBHOOK_BASE_URL` vers
> `http://localhost:5678/webhook`, ce qui fait diverger 3 tests
> (`test_leave_callback_service.py`). À aligner si Odoo est réactivé.

### Transport JSON-RPC

Tous les appels Odoo passent par un seul format (cf.
[`leave_service.py::_odoo_execute_kw`](../../backend/app/services/leave_service.py)
et les nodes « Build Odoo … Request » des workflows) :

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "service": "object",
    "method": "execute_kw",
    "args": [ODOO_DB, ODOO_UID, ODOO_PASSWORD, "<model>", "<method>", [args], {kwargs}]
  },
  "id": 1
}
```

---

## 2. Tables (modèles) Odoo utilisées

### 2.1 `hr.leave.allocation` — Allocations (le « solde » alloué)

| Élément | Valeur |
|---|---|
| Méthode | `search_read` |
| Domain | `[["employee_id","=",<id>], ["holiday_status_id","=",<type_id>], ["state","=","validate"]]` |
| Fields | `id`, `employee_id`, `holiday_status_id`, `number_of_days`, `state` |

> Seules les allocations à l'état **`validate`** comptent comme jours alloués.

### 2.2 `hr.leave` — Demandes / congés pris

| Usage | Méthode | Domain | Fields |
|---|---|---|---|
| **Congés pris** (precheck & analyse) | `search_read` | `[["employee_id","=",<id>], ["holiday_status_id","=",<type_id>], ["state","in",["confirm","validate1","validate"]]]` | `id`, `employee_id`, `holiday_status_id`, `number_of_days`, `request_date_from`, `request_date_to`, `state` |
| **Conflits département** (W01) | `search_read` | `[..., ["state","in",["validate","validate1","confirm"]]]` | `id`, `employee_id`, `request_date_from`, `request_date_to`, `state` |
| **Création** (W01) | `create` | — | vals : `employee_id`, `holiday_status_id`, `request_date_from`, `request_date_to`, `name` |
| **Relecture après création/décision** | `read` | — | `id`, `employee_id`, `holiday_status_id`, `request_date_from`, `request_date_to`, `name`, `number_of_days`, `state` |
| **Décision manager** (W02) | `action_approve` / `action_refuse` | id du congé | — |

### 2.3 États (`state`) du workflow `hr.leave`

| État | Signification |
|---|---|
| `draft` | Brouillon |
| `confirm` | Soumis / à approuver (état après création par W01) |
| `validate1` | Première validation |
| `validate` | Validé (compte comme congé pris) |
| `refuse` | Refusé |

**Calcul du solde** (cf. node « Compute Leave Balance ») :
`available = SUM(allocations.number_of_days où state=validate) − SUM(congés où state ∈ {validate, validate1})`.

### 2.4 Mapping interne → Odoo (MVP, dans `leave_service.py`)

```python
MVP_ODOO_EMPLOYEE_IDS    = {"user_010": 3}   # défaut: 3
MVP_ODOO_DEPARTMENT_ID   = 2
MVP_ODOO_ANNUAL_LEAVE_TYPE_ID = 5            # holiday_status_id pour "annual/annuel/congé"
```

---

## 3. Workflows Odoo (conservés dans `workflows/demande de congée/`)

Tous les nodes Odoo HTTP pointent vers `={{ ... odoo_base_url + '/jsonrpc' }}`.
Tous les callbacks pointent vers `flowpilot_api_base_url + '/api/leave-requests/...'`.

### 3.1 `FP_LEAVE_00_BALANCE_PRECHECK` — Pré-vérification du solde (synchrone)

- **Webhook** : `POST flowpilot/leave/balance-precheck` (`responseMode: lastNode`)
- **Appelé par** : `leave_service._post_leave_balance_precheck_webhook`
  (URL = `LEAVE_BALANCE_PRECHECK_WEBHOOK_URL`), **avant** insertion en base.
- **Nodes (ordre)** :
  1. `FastAPI Trigger - Leave Balance Precheck` (webhook)
  2. `Normalize Precheck Input` (code)
  3. `Build Odoo Allocation Request` (code) → construit le JSON-RPC
  4. `Odoo - Read Validated Allocations` (httpRequest) — `hr.leave.allocation`, `state=validate`
  5. `Build Odoo Taken Leaves Request` (code)
  6. `Odoo - Read Taken Leaves` (httpRequest) — `hr.leave`, `state ∈ {confirm, validate1, validate}`
  7. `Compute Balance Precheck Result` (code)
- **Payload entrée** (construit par `_build_leave_balance_precheck_payload`) :
  `employee_id`, `odoo_employee_id`, `leave_type`, `odoo_leave_type_id`,
  `date_from`, `date_to`, `requested_days`, `odoo_base_url`, `odoo_db`,
  `odoo_uid`, `odoo_password`.
- **Payload sortie** (consommé par `_normalize_leave_balance_precheck_result`) :
  `ok`, `status`, `error_code` (`INSUFFICIENT_LEAVE_BALANCE` / `LEAVE_PERIOD_OVERLAP`),
  `available_days`, `requested_days`, `balance_gap_days`, `has_enough_balance`,
  `recommendation`, `recommendation_label`, `risk_level`, `ai_explanation`,
  `employee_guidance`, `manager_guidance`, `message`, `conflict_detected`,
  `conflict_type`, `overlapping_leave_count`, `overlapping_leaves[]`.

### 3.2 `FP_LEAVE_01_Request_Analysis` (26 nodes) — Analyse + création Odoo (asynchrone)

- **Webhook** : `POST flowpilot/leave/request-analysis` (`responseMode: lastNode`)
- **Appelé par** : `leave_service._post_leave_request_analysis_webhook`
  (URL = `LEAVE_N8N_WEBHOOK_BASE_URL` + `/flowpilot/leave/request-analysis`),
  après insertion (statut `pending`).
- **Header sortant** : `X-FlowPilot-Secret: FLOWPILOT_N8N_SHARED_SECRET`.
- **Appels Odoo (dans l'ordre)** :
  1. `Odoo - Read Validated Allocations` — `hr.leave.allocation`, `state=validate`
  2. `Odoo - Read Existing Leaves` — `hr.leave`, `state ∈ {validate, validate1, confirm}`
  3. `Compute Leave Balance` — solde = allocations(validate) − congés(validate, validate1)
  4. **Branche `Balance Sufficient?`** (node `if`) :
     - **Non** → `Build Policy Rejection Callback` → `FastAPI Callback - Policy Rejection`
       (`POST /api/leave-requests/{id}/automation-analysis`) → fin.
     - **Oui** ↓
  5. `Odoo - Check Department Conflicts` — `hr.leave`, `state ∈ {validate, validate1, confirm}`
  6. `Compute Manager Recommendation` (code)
  7. `Odoo - Create Leave Request` — `hr.leave.create` (vals : `employee_id`,
     `holiday_status_id`, `request_date_from`, `request_date_to`, `name`)
  8. `Extract Odoo Leave ID` → **branche `Odoo Create OK?`** :
     - **Non** → `FastAPI Callback - Odoo Failure` (`/automation-analysis`)
     - **Oui** → `Odoo - Read Created Leave` (`read`) →
       `Build Analysis Callback` → `FastAPI Callback - Analysis Result`
       (`POST /api/leave-requests/{id}/automation-analysis`)
- **Callback final** consommé par `save_leave_automation_analysis`
  (schéma `LeaveAutomationAnalysisCallback`) : `ok`, `odoo_leave_id`,
  `odoo_state` (typiquement `confirm`), `recommendation`, `score`,
  `available_days`, `requested_days`, `risk_level`, `decision_reasons`,
  `manager_guidance`, etc. → met la demande à `manager_review_required`.

### 3.3 `FP_LEAVE_02_Manager_Decision_Sync` (15 nodes) — Synchro de la décision

- **Webhook** : `POST flowpilot/leave/decision-sync` (`responseMode: lastNode`)
- **Appelé par** : `leave_service._post_leave_decision_sync_webhook`
  (URL = `LEAVE_N8N_WEBHOOK_BASE_URL` + `/flowpilot/leave/decision-sync`),
  après approbation/rejet manager (nécessite un `odoo_leave_id`).
- **Nodes clés** :
  1. `FastAPI Trigger - Manager Decision Sync` (webhook)
  2. `Normalize Manager Decision` — `decision ∈ {approved, rejected}` ;
     `odoo_method = approved ? 'action_approve' : 'action_refuse'`
  3. `Build Odoo Decision Request` → `execute_kw(hr.leave, <odoo_method>, [id])`
  4. `Odoo - Apply Manager Decision` (httpRequest)
  5. `Map Decision Result` → **branche `Odoo Decision OK?`** :
     - **Non** → `FastAPI Callback - Decision Failure` (`/decision-sync-result`)
     - **Oui** → `Odoo - Read Leave After Decision` (`read`) →
       `Build Decision Sync Callback` → `FastAPI Callback - Decision Sync Result`
- **Callback final** consommé par `save_leave_decision_sync_result`
  (schéma `LeaveDecisionSyncCallback`) : `ok`, `decision`, `odoo_leave_id`,
  `odoo_state` (`validate` si approuvé, `refuse` si rejeté), `odoo_sync_status`,
  `manager_comment`, `decided_at`. → fixe le statut final + `odoo_sync_status`.

### 3.4 Endpoints backend de callback (existants, intacts)

| Callback | Endpoint backend | Schéma |
|---|---|---|
| W01 (×3) | `POST /api/leave-requests/{id}/automation-analysis` | `LeaveAutomationAnalysisCallback` |
| W02 (×2) | `POST /api/leave-requests/{id}/decision-sync-result` | `LeaveDecisionSyncCallback` |

---

## 4. Comment réactiver Odoo en 5 étapes

> Le module standalone (à venir) tournera **en parallèle** sans toucher à ces
> workflows. Réactiver Odoo = rebasculer le backend vers les webhooks Odoo.

**Étape 1 — Configurer Odoo + `.env`**
Installer `hr` + `hr_holidays`, créer la base, puis renseigner
`ODOO_BASE_URL`, `ODOO_DB`, `ODOO_UID`, `ODOO_PASSWORD` et les URLs webhook
(section 1). Vérifier le mapping employé/type (`MVP_ODOO_*`).

**Étape 2 — Désactiver les workflows standalone**
Dans n8n, désactiver `FP_LEAVE_STANDALONE_01` et `FP_LEAVE_STANDALONE_02`
(pour éviter le double envoi d'emails).

**Étape 3 — Réimporter et activer les 3 workflows Odoo**
Importer/activer `FP_LEAVE_00_BALANCE_PRECHECK`,
`FP_LEAVE_01_Request_Analysis_FlowPilot_CORRECTED`,
`FP_LEAVE_02_Manager_Decision_Sync_FlowPilot_CORRECTED`. Vérifier que les
chemins webhook correspondent (`flowpilot/leave/...`) et le credential
JSON-RPC/HTTP.

**Étape 4 — Dans `leave_service.py` mettre `USE_ODOO=True`**
Basculer le flag de routage (à introduire avec le module standalone) pour que
la création/approbation appelle les webhooks Odoo
(`request-analysis` / `decision-sync`) au lieu des webhooks standalone.

**Étape 5 — Créer les allocations dans Odoo**
Créer les `hr.leave.allocation` à l'état `validate` pour chaque employé/type,
sinon le solde calculé sera nul et toutes les demandes seront rejetées par
politique.

---

## 5. Récapitulatif des chemins webhook

| Workflow | Webhook (n8n) | Déclencheur backend |
|---|---|---|
| W00 Precheck | `flowpilot/leave/balance-precheck` | `LEAVE_BALANCE_PRECHECK_WEBHOOK_URL` |
| W01 Analysis | `flowpilot/leave/request-analysis` | `LEAVE_N8N_WEBHOOK_BASE_URL` + path |
| W02 Decision | `flowpilot/leave/decision-sync` | `LEAVE_N8N_WEBHOOK_BASE_URL` + path |
| Standalone 01 (à venir) | `flowpilot/leave-standalone/notify-manager` | — |
| Standalone 02 (à venir) | `flowpilot/leave-standalone/notify-employee` | — |
