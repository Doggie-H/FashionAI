# Phase A — Canonical Garment Catalog and Outfit Decision Engine

## Scope delivered

Phase A adds a versioned body contract, a canonical garment catalog, deterministic outfit ranking, and FastAPI endpoints. It provides the contracts required before real garment fitting, asset generation, or physics simulation are added.

The catalog assets referenced by `asset_uri` are **contract placeholders**. They define the required GLB path, skeleton compatibility, rest pose, anchors, and body-fit capability; Phase A does not claim those garment GLB files are already generated or physically fitted.

## Files

| Path | Purpose |
|---|---|
| `backend/app/phase_a_schemas.py` | Canonical Pydantic contracts |
| `backend/app/services/body_contract.py` | Measurement to parametric-body derivation |
| `backend/app/services/garment_catalog.py` | Validated canonical catalog repository |
| `backend/app/services/outfit_decision_engine.py` | Rules, scoring, evidence and abstention |
| `backend/app/routers/phase_a.py` | FastAPI endpoints |
| `backend/data/canonical_garments_v1.json` | Versioned canonical seed catalog |
| `backend/contracts/*.schema.json` | Exported JSON Schema Draft 2020-12 artifacts |

## API endpoints

| Method | Path | Contract | Purpose |
|---|---|---|---|
| `POST` | `/phase-a/body-contract` | `RawMeasurementsV1` → `ParametricBodyContractV1` | Validate measurements and derive body shape/bone scales |
| `GET` | `/phase-a/catalog` | `GarmentMetadataV1[]` | List active canonical garments; optional `category` filter |
| `GET` | `/phase-a/catalog/{garment_id}` | `GarmentMetadataV1` | Read a single canonical garment |
| `POST` | `/phase-a/outfit-decisions` | `OutfitDecisionRequestV1` → `OutfitDecisionResponseV1` | Rank valid outfit combinations with evidence |

## Contract principles

### Parametric body contract

`RawMeasurementsV1` contains raw, user-controlled measurements and declared visual considerations. `ParametricBodyContractV1` stores derived body shape scales, bone-length scales, visual flags, contract version, skeleton ID, and calibration version. The current calibration is explicitly labeled `heuristic-v1`; it is a visual prototype and not a medical, anthropometric, or tailoring guarantee.

### Garment metadata

Every garment has a stable `garment_id`, category, layer slot, styles, occasions, seasons, color family, material, silhouette, proportion effects, fit range, canonical 3D asset contract, lifecycle status, and source. IDs and templates are versioned so an outfit decision can be reproduced after the catalog changes.

### Outfit decision

The engine receives a body contract, a style context, optional permitted candidate IDs, and `top_k`. It rejects garments outside fit ranges, requires each requested layer slot, checks category compatibility, applies occasion/style/season/fit/skeleton rules, considers declared visual features, then returns ranked candidates. The response always separates score, evidence, constraints, trade-offs, confidence, and required user confirmations. When required slots cannot be satisfied, it returns a truthful abstention instead of fabricating an outfit.

## Minimal example

```json
{
  "body": {
    "contract_version": "1.0",
    "body_model_id": "xbot-prototype-v1",
    "skeleton_id": "mixamo-humanoid-v1",
    "calibration_version": "heuristic-v1",
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
    },
    "shape_parameters": {
      "height_scale": 0.9529,
      "shoulder_scale": 0.9286,
      "chest_scale": 0.9318,
      "waist_scale": 0.9306,
      "hip_scale": 1.0,
      "leg_scale": 0.9487
    },
    "bone_length_scales": {
      "spine": 0.9565,
      "upper_arm": 0.9529,
      "lower_arm": 0.9529,
      "upper_leg": 0.9487,
      "lower_leg": 0.9487
    },
    "visual_flags": ["sloped_shoulders", "flat_chest_profile", "bowed_leg_alignment"],
    "generated_at": "2026-08-26T00:00:00Z"
  },
  "context": {
    "occasion": "work",
    "preferred_styles": ["business", "classic"],
    "season": "autumn",
    "fit_preference": "tailored",
    "required_slots": ["base_top", "bottom"]
  },
  "top_k": 3
}
```

## Export schemas

Run this after any Pydantic contract change:

```powershell
Set-Location 'D:\Study\Studio Project\3d-ai-stylist\backend'
python scripts\export_phase_a_schemas.py
```

The resulting files are JSON Schema Draft 2020-12 compatible and can be used by a frontend form renderer, OpenAPI client, validation pipeline, or asset import service.

## Next integration boundary

Phase B should add physically present canonical GLB assets for each `template_id`, bind each mesh to `mixamo-humanoid-v1` or a licensed replacement skeleton, and implement a garment-fitting service that consumes `shape_parameters`, `bone_length_scales`, anchors, and rest pose. Do not map an arbitrary imported garment image directly to `asset_uri` without perception validation and an asset-quality review.
