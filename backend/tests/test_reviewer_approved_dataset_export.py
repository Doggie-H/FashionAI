from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401 - registers users table for workflow foreign keys
from app.database import Base
from app.workflow_models import GarmentAssetRevision, ReviewTask, WardrobeAsset


SCRIPT = Path(__file__).resolve().parents[1] / "vlm_finetune" / "scripts" / "export_reviewer_approved_dataset.py"
spec = importlib.util.spec_from_file_location("reviewer_dataset_export", SCRIPT)
assert spec and spec.loader
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


def _owner_for(split: str) -> int:
    for owner_id in range(1, 10_000):
        if exporter._split_for_owner(owner_id) == split:
            return owner_id
    raise AssertionError(f"no owner found for {split}")


def _insert_approved(session, owner_id: int, ordinal: int) -> tuple[str, dict[str, object]]:
    asset_id = f"asset_{ordinal}"
    revision_id = f"rev_{ordinal}"
    task_id = f"task_{ordinal}"
    asset = WardrobeAsset(asset_id=asset_id, owner_id=owner_id, name=f"Garment {ordinal}", category="top", active_revision_id=revision_id, status="active")
    revision = GarmentAssetRevision(
        revision_id=revision_id,
        asset_id=asset_id,
        revision=1,
        status="active",
        import_id=f"imp_{ordinal:012d}"[-16:],
        manifest_snapshot={"source_image_uri": f"/uploads/garments/item-{ordinal}.png", "source_image_sha256": "a" * 64},
        semantic_metadata={"garment_id": f"gar_user_{ordinal}", "category": "top", "styles": ["minimal"]},
        structural_profile={"neckline": "crew", "source_views": ["front"]},
        quality_summary={"eligible_for_decision": True},
    )
    review = ReviewTask(
        task_id=task_id,
        owner_id=owner_id,
        subject_type="garment_asset",
        subject_id=asset_id,
        subject_revision_id=revision_id,
        review_type="garment_metadata",
        priority="normal",
        status="approved",
        assignee_actor_id=900 + ordinal,
        evidence_snapshot={},
        checklist_version="garment-rubric-v1",
        decision="approve",
        reason_codes=["visible-cues-confirmed"],
        completed_at=datetime.now(timezone.utc),
    )
    session.add_all([asset, revision, review])
    return revision_id, {
        "training_allowed": True,
        "captured_at": "2026-08-27T00:00:00Z",
        "retention_policy_id": "retain-v1",
        "s3_key": f"ai-stylist/training/item-{ordinal}.png",
        "source": {"license_status": "user_consented", "provenance": "explicit testing consent"},
    }


def test_export_reviewer_approved_dataset_is_consent_gated_and_group_split(tmp_path: Path):
    database = tmp_path / "workflow.db"
    engine = create_engine(f"sqlite:///{database}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    ledger = {}
    for ordinal, split in enumerate(("train", "eval", "test"), start=1):
        revision_id, consent = _insert_approved(session, _owner_for(split), ordinal)
        ledger[revision_id] = consent
    missing_revision, _ = _insert_approved(session, 7777, 99)
    session.commit()
    session.close()

    ledger_path = tmp_path / "consent-ledger.json"
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
    output_dir = tmp_path / "export"
    report = exporter.export_dataset(f"sqlite:///{database}", ledger_path, output_dir, "fashion-reviewed-v1")

    assert report["training_ready"] is True
    assert report["split_counts"] == {"train": 1, "eval": 1, "test": 1}
    assert report["excluded"] == {"training_consent_missing": 1}
    exported_owner_groups = []
    for split in ("train", "eval", "test"):
        rows = [json.loads(line) for line in (output_dir / f"{split}.jsonl").read_text(encoding="utf-8").splitlines() if line]
        assert len(rows) == 1
        assert rows[0]["split"] == split
        assert rows[0]["review"]["status"] == "approved"
        assert rows[0]["consent"]["training_allowed"] is True
        exported_owner_groups.append(rows[0]["owner_group_id"])
    assert len(set(exported_owner_groups)) == 3
    assert missing_revision not in ledger
