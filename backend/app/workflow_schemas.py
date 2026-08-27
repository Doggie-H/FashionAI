from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .phase_b_schemas import GarmentStructuralProfileV1
from .phase_a_schemas import (
    GarmentCategory,
    GarmentMetadataV1,
    OutfitDecisionResponseV1,
    ParametricBodyContractV1,
    RawMeasurementsV1,
    StyleContextV1,
)


BodyProfileStatus = Literal["draft", "calibrated", "active", "needs_correction", "superseded", "archived"]
WardrobeAssetStatus = Literal["image_received", "normalized", "pending_review", "active", "rejected", "archived"]
StylingSessionStatus = Literal[
    "draft", "context_captured", "inputs_resolved", "decision_running", "recommendations_ready",
    "user_reviewing", "outfit_selected", "try_on_queued", "try_on_ready", "feedback_captured",
    "closed", "blocked_needs_input", "abstained", "failed",
]
TryOnRunStatus = Literal["requested", "asset_resolution", "binding_validation", "render_queued", "ready", "proxy_fallback", "needs_review", "failed"]
RenderMode = Literal["canonical_proxy", "rigged_template", "approved_reconstructed_asset"]


class CommandMetaV1(BaseModel):
    # In JWT mode these fields are injected by the transport adapter; body values remain demo-backward-compatible.
    actor_id: int | None = Field(default=None, gt=0)
    idempotency_key: str | None = Field(default=None, min_length=12, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    correlation_id: str | None = Field(default=None, min_length=8, max_length=128)


class CreateBodyProfileCommandV1(CommandMetaV1):
    measurements: RawMeasurementsV1


class ConfirmBodyProfileCommandV1(CommandMetaV1):
    confirmation_note: str | None = Field(default=None, max_length=500)


class BodyProfileRevisionV1(BaseModel):
    profile_id: str
    owner_id: int
    revision: int = Field(ge=1)
    status: BodyProfileStatus
    contract: ParametricBodyContractV1
    created_at: datetime
    confirmed_at: datetime | None = None


class CreateWardrobeAssetCommandV1(CommandMetaV1):
    name: str = Field(min_length=2, max_length=120)
    category: GarmentCategory
    import_id: str | None = Field(default=None, pattern=r"^imp_[a-f0-9]{12}$")
    canonical_garment_id: str | None = Field(default=None, pattern=r"^gar_[a-z0-9_]+$")


class WardrobeAssetRevisionV1(BaseModel):
    asset_id: str
    revision_id: str
    owner_id: int
    name: str
    category: GarmentCategory
    status: WardrobeAssetStatus
    import_id: str | None = None
    canonical_garment_id: str | None = None
    # Present only after a garment_metadata reviewer approved the VLM-derived draft.
    semantic_metadata: GarmentMetadataV1 | None = None
    # Present only after reviewer approval; 2D visual cues are not a mesh/fit guarantee.
    structural_profile: GarmentStructuralProfileV1 | None = None
    quality_summary: dict[str, str | float | bool | None] = Field(default_factory=dict)
    render_contract: dict[str, object] = Field(default_factory=dict)
    created_at: datetime
    approved_at: datetime | None = None


class ApproveWardrobeAssetCommandV1(CommandMetaV1):
    approval_note: str | None = Field(default=None, max_length=500)


class CreateStylingSessionCommandV1(CommandMetaV1):
    body_profile_id: str = Field(pattern=r"^body_[a-f0-9]{12}$")
    context: StyleContextV1
    wardrobe_asset_ids: list[str] = Field(default_factory=list, max_length=50)


class StylingSessionV1(BaseModel):
    session_id: str
    owner_id: int
    body_profile_id: str
    status: StylingSessionStatus
    context: StyleContextV1
    wardrobe_snapshot: list[WardrobeAssetRevisionV1] = Field(default_factory=list)
    active_decision_run_id: str | None = None
    selected_outfit_id: str | None = None
    body_contract: ParametricBodyContractV1
    created_at: datetime
    updated_at: datetime


class RunOutfitDecisionCommandV1(CommandMetaV1):
    top_k: int = Field(default=3, ge=1, le=5)


class OutfitDecisionRunV1(BaseModel):
    decision_run_id: str
    session_id: str
    status: Literal["ready", "abstained", "failed"]
    decision: OutfitDecisionResponseV1
    catalog_version: str
    rule_version: str
    created_at: datetime


class SelectOutfitCandidateCommandV1(CommandMetaV1):
    outfit_id: str = Field(min_length=4, max_length=128)


class RequestTryOnCommandV1(CommandMetaV1):
    render_mode: RenderMode = "canonical_proxy"
    preview_outfit_id: str | None = Field(default=None, min_length=4, max_length=128)


class TryOnRunV1(BaseModel):
    try_on_run_id: str
    session_id: str
    decision_run_id: str
    selected_outfit_id: str
    status: TryOnRunStatus
    render_mode: RenderMode
    requested_render_mode: RenderMode = "canonical_proxy"
    quality_status: Literal["approved", "proxy", "pending_review", "rejected", "unavailable"] = "proxy"
    asset_bindings: list[dict[str, object]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class AuditEventV1(BaseModel):
    event_id: str
    aggregate_type: str
    aggregate_id: str
    event_type: str
    actor_id: int | None = None
    correlation_id: str
    payload: dict[str, object]
    created_at: datetime


OutboxEventStatus = Literal["pending", "processing", "published", "retry", "dead_letter"]


class DeadLetterEventV1(BaseModel):
    event_id: str
    dedupe_key: str
    aggregate_type: str
    aggregate_id: str
    event_type: str
    schema_version: str
    payload: dict[str, object]
    correlation_id: str
    status: OutboxEventStatus
    attempt_count: int = Field(ge=0)
    available_at: datetime
    locked_at: datetime | None = None
    locked_by: str | None = None
    published_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime
    reviewed_at: datetime | None = None
    review_note: str | None = None
    reviewer_actor_id: int | None = None


class DeadLetterQueueV1(BaseModel):
    items: list[DeadLetterEventV1]
    total: int = Field(ge=0)


class ReviewDeadLetterCommandV1(CommandMetaV1):
    review_note: str = Field(min_length=5, max_length=1000)


class ReplayDeadLetterCommandV1(CommandMetaV1):
    review_note: str = Field(min_length=5, max_length=1000)


FeedbackSentiment = Literal["like", "dislike", "neutral"]
FeedbackIssueType = Literal["fit", "occasion", "asset", "visual_render", "explanation", "other"]
ReviewTaskStatus = Literal["open", "claimed", "in_review", "approved", "rejected", "rework_required", "expired", "cancelled"]
ReviewTaskType = Literal["garment_metadata", "garment_mesh_quality", "decision_quality", "user_feedback_triage"]
ReviewDecision = Literal["approve", "reject", "rework"]


class WorkflowActorV1(BaseModel):
    actor_id: int
    tenant_id: str | None = None
    roles: list[str] = Field(default_factory=list)
    auth_mode: str


class BodyProfileListV1(BaseModel):
    items: list[BodyProfileRevisionV1]
    next_cursor: str | None = None


class WardrobeAssetListV1(BaseModel):
    items: list[WardrobeAssetRevisionV1]
    next_cursor: str | None = None


class StylingSessionListV1(BaseModel):
    items: list[StylingSessionV1]
    next_cursor: str | None = None


class TryOnAssetBindingV1(BaseModel):
    asset_id: str
    revision_id: str | None = None
    category: str
    render_mode: RenderMode
    asset_uri: str | None = None
    quality_status: Literal["approved", "proxy", "pending_review", "rejected", "unavailable"]
    skeleton_id: str | None = None
    anchors: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class SubmitFeedbackCommandV1(CommandMetaV1):
    decision_run_id: str = Field(pattern=r"^decision_[a-f0-9]{12}$")
    try_on_run_id: str | None = Field(default=None, pattern=r"^tryon_[a-f0-9]{12}$")
    target_outfit_id: str | None = Field(default=None, min_length=4, max_length=128)
    sentiment: FeedbackSentiment
    reason_codes: list[str] = Field(min_length=1, max_length=8)
    issue_type: FeedbackIssueType | None = None
    fit_concern: Literal["too_tight", "too_loose", "proportion", "coverage", "movement", "unknown"] | None = None
    note: str | None = Field(default=None, max_length=1000)
    confidence: int | None = Field(default=None, ge=1, le=5)


class StylingSessionFeedbackV1(BaseModel):
    feedback_id: str
    session_id: str
    decision_run_id: str
    try_on_run_id: str | None = None
    owner_id: int
    target_outfit_id: str | None = None
    sentiment: FeedbackSentiment
    reason_codes: list[str]
    issue_type: FeedbackIssueType | None = None
    fit_concern: str | None = None
    note: str | None = None
    confidence: int | None = None
    created_at: datetime


class FeedbackListV1(BaseModel):
    items: list[StylingSessionFeedbackV1]
    next_cursor: str | None = None


class CreateReviewTaskCommandV1(CommandMetaV1):
    owner_id: int = Field(gt=0)
    subject_type: Literal["GarmentAssetRevision", "OutfitDecisionRun", "StylingSessionFeedback"]
    subject_id: str = Field(min_length=3, max_length=64)
    subject_revision_id: str | None = Field(default=None, max_length=64)
    review_type: ReviewTaskType
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    due_at: datetime | None = None
    evidence_snapshot: dict[str, object] = Field(default_factory=dict)
    checklist_version: str = Field(default="p1-rubric-v1", min_length=3, max_length=64)


class ClaimReviewTaskCommandV1(CommandMetaV1):
    pass


class SubmitReviewDecisionCommandV1(CommandMetaV1):
    decision: ReviewDecision
    reason_codes: list[str] = Field(min_length=1, max_length=8)
    reviewer_note: str = Field(min_length=5, max_length=1500)


class ReleaseReviewTaskCommandV1(CommandMetaV1):
    release_note: str = Field(min_length=5, max_length=1000)


class ReviewTaskV1(BaseModel):
    task_id: str
    tenant_id: str | None = None
    owner_id: int
    subject_type: str
    subject_id: str
    subject_revision_id: str | None = None
    review_type: ReviewTaskType
    priority: str
    status: ReviewTaskStatus
    assignee_actor_id: int | None = None
    due_at: datetime | None = None
    evidence_snapshot: dict[str, object]
    checklist_version: str
    decision: str | None = None
    reason_codes: list[str]
    reviewer_note: str | None = None
    created_at: datetime
    claimed_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime


class ReviewTaskListV1(BaseModel):
    items: list[ReviewTaskV1]
    next_cursor: str | None = None


class EvaluationLabelV1(BaseModel):
    label_id: str
    source_review_task_id: str
    subject_type: str
    subject_id: str
    label_type: str
    label_value: dict[str, object]
    rubric_version: str
    reviewer_actor_id: int
    created_at: datetime


TaxonomyProposalStatus = Literal["proposed", "approved_for_evaluation", "rejected"]
TaxonomyProposalDecision = Literal["approve_for_evaluation", "reject"]


class TaxonomyLearningProposalV1(BaseModel):
    proposal_id: str
    tenant_id: str | None = None
    dimension: Literal["style_occasion_prior", "style_intent_prior"]
    subject_key: str
    status: TaxonomyProposalStatus
    support_count: int = Field(ge=1)
    average_confidence: dict[str, float] = Field(default_factory=dict)
    proposal_payload: dict[str, object]
    source_review_task_ids: list[str]
    generated_at: datetime
    reviewed_at: datetime | None = None
    reviewer_actor_id: int | None = None
    review_note: str | None = None
    updated_at: datetime


class TaxonomyLearningProposalListV1(BaseModel):
    items: list[TaxonomyLearningProposalV1]
    next_cursor: str | None = None


class DecideTaxonomyLearningProposalCommandV1(CommandMetaV1):
    decision: TaxonomyProposalDecision
    review_note: str = Field(min_length=10, max_length=1500)
