#!/usr/bin/env python3

"""
This module contains unit tests for the boiler module
"""

# Standard library imports
import unittest
from unittest.mock import MagicMock

# Local imports
from hem_core.controls.time_control import SetpointTimeControl
from hem_core.energy_supply.energy_supply import EnergySupply
from hem_core.external_conditions import ExternalConditions
from hem_core.heating_systems.boiler import (
    Boiler,
    BoilerService,
    BoilerServiceSpace,
    BoilerServiceWaterCombi,
    BoilerServiceWaterRegular,
)
from hem_core.heating_systems.enums import HeatingServiceType
from hem_core.input_output.enums import (
    BoilerHotWaterTest,
    FuelType,
    HeatSourceLocation,
)
from hem_core.simulation_time import SimulationTime
from hem_core.water_heat_demand.cold_water_source import ColdWaterSource
from hem_core.water_heat_demand.dhw_demand import WaterEventResult


class TestBoilerService(unittest.TestCase):
    def setUp(self):
        self.control = MagicMock()
        self.boiler = BoilerService(None, "servoce_name", self.control)

    def test_is_on_with_control_on(self):
        self.control.is_on.return_value = True
        self.assertTrue(self.boiler.is_on())

    def test_is_on_with_control_off(self):
        self.control.is_on.return_value = False
        self.assertFalse(self.boiler.is_on())

    def test_is_on_with_no_control(self):
        self.boiler = BoilerService(None, "servoce_name", None)
        self.assertTrue(self.boiler.is_on())


class TestBoilerServiceWaterCombi(unittest.TestCase):
    """Unit tests for Boiler class"""

    def setUp(self):
        """Create Boiler object to be tested"""
        boiler_dict = {
            "type": "Boiler",
            "rated_power": 16.85,
            "EnergySupply": "mains_gas",
            "efficiency_full_load": 0.868,
            "efficiency_part_load": 0.952,
            "boiler_location": HeatSourceLocation.INTERNAL,
            "modulation_load": 1,
            "electricity_circ_pump": 0.0600,
            "electricity_part_load": 0.0131,
            "electricity_full_load": 0.0388,
            "electricity_standby": 0.0244,
        }

        boilerservicewatercombi_dict = {
            "separate_DHW_tests": "M&L",
            "fuel_energy_1": 7.099,
            "rejected_energy_1": 0.0004,
            "storage_loss_factor_1": 0.98328,
            "fuel_energy_2": 13.078,
            "rejected_energy_2": 0.0004,
            "storage_loss_factor_2": 0.91574,
            "rejected_factor_3": 0,
            "daily_HW_usage": 132.5802,
        }
        self.simtime = SimulationTime(start_time=0, end_time=2, step=1)
        self.energysupply = EnergySupply(fuel_type=FuelType.MAINS_GAS, simulation_time=self.simtime)
        self.usage_events_all_timesteps = [
            [
                WaterEventResult(
                    type="Other",
                    temperature_warm=60.0,
                    volume_warm=34.93868988826640,
                    volume_hot=34.93868988826640,
                    event_duration=5.0,
                ),
                WaterEventResult(
                    type="Other",
                    temperature_warm=60.0,
                    volume_warm=75.65325966014560,
                    volume_hot=75.65325966014560,
                    event_duration=15.0,
                ),
                WaterEventResult(
                    type="Other",
                    temperature_warm=60.0,
                    volume_warm=0.0,
                    volume_hot=0.0,
                    event_duration=0.0,
                ),
            ],
            [
                WaterEventResult(
                    type="Other",
                    temperature_warm=60.0,
                    volume_warm=32.60190808710678,
                    volume_hot=32.60190808710678,
                    event_duration=5.0,
                ),
            ],
        ]
        self.temp_return_feed = [51.05, 60.00]

        self.windspeed = [3.7, 3.8, 3.9, 4.0, 4.1, 4.2, 4.3, 4.4]
        self.wind_direction = [200, 220, 230, 240, 250, 260, 260, 270]
        self.airtemp = [0.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 20.0]
        energy_supply_conn_name_auxiliary = "Boiler_auxiliary"
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
        extcond = ExternalConditions(
            simulation_time=self.simtime,
            air_temps=self.airtemp,
            wind_speeds=self.windspeed,
            wind_directions=self.wind_direction,
            diffuse_horizontal_radiation=self.diffuse_horizontal_radiation,
            direct_beam_radiation=self.direct_beam_radiation,
            solar_reflectivity_of_ground=self.solar_reflectivity_of_ground,
            latitude=self.latitude,
            longitude=self.longitude,
            timezone=self.timezone,
            start_day=self.start_day,
            end_day=self.end_day,
            time_series_step=self.time_series_step,
            january_first=self.january_first,
            daylight_savings=self.daylight_savings,
            leap_day_included=self.leap_day_included,
            direct_beam_conversion_needed=self.direct_beam_conversion_needed,
            shading_segments=self.shading_segments,
        )

        self.boiler = Boiler(
            boiler_dict=boiler_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_aux=energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            ext_cond=extcond,
        )
        self.boiler._Boiler__create_service_connection(service_name="boiler_test")

        coldwatertemps = [1.0, 1.2]
        self.coldfeed = ColdWaterSource(
            cold_water_temps=coldwatertemps,
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )
        return_temp = 60
        self.boiler_service_water = BoilerServiceWaterCombi(
            boiler=self.boiler,
            boiler_data=boilerservicewatercombi_dict,
            service_name="boiler_test",
            temp_hot_water=return_temp,
            cold_feed=self.coldfeed,
            simulation_time=self.simtime,
        )

    def test_init_separate_DHW_tests_ms(self):
        boiler_data = {
            "separate_DHW_tests": "M&S",
            "fuel_energy_1": 7.099,
            "rejected_energy_1": 0.0004,
            "storage_loss_factor_1": 0.98328,
            "fuel_energy_2": 13.078,
            "rejected_energy_2": 0.0008,
            "storage_loss_factor_2": 0.91574,
            "rejected_factor_3": 0,
            "daily_HW_usage": 132.5802,
        }

        self.boiler_service_water = BoilerServiceWaterCombi(
            boiler=self.boiler,
            boiler_data=boiler_data,
            service_name="boiler_test",
            temp_hot_water=20,
            cold_feed=self.coldfeed,
            simulation_time=self.simtime,
        )

        self.assertAlmostEqual(
            self.boiler_service_water._BoilerServiceWaterCombi__rejected_energy_1,
            boiler_data["rejected_energy_1"],
        )
        self.assertAlmostEqual(
            self.boiler_service_water._BoilerServiceWaterCombi__storage_loss_factor_2,
            boiler_data["storage_loss_factor_2"],
        )
        self.assertAlmostEqual(
            self.boiler_service_water._BoilerServiceWaterCombi__rejected_factor_3,
            boiler_data["rejected_factor_3"],
        )

    def test_init_separate_DHW_tests_ml(self):
        boiler_data = {
            "separate_DHW_tests": "M&L",
            "fuel_energy_1": 7.099,
            "rejected_energy_1": 0.0004,
            "storage_loss_factor_1": 0.98328,
            "fuel_energy_2": 13.078,
            "rejected_energy_2": 0.0008,
            "storage_loss_factor_2": 0.91574,
            "rejected_factor_3": 0,
            "daily_HW_usage": 132.5802,
        }

        self.boiler_service_water = BoilerServiceWaterCombi(
            boiler=self.boiler,
            boiler_data=boiler_data,
            service_name="boiler_test",
            temp_hot_water=20,
            cold_feed=self.coldfeed,
            simulation_time=self.simtime,
        )

        self.assertAlmostEqual(
            self.boiler_service_water._BoilerServiceWaterCombi__rejected_energy_1,
            boiler_data["rejected_energy_1"],
        )
        self.assertAlmostEqual(
            self.boiler_service_water._BoilerServiceWaterCombi__storage_loss_factor_2,
            boiler_data["storage_loss_factor_2"],
        )
        self.assertAlmostEqual(
            self.boiler_service_water._BoilerServiceWaterCombi__rejected_factor_3,
            boiler_data["rejected_factor_3"],
        )

    def test_init_separate_DHW_tests_m_only(self):
        boiler_data = {
            "separate_DHW_tests": "M_only",
            "fuel_energy_1": 7.099,
            "rejected_energy_1": 0.0004,
            "storage_loss_factor_1": 0.98328,
            "fuel_energy_2": 13.078,
            "rejected_energy_2": 0.0008,
            "storage_loss_factor_2": 0.91574,
            "rejected_factor_3": 0,
            "daily_HW_usage": 132.5802,
        }

        self.boiler_service_water = BoilerServiceWaterCombi(
            boiler=self.boiler,
            boiler_data=boiler_data,
            service_name="boiler_test",
            temp_hot_water=20,
            cold_feed=self.coldfeed,
            simulation_time=self.simtime,
        )

        self.assertAlmostEqual(
            self.boiler_service_water._BoilerServiceWaterCombi__rejected_energy_1,
            boiler_data["rejected_energy_1"],
        )
        self.assertAlmostEqual(
            self.boiler_service_water._BoilerServiceWaterCombi__storage_loss_factor_1,
            boiler_data["storage_loss_factor_1"],
        )
        self.assertFalse(
            hasattr(self.boiler_service_water, "_BoilerServiceWaterCombi__rejected_factor_3")
        )

    def test_boiler_service_water(self):
        """Test that Boiler object returns correct hot water energy demand"""
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertAlmostEqual(
                    self.boiler_service_water.demand_hot_water(
                        self.usage_events_all_timesteps[t_idx]
                    ),
                    [7.66338330142884, 2.268102921416737][t_idx],
                    msg="incorrect energy_output_provided",
                )

    def test_demand_hot_water_with_no_hot_water(self):
        usage_events = []
        self.assertEqual(self.boiler_service_water.demand_hot_water(usage_events), 0.0)

    def test_get_cold_water_source(self):
        self.assertEqual(self.boiler_service_water.get_cold_water_source(), self.coldfeed)

    def test_get_temp_hot_water(self):
        self.assertAlmostEqual(self.boiler_service_water.get_temp_hot_water(10.0), [(60, 10.0)])

    def test_internal_gains(self):
        self.boiler_service_water._BoilerServiceWaterCombi__combi_loss = 10
        self.assertAlmostEqual(self.boiler_service_water.internal_gains(), 2500)

    def test_energy_output_max(self):
        self.assertAlmostEqual(self.boiler_service_water.energy_output_max(), 16.85)

    def test_get_daily_vol_factor(self):
        # Below threshold_volume
        self.boiler_service_water._BoilerServiceWaterCombi__separate_DHW_tests = (
            BoilerHotWaterTest.M_S
        )
        self.boiler_service_water._BoilerServiceWaterCombi__daily_HW_usage = 50
        self.assertAlmostEqual(self.boiler_service_water.get_daily_vol_factor(), 50.2)

        # Above S profile
        self.boiler_service_water._BoilerServiceWaterCombi__separate_DHW_tests = (
            BoilerHotWaterTest.M_S
        )
        self.boiler_service_water._BoilerServiceWaterCombi__daily_HW_usage = 150
        self.assertAlmostEqual(self.boiler_service_water.get_daily_vol_factor(), 0)

        # Below S profile
        self.boiler_service_water._BoilerServiceWaterCombi__separate_DHW_tests = (
            BoilerHotWaterTest.M_S
        )
        self.boiler_service_water._BoilerServiceWaterCombi__daily_HW_usage = 30
        self.assertAlmostEqual(self.boiler_service_water.get_daily_vol_factor(), 64.2)

        # Above L profile
        self.boiler_service_water._BoilerServiceWaterCombi__separate_DHW_tests = (
            BoilerHotWaterTest.M_L
        )
        self.boiler_service_water._BoilerServiceWaterCombi__daily_HW_usage = 300
        self.assertAlmostEqual(self.boiler_service_water.get_daily_vol_factor(), -99.6)

        # Below L profile
        self.boiler_service_water._BoilerServiceWaterCombi__separate_DHW_tests = (
            BoilerHotWaterTest.M_L
        )
        self.boiler_service_water._BoilerServiceWaterCombi__daily_HW_usage = 30
        self.assertAlmostEqual(self.boiler_service_water.get_daily_vol_factor(), 0)

        # M only
        self.boiler_service_water._BoilerServiceWaterCombi__separate_DHW_tests = (
            BoilerHotWaterTest.M_ONLY
        )
        self.boiler_service_water._BoilerServiceWaterCombi__daily_HW_usage = 150
        self.assertAlmostEqual(self.boiler_service_water.get_daily_vol_factor(), -49.8)

        # No additional tests
        self.boiler_service_water._BoilerServiceWaterCombi__separate_DHW_tests = (
            BoilerHotWaterTest.NO_ADDITIONAL_TESTS
        )
        self.boiler_service_water._BoilerServiceWaterCombi__daily_HW_usage = 130
        self.assertAlmostEqual(self.boiler_service_water.get_daily_vol_factor(), -29.8)

    def test_boiler_combi_loss(self):
        self.boiler_service_water._BoilerServiceWaterCombi__rejected_energy_1_adj = 0.001
        self.boiler_service_water._BoilerServiceWaterCombi__storage_loss_factor_1_adj = 0.109
        self.boiler_service_water._BoilerServiceWaterCombi__storage_loss_factor_2_adj = 0.1125

        # Tested to M and S
        self.boiler_service_water._BoilerServiceWaterCombi__separate_DHW_tests = (
            BoilerHotWaterTest.M_S
        )
        self.assertAlmostEqual(
            self.boiler_service_water.boiler_combi_loss(20, 1.5, "Other"), 0.14250000000000002
        )

        # Tested to M and L
        self.boiler_service_water._BoilerServiceWaterCombi__separate_DHW_tests = (
            BoilerHotWaterTest.M_S
        )
        self.assertAlmostEqual(self.boiler_service_water.boiler_combi_loss(20, 1.5, "Bath"), 0.1125)

        # M only
        self.boiler_service_water._BoilerServiceWaterCombi__separate_DHW_tests = (
            BoilerHotWaterTest.M_ONLY
        )
        self.assertAlmostEqual(self.boiler_service_water.boiler_combi_loss(20, 1.5, "Other"), 0.139)

        # No additional tests
        self.boiler_service_water._BoilerServiceWaterCombi__separate_DHW_tests = (
            BoilerHotWaterTest.NO_ADDITIONAL_TESTS
        )
        self.assertAlmostEqual(self.boiler_service_water.boiler_combi_loss(20, 1.5, "Other"), 0.139)

    def test_boiler_combi_loss_invalid_separate_dhw_tests(self):
        """Test that boiler_combi_loss throws on an invalid __separate_DHW_tests value"""
        self.boiler_service_water._BoilerServiceWaterCombi__separate_DHW_tests = None
        with self.assertRaises(ValueError):
            self.boiler_service_water.boiler_combi_loss(20, 1.5, "Other")


class TestBoilerServiceWaterRegular(unittest.TestCase):
    """Unit tests for Regular Boiler class"""

    def setUp(self):
        """Create Regular Boiler object to be tested"""
        boiler_dict = {
            "type": "Boiler",
            "EnergySupply": "mains gas",
            "rated_power": 24.0,
            "temperature_return_": 60,
            "efficiency_full_load": 0.891,
            "efficiency_part_load": 0.991,
            "boiler_location": HeatSourceLocation.INTERNAL,
            "modulation_load": 0.3,
            "electricity_circ_pump": 0.0600,
            "electricity_part_load": 0.0131,
            "electricity_full_load": 0.0388,
            "electricity_standby": 0.0244,
        }

        self.simtime = SimulationTime(start_time=0, end_time=2, step=1)
        self.energysupply = EnergySupply(fuel_type=FuelType.MAINS_GAS, simulation_time=self.simtime)
        self.volume_demanded = [10, 2]
        self.temp_return_feed = [51.05, 60.00]

        self.windspeed = [3.7, 3.8, 3.9, 4.0, 4.1, 4.2, 4.3, 4.4]
        self.wind_direction = [200, 220, 230, 240, 250, 260, 260, 270]
        self.airtemp = [0.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 20.0]
        energy_supply_conn_name_auxiliary = "Boiler_auxiliary"
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
        extcond = ExternalConditions(
            simulation_time=self.simtime,
            air_temps=self.airtemp,
            wind_speeds=self.windspeed,
            wind_directions=self.wind_direction,
            diffuse_horizontal_radiation=self.diffuse_horizontal_radiation,
            direct_beam_radiation=self.direct_beam_radiation,
            solar_reflectivity_of_ground=self.solar_reflectivity_of_ground,
            latitude=self.latitude,
            longitude=self.longitude,
            timezone=self.timezone,
            start_day=self.start_day,
            end_day=self.end_day,
            time_series_step=self.time_series_step,
            january_first=self.january_first,
            daylight_savings=self.daylight_savings,
            leap_day_included=self.leap_day_included,
            direct_beam_conversion_needed=self.direct_beam_conversion_needed,
            shading_segments=self.shading_segments,
        )

        controlmin = SetpointTimeControl(
            schedule=[52, 52], simulation_time=self.simtime, start_day=0, time_series_step=1
        )
        controlmax = SetpointTimeControl(
            schedule=[60, 60], simulation_time=self.simtime, start_day=0, time_series_step=1
        )

        self.boiler = Boiler(
            boiler_dict=boiler_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_aux=energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            ext_cond=extcond,
        )
        self.boiler._Boiler__create_service_connection(service_name="boiler_test")
        coldwatertemps = [1.0, 1.2]
        coldfeed = ColdWaterSource(
            cold_water_temps=coldwatertemps,
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )
        self.boiler_service_water = BoilerServiceWaterRegular(
            boiler=self.boiler,
            service_name="boiler_test",
            cold_feed=coldfeed,
            simulation_time=self.simtime,
            controlmin=controlmin,
            controlmax=controlmax,
        )

    def test_boiler_service_water(self):
        """Test that Regular Boiler object returns correct hot water energy demand"""
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertAlmostEqual(
                    self.boiler._demand_energy(
                        "boiler_test",
                        HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                        [0.7241412, 0.1748878][t_idx],
                        self.temp_return_feed[t_idx],
                    ),
                    [0.7241412, 0.1748878][t_idx],
                    msg="incorrect energy_output_provided",
                )

    def test_temp_setpnt(self):
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertAlmostEqual(self.boiler_service_water.setpnt(), (52, 60))

    def test_demand_energy(self):
        self.assertEqual(self.boiler_service_water.demand_energy(100, 20, 20), 24)

    def test_demand_energy_without_temp_return(self):
        """Test that demand_energy throws if temp_return is None and energy_demand is not 0.0"""
        with self.assertRaises(ValueError):
            self.assertEqual(self.boiler_service_water.demand_energy(100, 20, None), 24)

    def test_demand_energy_with_control_off(self):
        """Test that zero demand is returned when the control is off"""
        control = MagicMock()
        control.is_on.return_value = False
        coldfeed = ColdWaterSource([1, 1.2], self.simtime, 0, 1)
        self.boiler_service_water = BoilerServiceWaterRegular(
            boiler=self.boiler,
            service_name="boiler_test",
            cold_feed=coldfeed,
            simulation_time=self.simtime,
            controlmin=control,
            controlmax=control,
        )

        self.assertEqual(
            self.boiler_service_water.demand_energy(
                energy_demand=100, temp_flow=20, temp_return=20
            ),
            0,
        )

    def test_energy_output_max(self):
        self.assertEqual(
            self.boiler_service_water.energy_output_max(temp_flow=20, temp_return=20), 24
        )

    def test_energy_output_max_with_control_off(self):
        """Test that zero energy max is returned when the control is off"""
        control = MagicMock()
        control.is_on.return_value = False
        coldfeed = ColdWaterSource(
            cold_water_temps=[1, 1.2], simulation_time=self.simtime, start_day=0, time_series_step=1
        )
        self.boiler_service_water = BoilerServiceWaterRegular(
            boiler=self.boiler,
            service_name="boiler_test",
            cold_feed=coldfeed,
            simulation_time=self.simtime,
            controlmin=control,
            controlmax=control,
        )

        self.assertEqual(
            self.boiler_service_water.energy_output_max(temp_flow=20, temp_return=20), 0
        )


class TestBoilerServiceSpace(unittest.TestCase):
    """Unit tests for Boiler class"""

    def setUp(self):
        """Create Boiler object to be tested"""
        boiler_dict = {
            "type": "Boiler",
            "rated_power": 16.85,
            "EnergySupply": "mains_gas",
            "efficiency_full_load": 0.868,
            "efficiency_part_load": 0.952,
            "boiler_location": HeatSourceLocation.INTERNAL,
            "modulation_load": 1,
            "electricity_circ_pump": 0.0600,
            "electricity_part_load": 0.0131,
            "electricity_full_load": 0.0388,
            "electricity_standby": 0.0244,
        }
        self.simtime = SimulationTime(start_time=0, end_time=3, step=1)
        self.energysupply = EnergySupply(fuel_type=FuelType.MAINS_GAS, simulation_time=self.simtime)
        self.energy_demanded = [10.0, 2.0, 2.0]
        self.temp_flow = [55.0, 65.0, 65.0]
        self.temp_return_feed = [50.0, 60.0, 60.0]
        self.airtemp = [0.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 20.0]
        energy_supply_conn_name_auxiliary = "Boiler_auxiliary"
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
        extcond = ExternalConditions(
            simulation_time=self.simtime,
            air_temps=self.airtemp,
            wind_speeds=self.windspeed,
            wind_directions=self.wind_direction,
            diffuse_horizontal_radiation=self.diffuse_horizontal_radiation,
            direct_beam_radiation=self.direct_beam_radiation,
            solar_reflectivity_of_ground=self.solar_reflectivity_of_ground,
            latitude=self.latitude,
            longitude=self.longitude,
            timezone=self.timezone,
            start_day=self.start_day,
            end_day=self.end_day,
            time_series_step=self.time_series_step,
            january_first=self.january_first,
            daylight_savings=self.daylight_savings,
            leap_day_included=self.leap_day_included,
            direct_beam_conversion_needed=self.direct_beam_conversion_needed,
            shading_segments=self.shading_segments,
        )
        self.boiler = Boiler(
            boiler_dict=boiler_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_aux=energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            ext_cond=extcond,
        )
        self.boiler._Boiler__create_service_connection(service_name="boiler_test")
        ctrl = SetpointTimeControl(
            schedule=[21.0, 21.0, None],
            simulation_time=self.simtime,
            start_day=0,  # start_day
            time_series_step=1.0,  # time_series_step
        )
        self.boiler_service_space = BoilerServiceSpace(
            boiler=self.boiler, service_name="boiler_test", control=ctrl
        )

    def test_boiler_service_space(self):
        """Test that Boiler object returns correct space heating energy demand"""
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertAlmostEqual(
                    self.boiler_service_space.demand_energy(
                        self.energy_demanded[t_idx],
                        self.temp_flow[t_idx],
                        self.temp_return_feed[t_idx],
                    ),
                    [10.0, 2.0, 0.0][t_idx],
                    msg="incorrect energy_output_provided",
                )

    def test_temp_setpnt(self):
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(self.boiler_service_space.temp_setpnt(), [21, 21, None][t_idx])

    def test_in_required_period(self):
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.boiler_service_space.in_required_period(), [True, True, False][t_idx]
                )

    def test_energy_output_max(self):
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.boiler_service_space.energy_output_max(
                        temp_output=20, temp_return_feed=10, time_start=0
                    ),
                    [16.85, 16.85, 0][t_idx],
                )


class TestBoiler(unittest.TestCase):
    """Unit tests for Combi Boiler class"""

    def setUp(self):
        """Create Boiler object to be tested"""
        self.boiler_dict = {
            "type": "Boiler",
            "rated_power": 24.0,
            "EnergySupply": "mains_gas",
            "efficiency_full_load": 0.88,
            "efficiency_part_load": 0.986,
            "boiler_location": HeatSourceLocation.INTERNAL,
            "modulation_load": 0.2,
            "electricity_circ_pump": 0.0600,
            "electricity_part_load": 0.0131,
            "electricity_full_load": 0.0388,
            "electricity_standby": 0.0244,
        }
        self.simtime = SimulationTime(0, 2, 1)
        self.energysupply = EnergySupply(FuelType.MAINS_GAS, self.simtime)
        self.energy_supply_conn_auxiliary = MagicMock()
        self.energy_output_required = [2.0, 10.0]
        self.temp_return_feed = [51.05, 60.00]
        self.windspeed = [3.7, 3.8, 3.9, 4.0, 4.1, 4.2, 4.3, 4.4]
        self.wind_direction = [200, 220, 230, 240, 250, 260, 260, 270]
        self.airtemp = [0.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 20.0]
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
        self.extcond = ExternalConditions(
            simulation_time=self.simtime,
            air_temps=self.airtemp,
            wind_speeds=self.windspeed,
            wind_directions=self.wind_direction,
            diffuse_horizontal_radiation=self.diffuse_horizontal_radiation,
            direct_beam_radiation=self.direct_beam_radiation,
            solar_reflectivity_of_ground=self.solar_reflectivity_of_ground,
            latitude=self.latitude,
            longitude=self.longitude,
            timezone=self.timezone,
            start_day=self.start_day,
            end_day=self.end_day,
            time_series_step=self.time_series_step,
            january_first=self.january_first,
            daylight_savings=self.daylight_savings,
            leap_day_included=self.leap_day_included,
            direct_beam_conversion_needed=self.direct_beam_conversion_needed,
            shading_segments=self.shading_segments,
        )

        self.boiler = Boiler(
            boiler_dict=self.boiler_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_aux=self.energy_supply_conn_auxiliary,
            simulation_time=self.simtime,
            ext_cond=self.extcond,
        )

    def test_create_service_connection(self):
        """Test creation of EnergySupplyConnection for the service name given"""
        self.service_name = "new_service"
        # Ensure the service name does not exist in __energy_supply_connections
        self.assertNotIn(self.service_name, self.boiler._Boiler__energy_supply_connections)
        # Call the method under test
        self.boiler._Boiler__create_service_connection(service_name=self.service_name)
        # Check that the service name was added to __energy_supply_connections
        self.assertIn(self.service_name, self.boiler._Boiler__energy_supply_connections)
        # Check system exit when connection is created with existing service name
        with self.assertRaises(ValueError):
            self.boiler._Boiler__create_service_connection(service_name=self.service_name)

    def test_create_service_hot_water_combi(self):
        """Check BoilerServiceWaterCombi object is created correctly"""

        self.service_name = "service_hot_water_combi"
        self.coldfeed = ColdWaterSource(
            cold_water_temps=[1.0, 1.2],
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )
        self.temp_hot_water = 50
        self.boiler_data = {
            "type": "CombiBoiler",
            "ColdWaterSource": "mains water",
            "HeatSourceWet": "hp",
            "Control": "hw timer",
            "separate_DHW_tests": "M&L",
            "rejected_energy_1": 0.0004,
            "fuel_energy_2": 13.078,
            "rejected_energy_2": 0.0004,
            "storage_loss_factor_2": 0.91574,
            "rejected_factor_3": 0,
            "daily_HW_usage": 120,
            "setpoint_temp": 60.0,
        }

        boiler_service_WaterCombi_obj = self.boiler.create_service_hot_water_combi(
            boiler_data=self.boiler_data,
            service_name=self.service_name,
            temp_hot_water=self.temp_hot_water,
            cold_feed=self.coldfeed,
        )

        self.assertTrue(isinstance(boiler_service_WaterCombi_obj, BoilerServiceWaterCombi))

    def test_create_service_hot_water_regular(self):
        """Check the function returns BoilerServiceWaterRegular object"""

        self.service_name = "service_hot_water_regular"
        self.coldfeed = ColdWaterSource([1.0, 1.2], self.simtime, 0, 1)
        self.temp_hot_water = 50
        self.controlmin = SetpointTimeControl([None, None], self.simtime, 0, 1)
        self.controlmax = SetpointTimeControl([None, None], self.simtime, 0, 1)
        boiler_hotwater_regular = self.boiler.create_service_hot_water_regular(
            service_name=self.service_name,
            cold_feed=self.coldfeed,
            controlmin=self.controlmin,
            controlmax=self.controlmax,
        )

        self.assertTrue(isinstance(boiler_hotwater_regular, BoilerServiceWaterRegular))

    def test_create_service_space_heating(self):
        """Check the function returns BoilerServiceSpace object"""

        boiler_create_service_space_heating = self.boiler.create_service_space_heating(
            service_name="BoilerServiceSpace", control=MagicMock()
        )
        self.assertTrue(isinstance(boiler_create_service_space_heating, BoilerServiceSpace))

    def test_cycling_adjustment(self):
        self.assertAlmostEqual(
            self.boiler._Boiler__cycling_adjustment(
                temp_return_feed=40.0,
                standing_loss=0.05,
                prop_of_timestep_at_min_rate=0.5,
                temp_boiler_loc=20,
            ),
            0.015905414575341014,
        )

    def test_location_adjustment(self):
        # Internal boiler settings
        self.assertAlmostEqual(
            self.boiler.location_adjustment(
                temp_return_feed=30, standing_loss=5, temp_boiler_loc=20
            ),
            0.0,
        )
        # External boiler settings
        self.boiler_dict_external = {
            "type": "Boiler",
            "rated_power": 24.0,
            "EnergySupply": "mains_gas",
            "efficiency_full_load": 0.88,
            "efficiency_part_load": 0.986,
            "boiler_location": HeatSourceLocation.EXTERNAL,
            "modulation_load": 0.2,
            "electricity_circ_pump": 0.0600,
            "electricity_part_load": 0.0131,
            "electricity_full_load": 0.0388,
            "electricity_standby": 0.0244,
        }
        self.boiler_external = Boiler(
            boiler_dict=self.boiler_dict_external,
            energy_supply=self.energysupply,
            energy_supply_conn_aux=self.energy_supply_conn_auxiliary,
            simulation_time=self.simtime,
            ext_cond=self.extcond,
        )

        self.assertAlmostEqual(
            self.boiler_external.location_adjustment(
                temp_return_feed=30, standing_loss=5, temp_boiler_loc=2.5
            ),
            1.6574326024894575,
        )

    def test_location_adjustment_when_boiler_hotter_than_return(self):
        """Test location_adjustment returns 0 when boiler location is hotter than return feed"""
        # This can occur on a hot summer day
        self.assertAlmostEqual(
            self.boiler.location_adjustment(
                temp_return_feed=30, standing_loss=5, temp_boiler_loc=35
            ),
            0.0,
        )

    def test_location_adjustment_when_return_below_room_temp(self):
        """Test location_adjustment returns 0 when return feed is below room temperature"""
        # Return feed at 15°C, below room temp of 19.5°C
        self.assertAlmostEqual(
            self.boiler.location_adjustment(
                temp_return_feed=15, standing_loss=5, temp_boiler_loc=10
            ),
            0.0,
        )

    def test_location_adjustment_when_return_equals_room_temp(self):
        """Test location_adjustment returns 0 when return feed equals room temperature"""
        self.assertAlmostEqual(
            self.boiler.location_adjustment(
                temp_return_feed=19.5, standing_loss=5, temp_boiler_loc=10
            ),
            0.0,
        )

    def test_location_adjustment_when_boiler_equals_return_temp(self):
        """Test location_adjustment returns 0 when boiler location equals return feed"""
        self.assertAlmostEqual(
            self.boiler.location_adjustment(
                temp_return_feed=30, standing_loss=5, temp_boiler_loc=30
            ),
            0.0,
        )

    def test_calc_current_boiler_power(self):
        self.assertAlmostEqual(
            self.boiler._Boiler__calc_current_boiler_power(
                energy_output_provided=10, time_available=0
            ),
            0.0,
        )

        self.assertAlmostEqual(
            self.boiler._Boiler__calc_current_boiler_power(
                energy_output_provided=10, time_available=3
            ),
            4.800000000000001,
        )

    def test_calc_boiler_eff(self):
        # Check with location 'internal'
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertAlmostEqual(
                    self.boiler.calc_boiler_eff(
                        service_type=HeatingServiceType.SPACE,
                        temp_return_feed=37,
                        energy_output_required=3,
                        time_elapsed_hp=0,
                    ),
                    [0.8642616521182549, 0.8642616521182549][t_idx],
                )

        # Check with location 'external'
        boiler_dict_external = {
            "type": "Boiler",
            "rated_power": 24.0,
            "EnergySupply": "mains_gas",
            "efficiency_full_load": 0.88,
            "efficiency_part_load": 0.986,
            "boiler_location": HeatSourceLocation.EXTERNAL,
            "modulation_load": 0.2,
            "electricity_circ_pump": 0.0600,
            "electricity_part_load": 0.0131,
            "electricity_full_load": 0.0388,
            "electricity_standby": 0.0244,
        }

        energy_supply_conn_name_auxiliary = "Boiler_external"
        self.boiler_external = Boiler(
            boiler_dict=boiler_dict_external,
            energy_supply=self.energysupply,
            energy_supply_conn_aux=energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            ext_cond=self.extcond,
        )
        self.simtime.reset()
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertAlmostEqual(
                    self.boiler_external.calc_boiler_eff(
                        service_type=HeatingServiceType.SPACE,
                        temp_return_feed=37,
                        energy_output_required=3,
                        time_elapsed_hp=0,
                    ),
                    [0.8537436763973477, 0.855177537866697][t_idx],
                )

    def test_calc_boiler_eff_with_invalid_location(self):
        self.boiler_dict["boiler_location"] = "invalid"
        with self.assertRaises(ValueError):
            self.boiler = Boiler(
                boiler_dict=self.boiler_dict,
                energy_supply=self.energysupply,
                energy_supply_conn_aux=self.energy_supply_conn_auxiliary,
                simulation_time=self.simtime,
                ext_cond=self.extcond,
            )

    def test_calc_energy_output_provided(self):
        self.assertAlmostEqual(
            self.boiler._Boiler__calc_energy_output_provided(
                energy_output_required=5.0, time_available=1
            ),
            5.0,
        )

        self.assertAlmostEqual(
            self.boiler._Boiler__calc_energy_output_provided(
                energy_output_required=25.0, time_available=1
            ),
            24.0,
        )

    def test_time_available(self):
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertAlmostEqual(self.boiler._Boiler__time_available(0.0), [1.0, 1.0][t_idx])

        self.simtime.reset()
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertAlmostEqual(
                    self.boiler._Boiler__time_available(0.2, time_elapsed_hp=0.5), [0.4, 0.4][t_idx]
                )

    def test_demand_energy(self):
        # Test with different values of  service types and hybrid_service_bool
        self.boiler._Boiler__create_service_connection(service_name="boiler_demand_energy")

        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertAlmostEqual(
                    self.boiler._demand_energy(
                        service_name="boiler_demand_energy",
                        service_type=HeatingServiceType.DOMESTIC_HOT_WATER_COMBI,
                        energy_output_required=10,
                        temp_return_feed=37,
                        hybrid_service=False,
                        time_elapsed_hp=None,
                    ),
                    [10, 0.0][t_idx],
                )

        self.boiler._Boiler__create_service_connection(
            service_name="boiler_demand_energy_with_hybrid"
        )

        self.simtime.reset()
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.boiler._demand_energy(
                        service_name="boiler_demand_energy_with_hybrid",
                        service_type=HeatingServiceType.SPACE,
                        energy_output_required=100,
                        temp_return_feed=37,
                        hybrid_service=True,
                        time_elapsed_hp=0,
                    ),
                    [(24.0, 1.0), (24.0, 1.0)][t_idx],
                )

        # Test with time_elapsed_hp
        self.boiler._Boiler__create_service_connection(
            service_name="boiler_demand_energy_hybrid_time_elapsed"
        )

        self.simtime.reset()
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.boiler._demand_energy(
                        service_name="boiler_demand_energy_hybrid_time_elapsed",
                        service_type=HeatingServiceType.SPACE,
                        energy_output_required=100,
                        temp_return_feed=37,
                        hybrid_service=True,
                        time_elapsed_hp=0.5,
                    ),
                    [(12.0, 0.5), (12.0, 0.5)][t_idx],
                )

        required_services = {
            "boiler_demand_energy",
            "boiler_demand_energy_with_hybrid",
            "boiler_demand_energy_hybrid_time_elapsed",
        }
        service_names_in_list = {
            entry["service_name"] for entry in self.boiler._Boiler__service_results
        }
        self.assertTrue(required_services.issubset(service_names_in_list))

    def test_fuel_demand(self):
        # Test with Mock to check demand_energy() of energy supply was called with 0.0

        self.boiler._Boiler__energy_supply_connections = {
            "mock": MagicMock(),
            "mock2": MagicMock(),
        }
        self.boiler._Boiler__time_available = MagicMock()
        self.boiler._Boiler__time_available.return_value = 0.0
        self.boiler._demand_energy(
            service_name="mock",
            service_type=HeatingServiceType.SPACE,
            energy_output_required=0,
            temp_return_feed=37,
            hybrid_service=False,
            time_elapsed_hp=1,
        )

        self.boiler._Boiler__fuel_demand()
        self.boiler._Boiler__energy_supply_connections["mock"].demand_energy.assert_called_with(
            amount_demanded=0.0
        )

        # Test with Mock to check demand_energy() of energy supply was called with given value

        self.boiler.calc_boiler_eff = MagicMock()
        self.boiler._Boiler__calc_energy_output_provided = MagicMock()
        self.boiler._Boiler__calc_current_boiler_power = MagicMock()

        self.boiler._Boiler__time_available.return_value = 1.0
        self.boiler._Boiler__calc_energy_output_provided.return_value = 100.0
        self.boiler._Boiler__calc_current_boiler_power.return_value = 50.0

        self.boiler._demand_energy(
            service_name="mock",
            service_type=HeatingServiceType.SPACE,
            energy_output_required=100.0,
            temp_return_feed=37,
            hybrid_service=False,
            time_elapsed_hp=None,
        )
        self.boiler._Boiler__fuel_demand()
        self.boiler._Boiler__energy_supply_connections["mock"].demand_energy.assert_called_with(
            amount_demanded=106.257669110742
        )

        self.boiler._Boiler__calc_energy_output_provided.return_value = 50.0
        self.boiler._demand_energy(
            service_name="mock2",
            service_type=HeatingServiceType.SPACE,
            energy_output_required=50.0,
            temp_return_feed=37,
            hybrid_service=False,
            time_elapsed_hp=None,
        )
        self.boiler._Boiler__fuel_demand()
        self.boiler._Boiler__energy_supply_connections["mock2"].demand_energy.assert_called_with(
            amount_demanded=53.128834555371
        )

    def test_fuel_demand_with_no_return_feed(self):
        self.boiler._Boiler__service_results = [
            {
                "service_name": "mock",
                "service_type": "service_type",
                "temp_return_feed": None,
                "energy_output_provided": 10,
                "energy_output_required": 10,
                "time_available": 1,
            }
        ]
        self.boiler._Boiler__energy_supply_connections = {"mock": MagicMock()}

        self.boiler._Boiler__fuel_demand()

        self.boiler._Boiler__energy_supply_connections["mock"].demand_energy.assert_called_with(
            amount_demanded=0.0
        )

    def test_calc_auxiliary_energy(self):
        """Check boiler electrical consumption"""
        self.energysupply_aux = EnergySupply(FuelType.ELECTRICITY, self.simtime)
        self.energy_supply_conn_auxiliary = self.energysupply_aux.connection("boiler_auxillary")

        self.boiler = Boiler(
            boiler_dict=self.boiler_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_aux=self.energy_supply_conn_auxiliary,
            simulation_time=self.simtime,
            ext_cond=self.extcond,
        )
        # Check the function runs without throwing errors
        self.assertEqual(self.boiler._Boiler__calc_auxiliary_energy(1, 0), None)

        # Check the demand_energy() has been called once
        self.energy_supply_conn_auxiliary = MagicMock()
        self.boiler = Boiler(
            boiler_dict=self.boiler_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_aux=self.energy_supply_conn_auxiliary,
            simulation_time=self.simtime,
            ext_cond=self.extcond,
        )
        self.boiler._Boiler__calc_auxiliary_energy(1, 0.5)
        self.boiler._Boiler__energy_supply_connection_aux.demand_energy.assert_called_once()

    def test_calc_auxiliary_energy_with_space_heating(self):
        self.boiler._Boiler__service_results = [
            {
                "service_name": "mock",
                "service_type": HeatingServiceType.SPACE,
                "temp_return_feed": None,
                "energy_output_provided": 10,
                "energy_output_required": 10,
                "time_available": 10,
            },
            {
                "service_name": "mock",
                "service_type": HeatingServiceType.SPACE,
                "temp_return_feed": None,
                "energy_output_provided": 15,
                "energy_output_required": 15,
                "time_available": 15,
            },
        ]

        self.boiler._Boiler__energy_supply_connection_aux = MagicMock()

        self.boiler._Boiler__calc_auxiliary_energy(1, 0.5)

        self.boiler._Boiler__energy_supply_connection_aux.demand_energy.assert_called_with(
            amount_demanded=0.08042916666666666
        )

    def test_timestep_end(self):
        self.boiler._Boiler__create_service_connection(service_name="boiler_demand_energy")

        self.boiler._demand_energy(
            service_name="boiler_demand_energy",
            service_type=HeatingServiceType.DOMESTIC_HOT_WATER_COMBI,
            energy_output_required=10,
            temp_return_feed=60,
            hybrid_service=False,
            time_elapsed_hp=None,
        )

        self.assertAlmostEqual(self.boiler._Boiler__total_time_running_current_timestep, 1.0)
        self.assertEqual(
            self.boiler._Boiler__service_results[0]["service_name"], "boiler_demand_energy"
        )

        # Call the method under test
        self.boiler.timestep_end()
        # Assertions to check if the internal state was updated correctly
        self.assertAlmostEqual(self.boiler._Boiler__total_time_running_current_timestep, 0.0)
        self.assertEqual(self.boiler._Boiler__service_results, [])

    def test_energy_output_max(self):
        self.assertAlmostEqual(
            self.boiler._energy_output_max(time_elapsed_hp=0),
            24.0,
        )

        self.assertAlmostEqual(
            self.boiler._energy_output_max(time_elapsed_hp=0.5),
            12.0,
        )

    def test_effvsreturntemp(self):
        """Check boiler efficiency returned at different return temperatures"""
        # test_mains_gas_efficiency_below_dewpoint
        efficiency = self.boiler.effvsreturntemp(return_temp=50, offset=0.5)
        expected_efficiency = (-0.0000686 * 50**2 + 0.00175 * 50 + 0.97845) - 0.5
        self.assertAlmostEqual(efficiency, expected_efficiency)

        # test_mains_gas_efficiency_above_dewpoint
        efficiency = self.boiler.effvsreturntemp(return_temp=60, offset=0.5)
        expected_efficiency = (-0.000619 * 60 + 0.91250229) - 0.5
        self.assertAlmostEqual(efficiency, expected_efficiency)

        # test_lpg_efficiency_below_dewpoint
        self.energysupply = EnergySupply(fuel_type=FuelType.LPG_BULK, simulation_time=self.simtime)
        self.energy_supply_connection_aux = MagicMock()
        self.boiler_lpg = Boiler(
            boiler_dict=self.boiler_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_aux=self.energy_supply_connection_aux,
            simulation_time=self.simtime,
            ext_cond=self.extcond,
        )

        efficiency = self.boiler_lpg.effvsreturntemp(return_temp=45, offset=0.5)
        expected_efficiency = (-0.00006118 * 45**2 + 0.00126 * 45 + 0.98586) - 0.5
        self.assertAlmostEqual(efficiency, expected_efficiency)

        # test_lpg_efficiency_above_dewpoint
        efficiency = self.boiler_lpg.effvsreturntemp(return_temp=50, offset=0.5)
        expected_efficiency = (-0.00062 * 50 + 0.9332) - 0.5
        self.assertAlmostEqual(efficiency, expected_efficiency)

        # test_efficiency_without_offset
        self.energysupply = EnergySupply(fuel_type=FuelType.MAINS_GAS, simulation_time=self.simtime)
        self.boiler = Boiler(
            boiler_dict=self.boiler_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_aux=self.energy_supply_connection_aux,
            simulation_time=self.simtime,
            ext_cond=self.extcond,
        )
        self.assertAlmostEqual(self.boiler.effvsreturntemp(return_temp=50, offset=0), 0.89445)

    def test_effvsreturntemp_with_invalid_fuel(self):
        self.boiler._Boiler__fuel_code = "invalid"
        with self.assertRaises(ValueError):
            self.boiler.effvsreturntemp(return_temp=50, offset=0)

    def test_high_value_correction_part_load(self):
        """Check  a Boiler efficiency corrected for high values"""
        # Fuel Code Main_gas
        self.assertAlmostEqual(
            self.boiler.high_value_correction_part_load(net_efficiency_part_load=5), 1.08
        )
        self.assertAlmostEqual(
            self.boiler.high_value_correction_part_load(net_efficiency_part_load=1), 0.992758
        )

        # Fuel Code LPG_Bulk
        self.energysupply = EnergySupply(FuelType.LPG_BULK, self.simtime)
        self.energy_supply_connection_aux = MagicMock()
        self.boiler_lpg = Boiler(
            boiler_dict=self.boiler_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_aux=self.energy_supply_connection_aux,
            simulation_time=self.simtime,
            ext_cond=self.extcond,
        )
        self.assertAlmostEqual(
            self.boiler_lpg.high_value_correction_part_load(net_efficiency_part_load=5), 1.06
        )
        self.assertAlmostEqual(
            self.boiler_lpg.high_value_correction_part_load(net_efficiency_part_load=1), 0.992758
        )

    def test_high_value_correction_part_load_with_invalid_fuel(self):
        self.boiler._Boiler__fuel_code = "invalid"
        with self.assertRaises(ValueError):
            self.boiler.high_value_correction_part_load(net_efficiency_part_load=5)

    def test_high_value_correction_full_load(self):
        self.assertAlmostEqual(
            self.boiler.high_value_correction_full_load(net_efficiency_full_load=1.0), 0.969715
        )

    def test_net_to_gross(self):
        """Check the net to gross factor"""
        # Fuel code main_gas
        self.assertAlmostEqual(self.boiler.net_to_gross(), 0.901)

        # Fuel Code LPG_Bulk
        self.energysupply = EnergySupply(FuelType.LPG_BULK, self.simtime)
        self.energy_supply_connection_aux = MagicMock()
        self.boiler_lpg = Boiler(
            boiler_dict=self.boiler_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_aux=self.energy_supply_connection_aux,
            simulation_time=self.simtime,
            ext_cond=self.extcond,
        )
        self.assertAlmostEqual(self.boiler_lpg.net_to_gross(), 0.921)

    def test_net_to_gross_with_invalid_fuel(self):
        self.boiler._Boiler__fuel_code = "invalid"
        with self.assertRaises(ValueError):
            self.boiler.net_to_gross()
