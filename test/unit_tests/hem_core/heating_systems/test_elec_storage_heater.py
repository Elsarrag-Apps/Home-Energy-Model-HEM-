#!/usr/bin/env python3

"""
This module contains unit tests for the ElecStorageHeater module
"""

# Standard library imports
import re
import unittest
from unittest.mock import MagicMock, Mock

import pytest

# Local imports
from hem_core.controls.time_control import ChargeControl, SetpointTimeControl
from hem_core.energy_supply.energy_supply import EnergySupply
from hem_core.external_conditions import ExternalConditions
from hem_core.heating_systems.elec_storage_heater import (
    ElecStorageHeater,
    OutputMode,
)
from hem_core.input_output.enums import (
    AirFlowType,
    ControlLogicType,
    FuelType,
)
from hem_core.simulation_time import SimulationTime


class TestElecStorageHeater(unittest.TestCase):
    """Unit tests for ElecStorageHeater class"""

    def setUp(self):
        """Create ElecStorageHeater object to be tested"""
        self.simulation_time = SimulationTime(start_time=0, end_time=24, step=1)

        # Define schedule for ChargeControl
        self.schedule = [
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            True,
            True,
            True,
            True,
            False,
            False,
            False,
            False,
        ]

        # External conditions for ChargeControl
        project_dict = {
            "ExternalConditions": {
                "air_temperatures": [
                    19.0,
                    0.0,
                    1.0,
                    2.0,
                    5.0,
                    7.0,
                    6.0,
                    12.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                ],
                "wind_speeds": [
                    3.9,
                    3.8,
                    3.9,
                    4.1,
                    3.8,
                    4.2,
                    4.3,
                    4.1,
                    3.9,
                    3.8,
                    3.9,
                    4.1,
                    3.8,
                    4.2,
                    4.3,
                    4.1,
                    3.9,
                    3.8,
                    3.9,
                    4.1,
                    3.8,
                    4.2,
                    4.3,
                    4.1,
                ],
                "wind_directions": [
                    300,
                    250,
                    220,
                    180,
                    150,
                    120,
                    100,
                    80,
                    60,
                    40,
                    20,
                    10,
                    50,
                    100,
                    140,
                    190,
                    200,
                    320,
                    330,
                    340,
                    350,
                    355,
                    315,
                    5,
                ],
                "diffuse_horizontal_radiation": [
                    0,
                    0,
                    0,
                    0,
                    35,
                    73,
                    139,
                    244,
                    320,
                    361,
                    369,
                    348,
                    318,
                    249,
                    225,
                    198,
                    121,
                    68,
                    19,
                    0,
                    0,
                    0,
                    0,
                    0,
                ],
                "direct_beam_radiation": [
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    7,
                    53,
                    63,
                    164,
                    339,
                    242,
                    315,
                    577,
                    385,
                    285,
                    332,
                    126,
                    7,
                    0,
                    0,
                    0,
                    0,
                    0,
                ],
                "solar_reflectivity_of_ground": [
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                ],
                "latitude": 51.383,
                "longitude": -0.783,
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
                    {"number": 2, "start": 135, "end": 90},
                    {"number": 3, "start": 90, "end": 45},
                    {
                        "number": 4,
                        "start": 45,
                        "end": 0,
                        "shading": [{"type": "obstacle", "height": 10.5, "distance": 12}],
                    },
                    {"number": 5, "start": 0, "end": -45},
                    {"number": 6, "start": -45, "end": -90},
                    {"number": 7, "start": -90, "end": -135},
                    {"number": 8, "start": -135, "end": -180},
                ],
            }
        }

        self.external_conditions = ExternalConditions(
            simulation_time=self.simulation_time,
            air_temps=project_dict["ExternalConditions"]["air_temperatures"],
            wind_speeds=project_dict["ExternalConditions"]["wind_speeds"],
            wind_directions=project_dict["ExternalConditions"]["wind_directions"],
            diffuse_horizontal_radiation=project_dict["ExternalConditions"][
                "diffuse_horizontal_radiation"
            ],
            direct_beam_radiation=project_dict["ExternalConditions"]["direct_beam_radiation"],
            solar_reflectivity_of_ground=project_dict["ExternalConditions"][
                "solar_reflectivity_of_ground"
            ],
            latitude=project_dict["ExternalConditions"]["latitude"],
            longitude=project_dict["ExternalConditions"]["longitude"],
            timezone=project_dict["ExternalConditions"]["timezone"],
            start_day=project_dict["ExternalConditions"]["start_day"],
            end_day=project_dict["ExternalConditions"]["end_day"],
            time_series_step=project_dict["ExternalConditions"]["time_series_step"],
            january_first=project_dict["ExternalConditions"]["january_first"],
            daylight_savings=project_dict["ExternalConditions"]["daylight_savings"],
            leap_day_included=project_dict["ExternalConditions"]["leap_day_included"],
            direct_beam_conversion_needed=project_dict["ExternalConditions"][
                "direct_beam_conversion_needed"
            ],
            shading_segments=project_dict["ExternalConditions"]["shading_segments"],
        )

        self.external_sensor = {
            "correlation": [
                {"temperature": 0.0, "max_charge": 1.0},
                {"temperature": 10.0, "max_charge": 0.9},
                {"temperature": 18.0, "max_charge": 0.5},
            ]
        }

        # Create the ChargeControl object
        self.charge_control = ChargeControl(
            logic_type=ControlLogicType.AUTOMATIC,
            schedule=self.schedule,
            simulation_time=self.simulation_time,
            start_day=0,
            time_series_step=1,
            charge_level=[1.0, 0.8],
            temp_charge_cut=22,
            temp_charge_cut_delta=None,
            extcond=self.external_conditions,
            external_sensor=self.external_sensor,
        )

        self.mock_zone = Mock()
        self.mock_zone.temp_internal_air.return_value = 20.0
        self.mock_zone.setpnt_init.return_value = 21.0

        energy_supply = EnergySupply(
            fuel_type=FuelType.ELECTRICITY, simulation_time=self.simulation_time
        )
        self.energy_supply_conn = energy_supply.connection(end_user_name="storage_heater")

        self.control = SetpointTimeControl(
            schedule=[21.0, 21.0, None, 21.0] + [None] * 20,
            simulation_time=self.simulation_time,
            start_day=0,
            time_series_step=1.0,
        )

        self.dry_core_min_output = [[0.0, 0.0], [0.5, 0.02], [1.0, 0.05]]
        self.dry_core_max_output = [[0.0, 0.0], [0.5, 1.5], [1.0, 3.0]]

        # Initialize ElecStorageHeater with ChargeControl
        self.heater = ElecStorageHeater(
            pwr_in=3.5,  # kW
            rated_power_instant=2.5,  # kW
            storage_capacity=10.0,  # kWh
            air_flow_type=AirFlowType.FAN_ASSISTED,
            frac_convective=0.7,
            fan_pwr=11,  # W
            n_units=1,
            zone=self.mock_zone,
            energy_supply_conn=self.energy_supply_conn,
            simulation_time=self.simulation_time,
            control=self.control,
            charge_control=self.charge_control,  # Use real ChargeControl object here
            dry_core_min_output=self.dry_core_min_output,
            dry_core_max_output=self.dry_core_max_output,
            state_of_charge_init=0,
        )

        # Use the accessor method to set state of charge
        self.heater._set_state_of_charge(soc=0.5)

        self.mock_cold_feed = MagicMock()
        self.mock_cold_feed.get_temp_cold_water.return_value = [(10.0, 1.0)]
        self.mock_cold_feed.temperature.return_value = 10.0

        # Add energy supply for HeatBatteryDryCore tests
        self.energy_supply = EnergySupply(
            fuel_type=FuelType.ELECTRICITY, simulation_time=self.simulation_time
        )
        self.energy_supply_conn = self.energy_supply.connection(end_user_name="heat_battery")

        self.heat_battery_dict = {
            "pwr_in": 3.0,
            "heat_storage_capacity": 5.0,
            "state_of_charge_init": 0,
            "dry_core_min_output": [[0.0, 0.05], [1.0, 0.15]],  # Changed from [100.0, 0.15]
            "dry_core_max_output": [[0.0, 0.3], [1.0, 0.8]],  # Changed from [100.0, 0.8]
            "fan_pwr": 0.02,
            "rated_power_instant": 0.5,
            "flow_rate_l_per_min": 10,
            "electricity_circ_pump": 0.06,
            "electricity_standby": 0.024,
            "setpoint_temp_water": 65,
        }

    def test_initialisation(self):
        """Test that the ElecStorageHeater is initialised correctly."""
        energy = self.heater.demand_energy(energy_demand=1.0)
        self.assertGreater(energy, 0)  # Should provide some energy

        # Test air flow type is set correctly by checking if fan energy is calculated
        self.assertEqual(self.heater._ElecStorageHeater__air_flow_type, AirFlowType.FAN_ASSISTED)  # type: ignore[AttributeAccessIssue]

    def test_initialisation_invalid_soc_arrays(self):
        def assertRaisesValueErrorWithSoc(dry_core_min_output, dry_core_max_output, msg=None):
            with self.assertRaises(ValueError, msg=msg):
                ElecStorageHeater(
                    pwr_in=1,
                    rated_power_instant=1,
                    storage_capacity=10.0,
                    air_flow_type=AirFlowType.FAN_ASSISTED,
                    frac_convective=1,
                    fan_pwr=10,
                    n_units=1,
                    zone=self.mock_zone,
                    energy_supply_conn=self.energy_supply_conn,
                    simulation_time=self.simulation_time,
                    control=self.control,
                    charge_control=self.charge_control,
                    dry_core_min_output=dry_core_min_output,
                    dry_core_max_output=dry_core_max_output,
                    state_of_charge_init=0,
                )

        assertRaisesValueErrorWithSoc(
            [[0.0, 0.0], [0.5, 0.02], [0.3, 0.02], [1.0, 0.05]],
            [[0.0, 0.0], [0.5, 1.5], [0.7, 0.02], [1.0, 3.0]],
            "shouldn't allow esh_min_output values in non-increasing order",
        )

        assertRaisesValueErrorWithSoc(
            [[0.0, 0.0], [0.5, 0.02], [0.7, 0.02], [1.0, 0.05]],
            [[0.0, 0.0], [0.5, 1.5], [0.3, 0.02], [1.0, 3.0]],
            "shouldn't allow esh_max_output values in non-increasing order",
        )

        assertRaisesValueErrorWithSoc(
            [[0.0, 0.0], [0.5, 0.02], [0.7, 0.02], [0.9, 0.05]],
            [[0.0, 0.0], [0.5, 1.5], [0.7, 0.02], [1.0, 3.0]],
            "shouldn't allow esh_min_output values not ending in 1.0",
        )

        assertRaisesValueErrorWithSoc(
            [[0.0, 0.0], [0.5, 0.02], [0.7, 0.02], [1.0, 0.05]],
            [[0.0, 0.0], [0.5, 1.5], [0.7, 0.02], [0.9, 3.0]],
            "shouldn't allow esh_max_output values not ending in 1.0",
        )

        assertRaisesValueErrorWithSoc(
            [[0.2, 0.0], [0.5, 0.02], [0.7, 0.02], [1.0, 0.05]],
            [[0.0, 0.0], [0.5, 1.5], [0.7, 0.02], [1.0, 3.0]],
            "shouldn't allow esh_min_output values not starting at 1.0",
        )

        assertRaisesValueErrorWithSoc(
            [[0.0, 0.0], [0.5, 0.02], [0.7, 0.02], [1.0, 0.05]],
            [[0.2, 0.0], [0.5, 1.5], [0.7, 0.02], [1.0, 3.0]],
            "shouldn't allow esh_max_output values not starting at 1.0",
        )

        assertRaisesValueErrorWithSoc(
            [[0.0, 0.0], [1.0, 1.0]],
            [[0.0, 0.0], [1.0, 0.5]],
            "shouldn't allow any power_max values below power_min",
        )

        assertRaisesValueErrorWithSoc(
            [[0.0, 0.0], [1.0, 1.0]],
            [[0.0, 0.0], [0.5, 0.4], [1.0, 1.0]],
            "shouldn't allow any power_max values below power_min",
        )

    def test_initialisation_detailed_results(self):
        """Test that the results are initialised depending on the flag"""
        heater_with_detailed_results = ElecStorageHeater(
            pwr_in=1,
            rated_power_instant=1,
            storage_capacity=10.0,
            air_flow_type=AirFlowType.FAN_ASSISTED,
            frac_convective=1,
            fan_pwr=10,
            n_units=1,
            zone=self.mock_zone,
            energy_supply_conn=self.energy_supply_conn,
            simulation_time=self.simulation_time,
            control=self.control,
            charge_control=self.charge_control,
            dry_core_min_output=self.dry_core_min_output,
            dry_core_max_output=self.dry_core_max_output,
            state_of_charge_init=0,
            output_detailed_results=True,
        )

        heater_without_detailed_results = ElecStorageHeater(
            pwr_in=1,
            rated_power_instant=1,
            storage_capacity=10.0,
            air_flow_type=AirFlowType.FAN_ASSISTED,
            frac_convective=1,
            fan_pwr=10,
            n_units=1,
            zone=self.mock_zone,
            energy_supply_conn=self.energy_supply_conn,
            simulation_time=self.simulation_time,
            control=self.control,
            charge_control=self.charge_control,
            dry_core_min_output=self.dry_core_min_output,
            dry_core_max_output=self.dry_core_max_output,
            state_of_charge_init=0,
            output_detailed_results=False,
        )

        self.assertEqual(heater_with_detailed_results.output_esh_results(), {})
        self.assertEqual(heater_without_detailed_results.output_esh_results(), None)

    def test_temp_setpnt(self):
        """Test that temp_setpnt returns the values from the control"""
        for t_idx, _, _ in self.simulation_time:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.heater.temp_setpnt(), ([21, 21, None, 21] + [None] * 20)[t_idx]
                )

    def test_in_required_period(self):
        """Test that in_required_period match values from the control"""
        for t_idx, _, _ in self.simulation_time:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.heater.in_required_period(),
                    ([True, True, False, True] + [False] * 20)[t_idx],
                )

    def test_frac_convective(self):
        """Test that frac_convertive returns the value given in initialisation"""
        self.assertEqual(self.heater.frac_convective(), 0.7)

    def test_energy_output_min(self):
        """Test minimum energy output calculation across all timesteps."""
        expected_min_energy_output = [
            0.019999999999999997,
            0.030419151282454364,
            0.0406826518009459,
            0.046014105108884346,
            0.04674323706081289,
            0.045800000000000014,
            0.046400000000000004,
            0.038,
            0.046886897763894056,
            0.03215061095009046,
            0.021233700713726503,
            0.01542628227371725,
            0.011428072222071864,
            0.008466125322130943,
            0.006271860545638567,
            0.004646308882570838,
            0.010432746398675731,
            0.01897277720547578,
            0.019999999999999997,
            0.019999999999999997,
            0.020056174317410178,
            0.014844117518306485,
            0.010996794239857175,
            0.008146626650951819,
        ]  # Actual minimum energy output for each timestep

        for t_idx, _, _ in self.simulation_time:
            with self.subTest(i=t_idx):
                min_energy_output = self.heater.energy_output_min()
                self.heater.demand_energy(energy_demand=5.0)
                self.assertAlmostEqual(
                    min_energy_output,
                    expected_min_energy_output[t_idx],
                    msg=f"energy output min failed at timestep {t_idx}",
                )

    def test_energy_output_max(self):
        """Test maximum energy output calculation across all timesteps."""
        expected_max_energy_output = [
            1.5,
            1.772121660521405,
            2.2199562136927717,
            2.5517202117781994,
            2.7913851590672585,
            2.7899999999999996,
            2.8200000000000003,
            2.4000000000000004,
            2.463423313846487,
            1.8249489529640162,
            1.3519554011630448,
            1.0015529506734968,
            0.7419686857505708,
            0.5496640579327374,
            0.40720123344887615,
            0.30166213975932143,
            0.6996897293886958,
            1.3814284569589004,
            1.5,
            1.5,
            1.3009346098448467,
            0.9637557636923015,
            0.713967931076402,
            0.5289205810615784,
        ]  # Expected max energy output for each timestep

        for t_idx, _, _ in self.simulation_time:
            with self.subTest(i=t_idx):
                max_energy_output = self.heater._energy_output_max()
                self.heater.demand_energy(energy_demand=5.0)
                energy, time_used, __, __ = max_energy_output
                self.assertAlmostEqual(
                    energy,
                    expected_max_energy_output[t_idx],
                    msg=f"energy output max failed at timestep {t_idx}",
                )

    def test_electric_charge_automatic(self):
        """Test electric charge calculation across all timesteps."""
        expected_target_electric_charge = [
            0.5,
            1.0,
            0.99,
            0.98,
            0.95,
            0.93,
            0.9400000000000001,
            0.8,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.5,
            0.5,
            0.5,
            0.5,
            0.0,
            0.0,
            0.0,
            0.0,
        ]  # Expected target charge for each timestep

        for t_idx, _, _ in self.simulation_time:
            with self.subTest(i=t_idx):
                # Use the protected method instead of the private one
                target_elec_charge = self.heater._HeatStorageDryCore__target_electric_charge(  # type: ignore[AttributeAccessIssue]
                    time=self.simulation_time.current_hour()
                )
                self.assertAlmostEqual(
                    target_elec_charge,
                    expected_target_electric_charge[t_idx],
                    msg=f"target electric charge failed at timestep {t_idx}",
                )

    def test_electric_charge_manual(self):
        """Test electric charge calculation for manual control logic"""
        self.charge_control = ChargeControl(
            logic_type=ControlLogicType.MANUAL,
            schedule=self.schedule,
            simulation_time=self.simulation_time,
            start_day=0,
            time_series_step=1,
            charge_level=[1.0, 0.8],
            temp_charge_cut=22,
            temp_charge_cut_delta=None,
            extcond=self.external_conditions,
            external_sensor=self.external_sensor,
        )

        self.heater = ElecStorageHeater(
            pwr_in=3.5,  # kW
            rated_power_instant=2.5,  # kW
            storage_capacity=10.0,  # kWh
            air_flow_type=AirFlowType.FAN_ASSISTED,
            frac_convective=0.7,
            fan_pwr=11,  # W
            n_units=1,
            zone=self.mock_zone,
            energy_supply_conn=self.energy_supply_conn,
            simulation_time=self.simulation_time,
            control=self.control,
            charge_control=self.charge_control,
            dry_core_min_output=self.dry_core_min_output,
            dry_core_max_output=self.dry_core_max_output,
            state_of_charge_init=0,
        )

        expected_target_electric_charge = [
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
            1.0,
            1.0,
            1.0,
            0.0,
            0.0,
            0.0,
            0.0,
        ]

        for t_idx, _, _ in self.simulation_time:
            target_elec_charge = self.heater._HeatStorageDryCore__target_electric_charge(  # type: ignore[AttributeAccessIssue]
                time=self.simulation_time.current_hour()
            )
            self.assertAlmostEqual(
                target_elec_charge,
                expected_target_electric_charge[t_idx],
                msg=f"target electric charge failed at timestep {t_idx}",
            )

    def test_electric_charge_celect(self):
        """Test electric charge calculation for Celect control logic"""
        self.charge_control = ChargeControl(
            logic_type=ControlLogicType.CELECT,
            schedule=self.schedule,
            simulation_time=self.simulation_time,
            start_day=0,
            time_series_step=1,
            charge_level=[1.0, 0.8],
            temp_charge_cut=22,
            temp_charge_cut_delta=None,
            extcond=self.external_conditions,
            external_sensor=self.external_sensor,
        )

        self.heater = ElecStorageHeater(
            pwr_in=3.5,  # kW
            rated_power_instant=2.5,  # kW
            storage_capacity=10.0,  # kWh
            air_flow_type=AirFlowType.FAN_ASSISTED,
            frac_convective=0.7,
            fan_pwr=11,  # W
            n_units=1,
            zone=self.mock_zone,
            energy_supply_conn=self.energy_supply_conn,
            simulation_time=self.simulation_time,
            control=self.control,
            charge_control=self.charge_control,
            dry_core_min_output=self.dry_core_min_output,
            dry_core_max_output=self.dry_core_max_output,
            state_of_charge_init=0,
        )

        expected_target_electric_charge = [
            0.5,
            1.0,
            0.99,
            0.98,
            0.95,
            0.93,
            0.94,
            0.8,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.5,
            0.5,
            0.5,
            0.5,
            0.0,
            0.0,
            0.0,
            0.0,
        ]

        for t_idx, _, _ in self.simulation_time:
            target_elec_charge = self.heater._HeatStorageDryCore__target_electric_charge(  # type: ignore[AttributeAccessIssue]
                time=self.simulation_time.current_hour()
            )
            self.assertAlmostEqual(
                target_elec_charge,
                expected_target_electric_charge[t_idx],
                msg=f"target electric charge failed at timestep {t_idx}",
            )

    def test_electric_charge_hhrsh(self):
        """Test electric charge calculation for HHRSH control logic"""
        self.charge_control = ChargeControl(
            logic_type=ControlLogicType.HHRSH,
            schedule=self.schedule,
            simulation_time=self.simulation_time,
            start_day=0,
            time_series_step=1,
            charge_level=[1.0, 0.8],
            temp_charge_cut=22,
            temp_charge_cut_delta=None,
            extcond=self.external_conditions,
            external_sensor=self.external_sensor,
        )

        self.heater = ElecStorageHeater(
            pwr_in=3.5,  # kW
            rated_power_instant=2.5,  # kW
            storage_capacity=10.0,  # kWh
            air_flow_type=AirFlowType.FAN_ASSISTED,
            frac_convective=0.7,
            fan_pwr=11,  # W
            n_units=1,
            zone=self.mock_zone,
            energy_supply_conn=self.energy_supply_conn,
            simulation_time=self.simulation_time,
            control=self.control,
            charge_control=self.charge_control,
            dry_core_min_output=self.dry_core_min_output,
            dry_core_max_output=self.dry_core_max_output,
            state_of_charge_init=0,
        )

        expected_target_electric_charge = [
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            1,
            1,
            1,
            1,
            0,
            0,
            0,
            0,
        ]

        for t_idx, _, _ in self.simulation_time:
            target_elec_charge = self.heater._HeatStorageDryCore__target_electric_charge(  # type: ignore[AttributeAccessIssue]
                time=self.simulation_time.current_hour()
            )
            self.assertAlmostEqual(
                target_elec_charge,
                expected_target_electric_charge[t_idx],
                msg=f"target electric charge failed at timestep {t_idx}",
            )

    def test_electric_charge_hhrsh_negative_heat_retention_ratio(self):
        """Test electric charge calculation for HHRSH control logic for negative heat_retention_ratio"""
        self.charge_control = ChargeControl(
            logic_type=ControlLogicType.HHRSH,
            schedule=self.schedule,
            simulation_time=self.simulation_time,
            start_day=0,
            time_series_step=1,
            charge_level=[1.0, 0.8],
            temp_charge_cut=22,
            temp_charge_cut_delta=None,
            extcond=self.external_conditions,
            external_sensor=self.external_sensor,
        )

        self.heater = ElecStorageHeater(
            pwr_in=3.5,  # kW
            rated_power_instant=2.5,  # kW
            storage_capacity=10,  # kWh
            air_flow_type=AirFlowType.FAN_ASSISTED,
            frac_convective=0.7,
            fan_pwr=11,  # W
            n_units=1,
            zone=self.mock_zone,
            energy_supply_conn=self.energy_supply_conn,
            simulation_time=self.simulation_time,
            control=self.control,
            charge_control=self.charge_control,
            dry_core_min_output=self.dry_core_min_output,
            dry_core_max_output=self.dry_core_max_output,
            state_of_charge_init=0,
        )

        self.heater._HeatStorageDryCore__heat_retention_ratio = -0.9  # type: ignore[AttributeAccessIssue]
        self.heater._set_state_of_charge(soc=0.5)

        expected_target_electric_charge = [
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            1,
            1,
            1,
            1,
            0,
            0,
            0,
            0,
        ]

        for t_idx, _, _ in self.simulation_time:
            target_electric_charge = self.heater._HeatStorageDryCore__target_electric_charge(  # type: ignore[AttributeAccessIssue]
                time=self.simulation_time.current_hour()
            )
            self.assertAlmostEqual(
                target_electric_charge,
                expected_target_electric_charge[t_idx],
                msg=f"target electric charge failed at timestep {t_idx}",
            )

    def test_electric_charge_invalid_logic_type(self):
        """Test electric charge calculation raises on an invalid logic type"""
        self.charge_control = ChargeControl(
            logic_type=ControlLogicType.HEAT_BATTERY,
            schedule=self.schedule,
            simulation_time=self.simulation_time,
            start_day=0,
            time_series_step=1,
            charge_level=[1.0, 0.8],
            temp_charge_cut=22,
            temp_charge_cut_delta=None,
            extcond=self.external_conditions,
            external_sensor=self.external_sensor,
        )

        with self.assertRaises(ValueError) as cm:
            self.heater = ElecStorageHeater(
                pwr_in=3.5,  # kW
                rated_power_instant=2.5,  # kW
                storage_capacity=10,  # kWh
                air_flow_type=AirFlowType.FAN_ASSISTED,
                frac_convective=0.7,
                fan_pwr=11,  # W
                n_units=1,
                zone=self.mock_zone,
                energy_supply_conn=self.energy_supply_conn,
                simulation_time=self.simulation_time,
                control=self.control,
                charge_control=self.charge_control,
                dry_core_min_output=self.dry_core_min_output,
                dry_core_max_output=self.dry_core_max_output,
                state_of_charge_init=0,
            )

        # Optionally, verify the error message
        self.assertIn("heat_battery", str(cm.exception).lower())
        self.assertIn("not valid for ElecStorageHeater", str(cm.exception))

    def test_electric_charge_hhrsh_no_heat_retention_ratio(self):
        """Test electric charge calculation for HHRSH control logic throws wihout heat_retention_ratio"""
        self.charge_control = ChargeControl(
            logic_type=ControlLogicType.HHRSH,
            schedule=self.schedule,
            simulation_time=self.simulation_time,
            start_day=0,
            time_series_step=1,
            charge_level=[1.0, 0.8],
            temp_charge_cut=22,
            temp_charge_cut_delta=None,
            extcond=self.external_conditions,
            external_sensor=self.external_sensor,
        )

        self.heater = ElecStorageHeater(
            pwr_in=3.5,  # kW
            rated_power_instant=2.5,  # kW
            storage_capacity=10.0,  # kWh
            air_flow_type=AirFlowType.FAN_ASSISTED,
            frac_convective=0.7,
            fan_pwr=11,  # W
            n_units=1,
            zone=self.mock_zone,
            energy_supply_conn=self.energy_supply_conn,
            simulation_time=self.simulation_time,
            control=self.control,
            charge_control=self.charge_control,
            dry_core_min_output=self.dry_core_min_output,
            dry_core_max_output=self.dry_core_max_output,
            state_of_charge_init=0,
        )

        self.heater._HeatStorageDryCore__heat_retention_ratio = None  # type: ignore[AttributeAccessIssue]

        with self.assertRaises(ValueError):
            self.heater._HeatStorageDryCore__target_electric_charge(  # type: ignore[AttributeAccessIssue]
                time=self.simulation_time.current_hour()
            )

    def test_demand_energy(self):
        """Test demand energy functionality across all timesteps."""
        expected_energy = [
            4.0,
            4.272121660521405,
            4.719956213692772,
            5.0,
            5.0,
            5.0,
            5.0,
            4.9,
            4.963423313846487,
            4.324948952964016,
            3.851955401163045,
            3.5015529506734966,
            3.241968685750571,
            3.0496640579327376,
            2.907201233448876,
            2.8016621397593213,
            3.199689729388696,
            3.8814284569589006,
            4.0,
            4.0,
            3.8009346098448464,
            3.4637557636923013,
            3.213967931076402,
            3.0289205810615782,
        ]  # Expected energy for each timestep

        for t_idx, _, _ in self.simulation_time:
            with self.subTest(i=t_idx):
                energy_out = self.heater.demand_energy(energy_demand=5.0)
                self.assertAlmostEqual(
                    energy_out,
                    expected_energy[t_idx],
                    msg=f"demand energy failed at timestep {t_idx}",
                )

    def test_demand_energy_no_demand(self):
        """Test demand energy functionality across all timesteps with no demand"""
        expected_energy = [
            0.019999999999999997,
            0.030419151282454364,
            0.04762390188197366,
            0.0488,
            0.04700000000000001,
            0.0458,
            0.046400000000000004,
            0.038,
            0.04932504653147142,
            0.04902998233007885,
            0.0487366832133454,
            0.0484451386224712,
            0.048155338061819486,
            0.04786727109853878,
            0.047580927362187296,
            0.047296296544359594,
            0.019999999999999997,
            0.019999999999999997,
            0.019999999999999997,
            0.019999999999999997,
            0.04701336839831551,
            0.046732132738611196,
            0.046452579440732555,
            0.04617469844073066,
        ]  # Expected energy for each timestep

        for t_idx, _, _ in self.simulation_time:
            with self.subTest(i=t_idx):
                energy_out = self.heater.demand_energy(energy_demand=0)
                self.assertAlmostEqual(
                    energy_out,
                    expected_energy[t_idx],
                    msg=f"demand energy failed at timestep {t_idx}",
                )

    def test_demand_energy_detailed_results(self):
        heater = ElecStorageHeater(
            pwr_in=1,
            rated_power_instant=1,
            storage_capacity=10.0,
            air_flow_type=AirFlowType.FAN_ASSISTED,
            frac_convective=1,
            fan_pwr=10,
            n_units=1,
            zone=self.mock_zone,
            energy_supply_conn=self.energy_supply_conn,
            simulation_time=self.simulation_time,
            control=self.control,
            charge_control=self.charge_control,
            dry_core_min_output=self.dry_core_min_output,
            dry_core_max_output=self.dry_core_max_output,
            state_of_charge_init=0,
            output_detailed_results=True,
        )

        expected_results = {
            0: [
                0,
                1,
                5.0,
                0.1360608282280595,
                1,
                0.9999999999999999,
                0.01,
                0.08639391717719404,
                0.08639391717719405,
                1,
            ],
            1: [
                1,
                1,
                5.0,
                0.35997826917949083,
                1,
                0.9999999999999998,
                0.01,
                0.15039609025924494,
                0.15039609025924494,
                1,
            ],
            2: [
                2,
                1,
                5.0,
                0.525860161130055,
                1,
                0.9999999999999998,
                0.01,
                0.1978100741462394,
                0.19781007414623947,
                1,
            ],
            3: [
                3,
                1,
                5.0,
                0.6487484969563722,
                1,
                0.9999999999999997,
                0.01,
                0.23293522445060216,
                0.2329352244506022,
                1,
            ],
            4: [
                4,
                1,
                5.0,
                0.7397864472877566,
                1,
                0.9999999999999998,
                0.01,
                0.2589565797218265,
                0.2589565797218265,
                1,
            ],
            5: [
                5,
                1,
                5.0,
                0.8072290379637572,
                1,
                0.9999999999999998,
                0.01,
                0.2782336759254508,
                0.2782336759254508,
                1,
            ],
            6: [
                6,
                1,
                5.0,
                0.8571917472765138,
                1,
                0.9999999999999999,
                0.01,
                0.29251450119779937,
                0.29251450119779937,
                1,
            ],
            7: [
                7,
                1,
                5.0,
                0.894205037502244,
                1,
                0.9999999999999998,
                0.01,
                0.3030939974475749,
                0.303093997447575,
                1,
            ],
            8: [
                8,
                1,
                5.0,
                0.7855640835379172,
                1,
                0.0,
                0.01,
                0.2245375890937832,
                0.2245375890937832,
                1,
            ],
            9: [
                9,
                1,
                5.0,
                0.5819603347886747,
                1,
                0.0,
                0.01,
                0.16634155561491576,
                0.16634155561491573,
                1,
            ],
            10: [
                10,
                1,
                5.0,
                0.4311269125454673,
                1,
                0.0,
                0.01,
                0.12322886436036903,
                0.12322886436036903,
                1,
            ],
            11: [
                11,
                1,
                5.0,
                0.3193867248864036,
                1,
                0.0,
                0.01,
                0.09129019187172868,
                0.09129019187172868,
                1,
            ],
            12: [
                12,
                1,
                5.0,
                0.23660753075068583,
                1,
                0.0,
                0.01,
                0.0676294387966601,
                0.06762943879666009,
                1,
            ],
            13: [
                13,
                1,
                5.0,
                0.17528317748916877,
                1,
                0.0,
                0.01,
                0.050101121047743225,
                0.050101121047743225,
                1,
            ],
            14: [
                14,
                1,
                5.0,
                0.1298529738329292,
                1,
                0.0,
                0.01,
                0.037115823664450306,
                0.037115823664450306,
                1,
            ],
            15: [
                15,
                1,
                5.0,
                0.09619745025800532,
                1,
                0.0,
                0.01,
                0.027496078638649776,
                0.02749607863864978,
                1,
            ],
            16: [
                16,
                1,
                5.0,
                0.20732566160442942,
                1,
                0.9999999999999998,
                0.01,
                0.10676351247820681,
                0.10676351247820684,
                1,
            ],
            17: [
                17,
                1,
                5.0,
                0.41277253407174264,
                1,
                0.9999999999999998,
                0.01,
                0.16548625907103254,
                0.16548625907103257,
                1,
            ],
            18: [
                18,
                1,
                5.0,
                0.5649711048613184,
                1,
                0.9999999999999998,
                0.01,
                0.20898914858490067,
                0.2089891485849007,
                1,
            ],
            19: [
                19,
                1,
                5.0,
                0.6777226070926419,
                1,
                0.9999999999999998,
                0.01,
                0.24121688787563644,
                0.24121688787563647,
                1,
            ],
            20: [
                20,
                1,
                5.0,
                0.625190008414656,
                1,
                0.0,
                0.01,
                0.17869788703417083,
                0.17869788703417083,
                1,
            ],
            21: [
                21,
                1,
                5.0,
                0.46315225418860434,
                1,
                0.0,
                0.01,
                0.1323826616153104,
                0.13238266161531043,
                1,
            ],
            22: [
                22,
                1,
                5.0,
                0.34311168983701723,
                1,
                0.0,
                0.01,
                0.09807149263160868,
                0.09807149263160866,
                1,
            ],
            23: [
                23,
                1,
                5.0,
                0.25418342247140796,
                1,
                0.0,
                0.01,
                0.07265315038446787,
                0.07265315038446787,
                1,
            ],
        }

        for _ in self.simulation_time:
            heater.demand_energy(energy_demand=5.0)

        results = heater.output_esh_results()
        assert results is not None, (
            "heater.output_esh_results() returned None when a dict was expected"
        )

        for t_idx in range(24):
            for v_idx in range(len(expected_results[t_idx])):
                self.assertAlmostEqual(results[t_idx][v_idx], expected_results[t_idx][v_idx])

    def test_energy_for_fan(self):
        """Test energy for fan calculation across all timesteps."""
        expected_energy_for_fan = [
            0.003666666666666663,
            0.0034561513858793556,
            0.003133016027878955,
            0.0029047621124394848,
            0.0027330949708021268,
            0.0025983637642646956,
            0.0024893028132490476,
            0.002398927856611201,
            0.00243802553077851,
            0.0026117536650591346,
            0.002812153391189732,
            0.003045881325103026,
            0.0033220118367143004,
            0.003653245351058463,
            0.004057922556940931,
            0.004563550936407075,
            0.004342298713919709,
            0.0037302627836201,
            0.0036666666666666644,
            0.0036666666666666644,
            0.003861966010382251,
            0.004317143115057025,
            0.004894130588434899,
            0.005649492532217881,
        ]  # Expected energy for fan for each timestep

        for t_idx, _, _ in self.simulation_time:
            with self.subTest(i=t_idx):
                self.heater.demand_energy(energy_demand=0.5)
                energy_for_fan = self.heater._ElecStorageHeater__energy_for_fan  # type: ignore[AttributeAccessIssue]
                self.assertAlmostEqual(
                    energy_for_fan,
                    expected_energy_for_fan[t_idx],
                    msg=f"Energy for fan failed at timestep {t_idx}",
                )

    def test_energy_instant(self):
        """Test instant energy output calculation across all timesteps."""
        expected_energy_instant = [
            2.5,
            2.5,
            2.5,
            2.4482797882218006,
            2.208614840932741,
            2.2100000000000004,
            2.18,
            2.5,
            2.5,
            2.5,
            2.5,
            2.5,
            2.5,
            2.5,
            2.5,
            2.5,
            2.5,
            2.5,
            2.5,
            2.5,
            2.5,
            2.5,
            2.5,
            2.5,
        ]  # Expected backup energy instant for each timestep

        for t_idx, _, _ in self.simulation_time:
            with self.subTest(i=t_idx):
                self.heater.demand_energy(energy_demand=5)
                energy_instant = self.heater._ElecStorageHeater__energy_instant  # type: ignore[AttributeAccessIssue]
                self.assertAlmostEqual(
                    energy_instant,
                    expected_energy_instant[t_idx],
                    msg=f"Energy instant failed at timestep {t_idx}",
                )

    def test_energy_charged(self):
        """Test energy charged calculation across all timesteps."""
        expected_energy_charged = [
            1.5,
            3.500000000000001,
            3.5,
            3.5,
            3.3397997646920756,
            2.7899999999999996,
            2.82,
            2.4000000000000004,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            3.500000000000001,
            2.738269398472182,
            1.5,
            1.5,
            0.0,
            0.0,
            0.0,
            0.0,
        ]  # Expected energy charged for each timestep

        for t_idx, _, _ in self.simulation_time:
            with self.subTest(i=t_idx):
                self.heater.demand_energy(energy_demand=5)
                energy_charged = self.heater._ElecStorageHeater__energy_charged  # type: ignore[AttributeAccessIssue]
                self.assertAlmostEqual(
                    energy_charged,
                    expected_energy_charged[t_idx],
                    msg=f"Energy charged failed at timestep {t_idx}",
                )

    def test_energy_stored_delivered(self):
        """Test stored energy delivered calculation across all timesteps."""
        expected_energy_delivered = [
            1.5,
            1.772121660521405,
            2.219956213692772,
            2.5517202117781994,
            2.791385159067259,
            2.7899999999999996,
            2.82,
            2.4000000000000004,
            2.4634233138464876,
            1.8249489529640166,
            1.3519554011630448,
            1.0015529506734968,
            0.7419686857505706,
            0.5496640579327375,
            0.4072012334488761,
            0.30166213975932155,
            0.6996897293886956,
            1.3814284569589008,
            1.5,
            1.5,
            1.300934609844847,
            0.9637557636923016,
            0.713967931076402,
            0.5289205810615786,
        ]  # Expected energy stored delivered for each timestep

        for t_idx, _, _ in self.simulation_time:
            with self.subTest(i=t_idx):
                self.heater.demand_energy(energy_demand=5)
                energy_delivered = self.heater._ElecStorageHeater__energy_delivered  # type: ignore[AttributeAccessIssue]
                self.assertAlmostEqual(
                    energy_delivered,
                    expected_energy_delivered[t_idx],
                    msg=f"Energy stored delivered failed at timestep {t_idx}",
                )

    def test_invalid_air_flow_type(self):
        """Test invalid air flow type."""
        invalid_air_flow_type = "invalid-type"

        expected_message = f"'{invalid_air_flow_type}' is not a valid AirFlowType"

        with pytest.raises(ValueError, match=re.escape(expected_message)):
            ElecStorageHeater(
                pwr_in=3.5,
                rated_power_instant=2.5,
                storage_capacity=10.0,
                air_flow_type=AirFlowType(invalid_air_flow_type),
                frac_convective=0.7,
                fan_pwr=0.1,
                n_units=1,
                zone=self.mock_zone,
                energy_supply_conn=self.heater._ElecStorageHeater__energy_supply_conn,  # type: ignore[AttributeAccessIssue]
                simulation_time=self.simulation_time,
                control=self.heater._ElecStorageHeater__control,  # type: ignore[AttributeAccessIssue]
                charge_control=self.heater._ElecStorageHeater__charge_control,  # type: ignore[AttributeAccessIssue]
                dry_core_min_output=self.dry_core_min_output,
                dry_core_max_output=self.dry_core_max_output,
                state_of_charge_init=0,
            )

    def test_damper_only(self):
        """Test ElecStorageHeater with damper only (no fan)"""
        heater = ElecStorageHeater(
            pwr_in=3.5,
            rated_power_instant=2.5,
            storage_capacity=10.0,
            air_flow_type=AirFlowType.DAMPER_ONLY,
            frac_convective=0.7,
            fan_pwr=11,  # Should be ignored for damper only
            n_units=1,
            zone=self.mock_zone,
            energy_supply_conn=self.energy_supply_conn,
            simulation_time=self.simulation_time,
            control=self.control,
            charge_control=self.charge_control,
            dry_core_min_output=self.dry_core_min_output,
            dry_core_max_output=self.dry_core_max_output,
            state_of_charge_init=0,
        )

        heater._set_state_of_charge(soc=0.5)
        heater.demand_energy(energy_demand=1.0)
        # Fan energy should be 0 for damper only
        self.assertEqual(heater._ElecStorageHeater__energy_for_fan, 0.0)  # type: ignore[AttributeAccessIssue]

    def test_protected_accessor_methods(self):
        """Test all protected accessor methods"""
        # Test getter methods
        self.assertEqual(self.heater._get_state_of_charge(), 0.5)
        self.assertEqual(self.heater._get_storage_capacity(), 10.0)
        self.assertEqual(self.heater._get_pwr_in(), 3.5)
        self.assertEqual(self.heater._get_n_units(), 1)
        self.assertIsNotNone(self.heater._get_simulation_time())
        self.assertEqual(self.heater._get_demand_met(), 0.0)
        self.assertEqual(self.heater._get_demand_unmet(), 0.0)
        self.assertIsNotNone(self.heater._get_power_max_func())
        self.assertIsNotNone(self.heater._get_power_min_func())

        # Test setter methods
        self.heater._set_state_of_charge(soc=0.8)
        self.assertEqual(self.heater._get_state_of_charge(), 0.8)

        self.heater._set_demand_met(1.5)
        self.assertEqual(self.heater._get_demand_met(), 1.5)

        self.heater._set_demand_unmet(0.5)
        self.assertEqual(self.heater._get_demand_unmet(), 0.5)

        # Test SOC clipping
        self.heater._set_state_of_charge(soc=1.5)  # Above 1.0
        self.assertEqual(self.heater._get_state_of_charge(), 1.0)

        self.heater._set_state_of_charge(soc=-0.5)  # Below 0.0
        self.assertEqual(self.heater._get_state_of_charge(), 0.0)

    def test_invalid_charge_control_logic_error(self):
        """Test invalid charge control logic type in __target_electric_charge"""
        # Create a mock charge control with an invalid logic type
        mock_invalid_control = Mock()
        mock_invalid_control.logic_type.return_value = "INVALID_TYPE"

        # Replace the charge control temporarily
        original_control = self.heater._HeatStorageDryCore__charge_control  # type: ignore[AttributeAccessIssue]
        self.heater._HeatStorageDryCore__charge_control = mock_invalid_control  # type: ignore[AttributeAccessIssue]

        try:
            with self.assertRaises(ValueError) as cm:
                self.heater._HeatStorageDryCore__target_electric_charge(  # type: ignore[AttributeAccessIssue]
                    time=self.simulation_time.current_hour()
                )
            self.assertIn("Invalid logic type", str(cm.exception))
        finally:
            # Restore original control
            self.heater._HeatStorageDryCore__charge_control = original_control  # type: ignore[AttributeAccessIssue]

    def test_elec_storage_heater_no_instant_power(self):
        """Test ElecStorageHeater without instant backup power"""
        heater = ElecStorageHeater(
            pwr_in=3.5,
            rated_power_instant=0.0,  # No instant power
            storage_capacity=10.0,
            air_flow_type=AirFlowType.FAN_ASSISTED,
            frac_convective=0.7,
            fan_pwr=11,
            n_units=1,
            zone=self.mock_zone,
            energy_supply_conn=self.energy_supply_conn,
            simulation_time=self.simulation_time,
            control=self.control,
            charge_control=self.charge_control,
            dry_core_min_output=self.dry_core_min_output,
            dry_core_max_output=self.dry_core_max_output,
            state_of_charge_init=0,
        )

        # Set low SOC
        heater._set_state_of_charge(soc=0.1)

        # Demand high energy
        energy = heater.demand_energy(energy_demand=10.0)

        # Should get limited energy without instant backup
        self.assertLess(energy, 10.0)

    def test_elec_storage_energy_output_modes(self):
        """Test different energy output modes"""
        # Test MIN mode
        energy_min = self.heater._energy_output(mode=OutputMode.MIN)
        self.assertIsInstance(energy_min, tuple)
        self.assertGreater(energy_min[0], 0)

        # Test MAX mode
        energy_max = self.heater._energy_output(mode=OutputMode.MAX)
        self.assertIsInstance(energy_max, tuple)
        self.assertGreater(energy_max[0], energy_min[0])

    def test_get_temp_for_charge_control(self):
        """Test _get_temp_for_charge_control for ElecStorageHeater"""
        temp = self.heater._get_temp_for_charge_control()
        self.assertEqual(temp, 20.0)  # Should return zone temperature

    def test_get_zone_setpoint(self):
        """Test _get_zone_setpoint for ElecStorageHeater"""
        setpoint = self.heater._get_zone_setpoint()
        self.assertEqual(setpoint, 21.0)  # Should return zone setpoint

    def test_output_mode_enum_values(self):
        """Test OutputMode enum values"""
        # Ensure enum coverage
        self.assertEqual(OutputMode.MIN.value, "min")
        self.assertEqual(OutputMode.MAX.value, "max")

    def test_heat_storage_dry_core_boundary_soc_values(self):
        """Test HeatStorageDryCore with boundary state of charge values"""
        # Test with SOC at 0%
        self.heater._HeatStorageDryCore__current_core_soc = 0.0  # type: ignore[AttributeAccessIssue]
        # Use the protected method instead
        result = self.heater._energy_output(mode=OutputMode.MIN)
        self.assertIsInstance(result, tuple)
        self.assertGreaterEqual(result[0], 0)

    def test_heat_storage_dry_core_zero_capacity(self):
        """Test behavior with zero heat storage capacity"""
        energy_supply = EnergySupply(
            fuel_type=FuelType.ELECTRICITY, simulation_time=self.simulation_time
        )
        energy_supply_conn = energy_supply.connection(end_user_name="storage_heater")

        # This should handle zero capacity gracefully
        with self.assertRaises(ValueError):
            ElecStorageHeater(
                pwr_in=0.55,  # Fixed parameter name
                rated_power_instant=0.23,  # Fixed parameter name
                storage_capacity=0.0,  # Zero capacity
                air_flow_type=AirFlowType.DAMPER_ONLY,
                frac_convective=0.4,
                fan_pwr=0.02,
                n_units=1,
                zone=self.mock_zone,
                energy_supply_conn=energy_supply_conn,  # Fixed parameter name
                simulation_time=self.simulation_time,
                control=self.control,
                charge_control=self.charge_control,
                dry_core_min_output=[[0.0, 0.05], [100.0, 0.15]],
                dry_core_max_output=[[0.0, 0.3], [100.0, 0.8]],
                state_of_charge_init=0,
            )
