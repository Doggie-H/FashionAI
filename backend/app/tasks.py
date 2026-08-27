import os
from datetime import datetime, timezone
from pathlib import Path

from .queue import celery_app
from .phase_b_schemas import GarmentSemanticTaggingV1, ReconstructionStateV1
from .services.ai_stylist import stylist_engine
from .services.garment_import import analyze_garment_import_semantics, read_manifest, write_manifest
from .services.garment_reconstruction import quality_gate_passes, reconstruct_rigged_garment
from .services.garment_segmentation import segment_garment


@celery_app.task(bind=True, name="stylist.generate_recommendation", autoretry_for=(RuntimeError,), retry_backoff=True, max_retries=2)
def generate_recommendation(self, image_path: str, selected_tags: list[str], user_profile: dict | None = None):
    try:
        if not stylist_engine.is_loaded:
            stylist_engine.load_model()
        return {
            "ai_reasoning_and_recommendation": stylist_engine.get_style_advice(
                image_path=image_path,
                selected_tags=selected_tags,
                user_profile=user_profile,
            )
        }
    finally:
        if os.getenv("AI_STYLIST_KEEP_UPLOADS", "0").lower() not in {"1", "true", "yes", "on"}:
            Path(image_path).unlink(missing_ok=True)


@celery_app.task(bind=True, name="stylist.generate_measurement_recommendation", autoretry_for=(RuntimeError,), retry_backoff=True, max_retries=2)
def generate_measurement_recommendation(self, measurements: dict, selected_tags: list[str]):
    if not stylist_engine.is_loaded:
        stylist_engine.load_model()
    return {
        "ai_reasoning_and_recommendation": stylist_engine.get_measurement_advice(
            measurements=measurements, selected_tags=selected_tags
        )
    }


@celery_app.task(bind=True, name="stylist.process_garment_reconstruction", autoretry_for=(RuntimeError,), retry_backoff=True, max_retries=1)
def process_garment_reconstruction(self, import_id: str):
    manifest = read_manifest(import_id)
    if manifest is None:
        raise ValueError(f"Garment import manifest not found: {import_id}")
    now = datetime.now(timezone.utc)
    manifest.reconstruction = ReconstructionStateV1(
        pipeline_state="segmenting",
        job_id=self.request.id,
        requested_backend="garment3dgen_offline",
        updated_at=now,
    )
    write_manifest(manifest)

    try:
        segmentation = segment_garment(manifest)
    except Exception as error:
        manifest.rig_status = "failed"
        manifest.reconstruction = ReconstructionStateV1(
            pipeline_state="failed",
            job_id=self.request.id,
            requested_backend="garment3dgen_offline",
            failure_reason=f"Segmentation failed: {error}",
            updated_at=datetime.now(timezone.utc),
        )
        write_manifest(manifest)
        return manifest.model_dump(mode="json")
    manifest.segmentation = segmentation
    manifest.reconstruction = ReconstructionStateV1(
        pipeline_state="segmented",
        job_id=self.request.id,
        requested_backend="garment3dgen_offline",
        provider_version=segmentation.provider,
        updated_at=datetime.now(timezone.utc),
    )
    write_manifest(manifest)

    try:
        completed = reconstruct_rigged_garment(manifest)
        if not quality_gate_passes(completed.quality_gate, completed):
            completed.rig_status = "pending_reconstruction"
            completed.conversion_backend = "garment3dgen_offline"
            completed.reconstruction = ReconstructionStateV1(
                pipeline_state="pending_reconstruction",
                job_id=self.request.id,
                requested_backend="garment3dgen_offline",
                provider_version="configured-provider",
                failure_reason="Provider output did not pass the required mesh quality gate.",
                updated_at=datetime.now(timezone.utc),
            )
            write_manifest(completed)
            return completed.model_dump(mode="json")
        completed.rig_status = "rigged_template"
        completed.conversion_backend = "garment3dgen_offline"
        completed.reconstruction = ReconstructionStateV1(
            pipeline_state="rigged_template",
            job_id=self.request.id,
            requested_backend="garment3dgen_offline",
            provider_version="configured-provider",
            updated_at=datetime.now(timezone.utc),
        )
        write_manifest(completed)
        return completed.model_dump(mode="json")
    except NotImplementedError as error:
        manifest.rig_status = "pending_reconstruction"
        manifest.conversion_backend = "garment3dgen_offline"
        manifest.reconstruction = ReconstructionStateV1(
            pipeline_state="pending_reconstruction",
            job_id=self.request.id,
            requested_backend="garment3dgen_offline",
            provider_version="provider-not-configured",
            failure_reason=str(error),
            updated_at=datetime.now(timezone.utc),
        )
        write_manifest(manifest)
        return manifest.model_dump(mode="json")
    except RuntimeError as error:
        manifest.rig_status = "pending_reconstruction"
        manifest.conversion_backend = "garment3dgen_offline"
        manifest.reconstruction = ReconstructionStateV1(
            pipeline_state="pending_reconstruction",
            job_id=self.request.id,
            requested_backend="garment3dgen_offline",
            failure_reason=str(error),
            updated_at=datetime.now(timezone.utc),
        )
        write_manifest(manifest)
        return manifest.model_dump(mode="json")
    except Exception as error:
        manifest.rig_status = "failed"
        manifest.conversion_backend = "garment3dgen_offline"
        manifest.reconstruction = ReconstructionStateV1(
            pipeline_state="failed",
            job_id=self.request.id,
            requested_backend="garment3dgen_offline",
            failure_reason=f"Reconstruction provider failed: {error}",
            updated_at=datetime.now(timezone.utc),
        )
        write_manifest(manifest)
        return manifest.model_dump(mode="json")


@celery_app.task(bind=True, name="stylist.semantic_tag_garment_import", autoretry_for=(RuntimeError,), retry_backoff=True, max_retries=1)
def semantic_tag_garment_import(self, import_id: str):
    manifest = read_manifest(import_id)
    if manifest is None:
        raise ValueError(f"Garment import manifest not found: {import_id}")
    provider = os.getenv("GARMENT_TAGGER_PROVIDER", "disabled").strip().lower()
    manifest.analysis.semantic_tagging = GarmentSemanticTaggingV1(
        status="running",
        provider="qwen25vl" if provider == "qwen25vl" else "disabled",
        source_image_sha256=manifest.source_image_sha256,
    )
    manifest.analysis.needs_human_review = True
    write_manifest(manifest)
    completed = analyze_garment_import_semantics(import_id)
    return completed.model_dump(mode="json")


@celery_app.task(bind=True, name="stylist.handle_workflow_outbox_event", autoretry_for=(RuntimeError,), retry_backoff=True, max_retries=5)
def handle_workflow_outbox_event(self, event_id: str, event_type: str, payload: dict):
    """Generic consumer boundary. Keep domain side effects idempotent per consumer/event pair."""
    from .database import SessionLocal
    from .services.workflow_outbox import consume_event_once

    db = SessionLocal()
    try:
        consumer_name = "stylist.workflow_projector.v1"

        def project_event() -> None:
            if event_type == "StylingSessionOpened.v1":
                # Projection/notification extension point. Do not mutate immutable session snapshots here.
                return
            if event_type == "StylingSessionFeedbackRecorded.v1":
                # Feedback and triage ReviewTask were committed in the command transaction.
                # A future analytics/evaluation projector must remain idempotent by event_id.
                return
            if event_type == "TryOnRequested.v1":
                # Resolution evidence already exists on TryOnRun. Rendering/analytics must not rewrite the run blindly.
                return
            raise RuntimeError(f"Unsupported workflow outbox event type: {event_type}")

        processed = consume_event_once(
            db,
            consumer_name=consumer_name,
            event_id=event_id,
            handler=project_event,
        )
        return {"event_id": event_id, "event_type": event_type, "processed": processed, "payload": payload}
    finally:
        db.close()
