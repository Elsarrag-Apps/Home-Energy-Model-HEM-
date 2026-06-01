#!/usr/bin/env python3

"""
This module contains unit tests for the elec_battery module
"""

# Standard library imports
import re
import unittest

import pytest

from hem_core.energy_supply.elec_battery import ElectricBattery
from hem_core.external_conditions import ExternalConditions
from hem_core.input_output.enums import BatteryLocation

# Local imports
from hem_core.simulation_time import SimulationTime


class TestElectricBattery(unittest.TestCase):
    """Unit tests for ElectricBattery class"""

    def setUp(self):
        self.simtime = SimulationTime(start_time=0, end_time=8, step=1)
        proj_dict = {
            "ExternalConditions": {
                "air_temperatures": [0.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 20.0],
                "wind_speeds": [3.9, 3.8, 3.9, 4.1, 3.8, 4.2, 4.3, 4.1],
                "wind_directions": [0, 20, 40, 60, 0, 20, 40, 60],
                "diffuse_horizontal_radiation": [11, 25, 42, 52, 60, 44, 28, 15],
                "direct_beam_radiation": [11, 25, 42, 52, 60, 44, 28, 15],
                "solar_reflectivity_of_ground": [0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2],
                "latitude": 51.42,
                "longitude": -0.75,
                "timezone": 0,
                "start_day": 0,
                "end_day": 0,
                "time_series_step": 1,
                "january_first": 1,
                "daylight_savings": "not applicable",
                "leap_day_included": False,
                "direct_beam_conversion_needed": False,
                "shading_segments": [
                    {"number": 1, "start": 180, "end": 135},
                    {
                        "number": 2,
                        "start": 135,
                        "end": 90,
                        "shading": [{"type": "overhang", "height": 2.2, "distance": 6}],
                    },
                    {"number": 3, "start": 90, "end": 45},
                    {
                        "number": 4,
                        "start": 45,
                        "end": 0,
                        "shading": [
                            {"type": "obstacle", "height": 40, "distance": 4},
                            {"type": "overhang", "height": 3, "distance": 7},
                        ],
                    },
                    {
                        "number": 5,
                        "start": 0,
                        "end": -45,
                        "shading": [
                            {"type": "obstacle", "height": 3, "distance": 8},
                        ],
                    },
                    {"number": 6, "start": -45, "end": -90},
                    {"number": 7, "start": -90, "end": -135},
                    {"number": 8, "start": -135, "end": -180},
                ],
            }
        }
        self.__external_conditions = ExternalConditions(
            simulation_time=self.simtime,
            air_temps=proj_dict["ExternalConditions"]["air_temperatures"],
            wind_speeds=proj_dict["ExternalConditions"]["wind_speeds"],
            wind_directions=proj_dict["ExternalConditions"]["wind_directions"],
            diffuse_horizontal_radiation=proj_dict["ExternalConditions"][
                "diffuse_horizontal_radiation"
            ],
            direct_beam_radiation=proj_dict["ExternalConditions"]["direct_beam_radiation"],
            solar_reflectivity_of_ground=proj_dict["ExternalConditions"][
                "solar_reflectivity_of_ground"
            ],
            latitude=proj_dict["ExternalConditions"]["latitude"],
            longitude=proj_dict["ExternalConditions"]["longitude"],
            timezone=proj_dict["ExternalConditions"]["timezone"],
            start_day=proj_dict["ExternalConditions"]["start_day"],
            end_day=proj_dict["ExternalConditions"]["end_day"],
            time_series_step=proj_dict["ExternalConditions"]["time_series_step"],
            january_first=proj_dict["ExternalConditions"]["january_first"],
            daylight_savings=proj_dict["ExternalConditions"]["daylight_savings"],
            leap_day_included=proj_dict["ExternalConditions"]["leap_day_included"],
            direct_beam_conversion_needed=proj_dict["ExternalConditions"][
                "direct_beam_conversion_needed"
            ],
            shading_segments=proj_dict["ExternalConditions"]["shading_segments"],
        )

        """ Create ElectricBattery object to be tested """
        self.elec_battery = ElectricBattery(
            capacity=2,
            charge_discharge_efficiency=0.8,
            battery_age=3,
            minimum_charge_rate=0.001,
            maximum_charge_rate=1.5,
            maximum_discharge_rate=1.5,
            battery_location=BatteryLocation.OUTSIDE,
            grid_charging_possible=False,
            simulation_time=self.simtime,
            external_conditions=self.__external_conditions,
        )

    def test_get_charge_efficiency(self):
        """Test that get_charge_efficiency returns the correct value"""
        self.assertAlmostEqual(self.elec_battery.get_charge_efficiency(), 0.6687167004967052)

    def test_get_discharge_efficiency(self):
        """Test that get_discharge_efficiency returns the correct value"""
        self.assertAlmostEqual(self.elec_battery.get_discharge_efficiency(), 0.8358958756208815)

    def test_get_charge_discharge_efficiency(self):
        """Test that get_charge_discharge_efficiency returns the correct value"""
        self.assertAlmostEqual(self.elec_battery.get_charge_discharge_efficiency(), 0.8)

    def test_get_max_capacity(self):
        """Test that get_max_capacity returns the correct value"""
        self.assertAlmostEqual(self.elec_battery.get_max_capacity(), 1.76)

    def test_timestep_end(self):
        """Test that variables are reset at the end of the timestep"""
        self.elec_battery._ElectricBattery__total_time_charging_current_timestep = 10  # type: ignore[reportAttributeAccessIssue]

        self.elec_battery.timestep_end()
        self.assertEqual(
            self.elec_battery._ElectricBattery__total_time_charging_current_timestep,  # type: ignore[reportAttributeAccessIssue]
            0,
        )

    def test_limit_capacity_due_to_temp(self):
        """Test that __limit_capacity_due_to_temp returns the correct values based on battery location"""
        self.elec_battery._ElectricBattery__battery_location = BatteryLocation.OUTSIDE  # type: ignore[reportAttributeAccessIssue]
        self.assertEqual(self.elec_battery._ElectricBattery__limit_capacity_due_to_temp(), 0.8496)  # type: ignore[reportAttributeAccessIssue]

        self.elec_battery._ElectricBattery__battery_location = BatteryLocation.INSIDE  # type: ignore[reportAttributeAccessIssue]
        self.assertEqual(self.elec_battery._ElectricBattery__limit_capacity_due_to_temp(), 1)  # type: ignore[reportAttributeAccessIssue]

    def test_limit_capacity_due_to_temp_invalid_location(self):
        """Test that __limit_capacity_due_to_temp throws for an invalid battery location"""
        invalid_battery_location = "invalid-location"
        self.elec_battery._ElectricBattery__battery_location = invalid_battery_location  # type: ignore[reportAttributeAccessIssue]

        expected_options = [loc.value for loc in BatteryLocation]
        expected_message = f"Invalid battery location: {invalid_battery_location}. Valid options are: {expected_options}"

        with pytest.raises(ValueError, match=re.escape(expected_message)):
            self.elec_battery._ElectricBattery__limit_capacity_due_to_temp()  # type: ignore[reportAttributeAccessIssue]

    def test_capacity_temp_equ(self):
        """test that __capacity_temp_equ returns the correct values"""
        self.assertAlmostEqual(
            self.elec_battery._ElectricBattery__capacity_temp_equ(air_temp=5),  # type: ignore[reportAttributeAccessIssue]
            0.9043,
        )
        self.assertAlmostEqual(
            self.elec_battery._ElectricBattery__capacity_temp_equ(air_temp=10),  # type: ignore[reportAttributeAccessIssue]
            0.9476,
        )
        self.assertAlmostEqual(
            self.elec_battery._ElectricBattery__capacity_temp_equ(air_temp=20),  # type: ignore[reportAttributeAccessIssue]
            1.0,
        )
        self.assertAlmostEqual(
            self.elec_battery._ElectricBattery__capacity_temp_equ(air_temp=30),  # type: ignore[reportAttributeAccessIssue]
            1.0,
        )

    def test_charge_discharge_battery(self):
        """Test the charge_discharge_battery function including for
        overcharging and overdischarging.
        """
        # Supply to battery exceeds limit
        self.assertAlmostEqual(
            self.elec_battery.charge_discharge_battery(energy_flow=-1000),
            -1.6770509831248424,
            msg="Test failed: Supply to battery exceeds limit",
        )

        # Demand on battery exceeds limit
        self.assertAlmostEqual(
            self.elec_battery.charge_discharge_battery(energy_flow=1000),
            1.121472,
            msg="Test failed: Demand on battery exceeds limit",
        )

        # Normal charge
        self.assertAlmostEqual(
            self.elec_battery.charge_discharge_battery(energy_flow=-0.2),
            0.0,
            msg="Test failed: Normal charge",
        )

        # Normal discharge
        self.assertAlmostEqual(
            self.elec_battery.charge_discharge_battery(energy_flow=0.1),
            0.0747648,
            msg="Test failed: Normal discharge",
        )

    def test_charge_discharge_battery_below_minimum_chart_rate(self):
        """Test that the battery is not charged when below the minimum charge rate"""
        self.elec_battery._ElectricBattery__minimum_charge_rate = 20  # type: ignore[reportAttributeAccessIssue]
        self.elec_battery.charge_discharge_battery(energy_flow=-10)
        self.assertEqual(self.elec_battery.charge_discharge_battery(energy_flow=10), 0)

    def test_charge_discharge_battery_no_grid(self):
        """Test that charge_discharge_battery returns the correct values when charging from grid"""
        self.elec_battery.charge_discharge_battery(energy_flow=-10, charging_from_grid=True)
        self.assertEqual(
            self.elec_battery.charge_discharge_battery(energy_flow=10, charging_from_grid=True), 0
        )

    def test_charge_discharge_battery_grid(self):
        """Test that charge_discharge_battery returns the correct values when not charging from grid"""
        self.elec_battery.charge_discharge_battery(energy_flow=-10, charging_from_grid=False)
        self.assertEqual(
            self.elec_battery.charge_discharge_battery(energy_flow=10, charging_from_grid=False),
            1.121472,
        )

    def test_charge_discharge_battery_total_time(self):
        """Test that total_time_charging_current_timestep updated by charge_discharge_battery"""
        self.elec_battery.charge_discharge_battery(energy_flow=1)
        self.assertEqual(
            self.elec_battery._ElectricBattery__total_time_charging_current_timestep,  # type: ignore[reportAttributeAccessIssue]
            0.0,
        )

        self.elec_battery.charge_discharge_battery(energy_flow=-1)
        self.assertEqual(
            self.elec_battery._ElectricBattery__total_time_charging_current_timestep,  # type: ignore[reportAttributeAccessIssue]
            2 / 3.0,
        )
        self.elec_battery.charge_discharge_battery(energy_flow=1)
        self.assertEqual(
            self.elec_battery._ElectricBattery__total_time_charging_current_timestep,  # type: ignore[reportAttributeAccessIssue]
            2 / 3.0,
        )

    def test_charge_discharge_battery_total_time_no_charge(self):
        """Test that total_time_charging_current_timestep is 0 when below minimum charge rate"""
        self.elec_battery._ElectricBattery__minimum_charge_rate = 20  # type: ignore[reportAttributeAccessIssue]

        self.elec_battery.charge_discharge_battery(energy_flow=1)
        self.assertEqual(
            self.elec_battery._ElectricBattery__total_time_charging_current_timestep,  # type: ignore[reportAttributeAccessIssue]
            0.0,
        )

        self.elec_battery.charge_discharge_battery(energy_flow=-1)
        self.assertEqual(
            self.elec_battery._ElectricBattery__total_time_charging_current_timestep,  # type: ignore[reportAttributeAccessIssue]
            0,
        )

        self.elec_battery.charge_discharge_battery(energy_flow=1)
        self.assertEqual(
            self.elec_battery._ElectricBattery__total_time_charging_current_timestep,  # type: ignore[reportAttributeAccessIssue]
            0,
        )
