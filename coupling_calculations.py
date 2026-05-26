from __future__ import annotations

from dataclasses import dataclass

from bolt_database import BoltSize, PropertyClass


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


@dataclass(frozen=True)
class CouplingResult:
    effective_radius_mm: float
    design_torque_nm: float
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
    joint_separates: bool
    warnings: tuple[str, ...]


def validate_inputs(values: CouplingInputs) -> None:
    if values.transmitted_torque_nm < 0:
        raise ValueError("Transmitted torque must be zero or positive.")
    if values.service_factor <= 0:
        raise ValueError("Service factor must be greater than zero.")
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
    design_torque = values.transmitted_torque_nm * values.service_factor
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

    warnings: list[str] = []
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
        design_torque_nm=design_torque,
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
        joint_separates=joint_separates,
        warnings=tuple(warnings),
    )
