from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import require_any_permission, require_permission
from app.core.database import get_db
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.workflow_monitoring import (
    RetryWorkflowExecutionRequest,
    RetryWorkflowExecutionResponse,
    WorkflowExecutionDetail,
    WorkflowExecutionListItem,
)
from app.services.workflow_service import (
    get_workflow_execution_by_id,
    get_workflow_executions,
    retry_workflow_execution,
)

router = APIRouter()


@router.get(
    "/workflow-executions",
    response_model=ApiResponse[PaginatedResponse[WorkflowExecutionListItem]],
)
def read_workflow_executions(
    db: Session = Depends(get_db),
    _user=Depends(
        require_any_permission(["workflow.monitor.view", "workflow.executions.view"]),
    ),
) -> ApiResponse[PaginatedResponse[WorkflowExecutionListItem]]:
    return ApiResponse(success=True, data=get_workflow_executions(db))


@router.get(
    "/workflow-executions/{execution_id}",
    response_model=ApiResponse[WorkflowExecutionDetail],
)
def read_workflow_execution(
    execution_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("workflow.executions.view")),
) -> ApiResponse[WorkflowExecutionDetail]:
    execution = get_workflow_execution_by_id(execution_id, db)

    if execution is None:
        raise HTTPException(status_code=404, detail="Workflow execution not found.")

    return ApiResponse(success=True, data=execution)


@router.post(
    "/workflow-executions/{execution_id}/retry",
    response_model=ApiResponse[RetryWorkflowExecutionResponse],
)
def retry_failed_workflow_execution(
    execution_id: str,
    payload: RetryWorkflowExecutionRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("workflow.executions.retry")),
) -> ApiResponse[RetryWorkflowExecutionResponse]:
    retry_result = retry_workflow_execution(
        execution_id=execution_id,
        reason=payload.reason,
        db=db,
    )

    if retry_result is None:
        raise HTTPException(status_code=404, detail="Workflow execution not found.")

    return ApiResponse(success=True, data=retry_result)
