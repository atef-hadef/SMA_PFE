"""Unit tests for CrmTask and CrmDeal services (WF 06 + WF 07)."""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.models import Base, CrmLead, Role, User
from app.schemas.crm_tasks_deals import (
    CrmDealCreate,
    CrmDealStageTransitionRequest,
    CrmTaskCreate,
    CrmTaskUpdate,
)
from app.services.crm_comments_service import (
    create_comment,
    delete_comment,
    list_comments,
)
from app.services.crm_deals_service import (
    create_deal,
    list_deals,
    transition_deal_stage,
)
from app.services.crm_tasks_service import (
    create_task,
    list_pending_followup_tasks,
    list_tasks,
    list_team_members,
    mark_tasks_reminded,
    update_task,
)
from app.schemas.crm_tasks_deals import CrmCommentCreate


def utc(year: int, month: int, day: int, hour: int = 12) -> datetime:
    return datetime(year, month, day, hour, tzinfo=timezone.utc)


class CrmTasksAndDealsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")

        @event.listens_for(self.engine, "connect")
        def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
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
                email="owner@example.com",
                role_id="role_test",
            ),
        )
        self.db.add(
            User(
                id="user_020",
                full_name="Sales Manager",
                email="manager@example.com",
                role_id="role_test",
            ),
        )
        self.db.add(
            CrmLead(
                id="lead_xyz",
                full_name="Test Lead",
                company_name="Test Co",
                email="lead@example.com",
                status="hot",
                customer_status="prospect",
                lead_score=80,
            ),
        )
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    # -------- Tasks --------

    def test_create_task_persists_and_returns_item(self) -> None:
        item = create_task(
            self.db,
            CrmTaskCreate(
                title="Call prospect",
                description="Discovery call",
                due_date=utc(2027, 5, 25),
                priority="high",
                lead_id="lead_xyz",
                owner_user_id="user_030",
            ),
            created_by="user_030",
        )
        self.assertTrue(item.id.startswith("task_"))
        self.assertEqual(item.status, "pending")
        self.assertEqual(item.priority, "high")
        self.assertFalse(item.is_overdue)

    def test_create_task_with_unknown_owner_rejected(self) -> None:
        with self.assertRaises(HTTPException) as cm:
            create_task(
                self.db,
                CrmTaskCreate(
                    title="X",
                    due_date=utc(2027, 5, 25),
                    owner_user_id="unknown_user",
                ),
                created_by="user_030",
            )
        self.assertEqual(cm.exception.status_code, 422)

    def test_update_task_to_done_sets_completed_at(self) -> None:
        item = create_task(
            self.db,
            CrmTaskCreate(
                title="Send proposal",
                due_date=utc(2027, 5, 25),
                owner_user_id="user_030",
            ),
            created_by="user_030",
        )
        updated = update_task(self.db, item.id, CrmTaskUpdate(status="done"))
        self.assertEqual(updated.status, "done")
        self.assertIsNotNone(updated.completed_at)

    def test_list_pending_followup_groups_by_owner(self) -> None:
        soon = datetime.now(timezone.utc) + timedelta(hours=12)
        far = datetime.now(timezone.utc) + timedelta(days=10)
        create_task(
            self.db,
            CrmTaskCreate(title="Urgent A", due_date=soon, owner_user_id="user_030"),
            created_by="user_030",
        )
        create_task(
            self.db,
            CrmTaskCreate(title="Urgent B", due_date=soon, owner_user_id="user_030"),
            created_by="user_030",
        )
        create_task(
            self.db,
            CrmTaskCreate(title="Urgent C", due_date=soon, owner_user_id="user_020"),
            created_by="user_020",
        )
        create_task(
            self.db,
            CrmTaskCreate(title="Later", due_date=far, owner_user_id="user_030"),
            created_by="user_030",
        )

        result = list_pending_followup_tasks(self.db, threshold_hours=48)
        self.assertEqual(result.total_tasks, 3)
        self.assertEqual(len(result.owners), 2)

        by_owner = {g.owner_user_id: g for g in result.owners}
        self.assertEqual(len(by_owner["user_030"].tasks), 2)
        self.assertEqual(len(by_owner["user_020"].tasks), 1)

    def test_mark_tasks_reminded_only_affects_pending(self) -> None:
        soon = datetime.now(timezone.utc) + timedelta(hours=6)
        pending_a = create_task(
            self.db,
            CrmTaskCreate(title="A", due_date=soon, owner_user_id="user_030"),
            created_by="user_030",
        )
        done_b = create_task(
            self.db,
            CrmTaskCreate(title="B", due_date=soon, owner_user_id="user_030"),
            created_by="user_030",
        )
        update_task(self.db, done_b.id, CrmTaskUpdate(status="done"))

        ack = mark_tasks_reminded(self.db, [pending_a.id, done_b.id])
        self.assertEqual(ack.task_ids, [pending_a.id])

    def test_list_tasks_filters_by_status(self) -> None:
        soon = datetime.now(timezone.utc) + timedelta(hours=6)
        a = create_task(
            self.db,
            CrmTaskCreate(title="A", due_date=soon, owner_user_id="user_030"),
            created_by="user_030",
        )
        b = create_task(
            self.db,
            CrmTaskCreate(title="B", due_date=soon, owner_user_id="user_030"),
            created_by="user_030",
        )
        update_task(self.db, b.id, CrmTaskUpdate(status="done"))

        pending = list_tasks(self.db, status="pending")
        self.assertEqual(pending.count, 1)
        self.assertEqual(pending.items[0].id, a.id)

    # -------- Deals --------

    def test_create_deal_with_unknown_lead_rejected(self) -> None:
        with self.assertRaises(HTTPException) as cm:
            create_deal(
                self.db,
                CrmDealCreate(
                    lead_id="ghost",
                    owner_user_id="user_030",
                    title="X",
                ),
            )
        self.assertEqual(cm.exception.status_code, 422)

    def test_deal_stage_transition_persists_and_triggers_webhook(self) -> None:
        deal = create_deal(
            self.db,
            CrmDealCreate(
                lead_id="lead_xyz",
                owner_user_id="user_030",
                title="Test Deal",
                amount=10000,
            ),
        )
        with patch(
            "app.services.crm_deals_service.webhook_outbox_service.sync_attempt",
            return_value={"ok": True},
        ) as webhook:
            response = transition_deal_stage(
                self.db,
                deal.id,
                CrmDealStageTransitionRequest(new_stage="proposal", reason="Sent proposal."),
                requested_by="user_030",
            )

        self.assertEqual(response.new_stage, "proposal")
        self.assertEqual(response.previous_stage, "discovery")
        self.assertTrue(response.workflow_triggered)
        webhook.assert_called_once()

    def test_deal_invalid_transition_rejected(self) -> None:
        deal = create_deal(
            self.db,
            CrmDealCreate(
                lead_id="lead_xyz",
                owner_user_id="user_030",
                title="Skip-ahead Deal",
            ),
        )
        with self.assertRaises(HTTPException) as cm:
            transition_deal_stage(
                self.db,
                deal.id,
                CrmDealStageTransitionRequest(new_stage="won", trigger_workflow=False),
                requested_by="user_030",
            )
        self.assertEqual(cm.exception.status_code, 422)

    def test_deal_won_closes_and_records_reason(self) -> None:
        deal = create_deal(
            self.db,
            CrmDealCreate(
                lead_id="lead_xyz",
                owner_user_id="user_030",
                title="Winning path",
                stage="closing",
            ),
        )
        with patch(
            "app.services.crm_deals_service.webhook_outbox_service.sync_attempt",
            return_value={},
        ):
            response = transition_deal_stage(
                self.db,
                deal.id,
                CrmDealStageTransitionRequest(new_stage="won", reason="Signed contract."),
                requested_by="user_030",
            )
        self.assertEqual(response.new_stage, "won")
        stored = list_deals(self.db).items[0]
        self.assertEqual(stored.stage, "won")
        self.assertEqual(stored.won_reason, "Signed contract.")
        self.assertIsNotNone(stored.closed_at)
        self.assertEqual(stored.probability_percent, 100)

    # -------- Names & relations enrichment --------

    def test_list_tasks_includes_lead_and_owner_names(self) -> None:
        create_task(
            self.db,
            CrmTaskCreate(
                title="Follow up Northwind",
                due_date=utc(2026, 6, 10),
                priority="high",
                lead_id="lead_xyz",
                owner_user_id="user_030",
            ),
            created_by="user_020",
        )
        response = list_tasks(self.db)
        item = response.items[0]
        self.assertEqual(item.owner_full_name, "CRM Owner")
        self.assertEqual(item.owner_email, "owner@example.com")
        self.assertEqual(item.lead_full_name, "Test Lead")
        self.assertEqual(item.lead_company_name, "Test Co")
        self.assertEqual(item.comments_count, 0)

    def test_list_deals_includes_lead_and_owner_names(self) -> None:
        create_deal(
            self.db,
            CrmDealCreate(
                lead_id="lead_xyz",
                owner_user_id="user_030",
                title="Test deal",
            ),
        )
        response = list_deals(self.db)
        item = response.items[0]
        self.assertEqual(item.owner_full_name, "CRM Owner")
        self.assertEqual(item.lead_full_name, "Test Lead")
        self.assertEqual(item.lead_company_name, "Test Co")
        self.assertEqual(item.comments_count, 0)

    def test_list_team_members_returns_active_users(self) -> None:
        response = list_team_members(self.db)
        emails = {member.email for member in response.items}
        self.assertIn("owner@example.com", emails)
        self.assertIn("manager@example.com", emails)

    # -------- Comments --------

    def test_create_task_comment_persists_and_exposes_author(self) -> None:
        task = create_task(
            self.db,
            CrmTaskCreate(
                title="Send proposal",
                due_date=utc(2026, 6, 10),
                priority="medium",
                lead_id="lead_xyz",
                owner_user_id="user_030",
            ),
            created_by="user_030",
        )
        comment = create_comment(
            self.db,
            "task",
            task.id,
            CrmCommentCreate(content="Client a confirmé l'intérêt par téléphone."),
            author_user_id="user_030",
        )
        self.assertEqual(comment.entity_type, "task")
        self.assertEqual(comment.entity_id, task.id)
        self.assertEqual(comment.author_full_name, "CRM Owner")
        self.assertEqual(comment.content, "Client a confirmé l'intérêt par téléphone.")

        listed = list_comments(self.db, "task", task.id)
        self.assertEqual(listed.count, 1)

        refreshed = list_tasks(self.db)
        self.assertEqual(refreshed.items[0].comments_count, 1)

    def test_delete_task_comment_only_removes_target(self) -> None:
        task = create_task(
            self.db,
            CrmTaskCreate(
                title="Demo prep",
                due_date=utc(2026, 6, 10),
                priority="medium",
                lead_id="lead_xyz",
                owner_user_id="user_030",
            ),
            created_by="user_030",
        )
        first = create_comment(
            self.db,
            "task",
            task.id,
            CrmCommentCreate(content="First comment"),
            author_user_id="user_030",
        )
        create_comment(
            self.db,
            "task",
            task.id,
            CrmCommentCreate(content="Second comment"),
            author_user_id="user_020",
        )
        delete_comment(self.db, "task", task.id, first.id)
        remaining = list_comments(self.db, "task", task.id)
        self.assertEqual(remaining.count, 1)
        self.assertEqual(remaining.items[0].content, "Second comment")

    def test_create_deal_comment_persists_separately_from_task_comment(self) -> None:
        task = create_task(
            self.db,
            CrmTaskCreate(
                title="Demo prep",
                due_date=utc(2026, 6, 10),
                priority="medium",
                lead_id="lead_xyz",
                owner_user_id="user_030",
            ),
            created_by="user_030",
        )
        create_comment(
            self.db,
            "task",
            task.id,
            CrmCommentCreate(content="Task comment"),
            author_user_id="user_030",
        )
        deal = create_deal(
            self.db,
            CrmDealCreate(
                lead_id="lead_xyz",
                owner_user_id="user_030",
                title="Test deal",
            ),
        )
        create_comment(
            self.db,
            "deal",
            deal.id,
            CrmCommentCreate(content="Deal comment"),
            author_user_id="user_020",
        )
        task_comments = list_comments(self.db, "task", task.id)
        deal_comments = list_comments(self.db, "deal", deal.id)
        self.assertEqual(task_comments.count, 1)
        self.assertEqual(deal_comments.count, 1)
        self.assertEqual(deal_comments.items[0].author_full_name, "Sales Manager")

    def test_comment_on_missing_entity_returns_404(self) -> None:
        with self.assertRaises(HTTPException) as cm:
            create_comment(
                self.db,
                "task",
                "task_does_not_exist",
                CrmCommentCreate(content="Hello"),
                author_user_id="user_030",
            )
        self.assertEqual(cm.exception.status_code, 404)

    def test_deal_already_closed_cannot_transition(self) -> None:
        deal = create_deal(
            self.db,
            CrmDealCreate(
                lead_id="lead_xyz",
                owner_user_id="user_030",
                title="Already Lost",
                stage="lost",
            ),
        )
        with self.assertRaises(HTTPException) as cm:
            transition_deal_stage(
                self.db,
                deal.id,
                CrmDealStageTransitionRequest(new_stage="discovery", trigger_workflow=False),
                requested_by="user_030",
            )
        self.assertEqual(cm.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
