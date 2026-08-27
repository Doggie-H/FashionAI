# Asynchronous inference queue

## Architecture

The recommendation endpoint supports two modes:

| Mode | `AI_STYLIST_QUEUE_MODE` | Behavior |
|---|---|---|
| Inline | `inline` | Runs inference in the FastAPI process. Use for Demo Mode and local smoke tests. |
| Celery | `celery` | Stores the upload, submits a Celery task, and returns a job ID. Use with Redis and a dedicated worker. |

In Celery mode, `POST /stylist/recommend/` returns HTTP 202 Accepted with `{"status":"queued","job_id":"..."}`. Poll `GET /stylist/recommend/{job_id}` until the status is `completed` or `failed`. The frontend already implements this polling path.

## Local Redis

If Docker is available:

```powershell
docker compose -f docker-compose.queue.yml up -d
```

Install queue dependencies and run a worker from the backend directory:

```powershell
python -m pip install -r requirements-queue.txt
$env:AI_STYLIST_QUEUE_MODE = 'celery'
$env:CELERY_BROKER_URL = 'redis://127.0.0.1:6379/0'
$env:CELERY_RESULT_BACKEND = 'redis://127.0.0.1:6379/1'
celery -A app.queue:celery_app worker --loglevel=INFO --pool=solo
```

Run the API in another terminal with the same environment:

```powershell
$env:AI_STYLIST_QUEUE_MODE = 'celery'
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

`--pool=solo` is the safer Windows development setting. On Linux production, use a process pool and one dedicated GPU worker per GPU unless the model server explicitly supports concurrent batching.

## Production requirements

Use a durable Redis deployment with authentication/TLS, or replace the broker/backend with an approved managed service. Do not expose Redis publicly. Configure worker concurrency based on VRAM; for a 7B VLM, multiple concurrent model copies can exhaust GPU memory.

Use separate queues for fast CPU/demo work and GPU inference when the workload grows. Add task time limits, retry policy, dead-letter handling, idempotency keys, result expiry, request ownership checks, and persistent job metadata in a database. Redis result state alone is not an audit trail.

The task removes temporary uploads by default. Set `AI_STYLIST_KEEP_UPLOADS=1` only for controlled debugging, never as a permanent production default. Persist only the object reference and required audit metadata.

## Operational states

Treat `/health` as process health and the queued job state as work health. Add a readiness check that reports whether the model worker is loaded, and monitor queue depth, task age, failure rate, retry count, p50/p95 latency, GPU memory, and output validation failures.


## Phase C garment reconstruction queue

Phase C routes only `stylist.process_garment_reconstruction` to the `garment_gpu` queue. Keep ordinary recommendation work on `stylist_default`; do not allow a generic CPU worker to consume a heavyweight mesh job.

```powershell
# Terminal 1: Redis
cd "D:\Study\Studio Project\3d-ai-stylist"
docker compose -f docker-compose.queue.yml up -d

# Terminal 2: dedicated GPU queue worker
.\run-queue.ps1 -Role gpu-worker

# Terminal 3: API process
.\run-queue.ps1 -Role api
```

Submit a valid garment through `POST /phase-b/garment-imports`, then queue reconstruction with `POST /phase-b/garment-imports/{import_id}/reconstruct`. The request returns a job ID immediately. Poll both `GET /phase-b/garment-reconstruction-jobs/{job_id}` for Celery state and `GET /phase-b/garment-imports/{import_id}` for the persistent manifest state.

| Manifest state | Meaning | Avatar behavior |
|---|---|---|
| `queued`, `segmenting`, `segmented` | Worker work is in progress. | Keep the Phase B canonical proxy. |
| `pending_reconstruction` | Segmentation completed, but preflight or provider cannot safely produce a validated mesh. | Keep the canonical proxy and display the failure reason. |
| `rigged_template` | A provider returned an approved output that passed all required mesh checks. | Eligible for a future real rigged-GLB viewer path. |
| `failed` | Segmentation or a provider failed unexpectedly. | Do not present as a final try-on result. |

The current local GPU preflight defaults to **12 GB VRAM** for research-grade reconstruction. A device below that threshold is intentionally recorded as `pending_reconstruction`; it does not attempt to load an unsupported mesh model. The worker stores segmentation artifact quality, input hash, job ID, configured provider version, error reason, and the mesh quality-gate evidence in the manifest.

> `alpha_fallback` means that `rembg` is not installed and the source alpha is preserved in a normalized PNG. It is not a clothing mask and must remain `unverified`.

A future provider may set `rigged_template` only after `asset_exists`, GLB validation, target skeleton, rest pose, anchors, skin weights, scale, bounds, intersection check, and human review are all successful. The implementation deliberately does not claim texture transfer, cloth simulation, accurate hidden geometry, or physical fit from one photograph.
