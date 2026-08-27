# P1/P2 Endpoint Verification and Provider Runbook

**Status date:** 26 August 2026  
**Scope:** P1 session/reviewer workflow, P2 try-on resolution, the current S3-compatible storage boundary, and the remote GPU worker boundary.

> **Operational conclusion.** The P1/P2 API and workflow invariants below have been tested locally. The S3 adapter and Kubernetes GPU-worker manifest are **deployment boundaries and templates**, not proof that the Phase B upload/segmentation/reconstruction pipeline already runs on object storage or with a real reconstruction provider. Do not set a job or a UI state to `rigged_template` merely because a GPU worker exists.

## 1. Test evidence and result interpretation

| Validation | Latest result | What it proves | What it does not prove |
|---|---:|---|---|
| P1/P2 focused regression | **10 passed, 2 deselected** | Feedback provenance, reviewer claim/decision idempotency, HTTP API flow, proxy fallback, owner-scoped local storage, and P1/P2 consumer dedupe operate under the local test environment. | Real network delivery, S3 access, real garment reconstruction quality, or physical fitting. |
| HTTP integration contract | **1 passed** | JWT owner creates/uses a session; reviewer claims and decides a triage task; response gives proxy fallback for an unapproved rigged request. | Browser UX across a live API deployment or OIDC/JWKS integration. |
| PostgreSQL/Redis Testcontainers | **2 passed** | Alembic upgrade head, PostgreSQL concurrent unique-key recovery, and Redis in-flight guard/replay behavior work in containers. | Production database sizing, real broker throughput, or multi-region behavior. |
| Full backend regression from prior validation | **86 passed, 1 skipped, 2 deselected** | Existing backend behaviors remained compatible before the additional endpoint and consumer regression tests were added. | A production readiness certification. |
| Frontend build and audit | Build succeeded for `/`, `/admin`, `/review`, `/sessions`; `npm audit` found **0 vulnerabilities** | TypeScript/Next route compilation and dependency audit at the checked state. | Correctness of runtime API credentials, access policies, or real GLB rendering. |

The focused test log is retained at `backend/reports/p1_p2_regression_final.txt`; the HTTP contract log is `backend/reports/p1_p2_http_contract.txt`; the PostgreSQL/Redis run is `backend/reports/p1_p2_testcontainers.txt`.

### 1.1 Newly verified endpoint flow

The HTTP test performs the following end-to-end sequence using a short-lived test JWT: create and confirm a body profile, create and activate a top and bottom asset, create a `StylingSession`, execute and read an outfit decision, select a candidate, request `rigged_template`, receive a truthful `canonical_proxy` fallback because approved mesh evidence is absent, submit feedback, claim the generated review task, submit a reviewer decision, and confirm an `EvaluationLabel` exists. This test covers the real FastAPI router/dependency layer, not only a service function.

### 1.2 Consumer remediation made during verification

Inspection found that the generic outbox consumer handled only `StylingSessionOpened.v1`, while P1/P2 commands can emit `StylingSessionFeedbackRecorded.v1` and `TryOnRequested.v1`. Without remediation, a live worker would retry unsupported event types and eventually dead-letter them. The consumer now accepts all three versioned event types as idempotent projection extension points; `test_p1_p2_outbox_consumer.py` verifies first delivery is processed and repeat delivery is a no-op. This is intentionally a no-side-effect projector until a dedicated notification, analytics, or rendering projector is designed.

## 2. P1/P2 endpoint contract

The generated inventory is attached as `backend/reports/p1_p2_openapi_inventory.json`. In production command endpoints require `Authorization: Bearer <JWT>`, `Idempotency-Key`, and normally `X-Correlation-ID`; the latter is generated server-side when missing. The body `actor_id` compatibility field applies only to explicit local demo mode.

| Method | Endpoint | Role / scope | Success | Key runtime behavior |
|---|---|---|---|---|
| `GET` | `/workflow/me` | Authenticated actor | `200` | Returns JWT-derived actor, tenant, roles, auth mode. |
| `GET` | `/workflow/body-profiles` | Owner | `200` | Cursor list for resume; legacy demo supports `actor_id` query. |
| `POST` | `/workflow/body-profiles` | Owner command | `201` | Creates revision; confirmation remains a separate transition. |
| `POST` | `/workflow/body-profiles/{id}/confirm` | Owner command | `200` | Activates confirmed body revision. |
| `GET` | `/workflow/wardrobe-assets` | Owner | `200` | Cursor list, optionally status-filtered. |
| `POST` | `/workflow/wardrobe-assets` | Owner command | `201` | Creates a revision; imports needing review open a `garment_metadata` task. |
| `POST` | `/workflow/wardrobe-assets/{id}/approve` | Owner command, legacy path | `200` | Existing compatibility approval path. Prefer reviewer-task decision for governed import review. |
| `GET` | `/workflow/styling-sessions` | Owner | `200` | Cursor list for session resume. |
| `POST` | `/workflow/styling-sessions` | Owner command | `201` | Stores immutable body/wardrobe/context snapshot. |
| `GET` | `/workflow/styling-sessions/{id}` | Owner | `200` | Reads server aggregate state. |
| `POST` | `/workflow/styling-sessions/{id}/outfit-decisions` | Owner command | `200` | Persists deterministic evidence, score breakdown, rejected candidates, and abstention. |
| `GET` | `/workflow/styling-sessions/{id}/outfit-decisions/{runId}` | Owner | `200` | Restores immutable decision evidence. |
| `POST` | `/workflow/styling-sessions/{id}/select-outfit` | Owner command | `200` | Selects only a candidate in the active decision run. |
| `POST` | `/workflow/styling-sessions/{id}/try-on` | Owner command | `201` | Emits `TryOnRequested.v1`; returns requested **and actual** mode plus quality/evidence limitations. |
| `GET` | `/workflow/try-on-runs/{id}` | Owner | `200` | Reads owner-scoped resolved binding evidence. |
| `POST` | `/workflow/styling-sessions/{id}/feedback` | Owner command | `201` | Validates decision/candidate/try-on provenance, emits `StylingSessionFeedbackRecorded.v1`, and may open triage. |
| `GET` | `/workflow/styling-sessions/{id}/feedback` | Owner | `200` | Cursor list of feedback evidence. |
| `GET` | `/review-tasks` | `reviewer` or `admin` | `200` | Filters queue by status/type; reviewers may see operational evidence. |
| `POST` | `/review-tasks` | `reviewer` or `admin` | `201` | Creates a typed, auditable manual task. |
| `GET` | `/review-tasks/{id}` | `reviewer` or `admin` | `200` | Reads task/evidence snapshot. |
| `POST` | `/review-tasks/{id}/claim` | `reviewer` or `admin` | `200` | Atomic transition from `open` to `claimed`. |
| `POST` | `/review-tasks/{id}/submit-decision` | Assignee or `admin` | `200` | `approve`, `reject`, or `rework`; may mutate garment lifecycle or create label. |
| `POST` | `/review-tasks/{id}/release` | Assignee or `admin` | `200` | Releases a non-terminal task to `open`. |
| `GET` | `/review-tasks/{id}/audit-events` | `reviewer` or `admin` | `200` | Returns review timeline/correlation evidence. |

The generated OpenAPI currently advertises success and validation (`422`) responses most consistently. Runtime dependencies also emit `401`, `403`, `404`, and `409` for auth, ownership, state and idempotency conditions. Add explicit `responses=` metadata to routes before using the OpenAPI document as an external partner contract.

## 3. P2 try-on decision rules

| Requested mode | Required persisted conditions | Actual result when conditions fail |
|---|---|---|
| `canonical_proxy` | None beyond selected snapshot asset | `canonical_proxy`, quality `proxy`. |
| `rigged_template` | Valid generated GLB, matching target skeleton, anchors, skin weights, scale/bounds/intersection checks, and `review_status=approved`. | `canonical_proxy`, status `proxy_fallback`, quality `pending_review`. |
| `approved_reconstructed_asset` | Same approved mesh-quality conditions, plus a persisted generated asset URI. | Same truthful proxy fallback. |

A `201` response does not itself mean a rigged garment was rendered. The UI must inspect `render_mode`, `quality_status`, `asset_bindings`, and `limitations` rather than using requested mode as the display label.

## 4. S3-compatible storage configuration

### 4.1 Current code boundary and limitation

`app.services.asset_storage` defines `LocalAssetStorage` and `S3CompatibleAssetStorage`; the latter uses `boto3`, owner-prefixed keys, and short-lived signed reads. Copy `backend/.env.p2-provider.example` into a secret manager-backed deployment configuration, never into version control.

**Important limitation:** `app.services.garment_import.import_garment_image`, `write_manifest`, and `segment_garment` currently use the local `uploads/` filesystem. Therefore, setting `AI_STYLIST_STORAGE_BACKEND=s3` alone **does not migrate real Phase B source images, manifests, segmentation output, or generated mesh files to S3**. It only makes the storage adapter available to code that explicitly calls it. A production migration needs the implementation tasks in Section 4.5 before enabling an S3-only remote worker.

### 4.2 Safe configuration values

| Variable | Example form | Requirement |
|---|---|---|
| `AI_STYLIST_STORAGE_BACKEND` | `s3` | Enables the S3-compatible adapter only. |
| `AI_STYLIST_S3_BUCKET` | `ai-stylist-private-prod` | Private bucket; do not make object prefixes public. |
| `AI_STYLIST_S3_REGION` | `ap-southeast-1` | Provider region when applicable. |
| `AI_STYLIST_S3_ENDPOINT_URL` | `https://s3.example.internal` | Needed for MinIO, R2, B2 or other S3-compatible endpoint; omit for standard AWS endpoint selection. |
| `AI_STYLIST_S3_KEY_PREFIX` | `ai-stylist` | Stable partition prefix; do not change without a migration. |
| credential variables or workload identity | Provider-specific | Supply through workload identity or secret manager, never committed source/environment examples. |

The adapter creates object keys such as `ai-stylist/owners/{owner_id}/{namespace}/{uuid}.{suffix}`. This is a defense-in-depth partition; application authorization must still verify owner/tenant before requesting a signed URL.

### 4.3 Minimum IAM policy shape

Use a dedicated runtime identity and replace only placeholders below. The bucket must remain private. Scope object actions to the application prefix and scope `ListBucket` by prefix; avoid a blanket bucket-wide policy.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ListOnlyApplicationPrefix",
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": "arn:aws:s3:::<private-bucket>",
      "Condition": {"StringLike": {"s3:prefix": ["ai-stylist/owners/*"]}}
    },
    {
      "Sid": "ObjectAccessOnlyApplicationPrefix",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::<private-bucket>/ai-stylist/owners/*"
    }
  ]
}
```

A presigned URL is a bearer capability derived from the permissions of the identity that creates it; select a short expiry and never log it. AWS documents that a URL is valid only until its configured expiry or the expiry/revocation of its underlying credentials, whichever occurs first.[1] The current adapter defaults to 300 seconds. Before exposing browser upload URLs, add checksum, object-size/content-type policy, scanner/quarantine and post-upload ownership verification.

### 4.4 Retention and deletion

Define separate lifecycle policies for source images, segmentation artifacts, generated meshes, audit-required manifests, and user deletion requests. Lifecycle configuration can transition or expire objects; expiration removes objects automatically.[2] Record requested deletion and actual outcome in application audit data, because a lifecycle action is asynchronous and cannot substitute for an immediate user-visible deletion status.

Suggested starting policy, subject to legal/privacy review:

| Prefix | Initial retention decision | Automation |
|---|---|---|
| `owners/*/garments/` | Retain only while wardrobe asset/revision is active or reviewable. | Delete after verified user/revision deletion and retention window. |
| `owners/*/segments/` | Derived artifact, usually shorter-lived. | Expire after source/revision deletion plus a bounded troubleshooting period. |
| `owners/*/meshes/` | Retain only approved/referenced mesh versions. | Version-aware delete after no active `TryOnRun` can reference it. |
| `owners/*/manifests/` | Audit-sensitive metadata. | Retain under the approved audit/retention policy, not an arbitrary storage default. |

### 4.5 Required code migration before a real remote S3 worker

1. Add owner/tenant and `storage_object_key` fields to the import/revision contract; relax local-path-only URI validators to support storage IDs without accepting arbitrary public URLs.
2. Change Phase B upload to use `AssetStorage.put_bytes`, persist object key, SHA-256, content type, size, owner, tenant and scan state in the same transactional workflow.
3. Make `read_manifest` and `write_manifest` use the storage repository or database, not an implicitly shared local directory.
4. Make segmentation and reconstruction download source by object key through an internal service identity, write derived artifacts through the same storage boundary, and persist quality evidence atomically.
5. Add integration tests against a disposable S3-compatible service such as MinIO: owner isolation, signed-read expiration, prefix delete, source retrieval by remote worker, and retry-safe processing.
6. Rehearse rollback with `AI_STYLIST_STORAGE_BACKEND=local` only while the data migration is reversible. Do not direct some workers to local disk and others to S3 for the same manifest namespace.

## 5. Remote GPU provider configuration

### 5.1 Current capability and limitation

The local preflight reports **NVIDIA GeForce RTX 3050 Laptop GPU, 4.0 GB VRAM**, below `GARMENT_RECONSTRUCTION_MIN_VRAM_GB=12`. The correct state is `pending_reconstruction`.

The Celery route for `stylist.process_garment_reconstruction` is `garment_gpu`; the outbox consumer route is `stylist_outbox`. A remote worker must consume only `garment_gpu` so heavy reconstruction cannot starve outbox delivery. Celery supports routing named tasks to a dedicated queue and starting a worker that consumes that queue.[5]

**Second limitation:** the current `reconstruct_rigged_garment` intentionally raises `NotImplementedError` after GPU preflight because no licensed provider adapter exists. Deploying a GPU cluster or manifest will not produce a real GLB until that adapter is implemented and validated. In addition, current worker source/manifest access is local-filesystem based, so Section 4.5 is a prerequisite for a truly remote worker.

### 5.2 Infrastructure prerequisites

For a Docker-based remote host, install a supported NVIDIA driver, NVIDIA Container Toolkit, configure the Docker runtime with `nvidia-ctk runtime configure --runtime=docker`, restart Docker, and verify a sample GPU workload before deploying the application worker.[3] For Kubernetes, the NVIDIA GPU Operator deployment includes the driver/toolkit/device plugin and telemetry components; verify that `nvidia.com/gpu` is allocatable before scheduling the worker.[4]

The structural template is `backend/deployments/garment-gpu-worker.deployment.yaml.example`. It requests one GPU and starts:

```bash
celery -A app.queue.celery_app worker \
  -Q garment_gpu \
  -n garment-gpu@%h \
  --concurrency=1 \
  --loglevel=INFO
```

Do not apply the template unchanged. Replace image registry/tag, node selector, workload identity, secret reference, CPU/memory values, and minimum VRAM threshold based on measured provider requirements. Keep concurrency at one initially to prevent multiple reconstruction jobs from exhausting a GPU.

### 5.3 Remote worker preflight checklist

| Gate | Evidence required before enqueueing production jobs |
|---|---|
| GPU visibility | `nvidia-smi` on host and a CUDA sample/container pass; Kubernetes node exposes `nvidia.com/gpu`. |
| Capacity | Measured available VRAM exceeds provider/model/resolution/batch requirement with safety headroom; do not use the local 4 GB laptop as proof. |
| Image integrity | Immutable image digest, pinned provider/model version, SBOM/vulnerability review, and no provider token baked into image. |
| Queue isolation | Worker consumes `garment_gpu` only; outbox consumer continues on `stylist_outbox`. |
| Source access | Worker can retrieve manifest/source via migrated private object-storage contract, not a developer workstation path. |
| Output validation | Provider output records GLB URI, skeleton, rest pose, anchors, skin weights, scale, bounds, intersections, and human review status. |
| Failure semantics | Timeout/OOM/provider error returns `pending_reconstruction` or `failed` with bounded reason; no false rigged status. |
| Observability | GPU, queue depth, latency, OOM/retry/dead-letter, quality-gate rejection and provider-version metrics/dashboard are present. |

### 5.4 Provider adapter acceptance contract

Implement the adapter behind `reconstruct_rigged_garment(manifest)` only after its provider is licensed, selected and tested. The adapter must consume an immutable import version, return a generated asset URI plus provider version, and never alter user-owned source metadata. The task then evaluates `quality_gate_passes`; only its success path can set `rig_status=rigged_template`. Include an evaluation corpus covering categories, poses, transparent/complex garments, multiple image quality levels, known unsupported cases, and failure injection. Retain reviewer evidence for every approved mesh.

## 6. References

[1] [AWS S3 — Download and upload objects with presigned URLs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html)

[2] [AWS S3 — Managing the lifecycle of objects](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html)

[3] [NVIDIA — Installing the NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

[4] [NVIDIA — Installing the GPU Operator](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/getting-started.html)

[5] [Celery — Routing Tasks](https://docs.celeryq.dev/en/latest/userguide/routing.html)
