from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CouplingStandardProfile:
    key: str
    label: str
    minimum_service_factor: float
    source: str


COUPLING_STANDARD_PROFILES: tuple[CouplingStandardProfile, ...] = (
    CouplingStandardProfile(
        key="metallic_flexible_element",
        label="Metallic flexible element",
        minimum_service_factor=1.5,
        source="API 671, with AGMA flexible-coupling references",
    ),
    CouplingStandardProfile(
        key="gear",
        label="Gear coupling",
        minimum_service_factor=1.75,
        source="API 671 annex guidance, with AGMA flexible-coupling references",
    ),
    CouplingStandardProfile(
        key="torsional_resilient",
        label="Torsional damping or resilient",
        minimum_service_factor=3.0,
        source="API 671 annex guidance",
    ),
    CouplingStandardProfile(
        key="quill_shaft",
        label="Quill-shaft coupling",
        minimum_service_factor=1.5,
        source="API 671 annex guidance",
    ),
    CouplingStandardProfile(
        key="agreed_reduced_metallic",
        label="Agreed reduced metallic flexible",
        minimum_service_factor=1.2,
        source="API 671 reduced service factor by purchaser/vendor agreement",
    ),
)

_PROFILES_BY_KEY = {profile.key: profile for profile in COUPLING_STANDARD_PROFILES}


def get_standard_profile(key: str) -> CouplingStandardProfile:
    try:
        return _PROFILES_BY_KEY[key]
    except KeyError as exc:
        raise ValueError(f"Unknown coupling standard profile: {key}") from exc


def standard_profile_items() -> list[tuple[str, str]]:
    return [(profile.key, profile.label) for profile in COUPLING_STANDARD_PROFILES]


def standard_basis_lines(profile_key: str) -> tuple[str, ...]:
    profile = get_standard_profile(profile_key)
    return (
        f"{profile.label}: minimum service factor {profile.minimum_service_factor:g} ({profile.source}).",
        "Design torque is governed by the largest of steady-state selection, cyclic, and maximum transient torque inputs.",
        "AGMA 9104 mass-elastic guidance treats bolting connection stiffness as vendor-specific; use measured or vendor bolt/joint stiffness values.",
        "AGMA bore, keyway, fit, and balance checks are outside this friction fastener sizing model and should be verified separately when applicable.",
    )
