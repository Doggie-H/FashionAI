from __future__ import annotations

import json
from pathlib import Path

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "canonical_garments_v1.json"
SKELETON = ["mixamo-humanoid-v1"]


def asset(template_id: str, uri: str, anchors: list[str]) -> dict:
    return {
        "template_id": template_id,
        "asset_uri": uri,
        "compatible_skeleton_ids": SKELETON,
        "rest_pose": "a_pose",
        "anchors": anchors,
        "supports_body_fit": True,
    }


def garment(
    garment_id: str,
    name: str,
    category: str,
    layer_slot: str,
    styles: list[str],
    occasions: list[str],
    seasons: list[str],
    color_family: str,
    material: str,
    silhouette: str,
    fit_profile: dict,
    template_id: str,
    uri: str,
    anchors: list[str],
    **knowledge: object,
) -> dict:
    compatibility = {
        "top": ["bottom", "outerwear", "footwear", "belt", "accessory"],
        "bottom": ["top", "outerwear", "footwear", "belt", "accessory"],
        "dress": ["outerwear", "footwear", "belt", "accessory"],
        "outerwear": ["top", "bottom", "dress", "footwear", "belt", "accessory"],
        "footwear": ["top", "bottom", "dress", "outerwear", "belt", "accessory"],
        "belt": ["top", "bottom", "dress", "outerwear", "footwear", "accessory"],
        "accessory": ["top", "bottom", "dress", "outerwear", "footwear", "belt"],
    }
    return {
        "schema_version": "1.0",
        "garment_id": garment_id,
        "name": name,
        "category": category,
        "layer_slot": layer_slot,
        "styles": styles,
        "occasions": occasions,
        "seasons": seasons,
        "color_family": color_family,
        "material": material,
        "silhouette": silhouette,
        "proportion_effects": knowledge.pop("proportion_effects", []),
        "compatible_with": compatibility[category],
        "fit_profile": fit_profile,
        "asset": asset(template_id, uri, anchors),
        "status": "active",
        "source": "canonical_seed",
        **knowledge,
    }


def main() -> None:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    existing = {item["garment_id"]: item for item in payload["garments"]}
    enrichments = {
        "gar_white_structured_shirt": {"formality_level": "business", "statement_level": "subtle", "intent_support": ["professional_presence", "photo_ready", "low_maintenance", "confidence"], "care_level": "easy", "color_role": "neutral_base", "style_notes": "Nền linh hoạt cho business, preppy và quiet luxury.", "pairing_hints": ["business", "classic", "preppy", "quiet_luxury"]},
        "gar_navy_vneck_top": {"formality_level": "smart_casual", "statement_level": "subtle", "intent_support": ["comfort", "all_day", "packable"], "care_level": "easy", "color_role": "neutral_base", "style_notes": "Top mềm dễ chuyển từ daily sang date.", "pairing_hints": ["minimal", "romantic", "resort"]},
        "gar_black_highwaist_trouser": {"formality_level": "business", "statement_level": "subtle", "intent_support": ["professional_presence", "all_day", "confidence"], "care_level": "moderate", "color_role": "neutral_base", "pairing_hints": ["business", "classic", "quiet_luxury"]},
        "gar_earth_wideleg_trouser": {"formality_level": "smart_casual", "statement_level": "balanced", "intent_support": ["comfort", "movement", "packable"], "care_level": "moderate", "color_role": "neutral_base", "pairing_hints": ["minimal", "bohemian", "resort"]},
        "gar_burgundy_midi_dress": {"formality_level": "formal", "statement_level": "balanced", "intent_support": ["photo_ready", "celebration", "confidence"], "care_level": "special", "color_role": "accent", "pairing_hints": ["romantic", "classic", "vintage"]},
        "gar_navy_blazer": {"formality_level": "business", "statement_level": "balanced", "intent_support": ["professional_presence", "weather_protection", "confidence"], "care_level": "special", "color_role": "neutral_base", "pairing_hints": ["business", "classic", "preppy", "quiet_luxury"]},
        "gar_black_loafer": {"formality_level": "business", "statement_level": "subtle", "intent_support": ["all_day", "professional_presence"], "care_level": "moderate", "color_role": "neutral_base", "pairing_hints": ["classic", "business", "minimal", "preppy"]},
        "gar_black_slim_belt": {"formality_level": "smart_casual", "statement_level": "subtle", "intent_support": ["confidence", "photo_ready"], "care_level": "moderate", "color_role": "supporting", "pairing_hints": ["classic", "business", "romantic", "quiet_luxury"]},
    }
    compatibility = {
        "top": ["bottom", "outerwear", "footwear", "belt", "accessory"],
        "bottom": ["top", "outerwear", "footwear", "belt", "accessory"],
        "dress": ["outerwear", "footwear", "belt", "accessory"],
        "outerwear": ["top", "bottom", "dress", "footwear", "belt", "accessory"],
        "footwear": ["top", "bottom", "dress", "outerwear", "belt", "accessory"],
        "belt": ["top", "bottom", "dress", "outerwear", "footwear", "accessory"],
        "accessory": ["top", "bottom", "dress", "outerwear", "footwear", "belt"],
    }
    for garment_id, fields in enrichments.items():
        existing[garment_id].update(fields)
        existing[garment_id]["compatible_with"] = compatibility[existing[garment_id]["category"]]

    additions = [
        garment("gar_beige_knit_polo", "Áo polo len beige", "top", "base_top", ["quiet_luxury", "preppy", "minimal"], ["weekend", "date", "travel", "meeting"], ["spring", "autumn", "all_season"], "earth", "fine merino knit", "soft collar knit polo", {"fit_intent": "regular", "min_bust_cm": 70, "max_bust_cm": 120}, "tpl_beige_knit_polo", "/models/garments/beige-knit-polo.glb", ["shoulder", "chest", "waist"], proportion_effects=["soften_shoulders"], formality_level="smart_casual", statement_level="subtle", intent_support=["comfort", "all_day", "packable", "confidence"], care_level="special", color_role="neutral_base", style_notes="Nền quiet luxury/preppy nhẹ nhàng.", pairing_hints=["quiet_luxury", "preppy", "minimal"]),
        garment("gar_olive_utility_overshirt", "Áo khoác sơ mi utility olive", "outerwear", "outerwear", ["utility", "streetwear", "creative"], ["weekend", "travel", "outdoor", "daily"], ["spring", "autumn", "all_season"], "earth", "cotton twill", "relaxed utility overshirt", {"fit_intent": "relaxed", "min_bust_cm": 72, "max_bust_cm": 124}, "tpl_olive_utility_overshirt", "/models/garments/olive-utility-overshirt.glb", ["shoulder", "chest", "waist"], formality_level="casual", statement_level="balanced", intent_support=["weather_protection", "movement", "packable", "low_maintenance"], care_level="easy", color_role="supporting", pairing_hints=["utility", "streetwear", "creative"]),
        garment("gar_black_moto_jacket", "Áo khoác moto đen", "outerwear", "outerwear", ["edgy", "streetwear", "creative"], ["date", "cocktail", "weekend", "event"], ["autumn", "winter"], "black", "vegan leather", "cropped moto jacket", {"fit_intent": "regular", "min_bust_cm": 72, "max_bust_cm": 116}, "tpl_black_moto_jacket", "/models/garments/black-moto-jacket.glb", ["shoulder", "chest", "waist"], proportion_effects=["structure_shoulders"], formality_level="smart_casual", statement_level="statement", intent_support=["confidence", "photo_ready", "weather_protection"], care_level="special", color_role="statement", pairing_hints=["edgy", "streetwear", "creative"], avoid_pairing_with=["modest"]),
        garment("gar_fluid_bohemian_blouse", "Áo blouse bohemian hoạ tiết", "top", "base_top", ["bohemian", "romantic", "resort"], ["date", "travel", "weekend", "celebration"], ["spring", "summer"], "bright", "printed viscose", "fluid printed blouse", {"fit_intent": "relaxed", "min_bust_cm": 70, "max_bust_cm": 118}, "tpl_fluid_bohemian_blouse", "/models/garments/fluid-bohemian-blouse.glb", ["shoulder", "chest", "waist"], formality_level="smart_casual", statement_level="statement", intent_support=["photo_ready", "comfort", "packable"], care_level="moderate", color_role="statement", pairing_hints=["bohemian", "romantic", "resort"]),
        garment("gar_cream_pleated_midi_skirt", "Chân váy midi xếp ly cream", "bottom", "bottom", ["romantic", "preppy", "vintage"], ["date", "meeting", "celebration", "wedding_guest"], ["spring", "autumn"], "neutral", "pleated woven", "high waist pleated midi", {"fit_intent": "regular", "min_waist_cm": 56, "max_waist_cm": 106, "min_hip_cm": 78, "max_hip_cm": 132}, "tpl_cream_pleated_midi_skirt", "/models/garments/cream-pleated-midi-skirt.glb", ["waist", "hip"], proportion_effects=["define_waist", "elongate_legs"], formality_level="smart_casual", statement_level="balanced", intent_support=["photo_ready", "coverage", "celebration"], care_level="moderate", color_role="neutral_base", pairing_hints=["romantic", "preppy", "vintage"]),
        garment("gar_technical_athleisure_zip_top", "Áo zip athleisure navy", "top", "base_top", ["athleisure", "sporty", "utility"], ["gym", "outdoor", "travel", "weekend"], ["spring", "autumn", "all_season"], "navy", "technical stretch knit", "fitted zip active top", {"fit_intent": "regular", "min_bust_cm": 70, "max_bust_cm": 116}, "tpl_technical_athleisure_zip_top", "/models/garments/technical-athleisure-zip-top.glb", ["shoulder", "chest", "waist"], formality_level="casual", statement_level="subtle", intent_support=["movement", "comfort", "weather_protection", "packable"], care_level="easy", color_role="supporting", pairing_hints=["athleisure", "sporty", "utility"]),
        garment("gar_technical_jogger_black", "Quần jogger technical đen", "bottom", "bottom", ["athleisure", "sporty", "utility"], ["gym", "outdoor", "travel", "weekend"], ["spring", "autumn", "all_season"], "black", "technical stretch weave", "tapered technical jogger", {"fit_intent": "relaxed", "min_waist_cm": 58, "max_waist_cm": 112, "min_hip_cm": 80, "max_hip_cm": 138}, "tpl_technical_jogger_black", "/models/garments/technical-jogger-black.glb", ["waist", "hip", "left_foot", "right_foot"], formality_level="casual", statement_level="subtle", intent_support=["movement", "comfort", "weather_protection", "low_maintenance"], care_level="easy", color_role="neutral_base", pairing_hints=["athleisure", "sporty", "utility"]),
        garment("gar_white_minimal_sneaker", "Sneaker trắng tối giản", "footwear", "footwear", ["minimal", "preppy", "athleisure", "smart_casual"], ["daily", "travel", "weekend", "outdoor"], ["all_season"], "white", "leather and rubber", "clean low top sneaker", {"fit_intent": "regular"}, "tpl_white_minimal_sneaker", "/models/garments/white-minimal-sneaker.glb", ["left_foot", "right_foot"], proportion_effects=["elongate_legs"], formality_level="casual", statement_level="subtle", intent_support=["movement", "comfort", "all_day"], care_level="easy", color_role="neutral_base", pairing_hints=["minimal", "preppy", "athleisure", "smart_casual"]),
        garment("gar_camel_trench_coat", "Trench coat camel", "outerwear", "outerwear", ["quiet_luxury", "classic", "minimal"], ["meeting", "presentation", "travel", "date"], ["spring", "autumn"], "earth", "water-resistant cotton", "belted long trench", {"fit_intent": "regular", "min_bust_cm": 70, "max_bust_cm": 122}, "tpl_camel_trench_coat", "/models/garments/camel-trench-coat.glb", ["shoulder", "chest", "waist", "hip"], proportion_effects=["elongate_legs", "define_waist"], formality_level="business", statement_level="balanced", intent_support=["weather_protection", "professional_presence", "photo_ready"], care_level="moderate", color_role="neutral_base", pairing_hints=["quiet_luxury", "classic", "minimal"]),
        garment("gar_silver_statement_earrings", "Khuyên tai bạc điểm nhấn", "accessory", "accessory", ["creative", "edgy", "romantic"], ["cocktail", "celebration", "date", "event"], ["all_season"], "neutral", "silver tone metal", "sculptural statement earrings", {"fit_intent": "regular"}, "tpl_silver_statement_earrings", "/models/garments/silver-statement-earrings.glb", ["chest"], formality_level="formal", statement_level="statement", intent_support=["photo_ready", "celebration", "confidence"], care_level="special", color_role="statement", pairing_hints=["creative", "edgy", "romantic"]),
        garment("gar_straw_resort_bag", "Túi cói resort", "accessory", "accessory", ["resort", "bohemian", "romantic"], ["travel", "weekend", "date", "celebration"], ["spring", "summer"], "earth", "woven straw", "structured straw shoulder bag", {"fit_intent": "regular"}, "tpl_straw_resort_bag", "/models/garments/straw-resort-bag.glb", ["chest"], formality_level="casual", statement_level="balanced", intent_support=["packable", "comfort", "photo_ready"], care_level="special", color_role="accent", pairing_hints=["resort", "bohemian", "romantic"]),
    ]
    for item in additions:
        existing[item["garment_id"]] = item
    payload["catalog_version"] = "1.1.0-style-knowledge"
    payload["garments"] = [existing[key] for key in sorted(existing)]
    CATALOG_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(payload['garments'])} canonical garments to {CATALOG_PATH}")


if __name__ == "__main__":
    main()
