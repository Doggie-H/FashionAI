import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.phase_b_schemas import (
    GarmentImportManifestV1,
    MeshQualityGateV1,
    ReconstructionStartResponseV1,
    SegmentationArtifactV1,
)

OUTPUT_DIR = BACKEND_DIR / "contracts"
OUTPUT_DIR.mkdir(exist_ok=True)

SCHEMAS = {
    "phase_c_garment_import_manifest_v1.schema.json": GarmentImportManifestV1,
    "phase_c_segmentation_artifact_v1.schema.json": SegmentationArtifactV1,
    "phase_c_mesh_quality_gate_v1.schema.json": MeshQualityGateV1,
    "phase_c_reconstruction_start_response_v1.schema.json": ReconstructionStartResponseV1,
}

for filename, model in SCHEMAS.items():
    schema = model.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = f"https://ai-3d-stylist.local/contracts/{filename}"
    (OUTPUT_DIR / filename).write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
