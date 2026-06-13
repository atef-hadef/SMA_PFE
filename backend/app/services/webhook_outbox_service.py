"""Webhook outbox: durable retry queue for outbound webhooks to n8n.

Hybrid pattern used by callers:

    outbox = enqueue(db, url, payload, related_object_type=..., ...)
    try:
        response = sync_attempt(db, outbox)   # ~1s if n8n is up
    except HTTPException:
        # n8n unreachable — outbox row is marked 'failed' with backoff;
        # the cron worker will retry. Callers that have compensation logic
        # (e.g. revert customer_status) can also call mark_dead(outbox) to
        # opt out of the retry once the compensation has run.
        ...
        raise

A periodic POST /api/crm/webhook/process-outbox calls process_pending(db)
to drain stuck rows with exponential backoff. After max_attempts the row is
marked 'dead' and logged at CRITICAL so it surfaces in alerting.
"""

from datetime import datetime, timedelta, timezone
import json
import logging
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import WebhookOutbox

logger = logging.getLogger(__name__)

SYNC_TIMEOUT_SECONDS = 30
# Base for exponential backoff: next_retry_at = now + (2 ** attempts * 60s).
# attempts=1 -> 2 min, =2 -> 4 min, =3 -> 8 min, =4 -> 16 min (capped at 1h).
BACKOFF_BASE_SECONDS = 60
BACKOFF_CAP_SECONDS = 3600


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _compute_next_retry(attempts: int) -> datetime:
    delay = min(BACKOFF_CAP_SECONDS, BACKOFF_BASE_SECONDS * (2 ** max(0, attempts)))
    return _utc_now() + timedelta(seconds=delay)


def enqueue(
    db: Session,
    webhook_url: str,
    payload: dict[str, Any],
    *,
    related_object_type: str | None = None,
    related_object_id: str | None = None,
    workflow_name: str | None = None,
    max_attempts: int = 3,
) -> WebhookOutbox:
    """Persist a pending webhook attempt and commit immediately.

    Committing eagerly is intentional: the row is the audit trail. If the
    enclosing transaction is later rolled back, the outbox still records that
    the call was attempted.
    """
    now = _utc_now()
    row = WebhookOutbox(
        id=f"outbox_{uuid4().hex[:12]}",
        webhook_url=webhook_url[:512],
        payload=payload,
        status="pending",
        attempts=0,
        max_attempts=max(1, max_attempts),
        next_retry_at=None,
        last_error=None,
        related_object_type=related_object_type,
        related_object_id=related_object_id,
        workflow_name=workflow_name,
        created_at=now,
        updated_at=now,
    )

    try:
        db.add(row)
        db.commit()
        db.refresh(row)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Failed to enqueue webhook outbox row.")
        raise HTTPException(
            status_code=500,
            detail="Webhook outbox enqueue failed.",
        ) from exc

    return row


def sync_attempt(db: Session, outbox: WebhookOutbox) -> object:
    """POST the outbox row's payload now. Updates status accordingly.

    Returns the parsed n8n response on success. Raises HTTPException(502) on
    transport failure. On failure the row is marked 'failed' with
    next_retry_at set so the cron worker will pick it up later.
    """
    return _post_outbox(db, outbox, source="sync")


def mark_dead(
    db: Session,
    outbox: WebhookOutbox,
    reason: str,
) -> None:
    """Stop retrying this row. Use after a successful compensation."""
    outbox.status = "dead"
    outbox.next_retry_at = None
    outbox.last_error = (reason or "Marked dead by caller.")[:8000]
    outbox.updated_at = _utc_now()
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Failed to mark webhook outbox row as dead.")


def process_pending(db: Session) -> dict[str, int]:
    """Cron-style entry point — drain ready rows.

    Picks every row with status in {pending, failed} whose next_retry_at is
    NULL (= ready immediately) or in the past. Retries each in order. The
    counts returned are how many transitions happened in THIS run:
      sent: succeeded
      failed: failed but will retry later
      dead: hit max_attempts -> shelved
    """
    now = _utc_now()
    stats = {"sent": 0, "failed": 0, "dead": 0}

    try:
        rows = list(
            db.scalars(
                select(WebhookOutbox)
                .where(WebhookOutbox.status.in_(("pending", "failed")))
                .where(
                    or_(
                        WebhookOutbox.next_retry_at.is_(None),
                        WebhookOutbox.next_retry_at <= now,
                    )
                )
                .order_by(WebhookOutbox.created_at.asc())
            ).all()
        )
    except SQLAlchemyError:
        logger.exception("Failed to load pending outbox rows.")
        return stats

    for row in rows:
        try:
            _post_outbox(db, row, source="cron")
            stats["sent"] += 1
        except HTTPException:
            # _post_outbox already set status to failed or dead and committed.
            db.refresh(row)
            if row.status == "dead":
                stats["dead"] += 1
            else:
                stats["failed"] += 1

    return stats


def _post_outbox(
    db: Session,
    outbox: WebhookOutbox,
    *,
    source: str,
) -> object:
    """Perform the actual HTTP POST and update the row.

    `source` is just for logging ('sync' or 'cron').
    """
    now = _utc_now()
    outbox.status = "sending"
    outbox.attempts += 1
    outbox.updated_at = now
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Could not persist outbox sending state.")

    request_body = json.dumps(outbox.payload).encode("utf-8")
    request = Request(
        outbox.webhook_url,
        data=request_body,
        headers={
            "Content-Type": "application/json",
            "X-FlowPilot-Secret": settings.FLOWPILOT_N8N_SHARED_SECRET,
        },
        method="POST",
    )

    error_message: str | None = None
    try:
        with urlopen(request, timeout=SYNC_TIMEOUT_SECONDS) as response:
            response_text = response.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:400]
        error_message = f"HTTP {exc.code} from n8n: {body}"
    except (TimeoutError, URLError) as exc:
        error_message = f"n8n unreachable: {exc}"
    except Exception as exc:  # noqa: BLE001 - last-resort guard
        error_message = f"Unexpected error posting to n8n: {exc}"

    if error_message is None:
        outbox.status = "sent"
        outbox.next_retry_at = None
        outbox.last_error = None
        outbox.updated_at = _utc_now()
        try:
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            logger.exception("Could not persist outbox sent state.")
        logger.info(
            "Webhook outbox %s sent on attempt %s via %s (workflow=%s).",
            outbox.id,
            outbox.attempts,
            source,
            outbox.workflow_name,
        )
        return _parse_response(response_text)

    # Failure path: schedule a retry or shelve as dead.
    is_terminal = outbox.attempts >= outbox.max_attempts
    outbox.status = "dead" if is_terminal else "failed"
    outbox.next_retry_at = None if is_terminal else _compute_next_retry(outbox.attempts)
    outbox.last_error = error_message[:8000]
    outbox.updated_at = _utc_now()
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Could not persist outbox failed state.")

    if is_terminal:
        logger.critical(
            "Webhook outbox %s DEAD after %s attempts (workflow=%s related=%s/%s): %s",
            outbox.id,
            outbox.attempts,
            outbox.workflow_name,
            outbox.related_object_type,
            outbox.related_object_id,
            error_message,
        )
    else:
        logger.warning(
            "Webhook outbox %s failed attempt %s/%s via %s (workflow=%s): %s",
            outbox.id,
            outbox.attempts,
            outbox.max_attempts,
            source,
            outbox.workflow_name,
            error_message,
        )

    raise HTTPException(
        status_code=502,
        detail=f"n8n webhook delivery failed ({outbox.workflow_name or outbox.webhook_url}).",
    )


def _parse_response(response_text: str) -> object:
    if not response_text:
        return {}
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        return {"raw": response_text}
