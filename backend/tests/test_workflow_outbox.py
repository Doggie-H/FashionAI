from collections.abc import Callable

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app import models  # Registers legacy User table for foreign keys.
from app.database import Base
from app.services.workflow_outbox import (
    IdempotencyConflictError,
    RedisIdempotencyGuard,
    claim_outbox_batch,
    consume_event_once,
    execute_idempotent_with_outbox,
    publish_claimed_event,
)
from app.workflow_models import ProcessedCommand, ProcessedEventDelivery, WorkflowOutboxEvent


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def execute_session_command(db: Session, payload: dict, state: dict) -> dict:
    def handler(correlation_id: str, command_id: str):
        state["handler_calls"] += 1
        result = {"session_id": "style_outbox_demo", "correlation_id": correlation_id}
        events = [{
            "event_type": "StylingSessionOpened.v1",
            "aggregate_type": "StylingSession",
            "aggregate_id": result["session_id"],
            "payload": {"session_id": result["session_id"], "command_id": command_id},
        }]
        return result, events

    return execute_idempotent_with_outbox(
        db,
        actor_id=7,
        command_type="CreateStylingSession",
        idempotency_key="idem-create-style-0001",
        request_payload=payload,
        correlation_id="corr-client-0001",
        guard=RedisIdempotencyGuard(None),
        handler=handler,
        serializer=lambda value: value,
        deserializer=lambda stored: {
            "session_id": stored["session_id"],
            "correlation_id": stored["correlation_id"],
        },
    )


def test_postgres_style_idempotency_persists_one_command_and_one_outbox_event(db_session: Session):
    state = {"handler_calls": 0}
    payload = {"body_profile_id": "body_123", "occasion": "work"}

    first = execute_session_command(db_session, payload, state)
    replay = execute_session_command(db_session, payload, state)

    assert first == replay
    assert state["handler_calls"] == 1
    assert db_session.query(ProcessedCommand).count() == 1
    event = db_session.query(WorkflowOutboxEvent).one()
    assert event.event_type == "StylingSessionOpened.v1"
    assert event.status == "pending"
    assert event.correlation_id == "corr-client-0001"


def test_idempotency_key_rejects_changed_payload(db_session: Session):
    state = {"handler_calls": 0}
    execute_session_command(db_session, {"body_profile_id": "body_123", "occasion": "work"}, state)

    with pytest.raises(IdempotencyConflictError):
        execute_session_command(db_session, {"body_profile_id": "body_123", "occasion": "event"}, state)

    assert state["handler_calls"] == 1


class RecordingPublisher:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.events: list[tuple[str, str, dict]] = []

    def publish(self, event_id: str, event_type: str, payload: dict) -> None:
        if self.fail:
            raise RuntimeError("broker unavailable")
        self.events.append((event_id, event_type, payload))


def test_outbox_claim_publish_and_retry(db_session: Session):
    state = {"handler_calls": 0}
    execute_session_command(db_session, {"body_profile_id": "body_123", "occasion": "work"}, state)
    claimed = claim_outbox_batch(db_session, worker_id="publisher-a")
    assert len(claimed) == 1
    event_id = claimed[0].event_id

    failed = publish_claimed_event(db_session, event_id, "publisher-a", RecordingPublisher(fail=True))
    assert failed is False
    retry_event = db_session.get(WorkflowOutboxEvent, event_id)
    assert retry_event.status == "retry"
    assert retry_event.attempt_count == 1
    assert retry_event.last_error == "broker unavailable"

    # Make the retry immediately eligible for deterministic unit testing.
    retry_event.available_at = retry_event.created_at
    db_session.commit()
    reclaimed = claim_outbox_batch(db_session, worker_id="publisher-b")
    assert [event.event_id for event in reclaimed] == [event_id]
    publisher = RecordingPublisher()
    assert publish_claimed_event(db_session, event_id, "publisher-b", publisher) is True
    assert publisher.events[0][0] == event_id
    assert db_session.get(WorkflowOutboxEvent, event_id).status == "published"


def test_consumer_delivery_ledger_runs_downstream_handler_once(db_session: Session):
    event = WorkflowOutboxEvent(
        event_id="outbox_consumer_demo",
        dedupe_key="StylingSessionOpened.v1:style_demo:cmd_demo",
        aggregate_type="StylingSession",
        aggregate_id="style_demo",
        event_type="StylingSessionOpened.v1",
        payload={"session_id": "style_demo"},
        correlation_id="corr_demo",
    )
    db_session.add(event)
    db_session.commit()
    calls = {"count": 0}

    def handler() -> None:
        calls["count"] += 1

    assert consume_event_once(db_session, consumer_name="stylist.projector", event_id=event.event_id, handler=handler) is True
    assert consume_event_once(db_session, consumer_name="stylist.projector", event_id=event.event_id, handler=handler) is False
    assert calls["count"] == 1
    assert db_session.query(ProcessedEventDelivery).count() == 1


class FlakyRedisPublisher:
    def __init__(self):
        self.calls = 0
        self.published: list[str] = []

    def publish(self, event_id: str, event_type: str, payload: dict) -> None:
        self.calls += 1
        if self.calls == 1:
            raise ConnectionError("redis broker temporarily unavailable")
        self.published.append(event_id)


def test_background_relay_retries_database_and_redis_failure_until_event_is_published(monkeypatch, db_session: Session):
    from sqlalchemy.exc import OperationalError

    from app.services.outbox_relay import OutboxRelay

    state = {"handler_calls": 0}
    execute_session_command(db_session, {"body_profile_id": "body_123", "occasion": "work"}, state)
    event_id = db_session.query(WorkflowOutboxEvent).one().event_id
    monkeypatch.setenv("WORKFLOW_OUTBOX_RETRY_BASE_SECONDS", "0")
    monkeypatch.setenv("WORKFLOW_OUTBOX_RETRY_MAX_SECONDS", "0")

    calls = {"factory": 0}

    def flaky_session_factory():
        calls["factory"] += 1
        if calls["factory"] == 1:
            raise OperationalError("SELECT workflow_outbox_events", {}, ConnectionError("database temporarily unavailable"))
        return db_session

    publisher = FlakyRedisPublisher()
    relay = OutboxRelay(
        flaky_session_factory,
        worker_id="relay-test",
        publisher=publisher,
        poll_seconds=0,
        sleep=lambda _seconds: None,
    )
    reports = relay.run_forever(max_cycles=3)

    assert reports[0].database_error is True
    assert reports[1].claimed == 1
    assert reports[1].publish_failed == 1
    assert reports[2].published == 1
    assert publisher.published == [event_id]
    assert db_session.get(WorkflowOutboxEvent, event_id).status == "published"


def test_outbox_metrics_snapshot_exposes_pending_retry_processing_and_dead_letter(db_session: Session):
    from app.services.outbox_metrics import refresh_outbox_gauges

    event = WorkflowOutboxEvent(
        event_id="outbox_metrics_demo",
        dedupe_key="StylingSessionOpened.v1:style_metrics:cmd_metrics",
        aggregate_type="StylingSession",
        aggregate_id="style_metrics",
        event_type="StylingSessionOpened.v1",
        payload={"session_id": "style_metrics"},
        correlation_id="corr_metrics",
        status="dead_letter",
    )
    db_session.add(event)
    db_session.commit()

    snapshot = refresh_outbox_gauges(db_session)
    assert snapshot["dead_letter"]["count"] == 1
    assert snapshot["pending"]["count"] == 0


def test_outbox_moves_event_to_dead_letter_after_configured_publish_attempt_limit(monkeypatch, db_session: Session):
    state = {"handler_calls": 0}
    execute_session_command(db_session, {"body_profile_id": "body_dead", "occasion": "work"}, state)
    event = claim_outbox_batch(db_session, worker_id="publisher-dead-letter")[0]
    monkeypatch.setenv("WORKFLOW_OUTBOX_MAX_PUBLISH_ATTEMPTS", "1")

    assert publish_claimed_event(db_session, event.event_id, "publisher-dead-letter", RecordingPublisher(fail=True)) is False
    persisted = db_session.get(WorkflowOutboxEvent, event.event_id)
    assert persisted.status == "dead_letter"
    assert persisted.last_error == "broker unavailable"
