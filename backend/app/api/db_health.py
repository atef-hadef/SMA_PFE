from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.schemas.common import ApiResponse

router = APIRouter()


@router.get("/health/db", response_model=ApiResponse[dict[str, str]])
def get_database_health() -> ApiResponse[dict[str, str]]:
    db: Session = SessionLocal()

    try:
        database = db.execute(text("SELECT current_database();")).scalar_one()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="Database connection failed.",
        ) from exc
    finally:
        db.close()

    return ApiResponse(
        success=True,
        data={
            "status": "ok",
            "database": str(database),
            "message": "Database connection successful",
        },
    )
