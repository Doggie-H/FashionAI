from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, BACKEND_ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


trainer = _module("train_lora_vlm", "vlm_finetune/scripts/train_lora_vlm.py")
stager = _module("stage_dataset_from_s3", "vlm_finetune/scripts/stage_dataset_from_s3.py")


def _config() -> dict:
    return {
        "run": {"run_name": "approved-pilot", "output_prefix": "ai-stylist/fine-tune/runs/approved-pilot"},
        "model": {"id": "licensed-org/example-vlm", "revision": "frozen-commit-abcdef", "dtype": "bfloat16"},
        "adapter": {"method": "lora", "r": 8, "alpha": 16, "dropout": 0.05, "target_modules": ["q_proj"]},
        "dataset": {"dataset_version": "fashion-v1"},
        "training": {"epochs": 1, "learning_rate": 0.0001, "per_device_train_batch_size": 1, "gradient_accumulation_steps": 1, "gradient_checkpointing": True, "logging_steps": 1, "eval_strategy": "steps", "eval_steps": 1, "save_strategy": "steps", "save_steps": 1, "save_total_limit": 1, "warmup_ratio": 0.0},
    }


def _prepared_record(sample_id: str, image_path: str) -> dict:
    return {"sample_id": sample_id, "image_path": image_path, "messages": [{"role": "user", "content": "Classify."}, {"role": "assistant", "content": "top"}]}


def test_dry_run_accepts_complete_prepared_split_without_importing_cuda_stack(tmp_path: Path):
    for split in ("train", "eval", "test"):
        image = tmp_path / f"{split}.jpg"
        image.write_bytes(b"test-image")
        (tmp_path / f"{split}.jsonl").write_text(json.dumps(_prepared_record(f"stylevlm_{split}abc123456", image.name)) + "\n", encoding="utf-8")
    report = trainer._dry_run(_config(), tmp_path)
    assert report["ok"] is True
    assert report["split_counts"] == {"train": 1, "eval": 1, "test": 1}


def test_dry_run_rejects_unresolved_model_placeholder(tmp_path: Path):
    for split in ("train", "eval", "test"):
        image = tmp_path / f"{split}.jpg"
        image.write_bytes(b"test-image")
        (tmp_path / f"{split}.jsonl").write_text(json.dumps(_prepared_record(f"stylevlm_{split}abc123456", image.name)) + "\n", encoding="utf-8")
    config = _config()
    config["model"]["revision"] = "<immutable-model-revision>"
    with pytest.raises(ValueError, match="model.revision"):
        trainer._dry_run(config, tmp_path)


def test_stage_preflight_rejects_withdrawn_or_disputed_samples():
    records = [{"sample_id": "stylevlm_abcdef123456", "split": "train", "consent": {"training_allowed": True, "withdrawn_at": "2026-08-26T00:00:00Z"}, "review": {"status": "approved", "disagreement": True}}]
    errors = stager._preflight(records, "train")
    assert any("consent is not eligible" in error for error in errors)
    assert any("reviewer status is not eligible" in error for error in errors)
