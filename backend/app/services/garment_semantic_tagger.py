"""Review-gated semantic tagging for a garment import.

This module deliberately keeps VLM perception separate from wardrobe activation and
outfit ranking. A suggestion is persisted in the import manifest; only the approved
snapshot is used in a StylingSession.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..phase_a_schemas import GarmentMetadataV1
from ..phase_b_schemas import (
    GarmentImportManifestV1,
    GarmentSemanticTaggingV1,
    GarmentStructuralProfileV1,
    SemanticTagEvidenceV1,
    StructuralEvidenceV1,
)
from .garment_catalog import get_garment


_SUPPORTED_PROVIDER = "qwen25vl"
_MOCK_PROVIDER = "mock"
_LIST_DIMENSIONS: dict[str, set[str]] = {
    "styles": {"minimal", "classic", "smart_casual", "streetwear", "romantic", "business", "sporty", "quiet_luxury", "preppy", "edgy", "bohemian", "athleisure", "utility", "modest", "resort", "creative", "vintage"},
    "occasions": {"daily", "work", "date", "event", "travel", "formal", "interview", "meeting", "presentation", "celebration", "weekend", "gym", "outdoor", "home", "cocktail", "wedding_guest"},
    "seasons": {"spring", "summer", "autumn", "winter", "all_season"},
    "weather_suitability": {"hot", "mild", "cold", "rainy", "humid"},
    "intent_support": {"comfort", "all_day", "weather_protection", "photo_ready", "low_maintenance", "packable", "movement", "coverage", "professional_presence", "celebration", "confidence"},
    "pairing_hints": {"minimal", "classic", "smart_casual", "streetwear", "romantic", "business", "sporty", "quiet_luxury", "preppy", "edgy", "bohemian", "athleisure", "utility", "modest", "resort", "creative", "vintage"},
    "avoid_pairing_with": {"minimal", "classic", "smart_casual", "streetwear", "romantic", "business", "sporty", "quiet_luxury", "preppy", "edgy", "bohemian", "athleisure", "utility", "modest", "resort", "creative", "vintage"},
}
_STRUCTURAL_VALUES: dict[str, set[str]] = {
    "neckline": {"crew", "v_neck", "round", "collar", "polo", "halter", "strapless", "unknown"},
    "shoulder_construction": {"set_in", "dropped", "raglan", "sleeveless", "unknown"},
    "shoulder_width": {"narrow", "regular", "wide", "unknown"},
    "sleeve_length": {"sleeveless", "cap", "short", "elbow", "long", "unknown"},
    "torso_length": {"cropped", "waist", "hip", "long", "unknown"},
    "waist_shape": {"fitted", "regular", "relaxed", "peplum", "unknown"},
    "hem_shape": {"straight", "curved", "asymmetric", "unknown"},
    "rise": {"low", "mid", "high", "unknown"},
    "waist_construction": {"flat", "elastic", "belted", "unknown"},
    "hip_fit": {"fitted", "regular", "relaxed", "unknown"},
    "leg_shape": {"skinny", "slim", "straight", "tapered", "wide", "bootcut", "flared", "unknown"},
    "leg_length": {"short", "cropped", "ankle", "full", "unknown"},
}
_STRUCTURAL_VIEWS = {"front", "side", "back", "detail", "unknown"}

_SCALAR_DIMENSIONS: dict[str, set[str]] = {
    "category": {"top", "bottom", "dress", "outerwear", "footwear", "belt", "accessory"},
    "color_family": {"neutral", "black", "white", "navy", "earth", "burgundy", "emerald", "bright"},
    "formality_level": {"casual", "smart_casual", "business", "formal", "ceremonial"},
    "statement_level": {"subtle", "balanced", "statement"},
    "mobility_support": {"low", "normal", "high"},
    "modesty_level": {"standard", "covered", "conservative"},
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _source_path(manifest: GarmentImportManifestV1) -> Path:
    return _project_root() / manifest.source_image_uri.lstrip("/")


def _clean_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3].rstrip()
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("Vision provider did not return a JSON object")
    return payload


def _confidence(payload: dict[str, Any], dimension: str) -> float:
    source = payload.get("confidence", {})
    value = source.get(dimension, 0.45) if isinstance(source, dict) else source
    if isinstance(value, (int, float)) and 0 <= float(value) <= 1:
        return round(float(value), 3)
    return 0.45


def _rationale(payload: dict[str, Any], dimension: str) -> str:
    rationales = payload.get("rationales", {})
    value = rationales.get(dimension) if isinstance(rationales, dict) else None
    if isinstance(value, str) and value.strip():
        return value.strip()[:360]
    return "Model prediction from visible image cues; requires human confirmation."


def _valid_list(payload: dict[str, Any], dimension: str, limitations: list[str]) -> list[str] | None:
    value = payload.get(dimension)
    if not isinstance(value, list):
        return None
    allowed = _LIST_DIMENSIONS[dimension]
    accepted = [item for item in value if isinstance(item, str) and item in allowed]
    if len(accepted) != len(value):
        limitations.append(f"Some {dimension} labels were outside the closed taxonomy and were ignored.")
    return list(dict.fromkeys(accepted))[:8] or None


def _valid_scalar(payload: dict[str, Any], dimension: str, limitations: list[str]) -> str | None:
    value = payload.get(dimension)
    if not isinstance(value, str):
        return None
    if value not in _SCALAR_DIMENSIONS[dimension]:
        limitations.append(f"{dimension} was outside the closed taxonomy and was ignored.")
        return None
    return value


def _structural_profile(payload: dict[str, Any], limitations: list[str]) -> GarmentStructuralProfileV1 | None:
    raw = payload.get("structural_profile")
    if not isinstance(raw, dict):
        return None
    source_views_raw = raw.get("source_views", ["front"])
    source_views = [item for item in source_views_raw if isinstance(item, str) and item in _STRUCTURAL_VIEWS] if isinstance(source_views_raw, list) else ["front"]
    if not source_views:
        source_views = ["unknown"]
        limitations.append("Structural source views were invalid; visibility is unknown.")
    normalized: dict[str, Any] = {"source_views": source_views}
    for feature, allowed in _STRUCTURAL_VALUES.items():
        value = raw.get(feature, "unknown")
        if not isinstance(value, str) or value not in allowed:
            if value not in {None, "unknown"}:
                limitations.append(f"Structural {feature} was outside the closed taxonomy and was ignored.")
            normalized[feature] = "unknown"
        else:
            normalized[feature] = value
    evidence: list[StructuralEvidenceV1] = []
    raw_evidence = payload.get("structural_evidence", [])
    if isinstance(raw_evidence, list):
        for item in raw_evidence[:12]:
            if not isinstance(item, dict):
                continue
            feature = item.get("feature")
            value = item.get("value")
            confidence = item.get("confidence", 0.45)
            rationale = item.get("rationale")
            views = item.get("visible_views", source_views)
            if feature not in _STRUCTURAL_VALUES or not isinstance(value, str) or value not in _STRUCTURAL_VALUES[feature]:
                limitations.append("A structural evidence entry was outside the closed taxonomy and was ignored.")
                continue
            if not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
                confidence = 0.45
            safe_views = [view for view in views if isinstance(view, str) and view in _STRUCTURAL_VIEWS] if isinstance(views, list) else source_views
            evidence.append(StructuralEvidenceV1(
                feature=feature,
                value=value,
                confidence=round(float(confidence), 3),
                visible_views=safe_views or ["unknown"],
                rationale=str(rationale or "Visible image cue only; requires human confirmation.")[:360],
            ))
    normalized["evidence"] = evidence
    raw_limitations = raw.get("limitations", [])
    normalized["limitations"] = [item.strip()[:280] for item in raw_limitations if isinstance(item, str) and item.strip()][:12] if isinstance(raw_limitations, list) else []
    profile = GarmentStructuralProfileV1.model_validate(normalized)
    if any(getattr(profile, feature) != "unknown" for feature in _STRUCTURAL_VALUES):
        profile.limitations = list(dict.fromkeys([
            *profile.limitations,
            "Structural profile describes visible 2D cues only; it does not establish back panels, thickness, sewing pattern, measurements, or physical 3D fit.",
        ]))[:12]
    return profile


def _unavailable(manifest: GarmentImportManifestV1, reason: str) -> GarmentSemanticTaggingV1:
    return GarmentSemanticTaggingV1(
        status="unavailable",
        provider="disabled",
        source_image_sha256=manifest.source_image_sha256,
        limitations=[reason, "No semantic tag is eligible for ranking until a reviewer approves an analyzed metadata snapshot."],
        analyzed_at=_now(),
    )


def _qwen_preflight(manifest: GarmentImportManifestV1) -> tuple[str | None, str | None, str | None]:
    model_id = os.getenv("QWEN_VL_MODEL_ID")
    model_revision = os.getenv("QWEN_VL_MODEL_REVISION")
    if not model_id or not model_revision:
        return None, None, "Qwen model ID and immutable model revision must be configured privately before semantic tagging."
    try:
        import torch
    except ImportError:
        return None, None, "PyTorch is not installed in the tagging worker environment."
    if not torch.cuda.is_available():
        return None, None, "Qwen semantic tagging requires a CUDA worker; no CUDA device is available."
    minimum_vram_gb = float(os.getenv("GARMENT_TAGGER_MIN_VRAM_GB", "8"))
    vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
    if vram_gb < minimum_vram_gb:
        return None, None, f"Qwen semantic tagging requires at least {minimum_vram_gb:g} GB VRAM; detected {vram_gb:.1f} GB."
    if not _source_path(manifest).is_file():
        return None, None, "The original garment image is unavailable for semantic tagging."
    return model_id, model_revision, None


def _build_candidate_metadata(manifest: GarmentImportManifestV1, payload: dict[str, Any], model_id: str, model_revision: str) -> GarmentSemanticTaggingV1:
    canonical = get_garment(manifest.selected_garment_id)
    if canonical is None:
        raise ValueError("Selected canonical garment is missing from the active catalog")

    limitations = [
        "Predicted attributes describe visible image cues only; hidden construction, exact fabric, size, and physical fit are not established.",
        "This metadata is a draft and cannot affect ranking until a garment_metadata reviewer approval is recorded.",
    ]
    updates: dict[str, Any] = {
        "garment_id": f"gar_user_{manifest.import_id.removeprefix('imp_')}",
        "name": f"{canonical.name} — user import {manifest.import_id}",
        "category": manifest.analysis.category,
        "source": "user_import",
        "status": "draft",
    }
    evidence: list[SemanticTagEvidenceV1] = []

    predicted_category = _valid_scalar(payload, "category", limitations)
    if predicted_category:
        evidence.append(SemanticTagEvidenceV1(
            dimension="category", values=[predicted_category], confidence=_confidence(payload, "category"),
            rationale=_rationale(payload, "category"),
        ))
        if predicted_category != manifest.analysis.category:
            limitations.append("Vision category differs from the import category; a reviewer must resolve the category before activation.")

    for dimension in _LIST_DIMENSIONS:
        values = _valid_list(payload, dimension, limitations)
        if values:
            updates[dimension] = values
            evidence.append(SemanticTagEvidenceV1(
                dimension=dimension, values=values, confidence=_confidence(payload, dimension),
                rationale=_rationale(payload, dimension),
            ))

    for dimension in _SCALAR_DIMENSIONS:
        if dimension == "category":
            continue
        value = _valid_scalar(payload, dimension, limitations)
        if value:
            updates[dimension] = value
            evidence.append(SemanticTagEvidenceV1(
                dimension=dimension, values=[value], confidence=_confidence(payload, dimension),
                rationale=_rationale(payload, dimension),
            ))

    for text_dimension in ("material", "silhouette"):
        value = payload.get(text_dimension)
        if isinstance(value, str) and 2 <= len(value.strip()) <= 120:
            updates[text_dimension] = value.strip()
            evidence.append(SemanticTagEvidenceV1(
                dimension=text_dimension, values=[value.strip()], confidence=_confidence(payload, text_dimension),
                rationale=_rationale(payload, text_dimension),
            ))

    raw_limitations = payload.get("limitations")
    if isinstance(raw_limitations, list):
        limitations.extend(item.strip()[:280] for item in raw_limitations if isinstance(item, str) and item.strip())

    metadata = GarmentMetadataV1.model_validate({**canonical.model_dump(mode="json"), **updates})
    structural_profile = _structural_profile(payload, limitations)
    return GarmentSemanticTaggingV1(
        status="needs_review",
        provider=_SUPPORTED_PROVIDER,
        model_id=model_id,
        model_revision=model_revision,
        source_image_sha256=manifest.source_image_sha256,
        candidate_metadata=metadata,
        structural_profile=structural_profile,
        evidence=evidence,
        limitations=list(dict.fromkeys(limitations))[:12],
        analyzed_at=_now(),
    )


def analyze_import_for_semantic_tags(manifest: GarmentImportManifestV1) -> GarmentSemanticTaggingV1:
    """Run an explicitly configured VLM and return a non-authoritative draft metadata snapshot."""
    provider = os.getenv("GARMENT_TAGGER_PROVIDER", "disabled").strip().lower()
    if provider == "disabled":
        return _unavailable(manifest, "No garment semantic VLM provider is configured.")
    if provider == _MOCK_PROVIDER:
        payload = {
            "category": manifest.analysis.category,
            "styles": ["minimal", "classic", "smart_casual"],
            "occasions": ["daily", "weekend", "work"],
            "seasons": ["spring", "summer", "all_season"],
            "color_family": "navy",
            "material": "visible jersey knit (mock fixture)",
            "silhouette": "regular short-sleeve crew-neck top",
            "formality_level": "smart_casual",
            "statement_level": "subtle",
            "weather_suitability": ["hot", "mild"],
            "mobility_support": "high",
            "modesty_level": "standard",
            "intent_support": ["comfort", "all_day", "movement", "low_maintenance"],
            "pairing_hints": ["minimal", "classic", "smart_casual"],
            "avoid_pairing_with": [],
            "structural_profile": {
                "source_views": ["front"],
                "neckline": "crew",
                "shoulder_construction": "set_in",
                "shoulder_width": "regular",
                "sleeve_length": "short",
                "torso_length": "hip",
                "waist_shape": "regular",
                "hem_shape": "straight",
                "rise": "unknown",
                "waist_construction": "unknown",
                "hip_fit": "unknown",
                "leg_shape": "unknown",
                "leg_length": "unknown",
                "limitations": ["Fixture only supplies a front view; back construction and exact garment measurements are unknown."],
            },
            "structural_evidence": [
                {"feature": "neckline", "value": "crew", "confidence": 0.96, "visible_views": ["front"], "rationale": "Mock fixture contains a round crew neckline opening."},
                {"feature": "shoulder_construction", "value": "set_in", "confidence": 0.9, "visible_views": ["front"], "rationale": "Mock fixture depicts a sleeve seam emerging from the shoulder area."},
                {"feature": "sleeve_length", "value": "short", "confidence": 0.98, "visible_views": ["front"], "rationale": "Mock fixture depicts sleeves ending above the elbow."},
                {"feature": "torso_length", "value": "hip", "confidence": 0.82, "visible_views": ["front"], "rationale": "Mock fixture hem reaches a hip-length reference zone."},
                {"feature": "waist_shape", "value": "regular", "confidence": 0.76, "visible_views": ["front"], "rationale": "Mock fixture silhouette is neither visibly cinched nor oversized."},
            ],
            "confidence": {"category": 0.99, "styles": 0.91, "occasions": 0.87, "material": 0.65},
            "rationales": {
                "category": "Mock fixture is declared as a T-shirt top for deterministic scenario coverage.",
                "styles": "Mock fixture uses a clean regular silhouette and low-contrast navy color.",
                "occasions": "Mock scenario encodes a versatile casual-to-workwear T-shirt profile.",
            },
            "limitations": ["Mock provider output is deterministic test data, not visual inference from this image."],
        }
        tagging = _build_candidate_metadata(manifest, payload, "ai-stylist/mock-garment-tagger", "fixture-v1")
        tagging.provider = _MOCK_PROVIDER
        if tagging.candidate_metadata:
            tagging.candidate_metadata.name = "Mock navy T-shirt fixture"
        return tagging
    if provider != _SUPPORTED_PROVIDER:
        return _unavailable(manifest, f"Unsupported garment semantic VLM provider: {provider}.")

    model_id, model_revision, reason = _qwen_preflight(manifest)
    if reason:
        return _unavailable(manifest, reason)
    assert model_id is not None and model_revision is not None
    try:
        from ai_training.qwen_vl_adapter import Qwen25VLAdapter

        adapter = Qwen25VLAdapter(model_id=model_id, model_revision=model_revision)
        adapter.load_model()
        payload = _clean_json(adapter.analyze_garment_for_styling(str(_source_path(manifest))))
        return _build_candidate_metadata(manifest, payload, model_id, model_revision)
    except Exception as error:
        return GarmentSemanticTaggingV1(
            status="failed",
            provider=_SUPPORTED_PROVIDER,
            model_id=model_id,
            model_revision=model_revision,
            source_image_sha256=manifest.source_image_sha256,
            limitations=["No VLM prediction was accepted; the asset remains review-gated and is not eligible for ranking."],
            failure_reason=str(error)[:500],
            analyzed_at=_now(),
        )
