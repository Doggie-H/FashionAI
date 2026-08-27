from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.phase_a_schemas import RawMeasurementsV1, StyleContextV1
from app.services import review_tasks, workflow_service
from app.services.body_contract import build_parametric_body_contract
from app.services.try_on_resolver import resolve_try_on_assets
from app.workflow_models import EvaluationLabel, OutfitDecisionRun, ReviewTask, StylingSession, WorkflowAuditEvent
from app.workflow_schemas import (
    ClaimReviewTaskCommandV1,
    DecideTaxonomyLearningProposalCommandV1,
    SubmitFeedbackCommandV1,
    SubmitReviewDecisionCommandV1,
)


MEASUREMENTS = RawMeasurementsV1(
    height_cm=170,
    weight_kg=60,
    shoulder_cm=42,
    bust_cm=88,
    waist_cm=72,
    hip_cm=94,
    inseam_cm=78,
)


def _db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return engine, factory()


def test_feedback_keeps_session_decision_target_provenance_and_opens_triage_task():
    engine, db = _db()
    try:
        db.add(models.User(id=101, username="feedback-owner", email="feedback-owner@example.test"))
        contract = build_parametric_body_contract(MEASUREMENTS)
        session = StylingSession(
            session_id="style_aaaaaaaaaaaa",
            owner_id=101,
            body_profile_id="body_aaaaaaaaaaaa",
            status="try_on_ready",
            context=StyleContextV1(occasion="work").model_dump(mode="json"),
            body_contract_snapshot=contract.model_dump(mode="json"),
            wardrobe_snapshot=[],
            active_decision_run_id="decision_aaaaaaaaaaaa",
            selected_outfit_id="outfit_feedback_case",
        )
        decision = OutfitDecisionRun(
            decision_run_id="decision_aaaaaaaaaaaa",
            session_id=session.session_id,
            status="ready",
            catalog_version="test",
            rule_version="test",
            decision_payload={
                "decision_id": "dec_feedback_case",
                "catalog_version": "test",
                "candidates": [{
                    "outfit_id": "outfit_feedback_case",
                    "garment_ids": ["gar_business_shirt_navy"],
                    "total_score": 75.0,
                    "confidence": 0.8,
                    "constraints_satisfied": [],
                    "tradeoffs": [],
                    "evidence": [],
                    "needs_user_confirmation": [],
                }],
                "abstained": False,
            },
        )
        db.add_all([session, decision])
        db.commit()

        result = workflow_service.submit_feedback(
            db,
            session.session_id,
            SubmitFeedbackCommandV1(
                actor_id=101,
                idempotency_key="feedback-submit-0001",
                correlation_id="corr-feedback-0001",
                decision_run_id=decision.decision_run_id,
                target_outfit_id="outfit_feedback_case",
                sentiment="dislike",
                reason_codes=["visual_mismatch"],
                issue_type="visual_render",
                note="Proxy did not represent the intended silhouette.",
                confidence=4,
            ),
        )
        assert result.session_id == session.session_id
        assert result.target_outfit_id == "outfit_feedback_case"
        assert db.get(StylingSession, session.session_id).status == "feedback_captured"
        triage = db.query(ReviewTask).filter_by(subject_id=result.feedback_id, review_type="user_feedback_triage").one()
        assert triage.status == "open"
        assert db.query(WorkflowAuditEvent).filter_by(aggregate_id=session.session_id, event_type="StylingSessionFeedbackSubmitted").count() == 1
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_reviewer_claim_and_decision_are_atomic_and_idempotent():
    engine, db = _db()
    try:
        db.add_all([
            models.User(id=201, username="review-owner", email="review-owner@example.test"),
            models.User(id=202, username="reviewer-one", email="reviewer-one@example.test"),
            models.User(id=203, username="reviewer-two", email="reviewer-two@example.test"),
        ])
        task = ReviewTask(
            task_id="review_aaaaaaaaaaaa",
            owner_id=201,
            subject_type="StylingSessionFeedback",
            subject_id="feedback_aaaaaaaaaaaa",
            review_type="user_feedback_triage",
            priority="normal",
            status="open",
            evidence_snapshot={"feedback_id": "feedback_aaaaaaaaaaaa"},
            checklist_version="p1-feedback-triage-v1",
            reason_codes=[],
        )
        db.add(task)
        db.commit()

        first_claim = review_tasks.claim_review_task(db, task.task_id, ClaimReviewTaskCommandV1(
            actor_id=202, idempotency_key="review-claim-0001", correlation_id="corr-review-claim-0001",
        ))
        replay_claim = review_tasks.claim_review_task(db, task.task_id, ClaimReviewTaskCommandV1(
            actor_id=202, idempotency_key="review-claim-0001", correlation_id="corr-review-claim-0001",
        ))
        assert first_claim.status == replay_claim.status == "claimed"
        assert first_claim.assignee_actor_id == 202

        decision = review_tasks.submit_review_decision(
            db,
            task.task_id,
            SubmitReviewDecisionCommandV1(
                actor_id=202,
                idempotency_key="review-decision-0001",
                correlation_id="corr-review-decision-0001",
                decision="approve",
                reason_codes=["reproducible"],
                reviewer_note="Issue was reproduced and accepted into the evaluation set.",
            ),
            is_admin=False,
        )
        replay_decision = review_tasks.submit_review_decision(
            db,
            task.task_id,
            SubmitReviewDecisionCommandV1(
                actor_id=202,
                idempotency_key="review-decision-0001",
                correlation_id="corr-review-decision-0001",
                decision="approve",
                reason_codes=["reproducible"],
                reviewer_note="Issue was reproduced and accepted into the evaluation set.",
            ),
            is_admin=False,
        )
        assert decision.status == replay_decision.status == "approved"
        assert db.query(EvaluationLabel).filter_by(source_review_task_id=task.task_id).count() == 1
        assert db.query(WorkflowAuditEvent).filter_by(aggregate_id=task.task_id).count() == 2
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_rigged_resolution_requires_complete_approved_quality_evidence_or_returns_proxy():
    contract = build_parametric_body_contract(MEASUREMENTS)
    session = StylingSession(
        session_id="style_bbbbbbbbbbbb",
        owner_id=301,
        body_profile_id="body_bbbbbbbbbbbb",
        status="outfit_selected",
        context=StyleContextV1(occasion="work").model_dump(mode="json"),
        body_contract_snapshot=contract.model_dump(mode="json"),
        wardrobe_snapshot=[{
            "asset_id": "wad_bbbbbbbbbbbb",
            "revision_id": "garrev_bbbbbbbbbbbb",
            "category": "top",
            "canonical_garment_id": "gar_business_shirt_navy",
            "render_contract": {
                "rig_status": "rigged_template",
                "target_skeleton_id": "mixamo-humanoid-v1",
                "generated_asset_uri": "/uploads/garment_meshes/approved-shirt.glb",
                "anchors": ["shoulder", "chest"],
                "quality_gate": {
                    "asset_exists": True,
                    "glb_valid": True,
                    "skeleton_id": "mixamo-humanoid-v1",
                    "anchors_present": True,
                    "skin_weights_valid": True,
                    "scale_valid": True,
                    "bounds_valid": True,
                    "intersection_check": "passed",
                    "review_status": "approved",
                },
            },
        }],
    )
    approved = resolve_try_on_assets(session, ["gar_business_shirt_navy"], "rigged_template")
    assert approved["resolved_render_mode"] == "rigged_template"
    assert approved["quality_status"] == "approved"

    session.wardrobe_snapshot[0]["render_contract"]["quality_gate"]["review_status"] = "pending_review"
    fallback = resolve_try_on_assets(session, ["gar_business_shirt_navy"], "rigged_template")
    assert fallback["resolved_render_mode"] == "canonical_proxy"
    assert fallback["quality_status"] == "pending_review"


def test_reviewer_approval_promotes_semantic_metadata_and_try_on_maps_user_garment_id():
    from app.services.garment_catalog import get_garment
    from app.workflow_models import GarmentAssetRevision, WardrobeAsset

    engine, db = _db()
    try:
        db.add_all([
            models.User(id=401, username="semantic-owner", email="semantic-owner@example.test"),
            models.User(id=402, username="semantic-reviewer", email="semantic-reviewer@example.test"),
        ])
        canonical = get_garment("gar_beige_knit_polo")
        assert canonical is not None
        candidate = canonical.model_copy(update={
            "garment_id": "gar_user_abcdef123456",
            "name": "User imported knit polo",
            "source": "user_import",
            "status": "draft",
            "category": "top",
            "styles": ["quiet_luxury", "preppy"],
        })
        asset = WardrobeAsset(
            asset_id="wad_semantic0001",
            owner_id=401,
            name="User imported knit polo",
            category="top",
            status="pending_review",
        )
        revision = GarmentAssetRevision(
            revision_id="garrev_semantic0001",
            asset_id=asset.asset_id,
            revision=1,
            status="pending_review",
            import_id=None,
            canonical_garment_id="gar_beige_knit_polo",
            manifest_snapshot={
                "analysis": {"semantic_tagging": {
                    "status": "needs_review",
                    "candidate_metadata": candidate.model_dump(mode="json"),
                }},
            },
            quality_summary={"eligible_for_decision": False},
        )
        task = ReviewTask(
            task_id="review_semantic0001",
            owner_id=401,
            subject_type="GarmentAssetRevision",
            subject_id=asset.asset_id,
            subject_revision_id=revision.revision_id,
            review_type="garment_metadata",
            priority="normal",
            status="open",
            evidence_snapshot={"semantic_tagging": revision.manifest_snapshot},
            checklist_version="p1-garment-metadata-v1",
            reason_codes=[],
        )
        db.add_all([asset, revision, task])
        db.commit()

        review_tasks.claim_review_task(db, task.task_id, ClaimReviewTaskCommandV1(
            actor_id=402, idempotency_key="semantic-claim-0001", correlation_id="corr-semantic-claim-0001",
        ))
        review_tasks.submit_review_decision(db, task.task_id, SubmitReviewDecisionCommandV1(
            actor_id=402,
            idempotency_key="semantic-approve-0001",
            correlation_id="corr-semantic-approve-0001",
            decision="approve",
            reason_codes=["tag_evidence_confirmed"],
            reviewer_note="Visible garment attributes match the taxonomy draft.",
        ), is_admin=False)

        db.refresh(revision)
        db.refresh(asset)
        assert revision.status == "active"
        assert revision.semantic_metadata["garment_id"] == candidate.garment_id
        assert revision.manifest_snapshot["analysis"]["semantic_tagging"]["status"] == "approved"

        contract = build_parametric_body_contract(MEASUREMENTS)
        session = StylingSession(
            session_id="style_semantic0001",
            owner_id=401,
            body_profile_id="body_semantic0001",
            status="outfit_selected",
            context=StyleContextV1(occasion="meeting").model_dump(mode="json"),
            body_contract_snapshot=contract.model_dump(mode="json"),
            wardrobe_snapshot=[workflow_service._asset_response(asset, revision).model_dump(mode="json")],
        )
        resolution = resolve_try_on_assets(session, [candidate.garment_id], "canonical_proxy")
        assert resolution["quality_status"] == "proxy"
        assert resolution["asset_bindings"][0]["asset_id"] == asset.asset_id
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_approved_semantic_review_derives_governed_taxonomy_proposals():
    from app.services import taxonomy_learning
    from app.services.garment_catalog import get_garment
    from app.workflow_models import GarmentAssetRevision, TaxonomyLearningProposal, WardrobeAsset

    engine, db = _db()
    try:
        db.add_all([
            models.User(id=501, username="taxonomy-owner", email="taxonomy-owner@example.test"),
            models.User(id=502, username="taxonomy-reviewer", email="taxonomy-reviewer@example.test"),
        ])
        canonical = get_garment("gar_beige_knit_polo")
        assert canonical is not None
        candidate = canonical.model_copy(update={
            "garment_id": "gar_user_taxonomy0001",
            "name": "Reviewed navy T-shirt",
            "source": "user_import",
            "status": "draft",
            "styles": ["minimal"],
            "occasions": ["work"],
            "intent_support": ["comfort"],
        })
        asset = WardrobeAsset(asset_id="wad_taxonomy0001", owner_id=501, name="Reviewed navy T-shirt", category="top", status="pending_review")
        revision = GarmentAssetRevision(
            revision_id="garrev_taxonomy0001",
            asset_id=asset.asset_id,
            revision=1,
            status="pending_review",
            canonical_garment_id="gar_beige_knit_polo",
            manifest_snapshot={"analysis": {"semantic_tagging": {
                "status": "needs_review",
                "candidate_metadata": candidate.model_dump(mode="json"),
                "evidence": [
                    {"dimension": "styles", "confidence": 0.88},
                    {"dimension": "occasions", "confidence": 0.84},
                    {"dimension": "intent_support", "confidence": 0.8},
                ],
            }}},
            quality_summary={"eligible_for_decision": False},
        )
        task = ReviewTask(
            task_id="review_taxonomy0001",
            owner_id=501,
            subject_type="GarmentAssetRevision",
            subject_id=asset.asset_id,
            subject_revision_id=revision.revision_id,
            review_type="garment_metadata",
            priority="normal",
            status="open",
            evidence_snapshot={},
            checklist_version="p1-garment-metadata-v1",
            reason_codes=[],
        )
        db.add_all([asset, revision, task])
        db.commit()
        review_tasks.claim_review_task(db, task.task_id, ClaimReviewTaskCommandV1(actor_id=502, idempotency_key="taxonomy-claim-0001", correlation_id="corr-taxonomy-claim-0001"))
        review_tasks.submit_review_decision(db, task.task_id, SubmitReviewDecisionCommandV1(
            actor_id=502,
            idempotency_key="taxonomy-approve-0001",
            correlation_id="corr-taxonomy-approve-0001",
            decision="approve",
            reason_codes=["evidence_confirmed"],
            reviewer_note="Visible style, occasion and comfort tags were verified.",
        ), is_admin=False)

        proposals = db.query(TaxonomyLearningProposal).order_by(TaxonomyLearningProposal.dimension).all()
        assert len(proposals) == 2
        assert {item.dimension for item in proposals} == {"style_occasion_prior", "style_intent_prior"}
        assert all(item.status == "proposed" and item.support_count == 1 for item in proposals)
        assert all(item.proposal_payload["catalog_mutation"] is False for item in proposals)
        assert all(task.task_id in item.source_review_task_ids for item in proposals)
        first = proposals[0]
        with pytest.raises(taxonomy_learning.TaxonomyLearningProposalStateError):
            taxonomy_learning.decide_proposal(db, first.proposal_id, DecideTaxonomyLearningProposalCommandV1(
                actor_id=502,
                idempotency_key="taxonomy-decide-too-early",
                correlation_id="corr-taxonomy-decide-too-early",
                decision="approve_for_evaluation",
                review_note="Attempting evaluation approval before independent support threshold.",
            ))
        first.support_count = 3
        db.commit()
        approved = taxonomy_learning.decide_proposal(db, first.proposal_id, DecideTaxonomyLearningProposalCommandV1(
            actor_id=502,
            idempotency_key="taxonomy-decide-0001",
            correlation_id="corr-taxonomy-decide-0001",
            decision="approve_for_evaluation",
            review_note="Independent reviewed support and holdout evaluation are required before release.",
        ))
        assert approved.status == "approved_for_evaluation"
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
