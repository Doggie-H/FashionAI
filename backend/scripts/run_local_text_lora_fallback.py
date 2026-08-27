"""One-step CUDA LoRA fallback for a cached 0.5B text model.

It exists solely to validate local CUDA, backward pass and adapter persistence
when the cached VLM cannot use 4-bit quantization on this Windows/CUDA runtime.
It is explicitly not a VLM or fashion-training experiment.
"""

from __future__ import annotations

import gc
import json
import os
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

BACKEND_ROOT = Path(__file__).resolve().parents[1]
MODEL_ROOT = Path.home() / ".cache" / "huggingface" / "hub" / "models--Qwen--Qwen2.5-0.5B-Instruct" / "snapshots"
REPORT_PATH = BACKEND_ROOT / "reports" / "local_text_lora_fallback.json"
ADAPTER_DIR = BACKEND_ROOT / "reports" / "local_text_lora_fallback_adapter"
MIN_FREE_MIB = 2400


def _snapshot() -> Path | None:
    snapshots = sorted(path for path in MODEL_ROOT.iterdir() if path.is_dir()) if MODEL_ROOT.is_dir() else []
    return snapshots[0] if snapshots else None


def _write(report: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main() -> None:
    model_path = _snapshot()
    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "synthetic_one_step_text_lora_fallback",
        "production_training": False,
        "is_vlm": False,
        "data_disclosure": "Uses one synthetic text string only to verify CUDA/LoRA/optimizer wiring. It contains no user wardrobe images, reviewer history, or fashion training data.",
        "limitations": [
            "This is a text-only CUDA fallback after the VLM 4-bit stack failed on CUDA 13.2 bitsandbytes Windows binary availability.",
            "No visual understanding, garment tagging, taxonomy improvement, or fashion-expert capability is tested or produced.",
        ],
        "lora": {"r": 2, "alpha": 4, "target_modules": ["q_proj", "v_proj"]},
    }
    if model_path is None:
        report.update({"ok": False, "status": "blocked", "reason": "cached Qwen2.5-0.5B snapshot is missing"})
        _write(report)
        return
    report["model_path"] = str(model_path)
    try:
        import torch
        from peft import LoraConfig, get_peft_model
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if not torch.cuda.is_available():
            report.update({"ok": False, "status": "blocked", "reason": "torch CUDA is unavailable"})
            _write(report)
            return
        free_bytes, total_bytes = torch.cuda.mem_get_info()
        report["gpu_before"] = {"name": torch.cuda.get_device_name(0), "free_mib": round(free_bytes / 1024**2, 1), "total_mib": round(total_bytes / 1024**2, 1)}
        if free_bytes < MIN_FREE_MIB * 1024**2:
            report.update({"ok": False, "status": "blocked", "reason": "insufficient free VRAM for safe 0.5B fp16 fallback"})
            _write(report)
            return

        tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            local_files_only=True,
            torch_dtype=torch.float16,
            device_map={"": 0},
            low_cpu_mem_usage=True,
        )
        model.config.use_cache = False
        model = get_peft_model(model, LoraConfig(
            r=2,
            lora_alpha=4,
            lora_dropout=0.0,
            target_modules=["q_proj", "v_proj"],
            bias="none",
            task_type="CAUSAL_LM",
        ))
        model.train()
        inputs = tokenizer("Synthetic CUDA LoRA smoke test. Output exactly: technical adapter check.", return_tensors="pt", truncation=True, max_length=64)
        inputs = {key: value.to("cuda:0") for key, value in inputs.items()}
        labels = inputs["input_ids"].clone()
        optimizer = torch.optim.AdamW((parameter for parameter in model.parameters() if parameter.requires_grad), lr=1e-5)
        optimizer.zero_grad(set_to_none=True)
        output = model(**inputs, labels=labels)
        if not torch.isfinite(output.loss):
            raise RuntimeError("fallback produced non-finite loss")
        output.loss.backward()
        optimizer.step()
        ADAPTER_DIR.mkdir(parents=True, exist_ok=True)
        model.save_pretrained(ADAPTER_DIR)
        free_after, total_after = torch.cuda.mem_get_info()
        report.update({
            "ok": True,
            "status": "completed",
            "loss": float(output.loss.detach().cpu()),
            "adapter_dir": str(ADAPTER_DIR),
            "trainable_parameters": sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad),
            "gpu_after": {
                "free_mib": round(free_after / 1024**2, 1),
                "total_mib": round(total_after / 1024**2, 1),
                "max_allocated_mib": round(torch.cuda.max_memory_allocated() / 1024**2, 1),
                "max_reserved_mib": round(torch.cuda.max_memory_reserved() / 1024**2, 1),
            },
        })
    except Exception as error:
        report.update({"ok": False, "status": "blocked_or_failed", "reason": str(error)[:1000], "traceback": traceback.format_exc(limit=8)})
    finally:
        try:
            del model  # type: ignore[name-defined]
        except Exception:
            pass
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass
        _write(report)


if __name__ == "__main__":
    main()
