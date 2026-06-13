# Documentation technique — Assistant IA FlowPilot

> Document de référence pour la soutenance PFE.
> Basé **uniquement** sur le code réel du projet (noms de fichiers, fonctions et valeurs cités tels qu'ils existent).

**Fichiers sources analysés :**
- `backend/app/services/assistant_service.py` — classification d'intentions + orchestration
- `backend/app/services/assistant_tools.py` — outils de lecture des données (read-only)
- `backend/app/services/openui_service.py` — génération du dashboard (Mistral + fallback)
- `backend/app/schemas/assistant.py` — types de données (Pydantic)
- `backend/app/api/assistant.py` — endpoints HTTP + RBAC
- `backend/app/core/config.py` — configuration (clés, modèles, timeouts)
- `frontend/src/pages/AssistantPage.tsx` — interface de chat plein écran
- `frontend/src/components/assistant/openuiLibrary.tsx` — bibliothèque de composants visuels
- `frontend/src/components/assistant/OpenUIRenderer.tsx` — moteur de rendu + sécurité d'affichage

---

## SECTION 1 — Vue d'ensemble du système

### Ce que fait l'assistant IA dans FlowPilot

L'assistant IA de FlowPilot est un **assistant décisionnel conversationnel**. L'utilisateur pose une question **en langage naturel français** (ex. « Donne-moi un résumé CRM ») et reçoit en retour un **dashboard visuel dynamique** : cartes d'indicateurs (KPI), graphiques (donut, barres, entonnoir), tableaux, observations et recommandations, avec des boutons d'action.

Il couvre **trois domaines métier** :
1. **CRM** (leads commerciaux : pipeline, priorités, conversion, valeur, relances, brouillons d'e-mail, comparaison hebdomadaire) ;
2. **Congés / RH** (demandes, statuts, approbations, blocages, taux d'approbation) ;
3. **Automatisations** (santé des workflows n8n : succès / échecs / en attente).

### Les 3 grandes étapes de chaque réponse

```
1) COMPRENDRE   →  2) LIRE LES DONNÉES   →  3) PRÉSENTER
   (classer la       (outils backend            (Mistral conçoit le
    question en        en lecture seule           dashboard, le frontend
    « intention »)     sur PostgreSQL)            l'affiche en split-screen)
```

1. **Comprendre** : la question est classée dans une **intention** (`intent`) par des règles déterministes (expressions régulières) — fonction `_classify_intent` dans `assistant_service.py`.
2. **Lire les données** : l'intention déclenche **un outil backend** précis (ex. `get_crm_summary`) qui calcule de **vrais chiffres** depuis PostgreSQL, en **lecture seule**.
3. **Présenter** : ces chiffres sont envoyés à **Mistral** (via OpenRouter) qui **conçoit la mise en page** du dashboard en JSON ; le backend convertit ce JSON en composants ; le frontend React l'affiche.

### Pourquoi c'est différent d'un chatbot classique

| Chatbot classique | Assistant FlowPilot |
|---|---|
| Le LLM répond du texte libre | Le LLM ne produit **que la présentation** (UI), jamais les chiffres |
| Le LLM peut « inventer » des données | Les chiffres viennent **uniquement des outils backend** (PostgreSQL) |
| Le LLM a parfois accès à la base | Le LLM **ne voit jamais** la base ni le SQL — il reçoit un dictionnaire déjà calculé |
| Réponse = texte | Réponse = **dashboard génératif** (KPI, graphiques, tableaux) façon Generative UI / Thesys |
| Pas de garde-fou | **Fallback déterministe** si le LLM échoue + **RBAC** par permission |

---

## SECTION 2 — Les intentions (intents)

> Les intentions sont définies dans le type `AssistantIntent` (`backend/app/schemas/assistant.py`).
> **Décompte exact dans le code :** **18 intentions métier** + **3 intentions « méta »** = **21 valeurs**.
> *(Le projet comptait 17 intentions métier à l'origine ; `crm_comparison` a été ajouté ensuite, ce qui porte le total à 18.)*

La classification se fait dans `_classify_intent()` qui teste, **dans l'ordre**, la liste `_INTENT_PATTERNS` (regex). **La première règle qui correspond gagne.** Si aucune ne correspond → `unknown`.

Le routage intention → outil se fait via le dictionnaire `_TOOL_REGISTRY`.

### Intentions CRM (8)

| Intent | Questions déclenchantes (extraits réels des regex) | Outil appelé | Résultat |
|---|---|---|---|
| `crm_comparison` | « **compare** cette semaine », « semaine **précédente** / dernière », « évolution hebdomadaire », « **vs** » | `get_crm_comparison` | Comparaison **J-7 vs J-7→J-14** : nouveaux leads, leads prioritaires, **deltas calculés côté backend** (fonction `_format_delta`) + bar chart |
| `crm_priority_analysis` | « **priorité** », « leads **prioritaires** », « leads **chauds** », « **hot leads** », « urgents » | `get_crm_priority_analysis` | Répartition par priorité (high/medium/low) + tableau des leads haute priorité triés par score |
| `crm_status_distribution` | « **statut** » + « lead/crm/pipeline », « répartition », « distribution » | `get_crm_status_distribution` | Leads par statut (hot/warm/cold) + répartition lead/prospect/client |
| `crm_conversion_analysis` | « **taux de conversion** », « conversion », « convertis », « **entonnoir** » | `get_crm_conversion_analysis` | KPI taux de conversion + entonnoir **Leads → Prospects → Clients** |
| `crm_followup_recommendations` | « **relance** », « prospects à relancer », « follow-up », « à contacter », « action commerciale » | `get_crm_followup_recommendations` | Tableau des prospects/leads actifs à relancer (classés par score) |
| `crm_draft_review_summary` | « **brouillon** / draft », « à valider », « e-mails générés », « validation crm » | `get_crm_draft_review_summary` | Brouillons d'e-mail en attente de validation humaine + répartition par statut |
| `crm_value_analysis` | « **valeur** », « valeur commerciale », « montant », « chiffre d'affaires », « revenue » | `get_crm_value_analysis` | KPI valeur totale du pipeline + top leads par valeur estimée |
| `crm_summary` | « **résumé / synthèse / bilan / analyse CRM** » + « crm/leads/pipeline » ; aussi fallback CRM large (« lead », « score », « contact »…) | `get_crm_summary` | Vue d'ensemble : KPI (total, priorité, prospects, clients, conversion) + graphiques + tableau |

### Intentions Congés / RH (7)

| Intent | Questions déclenchantes | Outil appelé | Résultat |
|---|---|---|---|
| `leave_pending_approvals` | « attendent le **manager** », « en attente d'approbation », « décision manager », « combien attendent » | `get_leave_pending_approvals` | KPI + tableau des demandes en attente de décision managériale |
| `leave_block_reasons` | « pourquoi **bloqué** », « raisons de refus », « motifs de refus », « demandes bloquées » | `get_leave_block_reasons` | Tableau des demandes refusées par politique RH (`rejected_by_policy`) + raison |
| `leave_balance_block_analysis` | « **solde** », « solde insuffisant », « jours disponibles/restants », « balance » | `get_leave_balance_block_analysis` | Demandes bloquées car jours demandés > solde disponible (écart chiffré) |
| `leave_overlap_block_analysis` | « **chevauchement** », « overlap », « conflits de dates » | `get_leave_overlap_block_analysis` | Demandes bloquées pour conflit de dates |
| `leave_approval_rate` | « **taux d'approbation** », « taux d'accord/refus », « pourcentage approuvé » | `get_leave_approval_rate` | KPI taux d'approbation + répartition décisions (approuvées/refusées/en attente) |
| `leave_status_distribution` | « **statut** » + « congé/demande/absence », « répartition » | `get_leave_status_distribution` | Demandes par statut + par type de congé |
| `leave_summary` | « **analyse/bilan/résumé des congés** » ; aussi fallback Congés large (« congé », « absence », « rh », « leave »…) | `get_leave_summary` | Vue d'ensemble congés : total, en attente, approuvées, refusées, bloquées + graphiques |

### Intentions Business / global (3)

| Intent | Questions déclenchantes | Outil appelé | Résultat |
|---|---|---|---|
| `automation_health` | « **santé des automatisations** », « monitoring », « **workflows** », « n8n », « exécutions », « succès…échecs » | `get_automation_health` | KPI succès / échecs / en attente + bar chart + carte `WorkflowHealthCard` |
| `today_actions` | « **aujourd'hui** », « actions du jour », « que dois-je faire », « priorités du jour » | `get_today_actions` | Actions prioritaires : hot leads, brouillons à valider, congés en attente |
| `business_summary` | « tableau de bord **global/général** », « situation générale », « résumé **global** », « kpi globaux » | `get_business_summary` | Synthèse **CRM + Congés** combinée (KPI + tableaux) — uniquement si demande explicitement globale |

### Intentions « méta » (3) — pas d'outil de données

| Intent | Détection | Traitement |
|---|---|---|
| `general` | « bonjour », « salut », « aide », « que peux-tu faire » | LLM **texte** grounded (`_try_llm_fallback`) ou réponse statique |
| `out_of_scope` | « trigger », « agent ia », « bot », « météo », « news », « logs » | Redirection polie **statique** vers CRM / Congés (pas d'appel LLM) |
| `unknown` | Aucune règle ne correspond | LLM **texte** grounded ou message « Je n'ai pas compris, reformulez » |

---

## SECTION 3 — Le flux technique complet

Exemple suivi : l'utilisateur tape **« Donne-moi un résumé CRM »**.
Point d'entrée : `process_chat()` dans `assistant_service.py` (appelé par l'endpoint `POST /assistant/chat`).

### Étape 1 — Classification de l'intent
- **Fichier / fonction :** `assistant_service.py` → `_classify_intent(message)`
- **Entrée :** la chaîne `"Donne-moi un résumé CRM"`
- **Mécanisme :** parcours de `_INTENT_PATTERNS` (liste de regex). « résumé » + « crm » correspond à la règle `crm_summary`.
- **Sortie :** `intent = "crm_summary"`
- **Puis :** `_resolve_authorized_intent(intent, permissions)` vérifie les droits (voir Section 5). Avec `crm.leads.view`, l'intention est conservée.
- **Si échec :** si aucune regex ne matche → `unknown` → bascule LLM texte. Si pas la permission → message « Votre rôle ne permet pas d'analyser ce domaine ».

### Étape 2 — L'outil backend (lecture des données)
- **Fichier / fonction :** `assistant_service.py` → `_call_tool()` qui appelle `get_crm_summary(db)` (dans `assistant_tools.py`) via `_TOOL_REGISTRY`.
- **Entrée :** la session SQLAlchemy `db` (injectée par l'API).
- **Ce qu'il récupère (read-only, aucune écriture) :** total leads, leads haute priorité (`priority == "high"`), prospects, clients (`customer_status`), brouillons en attente, taux de conversion, répartition par statut et par priorité, top leads.
- **Sortie :** un `ToolResult` (TypedDict) = `summary`, `metrics`, `visualizations`, `sources`, `suggested_actions`.
- **Si échec :** chaque requête est protégée (`_safe_scalar`, `_safe_scalars`, `try/except SQLAlchemyError` + `db.rollback()`). Si la base est indisponible, l'outil renvoie des valeurs neutres et `process_chat` retombe sur un texte statique (`_STATIC_ANSWERS`).

### Étape 3 — L'appel à Mistral (conception du dashboard)
- **Fichier / fonction :** `openui_service.py` → `build_openui_response()` → `generate_dashboard_with_llm()`
- **Ce qu'on envoie exactement à Mistral :**
  - un **system prompt** (`_DASHBOARD_SYSTEM_PROMPT`) décrivant le contrat JSON strict + les composants autorisés + les règles ;
  - un **user message** JSON = `{ "question", "intent", "permissions", "data" }`, où `data` = `_serialize_response_for_llm(response)` (la réponse déjà calculée : `answer`, `visualizations`, `suggested_actions`, `sources`). **Jamais de SQL, jamais d'accès base.**
- **Paramètres réels de l'appel** (HTTP `POST {OPENROUTER_BASE_URL}/chat/completions`) :
  - `model` = `settings.OPENUI_MODEL or settings.OPENROUTER_MODEL` → **`mistralai/mistral-small-3.2-24b-instruct`**
  - `response_format = {"type": "json_object"}` → **force du JSON pur** (JSON mode)
  - `temperature = 0.2` → réponses **cohérentes/peu créatives**
  - `max_tokens = 2000` (constante `LLM_DASHBOARD_MAX_TOKENS`)
  - `timeout = 15.0` s (constante `LLM_DASHBOARD_TIMEOUT_SECONDS`), client **`httpx`**
- **Si échec :** toute exception (timeout, erreur HTTP, clé absente, `httpx` indisponible) → `generate_dashboard_with_llm` **retourne `None`** et logge un warning (`logger.warning(...)`). Aucun crash.

### Étape 4 — Génération du JSON dashboard
- Mistral renvoie un objet JSON : `{ "title", "summary", "sections": [ { "title", "components": [ {composants} ] } ] }`.
- Chaque composant porte un champ `"type"` (ex. `"kpi_grid"`, `"bar_chart"`, `"insight_list"`…).
- **Si échec :** si la réponse n'est pas du JSON valide → `json.loads` lève `JSONDecodeError` → warning + `None` (fallback).

### Étape 5 — Validation et conversion Python (JSON → OpenUI Lang)
- **Fichier / fonction :** `openui_service.py` → `_dashboard_json_to_openui(payload)` + `_node_to_openui(node)`
- **Mécanisme :** chaque `"type"` est cherché dans la **whitelist** `_COMPONENT_BUILDERS` (17 types autorisés). Un `type` inconnu est **silencieusement ignoré** (sécurité). Les tableaux passent par `_sanitize_rows` (suppression des IDs techniques) ; les sources par `_friendly_source` (libellés lisibles, dédoublonnés).
- **Sortie :** une chaîne **OpenUI Lang** : `root = AssistantDashboard("…", "…", [DashboardSection(…)])`.
- **Garde-fou :** `_looks_like_openui()` vérifie que la sortie contient bien `root =` et `AssistantDashboard(`. Sinon → `None` (fallback).
- **Si échec :** `build_openui_response` appelle alors `_build_deterministic_openui()` (templates Python fixes) qui reconstruit un dashboard équivalent sans LLM.

### Étape 6 — Le rendu React côté frontend
- **Fichiers :** `AssistantPage.tsx` → `OpenUIRenderer.tsx` → `openuiLibrary.tsx`
- `process_chat` renvoie un `AssistantChatResponse` avec `display_mode = "openui"` et `openui_content` (la chaîne OpenUI Lang), `openui_version = "0.5"`.
- `AssistantPage` (composant `AssistantAnalysisCard`) détecte `display_mode === "openui"` et monte `<OpenUIRenderer>`.
- `OpenUIRenderer` parse la chaîne avec `<Renderer>` (`@openuidev/react-lang`) et la bibliothèque `flowPilotOpenUILibrary`.
- Le composant racine `AssistantDashboard` (`AssistantDashboardRenderer`) répartit les composants en **split-screen** : texte d'analyse à gauche (40 %), dashboard visuel à droite (60 %), actions/sources en bas.
- **Si échec :** `OpenUIErrorBoundary` (React error boundary) capte toute erreur de rendu et appelle `onInvalidContent`, ce qui bascule `AssistantPage` sur le rendu **legacy** `AssistantChartRenderer` (graphiques en Tailwind pur). Pas d'écran blanc.

### Schéma du flux

```
Utilisateur ─▶ POST /assistant/chat ─▶ process_chat()
                                          │
         _classify_intent()  ──▶ "crm_summary"
                                          │
         _resolve_authorized_intent(permissions)  (RBAC)
                                          │
         _call_tool() ─▶ get_crm_summary(db)  ─▶ ToolResult (chiffres réels)
                                          │
         AssistantChatResponse (answer, visualizations, sources, actions)
                                          │
         build_openui_response(permissions)
              │
              ├─▶ generate_dashboard_with_llm()  ── Mistral (JSON mode, 0.2, 15s)
              │        └─ _dashboard_json_to_openui()  (whitelist 17 types)
              │                 └─ "root = AssistantDashboard(...)"
              │
              └─(si None)▶ _build_deterministic_openui()   (templates fixes)
                                          │
         Réponse JSON (display_mode=openui, openui_content)
                                          ▼
Frontend: AssistantPage ─▶ OpenUIRenderer ─▶ AssistantDashboardRenderer (split-screen)
                                  └─(si erreur)▶ AssistantChartRenderer (legacy)
```

---

## SECTION 4 — Les composants OpenUI

> Définis dans `frontend/src/components/assistant/openuiLibrary.tsx` (via `defineComponent` + `createLibrary`).
> **22 composants** sont enregistrés. Mistral, lui, émet du JSON avec **17 `type` autorisés** (whitelist `_COMPONENT_BUILDERS` côté backend), qui sont convertis vers ces composants.

| Composant (React) | `type` JSON Mistral | Ce qu'il affiche | Quand Mistral le choisit |
|---|---|---|---|
| `AssistantDashboard` | *(racine)* | Le conteneur global + en-tête + split-screen | Toujours (racine obligatoire) |
| `DashboardSection` | *(section)* | Groupe titré de composants | Pour structurer (« Indicateurs », « Analyse »…) |
| `KpiGrid` | `kpi_grid` | Grille responsive de 2 à 6 KPI | Résumés / vues d'ensemble |
| `KpiCard` | *(dans kpi_grid)* | 1 carte KPI : valeur + détail + tendance ↑/↓ | Élément d'une grille KPI |
| `SingleMetricCard` | `single_metric` | 1 chiffre en grand (carte « hero ») | Questions « combien » (réponse courte) |
| `BarChartCard` | `bar_chart` | Barres horizontales dégradées + part % | Distributions, comparaisons |
| `LineChartCard` | `line_chart` | Courbe SVG avec aire dégradée | Tendances chronologiques |
| `PieChartCard` | `pie_chart` | **Donut SVG** + légende + total au centre | Répartitions (par statut, par type) |
| `FunnelChartCard` | `funnel_chart` | Entonnoir fuselé + taux de passage | Conversion Lead → Prospect → Client |
| `SmartDataTable` | `table` | Tableau générique (colonnes + lignes) | Données détaillées sans IDs techniques |
| `PriorityLeadTable` | `priority_lead_table` | Liste de leads (nom, score, statut, action) | Hot leads / leads à suivre |
| `AlertList` | `alert_list` | Liste d'alertes (puces, ton warning/danger) | Points d'attention, échecs |
| `InsightList` | `insight_list` | Observations factuelles (puces) | Section « Analyse » (faits) |
| `RecommendationList` | `recommendation_list` | Recommandations IA (puces **→**) | Conseils (jamais des certitudes) |
| `SuggestedActions` | `suggested_actions` | Boutons d'action (navigation / mutations) | Fin de dashboard (« Suite ») |
| `WorkflowHealthCard` | `workflow_health` | Synthèse succès / échecs / en attente | Santé des automatisations |
| `SourceList` | `source_list` | Sources lisibles (« Données CRM »…) | Toujours (traçabilité) |
| `TextBlock` | `text` | Bloc de texte / contexte | Explication libre |
| `EmptyState` | `empty_state` | Message « aucune donnée » | Tableaux/listes vides |
| `InsufficientDataState` | `insufficient_data` | « Volume trop faible pour une tendance » | Données insuffisantes |
| `ErrorState` | *(interne)* | Erreur générique sans détail technique | Cas d'erreur de rendu |
| `LoadingState` | *(interne)* | État de chargement | Pendant le streaming |

**Split-screen (côté frontend).** Dans `AssistantDashboardRenderer`, les composants sont triés :
- **`NARRATIVE_TYPES`** = `{ TextBlock, InsightList, RecommendationList, AlertList, InsufficientDataState, ErrorState }` → **colonne gauche** (analyse) ;
- **`FOOTER_TYPES`** = `{ SuggestedActions, SourceList }` → **bas, pleine largeur** ;
- tout le reste (KPI, graphiques, tableaux, WorkflowHealthCard…) → **colonne droite** (dashboard visuel).

---

## SECTION 5 — Sécurité et permissions

### Comment le JWT protège les endpoints
- Les deux endpoints (`POST /assistant/chat` et `POST /assistant/actions`, dans `api/assistant.py`) sont protégés par `Depends(require_permission("dashboard.view"))`.
- `require_permission` (dans `app/api/dependencies.py`) **valide le JWT** (token Bearer envoyé par le frontend via `apiClient.ts`, stocké sous `flowpilot_access_token`), reconstruit l'utilisateur (`AuthUser`) avec ses **permissions**, et refuse l'accès (**401/403**) si le token est invalide ou la permission absente.

### Le système RBAC (Role Based Access Control)
Au-delà du JWT, **chaque intention est re-filtrée par permission** dans `_resolve_authorized_intent()` (`assistant_service.py`) :

```
Intentions CRM          → exigent  "crm.leads.view"
Intentions Congés       → exigent au moins une de :
                          "leave.request.view_own", "leave.request.view_all",
                          "leave.request.create", "leave.request.approve"
automation_health       → exige   "workflow.monitor.view"
business / today / general → exigent CRM ET Congés
                          (sinon dégradation vers crm_summary OU leave_summary,
                           ou refus si aucun des deux)
```

Si l'utilisateur n'a pas le droit → réponse texte « Votre rôle ne permet pas d'analyser ce domaine ».

### Permissions présentes dans le code (10)
| Permission | Où / pourquoi |
|---|---|
| `dashboard.view` | Accès aux deux endpoints assistant (porte d'entrée) |
| `crm.leads.view` | Toutes les intentions CRM |
| `leave.request.view_own` | Intentions Congés (l'une suffit) |
| `leave.request.view_all` | Intentions Congés |
| `leave.request.create` | Intentions Congés |
| `leave.request.approve` | Intentions Congés |
| `workflow.monitor.view` | `automation_health` |
| `crm.drafts.generate` | Actions mutantes : `prepare_followups`, `generate_email_draft`, `create_task` |
| `crm.email.send` | Action mutante : `send_approved_email` |
| `workflow.executions.view` | Action mutante : `launch_report` |

Les **actions mutantes** (qui modifieraient la base, enverraient un e-mail, etc.) passent par `POST /assistant/actions` → `_required_permission_for_action()` qui exige la permission ci-dessus **et** une **confirmation humaine** (`payload.confirmed`). Dans cette version, elles renvoient `status="deferred"` (non exécutées automatiquement) : l'utilisateur doit utiliser l'écran métier sécurisé.

### Pourquoi le LLM ne voit jamais la base de données
- Les **chiffres sont calculés exclusivement** par les outils de `assistant_tools.py` (SQLAlchemy, lecture seule).
- Mistral ne reçoit **que le dictionnaire déjà calculé** (`_serialize_response_for_llm`) — **aucune connexion DB, aucune requête SQL, aucun identifiant technique**.
- Le commentaire d'en-tête de `openui_service.py` le formalise : *« It never queries PostgreSQL and never executes model-generated SQL. »*
- Le test `test_no_sql_access_in_openui_service` vérifie même que le code de `openui_service` ne contient ni `sqlalchemy`, ni `select(`, ni `Session`.
- Conséquence : le LLM **choisit la présentation**, **explique** et **recommande**, mais **ne peut pas inventer ni recalculer** un chiffre.

---

## SECTION 6 — Le système de fallback

L'assistant a **trois niveaux** de génération de réponse, du plus riche au plus robuste. Le but : **ne jamais planter**.

```
                    ┌──────────────────────────────────────────────┐
   Question  ─────▶ │ process_chat()  (classification + outil)     │
                    └──────────────────────────────────────────────┘
                                       │  AssistantChatResponse (chiffres réels)
                                       ▼
                    ┌──────────────────────────────────────────────┐
                    │ build_openui_response()                      │
                    └──────────────────────────────────────────────┘
                                       │
              ┌────────────────────────┴───────────────────────────┐
              ▼                                                     ▼
   ┌───────────────────────────┐                    ┌────────────────────────────┐
   │ NIVEAU 1 — Mistral (JSON) │  ── échec / None ─▶│ NIVEAU 2 — Templates fixes │
   │ generate_dashboard_with_llm│                    │ _build_deterministic_openui│
   │ → dashboard adaptatif      │                    │ → dashboard standard       │
   └───────────────────────────┘                    └────────────────────────────┘
              │                                                     │
              └────────────────────┬────────────────────────────────┘
                                   ▼  openui_content (OpenUI Lang)
                    ┌──────────────────────────────────────────────┐
                    │ Frontend: OpenUIRenderer                     │
                    └──────────────────────────────────────────────┘
                                   │
                                   ├─ rendu OK ─▶ split-screen dashboard
                                   │
                                   └─ erreur de rendu ─▶ NIVEAU 3 :
                                      AssistantChartRenderer (legacy, Tailwind)
```

### Les cas où le fallback se déclenche
`generate_dashboard_with_llm()` retourne `None` (→ on passe aux **templates fixes**) dans ces cas :
1. **`OPENUI_ENABLED = false`** dans la config (LLM désactivé) ;
2. **`OPENROUTER_API_KEY` vide** (pas de clé) ;
3. **`httpx` indisponible**, ou **timeout (15 s)** / **erreur HTTP** OpenRouter (crédit épuisé, modèle invalide, réseau) ;
4. **JSON invalide** renvoyé par le modèle (`json.loads` échoue), ou JSON converti qui **ne passe pas** `_looks_like_openui()`.

`build_openui_response()` renvoie aussi `None` (→ **affichage texte simple**) si l'intention est `out_of_scope`, `unknown` ou `general`.

Enfin, si le **rendu React** échoue, `OpenUIErrorBoundary` bascule sur le **rendu legacy**.

### Ce que l'utilisateur voit dans chaque cas
| Cas | Ce qui s'affiche |
|---|---|
| Niveau 1 OK (Mistral) | Dashboard **adaptatif** (mise en page conçue par le LLM, change selon la question) |
| Niveau 2 (templates) | Dashboard **standard** équivalent (mêmes chiffres, mise en page fixe) — l'utilisateur ne voit **pas** d'erreur |
| Niveau 3 (legacy) | Graphiques Tailwind « classiques » (`AssistantChartRenderer`) — toujours pas d'erreur |
| `out_of_scope` / `unknown` / `general` | Réponse **texte** (LLM texte grounded ou message statique) |
| Base indisponible | Texte statique de repli (`_STATIC_ANSWERS`) |

> Remarque : il existe **un second usage du LLM**, distinct, pour les intentions `general`/`unknown` uniquement : `_try_llm_fallback()` (dans `assistant_service.py`, via `assistant_llm.py`) génère une **réponse texte** grounded sur un instantané des données. Il est lui aussi en *graceful degradation* (retourne `None` si OpenRouter échoue).

---

## SECTION 7 — Questions / Réponses pour la soutenance

**Q1 — Combien d'intentions ton système reconnaît-il ?**
Le code définit **18 intentions métier** + **3 intentions « méta »** (`general`, `out_of_scope`, `unknown`), soit **21 valeurs** dans le type `AssistantIntent` (`schemas/assistant.py`). À l'origine il y en avait 17 ; j'ai ajouté `crm_comparison` (comparaison hebdomadaire), d'où 18. Sur les 18 métier : **8 CRM, 7 Congés, 3 Business**.

**Q2 — Comment fais-tu la classification d'intention ? Pourquoi pas un LLM ?**
Par **règles déterministes** : `_classify_intent()` parcourt `_INTENT_PATTERNS`, une liste de **regex** (avec `re.I | re.UNICODE` pour gérer les accents). La première qui matche gagne, l'ordre va du **plus spécifique au plus général**. C'est **rapide, gratuit, reproductible et prévisible** — essentiel pour la sécurité (on sait exactement quel domaine est ouvert). Le LLM n'intervient **que pour la présentation**, jamais pour décider quelles données lire.

**Q3 — Quelle est la température Mistral et pourquoi ?**
`temperature = 0.2` (dans `generate_dashboard_with_llm`). Une température basse rend la sortie **cohérente et peu créative** : on veut une mise en page fiable et reproductible, pas de la fantaisie. Un dashboard doit être stable d'une fois à l'autre.

**Q4 — Que se passe-t-il si OpenRouter est indisponible ?**
`generate_dashboard_with_llm()` capte l'exception (`try/except`), logge un `warning` et **retourne `None`**. `build_openui_response()` appelle alors `_build_deterministic_openui()` : l'utilisateur voit un **dashboard template** équivalent, **sans aucune erreur**. C'est le principe de *graceful degradation*.

**Q5 — Comment évites-tu que Mistral invente des données ?**
Trois garde-fous : (1) Mistral **ne reçoit que** le dictionnaire déjà calculé par les outils backend (`_serialize_response_for_llm`), **jamais la base ni le SQL** ; (2) le **system prompt** (`_DASHBOARD_SYSTEM_PROMPT`) interdit explicitement d'inventer (« N'invente JAMAIS de chiffres. Utilise UNIQUEMENT les valeurs présentes dans `data` ») ; (3) la **conversion `_dashboard_json_to_openui`** n'accepte que des composants de la whitelist et nettoie les sorties. Les KPI chiffrés viennent donc toujours des outils, pas du LLM.

**Q6 — Quelle est la différence entre `crm_summary` et `crm_comparison` ?**
`crm_summary` (outil `get_crm_summary`) donne une **photographie instantanée** du pipeline (totaux, priorités, conversion). `crm_comparison` (outil `get_crm_comparison`) fait une **comparaison temporelle** : leads créés sur **les 7 derniers jours vs les 7 jours précédents** (filtre sur `created_at`), avec **deltas et pourcentages calculés côté backend** par la fonction `_format_delta`. Le LLM ne recalcule jamais ces variations.

**Q7 — Pourquoi convertis-tu le JSON de Mistral en « OpenUI Lang » au lieu de l'afficher directement ?**
Parce que le frontend utilise la bibliothèque `@openuidev/react-lang` qui parse un **DSL** (`root = AssistantDashboard(...)`) et le mappe à des composants React typés (Zod). En passant par un **JSON contraint → convertisseur Python (`_dashboard_json_to_openui`)**, je garde le contrôle : seuls les **17 types whitelistés** sont émis, les IDs techniques sont retirés, et un `type` inconnu est **ignoré** (le LLM ne peut pas injecter d'UI arbitraire).

**Q8 — Le LLM peut-il accéder à PostgreSQL ?**
Non, jamais. Les chiffres sont calculés par `assistant_tools.py` (SQLAlchemy, lecture seule). `openui_service.py` ne contient aucun accès base — c'est même **vérifié par le test** `test_no_sql_access_in_openui_service` (absence de `sqlalchemy`, `select(`, `Session` dans le module).

**Q9 — Comment l'interface affiche-t-elle texte et dashboard côte à côte (split-screen) ?**
Dans `openuiLibrary.tsx`, `AssistantDashboardRenderer` trie les composants : les types **narratifs** (`NARRATIVE_TYPES` : InsightList, RecommendationList, AlertList, TextBlock…) vont dans la **colonne gauche (40 %)**, les types **visuels** (KPI, graphiques, tableaux) dans la **colonne droite (60 %)**, et `SuggestedActions`/`SourceList` en **bas pleine largeur**. La grille CSS est `md:grid-cols-[2fr_3fr]` ; sur mobile elle repasse en une colonne (dashboard d'abord).

**Q10 — Que se passe-t-il si Mistral génère un composant qui n'existe pas ?**
Deux protections. Côté **backend** : `_node_to_openui` cherche le `type` dans `_COMPONENT_BUILDERS` ; s'il est absent, il renvoie `None` et le composant est **ignoré** (jamais transmis au frontend). Côté **frontend** : `OpenUIErrorBoundary` capte toute erreur de rendu et bascule sur le rendu legacy `AssistantChartRenderer`.

**Q11 — Quel modèle utilises-tu exactement, et quel est le timeout ?**
Le modèle est `settings.OPENUI_MODEL or settings.OPENROUTER_MODEL`, soit par défaut **`mistralai/mistral-small-3.2-24b-instruct`** (défini dans `config.py`). L'appel se fait en HTTP sur `https://openrouter.ai/api/v1/chat/completions` avec un **timeout de 15 secondes** (`LLM_DASHBOARD_TIMEOUT_SECONDS`), `max_tokens = 2000`, et `response_format = {"type": "json_object"}`.

**Q12 — Comment gères-tu les volumes de données trop faibles (1 seul lead) ?**
Le system prompt demande à Mistral d'utiliser le composant **`insufficient_data`** (`InsufficientDataState` côté React) quand les données sont insuffisantes pour dégager une tendance. Côté outils, on évite aussi de forcer un graphique sur une seule catégorie. Pour `crm_comparison`, s'il n'y a aucun lead sur 14 jours, le résumé indique explicitement qu'aucune tendance fiable n'est possible.

**Q13 — Comment sécurises-tu les boutons d'action (relances, e-mails) ?**
Les actions de **navigation** s'exécutent directement (sûres). Les actions **mutantes** passent par `POST /assistant/actions` → `_required_permission_for_action()` qui exige une permission précise (ex. `crm.drafts.generate`, `crm.email.send`) **et** `confirmed = true`. Dans cette version elles renvoient `status="deferred"` : rien n'est exécuté automatiquement, l'utilisateur est renvoyé vers l'écran métier sécurisé. Dans le system prompt, toute action mutante doit aussi avoir `requiresConfirmation = true`.

**Q14 — Pourquoi avoir gardé les « templates fixes » si Mistral fonctionne ?**
Pour la **robustesse** et l'**indépendance** : si la clé OpenRouter manque, expire, ou si le réseau tombe, l'assistant reste **100 % fonctionnel** grâce à `_build_deterministic_openui()`. La démo ne dépend donc pas d'un service externe, et les chiffres affichés sont strictement les mêmes (ils viennent des outils, pas du LLM).

**Q15 — Quelle est la structure exacte d'une réponse renvoyée au frontend ?**
Un objet `AssistantChatResponse` (`schemas/assistant.py`) : `answer` (texte), `intent`, `mode`, `sources` (liste `AssistantSource`), `suggested_actions` (liste `SuggestedAction`), `visualizations` (liste `VisualizationData` : `bar_chart`/`line_chart`/`pie_chart`/`table`/`kpi`), `conversation_id`, `display_mode` (`text` | `legacy` | `openui`), `openui_content` (la chaîne OpenUI Lang) et `openui_version` (`"0.5"`). Le frontend choisit le rendu selon `display_mode`.

**Bonus — Quelles technologies composent la stack ?**
Backend **FastAPI + SQLAlchemy + PostgreSQL** ; auth **JWT + RBAC** ; LLM **Mistral via OpenRouter** (`httpx`) ; Generative UI **OpenUI** (`@openuidev/react-lang`) ; frontend **React + TypeScript + Vite + TailwindCSS** ; automatisations **n8n**.

---

## SECTION 8 — Glossaire technique

- **Intent / Classification d'intent** — L'« intention » est la catégorie métier d'une question (ex. `crm_summary`). La *classification* est l'opération qui range la phrase de l'utilisateur dans la bonne intention. Ici elle est faite par **regex** (`_classify_intent`), pas par IA.

- **OpenUI / OpenUI Lang** — **OpenUI** est le système qui permet à un LLM de **décrire une interface** plutôt que du texte. **OpenUI Lang** est son mini-langage (DSL) : `root = AssistantDashboard("Titre", "Résumé", [DashboardSection(...)])`. Le frontend (`@openuidev/react-lang`) le parse et le transforme en composants React.

- **LLM** — *Large Language Model* (grand modèle de langage), une IA générative entraînée sur du texte. Ici on l'utilise pour **concevoir la mise en page**, pas pour produire les chiffres.

- **Mistral** — Le modèle de langage utilisé (`mistralai/mistral-small-3.2-24b-instruct`), un LLM open-weight français.

- **OpenRouter** — Une **passerelle** (proxy) qui donne accès à de nombreux LLM (dont Mistral) via une seule API compatible OpenAI (`/chat/completions`). C'est par elle que passe l'appel.

- **Fallback** — Solution de **repli** automatique quand le chemin principal échoue. Ici : si Mistral échoue → templates fixes ; si le rendu échoue → rendu legacy. But : **ne jamais planter**.

- **Template déterministe** — Code Python qui construit le dashboard **toujours de la même façon** (sans IA), à partir des mêmes données. C'est `_build_deterministic_openui()`. « Déterministe » = même entrée → même sortie.

- **JWT** — *JSON Web Token*, un jeton signé envoyé à chaque requête pour prouver **qui** est l'utilisateur. Le backend le vérifie avant de répondre.

- **RBAC** — *Role Based Access Control* (contrôle d'accès basé sur les rôles). Chaque utilisateur a un rôle → des **permissions** ; on n'autorise une action que si la permission est présente.

- **Permission** — Un droit nommé (ex. `crm.leads.view`). Si l'utilisateur ne l'a pas, l'intention correspondante est refusée.

- **Split-screen dashboard** — Affichage en **deux colonnes** façon Thesys : analyse textuelle à gauche (40 %), dashboard visuel à droite (60 %), actions en bas. Géré par `AssistantDashboardRenderer`.

- **Température LLM** — Paramètre (0 à ~2) qui règle l'**aléa/créativité** de la sortie. Basse (`0.2`) = réponses stables et prévisibles ; haute = plus variées. On veut bas pour un dashboard fiable.

- **JSON mode** — Option (`response_format: {"type": "json_object"}`) qui **force** le LLM à répondre par un **JSON valide uniquement**, sans texte autour. Indispensable pour parser la réponse sans erreur.

- **Whitelist de composants** — Liste **fermée** des seuls composants autorisés (`_COMPONENT_BUILDERS`, 17 `type`). Tout composant hors liste est **ignoré** : le LLM ne peut pas injecter d'interface arbitraire (sécurité + cohérence).

---

*Document généré à partir du code source réel du projet FlowPilot — Assistant IA.*
