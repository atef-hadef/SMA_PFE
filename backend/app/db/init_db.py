from app.core.database import engine
from app.models import Base


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)
