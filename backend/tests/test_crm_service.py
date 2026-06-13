import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base, CrmLead
from app.services import crm_service


class FakeN8nResponse:
    def __enter__(self) -> "FakeN8nResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    def read(self) -> bytes:
        return b'{"triggered": true}'


class CrmServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_generate_communication_draft_posts_lead_context_to_n8n(self) -> None:
        lead = CrmLead(
            id="lead_n8n_trace_test_001",
            full_name="atef ben hadef",
            company_name="Trace Company",
            email="trace.test@example.com",
            phone="+21622333444",
            source="website_form",
            status="hot",
            lead_score=88,
            message="Need a CRM automation proposal.",
            product_service="AI CRM Automation",
            intention="purchase",
            urgency="high",
            priority="high",
            ai_summary="Strong lead with clear CRM automation intent.",
            recommended_action="Send a personalized draft.",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(lead)
        self.db.commit()

        original_base_url = crm_service.settings.N8N_WEBHOOK_BASE_URL
        original_secret = crm_service.settings.FLOWPILOT_N8N_SHARED_SECRET
        crm_service.settings.N8N_WEBHOOK_BASE_URL = "http://n8n.local/webhook/"
        crm_service.settings.FLOWPILOT_N8N_SHARED_SECRET = "test-secret"

        try:
            # urlopen lives in webhook_outbox_service now: crm_service goes
            # through enqueue + sync_attempt, and sync_attempt is what calls
            # urlopen. The HTTP behaviour and posted payload stay identical.
            with patch(
                "app.services.webhook_outbox_service.urlopen",
                return_value=FakeN8nResponse(),
            ) as mocked_urlopen:
                result = crm_service.generate_communication_draft_for_lead(
                    self.db,
                    "lead_n8n_trace_test_001",
                )
        finally:
            crm_service.settings.N8N_WEBHOOK_BASE_URL = original_base_url
            crm_service.settings.FLOWPILOT_N8N_SHARED_SECRET = original_secret

        request = mocked_urlopen.call_args.args[0]
        posted_payload = json.loads(request.data.decode("utf-8"))

        self.assertEqual(result.lead_id, "lead_n8n_trace_test_001")
        self.assertEqual(result.n8n_response, {"triggered": True})
        self.assertEqual(
            request.full_url,
            "http://n8n.local/webhook/flowpilot-crm-communication-draft",
        )
        self.assertEqual(request.get_header("X-flowpilot-secret"), "test-secret")
        self.assertEqual(posted_payload["lead_id"], "lead_n8n_trace_test_001")
        # full_name est normalise (toTitleCase) avant l'envoi au workflow CRM_02.
        self.assertEqual(posted_payload["full_name"], "Atef Ben Hadef")
        self.assertEqual(posted_payload["requested_by"], "user_030")


if __name__ == "__main__":
    unittest.main()
