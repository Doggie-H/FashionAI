from __future__ import annotations

import time
from collections.abc import Mapping
from datetime import datetime, timezone

from prometheus_client import Counter, Gauge, Histogram
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..workflow_models import WorkflowOutboxEvent

OUTBOX_PUBLISH_ATTEMPTS = Counter(
    "ai_stylist_outbox_publish_attempts_total",
    "Number of claimed outbox publish attempts.",
    ["outcome"],
)
OUTBOX_RETRIES = Counter(
    "ai_stylist_outbox_retries_total",
    "Number of outbox events scheduled for retry.",
    ["reason"],
)
OUTBOX_DEAD_LETTERS = Counter(
    "ai_stylist_outbox_dead_letters_total",
    "Number of outbox events moved to dead letter status.",
    ["reason"],
)
OUTBOX_RELAY_DB_ERRORS = Counter(
    "ai_stylist_outbox_relay_database_errors_total",
    "Number of database errors observed by the outbox relay.",
    ["operation"],
)
OUTBOX_RELAY_CYCLES = Counter(
    "ai_stylist_outbox_relay_cycles_total",
    "Number of outbox relay cycles.",
    ["outcome"],
)
OUTBOX_PUBLISH_SECONDS = Histogram(
    "ai_stylist_outbox_publish_seconds",
    "Latency of a single outbox publish attempt.",
    buckets=(0.005, 0.01, 0.05, 0.1, 0.5, 1, 5, 15, 60),
)
OUTBOX_BACKLOG = Gauge(
    "ai_stylist_outbox_backlog_events",
    "Current number of outbox events by persistent status.",
    ["status"],
)
OUTBOX_OLDEST_AGE_SECONDS = Gauge(
    "ai_stylist_outbox_oldest_event_age_seconds",
    "Age in seconds of the oldest outstanding outbox event by status.",
    ["status"],
)

OUTSTANDING_STATUSES = ("pending", "retry", "processing", "dead_letter")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def observe_publish(outcome: str, started_at: float) -> None:
    OUTBOX_PUBLISH_ATTEMPTS.labels(outcome=outcome).inc()
    OUTBOX_PUBLISH_SECONDS.observe(max(0.0, time.monotonic() - started_at))


def observe_retry(reason: str) -> None:
    OUTBOX_RETRIES.labels(reason=reason).inc()


def observe_dead_letter(reason: str) -> None:
    OUTBOX_DEAD_LETTERS.labels(reason=reason).inc()


def observe_database_error(operation: str) -> None:
    OUTBOX_RELAY_DB_ERRORS.labels(operation=operation).inc()


def refresh_outbox_gauges(db: Session, now: datetime | None = None) -> dict[str, dict[str, float]]:
    """Refresh scrape gauges from PostgreSQL; safe to call from the API or relay once per cycle."""
    observed_at = now or utcnow()
    rows = db.execute(
        select(
            WorkflowOutboxEvent.status,
            func.count(WorkflowOutboxEvent.event_id),
            func.min(WorkflowOutboxEvent.created_at),
        )
        .where(WorkflowOutboxEvent.status.in_(OUTSTANDING_STATUSES))
        .group_by(WorkflowOutboxEvent.status)
    ).all()
    snapshot: dict[str, dict[str, float]] = {}
    by_status = {status: (int(count), created_at) for status, count, created_at in rows}
    for status in OUTSTANDING_STATUSES:
        count, created_at = by_status.get(status, (0, None))
        age = 0.0
        if created_at is not None:
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            age = max(0.0, (observed_at - created_at).total_seconds())
        OUTBOX_BACKLOG.labels(status=status).set(count)
        OUTBOX_OLDEST_AGE_SECONDS.labels(status=status).set(age)
        snapshot[status] = {"count": float(count), "oldest_age_seconds": age}
    return snapshot
