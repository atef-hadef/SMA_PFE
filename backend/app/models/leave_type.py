from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class LeaveType(Base):
    __tablename__ = "leave_types"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    label_fr: Mapped[str] = mapped_column(String(120), nullable=False)
    label_en: Mapped[str | None] = mapped_column(String(120), nullable=True)
    default_days: Mapped[int] = mapped_column(Integer, default=0)
    requires_document: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
