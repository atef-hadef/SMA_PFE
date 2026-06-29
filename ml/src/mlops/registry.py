"""
registry.py
===========
Registre de modèles LOCAL au format JSON (ml/artifacts/model_registry.json).

Complément léger et lisible au MLflow Model Registry : permet au backend FastAPI
de lire les métadonnées du modèle de production sans dépendre du serveur MLflow.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

_ML_ROOT = Path(__file__).resolve().parents[2]          # .../ml
MODEL_REGISTRY_PATH = _ML_ROOT / "artifacts" / "model_registry.json"


def get_registry() -> dict:
    """Charge le registre JSON local (structure vide par défaut)."""
    if not MODEL_REGISTRY_PATH.exists():
        return {"current_production": None, "models": []}
    with open(MODEL_REGISTRY_PATH, encoding="utf-8") as f:
        return json.load(f)


def update_registry(
    version: str,
    algorithm: str,
    metrics: dict,
    model_file: str,
    status: str = "production",
    n_features: int | None = None,
    n_training_samples: int | None = None,
    improvement_vs_llm: str | None = None,
    mlflow_run_id: str | None = None,
) -> None:
    """Ajoute/Met à jour une entrée modèle dans le registre."""
    registry = get_registry()

    entry = {
        "version": version,
        "trained_at": date.today().isoformat(),
        "algorithm": algorithm,
        "auc_roc": metrics.get("auc_roc"),
        "f1_score": metrics.get("f1_score"),
        "n_features": n_features,
        "n_training_samples": n_training_samples,
        "improvement_vs_llm": improvement_vs_llm,
        "model_file": model_file,
        "status": status,
        "mlflow_run_id": mlflow_run_id,
    }

    # Remplace une entrée existante de même version, sinon ajoute
    models = [m for m in registry.get("models", []) if m.get("version") != version]
    models.append(entry)
    registry["models"] = models

    if status == "production":
        # tout autre modèle passe en "archived"
        for m in registry["models"]:
            if m["version"] != version and m.get("status") == "production":
                m["status"] = "archived"
        registry["current_production"] = version

    MODEL_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MODEL_REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)


def get_production_entry() -> dict | None:
    """Retourne l'entrée du modèle de production courant."""
    registry = get_registry()
    current = registry.get("current_production")
    for m in registry.get("models", []):
        if m.get("version") == current:
            return m
    return None
