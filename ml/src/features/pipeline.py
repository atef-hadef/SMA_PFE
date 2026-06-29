"""
pipeline.py
===========
Construction de la matrice de features X complète pour l'entraînement ET le serving.

Garanties (défendables en soutenance) :
  - AUCUNE fuite de données : on exclut explicitement les colonnes dérivées du
    résultat (status, priority, customer_status, lead_score, last_contact_at, ...).
  - Encoders OneHot fittés au training, sauvegardés, puis RÉUTILISÉS au serving
    (handle_unknown="ignore" -> robuste aux catégories nouvelles).
  - Features contact (has_phone, has_company, email_is_professional,
    phone_is_tunisian) : présentes pour cohérence training/serving mais valent 0
    au training car le dataset ne contient pas ces colonnes (choix validé #1).

Colonnes INCLUSES :
  - source, language (OneHotEncoded)
  - sentiment, urgency, intention, product_service, location (OneHotEncoded) :
    attributs extraits par l'IA À L'ARRIVÉE du lead (avant toute conversion) ->
    disponibles au scoring, NON dérivés du résultat => PAS une fuite. Ce sont les
    vrais prédicteurs (cf. générateur). `sentiment` est renommé `ai_sentiment`
    pour éviter la collision avec les flags NLP sentiment_positive/negative/neutral.
  - interaction_count, estimated_value (numériques)
  - toutes les features NLP extraites du message (contribution originale)
  - features temporelles (depuis created_at)

Colonnes EXCLUES (fuite de données — dérivées de la proba/du résultat) :
  - customer_status, status, priority  -> dérivées de la proba/résultat
  - lead_score                         -> baseline LLM à battre, pas une feature
  - last_contact_at                    -> indisponible à l'arrivée du lead
  - converted                          -> label Y
  - id                                 -> identifiant
"""

from __future__ import annotations

import re
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import OneHotEncoder

from .nlp_extractor import NLP_FEATURE_NAMES, extract_nlp_features

# --------------------------------------------------------------------------- #
# CHEMINS (absolus, calculés depuis __file__ — pas de chemin fragile)
# --------------------------------------------------------------------------- #
_ML_ROOT = Path(__file__).resolve().parents[2]          # .../ml
DATASET_PATH = _ML_ROOT / "leads_dataset.csv"
ARTIFACTS_DIR = _ML_ROOT / "artifacts"
ENCODERS_PATH = ARTIFACTS_DIR / "encoders.joblib"

# Colonnes catégorielles -> OneHot. Clé = colonne du dataset, valeur = préfixe
# de sortie (évite la collision sentiment_* avec les flags NLP).
CATEGORICAL_SOURCE = {
    "source": "source",
    "language": "language",
    "sentiment": "ai_sentiment",
    "urgency": "ai_urgency",
    "intention": "intention",
    "product_service": "product",
    "location": "city",
}
CATEGORICAL_COLS = list(CATEGORICAL_SOURCE.keys())

# Colonnes numériques brutes du dataset
NUMERIC_COLS = ["interaction_count", "estimated_value"]

# Colonnes à exclure absolument (fuite de données)
LEAKAGE_COLS = [
    "customer_status", "status", "priority", "lead_score",
    "last_contact_at", "converted", "id",
]

# Features de surface purement structurelles : bruit pénalisant au serving
# (cf. AUDIT ML). Retirées du modèle. Toggle ici si l'AUC repasse < 0.77.
SURFACE_DROP = ["word_count", "char_count", "avg_word_length", "uppercase_ratio"]

# Nouveaux signaux d'achat binaires (QUICK FIX ML) — jamais standardisés.
_NEW_BINARY = [
    "has_budget_mention", "has_urgency_signal", "has_signature_intent",
    "has_quote_request", "has_company_identifier", "has_decision_maker",
    "is_professional_tone", "has_contact_info",
]

_BINARY_EXCLUDE = {
    "has_numbers", "competitor_mentioned", "has_phone", "has_company",
    "email_is_professional", "phone_is_tunisian", "is_business_hours",
    "is_morning", "is_afternoon", "is_weekend", "sentiment_positive",
    "sentiment_negative", "sentiment_neutral", *_NEW_BINARY,
}

# Features NLP continues à standardiser (le reste = binaires/temporelles ordinales).
# message_specificity (0..3) reste continu. Les SURFACE_DROP sont hors modèle.
CONTINUOUS_NLP = [
    n for n in NLP_FEATURE_NAMES
    if n not in _BINARY_EXCLUDE and n not in SURFACE_DROP
]

TARGET_COL = "converted"


def load_dataset(path: str | Path | None = None) -> pd.DataFrame:
    """Charge ml/leads_dataset.csv."""
    csv_path = Path(path) if path else DATASET_PATH
    return pd.read_csv(csv_path)


def _extract_nlp_block(df: pd.DataFrame) -> pd.DataFrame:
    """
    Applique extract_nlp_features ligne par ligne sur (message, created_at).
    phone/company/email absents du dataset -> features contact à 0 (choix #1).
    """
    records = []
    messages = df.get("message", pd.Series([""] * len(df)))
    created = df.get("created_at", pd.Series([None] * len(df)))
    for msg, ca in zip(messages, created):
        feats = extract_nlp_features(
            message=str(msg) if pd.notna(msg) else "",
            phone=None, company=None, email=None,
            created_at=ca if pd.notna(ca) else None,
        )
        records.append(feats)
    nlp_df = pd.DataFrame.from_records(records, columns=NLP_FEATURE_NAMES)
    nlp_df = nlp_df.drop(columns=SURFACE_DROP, errors="ignore")
    return nlp_df.reset_index(drop=True)


def build_feature_matrix(
    df: pd.DataFrame,
    fit_encoders: bool = True,
    encoders: dict | None = None,
) -> tuple[pd.DataFrame, dict]:
    """
    Construit la matrice X prête pour le ML.

    Retourne (X, encoders) où :
      - X         : DataFrame de features (numériques + binaires + OHE)
      - encoders  : dict {"onehot": OneHotEncoder, "categorical_cols": [...]}
                    fitté, réutilisable au serving.
    """
    df = df.reset_index(drop=True)

    # --- 1. Bloc NLP + temporel + contact (depuis le message) ---
    nlp_df = _extract_nlp_block(df)

    # --- 2. Bloc numérique brut ---
    num_df = pd.DataFrame(index=df.index)
    for col in NUMERIC_COLS:
        num_df[col] = pd.to_numeric(df.get(col, 0), errors="coerce").fillna(0.0)

    # --- 3. Bloc OneHot (catégoriels renommés vers leurs préfixes) ---
    prefixes = [CATEGORICAL_SOURCE[c] for c in CATEGORICAL_COLS]
    cat_raw = pd.DataFrame(index=df.index)
    for col, prefix in zip(CATEGORICAL_COLS, prefixes):
        cat_raw[prefix] = df.get(col, "").astype(str).fillna("")

    if fit_encoders or encoders is None:
        ohe = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
        ohe.fit(cat_raw[prefixes])
        encoders = {"onehot": ohe, "categorical_cols": prefixes}
    else:
        ohe = encoders["onehot"]

    ohe_arr = ohe.transform(cat_raw[prefixes])
    ohe_cols = list(ohe.get_feature_names_out(prefixes))
    ohe_df = pd.DataFrame(ohe_arr, columns=ohe_cols, index=df.index)

    # --- 4. Concaténation finale ---
    X = pd.concat([num_df, nlp_df, ohe_df], axis=1)

    # Sécurité : pas de NaN, types numériques
    X = X.apply(pd.to_numeric, errors="coerce").fillna(0.0)

    # Sanitize les noms de colonnes (LightGBM rejette ,/:/espaces/etc.)
    X.columns = [re.sub(r"[^0-9A-Za-z_]", "_", str(c)) for c in X.columns]

    # Sauvegarde des encoders au fit (réutilisés au serving)
    if fit_encoders:
        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(encoders, ENCODERS_PATH)

    return X, encoders


def get_feature_names(X: pd.DataFrame) -> list:
    """Retourne la liste des noms de features."""
    return list(X.columns)


def get_target(df: pd.DataFrame) -> np.ndarray:
    """Retourne le vecteur cible converted."""
    return df[TARGET_COL].astype(int).to_numpy()


# Colonnes binaires / OHE à NE PAS standardiser (cf. train.py)
BINARY_FEATURE_NAMES = [
    "has_numbers", "competitor_mentioned", "has_phone", "has_company",
    "email_is_professional", "phone_is_tunisian", "is_business_hours",
    "is_morning", "is_afternoon", "is_weekend", "sentiment_positive",
    "sentiment_negative", "sentiment_neutral", *_NEW_BINARY,
]


def get_numeric_feature_names(X: pd.DataFrame) -> list:
    """
    Colonnes à standardiser : numériques continues uniquement (jamais les
    binaires 0/1 ni les colonnes OneHot). Liste blanche explicite => robuste
    quels que soient les préfixes OHE présents.
    """
    continuous = set(NUMERIC_COLS) | set(CONTINUOUS_NLP)
    return [c for c in X.columns if c in continuous]


if __name__ == "__main__":
    df = load_dataset()
    X, enc = build_feature_matrix(df)
    print("Shape X      :", X.shape)
    print("NaN total    :", int(X.isna().sum().sum()))
    print("Features (5) :", list(X.columns[:5]))
    print("Nb features  :", X.shape[1])
    print("OHE cols     :", [c for c in X.columns if c.startswith(('source_', 'language_'))])
    print("A standardiser:", get_numeric_feature_names(X))
    print("Encoders sauvegardes ->", ENCODERS_PATH)
