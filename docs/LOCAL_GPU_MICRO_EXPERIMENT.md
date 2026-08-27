# Local GPU Micro-Experiment Runbook

## Scope

This runbook records a bounded technical experiment on the local NVIDIA GeForce RTX 3050 Laptop GPU with 4,095 MiB VRAM. It validates selected runtime paths only. It does **not** train the production fashion VLM, improve style knowledge, validate garment perception, or create a model eligible for deployment.

## Results

| Experiment | Result | Evidence |
|---|---|---|
| Cached SmolVLM, 4-bit, one synthetic image, LoRA `r=2` | Blocked | `bitsandbytes` on the Windows CUDA 13.2 runtime has no matching `libbitsandbytes_cuda132.dll`; no VLM adapter was produced. |
| Cached Qwen2.5-0.5B text model, fp16, one synthetic text input, LoRA `r=2` | Completed | One optimizer step succeeded with loss `9.423965454101562`; the saved adapter is a CUDA/LoRA artifact only. |
| Post-run probe | CUDA still visible to PyTorch | RTX 3050 remains 4,095 MiB; `nvidia-smi` still fails NVML initialization. |

## Hard boundaries

The fallback is **text-only**. It has no image input, no garment cue recognition, no taxonomy labels, no reviewer-approved data, and no fashion outcome. Do not mount `local_text_lora_fallback_adapter` into the AI Stylist, and do not present its loss as fashion accuracy.

The VLM failure does not mean the cached model is invalid. It means this local combination of VRAM, Windows, CUDA 13.2 and `bitsandbytes` cannot support the selected 4-bit VLM micro-run. Do not bypass the native-library compatibility problem by attempting a full fp16 VLM load on the 4 GB GPU.

## Dataset path

Use `vlm_finetune/scripts/export_reviewer_approved_dataset.py` for real dataset preparation. The exporter requires a separate training-consent ledger per immutable revision and outputs a zero-record report if approved history or consent is absent. Current local export has zero records and `training_ready=false`; no production dataset was created.

## Production path

A real VLM fine-tune remains remote-only until there is a licensed model pinned to an immutable revision, a consented reviewer-approved owner/wardrobe-separated dataset, S3-compatible least-privilege identity, a compatible GPU runtime with at least 24 GB VRAM, frozen-holdout acceptance gates and an explicit release approval.
