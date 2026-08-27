import json
from functools import lru_cache
from pathlib import Path

from ..phase_a_schemas import GarmentMetadataV1


CATALOG_PATH = Path(__file__).resolve().parents[2] / "data" / "canonical_garments_v1.json"


@lru_cache(maxsize=1)
def load_catalog() -> tuple[str, dict[str, GarmentMetadataV1]]:
    with CATALOG_PATH.open(encoding="utf-8") as catalog_file:
        payload = json.load(catalog_file)
    catalog = {
        item["garment_id"]: GarmentMetadataV1.model_validate(item)
        for item in payload["garments"]
        if item.get("status") == "active"
    }
    return payload["catalog_version"], catalog


def list_active_garments() -> list[GarmentMetadataV1]:
    _, catalog = load_catalog()
    return list(catalog.values())


def get_garment(garment_id: str) -> GarmentMetadataV1 | None:
    _, catalog = load_catalog()
    return catalog.get(garment_id)
