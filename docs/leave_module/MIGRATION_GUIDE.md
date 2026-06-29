# GUIDE DE MIGRATION STANDALONE ↔ ODOO

## Mode actuel : Standalone

Le système fonctionne actuellement **sans Odoo**. Toutes les données congés
(demandes, soldes, allocations, types) sont en **PostgreSQL direct**. Les
notifications passent par les 2 workflows n8n standalone + Gmail, avec une
analyse LLM (Mistral Large) côté manager.

---

## Pour passer de Standalone à Odoo (réactivation)

### Étape 1 — Configurer les variables `.env`

```env
ODOO_BASE_URL=http://localhost:8069
ODOO_DB=flowpilot_odoo
ODOO_UID=2
ODOO_PASSWORD=admin
ODOO_LEAVE_TYPE_ID=5
ODOO_DEPARTMENT_ID=2
```

> Voir [ODOO_INTEGRATION.md](./ODOO_INTEGRATION.md) §1 pour le détail du transport
> JSON-RPC et les valeurs par défaut réelles du projet.

### Étape 2 — Désactiver dans n8n (workflows standalone)

- `FP_LEAVE_STANDALONE_01_Notify_Manager` → **Active = false**
- `FP_LEAVE_STANDALONE_02_Notify_Employee` → **Active = false**

(évite le double envoi d'emails)

### Étape 3 — Activer dans n8n (workflows Odoo)

- `FP_LEAVE_00_BALANCE_PRECHECK` → **Active = true**
- `FP_LEAVE_01_Request_Analysis_FlowPilot_CORRECTED` → **Active = true**
- `FP_LEAVE_02_Manager_Decision_Sync_FlowPilot_CORRECTED` → **Active = true**

### Étape 4 — Créer les allocations dans Odoo

Dans Odoo, créer des enregistrements `hr.leave.allocation` :
- `state = validate` (seules les allocations validées comptent),
- `employee_id` mappé sur les users CRM (voir `MVP_ODOO_EMPLOYEE_IDS`),
- `holiday_status_id` = type de congé Odoo.

Sans allocation `validate`, le solde calculé sera nul et toute demande sera
rejetée par politique.

### Étape 5 — Tester avec un congé de test

Soumettre une demande via le frontend et vérifier que le payload arrive bien
sur Odoo via la chaîne de webhooks `FP_LEAVE_00 → 01 → 02` et que les callbacks
`/api/leave-requests/{id}/automation-analysis` puis `/decision-sync-result`
mettent à jour la demande.

> **Note** : le routage backend (création/approbation) appelle aujourd'hui les
> webhooks **standalone**. Pour un basculement complet vers Odoo, le frontend
> doit utiliser les endpoints Odoo historiques (`/leave-requests`,
> `/{id}/approve`, `/{id}/reject`) au lieu des variantes `*-standalone`, ou
> introduire un flag `USE_ODOO` côté service pour rerouter vers les webhooks
> Odoo. Les deux familles d'endpoints coexistent sans conflit.

---

## Pour rester en Standalone (configuration actuelle)

Aucune configuration externe requise. Tous les workflows utilisent PostgreSQL
directement. S'assurer simplement que les **2 workflows standalone sont actifs**
dans n8n et que les variables n8n (`FLOWPILOT_API_BASE_URL`,
`FLOWPILOT_N8N_SHARED_SECRET`, `OPENROUTER_API_KEY`) sont renseignées.

---

## Compatibilité des données

| Table | Standalone | Odoo |
|---|---|---|
| `leave_requests` | ✅ utilisée | ✅ utilisée (synchronisée) |
| `leave_allocations` | ✅ source de vérité | ❌ ignorée (Odoo source) |
| `leave_types` | ✅ utilisée | ❌ ignorée (Odoo `holiday_status_id`) |

---

## Différences fonctionnelles

| Fonctionnalité | Standalone | Odoo |
|---|---|---|
| Calcul solde | Python (`leave_standalone_service`) | Odoo `hr.leave.allocation` |
| Conflits équipe | Python (`DEPARTMENT_CONFIG`, par rôle) | Odoo `department_id` |
| Approbation | FastAPI direct (`*-standalone`) | Odoo `action_approve` / `action_refuse` |
| Emails | n8n + Gmail (2 workflows) | Odoo (aucun email dans les workflows actuels) |
| LLM | Mistral Large via OpenRouter | Aucun LLM dans les workflows Odoo |
| Burnout / analytics RH | ✅ (Python) | ❌ |
| Dépendance externe | Aucune | Serveur Odoo + JSON-RPC |
