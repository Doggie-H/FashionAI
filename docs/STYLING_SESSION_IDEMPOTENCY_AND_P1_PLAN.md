# StylingSession Snapshot, Idempotency và Kế hoạch P1

**Tác giả:** Manus AI  
**Phạm vi:** Giải thích implementation P0 hiện hữu và kế hoạch triển khai P1 cho UI/session, reviewer queue, feedback và governance runtime.

## 1. Tại sao `StylingSession` là aggregate trung tâm

Một lời khuyên phối đồ không được xem là hàm đơn giản `body + tags → text`. Nó là kết quả của một **case** tại một thời điểm: người nào, đang dùng body calibration nào, sở hữu các asset nào, muốn mặc vào hoàn cảnh nào, catalog/rules nào đã được áp dụng, và sau đó đã chọn/thử/phản hồi ra sao.

`StylingSession` biến case đó thành một aggregate bền vững. Tại P0, session lưu bốn nhóm dữ liệu: `owner_id`, `body_profile_id`, `context`, và hai snapshot là `body_contract_snapshot` cùng `wardrobe_snapshot`. Nó còn giữ state của workflow, `active_decision_run_id`, `selected_outfit_id`, thời điểm tạo/cập nhật.

> Session snapshot không nói rằng thông tin không bao giờ thay đổi. Nó nói rằng **quyết định đã được tạo phải luôn có thể giải thích dựa trên đúng dữ liệu tại thời điểm nó được tạo**.

## 2. Luồng tạo StylingSession snapshot, từng bước

### 2.1. Tiền điều kiện

Lệnh `POST /workflow/styling-sessions` nhận `actor_id`, `idempotency_key`, `body_profile_id`, `StyleContextV1` và danh sách `wardrobe_asset_ids` tùy chọn. Service không tạo session ngay. Nó kiểm tra theo thứ tự:

| Kiểm tra | Lý do nghiệp vụ | Kết quả nếu không đạt |
|---|---|---|
| Actor tồn tại | Không cho workflow không có owner. | `404`. |
| Body profile thuộc actor | Chống sử dụng body profile của người khác. | `404`. |
| Body profile đang `active` | User phải xác nhận calibration trước khi hệ thống quyết định dựa trên số đo đó. | `409`. |
| Asset được yêu cầu thuộc actor và `active` | Không dùng import dở dang, asset bị từ chối, hoặc asset của người khác. | `409`. |
| Active revision của asset hợp lệ | Mỗi asset phải chỉ ra revision chính xác dùng cho session. | `409`. |

Nếu caller không truyền `wardrobe_asset_ids`, P0 snapshot toàn bộ asset active của actor. Nếu caller truyền danh sách, mọi ID trong danh sách đều phải active; không có cơ chế “lọc bớt silently”. Điều này giúp UI biết rõ asset nào đã bị chặn thay vì nhận một outfit thiếu item mà không rõ lý do.

### 2.2. Dữ liệu nào được chụp lại

`body_contract_snapshot` là toàn bộ `ParametricBodyContractV1` đã được tạo khi calibrate: raw measurements, `shape_parameters`, `bone_length_scales`, visual flags, body model, skeleton và calibration version. Trong session sau này, decision engine đọc snapshot này, không đọc lại profile live.

`wardrobe_snapshot` là danh sách `WardrobeAssetRevisionV1`. Mỗi item bao gồm `asset_id`, `revision_id`, category, canonical garment ID, import ID nếu có, quality summary, trạng thái, và timestamps. Quan trọng nhất đối với decision là `canonical_garment_id`: P0 chỉ truyền những garment canonical đã active trong snapshot vào engine. Asset chưa approve sẽ không đi vào session.

`context` là `StyleContextV1`: occasion, preferred styles, season, fit preference, required slots và excluded colors. Context cũng phải nằm trong session vì “đi làm mùa thu” và “đi event mùa hè” không phải cùng một case ngay cả khi body/tủ đồ không đổi.

### 2.3. Tính bất biến và ví dụ drift

Giả sử thứ Hai người dùng tạo Session A với body profile `body_01`, áo `wad_shirt` revision 1 và quần `wad_trouser` revision 2. Thứ Ba người dùng sửa body, import áo mới và archive quần cũ. Session B tạo vào thứ Ba dùng dữ liệu mới. Session A vẫn phải giữ snapshot thứ Hai để trả lời được: “Vì sao lúc đó outfit này được chọn?” và để reviewer tái hiện decision.

P0 lưu snapshot bằng JSON trong database. Điều này là đúng để **replay explanation** và audit. Nó chưa đủ cho reproducible re-execution hoàn hảo: engine hiện đọc catalog seed đang hoạt động khi chạy rồi chỉ lưu `catalog_version` trong `OutfitDecisionRun`. Nếu catalog version bị sửa nhưng version string không đổi, chạy lại decision có thể khác. P1 phải thêm catalog snapshot/hash hoặc catalog revision immutable vào `OutfitDecisionRun`.

### 2.4. State machine P0

```text
inputs_resolved
  → decision_running
  → recommendations_ready ──→ outfit_selected ──→ try_on_ready
  ↘ abstained
```

`decision_running` là transient state trong cùng command hiện tại; sau khi deterministic engine hoàn tất, session chuyển `recommendations_ready` hoặc `abstained`. `select-outfit` chỉ chấp nhận một `outfit_id` có trong `OutfitDecisionRun` đang active. `try-on` P0 chỉ cho `canonical_proxy`, tạo `TryOnRun` với `proxy_fallback` và limitation công khai. Mọi yêu cầu `rigged_template` hoặc `approved_reconstructed_asset` bị từ chối đến khi có approved GLB resolver, skeleton retargeting và runtime quality check.

## 3. Cơ chế idempotency theo actor/key/correlation

### 3.1. Ba trường phục vụ ba câu hỏi khác nhau

| Trường | Câu hỏi được trả lời | P0 thực hiện |
|---|---|---|
| `actor_id` | “Ai có quyền thực hiện/lấy lại kết quả?” | Làm owner scope của aggregate và thành phần của unique idempotency key. Hiện là local dev adapter, không phải auth production. |
| `idempotency_key` | “Request retry này có phải là command cũ không?” | Bắt buộc, unique theo `(actor_id, command_type, idempotency_key)`. |
| `correlation_id` | “Các event/log/job thuộc cùng một business case nào?” | Optional trong command; ghi vào audit event và command record khi caller truyền. |

Idempotency không phải là cache URL chung. Key được ràng buộc bởi **actor** và **command type**. Vì vậy `actor=12`, `CreateStylingSession`, `key=checkout-01` không đụng với `actor=12`, `RequestTryOn`, `key=checkout-01`, cũng không đụng với actor khác.

### 3.2. Trình tự xử lý hiện tại

1. Router validate Pydantic contract.
2. Service kiểm tra `ProcessedCommand` theo actor, command type và idempotency key.
3. Nếu thấy record, service trả `response_payload` đã lưu; không tạo profile/asset/session/run/event mới.
4. Nếu chưa thấy record, service kiểm tra owner/state invariant, tạo aggregate state, ghi `WorkflowAuditEvent`, serialise response và thêm `ProcessedCommand`.
5. `db.commit()` commit state, event và response record trong cùng SQLite transaction P0.
6. Client nhận response. Nếu mạng timeout sau commit, client gửi lại cùng key và nhận đúng response cũ.

Ví dụ: người dùng bấm “Tạo Styling Session”, trình duyệt timeout nhưng backend đã commit. UI retry cùng `idempotency_key`; backend trả cùng `session_id` thay vì tạo session thứ hai. Đây là lý do key phải được UI giữ trong lifecycle của cùng một user intent và chỉ đổi khi user tạo một intent mới.

### 3.3. Những điều P0 chưa giải quyết hoàn toàn

P0 giải quyết retry tuần tự rất tốt nhưng chưa là distributed-idempotency production-complete. Có bốn điểm phải minh bạch:

| Hạn chế P0 | Nguyên nhân | Bổ sung P1/P2 |
|---|---|---|
| `actor_id` do client gửi | Chưa có auth/session server-side. | Lấy actor/tenant từ access token; bỏ tin cậy client-supplied actor ID. |
| Race condition đồng thời | Hai request cùng key có thể cùng đọc “chưa tồn tại” trước unique constraint. | PostgreSQL + unique constraint handling + transaction isolation/row lock; khi conflict thì đọc response record thắng cuộc. |
| Correlation ID fallback chưa thống nhất tuyệt đối | Khi client không gửi correlation ID, audit handler có thể dùng aggregate ID còn `ProcessedCommand` có thể sinh `corr_*` khác. | Sinh **một** correlation ID ngay đầu command dispatcher và truyền cùng ID vào mọi event, job, log và response. |
| Không có transactional outbox | Audit event được lưu, nhưng chưa publish queue event sau commit. | Outbox table, publisher, consumer idempotency, retry/DLQ và observability. |

Điểm thứ ba đặc biệt quan trọng: hiện tại cần khuyến nghị UI **luôn gửi `correlation_id`**. P1 phải sửa dispatcher để server sinh correlation ID duy nhất khi client thiếu, sau đó dùng đúng giá trị đó cho `ProcessedCommand`, `WorkflowAuditEvent` và Celery event.

## 4. Phạm vi P1 đề xuất

P1 không nên nhảy thẳng đến mesh 3D. Nó phải biến P0 thành trải nghiệm người dùng và reviewable operations.

| Workstream | Mục tiêu | Deliverable chính |
|---|---|---|
| Session UI | Cho người dùng tạo, tiếp tục, xem state và đóng StylingSession. | Session dashboard, profile confirmation, context form, outfit shortlist, state timeline. |
| Wardrobe lifecycle UI | Làm rõ import → normalize → review → active. | Asset card có status, quality summary, action chờ review. |
| Reviewer queue | Tách review work khỏi user UI và tạo quyết định reviewer có audit. | `ReviewTask`, claim/complete flow, reviewer evidence panel, approve/reject/rework. |
| Decision feedback | Thu feedback có cấu trúc sau selection/try-on. | Like/dislike, reason codes, fit/context/render issue, free note, confidence. |
| Event/outbox hardening | Chuyển audit-only event thành async business event an toàn. | Outbox, idempotent publisher, queue monitoring, retry/DLQ contract. |
| Governance | Làm actor/correlation/catalog version đáng tin cậy. | Auth-derived actor, single correlation dispatcher, catalog hash/revision, retention policy. |

## 5. P1 UI/session: user journey và công việc cụ thể

### 5.1. Luồng trải nghiệm cần xây

```text
My Sessions
  → Start session / Resume draft
  → Choose or confirm active BodyProfile
  → Choose active WardrobeAssets and capture context
  → Inputs resolved summary
  → Run outfit decision
  → Inspect candidate, evidence, trade-off and limitation
  → Select outfit
  → View truthful proxy try-on
  → Submit structured feedback
  → Close or reopen session
```

UI không được tự kết hợp API Phase A/B như trước. Mọi action phải gọi command `/workflow`, lưu `idempotency_key` theo user intent, dùng `correlation_id` cho case, sau đó refresh aggregate qua owner-scoped query endpoint. UI phải hiển thị state server-side, không tự suy diễn một request thành success khi mạng lỗi.

### 5.2. Backlog UI/session theo thứ tự

| Thứ tự | Hạng mục | API cần bổ sung hoặc hoàn thiện | Acceptance criteria |
|---|---|---|---|
| 1 | Authentication/dev actor adapter | `GET /workflow/me`, actor derived server-side. | Không còn nhập `actor_id` thủ công trong UI production path. |
| 2 | Session list/retrieve | `GET /workflow/styling-sessions?status=&cursor=`. | Có thể resume đúng owner sau reload. |
| 3 | Body profile manager | List revisions, create, confirm, supersede. | Không thể start session với profile chưa active. |
| 4 | Wardrobe lifecycle board | List assets/revisions/filter status. | Asset chưa active có label và không được selectable. |
| 5 | Context and constraints form | Extend `StyleContextV1` cho weather, mobility, budget, modesty, color/style goals. | Input contradiction hiển thị actionable error. |
| 6 | Decision workspace | Decision timeline, score/evidence/trade-off/abstention UI. | User chỉ select candidate thuộc active decision run. |
| 7 | Try-on workspace | Display `render_mode`, asset quality and limitation. | Proxy không bao giờ bị copy là “3D fit chính xác”. |
| 8 | Feedback form | `POST /workflow/styling-sessions/{id}/feedback`. | Mỗi feedback có reason code, target candidate/try-on và provenance. |

## 6. P1 reviewer queue: lifecycle và API

### 6.1. `ReviewTask` aggregate

P1 nên tạo table/aggregate `ReviewTask` thay vì biến approve endpoint thành nút boolean đơn giản.

```text
OPEN → CLAIMED → IN_REVIEW → APPROVED
                         ↘ REJECTED
                         ↘ REWORK_REQUIRED
OPEN / CLAIMED → EXPIRED / CANCELLED
```

Mỗi task phải có `task_id`, tenant/owner, subject type/id/revision, review type, priority, assignee, due time, evidence snapshot, checklist version, decision, reason codes, reviewer note, created/claimed/completed timestamps và audit events. A reviewer phải claim task atomically; hai reviewer không được cùng submit decision cho một task.

### 6.2. Review categories P1

| Review type | Subject | Checklist tối thiểu | Decision side effect |
|---|---|---|---|
| `garment_metadata` | Garment asset revision | Category, color/style/material, source/image clarity, ownership. | Activate, reject hoặc rework asset revision. |
| `garment_mesh_quality` | Reconstruction result | Source hash, mesh hash, skeleton, rest pose, anchors, skin weights, bounds, intersections, license. | Cho phép `rigged_template` hoặc giữ pending/failed. |
| `decision_quality` | Outfit decision run | Context fit, constraint satisfaction, evidence faithfulness, unsupported claims. | Add evaluation label; không tự sửa recommendation history. |
| `user_feedback_triage` | Feedback record | Issue type, severity, reproducibility. | Tạo bug/rework/evaluation action. |

### 6.3. API P1 reviewer queue

| Method | Endpoint | Idempotency/state rule |
|---|---|---|
| `GET` | `/review-tasks?status=open&review_type=` | Role-scoped list, cursor pagination. |
| `POST` | `/review-tasks/{id}/claim` | Atomic claim; conflict nếu đã có assignee. |
| `POST` | `/review-tasks/{id}/submit-decision` | `approve`, `reject`, `rework`; command idempotent. |
| `POST` | `/review-tasks/{id}/release` | Chỉ assignee/admin; về `OPEN` nếu chưa complete. |
| `GET` | `/review-tasks/{id}` | Evidence snapshot, checklist, event timeline. |
| `GET` | `/review-tasks/{id}/audit-events` | Reviewer trace riêng. |

## 7. Điều kiện chuẩn bị trước khi viết P1

| Nhóm chuẩn bị | Quyết định cần chốt | Tại sao không nên bỏ qua |
|---|---|---|
| Identity | Chọn auth provider, role `customer`/`reviewer`/`admin`, tenant model. | Nếu actor vẫn do client gửi, review ownership và private wardrobe không an toàn. |
| Database | PostgreSQL target, Alembic baseline, backup/migration policy. | SQLite/create_all không đủ cho concurrent reviewer claim và durable uniqueness. |
| Permission matrix | Ai xem/sửa/approve/reject/export/delete được body/asset/session. | Số đo và ảnh là dữ liệu nhạy cảm; reviewer không cần toàn quyền account. |
| Review rubric | Checklist/version, decision reason codes, SLA, escalation. | Không có rubric sẽ tạo review chủ quan và evaluation unusable. |
| Storage | Asset ownership, retention/deletion, signed access, hash strategy. | Import/mesh evidence không thể chỉ dựa file path local. |
| Observability | Correlation propagation, structured logs, task latency/error/queue depth. | Cần debug case từ UI → DB → queue → reviewer decision. |
| UX copy | Thuật ngữ `proxy`, `pending review`, `approved asset`, limitation. | Tránh overclaim AI/3D và giảm khiếu nại người dùng. |
| Evaluation | Feedback taxonomy, reviewer sampling, privacy-safe analytics. | Không dùng raw like/dislike làm ground truth tự động. |

## 8. Lộ trình thực thi đề xuất

### Sprint 0: P1 readiness

Thiết lập Alembic baseline và PostgreSQL development/staging; chốt auth/role matrix; sửa command dispatcher để sinh single correlation ID; thêm outbox schema; version hóa catalog hash; viết migration/data-retention decision record. Không nên viết reviewer UI trước khi five items này được chấp thuận.

### Sprint 1: Session-first user UI

Tạo session list/detail, body confirmation, wardrobe active-state board và context form. Thay state client-only bằng server aggregate refresh. Mỗi button command tự tạo idempotency key theo intent, disable khi in-flight, và retry cùng key sau timeout. Hoàn thành khi user reload browser vẫn resume đúng session và không tạo duplicate session/decision/try-on.

### Sprint 2: Decision workspace và feedback

Hiển thị evidence, trade-off, abstention và render limitation. Thêm structured feedback record, owner-scoped history, catalog/rule/model version display. Hoàn thành khi decision có thể truy từ session đến snapshot và feedback được gắn đúng candidate/try-on run.

### Sprint 3: Reviewer queue MVP

Tạo `ReviewTask`, reviewer role/claim, evidence panel, approve/reject/rework command, audit timeline và asset activation side effect. Hoàn thành khi hai reviewer concurrent không thể complete cùng task và rejected asset không vào active wardrobe/session.

### Sprint 4: Outbox, metrics và P1 release hardening

Publish domain event sau commit, queue retry/DLQ, correlation log/tracing, dashboard SLA, permission tests, migration rehearsal và UAT with reviewer rubric. Hoàn thành khi failure/retry có thể replay an toàn và mọi decision/review có audit trail.

## 9. Definition of Done P1

P1 chỉ nên được gọi là complete khi tất cả điều kiện sau đều đúng:

1. UI bắt đầu/resume/đóng session qua aggregate server-side, không ghép endpoint ad-hoc.
2. Actor đến từ authentication và mọi query/command được tenant/role scope.
3. Idempotency chịu được retry tuần tự và concurrent conflict có response xác định.
4. Một correlation ID được truyền đồng nhất qua command, audit event, outbox, Celery task và log.
5. Wardrobe asset chưa approved không xuất hiện trong user decision selector.
6. Reviewer claim/submit decision có concurrency control, rubric version và audit timeline.
7. Decision có snapshot/hash/version đủ để explain/replay; user feedback có target và reason code.
8. Proxy/rigged/reconstructed asset luôn mang render mode, quality status và limitation đúng sự thật.
9. Migration, backup/restore, retention/deletion, observability và permission tests đã được rehearsal ở staging.
