from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Protocol, TypeVar
from uuid import uuid4

from redis import Redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..queue import celery_app
from ..workflow_models import ProcessedCommand, ProcessedEventDelivery, WorkflowOutboxEvent
from .outbox_metrics import observe_dead_letter, observe_publish, observe_retry

T = TypeVar("T")

OUTBOX_EVENT_STYLING_SESSION_OPENED = "StylingSessionOpened.v1"
OUTBOX_EVENT_STYLING_SESSION_FEEDBACK_RECORDED = "StylingSessionFeedbackRecorded.v1"
OUTBOX_EVENT_TRY_ON_REQUESTED = "TryOnRequested.v1"
OUTBOX_STATUS_PENDING = "pending"
OUTBOX_STATUS_PROCESSING = "processing"
OUTBOX_STATUS_PUBLISHED = "published"
OUTBOX_STATUS_RETRY = "retry"
OUTBOX_STATUS_DEAD_LETTER = "dead_letter"


class IdempotencyInProgressError(RuntimeError):
    """The command has no committed result and another caller owns its short Redis lock."""


class IdempotencyConflictError(RuntimeError):
    """The same idempotency key was reused with a different request fingerprint."""


class EventPublisher(Protocol):
    def publish(self, event_id: str, event_type: str, payload: dict[str, Any]) -> None:
        """Publish a durable outbox event after its database transaction has committed."""


class CeleryEventPublisher:
    task_name = "stylist.handle_workflow_outbox_event"

    def publish(self, event_id: str, event_type: str, payload: dict[str, Any]) -> None:
        celery_app.send_task(self.task_name, args=[event_id, event_type, payload])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _identifier(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def command_fingerprint(request_payload: dict[str, Any]) -> str:
    canonical = json.dumps(request_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def resolve_correlation_id(provided: str | None) -> str:
    return provided or _identifier("corr")


class RedisIdempotencyGuard:
    """Best-effort fast path. PostgreSQL unique constraints remain the authority."""

    def __init__(self, redis_client: Redis | None, lock_ttl_seconds: int = 30, response_ttl_seconds: int = 86400):
        self.redis_client = redis_client
        self.lock_ttl_seconds = lock_ttl_seconds
        self.response_ttl_seconds = response_ttl_seconds

    @classmethod
    def from_environment(cls) -> "RedisIdempotencyGuard":
        url = os.getenv("IDEMPOTENCY_REDIS_URL")
        lock_ttl = int(os.getenv("WORKFLOW_IDEMPOTENCY_LOCK_SECONDS", "30"))
        response_ttl = int(os.getenv("WORKFLOW_IDEMPOTENCY_RESPONSE_TTL_SECONDS", "86400"))
        if not url:
            return cls(None, lock_ttl_seconds=lock_ttl, response_ttl_seconds=response_ttl)
        return cls(
            Redis.from_url(url, decode_responses=True),
            lock_ttl_seconds=lock_ttl,
            response_ttl_seconds=response_ttl,
        )

    @staticmethod
    def _lock_key(scope: str) -> str:
        return f"workflow:idem:lock:{scope}"

    @staticmethod
    def _response_key(scope: str) -> str:
        return f"workflow:idem:response:{scope}"

    def acquire_lock(self, scope: str, token: str) -> bool:
        if self.redis_client is None:
            return True
        try:
            return bool(self.redis_client.set(self._lock_key(scope), token, nx=True, ex=self.lock_ttl_seconds))
        except Exception:
            # Redis must not decide correctness; a PostgreSQL transaction still handles the command.
            return True

    def cache_response(self, scope: str, response_payload: dict[str, Any]) -> None:
        if self.redis_client is None:
            return
        try:
            self.redis_client.set(self._response_key(scope), json.dumps(response_payload), ex=self.response_ttl_seconds)
        except Exception:
            return

    def release_lock(self, scope: str, token: str) -> None:
        if self.redis_client is None:
            return
        try:
            # Delete only the caller's own lock; do not delete a lock acquired after TTL expiry.
            self.redis_client.eval(
                "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) end return 0",
                1,
                self._lock_key(scope),
                token,
            )
        except Exception:
            return


def idempotency_scope(actor_id: int, command_type: str, idempotency_key: str) -> str:
    return f"{actor_id}:{command_type}:{idempotency_key}"


def outbox_dedupe_key(event_type: str, aggregate_id: str, command_id: str) -> str:
    return f"{event_type}:{aggregate_id}:{command_id}"


def enqueue_outbox_event(
    db: Session,
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    command_id: str,
    correlation_id: str,
    payload: dict[str, Any],
) -> WorkflowOutboxEvent:
    event = WorkflowOutboxEvent(
        event_id=_identifier("outbox"),
        dedupe_key=outbox_dedupe_key(event_type, aggregate_id, command_id),
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        event_type=event_type,
        payload=payload,
        correlation_id=correlation_id,
        status=OUTBOX_STATUS_PENDING,
    )
    db.add(event)
    return event


def execute_idempotent_with_outbox(
    db: Session,
    *,
    actor_id: int,
    command_type: str,
    idempotency_key: str,
    request_payload: dict[str, Any],
    correlation_id: str | None,
    guard: RedisIdempotencyGuard,
    handler: Callable[[str, str], tuple[T, list[dict[str, Any]]]],
    serializer: Callable[[T], dict[str, Any]],
    deserializer: Callable[[dict[str, Any]], T],
) -> T:
    """Run command, response record, audit state, and outbox rows in one PostgreSQL transaction.

    The handler receives one server-resolved correlation ID and a command ID. It must only mutate the
    supplied Session and return serializable outbox event specifications. It must not publish messages.
    """
    scope = idempotency_scope(actor_id, command_type, idempotency_key)
    existing = db.execute(
        select(ProcessedCommand).where(
            ProcessedCommand.actor_id == actor_id,
            ProcessedCommand.command_type == command_type,
            ProcessedCommand.idempotency_key == idempotency_key,
        )
    ).scalar_one_or_none()
    fingerprint = command_fingerprint(request_payload)
    if existing is not None:
        stored_fingerprint = (existing.response_payload or {}).get("_request_fingerprint")
        if stored_fingerprint and stored_fingerprint != fingerprint:
            raise IdempotencyConflictError("Idempotency key cannot be reused with a different request payload")
        return deserializer(existing.response_payload)

    lock_token = _identifier("lock")
    if not guard.acquire_lock(scope, lock_token):
        raise IdempotencyInProgressError("Command with this idempotency key is already in progress")

    resolved_correlation_id = resolve_correlation_id(correlation_id)
    command_id = _identifier("cmd")
    try:
        result, event_specs = handler(resolved_correlation_id, command_id)
        response_payload = serializer(result)
        stored_response = {**response_payload, "_request_fingerprint": fingerprint}
        db.add(ProcessedCommand(
            command_id=command_id,
            actor_id=actor_id,
            command_type=command_type,
            idempotency_key=idempotency_key,
            response_payload=stored_response,
            correlation_id=resolved_correlation_id,
        ))
        for spec in event_specs:
            enqueue_outbox_event(
                db,
                event_type=spec["event_type"],
                aggregate_type=spec["aggregate_type"],
                aggregate_id=spec["aggregate_id"],
                command_id=command_id,
                correlation_id=resolved_correlation_id,
                payload=spec["payload"],
            )
        db.commit()
        guard.cache_response(scope, response_payload)
        return result
    except IntegrityError:
        db.rollback()
        winner = db.execute(
            select(ProcessedCommand).where(
                ProcessedCommand.actor_id == actor_id,
                ProcessedCommand.command_type == command_type,
                ProcessedCommand.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if winner is None:
            raise
        stored_fingerprint = (winner.response_payload or {}).get("_request_fingerprint")
        if stored_fingerprint and stored_fingerprint != fingerprint:
            raise IdempotencyConflictError("Idempotency key cannot be reused with a different request payload")
        return deserializer(winner.response_payload)
    except Exception:
        db.rollback()
        raise
    finally:
        guard.release_lock(scope, lock_token)


def claim_outbox_batch(db: Session, worker_id: str, limit: int = 50) -> list[WorkflowOutboxEvent]:
    """Claim work using PostgreSQL row locks; SQLite tests use a conservative fallback query."""
    now = _now()
    statement = (
        select(WorkflowOutboxEvent)
        .where(
            WorkflowOutboxEvent.status.in_([OUTBOX_STATUS_PENDING, OUTBOX_STATUS_RETRY]),
            WorkflowOutboxEvent.available_at <= now,
        )
        .order_by(WorkflowOutboxEvent.created_at.asc())
        .limit(limit)
    )
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        statement = statement.with_for_update(skip_locked=True)
    events = list(db.execute(statement).scalars())
    for event in events:
        event.status = OUTBOX_STATUS_PROCESSING
        event.locked_at = now
        event.locked_by = worker_id
        event.attempt_count += 1
    db.commit()
    return events


def _retry_at(attempt_count: int) -> datetime:
    base_seconds = float(os.getenv("WORKFLOW_OUTBOX_RETRY_BASE_SECONDS", "2"))
    max_seconds = float(os.getenv("WORKFLOW_OUTBOX_RETRY_MAX_SECONDS", "300"))
    seconds = min(max_seconds, base_seconds * (2 ** min(attempt_count, 8)))
    return _now() + timedelta(seconds=seconds)


def _max_publish_attempts() -> int:
    return max(1, int(os.getenv("WORKFLOW_OUTBOX_MAX_PUBLISH_ATTEMPTS", "12")))


def publish_claimed_event(db: Session, event_id: str, worker_id: str, publisher: EventPublisher) -> bool:
    event = db.get(WorkflowOutboxEvent, event_id)
    if event is None or event.status != OUTBOX_STATUS_PROCESSING or event.locked_by != worker_id:
        return False
    started_at = time.monotonic()
    try:
        publisher.publish(event.event_id, event.event_type, event.payload)
    except Exception as error:
        event.last_error = str(error)[:1000]
        if event.attempt_count >= _max_publish_attempts():
            event.status = OUTBOX_STATUS_DEAD_LETTER
            observe_dead_letter("publisher_error")
            observe_publish("dead_letter", started_at)
        else:
            event.status = OUTBOX_STATUS_RETRY
            event.available_at = _retry_at(event.attempt_count)
            observe_retry("publisher_error")
            observe_publish("retry", started_at)
        event.locked_by = None
        event.locked_at = None
        db.commit()
        return False
    event.status = OUTBOX_STATUS_PUBLISHED
    event.published_at = _now()
    event.locked_by = None
    event.locked_at = None
    db.commit()
    observe_publish("published", started_at)
    return True


def consume_event_once(
    db: Session,
    *,
    consumer_name: str,
    event_id: str,
    handler: Callable[[], None],
) -> bool:
    """Return True only when the downstream effect ran for the first completed delivery."""
    delivery = ProcessedEventDelivery(
        delivery_id=_identifier("delivery"),
        consumer_name=consumer_name,
        event_id=event_id,
        status="processing",
    )
    db.add(delivery)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return False
    try:
        handler()
        delivery.status = "completed"
        delivery.completed_at = _now()
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
