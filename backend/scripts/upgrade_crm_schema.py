import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import engine


CRM_LEAD_COLUMN_UPGRADES = [
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS customer_status VARCHAR(40) DEFAULT 'lead'",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS last_contact_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS next_action TEXT",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS product_service VARCHAR(160)",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS estimated_value NUMERIC(12, 2)",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS priority VARCHAR(40)",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS customer_category VARCHAR(40)",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS location VARCHAR(160)",
    "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE",
]

CREATE_CRM_INTERACTIONS_TABLE = """
CREATE TABLE IF NOT EXISTS crm_interactions (
    id VARCHAR(64) PRIMARY KEY,
    lead_id VARCHAR(64) NOT NULL REFERENCES crm_leads(id),
    interaction_type VARCHAR(80) NOT NULL,
    channel VARCHAR(80),
    summary TEXT NOT NULL,
    interaction_date TIMESTAMP WITH TIME ZONE NOT NULL,
    created_by VARCHAR(64) REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
)
"""


def upgrade_crm_schema() -> None:
    with engine.begin() as connection:
        for statement in CRM_LEAD_COLUMN_UPGRADES:
            connection.execute(text(statement))

        connection.execute(text(CREATE_CRM_INTERACTIONS_TABLE))


if __name__ == "__main__":
    upgrade_crm_schema()
    print("CRM schema upgraded successfully.")
