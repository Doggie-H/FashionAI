from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from PIL import Image

from ..phase_b_schemas import GarmentImportManifestV1, SegmentationArtifactV1


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SEGMENT_DIR = PROJECT_ROOT / "uploads" / "garment_segments"


def _source_path(manifest: GarmentImportManifestV1) -> Path:
    return PROJECT_ROOT / manifest.source_image_uri.lstrip("/")


def segment_garment(manifest: GarmentImportManifestV1) -> SegmentationArtifactV1:
    """Create a normalized RGBA garment image.

    Uses rembg if explicitly installed. Otherwise preserves the source alpha channel and
    marks the result unverified; this is safe for contract testing but not garment masking quality.
    """
    source = _source_path(manifest)
    if not source.exists():
        raise FileNotFoundError("Garment source image is missing")
    original = source.read_bytes()
    provider = "alpha_fallback"
    limitations = ["Background segmentation model is unavailable; alpha fallback does not isolate the garment."]
    output = original
    try:
        from rembg import remove
        output = remove(original)
        provider = "rembg"
        limitations = []
    except ImportError:
        pass

    with Image.open(BytesIO(output)) as image:
        rgba = image.convert("RGBA")
        has_transparency = rgba.getchannel("A").getextrema()[0] < 255
        SEGMENT_DIR.mkdir(parents=True, exist_ok=True)
        output_name = f"{manifest.import_id}.png"
        destination = SEGMENT_DIR / output_name
        rgba.save(destination, format="PNG", optimize=True)

    return SegmentationArtifactV1(
        provider=provider,
        asset_uri=f"/uploads/garment_segments/{output_name}",
        has_transparency=has_transparency,
        quality="verified" if provider == "rembg" and has_transparency else "unverified",
        limitations=limitations,
        completed_at=datetime.now(timezone.utc),
    )
