from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from . import taxonomy_learning, workflow_service
from ..workflow_models import EvaluationLabel, GarmentAssetRevision, ReviewTask, WardrobeAsset, WorkflowAuditEvent
from ..workflow_schemas import (
    ClaimReviewTaskCommandV1,
    CreateReviewTaskCommandV1,
    ReleaseReviewTaskCommandV1,
    ReviewTaskListV1,
    ReviewTaskV1,
    SubmitReviewDecisionCommandV1,
)


class ReviewTaskNotFoundError(ValueError):
    pass


class ReviewTaskStateError(ValueError):
    pass


REVIEW_TERMINAL_STATUSES = {"approved", "rejected", "rework_required", "expired", "cancelled"}
REVIEW_DECISION_TO_STATUS = {"approve": "approved", "reject": "rejected", "rework": "rework_required"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _identifier(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _response(task: ReviewTask) -> ReviewTaskV1:
    return ReviewTaskV1(
        task_id=task.task_id,
        tenant_id=task.tenant_id,
        owner_id=task.owner_id,
        subject_type=task.subject_type,
        subject_id=task.subject_id,
        subject_revision_id=task.subject_revision_id,
        review_type=task.review_type,
        priority=task.priority,
        status=task.status,
        assignee_actor_id=task.assignee_actor_id,
        due_at=task.due_at,
        evidence_snapshot=task.evidence_snapshot or {},
        checklist_version=task.checklist_version,
        decision=task.decision,
        reason_codes=task.reason_codes or [],
        reviewer_note=task.reviewer_note,
        created_at=task.created_at,
        claimed_at=task.claimed_at,
        completed_at=task.completed_at,
        updated_at=task.updated_at,
    )


def _audit(db: Session, task: ReviewTask, event_type: str, actor_id: int, correlation_id: str, payload: dict[str, object]) -> None:
    db.add(WorkflowAuditEvent(
        event_id=_identifier("evt"),
        aggregate_type="ReviewTask",
        aggregate_id=task.task_id,
        event_type=event_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
        payload=payload,
    ))


def create_review_task(
    db: Session,
    command: CreateReviewTaskCommandV1,
    *,
    tenant_id: str | None,
) -> ReviewTaskV1:
    workflow_service._require_actor(db, command.actor_id)
    workflow_service._require_actor(db, command.owner_id)

    def handler() -> ReviewTaskV1:
        task = ReviewTask(
            task_id=_identifier("review"),
            tenant_id=tenant_id,
            owner_id=command.owner_id,
            subject_type=command.subject_type,
            subject_id=command.subject_id,
            subject_revision_id=command.subject_revision_id,
            review_type=command.review_type,
            priority=command.priority,
            status="open",
            due_at=command.due_at,
            evidence_snapshot=command.evidence_snapshot,
            checklist_version=command.checklist_version,
            reason_codes=[],
        )
        db.add(task)
        db.flush()
        _audit(db, task, "ReviewTaskOpened", command.actor_id, command.correlation_id or task.task_id, {"review_type": task.review_type, "subject_type": task.subject_type, "subject_id": task.subject_id})
        return _response(task)

    return workflow_service._execute_idempotent(
        db, "CreateReviewTask", command.actor_id, command.idempotency_key, command.correlation_id,
        handler, lambda value: value.model_dump(mode="json") if isinstance(value, ReviewTaskV1) else ReviewTaskV1.model_validate(value),
    )


def list_review_tasks(
    db: Session,
    *,
    status: str | None = None,
    review_type: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> ReviewTaskListV1:
    query = db.query(ReviewTask)
    if status:
        query = query.filter(ReviewTask.status == status)
    if review_type:
        query = query.filter(ReviewTask.review_type == review_type)
    if cursor:
        query = query.filter(ReviewTask.task_id > cursor)
    rows = query.order_by(ReviewTask.task_id.asc()).limit(limit + 1).all()
    page = rows[:limit]
    return ReviewTaskListV1(items=[_response(row) for row in page], next_cursor=page[-1].task_id if len(rows) > limit and page else None)


def get_review_task(db: Session, task_id: str) -> ReviewTaskV1:
    task = db.get(ReviewTask, task_id)
    if task is None:
        raise ReviewTaskNotFoundError("Review task was not found")
    return _response(task)


def claim_review_task(db: Session, task_id: str, command: ClaimReviewTaskCommandV1) -> ReviewTaskV1:
    workflow_service._require_actor(db, command.actor_id)

    def handler() -> ReviewTaskV1:
        now = _now()
        claimed = db.query(ReviewTask).filter(
            ReviewTask.task_id == task_id,
            ReviewTask.status == "open",
            ReviewTask.assignee_actor_id.is_(None),
        ).update({"status": "claimed", "assignee_actor_id": command.actor_id, "claimed_at": now, "updated_at": now}, synchronize_session=False)
        if claimed != 1:
            task = db.get(ReviewTask, task_id)
            if task is None:
                raise ReviewTaskNotFoundError("Review task was not found")
            raise ReviewTaskStateError("Review task is no longer available to claim")
        db.expire_all()
        task = db.get(ReviewTask, task_id)
        assert task is not None
        _audit(db, task, "ReviewTaskClaimed", command.actor_id, command.correlation_id or task.task_id, {"assignee_actor_id": command.actor_id})
        db.flush()
        return _response(task)

    return workflow_service._execute_idempotent(
        db, "ClaimReviewTask", command.actor_id, command.idempotency_key, command.correlation_id,
        handler, lambda value: value.model_dump(mode="json") if isinstance(value, ReviewTaskV1) else ReviewTaskV1.model_validate(value),
    )


def _apply_garment_review_side_effect(db: Session, task: ReviewTask, decision: str) -> None:
    if task.review_type != "garment_metadata":
        return
    revision = db.get(GarmentAssetRevision, task.subject_revision_id) if task.subject_revision_id else None
    if revision is None:
        raise ReviewTaskStateError("Garment review task is missing a valid asset revision")
    asset = db.get(WardrobeAsset, revision.asset_id)
    if asset is None:
        raise ReviewTaskStateError("Garment review task is missing a wardrobe asset")
    if decision == "approve":
        if revision.status not in {"normalized", "pending_review"}:
            raise ReviewTaskStateError("Garment revision cannot be approved from its current lifecycle status")
        reconstruction = (revision.manifest_snapshot or {}).get("reconstruction", {})
        if reconstruction.get("pipeline_state") == "failed":
            raise ReviewTaskStateError("Failed reconstruction cannot be approved into the active wardrobe")
        approved_semantics = workflow_service._approve_semantic_metadata(revision, asset)
        approved_structure = workflow_service._approve_structural_profile(revision)
        revision.status = "active"
        revision.approved_at = _now()
        revision.quality_summary = {
            **(revision.quality_summary or {}),
            "eligible_for_decision": True,
            "approval": "review_task",
            "semantic_metadata_status": "approved" if approved_semantics else "not_available",
            "structural_profile_status": "approved_2d_cues" if approved_structure else "not_available",
            "structural_profile_mesh_evidence": False,
        }
        asset.status = "active"
        asset.active_revision_id = revision.revision_id
    elif decision == "reject":
        revision.status = "rejected"
        asset.status = "rejected"
        if asset.active_revision_id == revision.revision_id:
            asset.active_revision_id = None
    else:
        revision.status = "pending_review"
        asset.status = "pending_review"
    asset.updated_at = _now()


def submit_review_decision(
    db: Session,
    task_id: str,
    command: SubmitReviewDecisionCommandV1,
    *,
    is_admin: bool,
) -> ReviewTaskV1:
    workflow_service._require_actor(db, command.actor_id)

    def handler() -> ReviewTaskV1:
        task = db.get(ReviewTask, task_id)
        if task is None:
            raise ReviewTaskNotFoundError("Review task was not found")
        if task.status in REVIEW_TERMINAL_STATUSES:
            raise ReviewTaskStateError("Completed review task cannot receive another decision")
        if task.assignee_actor_id is None:
            raise ReviewTaskStateError("Review task must be claimed before a decision")
        if task.assignee_actor_id != command.actor_id and not is_admin:
            raise ReviewTaskStateError("Only the assignee or admin can submit the review decision")
        now = _now()
        task.status = REVIEW_DECISION_TO_STATUS[command.decision]
        task.decision = command.decision
        task.reason_codes = command.reason_codes
        task.reviewer_note = command.reviewer_note
        task.completed_at = now
        task.updated_at = now
        _apply_garment_review_side_effect(db, task, command.decision)
        _audit(db, task, "ReviewTaskDecisionSubmitted", command.actor_id, command.correlation_id or task.task_id, {"decision": command.decision, "reason_codes": command.reason_codes})
        if task.review_type == "garment_metadata" and command.decision == "approve":
            taxonomy_learning.derive_proposals_from_approved_garment_review(
                db,
                review_task_id=task.task_id,
                tenant_id=task.tenant_id,
                actor_id=command.actor_id,
                correlation_id=command.correlation_id or task.task_id,
            )
        if task.review_type in {"decision_quality", "user_feedback_triage"}:
            db.add(EvaluationLabel(
                label_id=_identifier("eval"),
                source_review_task_id=task.task_id,
                subject_type=task.subject_type,
                subject_id=task.subject_id,
                label_type=task.review_type,
                label_value={"decision": command.decision, "reason_codes": command.reason_codes, "reviewer_note": command.reviewer_note},
                rubric_version=task.checklist_version,
                reviewer_actor_id=command.actor_id,
            ))
        db.flush()
        return _response(task)

    return workflow_service._execute_idempotent(
        db, "SubmitReviewTaskDecision", command.actor_id, command.idempotency_key, command.correlation_id,
        handler, lambda value: value.model_dump(mode="json") if isinstance(value, ReviewTaskV1) else ReviewTaskV1.model_validate(value),
    )


def release_review_task(
    db: Session,
    task_id: str,
    command: ReleaseReviewTaskCommandV1,
    *,
    is_admin: bool,
) -> ReviewTaskV1:
    workflow_service._require_actor(db, command.actor_id)

    def handler() -> ReviewTaskV1:
        task = db.get(ReviewTask, task_id)
        if task is None:
            raise ReviewTaskNotFoundError("Review task was not found")
        if task.status in REVIEW_TERMINAL_STATUSES:
            raise ReviewTaskStateError("Completed review task cannot be released")
        if task.assignee_actor_id != command.actor_id and not is_admin:
            raise ReviewTaskStateError("Only the assignee or admin can release the review task")
        task.status = "open"
        task.assignee_actor_id = None
        task.claimed_at = None
        task.updated_at = _now()
        _audit(db, task, "ReviewTaskReleased", command.actor_id, command.correlation_id or task.task_id, {"release_note": command.release_note})
        db.flush()
        return _response(task)

    return workflow_service._execute_idempotent(
        db, "ReleaseReviewTask", command.actor_id, command.idempotency_key, command.correlation_id,
        handler, lambda value: value.model_dump(mode="json") if isinstance(value, ReviewTaskV1) else ReviewTaskV1.model_validate(value),
    )


def list_review_task_audit_events(db: Session, task_id: str):
    if db.get(ReviewTask, task_id) is None:
        raise ReviewTaskNotFoundError("Review task was not found")
    return db.query(WorkflowAuditEvent).filter(
        WorkflowAuditEvent.aggregate_type == "ReviewTask",
        WorkflowAuditEvent.aggregate_id == task_id,
    ).order_by(WorkflowAuditEvent.created_at.asc()).all()
