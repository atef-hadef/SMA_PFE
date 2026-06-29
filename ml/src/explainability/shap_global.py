"""
shap_global.py
==============
Feature importance GLOBALE via SHAP : quels facteurs pèsent le plus sur la
conversion à l'échelle de tout le portefeuille de leads.

Génère aussi un beeswarm plot (ml/artifacts/shap_global.png).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import shap

try:
    from .shap_local import _detect_model_type, resolve_label
except ImportError:  # exécution directe du script
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.explainability.shap_local import _detect_model_type, resolve_label  # type: ignore

_ARTIFACTS = Path(__file__).resolve().parents[2] / "artifacts"


def _shap_matrix(model, X, background, model_type):
    """Retourne la matrice SHAP (n_samples, n_features) pour la classe positive."""
    X_arr = np.asarray(X, dtype=float)
    if model_type == "tree":
        explainer = shap.TreeExplainer(model)
        raw = explainer.shap_values(X_arr)
    else:
        bg = np.asarray(background, dtype=float) if background is not None else X_arr
        explainer = shap.LinearExplainer(model, bg)
        raw = explainer.shap_values(X_arr)

    arr = np.asarray(raw)
    if arr.ndim == 3:
        if arr.shape[-1] == 2:
            arr = arr[:, :, 1]
        elif arr.shape[0] == 2:
            arr = arr[1]
    return arr


def compute_global_importance(
    model,
    X_test,
    feature_names: list,
    background=None,
    model_type: str | None = None,
    save_plot: bool = True,
    output_path: str | None = None,
) -> list[dict]:
    """
    Importance globale SHAP (moyenne des |valeurs SHAP|), triée décroissante.
    Retourne une liste de dicts {feature, label, importance, rank}.
    """
    model_type = model_type or _detect_model_type(model)
    shap_matrix = _shap_matrix(model, X_test, background, model_type)

    mean_abs = np.abs(shap_matrix).mean(axis=0)
    total = float(mean_abs.sum()) or 1.0
    norm = mean_abs / total  # importance normalisée (somme = 1)

    order = np.argsort(mean_abs)[::-1]
    result = []
    for rank, idx in enumerate(order, start=1):
        result.append({
            "feature": feature_names[idx],
            "label": resolve_label(feature_names[idx]),
            "importance": round(float(norm[idx]), 4),
            "rank": rank,
        })

    if save_plot:
        _save_beeswarm(shap_matrix, X_test, feature_names, output_path)

    return result


def _save_beeswarm(shap_matrix, X_test, feature_names, output_path=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out = Path(output_path) if output_path else _ARTIFACTS / "shap_global.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        shap.summary_plot(
            shap_matrix, np.asarray(X_test, dtype=float),
            feature_names=feature_names, show=False, max_display=15,
        )
        plt.title("SHAP — Importance globale des features (Lead Scoring)")
        plt.tight_layout()
        plt.savefig(out, dpi=120, bbox_inches="tight")
    finally:
        plt.close("all")


if __name__ == "__main__":
    import joblib

    bundle = joblib.load(_ARTIFACTS / "best_model.joblib")
    # Reconstruit un petit X de test scalé depuis le dataset
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.features.pipeline import build_feature_matrix, load_dataset  # type: ignore

    df = load_dataset().sample(300, random_state=42)
    X, _ = build_feature_matrix(df, fit_encoders=False, encoders=joblib.load(
        _ARTIFACTS / "encoders.joblib"))
    X = X[bundle["feature_names"]]
    X[bundle["numeric_cols"]] = bundle["scaler"].transform(X[bundle["numeric_cols"]])

    importance = compute_global_importance(
        bundle["raw_model"], X.to_numpy(), bundle["feature_names"],
        background=bundle.get("background"), model_type=bundle["model_type"],
    )
    print("Top 10 features (importance globale SHAP) :")
    for item in importance[:10]:
        print(f"  {item['rank']:2}. {item['label']:32} {item['importance']:.4f}")
    print(f"\nBeeswarm -> {_ARTIFACTS / 'shap_global.png'}")
