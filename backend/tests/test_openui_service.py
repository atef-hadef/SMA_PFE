import inspect
import json
import unittest
from unittest.mock import MagicMock, patch

from app.schemas.assistant import AssistantChatResponse, AssistantSource, SuggestedAction, VisualizationData
from app.services.assistant_service import _classify_intent, process_chat
from app.services import openui_service


def _sample_response(row_count: int = 2) -> AssistantChatResponse:
    rows = [
        {"Nom": f"Lead {index}", "Entreprise": "FlowPilot", "Score": 80 + index, "Statut": "hot", "lead_id": f"lead_{index}"}
        for index in range(row_count)
    ]
    return AssistantChatResponse(
        answer="Pipeline CRM : 2 leads haute priorité.",
        intent="crm_summary",
        mode="mixed",
        visualizations=[
            VisualizationData(
                type="kpi",
                title="Leads haute priorité",
                data={"label": "Leads haute priorité", "value": "2", "detail": "Calculé depuis PostgreSQL"},
            ),
            VisualizationData(
                type="bar_chart",
                title="Leads par statut",
                data={"xKey": "statut", "yKey": "nombre", "data": [{"statut": "hot", "nombre": 2}]},
            ),
            VisualizationData(
                type="table",
                title="Leads prioritaires",
                data={"rows": rows},
            ),
        ],
        suggested_actions=[
            SuggestedAction(label="Ouvrir le pipeline CRM", action_type="navigate", payload={"route": "/crm-leads"}),
            SuggestedAction(label="Préparer les relances", action_type="prepare_followups", payload={}),
        ],
        sources=[AssistantSource(title="Table crm_leads", source_type="database", reference="/api/crm/leads")],
    )


class OpenUIServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.original_enabled = openui_service.settings.OPENUI_ENABLED
        self.original_key = openui_service.settings.OPENROUTER_API_KEY
        self.original_max_rows = openui_service.settings.OPENUI_MAX_TABLE_ROWS
        openui_service.settings.OPENROUTER_API_KEY = ""

    def tearDown(self) -> None:
        openui_service.settings.OPENUI_ENABLED = self.original_enabled
        openui_service.settings.OPENROUTER_API_KEY = self.original_key
        openui_service.settings.OPENUI_MAX_TABLE_ROWS = self.original_max_rows

    def test_openui_response_when_enabled(self) -> None:
        openui_service.settings.OPENUI_ENABLED = True

        content = openui_service.build_openui_response(
            request_message="Donne-moi un résumé CRM de cette semaine.",
            response=_sample_response(),
        )

        self.assertIsNotNone(content)
        self.assertIn("root = AssistantDashboard", content or "")
        self.assertIn("KpiGrid", content or "")
        self.assertIn("BarChartCard", content or "")
        self.assertIn("PriorityLeadTable", content or "")

    def test_crm_summary_intent_does_not_become_global_summary(self) -> None:
        self.assertEqual(_classify_intent("Donne-moi un résumé CRM de cette semaine."), "crm_summary")
        self.assertEqual(_classify_intent("Donne-moi un resume CRM de cette semaine."), "crm_summary")

    def test_global_summary_requires_explicit_global_wording(self) -> None:
        self.assertEqual(_classify_intent("Donne-moi un résumé global de cette semaine."), "business_summary")
        self.assertEqual(_classify_intent("Donne-moi un resume general de cette semaine."), "business_summary")

    def test_comparison_questions_route_to_comparison_intent(self) -> None:
        self.assertEqual(_classify_intent("Compare cette semaine avec la semaine précédente."), "crm_comparison")
        self.assertEqual(_classify_intent("Compare cette semaine avec la semaine precedente."), "crm_comparison")
        self.assertEqual(_classify_intent("Quelle est l'évolution hebdomadaire des leads ?"), "crm_comparison")

    def test_comparison_uses_comparison_dashboard_category(self) -> None:
        self.assertEqual(
            openui_service.choose_display_category("crm_comparison", "Compare cette semaine.", []),
            "comparison_dashboard",
        )

    def test_comparison_response_builds_kpis_and_comparison_chart(self) -> None:
        openui_service.settings.OPENUI_ENABLED = True
        response = AssistantChatResponse(
            answer="Comparaison CRM sur 7 jours : 3 nouveaux leads cette semaine contre 1 la semaine précédente.",
            intent="crm_comparison",
            mode="mixed",
            visualizations=[
                VisualizationData(
                    type="kpi",
                    title="Nouveaux leads (7 derniers jours)",
                    data={"label": "Nouveaux leads cette semaine", "value": "3", "detail": "+2 (+200 %) vs semaine précédente"},
                ),
                VisualizationData(
                    type="kpi",
                    title="Leads semaine précédente",
                    data={"label": "Leads semaine précédente", "value": "1", "detail": "Période de référence (J-14 à J-7)"},
                ),
                VisualizationData(
                    type="bar_chart",
                    title="Comparaison hebdomadaire des leads",
                    data={"xKey": "période", "yKey": "nombre", "data": [{"période": "Cette semaine", "nombre": 3}, {"période": "Semaine précédente", "nombre": 1}]},
                ),
            ],
            suggested_actions=[SuggestedAction(label="Ouvrir le pipeline CRM", action_type="navigate", payload={"route": "/crm-leads"})],
            sources=[AssistantSource(title="Table crm_leads", source_type="database", reference="/api/crm/leads")],
        )

        content = openui_service.build_openui_response(
            request_message="Compare cette semaine avec la semaine précédente.",
            response=response,
        )

        self.assertIsNotNone(content)
        self.assertIn("KpiGrid", content or "")
        self.assertIn("BarChartCard", content or "")
        self.assertIn("Comparaison", content or "")

    def test_formatter_injects_contextual_kpi_details_not_jargon(self) -> None:
        openui_service.settings.OPENUI_ENABLED = True
        # KPI table (Indicateur/Valeur) — details here are injected by the formatter,
        # so this verifies the formatter never emits generic "calculée depuis" lines
        # and instead produces indicator-specific context.
        response = AssistantChatResponse(
            answer="Analyse CRM complète : 12 leads au total.",
            intent="crm_summary",
            mode="mixed",
            visualizations=[
                VisualizationData(
                    type="table",
                    title="Indicateurs clés CRM",
                    description="Vue synthétique du pipeline commercial.",
                    data={
                        "rows": [
                            {"Indicateur": "Leads CRM", "Valeur": 12},
                            {"Indicateur": "Prospects", "Valeur": 4},
                            {"Indicateur": "Clients", "Valeur": 2},
                            {"Indicateur": "Taux de conversion", "Valeur": 16.7},
                        ]
                    },
                ),
            ],
            suggested_actions=[SuggestedAction(label="Ouvrir le pipeline CRM", action_type="navigate", payload={"route": "/crm-leads"})],
            sources=[AssistantSource(title="Table crm_leads", source_type="database", reference="/api/crm/leads")],
        )

        content = openui_service.build_openui_response(
            request_message="Donne-moi un résumé CRM de cette semaine.",
            response=response,
        ) or ""

        lowered = content.lower()
        self.assertNotIn("calculée depuis les données", lowered)
        self.assertNotIn("calculé par l'outil", lowered)
        self.assertNotIn("postgresql", lowered)
        # Contextual, indicator-specific details are present and distinct.
        self.assertIn("Total du pipeline commercial", content)
        self.assertIn("En cours de qualification", content)
        self.assertIn("Conversions réalisées", content)

    def test_legacy_when_disabled(self) -> None:
        openui_service.settings.OPENUI_ENABLED = False

        content = openui_service.build_openui_response(
            request_message="Donne-moi un résumé CRM.",
            response=_sample_response(),
        )

        self.assertIsNone(content)

    def test_fallback_when_model_content_empty(self) -> None:
        openui_service.settings.OPENUI_ENABLED = True

        content = openui_service.build_openui_response(
            request_message="Donne-moi un résumé CRM.",
            response=_sample_response(),
        )

        self.assertIsNotNone(content)
        self.assertIn("AssistantDashboard", content or "")

    def test_table_rows_are_limited_and_technical_ids_removed(self) -> None:
        openui_service.settings.OPENUI_ENABLED = True
        openui_service.settings.OPENUI_MAX_TABLE_ROWS = 3

        content = openui_service.build_openui_response(
            request_message="Liste les hot leads qui nécessitent une action.",
            response=_sample_response(row_count=8),
        )

        self.assertIsNotNone(content)
        self.assertNotIn("lead_id", content or "")
        self.assertIn("Lead 0", content or "")
        self.assertIn("Lead 2", content or "")
        self.assertNotIn("Lead 3", content or "")

    def test_kpi_table_is_not_rendered_twice(self) -> None:
        openui_service.settings.OPENUI_ENABLED = True
        response = AssistantChatResponse(
            answer="Situation CRM : 1 lead haute priorité.",
            intent="crm_summary",
            mode="mixed",
            visualizations=[
                VisualizationData(
                    type="table",
                    title="Indicateurs clés — CRM & Congés",
                    description="Snapshot en temps réel.",
                    data={
                        "rows": [
                            {"Indicateur": "Leads CRM", "Valeur": 1},
                            {"Indicateur": "Leads haute priorité", "Valeur": 1},
                            {"Indicateur": "Demandes de congé", "Valeur": 0},
                        ]
                    },
                ),
                VisualizationData(
                    type="table",
                    title="Leads haute priorité",
                    data={"rows": [{"Nom": "Atef", "Entreprise": "Tactic", "Score": 98, "Statut": "hot"}]},
                ),
            ],
            suggested_actions=[
                SuggestedAction(label="Ouvrir le pipeline CRM", action_type="navigate", payload={"route": "/crm-leads"}),
                SuggestedAction(label="Voir les demandes de congé", action_type="navigate", payload={"route": "/leave-request"}),
            ],
            sources=[
                AssistantSource(title="Table crm_leads", source_type="database", reference="/api/crm/leads"),
                AssistantSource(title="Table leave_requests", source_type="database", reference="/api/leave-requests"),
            ],
        )

        content = openui_service.build_openui_response(
            request_message="Donne-moi un résumé CRM de cette semaine.",
            response=response,
        )

        self.assertIsNotNone(content)
        self.assertIn("KpiGrid", content or "")
        self.assertIn("PriorityLeadTable", content or "")
        self.assertNotIn('SmartDataTable("Indicateurs clés', content or "")
        self.assertNotIn("Demandes de congé", content or "")
        self.assertNotIn("/leave-request", content or "")

    def test_count_question_uses_single_metric_card(self) -> None:
        openui_service.settings.OPENUI_ENABLED = True

        content = openui_service.build_openui_response(
            request_message="Combien de hot leads avons-nous ?",
            response=_sample_response(),
        )

        self.assertIsNotNone(content)
        self.assertIn("SingleMetricCard", content or "")
        self.assertNotIn("BarChartCard", content or "")
        self.assertNotIn("PriorityLeadTable", content or "")

    def test_no_sql_access_in_openui_service(self) -> None:
        source = inspect.getsource(openui_service)

        self.assertNotIn("sqlalchemy", source.lower())
        self.assertNotIn("select(", source)
        self.assertNotIn("Session", source)

    def test_legacy_fields_are_preserved_in_hybrid_response(self) -> None:
        openui_service.settings.OPENUI_ENABLED = True
        response = _sample_response()

        content = openui_service.build_openui_response(
            request_message="Donne-moi un résumé CRM.",
            response=response,
        )

        response.display_mode = "openui" if content else "legacy"
        response.openui_content = content
        response.openui_version = openui_service.OPENUI_VERSION if content else None

        self.assertEqual(response.answer, "Pipeline CRM : 2 leads haute priorité.")
        self.assertEqual(len(response.visualizations), 3)
        self.assertEqual(len(response.suggested_actions), 2)
        self.assertEqual(len(response.sources), 1)
        self.assertEqual(response.display_mode, "openui")

    def test_user_without_permission_gets_no_business_data(self) -> None:
        result = process_chat(
            request=type("Request", (), {"message": "Donne-moi un résumé CRM", "conversation_id": None, "conversation_history": []})(),
            db=None,  # type: ignore[arg-type]
            permissions=["dashboard.view"],
        )

        self.assertEqual(result.visualizations, [])
        self.assertEqual(result.sources, [])
        self.assertEqual(result.display_mode, "text")


class LlmDashboardTest(unittest.TestCase):
    """Mistral (OpenRouter, JSON mode) generative-dashboard path."""

    def setUp(self) -> None:
        self.original_enabled = openui_service.settings.OPENUI_ENABLED
        self.original_key = openui_service.settings.OPENROUTER_API_KEY
        openui_service.settings.OPENUI_ENABLED = True

    def tearDown(self) -> None:
        openui_service.settings.OPENUI_ENABLED = self.original_enabled
        openui_service.settings.OPENROUTER_API_KEY = self.original_key

    def test_returns_none_gracefully_without_api_key(self) -> None:
        openui_service.settings.OPENROUTER_API_KEY = ""
        result = openui_service.generate_dashboard_with_llm(
            question="Donne-moi un résumé CRM.",
            intent="crm_summary",
            data={"answer": "12 leads", "visualizations": [], "suggested_actions": [], "sources": []},
            permissions=["crm.leads.view"],
        )
        self.assertIsNone(result)

    def test_build_falls_back_to_templates_when_llm_returns_none(self) -> None:
        openui_service.settings.OPENROUTER_API_KEY = ""
        with patch.object(openui_service, "generate_dashboard_with_llm", return_value=None) as mocked:
            content = openui_service.build_openui_response(
                request_message="Donne-moi un résumé CRM.",
                response=_sample_response(),
                permissions=["crm.leads.view"],
            )
        mocked.assert_called_once()
        self.assertIsNotNone(content)
        self.assertIn("AssistantDashboard", content or "")

    def test_llm_json_is_converted_to_openui_syntax(self) -> None:
        payload = {
            "title": "Résumé CRM",
            "summary": "Le pipeline contient 12 leads.",
            "sections": [
                {
                    "title": "Indicateurs",
                    "components": [
                        {"type": "kpi_grid", "cards": [{"label": "Leads", "value": 12, "detail": "Total", "tone": "info"}]},
                        {"type": "bar_chart", "title": "Leads par statut", "data": [{"label": "hot", "value": 2}, {"label": "warm", "value": 6}]},
                    ],
                },
                {
                    "title": "Suite",
                    "components": [
                        {"type": "suggested_actions", "actions": [{"label": "Ouvrir le pipeline CRM", "actionType": "navigate", "route": "/crm-leads"}]},
                        {"type": "source_list", "sources": [{"label": "Données CRM", "type": "database"}]},
                    ],
                },
            ],
        }
        content = openui_service._dashboard_json_to_openui(payload)
        self.assertIsNotNone(content)
        self.assertTrue((content or "").startswith("root = AssistantDashboard("))
        self.assertIn("KpiGrid", content or "")
        self.assertIn("KpiCard", content or "")
        self.assertIn("BarChartCard", content or "")
        self.assertIn("SuggestedActions", content or "")
        self.assertIn("/crm-leads", content or "")
        self.assertIn("SourceList", content or "")

    def test_mutating_action_forces_confirmation_in_conversion(self) -> None:
        payload = {
            "title": "Relances",
            "summary": "Préparer les relances.",
            "sections": [
                {
                    "title": "Suite",
                    "components": [
                        {"type": "suggested_actions", "actions": [
                            {"label": "Préparer les relances", "actionType": "prepare_followups"},
                        ]},
                    ],
                }
            ],
        }
        content = openui_service._dashboard_json_to_openui(payload) or ""
        self.assertIn("requiresConfirmation: true", content)

    def test_unknown_component_type_is_dropped_not_crashing(self) -> None:
        payload = {
            "title": "Test",
            "summary": "Résumé.",
            "sections": [
                {"title": "S", "components": [
                    {"type": "does_not_exist", "foo": "bar"},
                    {"type": "insight_list", "items": ["Observation factuelle."]},
                ]},
            ],
        }
        content = openui_service._dashboard_json_to_openui(payload) or ""
        self.assertIn("InsightList", content)
        self.assertNotIn("does_not_exist", content)

    def test_full_generation_with_mocked_openrouter(self) -> None:
        openui_service.settings.OPENROUTER_API_KEY = "test-key"
        dashboard_json = json.dumps({
            "title": "Résumé CRM",
            "summary": "Le pipeline contient 12 leads.",
            "sections": [
                {"title": "Indicateurs", "components": [
                    {"type": "kpi_grid", "cards": [{"label": "Leads", "value": 12, "tone": "info"}]},
                ]},
                {"title": "Suite", "components": [
                    {"type": "source_list", "sources": [{"label": "Données CRM", "type": "database"}]},
                ]},
            ],
        })

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"choices": [{"message": {"content": dashboard_json}}]}
        mock_client = MagicMock()
        mock_client.__enter__.return_value.post.return_value = mock_response

        with patch("httpx.Client", return_value=mock_client):
            result = openui_service.generate_dashboard_with_llm(
                question="Donne-moi un résumé CRM de cette semaine.",
                intent="crm_summary",
                data={"answer": "12 leads", "visualizations": [], "suggested_actions": [], "sources": []},
                permissions=["crm.leads.view"],
            )

        self.assertIsNotNone(result)
        self.assertTrue((result or "").startswith("root = AssistantDashboard("))
        self.assertIn("KpiGrid", result or "")
        self.assertIn("SourceList", result or "")

    def test_invalid_json_from_model_falls_back_to_none(self) -> None:
        openui_service.settings.OPENROUTER_API_KEY = "test-key"
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"choices": [{"message": {"content": "this is not json {{{"}}]}
        mock_client = MagicMock()
        mock_client.__enter__.return_value.post.return_value = mock_response

        with patch("httpx.Client", return_value=mock_client):
            result = openui_service.generate_dashboard_with_llm(
                question="Donne-moi un résumé CRM.",
                intent="crm_summary",
                data={"answer": "x", "visualizations": [], "suggested_actions": [], "sources": []},
                permissions=["crm.leads.view"],
            )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
