from __future__ import annotations

from collections import Counter
from itertools import product
from uuid import uuid4

from ..phase_a_schemas import (
    DecisionEvidenceV1,
    GarmentMetadataV1,
    OutfitCandidateV1,
    OutfitDecisionRequestV1,
    OutfitDecisionResponseV1,
    RejectedCandidateV1,
)
from .garment_catalog import load_catalog


SLOT_TO_CATEGORY = {
    "base_top": "top", "bottom": "bottom", "dress": "dress", "outerwear": "outerwear",
    "footwear": "footwear", "belt": "belt", "accessory": "accessory",
}
FORMALITY_ORDER = {"casual": 0, "smart_casual": 1, "business": 2, "formal": 3, "ceremonial": 4}
INTENSITY_ORDER = {"subtle": 0, "balanced": 1, "statement": 2}
STYLE_LABELS = {
    "minimal": "tối giản", "classic": "cổ điển", "smart_casual": "smart casual", "streetwear": "đường phố",
    "romantic": "lãng mạn", "business": "chuyên nghiệp", "sporty": "thể thao", "quiet_luxury": "quiet luxury",
    "preppy": "preppy", "edgy": "cá tính", "bohemian": "bohemian", "athleisure": "athleisure",
    "utility": "utility", "modest": "kín đáo", "resort": "resort", "creative": "sáng tạo", "vintage": "vintage",
}


def _in_range(value: float, minimum: float | None, maximum: float | None) -> bool:
    return (minimum is None or value >= minimum) and (maximum is None or value <= maximum)


def _fits_body(garment: GarmentMetadataV1, request: OutfitDecisionRequestV1) -> bool:
    profile = garment.fit_profile
    body = request.body.measurements
    return (
        _in_range(body.bust_cm, profile.min_bust_cm, profile.max_bust_cm)
        and _in_range(body.waist_cm, profile.min_waist_cm, profile.max_waist_cm)
        and _in_range(body.hip_cm, profile.min_hip_cm, profile.max_hip_cm)
    )


def _score_garment(garment: GarmentMetadataV1, request: OutfitDecisionRequestV1) -> tuple[float, list[DecisionEvidenceV1], list[str], list[str]]:
    context = request.context
    body = request.body
    score = 0.0
    evidence: list[DecisionEvidenceV1] = []
    constraints: list[str] = []
    tradeoffs: list[str] = []

    if context.occasion in garment.occasions:
        score += 28
        constraints.append(f"occasion:{context.occasion}")
        evidence.append(DecisionEvidenceV1(rule_id="occasion_match", message=f"{garment.name} phù hợp bối cảnh {context.occasion}.", score_delta=28))
    else:
        score -= 18
        message = f"{garment.name} không phải lựa chọn mặc định cho bối cảnh {context.occasion}."
        tradeoffs.append(message)
        evidence.append(DecisionEvidenceV1(rule_id="occasion_mismatch", message=message, score_delta=-18))

    if context.season in garment.seasons or "all_season" in garment.seasons:
        score += 10
        constraints.append(f"season:{context.season}")
        evidence.append(DecisionEvidenceV1(rule_id="season_match", message="Mùa sử dụng của garment phù hợp context.", score_delta=10))

    style_overlap = set(context.preferred_styles).intersection(garment.styles)
    if style_overlap:
        style_score = 8 * len(style_overlap)
        score += style_score
        constraints.append("style_overlap")
        evidence.append(DecisionEvidenceV1(rule_id="style_match", message=f"Khớp định hướng style: {', '.join(STYLE_LABELS[tag] for tag in sorted(style_overlap))}.", score_delta=style_score))
    avoided = set(context.avoid_style_tags).intersection(garment.styles)
    if avoided:
        penalty = -14 * len(avoided)
        score += penalty
        message = f"Garment mang style người dùng muốn tránh: {', '.join(STYLE_LABELS[tag] for tag in sorted(avoided))}."
        tradeoffs.append(message)
        evidence.append(DecisionEvidenceV1(rule_id="avoided_style_penalty", message=message, score_delta=penalty))

    if context.formality_target is not None:
        distance = abs(FORMALITY_ORDER[garment.formality_level] - FORMALITY_ORDER[context.formality_target])
        if distance == 0:
            score += 9
            evidence.append(DecisionEvidenceV1(rule_id="formality_match", message="Mức độ chỉn chu khớp nhu cầu sử dụng.", score_delta=9))
        elif distance == 1:
            score += 2
            message = "Mức độ chỉn chu lệch một bậc so với mục tiêu."
            tradeoffs.append(message)
            evidence.append(DecisionEvidenceV1(rule_id="formality_near_match", message=message, score_delta=2))
        else:
            score -= 10
            message = "Mức độ chỉn chu lệch đáng kể so với mục tiêu."
            tradeoffs.append(message)
            evidence.append(DecisionEvidenceV1(rule_id="formality_mismatch", message=message, score_delta=-10))

    intensity_gap = abs(INTENSITY_ORDER[garment.statement_level] - INTENSITY_ORDER[context.style_intensity])
    if intensity_gap == 0:
        score += 4
        evidence.append(DecisionEvidenceV1(rule_id="style_intensity_match", message="Mức độ nổi bật của garment khớp lựa chọn người dùng.", score_delta=4))
    elif intensity_gap > 1:
        tradeoffs.append("Mức độ nổi bật của garment không khớp hướng subtle/statement đã chọn.")

    if garment.fit_profile.fit_intent == context.fit_preference:
        score += 5
        evidence.append(DecisionEvidenceV1(rule_id="fit_preference", message="Fit intent khớp sở thích người dùng.", score_delta=5))

    if garment.color_family in context.excluded_colors:
        score -= 25
        message = f"Màu {garment.color_family} nằm trong danh sách loại trừ."
        tradeoffs.append(message)
        evidence.append(DecisionEvidenceV1(rule_id="excluded_color_penalty", message=message, score_delta=-25))
    if context.color_goals:
        if garment.color_family in context.color_goals:
            score += 6
            evidence.append(DecisionEvidenceV1(rule_id="color_goal_match", message="Color family khớp color goal đã khai báo.", score_delta=6))
        else:
            tradeoffs.append("Color family chưa khớp color goal ưu tiên.")
    if context.weather != "unknown":
        if context.weather in garment.weather_suitability:
            score += 6
            evidence.append(DecisionEvidenceV1(rule_id="weather_match", message="Garment có weather suitability phù hợp context.", score_delta=6))
        elif garment.weather_suitability:
            tradeoffs.append("Weather suitability của garment chưa khớp context.")
        else:
            tradeoffs.append("Garment chưa có weather suitability đã chuẩn hóa.")
    mobility_order = {"low": 0, "normal": 1, "high": 2}
    if mobility_order[garment.mobility_support] >= mobility_order[context.mobility_need]:
        score += 4
        evidence.append(DecisionEvidenceV1(rule_id="mobility_match", message="Mobility support đáp ứng nhu cầu di chuyển.", score_delta=4))
    else:
        tradeoffs.append("Garment có mobility support thấp hơn nhu cầu đã khai báo.")
    modesty_order = {"standard": 0, "covered": 1, "conservative": 2}
    if modesty_order[garment.modesty_level] >= modesty_order[context.modesty_preference]:
        score += 4
        evidence.append(DecisionEvidenceV1(rule_id="modesty_match", message="Mức độ coverage đáp ứng modesty preference.", score_delta=4))
    else:
        tradeoffs.append("Mức độ coverage của garment thấp hơn modesty preference.")
    if context.budget_max is not None:
        if garment.price is None:
            tradeoffs.append("Garment chưa có price metadata để kiểm tra budget.")
        elif garment.price <= context.budget_max:
            score += 5
            evidence.append(DecisionEvidenceV1(rule_id="budget_match", message="Price metadata nằm trong budget tối đa.", score_delta=5))
        else:
            score -= 20
            message = "Price metadata vượt budget tối đa."
            tradeoffs.append(message)
            evidence.append(DecisionEvidenceV1(rule_id="budget_exceeded", message=message, score_delta=-20))

    supported_intents = set(context.intent_tags).intersection(garment.intent_support)
    if supported_intents:
        intent_score = 4 * len(supported_intents)
        score += intent_score
        evidence.append(DecisionEvidenceV1(rule_id="functional_intent_support", message=f"Garment hỗ trợ nhu cầu: {', '.join(sorted(supported_intents))}.", score_delta=intent_score))
    if "low_maintenance" in context.intent_tags and garment.care_level == "easy":
        score += 4
        evidence.append(DecisionEvidenceV1(rule_id="easy_care_match", message="Yêu cầu low-maintenance được hỗ trợ bởi care level easy.", score_delta=4))

    if garment.garment_id in request.owned_garment_ids:
        if context.availability_policy == "owned_preferred":
            score += 12
            evidence.append(DecisionEvidenceV1(rule_id="owned_wardrobe_preference", message="Garment thuộc kho đồ active của người dùng.", score_delta=12))
        else:
            score += 3
            evidence.append(DecisionEvidenceV1(rule_id="owned_wardrobe_available", message="Garment thuộc kho đồ active của người dùng.", score_delta=3))

    effects = set(garment.proportion_effects)
    special_effects = {
        "sloped_shoulders": ("structure_shoulders", "Visual flag vai xuôi được hỗ trợ bằng đường vai có cấu trúc."),
        "flat_chest_profile": ("add_chest_dimension", "Visual flag ngực lép được hỗ trợ bằng hiệu ứng chiều sâu phần thân trên."),
        "bowed_leg_alignment": ("straighten_leg_line", "Visual flag chân vòng kiềng được hỗ trợ bằng đường ống/quy tắc tạo trục chân."),
    }
    for flag, (effect, message) in special_effects.items():
        if flag in body.visual_flags and effect in effects:
            score += 9
            constraints.append(f"visual_flag:{flag}")
            evidence.append(DecisionEvidenceV1(rule_id=f"effect_{effect}", message=message, score_delta=9))

    if body.measurements.height_cm < 165 and "elongate_legs" in effects:
        score += 6
        evidence.append(DecisionEvidenceV1(rule_id="proportion_elongate_legs", message="Item tạo đường dọc/cạp cao phù hợp mục tiêu kéo dài tỷ lệ chân.", score_delta=6))

    if body.skeleton_id in garment.asset.compatible_skeleton_ids and garment.asset.supports_body_fit:
        score += 8
        constraints.append("skeleton_compatible")
        evidence.append(DecisionEvidenceV1(rule_id="skeleton_compatible", message="Asset có contract phù hợp skeleton avatar hiện tại.", score_delta=8))
    else:
        tradeoffs.append("Asset chưa có contract skeleton phù hợp để render try-on.")

    return score, evidence, constraints, tradeoffs


def _compatible_combo(garments: tuple[GarmentMetadataV1, ...]) -> bool:
    categories = {garment.category for garment in garments}
    for garment in garments:
        allowed = set(garment.compatible_with)
        others = categories - {garment.category}
        if others and not others.issubset(allowed):
            return False
    return True


def _score_combo_coherence(garments: tuple[GarmentMetadataV1, ...], request: OutfitDecisionRequestV1) -> tuple[float, list[DecisionEvidenceV1], list[str], list[str], list[str], str, list[str]]:
    context = request.context
    score = 0.0
    evidence: list[DecisionEvidenceV1] = []
    constraints: list[str] = []
    tradeoffs: list[str] = []
    style_weights = Counter()
    for garment in garments:
        # Main clothing layers define the visual direction more strongly than shoes, belts or accessories.
        layer_weight = 2 if garment.layer_slot in {"base_top", "bottom", "dress", "outerwear"} else 1
        for style in garment.styles:
            style_weights[style] += layer_weight
    styles = Counter(style for garment in garments for style in garment.styles)
    preferred = [style for style in context.preferred_styles if style in styles]
    preferred.sort(key=lambda style: (-style_weights[style], context.preferred_styles.index(style)))
    archetypes = preferred or [style for style, _ in style_weights.most_common(2)]
    archetypes = list(dict.fromkeys(archetypes))[:3]
    if archetypes:
        primary = archetypes[0]
        repeated = style_weights[primary]
        if repeated >= 2:
            score += 12
            evidence.append(DecisionEvidenceV1(rule_id="style_coherence", message=f"Các lớp chính cùng củng cố archetype {STYLE_LABELS[primary]}.", score_delta=12))
            constraints.append(f"style_archetype:{primary}")
        else:
            score += 4
            evidence.append(DecisionEvidenceV1(rule_id="style_direction", message=f"Outfit giữ hướng {STYLE_LABELS[primary]} qua item chủ đạo.", score_delta=4))
    else:
        primary = "smart_casual"

    for garment in garments:
        conflicting = set(garment.avoid_pairing_with).intersection({style for other in garments if other is not garment for style in other.styles})
        if conflicting:
            score -= 8
            message = f"{garment.name} có pairing warning với style: {', '.join(STYLE_LABELS[tag] for tag in sorted(conflicting))}."
            tradeoffs.append(message)
            evidence.append(DecisionEvidenceV1(rule_id="pairing_warning", message=message, score_delta=-8))
        hints = set(garment.pairing_hints).intersection({style for other in garments if other is not garment for style in other.styles})
        if hints:
            score += 3
            evidence.append(DecisionEvidenceV1(rule_id="pairing_hint", message=f"{garment.name} có pairing hint phù hợp với outfit.", score_delta=3))

    colors = [garment.color_family for garment in garments]
    neutral_count = sum(color in {"neutral", "black", "white", "navy", "earth"} for color in colors)
    if neutral_count >= max(1, len(colors) - 1):
        score += 6
        evidence.append(DecisionEvidenceV1(rule_id="color_harmony", message="Outfit dùng nền màu trung tính ổn định để phối các lớp.", score_delta=6))
    elif len(set(colors)) >= 3:
        tradeoffs.append("Outfit dùng nhiều color family; nên xác nhận sắc độ thực tế của các item.")

    covered_intents = set().union(*(set(garment.intent_support) for garment in garments))
    missing_intents = set(context.intent_tags) - covered_intents
    highlights = [f"Hỗ trợ nhu cầu {intent.replace('_', ' ')}" for intent in sorted(set(context.intent_tags).intersection(covered_intents))]
    if missing_intents:
        tradeoffs.append(f"Kho đồ hiện tại chưa có metadata hỗ trợ rõ cho: {', '.join(sorted(missing_intents))}.")
    elif context.intent_tags:
        score += 8
        evidence.append(DecisionEvidenceV1(rule_id="outfit_intent_coverage", message="Tổ hợp item bao phủ toàn bộ nhu cầu sử dụng đã chọn.", score_delta=8))

    labels = ", ".join(STYLE_LABELS[tag] for tag in archetypes[:2]) if archetypes else "đa dụng"
    story = f"Bộ {labels} cho nhu cầu {context.occasion}, ưu tiên các item đang có trong kho đồ và các ràng buộc đã chọn."
    return score, evidence, constraints, tradeoffs, archetypes, story, highlights


def _diversify(candidates: list[OutfitCandidateV1], top_k: int) -> list[OutfitCandidateV1]:
    selected: list[OutfitCandidateV1] = []
    for candidate in sorted(candidates, key=lambda value: value.total_score, reverse=True):
        candidate_ids = set(candidate.garment_ids)
        candidate_style = candidate.style_archetypes[0] if candidate.style_archetypes else ""
        too_similar = False
        for existing in selected:
            overlap = len(candidate_ids.intersection(existing.garment_ids)) / max(1, len(candidate_ids.union(existing.garment_ids)))
            existing_style = existing.style_archetypes[0] if existing.style_archetypes else ""
            if overlap >= 0.67 and candidate_style == existing_style:
                too_similar = True
                break
        if not too_similar:
            selected.append(candidate)
        if len(selected) == top_k:
            return selected
    return selected[:top_k]


def decide_outfits(request: OutfitDecisionRequestV1) -> OutfitDecisionResponseV1:
    catalog_version, catalog = load_catalog()
    catalog = dict(catalog)
    rejected: list[RejectedCandidateV1] = []
    user_metadata_ids: set[str] = set()
    for garment in request.candidate_garments:
        if garment.garment_id in catalog:
            rejected.append(RejectedCandidateV1(
                candidate_key=garment.garment_id,
                reason_code="candidate_id_conflicts_with_catalog",
                message="User-imported garment metadata cannot reuse an active canonical catalog ID.",
            ))
            continue
        catalog[garment.garment_id] = garment
        user_metadata_ids.add(garment.garment_id)
    if request.candidate_garment_ids is None:
        allowed_ids = user_metadata_ids if request.candidate_garments else set(catalog.keys())
    else:
        allowed_ids = set(request.candidate_garment_ids)
    for garment_id in sorted(allowed_ids):
        garment = catalog.get(garment_id)
        if garment is None:
            rejected.append(RejectedCandidateV1(candidate_key=garment_id, reason_code="catalog_not_found", message="Garment không tồn tại trong catalog version hiện tại."))
        elif not _fits_body(garment, request):
            rejected.append(RejectedCandidateV1(candidate_key=garment_id, reason_code="body_fit_range", message="Garment nằm ngoài fit range đã khai báo cho body snapshot."))
    active = [garment for garment_id, garment in catalog.items() if garment_id in allowed_ids and _fits_body(garment, request)]
    required_slots = list(dict.fromkeys(request.context.required_slots))
    optional_slots = [slot for slot in dict.fromkeys(request.context.optional_slots) if slot not in required_slots]
    candidates_by_slot: list[list[GarmentMetadataV1 | None]] = []
    for slot in required_slots:
        category = SLOT_TO_CATEGORY[slot]
        candidates_by_slot.append([garment for garment in active if garment.category == category and garment.layer_slot == slot])
    missing_slots = [slot for slot, options in zip(required_slots, candidates_by_slot) if not options]
    if not candidates_by_slot or missing_slots:
        rejected.extend(RejectedCandidateV1(candidate_key=slot, reason_code="required_slot_unavailable", message="Không có garment active phù hợp cho required slot này.") for slot in missing_slots)
        return OutfitDecisionResponseV1(
            decision_id=f"dec_{uuid4().hex[:12]}", catalog_version=catalog_version, candidates=[], abstained=True,
            abstention_reason="Catalog hoặc kho đồ hiện tại không có garment phù hợp với required slot hoặc khoảng số đo đã cung cấp.",
            score_breakdown={}, rejected_candidates=rejected,
        )
    for slot in optional_slots:
        category = SLOT_TO_CATEGORY[slot]
        optional = [garment for garment in active if garment.category == category and garment.layer_slot == slot]
        candidates_by_slot.append([None, *optional])

    outfit_candidates: list[OutfitCandidateV1] = []
    for selection in product(*candidates_by_slot):
        combo = tuple(garment for garment in selection if garment is not None)
        if not _compatible_combo(combo):
            rejected.append(RejectedCandidateV1(candidate_key="|".join(garment.garment_id for garment in combo), reason_code="category_incompatible", message="Combination vi phạm canonical compatibility contract."))
            continue
        score = 0.0
        evidence: list[DecisionEvidenceV1] = []
        constraints: list[str] = []
        tradeoffs: list[str] = []
        for garment in combo:
            garment_score, garment_evidence, garment_constraints, garment_tradeoffs = _score_garment(garment, request)
            score += garment_score
            evidence.extend(garment_evidence)
            constraints.extend(garment_constraints)
            tradeoffs.extend(garment_tradeoffs)
        coherence_score, coherence_evidence, coherence_constraints, coherence_tradeoffs, archetypes, story, highlights = _score_combo_coherence(combo, request)
        score += coherence_score
        evidence.extend(coherence_evidence)
        constraints.extend(coherence_constraints)
        tradeoffs.extend(coherence_tradeoffs)
        required_count = len(required_slots)
        confidence = max(0.15, min(0.95, 0.42 + score / (required_count * 110)))
        confirmations = []
        if any(garment.source != "canonical_seed" for garment in combo):
            confirmations.append("Xác nhận metadata/size của garment nhập từ ảnh trước khi render.")
        if request.body.calibration_version.startswith("heuristic"):
            confirmations.append("Avatar dùng calibration heuristic; cần xác nhận độ ôm thực tế khi có 3D fitting.")
        if request.context.availability_policy != "owned_only" and any(garment.garment_id not in request.owned_garment_ids for garment in combo):
            confirmations.append("Một hoặc nhiều item là catalog discovery, chưa được xác nhận có trong kho đồ của bạn.")
        outfit_candidates.append(OutfitCandidateV1(
            outfit_id=f"out_{'_'.join(garment.garment_id.removeprefix('gar_') for garment in combo)}",
            garment_ids=[garment.garment_id for garment in combo], total_score=round(score, 2), confidence=round(confidence, 2),
            constraints_satisfied=sorted(set(constraints)), tradeoffs=sorted(set(tradeoffs)), evidence=evidence,
            needs_user_confirmation=confirmations, style_archetypes=archetypes, style_story=story, functional_highlights=highlights,
        ))

    ranked = _diversify(outfit_candidates, request.top_k)
    score_breakdown: dict[str, float] = {}
    for candidate in ranked:
        for item in candidate.evidence:
            score_breakdown[item.rule_id] = round(score_breakdown.get(item.rule_id, 0.0) + item.score_delta, 2)
    return OutfitDecisionResponseV1(
        decision_id=f"dec_{uuid4().hex[:12]}", catalog_version=catalog_version, candidates=ranked,
        abstained=not bool(ranked), abstention_reason=None if ranked else "Không tạo được combination hợp lệ từ catalog và context hiện tại.",
        score_breakdown=score_breakdown, rejected_candidates=rejected,
    )
