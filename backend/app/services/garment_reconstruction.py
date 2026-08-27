import os
from dataclasses import dataclass

from ..phase_b_schemas import GarmentImportManifestV1, MeshQualityGateV1


@dataclass(frozen=True)
class GPUPreflight:
    eligible: bool
    reason: str | None
    gpu_name: str | None
    vram_gb: float | None


def gpu_preflight(min_vram_gb: float | None = None) -> GPUPreflight:
    required = min_vram_gb or float(os.getenv("GARMENT_RECONSTRUCTION_MIN_VRAM_GB", "12"))
    try:
        import torch
        if not torch.cuda.is_available():
            return GPUPreflight(False, "CUDA is unavailable; run segmentation fallback or use a remote GPU worker.", None, None)
        properties = torch.cuda.get_device_properties(0)
        vram_gb = round(properties.total_memory / (1024 ** 3), 2)
        if vram_gb < required:
            return GPUPreflight(False, f"GPU VRAM {vram_gb} GB is below the configured {required} GB reconstruction threshold.", properties.name, vram_gb)
        return GPUPreflight(True, None, properties.name, vram_gb)
    except ImportError:
        return GPUPreflight(False, "PyTorch is unavailable; run segmentation fallback or use a remote GPU worker.", None, None)


def quality_gate_passes(gate: MeshQualityGateV1 | None, manifest: GarmentImportManifestV1) -> bool:
    if gate is None:
        return False
    return all((
        gate.asset_exists,
        gate.glb_valid,
        gate.skeleton_id == manifest.target_skeleton_id,
        gate.rest_pose == manifest.rest_pose,
        gate.anchors_present,
        gate.skin_weights_valid,
        gate.scale_valid,
        gate.bounds_valid,
        gate.intersection_check == "passed",
        gate.review_status == "approved",
    ))


def reconstruct_rigged_garment(manifest: GarmentImportManifestV1) -> GarmentImportManifestV1:
    """Provider boundary for Garment3DGen or a comparable offline reconstruction backend.

    The local project must not claim a rigged result until a provider returns a validated GLB
    with target skeleton, skin weights, rest pose, anchors, scale, and geometry checks.
    """
    preflight = gpu_preflight()
    if not preflight.eligible:
        raise RuntimeError(preflight.reason or "GPU preflight failed")
    raise NotImplementedError(
        "A reconstruction provider is not configured. Set up a licensed offline Garment3DGen-compatible worker, "
        "then validate generated mesh, texture, skin weights, rest pose, anchors, scale, and intersections before marking rigged_template."
    )
