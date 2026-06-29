"""
shap_local.py
=============
Explication SHAP locale d'un lead : pourquoi CE lead a obtenu CE score.

Sortie pensée pour un commercial non-technique : top 5 facteurs avec libellés
français, sens (positif/négatif), poids (%) et phrase d'explication.

TreeExplainer pour XGBoost/LightGBM/RandomForest, LinearExplainer pour
LogisticRegression (détection automatique du type de modèle).
"""

from __future__ import annotations

import numpy as np
import shap

# --------------------------------------------------------------------------- #
# Libellés français par feature (pour affichage commercial)
# --------------------------------------------------------------------------- #
FEATURE_LABELS_FR = {
    "purchase_ready_score": "Intention d'achat",
    "urgency_score": "Urgence détectée",
    "budget_score": "Budget mentionné",
    "decision_score": "Mots de décision",
    "problem_awareness_score": "Conscience du problème",
    "competitor_mentioned": "Concurrent mentionné",
    "word_count": "Longueur du message",
    "sentence_count": "Nombre de phrases",
    "question_count": "Questions posées",
    "sentiment_polarity": "Ton du message",
    "sentiment_positive": "Sentiment positif",
    "is_business_hours": "Horaires professionnels",
    "is_morning": "Soumis le matin",
    "has_company": "Entreprise fournie",
    "has_phone": "Téléphone fourni",
    "email_is_professional": "Email professionnel",
    "phone_is_tunisian": "Numéro tunisien",
    "interaction_count": "Interactions précédentes",
    "estimated_value": "Valeur estimée",
    "source": "Source du lead",
}

# Préfixes OneHot -> libellé lisible
_OHE_PREFIX_LABELS = {
    "source_": "Source",
    "language_": "Langue",
    "ai_sentiment_": "Sentiment IA",
    "ai_urgency_": "Urgence IA",
    "intention_": "Intention IA",
    "product_": "Produit",
    "city_": "Ville",
}

# Descriptions métier (texte affiché dans le détail d'un facteur)
FEATURE_DESCRIPTIONS_FR = {
    "purchase_ready_score": "Le message contient des mots indiquant une intention d'achat claire",
    "urgency_score": "Le message exprime un besoin urgent",
    "budget_score": "Le message évoque un budget ou un devis",
    "decision_score": "Le message contient des mots de prise de décision",
    "problem_awareness_score": "Le prospect est conscient d'un problème à résoudre",
    "competitor_mentioned": "Le prospect mentionne un concurrent ou une solution actuelle",
    "interaction_count": "Le nombre d'interactions précédentes avec ce prospect",
    "estimated_value": "La valeur estimée de l'opportunité",
    "sentiment_polarity": "La tonalité générale du message",
}


def resolve_label(feature: str) -> str:
    """Retourne un libellé FR lisible pour une feature (exacte ou OneHot)."""
    if feature in FEATURE_LABELS_FR:
        return FEATURE_LABELS_FR[feature]
    for prefix, label in _OHE_PREFIX_LABELS.items():
        if feature.startswith(prefix):
            value = feature[len(prefix):].replace("_", " ").strip()
            return f"{label} : {value}"
    return feature.replace("_", " ").capitalize()


def _describe(feature: str, direction: str) -> str:
    if feature in FEATURE_DESCRIPTIONS_FR:
        return FEATURE_DESCRIPTIONS_FR[feature]
    sens = "augmente" if direction == "positive" else "diminue"
    return f"Ce facteur ({resolve_label(feature)}) {sens} la probabilité de conversion"


def categorize_score(probability: float) -> str:
    """> 0.70 -> hot ; 0.40-0.70 -> warm ; < 0.40 -> cold."""
    if probability > 0.70:
        return "hot"
    if probability >= 0.40:
        return "warm"
    return "cold"


def _detect_model_type(model) -> str:
    name = type(model).__name__.lower()
    if "logistic" in name or "linear" in name:
        return "linear"
    return "tree"


def _positive_class_shap(values) -> np.ndarray:
    """Extrait le vecteur SHAP de la classe positive pour 1 échantillon."""
    arr = np.asarray(values)
    # Formes possibles : (1, n), (1, n, 2), (2, 1, n), (n,)
    if arr.ndim == 1:
        return arr
    if arr.ndim == 2:
        return arr[0]
    if arr.ndim == 3:
        # (1, n, classes) -> classe positive
        if arr.shape[-1] == 2:
            return arr[0, :, 1]
        # (classes, 1, n) -> classe positive
        if arr.shape[0] == 2:
            return arr[1, 0, :]
        return arr[0, :, 0]
    return arr.reshape(-1)


def _compute_shap_vector(model, feature_vector, feature_names, background, model_type):
    fv = np.asarray(feature_vector, dtype=float).reshape(1, -1)
    if model_type == "tree":
        explainer = shap.TreeExplainer(model)
        raw = explainer.shap_values(fv)
        return _positive_class_shap(raw)
    # linear
    if background is None:
        background = np.zeros((1, fv.shape[1]))
    explainer = shap.LinearExplainer(model, np.asarray(background, dtype=float))
    raw = explainer.shap_values(fv)
    return _positive_class_shap(raw)


def explain_lead(
    model,
    feature_vector,
    feature_names: list,
    lead_score_ml: int,
    lead_score_llm: int | None = None,
    background=None,
    model_type: str | None = None,
    model_version: str = "v1.0",
) -> dict:
    """Retourne l'explication SHAP complète d'un lead (top 5 facteurs + texte)."""
    model_type = model_type or _detect_model_type(model)
    shap_vec = _compute_shap_vector(
        model, feature_vector, feature_names, background, model_type,
    )

    abs_total = float(np.sum(np.abs(shap_vec))) or 1.0
    order = np.argsort(np.abs(shap_vec))[::-1][:5]

    top_factors = []
    for idx in order:
        sv = float(shap_vec[idx])
        feat = feature_names[idx]
        direction = "positive" if sv >= 0 else "negative"
        top_factors.append({
            "feature": feat,
            "label": resolve_label(feat),
            "shap_value": round(sv, 4),
            "direction": direction,
            "impact_pct": round(abs(sv) / abs_total * 100, 1),
            "description": _describe(feat, direction),
        })

    probability = round(lead_score_ml / 100.0, 4)
    category = categorize_score(probability)
    delta = (lead_score_ml - lead_score_llm) if lead_score_llm is not None else None

    return {
        "ml_score": int(lead_score_ml),
        "ml_probability": probability,
        "ml_category": category,
        "llm_score": lead_score_llm,
        "delta": delta,
        "top_factors": top_factors,
        "explanation_text": generate_explanation_text(top_factors, category, lead_score_ml),
        "model_version": model_version,
    }


def generate_explanation_text(top_factors: list, category: str, score: int) -> str:
    """Phrase d'explication en français pour un commercial non-technique."""
    cat_fr = {"hot": "chaud", "warm": "tiède", "cold": "froid"}.get(category, category)
    positives = [f for f in top_factors if f["direction"] == "positive"][:3]
    negatives = [f for f in top_factors if f["direction"] == "negative"][:2]

    if not top_factors:
        return f"Ce lead est {cat_fr} (score {score}/100)."

    parts = [f["label"].lower() for f in positives]
    if len(parts) >= 2:
        raisons = ", ".join(parts[:-1]) + " et " + parts[-1]
    elif parts:
        raisons = parts[0]
    else:
        raisons = "les signaux disponibles"

    txt = f"Ce lead est {cat_fr} (score {score}/100) principalement grâce à : {raisons}."
    if negatives:
        freins = " et ".join(f["label"].lower() for f in negatives)
        txt += f" Points de vigilance : {freins}."
    return txt


if __name__ == "__main__":
    import joblib
    from pathlib import Path

    bundle = joblib.load(Path(__file__).resolve().parents[2] / "artifacts" / "best_model.joblib")
    fnames = bundle["feature_names"]
    fv = np.zeros(len(fnames))
    result = explain_lead(
        model=bundle["raw_model"], feature_vector=fv, feature_names=fnames,
        lead_score_ml=82, lead_score_llm=70,
        background=bundle.get("background"), model_type=bundle["model_type"],
        model_version=bundle["version"],
    )
    print("ml_score        :", result["ml_score"])
    print("ml_category     :", result["ml_category"])
    print("delta vs LLM    :", result["delta"])
    print("explanation     :", result["explanation_text"])
    print("top_factors     :")
    for f in result["top_factors"]:
        print(f"  - {f['label']:30} shap={f['shap_value']:+.4f}  "
              f"{f['direction']:8} {f['impact_pct']}%")
