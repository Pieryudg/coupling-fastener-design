import math
import sys
import unittest
from dataclasses import replace
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

from bolt_database import connect, get_bolt_size, get_property_class, recommend_bolt_size
from coupling_calculations import CouplingInputs, calculate, effective_radius
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


if __name__ == "__main__":
    unittest.main()
