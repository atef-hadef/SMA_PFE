import unittest

from fastapi import HTTPException

from app.api.assistant import assistant_action
from app.schemas.assistant import AssistantActionRequest, SuggestedAction
from app.schemas.auth import AuthUser


class AssistantActionTest(unittest.TestCase):
    def test_rejects_unauthorized_mutating_action(self) -> None:
        user = AuthUser(
            id="user_test",
            full_name="Test User",
            email="test@example.com",
            role_id="role_sales",
            role_name="Sales",
            permissions=["dashboard.view", "crm.leads.view"],
            status="active",
        )
        payload = AssistantActionRequest(
            confirmed=True,
            idempotency_key="idem_test",
            action=SuggestedAction(
                label="Envoyer l'email approuvé",
                action_type="send_approved_email",
                payload={"draft_id": "draft_test"},
            ),
        )

        with self.assertRaises(HTTPException) as ctx:
            assistant_action(payload, current_user=user)

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("crm.email.send", str(ctx.exception.detail))

    def test_accepts_non_mutating_navigation_action(self) -> None:
        user = AuthUser(
            id="user_test",
            full_name="Test User",
            email="test@example.com",
            role_id="role_employee",
            role_name="Employee",
            permissions=["dashboard.view"],
            status="active",
        )
        payload = AssistantActionRequest(
            action=SuggestedAction(
                label="Ouvrir le CRM",
                action_type="navigate",
                payload={"route": "/crm-leads"},
            ),
        )

        result = assistant_action(payload, current_user=user)

        self.assertTrue(result.success)
        self.assertEqual(result.data.status, "accepted")


if __name__ == "__main__":
    unittest.main()
