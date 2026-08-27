from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Callable

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .outbox_metrics import (
    OUTBOX_RELAY_CYCLES,
    observe_database_error,
    refresh_outbox_gauges,
)
from .workflow_outbox import CeleryEventPublisher, EventPublisher, claim_outbox_batch, publish_claimed_event


@dataclass(frozen=True)
class RelayCycleReport:
    claimed: int = 0
    published: int = 0
    publish_failed: int = 0
    database_error: bool = False
    error: str | None = None


class OutboxRelay:
    """Own the durable outbox poll loop; errors are retried outside the API process."""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        worker_id: str,
        publisher: EventPublisher | None = None,
        batch_size: int = 50,
        poll_seconds: float = 2.0,
        retry_backoff_max_seconds: float = 30.0,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.session_factory = session_factory
        self.worker_id = worker_id
        self.publisher = publisher or CeleryEventPublisher()
        self.batch_size = batch_size
        self.poll_seconds = poll_seconds
        self.retry_backoff_max_seconds = retry_backoff_max_seconds
        self.sleep = sleep

    @classmethod
    def from_environment(cls, session_factory: Callable[[], Session], worker_id: str) -> "OutboxRelay":
        return cls(
            session_factory,
            worker_id=worker_id,
            batch_size=int(os.getenv("WORKFLOW_OUTBOX_BATCH_SIZE", "50")),
            poll_seconds=float(os.getenv("WORKFLOW_OUTBOX_POLL_SECONDS", "2")),
            retry_backoff_max_seconds=float(os.getenv("WORKFLOW_OUTBOX_RELAY_DB_BACKOFF_MAX_SECONDS", "30")),
        )

    def run_cycle(self) -> RelayCycleReport:
        db: Session | None = None
        try:
            db = self.session_factory()
            events = claim_outbox_batch(db, worker_id=self.worker_id, limit=self.batch_size)
            published = 0
            publish_failed = 0
            for event in events:
                try:
                    if publish_claimed_event(db, event.event_id, self.worker_id, self.publisher):
                        published += 1
                    else:
                        publish_failed += 1
                except SQLAlchemyError as error:
                    db.rollback()
                    observe_database_error("publish_state_update")
                    OUTBOX_RELAY_CYCLES.labels(outcome="database_error").inc()
                    return RelayCycleReport(
                        claimed=len(events),
                        published=published,
                        publish_failed=publish_failed,
                        database_error=True,
                        error=str(error)[:1000],
                    )
            refresh_outbox_gauges(db)
            outcome = "published" if published else ("retry_scheduled" if publish_failed else "idle")
            OUTBOX_RELAY_CYCLES.labels(outcome=outcome).inc()
            return RelayCycleReport(claimed=len(events), published=published, publish_failed=publish_failed)
        except SQLAlchemyError as error:
            if db is not None:
                db.rollback()
            observe_database_error("claim_or_metrics")
            OUTBOX_RELAY_CYCLES.labels(outcome="database_error").inc()
            return RelayCycleReport(database_error=True, error=str(error)[:1000])
        finally:
            if db is not None:
                db.close()

    def run_forever(self, *, max_cycles: int | None = None) -> list[RelayCycleReport]:
        """Run until stopped externally; max_cycles exists for deterministic tests and one-shot supervision."""
        reports: list[RelayCycleReport] = []
        consecutive_database_errors = 0
        while max_cycles is None or len(reports) < max_cycles:
            report = self.run_cycle()
            reports.append(report)
            if report.database_error:
                consecutive_database_errors += 1
                delay = min(
                    self.retry_backoff_max_seconds,
                    self.poll_seconds * (2 ** min(consecutive_database_errors - 1, 8)),
                )
                self.sleep(delay)
                continue
            consecutive_database_errors = 0
            if report.claimed == 0 or report.publish_failed > 0:
                self.sleep(self.poll_seconds)
        return reports
