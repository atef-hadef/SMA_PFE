# Audit du flux CRM — Rapport (Sprint A)

> **Date** : 2026-06-25
> **Périmètre** : audit transversal réalisé pendant le Sprint A (FIX 1→4) sur le module CRM + interactions avec le module Congés.
> **Statut** : document d'analyse. Les éléments marqués 🔴/🟠 ne sont **pas** corrigés (hors périmètre Sprint A) ; ceux marqués ✅ l'ont été pendant le sprint.

---

## 1. Incohérence `status` vs `customer_status`

**Constat (confirmé).** La table `crm_leads` porte **deux** champs de statut qui ne servent pas la même chose, ce qui prête à confusion :

| Champ | Rôle réel | Valeurs | Lu par |
|---|---|---|---|
| `status` | **Bucket de scoring** | `new` / `hot` / `warm` / `cold` | `_safe_status()` ([crm_service.py](../../backend/app/services/crm_service.py)) |
| `customer_status` | **Cycle de vie commercial** | `lead` → `prospect` → `conversion_pending` → `customer`/`vip` … + `lost` / `archived` / `unqualified` | `compute_crm_display_state()` (toute l'UI CRM) |

**Piège.** `_safe_status()` **coerce silencieusement** toute valeur inconnue de `status` vers `"new"`. Écrire `lead.status = "qualified"` (comme le demandait littéralement le brief FIX 3) serait donc **perdu** à la lecture. C'est pourquoi FIX 3 applique les transitions sur `customer_status` :

- `interested` → `customer_status = "prospect"` (qualifié) ✅
- `not_interested` → `customer_status = "lost"` ✅

**Recommandation.**
- 🟠 Renommer `status` → `score_bucket` (clarté), ou au minimum documenter les deux champs dans le modèle.
- 🟠 Remplacer la coercion silencieuse de `_safe_status()` par un log `warning` quand une valeur inattendue est rencontrée (détecter les bugs au lieu de les masquer).

---

## 2. Autres problèmes détectés pendant le Sprint A

| # | Sévérité | Problème | Détail | Statut |
|---|---|---|---|---|
| 2.1 | 🟠 | Permission `crm.leads.update` **inutilisée** | La permission existe ([permissions.py](../../backend/app/core/permissions.py)) et est accordée à `role_sales`, mais **aucun endpoint `PATCH /crm/leads/{id}`** n'existe. La « modification lead » se fait indirectement (réponse client, conversion). | Non corrigé |
| 2.2 | 🟠 | Coercion silencieuse `_safe_status()` | Voir §1. Perte de données potentielle sans trace. | Non corrigé |
| 2.3 | 🟢 | Deux chemins de création de tâche | `crm_tasks_service.create_task()` (ne pose pas `task_type`) vs création directe dans `crm_responses_service` (pose `task_type='follow_up'`). Cohérent fonctionnellement mais code dupliqué. | Connu |
| 2.4 | 🟢 | `DEFAULT_LEAD_ID = 'lead_001'` | [CRMLeadDetailsPage.tsx](../../frontend/src/pages/CRMLeadDetailsPage.tsx) retombe sur `lead_001` si `?leadId=` absent → peut afficher un lead arbitraire. | Connu |
| 2.5 | 🟢 | Drift de type JSON / JSONB | `audit_log.details` est `JSON` côté modèle (create_all dev) et `JSONB` côté migration SQL (prod Postgres). Sans impact fonctionnel, mais à harmoniser. | Connu (introduit en A4, assumé) |
| 2.6 | 🟢 | Bouton « Approuver **et** envoyer » non fusionné | Le brief FIX 1 suggérait un bouton unique ; l'implémentation garde `approve` puis `send` en 2 étapes (voir §3, séparation des rôles). | Décision validée |
| 2.7 | ✅ | Bouton « Enregistrer » des tâches inopérant | `ActionButton` rendait `type="button"` dans un `<form onSubmit>`. **Corrigé** en A1 (FIX 2). | Corrigé |

**Gestion d'erreur backend.** Aucun `except` silencieux (`except Exception: pass`) détecté dans `crm_service.py` : tout est `SQLAlchemyError → HTTPException(500)` avec `logger.exception`. La seule absorption volontaire d'erreur est `audit_service.log_activity()` (best-effort **documenté** : l'audit ne doit jamais casser l'action métier).

---

## 3. Permissions CRM — cohérence

Matrice des permissions CRM par rôle (source : [permissions.py](../../backend/app/core/permissions.py)) :

| Permission | admin | manager | sales | hr |
|---|:--:|:--:|:--:|:--:|
| `crm.leads.view` | ✅ | ✅ | ✅ | — |
| `crm.leads.create` | ✅ | — | ✅ | — |
| `crm.leads.update` | ✅ | — | ✅ | — |
| `crm.interactions.create` | ✅ | ✅ | ✅ | — |
| `crm.drafts.generate` | ✅ | — | ✅ | — |
| `crm.drafts.review` | ✅ | ✅ | ✅ | — |
| `crm.email.approve` | ✅ | ✅ | **—** | — |
| `crm.email.send` | ✅ | **—** | ✅ | — |
| `crm.customer.convert` | ✅ | ✅ | **—** | — |
| `crm.tasks.view/manage` | ✅ | ✅ | ✅ | — |
| `crm.deals.view/manage` | ✅ | ✅ | ✅ | — |

**Analyse.**

- 🟠 **Séparation des pouvoirs approve/send.** `manager` peut **approuver** mais **pas envoyer** ; `sales` peut **envoyer** mais **pas approuver**. Conséquence : **aucun de ces deux rôles seul** ne peut mener un email de `reviewed` → `sent`. C'est défendable comme contrôle « 4 yeux » (le manager valide, le commercial envoie), mais **à confirmer comme intentionnel** — sinon c'est un blocage. Seul `admin` est autonome de bout en bout.
- 🟢 **`sales` ne peut pas convertir en client** (`crm.customer.convert` réservé manager/admin). Cohérent avec un contrôle hiérarchique sur la conversion.
- ✅ **Isolation par commercial** correcte : `crm_scoped_owner_id()` restreint `role_sales` à ses propres leads/tâches/deals ; admin/manager ont la visibilité complète.
- ✅ **`hr` n'a aucun accès CRM** — normal, et l'audit feed (A4) le confine aux activités RH.

**Recommandation.** Trancher explicitement le point approve/send : soit documenter le contrôle « 4 yeux », soit donner `crm.email.send` au manager (et/ou `crm.email.approve` au sales) pour des rôles autonomes.

---

## 4. Endpoints deprecated

Aucun endpoint **CRM** n'est marqué `deprecated`. Les endpoints deprecated concernent le module **Congés** (ancien flux Odoo), remplacés par le flux **standalone** :

| Endpoint deprecated | Remplaçant standalone | Reco |
|---|---|---|
| `POST /leave-requests` | `POST /leave-requests/standalone` | Garder jusqu'à soutenance |
| `POST /leave-requests/{id}/approve` | `POST /leave-requests/{id}/approve-standalone` | Garder jusqu'à soutenance |
| `POST /leave-requests/{id}/reject` | `POST /leave-requests/{id}/reject-standalone` | Garder jusqu'à soutenance |
| `POST /leave-requests/{id}/automation-analysis` | `POST /n8n/leave-standalone/analysis-complete` | Garder jusqu'à soutenance |
| `POST /leave-requests/{id}/decision-sync-result` | `POST /n8n/leave-standalone/decision-complete` | Garder jusqu'à soutenance |

**Recommandation.**
- **Avant soutenance** : ne **rien supprimer** (instruction du sprint respectée — ces endpoints sont restés intouchés, y compris pour l'instrumentation d'audit qui ne cible que les routes standalone).
- **Après soutenance** : supprimer ces 5 routes + le code Odoo associé une fois le flux standalone validé en conditions réelles. Vérifier au préalable qu'aucun workflow n8n actif ne les appelle encore.

---

## 5. Workflows n8n CRM — robustesse

Inventaire de la résilience (sources : `workflows/crm/*.json`, [README_STEP1_PATCHES.md](../../workflows/crm/README_STEP1_PATCHES.md)) :

| Workflow | `retryOnFail` | `continueOnFail` | Error Workflow | Remarque |
|---|:--:|:--:|:--:|---|
| `CRM_00_Error_Handler` | n/a | n/a | n/a | Capte les échecs WF01-04 → `POST /crm/webhook/error-log` |
| `FP_CRM_01` Lead Intake | ✅ | ✅ | ✅ | OK |
| `FP_CRM_02` Communication Draft | ✅ | **🟠 absent** | ✅ | Callback draft sans `continueOnFail` |
| `FP_CRM_03` Human Conversion | ✅ | **🟠 absent** | ✅ | Callback conversion sans `continueOnFail` |
| `FP_CRM_04` Approved Email Send | ✅ | ✅ | ✅ | OK |
| `FP_CRM_05` Nurturing / Trigger | partiel | **🟠 absent** | ? | À vérifier |
| `FP_CRM_06` Task Reminder | ✅ | ✅ | ✅ | OK |
| `FP_CRM_07` Deal Pipeline | ✅ | ✅ | ✅ | OK |
| `FP_CRM_08` Weekly Reporting | ✅ | ✅ | ✅ | OK |
| `FP_CRM_99` Outbox Drain | — | **🟠 absent** | ? | À vérifier |

**Constats.**
- ✅ La couche `retryOnFail` (3 essais / 5 s) + Error Handler global couvre l'essentiel des appels HTTP sortants.
- 🟠 **`continueOnFail` manquant sur WF02 et WF03** : si le callback vers le backend échoue après les retries, le workflow tombe en erreur (rattrapé par l'Error Handler, mais l'étape suivante n'est pas exécutée). Pour un callback **non critique** (ex. trace d'interaction), un `continueOnFail` éviterait d'avorter tout le flux.
- 🟠 **Côté backend, le filet de sécurité est le `webhook_outbox`** : les leads/déclenchements passent par une file durable (`/crm/webhook/process-outbox`, drainé par WF99), donc une indisponibilité n8n momentanée n'est pas perdante. WF99 lui-même n'a pas de `continueOnFail` → à vérifier.

**Recommandation (post-PFE).**
- Ajouter `continueOnFail: true` sur les nodes de callback **non bloquants** de WF02/WF03.
- Confirmer l'`Error Workflow` lié sur WF05 et WF99 (l'import n8n peut réattribuer les IDs — cf. README §3).
- Tester l'Error Handler de bout en bout (procédure du README §« How to test »).

---

## 6. Recommandations post-PFE

Hors périmètre Sprint A (volontairement non faits), utiles pour une version production :

1. **Unifier le statut lead.** Renommer `status` → `score_bucket` et faire de `customer_status` la **seule** source de vérité du cycle de vie (machine à états explicite). Supprimer la coercion silencieuse.
2. **Endpoint `PATCH /crm/leads/{id}`.** Matérialiser la permission `crm.leads.update` (édition nom/email/valeur estimée/owner) + instrumentation audit `action="updated"`.
3. **Audit log — montée en charge.** Pagination/scroll infini, filtre par utilisateur, rétention/purge (TTL), et passage `details` en `JSONB` partout (harmoniser modèle ↔ migration).
4. **Trancher la séparation approve/send** (§3) et documenter la politique de rôles CRM.
5. **Workflows n8n.** `continueOnFail` sur callbacks non critiques (WF02/03/99), supervision des exécutions échouées via la page « Automatisations ».
6. **Nettoyage Congés.** Retirer les 5 endpoints deprecated + code Odoo une fois le standalone validé.
7. **Tests.** Ajouter des tests d'intégration sur les nouveautés Sprint A : réponses client (transitions `customer_status`, création de tâche), et audit log (scoping par rôle admin/manager/hr/sales).
8. **UX feedback.** Généraliser le pattern loading/success/error (déjà présent sur la plupart des écrans) et corriger le fallback `DEFAULT_LEAD_ID`.

---

### Annexe — livrables Sprint A (rappel)

| Sprint | Objet | Statut |
|---|---|---|
| A1 | FIX 2 — date tâche relance (bouton `type="submit"` + feedback) | ✅ |
| A2 | FIX 1 — workflow mail approbation (déjà implémenté, non reconstruit) | ✅ (vérifié) |
| A3 | FIX 3 — réponse client (`crm_lead_responses` + endpoints + UI + transitions) | ✅ |
| A4 | FIX 4 — audit log / page `/activities` (table + service + instrumentation + UI) | ✅ |
| A5 | FIX 5 — ce rapport | ✅ |
