from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from pathlib import Path
from uuid import uuid4

import jwt
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from testcontainers.core.container import DockerContainer
from testcontainers.postgres import PostgresContainer

from app import models
from app.database import Base, get_db
from app.phase_a_schemas import RawMeasurementsV1, StyleContextV1
from app.services.body_contract import build_parametric_body_contract
from app.services import workflow_service
from app.workflow_models import BodyProfileRevision, WorkflowOutboxEvent
from app.workflow_schemas import CreateStylingSessionCommandV1
from main import app


MEASUREMENTS = {
    "height_cm": 162,
    "weight_kg": 56,
    "shoulder_cm": 39,
    "bust_cm": 82,
    "waist_cm": 67,
    "hip_cm": 94,
    "inseam_cm": 74,
    "shoulder_slope": "sloped",
    "chest_profile": "flat",
    "leg_alignment": "bowed",
}
CONTEXT = {
    "occasion": "work",
    "preferred_styles": ["business", "classic"],
    "season": "autumn",
    "fit_preference": "tailored",
    "required_slots": ["base_top", "bottom"],
}
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def auth_db(monkeypatch):
    monkeypatch.setenv("WORKFLOW_AUTH_MODE", "jwt")
    monkeypatch.setenv("WORKFLOW_JWT_SIGNING_KEY", "test-workflow-jwt-key-with-at-least-32-bytes")
    monkeypatch.setenv("AI_STYLIST_DEMO_MODE", "1")
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    session.add(models.User(id=501, username="jwt-owner", email="jwt-owner@example.test"))
    session.commit()

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        yield session
    finally:
        app.dependency_overrides.clear()
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def jwt_headers(
    actor_id: int = 501,
    correlation_id: str = "corr-auth-context-0001",
    *,
    roles: list[str] | None = None,
    idempotency_key: str = "header-idempotency-key-0001",
) -> dict[str, str]:
    claims = {"sub": str(actor_id), "tenant_id": "tenant-demo"}
    if roles is not None:
        claims["roles"] = roles
    token = jwt.encode(
        claims,
        "test-workflow-jwt-key-with-at-least-32-bytes",
        algorithm="HS256",
    )
    return {
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": idempotency_key,
        "X-Correlation-ID": correlation_id,
    }


def test_workflow_uses_jwt_actor_and_header_correlation_not_client_metadata(auth_db):
    client = TestClient(app)
    response = client.post(
        "/workflow/body-profiles",
        json={"measurements": MEASUREMENTS},
        headers=jwt_headers(),
    )
    assert response.status_code == 201
    assert response.json()["owner_id"] == 501

    events = client.get(
        f"/workflow/audit-events/{response.json()['profile_id']}",
        headers=jwt_headers(correlation_id="corr-auth-context-0002"),
    )
    assert events.status_code == 200
    assert events.json()[0]["actor_id"] == 501
    assert events.json()[0]["correlation_id"] == "corr-auth-context-0001"

    mismatched = client.post(
        "/workflow/body-profiles",
        json={"actor_id": 999, "measurements": MEASUREMENTS},
        headers=jwt_headers(correlation_id="corr-auth-context-0003"),
    )
    assert mismatched.status_code == 403


def _upgrade(url: str) -> None:
    config = Config(str(ROOT / "alembic.ini"))
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    try:
        command.upgrade(config, "head")
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous


@pytest.fixture(scope="module")
def postgres_and_redis_runtime():
    if os.getenv("RUN_TESTCONTAINERS", "0").lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Set RUN_TESTCONTAINERS=1 to run PostgreSQL/Redis integration tests")
    with PostgresContainer("postgres:16-alpine") as postgres, DockerContainer("redis:7.4-alpine").with_exposed_ports(6379) as redis:
        pg_url = postgres.get_connection_url()
        redis_url = f"redis://{redis.get_container_host_ip()}:{redis.get_exposed_port(6379)}/2"
        _upgrade(pg_url)
        yield pg_url, redis_url


@pytest.fixture
def postgres_session_factory(postgres_and_redis_runtime):
    pg_url, _ = postgres_and_redis_runtime
    engine = create_engine(pg_url, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    try:
        yield factory
    finally:
        engine.dispose()


def _seed_active_profile(factory) -> tuple[int, str]:
    db: Session = factory()
    try:
        suffix = uuid4().hex[:12]
        actor_id = 7701 + db.query(models.User).count()
        db.add(models.User(id=actor_id, username=f"race-owner-{suffix}", email=f"race-owner-{suffix}@example.test"))
        measurements = RawMeasurementsV1.model_validate(MEASUREMENTS)
        contract = build_parametric_body_contract(measurements)
        profile = BodyProfileRevision(
            profile_id=f"body_{suffix}",
            owner_id=actor_id,
            revision=1,
            status="active",
            measurements=measurements.model_dump(mode="json"),
            body_contract=contract.model_dump(mode="json"),
            calibration_version="parametric-body-contract-v1",
        )
        db.add(profile)
        db.commit()
        return actor_id, profile.profile_id
    finally:
        db.close()


def _create_concurrent_session(factory, actor_id: int, profile_id: str, key: str):
    db: Session = factory()
    try:
        command = CreateStylingSessionCommandV1(
            actor_id=actor_id,
            idempotency_key=key,
            correlation_id="corr-postgres-race-0001",
            body_profile_id=profile_id,
            context=StyleContextV1.model_validate(CONTEXT),
        )
        return workflow_service.create_styling_session(db, command)
    finally:
        db.close()


@pytest.mark.containers
def test_postgres_unique_constraint_recovers_concurrent_styling_session_race(monkeypatch, postgres_and_redis_runtime, postgres_session_factory):
    actor_id, profile_id = _seed_active_profile(postgres_session_factory)
    monkeypatch.setenv("WORKFLOW_OUTBOX_ENABLED", "1")
    monkeypatch.delenv("IDEMPOTENCY_REDIS_URL", raising=False)
    barrier = Barrier(2)
    original_audit = workflow_service._audit

    def synchronized_audit(*args, **kwargs):
        if len(args) >= 3 and args[1] == "StylingSession":
            barrier.wait(timeout=10)
        return original_audit(*args, **kwargs)

    monkeypatch.setattr(workflow_service, "_audit", synchronized_audit)
    key = "postgres-race-idempotency-key-0001"
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(_create_concurrent_session, postgres_session_factory, actor_id, profile_id, key) for _ in range(2)]
        results = [future.result(timeout=20) for future in futures]

    assert {result.session_id for result in results}.__len__() == 1
    db: Session = postgres_session_factory()
    try:
        assert db.query(WorkflowOutboxEvent).count() == 1
    finally:
        db.close()


@pytest.mark.containers
def test_redis_guard_returns_inflight_then_replays_committed_postgres_result(monkeypatch, postgres_and_redis_runtime, postgres_session_factory):
    actor_id, profile_id = _seed_active_profile(postgres_session_factory)
    _, redis_url = postgres_and_redis_runtime
    monkeypatch.setenv("WORKFLOW_OUTBOX_ENABLED", "1")
    monkeypatch.setenv("IDEMPOTENCY_REDIS_URL", redis_url)
    original_handler = workflow_service._audit

    def delayed_audit(*args, **kwargs):
        if len(args) >= 3 and args[1] == "StylingSession":
            import time
            time.sleep(0.25)
        return original_handler(*args, **kwargs)

    monkeypatch.setattr(workflow_service, "_audit", delayed_audit)
    key = "redis-race-idempotency-key-0001"
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(_create_concurrent_session, postgres_session_factory, actor_id, profile_id, key) for _ in range(4)]
    completed = []
    for future in futures:
        try:
            completed.append(future.result(timeout=20))
        except Exception as error:
            assert error.__class__.__name__ == "IdempotencyInProgressError"

    assert len(completed) == 1
    replay = _create_concurrent_session(postgres_session_factory, actor_id, profile_id, key)
    assert replay.session_id == completed[0].session_id


def test_prometheus_metrics_endpoint_exposes_outbox_metrics_and_honors_bearer_token(monkeypatch):
    monkeypatch.setenv("METRICS_TOKEN", "metrics-test-token")
    client = TestClient(app)

    denied = client.get("/metrics")
    assert denied.status_code == 403
    allowed = client.get("/metrics", headers={"Authorization": "Bearer metrics-test-token"})
    assert allowed.status_code == 200
    assert "ai_stylist_outbox_backlog_events" in allowed.text
    assert "ai_stylist_outbox_relay_database_errors_total" in allowed.text


def test_admin_can_review_then_replay_dead_letter_with_jwt_role_and_audit(auth_db):
    from app.workflow_models import WorkflowAuditEvent, WorkflowOutboxEvent

    event = WorkflowOutboxEvent(
        event_id="outbox_admin_deadletter",
        dedupe_key="StylingSessionOpened.v1:style_admin:cmd_admin",
        aggregate_type="StylingSession",
        aggregate_id="style_admin",
        event_type="StylingSessionOpened.v1",
        payload={"session_id": "style_admin"},
        correlation_id="corr-admin-seeded",
        status="dead_letter",
        attempt_count=12,
        last_error="broker unavailable",
    )
    auth_db.add(event)
    auth_db.commit()
    client = TestClient(app)

    denied = client.get("/admin/outbox/dead-letters", headers=jwt_headers())
    assert denied.status_code == 403

    admin_headers = jwt_headers(
        roles=["admin"],
        correlation_id="corr-admin-review-0001",
        idempotency_key="admin-review-deadletter-0001",
    )
    queue = client.get("/admin/outbox/dead-letters", headers=admin_headers)
    assert queue.status_code == 200
    assert queue.json()["total"] == 1

    premature = client.post(
        "/admin/outbox/dead-letters/outbox_admin_deadletter/replay",
        json={"review_note": "Verified broker recovery."},
        headers=jwt_headers(roles=["admin"], idempotency_key="admin-replay-deadletter-0001"),
    )
    assert premature.status_code == 409

    reviewed = client.post(
        "/admin/outbox/dead-letters/outbox_admin_deadletter/review",
        json={"review_note": "Validated payload and broker recovery."},
        headers=admin_headers,
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["reviewer_actor_id"] == 501

    replayed = client.post(
        "/admin/outbox/dead-letters/outbox_admin_deadletter/replay",
        json={"review_note": "Approved controlled replay."},
        headers=jwt_headers(
            roles=["admin"],
            correlation_id="corr-admin-replay-0001",
            idempotency_key="admin-replay-deadletter-0002",
        ),
    )
    assert replayed.status_code == 200
    assert replayed.json()["status"] == "retry"
    assert auth_db.get(WorkflowOutboxEvent, "outbox_admin_deadletter").status == "retry"
    assert [item.event_type for item in auth_db.query(WorkflowAuditEvent).filter_by(aggregate_id="outbox_admin_deadletter").all()] == [
        "OutboxDeadLetterReviewed",
        "OutboxDeadLetterReplayRequested",
    ]


def test_admin_dead_letter_pagination_and_idempotent_replay_preserve_event(auth_db):
    from app.workflow_models import WorkflowAuditEvent

    for number in range(3):
        auth_db.add(
            WorkflowOutboxEvent(
                event_id=f"outbox_admin_page_{number}",
                dedupe_key=f"StylingSessionOpened.v1:style_page_{number}:cmd_page_{number}",
                aggregate_type="StylingSession",
                aggregate_id=f"style_page_{number}",
                event_type="StylingSessionOpened.v1",
                payload={"session_id": f"style_page_{number}", "ordinal": number},
                correlation_id=f"corr-page-seeded-{number}",
                status="dead_letter",
                attempt_count=8 + number,
                last_error="broker unavailable",
            )
        )
    auth_db.commit()
    client = TestClient(app)

    queue = client.get(
        "/admin/outbox/dead-letters?limit=2&offset=1",
        headers=jwt_headers(roles=["admin"], idempotency_key="admin-page-list-0001"),
    )
    assert queue.status_code == 200
    assert queue.json()["total"] == 3
    assert len(queue.json()["items"]) == 2

    event_id = "outbox_admin_page_0"
    original = auth_db.get(WorkflowOutboxEvent, event_id)
    original_payload = dict(original.payload)
    review_headers = jwt_headers(
        roles=["admin"],
        correlation_id="corr-idempotent-review-0001",
        idempotency_key="admin-idempotent-review-0001",
    )
    first_review = client.post(
        f"/admin/outbox/dead-letters/{event_id}/review",
        json={"review_note": "Payload, target queue, and recovery window were verified."},
        headers=review_headers,
    )
    second_review = client.post(
        f"/admin/outbox/dead-letters/{event_id}/review",
        json={"review_note": "Payload, target queue, and recovery window were verified."},
        headers=review_headers,
    )
    assert first_review.status_code == second_review.status_code == 200
    assert first_review.json() == second_review.json()

    replay_headers = jwt_headers(
        roles=["admin"],
        correlation_id="corr-idempotent-replay-0001",
        idempotency_key="admin-idempotent-replay-0001",
    )
    first_replay = client.post(
        f"/admin/outbox/dead-letters/{event_id}/replay",
        json={"review_note": "Approved after relay dependency recovery verification."},
        headers=replay_headers,
    )
    second_replay = client.post(
        f"/admin/outbox/dead-letters/{event_id}/replay",
        json={"review_note": "Approved after relay dependency recovery verification."},
        headers=replay_headers,
    )
    assert first_replay.status_code == second_replay.status_code == 200
    assert first_replay.json() == second_replay.json()
    persisted = auth_db.get(WorkflowOutboxEvent, event_id)
    assert persisted.event_id == event_id
    assert persisted.payload == original_payload
    assert persisted.status == "retry"
    assert auth_db.query(WorkflowAuditEvent).filter_by(aggregate_id=event_id).count() == 2
