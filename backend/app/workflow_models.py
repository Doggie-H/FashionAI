from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BodyProfileRevision(Base):
    __tablename__ = "body_profile_revisions"

    profile_id = Column(String(32), primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    revision = Column(Integer, nullable=False, default=1)
    status = Column(String(32), nullable=False, index=True)
    measurements = Column(JSON, nullable=False)
    body_contract = Column(JSON, nullable=False)
    calibration_version = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    supersedes_profile_id = Column(String(32), nullable=True)


class WardrobeAsset(Base):
    __tablename__ = "workflow_wardrobe_assets"

    asset_id = Column(String(32), primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    category = Column(String(32), nullable=False, index=True)
    active_revision_id = Column(String(40), nullable=True)
    status = Column(String(32), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class GarmentAssetRevision(Base):
    __tablename__ = "garment_asset_revisions"

    revision_id = Column(String(40), primary_key=True)
    asset_id = Column(String(32), ForeignKey("workflow_wardrobe_assets.asset_id"), nullable=False, index=True)
    revision = Column(Integer, nullable=False, default=1)
    status = Column(String(32), nullable=False, index=True)
    import_id = Column(String(32), nullable=True, index=True)
    canonical_garment_id = Column(String(128), nullable=True)
    manifest_snapshot = Column(JSON, nullable=True)
    # Stores reviewer-approved metadata only. Raw VLM output remains in manifest_snapshot for audit.
    semantic_metadata = Column(JSON, nullable=True)
    structural_profile = Column(JSON, nullable=True)
    quality_summary = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    approval_note = Column(Text, nullable=True)

    __table_args__ = (UniqueConstraint("asset_id", "revision", name="uq_garment_asset_revision"),)


class StylingSession(Base):
    __tablename__ = "styling_sessions"

    session_id = Column(String(32), primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    body_profile_id = Column(String(32), ForeignKey("body_profile_revisions.profile_id"), nullable=False, index=True)
    status = Column(String(32), nullable=False, index=True)
    context = Column(JSON, nullable=False)
    body_contract_snapshot = Column(JSON, nullable=False)
    wardrobe_snapshot = Column(JSON, nullable=False, default=list)
    selected_outfit_id = Column(String(128), nullable=True)
    active_decision_run_id = Column(String(40), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class OutfitDecisionRun(Base):
    __tablename__ = "outfit_decision_runs"

    decision_run_id = Column(String(40), primary_key=True)
    session_id = Column(String(32), ForeignKey("styling_sessions.session_id"), nullable=False, index=True)
    status = Column(String(24), nullable=False, index=True)
    catalog_version = Column(String(64), nullable=False)
    rule_version = Column(String(64), nullable=False)
    decision_payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class TryOnRun(Base):
    __tablename__ = "try_on_runs"

    try_on_run_id = Column(String(40), primary_key=True)
    session_id = Column(String(32), ForeignKey("styling_sessions.session_id"), nullable=False, index=True)
    decision_run_id = Column(String(40), ForeignKey("outfit_decision_runs.decision_run_id"), nullable=False, index=True)
    selected_outfit_id = Column(String(128), nullable=False)
    status = Column(String(32), nullable=False, index=True)
    render_mode = Column(String(40), nullable=False)
    limitations = Column(JSON, nullable=False, default=list)
    resolution_payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class StylingSessionFeedback(Base):
    __tablename__ = "styling_session_feedback"

    feedback_id = Column(String(40), primary_key=True)
    session_id = Column(String(32), ForeignKey("styling_sessions.session_id"), nullable=False, index=True)
    decision_run_id = Column(String(40), ForeignKey("outfit_decision_runs.decision_run_id"), nullable=False, index=True)
    try_on_run_id = Column(String(40), ForeignKey("try_on_runs.try_on_run_id"), nullable=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    target_outfit_id = Column(String(128), nullable=True)
    sentiment = Column(String(24), nullable=False)
    reason_codes = Column(JSON, nullable=False, default=list)
    issue_type = Column(String(48), nullable=True)
    fit_concern = Column(String(48), nullable=True)
    note = Column(Text, nullable=True)
    confidence = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class ReviewTask(Base):
    __tablename__ = "workflow_review_tasks"

    task_id = Column(String(40), primary_key=True)
    tenant_id = Column(String(128), nullable=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    subject_type = Column(String(64), nullable=False, index=True)
    subject_id = Column(String(64), nullable=False, index=True)
    subject_revision_id = Column(String(64), nullable=True, index=True)
    review_type = Column(String(48), nullable=False, index=True)
    priority = Column(String(16), nullable=False, default="normal", index=True)
    status = Column(String(24), nullable=False, default="open", index=True)
    assignee_actor_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    due_at = Column(DateTime(timezone=True), nullable=True, index=True)
    evidence_snapshot = Column(JSON, nullable=False, default=dict)
    checklist_version = Column(String(64), nullable=False)
    decision = Column(String(32), nullable=True)
    reason_codes = Column(JSON, nullable=False, default=list)
    reviewer_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    claimed_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class EvaluationLabel(Base):
    __tablename__ = "workflow_evaluation_labels"

    label_id = Column(String(40), primary_key=True)
    source_review_task_id = Column(String(40), ForeignKey("workflow_review_tasks.task_id"), nullable=False, unique=True)
    subject_type = Column(String(64), nullable=False, index=True)
    subject_id = Column(String(64), nullable=False, index=True)
    label_type = Column(String(64), nullable=False, index=True)
    label_value = Column(JSON, nullable=False, default=dict)
    rubric_version = Column(String(64), nullable=False)
    reviewer_actor_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class WorkflowAuditEvent(Base):
    __tablename__ = "workflow_audit_events"

    event_id = Column(String(40), primary_key=True)
    aggregate_type = Column(String(64), nullable=False, index=True)
    aggregate_id = Column(String(40), nullable=False, index=True)
    event_type = Column(String(96), nullable=False, index=True)
    actor_id = Column(Integer, nullable=True, index=True)
    correlation_id = Column(String(128), nullable=False, index=True)
    payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class ProcessedCommand(Base):
    __tablename__ = "processed_workflow_commands"

    command_id = Column(String(40), primary_key=True)
    actor_id = Column(Integer, nullable=False, index=True)
    command_type = Column(String(96), nullable=False)
    idempotency_key = Column(String(128), nullable=False)
    response_payload = Column(JSON, nullable=False)
    correlation_id = Column(String(128), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("actor_id", "command_type", "idempotency_key", name="uq_workflow_command_idempotency"),)


class WorkflowOutboxEvent(Base):
    __tablename__ = "workflow_outbox_events"

    event_id = Column(String(40), primary_key=True)
    dedupe_key = Column(String(192), nullable=False, unique=True, index=True)
    aggregate_type = Column(String(64), nullable=False, index=True)
    aggregate_id = Column(String(40), nullable=False, index=True)
    event_type = Column(String(96), nullable=False, index=True)
    schema_version = Column(String(16), nullable=False, default="1.0")
    payload = Column(JSON, nullable=False)
    correlation_id = Column(String(128), nullable=False, index=True)
    status = Column(String(24), nullable=False, default="pending", index=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    available_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    locked_at = Column(DateTime(timezone=True), nullable=True)
    locked_by = Column(String(128), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_note = Column(Text, nullable=True)
    reviewer_actor_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class ProcessedEventDelivery(Base):
    __tablename__ = "processed_event_deliveries"

    delivery_id = Column(String(40), primary_key=True)
    consumer_name = Column(String(96), nullable=False)
    event_id = Column(String(40), ForeignKey("workflow_outbox_events.event_id"), nullable=False)
    status = Column(String(24), nullable=False, default="processing")
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("consumer_name", "event_id", name="uq_processed_event_delivery"),
    )


class TaxonomyLearningProposal(Base):
    """Append-only learning proposal derived from approved garment metadata reviews.

    It never changes the active catalog by itself. An administrator may only
    approve it for offline evaluation/training-prior review.
    """

    __tablename__ = "taxonomy_learning_proposals"

    proposal_id = Column(String(40), primary_key=True)
    tenant_id = Column(String(128), nullable=True, index=True)
    dimension = Column(String(64), nullable=False, index=True)
    subject_key = Column(String(160), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="proposed", index=True)
    support_count = Column(Integer, nullable=False, default=0)
    average_confidence = Column(JSON, nullable=False, default=dict)
    proposal_payload = Column(JSON, nullable=False, default=dict)
    source_review_task_ids = Column(JSON, nullable=False, default=list)
    generated_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewer_actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    review_note = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("tenant_id", "dimension", "subject_key", name="uq_taxonomy_learning_proposal_key"),)
