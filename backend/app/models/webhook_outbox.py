from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class WebhookOutbox(Base):
    """Durable outbox for outbound webhook calls to n8n.

    Each row is one logical webhook attempt. The synchronous path writes a row
    before posting; on failure the cron worker re-tries via process_pending.
    Status lifecycle: pending -> sending -> sent | failed (+ next_retry_at) -> dead.
    """

    __tablename__ = "webhook_outbox"
    __table_args__ = (
        Index("ix_webhook_outbox_status_retry", "status", "next_retry_at"),
        Index(
            "ix_webhook_outbox_related",
            "related_object_type",
            "related_object_id",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    webhook_url: Mapped[str] = mapped_column(String(512), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    related_object_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    related_object_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    workflow_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
