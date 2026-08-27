"""Read-only runtime probe for local VLM training readiness.

This script never loads a model, downloads weights, starts a training loop, or mutates project data.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


def nvidia_smi() -> dict[str, object]:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return {"ok": False, "reason": "nvidia-smi is unavailable"}
    result = subprocess.run(
        [executable, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return {"ok": False, "reason": result.stderr.strip() or "nvidia-smi failed"}
    return {"ok": True, "devices": result.stdout.strip().splitlines()}


def torch_runtime() -> dict[str, object]:
    try:
        import torch
    except Exception as error:  # pragma: no cover - environment-specific
        return {"ok": False, "reason": f"torch import failed: {error}"}
    result: dict[str, object] = {
        "ok": bool(torch.cuda.is_available()),
        "torch_version": torch.__version__,
        "cuda_build": torch.version.cuda,
    }
    if torch.cuda.is_available():
        device = torch.cuda.get_device_properties(0)
        result["device_name"] = device.name
        result["vram_mib"] = int(device.total_memory / 1024**2)
        result["bf16_supported"] = bool(torch.cuda.is_bf16_supported())
    else:
        result["reason"] = "torch.cuda.is_available() is false"
    return result


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    disk = shutil.disk_usage(project_root)
    torch_report = torch_runtime()
    min_vram_mib = 24 * 1024
    report = {
        "read_only": True,
        "nvidia_smi": nvidia_smi(),
        "torch": torch_report,
        "project_free_disk_gib": round(disk.free / 1024**3, 2),
        "minimum_vram_mib_for_supported_vlm_lora": min_vram_mib,
        "local_training_eligible": bool(torch_report.get("ok")) and int(torch_report.get("vram_mib", 0)) >= min_vram_mib,
        "limitations": [
            "This probe does not load a model or start training.",
            "Passing CUDA alone does not approve training; governed dataset, model license/revision and release gates remain mandatory.",
        ],
    }
    output = project_root / "reports" / "local_vlm_training_runtime_probe.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
