from __future__ import annotations

import os
from copy import deepcopy
from datetime import datetime, timezone
from typing import Callable, TypeVar
from uuid import uuid4

from sqlalchemy.orm import Session

from .. import models
from ..phase_a_schemas import GarmentMetadataV1, OutfitDecisionRequestV1, OutfitDecisionResponseV1
from ..phase_b_schemas import GarmentStructuralProfileV1
from ..services.body_contract import build_parametric_body_contract
from ..services.garment_import import read_manifest, write_manifest
from ..services.outfit_decision_engine import decide_outfits
from ..services.try_on_resolver import resolve_try_on_assets
from ..services.workflow_outbox import (
    OUTBOX_EVENT_STYLING_SESSION_OPENED,
    OUTBOX_EVENT_STYLING_SESSION_FEEDBACK_RECORDED,
    OUTBOX_EVENT_TRY_ON_REQUESTED,
    RedisIdempotencyGuard,
    execute_idempotent_with_outbox,
)
from ..workflow_models import (
    BodyProfileRevision,
    GarmentAssetRevision,
    OutfitDecisionRun,
    ProcessedCommand,
    ReviewTask,
    StylingSession,
    StylingSessionFeedback,
    TryOnRun,
    WardrobeAsset,
    WorkflowAuditEvent,
)
from ..workflow_schemas import (
    ApproveWardrobeAssetCommandV1,
    AuditEventV1,
    BodyProfileRevisionV1,
    ConfirmBodyProfileCommandV1,
    CreateBodyProfileCommandV1,
    CreateStylingSessionCommandV1,
    CreateWardrobeAssetCommandV1,
    OutfitDecisionRunV1,
    RequestTryOnCommandV1,
    RunOutfitDecisionCommandV1,
    SelectOutfitCandidateCommandV1,
    StylingSessionV1,
    StylingSessionFeedbackV1,
    SubmitFeedbackCommandV1,
    TryOnRunV1,
    WardrobeAssetRevisionV1,
    BodyProfileListV1,
    WardrobeAssetListV1,
    StylingSessionListV1,
    FeedbackListV1,
)


RULE_VERSION = "outfit-decision-engine-v1"
CATALOG_VERSION = "1.0.0-seed"
T = TypeVar("T")


class WorkflowStateError(ValueError):
    pass


class WorkflowNotFoundError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _identifier(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _require_actor(db: Session, actor_id: int) -> None:
    if db.query(models.User).filter(models.User.id == actor_id).first() is None:
        raise WorkflowNotFoundError("Workflow actor does not exist")


def _audit(db: Session, aggregate_type: str, aggregate_id: str, event_type: str, actor_id: int | None, correlation_id: str, payload: dict[str, object]) -> None:
    db.add(WorkflowAuditEvent(
        event_id=_identifier("evt"),
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        event_type=event_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
        payload=payload,
    ))


def _execute_idempotent(db: Session, command_type: str, actor_id: int, idempotency_key: str, correlation_id: str | None, handler: Callable[[], T], serializer: Callable[[T], dict[str, object]]) -> T:
    existing = db.query(ProcessedCommand).filter(
        ProcessedCommand.actor_id == actor_id,
        ProcessedCommand.command_type == command_type,
        ProcessedCommand.idempotency_key == idempotency_key,
    ).first()
    if existing is not None:
        return serializer(existing.response_payload)  # type: ignore[arg-type]

    result = handler()
    payload = serializer(result)
    db.add(ProcessedCommand(
        command_id=_identifier("cmd"),
        actor_id=actor_id,
        command_type=command_type,
        idempotency_key=idempotency_key,
        response_payload=payload,
        correlation_id=correlation_id or _identifier("corr"),
    ))
    db.commit()
    return result


def _body_response(record: BodyProfileRevision) -> BodyProfileRevisionV1:
    return BodyProfileRevisionV1(
        profile_id=record.profile_id,
        owner_id=record.owner_id,
        revision=record.revision,
        status=record.status,
        contract=record.body_contract,
        created_at=record.created_at,
        confirmed_at=record.confirmed_at,
    )


def _approve_semantic_metadata(revision: GarmentAssetRevision, asset: WardrobeAsset) -> GarmentMetadataV1 | None:
    """Promote a reviewed VLM draft to the revision snapshot; never promote raw data implicitly."""
    manifest_data = deepcopy(revision.manifest_snapshot or {})
    tag_data = (manifest_data.get("analysis") or {}).get("semantic_tagging") if isinstance(manifest_data, dict) else None
    if not isinstance(tag_data, dict) or tag_data.get("status") not in {"needs_review", "approved"}:
        return None
    candidate = tag_data.get("candidate_metadata")
    if not isinstance(candidate, dict):
        return None
    metadata = GarmentMetadataV1.model_validate(candidate)
    if metadata.category != asset.category:
        raise WorkflowStateError("Reviewed semantic category does not match the wardrobe asset category")
    revision.semantic_metadata = metadata.model_dump(mode="json")
    tag_data["status"] = "approved"
    # Reassign JSON so SQLAlchemy persists the nested status transition.
    revision.manifest_snapshot = manifest_data
    if revision.import_id:
        source_manifest = read_manifest(revision.import_id)
        if source_manifest and source_manifest.analysis.semantic_tagging:
            source_manifest.analysis.semantic_tagging.status = "approved"
            write_manifest(source_manifest)
    return metadata


def _approve_structural_profile(revision: GarmentAssetRevision) -> GarmentStructuralProfileV1 | None:
    """Promote reviewer-approved 2D structural cues without treating them as mesh evidence."""
    manifest_data = deepcopy(revision.manifest_snapshot or {})
    tag_data = (manifest_data.get("analysis") or {}).get("semantic_tagging") if isinstance(manifest_data, dict) else None
    if not isinstance(tag_data, dict) or tag_data.get("status") not in {"needs_review", "approved"}:
        return None
    candidate = tag_data.get("structural_profile")
    if not isinstance(candidate, dict):
        return None
    profile = GarmentStructuralProfileV1.model_validate(candidate)
    revision.structural_profile = profile.model_dump(mode="json")
    tag_data["status"] = "approved"
    revision.manifest_snapshot = manifest_data
    if revision.import_id:
        source_manifest = read_manifest(revision.import_id)
        if source_manifest and source_manifest.analysis.semantic_tagging:
            source_manifest.analysis.semantic_tagging.status = "approved"
            write_manifest(source_manifest)
    return profile


def _asset_response(asset: WardrobeAsset, revision: GarmentAssetRevision) -> WardrobeAssetRevisionV1:
    manifest = revision.manifest_snapshot or {}
    render_contract = {
        "rig_status": manifest.get("rig_status"),
        "target_skeleton_id": manifest.get("target_skeleton_id"),
        "rest_pose": manifest.get("rest_pose"),
        "generated_asset_uri": manifest.get("generated_asset_uri"),
        "quality_gate": manifest.get("quality_gate"),
        "anchors": manifest.get("anchors", []),
    } if manifest else {}
    return WardrobeAssetRevisionV1(
        asset_id=asset.asset_id,
        revision_id=revision.revision_id,
        owner_id=asset.owner_id,
        name=asset.name,
        category=asset.category,
        status=revision.status,
        import_id=revision.import_id,
        canonical_garment_id=revision.canonical_garment_id,
        semantic_metadata=revision.semantic_metadata,
        structural_profile=revision.structural_profile,
        quality_summary=revision.quality_summary or {},
        render_contract=render_contract,
        created_at=revision.created_at,
        approved_at=revision.approved_at,
    )


def _session_response(session: StylingSession) -> StylingSessionV1:
    return StylingSessionV1(
        session_id=session.session_id,
        owner_id=session.owner_id,
        body_profile_id=session.body_profile_id,
        status=session.status,
        context=session.context,
        wardrobe_snapshot=session.wardrobe_snapshot or [],
        active_decision_run_id=session.active_decision_run_id,
        selected_outfit_id=session.selected_outfit_id,
        body_contract=session.body_contract_snapshot,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def _decision_response(record: OutfitDecisionRun) -> OutfitDecisionRunV1:
    return OutfitDecisionRunV1(
        decision_run_id=record.decision_run_id,
        session_id=record.session_id,
        status=record.status,
        decision=record.decision_payload,
        catalog_version=record.catalog_version,
        rule_version=record.rule_version,
        created_at=record.created_at,
    )


def _try_on_response(record: TryOnRun) -> TryOnRunV1:
    resolution = record.resolution_payload or {}
    return TryOnRunV1(
        try_on_run_id=record.try_on_run_id,
        session_id=record.session_id,
        decision_run_id=record.decision_run_id,
        selected_outfit_id=record.selected_outfit_id,
        status=record.status,
        render_mode=record.render_mode,
        requested_render_mode=resolution.get("requested_render_mode", record.render_mode),
        quality_status=resolution.get("quality_status", "proxy"),
        asset_bindings=resolution.get("asset_bindings", []),
        limitations=record.limitations or [],
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def create_body_profile(db: Session, command: CreateBodyProfileCommandV1) -> BodyProfileRevisionV1:
    _require_actor(db, command.actor_id)

    def handler() -> BodyProfileRevisionV1:
        contract = build_parametric_body_contract(command.measurements)
        profile = BodyProfileRevision(
            profile_id=_identifier("body"),
            owner_id=command.actor_id,
            revision=1,
            status="calibrated",
            measurements=command.measurements.model_dump(mode="json"),
            body_contract=contract.model_dump(mode="json"),
            calibration_version=contract.calibration_version,
        )
        db.add(profile)
        db.flush()
        _audit(db, "BodyProfile", profile.profile_id, "BodyProfileCalibrated", command.actor_id, command.correlation_id or profile.profile_id, {"revision": 1, "calibration_version": contract.calibration_version})
        return _body_response(profile)

    return _execute_idempotent(
        db, "CreateBodyProfile", command.actor_id, command.idempotency_key, command.correlation_id,
        handler, lambda value: value.model_dump(mode="json") if isinstance(value, BodyProfileRevisionV1) else BodyProfileRevisionV1.model_validate(value),
    )


def confirm_body_profile(db: Session, profile_id: str, command: ConfirmBodyProfileCommandV1) -> BodyProfileRevisionV1:
    _require_actor(db, command.actor_id)

    def handler() -> BodyProfileRevisionV1:
        profile = db.query(BodyProfileRevision).filter(BodyProfileRevision.profile_id == profile_id, BodyProfileRevision.owner_id == command.actor_id).first()
        if profile is None:
            raise WorkflowNotFoundError("Body profile was not found for this actor")
        if profile.status != "calibrated":
            raise WorkflowStateError(f"Body profile cannot be confirmed from status {profile.status}")
        db.query(BodyProfileRevision).filter(
            BodyProfileRevision.owner_id == command.actor_id,
            BodyProfileRevision.status == "active",
        ).update({"status": "superseded"})
        profile.status = "active"
        profile.confirmed_at = _now()
        db.flush()
        _audit(db, "BodyProfile", profile.profile_id, "BodyProfileActivated", command.actor_id, command.correlation_id or profile.profile_id, {"confirmation_note": command.confirmation_note})
        return _body_response(profile)

    return _execute_idempotent(
        db, "ConfirmBodyProfile", command.actor_id, command.idempotency_key, command.correlation_id,
        handler, lambda value: value.model_dump(mode="json") if isinstance(value, BodyProfileRevisionV1) else BodyProfileRevisionV1.model_validate(value),
    )


def create_wardrobe_asset(db: Session, command: CreateWardrobeAssetCommandV1) -> WardrobeAssetRevisionV1:
    _require_actor(db, command.actor_id)

    def handler() -> WardrobeAssetRevisionV1:
        manifest_snapshot = None
        quality_summary: dict[str, str | float | bool | None] = {"source": "canonical_metadata", "eligible_for_decision": False}
        revision_status = "normalized"
        canonical_garment_id = command.canonical_garment_id
        if command.import_id:
            manifest = read_manifest(command.import_id)
            if manifest is None:
                raise WorkflowNotFoundError("Garment import manifest was not found")
            if manifest.analysis.category != command.category:
                raise WorkflowStateError("Garment import category does not match requested wardrobe category")
            manifest_snapshot = manifest.model_dump(mode="json")
            canonical_garment_id = canonical_garment_id or manifest.selected_garment_id
            revision_status = "pending_review" if manifest.analysis.needs_human_review else "normalized"
            semantic_tagging = manifest.analysis.semantic_tagging
            quality_summary = {
                "source": "garment_import_manifest",
                "segmentation_quality": manifest.segmentation.quality if manifest.segmentation else None,
                "rig_status": manifest.rig_status,
                "semantic_tagging_status": semantic_tagging.status if semantic_tagging else "not_requested",
                "semantic_provider": semantic_tagging.provider if semantic_tagging else None,
                "eligible_for_decision": False,
            }
        asset = WardrobeAsset(
            asset_id=_identifier("wad"),
            owner_id=command.actor_id,
            name=command.name,
            category=command.category,
            status=revision_status,
        )
        revision = GarmentAssetRevision(
            revision_id=_identifier("garrev"),
            asset_id=asset.asset_id,
            revision=1,
            status=revision_status,
            import_id=command.import_id,
            canonical_garment_id=canonical_garment_id,
            manifest_snapshot=manifest_snapshot,
            semantic_metadata=None,
            quality_summary=quality_summary,
        )
        db.add_all([asset, revision])
        db.flush()
        _audit(db, "WardrobeAsset", asset.asset_id, "WardrobeAssetNormalized", command.actor_id, command.correlation_id or asset.asset_id, {"revision_id": revision.revision_id, "status": revision_status, "import_id": command.import_id})
        if revision_status == "pending_review":
            review_task = ReviewTask(
                task_id=_identifier("review"),
                owner_id=command.actor_id,
                subject_type="GarmentAssetRevision",
                subject_id=asset.asset_id,
                subject_revision_id=revision.revision_id,
                review_type="garment_metadata",
                priority="normal",
                status="open",
                evidence_snapshot={"asset": _asset_response(asset, revision).model_dump(mode="json"), "manifest": manifest_snapshot or {}},
                checklist_version="p1-garment-metadata-v1",
                reason_codes=[],
            )
            db.add(review_task)
            _audit(db, "ReviewTask", review_task.task_id, "ReviewTaskOpened", command.actor_id, command.correlation_id or asset.asset_id, {"review_type": "garment_metadata", "asset_id": asset.asset_id, "revision_id": revision.revision_id})
        return _asset_response(asset, revision)

    return _execute_idempotent(
        db, "CreateWardrobeAsset", command.actor_id, command.idempotency_key, command.correlation_id,
        handler, lambda value: value.model_dump(mode="json") if isinstance(value, WardrobeAssetRevisionV1) else WardrobeAssetRevisionV1.model_validate(value),
    )


def approve_wardrobe_asset(db: Session, asset_id: str, command: ApproveWardrobeAssetCommandV1) -> WardrobeAssetRevisionV1:
    _require_actor(db, command.actor_id)

    def handler() -> WardrobeAssetRevisionV1:
        asset = db.query(WardrobeAsset).filter(WardrobeAsset.asset_id == asset_id, WardrobeAsset.owner_id == command.actor_id).first()
        if asset is None:
            raise WorkflowNotFoundError("Wardrobe asset was not found for this actor")
        revision = db.query(GarmentAssetRevision).filter(GarmentAssetRevision.asset_id == asset_id).order_by(GarmentAssetRevision.revision.desc()).first()
        if revision is None:
            raise WorkflowStateError("Wardrobe asset has no revision")
        if revision.status not in {"normalized", "pending_review"}:
            raise WorkflowStateError(f"Wardrobe asset cannot be approved from status {revision.status}")
        if revision.import_id and revision.manifest_snapshot and revision.manifest_snapshot.get("reconstruction", {}).get("pipeline_state") == "failed":
            raise WorkflowStateError("A failed reconstruction asset cannot be activated")
        approved_semantics = _approve_semantic_metadata(revision, asset)
        revision.status = "active"
        revision.approved_at = _now()
        revision.approval_note = command.approval_note
        revision.quality_summary = {
            **(revision.quality_summary or {}),
            "eligible_for_decision": True,
            "approval": "human_confirmed",
            "semantic_metadata_status": "approved" if approved_semantics else "not_available",
        }
        asset.status = "active"
        asset.active_revision_id = revision.revision_id
        asset.updated_at = _now()
        db.flush()
        _audit(db, "WardrobeAsset", asset.asset_id, "WardrobeAssetActivated", command.actor_id, command.correlation_id or asset.asset_id, {"revision_id": revision.revision_id})
        return _asset_response(asset, revision)

    return _execute_idempotent(
        db, "ApproveWardrobeAsset", command.actor_id, command.idempotency_key, command.correlation_id,
        handler, lambda value: value.model_dump(mode="json") if isinstance(value, WardrobeAssetRevisionV1) else WardrobeAssetRevisionV1.model_validate(value),
    )


def _workflow_outbox_enabled() -> bool:
    return os.getenv("WORKFLOW_OUTBOX_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}


def create_styling_session(db: Session, command: CreateStylingSessionCommandV1) -> StylingSessionV1:
    _require_actor(db, command.actor_id)

    def handler() -> StylingSessionV1:
        body = db.query(BodyProfileRevision).filter(
            BodyProfileRevision.profile_id == command.body_profile_id,
            BodyProfileRevision.owner_id == command.actor_id,
        ).first()
        if body is None:
            raise WorkflowNotFoundError("Body profile was not found for this actor")
        if body.status != "active":
            raise WorkflowStateError("Styling sessions require an active body profile")
        asset_query = db.query(WardrobeAsset).filter(WardrobeAsset.owner_id == command.actor_id, WardrobeAsset.status == "active")
        if command.wardrobe_asset_ids:
            asset_query = asset_query.filter(WardrobeAsset.asset_id.in_(command.wardrobe_asset_ids))
        assets = asset_query.all()
        if command.wardrobe_asset_ids and len(assets) != len(set(command.wardrobe_asset_ids)):
            raise WorkflowStateError("Every requested wardrobe asset must be active and owned by the actor")
        snapshot: list[dict[str, object]] = []
        for asset in assets:
            revision = db.query(GarmentAssetRevision).filter(GarmentAssetRevision.revision_id == asset.active_revision_id).first()
            if revision is None or revision.status != "active":
                raise WorkflowStateError("Wardrobe asset active revision is invalid")
            snapshot.append(_asset_response(asset, revision).model_dump(mode="json"))
        session = StylingSession(
            session_id=_identifier("style"),
            owner_id=command.actor_id,
            body_profile_id=body.profile_id,
            status="inputs_resolved",
            context=command.context.model_dump(mode="json"),
            body_contract_snapshot=body.body_contract,
            wardrobe_snapshot=snapshot,
        )
        db.add(session)
        db.flush()
        _audit(db, "StylingSession", session.session_id, "StylingSessionInputsResolved", command.actor_id, command.correlation_id or session.session_id, {"body_profile_id": body.profile_id, "wardrobe_asset_count": len(snapshot)})
        return _session_response(session)

    serializer = lambda value: value.model_dump(mode="json") if isinstance(value, StylingSessionV1) else StylingSessionV1.model_validate(value)
    if _workflow_outbox_enabled():
        def outbox_handler(correlation_id: str, command_id: str):
            command.correlation_id = correlation_id
            result = handler()
            return result, [{
                "event_type": OUTBOX_EVENT_STYLING_SESSION_OPENED,
                "aggregate_type": "StylingSession",
                "aggregate_id": result.session_id,
                "payload": {
                    "session_id": result.session_id,
                    "owner_id": result.owner_id,
                    "body_profile_id": result.body_profile_id,
                    "command_id": command_id,
                    "correlation_id": correlation_id,
                },
            }]
        return execute_idempotent_with_outbox(
            db,
            actor_id=command.actor_id,
            command_type="CreateStylingSession",
            idempotency_key=command.idempotency_key,
            request_payload=command.model_dump(mode="json"),
            correlation_id=command.correlation_id,
            guard=RedisIdempotencyGuard.from_environment(),
            handler=outbox_handler,
            serializer=serializer,
            deserializer=StylingSessionV1.model_validate,
        )
    return _execute_idempotent(
        db, "CreateStylingSession", command.actor_id, command.idempotency_key, command.correlation_id,
        handler, serializer,
    )


def run_outfit_decision(db: Session, session_id: str, command: RunOutfitDecisionCommandV1) -> OutfitDecisionRunV1:
    _require_actor(db, command.actor_id)

    def handler() -> OutfitDecisionRunV1:
        session = db.query(StylingSession).filter(StylingSession.session_id == session_id, StylingSession.owner_id == command.actor_id).first()
        if session is None:
            raise WorkflowNotFoundError("Styling session was not found for this actor")
        if session.status not in {"inputs_resolved", "recommendations_ready", "user_reviewing"}:
            raise WorkflowStateError(f"Outfit decision cannot run from session status {session.status}")
        session.status = "decision_running"
        approved_user_metadata: list[GarmentMetadataV1] = []
        owned_garment_ids: list[str] = []
        for asset_snapshot in (session.wardrobe_snapshot or []):
            metadata = asset_snapshot.get("semantic_metadata") if isinstance(asset_snapshot, dict) else None
            if isinstance(metadata, dict):
                approved = GarmentMetadataV1.model_validate(metadata)
                approved_user_metadata.append(approved)
                owned_garment_ids.append(approved.garment_id)
            elif isinstance(asset_snapshot, dict) and asset_snapshot.get("canonical_garment_id"):
                owned_garment_ids.append(str(asset_snapshot["canonical_garment_id"]))
        availability_policy = (session.context or {}).get("availability_policy", "owned_only")
        request = OutfitDecisionRequestV1(
            body=session.body_contract_snapshot,
            context=session.context,
            candidate_garment_ids=owned_garment_ids if availability_policy == "owned_only" else None,
            candidate_garments=approved_user_metadata,
            owned_garment_ids=owned_garment_ids,
            top_k=command.top_k,
        )
        decision = decide_outfits(request)
        run = OutfitDecisionRun(
            decision_run_id=_identifier("decision"),
            session_id=session.session_id,
            status="abstained" if decision.abstained else "ready",
            catalog_version=decision.catalog_version,
            rule_version=RULE_VERSION,
            decision_payload=decision.model_dump(mode="json"),
        )
        session.active_decision_run_id = run.decision_run_id
        session.status = "abstained" if decision.abstained else "recommendations_ready"
        session.updated_at = _now()
        db.add(run)
        db.flush()
        _audit(db, "StylingSession", session.session_id, "OutfitDecisionCompleted", command.actor_id, command.correlation_id or session.session_id, {"decision_run_id": run.decision_run_id, "abstained": decision.abstained, "candidate_count": len(decision.candidates)})
        return _decision_response(run)

    return _execute_idempotent(
        db, "RunOutfitDecision", command.actor_id, command.idempotency_key, command.correlation_id,
        handler, lambda value: value.model_dump(mode="json") if isinstance(value, OutfitDecisionRunV1) else OutfitDecisionRunV1.model_validate(value),
    )


def select_outfit_candidate(db: Session, session_id: str, command: SelectOutfitCandidateCommandV1) -> StylingSessionV1:
    _require_actor(db, command.actor_id)

    def handler() -> StylingSessionV1:
        session = db.query(StylingSession).filter(StylingSession.session_id == session_id, StylingSession.owner_id == command.actor_id).first()
        if session is None:
            raise WorkflowNotFoundError("Styling session was not found for this actor")
        if session.status not in {"recommendations_ready", "user_reviewing"} or not session.active_decision_run_id:
            raise WorkflowStateError("An outfit can only be selected from a ready recommendation or preview-review state")
        run = db.query(OutfitDecisionRun).filter(OutfitDecisionRun.decision_run_id == session.active_decision_run_id).first()
        if run is None or run.status != "ready":
            raise WorkflowStateError("Active decision run is not selectable")
        decision = OutfitDecisionResponseV1.model_validate(run.decision_payload)
        if command.outfit_id not in {candidate.outfit_id for candidate in decision.candidates}:
            raise WorkflowStateError("Selected outfit is not a candidate of the active decision")
        session.selected_outfit_id = command.outfit_id
        session.status = "outfit_selected"
        session.updated_at = _now()
        db.flush()
        _audit(db, "StylingSession", session.session_id, "OutfitSelected", command.actor_id, command.correlation_id or session.session_id, {"outfit_id": command.outfit_id, "decision_run_id": run.decision_run_id})
        return _session_response(session)

    return _execute_idempotent(
        db, "SelectOutfitCandidate", command.actor_id, command.idempotency_key, command.correlation_id,
        handler, lambda value: value.model_dump(mode="json") if isinstance(value, StylingSessionV1) else StylingSessionV1.model_validate(value),
    )


def request_try_on(db: Session, session_id: str, command: RequestTryOnCommandV1) -> TryOnRunV1:
    _require_actor(db, command.actor_id)

    def handler() -> TryOnRunV1:
        session = db.query(StylingSession).filter(StylingSession.session_id == session_id, StylingSession.owner_id == command.actor_id).first()
        if session is None:
            raise WorkflowNotFoundError("Styling session was not found for this actor")
        if not session.active_decision_run_id:
            raise WorkflowStateError("Try-on requires an active decision run")
        if command.preview_outfit_id is None and (session.status not in {"outfit_selected", "try_on_ready"} or not session.selected_outfit_id):
            raise WorkflowStateError("Final try-on requires a selected outfit; pass preview_outfit_id to compare a decision candidate without selecting it")
        decision_run = db.query(OutfitDecisionRun).filter(OutfitDecisionRun.decision_run_id == session.active_decision_run_id).first()
        if decision_run is None:
            raise WorkflowStateError("Active decision run was not found")
        decision = OutfitDecisionResponseV1.model_validate(decision_run.decision_payload)
        target_outfit_id = command.preview_outfit_id or session.selected_outfit_id
        selected_candidate = next((candidate for candidate in decision.candidates if candidate.outfit_id == target_outfit_id), None)
        if selected_candidate is None:
            raise WorkflowStateError("Preview or selected outfit is not available in the active decision run")
        resolution = resolve_try_on_assets(session, selected_candidate.garment_ids, command.render_mode)
        resolved_mode = resolution["resolved_render_mode"]
        quality_status = resolution["quality_status"]
        status = "ready" if quality_status == "approved" else "proxy_fallback"
        run = TryOnRun(
            try_on_run_id=_identifier("tryon"),
            session_id=session.session_id,
            decision_run_id=session.active_decision_run_id,
            selected_outfit_id=target_outfit_id,
            status=status,
            render_mode=resolved_mode,
            limitations=resolution["limitations"],
            resolution_payload=resolution,
        )
        session.status = "user_reviewing" if command.preview_outfit_id else "try_on_ready"
        session.updated_at = _now()
        db.add(run)
        db.flush()
        _audit(db, "TryOnRun", run.try_on_run_id, "TryOnResolved", command.actor_id, command.correlation_id or session.session_id, {"session_id": session.session_id, "preview_outfit_id": command.preview_outfit_id, "selected_outfit_id": target_outfit_id, "requested_render_mode": command.render_mode, "resolved_render_mode": resolved_mode, "quality_status": quality_status, "status": status})
        return _try_on_response(run)

    serializer = lambda value: value.model_dump(mode="json") if isinstance(value, TryOnRunV1) else TryOnRunV1.model_validate(value)
    if _workflow_outbox_enabled():
        def outbox_handler(correlation_id: str, command_id: str):
            command.correlation_id = correlation_id
            result = handler()
            return result, [{
                "event_type": OUTBOX_EVENT_TRY_ON_REQUESTED,
                "aggregate_type": "TryOnRun",
                "aggregate_id": result.try_on_run_id,
                "payload": {
                    "try_on_run_id": result.try_on_run_id,
                    "session_id": result.session_id,
                    "decision_run_id": result.decision_run_id,
                    "selected_outfit_id": result.selected_outfit_id,
                    "requested_render_mode": result.requested_render_mode,
                    "resolved_render_mode": result.render_mode,
                    "quality_status": result.quality_status,
                    "command_id": command_id,
                    "correlation_id": correlation_id,
                },
            }]
        return execute_idempotent_with_outbox(
            db,
            actor_id=command.actor_id,
            command_type="RequestTryOn",
            idempotency_key=command.idempotency_key,
            request_payload=command.model_dump(mode="json"),
            correlation_id=command.correlation_id,
            guard=RedisIdempotencyGuard.from_environment(),
            handler=outbox_handler,
            serializer=serializer,
            deserializer=TryOnRunV1.model_validate,
        )
    return _execute_idempotent(
        db, "RequestTryOn", command.actor_id, command.idempotency_key, command.correlation_id,
        handler, serializer,
    )


def list_audit_events(db: Session, aggregate_id: str, actor_id: int | None = None) -> list[AuditEventV1]:
    if actor_id is not None:
        _require_actor(db, actor_id)
        aggregate_owner_matches = (
            db.query(StylingSession.session_id)
            .filter(StylingSession.session_id == aggregate_id, StylingSession.owner_id == actor_id)
            .first()
            or db.query(WardrobeAsset.asset_id)
            .filter(WardrobeAsset.asset_id == aggregate_id, WardrobeAsset.owner_id == actor_id)
            .first()
            or db.query(BodyProfileRevision.profile_id)
            .filter(BodyProfileRevision.profile_id == aggregate_id, BodyProfileRevision.owner_id == actor_id)
            .first()
        )
        if aggregate_owner_matches is None:
            raise WorkflowNotFoundError("Workflow aggregate was not found for this actor")
    events = db.query(WorkflowAuditEvent).filter(WorkflowAuditEvent.aggregate_id == aggregate_id).order_by(WorkflowAuditEvent.created_at.asc()).all()
    return [AuditEventV1(
        event_id=event.event_id,
        aggregate_type=event.aggregate_type,
        aggregate_id=event.aggregate_id,
        event_type=event.event_type,
        actor_id=event.actor_id,
        correlation_id=event.correlation_id,
        payload=event.payload or {},
        created_at=event.created_at,
    ) for event in events]


def get_body_profile(db: Session, profile_id: str, actor_id: int) -> BodyProfileRevisionV1:
    _require_actor(db, actor_id)
    profile = db.query(BodyProfileRevision).filter(
        BodyProfileRevision.profile_id == profile_id,
        BodyProfileRevision.owner_id == actor_id,
    ).first()
    if profile is None:
        raise WorkflowNotFoundError("Body profile was not found for this actor")
    return _body_response(profile)


def get_wardrobe_asset(db: Session, asset_id: str, actor_id: int) -> WardrobeAssetRevisionV1:
    _require_actor(db, actor_id)
    asset = db.query(WardrobeAsset).filter(
        WardrobeAsset.asset_id == asset_id,
        WardrobeAsset.owner_id == actor_id,
    ).first()
    if asset is None:
        raise WorkflowNotFoundError("Wardrobe asset was not found for this actor")
    revision = db.query(GarmentAssetRevision).filter(
        GarmentAssetRevision.revision_id == asset.active_revision_id
    ).first()
    if revision is None:
        revision = db.query(GarmentAssetRevision).filter(
            GarmentAssetRevision.asset_id == asset.asset_id
        ).order_by(GarmentAssetRevision.revision.desc()).first()
    if revision is None:
        raise WorkflowStateError("Wardrobe asset has no revision")
    return _asset_response(asset, revision)


def get_styling_session(db: Session, session_id: str, actor_id: int) -> StylingSessionV1:
    _require_actor(db, actor_id)
    session = db.query(StylingSession).filter(
        StylingSession.session_id == session_id,
        StylingSession.owner_id == actor_id,
    ).first()
    if session is None:
        raise WorkflowNotFoundError("Styling session was not found for this actor")
    return _session_response(session)



def _feedback_response(record: StylingSessionFeedback) -> StylingSessionFeedbackV1:
    return StylingSessionFeedbackV1(
        feedback_id=record.feedback_id,
        session_id=record.session_id,
        decision_run_id=record.decision_run_id,
        try_on_run_id=record.try_on_run_id,
        owner_id=record.owner_id,
        target_outfit_id=record.target_outfit_id,
        sentiment=record.sentiment,
        reason_codes=record.reason_codes or [],
        issue_type=record.issue_type,
        fit_concern=record.fit_concern,
        note=record.note,
        confidence=record.confidence,
        created_at=record.created_at,
    )


def list_body_profiles(db: Session, actor_id: int, cursor: str | None = None, limit: int = 50) -> BodyProfileListV1:
    _require_actor(db, actor_id)
    query = db.query(BodyProfileRevision).filter(BodyProfileRevision.owner_id == actor_id)
    if cursor:
        query = query.filter(BodyProfileRevision.profile_id > cursor)
    rows = query.order_by(BodyProfileRevision.profile_id.asc()).limit(limit + 1).all()
    page = rows[:limit]
    return BodyProfileListV1(items=[_body_response(row) for row in page], next_cursor=page[-1].profile_id if len(rows) > limit and page else None)


def list_wardrobe_assets(db: Session, actor_id: int, status: str | None = None, cursor: str | None = None, limit: int = 50) -> WardrobeAssetListV1:
    _require_actor(db, actor_id)
    query = db.query(WardrobeAsset).filter(WardrobeAsset.owner_id == actor_id)
    if status:
        query = query.filter(WardrobeAsset.status == status)
    if cursor:
        query = query.filter(WardrobeAsset.asset_id > cursor)
    rows = query.order_by(WardrobeAsset.asset_id.asc()).limit(limit + 1).all()
    page = rows[:limit]
    items: list[WardrobeAssetRevisionV1] = []
    for asset in page:
        revision = db.query(GarmentAssetRevision).filter(GarmentAssetRevision.revision_id == asset.active_revision_id).first()
        if revision is None:
            revision = db.query(GarmentAssetRevision).filter(GarmentAssetRevision.asset_id == asset.asset_id).order_by(GarmentAssetRevision.revision.desc()).first()
        if revision is not None:
            items.append(_asset_response(asset, revision))
    return WardrobeAssetListV1(items=items, next_cursor=page[-1].asset_id if len(rows) > limit and page else None)


def list_styling_sessions(db: Session, actor_id: int, status: str | None = None, cursor: str | None = None, limit: int = 50) -> StylingSessionListV1:
    _require_actor(db, actor_id)
    query = db.query(StylingSession).filter(StylingSession.owner_id == actor_id)
    if status:
        query = query.filter(StylingSession.status == status)
    if cursor:
        query = query.filter(StylingSession.session_id > cursor)
    rows = query.order_by(StylingSession.session_id.asc()).limit(limit + 1).all()
    page = rows[:limit]
    return StylingSessionListV1(items=[_session_response(row) for row in page], next_cursor=page[-1].session_id if len(rows) > limit and page else None)


def get_try_on_run(db: Session, try_on_run_id: str, actor_id: int) -> TryOnRunV1:
    _require_actor(db, actor_id)
    record = db.query(TryOnRun).join(StylingSession, StylingSession.session_id == TryOnRun.session_id).filter(
        TryOnRun.try_on_run_id == try_on_run_id,
        StylingSession.owner_id == actor_id,
    ).first()
    if record is None:
        raise WorkflowNotFoundError("Try-on run was not found for this actor")
    return _try_on_response(record)


def submit_feedback(db: Session, session_id: str, command: SubmitFeedbackCommandV1) -> StylingSessionFeedbackV1:
    _require_actor(db, command.actor_id)

    def handler() -> StylingSessionFeedbackV1:
        session = db.query(StylingSession).filter(StylingSession.session_id == session_id, StylingSession.owner_id == command.actor_id).first()
        if session is None:
            raise WorkflowNotFoundError("Styling session was not found for this actor")
        decision_run = db.query(OutfitDecisionRun).filter(
            OutfitDecisionRun.decision_run_id == command.decision_run_id,
            OutfitDecisionRun.session_id == session_id,
        ).first()
        if decision_run is None:
            raise WorkflowStateError("Feedback decision run does not belong to the styling session")
        decision = OutfitDecisionResponseV1.model_validate(decision_run.decision_payload)
        if command.target_outfit_id and command.target_outfit_id not in {candidate.outfit_id for candidate in decision.candidates}:
            raise WorkflowStateError("Feedback target outfit does not belong to the decision run")
        if command.try_on_run_id:
            try_on_run = db.query(TryOnRun).filter(
                TryOnRun.try_on_run_id == command.try_on_run_id,
                TryOnRun.session_id == session_id,
                TryOnRun.decision_run_id == command.decision_run_id,
            ).first()
            if try_on_run is None:
                raise WorkflowStateError("Feedback try-on run does not belong to the decision run")
        feedback = StylingSessionFeedback(
            feedback_id=_identifier("feedback"),
            session_id=session_id,
            decision_run_id=command.decision_run_id,
            try_on_run_id=command.try_on_run_id,
            owner_id=command.actor_id,
            target_outfit_id=command.target_outfit_id,
            sentiment=command.sentiment,
            reason_codes=command.reason_codes,
            issue_type=command.issue_type,
            fit_concern=command.fit_concern,
            note=command.note,
            confidence=command.confidence,
        )
        db.add(feedback)
        session.status = "feedback_captured"
        session.updated_at = _now()
        db.flush()
        _audit(db, "StylingSession", session_id, "StylingSessionFeedbackSubmitted", command.actor_id, command.correlation_id or session_id, {"feedback_id": feedback.feedback_id, "decision_run_id": command.decision_run_id, "issue_type": command.issue_type, "sentiment": command.sentiment})
        if command.issue_type:
            task = ReviewTask(
                task_id=_identifier("review"),
                owner_id=command.actor_id,
                subject_type="StylingSessionFeedback",
                subject_id=feedback.feedback_id,
                review_type="user_feedback_triage",
                priority="high" if command.issue_type in {"fit", "visual_render"} else "normal",
                status="open",
                evidence_snapshot=_feedback_response(feedback).model_dump(mode="json"),
                checklist_version="p1-feedback-triage-v1",
                reason_codes=[],
            )
            db.add(task)
            _audit(db, "ReviewTask", task.task_id, "ReviewTaskOpened", command.actor_id, command.correlation_id or session_id, {"review_type": task.review_type, "source_feedback_id": feedback.feedback_id})
        return _feedback_response(feedback)

    serializer = lambda value: value.model_dump(mode="json") if isinstance(value, StylingSessionFeedbackV1) else StylingSessionFeedbackV1.model_validate(value)
    if _workflow_outbox_enabled():
        def outbox_handler(correlation_id: str, command_id: str):
            command.correlation_id = correlation_id
            result = handler()
            return result, [{
                "event_type": OUTBOX_EVENT_STYLING_SESSION_FEEDBACK_RECORDED,
                "aggregate_type": "StylingSessionFeedback",
                "aggregate_id": result.feedback_id,
                "payload": {
                    "feedback_id": result.feedback_id,
                    "session_id": result.session_id,
                    "decision_run_id": result.decision_run_id,
                    "owner_id": result.owner_id,
                    "issue_type": result.issue_type,
                    "command_id": command_id,
                    "correlation_id": correlation_id,
                },
            }]
        return execute_idempotent_with_outbox(
            db,
            actor_id=command.actor_id,
            command_type="SubmitStylingSessionFeedback",
            idempotency_key=command.idempotency_key,
            request_payload=command.model_dump(mode="json"),
            correlation_id=command.correlation_id,
            guard=RedisIdempotencyGuard.from_environment(),
            handler=outbox_handler,
            serializer=serializer,
            deserializer=StylingSessionFeedbackV1.model_validate,
        )
    return _execute_idempotent(
        db, "SubmitStylingSessionFeedback", command.actor_id, command.idempotency_key, command.correlation_id,
        handler, serializer,
    )


def list_feedback(db: Session, session_id: str, actor_id: int, cursor: str | None = None, limit: int = 50) -> FeedbackListV1:
    _require_actor(db, actor_id)
    if db.query(StylingSession.session_id).filter(StylingSession.session_id == session_id, StylingSession.owner_id == actor_id).first() is None:
        raise WorkflowNotFoundError("Styling session was not found for this actor")
    query = db.query(StylingSessionFeedback).filter(StylingSessionFeedback.session_id == session_id)
    if cursor:
        query = query.filter(StylingSessionFeedback.feedback_id > cursor)
    rows = query.order_by(StylingSessionFeedback.feedback_id.asc()).limit(limit + 1).all()
    page = rows[:limit]
    return FeedbackListV1(items=[_feedback_response(row) for row in page], next_cursor=page[-1].feedback_id if len(rows) > limit and page else None)



def get_outfit_decision_run(db: Session, session_id: str, decision_run_id: str, actor_id: int) -> OutfitDecisionRunV1:
    _require_actor(db, actor_id)
    run = db.query(OutfitDecisionRun).join(StylingSession, StylingSession.session_id == OutfitDecisionRun.session_id).filter(
        OutfitDecisionRun.decision_run_id == decision_run_id,
        OutfitDecisionRun.session_id == session_id,
        StylingSession.owner_id == actor_id,
    ).first()
    if run is None:
        raise WorkflowNotFoundError("Outfit decision run was not found for this actor")
    return _decision_response(run)
