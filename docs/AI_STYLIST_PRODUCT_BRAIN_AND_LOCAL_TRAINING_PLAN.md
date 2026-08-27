# 3D AI Stylist: Định hướng sản phẩm, bộ não AI và kế hoạch training local

## 1. Mục tiêu sản phẩm

3D AI Stylist là hệ thống hỗ trợ người dùng hiểu kho đồ của chính họ, mô tả nhu cầu mặc tại thời điểm hiện tại và nhận các phương án phối đồ có thể giải thích. Hệ thống không được tự nhận là stylist tuyệt đối, không khẳng định size/fit vật lý và không mô tả canonical proxy là garment mesh được tái tạo thật.

> Mục tiêu là tạo ra **quyết định thời trang có evidence**, có vòng phản hồi/review và có giới hạn minh bạch; không phải chatbot sinh lời khuyên nghe hợp lý nhưng không kiểm chứng được.

## 2. Chức năng AI

| Năng lực | AI thực hiện | Boundary bắt buộc |
|---|---|---|
| Hiểu người dùng | Lưu body measurements, body contract, nhu cầu occasion/intent/style/formality/mobility/modesty. | Avatar scaling là heuristic, không phải chẩn đoán cơ thể hoặc fit guarantee. |
| Hiểu kho đồ | Nhận garment import, semantic tag, structural cue 2D và provenance. | Tag từ ảnh là draft cho đến khi reviewer approve. |
| Phối đồ | Lọc hard constraints rồi xếp hạng deterministic theo occasion, style, formality, intent, màu, availability, coherence và diversity. | Candidate `owned_only` chỉ dùng immutable wardrobe snapshot. |
| Giải thích | Trả score, evidence delta, trade-off, limitation và confirmation request. | Tổng evidence delta phải bằng total score. |
| Try-On | Preview canonical proxy, template rigged hoặc mesh đã duyệt; camera đa góc. | Proxy không phải reconstruction, cloth simulation hay physical fitting. |
| Học có kiểm soát | Tổng hợp review approval thành taxonomy proposal và xuất dataset governed. | Không tự sửa catalog, ranker weight hoặc model production. |

## 3. Bộ não AI theo nhiều tầng

### 3.1 Perception brain

Perception đọc ảnh trang phục và trả về JSON taxonomy đóng. Với ảnh 2D, hệ thống có thể dự đoán category, color, styles, occasions, formality và structural profile như neckline, shoulder construction, shoulder width, sleeve/torso length, waist shape, rise, hip fit và leg shape. Mỗi cue phải có confidence, rationale, `visible_views` và limitation.

Cùng một ảnh không đủ chứng minh panel mặt sau, pattern may, thickness, độ co giãn, kích cỡ, collision, physical fit hoặc mesh 3D. Các trường đó phải là `unknown` hoặc chờ reconstruction/review.

### 3.2 Knowledge brain

Knowledge brain là canonical garment catalog, style taxonomy, occasion/intent model, compatibility, layer slots, formality, silhouette, proportion effects và pairing hints/avoidance. Đây là kiến thức versioned, kiểm tra schema và thay đổi bằng governance, không phải prompt tự do.

### 3.3 Decision brain

Decision brain là deterministic outfit ranker. Nó lọc category/layer/fit/availability trước, sau đó score candidate. Mỗi reward, partial match và penalty tạo `DecisionEvidenceV1` để người dùng/reviewer biết vì sao outfit đứng cao hoặc thấp. Confidence hiện phản ánh tính đầy đủ/nhất quán evidence policy, không phải xác suất đẹp hay vừa cơ thể.

### 3.4 Review and learning brain

Reviewer xác nhận semantic/structural draft trước khi asset trở thành active. Lịch sử reviewer approval có thể sinh taxonomy learning proposal theo style–occasion và style–intent. Proposal chỉ được admin chuyển sang offline evaluation sau ngưỡng support; catalog/ranker/model không tự thay đổi.

### 3.5 3D truth brain

Try-On resolver chỉ dùng immutable session snapshot. Canonical proxy có thể minh họa shoulder/waist/rise/leg-shape đã reviewer duyệt, nhưng `render_mode=canonical_proxy` luôn giữ limitation. Mesh 3D chỉ được trả sau khi GLB, skeleton, rest pose, anchors, skin weights, scale, bounds, intersection và human quality review đều pass.

## 4. Luồng tư duy khi gợi ý outfit

```text
Nhập context + body profile + wardrobe snapshot
  -> hard constraints (owner, category, layer, availability, fit policy)
  -> construct outfit candidates
  -> deterministic policy scoring with evidence
  -> diversity and trade-off analysis
  -> user preview or explicit selection
  -> Try-On truth gate
  -> feedback / reviewer label / taxonomy proposal
```

AI phải ưu tiên **abstain hoặc request confirmation** nếu thiếu wardrobe asset, tag chưa review, context mơ hồ, fit concern hoặc quality gate không đạt. Không được bù khoảng trống bằng tuyên bố giả về garment 3D.

## 5. Kế hoạch training: local và remote

| Mức | Mục đích | Trạng thái và giới hạn |
|---|---|---|
| Local technical micro-run | Kiểm tra CUDA, optimizer, LoRA adapter persistence. | RTX 3050 4 GB đã chạy được text-only Qwen 0.5B one-step; không phải VLM/fashion training. |
| Local VLM micro-run | Kiểm tra cache-only VLM 4-bit. | SmolVLM bị chặn vì Windows CUDA 13.2 không có `bitsandbytes` binary tương thích. Không ép fp16 full VLM trên 4 GB. |
| Remote VLM LoRA | Train perception model có dataset governed, evaluate và release. | Chờ provider GPU, VRAM ít nhất 24 GB, model revision/license, dataset approval/S3 identity và release gate. |

## 6. Checklist việc cần làm trước khi training thật

### Dataset

- [ ] Thu thập garment images có consent dành riêng cho training.
- [ ] Reviewer approve semantic/structural labels; block withdrawn/disputed samples.
- [ ] Hoàn thành consent ledger theo `revision_id`, retention policy, source license/provenance, S3 key và SHA-256.
- [ ] Chạy `export_reviewer_approved_dataset.py` và kiểm tra `training_ready=true`.
- [ ] Tách train/eval/test theo cả owner và wardrobe; không làm random row split.
- [ ] Chạy `validate_manifest.py`; tất cả split non-empty, không duplicate/leakage.

### Model và evaluation

- [ ] Chọn VLM có license thương mại phù hợp, pin model ID + immutable revision.
- [ ] Review LoRA target modules theo kiến trúc model thật.
- [ ] Định nghĩa frozen holdout và baseline.
- [ ] Đặt threshold cho perception error, hard constraint violation, unsupported claim rate, reviewer preference, latency/cost và 3D truthfulness.

### Remote GPU

- [ ] Chọn Kubernetes GPU Job hoặc CUDA GPU VM có tối thiểu 24 GB VRAM.
- [ ] Cấu hình workload identity/service account; quyền S3 chỉ đọc dataset prefix và ghi artifact prefix.
- [ ] Inject `HF_TOKEN` qua secret manager, không commit token vào Git/YAML.
- [ ] Copy private LoRA config, thay toàn bộ placeholder và bảo vệ ngoài repository.
- [ ] Chạy remote preflight → S3 SHA-256 staging → dry-run.
- [ ] Chỉ đặt `RUN_APPROVED=1` sau reviewer release.

### Release

- [ ] Upload adapter, processor, config fingerprint, model revision, dataset/rubric version và training reports.
- [ ] Đánh giá frozen holdout trước shadow/canary.
- [ ] Ghi rollback plan về baseline và theo dõi production metrics.

## 7. Bắt đầu trên local sau khi clone GitHub

```powershell
# 1. Clone và tạo local environment
 git clone <repository-url>
 cd 3d-ai-stylist

# 2. Backend test
 cd backend
 C:\Python314\python.exe -m pytest -q

# 3. Semantic tagging scenario (mock, không phải VLM thật)
 C:\Python314\python.exe scripts\run_mock_vlm_tshirt_tagging_scenario.py

# 4. Local runtime probe
 C:\Python314\python.exe scripts\probe_local_vlm_training_runtime.py

# 5. Xem kết quả micro-run và không dùng adapter fallback cho production
 Get-Content reports\local_text_lora_fallback.json
```

Để train VLM production, không dùng RTX 3050 4 GB làm fallback. Làm theo `REMOTE_GPU_VLM_2D_TO_3D_CONFIGURATION.md` và `VLM_REMOTE_GPU_FINE_TUNE_PIPELINE.md`.

## 8. Định hướng phát triển

Giai đoạn tiếp theo nên ưu tiên tăng **chất lượng dữ liệu và evaluation** trước khi tăng kích thước model. Các cải tiến có giá trị là thêm ảnh multi-view được consent, reviewer rubric rõ cho structural cues, active-learning queue cho sample uncertainty cao, benchmark riêng perception/ranking/3D truthfulness, và model release theo canary/rollback. Một model lớn hơn không thay thế được dataset sạch, hard constraints và review governance.
