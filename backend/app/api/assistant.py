from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_permission
from app.core.database import get_db
from app.schemas.auth import AuthUser
from app.schemas.assistant import (
    AssistantActionRequest,
    AssistantActionResponse,
    AssistantChatRequest,
    AssistantChatResponse,
)
from app.schemas.common import ApiResponse
from app.services.assistant_service import process_chat

router = APIRouter()


@router.post(
    "/assistant/chat",
    response_model=ApiResponse[AssistantChatResponse],
    status_code=status.HTTP_200_OK,
    summary="AI Business Assistant — chat endpoint",
    description=(
        "Envoie un message en langage naturel à l'assistant FlowPilot AI. "
        "Retourne une réponse structurée avec une analyse live depuis PostgreSQL : "
        "réponse, intention détectée, mode d'affichage, sources, actions suggérées "
        "et visualisations optionnelles."
    ),
)
def assistant_chat(
    payload: AssistantChatRequest,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_permission("dashboard.view")),
) -> ApiResponse[AssistantChatResponse]:
    try:
        result = process_chat(
            payload,
            db,
            permissions=current_user.permissions,
            user_full_name=current_user.full_name,
            user_role_name=current_user.role_name,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="L'assistant a rencontré une erreur inattendue. Veuillez réessayer.",
        ) from exc

    return ApiResponse(success=True, data=result)


@router.post(
    "/assistant/actions",
    response_model=ApiResponse[AssistantActionResponse],
    status_code=status.HTTP_200_OK,
    summary="Validate an assistant suggested action",
)
def assistant_action(
    payload: AssistantActionRequest,
    current_user: AuthUser = Depends(require_permission("dashboard.view")),
) -> ApiResponse[AssistantActionResponse]:
    action = payload.action
    if action.action_type in {"navigate", "query", "refresh", "filter", "open_details", "open_modal"}:
        return ApiResponse(
            success=True,
            data=AssistantActionResponse(
                status="accepted",
                message="Action non mutante acceptée.",
            ),
        )

    required_permission = _required_permission_for_action(action.action_type)
    if required_permission not in current_user.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission required: {required_permission}.",
        )

    if not payload.confirmed:
        return ApiResponse(
            success=True,
            data=AssistantActionResponse(
                status="deferred",
                message="Confirmation humaine requise avant exécution.",
            ),
        )

    return ApiResponse(
        success=True,
        data=AssistantActionResponse(
            status="deferred",
            message=(
                "Action validée mais non exécutée dans cette première intégration OpenUI. "
                "Utilisez l'écran métier sécurisé correspondant."
            ),
        ),
    )


def _required_permission_for_action(action_type: str) -> str:
    if action_type in {"prepare_followups", "generate_email_draft", "create_task"}:
        return "crm.drafts.generate"
    if action_type == "send_approved_email":
        return "crm.email.send"
    if action_type == "launch_report":
        return "workflow.executions.view"
    return "dashboard.view"
