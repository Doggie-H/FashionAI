from __future__ import annotations

import importlib.util
import json
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = BACKEND_ROOT / "vlm_finetune" / "scripts" / "validate_manifest.py"
SCHEMA_PATH = BACKEND_ROOT / "vlm_finetune" / "schemas" / "style_vlm_sample.schema.json"
spec = importlib.util.spec_from_file_location("validate_manifest", MODULE_PATH)
assert spec and spec.loader
validator_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator_module)


def _sample(sample_id: str, split: str, owner: str, wardrobe: str, *, withdrawn: bool = False) -> dict:
    return {
        "sample_id": sample_id,
        "dataset_version": "fashion-style-v1",
        "split": split,
        "owner_group_id": owner,
        "wardrobe_group_id": wardrobe,
        "consent": {
            "training_allowed": True,
            "captured_at": "2026-08-26T00:00:00Z",
            "retention_policy_id": "retention-v1",
            "withdrawn_at": "2026-08-27T00:00:00Z" if withdrawn else None,
        },
        "image": {"s3_key": f"ai-stylist/fine-tune/{sample_id}.jpg", "sha256": "a" * 64, "mime_type": "image/jpeg"},
        "messages": [{"role": "user", "content": "Phân loại item."}, {"role": "assistant", "content": "top"}],
        "review": {"status": "approved", "rubric_version": "style-rubric-v1", "reviewer_ids": ["reviewer-1"], "disagreement": False},
        "source": {"license_status": "user_consented", "provenance": "consented test fixture"},
    }


def _write(path: Path, sample: dict) -> None:
    path.write_text(json.dumps(sample) + "\n", encoding="utf-8")


def test_manifest_validator_accepts_isolated_approved_consent_samples(tmp_path: Path):
    manifests = {}
    for split in ("train", "eval", "test"):
        path = tmp_path / f"{split}.jsonl"
        _write(path, _sample(f"stylevlm_{split}abcdef1234", split, f"owner-{split}", f"wardrobe-{split}"))
        manifests[split] = path
    report = validator_module.validate(manifests, SCHEMA_PATH)
    assert report["ok"] is True
    assert report["sample_count"] == 3


def test_manifest_validator_rejects_cross_split_owner_and_withdrawn_sample(tmp_path: Path):
    train = tmp_path / "train.jsonl"
    evaluate = tmp_path / "eval.jsonl"
    test = tmp_path / "test.jsonl"
    _write(train, _sample("stylevlm_trainabcdef1234", "train", "owner-shared", "wardrobe-train", withdrawn=True))
    _write(evaluate, _sample("stylevlm_evalabcdef12345", "eval", "owner-shared", "wardrobe-eval"))
    _write(test, _sample("stylevlm_testabcdef12345", "test", "owner-test", "wardrobe-test"))
    report = validator_module.validate({"train": train, "eval": evaluate, "test": test}, SCHEMA_PATH)
    assert report["ok"] is False
    assert any("withdrawn sample" in error for error in report["errors"])
    assert any("owner_group_id" in error and "prevent leakage" in error for error in report["errors"])
