from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CrmEmailDraft(Base):
    __tablename__ = "crm_email_drafts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    lead_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("crm_leads.id"),
        nullable=False,
    )
    deal_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("crm_deals.id", ondelete="SET NULL"),
        nullable=True,
    )
    draft_type: Mapped[str] = mapped_column(String(40), nullable=False)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="draft_generated")
    tone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    cta: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_by_agent: Mapped[str | None] = mapped_column(String(160), nullable=True)
    edited_by: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id"), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id"), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id"), nullable=True)
    rejected_by: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id"), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
