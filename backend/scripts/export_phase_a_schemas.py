import json
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.phase_a_schemas import GarmentMetadataV1, OutfitDecisionRequestV1, OutfitDecisionResponseV1, ParametricBodyContractV1

OUTPUT_DIR = BACKEND_DIR / "contracts"
OUTPUT_DIR.mkdir(exist_ok=True)

SCHEMAS = {
    "parametric_body_contract_v1.schema.json": ParametricBodyContractV1,
    "garment_metadata_v1.schema.json": GarmentMetadataV1,
    "outfit_decision_request_v1.schema.json": OutfitDecisionRequestV1,
    "outfit_decision_response_v1.schema.json": OutfitDecisionResponseV1,
}

for filename, model in SCHEMAS.items():
    schema = model.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = f"https://ai-3d-stylist.local/contracts/{filename}"
    (OUTPUT_DIR / filename).write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
