# OpenUI Assistant Integration

## Objectif

Cette intégration ajoute une couche Generative UI à la page existante `Assistant IA` de FlowPilot AI. L'assistant conserve son format historique (`answer`, `visualizations`, `suggested_actions`, `sources`) et peut, lorsque `OPENUI_ENABLED=true`, retourner aussi un dashboard OpenUI rendu dans React.

## Architecture

```text
AssistantPage.tsx
  -> POST /api/assistant/chat
  -> JWT + require_permission("dashboard.view")
  -> assistant_service.process_chat
  -> classification d'intention
  -> outils métier read-only assistant_tools.py
  -> SQLAlchemy / PostgreSQL
  -> AssistantChatResponse legacy
  -> openui_service.build_openui_response
  -> OpenUIRenderer React
```

Le service OpenUI ne lit pas la base de données. Il transforme uniquement la réponse métier déjà validée et autorisée.

La sélection d'affichage est volontairement stricte par domaine:

- une question CRM produit uniquement des sources, KPI, tableaux et actions CRM;
- une question congés produit uniquement des éléments congés;
- une question automatisations produit uniquement le monitoring des workflows;
- une synthèse globale doit être demandée explicitement (`résumé global`, `tableau de bord métier`, etc.).

## Fichiers Créés

- `frontend/src/components/assistant/openuiLibrary.tsx`
- `frontend/src/components/assistant/OpenUIRenderer.tsx`
- `frontend/src/components/assistant/assistantActions.ts`
- `frontend/src/components/assistant/OpenUIRenderer.test.tsx`
- `frontend/scripts/generate-openui-prompt.ts`
- `backend/app/openui/flowpilot_openui_prompt.txt`
- `backend/app/services/openui_service.py`
- `backend/tests/test_openui_service.py`
- `backend/tests/test_assistant_actions.py`
- `docs/OPENUI_ASSISTANT_INTEGRATION.md`

## Fichiers Modifiés

- `.env.example`
- `backend/app/core/config.py`
- `backend/app/schemas/assistant.py`
- `backend/app/services/assistant_service.py`
- `backend/app/api/assistant.py`
- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/tsconfig.app.json`
- `frontend/tsconfig.node.json`
- `frontend/vite.config.ts`
- `frontend/src/pages/AssistantPage.tsx`
- `frontend/src/services/assistantService.ts`

## Dépendances

Ajoutées au frontend:

- `@openuidev/react-lang`
- `zod`
- `tsx`
- `vitest`
- `@testing-library/react`
- `@testing-library/jest-dom`
- `jsdom`

## Variables d'Environnement

```env
OPENUI_ENABLED=false
OPENUI_MODEL=
OPENUI_TIMEOUT_SECONDS=30
OPENUI_MAX_TABLE_ROWS=20
```

`OPENUI_ENABLED=false` conserve le comportement legacy. `OPENUI_ENABLED=true` active la réponse hybride OpenUI si l'intention et les données s'y prêtent. Si le modèle OpenUI ou le rendu échoue, l'assistant revient au rendu historique.

## Génération Du Prompt

Le prompt système OpenUI est généré depuis la bibliothèque réelle:

```bash
cd frontend
npm run generate:openui-prompt
```

Le fichier généré est:

```text
backend/app/openui/flowpilot_openui_prompt.txt
```

Après ajout ou modification d'un composant OpenUI, régénérer ce fichier avant de relancer le backend.

## Composants Autorisés

La bibliothèque FlowPilot expose uniquement des composants validés par Zod:

- `AssistantDashboard`
- `DashboardSection`
- `TextBlock`
- `SingleMetricCard`
- `KpiGrid`
- `KpiCard`
- `BarChartCard`
- `LineChartCard`
- `PieChartCard`
- `FunnelChartCard`
- `SmartDataTable`
- `PriorityLeadTable`
- `AlertList`
- `InsightList`
- `RecommendationList`
- `SuggestedActions`
- `WorkflowHealthCard`
- `SourceList`
- `EmptyState`
- `InsufficientDataState`
- `ErrorState`
- `LoadingState`

Aucun JSX, HTML, JavaScript arbitraire, `eval` ou `dangerouslySetInnerHTML` n'est généré par le modèle.

Règles de rendu importantes:

- `SingleMetricCard` est privilégié pour les questions courtes de type `Combien...`.
- `PriorityLeadTable` est utilisé pour les listes CRM de hot leads ou leads prioritaires.
- `InsufficientDataState` indique explicitement quand le volume de données est trop faible pour conclure à une tendance.
- Les tables KPI déjà transformées en cartes ne sont pas rendues une deuxième fois en tableau.

## Ajouter Un Composant

1. Ajouter le composant dans `openuiLibrary.tsx` avec `defineComponent`.
2. Décrire les props avec Zod.
3. Ajouter le composant à `createLibrary`.
4. Ajouter si utile le composant dans un groupe.
5. Régénérer le prompt:

```bash
npm run generate:openui-prompt
```

6. Ajouter un test de rendu.

## Ajouter Un Outil Analytique

1. Créer ou réutiliser une fonction read-only dans `assistant_tools.py`.
2. Retourner un `ToolResult` avec `metrics`, `visualizations`, `sources`, `suggested_actions`.
3. Ajouter l'intention dans `assistant_service.py`.
4. Vérifier les permissions dans `_resolve_authorized_intent`.
5. Ne pas exposer d'ORM brut.
6. Limiter les lignes côté backend.

## Actions Et n8n

La première version exécute directement seulement:

- navigation;
- query de suivi;
- refresh;
- ouverture de détails.

Les actions mutantes (`prepare_followups`, `generate_email_draft`, `create_task`, `launch_report`, `send_approved_email`) demandent confirmation côté frontend et sont refusées ou différées côté backend si la permission manque ou si l'intégration métier dédiée n'est pas branchée.

Endpoint ajouté:

```text
POST /api/assistant/actions
```

Il revérifie JWT/RBAC et ne déclenche pas silencieusement n8n.

## Sécurité

- JWT requis via `require_permission("dashboard.view")`.
- RBAC métier conservé dans `assistant_service.py`.
- OpenUI reçoit seulement les données déjà autorisées.
- Pas d'accès SQL libre au modèle.
- Pas de requête SQL générée ou exécutée par OpenUI.
- Pas de secrets côté frontend.
- Tables limitées par `OPENUI_MAX_TABLE_ROWS`.
- Colonnes techniques filtrées (`*_id`, payloads, webhooks, traces internes).
- Erreurs OpenUI journalisées brièvement côté frontend/backend, avec fallback utilisateur.

## Fallback

Si `openui_content` est absent, vide, invalide ou si le renderer échoue:

```text
answer + AssistantChartRenderer + suggested_actions + sources
```

Le composant historique `AssistantChartRenderer.tsx` reste le fallback fiable.

## Tests

Backend:

```bash
cd backend
.venv\Scripts\python.exe -m unittest discover -s tests
```

Frontend:

```bash
cd frontend
npm test
npm run build
npm run lint
```

Note: `npm run lint` peut signaler des erreurs préexistantes hors assistant dans les pages CRM liées à `react-hooks/set-state-in-effect`.

## Questions De Démo PFE

- `Donne-moi un résumé CRM de cette semaine.`
- `Liste les hot leads qui nécessitent une action.`
- `Combien de hot leads avons-nous ?`
- `Compare l'activité CRM de cette semaine avec la semaine précédente.`
- `Quelle est la santé des automatisations ?`
- `Prépare les relances des prospects.`

## Limitations Connues

- Le premier lot ne déclenche pas de mutations n8n directement depuis OpenUI.
- Les comparaisons temporelles dépendent des outils analytiques disponibles dans `assistant_tools.py`.
- Si aucune clé OpenRouter n'est configurée, l'OpenUI est produit par le formatter déterministe à partir des données validées.
- Le chunk frontend dépasse 500 kB après minification; Vite affiche un avertissement non bloquant.
