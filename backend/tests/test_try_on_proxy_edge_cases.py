from __future__ import annotations

from types import SimpleNamespace

from app.services.try_on_resolver import resolve_try_on_assets


def _snapshot_asset(asset_id: str, garment_id: str, category: str, contract: dict | None = None) -> dict:
    return {
        "asset_id": asset_id,
        "revision_id": f"rev-{asset_id}",
        "canonical_garment_id": garment_id,
        "category": category,
        "render_contract": contract or {},
    }


def _approved_contract(rig_status: str = "rigged_template") -> dict:
    return {
        "rig_status": rig_status,
        "target_skeleton_id": "mixamo-humanoid-v1",
        "generated_asset_uri": "/uploads/mesh/approved.glb",
        "anchors": ["shoulder", "chest"],
        "quality_gate": {
            "asset_exists": True,
            "glb_valid": True,
            "anchors_present": True,
            "skin_weights_valid": True,
            "scale_valid": True,
            "bounds_valid": True,
            "intersection_check": "passed",
            "review_status": "approved",
            "skeleton_id": "mixamo-humanoid-v1",
        },
    }


def test_explicit_canonical_proxy_never_exposes_mesh_uri_even_if_mesh_is_approved():
    session = SimpleNamespace(wardrobe_snapshot=[_snapshot_asset("asset-top", "gar_top", "top", _approved_contract())])
    result = resolve_try_on_assets(session, ["gar_top"], "canonical_proxy")
    assert result["requested_render_mode"] == "canonical_proxy"
    assert result["resolved_render_mode"] == "canonical_proxy"
    assert result["quality_status"] == "proxy"
    assert result["asset_bindings"][0]["asset_uri"] is None
    assert result["asset_bindings"][0]["render_mode"] == "canonical_proxy"


def test_missing_snapshot_asset_returns_unavailable_without_proxy_geometry():
    session = SimpleNamespace(wardrobe_snapshot=[_snapshot_asset("asset-top", "gar_top", "top")])
    result = resolve_try_on_assets(session, ["gar_not_in_snapshot"], "canonical_proxy")
    assert result["resolved_render_mode"] == "canonical_proxy"
    assert result["quality_status"] == "unavailable"
    assert result["asset_bindings"] == []
    assert "immutable session snapshot" in result["limitations"][0]


def test_one_unapproved_asset_forces_whole_rigged_candidate_to_proxy_fallback():
    session = SimpleNamespace(wardrobe_snapshot=[
        _snapshot_asset("asset-top", "gar_top", "top", _approved_contract()),
        _snapshot_asset("asset-bottom", "gar_bottom", "bottom", {"rig_status": "pending_reconstruction"}),
    ])
    result = resolve_try_on_assets(session, ["gar_top", "gar_bottom"], "rigged_template")
    assert result["requested_render_mode"] == "rigged_template"
    assert result["resolved_render_mode"] == "canonical_proxy"
    assert result["quality_status"] == "pending_review"
    assert len(result["asset_bindings"]) == 2
    assert all(binding["render_mode"] == "canonical_proxy" for binding in result["asset_bindings"])
    assert all(binding["asset_uri"] is None for binding in result["asset_bindings"])


def test_complete_approved_evidence_allows_rigged_template_binding_but_keeps_fit_limitation():
    session = SimpleNamespace(wardrobe_snapshot=[_snapshot_asset("asset-top", "gar_top", "top", _approved_contract())])
    result = resolve_try_on_assets(session, ["gar_top"], "rigged_template")
    assert result["resolved_render_mode"] == "rigged_template"
    assert result["quality_status"] == "approved"
    assert result["asset_bindings"][0]["asset_uri"] == "/uploads/mesh/approved.glb"
    assert "not a guaranteed physical garment fit" in result["limitations"][0]
