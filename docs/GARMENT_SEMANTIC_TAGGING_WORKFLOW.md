# Garment Semantic Tagging Workflow

> **Mục đích:** biến ảnh trang phục do người dùng thêm vào thành một **bản nháp metadata có bằng chứng**, sau đó chỉ dùng metadata đã được duyệt trong gợi ý phối đồ. Pipeline này không suy diễn physical fit, chất liệu ẩn, mặt sau của trang phục hoặc cloth simulation từ một ảnh.

## 1. Trạng thái hiện tại

Pipeline đã có đầy đủ contract, API, worker boundary, persistence, review gate, ranker integration và UI status. Mặc định `GARMENT_TAGGER_PROVIDER=disabled`, vì vậy hệ thống trả về `unavailable` thay vì bịa tag. Chế độ VLM thực chỉ được bật khi worker GPU đã có model ID, immutable revision và năng lực CUDA/VRAM đủ điều kiện.

| Thành phần | Vai trò | Không được làm |
|---|---|---|
| `POST /phase-b/garment-imports` | Kiểm tra file, lưu ảnh, tạo manifest và canonical proxy | Không biến ảnh thành 3D rigged/fitting thật. |
| `POST /phase-b/garment-imports/{import_id}/semantic-tags` | Yêu cầu semantic analysis; enqueue khi provider Qwen khả dụng | Không gọi VLM trong request upload. |
| `garment_gpu` worker | Chạy VLM lazy-load, chuẩn hoá JSON vào taxonomy đóng | Không đưa raw text hoặc tag không thuộc taxonomy vào ranker. |
| `GarmentImportManifestV1` | Lưu raw semantic draft, model provenance, SHA-256, evidence, confidence và limitations | Không phải source-of-truth được ranking trực tiếp. |
| `GarmentAssetRevision.semantic_metadata` | Chỉ lưu metadata đã được reviewer phê duyệt | Không chứa prediction chưa review. |
| `OutfitDecisionRequestV1.candidate_garments` | Đưa immutable approved user-import metadata vào deterministic ranker | Không silent substitute item của user bằng catalog item. |

## 2. Luồng nghiệp vụ

```text
User upload image
  → image validation + SHA-256 + canonical proxy manifest
  → request semantic tags
  → GPU worker preflight
  → VLM JSON prediction constrained by taxonomy
  → manifest stores draft + evidence + limitations
  → create WardrobeAssetRevision (pending_review)
  → reviewer approves / rejects garment_metadata
  → approved semantic_metadata is frozen into asset revision
  → StylingSession snapshots only active revisions
  → deterministic ranker uses snapshot metadata + visible evidence
```

Mọi candidate từ user import có `source="user_import"`. Decision engine sẽ thêm thông báo xác nhận người dùng cho item không phải canonical seed. Try-On vẫn resolve theo `asset_id` của immutable session snapshot; semantic garment ID chỉ là identity dùng để ranking, không làm thay đổi truth gate của mesh.

## 3. Taxonomy được VLM phép trả về

VLM phải trả JSON dùng vocabulary đóng. Tag nằm ngoài vocabulary bị loại và được ghi limitation thay vì âm thầm map sai.

| Nhóm | Ví dụ giá trị được phép |
|---|---|
| Category | `top`, `bottom`, `dress`, `outerwear`, `footwear`, `belt`, `accessory` |
| Style | `minimal`, `classic`, `business`, `quiet_luxury`, `preppy`, `streetwear`, `romantic`, `athleisure`, `utility`, `modest`, `creative`, `vintage` và các giá trị contract khác |
| Occasion | `work`, `meeting`, `interview`, `presentation`, `date`, `weekend`, `travel`, `formal`, `gym` và các giá trị contract khác |
| Functional signals | season, weather suitability, formality, statement level, mobility, modesty, intent support, pairing hints, avoid-pairing warnings |
| Traceability | confidence/rationale theo dimension, model ID/revision, source SHA-256, limitations |

`confidence` là confidence của prediction theo image cue hiện có. Nó **không** phải xác suất vừa người, chất lượng vải, hay mức độ đẹp tuyệt đối.

## 4. Bật Qwen VLM thật trên worker GPU

Không đặt token, bucket, ảnh người dùng hay model revision thật trong source code. Cấu hình các giá trị riêng tư bằng secret manager hoặc environment của worker.

```bash
# Worker GPU đã được người vận hành phê duyệt.
GARMENT_TAGGER_PROVIDER=qwen25vl
QWEN_VL_MODEL_ID=<licensed-model-id>
QWEN_VL_MODEL_REVISION=<immutable-commit-or-revision>
GARMENT_TAGGER_MIN_VRAM_GB=8
QWEN_VL_QUANTIZATION=4bit
QWEN_VL_DEVICE_MAP=auto
QWEN_VL_MAX_NEW_TOKENS=160
QWEN_VL_TRUST_REMOTE_CODE=0
```

Pipeline kiểm tra CUDA, VRAM tối thiểu, source image và immutable model revision trước khi tải model. Khi preflight không đạt, manifest có `semantic_tagging.status="unavailable"`; item vẫn là canonical proxy/pending review, không bị gắn tag giả. RTX 3050 Laptop 4 GB của local project không đạt ngưỡng chạy Qwen2.5-VL-7B đáng tin cậy, nên không được dùng để công bố inference hay fine-tune thật.

## 5. Quy trình review bắt buộc

Reviewer mở `garment_metadata` task và kiểm tra category, style, occasion, intent, confidence/rationale cùng limitations. Khi approve, hệ thống copy `candidate_metadata` sang `GarmentAssetRevision.semantic_metadata`, chuyển semantic status sang `approved`, làm revision active và cho phép đưa snapshot đó vào StylingSession. Khi reject/rework, asset không active và ranker không đọc tag.

Reviewer cần đặc biệt xác nhận các trường có rủi ro cao: category nếu VLM khác với category người dùng nhập, material nếu chỉ thấy bề mặt, weather suitability, coverage, formality theo bối cảnh văn hoá và pairing/avoidance. Nếu ảnh không đủ bằng chứng, giữ field canonical/default hoặc yêu cầu ảnh bổ sung; không cố điền đầy taxonomy.

## 6. Kiểm chứng đã có

| Phạm vi | Kết quả |
|---|---|
| Semantic tagger unit test | Provider disabled không sinh tag giả; payload Qwen bị khoá taxonomy; status luôn `needs_review` trước approval. |
| Ranker test | User semantic garment ID được dùng làm owned candidate, không bị thay ngầm bằng canonical garment ID; evidence total vẫn bằng candidate score. |
| Workflow/review test | Reviewer approval mới persist `semantic_metadata`; Try-On map user garment ID về đúng immutable asset snapshot. |
| Phase B API test | Disabled provider trả `unavailable`; queue request chống duplicate. |
| Regression | Backend suite: `108 passed, 3 skipped`; frontend production build hoàn tất. |

## 7. Dữ liệu để AI thực sự giỏi dần

VLM runtime giúp perception, nhưng không thay thế dữ liệu đánh giá. Sau mỗi review cần tạo StyleCase gồm image hash/provenance/consent, version taxonomy, context, immutable wardrobe snapshot, VLM draft, reviewer correction, final decision evidence, user feedback và deletion/retention signal. Split train/eval/test theo cả owner và wardrobe. Chỉ sau khi có baseline và frozen holdout mới đánh giá LoRA; hard-constraint violation và unsupported claim phải chặn release.

> Không có fine-tune, remote GPU provider, model token hoặc reviewed personal dataset nào đã được chạy/cấu hình bởi thay đổi này. Phần đã hoàn tất là integration có guardrail, sẵn sàng kết nối với worker/provider do người dùng phê duyệt.


## 8. Mock VLM scenario cho regression

`backend/scripts/run_mock_vlm_tshirt_tagging_scenario.py` sinh một ảnh áo thun navy fixture hợp lệ rồi chạy FastAPI + SQLite in-memory cô lập. Script đặt `GARMENT_TAGGER_PROVIDER=mock`; mock provider trả metadata deterministic có provider `mock`, model `ai-stylist/mock-garment-tagger`, revision `fixture-v1` và limitation bắt buộc rằng nó **không phải visual inference thực**.

```powershell
Set-Location 'D:\Study\Studio Project\3d-ai-stylist\backend'
C:\Python314\python.exe scripts\run_mock_vlm_tshirt_tagging_scenario.py
```

Artifact tạo tại `backend/reports/mock_vlm_tshirt_tagging_scenario.json` cùng `mock_vlm_tshirt_fixture.png`. Scenario xác minh chuỗi import → semantic draft `needs_review` → claim/approve reviewer → active semantic metadata → taxonomy proposals → owned-only decision → canonical-proxy binding. Nó không chứng minh Qwen hoặc model thật nhận diện chính xác áo thun.

## 9. Review Dashboard semantic tag

Mở `/review`, dùng JWT có role `reviewer` hoặc `admin`, chọn filter `garment_metadata`, sau đó chọn một task. Dashboard hiển thị provider/model/revision, candidate metadata, evidence confidence/rationale theo dimension, limitations, checklist và audit timeline trước khi reviewer ghi note rồi approve/reject/rework. Chỉ task đã claim mới cho quyết định; command có Idempotency-Key và Correlation-ID.

Reviewer cần kiểm tra cue nhìn thấy được, không suy diễn cấu trúc khuất, thành phần sợi chính xác, size, physical fit, cloth dynamics hoặc mesh reconstruction chỉ từ confidence. Approval làm semantic metadata active cho revision; nó không nâng canonical proxy thành mesh rigged.

## 10. Taxonomy learning proposal, không phải tự sửa taxonomy

Sau một `garment_metadata` review được approve, hệ thống tự aggregate style–occasion và style–intent thành `TaxonomyLearningProposal`. Đây là event-driven deterministic aggregation từ immutable metadata đã duyệt, không là background VLM training.

| Trạng thái | Ý nghĩa | Tác động production |
|---|---|---|
| `proposed` | Có evidence từ reviewer history nhưng chưa đủ để áp dụng. | Không đổi catalog/ranker/model. |
| `approved_for_evaluation` | Chỉ admin, tối thiểu ba nguồn review độc lập; sẵn sàng tạo evaluation plan. | Vẫn không đổi catalog/ranker/model. |
| `rejected` | Proposal bị governance bác bỏ. | Không đổi catalog/ranker/model. |

Proposal lưu source task IDs, support count, average confidence, preconditions và audit trail. API `GET /taxonomy-learning/proposals` dành cho reviewer; `POST /taxonomy-learning/proposals/{proposal_id}/decision` chỉ cho admin. Trước bất kỳ catalog/ranker/fine-tune release nào, phải có split theo owner/wardrobe, frozen holdout, measurement của constraint violation/unsupported claim và release approval riêng.


## 11. Structural profile: từ cue ảnh 2D sang proxy 3D

`GarmentStructuralProfileV1` bổ sung một lớp perception riêng cho cấu trúc nhìn thấy được của trang phục. Đây không phải thông số pattern/mesh. Với áo, profile có neckline, shoulder construction/width, sleeve length, torso length, waist shape và hem shape. Với quần, profile có rise, waist construction, hip fit, leg shape và leg length. Mỗi cue cần evidence có `confidence`, `rationale` và `visible_views`.

| Ví dụ cue | Có thể biểu diễn sau review | Không được suy diễn từ một ảnh |
|---|---|---|
| Áo | crew neck, set-in/dropped/raglan shoulder, short/long sleeve, cropped/waist/hip/long torso, fitted/relaxed waist | số đo vai/eo thật, đường may phía sau, độ dày, drape, độ co giãn, fit trên cơ thể |
| Quần | low/mid/high rise, flat/elastic/belted waist, fitted/regular/relaxed hip, skinny/slim/straight/tapered/wide/bootcut/flared leg | vòng cạp cm, inseam thật, panel ẩn, fabric stretch, collision hoặc pressure fit |

Raw structural draft nằm trong semantic tagging manifest và có `needs_review`. Khi reviewer approve garment metadata, profile được copy vào `GarmentAssetRevision.structural_profile`, đánh dấu `approved_2d_cues`; trường `structural_profile_mesh_evidence` vẫn là `false`. Chỉ profile đã duyệt mới đi vào immutable StylingSession snapshot và Try-On binding.

Canonical proxy dùng profile để **minh họa** vai áo, độ ôm eo, dài áo hoặc cạp/dáng/dài ống quần. UI hiển thị structural cue và limitation kèm avatar. Nó vẫn là `canonical_proxy`, không được gọi là reconstructed GLB, garment simulation hay physical fitting. Render mesh chỉ bật sau quality gate độc lập: asset tồn tại, GLB valid, skeleton/rest pose/anchors/skin weights/scale/bounds/intersection pass và human mesh review approve.
