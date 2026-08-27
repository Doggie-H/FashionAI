# StylingSession API Documentation

**Version:** P0 Workflow Foundation with Transactional Outbox  
**Base URL:** `http://<api-host>:8000`  
**API group:** `/workflow`  
**Scope:** Body profile, wardrobe lifecycle, immutable `StylingSession`, decision, selection, truthful try-on, audit history, idempotency, correlation, and outbox event publication.

## 1. API operating model

A `StylingSession` is a durable styling case rather than a collection of unrelated endpoint responses. The session captures an immutable snapshot of the active body contract, selected active wardrobe revisions, and style context. The decision engine then creates a persisted decision run; only a candidate from that active run can be selected. Try-on records its render mode and limitations explicitly.

> `canonical_proxy` is a category/anchor preview, not a physically accurate reconstructed garment or a precise fit prediction. Requests for `rigged_template` or `approved_reconstructed_asset` are rejected until an approved resolver, skeleton retargeting, and quality evidence are available.

| Aggregate | Persistent responsibility | Primary API path |
|---|---|---|
| `BodyProfileRevision` | Versioned measurements and derived body contract; must be confirmed before a session can use it. | `/workflow/body-profiles` |
| `WardrobeAsset` and revision | Imported/canonical item lifecycle; must be active before session snapshot. | `/workflow/wardrobe-assets` |
| `StylingSession` | Immutable body/context/wardrobe case and state. | `/workflow/styling-sessions` |
| `OutfitDecisionRun` | Candidate list, evidence, abstention, catalog/rule versions. | `/styling-sessions/{id}/outfit-decisions` |
| `TryOnRun` | Requested render path, output state, and limitations. | `/styling-sessions/{id}/try-on` |
| `WorkflowAuditEvent` | Append-only actor/correlation trace of case transitions. | `/workflow/audit-events/{aggregate_id}` |

## 2. Authentication and standard headers

### 2.1. Production JWT mode

Set `WORKFLOW_AUTH_MODE=jwt` in production. All workflow commands must send a signed Bearer JWT and idempotency key. `sub` must be a positive internal user ID. An optional `tenant_id` claim is read for future tenant isolation. The server derives the actor from the JWT and rejects a JSON `actor_id` that differs from that actor.

| Header | Required | Example | Server behavior |
|---|---:|---|---|
| `Authorization` | Yes, production | `Bearer eyJ...` | Validates JWT; maps `sub` to actor. Missing/invalid token returns `401`. |
| `Idempotency-Key` | Yes, production commands | `style-create-20260826-001` | Scopes replay by authenticated actor + command type + key. |
| `X-Correlation-ID` | No | `corr_style_case_8b2c` | Uses supplied value across audit/outbox; server creates `corr_*` when absent. |
| `Content-Type` | Yes for JSON commands | `application/json` | Required for Pydantic command body. |
| `X-Metrics-Token` or `Authorization` | Only if `METRICS_TOKEN` is set | `Bearer <metrics-token>` | Restricts `/metrics`; do not use a user JWT as a shared scrape secret. |

`actor_id`, `idempotency_key`, and `correlation_id` remain accepted in the JSON payload only for explicitly enabled local-demo compatibility. Do not depend on this legacy path outside `AI_STYLIST_DEMO_MODE=1`.

### 2.2. Idempotency contract

Generate one idempotency key per user intent. Store the key in UI state while a request is in-flight. Reuse that exact key after a timeout or network retry. Generate a **new** key when the user changes semantic input and submits a new intent.

| Request outcome | Same key + same canonical payload | Same key + changed payload | New key |
|---|---|---|---|
| Existing committed command | Returns stored response; no duplicate session/event. | `409 IdempotencyConflict`. | Runs a new command. |
| Another request still owns in-flight Redis guard | `409`/retry-safe in-progress outcome; retry the same key later. | Do not retry with changed body. | Not applicable. |
| Redis temporarily unavailable | PostgreSQL unique constraint remains source of truth. | PostgreSQL fingerprint check applies. | Normal command transaction. |

## 3. Session state machine

```text
inputs_resolved
  → decision_running
  → recommendations_ready ──→ outfit_selected ──→ try_on_ready
  ↘ abstained
```

`decision_running` is an implementation transition around deterministic evaluation. The durable session becomes `recommendations_ready` if candidates exist or `abstained` if constraints cannot be satisfied. A candidate must belong to the active decision run. P0 try-on uses `canonical_proxy` and returns `proxy_fallback` with limitations.

## 4. Endpoint reference

### 4.1. Create body profile

`POST /workflow/body-profiles` creates a calibrated revision. It does not automatically make it active.

```http
POST /workflow/body-profiles
Authorization: Bearer <user-token>
Idempotency-Key: body-create-001
X-Correlation-ID: corr-style-case-001
Content-Type: application/json

{
  "measurements": {
    "height_cm": 162,
    "weight_kg": 56,
    "shoulder_cm": 39,
    "bust_cm": 82,
    "waist_cm": 67,
    "hip_cm": 94,
    "inseam_cm": 74,
    "shoulder_slope": "sloped",
    "chest_profile": "flat",
    "leg_alignment": "bowed"
  }
}
```

A `201` response contains `profile_id`, owner, revision, status `calibrated`, derived `contract`, and timestamps. The derived contract is prototype avatar calibration; it is not a medical or exact tailoring assessment.

### 4.2. Confirm body profile

`POST /workflow/body-profiles/{profile_id}/confirm` moves a calibrated profile to `active` when it belongs to the authenticated actor.

```json
{"confirmation_note": "Measurements reviewed by the user."}
```

A second confirmation of an already active profile returns `409`. A session using an unconfirmed body profile also returns `409`.

### 4.3. Create wardrobe asset revision

`POST /workflow/wardrobe-assets` creates a normalized asset revision. `canonical_garment_id` identifies a known catalog garment; `import_id` can link a Phase B garment import manifest.

```json
{
  "name": "Navy business shirt",
  "category": "top",
  "canonical_garment_id": "gar_business_shirt_navy"
}
```

The response begins in a lifecycle state such as `normalized` or `pending_review`. The asset cannot enter a StylingSession until approved and active.

### 4.4. Approve wardrobe asset

`POST /workflow/wardrobe-assets/{asset_id}/approve` activates the latest eligible revision.

```json
{"approval_note": "Metadata and import quality reviewed."}
```

The operation returns `409` if the revision is not normalized/pending review or if a linked reconstruction manifest is failed. An active revision is snapshotted at session creation; later asset changes do not mutate past session snapshots.

### 4.5. Create StylingSession

`POST /workflow/styling-sessions` captures active inputs and creates `StylingSessionOpened.v1` as a pending outbox event when `WORKFLOW_OUTBOX_ENABLED=1`.

```http
POST /workflow/styling-sessions
Authorization: Bearer <user-token>
Idempotency-Key: style-create-001
X-Correlation-ID: corr-style-case-001
Content-Type: application/json

{
  "body_profile_id": "body_abcdef123456",
  "context": {
    "occasion": "work",
    "preferred_styles": ["business", "classic"],
    "season": "autumn",
    "fit_preference": "tailored",
    "required_slots": ["base_top", "bottom"]
  },
  "wardrobe_asset_ids": ["wad_abc123def456", "wad_987654fedcba"]
}
```

If `wardrobe_asset_ids` is omitted, P0 snapshots all active assets belonging to the actor. If supplied, every requested asset must be active and owned by that actor; the API never silently removes invalid assets. The `201` response contains `session_id`, state `inputs_resolved`, the body contract snapshot, wardrobe revision snapshot, context, and timestamps.

The API transaction writes the session snapshot, `StylingSessionInputsResolved` audit event, processed command response, and outbox event together. The relay publishes only after commit.

### 4.6. Run outfit decision

`POST /workflow/styling-sessions/{session_id}/outfit-decisions` runs the deterministic ranker against the session snapshot.

```json
{"top_k": 3}
```

The response contains `decision_run_id`, status `ready`/`abstained`/`failed`, candidates, evidence, trade-offs, confidence, catalog version, and rule version. It returns `409` when session state is not eligible for another decision.

### 4.7. Select candidate

`POST /workflow/styling-sessions/{session_id}/select-outfit` selects a candidate from the **active** decision run only.

```json
{"outfit_id": "outfit_business_navy_001"}
```

The API returns `409` when the candidate is unknown, from another run, or session state is invalid.

### 4.8. Request try-on

`POST /workflow/styling-sessions/{session_id}/try-on` records a try-on request after candidate selection.

```json
{"render_mode": "canonical_proxy"}
```

P0 returns a `TryOnRun` with `proxy_fallback` and limitations. `rigged_template` and `approved_reconstructed_asset` are deliberately rejected until the asset resolver, retargeting, approved mesh evidence, and quality gates are connected.

### 4.9. Owner-scoped reads

| Method | Path | Result |
|---|---|---|
| `GET` | `/workflow/body-profiles/{profile_id}` | Returns only a profile owned by authenticated actor. |
| `GET` | `/workflow/wardrobe-assets/{asset_id}` | Returns only an asset owned by authenticated actor. |
| `GET` | `/workflow/styling-sessions/{session_id}` | Restores snapshot/state for authenticated actor. |
| `GET` | `/workflow/audit-events/{aggregate_id}` | Returns audit sequence for an owned aggregate in JWT mode. |

The `actor_id` query parameter on read endpoints is local-demo compatibility only. In JWT mode an inconsistent query actor produces `403`.

## 5. Error model

| HTTP status | Meaning | Client response |
|---:|---|---|
| `201` | New aggregate/run created. | Persist response; display state. |
| `200` | Command/query completed or idempotent response replayed. | Treat as success. |
| `400` | Missing/mismatched idempotency or correlation transport metadata. | Correct request; do not create a new key for a transport retry. |
| `401` | Missing/invalid JWT or auth configuration. | Reauthenticate. |
| `403` | Authenticated actor does not match body/query actor or resource ownership. | Do not retry as another actor. |
| `404` | Aggregate unavailable to actor. | Refresh local state; do not reveal another user's resource. |
| `409` | State invariant, invalid lifecycle transition, idempotency payload conflict, or in-flight duplicate. | Use same key only for unchanged retry; otherwise resolve UI state. |
| `503` | Auth service/broker/runtime dependency unavailable where explicitly surfaced. | Retry with same idempotency key after backoff. |

## 6. Transactional Outbox and observability

The outbox relay reads `pending` or due `retry` rows, claims them with PostgreSQL `FOR UPDATE SKIP LOCKED`, publishes to the `stylist_outbox` Celery queue, and marks `published` after broker acceptance. Broker errors transition an event to `retry` with exponential backoff. After `WORKFLOW_OUTBOX_MAX_PUBLISH_ATTEMPTS`, an event becomes `dead_letter` and requires authorized operator review/replay.

`GET /metrics` exports Prometheus metrics. The monitor tracks backlog by status, oldest outstanding age, publisher outcomes, retry counts, dead-letter count, relay database errors, and publish duration. See `docs/OUTBOX_MONITORING_AND_RUNBOOK.md` for thresholds, dashboards, alerts, and safe runbook actions.

## 7. Curl example: full minimal workflow

```bash
BASE_URL=http://localhost:8000
TOKEN='<jwt>'
CORRELATION_ID='corr-style-case-001'

curl -X POST "$BASE_URL/workflow/styling-sessions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Idempotency-Key: style-create-001" \
  -H "X-Correlation-ID: $CORRELATION_ID" \
  -H "Content-Type: application/json" \
  --data @create-session.json
```

If the network disconnects after server commit, repeat this exact request with identical JSON and `Idempotency-Key`. Do not invoke the outbox publisher manually from the client; it is a background responsibility driven by committed database state.


## 8. Admin dead-letter Review Queue and controlled replay

The admin queue is intentionally separate from the owner-scoped workflow API. It is enabled only after authentication has derived an actor with the `admin` role. In JWT mode, the role must be present in either the `roles` array or `role` claim. A local demonstration exception is available only with `AI_STYLIST_DEMO_MODE=1`, `WORKFLOW_ADMIN_ACTOR_IDS` explicitly allow-listed, and `X-Demo-Admin-Actor-ID`; it is not a production authentication mechanism.

| Method | Path | Required role | Purpose |
|---|---|---|---|
| `GET` | `/admin/outbox/dead-letters?limit=100&offset=0` | `admin` | Lists only durable `dead_letter` records, including payload, attempts, error and review metadata. |
| `POST` | `/admin/outbox/dead-letters/{event_id}/review` | `admin` | Captures the review note and reviewer in the audit trail. |
| `POST` | `/admin/outbox/dead-letters/{event_id}/replay` | `admin` | Changes a reviewed dead-letter event to `retry`, preserving the original event ID, dedupe key and payload. |

Both command endpoints require the ordinary `Authorization`, `Idempotency-Key`, `X-Correlation-ID`, and `Content-Type` headers. Their JSON body is `{ "review_note": "..." }`; the service requires a meaningful note. An event must still be `dead_letter` and already have durable review metadata before replay. A replay only re-schedules the same event for the relay. It does **not** mark it published and it does **not** authorize arbitrary payload modification.

```http
POST /admin/outbox/dead-letters/outbox_abc/review
Authorization: Bearer <admin-jwt-with-admin-role>
Idempotency-Key: dead-letter-review-001
X-Correlation-ID: corr-outbox-incident-001
Content-Type: application/json

{"review_note":"Validated payload, recipient, and broker recovery window."}
```

Use the same key and identical JSON only to recover a failed network request. The operation returns the stored command result instead of adding another audit entry. A changed body with the same key is rejected with `409`.

## 9. Load-test boundary

`backend/load_tests/locustfile.py` only creates StylingSessions against a **pre-seeded active** body profile. Every virtual-user command emits a distinct idempotency key and correlation ID so it exercises the normal durable command path rather than falsely measuring a replay cache. Do not target production. The exact staging/local prerequisites and acceptance criteria are in `docs/OUTBOX_MONITORING_AND_RUNBOOK.md`.


## 10. P1 session workspace, feedback and reviewer queue

`GET /workflow/me` resolves the active actor from the verified JWT and reports roles without persisting the token in the UI. In local demo mode only, read endpoints may use the documented `actor_id` compatibility parameter. Production clients must not place an actor ID in browser state as a substitute for authentication.

| Method | Path | Scope | Purpose |
|---|---|---|---|
| `GET` | `/workflow/body-profiles` | Owner | Cursor-paginated body revisions for profile selection/resume. |
| `GET` | `/workflow/wardrobe-assets?status=` | Owner | Cursor-paginated lifecycle board; only `active` assets may be snapshotted. |
| `GET` | `/workflow/styling-sessions?status=` | Owner | Resume server-side StylingSession state after reload. |
| `GET` | `/workflow/styling-sessions/{id}/outfit-decisions/{run_id}` | Owner | Restore immutable decision evidence for the named session. |
| `POST` | `/workflow/styling-sessions/{id}/feedback` | Owner | Persist feedback linked to an existing decision, candidate and optional try-on run. |
| `GET` | `/workflow/styling-sessions/{id}/feedback` | Owner | Read cursor-paginated feedback provenance. |
| `GET/POST` | `/review-tasks` | Reviewer or admin | List/create work items. |
| `POST` | `/review-tasks/{id}/claim` | Reviewer or admin | Atomic claim from `open`. |
| `POST` | `/review-tasks/{id}/submit-decision` | Assignee or admin | Submit `approve`, `reject`, or `rework` with reason codes/note. |
| `POST` | `/review-tasks/{id}/release` | Assignee or admin | Return a non-terminal task to `open`. |
| `GET` | `/review-tasks/{id}/audit-events` | Reviewer or admin | Reviewer timeline and correlation evidence. |

The expanded `StyleContextV1` remains additive: `weather`, `temperature_c`, `mobility_need`, `budget_max`, `modesty_preference`, `color_goals`, and `availability_policy` are captured in the immutable session snapshot. The deterministic decision record now retains an aggregate `score_breakdown` and typed `rejected_candidates`. Missing metadata is surfaced as a trade-off rather than silently treated as a favorable match.

A feedback payload needs at least one reason code and must reference a decision run owned by the same session. If a target outfit or try-on run is supplied, it must also belong to that run. Feedback with an issue type creates an open `user_feedback_triage` work item. A completed `decision_quality` or `user_feedback_triage` task, and not raw user sentiment alone, creates an evaluation label.

## 11. P2 resolved try-on contract

`POST /workflow/styling-sessions/{id}/try-on` accepts the requested `render_mode`, but the response states the **actual** resolved mode. `TryOnRunV1` includes `requested_render_mode`, `render_mode`, `quality_status`, `asset_bindings`, and limitations. A rigged request is enabled only when every selected asset has persisted approved GLB, skeleton, rest-pose, anchors, skin-weight, scale, bounds and intersection evidence. Otherwise the server returns `201` with `proxy_fallback`, actual `render_mode=canonical_proxy`, and a specific limitation.

> A `rigged_template` or `approved_reconstructed_asset` response is a reviewed visual asset contract. It is not a guarantee of physical cloth behavior, collision handling, material transfer, or real-world fit.

`TryOnRequested.v1` and `StylingSessionFeedbackRecorded.v1` are committed to the transactional outbox with their aggregate state and audit records. A worker may consume them only after commit and must remain idempotent by durable event ID.


## 12. Style knowledge, wardrobe-aware ranking, and candidate preview

`StyleContextV1` accepts the additive style tags `quiet_luxury`, `preppy`, `edgy`, `bohemian`, `athleisure`, `utility`, `modest`, `resort`, `creative`, and `vintage`, as well as `interview`, `meeting`, `presentation`, `celebration`, `weekend`, `gym`, `outdoor`, `home`, `cocktail`, and `wedding_guest` use cases. Historic snapshots remain valid because every field is additive.

| Context field | Meaning |
|---|---|
| `preferred_styles` | Visual directions selected by the user. |
| `intent_tags` | Typed needs including comfort, movement, weather protection, professional presence, photo readiness, coverage, care, packability, celebration, and confidence. |
| `formality_target` | `casual`, `smart_casual`, `business`, `formal`, or `ceremonial`. |
| `style_intensity` | `subtle`, `balanced`, or `statement`. |
| `optional_slots` | Permits outerwear, footwear, belt, and accessory variations without turning them into required slots. |
| `availability_policy` | `owned_only` strictly uses the session wardrobe snapshot. `owned_preferred` permits catalog discovery but rewards owned items. `allow_catalog` permits discovery and marks non-owned items for confirmation. |

The deterministic decision response now adds `style_archetypes`, `style_story`, and `functional_highlights` for every candidate while retaining score evidence, trade-offs, confirmation prompts, rejected candidates, and score breakdown. A high score does not establish physical fit.

### Preview a decision candidate without final selection

`POST /workflow/styling-sessions/{session_id}/try-on` accepts optional `preview_outfit_id`. It must belong to the active decision run.

```json
{
  "render_mode": "canonical_proxy",
  "preview_outfit_id": "out_<candidate-id>"
}
```

The call records a `TryOnRun` and sets the session to `user_reviewing`, but **does not change** `StylingSession.selected_outfit_id`. Use `/select-outfit` separately to persist an explicit choice. A selected candidate can then call `/try-on` without `preview_outfit_id` for a final try-on request.

The `/sessions` workspace offers front, side, rear, and free camera views for the same server-resolved binding. Camera state is local UI state only and cannot alter snapshot data, quality evidence, or the decision result.

> `canonical_proxy` is category geometry following the avatar transform; it is neither cloth simulation nor a fitted/reconstructed garment. `rigged_template` and `approved_reconstructed_asset` render only when server-side quality evidence permits them.
