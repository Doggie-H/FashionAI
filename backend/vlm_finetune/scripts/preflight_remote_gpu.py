from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import yaml


PLACEHOLDER = "<"


def contains_placeholder(value: Any) -> bool:
    if isinstance(value, str):
        return PLACEHOLDER in value or value.strip() == ""
    if isinstance(value, dict):
        return any(contains_placeholder(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_placeholder(item) for item in value)
    return False


def nvidia_report() -> dict[str, Any]:
    if not shutil.which("nvidia-smi"):
        return {"ok": False, "reason": "nvidia-smi is unavailable"}
    command = ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"]
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        return {"ok": False, "reason": result.stderr.strip() or "nvidia-smi failed"}
    devices = []
    for line in result.stdout.splitlines():
        fields = [part.strip() for part in line.split(",")]
        if len(fields) == 3:
            devices.append({"name": fields[0], "memory_mib": int(fields[1]), "driver_version": fields[2]})
    return {"ok": bool(devices), "devices": devices}


def main() -> None:
    parser = argparse.ArgumentParser(description="Fail-closed preflight before a governed remote VLM fine-tune run.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--min-vram-gb", type=float, default=24.0)
    parser.add_argument("--require-s3", action="store_true")
    args = parser.parse_args()

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []
    checks.append({"name": "config_has_no_placeholders", "ok": not contains_placeholder(config)})
    model = config.get("model", {}) if isinstance(config, dict) else {}
    checks.append({"name": "immutable_model_revision", "ok": bool(model.get("revision")) and not contains_placeholder(model.get("revision"))})
    dataset = config.get("dataset", {}) if isinstance(config, dict) else {}
    checks.append({"name": "dataset_version", "ok": bool(dataset.get("dataset_version")) and not contains_placeholder(dataset.get("dataset_version"))})
    checks.append({"name": "hf_token_present", "ok": bool(os.getenv("HF_TOKEN"))})
    if args.require_s3:
        checks.extend([
            {"name": "s3_bucket_present", "ok": bool(os.getenv("AI_STYLIST_S3_BUCKET"))},
            {"name": "s3_storage_backend", "ok": os.getenv("AI_STYLIST_STORAGE_BACKEND") == "s3"},
        ])

    gpu = nvidia_report()
    checks.append({"name": "nvidia_runtime", "ok": gpu["ok"], "detail": gpu})
    if gpu["ok"]:
        minimum_mib = int(args.min_vram_gb * 1024)
        checks.append({"name": "minimum_gpu_vram", "ok": all(device["memory_mib"] >= minimum_mib for device in gpu["devices"]), "required_mib": minimum_mib})

    report = {"ok": all(check["ok"] for check in checks), "checks": checks, "min_vram_gb": args.min_vram_gb}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
