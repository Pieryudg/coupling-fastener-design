import math
import sys
import unittest
from dataclasses import replace
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

from bolt_database import (
    connect,
    get_bolt_size,
    get_ctp_screw_record,
    get_material_yield,
    get_property_class,
    list_ctp_screw_types,
    list_ctp_sizes,
    list_friction_presets,
    list_material_codes,
    recommend_bolt_size,
)
from coupling_calculations import (
    CouplingInputs,
    calculate,
    calculate_ctp,
    default_ctp_inputs,
    effective_radius,
)
from standards import get_standard_profile, standard_basis_lines


def default_inputs():
    return CouplingInputs(
        transmitted_torque_nm=1200,
        service_factor=1.5,
        bolt_count=8,
        friction_coefficient=0.18,
        inner_radius_mm=45,
        outer_radius_mm=115,
        friction_interfaces=1,
        initial_preload_per_bolt_n=25000,
        preload_loss_percent=15,
        separating_load_per_bolt_n=1000,
        bolt_stiffness_n_per_mm=30000,
        joint_stiffness_n_per_mm=15000,
        max_yield_utilization=0.70,
    )


class CouplingFastenerAppTests(unittest.TestCase):
    def test_effective_radius_uniform_pressure(self):
        radius = effective_radius(45, 115, "uniform_pressure")
        self.assertTrue(math.isclose(radius, 85.104, rel_tol=1e-4))

    def test_default_coupling_result_checks_residual_pretension_and_yield(self):
        conn = connect()
        bolt = get_bolt_size(conn, "M10")
        prop = get_property_class(conn, "10.9")
        result = calculate(default_inputs(), bolt, prop)

        self.assertTrue(math.isclose(result.slip_safety_factor, 1.4466, rel_tol=1e-3))
        self.assertEqual(result.design_torque_nm, 1800)
        self.assertEqual(result.governing_torque_case, "steady-state selection")
        self.assertEqual(result.minimum_service_factor, 1.5)
        self.assertEqual(result.residual_pretension_n, 21250)
        self.assertTrue(math.isclose(result.service_residual_pretension_n, 20916.667, rel_tol=1e-4))
        self.assertTrue(math.isclose(result.assembly_yield_utilization, 0.4789, rel_tol=1e-3))
        self.assertEqual(result.warnings, ("All current checks pass.",))

    def test_recommendation_uses_database_order(self):
        conn = connect()
        prop = get_property_class(conn, "10.9")
        result = calculate(default_inputs(), get_bolt_size(conn, "M10"), prop)
        recommendation = recommend_bolt_size(
            conn,
            prop,
            result.required_initial_preload_per_bolt_n,
            default_inputs().max_yield_utilization,
        )

        self.assertIsNotNone(recommendation)
        self.assertEqual(recommendation.designation, "M8")

    def test_transient_torque_can_govern_design_torque(self):
        conn = connect()
        inputs = replace(default_inputs(), transient_torque_nm=2500)

        result = calculate(inputs, get_bolt_size(conn, "M10"), get_property_class(conn, "10.9"))

        self.assertEqual(result.design_torque_nm, 2500)
        self.assertEqual(result.governing_torque_case, "maximum transient torque")
        self.assertIn("Design torque is governed by maximum transient torque.", result.warnings)

    def test_standard_profile_warns_on_low_service_factor(self):
        conn = connect()
        inputs = replace(default_inputs(), service_factor=1.2, standard_profile="gear")

        result = calculate(inputs, get_bolt_size(conn, "M10"), get_property_class(conn, "10.9"))

        self.assertEqual(result.minimum_service_factor, 1.75)
        self.assertIn("Service factor is below the 1.75 minimum for Gear coupling.", result.warnings)

    def test_standard_basis_mentions_agma_stiffness_boundary(self):
        profile = get_standard_profile("metallic_flexible_element")

        self.assertEqual(profile.minimum_service_factor, 1.5)
        self.assertTrue(
            any("bolting connection stiffness" in line for line in standard_basis_lines(profile.key))
        )

    def test_ctp_default_case_matches_spreadsheet_cache(self):
        conn = connect()
        record = get_ctp_screw_record(conn, "1512", "47xx")
        inputs = default_ctp_inputs(record)
        result = calculate_ctp(inputs, record, get_material_yield(conn, inputs.material_code))

        self.assertEqual(result.thread_major_diameter_mm, 16)
        self.assertEqual(result.pitch_mm, 2)
        self.assertEqual(inputs.thread_engagement_mm, 19.2)
        self.assertTrue(math.isclose(result.tensile_stress_area_mm2, 156.670363, rel_tol=1e-6))
        self.assertTrue(math.isclose(result.axial_pretension_n, 128891.948947, rel_tol=1e-6))
        self.assertEqual(result.tightening_torque_nm, 365)
        self.assertTrue(math.isclose(result.preload_percent_tys, 76.1754775, rel_tol=1e-6))
        self.assertTrue(math.isclose(result.flange_friction_torque_nm, 43211.025884, rel_tol=1e-6))

        continuous, peak, momentary = result.torque_cases
        self.assertTrue(math.isclose(continuous.friction_ratio, 1.0775816929, rel_tol=1e-6))
        self.assertTrue(math.isclose(peak.friction_ratio, 0.5387908464, rel_tol=1e-6))
        self.assertTrue(math.isclose(momentary.friction_ratio, 0.4685137795, rel_tol=1e-6))
        self.assertNotIn("friction torque is below duty torque", "\n".join(result.warnings))
        self.assertTrue(math.isclose(continuous.bolt_safety_factor, 1.3127584263, rel_tol=1e-6))
        self.assertTrue(math.isclose(peak.bolt_safety_factor, 1.2770248669, rel_tol=1e-6))
        self.assertTrue(math.isclose(momentary.bolt_safety_factor, 1.2536471143, rel_tol=1e-6))
        self.assertTrue(math.isclose(momentary.bolt_von_mises_mpa, 861.4864484, rel_tol=1e-6))
        self.assertTrue(math.isclose(result.thread_root_safety_factor, 0.9677950537, rel_tol=1e-6))

    def test_ctp_dropdown_data_matches_workbook_lookup_table(self):
        conn = connect()

        self.assertEqual(
            list_ctp_screw_types(conn),
            ["1825", "1828", "1121", "1135", "1161", "1136", "1412", "1512", "1442", "SPECIAL"],
        )
        self.assertEqual(len(list_ctp_sizes(conn, "1828")), 51)
        self.assertEqual(list_ctp_sizes(conn, "1512")[:3], ["04xx", "07xx", "10xx"])
        self.assertEqual(list_ctp_sizes(conn, "1512")[-3:], ["67xx", "71xx", "75xx"])
        special_sizes = list_ctp_sizes(conn, "SPECIAL")
        self.assertEqual(special_sizes[:3], ["M1.6", "M2", "M2.5"])
        self.assertIn("M16", special_sizes)
        self.assertEqual(special_sizes[-1], "Manual")
        self.assertEqual(len(list_material_codes(conn)), 13)
        self.assertEqual(len(list_friction_presets(conn)), 16)

    def test_ctp_geometry_lookup_includes_non_default_families(self):
        conn = connect()

        record_1121 = get_ctp_screw_record(conn, "1121", "1120")
        self.assertEqual(record_1121.thread_mm, 24)
        self.assertEqual(record_1121.standard_torques_nm["0435 (EN17/24T)"], 490)

        record_1161 = get_ctp_screw_record(conn, "1161", "9049")
        self.assertEqual(record_1161.thread_mm, 64)
        self.assertEqual(record_1161.groove_diameter_mm, 56.6)

        record_1442 = get_ctp_screw_record(conn, "1442", "47xx")
        self.assertEqual(record_1442.shank_diameter_mm, 20)
        self.assertEqual(record_1442.groove_diameter_mm, 12.96)

        record_special_m16 = get_ctp_screw_record(conn, "SPECIAL", "M16")
        self.assertEqual(record_special_m16.thread_mm, 16)
        self.assertEqual(record_special_m16.pitch_mm, 2)
        self.assertEqual(record_special_m16.shank_diameter_mm, 16)
        self.assertEqual(record_special_m16.groove_diameter_mm, 0)
        self.assertEqual(record_special_m16.contact_diameter_mm, 24)

        record_special_m48 = get_ctp_screw_record(conn, "SPECIAL", "M48")
        self.assertEqual(record_special_m48.pitch_mm, 5)
        self.assertEqual(record_special_m48.contact_diameter_mm, 72)

    def test_ctp_special_fastener_uses_manual_geometry(self):
        conn = connect()
        record = get_ctp_screw_record(conn, "SPECIAL", "M16")
        base = default_ctp_inputs(record)
        inputs = base.__class__(
            **{
                **base.__dict__,
                "thread_mm": 18,
                "pitch_mm": 2.5,
                "shank_diameter_mm": 17.5,
                "groove_diameter_mm": 15.5,
                "contact_diameter_mm": 28,
                "shear_plane": "Shank",
                "tightening_torque_nm": 180,
                "use_standard_torque": False,
            }
        )
        result = calculate_ctp(inputs, record, get_material_yield(conn, inputs.material_code))

        self.assertEqual(result.thread_major_diameter_mm, 18)
        self.assertEqual(result.pitch_mm, 2.5)
        self.assertEqual(result.shear_bending_diameter_mm, 17.5)
        self.assertEqual(result.groove_diameter_mm, 15.5)
        self.assertEqual(result.contact_diameter_mm, 28)

    def test_ctp_percent_tys_preload_path(self):
        conn = connect()
        record = get_ctp_screw_record(conn, "1512", "47xx")
        base = default_ctp_inputs(record)
        inputs = base.__class__(
            **{
                **base.__dict__,
                "tightening_torque_nm": 0,
                "percent_tys": 50,
                "use_standard_torque": False,
            }
        )
        result = calculate_ctp(inputs, record, get_material_yield(conn, inputs.material_code))

        self.assertTrue(
            math.isclose(
                result.axial_pretension_n,
                0.5 * result.tensile_stress_area_mm2 * result.tensile_yield_mpa,
                rel_tol=1e-9,
            )
        )
        self.assertTrue(math.isclose(result.tightening_torque_nm, 239.5784128, rel_tol=1e-6))
        self.assertTrue(math.isclose(result.preload_percent_tys, 50, rel_tol=1e-9))

    def test_ctp_thread_pullout_uses_friction_source_branch(self):
        conn = connect()
        record = get_ctp_screw_record(conn, "1512", "47xx")
        base = default_ctp_inputs(record)

        emuge_result = calculate_ctp(base, record, get_material_yield(conn, base.material_code))
        light_oil = base.__class__(**{**base.__dict__, "screw_nut_friction_source": "Light Oil"})
        light_oil_result = calculate_ctp(light_oil, record, get_material_yield(conn, light_oil.material_code))

        self.assertTrue(math.isclose(emuge_result.thread_pullout_stress_mpa, 412.005297, rel_tol=1e-6))
        self.assertTrue(math.isclose(light_oil_result.thread_pullout_stress_mpa, 834.679914, rel_tol=1e-6))

    def test_ctp_tapped_hole_yield_is_checked_against_pullout_stress(self):
        conn = connect()
        record = get_ctp_screw_record(conn, "1512", "47xx")
        base = default_ctp_inputs(record)
        inputs = base.__class__(**{**base.__dict__, "tapped_hole_yield_mpa": 300})

        result = calculate_ctp(inputs, record, get_material_yield(conn, inputs.material_code))

        self.assertIn("Tapped hole yield strength 300.0 MPa is below thread pull-out stress", "\n".join(result.warnings))

    def test_ctp_direct_tightening_torque_overrides_standard(self):
        conn = connect()
        record = get_ctp_screw_record(conn, "1512", "47xx")
        base = default_ctp_inputs(record)
        inputs = base.__class__(**{**base.__dict__, "tightening_torque_nm": 200})
        result = calculate_ctp(inputs, record, get_material_yield(conn, inputs.material_code))

        self.assertEqual(result.tightening_torque_nm, 200)
        self.assertTrue(math.isclose(result.preload_percent_tys, 41.73998768, rel_tol=1e-6))
        self.assertLess(result.axial_pretension_n, 128891.948947)

    def test_ctp_checking_standard_applies_api671_yield_limits(self):
        conn = connect()
        record = get_ctp_screw_record(conn, "1512", "47xx")
        base = default_ctp_inputs(record)

        fifth = calculate_ctp(base, record, get_material_yield(conn, base.material_code))
        self.assertIn(
            "Continuous bolt shear/bending safety factor is below 1.50 for API671 5th edition.",
            fifth.warnings,
        )
        self.assertEqual(fifth.case_yield_sf_limits, (1.5, 1.15, 1.0))

        fourth_inputs = base.__class__(**{**base.__dict__, "checking_standard": "API671 4th edition"})
        fourth = calculate_ctp(fourth_inputs, record, get_material_yield(conn, fourth_inputs.material_code))
        self.assertNotIn(
            "Continuous bolt shear/bending safety factor is below 1.50 for API671 5th edition.",
            fourth.warnings,
        )
        self.assertEqual(fourth.case_yield_sf_limits, (1.25, 1.15, 1.0))

    def test_ctp_joint_type_controls_leverarm_and_tys_limit(self):
        conn = connect()
        record = get_ctp_screw_record(conn, "1512", "47xx")
        base = default_ctp_inputs(record)

        stripper = calculate_ctp(base, record, get_material_yield(conn, base.material_code))
        self.assertEqual(stripper.joint_type, "Stripper bolt")
        self.assertEqual(stripper.leverarm_mm, 0.05)
        self.assertEqual(stripper.preload_percent_tys_limit, 60)
        self.assertIn("maximum is 60% for Stripper bolt.", "\n".join(stripper.warnings))

        drive_inputs = base.__class__(**{**base.__dict__, "joint_type": "Drive bolt", "pack_thickness_mm": 20})
        drive = calculate_ctp(drive_inputs, record, get_material_yield(conn, drive_inputs.material_code))
        self.assertEqual(drive.leverarm_mm, 3.0)
        self.assertEqual(drive.preload_percent_tys_limit, 75)

        shim_inputs = base.__class__(**{**base.__dict__, "joint_type": "Shim", "pack_thickness_mm": 10})
        shim = calculate_ctp(shim_inputs, record, get_material_yield(conn, shim_inputs.material_code))
        self.assertEqual(shim.leverarm_mm, 1.5)
        self.assertEqual(shim.preload_percent_tys_limit, 60)

    def test_ctp_drive_and_shim_require_pack_thickness(self):
        conn = connect()
        record = get_ctp_screw_record(conn, "1512", "47xx")
        base = default_ctp_inputs(record)
        drive_without_pack = base.__class__(**{**base.__dict__, "joint_type": "Drive bolt", "pack_thickness_mm": 0})

        with self.assertRaisesRegex(ValueError, "Pack thickness is required"):
            calculate_ctp(drive_without_pack, record, get_material_yield(conn, drive_without_pack.material_code))

    def test_ctp_rejects_tightening_torque_and_percent_tys_together(self):
        conn = connect()
        record = get_ctp_screw_record(conn, "1512", "47xx")
        base = default_ctp_inputs(record)
        inputs = base.__class__(**{**base.__dict__, "tightening_torque_nm": 200, "percent_tys": 50})

        with self.assertRaisesRegex(ValueError, "either tightening torque or %TYS"):
            calculate_ctp(inputs, record, get_material_yield(conn, inputs.material_code))

    def test_ctp_residual_torque_and_shear_split(self):
        conn = connect()
        record = get_ctp_screw_record(conn, "1512", "47xx")
        inputs = default_ctp_inputs(record)
        result = calculate_ctp(inputs, record, get_material_yield(conn, inputs.material_code))
        peak = result.torque_cases[1]

        self.assertTrue(math.isclose(peak.residual_torque_nm, 36988.97411555714, rel_tol=1e-9))
        self.assertTrue(math.isclose(peak.shear_load_per_joint_n, 16549.876561770532, rel_tol=1e-9))
        self.assertEqual(peak.sleeve_safety_factor, "No Sleeve")

    def test_ctp_sleeve_and_groove_absent_present_behaviour(self):
        conn = connect()
        record = get_ctp_screw_record(conn, "1512", "47xx")
        base = default_ctp_inputs(record)
        no_groove = base.__class__(**{**base.__dict__, "groove_diameter_mm": 0})
        no_groove_result = calculate_ctp(no_groove, record, get_material_yield(conn, base.material_code))
        self.assertEqual(no_groove_result.groove_safety_factor, "No groove")
        self.assertEqual(no_groove_result.sleeve_preload_safety_factor, "No Sleeve")

        with_groove = base.__class__(**{**base.__dict__, "groove_diameter_mm": 12})
        with_groove_result = calculate_ctp(with_groove, record, get_material_yield(conn, base.material_code))
        self.assertEqual(with_groove_result.groove_diameter_mm, 12)
        self.assertIsInstance(with_groove_result.groove_safety_factor, float)

        gagging_sleeve = base.__class__(**{**base.__dict__, "sleeve_outer_diameter_mm": 16})
        gagging_result = calculate_ctp(gagging_sleeve, record, get_material_yield(conn, base.material_code))
        self.assertEqual(gagging_result.sleeve_preload_safety_factor, "Gagging")

        with_sleeve = base.__class__(**{**base.__dict__, "sleeve_outer_diameter_mm": 24})
        sleeve_result = calculate_ctp(with_sleeve, record, get_material_yield(conn, base.material_code))
        self.assertIsInstance(sleeve_result.torque_cases[1].sleeve_safety_factor, float)
        self.assertTrue(math.isclose(sleeve_result.sleeve_preload_safety_factor, 1.2479409705, rel_tol=1e-6))
        self.assertIn("Sleeve preload safety factor is below minimum 1.25.", sleeve_result.warnings)

        recommended_sleeve = base.__class__(**{**base.__dict__, "sleeve_outer_diameter_mm": 24.1})
        recommended_result = calculate_ctp(recommended_sleeve, record, get_material_yield(conn, base.material_code))
        self.assertTrue(math.isclose(recommended_result.sleeve_preload_safety_factor, 1.2666990833, rel_tol=1e-6))
        self.assertIn(
            "Sleeve preload safety factor is below recommended 1.50; minimum is 1.25.",
            recommended_result.warnings,
        )

if __name__ == "__main__":
    unittest.main()
