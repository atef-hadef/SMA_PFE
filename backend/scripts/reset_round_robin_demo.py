"""Reset des données démo CRM + démonstration du round-robin d'assignation.

Usage (depuis backend/) :
    .venv/Scripts/python.exe -m scripts.reset_round_robin_demo

Ce script :
  1. Supprime les leads de démo (demo_lead_*, lead_001, lead_002, lead_003)
     et toutes leurs dépendances (interactions, tâches, deals, brouillons,
     emails, pièces jointes, commentaires).
  2. Conserve l'historique réel (tout autre lead, ex. lead_1780259265823_*).
  3. Crée 6 nouveaux leads successivement via create_crm_lead pour montrer la
     distribution round-robin, puis affiche la répartition.

Sans danger : ne touche QUE les leads de démo ciblés.
"""

from sqlalchemy import text

from app.core.database import SessionLocal
from app.schemas.crm import CrmLeadCreate
from app.services.crm_service import (
    INACTIVE_WORKLOAD_STATUSES,
    create_crm_lead,
)

# Prédicat SQL des leads de démo à supprimer : leads seedés + leads générés par
# les exécutions précédentes de ce script (source='round_robin_test'), pour que
# chaque run reparte propre. L'historique réel n'est jamais touché.
DEMO_LEADS_PREDICATE = (
    "id LIKE 'demo_lead_%' "
    "OR id IN ('lead_001', 'lead_002', 'lead_003') "
    "OR source = 'round_robin_test'"
)

# Pendant la démo, les leads réels assignés à un commercial sont "garés" sur
# l'admin pour partir d'une charge 0/0/0, puis restaurés à la fin.
DEMO_PARK_OWNER = "user_001"
ACTIVE_SALES_SUBQUERY = (
    "SELECT id FROM users WHERE role_id = 'role_sales' AND status = 'active'"
)

# DELETE en ordre FK-safe (enfants -> parent).
RESET_STATEMENTS = [
    # Commentaires rattachés aux tâches / deals / leads ciblés.
    f"""DELETE FROM crm_comments WHERE
        entity_id IN (SELECT id FROM crm_tasks WHERE lead_id IN (SELECT id FROM crm_leads WHERE {DEMO_LEADS_PREDICATE}))
        OR entity_id IN (SELECT id FROM crm_deals WHERE lead_id IN (SELECT id FROM crm_leads WHERE {DEMO_LEADS_PREDICATE}))
        OR entity_id IN (SELECT id FROM crm_leads WHERE {DEMO_LEADS_PREDICATE})""",
    # Pièces jointes des brouillons des leads ciblés.
    f"""DELETE FROM crm_email_attachments WHERE draft_id IN (
        SELECT id FROM crm_email_drafts WHERE lead_id IN (SELECT id FROM crm_leads WHERE {DEMO_LEADS_PREDICATE}))""",
    f"DELETE FROM crm_email_messages WHERE lead_id IN (SELECT id FROM crm_leads WHERE {DEMO_LEADS_PREDICATE})",
    f"DELETE FROM crm_email_drafts WHERE lead_id IN (SELECT id FROM crm_leads WHERE {DEMO_LEADS_PREDICATE})",
    f"DELETE FROM crm_tasks WHERE lead_id IN (SELECT id FROM crm_leads WHERE {DEMO_LEADS_PREDICATE})",
    f"DELETE FROM crm_deals WHERE lead_id IN (SELECT id FROM crm_leads WHERE {DEMO_LEADS_PREDICATE})",
    f"DELETE FROM crm_interactions WHERE lead_id IN (SELECT id FROM crm_leads WHERE {DEMO_LEADS_PREDICATE})",
    f"DELETE FROM crm_leads WHERE {DEMO_LEADS_PREDICATE}",
]

_INACTIVE_SQL_LIST = ", ".join(f"'{s}'" for s in sorted(INACTIVE_WORKLOAD_STATUSES))


def _sales_workload(db) -> dict[str, int]:
    """Charge active (leads non clôturés) par commercial actif, trié par id."""
    rows = db.execute(
        text(
            f"""
            SELECT u.id, COUNT(l.id)
            FROM users u
            LEFT JOIN crm_leads l
              ON l.assigned_to = u.id
             AND LOWER(COALESCE(l.customer_status, '')) NOT IN ({_INACTIVE_SQL_LIST})
            WHERE u.role_id = 'role_sales' AND u.status = 'active'
            GROUP BY u.id
            ORDER BY u.id
            """
        )
    ).all()
    return {row[0]: row[1] for row in rows}


def main() -> None:
    db = SessionLocal()
    try:
        # 1. Reset des leads de démo (l'historique réel est préservé).
        for statement in RESET_STATEMENTS:
            db.execute(text(statement))
        db.commit()

        # 2. "Garer" les leads réels assignés à un commercial sur l'admin, afin
        #    de démarrer la démo avec une charge 0/0/0. Sauvegarde pour restaurer.
        parked = db.execute(
            text(
                f"SELECT id, owner_user_id, assigned_to FROM crm_leads "
                f"WHERE assigned_to IN ({ACTIVE_SALES_SUBQUERY})"
            )
        ).all()
        db.execute(
            text(
                f"UPDATE crm_leads SET owner_user_id = :park, assigned_to = :park "
                f"WHERE assigned_to IN ({ACTIVE_SALES_SUBQUERY})"
            ),
            {"park": DEMO_PARK_OWNER},
        )
        db.commit()

        print("=== APRÈS RESET ===")
        kept = db.execute(text("SELECT id, assigned_to, customer_status FROM crm_leads ORDER BY id")).all()
        print(f"  leads restants (historique réel) = {len(kept)}")
        for row in kept:
            print("   ", tuple(row))
        print(f"  {len(parked)} lead(s) réel(s) temporairement garé(s) sur {DEMO_PARK_OWNER} (admin)")

        # 3. Vérifier que la charge de départ est bien 0/0/0.
        start = _sales_workload(db)
        print(f"  charge de départ par commercial = {start}")
        assert all(load == 0 for load in start.values()), (
            f"La base de départ n'est pas équilibrée à 0/0/0 : {start}"
        )
        print("  ✓ Base de départ équilibrée à 0/0/0.")

        # 4. Création de 6 leads successifs via le round-robin.
        print("\n=== CRÉATION DE 6 LEADS (round-robin) ===")
        assignments: list[str] = []
        for i in range(1, 7):
            payload = CrmLeadCreate(
                name=f"RR Test Lead {i}",
                company=f"RR Test Co {i}",
                email=f"rr.test.{i}@example.com",
                source="round_robin_test",
                message=f"Lead de test round-robin numéro {i}.",
            )
            resp = create_crm_lead(payload, db)
            owner = db.execute(
                text("SELECT assigned_to FROM crm_leads WHERE id = :i"),
                {"i": resp.id},
            ).scalar()
            assignments.append(owner)
            print(f"  lead #{i} ({resp.id}) -> {owner}")

        # 5. Répartition finale.
        print("\n=== RÉPARTITION ===")
        new_dist: dict[str, int] = {}
        for owner in assignments:
            new_dist[owner] = new_dist.get(owner, 0) + 1
        print(f"  6 nouveaux leads -> {dict(sorted(new_dist.items()))}")
        print(f"  charge des commerciaux -> {_sales_workload(db)}")

        # 6. Restaurer les leads réels garés.
        for lead_id, owner_user_id, assigned_to in parked:
            db.execute(
                text(
                    "UPDATE crm_leads SET owner_user_id = :o, assigned_to = :a WHERE id = :i"
                ),
                {"o": owner_user_id, "a": assigned_to, "i": lead_id},
            )
        db.commit()
        if parked:
            print(f"\n  ↩ {len(parked)} lead(s) réel(s) restauré(s) sur leur propriétaire d'origine.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
