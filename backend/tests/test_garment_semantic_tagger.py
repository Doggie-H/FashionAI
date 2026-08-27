from datetime import datetime, timezone

from app.phase_b_schemas import (
    GarmentImageAnalysisV1,
    GarmentImportManifestV1,
    ReconstructionStateV1,
)
from app.services.garment_semantic_tagger import (
    _build_candidate_metadata,
    analyze_import_for_semantic_tags,
)


def _manifest() -> GarmentImportManifestV1:
    now = datetime.now(timezone.utc)
    return GarmentImportManifestV1(
        import_id="imp_abcdef123456",
        source_image_uri="/uploads/garments/imp_abcdef123456_beige-polo.jpg",
        source_image_sha256="a" * 64,
        analysis=GarmentImageAnalysisV1(
            category="top",
            confidence=0.9,
            color_hint="beige",
            silhouette_hint="regular",
            needs_human_review=True,
        ),
        selected_template_id="tpl_top_regular_v1",
        selected_garment_id="gar_beige_knit_polo",
        rig_status="canonical_proxy",
        conversion_backend="canonical_proxy",
        reconstruction=ReconstructionStateV1(updated_at=now),
        created_at=now,
    )


def test_disabled_semantic_provider_returns_no_fake_tags(monkeypatch):
    monkeypatch.setenv("GARMENT_TAGGER_PROVIDER", "disabled")
    result = analyze_import_for_semantic_tags(_manifest())
    assert result.status == "unavailable"
    assert result.candidate_metadata is None
    assert result.provider == "disabled"
    assert any("No garment semantic VLM provider" in item for item in result.limitations)


def test_qwen_payload_is_normalized_to_closed_taxonomy_and_review_gated():
    payload = {
        "category": "top",
        "styles": ["quiet_luxury", "preppy", "made_up_style"],
        "occasions": ["meeting", "work"],
        "seasons": ["autumn", "all_season"],
        "color_family": "neutral",
        "material": "knit cotton blend",
        "silhouette": "regular polo top",
        "formality_level": "business",
        "statement_level": "subtle",
        "weather_suitability": ["mild"],
        "mobility_support": "normal",
        "modesty_level": "standard",
        "intent_support": ["professional_presence", "confidence"],
        "pairing_hints": ["quiet_luxury", "preppy"],
        "avoid_pairing_with": [],
        "confidence": {"styles": 0.81, "occasions": 0.76, "category": 0.93},
        "rationales": {"styles": "Visible neutral knit, polo collar and restrained styling."},
        "limitations": ["Exact fiber composition is not visible."],
    }
    result = _build_candidate_metadata(_manifest(), payload, "licensed/qwen-vl", "commit-123")
    assert result.status == "needs_review"
    assert result.candidate_metadata is not None
    assert result.candidate_metadata.garment_id == "gar_user_abcdef123456"
    assert result.candidate_metadata.source == "user_import"
    assert result.candidate_metadata.status == "draft"
    assert result.candidate_metadata.styles == ["quiet_luxury", "preppy"]
    assert any("outside the closed taxonomy" in item for item in result.limitations)
    assert any(item.dimension == "styles" and item.confidence == 0.81 for item in result.evidence)
    assert any("reviewer" in item.lower() for item in result.limitations)


def test_mock_semantic_provider_is_explicitly_disclosed_and_review_gated(monkeypatch):
    monkeypatch.setenv("GARMENT_TAGGER_PROVIDER", "mock")
    result = analyze_import_for_semantic_tags(_manifest())
    assert result.provider == "mock"
    assert result.model_id == "ai-stylist/mock-garment-tagger"
    assert result.status == "needs_review"
    assert result.candidate_metadata is not None
    assert result.candidate_metadata.name == "Mock navy T-shirt fixture"
    assert "minimal" in result.candidate_metadata.styles
    assert result.structural_profile is not None
    assert result.structural_profile.neckline == "crew"
    assert result.structural_profile.shoulder_construction == "set_in"
    assert result.structural_profile.sleeve_length == "short"
    assert result.structural_profile.torso_length == "hip"
    assert any(item.feature == "neckline" and item.visible_views == ["front"] for item in result.structural_profile.evidence)
    assert any("not visual inference" in item for item in result.limitations)
