# P2 Provider and Storage Activation

## Purpose

P2 code now contains a storage abstraction, asset resolver, mesh-evidence gate, and viewer contract. It deliberately remains safe when no object-storage or reconstruction provider is configured: imports may use local storage, reconstruction stays `pending_reconstruction`, and try-on returns `canonical_proxy` fallback rather than representing an unverified mesh as fitted clothing.

## Object storage

Set `AI_STYLIST_STORAGE_BACKEND=s3` only after configuring an S3-compatible bucket, identity policy, endpoint, and lifecycle retention policy. The production requirements include `boto3`; credentials must be supplied through the deployment secret manager or workload identity, never source code.

| Variable | Required | Purpose |
|---|---:|---|
| `AI_STYLIST_STORAGE_BACKEND=s3` | Yes | Enables the S3-compatible adapter. |
| `AI_STYLIST_S3_BUCKET` | Yes | Private bucket containing owner-scoped objects. |
| `AI_STYLIST_S3_REGION` | Recommended | Cloud region for the provider client. |
| `AI_STYLIST_S3_ENDPOINT_URL` | Only for S3-compatible providers | Custom endpoint, for example MinIO. |
| `AI_STYLIST_S3_KEY_PREFIX` | No | Object prefix; default is `ai-stylist`. |

The adapter writes objects beneath `owners/{owner_id}/...`, verifies that prefix before signing a read URL, and supports deletion by owner/namespace. Application authorization must verify the actor owns the aggregate before calling `signed_read_url`; prefix checks are an additional boundary, not an authorization substitute. Object lifecycle expiration, legal holds, backup/versioning and deletion audit policy are deployment responsibilities that must be accepted before real user uploads are moved.

## Reconstruction provider

The local 4 GB RTX 3050 stays below the default `GARMENT_RECONSTRUCTION_MIN_VRAM_GB=12` threshold. This is expected to result in `pending_reconstruction`, not `failed` and not `rigged_template`. A licensed provider/remote worker must return a GLB and the following persisted mesh evidence before P2 may use a rigged render mode:

| Required evidence | Expected value |
|---|---|
| GLB asset | Existing, parsable URI controlled by the storage layer. |
| Skeleton and rest pose | Equal to the target manifest contract. |
| Anchors and skin weights | Present and valid. |
| Scale, bounds, intersections | Passed. |
| Human mesh-quality review | `approved`. |

The resolver rejects any missing or non-approved evidence and returns an explicit proxy fallback. Rendering an approved GLB in the viewer remains a visual preview only; it does not establish garment collision, cloth physics, material transfer, or physical fit accuracy.

## VLM/perception provider

Do not replace the current typed/heuristic import analysis merely by setting an environment label. A real VLM provider integration needs a licensed model/runtime, versioned prompt/schema, input retention policy, bounded queue worker, evaluation dataset, calibration targets, reviewer sampling and rollback plan. It must run asynchronously and write `unknown`/confidence/evidence fields; it must not load a heavy model inside FastAPI or self-certify its own output. Until those conditions are met, the current system should retain its explicit `needs_human_review` status.
