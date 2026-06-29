"""
nlp_extractor.py
================
Extraction de features NLP depuis le message texte d'un prospect.

C'est la *contribution originale* du module Data Science TAC-TIC : transformer un
message libre en signaux numériques exploitables par un modèle de scoring.

Quatre familles de features :
  1. Structurelles     -> forme du message (longueur, ponctuation, casse...)
  2. Intention         -> scores 0..1 par lexique métier français (urgence, budget...)
  3. Contact           -> qualité des coordonnées (pro vs perso, numéro TN...)
  4. Temporelles       -> moment de soumission (heure, jour, horaires pro...)
  5. Sentiment         -> TextBlob + mini-lexique FR maison (cf. choix validé #3)

Aucune dépendance fragile (pas de googletrans). TextBlob est faible en français,
on le complète donc par un lexique FR maison ; on documente cette limite.

Test intégré : `python ml/src/features/nlp_extractor.py`
"""

from __future__ import annotations

import re
from datetime import datetime

try:
    from textblob import TextBlob
    _TEXTBLOB_OK = True
except Exception:  # pragma: no cover - fallback si TextBlob indisponible
    _TEXTBLOB_OK = False


# --------------------------------------------------------------------------- #
# LEXIQUES D'INTENTION (français)
# --------------------------------------------------------------------------- #

URGENCY_WORDS = [
    "urgent", "rapidement", "vite", "pressé", "presse", "immédiatement",
    "immediatement", "dès que possible", "des que possible", "délai", "delai",
    "besoin urgent", "au plus vite", "asap", "sans délai", "sans delai",
    "dans les meilleurs délais", "dans les meilleurs delais",
]

BUDGET_WORDS = [
    "budget", "devis", "prix", "tarif", "tnd", "dt", "investissement", "coût",
    "cout", "combien", "financement", "montant", "estimation", "offre",
    "proposition",
]

DECISION_WORDS = [
    "choisir", "décider", "decider", "adopter", "implémenter", "implementer",
    "sélectionner", "selectionner", "retenir", "valider", "opter pour",
    "trancher", "finaliser",
]

PURCHASE_READY_WORDS = [
    "signer", "contrat", "commencer", "démarrer", "demarrer", "lancer",
    "acheter", "acquérir", "acquerir", "procéder", "proceder", "confirmer",
    "ordre", "bon de commande",
]

PROBLEM_AWARENESS_WORDS = [
    "problème", "probleme", "difficulté", "difficulte", "mal", "perdre",
    "manquer", "besoin", "cherche", "souffrir", "inefficace", "perte",
    "retard", "erreur",
]

COMPETITOR_WORDS = [
    "concurrent", "autre solution", "actuellement", "utilisons", "migrer",
    "changer de", "remplacer", "migration", "actuellement avec",
]

# Mini-lexique de sentiment FR maison (complément à TextBlob, choix validé #3)
FR_POSITIVE_WORDS = [
    "merci", "excellent", "parfait", "super", "génial", "genial", "ravi",
    "content", "satisfait", "intéressé", "interesse", "hâte", "hate",
    "convaincu", "impressionné", "impressionne", "bravo", "top", "idéal",
    "ideal", "prometteur", "enthousiaste",
]
FR_NEGATIVE_WORDS = [
    "problème", "probleme", "difficulté", "difficulte", "déçu", "decu",
    "insatisfait", "mauvais", "lent", "cher", "compliqué", "complique",
    "inefficace", "perte", "retard", "erreur", "souffrir", "frustré",
    "frustre", "bloqué", "bloque", "inquiet",
]

# Domaines email "grand public" (non professionnels)
PERSONAL_EMAIL_DOMAINS = ["gmail", "yahoo", "hotmail", "outlook", "live", "msn"]

# Seuil de saturation : N mots-clés distincts touchés -> score 1.0
_INTENT_SATURATION = 3.0

# --- QUICK FIX ML : signaux d'achat explicites (features binaires, FR + EN) ---
SIGNATURE_INTENT_WORDS = [
    "signer", "signature", "contrat", "accord", "validé", "valide", "engagement",
    "bon de commande", "sign", "contract", "agreement", "approved", "purchase order",
]
QUOTE_REQUEST_WORDS = [
    "devis", "tarif", "tarifs", "prix", "offre", "proposition",
    "quote", "pricing", "price", "proposal", "estimate",
]
COMPANY_IDENTIFIER_WORDS = [
    "notre entreprise", "notre société", "notre societe", "nous sommes",
    "notre équipe", "notre equipe", "our company", "we are", "our team",
]
DECISION_MAKER_WORDS = [
    "nous voulons", "nous allons", "nous avons décidé", "nous avons decide",
    "décidé", "decide", "we want", "we will", "we have decided", "we need",
]
URGENCY_SIGNAL_WORDS = URGENCY_WORDS + [
    "ce mois", "ce mois-ci", "cette semaine", "this month", "this week",
    "quickly", "as soon as possible", "right away",
]
BUDGET_MENTION_WORDS = ["budget", "tnd", "dt", "eur", "euro", "€", "dinar", "dinars"]
_CONTACT_INFO_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+|\+?\d[\d ().-]{6,}\d")
_DATE_RE = re.compile(
    r"\b\d{1,2}[/-]\d{1,2}|\b(janvier|février|fevrier|mars|avril|mai|juin|juillet|"
    r"ao[uû]t|septembre|octobre|novembre|décembre|decembre|january|february|march|"
    r"april|june|july|august|september|october|november|december)\b"
)


# --------------------------------------------------------------------------- #
# HELPERS
# --------------------------------------------------------------------------- #

def _keyword_score(text_lower: str, keywords: list[str]) -> float:
    """
    Score d'intention 0.0..1.0 = (nb de mots-clés distincts présents) / seuil,
    plafonné à 1.0. Saturant : 3 mots-clés distincts suffisent pour 1.0.
    """
    if not text_lower:
        return 0.0
    hits = sum(1 for kw in keywords if kw in text_lower)
    return round(min(1.0, hits / _INTENT_SATURATION), 4)


def _count_keyword_hits(text_lower: str, keywords: list[str]) -> int:
    return sum(1 for kw in keywords if kw in text_lower)


def _parse_datetime(created_at) -> datetime | None:
    """Accepte datetime, str ISO, ou None. Retourne datetime ou None."""
    if created_at is None or created_at == "":
        return None
    if isinstance(created_at, datetime):
        return created_at
    if isinstance(created_at, str):
        try:
            return datetime.fromisoformat(created_at)
        except ValueError:
            return None
    return None


def _fr_lexicon_polarity(text_lower: str) -> float:
    """Polarité FR maison dans [-1, 1] à partir du comptage pos/neg."""
    pos = _count_keyword_hits(text_lower, FR_POSITIVE_WORDS)
    neg = _count_keyword_hits(text_lower, FR_NEGATIVE_WORDS)
    total = pos + neg
    if total == 0:
        return 0.0
    return round((pos - neg) / total, 4)


# --------------------------------------------------------------------------- #
# FAMILLES DE FEATURES
# --------------------------------------------------------------------------- #

def _structural_features(message: str) -> dict:
    msg = message or ""
    words = re.findall(r"\b\w+\b", msg, flags=re.UNICODE)
    word_count = len(words)
    char_count = len(msg)

    # phrases : split sur '.', segments non vides (min 1 si du texte existe)
    sentence_parts = [p for p in msg.split(".") if p.strip()]
    sentence_count = len(sentence_parts) if sentence_parts else (1 if msg.strip() else 0)

    # paragraphes : séparés par double saut de ligne
    para_parts = [p for p in re.split(r"\n\s*\n", msg) if p.strip()]
    paragraph_count = len(para_parts) if para_parts else (1 if msg.strip() else 0)

    avg_word_length = round(sum(len(w) for w in words) / word_count, 4) if word_count else 0.0

    letters = [c for c in msg if c.isalpha()]
    uppercase_ratio = round(sum(1 for c in letters if c.isupper()) / len(letters), 4) if letters else 0.0

    return {
        "word_count": word_count,
        "sentence_count": sentence_count,
        "avg_word_length": avg_word_length,
        "char_count": char_count,
        "question_count": msg.count("?"),
        "exclamation_count": msg.count("!"),
        "uppercase_ratio": uppercase_ratio,
        "has_numbers": int(bool(re.search(r"\d", msg))),
        "paragraph_count": paragraph_count,
    }


def _intent_features(text_lower: str) -> dict:
    return {
        "urgency_score": _keyword_score(text_lower, URGENCY_WORDS),
        "budget_score": _keyword_score(text_lower, BUDGET_WORDS),
        "decision_score": _keyword_score(text_lower, DECISION_WORDS),
        "purchase_ready_score": _keyword_score(text_lower, PURCHASE_READY_WORDS),
        "problem_awareness_score": _keyword_score(text_lower, PROBLEM_AWARENESS_WORDS),
        "competitor_mentioned": int(_count_keyword_hits(text_lower, COMPETITOR_WORDS) > 0),
    }


def _contact_features(phone, company, email) -> dict:
    has_phone = int(bool(phone) and str(phone).strip() != "")
    has_company = int(bool(company) and str(company).strip() != "")

    if email and str(email).strip():
        email_lower = str(email).lower()
        is_pro = int(not any(dom in email_lower for dom in PERSONAL_EMAIL_DOMAINS))
    else:
        is_pro = 0

    if phone and str(phone).strip():
        digits = re.sub(r"[^\d+]", "", str(phone))
        phone_is_tunisian = int(digits.startswith("+216") or digits.startswith("216"))
    else:
        phone_is_tunisian = 0

    return {
        "has_phone": has_phone,
        "has_company": has_company,
        "email_is_professional": is_pro,
        "phone_is_tunisian": phone_is_tunisian,
    }


def _temporal_features(created_at) -> dict:
    dt = _parse_datetime(created_at)
    if dt is None:
        # Pas de date disponible -> valeurs neutres
        return {
            "hour_submitted": -1,
            "day_of_week": -1,
            "is_business_hours": 0,
            "is_morning": 0,
            "is_afternoon": 0,
            "is_weekend": 0,
            "month": -1,
        }
    hour = dt.hour
    dow = dt.weekday()  # 0 = lundi ... 6 = dimanche
    is_weekend = int(dow >= 5)
    is_business_hours = int(dow < 5 and 8 <= hour < 18)
    return {
        "hour_submitted": hour,
        "day_of_week": dow,
        "is_business_hours": is_business_hours,
        "is_morning": int(8 <= hour < 12),
        "is_afternoon": int(12 <= hour < 18),
        "is_weekend": is_weekend,
        "month": dt.month,
    }


def _sentiment_features(message: str, text_lower: str) -> dict:
    """
    Polarité = moyenne (TextBlob, lexique FR maison). TextBlob est faible en
    français ; le lexique FR maison stabilise le signal (choix validé #3).
    """
    tb_polarity = 0.0
    subjectivity = 0.0
    if _TEXTBLOB_OK and message and message.strip():
        try:
            blob = TextBlob(message)
            tb_polarity = float(blob.sentiment.polarity)
            subjectivity = float(blob.sentiment.subjectivity)
        except Exception:
            tb_polarity, subjectivity = 0.0, 0.0

    fr_polarity = _fr_lexicon_polarity(text_lower)
    # Blend : si TextBlob est neutre (FR mal géré), le lexique FR domine
    polarity = round((tb_polarity + fr_polarity) / 2.0, 4)

    return {
        "sentiment_polarity": polarity,
        "sentiment_subjectivity": round(subjectivity, 4),
        "sentiment_positive": int(polarity > 0.1),
        "sentiment_negative": int(polarity < -0.1),
        "sentiment_neutral": int(-0.1 <= polarity <= 0.1),
    }


def _intent_signal_features(message: str, text_lower: str) -> dict:
    """Signaux d'achat explicites : 8 binaires + 1 score de spécificité (0..3).

    Contribution QUICK FIX ML : détecter directement dans le texte les vrais
    signaux d'achat (budget, urgence, signature, devis...) que le modèle ignorait.
    """
    has_number = bool(re.search(r"\d", message))
    letters = [c for c in message if c.isalpha()]
    upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters) if letters else 0.0
    sentences = [p for p in re.split(r"[.!?]", message) if p.strip()]
    is_pro = int(
        bool(sentences)
        and message.strip().endswith((".", "!", "?"))
        and upper_ratio < 0.3
    )
    specificity = (
        int(has_number)
        + int(bool(_DATE_RE.search(text_lower)))
        + int(bool(re.search(r"\b[A-Z][a-zà-ÿ]{2,}", message)))
    )
    return {
        "has_budget_mention": int(any(k in text_lower for k in BUDGET_MENTION_WORDS) and has_number),
        "has_urgency_signal": int(any(k in text_lower for k in URGENCY_SIGNAL_WORDS)),
        "has_signature_intent": int(any(k in text_lower for k in SIGNATURE_INTENT_WORDS)),
        "has_quote_request": int(any(k in text_lower for k in QUOTE_REQUEST_WORDS)),
        "has_company_identifier": int(any(k in text_lower for k in COMPANY_IDENTIFIER_WORDS)),
        "has_decision_maker": int(any(k in text_lower for k in DECISION_MAKER_WORDS)),
        "is_professional_tone": is_pro,
        "has_contact_info": int(bool(_CONTACT_INFO_RE.search(message))),
        "message_specificity": specificity,
    }


# --------------------------------------------------------------------------- #
# FONCTION PRINCIPALE
# --------------------------------------------------------------------------- #

def extract_nlp_features(
    message: str,
    phone: str | None = None,
    company: str | None = None,
    email: str | None = None,
    created_at=None,
) -> dict:
    """Retourne un dict de toutes les features NLP extraites du message."""
    message = message or ""
    text_lower = message.lower()

    features: dict = {}
    features.update(_structural_features(message))
    features.update(_intent_features(text_lower))
    features.update(_contact_features(phone, company, email))
    features.update(_temporal_features(created_at))
    features.update(_sentiment_features(message, text_lower))
    features.update(_intent_signal_features(message, text_lower))
    return features


# Liste ordonnée des noms de features NLP (utile au pipeline / serving)
NLP_FEATURE_NAMES: list[str] = [
    # structurelles
    "word_count", "sentence_count", "avg_word_length", "char_count",
    "question_count", "exclamation_count", "uppercase_ratio", "has_numbers",
    "paragraph_count",
    # intention
    "urgency_score", "budget_score", "decision_score", "purchase_ready_score",
    "problem_awareness_score", "competitor_mentioned",
    # contact
    "has_phone", "has_company", "email_is_professional", "phone_is_tunisian",
    # temporelles
    "hour_submitted", "day_of_week", "is_business_hours", "is_morning",
    "is_afternoon", "is_weekend", "month",
    # sentiment
    "sentiment_polarity", "sentiment_subjectivity", "sentiment_positive",
    "sentiment_negative", "sentiment_neutral",
    # signaux d'achat (QUICK FIX ML)
    "has_budget_mention", "has_urgency_signal", "has_signature_intent",
    "has_quote_request", "has_company_identifier", "has_decision_maker",
    "is_professional_tone", "has_contact_info", "message_specificity",
]


if __name__ == "__main__":
    test_msg = (
        "Bonjour, nous sommes une PME tunisienne "
        "de distribution. Notre équipe de 20 "
        "commerciaux perd beaucoup d'opportunités "
        "faute de suivi. Nous avons un budget de "
        "10 000 TND et souhaitons démarrer "
        "rapidement. Pouvez-vous nous envoyer "
        "un devis urgent ?"
    )
    features = extract_nlp_features(
        message=test_msg,
        phone="+21612345678",
        company="TechCo Tunisia",
        email="contact@techco.tn",
        created_at=datetime(2026, 6, 17, 10, 30),
    )
    print(f"Nombre de features : {len(features)}\n")
    for k, v in features.items():
        print(f"  {k:35} = {v}")
