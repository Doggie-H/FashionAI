from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field


ContractVersion = Literal["1.0"]
GarmentCategory = Literal["top", "bottom", "dress", "outerwear", "footwear", "belt", "accessory"]
LayerSlot = Literal["base_top", "bottom", "dress", "outerwear", "footwear", "belt", "accessory"]
FitIntent = Literal["relaxed", "regular", "tailored", "body_skimming"]
StyleTag = Literal["minimal", "classic", "smart_casual", "streetwear", "romantic", "business", "sporty", "quiet_luxury", "preppy", "edgy", "bohemian", "athleisure", "utility", "modest", "resort", "creative", "vintage"]
Occasion = Literal["daily", "work", "date", "event", "travel", "formal", "interview", "meeting", "presentation", "celebration", "weekend", "gym", "outdoor", "home", "cocktail", "wedding_guest"]
Season = Literal["spring", "summer", "autumn", "winter", "all_season"]
IntentTag = Literal["comfort", "all_day", "weather_protection", "photo_ready", "low_maintenance", "packable", "movement", "coverage", "professional_presence", "celebration", "confidence"]
FormalityLevel = Literal["casual", "smart_casual", "business", "formal", "ceremonial"]
StyleIntensity = Literal["subtle", "balanced", "statement"]


class RawMeasurementsV1(BaseModel):
    height_cm: Annotated[float, Field(ge=120, le=230)]
    weight_kg: Annotated[float, Field(ge=30, le=250)]
    shoulder_cm: Annotated[float, Field(ge=25, le=80)]
    bust_cm: Annotated[float, Field(ge=50, le=180)]
    waist_cm: Annotated[float, Field(ge=40, le=180)]
    hip_cm: Annotated[float, Field(ge=50, le=200)]
    inseam_cm: Annotated[float, Field(ge=45, le=120)]
    shoulder_slope: Literal["straight", "sloped"] = "straight"
    chest_profile: Literal["full", "flat"] = "full"
    leg_alignment: Literal["straight", "bowed"] = "straight"


class BoneLengthScalesV1(BaseModel):
    spine: Annotated[float, Field(ge=0.8, le=1.2)]
    upper_arm: Annotated[float, Field(ge=0.8, le=1.2)]
    lower_arm: Annotated[float, Field(ge=0.8, le=1.2)]
    upper_leg: Annotated[float, Field(ge=0.8, le=1.2)]
    lower_leg: Annotated[float, Field(ge=0.8, le=1.2)]


class ShapeParametersV1(BaseModel):
    height_scale: Annotated[float, Field(ge=0.8, le=1.2)]
    shoulder_scale: Annotated[float, Field(ge=0.7, le=1.35)]
    chest_scale: Annotated[float, Field(ge=0.7, le=1.35)]
    waist_scale: Annotated[float, Field(ge=0.65, le=1.4)]
    hip_scale: Annotated[float, Field(ge=0.7, le=1.4)]
    leg_scale: Annotated[float, Field(ge=0.8, le=1.2)]


class ParametricBodyContractV1(BaseModel):
    contract_version: ContractVersion = "1.0"
    body_model_id: str = "xbot-prototype-v1"
    skeleton_id: str = "mixamo-humanoid-v1"
    calibration_version: str = "heuristic-v1"
    measurements: RawMeasurementsV1
    shape_parameters: ShapeParametersV1
    bone_length_scales: BoneLengthScalesV1
    visual_flags: list[str] = Field(default_factory=list, max_length=8)
    generated_at: datetime


class GarmentAssetV1(BaseModel):
    template_id: str = Field(pattern=r"^tpl_[a-z0-9_]+$")
    asset_uri: str = Field(pattern=r"^(https?://|/)[^\s]+$")
    compatible_skeleton_ids: list[str] = Field(min_length=1)
    rest_pose: Literal["t_pose", "a_pose"] = "a_pose"
    anchors: list[Literal["shoulder", "chest", "waist", "hip", "left_foot", "right_foot"]] = Field(default_factory=list)
    supports_body_fit: bool = True


class GarmentFitProfileV1(BaseModel):
    fit_intent: FitIntent
    min_bust_cm: Annotated[float | None, Field(default=None, ge=50, le=180)] = None
    max_bust_cm: Annotated[float | None, Field(default=None, ge=50, le=180)] = None
    min_waist_cm: Annotated[float | None, Field(default=None, ge=40, le=180)] = None
    max_waist_cm: Annotated[float | None, Field(default=None, ge=40, le=180)] = None
    min_hip_cm: Annotated[float | None, Field(default=None, ge=50, le=200)] = None
    max_hip_cm: Annotated[float | None, Field(default=None, ge=50, le=200)] = None


class GarmentMetadataV1(BaseModel):
    schema_version: ContractVersion = "1.0"
    garment_id: str = Field(pattern=r"^gar_[a-z0-9_]+$")
    name: str = Field(min_length=2, max_length=120)
    category: GarmentCategory
    layer_slot: LayerSlot
    styles: list[StyleTag] = Field(min_length=1, max_length=6)
    occasions: list[Occasion] = Field(min_length=1, max_length=6)
    seasons: list[Season] = Field(min_length=1, max_length=5)
    color_family: Literal["neutral", "black", "white", "navy", "earth", "burgundy", "emerald", "bright"]
    material: str = Field(min_length=2, max_length=80)
    silhouette: str = Field(min_length=2, max_length=120)
    proportion_effects: list[Literal["elongate_legs", "structure_shoulders", "define_waist", "soften_shoulders", "straighten_leg_line", "add_chest_dimension"]] = Field(default_factory=list)
    compatible_with: list[GarmentCategory] = Field(default_factory=list)
    fit_profile: GarmentFitProfileV1
    asset: GarmentAssetV1
    status: Literal["active", "draft", "archived"] = "active"
    source: Literal["canonical_seed", "user_import", "ai_generated"] = "canonical_seed"
    price: Annotated[float | None, Field(default=None, ge=0, le=1_000_000)] = None
    weather_suitability: list[Literal["hot", "mild", "cold", "rainy", "humid"]] = Field(default_factory=list, max_length=5)
    mobility_support: Literal["low", "normal", "high"] = "normal"
    modesty_level: Literal["standard", "covered", "conservative"] = "standard"
    formality_level: FormalityLevel = "smart_casual"
    statement_level: StyleIntensity = "balanced"
    intent_support: list[IntentTag] = Field(default_factory=list, max_length=8)
    care_level: Literal["easy", "moderate", "special"] = "moderate"
    color_role: Literal["neutral_base", "accent", "statement", "supporting"] = "supporting"
    occasion_notes: str | None = Field(default=None, max_length=220)
    style_notes: str | None = Field(default=None, max_length=220)
    pairing_hints: list[StyleTag] = Field(default_factory=list, max_length=6)
    avoid_pairing_with: list[StyleTag] = Field(default_factory=list, max_length=6)


class StyleContextV1(BaseModel):
    """Versioned, additive style constraints captured immutably in a StylingSession snapshot."""

    occasion: Occasion
    preferred_styles: list[StyleTag] = Field(default_factory=list, max_length=4)
    season: Season = "all_season"
    fit_preference: FitIntent = "regular"
    required_slots: list[LayerSlot] = Field(default_factory=lambda: ["base_top", "bottom"])
    excluded_colors: list[str] = Field(default_factory=list, max_length=5)
    weather: Literal["unknown", "hot", "mild", "cold", "rainy", "humid"] = "unknown"
    temperature_c: Annotated[float | None, Field(default=None, ge=-20, le=55)] = None
    mobility_need: Literal["low", "normal", "high"] = "normal"
    budget_max: Annotated[float | None, Field(default=None, gt=0, le=1_000_000)] = None
    modesty_preference: Literal["standard", "covered", "conservative"] = "standard"
    color_goals: list[str] = Field(default_factory=list, max_length=5)
    availability_policy: Literal["owned_only", "owned_preferred", "allow_catalog"] = "owned_only"
    intent_tags: list[IntentTag] = Field(default_factory=list, max_length=5)
    formality_target: FormalityLevel | None = None
    style_intensity: StyleIntensity = "balanced"
    optional_slots: list[LayerSlot] = Field(default_factory=list, max_length=4)
    avoid_style_tags: list[StyleTag] = Field(default_factory=list, max_length=4)


class OutfitDecisionRequestV1(BaseModel):
    body: ParametricBodyContractV1
    context: StyleContextV1
    candidate_garment_ids: list[str] | None = Field(default=None, max_length=50)
    # Immutable, reviewer-approved snapshots for user-imported garments. Raw perception is never accepted here.
    candidate_garments: list[GarmentMetadataV1] = Field(default_factory=list, max_length=50)
    owned_garment_ids: list[str] = Field(default_factory=list, max_length=50)
    top_k: Annotated[int, Field(default=3, ge=1, le=5)] = 3


class DecisionEvidenceV1(BaseModel):
    rule_id: str
    message: str
    score_delta: float


class OutfitCandidateV1(BaseModel):
    outfit_id: str
    garment_ids: list[str] = Field(min_length=1)
    total_score: float
    confidence: Annotated[float, Field(ge=0, le=1)]
    constraints_satisfied: list[str]
    tradeoffs: list[str]
    evidence: list[DecisionEvidenceV1]
    needs_user_confirmation: list[str]
    style_archetypes: list[StyleTag] = Field(default_factory=list)
    style_story: str = ""
    functional_highlights: list[str] = Field(default_factory=list)


class RejectedCandidateV1(BaseModel):
    candidate_key: str
    reason_code: str
    message: str


class OutfitDecisionResponseV1(BaseModel):
    schema_version: ContractVersion = "1.0"
    decision_id: str
    catalog_version: str
    candidates: list[OutfitCandidateV1]
    abstained: bool
    abstention_reason: str | None = None
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    rejected_candidates: list[RejectedCandidateV1] = Field(default_factory=list)
