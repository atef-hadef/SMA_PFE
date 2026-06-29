import json
import unittest
from datetime import date
from unittest.mock import patch

import pytest

ODOO_DEPRECATED_REASON = "Odoo workflow deprecated - standalone mode active"

from fastapi import HTTPException
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.api.leave_requests import submit_leave_request
from app.models import AgentRun, Base, LeaveRequest, Role, User, WorkflowExecution
from app.schemas.leave_requests import (
    LeaveAutomationAnalysisCallback,
    LeaveRequestCreate,
    LeaveDecisionSyncCallback,
)
from app.services.leave_service import (
    LeaveBalanceValidationError,
    approve_leave_request,
    create_leave_request,
    get_pending_leave_requests,
    reject_leave_request,
    save_leave_automation_analysis,
    save_leave_decision_sync_result,
)


class FakeN8nResponse:
    def __enter__(self) -> "FakeN8nResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    def read(self) -> bytes:
        return b'{"triggered": true}'


class FakeJsonResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeJsonResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class LeaveCallbackServiceTest(unittest.TestCase):
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
                id="user_010",
                full_name="Employee Test",
                email="employee.test@example.com",
                role_id="role_test",
            ),
        )
        self.db.add(
            User(
                id="user_020",
                full_name="Manager Test",
                email="manager.test@example.com",
                role_id="role_test",
            ),
        )
        self.db.commit()
        self.db.add(
            LeaveRequest(
                id="leave_callback_test_001",
                user_id="user_010",
                leave_type="Congé annuel",
                start_date=date(2026, 5, 20),
                end_date=date(2026, 5, 21),
                reason="Family event",
                status="pending",
            ),
        )
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_automation_analysis_updates_leave_and_creates_traces(self) -> None:
        payload = LeaveAutomationAnalysisCallback(
            ok=True,
            workflow="FP_LEAVE_01_REQUEST_ANALYSIS",
            branch="created_pending_manager_approval",
            odoo_leave_id=42,
            odoo_state="confirm",
            recommendation="recommended_approval",
            recommendation_label="Approbation recommandée",
            score=100,
        )

        result = save_leave_automation_analysis(
            "leave_callback_test_001",
            payload,
            self.db,
        )

        leave_request = self.db.get(LeaveRequest, "leave_callback_test_001")
        workflow_executions = list(self.db.scalars(select(WorkflowExecution)).all())
        agent_runs = list(self.db.scalars(select(AgentRun)).all())

        self.assertTrue(result.ok)
        self.assertIsNotNone(leave_request)
        self.assertEqual(leave_request.odoo_leave_id, "42")
        self.assertEqual(leave_request.odoo_state, "confirm")
        self.assertEqual(leave_request.odoo_sync_status, "synced")
        self.assertEqual(leave_request.status, "manager_review_required")
        self.assertEqual(leave_request.automation_recommendation, "recommended_approval")
        self.assertEqual(leave_request.score, 100)
        self.assertEqual(len(workflow_executions), 1)
        self.assertEqual(workflow_executions[0].process, "leave_request")
        self.assertEqual(workflow_executions[0].related_object_type, "leave_request")
        self.assertEqual(workflow_executions[0].related_object_id, "leave_callback_test_001")
        self.assertEqual(len(agent_runs), 1)
        self.assertEqual(agent_runs[0].agent_name, "HR Leave Request Analysis")
        self.assertEqual(agent_runs[0].workflow_execution_id, workflow_executions[0].id)

    def test_automation_analysis_preserves_insufficient_balance_justification(self) -> None:
        payload = LeaveAutomationAnalysisCallback(
            ok=True,
            workflow="FP_LEAVE_01_REQUEST_ANALYSIS",
            branch="created_pending_manager_approval",
            odoo_leave_id=42,
            odoo_state="confirm",
            recommendation="reject",
            recommendation_label="Refus recommandé",
            score=25,
            available_days=13,
            requested_days=24,
            has_enough_balance=False,
            ai_explanation=(
                "La demande dépasse le solde disponible. Le collaborateur demande "
                "24 jours alors que seulement 13 jours sont disponibles."
            ),
            decision_reasons=[
                "Solde disponible insuffisant",
                "Durée demandée supérieure au solde",
                "Écart de 11 jours",
            ],
            blocking_reasons=[
                "Le solde disponible ne couvre pas la période demandée",
            ],
            approval_factors=[
                "Le manager peut accepter uniquement en cas d'exception RH validée",
            ],
            rejection_factors=[
                "Demande supérieure au solde disponible",
                "Risque RH élevé",
            ],
            manager_guidance=(
                "Refuser la demande ou demander au collaborateur de réduire la période."
            ),
            balance_gap_days=11,
            can_manager_override=True,
            risk_level="high",
        )

        result = save_leave_automation_analysis(
            "leave_callback_test_001",
            payload,
            self.db,
        )
        pending_response = get_pending_leave_requests(self.db)
        pending_item = pending_response.items[0]

        self.assertTrue(result.ok)
        self.assertEqual(pending_item.ai_recommendation, "reject")
        self.assertEqual(pending_item.risk_level, "high")
        self.assertEqual(pending_item.available_days, 13)
        self.assertEqual(pending_item.requested_days, 24)
        self.assertEqual(pending_item.balance_gap_days, 11)
        self.assertIn("dépasse le solde disponible", pending_item.ai_explanation)
        self.assertIn("Solde disponible insuffisant", pending_item.decision_reasons)
        self.assertEqual(
            pending_item.manager_guidance,
            "Refuser la demande ou demander au collaborateur de réduire la période.",
        )
        self.assertTrue(pending_item.can_manager_override)
        self.assertTrue(pending_item.can_sync_with_odoo)

    def test_failed_decision_sync_preserves_manager_decision(self) -> None:
        leave_request = self.db.get(LeaveRequest, "leave_callback_test_001")
        self.assertIsNotNone(leave_request)
        leave_request.status = "approved"
        leave_request.reviewed_by = "user_020"
        self.db.commit()

        payload = LeaveDecisionSyncCallback(
            ok=False,
            workflow="FP_LEAVE_02_DECISION_SYNC",
            decision="approved",
            odoo_leave_id=42,
            odoo_state="confirm",
            manager_comment="Approved locally.",
            error_message="Odoo validation failed.",
        )

        result = save_leave_decision_sync_result(
            "leave_callback_test_001",
            payload,
            self.db,
        )

        leave_request = self.db.get(LeaveRequest, "leave_callback_test_001")

        self.assertTrue(result.ok)
        self.assertIsNotNone(leave_request)
        self.assertEqual(leave_request.status, "approved")
        self.assertEqual(leave_request.odoo_sync_status, "failed")
        self.assertEqual(leave_request.odoo_state, "confirm")
        self.assertEqual(leave_request.decision_comment, "Approved locally.")
        self.assertIn("Local manager decision was preserved", leave_request.automation_summary)

    @pytest.mark.skip(reason=ODOO_DEPRECATED_REASON)
    def test_create_leave_request_triggers_workflow_1_with_odoo_payload(self) -> None:
        with patch(
            "app.services.leave_service.urlopen",
            side_effect=[
                FakeJsonResponse(
                    {
                        "ok": True,
                        "status": "sufficient_balance",
                        "available_days": 13,
                        "requested_days": 2,
                        "has_enough_balance": True,
                    }
                ),
                FakeN8nResponse(),
            ],
        ) as mocked_urlopen:
            result = create_leave_request(
                payload=LeaveRequestCreate(
                    leave_type="Congé annuel",
                    start_date=date(2026, 5, 22),
                    end_date=date(2026, 5, 23),
                    reason="Family event",
                ),
                db=self.db,
            )

        precheck_request = mocked_urlopen.call_args_list[0].args[0]
        precheck_payload = json.loads(precheck_request.data.decode("utf-8"))
        request = mocked_urlopen.call_args_list[1].args[0]
        posted_payload = json.loads(request.data.decode("utf-8"))
        workflow_execution = self.db.get(
            WorkflowExecution,
            posted_payload["workflow_execution_id"],
        )

        self.assertEqual(
            precheck_request.full_url,
            "http://localhost:5678/webhook/flowpilot/leave/balance-precheck",
        )
        self.assertEqual(precheck_payload["employee_id"], "user_010")
        self.assertEqual(precheck_payload["odoo_employee_id"], 3)
        self.assertEqual(precheck_payload["leave_type"], "Congé annuel")
        self.assertEqual(precheck_payload["odoo_leave_type_id"], 5)
        self.assertEqual(precheck_payload["date_from"], "2026-05-22")
        self.assertEqual(precheck_payload["date_to"], "2026-05-23")
        self.assertEqual(precheck_payload["requested_days"], 2.0)
        self.assertEqual(precheck_payload["odoo_base_url"], "http://host.docker.internal:8069")
        self.assertEqual(precheck_payload["odoo_db"], "flowpilot_odoo")
        self.assertEqual(precheck_payload["odoo_uid"], 2)
        self.assertEqual(precheck_payload["odoo_password"], "123456789")
        self.assertEqual(
            request.full_url,
            "http://host.docker.internal:5678/webhook/flowpilot/leave/request-analysis",
        )
        self.assertEqual(posted_payload["flowpilot_request_id"], result.id)
        self.assertEqual(posted_payload["flowpilot_api_base_url"], "http://host.docker.internal:8000")
        self.assertEqual(posted_payload["odoo_base_url"], "http://host.docker.internal:8069")
        self.assertEqual(posted_payload["odoo_db"], "flowpilot_odoo")
        self.assertEqual(posted_payload["odoo_uid"], 2)
        self.assertEqual(posted_payload["odoo_password"], "123456789")
        self.assertEqual(posted_payload["employee_id"], "user_010")
        self.assertEqual(posted_payload["odoo_employee_id"], 3)
        self.assertEqual(posted_payload["odoo_department_id"], 2)
        self.assertEqual(posted_payload["odoo_leave_type_id"], 5)
        self.assertEqual(posted_payload["requested_days"], 2.0)
        self.assertIsNotNone(workflow_execution)
        self.assertEqual(workflow_execution.status, "running")

    def test_create_leave_request_blocks_insufficient_balance_before_insert(self) -> None:
        initial_leave_count = len(list(self.db.scalars(select(LeaveRequest)).all()))

        with patch(
            "app.services.leave_service.urlopen",
            side_effect=[
                FakeJsonResponse(
                    {
                        "ok": False,
                        "status": "insufficient_balance",
                        "error_code": "INSUFFICIENT_LEAVE_BALANCE",
                        "available_days": 13,
                        "requested_days": 24,
                        "balance_gap_days": 11,
                        "has_enough_balance": False,
                        "recommendation": "rejected_by_policy",
                        "recommendation_label": "Refus recommandÃ©",
                        "risk_level": "high",
                        "ai_explanation": "Votre solde disponible est insuffisant.",
                        "employee_guidance": (
                            "Veuillez rÃ©duire la pÃ©riode demandÃ©e ou contacter "
                            "le service RH pour une exception."
                        ),
                        "message": (
                            "Votre solde disponible est insuffisant. Vous disposez de "
                            "13 jour(s), mais vous demandez 24 jour(s)."
                        ),
                    }
                ),
            ],
        ) as mocked_urlopen:
            with self.assertRaises(LeaveBalanceValidationError) as context:
                create_leave_request(
                    payload=LeaveRequestCreate(
                        leave_type="CongÃ© annuel",
                        start_date=date(2026, 5, 1),
                        end_date=date(2026, 5, 24),
                        reason="Long leave",
                    ),
                    db=self.db,
                )

        leave_count = len(list(self.db.scalars(select(LeaveRequest)).all()))
        workflow_count = len(list(self.db.scalars(select(WorkflowExecution)).all()))

        self.assertEqual(leave_count, initial_leave_count)
        self.assertEqual(workflow_count, 0)
        self.assertEqual(mocked_urlopen.call_count, 1)
        self.assertEqual(
            mocked_urlopen.call_args.args[0].full_url,
            "http://localhost:5678/webhook/flowpilot/leave/balance-precheck",
        )
        self.assertEqual(context.exception.data.available_days, 13)
        self.assertEqual(context.exception.data.requested_days, 24)
        self.assertEqual(context.exception.data.balance_gap_days, 11)
        self.assertEqual(context.exception.data.recommendation, "rejected_by_policy")
        self.assertEqual(context.exception.data.error_code, "INSUFFICIENT_LEAVE_BALANCE")
        self.assertIn("Veuillez", context.exception.data.employee_guidance)

    def test_submit_leave_request_returns_422_for_insufficient_balance(self) -> None:
        initial_leave_count = len(list(self.db.scalars(select(LeaveRequest)).all()))

        with patch(
            "app.services.leave_service.urlopen",
            return_value=FakeJsonResponse(
                {
                    "ok": False,
                    "status": "insufficient_balance",
                    "error_code": "INSUFFICIENT_LEAVE_BALANCE",
                    "available_days": 13,
                    "requested_days": 24,
                    "balance_gap_days": 11,
                    "has_enough_balance": False,
                    "recommendation": "rejected_by_policy",
                    "recommendation_label": "Refus recommandé",
                    "risk_level": "high",
                    "ai_explanation": "La demande dépasse le solde disponible.",
                    "employee_guidance": (
                        "Veuillez réduire la période demandée ou contacter le service RH "
                        "pour une exception."
                    ),
                    "message": (
                        "Votre solde disponible est insuffisant. Veuillez réduire la "
                        "période demandée."
                    ),
                }
            ),
        ) as mocked_urlopen:
            response = submit_leave_request(
                payload=LeaveRequestCreate(
                    leave_type="annual",
                    start_date=date(2026, 5, 12),
                    end_date=date(2026, 6, 4),
                    reason="Long leave",
                ),
                db=self.db,
            )

        response_payload = json.loads(response.body.decode("utf-8"))
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response_payload["error"]["code"], "INSUFFICIENT_LEAVE_BALANCE")
        self.assertEqual(response_payload["data"]["balance_gap_days"], "11")
        self.assertEqual(
            len(list(self.db.scalars(select(LeaveRequest)).all())),
            initial_leave_count,
        )
        self.assertEqual(mocked_urlopen.call_count, 1)

    def test_submit_leave_request_returns_422_for_period_overlap(self) -> None:
        initial_leave_count = len(list(self.db.scalars(select(LeaveRequest)).all()))

        with patch(
            "app.services.leave_service.urlopen",
            return_value=FakeJsonResponse(
                {
                    "ok": False,
                    "status": "leave_period_overlap",
                    "error_code": "LEAVE_PERIOD_OVERLAP",
                    "conflict_detected": True,
                    "conflict_type": "employee_period_overlap",
                    "overlapping_leave_count": 1,
                    "overlapping_leaves": [
                        {
                            "id": 9,
                            "name": "test",
                            "date_from": "2026-05-13",
                            "date_to": "2026-05-15",
                            "state": "validate",
                            "number_of_days": 3,
                        }
                    ],
                    "recommendation": "change_dates",
                    "recommendation_label": "Modifier la période",
                    "risk_level": "high",
                    "ai_explanation": (
                        "La période demandée chevauche déjà un congé validé pour cet employé."
                    ),
                    "employee_guidance": "Veuillez choisir une autre période.",
                    "message": (
                        "La période demandée chevauche déjà un congé validé. "
                        "Veuillez choisir d’autres dates."
                    ),
                }
            ),
        ) as mocked_urlopen:
            response = submit_leave_request(
                payload=LeaveRequestCreate(
                    leave_type="annual",
                    start_date=date(2026, 5, 12),
                    end_date=date(2026, 5, 14),
                    reason="Overlapping leave",
                ),
                db=self.db,
            )

        response_payload = json.loads(response.body.decode("utf-8"))
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response_payload["error"]["code"], "LEAVE_PERIOD_OVERLAP")
        self.assertTrue(response_payload["data"]["conflict_detected"])
        self.assertEqual(response_payload["data"]["conflict_type"], "employee_period_overlap")
        self.assertEqual(response_payload["data"]["date_from"], "2026-05-12")
        self.assertEqual(response_payload["data"]["date_to"], "2026-05-14")
        self.assertEqual(response_payload["data"]["requested_days"], "3.0")
        self.assertEqual(
            response_payload["data"]["overlapping_leaves"][0]["date_from"],
            "2026-05-13",
        )
        self.assertEqual(
            response_payload["data"]["overlapping_leaves"][0]["date_to"],
            "2026-05-15",
        )
        self.assertEqual(
            len(list(self.db.scalars(select(LeaveRequest)).all())),
            initial_leave_count,
        )
        self.assertEqual(mocked_urlopen.call_count, 1)

    @pytest.mark.skip(reason=ODOO_DEPRECATED_REASON)
    def test_create_leave_request_with_sufficient_balance_triggers_workflow_1(self) -> None:
        with patch(
            "app.services.leave_service.urlopen",
            side_effect=[
                FakeJsonResponse(
                    {
                        "ok": True,
                        "status": "sufficient_balance",
                        "available_days": 13,
                        "requested_days": 2,
                        "has_enough_balance": True,
                    }
                ),
                FakeN8nResponse(),
            ],
        ) as mocked_urlopen:
            result = create_leave_request(
                payload=LeaveRequestCreate(
                    leave_type="CongÃ© annuel",
                    start_date=date(2026, 5, 22),
                    end_date=date(2026, 5, 23),
                    reason="Short leave",
                ),
                db=self.db,
            )

        request = mocked_urlopen.call_args_list[1].args[0]
        posted_payload = json.loads(request.data.decode("utf-8"))
        leave_request = self.db.get(LeaveRequest, result.id)

        self.assertEqual(mocked_urlopen.call_count, 2)
        self.assertEqual(
            request.full_url,
            "http://host.docker.internal:5678/webhook/flowpilot/leave/request-analysis",
        )
        self.assertIsNotNone(leave_request)
        self.assertEqual(posted_payload["flowpilot_request_id"], result.id)
        self.assertEqual(posted_payload["requested_days"], 2.0)

    @pytest.mark.skip(reason=ODOO_DEPRECATED_REASON)
    def test_approve_leave_request_triggers_workflow_2(self) -> None:
        leave_request = self.db.get(LeaveRequest, "leave_callback_test_001")
        self.assertIsNotNone(leave_request)
        leave_request.status = "manager_review_required"
        leave_request.odoo_leave_id = "42"
        self.db.commit()

        with patch(
            "app.services.leave_service.urlopen",
            return_value=FakeN8nResponse(),
        ) as mocked_urlopen:
            result = approve_leave_request(
                request_id="leave_callback_test_001",
                comment="Approved from test.",
                db=self.db,
            )

        request = mocked_urlopen.call_args.args[0]
        posted_payload = json.loads(request.data.decode("utf-8"))

        self.assertEqual(result.status, "approved")
        self.assertEqual(
            request.full_url,
            "http://host.docker.internal:5678/webhook/flowpilot/leave/decision-sync",
        )
        self.assertEqual(posted_payload["flowpilot_request_id"], "leave_callback_test_001")
        self.assertEqual(posted_payload["odoo_leave_id"], "42")
        self.assertEqual(posted_payload["decision"], "approved")
        self.assertEqual(posted_payload["manager_comment"], "Approved from test.")
        self.assertEqual(posted_payload["employee_id"], "user_010")

    def test_approve_without_odoo_leave_id_does_not_trigger_workflow_2(self) -> None:
        leave_request = self.db.get(LeaveRequest, "leave_callback_test_001")
        self.assertIsNotNone(leave_request)
        leave_request.status = "manager_review_required"
        leave_request.odoo_leave_id = None
        self.db.commit()

        with patch("app.services.leave_service.urlopen") as mocked_urlopen:
            with self.assertRaises(HTTPException) as context:
                approve_leave_request(
                    request_id="leave_callback_test_001",
                    comment="Approved without Odoo id.",
                    db=self.db,
                )

        self.assertEqual(context.exception.status_code, 422)
        mocked_urlopen.assert_not_called()

    def test_reject_leave_request_triggers_workflow_2(self) -> None:
        leave_request = self.db.get(LeaveRequest, "leave_callback_test_001")
        self.assertIsNotNone(leave_request)
        leave_request.status = "manager_review_required"
        leave_request.odoo_leave_id = "42"
        self.db.commit()

        with patch(
            "app.services.leave_service.urlopen",
            return_value=FakeN8nResponse(),
        ) as mocked_urlopen:
            result = reject_leave_request(
                request_id="leave_callback_test_001",
                comment="Rejected from test.",
                db=self.db,
            )

        request = mocked_urlopen.call_args.args[0]
        posted_payload = json.loads(request.data.decode("utf-8"))

        self.assertEqual(result.status, "rejected")
        self.assertEqual(posted_payload["decision"], "rejected")
        self.assertEqual(posted_payload["manager_comment"], "Rejected from test.")


if __name__ == "__main__":
    unittest.main()
