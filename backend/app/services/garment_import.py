import hashlib
import re
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError

from ..phase_b_schemas import (
    GarmentImageAnalysisV1,
    GarmentImportManifestV1,
    ReconstructionStateV1,
)
from .garment_catalog import list_active_garments
from .garment_semantic_tagger import analyze_import_for_semantic_tags


PROJECT_ROOT = Path(__file__).resolve().parents[3]
GARMENT_UPLOAD_DIR = PROJECT_ROOT / "uploads" / "garments"
MANIFEST_DIR = PROJECT_ROOT / "uploads" / "garment_manifests"
ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
FORMAT_TO_MIME = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
class MalformedGarmentManifestError(ValueError):
    """Raised when a persisted manifest no longer satisfies the versioned contract."""


CATEGORY_KEYWORDS = {
    "dress": "dress", "váy": "dress", "blazer": "outerwear", "jacket": "outerwear", "áo khoác": "outerwear",
    "belt": "belt", "dây nịt": "belt", "shoe": "footwear", "giày": "footwear", "trouser": "bottom",
    "pants": "bottom", "quần": "bottom", "skirt": "bottom", "váy ngắn": "bottom", "shirt": "top", "top": "top", "áo": "top",
}


def _safe_stem(filename: str) -> str:
    stem = Path(filename).stem.lower()
    cleaned = re.sub(r"[^a-z0-9_-]+", "-", stem).strip("-")
    return cleaned or "garment"


def _validate_image(filename: str, content: bytes, content_type: str | None) -> tuple[str, str]:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError("Unsupported file extension; use JPG, JPEG, PNG, or WEBP")
    if not (content_type or "").startswith("image/"):
        raise ValueError("Content type must be an image")
    if not content:
        raise ValueError("Garment image is empty")
    if len(content) > 10 * 1024 * 1024:
        raise ValueError("Garment image exceeds the 10 MB local import limit")
    try:
        with Image.open(BytesIO(content)) as image:
            detected_format = image.format
            width, height = image.size
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise ValueError("Uploaded content is not a valid image") from error
    if detected_format not in FORMAT_TO_MIME:
        raise ValueError("Unsupported decoded image format; use JPG, PNG, or WEBP")
    if content_type != FORMAT_TO_MIME[detected_format]:
        raise ValueError("File MIME type does not match decoded image format")
    expected_suffixes = {"JPEG": {".jpg", ".jpeg"}, "PNG": {".png"}, "WEBP": {".webp"}}
    if suffix not in expected_suffixes[detected_format]:
        raise ValueError("File extension does not match decoded image format")
    if width * height > 20_000_000:
        raise ValueError("Garment image exceeds the 20 megapixel local import limit")
    return suffix, detected_format


def _select_category(filename: str, supplied_category: str | None) -> tuple[str, bool, list[str]]:
    valid_categories = {"top", "bottom", "dress", "outerwear", "footwear", "belt", "accessory"}
    if supplied_category is not None and supplied_category not in valid_categories:
        raise ValueError(f"Unsupported garment category: {supplied_category}")
    if supplied_category in valid_categories:
        return supplied_category, False, []
    lowered = filename.lower()
    for keyword, category in CATEGORY_KEYWORDS.items():
        if keyword in lowered:
            return category, False, ["Category inferred from filename; confirm before using for production fitting."]
    return "top", True, ["No reliable local visual classifier is enabled; defaulted to top.", "A single image cannot determine hidden geometry, construction, or physical fabric properties."]


def _select_template(category: str):
    candidates = [garment for garment in list_active_garments() if garment.category == category]
    if not candidates:
        raise ValueError(f"No active canonical garment template exists for category {category}")
    return candidates[0]


def _render_binding(category: str) -> dict[str, float | str]:
    bindings: dict[str, dict[str, float | str]] = {
        "top": {"anchor": "chest", "y_offset": 0.18, "scale_x": 1.0, "scale_y": 1.0, "scale_z": 1.04},
        "bottom": {"anchor": "hip", "y_offset": -0.55, "scale_x": 1.04, "scale_y": 1.0, "scale_z": 1.04},
        "dress": {"anchor": "waist", "y_offset": -0.15, "scale_x": 1.03, "scale_y": 1.2, "scale_z": 1.05},
        "outerwear": {"anchor": "shoulder", "y_offset": 0.1, "scale_x": 1.1, "scale_y": 1.05, "scale_z": 1.12},
        "belt": {"anchor": "waist", "y_offset": -0.25, "scale_x": 1.05, "scale_y": 1.0, "scale_z": 1.08},
        "footwear": {"anchor": "left_foot", "y_offset": -1.45, "scale_x": 1.0, "scale_y": 1.0, "scale_z": 1.0},
        "accessory": {"anchor": "chest", "y_offset": 0.1, "scale_x": 1.0, "scale_y": 1.0, "scale_z": 1.0},
    }
    return bindings[category]


def write_manifest(manifest: GarmentImportManifestV1) -> None:
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    (MANIFEST_DIR / f"{manifest.import_id}.json").write_text(manifest.model_dump_json(indent=2), encoding="utf-8")


def import_garment_image(filename: str, content: bytes, content_type: str | None, category: str | None = None) -> GarmentImportManifestV1:
    suffix, _ = _validate_image(filename, content, content_type)
    GARMENT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(content).hexdigest()
    import_id = f"imp_{uuid4().hex[:12]}"
    stored_name = f"{import_id}_{_safe_stem(filename)}{suffix}"
    (GARMENT_UPLOAD_DIR / stored_name).write_bytes(content)

    inferred_category, needs_review, limitations = _select_category(filename, category)
    canonical = _select_template(inferred_category)
    now = datetime.now(timezone.utc)
    manifest = GarmentImportManifestV1(
        import_id=import_id,
        source_image_uri=f"/uploads/garments/{stored_name}",
        source_image_sha256=digest,
        analysis=GarmentImageAnalysisV1(
            category=inferred_category,
            confidence=0.95 if category else (0.65 if not needs_review else 0.25),
            color_hint=None,
            silhouette_hint=canonical.silhouette,
            needs_human_review=needs_review,
            limitations=limitations,
        ),
        selected_template_id=canonical.asset.template_id,
        selected_garment_id=canonical.garment_id,
        target_skeleton_id="mixamo-humanoid-v1",
        rest_pose=canonical.asset.rest_pose,
        rig_status="canonical_proxy",
        conversion_backend="canonical_proxy",
        render_binding=_render_binding(inferred_category),
        generated_asset_uri=canonical.asset.asset_uri,
        reconstruction=ReconstructionStateV1(pipeline_state="imported", updated_at=now),
        created_at=now,
    )
    write_manifest(manifest)
    return manifest


def analyze_garment_import_semantics(import_id: str) -> GarmentImportManifestV1:
    manifest = read_manifest(import_id)
    if manifest is None:
        raise ValueError(f"Garment import manifest not found: {import_id}")
    manifest.analysis.semantic_tagging = analyze_import_for_semantic_tags(manifest)
    manifest.analysis.needs_human_review = True
    if "Semantic tag review is required before image-derived metadata can influence outfit ranking." not in manifest.analysis.limitations:
        manifest.analysis.limitations.append("Semantic tag review is required before image-derived metadata can influence outfit ranking.")
    write_manifest(manifest)
    return manifest


def read_manifest(import_id: str) -> GarmentImportManifestV1 | None:
    path = MANIFEST_DIR / f"{import_id}.json"
    if not path.exists():
        return None
    try:
        return GarmentImportManifestV1.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, ValueError) as error:
        raise MalformedGarmentManifestError(f"Garment import manifest is malformed: {import_id}") from error
