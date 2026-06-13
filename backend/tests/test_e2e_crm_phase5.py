"""End-to-end integration test for the full CRM lifecycle (Phase 5).

Exercises the chain intake -> AI analysis -> scoring -> routing -> draft ->
review -> approve -> send -> follow-up auto-task -> conversion -> welcome ->
outbox state -> workflow trace -> pagination, asserting the behaviours added
in Phases 1-4 against an in-memory SQLite DB. All outbound n8n webhooks are
mocked so the test stays self-contained and reproducible.
"""

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.models import (
    Base,
    CrmEmailDraft,
    CrmLead,
    CrmTask,
    Role,
    User,
    WebhookOutbox,
    WorkflowExecution,
)
from app.schemas.crm import (
    CrmCustomerConversionRequest,
    CrmWorkflowTracePayload,
)
from app.schemas.n8n_callbacks import (
    AgentRunCallbackPayload,
    CrmAnalysisResultPayload,
    CrmCollectResultPayload,
    CrmCommunicationResultPayload,
    CrmEmailSentResultPayload,
    CrmRoutingResultPayload,
    CrmScoringResultPayload,
    WorkflowCallbackPayload,
)
from app.services import crm_service, n8n_callback_service


class FakeN8nResponse:
    """Minimal urlopen response stub used by webhook_outbox_service."""

    def __enter__(self) -> "FakeN8nResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return b'{"ok": true, "triggered": true}'


def utc(year: int, month: int, day: int, hour: int = 12) -> datetime:
    return datetime(year, month, day, hour, tzinfo=timezone.utc)


class CrmFullLifecycleE2E(unittest.TestCase):
    """Walks one lead through every stage of the CRM process."""

    LEAD_ID = "lead_e2e_001"
    REVIEWER_ID = "user_test_reviewer"
    ROUTED_OWNER_ID = "user_999_active"
    DEFAULT_OWNER_ID = "user_030"

    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")

        @event.listens_for(self.engine, "connect")
        def enable_sqlite_foreign_keys(dbapi_connection, _record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

        self.db.add(Role(id="role_test", name="Test Role"))
        self.db.add(
            User(
                id=self.DEFAULT_OWNER_ID,
                full_name="CRM Owner",
                email="owner@example.com",
                role_id="role_test",
                status="active",
            ),
        )
        self.db.add(
            User(
                id=self.REVIEWER_ID,
                full_name="Test Reviewer",
                email="reviewer@example.com",
                role_id="role_test",
                status="active",
            ),
        )
        self.db.add(
            User(
                id=self.ROUTED_OWNER_ID,
                full_name="Routed Owner",
                email="routed@example.com",
                role_id="role_test",
                status="active",
            ),
        )
        self.db.commit()

        # Mock outbound n8n calls globally for the whole test.
        self._urlopen_patcher = patch(
            "app.services.webhook_outbox_service.urlopen",
            return_value=FakeN8nResponse(),
        )
        self.mock_urlopen = self._urlopen_patcher.start()

    def tearDown(self) -> None:
        self._urlopen_patcher.stop()
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    # --------------------------------------------------------------
    # Helpers
    # --------------------------------------------------------------

    def _workflow_trace(self) -> WorkflowCallbackPayload:
        return WorkflowCallbackPayload(
            workflow_name="FP_CRM_TEST",
            process="CRM",
            status="success",
        )

    def _agent_trace(self) -> AgentRunCallbackPayload:
        return AgentRunCallbackPayload(
            agent_id="test_agent",
            agent_name="Test Agent",
            process="CRM",
            status="success",
        )

    # --------------------------------------------------------------
    # The one big test
    # --------------------------------------------------------------

    def test_full_crm_lifecycle(self) -> None:
        # Step 1 — Lead intake via n8n collect callback ------------------
        n8n_callback_service.handle_collect_result(
            CrmCollectResultPayload(
                lead_id=self.LEAD_ID,
                full_name="Lifecycle Tester",
                email="lifecycle@example.com",
                phone="+216-22-000-000",
                company_name="E2E Corp",
                source="website_form",
                message="We want to automate our CRM follow-up.",
                workflow_execution=self._workflow_trace(),
            ),
            self.db,
        )

        lead = self.db.get(CrmLead, self.LEAD_ID)
        self.assertIsNotNone(lead)
        self.assertEqual(lead.customer_status, "lead")
        self.assertEqual(lead.status, "new")
        # Step 1 ALSO asserts the legacy default owner behaviour
        self.assertEqual(lead.assigned_to, self.DEFAULT_OWNER_ID)

        # Step 2 — AI analysis callback -----------------------------------
        n8n_callback_service.handle_analysis_result(
            CrmAnalysisResultPayload(
                lead_id=self.LEAD_ID,
                sentiment="positive",
                intention="purchase",
                urgency="high",
                ai_summary="Strong intent to buy.",
                workflow_execution=self._workflow_trace(),
            ),
            self.db,
        )
        self.db.refresh(lead)
        self.assertEqual(lead.sentiment, "positive")
        self.assertEqual(lead.intention, "purchase")

        # Step 3 — Scoring (Phase 2 Fix 1: status accepted) ---------------
        n8n_callback_service.handle_scoring_result(
            CrmScoringResultPayload(
                lead_id=self.LEAD_ID,
                lead_score=85,
                status="hot",
                priority="high",
                workflow_execution=self._workflow_trace(),
            ),
            self.db,
        )
        self.db.refresh(lead)
        self.assertEqual(lead.lead_score, 85)
        self.assertEqual(lead.status, "hot")
        self.assertEqual(lead.priority, "high")

        # Step 4 — Routing (Phase 2 Fix 1 bis: assigned_to applied) -------
        n8n_callback_service.handle_routing_result(
            CrmRoutingResultPayload(
                lead_id=self.LEAD_ID,
                recommended_action="Schedule discovery call.",
                next_action="Send tailored draft.",
                assigned_to=self.ROUTED_OWNER_ID,
                assignment_reason="Hot lead with high urgency.",
                workflow_execution=self._workflow_trace(),
            ),
            self.db,
        )
        self.db.refresh(lead)
        self.assertEqual(lead.assigned_to, self.ROUTED_OWNER_ID)
        self.assertEqual(lead.owner_user_id, self.ROUTED_OWNER_ID)

        # Step 4 bis — Inactive owner is silently ignored -----------------
        self.db.add(
            User(
                id="user_inactive",
                full_name="Inactive",
                email="inactive@example.com",
                role_id="role_test",
                status="disabled",
            ),
        )
        self.db.commit()
        n8n_callback_service.handle_routing_result(
            CrmRoutingResultPayload(
                lead_id=self.LEAD_ID,
                assigned_to="user_inactive",
            ),
            self.db,
        )
        self.db.refresh(lead)
        self.assertEqual(
            lead.assigned_to,
            self.ROUTED_OWNER_ID,
            "Inactive user must NOT replace a valid active owner.",
        )

        # Step 5 — Draft generation (outbox + sync mock OK) ---------------
        crm_service.generate_communication_draft_for_lead(self.db, self.LEAD_ID)
        outbox_after_draft = self.db.scalars(
            select(WebhookOutbox).where(
                WebhookOutbox.workflow_name == "FP_CRM_02_Communication_Draft"
            )
        ).all()
        self.assertEqual(len(outbox_after_draft), 1)
        self.assertEqual(outbox_after_draft[0].status, "sent")

        # Step 6 — Draft callback persists the email draft ----------------
        n8n_callback_service.handle_communication_result(
            CrmCommunicationResultPayload(
                lead_id=self.LEAD_ID,
                draft_type="sales",
                email_subject="Discovery call invitation",
                email_body="<p>Hello Lifecycle Tester,</p><p>Let's chat.</p>",
                communication_status="draft_generated",
                workflow_execution=self._workflow_trace(),
            ),
            self.db,
        )
        draft = self.db.scalars(
            select(CrmEmailDraft).where(CrmEmailDraft.lead_id == self.LEAD_ID)
        ).first()
        self.assertIsNotNone(draft)
        self.assertEqual(draft.draft_type, "sales")
        self.assertEqual(draft.status, "draft_generated")
        draft_id = draft.id

        # Step 7 — Review (Phase 1 Fix 3: real reviewer) ------------------
        crm_service.review_email_draft(self.db, draft_id, self.REVIEWER_ID)
        self.db.refresh(draft)
        self.assertEqual(draft.status, "reviewed")
        self.assertEqual(draft.reviewed_by, self.REVIEWER_ID)

        # Step 8 — Approve (Phase 1 Fix 3: real approver) -----------------
        crm_service.approve_email_draft(self.db, draft_id, self.REVIEWER_ID)
        self.db.refresh(draft)
        self.assertEqual(draft.status, "approved")
        self.assertEqual(draft.approved_by, self.REVIEWER_ID)

        # Step 9 — Send (outbox + draft.status='sending') -----------------
        crm_service.send_approved_email_draft(
            self.db, draft_id, requested_by=self.REVIEWER_ID
        )
        self.db.refresh(draft)
        self.assertEqual(draft.status, "sending")

        # Step 10 — Second send returns 409 (Phase 2 Fix 2 idempotence) ---
        with self.assertRaises(HTTPException) as ctx:
            crm_service.send_approved_email_draft(
                self.db, draft_id, requested_by=self.REVIEWER_ID
            )
        self.assertEqual(ctx.exception.status_code, 409)

        # Step 11 — email-sent callback persists + creates follow-up task -
        n8n_callback_service.handle_email_sent_result(
            CrmEmailSentResultPayload(
                draft_id=draft_id,
                lead_id=self.LEAD_ID,
                status="sent",
                send_mode="real",
                provider="gmail",
                provider_message_id="gmail_test_42",
            ),
            self.db,
        )
        self.db.refresh(draft)
        self.assertEqual(draft.status, "sent")

        follow_ups = self.db.scalars(
            select(CrmTask).where(
                CrmTask.lead_id == self.LEAD_ID,
                CrmTask.task_type == "follow_up",
            )
        ).all()
        self.assertEqual(
            len(follow_ups), 1, "Phase 3 Fix 3 must auto-create a follow-up task."
        )
        self.assertEqual(follow_ups[0].status, "pending")
        self.assertEqual(follow_ups[0].owner_user_id, self.ROUTED_OWNER_ID)

        # Step 12 — Replay the email-sent callback: no duplicate task -----
        # We force draft back to 'sending' to make the replay non-idempotent
        # at the draft level but still hit the follow-up dedup guard.
        draft.status = "sending"
        self.db.commit()
        n8n_callback_service.handle_email_sent_result(
            CrmEmailSentResultPayload(
                draft_id=draft_id,
                lead_id=self.LEAD_ID,
                status="sent",
                send_mode="real",
                provider="gmail",
                provider_message_id="gmail_test_42_replay",
            ),
            self.db,
        )
        follow_ups_after_replay = self.db.scalars(
            select(CrmTask).where(
                CrmTask.lead_id == self.LEAD_ID,
                CrmTask.task_type == "follow_up",
            )
        ).all()
        self.assertEqual(
            len(follow_ups_after_replay),
            1,
            "Dedup must prevent a second follow-up task while one is pending.",
        )

        # Step 13 — Convert lead to customer ------------------------------
        crm_service.convert_lead_to_customer(
            self.db,
            self.LEAD_ID,
            CrmCustomerConversionRequest(
                human_validated=True,
                validation_reason="Signed engagement letter.",
                evidence_source="Email confirmation.",
                next_action="Kick off onboarding.",
                conversion_note="High-value account.",
                requested_by=self.REVIEWER_ID,
            ),
        )
        self.db.refresh(lead)
        self.assertEqual(lead.customer_status, "conversion_pending")

        # Step 14 — Welcome draft callback finalises customer status ------
        n8n_callback_service.handle_communication_result(
            CrmCommunicationResultPayload(
                lead_id=self.LEAD_ID,
                draft_type="welcome",
                email_subject="Bienvenue chez FlowPilot AI",
                email_body="<p>Welcome onboard.</p>",
                communication_status="draft_generated",
                workflow_execution=self._workflow_trace(),
            ),
            self.db,
        )
        self.db.refresh(lead)
        self.assertEqual(
            lead.customer_status,
            "customer",
            "Phase 1 Fix 5: welcome callback must finalize conversion_pending.",
        )

        # Step 15 — Outbox state: every row should be 'sent' --------------
        outbox_rows = self.db.scalars(select(WebhookOutbox)).all()
        self.assertGreaterEqual(len(outbox_rows), 3)
        statuses = {row.status for row in outbox_rows}
        self.assertEqual(
            statuses,
            {"sent"},
            f"All outbox rows should be 'sent' under mocked n8n. Got {statuses}.",
        )

        # Step 16 — Workflow trace success (Phase 4 Fix 4) ----------------
        trace_response = crm_service.record_crm_workflow_trace(
            CrmWorkflowTracePayload(
                workflow_name="FP_CRM_08_Weekly_Reporting",
                status="success",
                execution_id="exec_test_001",
                summary="Weekly report delivered.",
                related_object_type="weekly_report",
            ),
            self.db,
        )
        self.assertEqual(trace_response.status, "success")
        we = self.db.get(WorkflowExecution, trace_response.workflow_execution_id)
        self.assertIsNotNone(we)
        self.assertEqual(we.status, "success")

        # Step 17 — Workflow trace failed without error_message rejects ---
        with self.assertRaises(HTTPException) as ctx:
            crm_service.record_crm_workflow_trace(
                CrmWorkflowTracePayload(
                    workflow_name="FP_CRM_08_Weekly_Reporting",
                    status="failed",
                    error_message="",
                ),
                self.db,
            )
        self.assertEqual(ctx.exception.status_code, 422)

        # Step 18 — Pagination contract (Phase 4 Fix 2) -------------------
        # Add a few more leads to exercise pagination math.
        for i in range(3):
            self.db.add(
                CrmLead(
                    id=f"lead_extra_{i}",
                    full_name=f"Extra {i}",
                    company_name="Extra Co",
                    email=f"extra{i}@example.com",
                    status="new",
                    customer_status="lead",
                )
            )
        self.db.commit()

        page = crm_service.get_crm_leads(self.db, page=1, page_size=2)
        self.assertEqual(page.pagination.page, 1)
        self.assertEqual(page.pagination.page_size, 2)
        self.assertEqual(page.pagination.total_items, 4)
        self.assertEqual(page.pagination.total_pages, 2)
        self.assertEqual(len(page.items), 2)

        # Page_size clamp: a request for 500 is capped at 100.
        page_clamped = crm_service.get_crm_leads(self.db, page=1, page_size=500)
        self.assertLessEqual(page_clamped.pagination.page_size, 100)


if __name__ == "__main__":
    unittest.main()
