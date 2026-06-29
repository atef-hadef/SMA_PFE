"""Schémas Pydantic du module Data Science (scoring ML + SHAP + analytics)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

# Les champs model_* (model_name, model_version...) entrent en conflit avec le
# namespace protégé "model_" de Pydantic v2 -> on le désactive.
_ALLOW_MODEL_FIELDS = ConfigDict(protected_namespaces=())


class LeadScoreRequest(BaseModel):
    lead_id: str
    message: str
    phone: str | None = None
    company: str | None = None
    email: str | None = None
    source: str = "website_form"
    created_at: datetime | None = None
    llm_score: int | None = None


class SHAPFactor(BaseModel):
    feature: str
    label: str
    shap_value: float
    direction: str
    impact_pct: float
    description: str


class LeadScoreResponse(BaseModel):
    model_config = _ALLOW_MODEL_FIELDS

    lead_id: str
    ml_score: int
    ml_probability: float
    ml_category: str
    ml_confidence: float
    llm_score: int | None = None
    delta: int | None = None
    top_factors: list[SHAPFactor]
    explanation_text: str
    model_available: bool
    model_version: str


class ModelInfoResponse(BaseModel):
    model_config = _ALLOW_MODEL_FIELDS

    model_name: str
    version: str
    trained_at: str
    algorithm: str
    auc_roc: float
    f1_score: float
    n_features: int
    n_training_samples: int
    improvement_vs_llm: str
    mlflow_run_id: str | None = None


class FeatureImportance(BaseModel):
    feature: str
    label: str
    importance: float
    rank: int


class RecentScore(BaseModel):
    lead_id: str
    lead_name: str
    ml_score: int
    ml_category: str
    llm_score: int | None = None
    delta: int | None = None
    scored_at: str


class MLflowRun(BaseModel):
    model_config = _ALLOW_MODEL_FIELDS

    run_id: str
    model_name: str
    auc_roc: float
    f1_score: float
    precision_at_k: float
    status: str
    started_at: str


class AnalyticsResponse(BaseModel):
    model_config = _ALLOW_MODEL_FIELDS

    score_distribution: dict
    model_comparison: dict
    feature_importance: list[FeatureImportance]
    recent_scores: list[RecentScore]
    mlflow_runs: list[MLflowRun]
    model_info: ModelInfoResponse
