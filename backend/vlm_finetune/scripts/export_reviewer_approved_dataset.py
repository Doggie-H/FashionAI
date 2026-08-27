"""Export governed VLM manifests from reviewer-approved garment revisions.

The exporter is intentionally fail-closed: it never treats a completed review as
training consent. A separate private consent ledger supplies the storage key and
retention/provenance evidence per immutable revision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.workflow_models import GarmentAssetRevision, ReviewTask, WardrobeAsset


SYSTEM_MESSAGE = (
    "You are a garment perception assistant. Return only the approved visible garment metadata "
    "and structural cues. Never infer hidden construction, measurements, physical fit, or 3D mesh truth."
)


def _load_ledger(path: Path) -> dict[str, dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("consent ledger must be a JSON object keyed by revision_id")
    return {key: item for key, item in value.items() if isinstance(key, str) and isinstance(item, dict)}


def _split_for_owner(owner_id: int) -> str:
    """Keep every wardrobe belonging to one owner in one split."""
    bucket = int(hashlib.sha256(f"owner:{owner_id}".encode()).hexdigest()[:8], 16) % 100
    if bucket < 80:
        return "train"
    if bucket < 90:
        return "eval"
    return "test"


def _mime_from_uri(uri: object) -> str | None:
    lowered = str(uri or "").lower()
    if lowered.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if lowered.endswith(".png"):
        return "image/png"
    if lowered.endswith(".webp"):
        return "image/webp"
    return None


def _valid_ledger_entry(entry: dict[str, Any]) -> str | None:
    if entry.get("training_allowed") is not True:
        return "training_consent_missing"
    if entry.get("withdrawn_at"):
        return "consent_withdrawn"
    if not isinstance(entry.get("retention_policy_id"), str) or len(entry["retention_policy_id"]) < 3:
        return "retention_policy_missing"
    if not isinstance(entry.get("captured_at"), str):
        return "consent_timestamp_missing"
    if not isinstance(entry.get("s3_key"), str) or not entry["s3_key"].startswith("ai-stylist/"):
        return "approved_s3_key_missing"
    source = entry.get("source")
    if not isinstance(source, dict) or source.get("license_status") not in {"user_consented", "licensed_internal", "licensed_external"}:
        return "source_license_missing"
    if not isinstance(source.get("provenance"), str) or len(source["provenance"]) < 3:
        return "source_provenance_missing"
    return None


def _sample_for_revision(
    revision: GarmentAssetRevision,
    asset: WardrobeAsset,
    review: ReviewTask,
    consent: dict[str, Any],
    dataset_version: str,
) -> tuple[dict[str, Any] | None, str | None]:
    failure = _valid_ledger_entry(consent)
    if failure:
        return None, failure
    manifest = revision.manifest_snapshot if isinstance(revision.manifest_snapshot, dict) else {}
    source_uri = manifest.get("source_image_uri")
    source_sha256 = manifest.get("source_image_sha256")
    mime_type = _mime_from_uri(source_uri)
    if not isinstance(source_sha256, str) or len(source_sha256) != 64:
        return None, "source_sha256_missing"
    if mime_type is None:
        return None, "unsupported_image_mime"
    if not isinstance(revision.semantic_metadata, dict):
        return None, "approved_semantic_metadata_missing"
    if review.assignee_actor_id is None:
        return None, "reviewer_identity_missing"
    approved_payload = {
        "semantic_metadata": revision.semantic_metadata,
        "structural_profile": revision.structural_profile,
        "review_task_id": review.task_id,
        "rubric_version": review.checklist_version,
    }
    sample_id = "stylevlm_" + hashlib.sha256(revision.revision_id.encode()).hexdigest()[:24]
    return {
        "sample_id": sample_id,
        "dataset_version": dataset_version,
        "split": _split_for_owner(asset.owner_id),
        "owner_group_id": f"owner_{asset.owner_id}",
        "wardrobe_group_id": f"wardrobe_{asset.asset_id}",
        "consent": {
            "training_allowed": True,
            "captured_at": consent["captured_at"],
            "retention_policy_id": consent["retention_policy_id"],
            "withdrawn_at": None,
        },
        "image": {"s3_key": consent["s3_key"], "sha256": source_sha256, "mime_type": mime_type},
        "messages": [
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": "Analyze this single garment image using the governed fashion taxonomy and visible structural-cue contract."},
            {"role": "assistant", "content": json.dumps(approved_payload, ensure_ascii=False, sort_keys=True)},
        ],
        "review": {
            "status": "approved",
            "rubric_version": review.checklist_version,
            "reviewer_ids": [f"reviewer_{review.assignee_actor_id}"],
            "disagreement": False,
        },
        "source": consent["source"],
    }, None


def export_dataset(database_url: str, consent_ledger: Path, output_dir: Path, dataset_version: str) -> dict[str, Any]:
    if not dataset_version or "<" in dataset_version:
        raise ValueError("dataset_version must be a real immutable version name")
    ledger = _load_ledger(consent_ledger)
    engine = create_engine(database_url, connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {})
    session = sessionmaker(bind=engine)()
    excluded: Counter[str] = Counter()
    records: list[dict[str, Any]] = []
    try:
        reviews = session.query(ReviewTask).filter(
            ReviewTask.review_type == "garment_metadata",
            ReviewTask.status == "approved",
            ReviewTask.decision == "approve",
        ).all()
        seen_revisions: set[str] = set()
        for review in reviews:
            if not review.subject_revision_id or review.subject_revision_id in seen_revisions:
                continue
            seen_revisions.add(review.subject_revision_id)
            revision = session.query(GarmentAssetRevision).filter(GarmentAssetRevision.revision_id == review.subject_revision_id).first()
            if revision is None or revision.status != "active":
                excluded["active_revision_missing"] += 1
                continue
            asset = session.query(WardrobeAsset).filter(WardrobeAsset.asset_id == revision.asset_id).first()
            if asset is None or asset.status != "active":
                excluded["active_asset_missing"] += 1
                continue
            consent = ledger.get(revision.revision_id)
            if consent is None:
                excluded["training_consent_missing"] += 1
                continue
            sample, reason = _sample_for_revision(revision, asset, review, consent, dataset_version)
            if sample is None:
                excluded[reason or "unknown"] += 1
                continue
            records.append(sample)
    finally:
        session.close()

    output_dir.mkdir(parents=True, exist_ok=True)
    split_records = {split: [record for record in records if record["split"] == split] for split in ("train", "eval", "test")}
    for split, rows in split_records.items():
        (output_dir / f"{split}.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_version": dataset_version,
        "input_reviewed_revisions": len(records) + sum(excluded.values()),
        "exported_records": len(records),
        "split_counts": {split: len(rows) for split, rows in split_records.items()},
        "excluded": dict(sorted(excluded.items())),
        "training_ready": bool(records) and all(split_records.values()),
        "limitations": [
            "Only reviewer-approved active garment revisions with an independent training-consent ledger are exported.",
            "The exporter does not upload images, download images, alter reviews, or grant training consent.",
            "A non-empty manifest is not a release approval; validate and evaluate before any fine-tune.",
        ],
    }
    (output_dir / "export_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Export reviewer-approved, consent-governed VLM dataset manifests.")
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--consent-ledger", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dataset-version", required=True)
    args = parser.parse_args()
    print(json.dumps(export_dataset(args.database_url, args.consent_ledger, args.output_dir, args.dataset_version), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
