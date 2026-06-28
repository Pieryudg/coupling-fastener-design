from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ctp_calculations import (
    CTPBoltGeometry,
    CTPFrictionSettings,
    CTPInputs,
    CTPMaterial,
)


APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
CTP_DATA_PATH = DATA_DIR / "ctp_0007_seed.json"


def load_ctp_data(path: Path = CTP_DATA_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def list_ctp_bolt_types(data: dict[str, Any] | None = None) -> list[str]:
    payload = data or load_ctp_data()
    return sorted({row["type_code"] for row in payload["bolt_variants"]})


def list_ctp_sizes(type_code: str, data: dict[str, Any] | None = None) -> list[str]:
    payload = data or load_ctp_data()
    return [
        row["size_code"]
        for row in payload["bolt_variants"]
        if row["type_code"] == type_code
    ]


def list_ctp_materials(data: dict[str, Any] | None = None) -> list[str]:
    payload = data or load_ctp_data()
    return [row["code"] for row in payload["materials"]]


def list_ctp_friction_labels(data: dict[str, Any] | None = None) -> list[str]:
    payload = data or load_ctp_data()
    return [row["label"] for row in payload["friction_factors"]]


def get_ctp_variant(
    type_code: str,
    size_code: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = data or load_ctp_data()
    for row in payload["bolt_variants"]:
        if row["type_code"] == type_code and row["size_code"] == size_code:
            return row
    raise ValueError(f"Unknown CTP bolt variant: {type_code} {size_code}")


def get_ctp_material(
    material_code: str,
    data: dict[str, Any] | None = None,
) -> CTPMaterial:
    payload = data or load_ctp_data()
    for row in payload["materials"]:
        if row["code"] == material_code:
            return CTPMaterial(
                code=row["code"],
                yield_strength_mpa=float(row["yield_strength_mpa"]),
            )
    raise ValueError(f"Unknown CTP material: {material_code}")


def get_ctp_friction(
    label: str,
    data: dict[str, Any] | None = None,
) -> float:
    payload = data or load_ctp_data()
    for row in payload["friction_factors"]:
        if row["label"] == label:
            return float(row["mu"])
    raise ValueError(f"Unknown CTP friction label: {label}")


def standard_tightening_torque_nm(
    type_code: str,
    size_code: str,
    material_code: str,
    data: dict[str, Any] | None = None,
) -> float | None:
    variant = get_ctp_variant(type_code, size_code, data)
    torque_by_material = variant.get("standard_tightening_torque_nm", {})
    value = torque_by_material.get(material_code)
    return float(value) if value is not None else None


def build_ctp_geometry(
    *,
    type_code: str,
    size_code: str,
    pcd_mm: float,
    screw_count: int,
    shear_plane: str,
    leverarm_mm: float,
    groove_diameter_mm: float | None = None,
    contact_diameter_mm: float | None = None,
    data: dict[str, Any] | None = None,
) -> CTPBoltGeometry:
    variant = get_ctp_variant(type_code, size_code, data)
    return CTPBoltGeometry(
        type_code=type_code,
        size_code=size_code,
        thread_diameter_mm=float(variant["thread_diameter_mm"]),
        pitch_mm=float(variant["pitch_mm"]),
        pcd_mm=pcd_mm,
        screw_count=screw_count,
        shank_diameter_mm=float(variant["shank_diameter_mm"]),
        groove_diameter_mm=(
            float(variant["groove_diameter_mm"])
            if groove_diameter_mm is None
            else groove_diameter_mm
        ),
        contact_diameter_mm=(
            float(variant["contact_diameter_mm"])
            if contact_diameter_mm is None
            else contact_diameter_mm
        ),
        thread_type=str(variant.get("thread_type", "Machined")),
        shear_plane=shear_plane,
        leverarm_mm=leverarm_mm,
    )


def build_ctp_friction(
    *,
    screw_nut_label: str,
    nut_part_label: str,
    part_part_label: str,
    custom_screw_nut_mu: float | None = None,
    custom_nut_part_mu: float | None = None,
    custom_part_part_mu: float | None = None,
    data: dict[str, Any] | None = None,
) -> CTPFrictionSettings:
    return CTPFrictionSettings(
        screw_nut_label=screw_nut_label,
        screw_nut_mu=(
            custom_screw_nut_mu
            if screw_nut_label == "Custom" and custom_screw_nut_mu is not None
            else get_ctp_friction(screw_nut_label, data)
        ),
        nut_part_label=nut_part_label,
        nut_part_mu=(
            custom_nut_part_mu
            if nut_part_label == "Custom" and custom_nut_part_mu is not None
            else get_ctp_friction(nut_part_label, data)
        ),
        part_part_label=part_part_label,
        part_part_mu=(
            custom_part_part_mu
            if part_part_label == "Custom" and custom_part_part_mu is not None
            else get_ctp_friction(part_part_label, data)
        ),
    )


def default_ctp_inputs(data: dict[str, Any] | None = None) -> CTPInputs:
    payload = data or load_ctp_data()
    defaults = payload["default"]
    type_code = defaults["bolt_type_code"]
    size_code = defaults["size_code"]
    material_code = defaults["material_code"]
    geometry = build_ctp_geometry(
        type_code=type_code,
        size_code=size_code,
        pcd_mm=447.0,
        screw_count=10,
        shear_plane="Thread",
        leverarm_mm=0.05,
        data=payload,
    )
    material = get_ctp_material(material_code, payload)
    friction = build_ctp_friction(
        screw_nut_label=defaults["screw_nut_friction_label"],
        nut_part_label=defaults["nut_part_friction_label"],
        part_part_label=defaults["part_part_friction_label"],
        data=payload,
    )
    return CTPInputs(
        reference=defaults["reference"],
        geometry=geometry,
        material=material,
        friction=friction,
        continuous_torque_nm=40100.0,
        peak_factor=2.0,
        momentary_factor=1.15,
        standard_tightening_torque_nm=standard_tightening_torque_nm(
            type_code,
            size_code,
            material_code,
            payload,
        ),
        sleeve_outer_diameter_mm=0.0,
        sleeve_yield_strength_mpa=640.0,
    )
