"""Run a deterministic, review-gated mock VLM garment-tagging scenario.

This is not real visual inference. It creates a valid navy T-shirt fixture image,
uses GARMENT_TAGGER_PROVIDER=mock, and proves the workflow boundary from import
through review approval to owned-only outfit ranking and canonical-proxy Try-On.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import jwt
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ["WORKFLOW_AUTH_MODE"] = "jwt"
os.environ["WORKFLOW_JWT_SIGNING_KEY"] = "mock-vlm-tshirt-scenario-jwt-secret-at-least-32-bytes"
os.environ["GARMENT_TAGGER_PROVIDER"] = "mock"

from app import models
from app.database import Base, get_db
from app.services import garment_import
from main import app


MEMBER_ID = 930
REVIEWER_ID = 931
JWT_SECRET = os.environ["WORKFLOW_JWT_SIGNING_KEY"]
REPORT_PATH = BACKEND_ROOT / "reports" / "mock_vlm_tshirt_tagging_scenario.json"
IMAGE_PATH = BACKEND_ROOT / "reports" / "mock_vlm_tshirt_fixture.png"
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
    "occasion": "work",
    "preferred_styles": ["minimal", "classic", "smart_casual"],
    "intent_tags": ["comfort", "all_day", "professional_presence"],
    "formality_target": "smart_casual",
    "style_intensity": "subtle",
    "season": "summer",
    "weather": "hot",
    "mobility_need": "normal",
    "modesty_preference": "standard",
    "required_slots": ["base_top", "bottom"],
    "optional_slots": [],
    "availability_policy": "owned_only",
}


def _token(actor_id: int, roles: list[str]) -> str:
    return jwt.encode(
        {"sub": str(actor_id), "roles": roles, "exp": datetime.now(timezone.utc) + timedelta(minutes=15)},
        JWT_SECRET,
        algorithm="HS256",
    )


def _headers(actor_id: int, roles: list[str], intent: str, *, json_content: bool = True) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {_token(actor_id, roles)}",
        "Idempotency-Key": f"mock-vlm-{intent}-{uuid4().hex[:12]}",
        "X-Correlation-ID": f"corr-mock-vlm-{uuid4().hex[:16]}",
    }
    if json_content:
        headers["Content-Type"] = "application/json"
    return headers


def _post(client: TestClient, path: str, actor_id: int, roles: list[str], intent: str, payload: dict) -> dict:
    response = client.post(path, headers=_headers(actor_id, roles, intent), json=payload)
    if response.status_code not in {200, 201}:
        raise RuntimeError(f"{path} returned {response.status_code}: {response.text}")
    return response.json()


def _make_tshirt_fixture() -> bytes:
    """Create a deterministic visual fixture for upload validation; it is not VLM training data."""
    canvas = Image.new("RGBA", (640, 640), (245, 247, 250, 255))
    draw = ImageDraw.Draw(canvas)
    navy = (32, 62, 117, 255)
    dark = (20, 42, 84, 255)
    # Symmetric short-sleeve crew-neck T-shirt silhouette.
    draw.polygon([(216, 150), (278, 112), (362, 112), (424, 150), (518, 225), (466, 304), (430, 277), (430, 523), (210, 523), (210, 277), (174, 304), (122, 225)], fill=navy, outline=dark, width=8)
    draw.ellipse((278, 110, 362, 171), fill=(245, 247, 250, 255), outline=dark, width=7)
    draw.line((230, 485, 410, 485), fill=(61, 91, 146, 255), width=5)
    draw.text((210, 560), "MOCK NAVY T-SHIRT FIXTURE", fill=(45, 55, 72, 255))
    output = io.BytesIO()
    canvas.convert("RGB").save(output, format="PNG")
    IMAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    IMAGE_PATH.write_bytes(output.getvalue())
    return output.getvalue()


def main() -> None:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = factory()
    previous_upload_dir = garment_import.GARMENT_UPLOAD_DIR
    previous_manifest_dir = garment_import.MANIFEST_DIR
    workspace = tempfile.TemporaryDirectory(prefix="ai-stylist-mock-vlm-")
    garment_import.GARMENT_UPLOAD_DIR = Path(workspace.name) / "uploads" / "garments"
    garment_import.MANIFEST_DIR = Path(workspace.name) / "uploads" / "garment_manifests"

    db.add_all([
        models.User(id=MEMBER_ID, username="mock-vlm-member", email="mock-vlm-member@example.test"),
        models.User(id=REVIEWER_ID, username="mock-vlm-reviewer", email="mock-vlm-reviewer@example.test"),
    ])
    db.commit()

    def override_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    try:
        shirt_bytes = _make_tshirt_fixture()
        with TestClient(app) as client:
            upload = client.post(
                "/phase-b/garment-imports",
                files={"file": ("mock-navy-tshirt.png", shirt_bytes, "image/png")},
                data={"category": "top"},
            )
            if upload.status_code != 200:
                raise RuntimeError(f"Import failed: {upload.status_code}: {upload.text}")
            imported = upload.json()["manifest"]

            semantic = client.post(f"/phase-b/garment-imports/{imported['import_id']}/semantic-tags")
            if semantic.status_code != 200:
                raise RuntimeError(f"Mock semantic tagging failed: {semantic.status_code}: {semantic.text}")
            semantic_manifest = semantic.json()["manifest"]
            tagging = semantic_manifest["analysis"]["semantic_tagging"]
            if tagging["provider"] != "mock" or tagging["status"] != "needs_review":
                raise RuntimeError("Mock scenario did not produce an explicitly review-gated mock tagging draft")
            structural_draft = tagging.get("structural_profile")
            if not isinstance(structural_draft, dict) or structural_draft.get("neckline") != "crew":
                raise RuntimeError("Mock scenario did not produce the expected visible structural draft")

            user_asset = _post(client, "/workflow/wardrobe-assets", MEMBER_ID, ["member"], "user-asset-create", {
                "name": "Mock navy T-shirt",
                "category": "top",
                "import_id": imported["import_id"],
            })
            tasks = client.get(
                "/review-tasks?status=open&review_type=garment_metadata",
                headers={"Authorization": f"Bearer {_token(REVIEWER_ID, ['reviewer'])}"},
            )
            if tasks.status_code != 200:
                raise RuntimeError(f"Review task list failed: {tasks.status_code}: {tasks.text}")
            task = next((item for item in tasks.json()["items"] if item["subject_revision_id"] == user_asset["revision_id"]), None)
            if task is None:
                raise RuntimeError("Garment metadata review task was not opened")
            claimed = _post(client, f"/review-tasks/{task['task_id']}/claim", REVIEWER_ID, ["reviewer"], "review-claim", {})
            if claimed["status"] != "claimed":
                raise RuntimeError("Review task was not claimed")
            approved_task = _post(client, f"/review-tasks/{task['task_id']}/submit-decision", REVIEWER_ID, ["reviewer"], "review-approve", {
                "decision": "approve",
                "reason_codes": ["mock_fixture_e2e_verified"],
                "reviewer_note": "Mock fixture tags are approved only to validate workflow gating and provenance.",
            })
            if approved_task["status"] != "approved":
                raise RuntimeError("Review task was not approved")
            proposals_response = client.get(
                "/taxonomy-learning/proposals?status=proposed",
                headers={"Authorization": f"Bearer {_token(REVIEWER_ID, ['reviewer'])}"},
            )
            if proposals_response.status_code != 200:
                raise RuntimeError(f"Taxonomy proposal list failed: {proposals_response.status_code}: {proposals_response.text}")
            taxonomy_proposals = proposals_response.json()["items"]
            if not taxonomy_proposals:
                raise RuntimeError("Approved garment review did not derive any governed taxonomy proposal")

            active_user_asset = client.get(
                f"/workflow/wardrobe-assets/{user_asset['asset_id']}",
                headers={"Authorization": f"Bearer {_token(MEMBER_ID, ['member'])}"},
            )
            if active_user_asset.status_code != 200:
                raise RuntimeError(f"Active asset read failed: {active_user_asset.status_code}: {active_user_asset.text}")
            active_user_asset = active_user_asset.json()
            user_garment_id = active_user_asset["semantic_metadata"]["garment_id"]
            approved_structure = active_user_asset.get("structural_profile")
            if not isinstance(approved_structure, dict) or approved_structure.get("shoulder_construction") != "set_in":
                raise RuntimeError("Reviewer approval did not persist the structural profile on the active wardrobe asset")

            skirt = _post(client, "/workflow/wardrobe-assets", MEMBER_ID, ["member"], "skirt-create", {
                "name": "Canonical cream pleated midi skirt",
                "category": "bottom",
                "canonical_garment_id": "gar_cream_pleated_midi_skirt",
            })
            active_skirt = _post(client, f"/workflow/wardrobe-assets/{skirt['asset_id']}/approve", MEMBER_ID, ["member"], "skirt-approve", {
                "approval_note": "Canonical scenario garment approved.",
            })
            body = _post(client, "/workflow/body-profiles", MEMBER_ID, ["member"], "body-create", {"measurements": MEASUREMENTS})
            active_body = _post(client, f"/workflow/body-profiles/{body['profile_id']}/confirm", MEMBER_ID, ["member"], "body-confirm", {"confirmation_note": "Mock scenario measurements confirmed."})
            session = _post(client, "/workflow/styling-sessions", MEMBER_ID, ["member"], "session-create", {
                "body_profile_id": active_body["profile_id"],
                "context": CONTEXT,
                "wardrobe_asset_ids": [active_user_asset["asset_id"], active_skirt["asset_id"]],
            })
            decision = _post(client, f"/workflow/styling-sessions/{session['session_id']}/outfit-decisions", MEMBER_ID, ["member"], "decision-run", {"top_k": 1})
            candidate = decision["decision"]["candidates"][0]
            if user_garment_id not in candidate["garment_ids"]:
                raise RuntimeError("Decision did not use the reviewer-approved user garment ID")
            evidence_total = round(sum(float(item["score_delta"]) for item in candidate["evidence"]), 2)
            if evidence_total != candidate["total_score"]:
                raise RuntimeError("Decision evidence total does not match candidate total score")
            preview = _post(client, f"/workflow/styling-sessions/{session['session_id']}/try-on", MEMBER_ID, ["member"], "tryon-preview", {
                "render_mode": "canonical_proxy",
                "preview_outfit_id": candidate["outfit_id"],
            })
            user_binding = next((binding for binding in preview["asset_bindings"] if binding["asset_id"] == active_user_asset["asset_id"]), None)
            if user_binding is None:
                raise RuntimeError("Try-On did not map semantic user garment ID back to the wardrobe asset")
            if user_binding.get("structural_profile", {}).get("torso_length") != "hip":
                raise RuntimeError("Try-On binding did not carry the reviewer-approved structural profile")

            report = {
                "scenario": "isolated FastAPI HTTP mock semantic VLM tagging with a generated navy T-shirt fixture",
                "mock_disclosure": "Provider mock returns deterministic test data; this report does not demonstrate real visual VLM inference.",
                "fixture_image": str(IMAGE_PATH.relative_to(BACKEND_ROOT)),
                "import_id": imported["import_id"],
                "source_image_sha256": imported["source_image_sha256"],
                "tagging": {
                    "status": tagging["status"],
                    "provider": tagging["provider"],
                    "model_id": tagging["model_id"],
                    "model_revision": tagging["model_revision"],
                    "candidate_metadata": tagging["candidate_metadata"],
                    "structural_profile": tagging["structural_profile"],
                    "evidence": tagging["evidence"],
                    "limitations": tagging["limitations"],
                },
                "review": {"task_id": task["task_id"], "status": approved_task["status"], "reason_codes": approved_task["reason_codes"]},
                "taxonomy_learning": {
                    "proposal_count": len(taxonomy_proposals),
                    "proposals": taxonomy_proposals,
                    "disclosure": "Proposals are derived automatically from approved reviews but cannot change catalog or ranker without later evaluation and admin release.",
                },
                "active_user_asset": {"asset_id": active_user_asset["asset_id"], "semantic_garment_id": user_garment_id, "semantic_metadata": active_user_asset["semantic_metadata"], "structural_profile": approved_structure},
                "decision": {"outfit_id": candidate["outfit_id"], "garment_ids": candidate["garment_ids"], "score": candidate["total_score"], "evidence_total": evidence_total, "style_archetypes": candidate["style_archetypes"], "tradeoffs": candidate["tradeoffs"]},
                "preview": {"requested_mode": preview["requested_render_mode"], "actual_mode": preview["render_mode"], "quality_status": preview["quality_status"], "asset_bindings": preview["asset_bindings"], "limitations": preview["limitations"]},
            }
            REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
            REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        app.dependency_overrides.clear()
        garment_import.GARMENT_UPLOAD_DIR = previous_upload_dir
        garment_import.MANIFEST_DIR = previous_manifest_dir
        workspace.cleanup()
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


if __name__ == "__main__":
    main()
