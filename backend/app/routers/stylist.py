import json
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from ..schemas import MeasurementProfile
from ..services.ai_stylist import stylist_engine

router = APIRouter(prefix="/stylist", tags=["ai stylist"])
PROJECT_ROOT = Path(__file__).resolve().parents[3]
UPLOAD_DIR = PROJECT_ROOT / "uploads"
QUEUE_MODE = os.getenv("AI_STYLIST_QUEUE_MODE", "inline").lower()


@router.get("/tags")
def get_tags():
    taxonomy_path = PROJECT_ROOT / "data" / "fashion_taxonomy.json"
    if not taxonomy_path.exists():
        return {"tags": []}
    with taxonomy_path.open("r", encoding="utf-8") as file:
        taxonomy_db = json.load(file)
    all_tags = []
    for items in taxonomy_db.get("tags", {}).values():
        if isinstance(items, list):
            all_tags.extend(items)
    return {"tags": sorted(set(all_tags))}


def _build_profile(body_type, skin_tone, hair_type, face_shape):
    if not any([body_type, skin_tone, hair_type, face_shape]):
        return None
    return {
        "body_type": body_type or "Không rõ",
        "skin_tone": skin_tone or "Không rõ",
        "hair_type": hair_type or "Không rõ",
        "face_shape": face_shape or "Không rõ",
    }


@router.post("/recommend/")
async def get_recommendation(
    tags: str = Form(...),
    image: UploadFile = File(...),
    body_type: str = Form(None),
    skin_tone: str = Form(None),
    hair_type: str = Form(None),
    face_shape: str = Form(None),
):
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
    if not tag_list:
        raise HTTPException(status_code=422, detail="At least one tag is required")
    user_profile = _build_profile(body_type, skin_tone, hair_type, face_shape)

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(image.filename or "upload.jpg").suffix or ".jpg"
    tmp_path = UPLOAD_DIR / f"{uuid.uuid4()}{suffix}"
    try:
        tmp_path.write_bytes(await image.read())
        if QUEUE_MODE == "celery":
            from ..tasks import generate_recommendation
            task = generate_recommendation.delay(str(tmp_path), tag_list, user_profile)
            return JSONResponse(status_code=202, content={"status": "queued", "job_id": task.id})

        if not stylist_engine.is_loaded:
            stylist_engine.load_model()
        recommendation = stylist_engine.get_style_advice(
            image_path=str(tmp_path), selected_tags=tag_list, user_profile=user_profile
        )
        return {
            "message": "AI Stylist generated recommendations successfully",
            "data": {"ai_reasoning_and_recommendation": recommendation},
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if QUEUE_MODE != "celery" and os.getenv("AI_STYLIST_KEEP_UPLOADS", "0").lower() not in {"1", "true", "yes", "on"}:
            tmp_path.unlink(missing_ok=True)


class WardrobeRecommendRequest(MeasurementProfile):
    measurements: MeasurementProfile | None = None
    selected_tags: list[str] = []
    wardrobe_items: list[dict] = []


@router.post("/measurement-recommend/")
def measurement_recommendation(measurements: MeasurementProfile, selected_tags: list[str]):
    if not selected_tags:
        raise HTTPException(status_code=422, detail="At least one tag is required")
    payload = measurements.model_dump()
    if QUEUE_MODE == "celery":
        from ..tasks import generate_measurement_recommendation
        task = generate_measurement_recommendation.delay(payload, selected_tags)
        return JSONResponse(status_code=202, content={"status": "queued", "job_id": task.id})
    if not stylist_engine.is_loaded:
        stylist_engine.load_model()
    return {
        "message": "Measurement recommendation generated successfully",
        "data": {"ai_reasoning_and_recommendation": stylist_engine.get_measurement_advice(payload, selected_tags)},
    }


@router.post("/wardrobe-recommend/")
def wardrobe_recommendation(payload: dict):
    selected_tags = payload.get("selected_tags", [])
    if not selected_tags:
        raise HTTPException(status_code=422, detail="At least one tag is required")
    measurements = payload.get("measurements", {})
    wardrobe_items = payload.get("wardrobe_items", [])
    
    if not stylist_engine.is_loaded:
        stylist_engine.load_model()
    advice = stylist_engine.get_wardrobe_advice(
        wardrobe_items=[json.dumps(item, ensure_ascii=False) if isinstance(item, dict) else str(item) for item in wardrobe_items],
        selected_tags=selected_tags,
        user_profile=measurements
    )
    return {
        "message": "Wardrobe recommendation generated successfully",
        "data": {"ai_reasoning_and_recommendation": advice},
    }


@router.get("/recommend/{job_id}")
def get_recommendation_status(job_id: str):
    if QUEUE_MODE != "celery":
        raise HTTPException(status_code=404, detail="Queue mode is disabled")
    from ..queue import celery_app
    result = celery_app.AsyncResult(job_id)
    if result.state in {"PENDING", "STARTED", "RETRY"}:
        return {"status": result.state.lower(), "job_id": job_id}
    if result.state == "FAILURE":
        return {"status": "failed", "job_id": job_id, "error": str(result.result)}
    payload = result.result or {}
    return {"status": "completed", "job_id": job_id, "data": payload}
