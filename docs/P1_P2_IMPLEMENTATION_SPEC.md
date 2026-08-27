# P1–P2 Implementation Specification

**Status:** implementation baseline for the remaining roadmap phases.  
**Scope:** P1 controlled intelligence and P2 truthful try-on production path.  
**Non-goal:** claiming physically accurate garment fitting or a live external storage/VLM provider without provider credentials, approved assets, and measured quality evidence.

## 1. Baseline already delivered

The project already has immutable body/wardrobe/session snapshots, idempotent commands, audit records, an outbox relay, dead-letter review/replay, metrics, alert templates, garment import manifests, and a truthful category-proxy avatar. The remaining work is therefore not another prototype endpoint. It must extend the aggregate model while preserving actor-derived authorization, idempotency, correlation propagation, and durable audit evidence.

## 2. P1 controlled intelligence

| Capability | Aggregate / contract | Required invariant |
|---|---|---|
| Expanded context | `StyleContextV1` additive optional constraints: weather, mobility, budget, modesty, color goals, availability. | Contradictions are rejected before a decision run is persisted. |
| Explainable decision record | `OutfitDecisionRun.decision_payload` gains score breakdown, rejected candidates, and abstention evidence. | The immutable run retains catalog/rule/context versions and never mutates prior results. |
| Structured feedback | `StylingSessionFeedback` linked to session, decision run, candidate, and optional try-on run. | Only the session owner can submit; target IDs must belong to the same session. |
| Reviewer workflow | `ReviewTask` with evidence snapshot, checklist version, assignment, decision and audit events. | Claim is atomic; only assignee/admin can release or decide; a completed task is immutable. |
| Evaluation evidence | `EvaluationLabel` created only from reviewed decision-quality or feedback-triage tasks. | User feedback is not automatically treated as ground truth. |
| Session-first APIs | `/workflow/me`, list/read body profiles/assets/sessions, feedback history and run details. | Results are actor-scoped, cursor paginated and resume server state after reload. |

### Reviewer state machine

```text
open → claimed → in_review → approved
                     ├── rejected
                     └── rework_required
open / claimed → cancelled | expired
```

A review decision creates an audit event. `garment_metadata` approval can activate an eligible wardrobe revision, while rejection/rework keeps it non-active. `decision_quality` and `user_feedback_triage` decisions create evaluation labels; they never rewrite recommendation history.

## 3. P2 truthful try-on path

| Capability | Structure | Runtime rule |
|---|---|---|
| Storage boundary | `AssetStorage` interface with local filesystem adapter and a signed-access provider boundary. | Object-store implementation is enabled only when credentials/configuration exist; local demo is explicitly labeled. |
| Resolver | `TryOnAssetResolver` resolves selected garment revisions, manifest evidence, skeleton, rest pose, anchors and asset URI. | Only approved `rigged_template`/`approved_reconstructed_asset` candidates pass; otherwise proxy fallback is returned. |
| Runtime verification | `TryOnResolution` persists per-asset binding decision, quality evidence, fallback reason, render payload and metrics-friendly timing. | `rigged` status requires a GLB URI plus approved mesh evidence; it is not inferred from image import success. |
| Render contract | `TryOnRunV1` returns `asset_bindings`, `quality_status`, `render_payload`, and declared limitations. | The frontend can show an asset only according to the mode returned by the server. |
| Queue orchestration | try-on/asset-resolution command creates durable state then emits an outbox event. | Heavy reconstruction stays on `garment_gpu`; HTTP never loads a 3D/VLM model. |

## 4. Implementation sequence

1. Extend contracts and add Alembic migration for review, feedback, evaluation and try-on-resolution persistence.
2. Implement workflow services and routers with role checks, ownership, audit and idempotency.
3. Add deterministic constraint validation and decision evidence capture.
4. Add storage/resolver interfaces plus local demo adapter and truthful proxy fallback.
5. Replace the root demo-only route with a Session Workspace while retaining the measurement/BodyAvatar3D view as a clearly labeled onboarding/proxy component.
6. Add reviewer queue UI and P2 try-on evidence panel.
7. Test unit state transitions, endpoint ownership, concurrent claims, idempotency, migration head, resolver gates, frontend build and local smoke workflow.

## 5. Required external inputs before live provider claims

| Input | Why it is required |
|---|---|
| Object storage endpoint, bucket policy and credentials | Required to replace local filesystem uploads with signed, tenant-scoped object access. |
| Approved rigged GLB assets and mesh-quality evidence | Required before enabling a non-proxy render mode. |
| VLM/reconstruction provider license, endpoint or deployment | Required before enabling a real model instead of the current honest pending-reconstruction boundary. |
| JWT/OIDC issuer or rotated signing-key policy | Required to replace the current HMAC adapter with production identity verification. |
| Reviewer rubric and named roles | Required for stable, auditable human decisions and valid evaluation labels. |

Until those inputs exist, the implementation will expose typed provider boundaries, local/demo adapters, queued or proxy fallback statuses, and explicit limitations rather than fabricate production capability.
