# Workflow Foundation P0 Implementation

**Tác giả:** Manus AI  
**Mục đích:** Chuyển 3D AI Stylist từ các endpoint kỹ thuật rời rạc sang một core workflow có aggregate, trạng thái, truy vết, idempotency và dữ liệu quyết định có thể tái hiện.

## 1. Kết quả triển khai

P0 không thay thế UI demo hoặc các endpoint Phase A/B/C đã có. Thay vào đó, P0 thêm một lớp command-oriented tại `/workflow` để các luồng mới được quản trị theo business case. Các endpoint Phase A/B/C vẫn là adapter kỹ thuật tương thích ngược; workflow mới là nơi lưu ownership, snapshot, transition, audit event và quality gate.

| Thành phần | Cài đặt | Ý nghĩa nghiệp vụ |
|---|---|---|
| `BodyProfileRevision` | Lưu measurements, body contract, calibration version, trạng thái và confirmation. | Số đo không còn chỉ là payload tức thời; profile phải được xác nhận trước khi dùng cho stylist session. |
| `WardrobeAsset` và `GarmentAssetRevision` | Lưu asset owner, revision, import manifest snapshot, canonical garment ID, trạng thái/review. | Ảnh import không tự động thành tài sản active của tủ đồ. |
| `StylingSession` | Lưu body contract snapshot, context và danh sách active wardrobe revisions. | Decision luôn tái hiện được từ phiên, không phụ thuộc dữ liệu hiện tại đã bị sửa. |
| `OutfitDecisionRun` | Lưu decision structured, catalog version và rule version. | Candidate/evidence/abstention là bản ghi kiểm toán, không phải text trả về một lần. |
| `TryOnRun` | Lưu outfit đã chọn, render mode, status và limitation. | Phân biệt proxy, rigged asset và approved reconstruction một cách rõ ràng. |
| `WorkflowAuditEvent` | Event append-only theo aggregate và correlation ID. | Cung cấp history phục vụ debug, review và evaluation. |
| `ProcessedCommand` | Unique theo actor, command type và idempotency key. | Retry HTTP không tạo profile, asset, session hoặc try-on run trùng. |

## 2. State transition thực tế

| Aggregate | Trạng thái P0 đã dùng | Invariant thực thi |
|---|---|---|
| Body profile | `calibrated` → `active` → `superseded` | Chỉ body `calibrated` xác nhận được; khi kích hoạt profile mới, profile active cũ bị supersede. |
| Wardrobe asset revision | `normalized`/`pending_review` → `active` | Chỉ revision reviewable được activate; failed reconstruction snapshot bị chặn. |
| Styling session | `inputs_resolved` → `decision_running` → `recommendations_ready`/`abstained` → `outfit_selected` → `try_on_ready` | Session yêu cầu active body profile và tất cả asset yêu cầu phải active, thuộc đúng owner. |
| Try-on run | `proxy_fallback` | P0 chỉ mở `canonical_proxy`; mode rigged bị chặn cho đến khi có asset resolver, retargeting và runtime quality validation. |

> `canonical_proxy` vẫn là preview category. Nó **không** phải garment được reconstructed, rigged hoặc fitted vật lý.

## 3. Command API P0

Mọi command yêu cầu `actor_id` và `idempotency_key` dài tối thiểu 12 ký tự. `correlation_id` là optional; hệ thống sinh một correlation ID khi cần. Actor hiện được kiểm tra dựa vào `User` local hiện hữu; đây là adapter dev, chưa thay thế authentication/tenant isolation production.

| Method | Endpoint | Command | Kết quả |
|---|---|---|---|
| `POST` | `/workflow/body-profiles` | `CreateBodyProfile` | Tạo body revision `calibrated` cùng parametric contract. |
| `POST` | `/workflow/body-profiles/{profile_id}/confirm` | `ConfirmBodyProfile` | Kích hoạt profile và supersede active revision cũ. |
| `POST` | `/workflow/wardrobe-assets` | `CreateWardrobeAsset` | Tạo revision từ canonical garment hoặc Phase B `import_id`. |
| `POST` | `/workflow/wardrobe-assets/{asset_id}/approve` | `ApproveWardrobeAsset` | Đưa revision đã review vào active wardrobe. |
| `POST` | `/workflow/styling-sessions` | `CreateStylingSession` | Snapshot body/context/active assets. |
| `POST` | `/workflow/styling-sessions/{session_id}/outfit-decisions` | `RunOutfitDecision` | Chạy existing deterministic engine trong session boundary. |
| `POST` | `/workflow/styling-sessions/{session_id}/select-outfit` | `SelectOutfitCandidate` | Chỉ cho phép candidate thuộc decision run hiện hành. |
| `POST` | `/workflow/styling-sessions/{session_id}/try-on` | `RequestTryOn` | Tạo truthful proxy fallback run trong P0. |
| `GET` | `/workflow/body-profiles/{profile_id}?actor_id=` | Query | Khôi phục revision body theo đúng owner. |
| `GET` | `/workflow/wardrobe-assets/{asset_id}?actor_id=` | Query | Khôi phục asset/revision hiện hành theo đúng owner. |
| `GET` | `/workflow/styling-sessions/{session_id}?actor_id=` | Query | Khôi phục snapshot session theo đúng owner. |
| `GET` | `/workflow/audit-events/{aggregate_id}` | Query | Đọc immutable audit history của aggregate. |

## 4. Ví dụ workflow hoàn chỉnh

```text
1. Tạo User legacy hiện có.
2. POST BodyProfile → calibrated.
3. POST confirm → active.
4. Import garment ở Phase B hoặc chọn canonical garment.
5. POST WardrobeAsset → normalized/pending_review.
6. POST approve → active.
7. POST StylingSession với active body + active wardrobe assets.
8. POST OutfitDecision → recommendation record/evidence/version.
9. POST select-outfit với outfit ID hợp lệ.
10. POST try-on → proxy_fallback có limitation được công bố.
11. GET body/session theo `actor_id` để khôi phục đúng workflow case sau reload.
12. GET audit-events cho body/session/try-on khi cần truy vết.
```

Mỗi command retry cùng `actor_id`, command type và `idempotency_key` trả lại response đã lưu, không nhân đôi side effect.

## 5. Persistence và migration note

Các table P0 nằm ở `backend/app/workflow_models.py`. Môi trường local hiện khởi tạo table bằng `Base.metadata.create_all()` giống kiến trúc sẵn có. Đây là migration-compatible cho **database mới/local demo**, nhưng chưa phải cơ chế migration production.

Trước khi triển khai production, cần thêm Alembic và migration versioned cho các table sau:

| Table | Mục đích |
|---|---|
| `body_profile_revisions` | Revision và confirmation cho body contracts. |
| `workflow_wardrobe_assets` | Aggregate root cho asset tủ đồ. |
| `garment_asset_revisions` | Manifest/quality/provenance từng revision. |
| `styling_sessions` | Snapshot phiên tư vấn. |
| `outfit_decision_runs` | Decision versioned. |
| `try_on_runs` | Render intent, fallback và limitation. |
| `workflow_audit_events` | Audit stream theo aggregate. |
| `processed_workflow_commands` | Idempotency response record. |

## 6. Điều chưa làm trong P0, có chủ đích

P0 đặt business boundary trước. Các phần sau không được giả vờ đã có:

| Hạng mục | Trạng thái | Điều kiện trước khi mở |
|---|---|---|
| Auth/tenant isolation | Chưa có; dùng `actor_id` local adapter. | OAuth/session policy, tenant scope và authorization policy. |
| Outbox broker transaction | Chưa có; audit event lưu database. | Outbox table/publisher, retry/DLQ và event-consumer idempotency. |
| Full try-on GLB | Chưa có; chỉ proxy fallback. | Approved asset resolver, `SkeletonUtils` cloning/retarget, texture and collision checks. |
| VLM decision authority | Không dùng. | VLM chỉ perception/explanation trên verified decision record. |
| Object storage/retention | Chưa có; local filesystem. | Object ownership, signed access, deletion/retention policy. |
| Human review UI | API foundation có approve command. | Reviewer role, queue/dashboard, evidence display và audit policy. |

## 7. Verification

| Check | Result |
|---|---|
| Workflow state-machine tests | 7 scenarios passed: unknown actor, body confirmation/idempotency, asset lifecycle, full session, inactive/unapproved invariant, rigged render gate, Phase B import link. |
| Full backend suite | 69 passed, 1 skipped. |
| Backend coverage | 95% total. |
| Frontend dependency audit | 0 vulnerabilities. |
| Next.js production build | Passed. |
| Workflow diagram | Rendered successfully: `docs/workflow-foundation-p0.png`. |

## 8. Next logical increment

P1 nên thêm **context/constraint model đầy đủ, review work queue, structured feedback, evaluation events và decision score breakdown projection**. Chỉ sau khi P1 ổn định nên mở P2 để resolver asset GLB được approve và 3D try-on thật.
