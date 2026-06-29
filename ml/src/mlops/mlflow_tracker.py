"""
mlflow_tracker.py
=================
Wrapper MLflow pour le projet TAC-TIC. Encapsule tout le tracking : experiment,
runs, log de modèles, Model Registry.

MLflow 3.x : on utilise les ALIASES (`@production`) plutôt que les stages
(`stage="Production"`) qui sont dépréciés (choix validé). Un fallback vers
l'ancienne API est conservé pour robustesse.

Tracking URI : chemin ABSOLU calculé dynamiquement depuis la racine du projet
(choix validé #2 — pas de chemin hardcodé "file:///ml/mlruns").
"""

from __future__ import annotations

from pathlib import Path

import mlflow
import mlflow.sklearn
import pandas as pd

# --------------------------------------------------------------------------- #
# Configuration — URI absolu basé sur la racine du projet (choix validé #2)
#
# MLflow 3.x : le file store est en "maintenance mode" et ne supporte pas
# pleinement le Model Registry + aliases. On utilise donc le backend SQLite
# recommandé (sqlite:///ml/mlflow.db) avec les ARTEFACTS stockés dans ml/mlruns.
# UI soutenance :  mlflow ui --backend-store-uri sqlite:///<...>/ml/mlflow.db
# --------------------------------------------------------------------------- #
_ML_ROOT = Path(__file__).resolve().parents[2]          # .../ml
MLRUNS_DIR = _ML_ROOT / "mlruns"
_DB_PATH = _ML_ROOT / "mlflow.db"
MLFLOW_TRACKING_URI = f"sqlite:///{_DB_PATH.as_posix()}"
ARTIFACT_LOCATION = f"file:///{MLRUNS_DIR.as_posix()}"
EXPERIMENT_NAME = "TAC-TIC Lead Scoring"
PRODUCTION_ALIAS = "production"


def _numeric_metrics(metrics: dict) -> dict:
    """Ne garde que les valeurs numériques (MLflow log_metrics refuse le reste)."""
    out = {}
    for k, v in metrics.items():
        if isinstance(v, bool):
            out[k] = int(v)
        elif isinstance(v, (int, float)):
            out[k] = float(v)
    return out


class MLflowTracker:
    """Encapsule toute la logique MLflow du projet."""

    def __init__(self) -> None:
        MLRUNS_DIR.mkdir(parents=True, exist_ok=True)
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        # Crée l'experiment avec un artifact_location explicite si absent
        client = mlflow.MlflowClient()
        exp = client.get_experiment_by_name(EXPERIMENT_NAME)
        if exp is None:
            client.create_experiment(EXPERIMENT_NAME, artifact_location=ARTIFACT_LOCATION)
        mlflow.set_experiment(EXPERIMENT_NAME)

    def log_training_run(
        self,
        model_name: str,
        model,
        params: dict,
        metrics: dict,
        feature_names: list,
        artifacts_paths: list | None = None,
    ) -> str:
        """Logge un run d'entraînement complet. Retourne le run_id."""
        artifacts_paths = artifacts_paths or []
        registered_name = f"TacTic_{model_name.replace(' ', '_')}"

        with mlflow.start_run(run_name=model_name) as run:
            mlflow.log_params(params)
            mlflow.log_metrics(_numeric_metrics(metrics))
            mlflow.log_param("n_features", len(feature_names))
            mlflow.log_param("feature_names", str(feature_names[:10]))

            # log_model : MLflow 3 préfère name=, fallback artifact_path=.
            # serialization_format="cloudpickle" : évite l'audit skops qui rejette
            # les types internes de CalibratedClassifierCV.
            try:
                mlflow.sklearn.log_model(
                    sk_model=model,
                    name="model",
                    registered_model_name=registered_name,
                    serialization_format="cloudpickle",
                )
            except TypeError:
                mlflow.sklearn.log_model(
                    sk_model=model,
                    artifact_path="model",
                    registered_model_name=registered_name,
                    serialization_format="cloudpickle",
                )

            for path in artifacts_paths:
                if Path(path).exists():
                    mlflow.log_artifact(str(path))

            return run.info.run_id

    def promote_to_production(self, model_name: str, version: int = 1) -> None:
        """
        Promeut un modèle en production via ALIAS (MLflow 3.x).
        Fallback sur l'ancienne API stage si l'alias n'est pas supporté.
        """
        client = mlflow.MlflowClient()
        try:
            client.set_registered_model_alias(
                name=model_name,
                alias=PRODUCTION_ALIAS,
                version=str(version),
            )
        except Exception:
            # Fallback API dépréciée (MLflow < 3)
            client.transition_model_version_stage(
                name=model_name,
                version=version,
                stage="Production",
            )

    def get_production_model(self, model_name: str):
        """Charge le modèle en production (alias @production, fallback /Production)."""
        try:
            return mlflow.sklearn.load_model(f"models:/{model_name}@{PRODUCTION_ALIAS}")
        except Exception:
            return mlflow.sklearn.load_model(f"models:/{model_name}/Production")

    def get_latest_version(self, model_name: str) -> int:
        """Retourne le numéro de la dernière version enregistrée d'un modèle."""
        client = mlflow.MlflowClient()
        versions = client.search_model_versions(f"name='{model_name}'")
        if not versions:
            return 1
        return max(int(v.version) for v in versions)

    def get_all_runs(self) -> pd.DataFrame:
        """Retourne tous les runs de l'experiment sous forme de DataFrame."""
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        try:
            df = mlflow.search_runs(experiment_names=[EXPERIMENT_NAME])
        except Exception:
            return pd.DataFrame()
        return df if df is not None else pd.DataFrame()
