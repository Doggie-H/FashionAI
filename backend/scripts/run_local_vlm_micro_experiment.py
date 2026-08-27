"""One-step, synthetic-only local VLM LoRA micro-experiment.

This is a CUDA/quantization/adapter smoke test. It is not a governed fashion
fine-tune and must never be used as a production model or evaluation result.
"""

from __future__ import annotations

import gc
import json
import os
import shutil
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Enforce cache-only behaviour before importing Hugging Face libraries.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

BACKEND_ROOT = Path(__file__).resolve().parents[1]
CACHE_MODEL = Path(os.environ.get(
    "LOCAL_MICRO_VLM_PATH",
    str(Path.home() / ".cache" / "huggingface" / "hub" / "models--HuggingFaceTB--SmolVLM-Instruct" / "snapshots" / "81cd9a775a4d644f2faf4e7becff4559b46b14c7"),
))
FIXTURE_IMAGE = BACKEND_ROOT / "reports" / "mock_vlm_tshirt_fixture.png"
REPORT_PATH = BACKEND_ROOT / "reports" / "local_vlm_micro_experiment.json"
ADAPTER_DIR = BACKEND_ROOT / "reports" / "local_vlm_micro_experiment_adapter"
MIN_FREE_MIB = 2800


def _write(report: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def _base_report() -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "synthetic_one_step_local_micro_experiment",
        "production_training": False,
        "data_disclosure": "Uses one generated navy T-shirt fixture solely to test CUDA/model/LoRA/optimizer wiring; it is not a reviewer-approved fashion dataset.",
        "model_path": str(CACHE_MODEL),
        "adapter_target_modules": ["q_proj", "k_proj"],
        "lora": {"r": 2, "alpha": 4, "dropout": 0.0},
        "limits": {"steps": 1, "batch_size": 1, "load_in_4bit": True, "minimum_free_mib": MIN_FREE_MIB},
        "limitations": [
            "No production model, benchmark, fashion-quality claim, or physical-fit claim may be derived from this micro-experiment.",
            "This micro-experiment must not be used to replace reviewer-approved train/eval/test data or remote VLM evaluation.",
            "It is cache-only and never downloads a model or contacts a registry.",
        ],
    }


def main() -> None:
    report = _base_report()
    if not CACHE_MODEL.is_dir():
        report.update({"ok": False, "status": "blocked", "reason": "cached SmolVLM snapshot is missing"})
        _write(report)
        return
    if not FIXTURE_IMAGE.is_file():
        report.update({"ok": False, "status": "blocked", "reason": "synthetic fixture image is missing"})
        _write(report)
        return

    try:
        import torch
        from PIL import Image
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        from transformers import AutoModelForImageTextToText, AutoProcessor, BitsAndBytesConfig

        if not torch.cuda.is_available():
            report.update({"ok": False, "status": "blocked", "reason": "torch CUDA is unavailable"})
            _write(report)
            return
        free_bytes, total_bytes = torch.cuda.mem_get_info()
        report["gpu_before"] = {
            "name": torch.cuda.get_device_name(0),
            "free_mib": round(free_bytes / 1024**2, 1),
            "total_mib": round(total_bytes / 1024**2, 1),
        }
        if free_bytes < MIN_FREE_MIB * 1024**2:
            report.update({"ok": False, "status": "blocked", "reason": "insufficient free VRAM before loading the 4-bit micro-experiment"})
            _write(report)
            return

        quantization = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )
        processor = AutoProcessor.from_pretrained(CACHE_MODEL, local_files_only=True)
        model = AutoModelForImageTextToText.from_pretrained(
            CACHE_MODEL,
            local_files_only=True,
            quantization_config=quantization,
            device_map={"": 0},
            low_cpu_mem_usage=True,
        )
        model.config.use_cache = False
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
        if hasattr(model, "gradient_checkpointing_enable"):
            model.gradient_checkpointing_enable()
        model = get_peft_model(model, LoraConfig(
            r=2,
            lora_alpha=4,
            lora_dropout=0.0,
            target_modules=["q_proj", "k_proj"],
            bias="none",
            task_type="CAUSAL_LM",
        ))
        model.train()

        image = Image.open(FIXTURE_IMAGE).convert("RGB")
        messages = [{
            "role": "user",
            "content": [
                {"type": "image"},
                {"type": "text", "text": "Synthetic test only: identify the visible garment category."},
            ],
        }]
        prompt = processor.apply_chat_template(messages, add_generation_prompt=True)
        inputs = processor(text=prompt, images=[image], return_tensors="pt", padding=True)
        device = next(model.parameters()).device
        inputs = {key: value.to(device) if hasattr(value, "to") else value for key, value in inputs.items()}
        labels = inputs["input_ids"].clone()
        if "attention_mask" in inputs:
            labels[inputs["attention_mask"] == 0] = -100

        optimizer = torch.optim.AdamW((parameter for parameter in model.parameters() if parameter.requires_grad), lr=1e-5)
        optimizer.zero_grad(set_to_none=True)
        outputs = model(**inputs, labels=labels)
        loss = outputs.loss
        if not torch.isfinite(loss):
            raise RuntimeError("micro-experiment produced non-finite loss")
        loss.backward()
        optimizer.step()
        ADAPTER_DIR.mkdir(parents=True, exist_ok=True)
        model.save_pretrained(ADAPTER_DIR)

        free_after, total_after = torch.cuda.mem_get_info()
        report.update({
            "ok": True,
            "status": "completed",
            "loss": float(loss.detach().cpu()),
            "trainable_parameters": sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad),
            "adapter_dir": str(ADAPTER_DIR),
            "gpu_after": {
                "free_mib": round(free_after / 1024**2, 1),
                "total_mib": round(total_after / 1024**2, 1),
                "max_allocated_mib": round(torch.cuda.max_memory_allocated() / 1024**2, 1),
                "max_reserved_mib": round(torch.cuda.max_memory_reserved() / 1024**2, 1),
            },
        })
    except Exception as error:  # hardware/library failures become an audit report, not a fake success
        report.update({
            "ok": False,
            "status": "blocked_or_failed",
            "reason": str(error)[:1000],
            "traceback": traceback.format_exc(limit=8),
        })
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
