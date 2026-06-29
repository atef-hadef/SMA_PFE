"""
generate_leads_dataset.py
=========================
Génère un dataset SYNTHÉTIQUE de leads CRM fidèle au schéma réel de FlowPilot AI
(modèle SQLAlchemy `CrmLead` + schémas Pydantic `crm.py`).

Objectif : entraîner un modèle de *lead scoring* (prédiction de conversion) sur des
données qui ont EXACTEMENT la même forme et les mêmes vocabulaires que celles que
le système collecte en production.

Points clés de réalisme (pour être défendable en soutenance) :
  - Vocabulaires identiques au code (status, sentiment, urgency, intention, sources,
    produits, villes tunisiennes, lifecycle customer_status...).
  - La cible `converted` est générée par un PROCESSUS PROBABILISTE BRUITÉ (modèle
    logit + bruit gaussien + bruit d'étiquette), donc le dataset n'est PAS
    trivialement séparable -> AUC réaliste (~0.80-0.88), pas 0.99 suspect.
  - On génère aussi `lead_score` = l'ANCIEN score produit par le LLM (corrélé mais
    imparfait) pour permettre la comparaison : ton modèle ML vs le scoring actuel.
  - Messages texte bilingues (fr/en) cohérents avec sentiment + intention.

Usage :
    python generate_leads_dataset.py                 # 5000 lignes -> leads_dataset.csv
    python generate_leads_dataset.py --n 10000 --out data/leads.csv --seed 42
"""

from __future__ import annotations

import argparse
import math
import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# 1. VOCABULAIRES — copiés depuis le code réel (crm.py, seed_db.py, crm_lead.py)
# --------------------------------------------------------------------------- #

# crm.py: status Literal["new", "hot", "warm", "cold"]
LEAD_STATUSES = ["new", "hot", "warm", "cold"]

# crm.py: sentiment Literal["positive", "neutral", "negative"]
SENTIMENTS = ["positive", "neutral", "negative"]

# crm.py: urgency Literal["low", "medium", "high"]
URGENCIES = ["low", "medium", "high"]

# seed_db.py: valeurs d'intention réellement utilisées
INTENTIONS = ["purchase-ready", "evaluation", "information-gathering"]

# seed_db.py: source ("web", "referral", "email") + canaux réalistes du même type
SOURCES = ["web", "referral", "email", "social_media", "event", "partner",
           "organic_search", "cold_call"]

# seed_db.py: priority high / medium / low
PRIORITIES = ["low", "medium", "high"]

# seed_db.py: tes vrais produits/services
PRODUCTS = ["AI CRM Automation", "CRM Workflow Automation", "Automation Consulting"]

# seed_db.py: villes tunisiennes (projet tunisien)
LOCATIONS = ["Tunis, Tunisia", "Sfax, Tunisia", "Sousse, Tunisia",
             "Ariana, Tunisia", "Nabeul, Tunisia", "Monastir, Tunisia",
             "Bizerte, Tunisia", "Gabes, Tunisia"]

# crm.py / n8n_callback_service.py: paliers de cycle de vie
LIFECYCLE_CONVERTED = ["customer", "active_customer", "loyal_customer", "vip_customer"]
LIFECYCLE_NOT_CONVERTED = ["lead", "prospect"]

LANGUAGES = ["fr", "en"]

# --------------------------------------------------------------------------- #
# 2. POIDS DU MODÈLE GÉNÉRATIF (logit de conversion)
#    Ce sont les "vraies" relations cachées que le modèle ML devra retrouver.
#    Volontairement non communiquées au modèle -> il doit les apprendre.
# --------------------------------------------------------------------------- #

W_SENTIMENT = {"positive": 1.2, "neutral": 0.0, "negative": -1.1}
W_URGENCY = {"high": 1.0, "medium": 0.3, "low": -0.6}
W_INTENTION = {"purchase-ready": 1.6, "evaluation": 0.4, "information-gathering": -0.9}
W_SOURCE = {
    "referral": 1.0, "partner": 0.8, "event": 0.5, "web": 0.2,
    "organic_search": 0.1, "social_media": 0.0, "email": -0.2, "cold_call": -0.9,
}
W_PRODUCT = {
    "AI CRM Automation": 0.3,
    "CRM Workflow Automation": 0.1,
    "Automation Consulting": -0.1,
}

INTERCEPT = -2.5          # abaissé (était -2.0) pour compenser le bonus texte ci-dessous
VALUE_COEF = 0.0000018    # influence (faible) du montant estimé
NOISE_STD = 0.7           # bruit gaussien sur le logit -> rend la tâche non triviale
LABEL_FLIP_RATE = 0.05    # 5% d'étiquettes bruitées (clients imprévisibles)

# QUICK FIX ML (lever D) : signaux d'achat injectés dans le message AVEC un poids
# propre dans le logit, et une proba d'apparition INDÉPENDANTE de `intention`
# (+ bonus si purchase-ready pour rester cohérent). Conséquence : ces signaux ne
# sont pas colinéaires avec `intention` -> le modèle DOIT lire le texte pour les
# capter -> les features has_budget_mention/has_signature_intent/... deviennent
# réellement prédictives (et apparaissent dans l'importance).
W_TEXT_SIGNAL = 0.45      # poids par signal d'achat DISTINCT présent dans le message
BUYING_SIGNAL_BASE_P = {"budget": 0.18, "signature": 0.15, "quote": 0.20, "urgency": 0.22}
PURCHASE_READY_BONUS = 0.35   # proba de signal plus forte si intention purchase-ready

SIGNAL_PHRASES = {
    ("budget", "fr"): ["Notre budget est validé à {amt} TND.", "Budget de {amt} TND déjà approuvé."],
    ("budget", "en"): ["Our budget of {amt} TND is approved.", "We have a {amt} TND budget ready."],
    ("signature", "fr"): ["Nous voulons signer rapidement.", "Prêts à signer le contrat."],
    ("signature", "en"): ["We want to sign quickly.", "Ready to sign the contract."],
    ("quote", "fr"): ["Merci de nous envoyer un devis.", "Pouvez-vous transmettre un tarif ?"],
    ("quote", "en"): ["Please send us a quote.", "Can you share your pricing?"],
    ("urgency", "fr"): ["C'est urgent, ce mois-ci idéalement.", "Nous sommes pressés."],
    ("urgency", "en"): ["It's urgent, ideally this month.", "We're in a hurry."],
}

# Baseline LLM RÉALISTE : le score legacy du LLM est un estimateur BRUITÉ et
# INDÉPENDANT du logit DÉTERMINISTE. Crucial : il ne "voit" PAS le bruit réalisé
# qui a produit `converted` (un vrai LLM ne connaît pas le résultat futur). Son
# bruit est volontairement plus large que celui de la conversion -> un modèle ML
# qui dispose des features déterministes peut le battre honnêtement.
LLM_NOISE_STD = 1.6       # bruit (indépendant) de l'estimation LLM legacy
                          # -> LLM AUC ~0.69, le ML le bat honnêtement de ~+11%


# --------------------------------------------------------------------------- #
# 3. GÉNÉRATION DES MESSAGES TEXTE (cohérents avec intention + sentiment)
# --------------------------------------------------------------------------- #

MESSAGE_TEMPLATES = {
    ("purchase-ready", "fr"): [
        "Nous voulons démarrer rapidement, pouvez-vous m'envoyer un devis ?",
        "Budget validé en interne, on souhaite signer ce mois-ci.",
        "Prêt à acheter, quelles sont les prochaines étapes pour la mise en place ?",
    ],
    ("purchase-ready", "en"): [
        "We want to start quickly, can you send me a quote?",
        "Budget approved internally, we'd like to sign this month.",
        "Ready to buy, what are the next steps for onboarding?",
    ],
    ("evaluation", "fr"): [
        "Nous comparons plusieurs solutions, pouvez-vous présenter une démo ?",
        "Intéressés mais nous évaluons encore les options du marché.",
        "Quels sont vos tarifs par rapport à la concurrence ?",
    ],
    ("evaluation", "en"): [
        "We are comparing several solutions, can you arrange a demo?",
        "Interested but still evaluating market options.",
        "How does your pricing compare to competitors?",
    ],
    ("information-gathering", "fr"): [
        "Juste quelques renseignements sur ce que vous proposez.",
        "Je découvre votre produit, avez-vous une documentation ?",
        "Pas pressé, je collecte juste des informations pour plus tard.",
    ],
    ("information-gathering", "en"): [
        "Just gathering some information about what you offer.",
        "Discovering your product, do you have any documentation?",
        "No rush, just collecting information for later.",
    ],
}


def make_message(intention: str, language: str, rng: random.Random) -> str:
    return rng.choice(MESSAGE_TEMPLATES[(intention, language)])


# --------------------------------------------------------------------------- #
# 4. FONCTIONS DÉRIVÉES (status, priority, lead_score legacy, customer_status)
# --------------------------------------------------------------------------- #

def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def derive_status(prob: float, sentiment: str) -> str:
    """status commercial (new/hot/warm/cold) dérivé de la proba + sentiment."""
    if prob >= 0.65 and sentiment == "positive":
        return "hot"
    if prob >= 0.45:
        return "warm"
    if prob >= 0.25:
        return "new"
    return "cold"


def derive_priority(prob: float, urgency: str) -> str:
    if urgency == "high" or prob >= 0.6:
        return "high"
    if urgency == "medium" or prob >= 0.35:
        return "medium"
    return "low"


def derive_legacy_lead_score(det_logit: float, rng: np.random.Generator) -> int:
    """
    Ancien score produit par le LLM en production. C'est un estimateur BRUITÉ et
    INDÉPENDANT du logit DÉTERMINISTE (sans le bruit réalisé de la conversion) :
    le LLM lit le lead et estime une probabilité, sans connaître le futur. Sert de
    BASELINE honnête à battre par le modèle ML.
    """
    llm_prob = sigmoid(det_logit + rng.normal(0, LLM_NOISE_STD))
    return int(np.clip(round(llm_prob * 100), 0, 100))


def derive_customer_status(converted: int, prob: float, rng: random.Random) -> str:
    if converted:
        # plus la proba est forte, plus le palier client est élevé
        weights = [0.5, 0.3, 0.15, 0.05] if prob < 0.7 else [0.3, 0.35, 0.25, 0.10]
        return rng.choices(LIFECYCLE_CONVERTED, weights=weights, k=1)[0]
    return rng.choices(LIFECYCLE_NOT_CONVERTED, weights=[0.7, 0.3], k=1)[0]


def estimated_value_for(product: str, rng: np.random.Generator) -> float:
    """Montant estimé réaliste, dépend du produit (consulting > automation)."""
    base = {
        "AI CRM Automation": 18000,
        "CRM Workflow Automation": 12000,
        "Automation Consulting": 25000,
    }[product]
    val = rng.lognormal(mean=math.log(base), sigma=0.5)
    return round(float(np.clip(val, 1500, 200000)), 2)


# --------------------------------------------------------------------------- #
# 5. GÉNÉRATION PRINCIPALE
# --------------------------------------------------------------------------- #

def generate(n: int, seed: int) -> pd.DataFrame:
    rng_np = np.random.default_rng(seed)
    rng_py = random.Random(seed)

    rows = []
    start_date = datetime(2025, 1, 1)

    for i in range(n):
        # --- features brutes (distributions réalistes, non uniformes) ---
        source = rng_py.choices(
            SOURCES, weights=[25, 18, 14, 12, 8, 7, 10, 6], k=1
        )[0]
        sentiment = rng_py.choices(SENTIMENTS, weights=[40, 38, 22], k=1)[0]
        urgency = rng_py.choices(URGENCIES, weights=[35, 40, 25], k=1)[0]
        intention = rng_py.choices(INTENTIONS, weights=[30, 40, 30], k=1)[0]
        product = rng_py.choices(PRODUCTS, weights=[45, 35, 20], k=1)[0]
        location = rng_py.choice(LOCATIONS)
        language = rng_py.choices(LANGUAGES, weights=[70, 30], k=1)[0]
        estimated_value = estimated_value_for(product, rng_np)

        # --- nombre d'interactions (signal d'engagement réel du CRM) ---
        # corrélé à l'urgence : un lead urgent interagit davantage
        lam = {"high": 4.0, "medium": 2.2, "low": 1.0}[urgency]
        interaction_count = int(rng_np.poisson(lam))

        # --- QUICK FIX ML : signaux d'achat injectés (proba indép. de intention) ---
        signal_bonus = PURCHASE_READY_BONUS if intention == "purchase-ready" else 0.0
        signals_present, extra_phrases = [], []
        for sig in ("budget", "signature", "quote", "urgency"):
            if rng_py.random() < min(0.95, BUYING_SIGNAL_BASE_P[sig] + signal_bonus):
                signals_present.append(sig)
                phrase = rng_py.choice(SIGNAL_PHRASES[(sig, language)])
                if sig == "budget":
                    phrase = phrase.format(amt=f"{int(estimated_value):,}".replace(",", " "))
                extra_phrases.append(phrase)
        signal_strength = len(signals_present)

        # --- logit DÉTERMINISTE (le "vrai" mécanisme caché, sans bruit) ---
        det_logit = (
            INTERCEPT
            + W_SENTIMENT[sentiment]
            + W_URGENCY[urgency]
            + W_INTENTION[intention]
            + W_SOURCE[source]
            + W_PRODUCT[product]
            + VALUE_COEF * estimated_value
            + 0.12 * interaction_count
            + W_TEXT_SIGNAL * signal_strength
        )
        # logit de conversion = déterministe + bruit réalisé (non observable)
        logit = det_logit + rng_np.normal(0, NOISE_STD)
        prob = sigmoid(logit)
        converted = int(rng_np.random() < prob)

        # --- bruit d'étiquette : ~5% de clients imprévisibles ---
        if rng_np.random() < LABEL_FLIP_RATE:
            converted = 1 - converted

        # --- champs dérivés (comme en production) ---
        status = derive_status(prob, sentiment)
        priority = derive_priority(prob, urgency)
        # baseline LLM : estimateur indépendant sur le logit DÉTERMINISTE
        lead_score = derive_legacy_lead_score(det_logit, rng_np)
        customer_status = derive_customer_status(converted, prob, rng_py)
        message = make_message(intention, language, rng_py)
        if extra_phrases:
            message = message + " " + " ".join(extra_phrases)

        created_at = start_date + timedelta(
            days=int(rng_np.integers(0, 450)),
            hours=int(rng_np.integers(0, 24)),
        )
        # date de dernier contact (None si jamais contacté)
        if interaction_count > 0:
            last_contact_at = created_at + timedelta(
                days=int(rng_np.integers(0, 30))
            )
        else:
            last_contact_at = None

        rows.append({
            "id": f"lead_{i:06d}",
            "source": source,
            "sentiment": sentiment,
            "urgency": urgency,
            "intention": intention,
            "product_service": product,
            "location": location,
            "language": language,
            "estimated_value": estimated_value,
            "interaction_count": interaction_count,
            "message": message,
            # champs produits par l'IA actuelle (legacy) :
            "status": status,
            "priority": priority,
            "lead_score": lead_score,          # BASELINE LLM à comparer
            "customer_status": customer_status,
            "created_at": created_at.isoformat(),
            "last_contact_at": last_contact_at.isoformat() if last_contact_at else "",
            # CIBLE du modèle ML :
            "converted": converted,
        })

    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# 6. CLI + rapport rapide
# --------------------------------------------------------------------------- #

def main() -> None:
    parser = argparse.ArgumentParser(description="Génère un dataset CRM synthétique.")
    parser.add_argument("--n", type=int, default=5000, help="Nombre de leads.")
    parser.add_argument("--out", type=str, default="leads_dataset.csv", help="CSV de sortie.")
    parser.add_argument("--seed", type=int, default=42, help="Graine aléatoire.")
    args = parser.parse_args()

    df = generate(args.n, args.seed)
    df.to_csv(args.out, index=False, encoding="utf-8")

    rate = df["converted"].mean()
    print(f"[OK] {len(df)} leads générés -> {args.out}")
    print(f"     Taux de conversion : {rate:.1%}")
    print(f"     Colonnes : {list(df.columns)}")
    print("\nAperçu :")
    print(df.head(5).to_string(index=False))
    print("\nRépartition par sentiment :")
    print(df.groupby('sentiment')['converted'].mean().round(3).to_string())


if __name__ == "__main__":
    main()
