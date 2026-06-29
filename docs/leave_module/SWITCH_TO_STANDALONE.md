# BASCULE VERS LE MODE STANDALONE

## 1. État actuel : 100 % standalone, Odoo désactivé

Le module congés fonctionne **entièrement en standalone** (PostgreSQL direct).
La couche Odoo reste présente dans le code mais **n'est plus appelée** :

- **Frontend** : `LeaveRequestPage` (création) et `ManagerApprovalPage`
  (approbation / rejet) utilisent exclusivement les endpoints `*-standalone`.
- **Backend** : les anciens endpoints Odoo sont marqués `deprecated=True`
  (toujours fonctionnels, mais signalés comme dépréciés dans OpenAPI/Swagger).
- **Tests** : les 3 tests d'intégration Odoo sont `@pytest.mark.skip`.
- **n8n** : à basculer manuellement (voir §4).

---

## 2. Endpoints encore disponibles (dépréciés — Odoo)

Conservés pour rétrocompatibilité, marqués `deprecated=True` :

| Méthode + path | Remplacé par |
|---|---|
| `POST /api/leave-requests` | `POST /api/leave-requests/standalone` |
| `POST /api/leave-requests/{id}/approve` | `POST /api/leave-requests/{id}/approve-standalone` |
| `POST /api/leave-requests/{id}/reject` | `POST /api/leave-requests/{id}/reject-standalone` |
| `POST /api/leave-requests/{id}/automation-analysis` | `POST /api/n8n/leave-standalone/analysis-complete` |
| `POST /api/leave-requests/{id}/decision-sync-result` | `POST /api/n8n/leave-standalone/decision-complete` |

> Les endpoints de **lecture** (`GET /leave-requests`, `/my`, `/mine`, `/pending`)
> ne sont **pas** dépréciés : ils restent utilisés par les deux modes.

---

## 3. Endpoints actifs (standalone)

| Méthode + path | Permission |
|---|---|
| `GET /api/leave-requests/my-balance` | authentifié |
| `GET /api/leave-requests/leave-types` | authentifié |
| `POST /api/leave-requests/standalone` | `leave.request.create` |
| `POST /api/leave-requests/{id}/approve-standalone` | `leave.request.approve` |
| `POST /api/leave-requests/{id}/reject-standalone` | `leave.request.approve` |
| `GET /api/leave-requests/allocations` | `leave.request.view_all` |
| `POST /api/leave-requests/allocations` | `leave.request.hr_validate` |
| `GET /api/leave-requests/analytics` | `leave.request.view_all` |
| `POST /api/n8n/leave-standalone/analysis-complete` | `X-FlowPilot-Secret` |
| `POST /api/n8n/leave-standalone/decision-complete` | `X-FlowPilot-Secret` |

---

## 4. Procédure n8n (à faire manuellement dans l'UI)

### Désactiver (workflows Odoo)
- `FP_LEAVE_00_BALANCE_PRECHECK` → **Active = false**
- `FP_LEAVE_01_Request_Analysis_FlowPilot_CORRECTED` → **Active = false**
- `FP_LEAVE_02_Manager_Decision_Sync_FlowPilot_CORRECTED` → **Active = false**

### Activer (workflows standalone)
- `FP_LEAVE_STANDALONE_01_Notify_Manager` → **Active = true**
- `FP_LEAVE_STANDALONE_02_Notify_Employee` → **Active = true**

### Variables d'environnement n8n requises
```env
FLOWPILOT_API_BASE_URL=http://host.docker.internal:8000
FLOWPILOT_N8N_SHARED_SECRET=<même secret que le backend>
OPENROUTER_API_KEY=<clé OpenRouter>
```

> Les workflows standalone réutilisent le credential Gmail existant
> (`gmailOAuth2` — « Gmail account »).

---

## 5. Comment revenir en mode Odoo

La bascule est **réversible**. Procédure complète dans
[MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md) :

1. Configurer les variables `.env` Odoo (`ODOO_BASE_URL`, `ODOO_DB`…).
2. Dans n8n : désactiver les 2 workflows standalone, réactiver les 3 workflows Odoo.
3. Créer les allocations `hr.leave.allocation` (state `validate`) dans Odoo.
4. Côté frontend : repointer `LeaveRequestPage` / `ManagerApprovalPage` vers les
   fonctions historiques (`createLeaveRequest`, `approveLeaveRequest`,
   `rejectLeaveRequest`) — **toujours présentes** dans `leaveService.ts`.
5. (Optionnel) retirer `deprecated=True` des endpoints Odoo et le `skip` des 3 tests.

Détails techniques de l'intégration Odoo : [ODOO_INTEGRATION.md](./ODOO_INTEGRATION.md).
