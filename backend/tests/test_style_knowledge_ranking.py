from __future__ import annotations

from app.phase_a_schemas import OutfitDecisionRequestV1, RawMeasurementsV1, StyleContextV1
from app.services.body_contract import build_parametric_body_contract
from app.services.outfit_decision_engine import decide_outfits


BODY = build_parametric_body_contract(RawMeasurementsV1(
    height_cm=170,
    weight_kg=60,
    shoulder_cm=42,
    bust_cm=88,
    waist_cm=72,
    hip_cm=94,
    inseam_cm=78,
))


def test_owned_only_style_ranking_uses_selected_wardrobe_and_explains_intent():
    owned = [
        "gar_beige_knit_polo",
        "gar_cream_pleated_midi_skirt",
        "gar_camel_trench_coat",
        "gar_white_minimal_sneaker",
    ]
    response = decide_outfits(OutfitDecisionRequestV1(
        body=BODY,
        context=StyleContextV1(
            occasion="meeting",
            preferred_styles=["quiet_luxury", "preppy"],
            intent_tags=["professional_presence", "weather_protection", "confidence"],
            formality_target="business",
            style_intensity="subtle",
            required_slots=["base_top", "bottom"],
            optional_slots=["outerwear", "footwear"],
            availability_policy="owned_only",
        ),
        candidate_garment_ids=owned,
        owned_garment_ids=owned,
        top_k=3,
    ))
    assert not response.abstained
    assert response.candidates
    assert all(set(candidate.garment_ids).issubset(set(owned)) for candidate in response.candidates)
    assert any("quiet_luxury" in candidate.style_archetypes for candidate in response.candidates)
    best = response.candidates[0]
    assert best.style_story
    assert any(item.rule_id == "functional_intent_support" for item in best.evidence)
    assert any(item.rule_id == "outfit_intent_coverage" for item in best.evidence)
    assert any("weather protection" in highlight for highlight in best.functional_highlights)
    assert all(sum(item.score_delta for item in candidate.evidence) == candidate.total_score for candidate in response.candidates)


def test_catalog_discovery_is_explicit_and_owned_preferred_rewards_user_wardrobe():
    owned = ["gar_technical_athleisure_zip_top", "gar_technical_jogger_black"]
    response = decide_outfits(OutfitDecisionRequestV1(
        body=BODY,
        context=StyleContextV1(
            occasion="gym",
            preferred_styles=["athleisure", "sporty"],
            intent_tags=["movement", "comfort"],
            formality_target="casual",
            required_slots=["base_top", "bottom"],
            availability_policy="owned_preferred",
        ),
        candidate_garment_ids=None,
        owned_garment_ids=owned,
        top_k=3,
    ))
    assert not response.abstained
    assert set(owned).issubset(set(response.candidates[0].garment_ids))
    assert any(item.rule_id == "owned_wardrobe_preference" for item in response.candidates[0].evidence)
    assert all(sum(item.score_delta for item in candidate.evidence) == candidate.total_score for candidate in response.candidates)


def test_style_diversification_removes_near_duplicate_outfits_when_alternatives_exist():
    garment_ids = [
        "gar_beige_knit_polo", "gar_fluid_bohemian_blouse", "gar_cream_pleated_midi_skirt",
        "gar_earth_wideleg_trouser", "gar_white_minimal_sneaker", "gar_straw_resort_bag",
    ]
    response = decide_outfits(OutfitDecisionRequestV1(
        body=BODY,
        context=StyleContextV1(
            occasion="weekend",
            preferred_styles=["bohemian", "quiet_luxury", "resort"],
            intent_tags=["comfort", "photo_ready"],
            required_slots=["base_top", "bottom"],
            optional_slots=["footwear", "accessory"],
            availability_policy="owned_only",
        ),
        candidate_garment_ids=garment_ids,
        owned_garment_ids=garment_ids,
        top_k=3,
    ))
    assert not response.abstained
    assert len(response.candidates) >= 2
    primary_styles = [candidate.style_archetypes[0] for candidate in response.candidates if candidate.style_archetypes]
    assert len(set(primary_styles)) >= 2
    assert all(sum(item.score_delta for item in candidate.evidence) == candidate.total_score for candidate in response.candidates)


def test_reviewed_user_import_metadata_is_ranked_as_owned_without_catalog_substitution():
    from app.services.garment_catalog import get_garment

    canonical_top = get_garment("gar_beige_knit_polo")
    assert canonical_top is not None
    user_top = canonical_top.model_copy(update={
        "garment_id": "gar_user_abcdef123456",
        "name": "User imported beige knit polo",
        "source": "user_import",
        "status": "draft",
        "styles": ["quiet_luxury", "preppy"],
        "occasions": ["meeting", "work"],
        "formality_level": "business",
    })
    skirt_id = "gar_cream_pleated_midi_skirt"
    owned = [user_top.garment_id, skirt_id]
    response = decide_outfits(OutfitDecisionRequestV1(
        body=BODY,
        context=StyleContextV1(
            occasion="meeting",
            preferred_styles=["quiet_luxury", "preppy"],
            formality_target="business",
            required_slots=["base_top", "bottom"],
            availability_policy="owned_only",
        ),
        candidate_garment_ids=owned,
        candidate_garments=[user_top],
        owned_garment_ids=owned,
        top_k=1,
    ))
    assert response.abstained is False
    assert response.candidates
    candidate = response.candidates[0]
    assert user_top.garment_id in candidate.garment_ids
    assert "gar_beige_knit_polo" not in candidate.garment_ids
    assert any(item.rule_id == "owned_wardrobe_available" for item in candidate.evidence)
    assert sum(item.score_delta for item in candidate.evidence) == candidate.total_score
