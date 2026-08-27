import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.workflow_schemas import (
    BodyProfileRevisionV1,
    CreateBodyProfileCommandV1,
    CreateStylingSessionCommandV1,
    CreateWardrobeAssetCommandV1,
    OutfitDecisionRunV1,
    RequestTryOnCommandV1,
    StylingSessionV1,
    TryOnRunV1,
    WardrobeAssetRevisionV1,
)

OUTPUT_DIR = BACKEND_DIR / "contracts"
OUTPUT_DIR.mkdir(exist_ok=True)

SCHEMAS = {
    "workflow_create_body_profile_command_v1.schema.json": CreateBodyProfileCommandV1,
    "workflow_body_profile_revision_v1.schema.json": BodyProfileRevisionV1,
    "workflow_create_wardrobe_asset_command_v1.schema.json": CreateWardrobeAssetCommandV1,
    "workflow_wardrobe_asset_revision_v1.schema.json": WardrobeAssetRevisionV1,
    "workflow_create_styling_session_command_v1.schema.json": CreateStylingSessionCommandV1,
    "workflow_styling_session_v1.schema.json": StylingSessionV1,
    "workflow_outfit_decision_run_v1.schema.json": OutfitDecisionRunV1,
    "workflow_request_try_on_command_v1.schema.json": RequestTryOnCommandV1,
    "workflow_try_on_run_v1.schema.json": TryOnRunV1,
}

for filename, model in SCHEMAS.items():
    schema = model.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = f"https://ai-3d-stylist.local/contracts/{filename}"
    (OUTPUT_DIR / filename).write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
