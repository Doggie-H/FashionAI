# Cấu hình Remote GPU cho VLM Perception 2D và 3D Truth Gate

## Phạm vi và giới hạn

Remote VLM được dùng để đọc **cue nhìn thấy được** từ ảnh 2D: category, style, occasion, material/silhouette có evidence, neckline, shoulder construction/width, sleeve/torso length, waist shape, rise, hip fit và leg shape. Kết quả luôn là draft có provenance, confidence, limitations và reviewer approval.

> Fine-tune VLM **không tự chuyển** một ảnh thành garment 3D đáng tin cậy. Nó không xác lập panel khuất, sewing pattern, thickness, cloth dynamics, collision, skin weights, physical fit hoặc size. Mesh/rig 3D phải đi qua reconstruction worker và quality gate độc lập.

## Chọn kiểu hạ tầng

| Kiểu | Dùng khi | Điều cần có |
|---|---|---|
| Kubernetes GPU Job | Đã có cluster, namespace, image registry và workload identity. | Node GPU có ít nhất 24 GB VRAM, service account least privilege, immutable image digest, Secret/CSI/ExternalSecret do platform quản lý. |
| GPU VM | Đã có VM CUDA riêng và cách chạy job qua SSH/CI runner. | GPU ít nhất 24 GB VRAM, NVIDIA driver/CUDA/PyTorch tương thích, disk cho checkpoint, non-root runtime và secret manager/provider identity. |

Không chọn provider hoặc endpoint bằng suy đoán. Trước khi kết nối, xác nhận rõ tên provider, Kubernetes hoặc VM, GPU SKU/VRAM, vùng lưu dataset và cơ chế identity.

## Bước 1 — Chuẩn bị dataset governed

1. Export history bằng `vlm_finetune/scripts/export_reviewer_approved_dataset.py`.
2. Chỉ thêm revision vào consent ledger khi chủ sở hữu đã cho phép training; review approval không thay consent.
3. Mỗi ledger entry phải có consent timestamp, retention policy, non-withdrawn state, `ai-stylist/` S3 key, source license/provenance và SHA-256 source image.
4. Kiểm tra report exporter. Nếu `training_ready=false`, dừng; không thêm sample giả để làm đủ split.
5. Chạy `validate_manifest.py` trên train/eval/test. Validator phải chặn duplicate, sample disputed, missing approval/consent, split rỗng và owner/wardrobe leakage.

```powershell
Set-Location backend
C:\Python314\python.exe vlm_finetune\scripts\export_reviewer_approved_dataset.py `
  --database-url <private-database-url> `
  --consent-ledger <private-consent-ledger.json> `
  --output-dir <prepared-manifests-directory> `
  --dataset-version <immutable-reviewed-version>
```

Không đặt database URL, consent ledger hay S3 key thật vào Git. Dùng secret manager hoặc encrypted runtime mount.

## Bước 2 — Tạo private run config

Copy `vlm_finetune/configs/fashion_vlm_lora.example.yaml` ra vùng secret/private của provider. Thay toàn bộ placeholder bằng thông tin đã được duyệt:

| Nhóm | Giá trị cần pin | Không được làm |
|---|---|---|
| Model | License-approved VLM ID, immutable commit/revision, `trust_remote_code=false` trừ khi security review cho phép. | Dùng `latest`, model ID mơ hồ, hoặc token trong YAML. |
| LoRA | `r`, `alpha`, dropout và `target_modules` đã review theo kiến trúc model thật. | Sao chép target module từ model khác. |
| Dataset | Immutable dataset version, manifest keys đã validate, SHA-256 required. | Dùng manifest local/mock hoặc bỏ split eval/test. |
| Acceptance | Frozen holdout thresholds cho constraint violation, unsupported claims, reviewer preference. | Chạy train khi threshold vẫn placeholder. |

Với model VLM cỡ 7B, 24 GB là mức sàn pipeline hiện tại; thực tế GPU/VRAM phải được preflight theo model, precision, image token budget, batch và LoRA plan cụ thể.

## Bước 3 — Identity, secret và storage

Thiết lập workload identity/service account hoặc VM role có quyền tối thiểu:

| Resource | Quyền cho phép |
|---|---|
| Dataset prefix | Chỉ đọc prefix dataset đã duyệt. |
| Run artifact prefix | Chỉ ghi prefix run hiện tại. |
| Model registry | Secret manager inject `HF_TOKEN` lúc runtime; token không xuất hiện trong shell history, YAML hay report. |
| Kubernetes | Service account chỉ dùng namespace/job cần thiết; không dùng cluster-admin. |

Các biến runtime do provider inject:

```text
AI_STYLIST_STORAGE_BACKEND=s3
AI_STYLIST_S3_BUCKET=<approved-private-bucket>
HF_TOKEN=<injected-by-secret-manager>
RUN_APPROVED=1  # chỉ đặt sau dry-run + reviewer release
```

## Bước 4 — Preflight, staging và dry-run

Trên GPU worker, không trên RTX 3050 local:

```bash
python vlm_finetune/scripts/preflight_remote_gpu.py \
  --config /secure/fashion-vlm-lora.yaml \
  --report /work/reports/preflight.json \
  --min-vram-gb 24 \
  --require-s3

python vlm_finetune/scripts/stage_dataset_from_s3.py \
  --config /secure/fashion-vlm-lora.yaml \
  --output-root /work/dataset \
  --execute-download

python vlm_finetune/scripts/train_lora_vlm.py \
  --config /secure/fashion-vlm-lora.yaml \
  --prepared-root /work/dataset \
  --report /work/reports/dry-run.json
```

Ba lệnh phải pass trước khi đặt `RUN_APPROVED=1`. Dataset staging phải verify SHA-256 sau download. Kubernetes Job template hiện giả định manifests đã có ở `/work/manifests`; dùng staging Job governed hoặc initContainer verify hash, không bỏ qua bước này.

## Bước 5 — Chạy và release

Sau review release, chạy single-GPU LoRA job với immutable image digest, `backoffLimit: 0`, read-only root filesystem và explicit resource requests/limits. Upload adapter, processor, private config fingerprint, model revision, dataset/rubric version, preflight/dry-run reports và training summary vào artifact prefix.

Đánh giá trên frozen holdout trước shadow/canary. Báo cáo riêng perception error, hard-constraint violation, unsupported-claim rate, reviewer pairwise preference, latency/cost và 3D truthfulness. Rollback về baseline khi một hard release gate fail.

## Mapping từ perception sang 3D

1. VLM draft nhận structural cue 2D có `visible_views` và limitation.
2. Reviewer approve mới persist `semantic_metadata` và `structural_profile` vào immutable wardrobe revision.
3. Stylist ranking dùng approved metadata; canonical proxy có thể minh họa shoulder/waist/rise/leg shape.
4. Ảnh 2D cue không thay `render_mode` và không mở khóa mesh.
5. Reconstruction/rig worker chỉ trả approved mesh khi GLB, skeleton, rest pose, anchors, skin weights, scale, bounds, intersection và human quality review đều pass.

## Trạng thái hiện tại của project

Không có remote GPU connector, provider, bucket, model registry token, approved dataset hoặc Kubernetes/VM identity nào được cấu hình trong session hiện tại. Vì vậy runbook là hướng dẫn triển khai có guardrail; nó không phải bằng chứng rằng VLM remote hoặc 3D reconstruction đã chạy.
