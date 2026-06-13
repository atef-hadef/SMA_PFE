# Validation finale — Processus Demande de congé

## 1. Objectif du processus

Le processus de Demande de congé de FlowPilot AI permet à un employé de soumettre une demande d’absence via une interface métier simple, tout en appliquant des règles de gestion avant toute création locale ou synchronisation externe.

Dans cette version MVP, FlowPilot vérifie d’abord la cohérence de la demande, notamment le solde disponible et les chevauchements de périodes. Si la demande est valide, elle est ensuite créée localement, analysée par les workflows n8n, synchronisée avec Odoo, puis transmise au manager pour approbation. Le processus garantit ainsi une validation métier en amont, une traçabilité complète et une orchestration humaine assistée.

## 2. Architecture globale

Le flux final validé est le suivant :

```text
React LeaveRequestPage
→ FastAPI POST /api/leave-requests
→ n8n Workflow 0 Balance Precheck
→ PostgreSQL : création locale uniquement si la demande est valide
→ n8n Workflow 1 Request Analysis / Odoo creation
→ ManagerApprovalPage
→ n8n Workflow 2 Manager Decision Sync
→ Odoo approval/refusal synchronization
→ historique des décisions
```

Ce flux montre que FlowPilot AI n’est pas un simple formulaire connecté à un ERP. L’application joue le rôle de couche d’orchestration métier : elle filtre les demandes non conformes, prépare les demandes valides pour les workflows, puis centralise l’historique des décisions et des synchronisations.

## 3. Rôle des composants

### Frontend

- LeaveRequestPage : formulaire salarié et affichage des messages de blocage métier.
- ManagerApprovalPage : interface de décision pour le manager.
- Dashboard : vue d’ensemble métier et suivi global du processus.

### FastAPI

- Couche API centrale du processus.
- Appelle n8n pour les étapes automatisées.
- Contrôle la création en PostgreSQL.
- Empêche l’enregistrement local des demandes invalides.
- Retourne des erreurs métier explicites au frontend.

### PostgreSQL

- Stocke les demandes de congé valides.
- Stocke les traces de workflow.
- Stocke l’historique des décisions manager.

### n8n

- Workflow 0 : précontrôle du solde et des chevauchements.
- Workflow 1 : analyse de la demande valide et création côté Odoo.
- Workflow 2 : synchronisation de la décision manager avec Odoo.

### Odoo

- Source RH du solde de congés.
- Source RH des congés déjà existants.
- Système RH final pour les demandes approuvées ou refusées.

## 4. Workflow 0 — Balance Precheck

Workflow 0 est exécuté avant toute création locale de leave_request. Son rôle est de valider la demande en amont et de bloquer immédiatement les cas non conformes.

Il lit les allocations Odoo et les congés existants dans Odoo, puis calcule les indicateurs métier suivants :

- total allocated days
- leaves already taken
- available days
- requested days
- balance gap
- overlap with existing/pending leaves

Ce workflow renvoie un résultat de type ok=true ou ok=false. Il ne crée rien en base et ne déclenche aucune écriture Odoo. Il s’agit d’un précontrôle métier strictement non persistant.

Règles métier appliquées :

- un solde insuffisant bloque la demande ;
- un chevauchement avec un congé du même employé bloque la demande ;
- une demande valide continue vers Workflow 1.

## 5. Workflow 1 — Request Analysis

Workflow 1 est déclenché uniquement lorsque Workflow 0 a retourné ok=true.

Ce workflow :

- crée le congé côté Odoo ;
- envoie un callback d’automation-analysis à FastAPI ;
- prépare la demande pour l’approbation manager ;
- conserve une branche de rejet métier uniquement comme filet de sécurité si l’analyse ou la création échoue.

Cette étape marque le passage d’une demande validée métier vers un objet RH exploitable dans le circuit d’approbation.

## 6. Workflow 2 — Manager Decision Sync

Workflow 2 est déclenché uniquement après qu’un manager a approuvé ou refusé une demande valide déjà liée à Odoo.

Il nécessite un odoo_leave_id afin d’assurer la cohérence entre la demande locale et l’enregistrement RH distant. Ensuite, il appelle l’action Odoo appropriée : action_approve ou action_refuse, puis transmet un callback decision-sync-result à FastAPI.

Ce workflow garantit que la décision humaine est propagée vers le système RH de référence et que l’historique local reste synchronisé.

## 7. Règles métier validées

### Règle 1 : solde insuffisant

Exemple :

- available_days = 13
- requested_days = 24

Résultat attendu :

- HTTP 422
- code INSUFFICIENT_LEAVE_BALANCE
- no local leave_request
- no Workflow 1
- no Odoo leave
- employee sees insufficient balance message

### Règle 2 : période chevauchante

Exemple :

- requested period = 12/05/2026 to 14/05/2026
- existing leave = 13/05/2026 to 15/05/2026

Résultat attendu :

- HTTP 422
- code LEAVE_PERIOD_OVERLAP
- no local leave_request
- no Workflow 1
- no Odoo leave
- employee sees reserved period date

### Règle 3 : demande valide

Exemple :

- enough balance
- no overlap

Résultat attendu :

- Workflow 0 ok=true
- local leave_request created
- Workflow 1 triggered
- Odoo leave created
- request appears in ManagerApprovalPage
- manager can approve/reject
- Workflow 2 syncs decision with Odoo

## 8. Tests de validation

Les tests ci-dessous résument la validation finale du processus.

| Test | Données utilisées | Résultat attendu | Résultat obtenu | Statut |
|---|---|---|---|---|
| Test solde insuffisant | available_days = 13, requested_days = 24 | HTTP 422, code INSUFFICIENT_LEAVE_BALANCE, aucune création locale, aucun congé Odoo | Conforme à l’attendu lors du smoke test | Validé |
| Test période déjà réservée | Période demandée 12/05/2026 au 14/05/2026, congé existant 13/05/2026 au 15/05/2026 | HTTP 422, code LEAVE_PERIOD_OVERLAP, aucune création locale, aucun congé Odoo | Conforme à l’attendu lors du smoke test | Validé |
| Test demande valide + approbation manager | Solde suffisant, aucune collision, décision manager = approve | Workflow 0 ok=true, création locale, Workflow 1, approbation manager, synchronisation Odoo | Conforme à l’attendu lors du smoke test | Validé |
| Test demande valide + refus manager | Solde suffisant, aucune collision, décision manager = reject | Workflow 0 ok=true, création locale, Workflow 1, refus manager, synchronisation Odoo | Conforme à l’attendu lors du smoke test | Validé |
| Test historique décisions | Demande validée puis décision manager enregistrée | Historique consultable et décision tracée | Conforme à l’attendu lors du smoke test | Validé |
| Test absence de création locale pour demandes bloquées | Demande bloquée par solde ou chevauchement | Aucun leave_request local créé | Conforme à l’attendu lors du smoke test | Validé |

## 9. Valeur ajoutée de FlowPilot par rapport à Odoo seul

Odoo sait gérer les absences, mais FlowPilot ajoute une couche d’orchestration intelligente et métier au-dessus du système RH.

Concrètement, FlowPilot :

- bloque les demandes invalides avant leur création ;
- explique au salarié pourquoi sa demande est refusée ;
- évite de solliciter inutilement le manager pour des cas déjà non conformes ;
- centralise la supervision du processus métier ;
- relie le processus RH à une logique de monitoring multi-workflows ;
- propose une interface simplifiée pour les employés et les managers.

Cette approche transforme Odoo en système de référence RH, tandis que FlowPilot devient la couche de décision, de prévalidation et de pilotage.

## 10. Touche IA / Data Science

Dans la version MVP, l’intelligence repose sur des règles métier automatisées, des recommandations explicables et une orchestration multi-agents. Des modèles prédictifs peuvent être ajoutés en perspective.

Les mécanismes déjà présents ou préparés dans l’architecture couvrent :

- la logique de recommandation métier ;
- l’évaluation du niveau de risque ;
- l’explication de la décision ;
- l’évaluation des règles métier ;
- la décision manager avec human-in-the-loop.

À moyen terme, FlowPilot peut intégrer des améliorations de type machine learning, par exemple :

- prédiction des absences ;
- score de conflit de charge ;
- risque de disponibilité d’équipe ;
- recommandation personnalisée de congé.

Ces axes constituent une évolution possible, mais ils ne doivent pas être présentés comme déjà entraînés ou déjà déployés dans le MVP validé.

## 11. Limitations MVP

La validation finale confirme le bon fonctionnement du processus, mais certaines limites restent connues dans cette version MVP :

- le mapping user/employee est encore simplifié ou partiellement codé en dur ;
- le contrôle des rôles et des permissions peut être renforcé ;
- il n’y a pas encore de prédiction ML avancée ;
- le processus dépend de la disponibilité d’Odoo ;
- les permissions d’audit de niveau entreprise ne sont pas encore complètes ;
- le monitoring des workflows peut être enrichi.

Ces limites n’empêchent pas la validation fonctionnelle du processus, mais elles doivent être prises en compte pour une montée en puissance vers une version production.

## 12. Conclusion

Le processus Leave Request est validé comme MVP.

Cette validation démontre de manière concrète :

- l’automatisation du flux métier ;
- l’intégration avec Odoo ;
- la prévalidation des demandes ;
- l’aide à la décision ;
- l’approbation manager ;
- la traçabilité des actions ;
- un fonctionnement human-in-the-loop.

FlowPilot AI fournit ainsi une orchestration métier crédible et démontrable pour la gestion des congés, avec une valeur ajoutée claire par rapport à Odoo seul.
