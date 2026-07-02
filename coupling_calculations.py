from __future__ import annotations

import math
from dataclasses import dataclass

from bolt_database import BoltSize, CtpScrewRecord, PropertyClass
from standards import get_standard_profile


@dataclass(frozen=True)
class CouplingInputs:
    transmitted_torque_nm: float
    service_factor: float
    bolt_count: int
    friction_coefficient: float
    inner_radius_mm: float
    outer_radius_mm: float
    friction_interfaces: int
    initial_preload_per_bolt_n: float
    preload_loss_percent: float
    separating_load_per_bolt_n: float
    bolt_stiffness_n_per_mm: float
    joint_stiffness_n_per_mm: float
    max_yield_utilization: float
    radius_model: str = "uniform_pressure"
    cyclic_torque_nm: float = 0.0
    transient_torque_nm: float = 0.0
    standard_profile: str = "metallic_flexible_element"


@dataclass(frozen=True)
class CouplingResult:
    effective_radius_mm: float
    steady_state_selection_torque_nm: float
    design_torque_nm: float
    governing_torque_case: str
    slip_capacity_nm: float
    slip_safety_factor: float
    residual_pretension_n: float
    service_residual_pretension_n: float
    required_residual_clamp_per_bolt_n: float
    required_initial_preload_per_bolt_n: float
    bolt_yield_load_n: float
    bolt_proof_load_n: float
    assembly_yield_utilization: float
    service_yield_utilization: float
    required_preload_yield_utilization: float
    load_fraction_to_bolt: float
    bolt_load_under_service_n: float
    minimum_service_factor: float
    joint_separates: bool
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class CtpInputs:
    reference: str
    screw_type: str
    size: str
    pcd_mm: float
    screw_count: int
    material_code: str
    manual_yield_mpa: float | None
    thread_mm: float
    pitch_mm: float
    shank_diameter_mm: float
    groove_diameter_mm: float
    contact_diameter_mm: float
    thread_type: str
    screw_nut_friction: float
    nut_part_friction: float
    part_part_friction: float
    continuous_torque_nm: float
    peak_torque_nm: float
    momentary_torque_nm: float
    tightening_torque_nm: float
    percent_tys: float
    use_standard_torque: bool
    shear_plane: str
    leverarm_mm: float
    joint_type: str
    pack_thickness_mm: float
    nut_contact_mode: str
    custom_nut_contact_diameter_mm: float
    sleeve_outer_diameter_mm: float
    sleeve_type_mode: str
    sleeve_yield_mpa: float
    tapped_hole_yield_mpa: float
    thread_engagement_mode: str
    thread_engagement_mm: float
    checking_standard: str
    screw_nut_friction_source: str = ""


@dataclass(frozen=True)
class CtpCheckingCriteria:
    name: str
    continuous_yield_sf: float
    peak_yield_sf: float
    momentary_yield_sf: float
    groove_yield_sf: float
    thread_root_required_sf: float
    thread_root_preferred_sf: float


@dataclass(frozen=True)
class CtpTorqueCase:
    name: str
    duty_torque_nm: float
    friction_torque_nm: float
    friction_ratio: float | str
    residual_torque_nm: float
    shear_load_per_joint_n: float
    sleeve_safety_factor: float | str
    partial_shank_von_mises_mpa: float | str
    partial_shank_safety_factor: float | str
    bolt_von_mises_mpa: float
    bolt_safety_factor: float


@dataclass(frozen=True)
class CtpResult:
    thread_major_diameter_mm: float
    pitch_mm: float
    pitch_diameter_mm: float
    thread_root_diameter_mm: float
    tensile_stress_diameter_mm: float
    tensile_stress_area_mm2: float
    shear_bending_diameter_mm: float
    groove_diameter_mm: float
    contact_diameter_mm: float
    average_nut_radius_mm: float
    sleeve_type: str
    tensile_yield_mpa: float
    axial_pretension_n: float
    tightening_torque_nm: float
    preload_percent_tys: float
    thread_friction_torque_nm: float
    torsional_tightening_torque_nm: float
    flange_friction_torque_nm: float
    torque_cases: tuple[CtpTorqueCase, ...]
    sleeve_preload_safety_factor: float | str
    groove_safety_factor: float | str
    thread_root_safety_factor: float
    thread_pullout_stress_mpa: float
    tapped_hole_yield_mpa: float
    minimum_safety_factor: float
    joint_type: str
    pack_thickness_mm: float
    leverarm_mm: float
    preload_percent_tys_limit: float
    checking_standard: str
    case_yield_sf_limits: tuple[float, float, float]
    sleeve_preload_minimum_sf_limit: float
    sleeve_preload_recommended_sf_limit: float
    groove_yield_sf_limit: float
    thread_root_required_sf_limit: float
    thread_root_preferred_sf_limit: float
    warnings: tuple[str, ...]


CTP_CHECKING_CRITERIA = {
    "API671 5th edition": CtpCheckingCriteria(
        name="API671 5th edition",
        continuous_yield_sf=1.50,
        peak_yield_sf=1.15,
        momentary_yield_sf=1.00,
        groove_yield_sf=1.10,
        thread_root_required_sf=1.00,
        thread_root_preferred_sf=1.10,
    ),
    "API671 4th edition": CtpCheckingCriteria(
        name="API671 4th edition",
        continuous_yield_sf=1.25,
        peak_yield_sf=1.15,
        momentary_yield_sf=1.00,
        groove_yield_sf=1.10,
        thread_root_required_sf=1.00,
        thread_root_preferred_sf=1.10,
    ),
}
CTP_CHECKING_STANDARD_NAMES = tuple(CTP_CHECKING_CRITERIA)
CTP_DEFAULT_CHECKING_STANDARD = "API671 5th edition"
CTP_JOINT_TYPES = ("Drive bolt", "Stripper bolt", "Shim")
CTP_DEFAULT_JOINT_TYPE = "Stripper bolt"
CTP_SLEEVE_TYPE_MODES = ("Auto", "No Sleeve", "Full Sleeve", "Partial Sleeve")
CTP_DEFAULT_SLEEVE_TYPE_MODE = "Auto"
CTP_SLEEVE_PRELOAD_MINIMUM_SF = 1.25
CTP_SLEEVE_PRELOAD_RECOMMENDED_SF = 1.50


def validate_inputs(values: CouplingInputs) -> None:
    if values.transmitted_torque_nm < 0:
        raise ValueError("Transmitted torque must be zero or positive.")
    if values.service_factor <= 0:
        raise ValueError("Service factor must be greater than zero.")
    if values.cyclic_torque_nm < 0:
        raise ValueError("Cyclic torque must be zero or positive.")
    if values.transient_torque_nm < 0:
        raise ValueError("Transient torque must be zero or positive.")
    if values.bolt_count < 1:
        raise ValueError("Bolt count must be at least one.")
    if values.friction_coefficient <= 0:
        raise ValueError("Friction coefficient must be greater than zero.")
    if values.outer_radius_mm <= values.inner_radius_mm:
        raise ValueError("Outer friction radius must be greater than inner radius.")
    if values.inner_radius_mm < 0:
        raise ValueError("Inner friction radius must be zero or positive.")
    if values.friction_interfaces < 1:
        raise ValueError("Use at least one friction interface.")
    if values.initial_preload_per_bolt_n < 0:
        raise ValueError("Initial preload must be zero or positive.")
    if not 0 <= values.preload_loss_percent < 100:
        raise ValueError("Preload loss must be from 0 to less than 100 percent.")
    if values.separating_load_per_bolt_n < 0:
        raise ValueError("Separating load must be zero or positive.")
    if values.bolt_stiffness_n_per_mm <= 0 or values.joint_stiffness_n_per_mm <= 0:
        raise ValueError("Bolt and joint stiffness must both be greater than zero.")
    if not 0 < values.max_yield_utilization <= 1:
        raise ValueError("Maximum yield utilization must be between 0 and 1.")
    get_standard_profile(values.standard_profile)


def effective_radius(inner_radius_mm: float, outer_radius_mm: float, model: str) -> float:
    if model == "uniform_wear":
        return (inner_radius_mm + outer_radius_mm) / 2.0
    return (2.0 / 3.0) * (
        (outer_radius_mm**3 - inner_radius_mm**3)
        / (outer_radius_mm**2 - inner_radius_mm**2)
    )


def calculate(
    values: CouplingInputs,
    bolt: BoltSize,
    prop: PropertyClass,
) -> CouplingResult:
    validate_inputs(values)

    radius = effective_radius(
        values.inner_radius_mm,
        values.outer_radius_mm,
        values.radius_model,
    )
    loss_factor = 1.0 - values.preload_loss_percent / 100.0
    steady_state_selection_torque = values.transmitted_torque_nm * values.service_factor
    torque_cases = (
        ("steady-state selection", steady_state_selection_torque),
        ("cyclic torque", values.cyclic_torque_nm),
        ("maximum transient torque", values.transient_torque_nm),
    )
    governing_torque_case, design_torque = max(torque_cases, key=lambda item: item[1])
    residual_pretension = values.initial_preload_per_bolt_n * loss_factor
    total_residual_clamp = residual_pretension * values.bolt_count
    slip_capacity = (
        values.friction_coefficient
        * total_residual_clamp
        * radius
        * values.friction_interfaces
        / 1000.0
    )
    slip_safety = (
        slip_capacity / design_torque
        if design_torque > 0
        else float("inf")
    )

    required_residual_total = (
        design_torque
        * 1000.0
        / (values.friction_coefficient * radius * values.friction_interfaces)
    )
    required_residual_per_bolt = required_residual_total / values.bolt_count
    required_initial_per_bolt = required_residual_per_bolt / loss_factor

    bolt_yield_load = prop.yield_mpa * bolt.tensile_area_mm2
    bolt_proof_load = prop.proof_mpa * bolt.tensile_area_mm2

    phi = values.bolt_stiffness_n_per_mm / (
        values.bolt_stiffness_n_per_mm + values.joint_stiffness_n_per_mm
    )
    bolt_load_under_service = residual_pretension + phi * values.separating_load_per_bolt_n
    service_residual_pretension = residual_pretension - (
        1.0 - phi
    ) * values.separating_load_per_bolt_n

    assembly_yield_util = values.initial_preload_per_bolt_n / bolt_yield_load
    service_yield_util = bolt_load_under_service / bolt_yield_load
    required_yield_util = required_initial_per_bolt / bolt_yield_load
    joint_separates = service_residual_pretension <= 0
    standard_profile = get_standard_profile(values.standard_profile)

    warnings: list[str] = []
    if values.service_factor < standard_profile.minimum_service_factor:
        warnings.append(
            f"Service factor is below the {standard_profile.minimum_service_factor:g} minimum for {standard_profile.label}."
        )
    if governing_torque_case != "steady-state selection":
        warnings.append(f"Design torque is governed by {governing_torque_case}.")
    if slip_safety < 1.0:
        warnings.append("Slip torque capacity is below design torque demand.")
    if assembly_yield_util > values.max_yield_utilization:
        warnings.append("Initial preload exceeds the selected yield utilization limit.")
    if service_yield_util > values.max_yield_utilization:
        warnings.append("Service bolt load exceeds the selected yield utilization limit.")
    if values.initial_preload_per_bolt_n > bolt_proof_load:
        warnings.append("Initial preload is above the bolt proof load.")
    if joint_separates:
        warnings.append("Residual pretension becomes zero or negative; joint separation occurs.")
    if required_yield_util > values.max_yield_utilization:
        warnings.append("Required preload for friction capacity exceeds the yield utilization limit.")
    if not warnings:
        warnings.append("All current checks pass.")

    return CouplingResult(
        effective_radius_mm=radius,
        steady_state_selection_torque_nm=steady_state_selection_torque,
        design_torque_nm=design_torque,
        governing_torque_case=governing_torque_case,
        slip_capacity_nm=slip_capacity,
        slip_safety_factor=slip_safety,
        residual_pretension_n=residual_pretension,
        service_residual_pretension_n=service_residual_pretension,
        required_residual_clamp_per_bolt_n=required_residual_per_bolt,
        required_initial_preload_per_bolt_n=required_initial_per_bolt,
        bolt_yield_load_n=bolt_yield_load,
        bolt_proof_load_n=bolt_proof_load,
        assembly_yield_utilization=assembly_yield_util,
        service_yield_utilization=service_yield_util,
        required_preload_yield_utilization=required_yield_util,
        load_fraction_to_bolt=phi,
        bolt_load_under_service_n=bolt_load_under_service,
        minimum_service_factor=standard_profile.minimum_service_factor,
        joint_separates=joint_separates,
        warnings=tuple(warnings),
    )


def default_ctp_inputs(record: CtpScrewRecord) -> CtpInputs:
    return CtpInputs(
        reference="TSKW/0360/KA/GA253480 Hub Bolts",
        screw_type=record.screw_type,
        size=record.size,
        pcd_mm=447.0,
        screw_count=10,
        material_code="0225 (Classe 12-9)",
        manual_yield_mpa=None,
        thread_mm=record.thread_mm,
        pitch_mm=record.pitch_mm,
        shank_diameter_mm=record.shank_diameter_mm,
        groove_diameter_mm=record.groove_diameter_mm,
        contact_diameter_mm=record.contact_diameter_mm,
        thread_type=record.thread_type,
        screw_nut_friction=0.155,
        nut_part_friction=0.12,
        part_part_friction=0.15,
        continuous_torque_nm=40100.0,
        peak_torque_nm=80200.0,
        momentary_torque_nm=92230.0,
        tightening_torque_nm=0.0,
        percent_tys=0.0,
        use_standard_torque=True,
        shear_plane="Thread",
        leverarm_mm=0.05,
        joint_type=CTP_DEFAULT_JOINT_TYPE,
        pack_thickness_mm=0.0,
        nut_contact_mode="Standard",
        custom_nut_contact_diameter_mm=20.0,
        sleeve_outer_diameter_mm=0.0,
        sleeve_type_mode=CTP_DEFAULT_SLEEVE_TYPE_MODE,
        sleeve_yield_mpa=640.0,
        tapped_hole_yield_mpa=0.0,
        thread_engagement_mode="Manual",
        thread_engagement_mm=record.thread_mm * 1.2,
        checking_standard=CTP_DEFAULT_CHECKING_STANDARD,
        screw_nut_friction_source="Emuge+Oil",
    )


def calculate_ctp(
    values: CtpInputs,
    record: CtpScrewRecord,
    material_yield_mpa: float,
) -> CtpResult:
    validate_ctp_inputs(values)
    criteria = ctp_checking_criteria(values.checking_standard)
    leverarm_mm = _effective_leverarm(values)
    preload_percent_limit = _preload_percent_limit(values.joint_type)
    thread_major = record.thread_mm if values.screw_type != "SPECIAL" else values.thread_mm
    pitch = record.pitch_mm if values.screw_type != "SPECIAL" else values.pitch_mm
    shank = record.shank_diameter_mm if values.screw_type != "SPECIAL" else values.shank_diameter_mm
    groove = values.groove_diameter_mm
    contact_diameter = _contact_diameter(values, record)
    tensile_yield = values.manual_yield_mpa or material_yield_mpa
    sleeve_type = _sleeve_type(
        values.sleeve_outer_diameter_mm,
        values.shear_plane,
        values.sleeve_type_mode,
    )

    pitch_diameter = thread_major - 0.6495 * pitch
    root_diameter = thread_major - 1.2268 * pitch
    tensile_stress_diameter = (pitch_diameter + root_diameter) / 2.0
    tensile_stress_area = ((pitch_diameter + root_diameter) / 4.0) ** 2 * math.pi
    shear_bending_diameter = (
        tensile_stress_diameter if values.shear_plane == "Thread" else shank
    )
    average_nut_radius = _average_annular_radius(contact_diameter / 2.0, pitch_diameter / 2.0)
    standard_torque = record.standard_torques_nm.get(values.material_code, 0.0)
    tightening_torque = _select_tightening_torque(values, standard_torque)
    axial_pretension = _preload_from_tightening(
        tightening_torque,
        values,
        pitch,
        pitch_diameter,
        average_nut_radius,
        tensile_stress_area,
        tensile_yield,
    )
    reported_tightening_torque = _reported_tightening_torque(
        tightening_torque,
        values,
        pitch,
        pitch_diameter,
        average_nut_radius,
        axial_pretension,
    )
    preload_percent_tys = axial_pretension / (tensile_stress_area * tensile_yield) * 100.0
    thread_friction_torque = values.nut_part_friction * average_nut_radius * axial_pretension / 1000.0
    torsional_tightening_torque = (
        (0.16 * pitch + 0.583 * values.screw_nut_friction * pitch_diameter)
        * axial_pretension
        / 1000.0
    )
    flange_friction_torque = (
        axial_pretension
        * values.screw_count
        * values.part_part_friction
        * values.pcd_mm
        / 2.0
        / 1000.0
    )

    torque_cases = tuple(
        _torque_case(
            name,
            duty,
            values,
            flange_friction_torque,
            axial_pretension,
            shear_bending_diameter,
            leverarm_mm,
            thread_major_diameter=thread_major,
            sleeve_outer_diameter=values.sleeve_outer_diameter_mm,
            sleeve_yield=values.sleeve_yield_mpa,
            sleeve_type=sleeve_type,
            tensile_yield=tensile_yield,
        )
        for name, duty in (
            ("Continuous", values.continuous_torque_nm),
            ("Peak", values.peak_torque_nm),
            ("Momentary", values.momentary_torque_nm),
        )
    )
    sleeve_preload_safety = _sleeve_preload_safety(
        values.sleeve_outer_diameter_mm,
        thread_major,
        sleeve_type,
        values.sleeve_yield_mpa,
        axial_pretension,
    )
    groove_safety = _groove_safety(
        groove,
        axial_pretension,
        torsional_tightening_torque,
        tensile_yield,
    )
    thread_root_safety = _thread_root_safety(
        axial_pretension,
        torsional_tightening_torque,
        tensile_stress_area,
        root_diameter,
        tensile_yield,
    )
    engagement = (
        values.thread_engagement_mm
        if values.thread_engagement_mode != "Thread"
        else thread_major * 1.2
    )
    thread_pullout_area = math.pi / 2.0 * pitch_diameter * engagement
    engaged_thread_qty = engagement / pitch
    first_thread_factor = _thread_pullout_factor(
        engaged_thread_qty,
        values.screw_nut_friction_source,
    )
    thread_pullout_stress = (
        (axial_pretension / tensile_stress_area)
        * tensile_stress_area
        / thread_pullout_area
        * first_thread_factor
    )
    numeric_sfs = [case.bolt_safety_factor for case in torque_cases]
    numeric_sfs.extend(
        sf
        for sf in [sleeve_preload_safety, groove_safety, thread_root_safety]
        if isinstance(sf, float)
    )
    for case in torque_cases:
        if isinstance(case.sleeve_safety_factor, float):
            numeric_sfs.append(case.sleeve_safety_factor)
        if isinstance(case.partial_shank_safety_factor, float):
            numeric_sfs.append(case.partial_shank_safety_factor)
    minimum_safety = min(numeric_sfs) if numeric_sfs else float("inf")

    return CtpResult(
        thread_major_diameter_mm=thread_major,
        pitch_mm=pitch,
        pitch_diameter_mm=pitch_diameter,
        thread_root_diameter_mm=root_diameter,
        tensile_stress_diameter_mm=tensile_stress_diameter,
        tensile_stress_area_mm2=tensile_stress_area,
        shear_bending_diameter_mm=shear_bending_diameter,
        groove_diameter_mm=groove,
        contact_diameter_mm=contact_diameter,
        average_nut_radius_mm=average_nut_radius,
        sleeve_type=sleeve_type,
        tensile_yield_mpa=tensile_yield,
        axial_pretension_n=axial_pretension,
        tightening_torque_nm=reported_tightening_torque,
        preload_percent_tys=preload_percent_tys,
        thread_friction_torque_nm=thread_friction_torque,
        torsional_tightening_torque_nm=torsional_tightening_torque,
        flange_friction_torque_nm=flange_friction_torque,
        torque_cases=torque_cases,
        sleeve_preload_safety_factor=sleeve_preload_safety,
        groove_safety_factor=groove_safety,
        thread_root_safety_factor=thread_root_safety,
        thread_pullout_stress_mpa=thread_pullout_stress,
        tapped_hole_yield_mpa=values.tapped_hole_yield_mpa,
        minimum_safety_factor=minimum_safety,
        joint_type=values.joint_type,
        pack_thickness_mm=values.pack_thickness_mm,
        leverarm_mm=leverarm_mm,
        preload_percent_tys_limit=preload_percent_limit,
        checking_standard=criteria.name,
        case_yield_sf_limits=(
            criteria.continuous_yield_sf,
            criteria.peak_yield_sf,
            criteria.momentary_yield_sf,
        ),
        sleeve_preload_minimum_sf_limit=CTP_SLEEVE_PRELOAD_MINIMUM_SF,
        sleeve_preload_recommended_sf_limit=CTP_SLEEVE_PRELOAD_RECOMMENDED_SF,
        groove_yield_sf_limit=criteria.groove_yield_sf,
        thread_root_required_sf_limit=criteria.thread_root_required_sf,
        thread_root_preferred_sf_limit=criteria.thread_root_preferred_sf,
        warnings=_ctp_warnings(
            torque_cases,
            groove_safety,
            thread_root_safety,
            criteria,
            values.joint_type,
            preload_percent_tys,
            preload_percent_limit,
            sleeve_preload_safety,
            thread_pullout_stress,
            values.tapped_hole_yield_mpa,
        ),
    )


def validate_ctp_inputs(values: CtpInputs) -> None:
    if values.pcd_mm <= 0:
        raise ValueError("PCD must be greater than zero.")
    if values.screw_count < 1:
        raise ValueError("Screw count must be at least one.")
    if values.thread_mm <= 0 or values.pitch_mm <= 0:
        raise ValueError("Thread and pitch must be greater than zero.")
    if values.checking_standard not in CTP_CHECKING_CRITERIA:
        raise ValueError(f"Unknown checking standard: {values.checking_standard}")
    if values.joint_type not in CTP_JOINT_TYPES:
        raise ValueError(f"Unknown joint type: {values.joint_type}")
    if values.sleeve_type_mode not in CTP_SLEEVE_TYPE_MODES:
        raise ValueError(f"Unknown sleeve type: {values.sleeve_type_mode}")
    if values.pack_thickness_mm < 0:
        raise ValueError("Pack thickness must be zero or positive.")
    if values.joint_type in {"Drive bolt", "Shim"} and values.pack_thickness_mm <= 0:
        raise ValueError(f"Pack thickness is required for {values.joint_type}.")
    if values.contact_diameter_mm <= 0:
        raise ValueError("Contact diameter must be greater than zero.")
    if values.tightening_torque_nm > 0 and values.percent_tys > 0:
        raise ValueError("Enter either tightening torque or %TYS, not both.")
    for label, coefficient in (
        ("Screw/nut friction", values.screw_nut_friction),
        ("Nut/part friction", values.nut_part_friction),
        ("Part/part friction", values.part_part_friction),
    ):
        if coefficient <= 0:
            raise ValueError(f"{label} must be greater than zero.")
    if values.sleeve_outer_diameter_mm < 0:
        raise ValueError("Sleeve outer diameter must be zero or positive.")
    if values.sleeve_type_mode in {"Full Sleeve", "Partial Sleeve"} and values.sleeve_outer_diameter_mm <= 0:
        raise ValueError(f"Sleeve OD is required for {values.sleeve_type_mode}.")
    if values.tapped_hole_yield_mpa < 0:
        raise ValueError("Tapped hole yield must be zero or positive.")
    if values.leverarm_mm < 0:
        raise ValueError("Leverarm must be zero or positive.")


def _contact_diameter(values: CtpInputs, record: CtpScrewRecord) -> float:
    if values.screw_type == "SPECIAL":
        return values.contact_diameter_mm
    if values.nut_contact_mode == "Special" and values.custom_nut_contact_diameter_mm > 0:
        return values.custom_nut_contact_diameter_mm
    return record.contact_diameter_mm


def _sleeve_type(sleeve_outer_diameter: float, shear_plane: str, mode: str) -> str:
    if mode != "Auto":
        return mode
    if sleeve_outer_diameter <= 0:
        return "No Sleeve"
    if shear_plane == "Shank":
        return "Partial Sleeve"
    return "Full Sleeve"


def _effective_leverarm(values: CtpInputs) -> float:
    if values.joint_type == "Stripper bolt":
        return 0.05
    if values.joint_type in {"Drive bolt", "Shim"}:
        return 0.15 * values.pack_thickness_mm
    return values.leverarm_mm


def _preload_percent_limit(joint_type: str) -> float:
    if joint_type in {"Stripper bolt", "Shim"}:
        return 60.0
    return 75.0


def _average_annular_radius(outer_radius: float, inner_radius: float) -> float:
    if outer_radius <= inner_radius:
        raise ValueError("Nut contact diameter must exceed pitch diameter.")
    return (2.0 / 3.0) * (
        (outer_radius**3 - inner_radius**3) / (outer_radius**2 - inner_radius**2)
    )


def _select_tightening_torque(values: CtpInputs, standard_torque: float) -> float:
    if values.tightening_torque_nm > 0:
        return values.tightening_torque_nm
    if values.percent_tys > 0:
        return 0.0
    if values.use_standard_torque and standard_torque > 0:
        return standard_torque
    raise ValueError("Specify tightening torque, percent TYS, or a standard torque.")


def _preload_from_tightening(
    tightening_torque_nm: float,
    values: CtpInputs,
    pitch: float,
    pitch_diameter: float,
    average_nut_radius: float,
    tensile_stress_area: float,
    tensile_yield: float,
) -> float:
    if values.tightening_torque_nm > 0 or (values.use_standard_torque and tightening_torque_nm > 0):
        denominator = (
            0.16 * pitch
            + 0.583 * values.screw_nut_friction * pitch_diameter
            + values.nut_part_friction * average_nut_radius
        )
        return 1000.0 * tightening_torque_nm / denominator
    if values.percent_tys > 0:
        return values.percent_tys * tensile_stress_area * tensile_yield / 100.0
    return 0.0


def _reported_tightening_torque(
    selected_tightening_torque_nm: float,
    values: CtpInputs,
    pitch: float,
    pitch_diameter: float,
    average_nut_radius: float,
    axial_pretension: float,
) -> float:
    if values.tightening_torque_nm > 0:
        return values.tightening_torque_nm
    if values.percent_tys > 0:
        return (
            0.16 * pitch
            + 0.583 * values.screw_nut_friction * pitch_diameter
            + values.nut_part_friction * average_nut_radius
        ) * axial_pretension / 1000.0
    return selected_tightening_torque_nm


def _thread_pullout_factor(
    engaged_thread_qty: float,
    screw_nut_friction_source: str,
) -> float:
    if "Emuge" in screw_nut_friction_source or "Prevailing" in screw_nut_friction_source:
        return max(
            1.0,
            0.001762 * engaged_thread_qty**3
            - 0.028314 * engaged_thread_qty**2
            + 0.182016 * engaged_thread_qty
            + 0.720405,
        )
    return max(
        1.0,
        0.002317 * engaged_thread_qty**3
        - 0.039254 * engaged_thread_qty**2
        + 0.416953 * engaged_thread_qty
        + 0.436158,
    )


def _torque_case(
    name: str,
    duty_torque: float,
    values: CtpInputs,
    flange_friction_torque: float,
    axial_pretension: float,
    shear_bending_diameter: float,
    leverarm_mm: float,
    thread_major_diameter: float,
    sleeve_outer_diameter: float,
    sleeve_yield: float,
    sleeve_type: str,
    tensile_yield: float,
) -> CtpTorqueCase:
    if duty_torque == 0:
        friction_ratio: float | str = "Torque ?"
    else:
        friction_ratio = flange_friction_torque / duty_torque
    residual_torque = max(0.0, duty_torque - flange_friction_torque)
    shear_load = 2000.0 * residual_torque / (values.pcd_mm * values.screw_count)
    has_sleeve = sleeve_type in {"Full Sleeve", "Partial Sleeve"}
    sleeve_share = (
        shear_load * (sleeve_outer_diameter**2 - thread_major_diameter**2) / sleeve_outer_diameter**2
        if has_sleeve and sleeve_outer_diameter > thread_major_diameter
        else 0.0
    )
    bolt_share = shear_load - sleeve_share
    sleeve_safety: float | str = "No Sleeve"
    if has_sleeve and sleeve_outer_diameter > 0:
        bending = (
            sleeve_share
            * leverarm_mm
            * sleeve_outer_diameter
            / 2.0
            / (math.pi / 64.0 * (sleeve_outer_diameter**4 - thread_major_diameter**4))
            if sleeve_outer_diameter > thread_major_diameter
            else 0.0
        )
        shear = shear_load / (math.pi / 4.0 * sleeve_outer_diameter**2)
        von_mises = math.sqrt(bending**2 + 3.0 * shear**2)
        sleeve_safety = sleeve_yield / von_mises if von_mises else float("inf")
    axial_stress = 4.0 * axial_pretension / (math.pi * shear_bending_diameter**2)
    partial_shank_vm: float | str = "N/A"
    partial_shank_safety: float | str = "N/A"
    if sleeve_type == "Partial Sleeve":
        partial_shank_shear = shear_load / (math.pi / 4.0 * shear_bending_diameter**2)
        partial_shank_vm_numeric = math.sqrt(axial_stress**2 + 3.0 * partial_shank_shear**2)
        partial_shank_vm = partial_shank_vm_numeric
        partial_shank_safety = (
            tensile_yield / partial_shank_vm_numeric
            if partial_shank_vm_numeric
            else float("inf")
        )
    bending_stress = (
        bolt_share
        * leverarm_mm
        * shear_bending_diameter
        / 2.0
        / (math.pi / 64.0 * shear_bending_diameter**4)
    )
    shear_stress = bolt_share / (math.pi / 4.0 * shear_bending_diameter**2)
    bolt_vm = math.sqrt((axial_stress + bending_stress) ** 2 + 3.0 * shear_stress**2)
    bolt_safety = tensile_yield / bolt_vm if bolt_vm else float("inf")
    return CtpTorqueCase(
        name=name,
        duty_torque_nm=duty_torque,
        friction_torque_nm=flange_friction_torque,
        friction_ratio=friction_ratio,
        residual_torque_nm=residual_torque,
        shear_load_per_joint_n=shear_load,
        sleeve_safety_factor=sleeve_safety,
        partial_shank_von_mises_mpa=partial_shank_vm,
        partial_shank_safety_factor=partial_shank_safety,
        bolt_von_mises_mpa=bolt_vm,
        bolt_safety_factor=bolt_safety,
    )


def _sleeve_preload_safety(
    sleeve_outer_diameter: float,
    thread_major_diameter: float,
    sleeve_type: str,
    sleeve_yield: float,
    axial_pretension: float,
) -> float | str:
    if sleeve_type == "No Sleeve" or sleeve_outer_diameter <= 0 or thread_major_diameter <= 0:
        return "No Sleeve"
    sleeve_area = max(
        0.0,
        math.pi / 4.0 * (sleeve_outer_diameter**2 - thread_major_diameter**2),
    )
    if sleeve_area <= 0 or axial_pretension <= 0:
        return "Gagging"
    preload_stress = axial_pretension / sleeve_area
    return sleeve_yield / preload_stress if preload_stress else float("inf")


def _groove_safety(
    groove_diameter: float,
    axial_pretension: float,
    torsional_tightening_torque: float,
    tensile_yield: float,
) -> float | str:
    if groove_diameter <= 0:
        return "No groove"
    axial_stress = 4.0 * axial_pretension / (math.pi * groove_diameter**2)
    twisting_stress = 16.0 * torsional_tightening_torque * 1000.0 / (
        math.pi * groove_diameter**3
    )
    von_mises = math.sqrt(axial_stress**2 + 3.0 * twisting_stress**2)
    return tensile_yield / von_mises if von_mises else float("inf")


def _thread_root_safety(
    axial_pretension: float,
    torsional_tightening_torque: float,
    tensile_stress_area: float,
    root_diameter: float,
    tensile_yield: float,
) -> float:
    axial_stress = axial_pretension / tensile_stress_area
    twisting_stress = (
        torsional_tightening_torque
        * 1000.0
        * root_diameter
        / 2.0
        / (math.pi / 32.0 * root_diameter**4)
    )
    von_mises = math.sqrt(axial_stress**2 + 3.0 * twisting_stress**2)
    return tensile_yield / von_mises if von_mises else float("inf")


def ctp_checking_criteria(name: str) -> CtpCheckingCriteria:
    try:
        return CTP_CHECKING_CRITERIA[name]
    except KeyError as exc:
        raise ValueError(f"Unknown checking standard: {name}") from exc


def _ctp_warnings(
    torque_cases: tuple[CtpTorqueCase, ...],
    groove_safety: float | str,
    thread_root_safety: float,
    criteria: CtpCheckingCriteria,
    joint_type: str,
    preload_percent_tys: float,
    preload_percent_limit: float,
    sleeve_preload_safety: float | str,
    thread_pullout_stress: float,
    tapped_hole_yield: float,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if preload_percent_tys > preload_percent_limit:
        warnings.append(
            f"Tightening preload is {preload_percent_tys:.2f}% TYS; "
            f"maximum is {preload_percent_limit:.0f}% for {joint_type}."
        )
    case_limits = {
        "Continuous": criteria.continuous_yield_sf,
        "Peak": criteria.peak_yield_sf,
        "Momentary": criteria.momentary_yield_sf,
    }
    for case in torque_cases:
        yield_limit = case_limits[case.name]
        if case.bolt_safety_factor < yield_limit:
            warnings.append(
                f"{case.name} bolt shear/bending safety factor is below {yield_limit:.2f} for {criteria.name}."
            )
        if isinstance(case.sleeve_safety_factor, float) and case.sleeve_safety_factor < yield_limit:
            warnings.append(
                f"{case.name} sleeve safety factor is below {yield_limit:.2f} for {criteria.name}."
            )
        if isinstance(case.partial_shank_safety_factor, float) and case.partial_shank_safety_factor < yield_limit:
            warnings.append(
                f"{case.name} partial sleeve shank safety factor is below {yield_limit:.2f} for {criteria.name}."
            )
    if isinstance(sleeve_preload_safety, float):
        if sleeve_preload_safety < CTP_SLEEVE_PRELOAD_MINIMUM_SF:
            warnings.append(
                f"Sleeve preload safety factor is below minimum {CTP_SLEEVE_PRELOAD_MINIMUM_SF:.2f}."
            )
        elif sleeve_preload_safety < CTP_SLEEVE_PRELOAD_RECOMMENDED_SF:
            warnings.append(
                f"Sleeve preload safety factor is below recommended {CTP_SLEEVE_PRELOAD_RECOMMENDED_SF:.2f}; "
                f"minimum is {CTP_SLEEVE_PRELOAD_MINIMUM_SF:.2f}."
            )
    if isinstance(groove_safety, float) and groove_safety < criteria.groove_yield_sf:
        warnings.append(f"Groove assembly safety factor is below {criteria.groove_yield_sf:.2f}.")
    if thread_root_safety < criteria.thread_root_required_sf:
        warnings.append(
            f"Thread-root assembly safety factor is below required {criteria.thread_root_required_sf:.2f}."
        )
    elif thread_root_safety < criteria.thread_root_preferred_sf:
        warnings.append(
            f"Thread-root assembly safety factor is below preferred {criteria.thread_root_preferred_sf:.2f}; "
            "residual torque can reduce by about 20% upon loading."
        )
    if tapped_hole_yield > 0 and tapped_hole_yield < thread_pullout_stress:
        warnings.append(
            f"Tapped hole yield strength {tapped_hole_yield:.1f} MPa is below thread pull-out stress "
            f"{thread_pullout_stress:.1f} MPa."
        )
    if not warnings:
        warnings.append("All current checks pass.")
    return tuple(warnings)
