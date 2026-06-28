from __future__ import annotations

import math
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class CTPBoltGeometry:
    type_code: str
    size_code: str
    thread_diameter_mm: float
    pitch_mm: float
    pcd_mm: float
    screw_count: int
    shank_diameter_mm: float
    groove_diameter_mm: float
    contact_diameter_mm: float
    thread_type: str = "Machined"
    shear_plane: str = "Thread"
    leverarm_mm: float = 0.05


@dataclass(frozen=True)
class CTPMaterial:
    code: str
    yield_strength_mpa: float


@dataclass(frozen=True)
class CTPFrictionSettings:
    screw_nut_label: str
    screw_nut_mu: float
    nut_part_label: str
    nut_part_mu: float
    part_part_label: str
    part_part_mu: float


@dataclass(frozen=True)
class CTPInputs:
    reference: str
    geometry: CTPBoltGeometry
    material: CTPMaterial
    friction: CTPFrictionSettings
    continuous_torque_nm: float
    peak_factor: float = 2.0
    momentary_factor: float = 1.15
    tightening_torque_nm: float | None = None
    preload_percent_of_yield: float | None = None
    standard_tightening_torque_nm: float | None = None
    sleeve_outer_diameter_mm: float = 0.0
    sleeve_yield_strength_mpa: float = 640.0
    thread_engagement_mm: float | None = None


@dataclass(frozen=True)
class StatusValue:
    value: float | None
    status: str

    @property
    def is_numeric(self) -> bool:
        return self.value is not None and math.isfinite(self.value)


@dataclass(frozen=True)
class TorqueCaseResult:
    name: str
    torque_nm: float
    friction_torque_nm: float
    torque_ratio: StatusValue
    residual_torque_nm: float
    residual_shear_load_n: float
    sleeve_shear_load_n: float
    sleeve_von_mises_mpa: float
    sleeve_safety_factor: StatusValue
    bolt_shear_load_n: float
    bolt_axial_stress_mpa: float
    bolt_bending_stress_mpa: float
    bolt_shear_stress_mpa: float
    bolt_von_mises_mpa: float
    bolt_safety_factor: StatusValue


@dataclass(frozen=True)
class CTPResult:
    inputs: CTPInputs
    thread_diameter_mm: float
    pitch_mm: float
    pitch_diameter_mm: float
    thread_root_diameter_mm: float
    tensile_stress_diameter_mm: float
    tensile_stress_area_mm2: float
    shear_bending_diameter_mm: float
    groove_diameter_mm: float
    contact_diameter_mm: float
    average_nut_radius_mm: float
    preload_n: float
    tightening_torque_nm: float
    nut_friction_torque_nm: float
    thread_tightening_torque_nm: float
    friction_torque_nm: float
    cases: tuple[TorqueCaseResult, ...]
    groove_axial_stress: StatusValue
    groove_twist_stress: StatusValue
    groove_von_mises_stress: StatusValue
    groove_safety_factor: StatusValue
    thread_root_axial_stress_mpa: float
    thread_root_twist_stress_mpa: float
    thread_root_von_mises_mpa: float
    thread_root_safety_factor: StatusValue
    min_thread_engagement_mm: float
    engaged_thread_count: float
    thread_pullout_area_mm2: float
    first_thread_pullout_stress_mpa: float
    minimum_safety_factor: float | None
    check_summary: str
    warnings: tuple[str, ...]

    def case(self, name: str) -> TorqueCaseResult:
        for item in self.cases:
            if item.name == name:
                return item
        raise ValueError(f"Unknown torque case: {name}")


@dataclass(frozen=True)
class SolverResult:
    converged: bool
    value: float | None
    iterations: int
    message: str
    result: CTPResult | None = None


def calculate_ctp(inputs: CTPInputs) -> CTPResult:
    _validate_inputs(inputs)
    geometry = inputs.geometry
    material = inputs.material
    friction = inputs.friction

    thread_diameter = geometry.thread_diameter_mm
    pitch = geometry.pitch_mm
    pitch_diameter = thread_diameter - 0.6495 * pitch
    thread_root_diameter = thread_diameter - 1.2268 * pitch
    tensile_stress_diameter = (pitch_diameter + thread_root_diameter) / 2.0
    tensile_stress_area = ((pitch_diameter + thread_root_diameter) / 4.0) ** 2 * math.pi

    shear_bending_diameter = (
        geometry.shank_diameter_mm
        if geometry.shear_plane == "Shank"
        else tensile_stress_diameter
    )
    groove_diameter = max(0.0, geometry.groove_diameter_mm)
    contact_diameter = geometry.contact_diameter_mm
    average_nut_radius = _annulus_effective_radius(
        pitch_diameter / 2.0,
        contact_diameter / 2.0,
    )
    denominator = (
        0.16 * pitch
        + 0.583 * friction.screw_nut_mu * pitch_diameter
        + friction.nut_part_mu * average_nut_radius
    )

    if inputs.tightening_torque_nm is not None and inputs.tightening_torque_nm != 0:
        preload = 1000.0 * inputs.tightening_torque_nm / denominator
        tightening_torque = inputs.tightening_torque_nm
    elif (
        inputs.preload_percent_of_yield is not None
        and inputs.preload_percent_of_yield != 0
    ):
        preload = (
            inputs.preload_percent_of_yield
            * tensile_stress_area
            * material.yield_strength_mpa
            / 100.0
        )
        tightening_torque = denominator * preload / 1000.0
    elif inputs.standard_tightening_torque_nm is not None:
        preload = 1000.0 * inputs.standard_tightening_torque_nm / denominator
        tightening_torque = inputs.standard_tightening_torque_nm
    else:
        preload = 0.0
        tightening_torque = 0.0

    nut_friction_torque = friction.nut_part_mu * average_nut_radius * preload / 1000.0
    thread_tightening_torque = (
        0.16 * pitch + 0.583 * friction.screw_nut_mu * pitch_diameter
    ) * preload / 1000.0
    friction_torque = (
        preload
        * geometry.screw_count
        * friction.part_part_mu
        * geometry.pcd_mm
        / 2.0
        / 1000.0
    )

    continuous_torque = inputs.continuous_torque_nm
    peak_torque = continuous_torque * inputs.peak_factor
    momentary_torque = peak_torque * inputs.momentary_factor
    cases = tuple(
        _calculate_case(
            name,
            torque,
            inputs,
            preload,
            friction_torque,
            shear_bending_diameter,
        )
        for name, torque in (
            ("continuous", continuous_torque),
            ("peak", peak_torque),
            ("momentary", momentary_torque),
        )
    )

    groove_axial, groove_twist, groove_von_mises, groove_sf = _calculate_groove(
        groove_diameter,
        preload,
        thread_tightening_torque,
        material.yield_strength_mpa,
    )
    thread_root_axial = preload / tensile_stress_area
    thread_root_twist = (
        thread_tightening_torque
        * 1000.0
        * thread_root_diameter
        / 2.0
        / (math.pi / 32.0 * thread_root_diameter**4)
    )
    thread_root_von_mises = math.sqrt(thread_root_axial**2 + 3.0 * thread_root_twist**2)
    thread_root_sf = StatusValue(
        _safe_div(material.yield_strength_mpa, thread_root_von_mises),
        "OK",
    )

    min_thread_engagement = (
        inputs.thread_engagement_mm
        if inputs.thread_engagement_mm is not None
        else thread_diameter * 1.2
    )
    engaged_thread_count = min_thread_engagement / pitch
    thread_pullout_area = math.pi / 2.0 * pitch_diameter * min_thread_engagement
    first_thread_pullout_stress = (
        thread_root_axial
        * tensile_stress_area
        / thread_pullout_area
        * _first_thread_load_factor(engaged_thread_count, friction.screw_nut_label)
    )

    minimum_sf = _minimum_safety_factor(cases, groove_sf, thread_root_sf)
    check_summary = _check_summary(
        cases,
        groove_sf,
        thread_root_sf,
        minimum_sf,
        geometry,
        friction,
    )
    warnings = _warnings(cases, groove_sf, thread_root_sf, minimum_sf)

    return CTPResult(
        inputs=inputs,
        thread_diameter_mm=thread_diameter,
        pitch_mm=pitch,
        pitch_diameter_mm=pitch_diameter,
        thread_root_diameter_mm=thread_root_diameter,
        tensile_stress_diameter_mm=tensile_stress_diameter,
        tensile_stress_area_mm2=tensile_stress_area,
        shear_bending_diameter_mm=shear_bending_diameter,
        groove_diameter_mm=groove_diameter,
        contact_diameter_mm=contact_diameter,
        average_nut_radius_mm=average_nut_radius,
        preload_n=preload,
        tightening_torque_nm=tightening_torque,
        nut_friction_torque_nm=nut_friction_torque,
        thread_tightening_torque_nm=thread_tightening_torque,
        friction_torque_nm=friction_torque,
        cases=cases,
        groove_axial_stress=groove_axial,
        groove_twist_stress=groove_twist,
        groove_von_mises_stress=groove_von_mises,
        groove_safety_factor=groove_sf,
        thread_root_axial_stress_mpa=thread_root_axial,
        thread_root_twist_stress_mpa=thread_root_twist,
        thread_root_von_mises_mpa=thread_root_von_mises,
        thread_root_safety_factor=thread_root_sf,
        min_thread_engagement_mm=min_thread_engagement,
        engaged_thread_count=engaged_thread_count,
        thread_pullout_area_mm2=thread_pullout_area,
        first_thread_pullout_stress_mpa=first_thread_pullout_stress,
        minimum_safety_factor=minimum_sf,
        check_summary=check_summary,
        warnings=warnings,
    )


def solve_sleeve_od(
    inputs: CTPInputs,
    target_sf: float = 1.0,
    *,
    max_iterations: int = 80,
) -> SolverResult:
    lower = max(inputs.geometry.thread_diameter_mm * 1.001, 0.001)
    upper = max(lower * 2.0, inputs.geometry.thread_diameter_mm * 3.0)

    def with_od(od: float) -> CTPInputs:
        return replace(inputs, sleeve_outer_diameter_mm=od)

    lower_result = calculate_ctp(with_od(lower))
    lower_sf = _case_min_sleeve_sf(lower_result)
    if lower_sf is not None and lower_sf >= target_sf:
        return SolverResult(True, lower, 0, "Sleeve OD already satisfies target.", lower_result)

    upper_result = calculate_ctp(with_od(upper))
    upper_sf = _case_min_sleeve_sf(upper_result)
    while (upper_sf is None or upper_sf < target_sf) and upper < inputs.geometry.thread_diameter_mm * 20.0:
        upper *= 1.6
        upper_result = calculate_ctp(with_od(upper))
        upper_sf = _case_min_sleeve_sf(upper_result)

    if upper_sf is None or upper_sf < target_sf:
        return SolverResult(False, None, 0, "Target sleeve safety factor is not bracketed.")

    best_result = upper_result
    for iteration in range(1, max_iterations + 1):
        mid = (lower + upper) / 2.0
        result = calculate_ctp(with_od(mid))
        sf = _case_min_sleeve_sf(result)
        if sf is not None and sf >= target_sf:
            upper = mid
            best_result = result
        else:
            lower = mid
        if abs(upper - lower) < 1e-6:
            return SolverResult(True, upper, iteration, "Converged.", best_result)
    return SolverResult(True, upper, max_iterations, "Converged to iteration limit.", best_result)


def solve_bending_torque_share(
    inputs: CTPInputs,
    target_sf: float = 1.00001,
    *,
    max_iterations: int = 80,
) -> SolverResult:
    base_peak = inputs.continuous_torque_nm * inputs.peak_factor
    if base_peak <= 0:
        return SolverResult(False, None, 0, "Peak torque must be positive.")

    def with_momentary_torque(torque_nm: float) -> CTPInputs:
        return replace(inputs, momentary_factor=torque_nm / base_peak)

    low = 0.0
    high = max(base_peak * inputs.momentary_factor, 1.0)
    while _momentary_bolt_sf(calculate_ctp(with_momentary_torque(high))) >= target_sf:
        low = high
        high *= 1.6
        if high > base_peak * 1000.0:
            return SolverResult(False, None, 0, "Target torque limit is not bracketed.")

    best = calculate_ctp(with_momentary_torque(low))
    for iteration in range(1, max_iterations + 1):
        mid = (low + high) / 2.0
        result = calculate_ctp(with_momentary_torque(mid))
        if _momentary_bolt_sf(result) >= target_sf:
            low = mid
            best = result
        else:
            high = mid
        if abs(high - low) < 1e-6:
            return SolverResult(True, low, iteration, "Converged.", best)
    return SolverResult(True, low, max_iterations, "Converged to iteration limit.", best)


def solve_preload_for_bending(
    inputs: CTPInputs,
    target_sf: float = 1.00001,
    *,
    max_torque_nm: float = 2000.0,
    max_iterations: int = 80,
) -> SolverResult:
    def with_torque(torque_nm: float) -> CTPInputs:
        return replace(
            inputs,
            tightening_torque_nm=torque_nm,
            preload_percent_of_yield=None,
            standard_tightening_torque_nm=None,
        )

    def min_bolt_sf(result: CTPResult) -> float:
        values = [case.bolt_safety_factor.value for case in result.cases]
        return min(value for value in values if value is not None)

    samples = 80
    bracket: tuple[float, float] | None = None
    previous_torque = 0.0
    previous_sf = min_bolt_sf(calculate_ctp(with_torque(previous_torque)))
    for index in range(1, samples + 1):
        torque = max_torque_nm * index / samples
        sf = min_bolt_sf(calculate_ctp(with_torque(torque)))
        if previous_sf >= target_sf and sf < target_sf:
            bracket = (previous_torque, torque)
            break
        previous_torque = torque
        previous_sf = sf

    if bracket is None:
        return SolverResult(False, None, samples, "Target preload safety factor is not bracketed.")

    low, high = bracket
    best = calculate_ctp(with_torque(low))
    for iteration in range(1, max_iterations + 1):
        mid = (low + high) / 2.0
        result = calculate_ctp(with_torque(mid))
        if min_bolt_sf(result) >= target_sf:
            low = mid
            best = result
        else:
            high = mid
        if abs(high - low) < 1e-6:
            return SolverResult(True, low, iteration, "Converged.", best)
    return SolverResult(True, low, max_iterations, "Converged to iteration limit.", best)


def _validate_inputs(inputs: CTPInputs) -> None:
    geometry = inputs.geometry
    if geometry.thread_diameter_mm <= 0:
        raise ValueError("Thread diameter must be greater than zero.")
    if geometry.pitch_mm <= 0:
        raise ValueError("Pitch must be greater than zero.")
    if geometry.pcd_mm <= 0:
        raise ValueError("PCD must be greater than zero.")
    if geometry.screw_count < 1:
        raise ValueError("Screw count must be at least one.")
    if geometry.contact_diameter_mm <= geometry.thread_diameter_mm:
        raise ValueError("Contact diameter must be greater than thread diameter.")
    if geometry.leverarm_mm < 0:
        raise ValueError("Leverarm must be zero or positive.")
    if geometry.shear_plane not in {"Thread", "Shank"}:
        raise ValueError("Shear plane must be Thread or Shank.")
    if inputs.continuous_torque_nm < 0:
        raise ValueError("Continuous torque must be zero or positive.")
    if inputs.peak_factor < 0 or inputs.momentary_factor < 0:
        raise ValueError("Torque factors must be zero or positive.")
    for label, value in (
        ("screw/nut friction", inputs.friction.screw_nut_mu),
        ("nut/part friction", inputs.friction.nut_part_mu),
        ("part/part friction", inputs.friction.part_part_mu),
        ("material yield", inputs.material.yield_strength_mpa),
        ("sleeve yield", inputs.sleeve_yield_strength_mpa),
    ):
        if value <= 0:
            raise ValueError(f"{label} must be greater than zero.")


def _calculate_case(
    name: str,
    torque: float,
    inputs: CTPInputs,
    preload: float,
    friction_torque: float,
    shear_bending_diameter: float,
) -> TorqueCaseResult:
    geometry = inputs.geometry
    residual_torque = max(0.0, torque - friction_torque)
    residual_shear = (
        0.0
        if residual_torque == 0
        else 2000.0 * residual_torque / (geometry.pcd_mm * geometry.screw_count)
    )
    sleeve_od = max(0.0, inputs.sleeve_outer_diameter_mm)
    sleeve_share = (
        residual_shear * _safe_ratio(sleeve_od**2 - geometry.thread_diameter_mm**2, sleeve_od**2)
        if sleeve_od > 0
        else 0.0
    )
    sleeve_inertia = math.pi / 64.0 * (sleeve_od**4 - geometry.thread_diameter_mm**4)
    sleeve_bending = _safe_zero(
        sleeve_share * geometry.leverarm_mm * sleeve_od / 2.0,
        sleeve_inertia,
    )
    sleeve_shear = _safe_zero(residual_shear, math.pi / 4.0 * sleeve_od**2)
    sleeve_von_mises = math.sqrt(sleeve_bending**2 + 3.0 * sleeve_shear**2)
    sleeve_sf = (
        StatusValue(inputs.sleeve_yield_strength_mpa / sleeve_von_mises, "OK")
        if sleeve_von_mises > 0
        else StatusValue(None, "No Sleeve")
    )

    bolt_shear_load = residual_shear - sleeve_share
    bolt_axial = _safe_zero(4.0 * preload, math.pi * shear_bending_diameter**2)
    bolt_bending = _safe_zero(
        bolt_shear_load * geometry.leverarm_mm * shear_bending_diameter / 2.0,
        math.pi / 64.0 * shear_bending_diameter**4,
    )
    bolt_shear = _safe_zero(bolt_shear_load, math.pi / 4.0 * shear_bending_diameter**2)
    bolt_von_mises = math.sqrt((bolt_axial + bolt_bending) ** 2 + 3.0 * bolt_shear**2)
    bolt_sf = StatusValue(
        _safe_div(inputs.material.yield_strength_mpa, bolt_von_mises),
        "OK" if bolt_von_mises > 0 else "N/A",
    )
    torque_ratio = StatusValue(
        _safe_div(friction_torque, torque),
        "OK" if torque > 0 else "Torque ?",
    )

    return TorqueCaseResult(
        name=name,
        torque_nm=torque,
        friction_torque_nm=friction_torque,
        torque_ratio=torque_ratio,
        residual_torque_nm=residual_torque,
        residual_shear_load_n=residual_shear,
        sleeve_shear_load_n=sleeve_share,
        sleeve_von_mises_mpa=sleeve_von_mises,
        sleeve_safety_factor=sleeve_sf,
        bolt_shear_load_n=bolt_shear_load,
        bolt_axial_stress_mpa=bolt_axial,
        bolt_bending_stress_mpa=bolt_bending,
        bolt_shear_stress_mpa=bolt_shear,
        bolt_von_mises_mpa=bolt_von_mises,
        bolt_safety_factor=bolt_sf,
    )


def _calculate_groove(
    groove_diameter: float,
    preload: float,
    thread_torque: float,
    yield_strength: float,
) -> tuple[StatusValue, StatusValue, StatusValue, StatusValue]:
    if groove_diameter <= 0:
        no_groove = StatusValue(None, "No groove")
        blank = StatusValue(None, "")
        return no_groove, no_groove, blank, blank
    axial = 4.0 * preload / (math.pi * groove_diameter**2)
    twist = 16.0 * thread_torque * 1000.0 / (math.pi * groove_diameter**3)
    von_mises = math.sqrt(axial**2 + 3.0 * twist**2)
    return (
        StatusValue(axial, "OK"),
        StatusValue(twist, "OK"),
        StatusValue(von_mises, "OK"),
        StatusValue(_safe_div(yield_strength, von_mises), "OK"),
    )


def _annulus_effective_radius(inner_radius: float, outer_radius: float) -> float:
    return (
        (2.0 / 3.0)
        * (outer_radius**3 - inner_radius**3)
        / (outer_radius**2 - inner_radius**2)
    )


def _first_thread_load_factor(thread_count: float, friction_label: str) -> float:
    if "Emuge" in friction_label or "Prevailing" in friction_label:
        factor = (
            0.001762 * thread_count**3
            - 0.028314 * thread_count**2
            + 0.182016 * thread_count
            + 0.720405
        )
    else:
        factor = (
            0.002317 * thread_count**3
            - 0.039254 * thread_count**2
            + 0.416953 * thread_count
            + 0.436158
        )
    return max(1.0, factor)


def _safe_div(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def _safe_zero(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _minimum_safety_factor(
    cases: tuple[TorqueCaseResult, ...],
    groove_sf: StatusValue,
    thread_root_sf: StatusValue,
) -> float | None:
    values: list[float] = []
    for case in cases:
        if case.sleeve_safety_factor.is_numeric:
            values.append(case.sleeve_safety_factor.value or 0.0)
        if case.bolt_safety_factor.is_numeric:
            values.append(case.bolt_safety_factor.value or 0.0)
    if groove_sf.is_numeric:
        values.append(groove_sf.value or 0.0)
    if thread_root_sf.is_numeric:
        values.append(thread_root_sf.value or 0.0)
    return min(values) if values else None


def _check_summary(
    cases: tuple[TorqueCaseResult, ...],
    groove_sf: StatusValue,
    thread_root_sf: StatusValue,
    minimum_sf: float | None,
    geometry: CTPBoltGeometry,
    friction: CTPFrictionSettings,
) -> str:
    if minimum_sf is None:
        return ""
    parts = [f"{_format_general(minimum_sf, 3)} Check:"]
    if groove_sf.is_numeric and (groove_sf.value or 0.0) < 1.1:
        parts.append("Min groove diameter")
    sleeve_thresholds = {"continuous": 1.5, "peak": 1.25, "momentary": 1.1}
    if any(
        case.sleeve_safety_factor.is_numeric
        and (case.sleeve_safety_factor.value or 0.0) < sleeve_thresholds[case.name]
        for case in cases
    ):
        parts.append("+ Sleeve outer diameter")
    bolt_plane = (
        "critical shear and bending plane"
        if geometry.leverarm_mm != 0
        else "critical shear plane"
    )
    if any(
        case.bolt_safety_factor.is_numeric
        and (case.bolt_safety_factor.value or 0.0) < sleeve_thresholds[case.name]
        for case in cases
    ):
        parts.append(f"+ {bolt_plane}")
    if thread_root_sf.is_numeric and (thread_root_sf.value or 0.0) < 1.1:
        parts.append(f"+ Axial pretension in screw+{friction.screw_nut_label}")
    return " ".join(parts)


def _warnings(
    cases: tuple[TorqueCaseResult, ...],
    groove_sf: StatusValue,
    thread_root_sf: StatusValue,
    minimum_sf: float | None,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if minimum_sf is not None and minimum_sf < 1.0:
        warnings.append("Minimum safety factor is below 1.0.")
    for case in cases:
        ratio = case.torque_ratio.value
        if ratio is not None and ratio < 1.0:
            warnings.append(f"{case.name.title()} friction torque is below demand.")
    if groove_sf.is_numeric and (groove_sf.value or 0.0) < 1.1:
        warnings.append("Groove safety factor is below 1.10.")
    if thread_root_sf.is_numeric and (thread_root_sf.value or 0.0) < 1.1:
        warnings.append("Thread root assembly safety factor is below 1.10.")
    if not warnings:
        warnings.append("All CTP 0007 checks pass.")
    return tuple(warnings)


def _format_general(value: float, decimals: int) -> str:
    text = f"{round(value, decimals):.{decimals}f}"
    return text.rstrip("0").rstrip(".")


def _case_min_sleeve_sf(result: CTPResult) -> float | None:
    values = [
        case.sleeve_safety_factor.value
        for case in result.cases
        if case.sleeve_safety_factor.value is not None
    ]
    return min(values) if values else None


def _momentary_bolt_sf(result: CTPResult) -> float:
    value = result.case("momentary").bolt_safety_factor.value
    return value if value is not None else 0.0
