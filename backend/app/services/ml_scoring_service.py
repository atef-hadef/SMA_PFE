"""
ml_scoring_service.py
=====================
Service de scoring ML pour le CRM. Charge le modèle entraîné (bundle joblib) une
seule fois (singleton), score un lead à partir de son message + métadonnées, et
fournit une explication SHAP. Si le modèle n'est pas disponible, bascule sur un
fallback NLP simple (sans SHAP).

Chemins robustes : tout est résolu depuis __file__ (choix validé #4, pas de
chemin relatif fragile). ml/src est ajouté au sys.path pour réutiliser le code
Data Science (features, explainability) sans duplication.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

# --- Résolution des chemins (depuis backend/app/services/ -> racine projet) ---
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_ML_DIR = _PROJECT_ROOT / "ml"
_ML_SRC = _ML_DIR / "src"
_ARTIFACTS = _ML_DIR / "artifacts"

MODEL_PATH = _ARTIFACTS / "best_model.joblib"
ENCODERS_PATH = _ARTIFACTS / "encoders.joblib"
REGISTRY_PATH = _ARTIFACTS / "model_registry.json"
METRICS_PATH = _ARTIFACTS / "metrics.json"
IMPORTANCE_PATH = _ARTIFACTS / "feature_importance.json"

if str(_ML_SRC) not in sys.path:
    sys.path.insert(0, str(_ML_SRC))


def _safe_json(path: Path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


# Labels métier FR pour l'explication SHAP affichée dans la fiche lead (présentation
# serving — n'altère pas le cœur ML/shap_local). Fallback sur le label existant.
FEATURE_LABELS_FR = {
    "intention_purchase_ready": "Intention d'achat confirmée",
    "intention_information_gathering": "Phase de découverte",
    "intention_evaluation": "En phase d'évaluation",
    "ai_urgency_high": "Urgence élevée détectée",
    "ai_urgency_low": "Aucune urgence signalée",
    "ai_urgency_medium": "Urgence modérée",
    "ai_sentiment_positive": "Message à tonalité positive",
    "ai_sentiment_negative": "Signaux négatifs détectés",
    "ai_sentiment_neutral": "Tonalité neutre",
    "has_budget_mention": "Budget explicitement mentionné",
    "has_urgency_signal": "Signal d'urgence temporelle",
    "has_signature_intent": "Intention de signature",
    "has_quote_request": "Demande de devis",
    "has_company_identifier": "Entreprise identifiée",
    "has_decision_maker": "Décideur identifié",
    "is_professional_tone": "Message professionnel",
    "has_contact_info": "Coordonnées fournies",
    "message_specificity": "Message détaillé et précis",
    "sentence_count": "Richesse du message",
    "urgency_score": "Score d'urgence textuel",
    "budget_score": "Indicateurs budgétaires",
    "purchase_ready_score": "Signaux d'achat",
    "decision_score": "Signaux de décision",
    "sentiment_polarity": "Polarité du sentiment",
    "question_count": "Questions posées",
    "word_count": "Volume du message",
    "estimated_value": "Valeur estimée du contrat",
    "interaction_count": "Nombre d'interactions",
    "source_referral": "Source : recommandation",
    "source_email": "Source : email direct",
    "source_web": "Source : site web",
    "source_social_media": "Source : réseaux sociaux",
    "source_cold_call": "Source : appel sortant",
}


def _business_description(category: str, score: int, top_factors: list) -> str:
    """Description contextuelle selon la catégorie, avec labels métier."""
    pos = [f["label"] for f in top_factors if f["direction"] == "positive"][:3]
    neg = [f["label"] for f in top_factors if f["direction"] == "negative"][:3]
    pos_txt = ", ".join(pos) if pos else "les signaux disponibles"
    neg_txt = ", ".join(neg) if neg else "aucun frein majeur"

    if category == "hot":
        return (
            f"Lead à fort potentiel de conversion (score {score}/100). "
            f"Les signaux déterminants sont : {pos_txt}. "
            f"Recommandation : prise de contact prioritaire sous 2h."
        )
    if category == "warm":
        return (
            f"Lead en phase d'évaluation (score {score}/100). "
            f"Points favorables : {pos_txt}. Points de vigilance : {neg_txt}. "
            f"Recommandation : suivi personnalisé sous 24h."
        )
    return (
        f"Lead en phase de découverte (score {score}/100). "
        f"Signaux limitants : {neg_txt}. "
        f"Recommandation : nurturing automatique, relance dans 7-14 jours."
    )


class MLScoringService:
    _instance: "MLScoringService | None" = None

    def __init__(self) -> None:
        self._model = None          # bundle dict
        self._encoders = None
        self._registry = None
        self._model_available = False

    # ------------------------------------------------------------------ #
    @classmethod
    def get_instance(cls) -> "MLScoringService":
        """Singleton — charge le modèle une seule fois."""
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._load_model()
        return cls._instance

    def _load_model(self) -> None:
        try:
            self._model = joblib.load(MODEL_PATH)
            self._encoders = joblib.load(ENCODERS_PATH)
            self._registry = _safe_json(REGISTRY_PATH, {"models": [], "current_production": None})
            self._model_available = True
        except (FileNotFoundError, OSError):
            self._model_available = False

    # ------------------------------------------------------------------ #
    def _build_serving_vector(
        self, message, phone, company, email, source, created_at, known=None,
    ) -> np.ndarray:
        """
        Construit le vecteur de features aligné sur le modèle pour UN lead.

        `known` (optionnel) contient les attributs structurés réels du lead quand
        ils existent en base (sentiment/urgency/intention/estimated_value/...).
        Sinon, ils sont INFÉRÉS depuis le NLP du message (lead brut à l'intake).
        Les features contact sont calculées depuis phone/company/email.
        """
        import re

        from features.nlp_extractor import extract_nlp_features

        known = known or {}
        bundle = self._model
        feature_names = bundle["feature_names"]
        vec = {name: 0.0 for name in feature_names}

        # 1. Features NLP (contact réellement renseigné au serving)
        nlp = extract_nlp_features(
            message=message or "", phone=phone, company=company,
            email=email, created_at=created_at,
        )
        for k, v in nlp.items():
            if k in vec:
                vec[k] = float(v)

        # 2. Catégoriels : attributs réels si fournis, sinon inférés du NLP
        inferred = self._infer_categoricals(nlp, source)
        defaults = bundle.get("serving_defaults", {})
        cat_vals = {
            "source": source or defaults.get("source", ""),
            "language": known.get("language") or defaults.get("language", ""),
            "ai_sentiment": known.get("sentiment") or inferred["ai_sentiment"],
            "ai_urgency": known.get("urgency") or inferred["ai_urgency"],
            "intention": known.get("intention") or inferred["intention"],
            "product": known.get("product_service") or defaults.get("product", ""),
            "city": known.get("location") or defaults.get("city", ""),
        }

        ohe = self._encoders["onehot"]
        prefixes = self._encoders["categorical_cols"]
        full_cat = {p: cat_vals.get(p, "") for p in prefixes}
        df_cat = pd.DataFrame([full_cat])[prefixes]
        ohe_arr = ohe.transform(df_cat)[0]
        ohe_cols = ohe.get_feature_names_out(prefixes)
        for col, val in zip(ohe_cols, ohe_arr):
            key = re.sub(r"[^0-9A-Za-z_]", "_", str(col))
            if key in vec:
                vec[key] = float(val)

        # 3. Numériques : valeur réelle si connue, sinon moyenne (contribution
        #    neutre après standardisation).
        numeric_cols = bundle["numeric_cols"]
        scaler = bundle["scaler"]
        known_num = {
            "interaction_count": known.get("interaction_count"),
            "estimated_value": known.get("estimated_value"),
        }
        for col, kval in known_num.items():
            if col in numeric_cols:
                vec[col] = float(kval) if kval is not None else float(
                    scaler.mean_[numeric_cols.index(col)])

        # 4. Vecteur ordonné + standardisation des colonnes numériques
        ordered = np.array([vec[name] for name in feature_names], dtype=float).reshape(1, -1)
        idx = [feature_names.index(c) for c in numeric_cols if c in feature_names]
        if idx:
            ordered[:, idx] = scaler.transform(ordered[:, idx])
        return ordered

    @staticmethod
    def _infer_categoricals(nlp: dict, source: str | None) -> dict:
        """Infère sentiment/urgence/intention depuis les signaux NLP du message.

        QUICK FIX ML (lever A) : on s'appuie sur les signaux d'achat explicites
        (has_signature_intent, has_quote_request, has_budget_mention,
        has_urgency_signal) pour qu'un lead brut à fort signal active les features
        FORTES du modèle (intention=purchase-ready, urgency=high, sentiment=positive)
        au lieu de retomber sur les features de surface.
        """
        pol = nlp.get("sentiment_polarity", 0.0)
        buy = (
            nlp.get("has_signature_intent", 0)
            + nlp.get("has_quote_request", 0)
            + nlp.get("has_budget_mention", 0)
        )
        # Sentiment : des signaux d'achat explicites (>=2) priment sur TextBlob,
        # peu fiable en français (il classe par ex. "urgent" comme négatif). Un
        # message budget+signature+devis est un signal commercial POSITIF.
        if pol > 0.1 or buy >= 2:
            sentiment = "positive"
        elif pol < -0.1:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        # Urgence : signal explicite ("ce mois", "asap"...) => high
        us = nlp.get("urgency_score", 0.0)
        if nlp.get("has_urgency_signal", 0) or us >= 0.5:
            urgency = "high"
        elif us > 0:
            urgency = "medium"
        else:
            urgency = "low"

        # Intention : signature/devis OU purchase_ready => purchase-ready
        if (
            nlp.get("has_signature_intent", 0)
            or nlp.get("has_quote_request", 0)
            or nlp.get("purchase_ready_score", 0.0) >= 0.33
        ):
            intention = "purchase-ready"
        elif (
            nlp.get("has_budget_mention", 0)
            or nlp.get("budget_score", 0.0) > 0
            or nlp.get("decision_score", 0.0) > 0
        ):
            intention = "evaluation"
        else:
            intention = "information-gathering"

        return {
            "source": source or "",
            "language": "",
            "ai_sentiment": sentiment,
            "ai_urgency": urgency,
            "intention": intention,
            "product": "",
            "city": "",
        }

    # ------------------------------------------------------------------ #
    def score_lead(
        self,
        lead_id: str,
        message: str,
        phone: str | None = None,
        company: str | None = None,
        email: str | None = None,
        source: str = "website_form",
        created_at=None,
        llm_score: int | None = None,
        known: dict | None = None,
    ) -> dict:
        if not self._model_available:
            return self._fallback_score(lead_id, message, llm_score)

        from explainability.shap_local import explain_lead

        bundle = self._model
        vector = self._build_serving_vector(
            message, phone, company, email, source, created_at, known,
        )
        proba = float(bundle["calibrated"].predict_proba(vector)[0, 1])
        ml_score = int(round(proba * 100))

        explanation = explain_lead(
            model=bundle["raw_model"],
            feature_vector=vector[0],
            feature_names=bundle["feature_names"],
            lead_score_ml=ml_score,
            lead_score_llm=llm_score,
            background=bundle.get("background"),
            model_type=bundle["model_type"],
            model_version=bundle.get("version", "v1.0"),
        )
        # Présentation serving : labels métier + description contextuelle.
        for f in explanation["top_factors"]:
            f["label"] = FEATURE_LABELS_FR.get(f["feature"], f["label"])
        explanation["explanation_text"] = _business_description(
            explanation["ml_category"], ml_score, explanation["top_factors"],
        )
        # confiance : distance à 0.5 (incertitude max) ramenée sur [0,1]
        confidence = round(abs(proba - 0.5) * 2, 4)

        return {
            "lead_id": lead_id,
            "ml_score": ml_score,
            "ml_probability": round(proba, 4),
            "ml_category": explanation["ml_category"],
            "ml_confidence": confidence,
            "llm_score": llm_score,
            "delta": explanation["delta"],
            "top_factors": explanation["top_factors"],
            "explanation_text": explanation["explanation_text"],
            "model_available": True,
            "model_version": bundle.get("version", "v1.0"),
        }

    def _fallback_score(self, lead_id, message, llm_score) -> dict:
        """Score heuristique NLP simple si le modèle ML n'est pas entraîné."""
        from features.nlp_extractor import extract_nlp_features

        nlp = extract_nlp_features(message or "")
        raw = (
            0.40 * nlp["purchase_ready_score"]
            + 0.25 * nlp["urgency_score"]
            + 0.20 * nlp["budget_score"]
            + 0.15 * nlp["decision_score"]
        )
        proba = round(min(1.0, raw + 0.1), 4)
        ml_score = int(round(proba * 100))
        category = "hot" if proba > 0.70 else "warm" if proba >= 0.40 else "cold"
        return {
            "lead_id": lead_id,
            "ml_score": ml_score,
            "ml_probability": proba,
            "ml_category": category,
            "ml_confidence": 0.0,
            "llm_score": llm_score,
            "delta": (ml_score - llm_score) if llm_score is not None else None,
            "top_factors": [],
            "explanation_text": (
                "Modèle ML non entraîné — score heuristique basé sur les signaux "
                "d'intention détectés dans le message."
            ),
            "model_available": False,
            "model_version": "fallback",
        }

    # ------------------------------------------------------------------ #
    def get_model_info(self) -> dict:
        """Métadonnées du modèle de production (depuis le registre + metrics)."""
        registry = self._registry or _safe_json(REGISTRY_PATH, {"models": [], "current_production": None})
        current = registry.get("current_production")
        entry = next(
            (m for m in registry.get("models", []) if m.get("version") == current),
            None,
        )
        if entry is None:
            metrics = _safe_json(METRICS_PATH, {})
            best = metrics.get("best_model", {})
            entry = {
                "version": best.get("version", "n/a"),
                "trained_at": metrics.get("trained_at", "n/a"),
                "algorithm": best.get("name", "n/a"),
                "auc_roc": best.get("auc_roc", 0.0),
                "f1_score": 0.0,
                "n_features": metrics.get("n_features", 0),
                "n_training_samples": metrics.get("n_training_samples", 0),
                "improvement_vs_llm": best.get("improvement_vs_llm", "n/a"),
                "mlflow_run_id": None,
            }
        return {
            "model_name": "TacTic_LeadScoring",
            "version": entry.get("version", "n/a"),
            "trained_at": str(entry.get("trained_at", "n/a")),
            "algorithm": entry.get("algorithm", "n/a"),
            "auc_roc": float(entry.get("auc_roc") or 0.0),
            "f1_score": float(entry.get("f1_score") or 0.0),
            "n_features": int(entry.get("n_features") or 0),
            "n_training_samples": int(entry.get("n_training_samples") or 0),
            "improvement_vs_llm": entry.get("improvement_vs_llm", "n/a"),
            "mlflow_run_id": entry.get("mlflow_run_id"),
        }

    # ------------------------------------------------------------------ #
    def get_analytics(self, db) -> dict:
        """Données du dashboard Data Science (calcul temps réel depuis la DB)."""
        metrics = _safe_json(METRICS_PATH, {"models": []})
        importance = _safe_json(IMPORTANCE_PATH, [])

        # Comparaison ML vs LLM (depuis metrics.json)
        model_comparison = {
            m["model_name"]: {
                "auc_roc": m.get("auc_roc"),
                "f1_score": m.get("f1_score"),
                "precision_at_20": m.get("precision_at_20"),
                "lift_at_20": m.get("lift_at_20"),
            }
            for m in metrics.get("models", [])
        }

        # Feature importance (top 12, libellés FR)
        feature_importance = importance[:12] if isinstance(importance, list) else []

        # Scoring temps réel des leads récents (DB)
        recent_scores: list[dict] = []
        distribution = {"hot": 0, "warm": 0, "cold": 0}
        try:
            from app.models import CrmLead

            leads = (
                db.query(CrmLead)
                .filter(CrmLead.is_active.is_(True))
                .order_by(CrmLead.created_at.desc())
                .limit(20)
                .all()
            )
            for lead in leads:
                known = {
                    "sentiment": lead.sentiment,
                    "urgency": lead.urgency,
                    "intention": lead.intention,
                    "product_service": lead.product_service,
                    "location": lead.location,
                    "estimated_value": float(lead.estimated_value)
                    if lead.estimated_value is not None else None,
                }
                scored = self.score_lead(
                    lead_id=lead.id, message=lead.message or "",
                    phone=lead.phone, company=lead.company_name,
                    email=lead.email, source=lead.source or "website_form",
                    created_at=lead.created_at, llm_score=lead.lead_score,
                    known=known,
                )
                distribution[scored["ml_category"]] += 1
                if len(recent_scores) < 10:
                    recent_scores.append({
                        "lead_id": lead.id,
                        "lead_name": lead.full_name,
                        "ml_score": scored["ml_score"],
                        "ml_category": scored["ml_category"],
                        "llm_score": scored["llm_score"],
                        "delta": scored["delta"],
                        "scored_at": str(lead.created_at),
                    })
        except Exception:  # noqa: BLE001 — DB vide / indisponible -> dashboard vide
            pass

        # Runs MLflow
        mlflow_runs = self._get_mlflow_runs(metrics)

        return {
            "score_distribution": distribution,
            "model_comparison": model_comparison,
            "feature_importance": feature_importance,
            "recent_scores": recent_scores,
            "mlflow_runs": mlflow_runs,
            "model_info": self.get_model_info(),
        }

    def get_mlflow_runs(self) -> list[dict]:
        """Runs MLflow de l'expériment (pour l'endpoint dédié)."""
        return self._get_mlflow_runs(_safe_json(METRICS_PATH, {"models": []}))

    def _get_mlflow_runs(self, metrics: dict) -> list[dict]:
        """Liste des runs pour le dashboard (MLflow si dispo, sinon metrics.json)."""
        best_name = metrics.get("best_model", {}).get("name")
        try:
            from mlops.mlflow_tracker import MLflowTracker

            df = MLflowTracker().get_all_runs()
            runs = []
            for _, row in df.iterrows():
                name = row.get("tags.mlflow.runName", "run")
                runs.append({
                    "run_id": row.get("run_id", ""),
                    "model_name": name,
                    "auc_roc": float(row.get("metrics.auc_roc") or 0.0),
                    "f1_score": float(row.get("metrics.f1_score") or 0.0),
                    "precision_at_k": float(row.get("metrics.precision_at_20") or 0.0),
                    "status": self._run_status(name, best_name),
                    "started_at": str(row.get("start_time", "")),
                })
            if runs:
                runs.sort(key=lambda r: r["auc_roc"], reverse=True)
                # dédoublonnage par modèle (réentraînements) -> meilleur run gardé
                seen: set[str] = set()
                unique = []
                for r in runs:
                    if r["model_name"] not in seen:
                        seen.add(r["model_name"])
                        unique.append(r)
                return unique
        except Exception:  # noqa: BLE001
            pass

        # Fallback : à partir de metrics.json
        return [
            {
                "run_id": "",
                "model_name": m["model_name"],
                "auc_roc": m.get("auc_roc", 0.0),
                "f1_score": m.get("f1_score", 0.0),
                "precision_at_k": m.get("precision_at_20", 0.0),
                "status": self._run_status(m["model_name"], best_name),
                "started_at": metrics.get("trained_at", ""),
            }
            for m in metrics.get("models", [])
        ]

    @staticmethod
    def _run_status(name: str, best_name: str | None) -> str:
        if "LLM" in (name or "").upper():
            return "baseline"
        if best_name and best_name.replace(" ", "") in (name or "").replace(" ", ""):
            return "production"
        return "candidate"
