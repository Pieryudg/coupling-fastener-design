import math
import sys
import unittest
from dataclasses import replace
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

from ctp_calculations import (  # noqa: E402
    calculate_ctp,
    solve_bending_torque_share,
    solve_preload_for_bending,
    solve_sleeve_od,
)
from ctp_database import (  # noqa: E402
    build_ctp_friction,
    default_ctp_inputs,
    get_ctp_material,
    get_ctp_variant,
    list_ctp_friction_labels,
    standard_tightening_torque_nm,
)


class CTP0007Tests(unittest.TestCase):
    def test_default_ctp_golden_values_match_cached_workbook(self):
        result = calculate_ctp(default_ctp_inputs())

        self.assertTrue(math.isclose(result.preload_n, 128891.948946884, rel_tol=1e-12))
        self.assertTrue(math.isclose(result.friction_torque_nm, 43211.025884442861, rel_tol=1e-12))
        self.assertTrue(
            math.isclose(
                result.case("momentary").torque_ratio.value,
                0.468513779512554,
                rel_tol=1e-12,
            )
        )
        self.assertTrue(
            math.isclose(
                result.case("momentary").bolt_safety_factor.value,
                1.2536471142890915,
                rel_tol=1e-12,
            )
        )
        self.assertTrue(
            math.isclose(
                result.thread_root_safety_factor.value,
                0.9677950537105884,
                rel_tol=1e-12,
            )
        )
        self.assertIn("0.968 Check", result.check_summary)

    def test_lookup_seed_covers_default_workbook_selection(self):
        variant = get_ctp_variant("1512", "47xx")
        material = get_ctp_material("0225 (Classe 12-9)")

        self.assertEqual(variant["thread_diameter_mm"], 16.0)
        self.assertEqual(variant["pitch_mm"], 2.0)
        self.assertEqual(variant["contact_diameter_mm"], 24.0)
        self.assertEqual(material.yield_strength_mpa, 1080.0)
        self.assertEqual(
            standard_tightening_torque_nm("1512", "47xx", "0225 (Classe 12-9)"),
            365.0,
        )
        self.assertIn("API 671", list_ctp_friction_labels())

    def test_custom_friction_and_torque_input_take_precedence(self):
        base = default_ctp_inputs()
        custom_friction = build_ctp_friction(
            screw_nut_label="Custom",
            nut_part_label="Custom",
            part_part_label="Custom",
            custom_screw_nut_mu=0.2,
            custom_nut_part_mu=0.11,
            custom_part_part_mu=0.18,
        )
        inputs = replace(
            base,
            friction=custom_friction,
            tightening_torque_nm=100.0,
            preload_percent_of_yield=50.0,
            standard_tightening_torque_nm=365.0,
        )
        result = calculate_ctp(inputs)

        denominator = (
            0.16 * result.pitch_mm
            + 0.583 * 0.2 * result.pitch_diameter_mm
            + 0.11 * result.average_nut_radius_mm
        )
        self.assertEqual(result.tightening_torque_nm, 100.0)
        self.assertTrue(math.isclose(result.preload_n, 100000.0 / denominator))
        self.assertEqual(result.inputs.friction.part_part_mu, 0.18)

    def test_no_sleeve_active_sleeve_no_groove_and_shear_plane_edges(self):
        base = default_ctp_inputs()
        no_sleeve = calculate_ctp(base)
        with_sleeve = calculate_ctp(replace(base, sleeve_outer_diameter_mm=30.0))
        shank_inputs = replace(
            base,
            geometry=replace(base.geometry, shear_plane="Shank", groove_diameter_mm=10.0),
        )
        shank_result = calculate_ctp(shank_inputs)

        self.assertEqual(no_sleeve.case("momentary").sleeve_safety_factor.status, "No Sleeve")
        self.assertEqual(no_sleeve.groove_axial_stress.status, "No groove")
        self.assertEqual(with_sleeve.case("momentary").sleeve_safety_factor.status, "OK")
        self.assertEqual(shank_result.shear_bending_diameter_mm, base.geometry.shank_diameter_mm)
        self.assertEqual(shank_result.groove_safety_factor.status, "OK")

    def test_zero_torque_reports_torque_status(self):
        result = calculate_ctp(replace(default_ctp_inputs(), continuous_torque_nm=0.0))

        self.assertEqual(result.case("continuous").torque_ratio.status, "Torque ?")
        self.assertEqual(result.case("peak").torque_ratio.status, "Torque ?")
        self.assertEqual(result.case("momentary").torque_ratio.status, "Torque ?")

    def test_goal_seek_equivalent_solvers_return_explicit_status(self):
        inputs = default_ctp_inputs()
        sleeve = solve_sleeve_od(inputs, target_sf=1.0)
        torque_share = solve_bending_torque_share(inputs, target_sf=1.00001)
        preload = solve_preload_for_bending(inputs, target_sf=1.00001)
        impossible = solve_sleeve_od(inputs, target_sf=1_000_000.0)

        self.assertTrue(sleeve.converged)
        self.assertIsNotNone(sleeve.result)
        self.assertTrue(torque_share.converged)
        self.assertGreaterEqual(
            torque_share.result.case("momentary").bolt_safety_factor.value,
            1.00001,
        )
        self.assertTrue(preload.converged)
        self.assertGreaterEqual(
            preload.result.case("momentary").bolt_safety_factor.value,
            1.00001,
        )
        self.assertFalse(impossible.converged)
        self.assertIn("not bracketed", impossible.message)


if __name__ == "__main__":
    unittest.main()
