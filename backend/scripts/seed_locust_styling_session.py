from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import models
from app.database import SessionLocal
from app.phase_a_schemas import RawMeasurementsV1
from app.services import workflow_service
from app.workflow_models import BodyProfileRevision, WardrobeAsset
from app.workflow_schemas import ConfirmBodyProfileCommandV1, CreateBodyProfileCommandV1

MEASUREMENTS = {
    "height_cm": 170,
    "weight_kg": 60,
    "shoulder_cm": 42,
    "bust_cm": 88,
    "waist_cm": 72,
    "hip_cm": 94,
    "inseam_cm": 78,
    "shoulder_slope": "straight",
    "chest_profile": "full",
    "leg_alignment": "straight",
}


def main() -> None:
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.username == "locust-load-user").first()
        if user is None:
            user = models.User(username="locust-load-user", email="locust-load-user@example.test")
            db.add(user)
            db.commit()
            db.refresh(user)

        profile = (
            db.query(BodyProfileRevision)
            .filter(BodyProfileRevision.owner_id == user.id, BodyProfileRevision.status == "active")
            .order_by(BodyProfileRevision.created_at.desc())
            .first()
        )
        if profile is None:
            created = workflow_service.create_body_profile(
                db,
                CreateBodyProfileCommandV1(
                    actor_id=user.id,
                    idempotency_key=f"locust-seed-body-create-{user.id}",
                    correlation_id=f"corr-locust-seed-body-{user.id}",
                    measurements=RawMeasurementsV1.model_validate(MEASUREMENTS),
                ),
            )
            profile = workflow_service.confirm_body_profile(
                db,
                created.profile_id,
                ConfirmBodyProfileCommandV1(
                    actor_id=user.id,
                    idempotency_key=f"locust-seed-body-confirm-{user.id}",
                    correlation_id=f"corr-locust-seed-confirm-{user.id}",
                    confirmation_note="Load-test seed profile confirmed.",
                ),
            )

        active_assets = (
            db.query(WardrobeAsset)
            .filter(WardrobeAsset.owner_id == user.id, WardrobeAsset.status == "active")
            .order_by(WardrobeAsset.asset_id.asc())
            .all()
        )
        print(json.dumps({
            "LOCUST_LEGACY_ACTOR_ID": user.id,
            "LOCUST_BODY_PROFILE_ID": profile.profile_id,
            "LOCUST_WARDROBE_ASSET_IDS": ",".join(asset.asset_id for asset in active_assets),
            "note": "Run only in local demo mode unless you replace LOCUST_LEGACY_ACTOR_ID with a valid JWT in LOCUST_JWT.",
        }, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
