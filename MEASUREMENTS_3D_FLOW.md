# Measurement-first 3D Stylist flow

## User flow

The primary experience no longer requires an image. The user enters height, weight, shoulder width, bust, waist, hip, and inseam measurements. The frontend recalculates the mannequin proportions on every change, displays a shape hint, collects style goals, and sends the structured profile to the backend.

The current mannequin is a Three.js/React Three Fiber renderer that loads `web/public/models/Xbot.glb` with `useGLTF`. Orbit controls, studio lighting, Suspense loading, bounded scale deformation, and a stable asset path are included. The GLB is a visual approximation rather than a scanned or anatomically accurate human model.

## Frontend contract

`BodyAvatar3D.tsx` accepts:

```ts
{
  height: number;
  weight: number;
  shoulder: number;
  bust: number;
  waist: number;
  hip: number;
  inseam: number;
  shoulder_slope?: "straight" | "sloped";
  chest_profile?: "full" | "flat";
  leg_alignment?: "straight" | "bowed";
}
```

The dimensions are normalized to bounded visual scale factors. Extreme values are clamped so malformed input cannot break the layout.

## Backend contract

`POST /stylist/measurement-recommend/`

```json
{
  "measurements": {
    "height": 170,
    "weight": 60,
    "shoulder": 42,
    "bust": 88,
    "waist": 72,
    "hip": 94,
    "inseam": 78
  },
  "selected_tags": ["Thanh lịch"]
}
```

The API validates realistic ranges with Pydantic. It returns an inline recommendation in `inline` mode or HTTP 202 plus `job_id` in `celery` mode. The frontend understands both responses.

## Run locally

For the simplest demo:

```powershell
# Terminal 1
Set-Location 'D:\Study\Studio Project\3d-ai-stylist\backend'
$env:AI_STYLIST_DEMO_MODE='1'
$env:AI_STYLIST_QUEUE_MODE='inline'
python -m uvicorn main:app --host 127.0.0.1 --port 8000

# Terminal 2
Set-Location 'D:\Study\Studio Project\3d-ai-stylist\web'
npm run dev
```

Open `http://127.0.0.1:3000`.

For the asynchronous path, start Redis and the Celery worker as described in `ASYNC_QUEUE.md`, then set `AI_STYLIST_QUEUE_MODE=celery` for both the worker and API.

## Product caveat

The avatar and recommendation are measurement-based visualization and styling assistance. They must not be presented as medical, health, body-worth, or objective identity judgments. Measurements should be user-controlled, deletable, access-controlled, and accompanied by an explanation that the visual shape is an approximation.
