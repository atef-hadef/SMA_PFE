import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import engine


LEAVE_REQUEST_COLUMN_UPGRADES = [
    "ALTER TABLE leave_requests ADD COLUMN IF NOT EXISTS odoo_leave_id VARCHAR(64)",
    "ALTER TABLE leave_requests ADD COLUMN IF NOT EXISTS odoo_state VARCHAR(40)",
    (
        "ALTER TABLE leave_requests ADD COLUMN IF NOT EXISTS "
        "odoo_sync_status VARCHAR(40) DEFAULT 'pending'"
    ),
    (
        "ALTER TABLE leave_requests ADD COLUMN IF NOT EXISTS "
        "automation_recommendation VARCHAR(120)"
    ),
    "ALTER TABLE leave_requests ADD COLUMN IF NOT EXISTS automation_summary TEXT",
    "ALTER TABLE leave_requests ADD COLUMN IF NOT EXISTS score INTEGER",
    "ALTER TABLE leave_requests ADD COLUMN IF NOT EXISTS available_days NUMERIC(8, 2)",
    "ALTER TABLE leave_requests ADD COLUMN IF NOT EXISTS requested_days NUMERIC(8, 2)",
]


def upgrade_leave_schema() -> None:
    with engine.begin() as connection:
        for statement in LEAVE_REQUEST_COLUMN_UPGRADES:
            connection.execute(text(statement))


if __name__ == "__main__":
    upgrade_leave_schema()
    print("Leave request schema upgraded successfully.")
