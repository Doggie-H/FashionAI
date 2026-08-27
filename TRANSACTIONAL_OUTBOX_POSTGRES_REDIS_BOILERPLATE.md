# Transactional Outbox và PostgreSQL–Redis Idempotency Boilerplate

**Tác giả:** Manus AI  
**Phạm vi:** Bộ mã nguồn mẫu production-oriented cho command `CreateStylingSession`. Nó bổ sung PostgreSQL transaction, unique idempotency, Redis guard, outbox publisher, Celery consumer ledger và DDL migration mẫu. Đây là **boilerplate opt-in**, không tự chuyển môi trường local SQLite demo sang production.

## 1. Quy tắc kiến trúc không được đảo ngược

PostgreSQL là nguồn sự thật về command, aggregate state, audit event và outbox event. Redis không được dùng làm nguồn sự thật cho idempotency; Redis chỉ giảm duplicate request đang chạy và cache response đã commit. Nếu Redis lỗi, command vẫn có thể đúng nhờ unique constraint PostgreSQL. Nếu publish broker lỗi, aggregate vẫn đã commit và event sẽ retry từ outbox.

> Transactional Outbox không bảo đảm “exactly once delivery” trên mạng. Nó bảo đảm **at-least-once publish sau commit**. Exactly-once effect đạt được ở consumer bằng delivery ledger unique theo `consumer_name + event_id`.

| Thành phần | File | Trách nhiệm |
|---|---|---|
| Outbox model | `backend/app/workflow_models.py` | `WorkflowOutboxEvent`, `ProcessedEventDelivery`. |
| Idempotency/outbox service | `backend/app/services/workflow_outbox.py` | Fingerprint, Redis lock, DB command record, outbox enqueue, claim, retry, publish, consumer dedupe. |
| Celery consumer | `backend/app/tasks.py` | `stylist.handle_workflow_outbox_event`. |
| Queue routing | `backend/app/queue.py` | Tách `stylist_outbox` khỏi `garment_gpu`. |
| Publisher runner | `backend/scripts/publish_workflow_outbox.py` | Claim/publish loop sau commit. |
| Database migration | `backend/migrations/001_workflow_outbox_postgres.sql` | PostgreSQL DDL, index và constraints. |
| Infrastructure config | `docker-compose.workflow-infra.yml`, `.env.workflow.example` | PostgreSQL 16 và Redis 7.4 cho dev/staging. |

## 2. Trình tự command production

1. API lấy actor từ authentication server-side, không từ JSON do client tự khai báo.
2. Client gửi một `Idempotency-Key` chỉ cho một user intent và có thể gửi `Correlation-ID`.
3. Service truy vấn `processed_workflow_commands` bằng `(actor_id, command_type, idempotency_key)`.
4. Nếu record tồn tại, service so sánh request fingerprint. Cùng payload trả lại response cũ; khác payload trả `409`.
5. Nếu chưa có record, Redis `SET NX EX` tạo in-flight guard. Không có Redis không làm command fail; PostgreSQL vẫn bảo vệ correctness.
6. Trong **một** transaction PostgreSQL, service insert `StylingSession` snapshot, audit event, processed command và `WorkflowOutboxEvent` `pending`.
7. Commit thành công rồi API trả response. Khi unique constraint báo conflict, service rollback, đọc winning command, và trả lại stored response.
8. Publisher claim event `pending/retry` bằng `FOR UPDATE SKIP LOCKED`, đánh dấu `processing`, commit claim, sau đó publish Celery.
9. Publish thành công đánh dấu `published`; lỗi broker chuyển `retry` với exponential backoff. Consumer dùng delivery ledger để bỏ qua delivery lặp.

Sơ đồ chi tiết: `docs/transactional-outbox-create-styling-session.mmd` và PNG render tương ứng.

## 3. Khởi tạo development/staging

### 3.1. Chuẩn bị cấu hình

```powershell
cd 'D:\Study\Studio Project\3d-ai-stylist'
Copy-Item .env.workflow.example .env.workflow
# Đặt hai password riêng, dài, không commit .env.workflow.
```

Compose đọc biến từ `.env.workflow` khi caller truyền file environment. Không dùng password placeholder trong bất kỳ môi trường nào.

```powershell
docker compose --env-file .env.workflow -f docker-compose.workflow-infra.yml up -d
```

### 3.2. Áp dụng schema

Đây là migration SQL mẫu. Khi đưa vào production, chuyển nội dung nó thành revision Alembic đã review thay vì chạy file thủ công.

```powershell
$env:DATABASE_URL = 'postgresql+psycopg2://...'
cd backend
psql $env:DATABASE_URL -f migrations/001_workflow_outbox_postgres.sql
```

Lệnh trên yêu cầu PostgreSQL client. Có thể chạy thông qua container `postgres` hoặc quy trình Alembic của CI/CD. Không dùng `Base.metadata.create_all()` làm migration production.

### 3.3. Khởi động thành phần runtime

```powershell
cd 'D:\Study\Studio Project\3d-ai-stylist'
$env:IDEMPOTENCY_REDIS_URL = 'redis://:...@127.0.0.1:6379/2'
$env:CELERY_BROKER_URL = 'redis://:...@127.0.0.1:6379/0'
$env:CELERY_RESULT_BACKEND = 'redis://:...@127.0.0.1:6379/1'

# Terminal 1: API.
.\run-queue.ps1 -Role api

# Terminal 2: Celery consumer cho event đã publish.
.\run-queue.ps1 -Role outbox-worker

# Terminal 3: publisher claim và publish event outbox.
cd backend
python scripts\publish_workflow_outbox.py
```

Publisher là process bền vững. Trong production nó nên chạy như deployment/service riêng, có health check và metrics; không nhúng loop vô FastAPI request process.

## 4. Cách dùng service boilerplate

`execute_idempotent_with_outbox` nhận một `handler(correlation_id, command_id)`. Handler chỉ được mutate database session và trả `(result, event_specs)`; tuyệt đối không gọi Celery, email hoặc HTTP webhook trước `db.commit()`.

```python
from app.services.workflow_outbox import (
    OUTBOX_EVENT_STYLING_SESSION_OPENED,
    RedisIdempotencyGuard,
    execute_idempotent_with_outbox,
)

result = execute_idempotent_with_outbox(
    db,
    actor_id=authenticated_actor.id,
    command_type="CreateStylingSession",
    idempotency_key=request.headers["Idempotency-Key"],
    request_payload=command.model_dump(mode="json"),
    correlation_id=request.headers.get("Correlation-ID"),
    guard=RedisIdempotencyGuard.from_environment(),
    handler=lambda correlation_id, command_id: (
        create_session_snapshot_in_current_transaction(db, command, correlation_id),
        [{
            "event_type": OUTBOX_EVENT_STYLING_SESSION_OPENED,
            "aggregate_type": "StylingSession",
            "aggregate_id": session_id,
            "payload": {"session_id": session_id, "command_id": command_id},
        }],
    ),
    serializer=lambda result: result.model_dump(mode="json"),
    deserializer=StylingSessionV1.model_validate,
)
```

P0 `workflow_service.py` vẫn giữ dispatcher SQLite hiện tại để test/demo ổn định. Khi migration/authentication đã sẵn sàng, thay wrapper `CreateStylingSession` bằng service trên, giữ nguyên domain validation và snapshot construction bên trong handler. Không bật nửa vời: API, migration, publisher và consumer phải được deploy cùng release.

## 5. Idempotency contract cho UI

| Tình huống UI | `Idempotency-Key` | `Correlation-ID` | Kết quả mong đợi |
|---|---|---|---|
| Người dùng click “Create session” lần đầu | Sinh UUID/key mới. | Sinh một case ID hoặc để server sinh. | Tạo một session. |
| Browser retry sau timeout | Giữ nguyên key. | Giữ nguyên correlation ID. | Trả cùng session ID/response. |
| Người dùng sửa context rồi click lại | Sinh key mới. | Có thể giữ correlation ID cùng case. | Tạo command mới có snapshot mới. |
| Người dùng vô tình reuse key với payload khác | Không nên làm. | Không thay đổi ý nghĩa. | `409 IdempotencyConflict`. |
| Redis unavailable | Key vẫn được gửi. | Không đổi. | PostgreSQL unique constraint vẫn là safety net. |

Không sinh idempotency key mỗi lần render React. Sinh nó tại handler của action user, lưu khi request in-flight, và tái sử dụng đúng key khi retry.

## 6. Retry, lock và dead-letter policy

| Cơ chế | Boilerplate hiện có | Production hardening tiếp theo |
|---|---|---|
| API concurrent duplicate | Redis lock nhỏ + PostgreSQL unique constraint recovery. | Instrument lock collision, response replay rate và transaction conflict. |
| Publisher collision | `FOR UPDATE SKIP LOCKED` khi dialect PostgreSQL. | Lease expiry/reclaim cho `processing` event bị worker chết. |
| Broker failure | `retry`, `available_at`, exponential backoff capped 300s, `last_error`. | `max_attempts`, `dead_letter`, alerting và manual replay API. |
| Consumer duplicate | Unique delivery ledger. | Consumer-specific transaction boundary và idempotent external API key. |
| Schema evolution | `event_type` versioned bằng `.v1`; `schema_version`. | Upcaster/compatibility tests trước khi producer thay payload. |

## 7. Kiểm thử đã có

`backend/tests/test_workflow_outbox.py` xác minh bốn tình huống: replay cùng key tạo đúng một command/outbox event; reuse key với payload khác bị từ chối; publisher retry broker failure rồi publish thành công; consumer effect chạy đúng một lần theo delivery ledger. Test này chạy SQLite để unit test deterministic. `SKIP LOCKED`, JSONB, concurrent claim thật và network Redis phải được integration-test trên PostgreSQL/Redis riêng ở CI hoặc staging.

## 8. Chưa được tuyên bố hoàn thành

Boilerplate **không** tự giải quyết authentication, tenant isolation, Alembic history, observability, Kubernetes/systemd deployment, encrypted secrets, outbox lease reaper, dead-letter UI, review queue, hay PostgreSQL integration test live. Những mục này là điều kiện P1/production, không phải chi tiết có thể thay bằng Redis cache.


## 9. Authentication-derived actor và correlation propagation

Production workflow endpoints sử dụng `WORKFLOW_AUTH_MODE=jwt`. `Authorization: Bearer <JWT>` phải chứa `sub` là user ID dương; `tenant_id` được đọc nếu token có claim tương ứng. API không lấy `actor_id` từ JSON. Nếu caller gửi `actor_id` trái với subject token, request bị từ chối `403`.

`Idempotency-Key` là bắt buộc ở header production. `X-Correlation-ID` là tùy chọn; nếu không có, transport adapter tạo một `corr_*` duy nhất rồi gắn lại vào command, audit event, `ProcessedCommand`, outbox payload và Celery payload. Việc giữ một ID duy nhất là điều kiện để trace một StylingSession xuyên API, PostgreSQL, publisher và worker.

```powershell
$env:WORKFLOW_AUTH_MODE = 'jwt'
$env:WORKFLOW_JWT_SIGNING_KEY = '<secret-at-least-32-bytes>'
$env:WORKFLOW_OUTBOX_ENABLED = '1'
$env:AI_STYLIST_AUTO_CREATE_DB = '0'
```

`legacy_body` chỉ còn là compatibility path khi `AI_STYLIST_DEMO_MODE=1`; không bật mode đó ở staging hay production.

## 10. Alembic và Testcontainers

Alembic đã có baseline `20260826_00` cho legacy/Workflow Foundation và revision `20260826_01` cho `workflow_outbox_events` cùng `processed_event_deliveries`. Database PostgreSQL clean dùng `alembic upgrade head`. Database dev đã được tạo bởi `create_all` phải được backup, đối chiếu schema và **stamp baseline có kiểm soát** trước khi upgrade; không chạy baseline create-table trực tiếp trên database đã có tables.

```powershell
cd backend
$env:DATABASE_URL = 'postgresql+psycopg2://...'
python -m alembic upgrade head

# Chạy integration test thật với Docker PostgreSQL 16 và Redis 7.4.
$env:RUN_TESTCONTAINERS = '1'
python -m pytest -q tests/test_workflow_auth_outbox_integration.py -m containers
```

Bộ test Testcontainers áp dụng Alembic vào PostgreSQL mới, kiểm tra hai thread tạo StylingSession cùng idempotency key chỉ lưu đúng một command/outbox event nhờ unique constraint, và kiểm tra Redis in-flight guard trả trạng thái đang xử lý rồi replay đúng response đã commit. Test không thay thế staging test về authentication provider thật, lease-reaper, dead letter hay external consumer.
