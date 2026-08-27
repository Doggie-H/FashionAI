from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import database
from app.database import Base
from app import models, tasks
from app.workflow_models import ProcessedEventDelivery


def test_workflow_projector_accepts_p0_p1_p2_event_types_and_deduplicates(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(database, "SessionLocal", factory)
    try:
        for number, event_type in enumerate(("StylingSessionOpened.v1", "StylingSessionFeedbackRecorded.v1", "TryOnRequested.v1"), start=1):
            event_id = f"evt_p1p2_{number}"
            first = tasks.handle_workflow_outbox_event.run(event_id, event_type, {"version": 1})
            replay = tasks.handle_workflow_outbox_event.run(event_id, event_type, {"version": 1})
            assert first["processed"] is True
            assert replay["processed"] is False
        db = factory()
        try:
            assert db.query(ProcessedEventDelivery).filter_by(consumer_name="stylist.workflow_projector.v1").count() == 3
        finally:
            db.close()
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
