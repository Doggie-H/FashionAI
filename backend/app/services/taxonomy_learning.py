"""Governed taxonomy-learning proposals from approved garment metadata reviews.

The service learns *candidate priors* for evaluation only. It intentionally does
not edit canonical_garments_v1.json, change ranker weights, or trigger model
fine-tuning. Those actions require separate frozen-holdout evaluation and a
human release decision.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable
from uuid import uuid4

from sqlalchemy.orm import Session

from ..workflow_models import GarmentAssetRevision, TaxonomyLearningProposal, WorkflowAuditEvent
from ..workflow_schemas import (
    DecideTaxonomyLearningProposalCommandV1,
    TaxonomyLearningProposalListV1,
    TaxonomyLearningProposalV1,
)
from . import workflow_service


class TaxonomyLearningProposalNotFoundError(ValueError):
    pass


class TaxonomyLearningProposalStateError(ValueError):
    pass


MIN_SUPPORT_FOR_EVALUATION = 3


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _identifier(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _response(record: TaxonomyLearningProposal) -> TaxonomyLearningProposalV1:
    return TaxonomyLearningProposalV1(
        proposal_id=record.proposal_id,
        tenant_id=record.tenant_id,
        dimension=record.dimension,
        subject_key=record.subject_key,
        status=record.status,
        support_count=record.support_count,
        average_confidence=record.average_confidence or {},
        proposal_payload=record.proposal_payload or {},
        source_review_task_ids=record.source_review_task_ids or [],
        generated_at=record.generated_at,
        reviewed_at=record.reviewed_at,
        reviewer_actor_id=record.reviewer_actor_id,
        review_note=record.review_note,
        updated_at=record.updated_at,
    )


def _audit(db: Session, record: TaxonomyLearningProposal, event_type: str, actor_id: int | None, correlation_id: str, payload: dict[str, object]) -> None:
    db.add(WorkflowAuditEvent(
        event_id=_identifier("evt"),
        aggregate_type="TaxonomyLearningProposal",
        aggregate_id=record.proposal_id,
        event_type=event_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
        payload=payload,
    ))


def _confidence_map(revision: GarmentAssetRevision) -> dict[str, float]:
    manifest = revision.manifest_snapshot or {}
    tagging = (manifest.get("analysis") or {}).get("semantic_tagging") if isinstance(manifest, dict) else None
    evidence = tagging.get("evidence", []) if isinstance(tagging, dict) else []
    result: dict[str, float] = {}
    if not isinstance(evidence, list):
        return result
    for item in evidence:
        if not isinstance(item, dict):
            continue
        dimension = item.get("dimension")
        confidence = item.get("confidence")
        if isinstance(dimension, str) and isinstance(confidence, (int, float)) and 0 <= float(confidence) <= 1:
            result[dimension] = float(confidence)
    return result


def _pairs(values_a: Iterable[str], values_b: Iterable[str]) -> list[tuple[str, str]]:
    return [(first, second) for first in values_a for second in values_b if first and second]


def _upsert_prior(
    db: Session,
    *,
    tenant_id: str | None,
    dimension: str,
    first: str,
    second: str,
    task_id: str,
    confidence: dict[str, float],
) -> TaxonomyLearningProposal:
    subject_key = f"{first}|{second}"
    record = db.query(TaxonomyLearningProposal).filter(
        TaxonomyLearningProposal.tenant_id == tenant_id,
        TaxonomyLearningProposal.dimension == dimension,
        TaxonomyLearningProposal.subject_key == subject_key,
    ).first()
    if record is None:
        record = TaxonomyLearningProposal(
            proposal_id=_identifier("taxprop"),
            tenant_id=tenant_id,
            dimension=dimension,
            subject_key=subject_key,
            status="proposed",
            support_count=1,
            average_confidence=confidence,
            proposal_payload={
                "kind": "taxonomy_prior_candidate",
                "first_tag": first,
                "second_tag": second,
                "catalog_mutation": False,
                "ranker_mutation": False,
                "release_preconditions": [
                    f"support_count >= {MIN_SUPPORT_FOR_EVALUATION}",
                    "independent reviewer verification",
                    "frozen holdout evaluation",
                    "admin release approval outside this proposal record",
                ],
            },
            source_review_task_ids=[task_id],
        )
        db.add(record)
        return record

    task_ids = list(record.source_review_task_ids or [])
    if task_id in task_ids:
        return record
    previous_count = record.support_count
    record.support_count = previous_count + 1
    current = record.average_confidence or {}
    record.average_confidence = {
        key: round(((float(current.get(key, 0.0)) * previous_count) + value) / record.support_count, 4)
        for key, value in {**current, **confidence}.items()
    }
    record.source_review_task_ids = [*task_ids, task_id]
    record.updated_at = _now()
    # Re-open a previously rejected candidate only through a new manual proposal, never silently.
    return record


def derive_proposals_from_approved_garment_review(
    db: Session,
    *,
    review_task_id: str,
    tenant_id: str | None,
    actor_id: int,
    correlation_id: str,
) -> list[TaxonomyLearningProposal]:
    """Derive deterministic proposal records after an approved semantic garment review."""
    from ..workflow_models import ReviewTask

    task = db.get(ReviewTask, review_task_id)
    if task is None or task.review_type != "garment_metadata" or task.decision != "approve":
        return []
    revision = db.get(GarmentAssetRevision, task.subject_revision_id) if task.subject_revision_id else None
    if revision is None or not isinstance(revision.semantic_metadata, dict):
        return []
    metadata = revision.semantic_metadata
    styles = [item for item in metadata.get("styles", []) if isinstance(item, str)]
    occasions = [item for item in metadata.get("occasions", []) if isinstance(item, str)]
    intents = [item for item in metadata.get("intent_support", []) if isinstance(item, str)]
    confidences = _confidence_map(revision)
    generated: list[TaxonomyLearningProposal] = []
    for style, occasion in _pairs(styles, occasions):
        generated.append(_upsert_prior(
            db,
            tenant_id=tenant_id,
            dimension="style_occasion_prior",
            first=style,
            second=occasion,
            task_id=task.task_id,
            confidence={key: value for key, value in confidences.items() if key in {"styles", "occasions"}},
        ))
    for style, intent in _pairs(styles, intents):
        generated.append(_upsert_prior(
            db,
            tenant_id=tenant_id,
            dimension="style_intent_prior",
            first=style,
            second=intent,
            task_id=task.task_id,
            confidence={key: value for key, value in confidences.items() if key in {"styles", "intent_support"}},
        ))
    for record in generated:
        _audit(
            db,
            record,
            "TaxonomyLearningProposalDerived",
            actor_id,
            correlation_id,
            {"source_review_task_id": task.task_id, "support_count": record.support_count, "catalog_mutation": False},
        )
    return generated


def list_proposals(
    db: Session,
    *,
    status: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> TaxonomyLearningProposalListV1:
    query = db.query(TaxonomyLearningProposal)
    if status:
        query = query.filter(TaxonomyLearningProposal.status == status)
    if cursor:
        query = query.filter(TaxonomyLearningProposal.proposal_id > cursor)
    rows = query.order_by(TaxonomyLearningProposal.proposal_id.asc()).limit(limit + 1).all()
    page = rows[:limit]
    return TaxonomyLearningProposalListV1(
        items=[_response(record) for record in page],
        next_cursor=page[-1].proposal_id if len(rows) > limit and page else None,
    )


def decide_proposal(
    db: Session,
    proposal_id: str,
    command: DecideTaxonomyLearningProposalCommandV1,
) -> TaxonomyLearningProposalV1:
    workflow_service._require_actor(db, command.actor_id)

    def handler() -> TaxonomyLearningProposalV1:
        record = db.get(TaxonomyLearningProposal, proposal_id)
        if record is None:
            raise TaxonomyLearningProposalNotFoundError("Taxonomy learning proposal was not found")
        if record.status != "proposed":
            raise TaxonomyLearningProposalStateError("Only a proposed taxonomy learning record can be decided")
        if command.decision == "approve_for_evaluation" and record.support_count < MIN_SUPPORT_FOR_EVALUATION:
            raise TaxonomyLearningProposalStateError(
                f"Proposal requires at least {MIN_SUPPORT_FOR_EVALUATION} independent approved review sources before evaluation approval"
            )
        record.status = "approved_for_evaluation" if command.decision == "approve_for_evaluation" else "rejected"
        record.reviewed_at = _now()
        record.reviewer_actor_id = command.actor_id
        record.review_note = command.review_note
        record.updated_at = _now()
        _audit(
            db,
            record,
            "TaxonomyLearningProposalDecided",
            command.actor_id,
            command.correlation_id or record.proposal_id,
            {"decision": command.decision, "support_count": record.support_count, "catalog_mutation": False},
        )
        db.flush()
        return _response(record)

    return workflow_service._execute_idempotent(
        db,
        "DecideTaxonomyLearningProposal",
        command.actor_id,
        command.idempotency_key,
        command.correlation_id,
        handler,
        lambda value: value.model_dump(mode="json") if isinstance(value, TaxonomyLearningProposalV1) else TaxonomyLearningProposalV1.model_validate(value),
    )
