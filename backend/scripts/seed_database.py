import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.seed_db import seed_database


if __name__ == "__main__":
    seed_database()
    print("Database seeded successfully.")
