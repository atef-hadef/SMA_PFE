"""REST endpoints for CRM Tasks (WF 06)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import (
    require_any_permission,
    require_internal_secret,
    require_permission,
)
from app.core.permissions import crm_scoped_owner_id
from app.core.database import get_db
from app.schemas.auth import AuthUser
from app.schemas.common import ApiResponse
from app.schemas.crm_tasks_deals import (
    CrmCommentCreate,
    CrmCommentItem,
    CrmCommentListResponse,
    CrmPendingFollowupResponse,
    CrmTaskCreate,
    CrmTaskItem,
    CrmTaskListResponse,
    CrmTaskReminderAck,
    CrmTaskUpdate,
    CrmTeamMemberListResponse,
)
from app.services.crm_comments_service import (
    create_comment,
    delete_comment,
    list_comments,
)
from app.services.crm_tasks_service import (
    create_task,
    delete_task,
    get_task,
    list_pending_followup_tasks,
    list_tasks,
    list_team_members,
    mark_tasks_reminded,
    update_task,
)

router = APIRouter()


@router.get(
    "/crm/team-members",
    response_model=ApiResponse[CrmTeamMemberListResponse],
)
def read_crm_team_members(
    db: Session = Depends(get_db),
    _user=Depends(
        require_any_permission(
            [
                "crm.tasks.view",
                "crm.tasks.manage",
                "crm.deals.view",
                "crm.deals.manage",
                "crm.leads.view",
            ]
        )
    ),
) -> ApiResponse[CrmTeamMemberListResponse]:
    """Lightweight roster used by tasks/deals owner pickers."""
    return ApiResponse(success=True, data=list_team_members(db))


@router.get("/crm/tasks", response_model=ApiResponse[CrmTaskListResponse])
def read_crm_tasks(
    status: str | None = None,
    owner_user_id: str | None = None,
    lead_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_permission("crm.tasks.view")),
) -> ApiResponse[CrmTaskListResponse]:
    # role_sales : forcé sur ses propres tâches ; admin/manager : filtre libre.
    scoped = crm_scoped_owner_id(current_user)
    effective_owner = scoped if scoped is not None else owner_user_id
    return ApiResponse(
        success=True,
        data=list_tasks(db, status=status, owner_user_id=effective_owner, lead_id=lead_id),
    )


@router.get("/crm/tasks/pending-followup", response_model=ApiResponse[CrmPendingFollowupResponse])
def read_crm_pending_followup_tasks(
    threshold_hours: int = 48,
    db: Session = Depends(get_db),
    _internal=Depends(require_internal_secret),
) -> ApiResponse[CrmPendingFollowupResponse]:
    """Internal endpoint consumed by n8n WF 06 each morning."""
    return ApiResponse(
        success=True,
        data=list_pending_followup_tasks(db, threshold_hours=threshold_hours),
    )


@router.post(
    "/crm/tasks/reminder-sent",
    response_model=ApiResponse[CrmTaskReminderAck],
)
def acknowledge_task_reminders(
    payload: dict,
    db: Session = Depends(get_db),
    _internal=Depends(require_internal_secret),
) -> ApiResponse[CrmTaskReminderAck]:
    """Called by WF 06 after the digest email was sent (per owner)."""
    task_ids = payload.get("task_ids") or []
    if not isinstance(task_ids, list):
        task_ids = []
    return ApiResponse(
        success=True,
        data=mark_tasks_reminded(db, [str(t) for t in task_ids if t]),
    )


@router.get("/crm/tasks/{task_id}", response_model=ApiResponse[CrmTaskItem])
def read_crm_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_permission("crm.tasks.view")),
) -> ApiResponse[CrmTaskItem]:
    item = get_task(db, task_id)
    scoped = crm_scoped_owner_id(current_user)
    if scoped is not None and item.owner_user_id != scoped:
        raise HTTPException(status_code=403, detail="Accès refusé : cette tâche ne vous appartient pas.")
    return ApiResponse(success=True, data=item)


@router.post("/crm/tasks", response_model=ApiResponse[CrmTaskItem])
def create_crm_task(
    payload: CrmTaskCreate,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_permission("crm.tasks.manage")),
) -> ApiResponse[CrmTaskItem]:
    return ApiResponse(
        success=True,
        message="CRM task created.",
        data=create_task(db, payload, created_by=current_user.id),
    )


@router.patch("/crm/tasks/{task_id}", response_model=ApiResponse[CrmTaskItem])
def update_crm_task(
    task_id: str,
    payload: CrmTaskUpdate,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("crm.tasks.manage")),
) -> ApiResponse[CrmTaskItem]:
    return ApiResponse(
        success=True,
        message="CRM task updated.",
        data=update_task(db, task_id, payload),
    )


@router.delete("/crm/tasks/{task_id}", response_model=ApiResponse[None])
def delete_crm_task(
    task_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("crm.tasks.manage")),
) -> ApiResponse[None]:
    delete_task(db, task_id)
    return ApiResponse(success=True, message="CRM task removed.", data=None)


@router.get(
    "/crm/tasks/{task_id}/comments",
    response_model=ApiResponse[CrmCommentListResponse],
)
def read_crm_task_comments(
    task_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("crm.tasks.view")),
) -> ApiResponse[CrmCommentListResponse]:
    return ApiResponse(success=True, data=list_comments(db, "task", task_id))


@router.post(
    "/crm/tasks/{task_id}/comments",
    response_model=ApiResponse[CrmCommentItem],
)
def create_crm_task_comment(
    task_id: str,
    payload: CrmCommentCreate,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_permission("crm.tasks.manage")),
) -> ApiResponse[CrmCommentItem]:
    return ApiResponse(
        success=True,
        message="Comment added.",
        data=create_comment(
            db, "task", task_id, payload, author_user_id=current_user.id
        ),
    )


@router.delete(
    "/crm/tasks/{task_id}/comments/{comment_id}",
    response_model=ApiResponse[None],
)
def delete_crm_task_comment(
    task_id: str,
    comment_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("crm.tasks.manage")),
) -> ApiResponse[None]:
    delete_comment(db, "task", task_id, comment_id)
    return ApiResponse(success=True, message="Comment removed.", data=None)
