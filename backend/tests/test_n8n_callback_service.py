import unittest

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.models import (
    AgentRun,
    Base,
    CrmInteraction,
    CrmLead,
    Role,
    User,
    WorkflowExecution,
)
from app.schemas.n8n_callbacks import (
    CrmCollectResultPayload,
    CrmCommunicationResultPayload,
    CrmRoutingResultPayload,
)
from app.services.n8n_callback_service import (
    handle_collect_result,
    handle_communication_result,
    handle_routing_result,
)


class N8nCallbackServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")

        @event.listens_for(self.engine, "connect")
        def enable_sqlite_foreign_keys(
            dbapi_connection: object,
            connection_record: object,
        ) -> None:
            del connection_record
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.db.add(Role(id="role_test", name="Test Role"))
        self.db.add(
            User(
                id="user_030",
                full_name="CRM Owner",
                email="crm.owner@example.com",
                role_id="role_test",
            ),
        )
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_collect_result_persists_lead_interaction_and_traces(self) -> None:
        payload = CrmCollectResultPayload(
            lead_id="lead_n8n_trace_test_001",
            full_name="N8N Trace Test",
            email="trace.test@example.com",
            source="n8n",
            message="Trace persistence smoke test lead.",
            workflow_execution={
                "workflow_name": "FP_CRM_01_Lead_Intake_AI_Scoring_Routing",
                "status": "success",
                "trigger_source": "n8n",
            },
            agent_run={
                "agent_id": "crm_lead_intake_agent",
                "agent_name": "CRM Lead Intake AI",
                "status": "success",
                "requested_by": "invalid_user",
            },
        )

        result = handle_collect_result(payload, self.db)

        leads = list(self.db.scalars(select(CrmLead)).all())
        interactions = list(self.db.scalars(select(CrmInteraction)).all())
        workflow_executions = list(self.db.scalars(select(WorkflowExecution)).all())
        agent_runs = list(self.db.scalars(select(AgentRun)).all())

        self.assertEqual(result.lead_id, "lead_n8n_trace_test_001")
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0].id, "lead_n8n_trace_test_001")
        self.assertEqual(len(interactions), 1)
        self.assertEqual(interactions[0].lead_id, "lead_n8n_trace_test_001")
        self.assertEqual(interactions[0].interaction_type, "lead_collected")
        self.assertEqual(len(workflow_executions), 1)
        self.assertEqual(workflow_executions[0].related_object_id, "lead_n8n_trace_test_001")
        self.assertEqual(result.workflow_execution_id, workflow_executions[0].id)
        self.assertEqual(len(agent_runs), 1)
        self.assertEqual(agent_runs[0].workflow_execution_id, workflow_executions[0].id)
        self.assertEqual(agent_runs[0].requested_by, "user_030")
        self.assertEqual(result.agent_run_id, agent_runs[0].id)

    def test_communication_result_preserves_nested_interaction_summary(self) -> None:
        self._add_test_lead()
        payload = CrmCommunicationResultPayload(
            lead_id="lead_n8n_trace_test_001",
            channel="email",
            status="draft",
            interaction={
                "interaction_type": "communication_draft",
                "channel": "email",
                "summary": (
                    "Bienvenue chez FlowPilot AI - welcome email draft after "
                    "customer conversion."
                ),
            },
        )

        result = handle_communication_result(payload, self.db)

        interaction = self.db.get(CrmInteraction, result.interaction_id)

        self.assertIsNotNone(interaction)
        self.assertEqual(interaction.interaction_type, "communication_draft")
        self.assertEqual(interaction.channel, "email")
        self.assertEqual(
            interaction.summary,
            "Bienvenue chez FlowPilot AI - welcome email draft after customer conversion.",
        )

    def test_communication_result_keeps_workflow_02_fallback_draft(self) -> None:
        self._add_test_lead()
        payload = CrmCommunicationResultPayload(
            lead_id="lead_n8n_trace_test_001",
            channel="email",
            status="draft",
        )

        result = handle_communication_result(payload, self.db)

        interaction = self.db.get(CrmInteraction, result.interaction_id)

        self.assertIsNotNone(interaction)
        self.assertEqual(interaction.interaction_type, "communication_draft")
        self.assertEqual(interaction.summary, "CRM communication draft.")

    def test_routing_keeps_conversion_pending_when_payload_says_customer(self) -> None:
        self._add_pending_lead()
        payload = CrmRoutingResultPayload(
            lead_id="lead_pending_test_001",
            customer_status="customer",
            recommended_action="Customer converted by human validation.",
            next_action="Review welcome draft.",
        )

        handle_routing_result(payload, self.db)

        lead = self.db.get(CrmLead, "lead_pending_test_001")
        self.assertEqual(lead.customer_status, "conversion_pending")
        self.assertEqual(lead.next_action, "Review welcome draft.")

    def test_communication_finalizes_conversion_pending_to_customer(self) -> None:
        self._add_pending_lead()
        payload = CrmCommunicationResultPayload(
            lead_id="lead_pending_test_001",
            channel="email",
            email_subject="Bienvenue chez FlowPilot AI",
            email_body="<p>Bienvenue chez FlowPilot AI.</p>",
            communication_status="welcome_email_draft_generated",
            status="draft",
        )

        handle_communication_result(payload, self.db)

        lead = self.db.get(CrmLead, "lead_pending_test_001")
        self.assertEqual(lead.customer_status, "customer")

    def _add_pending_lead(self) -> None:
        self.db.add(
            CrmLead(
                id="lead_pending_test_001",
                full_name="Pending Conversion",
                company_name="Pending Co",
                email="pending@example.com",
                status="hot",
                customer_status="conversion_pending",
                lead_score=80,
            ),
        )
        self.db.commit()

    def _add_test_lead(self) -> None:
        self.db.add(
            CrmLead(
                id="lead_n8n_trace_test_001",
                full_name="N8N Trace Test",
                company_name="Trace Company",
                email="trace.test@example.com",
                status="customer",
                customer_status="customer",
                lead_score=90,
            ),
        )
        self.db.commit()


if __name__ == "__main__":
    unittest.main()
