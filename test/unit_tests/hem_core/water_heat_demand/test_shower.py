#!/usr/bin/env python3

"""
This module contains unit tests for the shower module
"""

# Standard library imports
import unittest

from hem_core.energy_supply.energy_supply import EnergySupply

# Local imports
from hem_core.heating_systems.wwhrs import WWHRS_Instantaneous
from hem_core.input_output.enums import FuelType, WWHRSConfiguration
from hem_core.simulation_time import SimulationTime
from hem_core.water_heat_demand.cold_water_source import ColdWaterSource
from hem_core.water_heat_demand.shower import InstantElecShower, MixerShower


def func_temp_hot_water_fixed(f):
    """Function to return a fixed temperature for hot water"""
    return 52.0


class TestMixerShower(unittest.TestCase):
    """Unit tests for MixerShower class"""

    def setUp(self):
        """Create MixerShower object to be tested"""
        self.simtime = SimulationTime(start_time=0, end_time=3, step=1)
        coldwatertemps = [2.0, 3.0, 4.0]
        self.coldwatersource = ColdWaterSource(
            cold_water_temps=coldwatertemps,
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )
        self.mixershower = MixerShower(flowrate=6.5, cold_water_source=self.coldwatersource)

    def test_hot_water_demand(self):
        """Test that MixerShower object returns correct volume of hot water"""
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                result = self.mixershower.hot_water_demand(
                    event={
                        "temperature": 40.0,
                        "duration": 5.0,
                        "start": 0,
                        "type": "Shower",
                        "name": "mixer",
                    },
                    func_temp_hot_water=func_temp_hot_water_fixed,
                )[0]
                assert result is not None
                self.assertAlmostEqual(
                    result,
                    [24.7, 24.54081632653061, 24.375][t_idx],
                    msg="incorrect volume of hot water returned",
                )

    def test_get_cold_water_source(self):
        self.assertTrue(isinstance(self.mixershower.get_cold_water_source(), ColdWaterSource))

    def test_vol_warm_water(self):
        """Test that MixerShower object returns correct volume of warm water"""
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertAlmostEqual(
                    self.mixershower.hot_water_demand(
                        event={
                            "temperature": 40.0,
                            "duration": 5.0,
                            "start": 0,
                            "type": "Shower",
                            "name": "mixer",
                        },
                        func_temp_hot_water=func_temp_hot_water_fixed,
                    )[1],
                    [32.5, 32.5, 32.5][t_idx],
                    msg="incorrect volume of warm water returned",
                )

    def test_wwhrs_instantaneousSystemB(self):
        flow_rates = [5, 7, 9, 11, 13]
        system_a_efficiencies = [44.8, 39.1, 34.8, 31.4, 28.6]
        wwhrs = WWHRS_Instantaneous(
            flow_rates=flow_rates,
            system_a_efficiencies=system_a_efficiencies,
            cold_water_source=self.coldwatersource,
            system_a_utilisation_factor=0.7,
            system_b_utilisation_factor=0.7,
            system_b_efficiency_factor=0.81,
        )
        self.mixershower = MixerShower(
            flowrate=6.5,
            cold_water_source=self.coldwatersource,
            wwhrs=wwhrs,
            wwhrs_configuration=WWHRSConfiguration.SHOWER,
        )

        # With Techncial Recommendations calculations for System B
        # temp_shower = 40°C, temp_hot = 52°C, flowrate = 6.5 L/min
        # For each timestep with different cold water temps
        expected_hot_water = []

        for t_idx in range(3):
            # Cold water temps: [2.0, 3.0, 4.0]
            temp_cold = [2.0, 3.0, 4.0][t_idx]

            # Interpolate efficiency at 6.5 L/min ≈ 40.525%
            # With System B factor (0.81) and utilisation factor (0.7): 40.525 * 0.81 * 0.7 = 22.977675%
            # T_drain = 40 - 6 = 34°C
            # temp = 0.22977675 * (34 - temp_cold) / (52 - 40)
            # T_pre = (temp_cold + 52 * temp) / (1 + temp)

            temp_drain = 34.0
            eta_uf = 0.40525 * 0.81 * 0.7  # ≈ 0.22977675
            temp = eta_uf * (temp_drain - temp_cold) / (52.0 - 40.0)
            temp_pre = (temp_cold + 52.0 * temp) / (1 + temp)

            # Volume of hot water = warm_water * (temp_shower - temp_pre) / (temp_hot - temp_pre)
            vol_warm = 32.5
            vol_hot = vol_warm * (40.0 - temp_pre) / (52.0 - temp_pre)
            expected_hot_water.append(vol_hot)

        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertAlmostEqual(
                    self.mixershower.hot_water_demand(
                        event={
                            "temperature": 40.0,
                            "duration": 5.0,
                            "start": 0,
                            "type": "Shower",
                            "name": "mixer",
                        },
                        func_temp_hot_water=func_temp_hot_water_fixed,
                    )[0],
                    expected_hot_water[t_idx],
                    places=4,
                    msg="incorrect volume of hot water returned",
                )

    def test_wwhrs_instantaneousSystemC(self):
        flow_rates = [5, 7, 9, 11, 13]
        system_a_efficiencies = [44.8, 39.1, 34.8, 31.4, 28.6]
        wwhrs = WWHRS_Instantaneous(
            flow_rates=flow_rates,
            system_a_efficiencies=system_a_efficiencies,
            cold_water_source=self.coldwatersource,
            system_a_utilisation_factor=0.7,
            system_c_utilisation_factor=0.7,
            system_c_efficiency_factor=0.88,
        )
        self.mixershower = MixerShower(
            flowrate=6.5,
            cold_water_source=self.coldwatersource,
            wwhrs=wwhrs,
            wwhrs_configuration=WWHRSConfiguration.WATER_HEATING_SYSTEM,
        )

        # System C doesn't affect hot water demand at the shower (only at the water heater)
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                result = self.mixershower.hot_water_demand(
                    event={
                        "temperature": 40.0,
                        "duration": 5.0,
                        "start": 0,
                        "type": "Shower",
                        "name": "mixer",
                    },
                    func_temp_hot_water=func_temp_hot_water_fixed,
                )[0]
                assert result is not None, (
                    "hot_water_demand returned None when a float was expected"
                )
                self.assertAlmostEqual(
                    result,
                    [24.7, 24.54081632653061, 24.375][t_idx],
                    msg="incorrect volume of hot water returned",
                )

    def test_wwhrs_instantaneousSystemA(self):
        flow_rates = [5, 7, 9, 11, 13]
        system_a_efficiencies = [44.8, 39.1, 34.8, 31.4, 28.6]
        wwhrs = WWHRS_Instantaneous(
            flow_rates=flow_rates,
            system_a_efficiencies=system_a_efficiencies,
            cold_water_source=self.coldwatersource,
            system_a_utilisation_factor=0.7,
        )
        self.mixershower = MixerShower(
            flowrate=6.5, cold_water_source=self.coldwatersource, wwhrs=wwhrs
        )

        # With Technical Recommendations calculations for System A
        # temp_shower = 40°C, temp_hot = 52°C, flowrate = 6.5 L/min
        expected_hot_water = []

        for t_idx in range(3):
            # Cold water temps: [2.0, 3.0, 4.0]
            temp_cold = [2.0, 3.0, 4.0][t_idx]

            # Interpolate efficiency at 6.5 L/min ≈ 40.525%
            # With utilisation factor (0.7): 40.525 * 0.7 = 28.3675%
            # T_drain = 40 - 6 = 34°C
            # T_pre = temp_cold + 0.287 * (34 - temp_cold)

            temp_drain = 34.0
            eta_uf = 0.40525 * 0.7  # ≈ 0.283675
            temp_pre = temp_cold + eta_uf * (temp_drain - temp_cold)

            # Volume of hot water = warm_water * (temp_shower - temp_pre) / (temp_hot - temp_pre)
            vol_warm = 32.5
            vol_hot = vol_warm * (40.0 - temp_pre) / (52.0 - temp_pre)
            print(vol_hot)
            expected_hot_water.append(vol_hot)

        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertAlmostEqual(
                    self.mixershower.hot_water_demand(
                        event={
                            "temperature": 40.0,
                            "duration": 5.0,
                            "start": 0,
                            "type": "Shower",
                            "name": "mixer",
                        },
                        func_temp_hot_water=func_temp_hot_water_fixed,
                    )[0],
                    expected_hot_water[t_idx],
                    places=4,
                    msg="incorrect volume of hot water returned",
                )


class TestInstantElecShower(unittest.TestCase):
    """Unit tests for InstantElecShower class"""

    def setUp(self):
        """Create InstantElecShower object to be tested"""
        self.simtime = SimulationTime(start_time=0, end_time=3, step=1)
        coldwatertemps = [2.0, 3.0, 4.0]
        coldwatersource = ColdWaterSource(
            cold_water_temps=coldwatertemps,
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )
        self.energysupply = EnergySupply(
            fuel_type=FuelType.ELECTRICITY, simulation_time=self.simtime
        )
        energysupplyconn = self.energysupply.connection(end_user_name="shower")
        self.instantelecshower = InstantElecShower(
            rated_power=50, cold_water_source=coldwatersource, elec_supply_conn=energysupplyconn
        )

    def test_hot_water_demand(self):
        """Test that there is a demand on the energy supply connection but that
        that no demand on the water heating system is returned
        """
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.instantelecshower.hot_water_demand(
                    event={
                        "temperature": 40.0,
                        "duration": (t_idx + 1) * 6,
                        "start": 0,
                        "type": "Shower",
                        "name": "instantelec",
                    },
                    func_temp_hot_water=func_temp_hot_water_fixed,
                )
                self.assertEqual(
                    self.energysupply.results_by_end_user()["shower"][t_idx],
                    [5.0, 10.0, 15.0][t_idx],
                    "correct electricity demand not returned",
                )
                self.assertEqual(
                    self.instantelecshower.hot_water_demand(
                        event={
                            "temperature": 40.0,
                            "duration": (t_idx + 1) * 6,
                            "start": 0,
                            "type": "Shower",
                            "name": "instantelec",
                        },
                        func_temp_hot_water=func_temp_hot_water_fixed,
                    )[0],
                    [0.0, 0.0, 0.0][t_idx],
                    "correct hot water demand not returned",
                )

    def test_get_cold_water_source(self):
        self.assertTrue(isinstance(self.instantelecshower.get_cold_water_source(), ColdWaterSource))
