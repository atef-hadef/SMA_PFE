from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import require_permission
from app.core.database import get_db
from app.schemas.auth import AuthUser
from app.schemas.agents import (
    AgentDetail,
    AgentListItem,
    AgentRunRequest,
    AgentRunResponse,
)
from app.schemas.common import ApiResponse, PaginatedResponse
from app.services.agent_service import get_agent_by_id, get_agents, run_agent

router = APIRouter()


@router.get("/agents", response_model=ApiResponse[PaginatedResponse[AgentListItem]])
def read_agents(
    db: Session = Depends(get_db),
    _user=Depends(require_permission("agents.view")),
) -> ApiResponse[PaginatedResponse[AgentListItem]]:
    return ApiResponse(success=True, data=get_agents(db))


@router.get("/agents/{agent_id}", response_model=ApiResponse[AgentDetail])
def read_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("agents.view")),
) -> ApiResponse[AgentDetail]:
    agent = get_agent_by_id(agent_id, db)

    if agent is None:
        raise HTTPException(status_code=404, detail="AI agent not found.")

    return ApiResponse(success=True, data=agent)


@router.post("/agents/{agent_id}/run", response_model=ApiResponse[AgentRunResponse])
def run_ai_agent(
    agent_id: str,
    payload: AgentRunRequest,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_permission("agents.run")),
) -> ApiResponse[AgentRunResponse]:
    run_result = run_agent(
        agent_id=agent_id,
        payload=payload.payload,
        db=db,
        requested_by=current_user.id,
    )

    if run_result is None:
        raise HTTPException(status_code=404, detail="AI agent not found.")

    return ApiResponse(success=True, data=run_result)
