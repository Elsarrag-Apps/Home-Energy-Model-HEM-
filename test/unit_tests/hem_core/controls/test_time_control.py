#!/usr/bin/env python3

"""
This module contains unit tests for the Time Control module
"""

# Standard library imports
import unittest
from unittest.mock import MagicMock

from hem_core.controls.time_control import (
    ChargeControl,
    CombinationTimeControl,
    OnOffCostMinimisingTimeControl,
    OnOffTimeControl,
    SetpointTimeControl,
    SmartApplianceControl,
)
from hem_core.external_conditions import ExternalConditions
from hem_core.input_output.enums import (
    ControlCombinationOperation,
    ControlLogicType,
)

# Local imports
from hem_core.simulation_time import SimulationTime


class Test_OnOffTimeControl(unittest.TestCase):
    """Unit tests for OnOffTimeControl class"""

    def setUp(self):
        """Create TimeControl object to be tested"""
        self.simtime = SimulationTime(0, 8, 1)
        self.schedule = [True, False, True, True, False, True, False, False]
        self.timecontrol = OnOffTimeControl(
            schedule=self.schedule, simulation_time=self.simtime, start_day=0, time_series_step=1
        )

    def test_is_on(self):
        """Test that OnOffTimeControl object returns correct schedule"""
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.timecontrol.is_on(),
                    self.schedule[t_idx],
                    "incorrect schedule returned",
                )


class Test_OnOffCostMinimisingTimeControl(unittest.TestCase):
    def setUp(self):
        self.simtime = SimulationTime(start_time=0, end_time=48, step=1)
        cost_schedule = 2 * ([5.0] * 7 + [10.0] * 2 + [7.5] * 8 + [15.0] * 6 + [5.0])
        self.cost_minimising_ctrl = OnOffCostMinimisingTimeControl(
            schedule=cost_schedule,
            simulation_time=self.simtime,
            start_day=0,  # Start day
            time_series_step=1.0,  # Schedule data is hourly
            time_on_daily=12.0,  # Need 12 "on" hours
        )

    def test_init_invalid_schedule_length(self):
        cost_schedule = 2 * ([5.0] * 7 + [10.0] * 2 + [7.5] * 8 + [15.0] * 6)
        with self.assertRaises(ValueError):
            self.cost_minimising_ctrl = OnOffCostMinimisingTimeControl(
                schedule=cost_schedule,
                simulation_time=self.simtime,
                start_day=0,  # Start day
                time_series_step=1.0,  # Schedule data is hourly
                time_on_daily=12.0,  # Need 12 "on" hours
            )

    def test_is_on(self):
        resulting_schedule = 2 * (
            [True] * 7 + [False] * 2 + [True] * 4 + [False] * 4 + [False] * 6 + [True]
        )
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.cost_minimising_ctrl.is_on(),
                    resulting_schedule[t_idx],
                    "incorrect schedule returned",
                )


class Test_SetpointTimeControl(unittest.TestCase):
    """Unit tests for SetpointTimeControl class"""

    def setUp(self):
        """Create TimeControl object to be tested"""
        self.simtime = SimulationTime(start_time=0, end_time=8, step=1)
        self.schedule = [21.0, None, None, 21.0, None, 21.0, 25.0, 15.0]
        self.timecontrol = SetpointTimeControl(
            schedule=self.schedule, simulation_time=self.simtime, start_day=0, time_series_step=1
        )
        self.timecontrol_min = SetpointTimeControl(
            schedule=self.schedule,
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
            setpoint_min=16.0,
            setpoint_max=None,
        )
        self.timecontrol_max = SetpointTimeControl(
            schedule=self.schedule,
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
            setpoint_min=None,
            setpoint_max=24.0,
        )
        self.timecontrol_minmax = SetpointTimeControl(
            schedule=self.schedule,
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
            setpoint_min=16.0,
            setpoint_max=24.0,
            default_to_max=False,
        )
        self.timecontrol_advstart = SetpointTimeControl(
            schedule=self.schedule,
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
            setpoint_min=None,
            setpoint_max=None,
            default_to_max=False,
            duration_advanced_start=1.0,
        )
        self.timecontrol_advstart_minmax = SetpointTimeControl(
            schedule=self.schedule,
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
            setpoint_min=16.0,
            setpoint_max=24.0,
            default_to_max=False,
            duration_advanced_start=1.0,
        )

    def test_in_required_period(self):
        """Test that SetpointTimeControl objects return correct status for required period"""
        results = [True, False, False, True, False, True, True, True]
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.timecontrol.in_required_period(),
                    results[t_idx],
                    "incorrect in_required_period value returned for control with no min or max set",
                )
                self.assertEqual(
                    self.timecontrol_min.in_required_period(),
                    results[t_idx],
                    "incorrect in_required_period value returned for control with min set",
                )
                self.assertEqual(
                    self.timecontrol_max.in_required_period(),
                    results[t_idx],
                    "incorrect in_required_period value returned for control with max set",
                )
                self.assertEqual(
                    self.timecontrol_minmax.in_required_period(),
                    results[t_idx],
                    "incorrect in_required_period value returned for control with min and max set",
                )
                self.assertEqual(
                    self.timecontrol_advstart.in_required_period(),
                    results[t_idx],
                    "incorrect in_required_period value returned for control with advanced start",
                )
                self.assertEqual(
                    self.timecontrol_advstart_minmax.in_required_period(),
                    results[t_idx],
                    "incorrect in_required_period value returned for control with advanced start",
                )

    def test_is_on(self):
        """Test that SetpointTimeControl object is always on"""
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.timecontrol.is_on(),
                    [True, False, False, True, False, True, True, True][t_idx],
                    "incorrect is_on value returned for control with no min or max set",
                )
                self.assertEqual(
                    self.timecontrol_min.is_on(),
                    True,  # Should always be True for this type of control
                    "incorrect is_on value returned for control with min set",
                )
                self.assertEqual(
                    self.timecontrol_max.is_on(),
                    True,  # Should always be True for this type of control
                    "incorrect is_on value returned for control with max set",
                )
                self.assertEqual(
                    self.timecontrol_minmax.is_on(),
                    True,  # Should always be True for this type of control
                    "incorrect is_on value returned for control with min and max set",
                )
                self.assertEqual(
                    self.timecontrol_advstart.is_on(),
                    [True, False, True, True, True, True, True, True][t_idx],
                    "incorrect is_on value returned for control with advanced start",
                )
                self.assertEqual(
                    self.timecontrol_advstart_minmax.is_on(),
                    True,
                    "incorrect is_on value returned for control with advanced start",
                )

    def test_is_on_lookahead(self):
        """Test that is_on returns the correct value when looking ahead in the warmup period"""
        schedule = [None] * 24
        control = SetpointTimeControl(
            schedule=schedule,
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
            duration_advanced_start=30,
        )
        self.assertFalse(control.is_on())

        schedule = [20] * 24
        control = SetpointTimeControl(
            schedule=schedule, simulation_time=self.simtime, start_day=0, time_series_step=1
        )
        self.assertTrue(control.is_on())

    def test_setpnt(self):
        """Test that SetpointTimeControl object returns correct schedule"""
        results_min = [21.0, 16.0, 16.0, 21.0, 16.0, 21.0, 25.0, 16.0]
        results_max = [21.0, 24.0, 24.0, 21.0, 24.0, 21.0, 24.0, 15.0]
        results_minmax = [21.0, 16.0, 16.0, 21.0, 16.0, 21.0, 24.0, 16.0]
        results_advstart = [21.0, None, 21.0, 21.0, 21.0, 21.0, 25.0, 15.0]
        results_advstart_minmax = [21.0, 16.0, 21.0, 21.0, 21.0, 21.0, 24.0, 16.0]

        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.timecontrol.setpnt(),
                    self.schedule[t_idx],
                    "incorrect schedule returned for control with no min or max set",
                )
                self.assertEqual(
                    self.timecontrol_min.setpnt(),
                    results_min[t_idx],
                    "incorrect schedule returned for control with min set",
                )
                self.assertEqual(
                    self.timecontrol_max.setpnt(),
                    results_max[t_idx],
                    "incorrect schedule returned for control with max set",
                )
                self.assertEqual(
                    self.timecontrol_minmax.setpnt(),
                    results_minmax[t_idx],
                    "incorrect schedule returned for control with min and max set",
                )
                self.assertEqual(
                    self.timecontrol_advstart.setpnt(),
                    results_advstart[t_idx],
                    "incorrect schedule returned for control with advanced start",
                )
                self.assertEqual(
                    self.timecontrol_advstart_minmax.setpnt(),
                    results_advstart_minmax[t_idx],
                    "incorrect schedule returned for control with advanced start and min and max set",
                )

    def test_setpnt_lookahead(self):
        """Test that setpnt returns the correct values when looking ahead in the warmup period"""
        schedule = [None] * 24
        control = SetpointTimeControl(
            schedule=schedule,
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
            duration_advanced_start=30,
        )
        self.assertEqual(control.setpnt(), None)

        schedule = [20] * 24
        control = SetpointTimeControl(
            schedule=schedule,
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
            duration_advanced_start=30,
        )
        self.assertEqual(control.setpnt(), 20)

    def test_setpnt_minmax(self):
        """Test that setpnt returns the correct values with min and max set"""
        schedule = [None] * 24

        control = SetpointTimeControl(
            schedule=schedule,
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
            setpoint_min=10,
        )
        self.assertEqual(control.setpnt(), 10)

        with self.assertRaises(ValueError):
            control = SetpointTimeControl(
                schedule=schedule,
                simulation_time=self.simtime,
                start_day=0,
                time_series_step=1,
                setpoint_min=10,
                setpoint_max=20,
                duration_advanced_start=30,
            )
            self.assertEqual(control.setpnt(), 20)

        control = SetpointTimeControl(
            schedule=schedule,
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
            setpoint_min=10,
            setpoint_max=20,
            default_to_max=True,
            duration_advanced_start=30,
        )
        self.assertEqual(control.setpnt(), 20)

        control = SetpointTimeControl(
            schedule=schedule,
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
            setpoint_min=10,
            setpoint_max=20,
            default_to_max=False,
            duration_advanced_start=30,
        )
        self.assertEqual(control.setpnt(), 10)


class Test_SmartApplianceControl(unittest.TestCase):
    def setUp(self):
        self.simtime = SimulationTime(start_time=0, end_time=24, step=1)
        self.elec_battery = MagicMock()
        self.energy_supply = MagicMock()

        self.energy_supply.has_battery.return_value = True
        self.energy_supply.get_battery_max_discharge.return_value = 100
        self.energy_supply.get_battery_max_capacity.return_value = 100
        self.energy_supply.get_battery_available_charge.return_value = 0
        self.energy_supply.get_battery_charge_efficiency.return_value = 1
        self.energy_supply.get_battery_discharge_efficiency.return_value = 1

        power_timeseries = {"mains elec": [100.0] * 12}
        timeseries_step = 2
        non_appliance_demand_24hr = {"mains elec": [0.1, 0.2] * 6}
        battery_24hr = {"battery_state_of_charge": {"mains elec": [0.5] * 12}}
        energysupplies = {"mains elec": self.energy_supply}
        appliances = ["Clothes_drying"]

        self.smart_appliance_control = SmartApplianceControl(
            power_timeseries=power_timeseries,
            timeseries_step=timeseries_step,
            simulation_time=self.simtime,
            non_appliance_demand_24hr=non_appliance_demand_24hr,
            battery_24hr=battery_24hr,
            energysupplies=energysupplies,
            appliances=appliances,
        )

    def test_init_invalid_length(self):
        """Test that init throws if the power_timeseries length doesn't cover the simulation length"""
        power_timeseries = {"mains elec": [100.0] * 11}
        timeseries_step = 2
        non_appliance_demand_24hr = {"mains elec": [0.1] * 12}
        battery_24hr = {"battery_state_of_charge": {"mains elec": [0.0] * 12}}
        energysupplies = {"mains elec": self.energy_supply}
        appliances = ["Clothes_drying"]

        with self.assertRaises(ValueError):
            self.smart_appliance_control = SmartApplianceControl(
                power_timeseries=power_timeseries,
                timeseries_step=timeseries_step,
                simulation_time=self.simtime,
                non_appliance_demand_24hr=non_appliance_demand_24hr,
                battery_24hr=battery_24hr,
                energysupplies=energysupplies,
                appliances=appliances,
            )

    def test_ts_step(self):
        """Test that ts_step returns the correct values"""
        self.assertEqual(self.smart_appliance_control.ts_step(t_idx=0), 0)
        self.assertEqual(self.smart_appliance_control.ts_step(t_idx=23), 11)
        self.assertEqual(self.smart_appliance_control.ts_step(t_idx=24), 12)

    def test_add_appliance_demand(self):
        """Test that add_appliance_demand adds the correct demand"""
        self.smart_appliance_control.add_appliance_demand(
            t_idx=5, demand=100, energysupply="mains elec"
        )

        self.assertAlmostEqual(
            self.smart_appliance_control.get_demand(t_idx=5, energysupply="mains elec"), -9950.2
        )

    def test_update_demand_buffer(self):
        """Test that update_demand_buffer updates the demand"""
        for t_idx, _, _ in self.simtime:
            self.smart_appliance_control.update_demand_buffer(t_idx=t_idx)

            self.assertAlmostEqual(
                self.smart_appliance_control.get_demand(t_idx=t_idx, energysupply="mains elec"), 0.1
            )

    def test_get_demand(self):
        """Test that get_demand returns the correct values"""
        self.assertAlmostEqual(
            self.smart_appliance_control.get_demand(t_idx=0, energysupply="mains elec"), -0.3
        )
        self.assertAlmostEqual(
            self.smart_appliance_control.get_demand(t_idx=1, energysupply="mains elec"), -0.2
        )

    def test_get_demand_no_battery(self):
        """Test that get_demand returns the correct values with no battery"""
        self.energy_supply.has_battery.return_value = False

        power_timeseries = {"mains elec": [100.0] * 12}
        timeseries_step = 2
        non_appliance_demand_24hr = {"mains elec": [0.1, 0.2] * 12}
        battery_24hr = {"battery_state_of_charge": {}}
        energysupplies = {"mains elec": self.energy_supply}
        appliances = ["Clothes_drying"]

        self.smart_appliance_control = SmartApplianceControl(
            power_timeseries=power_timeseries,
            timeseries_step=timeseries_step,
            simulation_time=self.simtime,
            non_appliance_demand_24hr=non_appliance_demand_24hr,
            battery_24hr=battery_24hr,
            energysupplies=energysupplies,
            appliances=appliances,
        )

        self.assertAlmostEqual(
            self.smart_appliance_control.get_demand(t_idx=0, energysupply="mains elec"), 0.2
        )
        self.assertAlmostEqual(
            self.smart_appliance_control.get_demand(t_idx=1, energysupply="mains elec"), 0.3
        )


class Test_ChargeControl(unittest.TestCase):
    """Unit tests for ChargeControl class"""

    def setUp(self):
        """Create ChargeControl object to be tested"""
        self.simtime1 = SimulationTime(start_time=0, end_time=24, step=1)
        self.simtime2 = SimulationTime(start_time=0, end_time=24, step=1)
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
        proj_dict = {
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
        self.external_conditions1 = ExternalConditions(
            simulation_time=self.simtime1,
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
        self.external_conditions2 = ExternalConditions(
            simulation_time=self.simtime2,
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
        self.external_sensor = {
            "correlation": [
                {"temperature": 0.0, "max_charge": 1.0},
                {"temperature": 10.0, "max_charge": 0.9},
                {"temperature": 18.0, "max_charge": 0.0},
            ]
        }
        self.charge_control1 = ChargeControl(
            logic_type=ControlLogicType.AUTOMATIC,
            schedule=self.schedule,
            simulation_time=self.simtime1,
            start_day=0,
            time_series_step=1,
            charge_level=[1.0, 0.8],
            temp_charge_cut=15.5,
            temp_charge_cut_delta=None,
            extcond=self.external_conditions1,
            external_sensor=self.external_sensor,
        )
        self.charge_control2 = ChargeControl(
            logic_type=ControlLogicType.AUTOMATIC,
            schedule=self.schedule,
            simulation_time=self.simtime2,
            start_day=0,
            time_series_step=1,
            charge_level=[1.0, 0.8],
            temp_charge_cut=15.5,
            temp_charge_cut_delta=None,
            extcond=self.external_conditions2,
            external_sensor=self.external_sensor,
        )
        self.charge_control3 = ChargeControl(
            logic_type=ControlLogicType.MANUAL,
            schedule=self.schedule,
            simulation_time=self.simtime2,
            start_day=0,
            time_series_step=1,
            charge_level=[1.0, 0.8],
            temp_charge_cut=None,
            temp_charge_cut_delta=None,
            extcond=self.external_conditions2,
            external_sensor=self.external_sensor,
        )

    def test_init(self):
        """Test that energy_to_store is created for heat battery logic types"""
        chargeControl = ChargeControl(
            logic_type=ControlLogicType.MANUAL,
            schedule=self.schedule,
            simulation_time=self.simtime1,
            start_day=0,
            time_series_step=1,
            charge_level=[1.0, 0.8],
            temp_charge_cut=None,
            temp_charge_cut_delta=None,
            extcond=self.external_conditions1,
            external_sensor=self.external_sensor,
        )

        self.assertFalse(hasattr(chargeControl, "_ChargeControl__energy_to_store"))

        chargeControl = ChargeControl(
            logic_type=ControlLogicType.HEAT_BATTERY,
            schedule=self.schedule,
            simulation_time=self.simtime1,
            start_day=0,
            time_series_step=1,
            charge_level=[1.0, 0.8],
            temp_charge_cut=None,
            temp_charge_cut_delta=None,
            extcond=self.external_conditions1,
            external_sensor=self.external_sensor,
        )

        self.assertEqual(chargeControl._ChargeControl__energy_to_store, 0)  # type: ignore[private-attr]

    def test_init_missing_parameters(self):
        """Test that init raises for missing parameters"""
        # When temp_charge_cut is None
        for logic_type in [
            ControlLogicType.AUTOMATIC,
            ControlLogicType.CELECT,
            ControlLogicType.HHRSH,
            "invalid",
        ]:
            with self.subTest(logic_type=logic_type):
                with self.assertRaises(ValueError):
                    ChargeControl(
                        logic_type=logic_type,
                        schedule=self.schedule,
                        simulation_time=self.simtime1,
                        start_day=0,
                        time_series_step=1,
                        charge_level=[1.0, 0.8],
                        temp_charge_cut=None,
                        temp_charge_cut_delta=None,
                        extcond=self.external_conditions1,
                        external_sensor=self.external_sensor,
                    )

        # When external_conditions is None
        for logic_type in [ControlLogicType.HHRSH, ControlLogicType.HEAT_BATTERY]:
            with self.subTest(logic_type=logic_type):
                with self.assertRaises(ValueError):
                    ChargeControl(
                        logic_type=logic_type,
                        schedule=self.schedule,
                        simulation_time=self.simtime1,
                        start_day=0,
                        time_series_step=1,
                        charge_level=[1.0, 0.8],
                        temp_charge_cut=15.5,
                        temp_charge_cut_delta=None,
                        extcond=None,
                        external_sensor=self.external_sensor,
                    )

    def test_is_on(self):
        """Test that ChargeControl object returns correct schedule"""
        for t_idx, _, _ in self.simtime1:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.charge_control1.is_on(),
                    self.schedule[t_idx],
                    "incorrect schedule returned",
                )

    def test_logic_type(self):
        """Test that logic_type returns the correct value"""
        self.assertEqual(self.charge_control1.logic_type(), ControlLogicType.AUTOMATIC)

    def test_calculate_heating_degree_hours(self):
        """Test that calculate_heating_degree_hours returns the correct value"""
        self.assertEqual(
            self.charge_control1._ChargeControl__calculate_heating_degree_hours(  # type: ignore[private-attr]
                temps=[20, 21], base_temp=25
            ),
            9,
        )
        self.assertEqual(
            self.charge_control1._ChargeControl__calculate_heating_degree_hours(  # type: ignore[private-attr]
                temps=[20, 21], base_temp=15
            ),
            0,
        )
        self.assertEqual(
            self.charge_control1._ChargeControl__calculate_heating_degree_hours(  # type: ignore[private-attr]
                temps=[20, 21, None], base_temp=15
            ),
            None,
        )

    def test_target_charge_automatic(self):
        """Test that ChargeControl object returns correct schedule with an automatic logic type"""
        # Expected results for the unit test
        expected_target_charges_1 = [
            0.0,
            1.0,
            0.99,
            0.98,
            0.95,
            0.93,
            0.9400000000000001,
            0.675,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        ]
        expected_target_charges_2 = [
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        ]
        for t_idx, _, _ in self.simtime1:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.charge_control1.target_charge(temp_air=12.5),
                    expected_target_charges_1[t_idx],
                    "incorrect target charge returned",
                )

        for t_idx, _, _ in self.simtime2:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.charge_control2.target_charge(temp_air=19.5),
                    expected_target_charges_2[t_idx],
                    "incorrect target charge returned",
                )

    def test_target_charge_manual(self):
        """Test that ChargeControl object returns correct schedule with a manual logic type"""
        expected_target_charges = [
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

        self.charge_control1._ChargeControl__logic_type = ControlLogicType.MANUAL  # type: ignore[private-attr]

        for t_idx, _, _ in self.simtime1:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.charge_control1.target_charge(temp_air=12.5),
                    expected_target_charges[t_idx],
                    "incorrect target charge returned",
                )

    def test_target_charge_celect(self):
        """Test that ChargeControl object returns correct schedule with a celect logic type"""
        expected_target_charges = [
            0.0,
            1.0,
            0.99,
            0.98,
            0.95,
            0.93,
            0.9400000000000001,
            0.675,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        ]

        self.charge_control1._ChargeControl__logic_type = ControlLogicType.CELECT  # type: ignore[private-attr]

        for t_idx, _, _ in self.simtime1:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.charge_control1.target_charge(temp_air=12.5),
                    expected_target_charges[t_idx],
                    "incorrect target charge returned",
                )

    def test_target_charge_automatic_no_sensor(self):
        """Test that ChargeControl object returns correct schedule with an automatic logic type and no sensor"""
        expected_target_charges = [
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

        self.charge_control1._ChargeControl__external_sensor = None  # type: ignore[private-attr]

        self.charge_control1._ChargeControl__logic_type = ControlLogicType.AUTOMATIC  # type: ignore[private-attr]

        for t_idx, _, _ in self.simtime1:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.charge_control1.target_charge(temp_air=12.5),
                    expected_target_charges[t_idx],
                    "incorrect target charge returned",
                )

    def test_target_charge_celect_no_sensor(self):
        """Test that ChargeControl object returns correct schedule with a celect logic type and no sensor"""
        expected_target_charges = [
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

        self.charge_control1._ChargeControl__external_sensor = None  # type: ignore[private-attr]

        self.charge_control1._ChargeControl__logic_type = ControlLogicType.CELECT  # type: ignore[private-attr]

        for t_idx, _, _ in self.simtime1:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.charge_control1.target_charge(temp_air=12.5),
                    expected_target_charges[t_idx],
                    "incorrect target charge returned",
                )

    def test_target_charge_hhrsh(self):
        """Test that ChargeControl object returns correct schedule with a HHRSH logic type"""
        expected_target_charges = [
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

        self.charge_control1._ChargeControl__logic_type = ControlLogicType.HHRSH  # type: ignore[private-attr]

        for t_idx, _, _ in self.simtime1:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.charge_control1.target_charge(temp_air=12.5),
                    expected_target_charges[t_idx],
                    "incorrect target charge returned",
                )

    def test_temp_charge_cut_corr(self):
        """Check correction of nominal/json temp_charge_cut with monthly table.
        This function will most likely be superseded when the Electric Storage methodology
        is upgraded to consider more realistic manufacturers' controls and corresponding
        unit_test will be deprecated."""

        result = self.charge_control1.temp_charge_cut_corr()
        self.assertEqual(result, 15.5)
        self.assertEqual(self.charge_control3.temp_charge_cut_corr(), None)

    def test_temp_charge_cut_corr_temp_charge_cut_delta(self):
        """Test that temp_charge_cut_delta returns the correct values with a temp_charge_cut_delta"""
        self.charge_control1._ChargeControl__temp_charge_cut_delta = [i for i in range(24)]  # type: ignore[private-attr]
        for t_idx, _, _ in self.simtime1:
            with self.subTest(i=t_idx):
                result = self.charge_control1.temp_charge_cut_corr()
                assert result is not None, (
                    "temp_charge_cut_corr should return a value when temp_charge_cut is set"
                )
                self.assertAlmostEqual(result, 15.5 + t_idx)

    def test_temp_charge_cut_delta_length(self):
        """Test it raises an error if temp_charge_cut_delta does not provide enough values for the simulation"""
        with self.assertRaises(ValueError):
            ChargeControl(
                logic_type=ControlLogicType.AUTOMATIC,
                schedule=self.schedule,
                simulation_time=self.simtime1,
                start_day=0,
                time_series_step=1,
                charge_level=[1.0, 0.8],
                temp_charge_cut=15.5,
                temp_charge_cut_delta=[0.0, 0.0],
                extcond=None,
                external_sensor=self.external_sensor,
            )

    def test_energy_to_store(self):
        """Test that energy_to_store returns the correct values"""
        simtime = SimulationTime(start_time=0, end_time=48, step=1)
        charge_control = ChargeControl(
            logic_type=ControlLogicType.HHRSH,
            schedule=self.schedule + [True] * 24,
            simulation_time=simtime,
            start_day=0,
            time_series_step=1,
            charge_level=[1.0, 0.8],
            temp_charge_cut=15.5,
            temp_charge_cut_delta=None,
            extcond=self.external_conditions1,
            external_sensor=self.external_sensor,
        )

        expected = [None] * 8 + [0.0] * 8 + [None] * 4 + [0.0] * 4 + [2400.0] * 24

        for t_idx, _, _ in simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    charge_control.energy_to_store(energy_demand=100, base_temp=70), expected[t_idx]
                )

    def test_energy_to_store_no_energy(self):
        """Test that energy_to_store returns the correct values when there's no energy to store"""
        simtime = SimulationTime(0, 48, 1)
        charge_control = ChargeControl(
            logic_type=ControlLogicType.HHRSH,
            schedule=self.schedule + [True] * 24,
            simulation_time=simtime,
            start_day=0,
            time_series_step=1,
            charge_level=[1.0, 0.8],
            temp_charge_cut=15.5,
            temp_charge_cut_delta=None,
            extcond=self.external_conditions1,
            external_sensor=self.external_sensor,
        )

        charge_control._ChargeControl__past_ext_temp = [19] * 24  # type: ignore[private-attr]

        for t_idx, _, _ in simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    charge_control.energy_to_store(energy_demand=100, base_temp=19), 0.0
                )

    def test_get_limit_factor_invalid(self):
        """Test that get_limit_factor throws if there are invalid values"""
        with self.assertRaises(RuntimeError):
            self.charge_control1._ChargeControl__get_limit_factor(float("NaN"))  # type: ignore[private-attr]


class TestCombinationTimeControl(unittest.TestCase):
    def setUp(self):
        # Define mock controls based on JSON configuration
        self.simtime = SimulationTime(start_time=0, end_time=8, step=1)
        self.start_day = 0
        self.time_series_step = 1

        self.simtime_cost = SimulationTime(start_time=0, end_time=24, step=1)
        self.cost_schedule = [5.0] * 12 + [10.0] * 6 + [5.0] * 6
        self.cost_minimising_ctrl = OnOffCostMinimisingTimeControl(
            schedule=self.cost_schedule,
            simulation_time=self.simtime,
            start_day=0,  # Start day
            time_series_step=1.0,  # Schedule data is hourly
            time_on_daily=5.0,  # Need 12 "on" hours
        )
        self.controls = {
            "ctrl1": OnOffTimeControl(
                schedule=[True, True, False, True, True, True, True, True],
                simulation_time=self.simtime,
                start_day=0,
                time_series_step=1,
            ),
            "ctrl2": OnOffTimeControl(
                schedule=[False, True, True, False, False, False, True, False],
                simulation_time=self.simtime,
                start_day=0,
                time_series_step=1,
            ),
            "ctrl3": OnOffTimeControl(
                schedule=[True, False, True, False, False, False, True, False],
                simulation_time=self.simtime,
                start_day=0,
                time_series_step=1,
            ),
            "ctrl4": SetpointTimeControl(
                schedule=[45.0, 47.0, 50.0, 48.0, 48.0, 48.0, 48.0, 48.0],
                simulation_time=self.simtime,
                start_day=0,
                time_series_step=1,
            ),
            "ctrl5": SetpointTimeControl(
                schedule=[52.0, 52.0, 52.0, 52.0, 52.0, 52.0, 52.0, 52.0],
                simulation_time=self.simtime,
                start_day=0,
                time_series_step=1,
            ),
            "ctrl6": OnOffTimeControl(
                schedule=[True, True, False, True, True, True, True, True],
                simulation_time=self.simtime,
                start_day=0,
                time_series_step=1,
            ),
            "ctrl7": OnOffTimeControl(
                schedule=[False, True, False, False, False, False, True, False],
                simulation_time=self.simtime,
                start_day=0,
                time_series_step=1,
            ),
            "ctrl8": OnOffTimeControl(
                schedule=[True, False, False, True, True, True, True, True],
                simulation_time=self.simtime,
                start_day=0,
                time_series_step=1,
            ),
            "ctrl9": SetpointTimeControl(
                schedule=[45.0, None, 50.0, 48.0, 48.0, None, 48.0, 48.0],
                simulation_time=self.simtime,
                start_day=0,
                time_series_step=1,
            ),
            "ctrl10": self.cost_minimising_ctrl,
        }

        self.combination_on_off = {
            "main": {"operation": "AND", "controls": ["ctrl1", "ctrl2", "comb1", "comb2"]},
            "comb1": {"operation": "OR", "controls": ["ctrl3", "comb3"]},
            "comb2": {"operation": "MAX", "controls": ["ctrl4", "ctrl5"]},
            "comb3": {"operation": "XOR", "controls": ["ctrl6", "ctrl7", "ctrl8"]},
        }

        self.combination_control_on_off = CombinationTimeControl(
            combination=self.combination_on_off,
            controls=self.controls,
            simulation_time=self.simtime,
        )

        self.combination_setpnt = {
            "main": {"operation": "AND", "controls": ["ctrl1", "ctrl2", "comb1"]},
            "comb1": {"operation": "MAX", "controls": ["ctrl4", "ctrl5"]},
        }

        self.combination_control_setpnt = CombinationTimeControl(
            combination=self.combination_setpnt,
            controls=self.controls,
            simulation_time=self.simtime,
        )

        self.combination_req = {
            "main": {"operation": "AND", "controls": ["ctrl9", "comb1"]},
            "comb1": {"operation": "AND", "controls": ["ctrl4", "ctrl1"]},
        }

        self.combination_control_req = CombinationTimeControl(
            combination=self.combination_req,
            controls=self.controls,
            simulation_time=self.simtime,
        )

        self.combination_on_off_cost = {
            "main": {"operation": "AND", "controls": ["ctrl1", "ctrl2", "comb1"]},
            "comb1": {"operation": "OR", "controls": ["ctrl3", "ctrl10"]},
        }

        self.combination_control_on_off_cost = CombinationTimeControl(
            combination=self.combination_on_off_cost,
            controls=self.controls,
            simulation_time=self.simtime,
        )

        # Setup for ChargeControl test

        self.simtime1 = SimulationTime(start_time=0, end_time=24, step=1)
        self.schedule = [
            True,
            True,
            True,
            True,
            True,
            True,
            False,
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
        proj_dict = {
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
            simulation_time=self.simtime1,
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

        self.external_sensor = {
            "correlation": [
                {"temperature": 0.0, "max_charge": 1.0},
                {"temperature": 10.0, "max_charge": 0.9},
                {"temperature": 18.0, "max_charge": 0.0},
            ]
        }
        self.charge_control = ChargeControl(
            logic_type=ControlLogicType.AUTOMATIC,
            schedule=self.schedule,
            simulation_time=self.simtime1,
            start_day=0,
            time_series_step=1,
            charge_level=[1.0, 0.8],
            temp_charge_cut=15.5,
            temp_charge_cut_delta=None,
            extcond=self.external_conditions,
            external_sensor=self.external_sensor,
        )

        self.controls1 = {
            "ctrl11": OnOffTimeControl(
                schedule=[True, False, False, True, True, True, True, True],
                simulation_time=self.simtime,
                start_day=0,
                time_series_step=1,
            ),
            "ctrl12": self.charge_control,
            "ctrl13": OnOffTimeControl(
                schedule=[True, True, False, False, True, False, True, True],
                simulation_time=self.simtime,
                start_day=0,
                time_series_step=1,
            ),
        }

        self.combination_target_charge = {
            "main": {"operation": "AND", "controls": ["ctrl11", "ctrl12"]}
        }
        self.combination_target_charge1 = {
            "main": {"operation": "AND", "controls": ["ctrl11", "ctrl13"]}
        }

        self.combination_control_target_charge = CombinationTimeControl(
            combination=self.combination_target_charge,
            controls=self.controls1,
            simulation_time=self.simtime,
        )

        self.combination_control_target_charge1 = CombinationTimeControl(
            combination=self.combination_target_charge1,
            controls=self.controls1,
            simulation_time=self.simtime,
        )

    def test_evaluate_boolean_operation_is_on(self):
        """Test that evaluate_boolean_operation_is_on returns the correct values"""
        self.assertFalse(
            self.combination_control_target_charge._CombinationTimeControl__evaluate_boolean_operation_is_on(  # type: ignore[private-attr]
                operation=ControlCombinationOperation.AND_,
                control_results=[False, False],
            )
        )
        self.assertFalse(
            self.combination_control_target_charge._CombinationTimeControl__evaluate_boolean_operation_is_on(  # type: ignore[private-attr]
                operation=ControlCombinationOperation.AND_,
                control_results=[True, False],
            )
        )
        self.assertFalse(
            self.combination_control_target_charge._CombinationTimeControl__evaluate_boolean_operation_is_on(  # type: ignore[private-attr]
                operation=ControlCombinationOperation.AND_,
                control_results=[False, True],
            )
        )
        self.assertTrue(
            self.combination_control_target_charge._CombinationTimeControl__evaluate_boolean_operation_is_on(  # type: ignore[private-attr]
                operation=ControlCombinationOperation.AND_,
                control_results=[True, True],
            )
        )

        self.assertFalse(
            self.combination_control_target_charge._CombinationTimeControl__evaluate_boolean_operation_is_on(  # type: ignore[private-attr]
                operation=ControlCombinationOperation.OR_,
                control_results=[False, False],
            )
        )
        self.assertTrue(
            self.combination_control_target_charge._CombinationTimeControl__evaluate_boolean_operation_is_on(  # type: ignore[private-attr]
                operation=ControlCombinationOperation.OR_,
                control_results=[False, True],
            )
        )
        self.assertTrue(
            self.combination_control_target_charge._CombinationTimeControl__evaluate_boolean_operation_is_on(  # type: ignore[private-attr]
                operation=ControlCombinationOperation.OR_,
                control_results=[True, False],
            )
        )
        self.assertTrue(
            self.combination_control_target_charge._CombinationTimeControl__evaluate_boolean_operation_is_on(  # type: ignore[private-attr]
                operation=ControlCombinationOperation.OR_,
                control_results=[True, True],
            )
        )

        self.assertFalse(
            self.combination_control_target_charge._CombinationTimeControl__evaluate_boolean_operation_is_on(  # type: ignore[private-attr]
                operation=ControlCombinationOperation.XOR,
                control_results=[False, False],
            )
        )
        self.assertTrue(
            self.combination_control_target_charge._CombinationTimeControl__evaluate_boolean_operation_is_on(  # type: ignore[private-attr]
                operation=ControlCombinationOperation.XOR,
                control_results=[False, True],
            )
        )
        self.assertTrue(
            self.combination_control_target_charge._CombinationTimeControl__evaluate_boolean_operation_is_on(  # type: ignore[private-attr]
                operation=ControlCombinationOperation.XOR,
                control_results=[True, False],
            )
        )
        self.assertFalse(
            self.combination_control_target_charge._CombinationTimeControl__evaluate_boolean_operation_is_on(  # type: ignore[private-attr]
                operation=ControlCombinationOperation.XOR,
                control_results=[True, True],
            )
        )

        self.assertFalse(
            self.combination_control_target_charge._CombinationTimeControl__evaluate_boolean_operation_is_on(  # type: ignore[private-attr]
                operation=ControlCombinationOperation.NOT_,
                control_results=[True],
            )
        )
        self.assertTrue(
            self.combination_control_target_charge._CombinationTimeControl__evaluate_boolean_operation_is_on(  # type: ignore[private-attr]
                operation=ControlCombinationOperation.NOT_,
                control_results=[False],
            )
        )

    def test_evaluate_boolean_operation_is_on_invalid(self):
        """Test that evaluate_boolean_operation_is_on throws on invalid input"""
        with self.assertRaises(ValueError):
            self.combination_control_target_charge._CombinationTimeControl__evaluate_boolean_operation_is_on(  # type: ignore[private-attr]
                operation=ControlCombinationOperation.NOT_,
                control_results=[True, True],
            )

        with self.assertRaises(ValueError):
            self.combination_control_target_charge._CombinationTimeControl__evaluate_boolean_operation_is_on(  # type: ignore[private-attr]
                operation=ControlCombinationOperation.MAX,
                control_results=[True],
            )

        with self.assertRaises(ValueError):
            self.combination_control_target_charge._CombinationTimeControl__evaluate_boolean_operation_is_on(  # type: ignore[private-attr]
                operation=ControlCombinationOperation.MIN,
                control_results=[True],
            )

    def test_evaluate_control_in_req_period_invalid(self):
        """Test that evaluate_control_in_req_period throws on an invalid control type"""

        self.controls1 = {"ctrl11": ""}

        self.combination_control_target_charge = CombinationTimeControl(
            combination=self.combination_target_charge,
            controls=self.controls1,  # type: ignore[assignment] # Invalid control type to test error handling
            simulation_time=self.simtime,
        )

        with self.assertRaises(ValueError):
            self.combination_control_target_charge._CombinationTimeControl__evaluate_control_in_req_period(  # type: ignore[private-attr]
                control_name="ctrl11"
            )

    def test_evaluate_control_setpnt(self):
        """Test that evaluate_control_setpnt throws on an invalid control type"""
        self.controls1 = {"ctrl11": ""}

        self.combination_control_target_charge = CombinationTimeControl(
            combination=self.combination_target_charge,
            controls=self.controls1,  # type: ignore[assignment] # Invalid control type to test error handling
            simulation_time=self.simtime,
        )

        with self.assertRaises(ValueError):
            self.combination_control_target_charge._CombinationTimeControl__evaluate_control_setpnt(  # type: ignore[private-attr]
                control_name="ctrl11"
            )

    def test_evaluate_combination_target_charge(self):
        """Test that evaluate_combination_target_charge returns the correct value"""

        charge_control = MagicMock(spec=ChargeControl)
        charge_control.target_charge.return_value = 2

        self.controls1 = {
            "ctrl1": OnOffTimeControl(
                schedule=[True, False, False, True, True, True, True, True],
                simulation_time=self.simtime,
                start_day=0,
                time_series_step=1,
            ),
            "ctrl2": OnOffTimeControl(
                schedule=[True, True, False, False, True, False, True, True],
                simulation_time=self.simtime,
                start_day=0,
                time_series_step=1,
            ),
            "ctrl3": charge_control,
            "ctrl4": charge_control,
        }

        self.combination_target_charge = {
            "main": {"operation": "AND", "controls": ["main2", "ctrl2"]},
            "main2": {"operation": "AND", "controls": ["ctrl1", "ctrl4"]},
        }

        self.combination_control_target_charge = CombinationTimeControl(
            combination=self.combination_target_charge,
            controls=self.controls1,
            simulation_time=self.simtime,
        )

        self.assertEqual(
            self.combination_control_target_charge._CombinationTimeControl__evaluate_combination_target_charge(  # type: ignore[private-attr]
                combination_name="main",
                temp_air=20,
            ),
            2,
        )

    def test_evaluate_combination_target_charge_more_charge_control(self):
        """Test that evaluate_combination_target_charge throws if there are too many ChargeControl objects"""

        charge_control = MagicMock(spec=ChargeControl)
        charge_control.target_charge.return_value = 2

        self.controls1 = {
            "ctrl1": OnOffTimeControl(
                schedule=[True, False, False, True, True, True, True, True],
                simulation_time=self.simtime,
                start_day=0,
                time_series_step=1,
            ),
            "ctrl2": OnOffTimeControl(
                schedule=[True, True, False, False, True, False, True, True],
                simulation_time=self.simtime,
                start_day=0,
                time_series_step=1,
            ),
            "ctrl3": charge_control,
            "ctrl4": charge_control,
        }

        self.combination_target_charge = {
            "main": {"operation": "AND", "controls": ["main2", "ctrl2"]},
            "main2": {"operation": "AND", "controls": ["ctrl3", "ctrl4"]},
        }

        self.combination_control_target_charge = CombinationTimeControl(
            combination=self.combination_target_charge,
            controls=self.controls1,
            simulation_time=self.simtime,
        )

        with self.assertRaises(ValueError):
            self.combination_control_target_charge._CombinationTimeControl__evaluate_combination_target_charge(  # type: ignore[private-attr]
                combination_name="main",
                temp_air=20,
            )

    def test_evaluate_combination_in_req_period(self):
        """Test that evaluate_combination_in_req_period returns the correct values"""
        self.combination_control_req._CombinationTimeControl__combination = {  # type: ignore[private-attr]
            "main": {"operation": "AND", "controls": ["ctrl4", "ctrl9"]},
        }

        self.simtime.reset()
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.combination_control_req._CombinationTimeControl__evaluate_combination_in_req_period(  # type: ignore[private-attr]
                        combination_name="main"
                    ),
                    [True, False, True, True, True, False, True, True][t_idx],
                )

        self.combination_control_req._CombinationTimeControl__combination = {  # type: ignore[private-attr]
            "main": {"operation": "OR", "controls": ["ctrl4", "ctrl9"]},
        }

        self.simtime.reset()
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.combination_control_req._CombinationTimeControl__evaluate_combination_in_req_period(  # type: ignore[private-attr]
                        combination_name="main"
                    ),
                    [True, True, True, True, True, True, True, True][t_idx],
                )

        self.combination_control_req._CombinationTimeControl__combination = {  # type: ignore[private-attr]
            "main": {"operation": "XOR", "controls": ["ctrl4", "ctrl9"]},
        }

        self.simtime.reset()
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.combination_control_req._CombinationTimeControl__evaluate_combination_in_req_period(  # type: ignore[private-attr]
                        combination_name="main"
                    ),
                    [False, True, False, False, False, True, False, False][t_idx],
                )

        self.combination_control_req._CombinationTimeControl__combination = {  # type: ignore[private-attr]
            "main": {"operation": "MAX", "controls": ["ctrl4", "ctrl9"]},
        }

        self.simtime.reset()
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.combination_control_req._CombinationTimeControl__evaluate_combination_in_req_period(  # type: ignore[private-attr]
                        combination_name="main"
                    ),
                    [True, True, True, True, True, True, True, True][t_idx],
                )

        self.combination_control_req._CombinationTimeControl__combination = {  # type: ignore[private-attr]
            "main": {"operation": "MIN", "controls": ["ctrl4", "ctrl9"]},
        }

        self.simtime.reset()
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.combination_control_req._CombinationTimeControl__evaluate_combination_in_req_period(  # type: ignore[private-attr]
                        combination_name="main"
                    ),
                    [True, True, True, True, True, True, True, True][t_idx],
                )

        self.combination_control_req._CombinationTimeControl__combination = {  # type: ignore[private-attr]
            "main": {"operation": "MEAN", "controls": ["ctrl4", "ctrl9"]},
        }

        self.simtime.reset()
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.combination_control_req._CombinationTimeControl__evaluate_combination_in_req_period(  # type: ignore[private-attr]
                        combination_name="main"
                    ),
                    [True, True, True, True, True, True, True, True][t_idx],
                )

        self.combination_control_req._CombinationTimeControl__combination = {  # type: ignore[private-attr]
            "main": {"operation": "AND", "controls": []},
        }

        with self.assertRaises(ValueError):
            self.combination_control_req._CombinationTimeControl__evaluate_combination_in_req_period(  # type: ignore[private-attr]
                "main"
            )

    def test_evaluate_combination_in_req_period_invalid(self):
        """Test that evaluate_combination_in_req_period throws on invalid control combinations"""

        # OnOff + Setpoint combination in_req_perdioc() only supports the AND operation

        self.combination_control_req._CombinationTimeControl__combination = {  # type: ignore[private-attr]
            "main": {"operation": "OR", "controls": ["ctrl9", "comb1"]},
            "comb1": {"operation": "OR", "controls": ["ctrl4", "ctrl1"]},
        }

        with self.assertRaises(ValueError):
            self.combination_control_req._CombinationTimeControl__evaluate_combination_in_req_period(  # type: ignore[private-attr]
                combination_name="main"
            )

        # OnOff + OnOff combination is not applicable for in_req_period() operation

        self.combination_control_req._CombinationTimeControl__combination = {  # type: ignore[private-attr]
            "main": {"operation": "OR", "controls": ["ctrl2", "ctrl1"]},
        }

        with self.assertRaises(ValueError):
            self.combination_control_req._CombinationTimeControl__evaluate_combination_in_req_period(  # type: ignore[private-attr]
                combination_name="main"
            )

        self.combination_control_req._CombinationTimeControl__combination = {  # type: ignore[private-attr]
            "main": {"operation": "AND", "controls": []},
        }

        with self.assertRaises(ValueError):
            self.combination_control_req._CombinationTimeControl__evaluate_combination_in_req_period(  # type: ignore[private-attr]
                "main"
            )

    def test_evaluate_combination_setpnt(self):
        """Test that evaluate_combination_setpnt returns the correct values"""
        self.combination_control_req._CombinationTimeControl__combination = {  # type: ignore[private-attr]
            "main": {"operation": "MIN", "controls": ["ctrl4", "ctrl5"]},
        }

        self.simtime.reset()
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.combination_control_req._CombinationTimeControl__evaluate_combination_setpnt(  # type: ignore[private-attr]
                        combination_name="main"
                    ),
                    [45.0, 47.0, 50.0, 48.0, 48.0, 48.0, 48.0, 48.0][t_idx],
                )

        self.combination_control_req._CombinationTimeControl__combination = {  # type: ignore[private-attr]
            "main": {"operation": "MAX", "controls": ["ctrl4", "ctrl5"]},
        }

        self.simtime.reset()
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.combination_control_req._CombinationTimeControl__evaluate_combination_setpnt(  # type: ignore[private-attr]
                        combination_name="main"
                    ),
                    [52.0, 52.0, 52.0, 52.0, 52.0, 52.0, 52.0, 52.0][t_idx],
                )

        self.combination_control_req._CombinationTimeControl__combination = {  # type: ignore[private-attr]
            "main": {"operation": "MEAN", "controls": ["ctrl4", "ctrl5"]},
        }

        self.simtime.reset()
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.combination_control_req._CombinationTimeControl__evaluate_combination_setpnt(  # type: ignore[private-attr]
                        combination_name="main"
                    ),
                    [True, True, True, True, True, True, True, True][t_idx],
                )

        self.combination_control_req._CombinationTimeControl__combination = {  # type: ignore[private-attr]
            "main": {"operation": "AND", "controls": []},
        }

        with self.assertRaises(ValueError):
            self.combination_control_req._CombinationTimeControl__evaluate_combination_setpnt(  # type: ignore[private-attr]
                "main"
            )

    def test_evaluate_combination_setpnt_invalid(self):
        """Test that evaluate_combination_setpnt throws on invalid values"""

        # Only one numerical value allowed in AND operation

        self.combination_control_req._CombinationTimeControl__combination = {  # type: ignore[private-attr]
            "main": {"operation": "AND", "controls": ["ctrl1", "ctrl2"]}
        }

        self.combination_control_req._CombinationTimeControl__controls = {  # type: ignore[private-attr]
            "ctrl1": OnOffTimeControl(
                schedule=[1.0, False, True, True, True, True, True, True],  # type: ignore[type-arg] # Test error handling
                simulation_time=self.simtime,
                start_day=0,
                time_series_step=1,
            ),
            "ctrl2": OnOffTimeControl(
                schedule=[3.0, True, False, False, True, False, True, True, True],  # type: ignore[type-arg] # Test error handling
                simulation_time=self.simtime,
                start_day=0,
                time_series_step=1,
            ),
        }

        with self.assertRaises(ValueError):
            self.combination_control_req._CombinationTimeControl__evaluate_combination_setpnt(  # type: ignore[private-attr]
                combination_name="main"
            )

        # OnOff + Setpoint combination setpnt() only supports the AND operation

        self.combination_control_req._CombinationTimeControl__combination = {  # type: ignore[private-attr]
            "main": {"operation": "OR", "controls": ["ctrl1", "ctrl2"]}
        }

        self.combination_control_req._CombinationTimeControl__controls = {  # type: ignore[private-attr]
            "ctrl1": OnOffTimeControl(
                schedule=[20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0],  # type: ignore[type-arg] # Test error handling
                simulation_time=self.simtime,
                start_day=0,
                time_series_step=1,
            ),
            "ctrl2": OnOffTimeControl(
                schedule=[True] * 8, simulation_time=self.simtime, start_day=0, time_series_step=1
            ),
        }

        with self.assertRaises(ValueError):
            self.combination_control_req._CombinationTimeControl__evaluate_combination_setpnt(  # type: ignore[private-attr]
                combination_name="main"
            )

        # Unsupported operation: SupportedOperation.AND

        self.combination_control_req._CombinationTimeControl__combination = {  # type: ignore[private-attr]
            "main": {"operation": "AND", "controls": ["ctrl1", "ctrl2"]}
        }

        self.combination_control_req._CombinationTimeControl__controls = {  # type: ignore[private-attr]
            "ctrl1": SetpointTimeControl(
                schedule=[45.0, 47.0, 50.0, 48.0, 48.0, 48.0, 48.0, 48.0],
                simulation_time=self.simtime,
                start_day=0,
                time_series_step=1,
            ),
            "ctrl2": SetpointTimeControl(
                schedule=[45.0, 47.0, 50.0, 48.0, 48.0, 48.0, 48.0, 48.0],
                simulation_time=self.simtime,
                start_day=0,
                time_series_step=1,
            ),
        }

        with self.assertRaises(ValueError):
            self.combination_control_req._CombinationTimeControl__evaluate_combination_setpnt(  # type: ignore[private-attr]
                combination_name="main"
            )

        # OnOff + OnOff combination is not applicable for setpnt() operation

        self.combination_control_req._CombinationTimeControl__combination = {  # type: ignore[private-attr]
            "main": {"operation": "OR", "controls": ["ctrl1", "ctrl2"]}
        }

        self.combination_control_req._CombinationTimeControl__controls = {  # type: ignore[private-attr]
            "ctrl1": OnOffTimeControl(
                schedule=[False, False, False, True, True, True, True, True],
                simulation_time=self.simtime,
                start_day=0,
                time_series_step=1,
            ),
            "ctrl2": OnOffTimeControl(
                schedule=[False, True, False, False, True, False, True, True],
                simulation_time=self.simtime,
                start_day=0,
                time_series_step=1,
            ),
        }

        with self.assertRaises(ValueError):
            self.combination_control_req._CombinationTimeControl__evaluate_combination_setpnt(  # type: ignore[private-attr]
                combination_name="main"
            )

    def test_is_on(self):
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.combination_control_on_off.is_on(),
                    [False, False, False, False, False, False, True, False][t_idx],
                )

    def test_setpnt(self):
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.combination_control_setpnt.setpnt(),
                    [None, 52.0, None, None, None, None, 52.0, None][t_idx],
                )

    def test_in_required_period(self):
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.combination_control_req.in_required_period(),
                    [True, False, False, True, True, False, True, True][t_idx],
                )

    def test_is_on_cost(self):
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.combination_control_on_off_cost.is_on(),
                    [False, True, False, False, False, False, True, False][t_idx],
                )

    def test_target_charge(self):
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.combination_control_target_charge.target_charge(temp_air=None),
                    [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0][t_idx],
                )

        with self.assertRaises(ValueError):
            self.combination_control_target_charge1.target_charge(temp_air=None)

    def test_max_min_mean_operations_logic(self):
        """Test that MAX, MIN, MEAN operations use OR logic for is_on()"""
        simtime_short = SimulationTime(start_time=0, end_time=4, step=1)

        controls = {
            "ctrl_a": OnOffTimeControl(
                schedule=[False, False, True, True],
                simulation_time=simtime_short,
                start_day=0,
                time_series_step=1,
            ),
            "ctrl_b": OnOffTimeControl(
                schedule=[False, False, False, True],
                simulation_time=simtime_short,
                start_day=0,
                time_series_step=1,
            ),
            "ctrl_c": SetpointTimeControl(
                schedule=[None, 20.0, None, None],
                simulation_time=simtime_short,
                start_day=0,
                time_series_step=1,
            ),
        }

        for operation in ["MAX", "MIN", "MEAN"]:
            combination = {
                "main": {"operation": operation, "controls": ["ctrl_a", "ctrl_b", "ctrl_c"]}
            }

            combination_control = CombinationTimeControl(
                combination=combination,
                controls=controls,
                simulation_time=simtime_short,
            )

            expected_results = [False, True, True, True]

            for t_idx, _, _ in simtime_short:
                result = combination_control.is_on()
                assert result == expected_results[t_idx]
