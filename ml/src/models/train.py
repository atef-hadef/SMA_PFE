"""
train.py
========
Entraîne 4 modèles ML, les compare au LLM baseline, et tracke tout avec MLflow.

Pipeline par modèle (défendable en soutenance) :
  1. Split stratifié 80/20 (random_state=42) sur la cible `converted`
  2. StandardScaler sur les features numériques CONTINUES uniquement
     (pas sur les binaires 0/1 ni les colonnes OneHot) — ordre des colonnes
     préservé pour garder les noms de features alignés avec SHAP
  3. Calibration des probabilités via CalibratedClassifierCV(cv=5)
  4. Tracking MLflow : params + metrics + modèle + artefacts

Baseline LLM : on évalue la colonne `lead_score` (score LLM legacy / 100) comme
probabilité, sur le MÊME jeu de test, et on la logge dans un run "LLM_Baseline".

Sorties :
  - ml/artifacts/best_model.joblib  (bundle : modèle calibré + modèle brut SHAP + scaler)
  - ml/artifacts/metrics.json       (toutes les métriques)
  - ml/artifacts/roc_curves.png     (courbes ROC)
  - ml/mlruns/                      (runs MLflow)
  - MLflow Model Registry           "TacTic_LeadScoring" alias @production
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

# Imports robustes : marche en `python src/models/train.py` ET en module
try:
    from ..features.pipeline import (
        ARTIFACTS_DIR,
        build_feature_matrix,
        get_numeric_feature_names,
        get_target,
        load_dataset,
    )
    from ..mlops.mlflow_tracker import MLflowTracker
    from ..mlops.registry import update_registry
    from .evaluate import (
        compute_all_metrics,
        generate_comparison_table,
        save_roc_curves,
    )
except ImportError:  # exécution directe
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.features.pipeline import (  # type: ignore
        ARTIFACTS_DIR,
        build_feature_matrix,
        get_numeric_feature_names,
        get_target,
        load_dataset,
    )
    from src.mlops.mlflow_tracker import MLflowTracker  # type: ignore
    from src.mlops.registry import update_registry  # type: ignore
    from src.models.evaluate import (  # type: ignore
        compute_all_metrics,
        generate_comparison_table,
        save_roc_curves,
    )

from xgboost import XGBClassifier
from lightgbm import LGBMClassifier

RANDOM_STATE = 42
MODEL_VERSION = "v1.0"
BEST_MODEL_PATH = ARTIFACTS_DIR / "best_model.joblib"
METRICS_PATH = ARTIFACTS_DIR / "metrics.json"
ROC_PATH = ARTIFACTS_DIR / "roc_curves.png"


def _build_models(scale_pos_weight: float) -> dict:
    """Instancie les 4 modèles avec les hyperparamètres demandés."""
    return {
        "LogisticRegression": LogisticRegression(
            max_iter=1000, class_weight="balanced",
        ),
        "RandomForest": RandomForestClassifier(
            n_estimators=200, class_weight="balanced", random_state=RANDOM_STATE,
        ),
        "XGBoost": XGBClassifier(
            n_estimators=200, learning_rate=0.1, max_depth=6,
            scale_pos_weight=scale_pos_weight, random_state=RANDOM_STATE,
            eval_metric="auc",
        ),
        "LightGBM": LGBMClassifier(
            n_estimators=200, learning_rate=0.1, class_weight="balanced",
            random_state=RANDOM_STATE, verbose=-1,
        ),
    }


def _model_type(name: str) -> str:
    return "linear" if name == "LogisticRegression" else "tree"


def _scale_df(df, scaler, numeric_cols):
    """Standardise les colonnes numériques en préservant l'ordre des colonnes."""
    out = df.copy()
    out[numeric_cols] = scaler.transform(df[numeric_cols])
    return out


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # emojis du tableau sur Windows
    except Exception:
        pass
    print("=" * 70)
    print("  ENTRAÎNEMENT — TAC-TIC Lead Scoring")
    print("=" * 70)

    # --- 1. Données + features ---
    df = load_dataset()
    X, _enc = build_feature_matrix(df, fit_encoders=True)
    y = get_target(df)
    feature_names = list(X.columns)
    print(f"\nDataset : {len(df)} leads | {X.shape[1]} features | "
          f"taux conversion = {y.mean():.1%}")

    # --- 2. Split stratifié 80/20 ---
    idx = np.arange(len(df))
    idx_train, idx_test = train_test_split(
        idx, test_size=0.20, stratify=y, random_state=RANDOM_STATE,
    )
    X_train, X_test = X.iloc[idx_train], X.iloc[idx_test]
    y_train, y_test = y[idx_train], y[idx_test]
    print(f"Train : {len(idx_train)} | Test : {len(idx_test)} | "
          f"conversion train={y_train.mean():.1%} test={y_test.mean():.1%}")

    # --- 3. Scaler sur numériques continues uniquement ---
    numeric_cols = get_numeric_feature_names(X)
    scaler = StandardScaler().fit(X_train[numeric_cols])
    X_train_s = _scale_df(X_train, scaler, numeric_cols)
    X_test_s = _scale_df(X_test, scaler, numeric_cols)

    n_pos = int(y_train.sum())
    n_neg = int(len(y_train) - n_pos)
    scale_pos_weight = round(n_neg / max(n_pos, 1), 4)

    # --- 4. Entraînement + MLflow ---
    tracker = MLflowTracker()
    models = _build_models(scale_pos_weight)
    all_metrics: list[dict] = []
    roc_inputs: dict = {}
    run_ids: dict = {}
    raw_models: dict = {}

    for name, estimator in models.items():
        print(f"\n--- {name} ---")
        # Modèle brut (pour SHAP) entraîné sur features scalées
        raw = clone(estimator).fit(X_train_s, y_train)
        raw_models[name] = raw

        # Modèle calibré (probabilités fiables) pour le scoring
        calibrated = CalibratedClassifierCV(
            clone(estimator), cv=5, method="sigmoid",
        ).fit(X_train_s, y_train)

        y_proba = calibrated.predict_proba(X_test_s)[:, 1]
        y_pred = (y_proba >= 0.5).astype(int)

        metrics = compute_all_metrics(y_test, y_proba, y_pred, name)
        all_metrics.append(metrics)
        roc_inputs[name] = {"y_true": y_test, "y_proba": y_proba, "auc": metrics["auc_roc"]}
        print(f"    AUC={metrics['auc_roc']:.4f}  F1={metrics['f1_score']:.4f}  "
              f"P@20={metrics['precision_at_20']:.4f}  Lift={metrics['lift_at_20']:.2f}")

        params = estimator.get_params()
        params = {k: v for k, v in params.items() if isinstance(v, (int, float, str, bool))}
        run_ids[name] = tracker.log_training_run(
            model_name=name, model=calibrated, params=params,
            metrics=metrics, feature_names=feature_names,
        )

    # --- 5. Baseline LLM (lead_score / 100) ---
    print("\n--- LLM_Baseline ---")
    llm_proba = (df["lead_score"].to_numpy()[idx_test] / 100.0).clip(0, 1)
    llm_pred = (llm_proba >= 0.5).astype(int)
    llm_metrics = compute_all_metrics(y_test, llm_proba, llm_pred, "LLM Baseline")
    all_metrics.append(llm_metrics)
    roc_inputs["LLM Baseline"] = {
        "y_true": y_test, "y_proba": llm_proba, "auc": llm_metrics["auc_roc"],
    }
    print(f"    AUC={llm_metrics['auc_roc']:.4f}  F1={llm_metrics['f1_score']:.4f}  "
          f"P@20={llm_metrics['precision_at_20']:.4f}")
    tracker.log_training_run(
        model_name="LLM_Baseline", model=models["LogisticRegression"],
        params={"type": "llm_legacy_score"}, metrics=llm_metrics,
        feature_names=["lead_score"],
    )

    # --- 6. Tableau comparatif ---
    table = generate_comparison_table(all_metrics)
    print("\n" + "=" * 70)
    print("  TABLEAU COMPARATIF")
    print("=" * 70)
    print(table.to_string(index=False))

    # --- 7. Meilleur modèle ML ---
    ml_only = [m for m in all_metrics if "LLM" not in m["model_name"]]
    best = max(ml_only, key=lambda m: m["auc_roc"])
    best_name = best["model_name"]
    best_auc = best["auc_roc"]
    llm_auc = llm_metrics["auc_roc"]
    improvement = ((best_auc - llm_auc) / llm_auc * 100) if llm_auc else 0.0
    improvement_str = f"{improvement:+.1f}%"
    print(f"\n⭐ Meilleur modèle : {best_name} (AUC={best_auc:.4f}) | "
          f"LLM={llm_auc:.4f} | amélioration {improvement_str}")

    # --- 8. Courbes ROC + importance globale SHAP ---
    save_roc_curves(roc_inputs, str(ROC_PATH))
    print(f"Courbes ROC -> {ROC_PATH}")

    try:
        from src.explainability.shap_global import compute_global_importance
        importance = compute_global_importance(
            raw_models[best_name], X_test_s.to_numpy(), feature_names,
            background=X_train_s.sample(
                n=min(200, len(X_train_s)), random_state=RANDOM_STATE).to_numpy(),
            model_type=_model_type(best_name), save_plot=True,
        )
        with open(ARTIFACTS_DIR / "feature_importance.json", "w", encoding="utf-8") as f:
            json.dump(importance, f, indent=2, ensure_ascii=False)
        print(f"feature_importance.json -> {ARTIFACTS_DIR / 'feature_importance.json'}")
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] importance globale : {exc}")

    # --- 9. Sauvegarde du bundle best_model.joblib ---
    bundle = {
        "calibrated": CalibratedClassifierCV(
            clone(models[best_name]), cv=5, method="sigmoid",
        ).fit(X_train_s, y_train),
        "raw_model": raw_models[best_name],
        "scaler": scaler,
        "numeric_cols": numeric_cols,
        "feature_names": feature_names,
        "model_name": best_name,
        "model_type": _model_type(best_name),
        "version": MODEL_VERSION,
        # Échantillon de fond pour SHAP (LinearExplainer / interventional)
        "background": X_train_s.sample(
            n=min(200, len(X_train_s)), random_state=RANDOM_STATE,
        ).to_numpy(),
        # Mode d'entraînement par catégorie -> défauts de serving pour les champs
        # non inférables (language/product/city), évite le biais train/serve.
        "serving_defaults": {
            prefix: (str(df[col].mode().iloc[0]) if col in df.columns and len(df[col].mode()) else "")
            for col, prefix in __import__(
                "src.features.pipeline", fromlist=["CATEGORICAL_SOURCE"]
            ).CATEGORICAL_SOURCE.items()
        },
    }
    joblib.dump(bundle, BEST_MODEL_PATH)
    print(f"best_model.joblib -> {BEST_MODEL_PATH}")

    # --- 10. metrics.json ---
    metrics_payload = {
        "trained_at": __import__("datetime").date.today().isoformat(),
        "n_training_samples": len(idx_train),
        "n_features": X.shape[1],
        "models": all_metrics,
        "llm_baseline": llm_metrics,
        "best_model": {
            "name": best_name, "version": MODEL_VERSION,
            "auc_roc": best_auc, "improvement_vs_llm": improvement_str,
        },
    }
    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics_payload, f, indent=2, ensure_ascii=False)
    print(f"metrics.json -> {METRICS_PATH}")

    # --- 11. Registre local + MLflow Model Registry (alias @production) ---
    update_registry(
        version=MODEL_VERSION, algorithm=best_name, metrics=best,
        model_file="best_model.joblib", status="production",
        n_features=X.shape[1], n_training_samples=len(idx_train),
        improvement_vs_llm=improvement_str, mlflow_run_id=run_ids.get(best_name),
    )
    print("Registre local mis a jour (model_registry.json)")

    try:
        import mlflow
        run_id = run_ids[best_name]
        mv = mlflow.register_model(f"runs:/{run_id}/model", "TacTic_LeadScoring")
        tracker.promote_to_production("TacTic_LeadScoring", version=int(mv.version))
        print(f"MLflow Registry : TacTic_LeadScoring v{mv.version} @production")
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] MLflow Registry : {exc}")

    print("\n✅ Entraînement terminé.")


if __name__ == "__main__":
    main()
