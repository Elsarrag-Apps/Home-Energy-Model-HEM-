#!/usr/bin/env python3

"""
This module contains unit tests for the Instant Electric Heater module
"""

# Standard library imports
import unittest
from unittest import mock
from unittest.mock import MagicMock, Mock, patch

import numpy as np

from hem_core.energy_supply.energy_supply import EnergySupply
from hem_core.external_conditions import ExternalConditions
from hem_core.heating_systems.emitters import Emitters
from hem_core.input_output.enums import (
    EcoDesignControllerClass,
    FuelType,
    WetEmitterType,
)

# Local imports
from hem_core.simulation_time import SimulationTime


class TestEmitters(unittest.TestCase):
    """Unit tests for InstantElecHeater class"""

    def setUp(self):
        """Create InstantElecHeater object to be tested"""
        self.simtime = SimulationTime(0, 2, 0.25)

        # Create simple HeatSource object implementing required interface to run tests
        class HeatSource:
            def energy_output_max(
                self, temp_flow, temp_return, time_start, emitters_data_for_buffer_tank=None
            ):
                if emitters_data_for_buffer_tank is not None:
                    return (2.5, emitters_data_for_buffer_tank)
                else:
                    return 2.5

            def temp_setpnt(self):
                return 20

            def in_required_period(self):
                return True

            def demand_energy(
                self,
                energy_req_from_heating_system,
                temp_flow,
                temp_return,
                time_start,
                update_heat_source_state=True,
                emitters_data_for_buffer_tank=None,
            ):
                return max(0, min(2.5, energy_req_from_heating_system))

        self.heat_source = HeatSource()

        # Create simple Zone object implementing required interface to run tests
        class Zone:
            def area(self):
                return 80.0

            def temp_internal_air(self):
                return 20.0

        self.zone = Zone()
        self.airtemp = [0.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 20.0]
        self.windspeed = [3.7, 3.8, 3.9, 4.0, 4.1, 4.2, 4.3, 4.4]
        self.wind_direction = [200, 220, 230, 240, 250, 260, 260, 270]
        self.airtemp = [0.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 20.0]
        self.diffuse_horizontal_radiation = [333, 610, 572, 420, 0, 10, 90, 275]
        self.direct_beam_radiation = [420, 750, 425, 500, 0, 40, 0, 388]
        self.solar_reflectivity_of_ground = [0.2] * 8760
        self.latitude = 51.42
        self.longitude = -0.75
        self.timezone = 0
        self.start_day = 0
        self.end_day = 0
        self.time_series_step = 1
        self.january_first = 1
        self.daylight_savings = "not applicable"
        self.leap_day_included = False
        self.direct_beam_conversion_needed = False
        self.shading_segments = [
            {"number": 1, "start": 180, "end": 135},
            {"number": 2, "start": 135, "end": 90},
            {"number": 3, "start": 90, "end": 45},
            {"number": 4, "start": 45, "end": 0},
            {"number": 5, "start": 0, "end": -45},
            {"number": 6, "start": -45, "end": -90},
            {"number": 7, "start": -90, "end": -135},
            {"number": 8, "start": -135, "end": -180},
        ]
        self.ext_cond = ExternalConditions(
            self.simtime,
            self.airtemp,
            self.windspeed,
            self.wind_direction,
            self.diffuse_horizontal_radiation,
            self.direct_beam_radiation,
            self.solar_reflectivity_of_ground,
            self.latitude,
            self.longitude,
            self.timezone,
            self.start_day,
            self.end_day,
            self.time_series_step,
            self.january_first,
            self.daylight_savings,
            self.leap_day_included,
            self.direct_beam_conversion_needed,
            self.shading_segments,
        )

        self.ecodesign_controller = {
            "ecodesign_control_class": EcoDesignControllerClass.CLASS_II,
            "min_outdoor_temp": -4,
            "max_outdoor_temp": 20,
            "min_flow_temp": 30,
        }

        self.emitters = Emitters(
            0.07,
            [
                {
                    "wet_emitter_type": WetEmitterType.RADIATOR,
                    "c": 0.04,
                    "n": 1.2,
                    "frac_convective": 0.4,
                },
                {
                    "wet_emitter_type": WetEmitterType.RADIATOR,
                    "c_per_m": 0.08,
                    "thermal_mass_per_m": 0.14,
                    "length": 0.5,
                    "n": 1.2,
                    "frac_convective": 0.4,
                },
            ],
            [
                {
                    "location": "internal",
                    "internal_diameter_mm": 10,
                    "external_diameter_mm": 12,
                    "length": 1.0,
                    "insulation_thermal_conductivity": 0.035,
                    "insulation_thickness_mm": 0.0,
                    "surface_reflectivity": False,
                    "pipe_contents": "water",
                }
            ],
            10.0,
            True,
            None,
            3,
            18,
            0.0,
            self.heat_source,
            self.zone,
            self.ext_cond,
            self.ecodesign_controller,
            55.0,
            self.simtime,
            20,
        )

        self.energysupply = EnergySupply(FuelType.ELECTRICITY, self.simtime)
        self.energysupplyconn = self.energysupply.connection("main")

        self.fancoil_test_data = {
            "fan_speed_data": [
                {"temperature_diff": 80.0, "power_output": [2.7, 3.6, 5, 5.3, 6.2, 7.4]},
                {"temperature_diff": 70.0, "power_output": [2.3, 3.1, 4.2, 4.5, 5.3, 6.3]},
                {"temperature_diff": 60.0, "power_output": [1.9, 2.6, 3.5, 3.8, 4.4, 5.3]},
                {"temperature_diff": 50.0, "power_output": [1.5, 2, 2.8, 3, 3.5, 4.2]},
                {"temperature_diff": 40.0, "power_output": [1.1, 1.5, 2.05, 2.25, 2.6, 3.15]},
                {"temperature_diff": 30.0, "power_output": [0.7, 0.97, 1.32, 1.49, 1.7, 2.09]},
                {"temperature_diff": 20.0, "power_output": [0.3, 0.44, 0.59, 0.73, 0.8, 1.03]},
                {"temperature_diff": 10.0, "power_output": [0, 0, 0, 0, 0, 0]},
            ],
            "fan_power_W": [15, 19, 25, 33, 43, 56],
        }

        self.fancoil = Emitters(
            None,
            [
                {
                    "wet_emitter_type": WetEmitterType.FANCOIL,
                    "n_units": 1,
                    "frac_convective": 0.4,
                    "fancoil_test_data": self.fancoil_test_data,
                }
            ],
            [
                {
                    "location": "internal",
                    "internal_diameter_mm": 25,
                    "external_diameter_mm": 27,
                    "length": 10.0,
                    "insulation_thermal_conductivity": 0.035,
                    "insulation_thickness_mm": 38,
                    "surface_reflectivity": False,
                    "pipe_contents": "water",
                }
            ],
            10.0,
            True,
            None,
            3,
            18,
            0.0,
            self.heat_source,
            self.zone,
            self.ext_cond,
            self.ecodesign_controller,
            55.0,
            self.simtime,
            20,
            self.energysupplyconn,
        )

    def test_init_invalid_flow_rate(self):
        """Test that the constructor throws if the flow rates aren't given when needed"""

        # Min flow rate is needed if variable_flow is true
        variable_flow = True
        min_flow_rate = None
        max_flow_rate = 18
        design_flow_rate = 3
        with self.assertRaises(ValueError):
            self.fancoil = Emitters(
                None,
                [],
                [],
                10.0,
                variable_flow,
                design_flow_rate,
                min_flow_rate,
                max_flow_rate,
                0.0,
                self.heat_source,
                self.zone,
                self.ext_cond,
                self.ecodesign_controller,
                55.0,
                self.simtime,
                20,
                self.energysupplyconn,
            )

        # Max flow rate is needed if variable_flow is true
        variable_flow = True
        min_flow_rate = 3
        max_flow_rate = None
        design_flow_rate = 3
        with self.assertRaises(ValueError):
            self.fancoil = Emitters(
                None,
                [],
                [],
                10.0,
                variable_flow,
                design_flow_rate,
                min_flow_rate,
                max_flow_rate,
                0.0,
                self.heat_source,
                self.zone,
                self.ext_cond,
                self.ecodesign_controller,
                55.0,
                self.simtime,
                20,
                self.energysupplyconn,
            )

        # Max flow rate can be None if variable_flow is false
        variable_flow = False
        min_flow_rate = 3
        max_flow_rate = None
        design_flow_rate = 3
        self.fancoil = Emitters(
            None,
            [],
            [],
            10.0,
            variable_flow,
            design_flow_rate,
            min_flow_rate,
            max_flow_rate,
            0.0,
            self.heat_source,
            self.zone,
            self.ext_cond,
            self.ecodesign_controller,
            55.0,
            self.simtime,
            20,
            self.energysupplyconn,
        )

        # Design flow rate is needed if variable_flow is false
        variable_flow = False
        min_flow_rate = 3
        max_flow_rate = None
        design_flow_rate = None
        with self.assertRaises(ValueError):
            self.fancoil = Emitters(
                None,
                [],
                [],
                10.0,
                variable_flow,
                design_flow_rate,
                min_flow_rate,
                max_flow_rate,
                0.0,
                self.heat_source,
                self.zone,
                self.ext_cond,
                self.ecodesign_controller,
                55.0,
                self.simtime,
                20,
                self.energysupplyconn,
            )

        # Design flow rate is needed if variable_flow is true
        variable_flow = True
        min_flow_rate = 3
        max_flow_rate = 6
        design_flow_rate = None
        self.fancoil = Emitters(
            None,
            [],
            [],
            10.0,
            variable_flow,
            design_flow_rate,
            min_flow_rate,
            max_flow_rate,
            0.0,
            self.heat_source,
            self.zone,
            self.ext_cond,
            self.ecodesign_controller,
            55.0,
            self.simtime,
            20,
            self.energysupplyconn,
        )

    def test_init_bypass_fraction_recirculated(self):
        """Test the handling of the bypass_fraction_recirculated parameter in the constructor"""

        # Value of is converted to 0
        bypass_fraction_recirculated = None
        self.fancoil = Emitters(
            None,
            [],
            [],
            10.0,
            True,
            3,
            3,
            6,
            bypass_fraction_recirculated,
            self.heat_source,
            self.zone,
            self.ext_cond,
            self.ecodesign_controller,
            55.0,
            self.simtime,
            20,
            self.energysupplyconn,
        )
        self.assertEqual(self.fancoil._Emitters__bypass_fraction_recirculated, 0)

        # Throws on values too high
        bypass_fraction_recirculated = 2
        with self.assertRaises(ValueError):
            self.fancoil = Emitters(
                None,
                [],
                [],
                10.0,
                True,
                3,
                3,
                6,
                bypass_fraction_recirculated,
                self.heat_source,
                self.zone,
                self.ext_cond,
                self.ecodesign_controller,
                55.0,
                self.simtime,
                20,
                self.energysupplyconn,
            )

        # Throws on values too low
        bypass_fraction_recirculated = -1
        with self.assertRaises(ValueError):
            self.fancoil = Emitters(
                None,
                [],
                [],
                10.0,
                True,
                3,
                3,
                6,
                bypass_fraction_recirculated,
                self.heat_source,
                self.zone,
                self.ext_cond,
                self.ecodesign_controller,
                55.0,
                self.simtime,
                20,
                self.energysupplyconn,
            )

    def test_init_output_detailed_results(self):
        """Test the handling of the output_detailed_results parameter in the constructor"""

        # Return none from output_emitter_results if false
        emitters_detailed_results = False
        self.fancoil = Emitters(
            None,
            [],
            [],
            10.0,
            True,
            3,
            3,
            6,
            None,
            self.heat_source,
            self.zone,
            self.ext_cond,
            self.ecodesign_controller,
            55.0,
            self.simtime,
            20,
            self.energysupplyconn,
            emitters_detailed_results,
        )
        self.assertEqual(self.fancoil.output_emitter_results(), None)

        # Return a dict from output_emitter_results if false
        emitters_detailed_results = True
        self.fancoil = Emitters(
            None,
            [],
            [],
            10.0,
            True,
            3,
            3,
            6,
            None,
            self.heat_source,
            self.zone,
            self.ext_cond,
            self.ecodesign_controller,
            55.0,
            self.simtime,
            20,
            self.energysupplyconn,
            emitters_detailed_results,
        )
        self.assertEqual(self.fancoil.output_emitter_results(), {})

    def test_init_emitters(self):
        """Test the handling of the emitters parameter in the constructor"""
        emitters = [
            {
                "wet_emitter_type": WetEmitterType.RADIATOR,
                "c": 0.08,
                "n": 1.2,
                "frac_convective": 0.4,
            }
        ]
        # Test that the constructor throws if thermal mass is None for a radiator type
        with self.assertRaises(ValueError):
            Emitters(
                None,
                emitters,
                [],
                10.0,
                True,
                3,
                3,
                6,
                None,
                self.heat_source,
                self.zone,
                self.ext_cond,
                self.ecodesign_controller,
                55.0,
                self.simtime,
                20,
                self.energysupplyconn,
            )

        emitters = [
            {
                "wet_emitter_type": WetEmitterType.UFH,
                "c": 0.08,
                "n": 1.2,
                "frac_convective": 0.4,
                "system_performance_factor": 1,
                "emitter_floor_area": 1,
                "equivalent_specific_thermal_mass": 0,
            }
        ]
        # Test that the thermal mass can be None for a UFH type
        emitter = Emitters(
            None,
            emitters,
            [],
            10.0,
            True,
            3,
            3,
            6,
            None,
            self.heat_source,
            self.zone,
            self.ext_cond,
            self.ecodesign_controller,
            55.0,
            self.simtime,
            20,
            self.energysupplyconn,
        )
        self.assertEqual(emitter._Emitters__thermal_mass, 0)

        emitters = [
            {
                "wet_emitter_type": WetEmitterType.FANCOIL,
                "c": 0.08,
                "n": 1.2,
                "frac_convective": 0.4,
                "fancoil_test_data": self.fancoil_test_data,
            }
        ]
        # Test that fan coil can be created with given data
        emitter = Emitters(
            None,
            emitters,
            [],
            10.0,
            True,
            3,
            3,
            6,
            None,
            self.heat_source,
            self.zone,
            self.ext_cond,
            self.ecodesign_controller,
            55.0,
            self.simtime,
            20,
            self.energysupplyconn,
        )

        emitters = [
            {
                "wet_emitter_type": WetEmitterType.FANCOIL,
                "c": 0.08,
                "n": 1.2,
                "frac_convective": 0.4,
            }
        ]
        # Test that the constructor throws if the fancoil_test_data is missing
        with self.assertRaises(ValueError):
            emitter = Emitters(
                None,
                emitters,
                [],
                10.0,
                True,
                3,
                3,
                6,
                None,
                self.heat_source,
                self.zone,
                self.ext_cond,
                self.ecodesign_controller,
                55.0,
                self.simtime,
                20,
                self.energysupplyconn,
            )

        emitters = [
            {
                "wet_emitter_type": WetEmitterType.FANCOIL,
                "c": 0.08,
                "n": 1.2,
                "fancoil_test_data": self.fancoil_test_data,
            }
        ]
        # Test that the constructor throws if frac_convective is missing
        with self.assertRaises(ValueError):
            emitter = Emitters(
                None,
                emitters,
                [],
                10.0,
                True,
                3,
                3,
                6,
                None,
                self.heat_source,
                self.zone,
                self.ext_cond,
                self.ecodesign_controller,
                55.0,
                self.simtime,
                20,
                self.energysupplyconn,
            )

        emitters = [
            {
                "wet_emitter_type": WetEmitterType.UFH,
                "c": 0.08,
                "n": 1.2,
                "frac_convective": 0.4,
                "system_performance_factor": 1,
                "emitter_floor_area": 100,
                "equivalent_specific_thermal_mass": 0,
            }
        ]
        # Test that the constructor throws if emitter_floor_area is above the zone floor area
        with self.assertRaises(ValueError):
            emitter = Emitters(
                None,
                emitters,
                [],
                10.0,
                True,
                3,
                3,
                6,
                None,
                self.heat_source,
                self.zone,
                self.ext_cond,
                self.ecodesign_controller,
                55.0,
                self.simtime,
                20,
                self.energysupplyconn,
            )

        emitters = [
            {
                "wet_emitter_type": WetEmitterType.FANCOIL,
                "c": 0.08,
                "n": 1.2,
                "frac_convective": 0.4,
                "fancoil_test_data": self.fancoil_test_data,
            },
            {
                "wet_emitter_type": WetEmitterType.FANCOIL,
                "c": 0.08,
                "n": 1.2,
                "frac_convective": 0.4,
                "fancoil_test_data": self.fancoil_test_data,
            },
        ]
        # Test that the constructor throws if there is more than one fancoil
        with self.assertRaises(ValueError):
            emitter = Emitters(
                None,
                emitters,
                [],
                10.0,
                True,
                3,
                3,
                6,
                None,
                self.heat_source,
                self.zone,
                self.ext_cond,
                self.ecodesign_controller,
                55.0,
                self.simtime,
                20,
                self.energysupplyconn,
            )

        emitters = [
            {
                "wet_emitter_type": WetEmitterType.UFH,
                "c": 0.08,
                "n": 1.2,
                "frac_convective": 0.4,
                "system_performance_factor": 1,
                "emitter_floor_area": 1,
                "equivalent_specific_thermal_mass": 0,
            },
            {
                "wet_emitter_type": WetEmitterType.UFH,
                "c": 0.08,
                "n": 1.2,
                "frac_convective": 0.4,
                "system_performance_factor": 1,
                "emitter_floor_area": 1,
                "equivalent_specific_thermal_mass": 0,
            },
        ]
        # Test that the constructor doesn't throw if there is more than one UFH
        emitter = Emitters(
            None,
            emitters,
            [],
            10.0,
            True,
            3,
            3,
            6,
            None,
            self.heat_source,
            self.zone,
            self.ext_cond,
            self.ecodesign_controller,
            55.0,
            self.simtime,
            20,
            self.energysupplyconn,
        )
        # Test that radiator with thermal_mass_per_m works when system thermal_mass is None
        emitters = [
            {
                "wet_emitter_type": WetEmitterType.RADIATOR,
                "c": 0.08,
                "n": 1.2,
                "frac_convective": 0.4,
                "thermal_mass_per_m": 0.5,
                "length": 2.0,
            }
        ]
        emitter = Emitters(
            None,  # No system-level thermal mass
            emitters,
            [],
            10.0,
            True,
            3,
            3,
            6,
            None,
            self.heat_source,
            self.zone,
            self.ext_cond,
            self.ecodesign_controller,
            55.0,
            self.simtime,
            20,
            self.energysupplyconn,
        )
        self.assertAlmostEqual(emitter._Emitters__thermal_mass, 1.0)

    def test_temp_setpnt(self):
        """Test that temp_setpnt returns 20 given in the heatsource"""
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertAlmostEqual(self.fancoil.temp_setpnt(), 20)

    def test_in_required_period(self):
        """Test that in_required_period returns true given in the heatsource"""
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertTrue(self.fancoil.in_required_period())

    def test_frac_convective_fancoil(self):
        """Test that frac_convective returns the correct values for a fancoil system"""
        self.assertAlmostEqual(self.fancoil.frac_convective(), 0.4)

    def test_frac_convective_others(self):
        """Test that frac_convective returns the correct values for non-fancoil systems"""
        emitters = [
            {
                "wet_emitter_type": WetEmitterType.UFH,
                "c": 0.08,
                "n": 1.2,
                "frac_convective": 0.4,
                "system_performance_factor": 1,
                "emitter_floor_area": 1,
                "equivalent_specific_thermal_mass": 1,
            },
            {
                "wet_emitter_type": WetEmitterType.UFH,
                "c": 0.08,
                "n": 1.2,
                "frac_convective": 0.6,
                "system_performance_factor": 1,
                "emitter_floor_area": 2,
                "equivalent_specific_thermal_mass": 1,
            },
        ]
        emitter = Emitters(
            None,
            emitters,
            [],
            10.0,
            True,
            3,
            3,
            6,
            None,
            self.heat_source,
            self.zone,
            self.ext_cond,
            self.ecodesign_controller,
            55.0,
            self.simtime,
            20,
            self.energysupplyconn,
        )

        self.assertAlmostEqual(emitter.frac_convective(), 0.5333333333333333)

    def test_power_output_emitter_weight_above_temp(self):
        """Test that power_output_emitter_weight returns the correct values when above temp"""
        emitters = [
            {
                "wet_emitter_type": WetEmitterType.UFH,
                "c": 0.08,
                "n": 1.2,
                "frac_convective": 0.4,
                "system_performance_factor": 1,
                "emitter_floor_area": 1,
                "equivalent_specific_thermal_mass": 1,
            },
            {
                "wet_emitter_type": WetEmitterType.UFH,
                "c": 0.08,
                "n": 1.2,
                "frac_convective": 0.6,
                "system_performance_factor": 1,
                "emitter_floor_area": 3,
                "equivalent_specific_thermal_mass": 1,
            },
        ]
        self.ecodesign_controller = {
            "ecodesign_control_class": EcoDesignControllerClass.CLASS_I,
            "min_outdoor_temp": 10,
            "max_outdoor_temp": 15,
            "min_flow_temp": 30,
        }
        emitter = Emitters(
            None,
            emitters,
            [],
            10.0,
            True,
            3,
            3,
            6,
            None,
            self.heat_source,
            self.zone,
            self.ext_cond,
            self.ecodesign_controller,
            60.0,
            self.simtime,
            20,
            self.energysupplyconn,
        )

        self.assertAlmostEqual(emitter.power_output_emitter_weight()[0], 0.25)
        self.assertAlmostEqual(emitter.power_output_emitter_weight()[1], 0.75)

    def test_power_output_emitter_weight_below_temp(self):
        """Test that power_output_emitter_weight returns the correct values when below temp"""
        emitters = [
            {
                "wet_emitter_type": WetEmitterType.UFH,
                "c": 0.08,
                "n": 1.2,
                "frac_convective": 0.4,
                "system_performance_factor": 1,
                "emitter_floor_area": 1,
                "equivalent_specific_thermal_mass": 1,
            },
            {
                "wet_emitter_type": WetEmitterType.UFH,
                "c": 0.08,
                "n": 1.2,
                "frac_convective": 0.6,
                "system_performance_factor": 1,
                "emitter_floor_area": 3,
                "equivalent_specific_thermal_mass": 1,
            },
        ]
        self.ecodesign_controller = {
            "ecodesign_control_class": EcoDesignControllerClass.CLASS_I,
            "min_outdoor_temp": 10,
            "max_outdoor_temp": 15,
            "min_flow_temp": 30,
        }
        emitter = Emitters(
            None,
            emitters,
            [],
            10.0,
            True,
            3,
            3,
            6,
            None,
            self.heat_source,
            self.zone,
            self.ext_cond,
            self.ecodesign_controller,
            10.0,
            self.simtime,
            20,
            self.energysupplyconn,
        )

        self.assertEqual(emitter.power_output_emitter_weight(), [0.5, 0.5])

    def test_temp_flow_return_below_temp(self):
        """Test that temp_flow_return returns the correct values when the max temp is below air temp"""
        emitters = [
            {
                "wet_emitter_type": WetEmitterType.FANCOIL,
                "c": 0.08,
                "n": 1.2,
                "frac_convective": 0.4,
                "fancoil_test_data": self.fancoil_test_data,
            }
        ]
        ecodesign_controller = {
            "ecodesign_control_class": EcoDesignControllerClass.CLASS_II,
            "min_outdoor_temp": -2,
            "max_outdoor_temp": -1,
            "min_flow_temp": 30,
        }
        emitter = Emitters(
            None,
            emitters,
            [],
            10.0,
            True,
            3,
            3,
            6,
            None,
            self.heat_source,
            self.zone,
            self.ext_cond,
            ecodesign_controller,
            10.0,
            self.simtime,
            20,
            self.energysupplyconn,
        )

        self.assertAlmostEqual(emitter.temp_flow_return()[0], 30)
        self.assertAlmostEqual(emitter.temp_flow_return()[1], 25.71428571428571)

    def test_temp_flow_return_high_flow_temp(self):
        """Test that temp_flow_return returns returns a return_temp of 60 if the flow_temp is >= 70"""
        emitters = [
            {
                "wet_emitter_type": WetEmitterType.FANCOIL,
                "c": 0.08,
                "n": 1.2,
                "frac_convective": 0.4,
                "fancoil_test_data": self.fancoil_test_data,
            }
        ]
        ecodesign_controller = {"ecodesign_control_class": EcoDesignControllerClass.CLASS_I}
        emitter = Emitters(
            None,
            emitters,
            [],
            10.0,
            True,
            3,
            3,
            6,
            None,
            self.heat_source,
            self.zone,
            self.ext_cond,
            ecodesign_controller,
            80.0,
            self.simtime,
            20,
            self.energysupplyconn,
        )

        self.assertAlmostEqual(emitter.temp_flow_return()[1], 60)

    def test_demand_energy(self):
        """Test that Emitter object returns correct energy supplied"""
        energy_demand_list = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0]
        energy_demand = 0.0
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                energy_demand += energy_demand_list[t_idx]
                energy_provided = self.emitters.demand_energy(energy_demand)
                energy_demand -= energy_provided
                self.assertAlmostEqual(
                    energy_provided,
                    [
                        0.2653455026425582,
                        0.8220668279394978,
                        0.9930585230650698,
                        0.9930585230650698,
                        0.8968537869744039,
                        0.8741640483161602,
                        0.8741640483161602,
                        0.7491924984261082,
                    ][t_idx],
                    msg="incorrect energy provided by emitters",
                )
                self.assertAlmostEqual(
                    self.emitters._Emitters__temp_emitter_prev,
                    [
                        35.951417432079616,
                        45.833333333333336,
                        45.833333333333336,
                        45.833333333333336,
                        43.22916666666667,
                        43.22916666666667,
                        43.22916666666667,
                        37.88127852847367,
                    ][t_idx],
                    msg="incorrect emitter temperature calculated",
                )

    def test_demand_energy_fancoil(self):
        """Test that fancoil returns correct energy supplied"""
        energy_demand_list = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0]
        energy_demand = 0.0
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                energy_demand += energy_demand_list[t_idx]
                energy_provided = self.fancoil.demand_energy(energy_demand)
                energy_demand -= energy_provided
                self.assertAlmostEqual(
                    energy_provided,
                    [
                        0.44410447686163224,
                        0.44410447686163224,
                        0.44410447686163224,
                        0.44410447686163224,
                        0.38823264591676754,
                        0.38823264591676754,
                        0.38823264591676754,
                        0.38823264591676754,
                    ][t_idx],
                    msg="incorrect energy provided by emitters",
                )
                self.assertAlmostEqual(
                    self.fancoil._Emitters__temp_emitter_prev,
                    [20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0][t_idx],
                    msg="incorrect emitter temperature calculated",
                )

    def test_temp_flow_return(self):
        """Test flow and return temperature based on ecodesign control class"""
        flow_temp, return_temp = self.emitters.temp_flow_return()
        self.assertAlmostEqual(flow_temp, 50.8333, 3)
        self.assertAlmostEqual(return_temp, 43.5714, 3)

        # Test with different outdoor temp
        self.ecodesign_controller = {
            "ecodesign_control_class": EcoDesignControllerClass.CLASS_II,
            "min_outdoor_temp": 10,
            "max_outdoor_temp": 15,
            "min_flow_temp": 30,
        }

        self.emitters = Emitters(
            0.14,
            [
                {
                    "wet_emitter_type": WetEmitterType.RADIATOR,
                    "c": 0.08,
                    "n": 1.2,
                    "frac_convective": 0.4,
                }
            ],
            [],
            10.0,
            True,
            None,
            3,
            18,
            0.0,
            self.heat_source,
            self.zone,
            self.ext_cond,
            self.ecodesign_controller,
            55.0,
            self.simtime,
            20,
        )

        flow_temp, return_temp = self.emitters.temp_flow_return()
        self.assertAlmostEqual(flow_temp, 55.0, 3)
        self.assertAlmostEqual(return_temp, 47.1428, 3)

        # Test with different control class
        self.ecodesign_controller = {
            "ecodesign_control_class": EcoDesignControllerClass.CLASS_IV,
            "min_outdoor_temp": -4,
            "max_outdoor_temp": 20,
            "min_flow_temp": 30,
        }

        self.emitters = Emitters(
            0.14,
            [
                {
                    "wet_emitter_type": WetEmitterType.RADIATOR,
                    "c": 0.08,
                    "n": 1.2,
                    "frac_convective": 0.4,
                }
            ],
            [],
            10.0,
            True,
            None,
            3,
            18,
            0.0,
            self.heat_source,
            self.zone,
            self.ext_cond,
            self.ecodesign_controller,
            55.0,
            self.simtime,
            20,
        )

        flow_temp, return_temp = self.emitters.temp_flow_return()
        self.assertAlmostEqual(flow_temp, 55.0)
        self.assertAlmostEqual(return_temp, 47.14285714)

        # Test with different control class and ufh
        self.ecodesign_controller = {
            "ecodesign_control_class": EcoDesignControllerClass.CLASS_IV,
            "min_outdoor_temp": -4,
            "max_outdoor_temp": 20,
            "min_flow_temp": 30,
        }

        self.emitters = Emitters(
            0.14,
            [
                {
                    "wet_emitter_type": WetEmitterType.UFH,
                    "equivalent_specific_thermal_mass": 80,
                    "system_performance_factor": 5,
                    "emitter_floor_area": 80.0,
                    "frac_convective": 0.43,
                }
            ],
            [],
            10.0,
            True,
            None,
            3,
            18,
            0.0,
            self.heat_source,
            self.zone,
            self.ext_cond,
            self.ecodesign_controller,
            55.0,
            self.simtime,
            20,
        )

        flow_temp, return_temp = self.emitters.temp_flow_return()
        self.assertAlmostEqual(flow_temp, 55.0)
        self.assertAlmostEqual(return_temp, 47.14285714)

    def test_temp_flow_return_invalid_value(self):
        # Use an invalid ecodesign_control_class value (e.g., 11)
        self.ecodesign_controller = {
            "ecodesign_control_class": 11,
            "min_outdoor_temp": -4,
            "max_outdoor_temp": 20,
            "min_flow_temp": 30,
        }
        with self.assertRaises(ValueError):
            self.emitters = Emitters(
                0.14,
                [
                    {
                        "wet_emitter_type": WetEmitterType.RADIATOR,
                        "c": 0.08,
                        "n": 1.2,
                        "frac_convective": 0.4,
                    }
                ],
                [],
                10.0,
                True,
                None,
                3,
                18,
                0.0,
                self.heat_source,
                self.zone,
                self.ext_cond,
                self.ecodesign_controller,
                55.0,
                self.simtime,
                20,
            )

    def test_power_output_emitter(self):
        """Test emitter output at given emitter and room temp"""
        self.ecodesign_controller = {
            "ecodesign_control_class": EcoDesignControllerClass.CLASS_II,
            "min_outdoor_temp": -4,
            "max_outdoor_temp": 20,
            "min_flow_temp": 30,
        }

        self.emitters = Emitters(
            0.14,
            [
                {
                    "wet_emitter_type": WetEmitterType.RADIATOR,
                    "c": 0.08,
                    "n": 1.2,
                    "frac_convective": 0.4,
                }
            ],
            [],
            10.0,
            True,
            None,
            3,
            18,
            0.0,
            self.heat_source,
            self.zone,
            self.ext_cond,
            self.ecodesign_controller,
            55.0,
            self.simtime,
            20,
        )
        temp_emitter = 15.0
        temp_rm = 10.0
        self.assertAlmostEqual(
            self.emitters.power_output_emitter(temp_emitter, temp_rm), 0.55189186
        )

    def test_power_output_emitter_ufh(self):
        """Test ufh emitter output at given emitter and room temp"""
        self.ecodesign_controller = {
            "ecodesign_control_class": EcoDesignControllerClass.CLASS_II,
            "min_outdoor_temp": -4,
            "max_outdoor_temp": 20,
            "min_flow_temp": 30,
        }

        self.emitters = Emitters(
            0.14,
            [
                {
                    "wet_emitter_type": WetEmitterType.UFH,
                    "equivalent_specific_thermal_mass": 80,
                    "system_performance_factor": 5,
                    "emitter_floor_area": 80.0,
                    "frac_convective": 0.43,
                }
            ],
            [],
            10.0,
            True,
            None,
            3,
            18,
            0.0,
            self.heat_source,
            self.zone,
            self.ext_cond,
            self.ecodesign_controller,
            55.0,
            self.simtime,
            20,
        )
        temp_emitter = 15.0
        temp_rm = 10.0
        self.assertAlmostEqual(self.emitters.power_output_emitter(temp_emitter, temp_rm), 2.0)

    def test_temp_emitter_req(self):
        """Test emitter temperature that gives required power output at given room temp"""
        power_emitter_req = 0.22
        temp_rm = 2.0

        self.assertAlmostEqual(
            self.emitters.temp_emitter_req(power_emitter_req, temp_rm), 4.3179652462910205
        )

    def test_temp_emitter_req_exception(self):
        """Test that temp_emitter_req throws if there is an error in fsolve"""
        with self.assertRaises(RuntimeError):
            with mock.patch(
                "hem_core.heating_systems.emitters.fsolve",
                side_effect=RuntimeError("Mocked fsolve failure"),
            ):
                self.emitters.temp_emitter_req(0.22, 2)

    def test_func_temp_emitter_change_rate(self):
        """Test Differential eqn is formed for change rate of emitter temperature"""

        func = self.emitters._Emitters__func_temp_emitter_change_rate(5)
        # Check if the returned value is a lambda function
        self.assertTrue(callable(func))
        self.assertEqual(func.__name__, "<lambda>")

    def test_temp_emitter(self):
        """Test function calculates emitter temperature after specified time with specified power input"""
        # Check None conditions  are invoked
        temp_emitter, time_temp_diff_max_reached = self.emitters.temp_emitter(
            time_start=0,
            time_end=2,
            temp_emitter_start=5,
            temp_rm=10,
            power_input=0.2,
            temp_emitter_max=None,
        )
        self.assertAlmostEqual(temp_emitter, 7.85528119911919)
        self.assertEqual(time_temp_diff_max_reached, None)

        # Check not None conditions are invoked
        temp_emitter, time_temp_diff_max_reached = self.emitters.temp_emitter(
            time_start=0,
            time_end=2,
            temp_emitter_start=70,
            temp_rm=10,
            power_input=0.2,
            temp_emitter_max=25,
        )

        self.assertAlmostEqual(temp_emitter, 25.0)
        self.assertAlmostEqual(time_temp_diff_max_reached, 1.2964605622321956)

    def test_temp_emitter_exception(self):
        """Test that temp_emitter throws on errors in solve_ivp"""
        with self.assertRaises(RuntimeError):
            with mock.patch(
                "hem_core.heating_systems.emitters.solve_ivp",
                side_effect=RuntimeError("Mocked solve_ivp failure"),
            ):
                self.emitters.temp_emitter(0, 2, 70, 10, 0.2, 25)

    def test_format_fancoil_manufacturer_data(self):
        """Test the function accepts test data and
        returns fancoil manufacturer data in expected numpy format"""
        test_data = {
            "fan_speed_data": [
                {"temperature_diff": 80.0, "power_output": [2.7, 3.6, 5, 5.3, 6.2, 7.4]},
                {"temperature_diff": 70.0, "power_output": [2.3, 3.1, 4.2, 4.5, 5.3, 6.3]},
            ],
            "fan_power_W": [15, 19, 25, 33, 43, 56],
        }

        fc_temperature_data, fc_fan_power_data = self.emitters.format_fancoil_manufacturer_data(
            test_data
        )

        expected_temperature = np.array(
            [[80.0, 2.7, 3.6, 5.0, 5.3, 6.2, 7.4], [70.0, 2.3, 3.1, 4.2, 4.5, 5.3, 6.3]]
        )

        expected_fan_power = np.array([["Fan power (W)", 15, 19, 25, 33, 43, 56]])

        # Use np.testing.assert_array_equal for better diagnostics
        np.testing.assert_array_equal(
            fc_temperature_data.astype(float),
            expected_temperature,
            err_msg="Temperature Arrays are not equal",
        )

        # Reshape fc_fan_power_data to match the shape of expected_fan_power
        np.testing.assert_array_equal(
            fc_fan_power_data.reshape(1, -1),
            expected_fan_power,
            err_msg="Fan power Arrays are not equal",
        )

        # Test the function does a system exit if the fan_speeds list differ in length
        test_data_invalid = {
            "fan_speed_data": [
                {"temperature_diff": 80.0, "power_output": [2, 4, 6, 8, 9, 11]},
                {"temperature_diff": 70.0, "power_output": [2, 4, 6, 8, 9]},
            ],
            "fan_power_W": [15, 19, 25, 33, 43, 56],
        }

        with self.assertRaises(ValueError):
            self.emitters.format_fancoil_manufacturer_data(test_data_invalid)

        # Test the function does a system exit if the fan_power_W list differ in length
        test_data_invalid = {
            "fan_speed_data": [
                {"temperature_diff": 80.0, "power_output": [2, 4, 6, 8, 9]},
                {"temperature_diff": 70.0, "power_output": [2, 4, 6, 8, 9]},
            ],
            "fan_power_W": [15, 19, 25, 33, 43, 56],
        }

        with self.assertRaises(ValueError):
            self.emitters.format_fancoil_manufacturer_data(test_data_invalid)

    def test_fancoil_output_zero_power(self):
        """Test that the results of fancoil_output are correct for a 0 temperature diff"""
        data = [np.array([[0, 0, 0]]), np.array(["Fan power (W)", 15, 19])]

        actual_output, fan_power_value, fraction_timestep_running = self.emitters.fancoil_output(
            5, data[0], data[1], 12
        )

        self.assertAlmostEqual(actual_output, 0)
        self.assertAlmostEqual(fan_power_value, 0)
        self.assertAlmostEqual(fraction_timestep_running, 1)

    def test_energy_required_from_heat_source(self):
        energy_demand_list = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
        energy_demand = 0.0
        timestep = 1.0
        temp_rm_prev = 10.0
        temp_flow_target = 30
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                energy_demand += energy_demand_list[t_idx]
                power_emitter_req = energy_demand / timestep
                temp_emitter_req = self.emitters.temp_emitter_req(power_emitter_req, temp_rm_prev)
                energy_req, temp_emitter_max_is_final_temp, __ = (
                    self.emitters._Emitters__energy_required_from_heat_source(
                        energy_demand,
                        timestep=timestep,
                        temp_rm_prev=temp_rm_prev,
                        temp_emitter_max=25,
                        temp_return=30,
                        time_heating_start=0,
                        temp_emitter_heating_start=self.emitters._Emitters__temp_emitter_prev,
                        temp_emitter_req=temp_emitter_req,
                        temp_flow_target=temp_flow_target,
                    )
                )

            self.assertAlmostEqual(
                energy_req,
                [
                    0.7457780407382995,
                    2.4627899136391274,
                    2.4627899136391274,
                    2.4627899136391274,
                    2.4627899136391274,
                    2.4627899136391274,
                    2.4627899136391274,
                    2.4627899136391274,
                ][t_idx],
            )
            self.assertEqual(
                temp_emitter_max_is_final_temp,
                [False, False, True, True, True, True, True, True][t_idx],
            )

    def test_energy_required_from_heat_source_with_buffer_tank(self):
        """Test that the correct values are returned from energy_required_from_heat_source with buffer tank"""
        self.emitters._Emitters__with_buffer_tank = True
        temp_flow_target = 30

        energy_demand_list = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
        energy_demand = 0.0
        timestep = 1.0
        temp_rm_prev = 10.0
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                energy_demand += energy_demand_list[t_idx]
                power_emitter_req = energy_demand / timestep
                temp_emitter_req = self.emitters.temp_emitter_req(power_emitter_req, temp_rm_prev)
                energy_req, temp_emitter_max_is_final_temp, emitters_data_for_buffer_tank = (
                    self.emitters._Emitters__energy_required_from_heat_source(
                        energy_demand,
                        timestep=timestep,
                        temp_rm_prev=temp_rm_prev,
                        temp_emitter_max=25,
                        temp_return=30,
                        time_heating_start=0,
                        temp_emitter_heating_start=self.emitters._Emitters__temp_emitter_prev,
                        temp_emitter_req=temp_emitter_req,
                        temp_flow_target=temp_flow_target,
                    )
                )

                self.assertAlmostEqual(
                    energy_req,
                    [
                        0.7457780407382995,
                        2.4627899136391274,
                        2.4627899136391274,
                        2.4627899136391274,
                        2.4627899136391274,
                        2.4627899136391274,
                        2.4627899136391274,
                        2.4627899136391274,
                    ][t_idx],
                )
                self.assertEqual(
                    temp_emitter_max_is_final_temp,
                    [False, False, True, True, True, True, True, True][t_idx],
                )
                self.assertAlmostEqual(
                    emitters_data_for_buffer_tank["power_req_from_buffer_tank"],
                    [
                        0.7457780407382995,
                        2.642140030432491,
                        4.463313771204879,
                        6.239178323597834,
                        7.983003024859063,
                        9.702252941082214,
                        11.401689338957867,
                        13.084599772694327,
                    ][t_idx],
                )

    def test_energy_required_from_heat_source_with_buffer_tank_no_time_remaining(self):
        """Test that the correct values are returned from energy_required_from_heat_source with buffer tank and no time remaining in the timestep"""
        self.emitters._Emitters__with_buffer_tank = True
        temp_flow_target = 30

        energy_demand_list = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
        energy_demand = 0.0
        timestep = 1.0
        temp_rm_prev = 10.0
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                energy_demand += energy_demand_list[t_idx]
                power_emitter_req = energy_demand / timestep
                temp_emitter_req = self.emitters.temp_emitter_req(power_emitter_req, temp_rm_prev)
                energy_req, temp_emitter_max_is_final_temp, emitters_data_for_buffer_tank = (
                    self.emitters._Emitters__energy_required_from_heat_source(
                        energy_demand,
                        timestep=timestep,
                        temp_rm_prev=temp_rm_prev,
                        temp_emitter_max=25,
                        temp_return=30,
                        time_heating_start=1,
                        temp_emitter_heating_start=self.emitters._Emitters__temp_emitter_prev,
                        temp_emitter_req=temp_emitter_req,
                        temp_flow_target=temp_flow_target,
                    )
                )

                self.assertAlmostEqual(
                    energy_req,
                    [0, 0, 0, 0, 0, 0, 0, 0][t_idx],
                )
                self.assertEqual(
                    temp_emitter_max_is_final_temp,
                    [False, False, False, False, False, False, False, False][t_idx],
                )
                self.assertAlmostEqual(
                    emitters_data_for_buffer_tank["power_req_from_buffer_tank"],
                    [0, 0, 0, 0, 0, 0, 0, 0][t_idx],
                )

    # def test_running_time_throughput_factor(self):
    #     ''' Test appropriate heat source function and arguments are called to calculate throughput factor'''
    #     #Check for conditionals when energy demand is greater than 0.0
    #     msg = self.emitters.running_time_throughput_factor(energy_demand = 0.5,
    #                                                        space_heat_running_time_cumulative =  5)
    #
    #     self.assertEqual('Heat source throughput function called with 5, 2.5, 50.833333333333336, 43.57142857142857, 0.0', msg)
    #
    #     #Check for conditionals when energy demand is 0.0
    #     msg = self.emitters.running_time_throughput_factor(energy_demand = 0.0,
    #                                                        space_heat_running_time_cumulative =  5)
    #
    #     self.assertEqual('Heat source throughput function called with 5, 0.0, 50.833333333333336, 43.57142857142857, 0.0', msg)

    def test_energy_output_min(self):
        mockzone = Mock()
        mockzone.temp_internal_air.return_value = 10.0
        mockzone.area.return_value = 80
        self.emitters = Emitters(
            0.14,
            [
                {
                    "wet_emitter_type": WetEmitterType.RADIATOR,
                    "c": 0.08,
                    "n": 1.2,
                    "frac_convective": 0.4,
                }
            ],
            [],
            10.0,
            True,
            None,
            3,
            18,
            0.0,
            self.heat_source,
            mockzone,
            self.ext_cond,
            self.ecodesign_controller,
            55.0,
            self.simtime,
            20,
        )
        self.assertAlmostEqual(self.emitters.energy_output_min(), 0.2780866841016483)

    def test_calc_emitter_cooldown_exception(self):
        """Test that cal_emitter_cooldown throws on an exception in root"""
        with self.assertRaises(RuntimeError):
            with mock.patch(
                "hem_core.heating_systems.emitters.root",
                side_effect=RuntimeError("Mocked root failure"),
            ):
                self.emitters._Emitters__calc_emitter_cooldown(10, 20, 20, 1)

    def test_return_temp_from_flow_rate_above_max(self):
        """Test that return_temp_from_flow_rate returns the correct values when the flow rate is above the max rate"""
        self.emitters._Emitters__min_flow_rate = 0.01
        self.emitters._Emitters__max_flow_rate = 0.02
        temp_return_target, blended_temp_flow_target, flow_rate_m3s = (
            self.emitters.return_temp_from_flow_rate(3, 50, 30)
        )
        self.assertAlmostEqual(temp_return_target, 37.316179275512695)
        self.assertAlmostEqual(blended_temp_flow_target, 50)
        self.assertAlmostEqual(flow_rate_m3s, 0.00002)

    def test_return_temp_from_flow_rate_non_variable_flow(self):
        """Test that return_temp_from_flow_rate returns the correct values without variable flow"""
        self.emitters._Emitters__variable_flow = False
        self.emitters._Emitters__design_flow_rate = 0.02
        temp_return_target, blended_temp_flow_target, flow_rate_m3s = (
            self.emitters.return_temp_from_flow_rate(3, 50, 30)
        )
        self.assertAlmostEqual(temp_return_target, 37.316179275512695)
        self.assertAlmostEqual(blended_temp_flow_target, 50)
        self.assertAlmostEqual(flow_rate_m3s, 0.00002)

    def test_return_temp_from_flow_rate_non_variable_flow_no_energy(self):
        """Test that return_temp_from_flow_rate returns the correct values without variable flow and no energy"""
        self.emitters._Emitters__variable_flow = False
        self.emitters._Emitters__design_flow_rate = 0.02
        temp_return_target, blended_temp_flow_target, flow_rate_m3s = (
            self.emitters.return_temp_from_flow_rate(0, 50, 30)
        )
        self.assertAlmostEqual(temp_return_target, 50)
        self.assertAlmostEqual(blended_temp_flow_target, 50)
        self.assertAlmostEqual(flow_rate_m3s, 0)

    def test_return_temp_from_flow_rate_recirculated(self):
        """Test that return_temp_from_flow_rate returns the correct values with a bypass percentage recirculated"""
        self.emitters._Emitters__bypass_fraction_recirculated = 0.5
        temp_return_target, blended_temp_flow_target, flow_rate_m3s = (
            self.emitters.return_temp_from_flow_rate(3, 50, 30)
        )
        self.assertAlmostEqual(temp_return_target, 42.38971339502484)
        self.assertAlmostEqual(blended_temp_flow_target, 47.46323823928833)
        self.assertAlmostEqual(flow_rate_m3s, 0.00005)

    def test_demand_energy_flow_return_no_progress(self):
        """Test that demand_energy_flow_return throws if no progress is made calculating temperature"""
        with self.assertRaises(RuntimeError):
            self.fancoil = Emitters(
                None,
                [],
                [],
                10.0,
                True,
                10,
                10,
                20,
                0.0,
                self.heat_source,
                self.zone,
                self.ext_cond,
                self.ecodesign_controller,
                55.0,
                self.simtime,
                20,
                self.energysupplyconn,
                True,
            )
            self.fancoil.demand_energy_flow_return(-1, 50, 40, True, False, None)

    def test_demand_energy_flow_return_no_demand(self):
        """Test that the demand_energy_flow_return results are correct for zero demand"""
        emitters = [
            {
                "wet_emitter_type": WetEmitterType.FANCOIL,
                "c": 0.08,
                "n": 1.2,
                "frac_convective": 0.4,
                "fancoil_test_data": self.fancoil_test_data,
            }
        ]

        self.fancoil = Emitters(
            10,
            emitters,
            [],
            10.0,
            True,
            15,
            10,
            20,
            0.0,
            self.heat_source,
            self.zone,
            self.ext_cond,
            self.ecodesign_controller,
            55.0,
            self.simtime,
            20,
            self.energysupplyconn,
            True,
        )

        self.fancoil._Emitters__output_detailed_results = True
        energy_released_from_emitters, energy_req_from_heat_source = (
            self.fancoil.demand_energy_flow_return(0, 50, 40, True, False, None)
        )
        self.assertAlmostEqual(energy_released_from_emitters, 0)
        self.assertAlmostEqual(energy_req_from_heat_source, 0)

        results = self.fancoil.output_emitter_results()
        results[0] = list(results[0].__dict__.values())

        self.assertEqual(results, {0: [0, 0, 45.0, 0.0, 0, "n/a", 45.0, 0, 50, 40, False, 0.0, 0]})

    def test_demand_energy_flow_return_with_buffer_tank(self):
        """Test that the demand_energy_flow_return calls demand_energy with emitters_data_for_buffer_tank"""
        emitters = [
            {
                "wet_emitter_type": WetEmitterType.FANCOIL,
                "c": 0.08,
                "n": 1.2,
                "frac_convective": 0.4,
                "fancoil_test_data": self.fancoil_test_data,
            }
        ]

        emitters_data_for_buffer_tank = MagicMock()

        heat_source = MagicMock()
        heat_source.energy_output_max.return_value = (2.5, emitters_data_for_buffer_tank)
        heat_source.demand_energy.return_value = 2

        self.fancoil = Emitters(
            10,
            emitters,
            [],
            10.0,
            True,
            15,
            10,
            20,
            0.0,
            heat_source,
            self.zone,
            self.ext_cond,
            self.ecodesign_controller,
            55.0,
            self.simtime,
            20,
            self.energysupplyconn,
            True,
            True,
        )

        self.fancoil.demand_energy_flow_return(10, 50, 40, True, False, None)

        self.assertEqual(
            heat_source.demand_energy.call_args[1]["emitters_data_for_buffer_tank"],
            emitters_data_for_buffer_tank,
        )

    def test_demand_energy_flow(self):
        """Test that the temp_emitter_req value is used if target emitter temperature is reached on warm-up"""
        emitters = [
            {
                "wet_emitter_type": WetEmitterType.RADIATOR,
                "c": 0.08,
                "n": 1.2,
                "frac_convective": 0.4,
            }
        ]

        temp_emitter_req = 30

        with patch.object(Emitters, "temp_emitter_req", return_value=temp_emitter_req):
            with patch.object(Emitters, "temp_emitter", side_effect=[(20, None), (25, 2)]):
                self.fancoil = Emitters(
                    10,
                    emitters,
                    [],
                    10.0,
                    True,
                    15,
                    10,
                    20,
                    0.0,
                    self.heat_source,
                    self.zone,
                    self.ext_cond,
                    self.ecodesign_controller,
                    55.0,
                    self.simtime,
                    20,
                    self.energysupplyconn,
                    True,
                    True,
                )
                self.fancoil.demand_energy_flow_return(10, 10, 20, True, False, None)

                results = self.fancoil.output_emitter_results()
                temp_emitter_req = results[0].temp_emitter_required
                temp_emitter = results[0].temp_emitter

                self.assertAlmostEqual(temp_emitter_req, temp_emitter_req)
                self.assertAlmostEqual(temp_emitter, temp_emitter_req)

    def test_update_return_temp_over_flow_target(self):
        """Test that temp_flow_target is returned if temp_return_target over the temp_flow_target"""
        with mock.patch("hem_core.heating_systems.emitters.fsolve", return_value=[20]):
            temp_return_target = self.emitters.update_return_temp(
                10, 11, 12, 13, 14, 15, False, False
            )
            self.assertEqual(temp_return_target, 11)

    def test_update_return_temp_exception(self):
        """Test that update_return_temp throws if there is an error in fsolve"""
        with self.assertRaises(RuntimeError):
            with mock.patch(
                "hem_core.heating_systems.emitters.fsolve",
                side_effect=RuntimeError("Mocked fsolve failure"),
            ):
                self.emitters.update_return_temp(10, 10, 10, 10, 10, 10, False, False)

    def test_energy_output_min_fancoil(self):
        """Test that test_energy_output_min returns 0 for fancoils"""
        self.assertEqual(self.fancoil.energy_output_min(), 0)

    def test_init_pipework_with_fancoil(self):
        """Test that internal pipework is correctly processed when fancoil is present"""
        emitters = [
            {
                "wet_emitter_type": "fancoil",
                "n_units": 1,
                "frac_convective": 0.4,
                "fancoil_test_data": self.fancoil_test_data,
            }
        ]

        pipework = [
            {
                "location": "internal",
                "internal_diameter_mm": 25,
                "external_diameter_mm": 27,
                "length": 10.0,
                "insulation_thermal_conductivity": 0.035,
                "insulation_thickness_mm": 38,
                "surface_reflectivity": False,
                "pipe_contents": "water",
            }
        ]

        emitter = Emitters(
            None,
            emitters,
            pipework,
            10.0,
            True,
            3,
            3,
            6,
            None,
            self.heat_source,
            self.zone,
            self.ext_cond,
            self.ecodesign_controller,
            55.0,
            self.simtime,
            20,
            self.energysupplyconn,
        )

        # When fancoil is present, pipework should be added to pipework_list
        self.assertEqual(len(emitter._Emitters__pipework_list), 1)
        self.assertTrue(emitter._Emitters__flag_fancoil)

    def test_init_pipework_with_radiator_insulated(self):
        """Test that insulated internal pipework prints a message when used with radiators"""
        emitters = [{"wet_emitter_type": "radiator", "c": 0.08, "n": 1.2, "frac_convective": 0.4}]

        pipework = [
            {
                "location": "internal",
                "internal_diameter_mm": 25,
                "external_diameter_mm": 27,
                "length": 10.0,
                "insulation_thermal_conductivity": 0.035,
                "insulation_thickness_mm": 38,  # Insulated pipework
                "surface_reflectivity": False,
                "pipe_contents": "water",
            }
        ]

        # Test for warning when different test points provided for different air flow rates
        with self.assertLogs("hem_core.heating_systems.emitters", "WARNING") as cm:
            emitter = Emitters(
                0.14,
                emitters,
                pipework,
                10.0,
                True,
                3,
                3,
                6,
                None,
                self.heat_source,
                self.zone,
                self.ext_cond,
                self.ecodesign_controller,
                55.0,
                self.simtime,
                20,
            )

            # Check that the warning message was printed
            self.assertEqual(
                cm.output,
                [
                    "WARNING:hem_core.heating_systems.emitters:Heat loss from insulated pipework "
                    "to heat emitters is currently ignored - only uninsulated pipework is "
                    "currently considered."
                ],
            )

        # Check that no radiator was added for insulated pipework
        self.assertEqual(len(emitter._Emitters__emitters), 1)  # Only the original radiator

    def test_init_pipework_with_radiator_uninsulated(self):
        """Test that uninsulated internal pipework is converted to equivalent radiator"""
        emitters = [{"wet_emitter_type": "radiator", "c": 0.08, "n": 1.2, "frac_convective": 0.4}]

        pipework = [
            {
                "location": "internal",
                "internal_diameter_mm": 25,
                "external_diameter_mm": 27,
                "length": 10.0,
                "insulation_thermal_conductivity": 0.035,
                "insulation_thickness_mm": 0,  # Uninsulated pipework
                "surface_reflectivity": False,
                "pipe_contents": "water",
            }
        ]

        initial_thermal_mass = 0.14
        emitter = Emitters(
            initial_thermal_mass,
            emitters,
            pipework,
            10.0,
            True,
            3,
            3,
            6,
            None,
            self.heat_source,
            self.zone,
            self.ext_cond,
            self.ecodesign_controller,
            55.0,
            self.simtime,
            20,
        )

        # Check that a new radiator was added for uninsulated pipework
        self.assertEqual(
            len(emitter._Emitters__emitters), 2
        )  # Original radiator + pipework as radiator

        # Check that the new radiator has the correct properties
        new_radiator = emitter._Emitters__emitters[1]
        self.assertEqual(new_radiator["wet_emitter_type"], "radiator")
        self.assertEqual(new_radiator["frac_convective"], 0.7)
        self.assertIn("c", new_radiator)
        self.assertIn("n", new_radiator)

        # Check that thermal mass was increased
        self.assertGreater(emitter._Emitters__thermal_mass, initial_thermal_mass)

    def test_init_pipework_external_location(self):
        """Test that external pipework is not processed"""
        emitters = [{"wet_emitter_type": "radiator", "c": 0.08, "n": 1.2, "frac_convective": 0.4}]

        pipework = [
            {
                "location": "external",  # External location
                "internal_diameter_mm": 25,
                "external_diameter_mm": 27,
                "length": 10.0,
                "insulation_thermal_conductivity": 0.035,
                "insulation_thickness_mm": 0,
                "surface_reflectivity": False,
                "pipe_contents": "water",
            }
        ]

        emitter = Emitters(
            0.14,
            emitters,
            pipework,
            10.0,
            True,
            3,
            3,
            6,
            None,
            self.heat_source,
            self.zone,
            self.ext_cond,
            self.ecodesign_controller,
            55.0,
            self.simtime,
            20,
        )

        # Check that no new radiator was added for external pipework
        self.assertEqual(len(emitter._Emitters__emitters), 1)  # Only the original radiator
        # Check that pipework_list is empty
        self.assertEqual(len(emitter._Emitters__pipework_list), 0)

    def test_init_pipework_multiple_pipes(self):
        """Test processing multiple pipework entries with different configurations"""
        emitters = [{"wet_emitter_type": "radiator", "c": 0.08, "n": 1.2, "frac_convective": 0.4}]

        pipework = [
            {
                "location": "internal",
                "internal_diameter_mm": 25,
                "external_diameter_mm": 27,
                "length": 5.0,
                "insulation_thermal_conductivity": 0.035,
                "insulation_thickness_mm": 0,  # Uninsulated
                "surface_reflectivity": False,
                "pipe_contents": "water",
            },
            {
                "location": "internal",
                "internal_diameter_mm": 20,
                "external_diameter_mm": 22,
                "length": 3.0,
                "insulation_thermal_conductivity": 0.035,
                "insulation_thickness_mm": 25,  # Insulated
                "surface_reflectivity": True,
                "pipe_contents": "water",
            },
            {
                "location": "external",
                "internal_diameter_mm": 30,
                "external_diameter_mm": 32,
                "length": 8.0,
                "insulation_thermal_conductivity": 0.035,
                "insulation_thickness_mm": 0,
                "surface_reflectivity": False,
                "pipe_contents": "water",
            },
        ]

        emitter = Emitters(
            0.14,
            emitters,
            pipework,
            10.0,
            True,
            3,
            3,
            6,
            None,
            self.heat_source,
            self.zone,
            self.ext_cond,
            self.ecodesign_controller,
            55.0,
            self.simtime,
            20,
        )

        # Check that only uninsulated internal pipework was added as a radiator
        self.assertEqual(
            len(emitter._Emitters__emitters), 2
        )  # Original + 1 uninsulated internal pipe

    def test_fancoil_pipework_heat_loss(self):
        """Test that pipework heat loss is correctly calculated and subtracted for fancoils"""
        emitters = [
            {
                "wet_emitter_type": "fancoil",
                "n_units": 1,
                "frac_convective": 0.4,
                "fancoil_test_data": self.fancoil_test_data,
            }
        ]

        # Internal pipework that will generate heat loss
        pipework = [
            {
                "location": "internal",
                "internal_diameter_mm": 25,
                "external_diameter_mm": 27,
                "length": 10.0,
                "insulation_thermal_conductivity": 0.035,
                "insulation_thickness_mm": 0,  # Uninsulated to ensure heat loss
                "surface_reflectivity": False,
                "pipe_contents": "water",
            },
            {
                "location": "internal",
                "internal_diameter_mm": 20,
                "external_diameter_mm": 22,
                "length": 5.0,
                "insulation_thermal_conductivity": 0.035,
                "insulation_thickness_mm": 0,  # Another uninsulated pipe
                "surface_reflectivity": False,
                "pipe_contents": "water",
            },
        ]

        # Create emitter system with fancoil and pipework
        fancoil_system = Emitters(
            None,
            emitters,
            pipework,
            10.0,
            True,
            None,
            3,
            18,
            0.0,
            self.heat_source,
            self.zone,
            self.ext_cond,
            self.ecodesign_controller,
            55.0,
            self.simtime,
            20,
            self.energysupplyconn,
        )

        # Verify pipework was added to pipework_list
        self.assertEqual(len(fancoil_system._Emitters__pipework_list), 2)

        # Test energy demand to trigger pipework heat loss calculation
        # This will execute the lines that calculate pw_heat_loss
        energy_demand = 2.0  # kWh

        # Mock the zone temperature to ensure heat loss calculation
        original_temp = self.zone.temp_internal_air
        self.zone.temp_internal_air = lambda: 20.0  # Room temperature

        # Call demand_energy which should trigger the pipework heat loss calculation
        energy_released = fancoil_system.demand_energy(energy_demand)

        # Verify that energy was released (should be less than demand due to pipework losses)
        self.assertGreater(energy_released, 0)
        self.assertLess(energy_released, energy_demand)

        # Restore original zone temperature method
        self.zone.temp_internal_air = original_temp

    def test_fancoil_pipework_heat_loss_with_detailed_results(self):
        """Test pipework heat loss calculation with detailed results output"""
        emitters = [
            {
                "wet_emitter_type": "fancoil",
                "n_units": 2,  # Multiple units to test scaling
                "frac_convective": 0.5,
                "fancoil_test_data": self.fancoil_test_data,
            }
        ]

        pipework = [
            {
                "location": "internal",
                "internal_diameter_mm": 30,
                "external_diameter_mm": 32,
                "length": 20.0,
                "insulation_thermal_conductivity": 0.040,
                "insulation_thickness_mm": 10,  # Some insulation
                "surface_reflectivity": True,
                "pipe_contents": "water",
            }
        ]

        # Create emitter system with output_detailed_results=True
        fancoil_system = Emitters(
            None,
            emitters,
            pipework,
            10.0,
            True,
            None,
            3,
            18,
            0.0,
            self.heat_source,
            self.zone,
            self.ext_cond,
            self.ecodesign_controller,
            55.0,
            self.simtime,
            20,
            self.energysupplyconn,
            output_detailed_results=True,
        )

        # Set up test conditions
        energy_demand_list = [1.5, 2.0, 1.0, 0.5]

        for t_idx, _, _ in self.simtime:
            if t_idx < len(energy_demand_list):
                with self.subTest(i=t_idx):
                    energy_demand = energy_demand_list[t_idx]

                    # Call demand_energy to trigger pipework heat loss calculation
                    energy_released = fancoil_system.demand_energy(energy_demand)

                    # Verify energy was processed
                    self.assertGreaterEqual(energy_released, 0)

        # Check that detailed results were recorded
        detailed_results = fancoil_system.output_emitter_results()
        self.assertIsNotNone(detailed_results)
        self.assertGreater(len(detailed_results), 0)
