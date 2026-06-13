"""seed_demo_leads.py — Jeu de données de démonstration complet (réversible).

Insère un jeu de données fictif et varié pour exercer **tous les domaines** de
l'assistant IA FlowPilot, afin que chaque intention renvoie un dashboard riche :

  1. CRM (~18 leads)           → résumé, priorités, statuts, conversion, valeur,
                                  relances, comparaison hebdomadaire.
  2. Brouillons d'e-mail (~8)  → intention `crm_draft_review_summary`
                                  (en attente / approuvés / envoyés / rejetés).
  3. Congés / RH (~11)         → toutes les intentions Congés : en attente,
                                  approuvées, refusées, bloquées par politique RH
                                  (solde insuffisant + chevauchement de dates).
  4. Automatisations n8n (~11) → intention `automation_health`
                                  (succès / échecs / en attente).

Toutes les lignes utilisent un identifiant préfixé (``demo_lead_``, ``demo_draft_``,
``demo_leave_``, ``demo_wf_``) afin de pouvoir être supprimées proprement après la
démo, **sans toucher aux vraies données**.

Utilisation (depuis le dossier backend/) :
    python seed_demo_leads.py seed      # insère tout le jeu de démo
    python seed_demo_leads.py clear     # supprime UNIQUEMENT les données de démo
    python seed_demo_leads.py status    # affiche la répartition des données de démo
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import delete, func, select

from app.core.database import SessionLocal
from app.models import CrmEmailDraft, CrmLead, LeaveRequest, WorkflowExecution

try:  # owner is optional — assign an existing user if there is one
    from app.models import User
except Exception:  # pragma: no cover - defensive
    User = None  # type: ignore[assignment]


LEAD_PREFIX = "demo_lead_"
DRAFT_PREFIX = "demo_draft_"
LEAVE_PREFIX = "demo_leave_"
WF_PREFIX = "demo_wf_"

# Backwards-compat alias (older docs referenced DEMO_PREFIX for leads).
DEMO_PREFIX = LEAD_PREFIX


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ===========================================================================
# 1. CRM LEADS
# (contact, company, status, score, priority, customer_status, value, days_ago,
#  source, location, next_action)
# ===========================================================================
DEMO_LEADS: list[tuple[str, str, str, int, str, str, int, int, str, str, str]] = [
    # ---- Cette semaine (J-1 à J-6) : 7 leads ----
    ("Sami Trabelsi", "TechNova Solutions", "hot", 96, "high", "prospect", 24000, 1, "web", "Tunis", "Planifier une démo produit"),
    ("Leïla Gharbi", "Carthage Bank", "hot", 91, "high", "prospect", 40000, 2, "referral", "Tunis", "Envoyer la proposition commerciale"),
    ("Karim Najjar", "BlueWave Shipping", "warm", 74, "medium", "lead", 12000, 2, "email", "Sfax", "Relancer après l'envoi du comparatif"),
    ("Nadia Belhadj", "MedTrust Clinics", "hot", 88, "high", "customer", 31000, 3, "web", "Sousse", "Préparer le renouvellement annuel"),
    ("Yassine Khelifi", "Nexus Telecom", "warm", 67, "medium", "lead", 9000, 4, "event", "Tunis", "Programmer un appel de découverte"),
    ("Imen Saidi", "Olive&Co Foods", "cold", 42, "low", "lead", 3000, 5, "email", "Bizerte", "Ajouter à la campagne de nurturing"),
    ("Walid Mansour", "Sahel Energy", "warm", 71, "medium", "prospect", 18000, 6, "referral", "Gabès", "Envoyer l'étude de cas énergie"),
    # ---- Semaine précédente (J-8 à J-13) : 5 leads ----
    ("Rania Feki", "Atlas Insurance", "hot", 84, "high", "prospect", 22000, 8, "web", "Tunis", "Confirmer le périmètre du contrat"),
    ("Mohamed Aziz", "Phoenix Retail", "cold", 38, "low", "lead", 2500, 9, "email", "Sfax", "Qualifier le besoin réel"),
    ("Sonia Bouzid", "Zenith Software", "warm", 63, "medium", "lead", 11000, 10, "web", "Tunis", "Partager la grille tarifaire"),
    ("Hatem Dridi", "Delice Dairy", "cold", 49, "low", "lead", 4000, 11, "email", "Sidi Bouzid", "Recontacter au prochain trimestre"),
    ("Amira Jelassi", "Oasis Travel", "hot", 80, "high", "customer", 16000, 13, "referral", "Djerba", "Onboarding du nouveau client"),
    # ---- Il y a deux semaines (J-15 à J-20) : 6 leads ----
    ("Fares Hammami", "Falcon Security", "warm", 69, "medium", "prospect", 14000, 15, "web", "Tunis", "Envoyer le devis sécurité"),
    ("Olfa Chaabane", "Cedar Construction", "cold", 35, "low", "lead", 5000, 16, "email", "Kairouan", "Évaluer la maturité du projet"),
    ("Bilel Ayari", "Lumina Media", "warm", 58, "medium", "lead", 6500, 17, "event", "Tunis", "Proposer un atelier de cadrage"),
    ("Hela Mejri", "Sirius Logistics", "hot", 93, "high", "prospect", 28000, 18, "referral", "Radès", "Négocier les volumes annuels"),
    ("Anis Bouaziz", "Amber Pharma", "cold", 31, "low", "lead", 2000, 19, "email", "Monastir", "Vérifier le budget disponible"),
    ("Maha Zouari", "Sahara Foods", "warm", 77, "medium", "customer", 20000, 20, "web", "Médenine", "Planifier la revue trimestrielle"),
]

_SENTIMENT = {"hot": "positive", "warm": "neutral", "cold": "neutral"}
_URGENCY = {"hot": "high", "warm": "medium", "cold": "low"}
_CATEGORY = {"hot": "VIP", "warm": "standard", "cold": "new"}


# ===========================================================================
# 2. CRM EMAIL DRAFTS (référencent les leads de démo ci-dessus)
# (lead_index, draft_type, status, days_ago, subject)
#   status ∈ draft_generated / edited / reviewed (en attente)
#            | approved | sent | rejected
# ===========================================================================
DEMO_DRAFTS: list[tuple[int, str, str, int, str]] = [
    (1, "followup", "draft_generated", 1, "Suite à notre échange — démo produit TechNova"),
    (2, "proposal", "draft_generated", 1, "Votre proposition commerciale — Carthage Bank"),
    (3, "followup", "edited", 2, "Relance comparatif — BlueWave Shipping"),
    (8, "introduction", "reviewed", 3, "Présentation FlowPilot — Atlas Insurance"),
    (4, "reminder", "approved", 4, "Rappel renouvellement annuel — MedTrust Clinics"),
    (12, "introduction", "sent", 6, "Bienvenue chez FlowPilot — Oasis Travel"),
    (7, "followup", "sent", 7, "Étude de cas énergie — Sahel Energy"),
    (9, "followup", "rejected", 9, "Reprise de contact — Phoenix Retail"),
]


# ===========================================================================
# 3. LEAVE REQUESTS
# (user_pref, leave_type, start_offset, duration_days, status, days_ago,
#  available_days, requested_days, recommendation, summary, reason)
#   start_offset : nb de jours par rapport à aujourd'hui (futur si > 0)
# ===========================================================================
DEMO_LEAVES: list[tuple[str, str, int, int, str, int, object, object, object, object, str]] = [
    # ---- En attente d'une décision manager (3) ----
    ("user_010", "Congé annuel", 10, 5, "pending", 1, Decimal("18.0"), Decimal("5.0"), "manager_review", None, "Vacances en famille"),
    ("user_030", "Congé annuel", 21, 10, "manager_review_required", 2, Decimal("12.0"), Decimal("10.0"), "manager_review", "Durée supérieure à 7 jours : validation manager requise.", "Voyage à l'étranger"),
    ("user_010", "Congé sans solde", 30, 3, "pending", 3, Decimal("0.0"), Decimal("3.0"), "manager_review", None, "Raisons personnelles"),
    # ---- Approuvées (3) ----
    ("user_030", "Congé maladie", -5, 2, "approved", 7, Decimal("15.0"), Decimal("2.0"), "auto_approve", "Solde suffisant, aucune règle déclenchée.", "Certificat médical fourni"),
    ("user_010", "Congé annuel", -12, 4, "approved", 14, Decimal("20.0"), Decimal("4.0"), "auto_approve", "Solde suffisant, aucun chevauchement.", "Pont de mai"),
    ("user_040", "Congé annuel", -20, 1, "approved", 22, Decimal("9.0"), Decimal("1.0"), "auto_approve", "Demande courte, validée automatiquement.", "Rendez-vous administratif"),
    # ---- Refusée par le manager (1) ----
    ("user_010", "Congé annuel", 5, 6, "rejected", 4, Decimal("8.0"), Decimal("6.0"), "manager_review", "Refusée par le manager : période de forte activité.", "Vacances anticipées"),
    # ---- Bloquée par politique RH — solde insuffisant (2) ----
    ("user_030", "Congé annuel", 14, 12, "rejected_by_policy", 5, Decimal("6.0"), Decimal("12.0"), "rejected_by_policy", "Solde insuffisant : 12 jours demandés pour 6 jours disponibles.", "Long voyage prévu"),
    ("user_010", "Congé annuel", 40, 9, "rejected_by_policy", 6, Decimal("3.5"), Decimal("9.0"), "rejected_by_policy", "Solde insuffisant : 9 jours demandés pour 3,5 jours disponibles.", "Congés d'été"),
    # ---- Bloquée par politique RH — chevauchement de dates (2) ----
    ("user_030", "Congé annuel", 8, 4, "rejected_by_policy", 5, Decimal("14.0"), Decimal("4.0"), "rejected_by_policy", "Chevauchement détecté avec une absence déjà approuvée sur la même équipe.", "Pont de juin"),
    ("user_010", "Congé annuel", 12, 3, "rejected_by_policy", 8, Decimal("10.0"), Decimal("3.0"), "rejected_by_policy", "Chevauchement de dates avec un collègue du même service.", "Week-end prolongé"),
]


# ===========================================================================
# 4. WORKFLOW EXECUTIONS (n8n) — santé des automatisations
# (workflow_name, process, status, days_ago, duration_s, error_message)
#   status ∈ success / completed | failed / error | running / queued / pending
# ===========================================================================
DEMO_WORKFLOWS: list[tuple[str, str, str, int, object, object]] = [
    ("CRM - Génération brouillon e-mail", "crm", "success", 1, 4, None),
    ("CRM - Scoring des leads", "crm", "success", 1, 7, None),
    ("Congés - Pré-validation solde", "leave", "success", 2, 3, None),
    ("Congés - Synchronisation Odoo", "leave", "completed", 2, 12, None),
    ("CRM - Enrichissement société", "crm", "success", 3, 9, None),
    ("CRM - Envoi e-mail approuvé", "crm", "failed", 1, 6, "SMTP timeout : serveur de messagerie injoignable."),
    ("Congés - Notification manager", "leave", "failed", 2, 2, "Webhook 500 : endpoint manager indisponible."),
    ("CRM - Import leads CSV", "crm", "error", 4, None, "Format de fichier invalide : colonne 'email' manquante."),
    ("CRM - Génération brouillon e-mail", "crm", "running", 0, None, None),
    ("Congés - Pré-validation solde", "leave", "queued", 0, None, None),
    ("CRM - Scoring des leads", "crm", "pending", 0, None, None),
]


def _slug(company: str) -> str:
    first = company.split()[0].lower()
    return "".join(ch for ch in first if ch.isalnum()) or "lead"


def _pick_owner(db) -> str | None:
    if User is None:
        return None
    try:
        return db.scalar(select(User.id).limit(1))
    except Exception:
        return None


def _existing_user(db, preferred: str) -> str | None:
    """Return ``preferred`` if that user exists, else any existing user id."""
    if User is None:
        return None
    try:
        if db.get(User, preferred) is not None:
            return preferred
        return db.scalar(select(User.id).limit(1))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Seeders (one per domain) — all idempotent
# ---------------------------------------------------------------------------

def _seed_leads(db) -> int:
    owner = _pick_owner(db)
    created = 0
    for index, row in enumerate(DEMO_LEADS, start=1):
        lead_id = f"{LEAD_PREFIX}{index:03d}"
        if db.get(CrmLead, lead_id) is not None:
            continue  # idempotent
        (contact, company, status, score, priority, customer_status,
         value, days_ago, source, location, next_action) = row
        created_at = _now() - timedelta(days=days_ago, hours=index % 9)
        db.add(
            CrmLead(
                id=lead_id,
                full_name=contact,
                company_name=company,
                email=f"contact@{_slug(company)}.tn",
                phone=None,
                source=source,
                status=status,
                customer_status=customer_status,
                lead_score=score,
                sentiment=_SENTIMENT[status],
                urgency=_URGENCY[status],
                intention=None,
                message=None,
                ai_summary=f"Lead de démonstration ({status}) — score {score}/100.",
                recommended_action=next_action,
                last_contact_at=created_at + timedelta(days=1),
                next_action=next_action,
                product_service="Automatisation FlowPilot",
                estimated_value=Decimal(value),
                priority=priority,
                customer_category=_CATEGORY[status],
                location=location,
                is_active=True,
                owner_user_id=owner,
                assigned_to=owner,
                notes="Donnée de démonstration — supprimable via 'python seed_demo_leads.py clear'.",
                created_at=created_at,
                updated_at=created_at,
            )
        )
        created += 1
    return created


def _seed_drafts(db) -> int:
    created = 0
    for index, row in enumerate(DEMO_DRAFTS, start=1):
        draft_id = f"{DRAFT_PREFIX}{index:03d}"
        if db.get(CrmEmailDraft, draft_id) is not None:
            continue  # idempotent
        lead_index, draft_type, status, days_ago, subject = row
        lead_id = f"{LEAD_PREFIX}{lead_index:03d}"
        if db.get(CrmLead, lead_id) is None:
            continue  # the referenced demo lead is not present — skip safely
        created_at = _now() - timedelta(days=days_ago, hours=index % 5)
        db.add(
            CrmEmailDraft(
                id=draft_id,
                lead_id=lead_id,
                draft_type=draft_type,
                subject=subject,
                body=(
                    "Bonjour,\n\nCeci est un brouillon de démonstration généré par "
                    "l'assistant FlowPilot pour illustrer le flux de validation.\n\n"
                    "Cordialement,\nL'équipe commerciale"
                ),
                status=status,
                tone="professionnel",
                cta="Planifier un échange",
                generated_by_agent="demo-seed",
                created_at=created_at,
                updated_at=created_at,
                sent_at=(created_at + timedelta(hours=2)) if status == "sent" else None,
            )
        )
        created += 1
    return created


def _seed_leaves(db) -> int:
    manager = _existing_user(db, "user_020")
    created = 0
    for index, row in enumerate(DEMO_LEAVES, start=1):
        leave_id = f"{LEAVE_PREFIX}{index:03d}"
        if db.get(LeaveRequest, leave_id) is not None:
            continue  # idempotent
        (user_pref, leave_type, start_offset, duration, status, days_ago,
         available, requested, recommendation, summary, reason) = row
        user_id = _existing_user(db, user_pref)
        if user_id is None:
            continue  # no user to attach the request to — skip safely
        created_at = _now() - timedelta(days=days_ago, hours=index % 7)
        start = date.today() + timedelta(days=start_offset)
        end = start + timedelta(days=duration)
        decided = status in ("approved", "rejected", "rejected_by_policy")
        db.add(
            LeaveRequest(
                id=leave_id,
                user_id=user_id,
                leave_type=leave_type,
                start_date=start,
                end_date=end,
                reason=reason,
                status=status,
                automation_recommendation=recommendation,
                automation_summary=summary,
                score=None,
                available_days=available,
                requested_days=requested,
                reviewed_by=manager if status in ("approved", "rejected") else None,
                reviewed_at=(created_at + timedelta(hours=6)) if decided else None,
                decision_comment=summary if status == "rejected" else None,
                created_at=created_at,
                updated_at=created_at + (timedelta(hours=6) if decided else timedelta()),
            )
        )
        created += 1
    return created


def _seed_workflows(db) -> int:
    created = 0
    for index, row in enumerate(DEMO_WORKFLOWS, start=1):
        wf_id = f"{WF_PREFIX}{index:03d}"
        if db.get(WorkflowExecution, wf_id) is not None:
            continue  # idempotent
        workflow_name, process, status, days_ago, duration, error_message = row
        created_at = _now() - timedelta(days=days_ago, hours=index % 6)
        finished = status in ("success", "completed", "failed", "error")
        db.add(
            WorkflowExecution(
                id=wf_id,
                related_object_type=process,
                related_object_id=None,
                workflow_name=workflow_name,
                process=process,
                trigger_source="demo-seed",
                status=status,
                started_at=created_at,
                finished_at=(created_at + timedelta(seconds=duration or 0)) if finished else None,
                duration_seconds=duration,
                error_message=error_message,
                result_summary=("Exécution terminée avec succès." if status in ("success", "completed") else None),
                input_summary=None,
                output_summary=None,
                agent_name="demo-seed",
                created_at=created_at,
                updated_at=created_at,
            )
        )
        created += 1
    return created


def seed() -> None:
    db = SessionLocal()
    try:
        leads = _seed_leads(db)
        db.commit()  # commit leads first so drafts can reference them
        drafts = _seed_drafts(db)
        leaves = _seed_leaves(db)
        workflows = _seed_workflows(db)
        db.commit()
        print(
            "OK : données de démo insérées — "
            f"{leads} lead(s), {drafts} brouillon(s), {leaves} congé(s), {workflows} workflow(s)."
        )
        _print_distribution(db)
    finally:
        db.close()


def clear() -> None:
    db = SessionLocal()
    try:
        # Drafts reference leads → delete drafts first to respect the FK.
        d = db.execute(delete(CrmEmailDraft).where(CrmEmailDraft.id.like(f"{DRAFT_PREFIX}%")))
        l = db.execute(delete(CrmLead).where(CrmLead.id.like(f"{LEAD_PREFIX}%")))
        lv = db.execute(delete(LeaveRequest).where(LeaveRequest.id.like(f"{LEAVE_PREFIX}%")))
        wf = db.execute(delete(WorkflowExecution).where(WorkflowExecution.id.like(f"{WF_PREFIX}%")))
        db.commit()
        print(
            "OK : données de démo supprimées — "
            f"{l.rowcount} lead(s), {d.rowcount} brouillon(s), {lv.rowcount} congé(s), "
            f"{wf.rowcount} workflow(s). Les vraies données sont intactes."
        )
    finally:
        db.close()


def _count_demo(db, model, prefix) -> int:
    return db.scalar(
        select(func.count()).select_from(model).where(model.id.like(f"{prefix}%"))
    ) or 0


def _print_distribution(db) -> None:
    now = _now()
    this_week = db.scalar(
        select(func.count()).select_from(CrmLead).where(
            CrmLead.id.like(f"{LEAD_PREFIX}%"), CrmLead.created_at >= now - timedelta(days=7)
        )
    )
    last_week = db.scalar(
        select(func.count()).select_from(CrmLead).where(
            CrmLead.id.like(f"{LEAD_PREFIX}%"),
            CrmLead.created_at >= now - timedelta(days=14),
            CrmLead.created_at < now - timedelta(days=7),
        )
    )
    print("--- Répartition des données de démo ---")
    print(f"  Leads CRM          : {_count_demo(db, CrmLead, LEAD_PREFIX)}")
    print(f"    · cette semaine  : {this_week or 0}")
    print(f"    · sem. précéd.   : {last_week or 0}")
    print(f"    · variation      : {(this_week or 0) - (last_week or 0):+d}")
    print(f"  Brouillons e-mail  : {_count_demo(db, CrmEmailDraft, DRAFT_PREFIX)}")
    print(f"  Demandes de congé  : {_count_demo(db, LeaveRequest, LEAVE_PREFIX)}")
    print(f"  Workflows n8n      : {_count_demo(db, WorkflowExecution, WF_PREFIX)}")


def status() -> None:
    db = SessionLocal()
    try:
        _print_distribution(db)
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Données de démonstration de l'assistant IA (réversible).")
    parser.add_argument("action", choices=["seed", "clear", "status"], help="Action à exécuter.")
    args = parser.parse_args()
    {"seed": seed, "clear": clear, "status": status}[args.action]()


if __name__ == "__main__":
    main()
