from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import yaml


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} must be a JSON object")
            rows.append(value)
    return rows


def _require(value: Any, name: str) -> None:
    if not value or (isinstance(value, str) and "<" in value):
        raise ValueError(f"{name} is missing or still a placeholder")


def _prepared_paths(root: Path) -> dict[str, Path]:
    paths = {split: root / f"{split}.jsonl" for split in ("train", "eval", "test")}
    for split, path in paths.items():
        if not path.exists():
            raise FileNotFoundError(f"prepared {split} manifest is missing: {path}")
    return paths


def _dry_run(config: dict[str, Any], prepared_root: Path) -> dict[str, Any]:
    model = config.get("model", {})
    adapter = config.get("adapter", {})
    dataset = config.get("dataset", {})
    _require(model.get("id"), "model.id")
    _require(model.get("revision"), "model.revision")
    _require(dataset.get("dataset_version"), "dataset.dataset_version")
    if adapter.get("method") != "lora":
        raise ValueError("only the reviewed LoRA adapter route is supported by this launcher")
    paths = _prepared_paths(prepared_root)
    counts = {split: len(_read_jsonl(path)) for split, path in paths.items()}
    if not all(counts.values()):
        raise ValueError("prepared train/eval/test manifests must be non-empty")
    missing_images: list[str] = []
    for split, path in paths.items():
        for record in _read_jsonl(path):
            image_path = record.get("image_path")
            if not isinstance(image_path, str) or not (prepared_root / image_path).is_file():
                missing_images.append(f"{split}:{record.get('sample_id', '<unknown>')}")
    if missing_images:
        raise ValueError(f"prepared manifest references missing local images: {missing_images[:10]}")
    return {
        "ok": True,
        "mode": "dry_run",
        "model_id": model["id"],
        "model_revision": model["revision"],
        "dataset_version": dataset["dataset_version"],
        "split_counts": counts,
        "adapter": {"method": adapter.get("method"), "r": adapter.get("r"), "alpha": adapter.get("alpha")},
    }


def _to_hf_records(rows: list[dict[str, Any]], prepared_root: Path) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for row in rows:
        image = prepared_root / row["image_path"]
        converted.append({"image": str(image), "messages": row["messages"], "sample_id": row["sample_id"]})
    return converted


def _execute(config: dict[str, Any], prepared_root: Path) -> dict[str, Any]:
    if os.getenv("RUN_APPROVED") != "1":
        raise PermissionError("RUN_APPROVED=1 is required for an actual fine-tune run")
    if not os.getenv("HF_TOKEN"):
        raise PermissionError("HF_TOKEN must be supplied by the remote provider secret")
    # Delay heavy imports so --dry-run works on developer machines without a CUDA/VLM stack.
    import torch
    from datasets import Dataset
    from peft import LoraConfig
    from transformers import AutoModelForImageTextToText, AutoProcessor
    from trl import SFTConfig, SFTTrainer

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable; do not train VLMs on the local demo path")
    model_config = config["model"]
    train_config = config["training"]
    adapter = config["adapter"]
    train_rows = _to_hf_records(_read_jsonl(prepared_root / "train.jsonl"), prepared_root)
    eval_rows = _to_hf_records(_read_jsonl(prepared_root / "eval.jsonl"), prepared_root)

    dtype = torch.bfloat16 if model_config.get("dtype") == "bfloat16" and torch.cuda.is_bf16_supported() else torch.float16
    processor = AutoProcessor.from_pretrained(model_config["id"], revision=model_config["revision"], token=os.environ["HF_TOKEN"], trust_remote_code=bool(model_config.get("trust_remote_code", False)))
    model = AutoModelForImageTextToText.from_pretrained(
        model_config["id"], revision=model_config["revision"], token=os.environ["HF_TOKEN"], torch_dtype=dtype,
        trust_remote_code=bool(model_config.get("trust_remote_code", False)),
    )
    peft = LoraConfig(r=int(adapter["r"]), lora_alpha=int(adapter["alpha"]), lora_dropout=float(adapter["dropout"]), target_modules=list(adapter["target_modules"]), bias="none", task_type="CAUSAL_LM")
    output_dir = str(prepared_root / "artifacts" / config["run"]["run_name"])
    args = SFTConfig(
        output_dir=output_dir,
        num_train_epochs=float(train_config["epochs"]),
        learning_rate=float(train_config["learning_rate"]),
        per_device_train_batch_size=int(train_config["per_device_train_batch_size"]),
        gradient_accumulation_steps=int(train_config["gradient_accumulation_steps"]),
        gradient_checkpointing=bool(train_config["gradient_checkpointing"]),
        max_length=None,
        logging_steps=int(train_config["logging_steps"]),
        eval_strategy=str(train_config["eval_strategy"]),
        eval_steps=int(train_config["eval_steps"]),
        save_strategy=str(train_config["save_strategy"]),
        save_steps=int(train_config["save_steps"]),
        save_total_limit=int(train_config["save_total_limit"]),
        warmup_ratio=float(train_config["warmup_ratio"]),
        report_to=list(train_config.get("report_to", [])),
        bf16=dtype is torch.bfloat16,
        fp16=dtype is torch.float16,
    )
    trainer = SFTTrainer(
        model=model,
        args=args,
        train_dataset=Dataset.from_list(train_rows),
        eval_dataset=Dataset.from_list(eval_rows),
        processing_class=processor,
        peft_config=peft,
    )
    result = trainer.train()
    trainer.save_model(output_dir)
    processor.save_pretrained(output_dir)
    return {
        "ok": True,
        "mode": "executed",
        "output_dir": output_dir,
        "global_step": int(result.global_step),
        "training_loss": float(result.training_loss),
        "cuda_device": torch.cuda.get_device_name(0),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run approved LoRA supervised fine-tuning for a governed fashion VLM dataset.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--prepared-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--execute", action="store_true", help="Run only after human approval and remote preflight; omission performs dry-run.")
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    report = _dry_run(config, args.prepared_root)
    if args.execute:
        report = _execute(config, args.prepared_root)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
