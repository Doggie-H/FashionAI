from datetime import datetime, timezone

import os

from celery.result import AsyncResult
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from kombu.exceptions import OperationalError

from ..phase_b_schemas import (
    GarmentImportResponseV1,
    ReconstructionStartResponseV1,
    GarmentSemanticTaggingV1,
    SemanticTaggingStartResponseV1,
    ReconstructionStateV1,
    TryOnBindingRequestV1,
    TryOnBindingV1,
)
from ..queue import celery_app
from ..services.garment_import import (
    MalformedGarmentManifestError,
    analyze_garment_import_semantics,
    import_garment_image,
    read_manifest,
    write_manifest,
)
from ..tasks import process_garment_reconstruction, semantic_tag_garment_import


router = APIRouter(prefix="/phase-b", tags=["virtual try-on phase b"])


def _load_manifest_or_http(import_id: str):
    try:
        manifest = read_manifest(import_id)
    except MalformedGarmentManifestError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if manifest is None:
        raise HTTPException(status_code=404, detail="Garment import manifest not found")
    return manifest


def _manifest_response_status(manifest) -> str:
    state = manifest.reconstruction.pipeline_state
    if state in {"queued", "segmenting", "segmented"}:
        return "queued"
    if state == "pending_reconstruction":
        return "pending_reconstruction"
    if state == "failed":
        return "failed"
    return "needs_review" if manifest.analysis.needs_human_review else "completed"


@router.post("/garment-imports", response_model=GarmentImportResponseV1)
async def create_garment_import(
    file: UploadFile = File(...),
    category: str | None = Form(default=None),
):
    try:
        content = await file.read()
        manifest = import_garment_image(file.filename or "", content, file.content_type, category)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return GarmentImportResponseV1(status=_manifest_response_status(manifest), manifest=manifest)


@router.get("/garment-imports/{import_id}", response_model=GarmentImportResponseV1)
def get_garment_import(import_id: str):
    manifest = _load_manifest_or_http(import_id)
    return GarmentImportResponseV1(
        status=_manifest_response_status(manifest),
        manifest=manifest,
        job_id=manifest.reconstruction.job_id,
    )


@router.post("/garment-imports/{import_id}/semantic-tags", response_model=SemanticTaggingStartResponseV1)
def start_semantic_tagging(import_id: str):
    manifest = _load_manifest_or_http(import_id)
    existing = manifest.analysis.semantic_tagging
    if existing and existing.status in {"queued", "running"}:
        raise HTTPException(status_code=409, detail="Garment semantic tagging is already queued")
    provider = os.getenv("GARMENT_TAGGER_PROVIDER", "disabled").strip().lower()
    if provider != "qwen25vl":
        manifest = analyze_garment_import_semantics(import_id)
        semantic_status = manifest.analysis.semantic_tagging.status if manifest.analysis.semantic_tagging else "unavailable"
        status = semantic_status if semantic_status in {"needs_review", "unavailable", "failed"} else "unavailable"
        return SemanticTaggingStartResponseV1(status=status, manifest=manifest)
    try:
        job = semantic_tag_garment_import.delay(import_id)
    except OperationalError as error:
        raise HTTPException(status_code=503, detail="Celery broker is unavailable; start the GPU tagging worker before queuing garment semantic analysis") from error
    manifest.analysis.semantic_tagging = GarmentSemanticTaggingV1(
        status="queued",
        provider="qwen25vl",
        source_image_sha256=manifest.source_image_sha256,
    )
    manifest.analysis.needs_human_review = True
    write_manifest(manifest)
    return SemanticTaggingStartResponseV1(status="queued", manifest=manifest, job_id=job.id)


@router.get("/garment-semantic-tagging-jobs/{job_id}")
def get_garment_semantic_tagging_job(job_id: str):
    task = AsyncResult(job_id, app=celery_app)
    return {"job_id": job_id, "celery_state": task.state, "result": task.result if task.successful() else None}


@router.post("/garment-imports/{import_id}/reconstruct", response_model=ReconstructionStartResponseV1)
def start_garment_reconstruction(import_id: str):
    manifest = _load_manifest_or_http(import_id)
    if manifest.reconstruction.pipeline_state in {"queued", "segmenting"}:
        raise HTTPException(status_code=409, detail="Garment reconstruction is already queued")
    try:
        job = process_garment_reconstruction.delay(import_id)
    except OperationalError as error:
        raise HTTPException(status_code=503, detail="Celery broker is unavailable; start Redis and the GPU worker before queuing reconstruction") from error

    manifest.reconstruction = ReconstructionStateV1(
        pipeline_state="queued",
        job_id=job.id,
        requested_backend="garment3dgen_offline",
        updated_at=datetime.now(timezone.utc),
    )
    write_manifest(manifest)
    return ReconstructionStartResponseV1(status="queued", manifest=manifest, job_id=job.id)


@router.get("/garment-reconstruction-jobs/{job_id}")
def get_garment_reconstruction_job(job_id: str):
    task = AsyncResult(job_id, app=celery_app)
    return {"job_id": job_id, "celery_state": task.state, "result": task.result if task.successful() else None}


@router.post("/try-on-bindings", response_model=list[TryOnBindingV1])
def create_try_on_bindings(request: TryOnBindingRequestV1):
    bindings: list[TryOnBindingV1] = []
    for import_id in request.import_ids:
        try:
            manifest = _load_manifest_or_http(import_id)
        except HTTPException as error:
            if error.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Garment import manifest not found: {import_id}") from error
            raise
        if manifest.target_skeleton_id != request.target_skeleton_id:
            raise HTTPException(status_code=409, detail=f"Skeleton contract mismatch: {import_id}")
        bindings.append(TryOnBindingV1(
            import_id=manifest.import_id,
            category=manifest.analysis.category,
            selected_garment_id=manifest.selected_garment_id,
            template_id=manifest.selected_template_id,
            rig_status=manifest.rig_status,
            target_skeleton_id=manifest.target_skeleton_id,
            render_binding=manifest.render_binding,
        ))
    return bindings
