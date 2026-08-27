from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..services import workflow_service
from ..workflow_models import WorkflowOutboxEvent
from ..workflow_schemas import DeadLetterEventV1, DeadLetterQueueV1


class OutboxAdminNotFoundError(ValueError):
    pass


class OutboxAdminStateError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _event_response(event: WorkflowOutboxEvent) -> DeadLetterEventV1:
    return DeadLetterEventV1(
        event_id=event.event_id,
        dedupe_key=event.dedupe_key,
        aggregate_type=event.aggregate_type,
        aggregate_id=event.aggregate_id,
        event_type=event.event_type,
        schema_version=event.schema_version,
        payload=event.payload or {},
        correlation_id=event.correlation_id,
        status=event.status,
        attempt_count=event.attempt_count,
        available_at=event.available_at,
        locked_at=event.locked_at,
        locked_by=event.locked_by,
        published_at=event.published_at,
        last_error=event.last_error,
        created_at=event.created_at,
        reviewed_at=event.reviewed_at,
        review_note=event.review_note,
        reviewer_actor_id=event.reviewer_actor_id,
    )


def list_dead_letters(db: Session, *, limit: int = 100, offset: int = 0) -> DeadLetterQueueV1:
    query = db.query(WorkflowOutboxEvent).filter(WorkflowOutboxEvent.status == "dead_letter")
    total = query.count()
    events = query.order_by(WorkflowOutboxEvent.created_at.asc()).offset(offset).limit(limit).all()
    return DeadLetterQueueV1(items=[_event_response(event) for event in events], total=total)


def review_dead_letter(
    db: Session,
    *,
    event_id: str,
    admin_actor_id: int,
    correlation_id: str,
    idempotency_key: str,
    review_note: str,
) -> DeadLetterEventV1:
    workflow_service._require_actor(db, admin_actor_id)

    def handler() -> DeadLetterEventV1:
        event = db.get(WorkflowOutboxEvent, event_id)
        if event is None:
            raise OutboxAdminNotFoundError("Outbox event was not found")
        if event.status != "dead_letter":
            raise OutboxAdminStateError("Only dead-letter events can be reviewed")
        event.reviewed_at = _now()
        event.review_note = review_note
        event.reviewer_actor_id = admin_actor_id
        workflow_service._audit(
            db,
            "WorkflowOutboxEvent",
            event.event_id,
            "OutboxDeadLetterReviewed",
            admin_actor_id,
            correlation_id,
            {"attempt_count": event.attempt_count, "review_note": review_note},
        )
        db.flush()
        return _event_response(event)

    return workflow_service._execute_idempotent(
        db,
        "ReviewOutboxDeadLetter",
        admin_actor_id,
        idempotency_key,
        correlation_id,
        handler,
        lambda value: value.model_dump(mode="json") if isinstance(value, DeadLetterEventV1) else DeadLetterEventV1.model_validate(value).model_dump(mode="json"),
    )


def replay_dead_letter(
    db: Session,
    *,
    event_id: str,
    admin_actor_id: int,
    correlation_id: str,
    idempotency_key: str,
    review_note: str,
) -> DeadLetterEventV1:
    workflow_service._require_actor(db, admin_actor_id)

    def handler() -> DeadLetterEventV1:
        event = db.get(WorkflowOutboxEvent, event_id)
        if event is None:
            raise OutboxAdminNotFoundError("Outbox event was not found")
        if event.status != "dead_letter":
            raise OutboxAdminStateError("Only dead-letter events can be replayed")
        if event.reviewed_at is None or event.reviewer_actor_id is None:
            raise OutboxAdminStateError("Dead-letter event must be reviewed before replay")
        event.status = "retry"
        event.available_at = _now()
        event.locked_at = None
        event.locked_by = None
        event.last_error = f"Replay requested by admin {admin_actor_id}: {review_note}"[:1000]
        workflow_service._audit(
            db,
            "WorkflowOutboxEvent",
            event.event_id,
            "OutboxDeadLetterReplayRequested",
            admin_actor_id,
            correlation_id,
            {
                "attempt_count": event.attempt_count,
                "reviewer_actor_id": event.reviewer_actor_id,
                "replay_note": review_note,
            },
        )
        db.flush()
        return _event_response(event)

    return workflow_service._execute_idempotent(
        db,
        "ReplayOutboxDeadLetter",
        admin_actor_id,
        idempotency_key,
        correlation_id,
        handler,
        lambda value: value.model_dump(mode="json") if isinstance(value, DeadLetterEventV1) else DeadLetterEventV1.model_validate(value).model_dump(mode="json"),
    )
