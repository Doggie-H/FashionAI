from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .phase_a_schemas import GarmentCategory, GarmentMetadataV1


RigStatus = Literal["canonical_proxy", "rigged_template", "pending_reconstruction", "failed"]
ConversionBackend = Literal["canonical_proxy", "garment3dgen_offline"]
PipelineState = Literal["imported", "queued", "segmenting", "segmented", "pending_reconstruction", "rigged_template", "failed"]
SemanticTaggingStatus = Literal["not_requested", "queued", "running", "needs_review", "approved", "rejected", "unavailable", "failed"]
SemanticTaggingProvider = Literal["disabled", "mock", "qwen25vl"]
SemanticDimension = Literal[
    "category", "styles", "occasions", "seasons", "color_family", "material", "silhouette",
    "formality_level", "statement_level", "weather_suitability", "mobility_support", "modesty_level",
    "intent_support", "pairing_hints", "avoid_pairing_with",
]
StructuralView = Literal["front", "side", "back", "detail", "unknown"]
StructuralFeature = Literal[
    "neckline", "shoulder_construction", "shoulder_width", "sleeve_length", "torso_length",
    "waist_shape", "hem_shape", "rise", "waist_construction", "hip_fit", "leg_shape", "leg_length",
]


class StructuralEvidenceV1(BaseModel):
    feature: StructuralFeature
    value: str = Field(min_length=3, max_length=40)
    confidence: float = Field(ge=0, le=1)
    visible_views: list[StructuralView] = Field(default_factory=lambda: ["unknown"], min_length=1, max_length=4)
    rationale: str = Field(min_length=1, max_length=360)


class GarmentStructuralProfileV1(BaseModel):
    """Visible structural cues only; never an asserted physical pattern or exact 3D geometry."""

    schema_version: Literal["1.0"] = "1.0"
    source_views: list[StructuralView] = Field(default_factory=lambda: ["front"], min_length=1, max_length=4)
    neckline: Literal["crew", "v_neck", "round", "collar", "polo", "halter", "strapless", "unknown"] = "unknown"
    shoulder_construction: Literal["set_in", "dropped", "raglan", "sleeveless", "unknown"] = "unknown"
    shoulder_width: Literal["narrow", "regular", "wide", "unknown"] = "unknown"
    sleeve_length: Literal["sleeveless", "cap", "short", "elbow", "long", "unknown"] = "unknown"
    torso_length: Literal["cropped", "waist", "hip", "long", "unknown"] = "unknown"
    waist_shape: Literal["fitted", "regular", "relaxed", "peplum", "unknown"] = "unknown"
    hem_shape: Literal["straight", "curved", "asymmetric", "unknown"] = "unknown"
    rise: Literal["low", "mid", "high", "unknown"] = "unknown"
    waist_construction: Literal["flat", "elastic", "belted", "unknown"] = "unknown"
    hip_fit: Literal["fitted", "regular", "relaxed", "unknown"] = "unknown"
    leg_shape: Literal["skinny", "slim", "straight", "tapered", "wide", "bootcut", "flared", "unknown"] = "unknown"
    leg_length: Literal["short", "cropped", "ankle", "full", "unknown"] = "unknown"
    evidence: list[StructuralEvidenceV1] = Field(default_factory=list, max_length=12)
    limitations: list[str] = Field(default_factory=list, max_length=12)


class SemanticTagEvidenceV1(BaseModel):
    dimension: SemanticDimension
    values: list[str] = Field(min_length=1, max_length=8)
    confidence: float = Field(ge=0, le=1)
    rationale: str = Field(min_length=1, max_length=360)


class GarmentSemanticTaggingV1(BaseModel):
    """Model suggestion only. It becomes ranking metadata only after garment review approval."""

    schema_version: Literal["1.0"] = "1.0"
    status: SemanticTaggingStatus = "not_requested"
    provider: SemanticTaggingProvider = "disabled"
    model_id: str | None = Field(default=None, max_length=240)
    model_revision: str | None = Field(default=None, max_length=240)
    source_image_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    candidate_metadata: GarmentMetadataV1 | None = None
    structural_profile: GarmentStructuralProfileV1 | None = None
    evidence: list[SemanticTagEvidenceV1] = Field(default_factory=list, max_length=20)
    limitations: list[str] = Field(default_factory=list, max_length=12)
    failure_reason: str | None = Field(default=None, max_length=500)
    analyzed_at: datetime | None = None


class GarmentImageAnalysisV1(BaseModel):
    category: GarmentCategory
    confidence: float = Field(ge=0, le=1)
    color_hint: str | None = Field(default=None, max_length=40)
    silhouette_hint: str | None = Field(default=None, max_length=120)
    needs_human_review: bool
    limitations: list[str] = Field(default_factory=list, max_length=8)
    semantic_tagging: GarmentSemanticTaggingV1 | None = None


class SegmentationArtifactV1(BaseModel):
    provider: Literal["rembg", "alpha_fallback"]
    asset_uri: str = Field(pattern=r"^/uploads/garment_segments/[^\s]+$")
    has_transparency: bool
    quality: Literal["verified", "unverified"]
    limitations: list[str] = Field(default_factory=list, max_length=6)
    completed_at: datetime


class ReconstructionStateV1(BaseModel):
    pipeline_state: PipelineState = "imported"
    job_id: str | None = None
    requested_backend: ConversionBackend = "garment3dgen_offline"
    provider_version: str | None = None
    failure_reason: str | None = None
    updated_at: datetime


class MeshQualityGateV1(BaseModel):
    asset_exists: bool
    glb_valid: bool
    skeleton_id: str | None = None
    rest_pose: Literal["a_pose", "t_pose"] | None = None
    anchors_present: bool
    skin_weights_valid: bool
    scale_valid: bool
    bounds_valid: bool
    intersection_check: Literal["not_run", "passed", "failed"] = "not_run"
    review_status: Literal["pending_review", "approved", "rejected"] = "pending_review"
    failure_reasons: list[str] = Field(default_factory=list, max_length=10)


class GarmentImportManifestV1(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    import_id: str = Field(pattern=r"^imp_[a-f0-9]{12}$")
    source_image_uri: str = Field(pattern=r"^/uploads/garments/[^\s]+$")
    source_image_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    analysis: GarmentImageAnalysisV1
    selected_template_id: str = Field(pattern=r"^tpl_[a-z0-9_]+$")
    selected_garment_id: str = Field(pattern=r"^gar_[a-z0-9_]+$")
    target_skeleton_id: str = "mixamo-humanoid-v1"
    rest_pose: Literal["a_pose", "t_pose"] = "a_pose"
    rig_status: RigStatus
    conversion_backend: ConversionBackend
    render_binding: dict[str, float | str] = Field(default_factory=dict)
    generated_asset_uri: str | None = None
    segmentation: SegmentationArtifactV1 | None = None
    quality_gate: MeshQualityGateV1 | None = None
    reconstruction: ReconstructionStateV1
    created_at: datetime


class GarmentImportResponseV1(BaseModel):
    status: Literal["completed", "queued", "needs_review", "pending_reconstruction", "failed"]
    manifest: GarmentImportManifestV1
    job_id: str | None = None


class SemanticTaggingStartResponseV1(BaseModel):
    status: Literal["queued", "needs_review", "unavailable", "failed"]
    manifest: GarmentImportManifestV1
    job_id: str | None = None


class ReconstructionStartResponseV1(BaseModel):
    status: Literal["queued", "pending_reconstruction", "failed"]
    manifest: GarmentImportManifestV1
    job_id: str | None = None


class TryOnBindingRequestV1(BaseModel):
    import_ids: list[str] = Field(min_length=1, max_length=6)
    target_skeleton_id: str = "mixamo-humanoid-v1"


class TryOnBindingV1(BaseModel):
    import_id: str
    category: GarmentCategory
    selected_garment_id: str
    template_id: str
    rig_status: RigStatus
    target_skeleton_id: str
    render_binding: dict[str, float | str]
