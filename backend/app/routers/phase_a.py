from fastapi import APIRouter, HTTPException, Query

from ..phase_a_schemas import (
    OutfitDecisionRequestV1,
    OutfitDecisionResponseV1,
    ParametricBodyContractV1,
    RawMeasurementsV1,
)
from ..services.body_contract import build_parametric_body_contract
from ..services.garment_catalog import get_garment, list_active_garments
from ..services.outfit_decision_engine import decide_outfits


router = APIRouter(prefix="/phase-a", tags=["virtual try-on phase a"])


@router.post("/body-contract", response_model=ParametricBodyContractV1)
def create_body_contract(measurements: RawMeasurementsV1):
    return build_parametric_body_contract(measurements)


@router.get("/catalog")
def list_catalog(category: str | None = Query(default=None)):
    garments = list_active_garments()
    if category:
        garments = [garment for garment in garments if garment.category == category]
    return {"catalog_version": "1.0.0-seed", "garments": garments}


@router.get("/catalog/{garment_id}")
def read_garment(garment_id: str):
    garment = get_garment(garment_id)
    if garment is None:
        raise HTTPException(status_code=404, detail="Garment not found in active catalog")
    return garment


@router.post("/outfit-decisions", response_model=OutfitDecisionResponseV1)
def create_outfit_decision(request: OutfitDecisionRequestV1):
    return decide_outfits(request)
