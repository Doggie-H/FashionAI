# Phase B — Garment Image Import and Skeleton Binding

## Scope delivered

Phase B adds an operational import path from a 2D garment image into a persistent **garment import manifest**, then creates a skeleton-compatible try-on binding for the Three.js avatar. The system can now show an imported garment as a category-specific **canonical proxy** on the avatar.

> A canonical proxy is not a reconstructed garment mesh. It is an explicit, inspectable placeholder that validates catalog selection, rest pose, skeleton ID, attachment anchor, render binding, UI interaction, and API flow before offline image-to-3D reconstruction is introduced.

## API flow

| Step | Endpoint | Output |
|---|---|---|
| Import | `POST /phase-b/garment-imports` | Source-image storage, SHA-256, analysis, selected canonical template, import manifest |
| Inspect | `GET /phase-b/garment-imports/{import_id}` | Persistent import manifest |
| Bind | `POST /phase-b/try-on-bindings` | Category-aware binding for the avatar skeleton |

The import endpoint accepts JPG, JPEG, PNG, and WEBP files up to 10 MB. A supplied valid category is used as an explicit user declaration. Without one, the local Phase B baseline infers a category only from the filename and labels uncertain cases as `needs_review`.

## Manifest guarantees

Every manifest contains a stable import ID, source image URI, SHA-256, selected canonical garment/template IDs, target skeleton, rest pose, rig status, conversion backend, binding transform, and generated asset URI. This supports reproducibility and the future queue worker.

| Field | Current Phase B value | Meaning |
|---|---|---|
| `rig_status` | `canonical_proxy` | A non-physical preview geometry is being used |
| `conversion_backend` | `canonical_proxy` | No generic image-to-mesh model was run |
| `target_skeleton_id` | `mixamo-humanoid-v1` | Binding contract required by the current Xbot viewer |
| `generated_asset_uri` | Canonical template URI | Logical target asset; it may be a future asset contract placeholder |

## Frontend behavior

The user can import a garment photo in the measurement UI. The client creates an import, requests a try-on binding, replaces the previous proxy in the same category, and renders the category-specific proxy inside the same transformed Three.js group as Xbot. This ensures the proxy follows avatar rotation and positioning.

The viewer displays proxies for top, bottom, dress, outerwear, belt, footwear, and accessories. These geometries visually communicate attachment location only. They do not support cloth simulation, collision avoidance, fitted sleeves, texture transfer, hidden back panels, or accurate garment dimensions.

## Future real image-to-3D worker

A real reconstruction provider must run asynchronously and replace `canonical_proxy` only after successful validation. The required worker interface is:

```text
source image plus import manifest
  -> perception and segmentation
  -> category template or garment reconstruction provider
  -> mesh cleanup and UV texture generation
  -> rigging and skin weights for target skeleton
  -> rest pose and anchor validation
  -> collision and scale validation
  -> approval state
  -> rigged template asset URI
```

The generated asset must use `rig_status=rigged_template` only if it is tied to the target skeleton and passes geometry checks. Uncertain outputs remain `pending_reconstruction` or `failed`, and must not be represented as finished try-on assets.

## Data Flow artifact

See `docs/data-flow-phase-a.mmd` and the rendered `data-flow-phase-a.png` attachment. It shows the measurement-to-body-contract path, optional garment import path, canonical catalog, constraint engine, evidence, abstention, and final recommendation/preview.

## Verification

Phase B adds import/binding tests for the happy path, invalid upload, missing manifest, and missing binding. The project test suite and frontend build must run after contract or rendering changes.
