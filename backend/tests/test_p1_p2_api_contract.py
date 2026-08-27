from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base, get_db
from app.phase_a_schemas import RawMeasurementsV1
from app.workflow_models import EvaluationLabel, ReviewTask
from main import app


TEST_JWT_SECRET = "p1-p2-api-secret-with-32-byte-minimum"

MEASUREMENTS = {
    "height_cm": 170,
    "weight_kg": 60,
    "shoulder_cm": 42,
    "bust_cm": 88,
    "waist_cm": 72,
    "hip_cm": 94,
    "inseam_cm": 78,
}
CONTEXT = {"occasion": "work", "preferred_styles": ["business"], "required_slots": ["base_top", "bottom"], "availability_policy": "owned_only"}


def _token(actor_id: int, roles: list[str]) -> str:
    return jwt.encode({"sub": str(actor_id), "roles": roles, "exp": datetime.now(timezone.utc) + timedelta(minutes=10)}, TEST_JWT_SECRET, algorithm="HS256")


def _headers(token: str, key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Idempotency-Key": key, "X-Correlation-ID": f"corr-{key}"}


def test_p1_p2_http_contract_feedback_reviewer_and_proxy_fallback(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = factory()
    db.add_all([
        models.User(id=701, username="p1-owner", email="p1-owner@example.test"),
        models.User(id=702, username="p1-reviewer", email="p1-reviewer@example.test"),
    ])
    db.commit()
    monkeypatch.setenv("WORKFLOW_AUTH_MODE", "jwt")
    monkeypatch.setenv("WORKFLOW_JWT_SIGNING_KEY", TEST_JWT_SECRET)

    def override_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    owner_token = _token(701, ["member"])
    reviewer_token = _token(702, ["reviewer"])
    try:
        with TestClient(app) as client:
            body = client.post("/workflow/body-profiles", headers=_headers(owner_token, "p1-body-create"), json={"measurements": MEASUREMENTS})
            assert body.status_code == 201, body.text
            profile_id = body.json()["profile_id"]
            assert client.post(f"/workflow/body-profiles/{profile_id}/confirm", headers=_headers(owner_token, "p1-body-confirm"), json={"confirmation_note": "Verified measurements."}).status_code == 200

            asset_ids: list[str] = []
            for category in ("top", "bottom"):
                catalog = client.get(f"/phase-a/catalog?category={category}").json()["garments"][0]
                asset = client.post("/workflow/wardrobe-assets", headers=_headers(owner_token, f"p1-asset-{category}"), json={"name": f"P1 {category}", "category": category, "canonical_garment_id": catalog["garment_id"]})
                assert asset.status_code == 201, asset.text
                asset_id = asset.json()["asset_id"]
                assert client.post(f"/workflow/wardrobe-assets/{asset_id}/approve", headers=_headers(owner_token, f"p1-approve-{category}"), json={}).status_code == 200
                asset_ids.append(asset_id)

            session = client.post("/workflow/styling-sessions", headers=_headers(owner_token, "p1-session-create"), json={"body_profile_id": profile_id, "context": CONTEXT, "wardrobe_asset_ids": asset_ids})
            assert session.status_code == 201, session.text
            session_id = session.json()["session_id"]
            assert client.get("/workflow/styling-sessions", headers={"Authorization": f"Bearer {owner_token}"}).status_code == 200

            decision = client.post(f"/workflow/styling-sessions/{session_id}/outfit-decisions", headers=_headers(owner_token, "p1-decision"), json={"top_k": 1})
            assert decision.status_code == 200, decision.text
            decision_run_id = decision.json()["decision_run_id"]
            outfit_id = decision.json()["decision"]["candidates"][0]["outfit_id"]
            assert client.get(f"/workflow/styling-sessions/{session_id}/outfit-decisions/{decision_run_id}", headers={"Authorization": f"Bearer {owner_token}"}).status_code == 200
            preview = client.post(f"/workflow/styling-sessions/{session_id}/try-on", headers=_headers(owner_token, "p1-preview"), json={"render_mode": "rigged_template", "preview_outfit_id": outfit_id})
            assert preview.status_code == 201, preview.text
            assert preview.json()["render_mode"] == "canonical_proxy"
            session_after_preview = client.get(f"/workflow/styling-sessions/{session_id}", headers={"Authorization": f"Bearer {owner_token}"})
            assert session_after_preview.status_code == 200
            assert session_after_preview.json().get("selected_outfit_id") is None
            selection = client.post(f"/workflow/styling-sessions/{session_id}/select-outfit", headers=_headers(owner_token, "p1-select"), json={"outfit_id": outfit_id})
            assert selection.status_code == 200, selection.text
            assert selection.json()["selected_outfit_id"] == outfit_id
            assert selection.json()["active_decision_run_id"] == decision_run_id

            try_on = client.post(f"/workflow/styling-sessions/{session_id}/try-on", headers=_headers(owner_token, "p1-tryon"), json={"render_mode": "rigged_template"})
            assert try_on.status_code == 201, try_on.text
            assert try_on.json()["render_mode"] == "canonical_proxy"
            assert try_on.json()["quality_status"] == "pending_review"

            feedback = client.post(f"/workflow/styling-sessions/{session_id}/feedback", headers=_headers(owner_token, "p1-feedback"), json={"decision_run_id": decision_run_id, "try_on_run_id": try_on.json()["try_on_run_id"], "target_outfit_id": outfit_id, "sentiment": "dislike", "reason_codes": ["visual_mismatch"], "issue_type": "visual_render", "note": "The proxy needs a reviewer decision.", "confidence": 3})
            assert feedback.status_code == 201, feedback.text
            assert client.get(f"/workflow/styling-sessions/{session_id}/feedback", headers={"Authorization": f"Bearer {owner_token}"}).json()["items"][0]["feedback_id"] == feedback.json()["feedback_id"]

            queue = client.get("/review-tasks?status=open", headers={"Authorization": f"Bearer {reviewer_token}"})
            assert queue.status_code == 200, queue.text
            task = next(item for item in queue.json()["items"] if item["subject_id"] == feedback.json()["feedback_id"])
            claimed = client.post(f"/review-tasks/{task['task_id']}/claim", headers=_headers(reviewer_token, "p1-review-claim"), json={})
            assert claimed.status_code == 200, claimed.text
            completed = client.post(f"/review-tasks/{task['task_id']}/submit-decision", headers=_headers(reviewer_token, "p1-review-decision"), json={"decision": "approve", "reason_codes": ["reproduced"], "reviewer_note": "Issue reproduced and approved for the evaluation dataset."})
            assert completed.status_code == 200, completed.text
            assert completed.json()["status"] == "approved"
            assert client.get(f"/review-tasks/{task['task_id']}/audit-events", headers={"Authorization": f"Bearer {reviewer_token}"}).status_code == 200

            assert db.query(ReviewTask).filter_by(task_id=task["task_id"], status="approved").count() == 1
            assert db.query(EvaluationLabel).filter_by(source_review_task_id=task["task_id"]).count() == 1
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
