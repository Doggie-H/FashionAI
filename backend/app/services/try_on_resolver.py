from __future__ import annotations

from typing import Literal

from ..workflow_models import StylingSession


RenderMode = Literal["canonical_proxy", "rigged_template", "approved_reconstructed_asset"]


def _approved_structural_profile(asset: dict[str, object]) -> dict[str, object] | None:
    profile = asset.get("structural_profile")
    return profile if isinstance(profile, dict) else None


def _proxy_binding(asset: dict[str, object], reason: str) -> dict[str, object]:
    structural_profile = _approved_structural_profile(asset)
    limitations = [reason, "Category proxy only; it is not a reconstructed or physically fitted garment."]
    if structural_profile:
        limitations.append("Reviewer-approved 2D structural cues are shown as proxy guidance only; they do not prove mesh geometry or physical fit.")
    return {
        "asset_id": str(asset.get("asset_id", "unknown")),
        "revision_id": asset.get("revision_id"),
        "category": str(asset.get("category", "accessory")),
        "render_mode": "canonical_proxy",
        "asset_uri": None,
        "quality_status": "proxy",
        "skeleton_id": None,
        "anchors": [],
        "structural_profile": structural_profile,
        "limitations": limitations,
    }


def _approved_binding(asset: dict[str, object], render_contract: dict[str, object], requested_mode: RenderMode) -> dict[str, object] | None:
    quality_gate = render_contract.get("quality_gate")
    if not isinstance(quality_gate, dict):
        return None
    required_checks = ("asset_exists", "glb_valid", "anchors_present", "skin_weights_valid", "scale_valid", "bounds_valid")
    if not all(quality_gate.get(check) is True for check in required_checks):
        return None
    if quality_gate.get("intersection_check") != "passed" or quality_gate.get("review_status") != "approved":
        return None
    expected_skeleton = render_contract.get("target_skeleton_id")
    actual_skeleton = quality_gate.get("skeleton_id")
    if not isinstance(expected_skeleton, str) or expected_skeleton != actual_skeleton:
        return None
    generated_asset_uri = render_contract.get("generated_asset_uri")
    if not isinstance(generated_asset_uri, str) or not generated_asset_uri:
        return None
    if requested_mode == "rigged_template" and render_contract.get("rig_status") != "rigged_template":
        return None
    return {
        "asset_id": str(asset.get("asset_id", "unknown")),
        "revision_id": asset.get("revision_id"),
        "category": str(asset.get("category", "accessory")),
        "render_mode": requested_mode,
        "asset_uri": generated_asset_uri,
        "quality_status": "approved",
        "skeleton_id": actual_skeleton,
        "anchors": list(render_contract.get("anchors", [])),
        "structural_profile": _approved_structural_profile(asset),
        "limitations": ["Approved mesh evidence is required for this render mode; visual output is still not a physical fit guarantee.", "2D structural cues supplement review context but do not replace mesh-quality evidence."],
    }


def resolve_try_on_assets(session: StylingSession, selected_garment_ids: list[str], requested_mode: RenderMode) -> dict[str, object]:
    """Resolve only persisted snapshot evidence; return proxy fallback when any requested rigged asset is not verified."""
    snapshot = list(session.wardrobe_snapshot or [])
    selected_assets: list[dict[str, object]] = []
    for garment_id in selected_garment_ids:
        asset = next(
            (
                item for item in snapshot
                if item.get("canonical_garment_id") == garment_id
                or (
                    isinstance(item.get("semantic_metadata"), dict)
                    and item["semantic_metadata"].get("garment_id") == garment_id
                )
            ),
            None,
        )
        if isinstance(asset, dict):
            selected_assets.append(asset)

    if not selected_assets:
        return {
            "requested_render_mode": requested_mode,
            "resolved_render_mode": "canonical_proxy",
            "quality_status": "unavailable",
            "asset_bindings": [],
            "limitations": ["No active wardrobe revision matching the selected candidate was available in the immutable session snapshot."],
        }

    if requested_mode == "canonical_proxy":
        bindings = [_proxy_binding(asset, "Canonical proxy was requested.") for asset in selected_assets]
        return {
            "requested_render_mode": requested_mode,
            "resolved_render_mode": "canonical_proxy",
            "quality_status": "proxy",
            "asset_bindings": bindings,
            "limitations": ["Category proxy only; it is not a reconstructed or physically fitted garment and does not establish cloth collision or texture transfer."],
        }

    resolved = []
    for asset in selected_assets:
        contract = asset.get("render_contract")
        approved = _approved_binding(asset, contract if isinstance(contract, dict) else {}, requested_mode)
        if approved is None:
            bindings = [_proxy_binding(candidate, "Requested rigged mode failed persisted asset, skeleton, or human-review quality evidence.") for candidate in selected_assets]
            return {
                "requested_render_mode": requested_mode,
                "resolved_render_mode": "canonical_proxy",
                "quality_status": "pending_review",
                "asset_bindings": bindings,
                "limitations": ["Rigged rendering was not enabled because one or more assets lack approved mesh-quality evidence. Canonical proxy fallback was used."],
            }
        resolved.append(approved)

    return {
        "requested_render_mode": requested_mode,
        "resolved_render_mode": requested_mode,
        "quality_status": "approved",
        "asset_bindings": resolved,
        "limitations": ["Approved mesh assets passed persisted structural gates. This is visual try-on evidence, not a guaranteed physical garment fit."],
    }
