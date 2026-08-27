# Outbox Monitoring and Alert Runbook

**Scope:** Transactional Outbox relay for StylingSession and future workflow events. This document defines the Prometheus scrape contract, Grafana dashboard, alerts, operator actions, and safety boundaries.

## 1. Monitoring architecture

The FastAPI process exposes `/metrics`. On each scrape it refreshes gauges from the durable outbox table and exposes in-process counters/histograms from the API and relay. Prometheus scrapes this endpoint every 15 seconds, evaluates `observability/prometheus/outbox-alerts.yml`, and Grafana loads `observability/grafana/dashboards/outbox-overview.json`.

| Layer | Artifact | Responsibility |
|---|---|---|
| Application | `GET /metrics` | Expose in-process relay counters and current durable backlog/age gauges. |
| Relay | `OutboxRelay` | Claim due rows, publish, retry DB/broker failures, update metrics. |
| Prometheus | `observability/prometheus/prometheus.yml` | Pull metrics and evaluate rules. |
| Alert rules | `observability/prometheus/outbox-alerts.yml` | Detect backlog, delay, DB errors, retry storm, dead letter. |
| Grafana | `observability/grafana/dashboards/outbox-overview.json` | Visualize status, age, failure rate and throughput. |

The `/metrics` endpoint must not be internet-public. Set `METRICS_TOKEN` and configure Prometheus with the matching bearer token file, or restrict endpoint access at the service/network layer.

## 2. Metrics contract

| Metric | Type | Interpretation |
|---|---|---|
| `ai_stylist_outbox_backlog_events{status}` | Gauge | Current durable count for `pending`, `retry`, `processing`, or `dead_letter`. |
| `ai_stylist_outbox_oldest_event_age_seconds{status}` | Gauge | Age of oldest outstanding event in each status. |
| `ai_stylist_outbox_publish_attempts_total{outcome}` | Counter | Publish outcomes: `published`, `retry`, `dead_letter`. |
| `ai_stylist_outbox_retries_total{reason}` | Counter | Retry transitions, currently `publisher_error`. |
| `ai_stylist_outbox_dead_letters_total{reason}` | Counter | Events moved to dead letter. |
| `ai_stylist_outbox_relay_database_errors_total{operation}` | Counter | Claim/metrics/publish-state DB errors observed by relay or scrape. |
| `ai_stylist_outbox_relay_cycles_total{outcome}` | Counter | Relay cycles labeled `published`, `retry_scheduled`, `idle`, `database_error`. |
| `ai_stylist_outbox_publish_seconds` | Histogram | Time spent in each broker publish attempt. |

Counters reset when their process restarts. Use `rate()` or `increase()` for alerting; use gauges for current durable backlog state.

## 3. Start local observability stack

Create a local token file that is not committed, set the same value in the API environment as `METRICS_TOKEN`, then run:

```powershell
cd 'D:\Study\Studio Project\3d-ai-stylist'
Set-Content .metrics-token -Value 'replace-with-long-random-token' -NoNewline
$env:METRICS_TOKEN_FILE = (Resolve-Path .metrics-token)
$env:GRAFANA_ADMIN_PASSWORD = 'replace-with-long-unique-password'
docker compose -f docker-compose.observability.yml up -d
```

Open Prometheus at `http://localhost:9090` and Grafana at `http://localhost:3001`. The provided local configuration targets `host.docker.internal:8000`, which is appropriate for Docker Desktop. Replace that target with the API service DNS name in a container orchestration environment.

## 4. Alerts and operator response

### Dead letter

**Signal:** `OutboxDeadLetterEvents` is critical whenever durable `dead_letter` count is above zero.

First inspect event ID, aggregate ID, correlation ID, attempt count, error text, payload schema version, and downstream consumer logs. Determine whether the broker/outage is resolved and whether the payload remains safe/valid. Do not delete the row or invent a replacement event; preserve the original event ID for audit. After remediation, use an authorized replay command that transitions the same record to `retry`, resets a bounded error state, and records a new audit event. A replay endpoint is intentionally not exposed in P0; require admin authorization before adding it.

### Backlog

**Signal:** `OutboxBacklogGrowing` is warning when `pending + retry > 100` for 15 minutes.

Confirm API writes are committing, then check `ai_stylist_outbox_relay_cycles_total` and publisher logs. If the relay is idle while backlog grows, verify deployment health, database connectivity, lease state, worker ID uniqueness, and PostgreSQL query plan for the claim index. Scale publishers only after confirming `FOR UPDATE SKIP LOCKED` is executing against PostgreSQL, not a local SQLite fallback.

### Oldest event age

**Signal:** `OutboxOldestEventDelayed` is critical when an outstanding event exceeds five minutes for ten minutes.

Separate `pending`, `retry`, and `processing`. Pending suggests no claim capacity; retry suggests broker failure/backoff; processing suggests a stuck publisher or a future lease-reaper requirement. Do not simply lower the alert threshold or mass-mark records published.

### Database error

**Signal:** `OutboxRelayDatabaseErrors` is critical if database errors occur within five minutes.

Check PostgreSQL reachability, connection pool saturation, migration version, disk/replication health, and database error logs. The relay automatically backs off and retries its loop; restore DB service before restarting multiple publishers. After recovery, verify backlog age falls and no event transitions directly to published without a broker acknowledgement.

### Retry storm

**Signal:** `OutboxRetryStorm` warns when more than 25 retry transitions occur over ten minutes.

Check Redis/Celery broker reachability, authentication, TLS/network policy, worker queue `stylist_outbox`, broker memory, and payload serialization exceptions. The event should remain `retry` with bounded `last_error`; it becomes `dead_letter` only after `WORKFLOW_OUTBOX_MAX_PUBLISH_ATTEMPTS`.

## 5. Retry policy and limits

| Environment variable | Default | Purpose |
|---|---:|---|
| `WORKFLOW_OUTBOX_RETRY_BASE_SECONDS` | `2` | Base exponential-backoff delay. |
| `WORKFLOW_OUTBOX_RETRY_MAX_SECONDS` | `300` | Maximum retry delay. |
| `WORKFLOW_OUTBOX_MAX_PUBLISH_ATTEMPTS` | `12` | Publish attempts before dead letter. |
| `WORKFLOW_OUTBOX_BATCH_SIZE` | `50` | Claim batch size. |
| `WORKFLOW_OUTBOX_POLL_SECONDS` | `2` | Idle/retry relay sleep. |
| `WORKFLOW_OUTBOX_RELAY_DB_BACKOFF_MAX_SECONDS` | `30` | Maximum relay loop backoff after DB error. |

A Redis publish failure is retryable because PostgreSQL retains the event. A database failure in the relay loop is retryable because no in-memory work is considered authoritative. A publisher must never mark an event published before the broker accepts it.

## 6. Verification checklist

| Check | Expected result |
|---|---|
| `GET /metrics` with correct token | Exposes `ai_stylist_outbox_*` families. |
| Relay with broker temporarily unavailable | Event becomes `retry`, preserves error, remains durable. |
| Broker restored | Due event becomes `published`; no duplicate command/session. |
| Relay DB connection failure | Relay loop records DB error, backs off, then resumes. |
| Exceeded max attempts | Event becomes `dead_letter`; alert fires. |
| Grafana dashboard | Shows backlog by state, oldest age, retry rate, DB errors and outcome rate. |
| Alert action | Operator preserves event identity and writes auditable replay/review evidence. |


## 7. Alertmanager delivery and secret handling

Prometheus forwards matching alert groups to the `alertmanager:9093` service in `docker-compose.observability.yml`. Warning and critical alerts route to Slack; critical alerts also route to PagerDuty. The notification text comes from `observability/alertmanager/templates/ai-stylist-outbox.tmpl` and always includes the alert summary, severity, description, and runbook URL.

Alertmanager does not interpolate an environment variable into `slack_api_url_file` or PagerDuty `routing_key_file`. The compose stack therefore mounts local files at fixed read-only paths. Keep the source configuration credential-free and create the files outside version control.

```powershell
cd 'D:\Study\Studio Project\3d-ai-stylist'
Set-Content .metrics-token -Value '<long-metrics-token>' -NoNewline
Set-Content .slack-webhook-url -Value '<Slack Incoming Webhook URL>' -NoNewline
Set-Content .pagerduty-routing-key -Value '<PagerDuty Events API v2 routing key>' -NoNewline
$env:METRICS_TOKEN_FILE = (Resolve-Path .metrics-token)
$env:SLACK_WEBHOOK_URL_FILE = (Resolve-Path .slack-webhook-url)
$env:PAGERDUTY_ROUTING_KEY_FILE = (Resolve-Path .pagerduty-routing-key)
$env:GRAFANA_ADMIN_PASSWORD = '<unique-local-password>'
docker compose -f docker-compose.observability.yml up -d
```

Do not commit the three files, paste their values into YAML, or use a Manus connector as a substitute for an Alertmanager integration. Rotate a compromised Slack webhook or PagerDuty routing key in its provider first, replace the mounted local file, then restart only Alertmanager. Validate configuration before delivery with `docker run --rm -v "${PWD}\observability\alertmanager:/checks:ro" --entrypoint /bin/amtool prom/alertmanager:v0.28.1 check-config /checks/alertmanager.yml`. A syntactically valid configuration with placeholder values is **not** proof that notifications were delivered.

## 8. Controlled dead-letter operator procedure

When `OutboxDeadLetterEvents` fires, open `/admin` only with a JWT whose `roles` or `role` claim includes `admin`. Inspect the aggregate, correlation ID, attempt count, last error, schema version, and immutable payload. Establish that the target broker/consumer condition is healthy and that publishing the original event is still safe. Enter a specific review note and submit **Review**. The API stores `reviewed_at`, `reviewer_actor_id`, the note, and `OutboxDeadLetterReviewed` in the durable audit trail.

Only after review can the operator submit **Replay** with a fresh idempotency key and a recovery note. The API transitions only the same `dead_letter` row to `retry`; it preserves event ID, dedupe key, payload, attempt count, and published state. It appends `OutboxDeadLetterReplayRequested`, but the relay—not the dashboard—may subsequently mark the event published after broker acceptance. Stop and escalate when the event has an invalid schema, unsafe recipient, unexplained duplicate effect, or unresolved downstream incident.

## 9. Locust staging load test

Install reproducible development dependencies with `python -m pip install -r backend/requirements-dev.txt`. Never run a high-load test against production or against an unknown shared database. The scenario creates ordinary `StylingSession` commands and intentionally needs a pre-existing active body profile; it does not create or mutate body data per virtual user.

For a controlled local demo only, launch the API in `AI_STYLIST_DEMO_MODE=1`, then run the seed script and copy its values into the environment:

```powershell
cd 'D:\Study\Studio Project\3d-ai-stylist\backend'
C:\Python314\python.exe scripts\seed_locust_styling_session.py
$env:LOCUST_HOST = 'http://127.0.0.1:8000'
$env:LOCUST_LEGACY_ACTOR_ID = '<seeded user ID>'
$env:LOCUST_BODY_PROFILE_ID = '<seeded active profile ID>'
C:\Python314\python.exe -m locust -f load_tests\locustfile.py --headless -u 10 -r 2 -t 2m --host $env:LOCUST_HOST --html load_tests\artifacts\styling-session-local.html
```

For a quick local sanity check, `scripts\run_locust_smoke.ps1` starts an isolated SQLite demo API, seeds the profile, runs two users for five seconds by default, then stops the process and removes the database. It is intentionally a smoke test rather than a capacity result. For a staging-like JWT setup, omit `LOCUST_LEGACY_ACTOR_ID` and set `LOCUST_JWT` to a short-lived test principal that owns the supplied profile. Tune user count and ramp only after a small smoke run. A release candidate should meet the agreed environment-specific latency SLO, have no `401`/`403`/`409`/`5xx` responses beyond explicitly approved rates, create one session and one outbox event per successful unique command, avoid unexpected dead letters, and show backlog/oldest-age recovery in Prometheus after the test ends. Preserve the Locust HTML output and relevant Grafana time window with the incident or release evidence.


## 10. P1/P2 operational controls

### Feedback and reviewer work items

`StylingSessionFeedbackRecorded.v1` is emitted only after the feedback row, provenance links and audit entry commit. When feedback includes an issue type, inspect the resulting `user_feedback_triage` task in `/review`. The operator flow is to inspect the immutable evidence snapshot, atomically claim the task, record reason codes and a reviewer note, then submit `approve`, `reject`, or `rework`. Do not re-label a task by mutating user feedback or reuse a review-decision command with a different payload under the same idempotency key.

A `garment_metadata` review decision can change an asset revision lifecycle. Before approving it, verify source ownership, normalized metadata, import manifest, failure state, and intended canonical category. A reviewer decision is an evaluation and operations signal; it does not prove the real garment fits a human body.

### Try-on requested versus resolved mode

Observe `TryOnRequested.v1` with persisted `requested_render_mode`, `resolved_render_mode`, `quality_status`, session and correlation IDs. A `proxy_fallback` response is expected whenever selected snapshot assets lack one or more approved mesh checks. It is not an incident by itself. Investigate only when a request that should have an approved asset falls back unexpectedly, or when a run claims a rigged mode without an approved quality gate.

### Storage and provider readiness

Do not enable `AI_STYLIST_STORAGE_BACKEND=s3` until a private bucket, workload identity or secret manager, object lifecycle/retention policy, and owner-scoped access test are approved. Do not lower the reconstruction VRAM threshold simply to force a 4 GB local GPU through the pipeline. The expected state is `pending_reconstruction`; use a measured remote GPU worker and persist complete quality evidence before enabling a rigged render mode.
