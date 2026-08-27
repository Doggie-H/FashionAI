from datetime import datetime, timezone

from ..phase_a_schemas import (
    BoneLengthScalesV1,
    ParametricBodyContractV1,
    RawMeasurementsV1,
    ShapeParametersV1,
)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return round(max(minimum, min(maximum, value)), 4)


def build_parametric_body_contract(measurements: RawMeasurementsV1) -> ParametricBodyContractV1:
    """Derive stable prototype avatar parameters from user-supplied measurements.

    This is a visual calibration contract, not medical assessment or exact tailoring.
    """
    shape = ShapeParametersV1(
        height_scale=_clamp(measurements.height_cm / 170, 0.8, 1.2),
        shoulder_scale=_clamp(measurements.shoulder_cm / 42, 0.7, 1.35),
        chest_scale=_clamp(measurements.bust_cm / 88, 0.7, 1.35),
        waist_scale=_clamp(measurements.waist_cm / 72, 0.65, 1.4),
        hip_scale=_clamp(measurements.hip_cm / 94, 0.7, 1.4),
        leg_scale=_clamp(measurements.inseam_cm / 78, 0.8, 1.2),
    )
    leg_length_scale = _clamp(measurements.inseam_cm / 78, 0.8, 1.2)
    torso_length_scale = _clamp((measurements.height_cm - measurements.inseam_cm) / 92, 0.8, 1.2)
    flags: list[str] = []
    if measurements.shoulder_slope == "sloped":
        flags.append("sloped_shoulders")
    if measurements.chest_profile == "flat":
        flags.append("flat_chest_profile")
    if measurements.leg_alignment == "bowed":
        flags.append("bowed_leg_alignment")

    return ParametricBodyContractV1(
        measurements=measurements,
        shape_parameters=shape,
        bone_length_scales=BoneLengthScalesV1(
            spine=torso_length_scale,
            upper_arm=_clamp(measurements.height_cm / 170, 0.8, 1.2),
            lower_arm=_clamp(measurements.height_cm / 170, 0.8, 1.2),
            upper_leg=leg_length_scale,
            lower_leg=leg_length_scale,
        ),
        visual_flags=flags,
        generated_at=datetime.now(timezone.utc),
    )
