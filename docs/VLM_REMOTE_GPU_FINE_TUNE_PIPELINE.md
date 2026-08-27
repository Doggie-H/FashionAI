# Pipeline Fine-Tune VLM trên Remote GPU

**Trạng thái hiện tại:** pipeline artifacts, validation gate và Kubernetes Job template đã được triển khai. **Remote GPU provider chưa được kết nối trong session này**: kiểm tra read-only không thấy connector GPU và project chỉ có `.env.p2-provider.example`; vì vậy không có cluster, endpoint, bucket, workload identity, model token hay training job thật nào đã được tạo/chạy.

## 1. Mục tiêu và ranh giới

Pipeline này chỉ phục vụ **supervised LoRA fine-tuning** sau khi dataset được cấp quyền, có consent, reviewer approval và evaluation split độc lập. Nó không tự biến model thành chuyên gia thời trang; quyết định availability, quality-gate mesh, owned-only policy, safety và reviewer escalation vẫn ở deterministic policy layer.

> Không chạy fine-tune bằng ảnh người dùng, ảnh wardrobe hoặc public dataset chỉ vì chúng có sẵn. Chỉ dùng dữ liệu có consent/license, provenance, retention policy và reviewer label hợp lệ.

| Thành phần | Artifact đã chuẩn bị | Vai trò |
|---|---|---|
| Config | `backend/vlm_finetune/configs/fashion_vlm_lora.example.yaml` | Model revision, LoRA, training, dataset version và release gates; mọi giá trị `<...>` phải được thay bằng config private. |
| Dataset contract | `backend/vlm_finetune/schemas/style_vlm_sample.schema.json` | Chỉ nhận sample có `training_allowed=true`, source provenance, ảnh SHA-256 và label reviewer approved. |
| Manifest gate | `backend/vlm_finetune/scripts/validate_manifest.py` | Chặn record withdrawn/disputed và owner/wardrobe leakage giữa train/eval/test. |
| Remote preflight | `backend/vlm_finetune/scripts/preflight_remote_gpu.py` | Chặn config placeholder, thiếu model revision/token/storage, không có NVIDIA runtime hoặc VRAM dưới ngưỡng. |
| S3 staging | `backend/vlm_finetune/scripts/stage_dataset_from_s3.py` | Download qua workload identity, kiểm tra SHA-256, tạo prepared local records; yêu cầu explicit `--execute-download`. |
| Trainer | `backend/vlm_finetune/scripts/train_lora_vlm.py` | `--dry-run` mặc định; chỉ `--execute` với `RUN_APPROVED=1` mới import training stack/CUDA. |
| GPU job | `backend/deployments/vlm-finetune-job.yaml.example` | Job một lần, non-retry, GPU node selector, immutable image digest và read-only filesystem. |

## 2. Hai cách vận hành khả thi

| Cách vận hành | Đánh đổi | Chi phí | Độ phức tạp |
|---|---|---|---|
| **Remote Kubernetes GPU theo template hiện có** | Phù hợp với workload identity, S3 prefix policy, immutable job và audit; cần platform team quản lý cluster/NVIDIA runtime. | Theo GPU node/provider đã chọn. | Cao; cần namespace, image registry, service account và storage policy. |
| **Remote GPU VM một lần với cùng Docker image** | Nhanh để pilot có kiểm soát; phải tự quản lý firewall, disk cleanup, token và teardown. | Theo GPU VM đã chọn. | Trung bình; yêu cầu shell/SSH hoặc runner provider đã được user cho phép. |

Fine-tuning vượt khả năng GPU 4 GB local và yêu cầu CUDA/driver/packages riêng, vì vậy không nên triển khai như API request, browser task hay process local lâu dài. Nếu chưa có provider thật, lựa chọn nhẹ hơn là **shadow evaluation**: dùng ranker + reviewer labels + VLM inference remote theo batch nhỏ, chưa fine-tune và chưa tác động policy production.

## 3. Prerequisite bắt buộc trước provider deployment

| Nhóm | Điều kiện bắt buộc | Bằng chứng cần lưu |
|---|---|---|
| Dataset | Train/eval/test JSONL được validator pass; split theo owner và wardrobe; consent chưa bị rút; reviewer non-disputed. | `manifest-validation.json`, dataset version, rubric version, retention policy. |
| Model | Base model có license thương mại/chính sách redistribution được duyệt; model revision là immutable. | Model card snapshot, license approval, revision/commit ID. |
| Storage | Private S3-compatible bucket, TLS endpoint, separate prefixes cho raw/approved/train artifacts, lifecycle deletion. | Prefix policy và object version/lifecycle configuration. |
| Identity | Workload identity/service account có quyền read manifest+image approved và write đúng run prefix; browser/API client không có quyền này. | IAM/role binding và policy review. |
| GPU | NVIDIA runtime, CUDA/PyTorch build tương thích, VRAM tối thiểu theo model/batch và disk đủ dataset/checkpoint. | Preflight JSON, `nvidia-smi`, immutable image digest. |
| Review | Release approver đã duyệt config, dataset version, baseline và acceptance criteria. | Release ticket/audit record; `RUN_APPROVED=1` chỉ được cấp cho job đã duyệt. |

## 4. Quy trình triển khai chi tiết

### Bước 1 — Chuẩn bị dữ liệu và split

Tạo JSONL theo schema `StyleVlmTrainingSampleV1`. Mỗi sample phải có image key S3, SHA-256, conversational messages, consent và reviewer label. Tách train/eval/test theo cả `owner_group_id` và `wardrobe_group_id`; không random split từng row. Chạy validator trước khi đưa sample vào GPU:

```bash
python -m vlm_finetune.scripts.validate_manifest \
  --train manifests/train.jsonl \
  --eval manifests/eval.jsonl \
  --test manifests/test.jsonl \
  --report reports/manifest-validation.json
```

Validator dừng với exit code `2` khi phát hiện consent bị rút, reviewer dispute, split mismatch, sample duplicate hoặc leakage. Không thay validator bằng “đánh dấu thủ công là approved”.

### Bước 2 — Tạo object-storage policy tối thiểu

Tạo separate prefixes, ví dụ `ai-stylist/fine-tune/datasets/<dataset-version>/` cho manifest/ảnh approved và `ai-stylist/fine-tune/runs/<run-name>/` cho report/adapter/checkpoint. Service account fine-tune chỉ cần `GetObject` ở dataset prefix và `PutObject`/`AbortMultipartUpload` ở đúng run prefix. Không cấp list/read toàn bucket, delete raw user uploads hoặc credential tĩnh cho frontend.

Đặt `AI_STYLIST_STORAGE_BACKEND=s3`, bucket, region và endpoint trong private ConfigMap/provider secret; tham khảo `.env.p2-provider.example` nhưng không commit file `.env` có credential.

### Bước 3 — Build image khớp GPU provider

`backend/vlm_finetune/Dockerfile` không tự chọn PyTorch CUDA wheel. Platform team phải pin CUDA image, driver compatibility và PyTorch wheel phù hợp với remote provider, sau đó build/push immutable digest. Cài `backend/vlm_finetune/requirements.txt` trong image; không cài hay train VLM thực trên local RTX 3050 4 GB.

### Bước 4 — Đặt private run config

Copy `fashion_vlm_lora.example.yaml` thành config private và thay toàn bộ placeholder. Pin `model.id` **và** immutable `model.revision`; khai báo LoRA target modules chỉ sau khi kiểm tra architecture model; đặt `max_length: null` cho sample VLM để không cắt image tokens. TRL tài liệu hóa VLM dataset với cột image/images và cảnh báo truncation image token có thể gây lỗi.[1]

### Bước 5 — Preflight và dry-run

Chạy preflight trong remote image, trước lúc staging hoặc `accelerate launch`:

```bash
python -m vlm_finetune.scripts.preflight_remote_gpu \
  --config /config/fashion_vlm_lora.yaml \
  --report /work/reports/preflight.json \
  --min-vram-gb 24 --require-s3
```

Preflight phải pass NVIDIA runtime, memory floor, storage backend/bucket, `HF_TOKEN`, dataset version và immutable model revision. Sau đó chạy `train_lora_vlm.py` **không** có `--execute` để xác minh prepared manifest/path/image count. Không sửa hoặc bypass check nhằm chạy cho được trên GPU ít VRAM.

### Bước 6 — Stage ảnh approved và xác minh hash

Sau khi manifest validation được duyệt, dùng workload identity để stage train/eval/test. Script chỉ download khi explicit switch:

```bash
python -m vlm_finetune.scripts.stage_dataset_from_s3 \
  --manifest /work/manifests/train.jsonl --split train \
  --output-root /work/dataset --execute-download
```

Lặp lại cho eval/test. Mỗi download phải đúng SHA-256 trong approved manifest. Mismatch dừng job và xóa file staged lỗi.

### Bước 7 — Thực thi LoRA có human approval

Khi release approver xác nhận baseline, config, validation/preflight reports và artifact prefix, tạo Kubernetes Job từ `vlm-finetune-job.yaml.example` với image digest và config/private secret thật. Job yêu cầu `RUN_APPROVED=1`, `HF_TOKEN`, remote CUDA và `--execute` rõ ràng. PEFT/LoRA huấn luyện adapter thay vì full weights, giúp giảm phạm vi trainable parameters và storage so với full fine-tune.[2] Accelerate khuyến nghị configure launch environment trước và dùng `accelerate launch` cho GPU/multi-GPU launcher.[3]

### Bước 8 — Đánh giá, promote hoặc rollback

Job hoàn thành không đồng nghĩa model được deploy. Upload adapter, processor, config, train summary, validation/preflight reports, model revision và dataset version vào run prefix. Chạy frozen test slice gồm hard constraints, unsupported-claim rate, reviewer pairwise preference, low-confidence/abstention và Vietnamese user-context cases. Chỉ promote adapter qua shadow mode/canary sau khi không có hard-policy regression. Giữ khả năng rollback về model/policy baseline.

## 5. Điều chưa thể chạy trong session này

Chưa có provider connector hoặc cluster config, provider secret, private model registry token, actual bucket/config, reviewed VLM training corpus, base-model license approval, GPU preflight report hoặc human release approval. Do đó pipeline không được apply/run fine-tune thật trong session này. Artifacts mới được thiết kế để **fail closed** cho tới khi các điều kiện trên được cung cấp.

## References

[1] [TRL SFTTrainer — Training Vision-Language Models](https://huggingface.co/docs/trl/en/sft_trainer)  
[2] [Hugging Face PEFT documentation](https://huggingface.co/docs/peft/en/index)  
[3] [Accelerate — Launching scripts](https://huggingface.co/docs/accelerate/en/basic_tutorials/launch)
