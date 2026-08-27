from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("WORKFLOW_AUTH_MODE", "jwt")
os.environ.setdefault("WORKFLOW_JWT_SIGNING_KEY", "scenario-10-item-jwt-secret-minimum-32-bytes")

from app import models
from app.database import Base, get_db
from app.services.garment_catalog import get_garment, load_catalog
from main import app


ACTOR_ID = 910
JWT_SECRET = os.environ["WORKFLOW_JWT_SIGNING_KEY"]
OUT_PATH = BACKEND_ROOT / "reports" / "style_session_10_item_scenario.json"
WARDROBE = [
    ("gar_white_structured_shirt", "Áo sơ mi trắng vai định hình"),
    ("gar_beige_knit_polo", "Áo polo len beige"),
    ("gar_fluid_bohemian_blouse", "Áo blouse bohemian hoạ tiết"),
    ("gar_black_highwaist_trouser", "Quần tây đen cạp cao"),
    ("gar_cream_pleated_midi_skirt", "Chân váy midi xếp ly cream"),
    ("gar_technical_jogger_black", "Quần jogger technical đen"),
    ("gar_navy_blazer", "Blazer navy dáng regular"),
    ("gar_camel_trench_coat", "Trench coat camel"),
    ("gar_black_loafer", "Loafer da đen"),
    ("gar_white_minimal_sneaker", "Sneaker trắng tối giản"),
]
MEASUREMENTS = {
    "height_cm": 170,
    "weight_kg": 60,
    "shoulder_cm": 42,
    "bust_cm": 88,
    "waist_cm": 72,
    "hip_cm": 94,
    "inseam_cm": 78,
}
CONTEXT = {
    "occasion": "meeting",
    "preferred_styles": ["quiet_luxury", "preppy", "business"],
    "intent_tags": ["professional_presence", "confidence", "weather_protection"],
    "formality_target": "business",
    "style_intensity": "subtle",
    "season": "autumn",
    "weather": "mild",
    "mobility_need": "normal",
    "modesty_preference": "standard",
    "required_slots": ["base_top", "bottom"],
    "optional_slots": ["outerwear", "footwear"],
    "availability_policy": "owned_only",
}


def token() -> str:
    return jwt.encode(
        {"sub": str(ACTOR_ID), "roles": ["member"], "exp": datetime.now(timezone.utc) + timedelta(minutes=15)},
        JWT_SECRET,
        algorithm="HS256",
    )


def headers(intent: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token()}",
        "Idempotency-Key": f"scenario-{intent}-{uuid4().hex[:12]}",
        "X-Correlation-ID": f"corr-scenario-{uuid4().hex[:16]}",
        "Content-Type": "application/json",
    }


def post(client: TestClient, path: str, intent: str, payload: dict) -> dict:
    response = client.post(path, headers=headers(intent), json=payload)
    if response.status_code not in {200, 201}:
        raise RuntimeError(f"{path} returned {response.status_code}: {response.text}")
    return response.json()


def main() -> None:
    load_catalog.cache_clear()
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = factory()
    db.add(models.User(id=ACTOR_ID, username="scenario-style-user", email="scenario-style-user@example.test"))
    db.commit()

    def override_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            body = post(client, "/workflow/body-profiles", "body-create", {"measurements": MEASUREMENTS})
            body = post(client, f"/workflow/body-profiles/{body['profile_id']}/confirm", "body-confirm", {"confirmation_note": "Scenario 10-item measurements confirmed."})
            asset_ids: list[str] = []
            seeded_items: list[dict[str, str]] = []
            for catalog_id, label in WARDROBE:
                garment = get_garment(catalog_id)
                asset = post(client, "/workflow/wardrobe-assets", f"asset-create-{catalog_id}", {"name": label, "category": garment.category, "canonical_garment_id": catalog_id})
                active = post(client, f"/workflow/wardrobe-assets/{asset['asset_id']}/approve", f"asset-approve-{catalog_id}", {"approval_note": "Scenario-only approved canonical metadata."})
                asset_ids.append(active["asset_id"])
                seeded_items.append({"asset_id": active["asset_id"], "canonical_garment_id": catalog_id, "name": label, "category": garment.category})

            session = post(client, "/workflow/styling-sessions", "session-create", {"body_profile_id": body["profile_id"], "context": CONTEXT, "wardrobe_asset_ids": asset_ids})
            decision = post(client, f"/workflow/styling-sessions/{session['session_id']}/outfit-decisions", "decision-run", {"top_k": 3})
            candidates = decision["decision"]["candidates"]
            if not candidates:
                raise RuntimeError(f"Scenario unexpectedly abstained: {decision['decision'].get('abstention_reason')}")
            preview = post(client, f"/workflow/styling-sessions/{session['session_id']}/try-on", "tryon-preview", {"render_mode": "rigged_template", "preview_outfit_id": candidates[0]["outfit_id"]})
            before_select = client.get(f"/workflow/styling-sessions/{session['session_id']}", headers={"Authorization": f"Bearer {token()}"})
            if before_select.status_code != 200:
                raise RuntimeError(f"Session read after preview returned {before_select.status_code}: {before_select.text}")
            selected_before = before_select.json().get("selected_outfit_id")
            selected = post(client, f"/workflow/styling-sessions/{session['session_id']}/select-outfit", "outfit-select", {"outfit_id": candidates[0]["outfit_id"]})
            final_try_on = post(client, f"/workflow/styling-sessions/{session['session_id']}/try-on", "tryon-final", {"render_mode": "canonical_proxy"})

            report = {
                "scenario": "isolated FastAPI HTTP StylingSession with a 10-item owned-only wardrobe",
                "wardrobe_count": len(seeded_items),
                "wardrobe": seeded_items,
                "context": CONTEXT,
                "session_id": session["session_id"],
                "decision_run_id": decision["decision_run_id"],
                "candidate_count": len(candidates),
                "candidates": [{
                    "outfit_id": candidate["outfit_id"],
                    "garment_ids": candidate["garment_ids"],
                    "score": candidate["total_score"],
                    "confidence": candidate["confidence"],
                    "style_archetypes": candidate.get("style_archetypes", []),
                    "style_story": candidate.get("style_story", ""),
                    "functional_highlights": candidate.get("functional_highlights", []),
                    "evidence": candidate.get("evidence", []),
                    "evidence_score_total": round(sum(float(item.get("score_delta", 0)) for item in candidate.get("evidence", [])), 2),
                    "tradeoffs": candidate.get("tradeoffs", []),
                    "needs_user_confirmation": candidate.get("needs_user_confirmation", []),
                } for candidate in candidates],
                "preview": {
                    "requested_render_mode": preview["requested_render_mode"],
                    "actual_render_mode": preview["render_mode"],
                    "quality_status": preview["quality_status"],
                    "binding_count": len(preview["asset_bindings"]),
                    "selected_outfit_before_explicit_selection": selected_before,
                    "limitations": preview["limitations"],
                },
                "explicit_selection": {"selected_outfit_id": selected.get("selected_outfit_id"), "session_status": selected["status"]},
                "final_try_on": {
                    "requested_render_mode": final_try_on["requested_render_mode"],
                    "actual_render_mode": final_try_on["render_mode"],
                    "quality_status": final_try_on["quality_status"],
                    "binding_count": len(final_try_on["asset_bindings"]),
                    "limitations": final_try_on["limitations"],
                },
            }
            OUT_PATH.parent.mkdir(exist_ok=True)
            OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


if __name__ == "__main__":
    main()
