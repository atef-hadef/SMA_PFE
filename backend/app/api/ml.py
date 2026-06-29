"""Endpoints FastAPI du module Data Science (scoring ML + SHAP + analytics)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import require_permission
from app.core.database import get_db
from app.schemas.auth import AuthUser
from app.schemas.common import ApiResponse
from app.schemas.ml import (
    AnalyticsResponse,
    LeadScoreRequest,
    LeadScoreResponse,
    MLflowRun,
    ModelInfoResponse,
)
from app.services.ml_scoring_service import MLScoringService

router = APIRouter(prefix="/ml", tags=["ml"])


@router.post("/score-lead", response_model=ApiResponse[LeadScoreResponse])
def score_lead(
    request: LeadScoreRequest,
    _user: AuthUser = Depends(require_permission("crm.leads.view")),
) -> ApiResponse[LeadScoreResponse]:
    """Score un lead avec le modèle ML + explication SHAP."""
    service = MLScoringService.get_instance()
    result = service.score_lead(
        lead_id=request.lead_id,
        message=request.message,
        phone=request.phone,
        company=request.company,
        email=request.email,
        source=request.source,
        created_at=request.created_at,
        llm_score=request.llm_score,
    )
    return ApiResponse(success=True, data=LeadScoreResponse(**result))


@router.get("/model-info", response_model=ApiResponse[ModelInfoResponse])
def get_model_info(
    _user: AuthUser = Depends(require_permission("crm.leads.view")),
) -> ApiResponse[ModelInfoResponse]:
    """Métadonnées du modèle en production (version, AUC, date, features)."""
    service = MLScoringService.get_instance()
    return ApiResponse(success=True, data=ModelInfoResponse(**service.get_model_info()))


@router.get("/analytics", response_model=ApiResponse[AnalyticsResponse])
def get_analytics(
    db: Session = Depends(get_db),
    _user: AuthUser = Depends(require_permission("crm.leads.view")),
) -> ApiResponse[AnalyticsResponse]:
    """Données du dashboard Data Science (distribution, comparaison, importance...)."""
    service = MLScoringService.get_instance()
    return ApiResponse(success=True, data=AnalyticsResponse(**service.get_analytics(db)))


@router.get("/mlflow-runs", response_model=ApiResponse[list[MLflowRun]])
def get_mlflow_runs(
    _user: AuthUser = Depends(require_permission("crm.leads.view")),
) -> ApiResponse[list[MLflowRun]]:
    """Tous les runs MLflow de l'expériment (pour le dashboard)."""
    service = MLScoringService.get_instance()
    runs = [MLflowRun(**r) for r in service.get_mlflow_runs()]
    return ApiResponse(success=True, data=runs)
