from fastapi import APIRouter, UploadFile, File, HTTPException
from ..services import cv_engine

router = APIRouter(
    prefix="/vision",
    tags=["vision (computer vision)"],
)

@router.post("/upload-clothing/")
async def upload_clothing(file: UploadFile = File(...)):
    """
    Nhận ảnh từ user, xóa phông và nhận diện đặc tính áo quần.
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    image_bytes = await file.read()
    try:
        result = cv_engine.process_and_save_clothing_image(image_bytes)
        return {
            "message": "Image processed successfully",
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image processing failed: {str(e)}")
