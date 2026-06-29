"""
evaluate.py
===========
Métriques d'évaluation pour le lead scoring.

Au-delà de l'AUC, on calcule des métriques *métier* défendables en soutenance :
  - precision@k : sur les k% leads les mieux scorés, quelle proportion convertit ?
    -> répond à "si un commercial ne rappelle que le top 20%, combien sont bons ?"
  - lift@k      : combien de fois mieux que le hasard sur ce top k% ?
  - brier_score : qualité de calibration des probabilités (plus bas = mieux).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)


def precision_at_k(y_true: np.ndarray, y_proba: np.ndarray, k: float = 0.20) -> float:
    """
    Parmi les k% leads avec le score le plus haut, proportion réellement convertie.
    """
    y_true = np.asarray(y_true)
    y_proba = np.asarray(y_proba)
    n = len(y_true)
    if n == 0:
        return 0.0
    n_top = max(1, int(round(n * k)))
    top_idx = np.argsort(y_proba)[::-1][:n_top]
    return float(np.mean(y_true[top_idx]))


def compute_lift(y_true: np.ndarray, y_proba: np.ndarray, k: float = 0.20) -> float:
    """Combien de fois mieux que le hasard sur le top k% des leads."""
    y_true = np.asarray(y_true)
    base_rate = float(np.mean(y_true)) if len(y_true) else 0.0
    if base_rate == 0.0:
        return 0.0
    return round(precision_at_k(y_true, y_proba, k) / base_rate, 4)


def compute_all_metrics(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    y_pred: np.ndarray,
    model_name: str,
) -> dict:
    """Calcule toutes les métriques pour un modèle."""
    y_true = np.asarray(y_true)
    y_proba = np.asarray(y_proba)
    y_pred = np.asarray(y_pred)

    # confusion_matrix sklearn -> [[TN, FP], [FN, TP]]
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()

    return {
        "model_name": model_name,
        "auc_roc": round(float(roc_auc_score(y_true, y_proba)), 4),
        "auc_pr": round(float(average_precision_score(y_true, y_proba)), 4),
        "f1_score": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "brier_score": round(float(brier_score_loss(y_true, y_proba)), 4),
        "precision_at_20": round(precision_at_k(y_true, y_proba, 0.20), 4),
        "lift_at_20": compute_lift(y_true, y_proba, 0.20),
        # format demandé : [[TP, FP], [FN, TN]]
        "confusion_matrix": [[int(tp), int(fp)], [int(fn), int(tn)]],
    }


def generate_comparison_table(all_metrics: list[dict]) -> pd.DataFrame:
    """
    Tableau comparatif trié par AUC décroissant.
    Le meilleur modèle ML reçoit le statut ⭐ Best, le LLM le statut 📊 Baseline.
    """
    rows = []
    for m in all_metrics:
        rows.append({
            "Modèle": m["model_name"],
            "AUC": m["auc_roc"],
            "F1": m["f1_score"],
            "P@k": m["precision_at_20"],
            "Lift": m["lift_at_20"],
            "Brier": m["brier_score"],
        })
    df = pd.DataFrame(rows).sort_values("AUC", ascending=False).reset_index(drop=True)

    # Statut : LLM = baseline ; meilleur ML = Best ; autres ML = OK
    is_llm = df["Modèle"].str.contains("LLM", case=False)
    best_ml_idx = df[~is_llm]["AUC"].idxmax() if (~is_llm).any() else None

    statuts = []
    for idx, row in df.iterrows():
        if "LLM" in row["Modèle"].upper():
            statuts.append("📊 Baseline")
        elif idx == best_ml_idx:
            statuts.append("⭐ Best")
        else:
            statuts.append("✅")
    df["Statut"] = statuts
    return df


def save_roc_curves(
    models_results: dict,
    output_path: str = "ml/artifacts/roc_curves.png",
) -> None:
    """
    Trace la courbe ROC de tous les modèles sur un même graphique.
    `models_results` : {model_name: {"y_true": ..., "y_proba": ..., "auc": float}}
    Le LLM baseline est tracé en pointillé.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.figure(figsize=(8, 6))
    for name, res in models_results.items():
        fpr, tpr, _ = roc_curve(res["y_true"], res["y_proba"])
        is_llm = "LLM" in name.upper()
        plt.plot(
            fpr, tpr,
            linestyle="--" if is_llm else "-",
            linewidth=2.2 if not is_llm else 1.8,
            label=f"{name} (AUC={res['auc']:.3f})",
        )
    plt.plot([0, 1], [0, 1], color="gray", linestyle=":", label="Hasard (AUC=0.500)")
    plt.xlabel("Taux de faux positifs")
    plt.ylabel("Taux de vrais positifs")
    plt.title("Courbes ROC — Lead Scoring TAC-TIC")
    plt.legend(loc="lower right", fontsize=9)
    plt.grid(alpha=0.3)
    plt.tight_layout()

    from pathlib import Path
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=120)
    plt.close()
