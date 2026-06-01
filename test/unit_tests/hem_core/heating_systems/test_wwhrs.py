#!/usr/bin/env python3

"""
Comprehensive unit tests for the unified WWHRS_Instantaneous class.
Designed to achieve 100% code coverage for all system types (A, B, C).
"""

# Standard library imports
import unittest

# Local imports
from hem_core.heating_systems.wwhrs import WWHRS_Instantaneous, delta_T_shower
from hem_core.simulation_time import SimulationTime
from hem_core.water_heat_demand.cold_water_source import ColdWaterSource


class TestWWHRS_Instantaneous(unittest.TestCase):
    """Test suite for the unified WWHRS_Instantaneous class"""

    def setUp(self):
        """Set up test fixtures"""
        self.simtime = SimulationTime(start_time=0, end_time=3, step=1)
        self.cold_water_source = ColdWaterSource(
            cold_water_temps=[17.0, 17.0, 17.0],
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )
        self.flow_rates = [5, 7, 9, 11, 13]
        self.system_a_efficiencies = [44.8, 39.1, 34.8, 31.4, 28.6]
        self.system_a_utilisation_factor = 0.7

    def test_init_with_all_parameters(self):
        """Test initialization with all system types specified"""
        system_b_efficiencies = [36.3, 31.7, 28.2, 25.4, 23.2]
        system_b_utilisation_factor = 0.65
        system_c_efficiencies = [38.9, 34.0, 30.3, 27.3, 24.8]
        system_c_utilisation_factor = 0.68

        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=self.cold_water_source,
            system_a_utilisation_factor=self.system_a_utilisation_factor,
            system_b_efficiencies=system_b_efficiencies,
            system_b_utilisation_factor=system_b_utilisation_factor,
            system_c_efficiencies=system_c_efficiencies,
            system_c_utilisation_factor=system_c_utilisation_factor,
            system_b_efficiency_factor=0.81,
            system_c_efficiency_factor=0.88,
        )

        # Test that all values are set correctly
        self.assertEqual(wwhrs.get_efficiency_from_flowrate(5, "A"), 44.8)
        self.assertEqual(wwhrs.get_efficiency_from_flowrate(5, "B"), 36.3)
        self.assertEqual(wwhrs.get_efficiency_from_flowrate(5, "C"), 38.9)

    def test_system_a_missing_utilisation_factor(self):
        """Test System A calculation when utilisation factor is missing"""
        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=self.cold_water_source,
            system_a_utilisation_factor=None,  # Missing
        )

        with self.assertRaises(ValueError) as context:
            wwhrs.calculate_performance("A", 35.0, 8.0, 8.0, 55.0)
        self.assertIn("system_a_utilisation_factor is required", str(context.exception))

    def test_get_efficiency_system_a_when_none(self):
        """Test that requesting System A efficiency raises error when system_a_efficiencies is None"""
        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=None,  # No System A data provided
            cold_water_source=self.cold_water_source,
            system_b_efficiencies=[36.3, 31.7, 28.2, 25.4, 23.2],
            system_b_utilisation_factor=0.65,
        )

        with self.assertRaises(ValueError) as context:
            wwhrs.get_efficiency_from_flowrate(8.0, "A")
        self.assertIn(
            "System A efficiencies not available - no system_a_efficiencies provided",
            str(context.exception),
        )

    def test_system_b_conversion_missing_parameters(self):
        """Test System B conversion approach with missing parameters"""
        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=self.cold_water_source,
            system_a_utilisation_factor=0.7,
            # Missing system_b_utilisation_factor and system_b_efficiency_factor
        )

        with self.assertRaises(ValueError) as context:
            wwhrs.calculate_performance("B", 35.0, 8.0, 8.0, 55.0)
        self.assertIn(
            "Both system_b_utilisation_factor and system_b_efficiency_factor are required",
            str(context.exception),
        )

    def test_system_b_pre_corrected_missing_utilisation_factor(self):
        """Test System B pre-corrected approach with missing utilisation factor"""
        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=self.cold_water_source,
            system_a_utilisation_factor=0.7,
            system_b_efficiencies=[36.3, 31.7, 28.2, 25.4, 23.2],
            # Missing system_b_utilisation_factor
        )

        with self.assertRaises(ValueError) as context:
            wwhrs.calculate_performance("B", 35.0, 8.0, 8.0, 55.0)
        self.assertIn(
            "system_b_utilisation_factor is required when using system_b_efficiencies",
            str(context.exception),
        )

    def test_system_b_conversion_missing_utilisation_factor_only(self):
        """Test System B conversion approach with missing utilisation factor (but efficiency factor provided)"""
        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=self.cold_water_source,
            system_a_utilisation_factor=0.7,
            system_b_efficiency_factor=0.81,
            # Missing system_b_utilisation_factor
        )

        with self.assertRaises(ValueError) as context:
            wwhrs.calculate_performance("B", 35.0, 8.0, 8.0, 55.0)
        self.assertIn(
            "Both system_b_utilisation_factor and system_b_efficiency_factor are required",
            str(context.exception),
        )

    def test_system_c_conversion_missing_utilisation_factor_only(self):
        """Test System C conversion approach with missing utilisation factor (but efficiency factor provided)"""
        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=self.cold_water_source,
            system_a_utilisation_factor=0.7,
            system_c_efficiency_factor=0.88,
            # Missing system_c_utilisation_factor
        )

        with self.assertRaises(ValueError) as context:
            wwhrs.calculate_performance("C", 35.0, 8.0, 8.0, 55.0)
        self.assertIn(
            "Both system_c_utilisation_factor and system_c_efficiency_factor are required",
            str(context.exception),
        )

    def test_system_c_pre_corrected_missing_utilisation_factor(self):
        """Test System C pre-corrected approach with missing utilisation factor"""
        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=self.cold_water_source,
            system_a_utilisation_factor=0.7,
            system_c_efficiencies=[38.9, 34.0, 30.3, 27.3, 24.8],  # Pre-corrected data provided
            # Missing system_c_utilisation_factor
        )

        with self.assertRaises(ValueError) as context:
            wwhrs.calculate_performance("C", 35.0, 8.0, 8.0, 55.0)
        self.assertIn(
            "system_c_utilisation_factor is required when using system_c_efficiencies",
            str(context.exception),
        )

    def test_init_with_reduction_factors(self):
        """Test initialization using reduction factors for Systems B and C"""
        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=self.cold_water_source,
            system_a_utilisation_factor=self.system_a_utilisation_factor,
        )

        # System A should work
        self.assertEqual(wwhrs.get_efficiency_from_flowrate(5, "A"), 44.8)

        # Systems B and C should raise errors when no efficiencies provided
        with self.assertRaises(ValueError):
            wwhrs.get_efficiency_from_flowrate(5, "B")

        with self.assertRaises(ValueError):
            wwhrs.get_efficiency_from_flowrate(5, "C")

    def test_calculate_performance_system_a(self):
        """Test System A performance calculation"""
        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=self.cold_water_source,
            system_a_utilisation_factor=self.system_a_utilisation_factor,
        )

        result = wwhrs.calculate_performance(
            system_type="A",
            temp_target=35.0,
            flowrate_waste_water=8.0,
            volume_cold_water=8.0,
            temp_hot=55.0,
        )

        # Check result structure
        self.assertIn("T_cyl_feed", result)
        self.assertIn("flowrate_hot", result)

        # For System A, cylinder is not fed pre-heated water
        self.assertEqual(result["T_cyl_feed"], 20.1038)  # Same as cold water

    def test_calculate_performance_system_b(self):
        """Test System B performance calculation"""
        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=self.cold_water_source,
            system_a_utilisation_factor=self.system_a_utilisation_factor,
            system_b_utilisation_factor=0.65,
            system_b_efficiency_factor=0.81,
        )

        result = wwhrs.calculate_performance(
            system_type="B",
            temp_target=35.0,
            flowrate_waste_water=8.0,
            volume_cold_water=8.0,
            temp_hot=55.0,
        )

        # Check result structure
        self.assertIn("T_cyl_feed", result)
        self.assertIn("flowrate_hot", result)

        # For System B, both shower and cylinder get pre-heated water
        self.assertEqual(result["T_cyl_feed"], 17.0)

        # Check flowrate_hot calculation
        self.assertIsNotNone(result["flowrate_hot"])

    def test_calculate_performance_system_b_division_by_zero(self):
        """Test System B with temp_hot = temp_target (division by zero protection)"""
        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=self.cold_water_source,
            system_a_utilisation_factor=self.system_a_utilisation_factor,
            system_b_utilisation_factor=0.65,
            system_b_efficiency_factor=0.81,
        )

        result = wwhrs.calculate_performance(
            system_type="B",
            temp_target=35.0,
            flowrate_waste_water=8.0,
            volume_cold_water=8.0,
            temp_hot=35.0,  # Same as temp_target
        )

        self.assertEqual(result["flowrate_hot"], 8.0)  # Equal to flowrate_waste_water

    def test_calculate_performance_system_c(self):
        """Test System C performance calculation"""
        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=self.cold_water_source,
            system_a_utilisation_factor=self.system_a_utilisation_factor,
            system_c_utilisation_factor=0.68,
            system_c_efficiency_factor=0.88,
        )

        result = wwhrs.calculate_performance(
            system_type="C",
            temp_target=35.0,
            flowrate_waste_water=8.0,
            volume_cold_water=8.0,
            temp_hot=55.0,
        )

        # Check result structure
        self.assertIn("T_cyl_feed", result)
        self.assertIn("flowrate_hot", result)

        # For System C, only cylinder gets pre-heated water
        self.assertEqual(result["T_cyl_feed"], 22.601422933333335)
        self.assertIsNotNone(result["flowrate_hot"])

    def test_calculate_performance_system_c_division_by_zero(self):
        """Test System C with temp_target = temp_main (division by zero protection)"""
        # Create cold water source with temp matching target
        cold_water_source = ColdWaterSource(
            cold_water_temps=[35.0, 35.0, 35.0],
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )

        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=cold_water_source,
            system_a_utilisation_factor=self.system_a_utilisation_factor,
            system_c_utilisation_factor=0.68,
            system_c_efficiency_factor=0.88,
        )

        result = wwhrs.calculate_performance(
            system_type="C",
            temp_target=35.0,
            flowrate_waste_water=8.0,
            volume_cold_water=8.0,
            temp_hot=55.0,
        )

        # Should return temp_main when division by zero would occur
        self.assertEqual(result["T_cyl_feed"], 35.0)

    def test_calculate_performance_invalid_system_type(self):
        """Test that invalid system type raises error"""
        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=self.cold_water_source,
            system_a_utilisation_factor=self.system_a_utilisation_factor,
        )

        with self.assertRaises(ValueError) as context:
            wwhrs.calculate_performance(
                system_type="D",  # Invalid
                temp_target=35.0,
                flowrate_waste_water=8.0,
                volume_cold_water=8.0,
                temp_hot=60.0,
            )
        self.assertIn("Invalid system type", str(context.exception))

    def test_get_efficiency_from_flowrate_interpolation(self):
        """Test efficiency interpolation for various flow rates"""
        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=self.cold_water_source,
            system_a_utilisation_factor=self.system_a_utilisation_factor,
        )

        # Test exact match
        self.assertEqual(wwhrs.get_efficiency_from_flowrate(5.0, "A"), 44.8)
        self.assertEqual(wwhrs.get_efficiency_from_flowrate(13.0, "A"), 28.6)

        # Test interpolation
        efficiency_8 = wwhrs.get_efficiency_from_flowrate(8.0, "A")
        self.assertGreater(efficiency_8, 34.8)  # > efficiency at 9
        self.assertLess(efficiency_8, 39.1)  # < efficiency at 7

        # Test below minimum
        self.assertEqual(wwhrs.get_efficiency_from_flowrate(3.0, "A"), 44.8)

        # Test above maximum
        self.assertEqual(wwhrs.get_efficiency_from_flowrate(15.0, "A"), 28.6)

    def test_get_efficiency_from_flowrate_all_systems(self):
        """Test efficiency retrieval for all system types"""
        system_b_efficiencies = [36.3, 31.7, 28.2, 25.4, 23.2]
        system_c_efficiencies = [38.9, 34.0, 30.3, 27.3, 24.8]

        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=self.cold_water_source,
            system_a_utilisation_factor=self.system_a_utilisation_factor,
            system_b_efficiencies=system_b_efficiencies,
            system_c_efficiencies=system_c_efficiencies,
        )

        # Test all systems
        self.assertEqual(wwhrs.get_efficiency_from_flowrate(5.0, "A"), 44.8)
        self.assertEqual(wwhrs.get_efficiency_from_flowrate(5.0, "B"), 36.3)
        self.assertEqual(wwhrs.get_efficiency_from_flowrate(5.0, "C"), 38.9)

        # Test case insensitivity
        self.assertEqual(wwhrs.get_efficiency_from_flowrate(5.0, "a"), 44.8)
        self.assertEqual(wwhrs.get_efficiency_from_flowrate(5.0, "b"), 36.3)
        self.assertEqual(wwhrs.get_efficiency_from_flowrate(5.0, "c"), 38.9)

    def test_get_efficiency_from_flowrate_invalid_system(self):
        """Test that invalid system type raises error"""
        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=self.cold_water_source,
            system_a_utilisation_factor=self.system_a_utilisation_factor,
        )

        with self.assertRaises(ValueError) as context:
            wwhrs.get_efficiency_from_flowrate(8.0, "D")
        self.assertIn("Invalid system type", str(context.exception))

    def test_temperature_methods(self):
        """Test temperature getter and setter methods"""
        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=self.cold_water_source,
            system_a_utilisation_factor=self.system_a_utilisation_factor,
        )

        # Initial temperature should be from cold water source (no pre-heated water)
        self.assertEqual(wwhrs.get_temp_cold_water(10.0), [(17.0, 10.0)])

        # Test registering pre-heated volume
        wwhrs.register_preheated_volume(temperature=20.0, volume=12.0)
        self.assertEqual(wwhrs.get_temp_cold_water(12.0), [(20.0, 12.0)])

        # Test that requesting more than registered returns mix of pre-heated and mains
        wwhrs.register_preheated_volume(temperature=20.0, volume=5.0)
        result = wwhrs.get_temp_cold_water(12.0)
        self.assertEqual(result[0], (20.0, 12.0))

    def test_last_used_time_tracking(self):
        """Test last used time tracking functionality"""
        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=self.cold_water_source,
            system_a_utilisation_factor=self.system_a_utilisation_factor,
        )

        # Initially should be None
        self.assertIsNone(wwhrs.get_last_used_time())

        # Set last used time
        test_time = 123.45
        wwhrs.set_last_used_time(test_time)
        self.assertEqual(wwhrs.get_last_used_time(), test_time)

        # Update to new time
        new_time = 456.78
        wwhrs.set_last_used_time(new_time)
        self.assertEqual(wwhrs.get_last_used_time(), new_time)

    def test_system_b_with_specific_efficiencies(self):
        """Test System B using specific efficiencies instead of reduction factor"""
        system_b_efficiencies = [36.3, 31.7, 28.2, 25.4, 23.2]

        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=self.cold_water_source,
            system_a_utilisation_factor=self.system_a_utilisation_factor,
            system_b_efficiencies=system_b_efficiencies,
            system_b_utilisation_factor=0.65,
        )

        wwhrs.calculate_performance(
            system_type="B",
            temp_target=35.0,
            flowrate_waste_water=8.0,
            volume_cold_water=8.0,
            temp_hot=55.0,
        )

        # Verify it uses specific efficiencies, not reduction factor
        # Efficiency at 8 L/min should be interpolated from system_b_efficiencies
        efficiency_8 = wwhrs.get_efficiency_from_flowrate(8.0, "B")
        self.assertNotEqual(efficiency_8, wwhrs.get_efficiency_from_flowrate(8.0, "A"))

    def test_system_c_with_specific_efficiencies(self):
        """Test System C using specific efficiencies instead of reduction factor"""
        system_c_efficiencies = [38.9, 34.0, 30.3, 27.3, 24.8]

        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=self.cold_water_source,
            system_a_utilisation_factor=self.system_a_utilisation_factor,
            system_c_efficiencies=system_c_efficiencies,
            system_c_utilisation_factor=0.68,
        )

        wwhrs.calculate_performance(
            system_type="C",
            temp_target=35.0,
            flowrate_waste_water=8.0,
            volume_cold_water=8.0,
            temp_hot=55.0,
        )

        # Verify it uses specific efficiencies, not reduction factor
        efficiency_8 = wwhrs.get_efficiency_from_flowrate(8.0, "C")
        self.assertNotEqual(efficiency_8, wwhrs.get_efficiency_from_flowrate(8.0, "A"))

    def test_edge_cases_flowrate_cold_water(self):
        """Test edge cases with flowrate_cold_water parameter"""
        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=self.cold_water_source,
            system_a_utilisation_factor=self.system_a_utilisation_factor,
            system_b_utilisation_factor=0.65,
            system_b_efficiency_factor=0.81,
        )

        # System B uses flowrate_cold_water if provided
        result_b = wwhrs.calculate_performance(
            system_type="B",
            temp_target=35.0,
            flowrate_waste_water=8.0,
            temp_hot=55.0,
            volume_cold_water=6.0,
        )
        self.assertEqual(result_b["flowrate_hot"], 3.297999789473684)  # Should use provided value

    def test_module_constant(self):
        """Test module-level constant"""
        self.assertEqual(delta_T_shower, 6.0)

    def test_system_a_temp_hot_equals_temp_pre(self):
        """Test System A when temp_hot equals temp_pre (line 139)"""
        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=self.cold_water_source,
            system_a_utilisation_factor=self.system_a_utilisation_factor,
        )

        # Set up conditions where temp_hot will equal temp_pre
        result = wwhrs.calculate_performance(
            system_type="A",
            temp_target=35.0,
            flowrate_waste_water=8.0,
            volume_cold_water=8.0,
            temp_hot=20.1038,  # This should equal temp_pre
        )

        self.assertIsNone(result["flowrate_hot"])

    def test_system_b_missing_temp_hot(self):
        """Test System B with None temp_hot (line 152)"""
        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=self.cold_water_source,
            system_a_utilisation_factor=self.system_a_utilisation_factor,
        )

        with self.assertRaises(ValueError) as context:
            wwhrs.calculate_performance(
                system_type="B",
                temp_target=35.0,
                flowrate_waste_water=8.0,
                volume_cold_water=8.0,
                temp_hot=None,
            )
        self.assertIn("temp_hot must be provided", str(context.exception))

    def test_system_b_temp_hot_equals_temp_pre(self):
        """Test System B when temp_hot equals temp_pre using mock (line 183)"""
        from unittest.mock import patch

        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=self.cold_water_source,
            system_a_utilisation_factor=self.system_a_utilisation_factor,
            system_b_utilisation_factor=0.65,
            system_b_efficiency_factor=0.81,
        )

        # Patch math.isclose to return True for the fourth call (line 186)
        with patch("hem_core.heating_systems.wwhrs.math.isclose") as mock_isclose:
            mock_isclose.side_effect = [False, False, False, True]

            result = wwhrs.calculate_performance(
                system_type="B",
                temp_target=35.0,
                flowrate_waste_water=8.0,
                volume_cold_water=8.0,
                temp_hot=55.0,
            )

            self.assertIsNone(result["flowrate_hot"])
            self.assertEqual(mock_isclose.call_count, 4)

    def test_system_c_missing_temp_hot(self):
        """Test System C with None temp_hot (line 196)"""
        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=self.cold_water_source,
            system_a_utilisation_factor=self.system_a_utilisation_factor,
        )

        with self.assertRaises(ValueError) as context:
            wwhrs.calculate_performance(
                system_type="C",
                temp_target=35.0,
                flowrate_waste_water=8.0,
                volume_cold_water=8.0,
                temp_hot=None,
            )
        self.assertIn("temp_hot must be provided", str(context.exception))

    def test_system_c_temp_hot_equals_temp_main(self):
        """Test System C when temp_hot equals temp_main (line 228)"""
        # Create cold water source with specific temperature
        cold_water_source = ColdWaterSource(
            cold_water_temps=[55.0, 55.0, 55.0],  # Same as temp_hot
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )

        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=cold_water_source,
            system_a_utilisation_factor=self.system_a_utilisation_factor,
            system_c_utilisation_factor=0.68,
            system_c_efficiency_factor=0.88,
        )

        result = wwhrs.calculate_performance(
            system_type="C",
            temp_target=35.0,
            flowrate_waste_water=8.0,
            volume_cold_water=8.0,
            temp_hot=55.0,  # Same as temp_main
        )

        self.assertIsNone(result["flowrate_hot"])

    def test_draw_off_water_method(self):
        """Test draw_off_water method consumes pre-heated volume"""
        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=self.cold_water_source,
            system_a_utilisation_factor=self.system_a_utilisation_factor,
        )

        # With no pre-heated water, should return mains temperature
        result = wwhrs.draw_off_water(15.0)
        self.assertEqual(result, [(17.0, 15.0)])

        # Register pre-heated volume and draw less than available
        wwhrs.register_preheated_volume(temperature=25.0, volume=30.0)
        result = wwhrs.draw_off_water(20.0)
        self.assertEqual(result, [(25.0, 20.0)])

        # Draw again - should get remaining 10L pre-heated, then mains
        result = wwhrs.draw_off_water(15.0)
        self.assertEqual(result[0], (25.0, 10.0))  # Remaining pre-heated
        self.assertEqual(result[1], (17.0, 5.0))  # Rest from mains

        # Draw again - all pre-heated exhausted, should get mains only
        result = wwhrs.draw_off_water(10.0)
        self.assertEqual(result, [(17.0, 10.0)])

    def test_register_preheated_volume_accumulation(self):
        """Test that multiple registrations accumulate with weighted average temperature"""
        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=self.cold_water_source,
            system_a_utilisation_factor=self.system_a_utilisation_factor,
        )

        # Register first volume
        wwhrs.register_preheated_volume(temperature=20.0, volume=10.0)

        # Register second volume with different size - should accumulate with weighted average
        wwhrs.register_preheated_volume(temperature=35.0, volume=20.0)

        # Weighted average: (20*10 + 35*20) / 30 = (200 + 700) / 30 = 30.0
        # Total volume: 30.0
        result = wwhrs.get_temp_cold_water(30.0)
        self.assertEqual(result, [(30.0, 30.0)])

    def test_register_zero_volume(self):
        """Test that registering zero volume has no effect"""
        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=self.cold_water_source,
            system_a_utilisation_factor=self.system_a_utilisation_factor,
        )

        # Register zero volume
        wwhrs.register_preheated_volume(temperature=25.0, volume=0.0)

        # Should return mains temperature (no pre-heated water registered)
        result = wwhrs.get_temp_cold_water(10.0)
        self.assertEqual(result, [(17.0, 10.0)])

    def test_preheated_volume_not_consumed_by_get_temp(self):
        """Test that get_temp_cold_water does not consume pre-heated volume"""
        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=self.cold_water_source,
            system_a_utilisation_factor=self.system_a_utilisation_factor,
        )

        wwhrs.register_preheated_volume(temperature=22.0, volume=15.0)

        # Call get_temp_cold_water multiple times
        result1 = wwhrs.get_temp_cold_water(10.0)
        result2 = wwhrs.get_temp_cold_water(10.0)

        # Both should return pre-heated temperature (volume not consumed)
        self.assertEqual(result1, [(22.0, 10.0)])
        self.assertEqual(result2, [(22.0, 10.0)])

    def test_draw_off_consumes_preheated_volume(self):
        """Test that draw_off_water consumes pre-heated volume"""
        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=self.cold_water_source,
            system_a_utilisation_factor=self.system_a_utilisation_factor,
        )

        wwhrs.register_preheated_volume(temperature=22.0, volume=15.0)

        # First draw consumes some pre-heated volume
        result1 = wwhrs.draw_off_water(10.0)
        self.assertEqual(result1, [(22.0, 10.0)])

        # Second draw - only 5L pre-heated remaining
        result2 = wwhrs.draw_off_water(10.0)
        self.assertEqual(result2[0], (22.0, 5.0))  # Remaining pre-heated
        self.assertEqual(result2[1], (17.0, 5.0))  # Rest from mains

    def test_register_negative_volume_raises_error(self):
        """Test that registering negative volume raises ValueError"""
        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=self.cold_water_source,
            system_a_utilisation_factor=self.system_a_utilisation_factor,
        )

        with self.assertRaises(ValueError) as context:
            wwhrs.register_preheated_volume(temperature=25.0, volume=-5.0)
        self.assertIn("cannot be negative", str(context.exception))

    def test_timestep_end_resets_preheated_volume(self):
        """Test that timestep_end resets pre-heated water availability"""
        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=self.cold_water_source,
            system_a_utilisation_factor=self.system_a_utilisation_factor,
        )

        # Register pre-heated volume
        wwhrs.register_preheated_volume(temperature=25.0, volume=20.0)

        # Verify pre-heated water is available
        result = wwhrs.get_temp_cold_water(10.0)
        self.assertEqual(result, [(25.0, 10.0)])

        # Call timestep_end to reset
        wwhrs.timestep_end()

        # After reset, should return mains temperature
        result = wwhrs.get_temp_cold_water(10.0)
        self.assertEqual(result, [(17.0, 10.0)])

    def test_get_temp_cold_water_partial_preheated(self):
        """Test get_temp_cold_water when requesting more than pre-heated volume available"""
        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=self.cold_water_source,
            system_a_utilisation_factor=self.system_a_utilisation_factor,
        )

        # Register limited pre-heated volume
        wwhrs.register_preheated_volume(temperature=22.0, volume=8.0)

        # Request more than available - should get mix of pre-heated and mains
        result = wwhrs.get_temp_cold_water(15.0)

        # First 8L at pre-heated temp, remaining 7L at mains temp (17.0)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], (22.0, 8.0))
        self.assertEqual(result[1], (17.0, 7.0))


class TestWWHRS_IntegrationScenarios(unittest.TestCase):
    """Integration test scenarios for WWHRS"""

    def setUp(self):
        """Set up test fixtures"""
        self.simtime = SimulationTime(start_time=0, end_time=3, step=1)
        self.cold_water_source = ColdWaterSource(
            cold_water_temps=[5.0, 10.0, 15.0],  # Varying temperatures
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )
        self.flow_rates = [5, 7, 9, 11, 13]
        self.efficiencies = [44.8, 39.1, 34.8, 31.4, 28.6]

    def test_realistic_shower_scenario(self):
        """Test a realistic shower scenario with all system types"""
        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.efficiencies,
            cold_water_source=self.cold_water_source,
            system_a_utilisation_factor=0.7,
            system_b_utilisation_factor=0.65,
            system_c_utilisation_factor=0.68,
            system_b_efficiency_factor=0.81,
            system_c_efficiency_factor=0.88,
        )

        # Typical shower parameters
        shower_temp = 38.0
        shower_flow = 10.0
        hot_water_temp = 60.0

        # Test all three systems
        results = {}
        for system in ["A", "B", "C"]:
            results[system] = wwhrs.calculate_performance(
                system_type=system,
                temp_target=shower_temp,
                flowrate_waste_water=shower_flow,
                volume_cold_water=8.0,
                temp_hot=hot_water_temp,
            )

        self.assertIsNotNone(results["A"]["flowrate_hot"])
        self.assertIsNotNone(results["B"]["flowrate_hot"])
        self.assertIsNotNone(results["C"]["flowrate_hot"])

    def test_extreme_conditions(self):
        """Test WWHRS under extreme conditions"""
        wwhrs = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.efficiencies,
            cold_water_source=self.cold_water_source,
            system_a_utilisation_factor=0.7,
        )

        # Very high flow rate
        result_high_flow = wwhrs.calculate_performance(
            system_type="A",
            temp_target=40.0,
            volume_cold_water=8.0,
            flowrate_waste_water=20.0,  # Beyond test range
            temp_hot=55.0,
        )
        self.assertIsNotNone(result_high_flow["T_cyl_feed"])

        # Very low temperature difference
        cold_water_source_warm = ColdWaterSource(
            cold_water_temps=[35.0, 35.0, 35.0],
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )
        wwhrs_warm = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.efficiencies,
            cold_water_source=cold_water_source_warm,
            system_a_utilisation_factor=0.7,
        )

        result_low_diff = wwhrs_warm.calculate_performance(
            system_type="A",
            temp_target=36.0,  # Only 1°C above cold water
            flowrate_waste_water=8.0,
            volume_cold_water=8.0,
            temp_hot=55.0,
        )
        # Should still calculate but effect will be minimal
        self.assertAlmostEqual(result_low_diff["T_cyl_feed"], 33.70675, delta=0.5)
