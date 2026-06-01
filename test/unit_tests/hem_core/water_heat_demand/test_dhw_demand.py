#!/usr/bin/env python3

"""
This module contains unit tests for the shower module
"""

import math
import re
import unittest
from typing import cast
from unittest.mock import MagicMock, call

import pytest

# Local imports
from hem_core.energy_supply.energy_supply import EnergySupply
from hem_core.heating_systems.point_of_use import PointOfUse
from hem_core.heating_systems.wwhrs import WWHRS_Instantaneous
from hem_core.input_output.enums import FuelType
from hem_core.simulation_time import SimulationTime
from hem_core.water_heat_demand.cold_water_source import ColdWaterSource
from hem_core.water_heat_demand.dhw_demand import (
    DHWDemand,
    HotWaterSource,
    OutletType,
    PreHeatWaterSource,
    WaterEventResult,
)


class HotWaterSourceMockWithUniqueHotWaterTemperature:
    def get_temp_hot_water(
        self, volume_req: float, volume_req_already: float
    ) -> list[tuple[float, float]]:
        volume_req_cumulative = volume_req + volume_req_already
        return [(55.0, volume_req_cumulative)]


class HotWaterSourceMock:
    def __init__(self, cold_feed: "ColdWaterSource | PreHeatWaterSourceMock"):
        self.cold_feed = cold_feed

    def get_temp_hot_water(
        self, volume_req: float, volume_req_already: float
    ) -> list[tuple[float, float]]:
        volume_req_cumulative = volume_req + volume_req_already
        frac_volume_req_already = volume_req_already / volume_req_cumulative
        frac_layer_1 = max(0.0, 0.6 - frac_volume_req_already)
        frac_layer_2 = 0.4 - max(0.0, frac_volume_req_already - 0.6)

        return [
            (55.0, volume_req_cumulative * frac_layer_1),
            (45.0, volume_req_cumulative * frac_layer_2),
        ]

    def get_cold_water_source(self) -> "ColdWaterSource | PreHeatWaterSourceMock":
        return self.cold_feed

    def demand_hot_water(self, usage_events: list[WaterEventResult]) -> float:
        return math.fsum(e.temperature_warm * e.volume_warm / 4200.0 for e in usage_events)


class PreHeatWaterSourceMock:
    def __init__(self, cold_feed: ColdWaterSource):
        self.cold_feed = cold_feed

    def demand_hot_water(self, usage_events: list[WaterEventResult]) -> None:
        return None

    def get_cold_water_source(self) -> ColdWaterSource:
        return self.cold_feed


class TestDHWDemand(unittest.TestCase):
    """Unit tests for DHWDemand class"""

    def setUp(self):
        """Create DHWDemand object to be tested"""
        self.simtime = SimulationTime(start_time=0, end_time=24, step=1)
        coldwatertemps = [
            2.0,
            3.0,
            4.0,
            2.0,
            3.0,
            4.0,
            2.0,
            3.0,
            4.0,
            2.0,
            3.0,
            4.0,
            2.0,
            3.0,
            4.0,
            2.0,
            3.0,
            4.0,
            2.0,
            3.0,
            4.0,
            2.0,
            3.0,
            4.0,
        ]
        self.coldwatersource = ColdWaterSource(
            cold_water_temps=coldwatertemps,
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )
        self.shower_dict = {
            "mixer": {
                "type": "MixerShower",
                "flowrate": 8.0,
                "ColdWaterSource": "mains water",
                "WWHRS": "Example_Inst_WWHRS",
            },
            "IES": {
                "type": "InstantElecShower",
                "rated_power": 9.0,
                "ColdWaterSource": "mains water",
                "EnergySupply": "mains elec",
            },
        }
        self.baths_dict = {
            "medium": {"size": 100, "ColdWaterSource": "mains water", "flowrate": 8.0}
        }
        self.other_hw_users_dict = {"other": {"flowrate": 8.0, "ColdWaterSource": "mains water"}}
        self.hw_pipework_list = [
            {"location": "internal", "internal_diameter_mm": 30, "length": 10.0},
            {"location": "internal", "internal_diameter_mm": 28, "length": 9.0},
            {"location": "external", "internal_diameter_mm": 32, "length": 5.0},
            {"location": "external", "internal_diameter_mm": 31, "length": 8.0},
        ]

        self.cold_water_sources = {"mains water": self.coldwatersource}

        self.flow_rates = [5, 7, 9, 11, 13]
        self.system_a_efficiencies = [44.8, 39.1, 34.8, 31.4, 28.6]
        self.system_a_utilisation_factor = 0.7
        self.wwhrsb = WWHRS_Instantaneous(
            flow_rates=self.flow_rates,
            system_a_efficiencies=self.system_a_efficiencies,
            cold_water_source=self.coldwatersource,
            system_a_utilisation_factor=self.system_a_utilisation_factor,
            system_b_efficiency_factor=0.81,
        )
        self.wwhrs = {"Example_Inst_WWHRS": self.wwhrsb}
        self.energy_supplies = {
            "_unmet_demand": EnergySupply(
                fuel_type=FuelType.UNMET_DEMAND, simulation_time=self.simtime
            ),
            "mains elec": EnergySupply(
                fuel_type=FuelType.ELECTRICITY, simulation_time=self.simtime
            ),
        }
        self.event_schedules = {
            0: None,
            1: None,
            2: None,
            3: None,
            4: [
                {"start": 4.1, "duration": 6, "temperature": 41.0, "type": "Shower", "name": "IES"},
                {"start": 4.5, "duration": 6, "temperature": 41.0, "type": "Shower", "name": "IES"},
            ],
            5: None,
            6: [
                {"start": 6, "duration": 6, "temperature": 41.0, "type": "Shower", "name": "IES"},
                {
                    "start": 6,
                    "volume": 100.0,
                    "temperature": 41.0,
                    "type": "Bath",
                    "name": "medium",
                },
            ],
            7: [
                {"start": 7, "duration": 6, "temperature": 41.0, "type": "Shower", "name": "mixer"},
                {"start": 7, "duration": 1, "temperature": 41.0, "type": "Other", "name": "other"},
            ],
            8: [
                {"start": 8, "duration": 6, "temperature": 41.0, "type": "Shower", "name": "mixer"},
                {"start": 8, "duration": 3, "temperature": 41.0, "type": "Bath", "name": "medium"},
            ],
            9: None,
            10: None,
            11: None,
            12: None,
            13: None,
            14: None,
            15: None,
            16: None,
            17: None,
            18: None,
            19: None,
            20: None,
            21: None,
            22: None,
            23: None,
        }

        self.dhw_demand = DHWDemand(
            showers_dict=self.shower_dict,
            baths_dict=self.baths_dict,
            other_hw_users_dict=self.other_hw_users_dict,
            hw_pipework_inputs=self.hw_pipework_list,
            cold_water_sources=self.cold_water_sources,
            wwhrs=self.wwhrs,
            energy_supplies=self.energy_supplies,
            event_schedules=self.event_schedules,
            hot_water_sources=cast(
                dict[str, HotWaterSource],
                {
                    "hw cylinder": HotWaterSourceMock(
                        cold_feed=self.cold_water_sources["mains water"]
                    )
                },
            ),
        )

    def test_unmet_demand_connection_failure(self):
        energy_supplies = {
            "mains elec": EnergySupply(
                fuel_type=FuelType.ELECTRICITY, simulation_time=self.simtime
            ),
        }
        with self.assertRaises(ValueError):
            DHWDemand(
                showers_dict=self.shower_dict,
                baths_dict=self.baths_dict,
                other_hw_users_dict=self.other_hw_users_dict,
                hw_pipework_inputs=self.hw_pipework_list,
                cold_water_sources=self.cold_water_sources,
                wwhrs=self.wwhrs,
                energy_supplies=energy_supplies,
                event_schedules=self.event_schedules,
                hot_water_sources=cast(
                    dict[str, HotWaterSource],
                    {
                        "hw cylinder": HotWaterSourceMock(
                            cold_feed=self.cold_water_sources["mains water"]
                        )
                    },
                ),
            )

    def test_hot_water_demand(self):
        self.maxDiff = None
        expected_results = [
            (
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": [], "hw cylinder": []},
            ),
            (
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": [], "hw cylinder": []},
            ),
            (
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": [], "hw cylinder": []},
            ),
            (
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": [], "hw cylinder": []},
            ),
            (
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 12.0, "hw cylinder": 0.0},
                {"_electric_showers": 2, "hw cylinder": 0.0},
                {"_electric_showers": 1.7999999999999998, "hw cylinder": 0.0},
                {
                    "_electric_showers": [
                        WaterEventResult(
                            temperature_warm=41.0,
                            type="Shower",
                            volume_warm=20.378383818053738,
                            volume_hot=0.0,
                            event_duration=6,
                        ),
                        WaterEventResult(
                            temperature_warm=41.0,
                            type="Shower",
                            volume_warm=20.378383818053738,
                            volume_hot=0.0,
                            event_duration=6,
                        ),
                    ],
                    "hw cylinder": [],
                },
            ),
            (
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": [], "hw cylinder": []},
            ),
            (
                {"_electric_showers": 0.0, "hw cylinder": 81.141483189812},
                {"_electric_showers": 6.0, "hw cylinder": 12.5},
                {"_electric_showers": 1.0, "hw cylinder": 1.0},
                {"_electric_showers": 0.9, "hw cylinder": 4.532666666666667},
                {
                    "_electric_showers": [
                        WaterEventResult(
                            temperature_warm=41.0,
                            type="Shower",
                            volume_warm=19.85586115605236,
                            volume_hot=0.0,
                            event_duration=6,
                        ),
                    ],
                    "hw cylinder": [
                        WaterEventResult(
                            temperature_warm=41.0,
                            type="Bath",
                            volume_warm=100,
                            volume_hot=73.58490566037736,
                            event_duration=12.5,
                        ),
                        WaterEventResult(
                            temperature_warm=55.0,
                            type="PipeFlush",
                            volume_warm=7.556577529434648,
                            volume_hot=7.556577529434648,
                            event_duration=0.0,
                        ),
                    ],
                },
            ),
            (
                {"_electric_showers": 0.0, "hw cylinder": 53.58989404060333},
                {"_electric_showers": 0.0, "hw cylinder": 7.0},
                {"_electric_showers": 0.0, "hw cylinder": 2.0},
                {"_electric_showers": 0.0, "hw cylinder": 2.473208888888889},
                {
                    "_electric_showers": [],
                    "hw cylinder": [
                        WaterEventResult(
                            temperature_warm=41.0,
                            type="Shower",
                            volume_warm=48.0,
                            volume_hot=32.63058513558019,
                            event_duration=0.0,
                        ),
                        WaterEventResult(
                            temperature_warm=55.0,
                            type="PipeFlush",
                            volume_warm=7.556577529434648,
                            volume_hot=7.556577529434648,
                            event_duration=0.0,
                        ),
                        WaterEventResult(
                            temperature_warm=41.0,
                            type="PipeFlush",
                            volume_warm=8.0,
                            volume_hot=5.846153846153845,
                            event_duration=0.0,
                        ),
                        WaterEventResult(
                            temperature_warm=55.0,
                            type="PipeFlush",
                            volume_warm=7.556577529434648,
                            volume_hot=7.556577529434648,
                            event_duration=0.0,
                        ),
                    ],
                },
            ),
            (
                {"_electric_showers": 0.0, "hw cylinder": 64.89041357202146},
                {"_electric_showers": 0.0, "hw cylinder": 9.0},
                {"_electric_showers": 0.0, "hw cylinder": 2.0},
                {"_electric_showers": 0.0, "hw cylinder": 3.09616},
                {
                    "_electric_showers": [],
                    "hw cylinder": [
                        WaterEventResult(
                            temperature_warm=41.0,
                            type="PipeFlush",
                            volume_warm=48.0,
                            volume_hot=32.365493807269814,
                            event_duration=0.0,
                        ),
                        WaterEventResult(
                            temperature_warm=55.0,
                            type="PipeFlush",
                            volume_warm=7.556577529434648,
                            volume_hot=7.556577529434648,
                            event_duration=0.0,
                        ),
                        WaterEventResult(
                            temperature_warm=55.0,
                            type="Bath",
                            volume_warm=24.0,
                            volume_hot=17.41176470588235,
                            event_duration=0.0,
                        ),
                        WaterEventResult(
                            temperature_warm=54.99999999999999,
                            type="PipeFlush",
                            volume_warm=7.556577529434648,
                            volume_hot=7.556577529434648,
                            event_duration=0.0,
                        ),
                    ],
                },
            ),
            (
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": [], "hw cylinder": []},
            ),
            (
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": [], "hw cylinder": []},
            ),
            (
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": [], "hw cylinder": []},
            ),
            (
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": [], "hw cylinder": []},
            ),
            (
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": [], "hw cylinder": []},
            ),
            (
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": [], "hw cylinder": []},
            ),
            (
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": [], "hw cylinder": []},
            ),
            (
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": [], "hw cylinder": []},
            ),
            (
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": [], "hw cylinder": []},
            ),
            (
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": [], "hw cylinder": []},
            ),
            (
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": [], "hw cylinder": []},
            ),
            (
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": [], "hw cylinder": []},
            ),
            (
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": [], "hw cylinder": []},
            ),
            (
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": [], "hw cylinder": []},
            ),
            (
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": [], "hw cylinder": []},
            ),
        ]

        energy_supplies = {
            "_unmet_demand": MagicMock(),
            "mains elec": MagicMock(),
        }

        dhw_demand = DHWDemand(
            showers_dict=self.shower_dict,
            baths_dict=self.baths_dict,
            other_hw_users_dict=self.other_hw_users_dict,
            hw_pipework_inputs=self.hw_pipework_list,
            cold_water_sources=self.cold_water_sources,
            wwhrs=self.wwhrs,
            energy_supplies=cast(dict[str, EnergySupply], energy_supplies),
            event_schedules=self.event_schedules,
            hot_water_sources=cast(
                dict[str, HotWaterSource],
                {"hw cylinder": HotWaterSourceMockWithUniqueHotWaterTemperature()},
            ),
        )

        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                result = dhw_demand.hot_water_demand(t_idx=t_idx)
                # For timesteps 7 and 8, use approximate comparison
                if t_idx in [7, 8]:
                    self.assertAlmostEqual(result[0], expected_results[t_idx][0], places=1)
                    self.assertAlmostEqual(result[3], expected_results[t_idx][3], places=1)
                else:
                    self.assertEqual(result, expected_results[t_idx])

    def test_hot_water_demand_unmet(self):
        self.event_schedules[0] = [
            {"start": 0, "volume": 100.0, "temperature": 90.0, "type": "Bath", "name": "medium"},
            {"start": 0, "duration": 6, "temperature": 70.0, "type": "Shower", "name": "mixer"},
            {"start": 0, "duration": 1, "temperature": 80.0, "type": "Other", "name": "other"},
        ]

        energy_supply_unmet_demand = MagicMock()
        energy_supply_unmet_demand_conn = MagicMock()
        energy_supply_unmet_demand.connection.return_value = energy_supply_unmet_demand_conn
        energy_supplies = {
            "_unmet_demand": energy_supply_unmet_demand,
            "mains elec": MagicMock(),
        }
        dhw_demand = DHWDemand(
            showers_dict=self.shower_dict,
            baths_dict=self.baths_dict,
            other_hw_users_dict=self.other_hw_users_dict,
            hw_pipework_inputs=self.hw_pipework_list,
            cold_water_sources=self.cold_water_sources,
            wwhrs=self.wwhrs,
            energy_supplies=cast(dict[str, EnergySupply], energy_supplies),
            event_schedules=self.event_schedules,
            hot_water_sources=cast(
                dict[str, HotWaterSource],
                {"hw cylinder": HotWaterSourceMockWithUniqueHotWaterTemperature()},
            ),
        )

        self.assertEqual(
            dhw_demand.hot_water_demand(t_idx=0),
            (
                {"_electric_showers": 0.0, "hw cylinder": 0.0},
                {"_electric_showers": 0.0, "hw cylinder": 19.5},
                {"_electric_showers": 0.0, "hw cylinder": 3.0},
                {"_electric_showers": 0.0, "hw cylinder": 14.746275555555554},
                {"_electric_showers": [], "hw cylinder": []},
            ),
        )
        energy_supply_unmet_demand_conn.demand_energy.assert_has_calls(
            [
                call(amount_demanded=10.227555555555554),
                call(amount_demanded=3.793493333333333),
                call(amount_demanded=0.7252266666666667),
            ]
        )

    def test_calc_water_heating(self):
        preheatwatersource = PreHeatWaterSourceMock(
            cold_feed=self.cold_water_sources["mains water"]
        )
        hotwatersource = HotWaterSourceMock(cold_feed=preheatwatersource)

        energy_supplies = {
            "_unmet_demand": EnergySupply(
                fuel_type=FuelType.UNMET_DEMAND, simulation_time=self.simtime
            ),
            "mains elec": EnergySupply(
                fuel_type=FuelType.ELECTRICITY, simulation_time=self.simtime
            ),
        }

        dhw_demand = DHWDemand(
            showers_dict=self.shower_dict,
            baths_dict=self.baths_dict,
            other_hw_users_dict=self.other_hw_users_dict,
            hw_pipework_inputs=self.hw_pipework_list,
            cold_water_sources=self.cold_water_sources,
            wwhrs=self.wwhrs,
            energy_supplies=energy_supplies,
            event_schedules=self.event_schedules,
            hot_water_sources=cast(dict[str, HotWaterSource], {"hw cylinder": hotwatersource}),
            pre_heated_water_sources=cast(
                dict[str, PreHeatWaterSource], {"pre-heat tank": preheatwatersource}
            ),
        )

        temp_int_air = 20.0
        temp_ext_air = 5.0

        hw_demand_vol_expected = {
            "hw cylinder": (
                [0.0] * 6 + [87.14841426412852, 58.267631655968856, 72.45826885901587] + [0.0] * 15
            ),
            "_electric_showers": [0.0] * 24,
        }
        hw_duration_expected = {
            "hw cylinder": [0.0] * 6 + [12.5, 7.0, 9.0] + [0.0] * 15,
            "_electric_showers": [0.0] * 4 + [12.0, 0.0, 6.0] + [0.0] * 17,
        }
        no_events_expected = {
            "hw cylinder": [0.0] * 6 + [1, 2, 2] + [0.0] * 15,
            "_electric_showers": [0] * 4 + [2, 0, 1] + [0] * 17,
        }
        hw_energy_demand_expected = {
            "hw cylinder": (
                [0.0] * 6 + [4.532666666666667, 2.473208888888889, 3.09616] + [0.0] * 15
            ),
            "_electric_showers": [0.0] * 4 + [1.7999999999999998, 0.0, 0.9] + [0.0] * 17,
        }
        hw_energy_demand_incl_pipework_loss_expected = {
            "hw cylinder": (
                [0.0] * 6 + [4.91031082679879, 3.2109323644958288, 3.8163186309496315] + [0.0] * 15
            ),
        }
        hw_energy_output_expected = {
            "hw cylinder": (
                [0.0] * 6 + [1.0571538068629902, 0.7085933280116948, 0.864783804202171] + [0.0] * 15
            ),
            "_electric_showers": [0.0] * 24,
        }
        dist_pw_losses_expected = {
            "hw cylinder": (
                [0.0] * 6
                + [0.2780167312270571, 0.5560334624541142, 0.5560334624541142]
                + [0.0] * 15
            ),
            "_electric_showers": [0.0] * 24,
        }
        primary_pw_losses_expected = {
            "hw cylinder": [0.0] * 24,
            "_electric_showers": [0.0] * 24,
        }
        storage_losses_expected = {
            "hw cylinder": [0.0] * 24,
            "_electric_showers": [0.0] * 24,
        }
        gains_internal_dhw_expected = {
            "hw cylinder": (
                [0.0] * 6 + [732.3002698651746, 585.9605397303493, 683.5872063970161] + [0.0] * 15
            ),
            "_electric_showers": (
                [0.0] * 4 + [248.68421052631578, 0.0, 121.15384615384616] + [0.0] * 17
            ),
        }

        for t_idx, _, timestep in self.simtime:
            (
                hw_demand_vol,
                hw_duration,
                no_events,
                hw_energy_demand,
                hw_energy_demand_incl_pipework_loss,
                hw_energy_output,
                dist_pw_losses,
                primary_pw_losses,
                storage_losses,
                gains_internal_dhw,
            ) = dhw_demand.calc_water_heating(
                t_idx=t_idx,
                timestep=timestep,
                internal_air_temperature=temp_int_air,
                external_air_temperature=temp_ext_air,
            )

            for hws_name in ["hw cylinder", "_electric_showers"]:
                self.assertAlmostEqual(
                    hw_demand_vol[hws_name],
                    hw_demand_vol_expected[hws_name][t_idx],
                    msg=f"Incorrect hot water demand volume for {hws_name} in timestep {t_idx}",
                )
                self.assertAlmostEqual(
                    hw_duration[hws_name],
                    hw_duration_expected[hws_name][t_idx],
                    msg=f"Incorrect hot water duration for {hws_name} in timestep {t_idx}",
                )
                self.assertAlmostEqual(
                    no_events[hws_name],
                    no_events_expected[hws_name][t_idx],
                    msg=f"Incorrect number of hot water events for {hws_name} in timestep {t_idx}",
                )
                self.assertAlmostEqual(
                    hw_energy_demand[hws_name],
                    hw_energy_demand_expected[hws_name][t_idx],
                    msg=f"Incorrect hot water demand energy for {hws_name} in timestep {t_idx}",
                )
                self.assertAlmostEqual(
                    dist_pw_losses[hws_name],
                    dist_pw_losses_expected[hws_name][t_idx],
                    msg=f"Incorrect hot water distribution pipework losses for {hws_name} in timestep {t_idx}",
                )
                self.assertAlmostEqual(
                    gains_internal_dhw[hws_name],
                    gains_internal_dhw_expected[hws_name][t_idx],
                    msg=f"Incorrect hot water internal gains for {hws_name} in timestep {t_idx}",
                )

            self.assertAlmostEqual(
                hw_energy_demand_incl_pipework_loss["hw cylinder"],
                hw_energy_demand_incl_pipework_loss_expected["hw cylinder"][t_idx],
                msg=f"Incorrect hot water demand energy incl. pipework losses in timestep {t_idx}",
            )
            self.assertAlmostEqual(
                hw_energy_output["hw cylinder"],
                hw_energy_output_expected["hw cylinder"][t_idx],
                msg=f"Incorrect hot water energy output in timestep {t_idx}",
            )
            self.assertAlmostEqual(
                primary_pw_losses["hw cylinder"],
                primary_pw_losses_expected["hw cylinder"][t_idx],
                msg=f"Incorrect primary pipework losses in timestep {t_idx}",
            )
            self.assertAlmostEqual(
                storage_losses["hw cylinder"],
                storage_losses_expected["hw cylinder"][t_idx],
                msg=f"Incorrect hot water storage losses in timestep {t_idx}",
            )

    def test_calc_water_heating_with_internal_gains(self):
        class HotWaterSourceMockWithInternalGains(HotWaterSourceMock):
            def __init__(self, cold_feed: ColdWaterSource):
                super().__init__(cold_feed)

            def internal_gains(self) -> float:
                return 20.0

            def get_losses_from_primary_pipework_and_storage(self) -> tuple[float, float]:
                return (5.0, 15.0)

        hotwatersource = HotWaterSourceMockWithInternalGains(
            cold_feed=self.cold_water_sources["mains water"]
        )

        energy_supplies = {
            "_unmet_demand": EnergySupply(
                fuel_type=FuelType.UNMET_DEMAND, simulation_time=self.simtime
            ),
            "mains elec": EnergySupply(
                fuel_type=FuelType.ELECTRICITY, simulation_time=self.simtime
            ),
        }

        dhw_demand = DHWDemand(
            showers_dict=self.shower_dict,
            baths_dict=self.baths_dict,
            other_hw_users_dict=self.other_hw_users_dict,
            hw_pipework_inputs=self.hw_pipework_list,
            cold_water_sources=self.cold_water_sources,
            wwhrs=self.wwhrs,
            energy_supplies=energy_supplies,
            event_schedules=self.event_schedules,
            hot_water_sources=cast(dict[str, HotWaterSource], {"hw cylinder": hotwatersource}),
            pre_heated_water_sources=None,
        )

        temp_int_air = 20.0
        temp_ext_air = 5.0

        hw_demand_vol_expected = {
            "hw cylinder": (
                [0.0] * 6 + [87.14841426412852, 58.267631655968856, 72.45826885901587] + [0.0] * 15
            ),
            "_electric_showers": [0.0] * 24,
        }
        hw_duration_expected = {
            "hw cylinder": [0.0] * 6 + [12.5, 7.0, 9.0] + [0.0] * 15,
            "_electric_showers": [0.0] * 4 + [12.0, 0.0, 6.0] + [0.0] * 17,
        }
        no_events_expected = {
            "hw cylinder": [0.0] * 6 + [1, 2, 2] + [0.0] * 15,
            "_electric_showers": [0] * 4 + [2, 0, 1] + [0] * 17,
        }
        hw_energy_demand_expected = {
            "hw cylinder": (
                [0.0] * 6 + [4.532666666666667, 2.473208888888889, 3.09616] + [0.0] * 15
            ),
            "_electric_showers": [0.0] * 4 + [1.7999999999999998, 0.0, 0.9] + [0.0] * 17,
        }
        hw_energy_demand_incl_pipework_loss_expected = {
            "hw cylinder": (
                [0.0] * 6 + [4.91031082679879, 3.2109323644958288, 3.8163186309496315] + [0.0] * 15
            ),
        }
        hw_energy_output_expected = {
            "hw cylinder": (
                [0.0] * 6 + [1.0571538068629902, 0.7085933280116948, 0.864783804202171] + [0.0] * 15
            ),
            "_electric_showers": [0.0] * 24,
        }
        dist_pw_losses_expected = {
            "hw cylinder": (
                [0.0] * 6
                + [0.2780167312270571, 0.5560334624541142, 0.5560334624541142]
                + [0.0] * 15
            ),
            "_electric_showers": [0.0] * 24,
        }
        primary_pw_losses_expected = {
            "hw cylinder": [5.0] * 24,
            "_electric_showers": [0.0] * 24,
        }
        storage_losses_expected = {
            "hw cylinder": [15.0] * 24,
            "_electric_showers": [0.0] * 24,
        }
        gains_internal_dhw_expected = {
            "hw cylinder": (
                [20.0] * 4
                + [20.0, 20.0, 752.3002698651746, 605.9605397303493, 703.5872063970161]
                + [20.0] * 15
            ),
            "_electric_showers": (
                [0.0] * 4 + [248.68421052631578, 0.0, 121.15384615384616] + [0.0] * 17
            ),
        }

        for t_idx, _, timestep in self.simtime:
            (
                hw_demand_vol,
                hw_duration,
                no_events,
                hw_energy_demand,
                hw_energy_demand_incl_pipework_loss,
                hw_energy_output,
                dist_pw_losses,
                primary_pw_losses,
                storage_losses,
                gains_internal_dhw,
            ) = dhw_demand.calc_water_heating(
                t_idx=t_idx,
                timestep=timestep,
                internal_air_temperature=temp_int_air,
                external_air_temperature=temp_ext_air,
            )

            for hws_name in ["hw cylinder", "_electric_showers"]:
                self.assertAlmostEqual(
                    hw_demand_vol[hws_name],
                    hw_demand_vol_expected[hws_name][t_idx],
                    msg=f"Incorrect hot water demand volume for {hws_name} in timestep {t_idx}",
                )
                self.assertAlmostEqual(
                    hw_duration[hws_name],
                    hw_duration_expected[hws_name][t_idx],
                    msg=f"Incorrect hot water duration for {hws_name} in timestep {t_idx}",
                )
                self.assertAlmostEqual(
                    no_events[hws_name],
                    no_events_expected[hws_name][t_idx],
                    msg=f"Incorrect number of hot water events for {hws_name} in timestep {t_idx}",
                )
                self.assertAlmostEqual(
                    hw_energy_demand[hws_name],
                    hw_energy_demand_expected[hws_name][t_idx],
                    msg=f"Incorrect hot water demand energy for {hws_name} in timestep {t_idx}",
                )
                self.assertAlmostEqual(
                    dist_pw_losses[hws_name],
                    dist_pw_losses_expected[hws_name][t_idx],
                    msg=f"Incorrect hot water distribution pipework losses for {hws_name} in timestep {t_idx}",
                )
                self.assertAlmostEqual(
                    gains_internal_dhw[hws_name],
                    gains_internal_dhw_expected[hws_name][t_idx],
                    msg=f"Incorrect hot water internal gains for {hws_name} in timestep {t_idx}",
                )

            self.assertAlmostEqual(
                hw_energy_demand_incl_pipework_loss["hw cylinder"],
                hw_energy_demand_incl_pipework_loss_expected["hw cylinder"][t_idx],
                msg=f"Incorrect hot water demand energy incl. pipework losses in timestep {t_idx}",
            )
            self.assertAlmostEqual(
                hw_energy_output["hw cylinder"],
                hw_energy_output_expected["hw cylinder"][t_idx],
                msg=f"Incorrect hot water energy output in timestep {t_idx}",
            )
            self.assertAlmostEqual(
                primary_pw_losses["hw cylinder"],
                primary_pw_losses_expected["hw cylinder"][t_idx],
                msg=f"Incorrect primary pipework losses in timestep {t_idx}",
            )
            self.assertAlmostEqual(
                storage_losses["hw cylinder"],
                storage_losses_expected["hw cylinder"][t_idx],
                msg=f"Incorrect hot water storage losses in timestep {t_idx}",
            )

    def test_calc_pipework_losses(self):
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.dhw_demand.calc_pipework_losses(
                        hot_water_source_name="hw cylinder",
                        no_of_hot_water_events=[
                            0,
                            0,
                            0,
                            2,
                            0,
                            2,
                            2,
                            2,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                        ][t_idx],
                        demand_water_temperature=[
                            55.0,
                            55.0,
                            55.0,
                            57.0,
                            55.0,
                            58.0,
                            60.0,
                            40.0,
                            55.0,
                            55.0,
                            55.0,
                            55.0,
                            55.0,
                            55.0,
                            55.0,
                            55.0,
                            55.0,
                            55.0,
                            55.0,
                            55.0,
                            55.0,
                            55.0,
                            55.0,
                            55.0,
                        ][t_idx],
                        internal_air_temperature=20.0,
                        external_air_temperature=5.0,
                    ),
                    [
                        (0.0, 0.0),
                        (0.0, 0.0),
                        (0.0, 0.0),
                        (0.3615154654675836, 0.4052961328742277),
                        (0.0, 0.0),
                        (0.3712861537234643, 0.41309028927565516),
                        (0.3908275302352256, 0.42867860207851005),
                        (0.1954137651176128, 0.27279547404996096),
                        (0.0, 0.0),
                        (0.0, 0.0),
                        (0.0, 0.0),
                        (0.0, 0.0),
                        (0.0, 0.0),
                        (0.0, 0.0),
                        (0.0, 0.0),
                        (0.0, 0.0),
                        (0.0, 0.0),
                        (0.0, 0.0),
                        (0.0, 0.0),
                        (0.0, 0.0),
                        (0.0, 0.0),
                        (0.0, 0.0),
                        (0.0, 0.0),
                        (0.0, 0.0),
                    ][t_idx],
                )

    def test_calc_pipework_losses_with_no_pipework(self):
        self.energy_supplies = {
            "_unmet_demand": EnergySupply(
                fuel_type=FuelType.UNMET_DEMAND, simulation_time=self.simtime
            ),
            "mains elec": EnergySupply(
                fuel_type=FuelType.ELECTRICITY, simulation_time=self.simtime
            ),
        }
        hw_pipework_list = []

        dhw_demand = DHWDemand(
            showers_dict=self.shower_dict,
            baths_dict=self.baths_dict,
            other_hw_users_dict=self.other_hw_users_dict,
            hw_pipework_inputs=hw_pipework_list,
            cold_water_sources=self.cold_water_sources,
            wwhrs=self.wwhrs,
            energy_supplies=self.energy_supplies,
            event_schedules=self.event_schedules,
            hot_water_sources=cast(
                dict[str, HotWaterSource],
                {
                    "hw cylinder": HotWaterSourceMock(
                        cold_feed=self.cold_water_sources["mains water"]
                    )
                },
            ),
        )

        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    dhw_demand.calc_pipework_losses(
                        hot_water_source_name="hw cylinder",
                        no_of_hot_water_events=0,
                        demand_water_temperature=55.0,
                        internal_air_temperature=20.0,
                        external_air_temperature=5.0,
                    ),
                    (0.0, 0.0),
                )

    def test_calc_pipework_losses_with_invalid_location(self):
        pipework = MagicMock()
        pipework.location.return_value = "UNKNOWN_LOCATION"
        pipework._Pipework_Simple__location = "UNKNOWN_LOCATION"
        self.dhw_demand._DHWDemand__hw_distribution_pipework = {"hw cylinder": [pipework]}  # type: ignore[AttributeAccessIssue]

        expected_message = "Unexpected location value: UNKNOWN_LOCATION"
        with pytest.raises(ValueError, match=expected_message):
            self.dhw_demand.calc_pipework_losses(
                hot_water_source_name="hw cylinder",
                no_of_hot_water_events=0,
                demand_water_temperature=55.0,
                internal_air_temperature=20.0,
                external_air_temperature=5.0,
            )

    def test_init_distribution_pointofuse(self):
        self.energy_supplies = {
            "_unmet_demand": EnergySupply(
                fuel_type=FuelType.UNMET_DEMAND, simulation_time=self.simtime
            ),
            "mains elec": EnergySupply(
                fuel_type=FuelType.ELECTRICITY, simulation_time=self.simtime
            ),
        }
        hw_pipework_list = {}

        dhw_demand = DHWDemand(
            showers_dict=self.shower_dict,
            baths_dict=self.baths_dict,
            other_hw_users_dict=self.other_hw_users_dict,
            hw_pipework_inputs=hw_pipework_list,
            cold_water_sources=self.cold_water_sources,
            wwhrs=self.wwhrs,
            energy_supplies=self.energy_supplies,
            event_schedules=self.event_schedules,
            hot_water_sources=cast(
                dict[str, HotWaterSource],
                {
                    "pou": PointOfUse(
                        efficiency=1.0,
                        energy_supply_conn=MagicMock(),
                        simulation_time=MagicMock(),
                        cold_feed=MagicMock(),
                        temp_hot_water=MagicMock(),
                    )
                },
            ),
        )
        assert dhw_demand._DHWDemand__hw_distribution_pipework["pou"] == []  # type: ignore[AttributeAccessIssue]

    def test_init_distribution_missing_dict(self):
        self.energy_supplies = {
            "_unmet_demand": EnergySupply(
                fuel_type=FuelType.UNMET_DEMAND, simulation_time=self.simtime
            ),
            "mains elec": EnergySupply(
                fuel_type=FuelType.ELECTRICITY, simulation_time=self.simtime
            ),
        }
        hw_pipework_list = {}

        expected_message = "Distribution pipework not specified for HotWaterSource: hw cylinder"
        with pytest.raises(ValueError, match=expected_message):
            DHWDemand(
                showers_dict=self.shower_dict,
                baths_dict=self.baths_dict,
                other_hw_users_dict=self.other_hw_users_dict,
                hw_pipework_inputs=hw_pipework_list,
                cold_water_sources=self.cold_water_sources,
                wwhrs=self.wwhrs,
                energy_supplies=self.energy_supplies,
                event_schedules=self.event_schedules,
                hot_water_sources=cast(
                    dict[str, HotWaterSource],
                    {
                        "hw cylinder": HotWaterSourceMock(
                            cold_feed=self.cold_water_sources["mains water"]
                        )
                    },
                ),
            )

    def test_init_distribution_part_missing_list(self):
        self.energy_supplies = {
            "_unmet_demand": EnergySupply(
                fuel_type=FuelType.UNMET_DEMAND, simulation_time=self.simtime
            ),
            "mains elec": EnergySupply(
                fuel_type=FuelType.ELECTRICITY, simulation_time=self.simtime
            ),
        }
        hw_pipework_list = []

        expected_message = "If more than one HotWaterSource is defined, then distribution pipework must be defined for each one"
        with pytest.raises(ValueError, match=expected_message):
            DHWDemand(
                showers_dict=self.shower_dict,
                baths_dict=self.baths_dict,
                other_hw_users_dict=self.other_hw_users_dict,
                hw_pipework_inputs=hw_pipework_list,
                cold_water_sources=self.cold_water_sources,
                wwhrs=self.wwhrs,
                energy_supplies=self.energy_supplies,
                event_schedules=self.event_schedules,
                hot_water_sources=cast(
                    dict[str, HotWaterSource],
                    {
                        "hw cylinder": HotWaterSourceMock(
                            cold_feed=self.cold_water_sources["mains water"]
                        ),
                        "combi": HotWaterSourceMock(
                            cold_feed=self.cold_water_sources["mains water"]
                        ),
                    },
                ),
            )

    def test_init_distribution_extra(self):
        self.energy_supplies = {
            "_unmet_demand": EnergySupply(
                fuel_type=FuelType.UNMET_DEMAND, simulation_time=self.simtime
            ),
            "mains elec": EnergySupply(
                fuel_type=FuelType.ELECTRICITY, simulation_time=self.simtime
            ),
        }
        hw_pipework_list = {"hw cylinder": [], "extra": []}

        expected_message = re.escape(
            "Distribution pipework defined for non-existent HotWaterSource(s): ['extra']"
        )
        with pytest.raises(ValueError, match=expected_message):
            DHWDemand(
                showers_dict=self.shower_dict,
                baths_dict=self.baths_dict,
                other_hw_users_dict=self.other_hw_users_dict,
                hw_pipework_inputs=hw_pipework_list,
                cold_water_sources=self.cold_water_sources,
                wwhrs=self.wwhrs,
                energy_supplies=self.energy_supplies,
                event_schedules=self.event_schedules,
                hot_water_sources=cast(
                    dict[str, HotWaterSource],
                    {
                        "hw cylinder": HotWaterSourceMock(
                            cold_feed=self.cold_water_sources["mains water"]
                        )
                    },
                ),
            )

    def test_init_invalid_shower_type(self):
        """Test that invalid shower type raises ValueError"""
        expected_message = "Shower 'shower1': Invalid shower type 'InvalidShowerType'"
        with pytest.raises(ValueError, match=expected_message):
            DHWDemand(
                showers_dict={
                    "shower1": {"type": "InvalidShowerType", "ColdWaterSource": "mains water"}
                },
                baths_dict={},
                other_hw_users_dict={},
                hw_pipework_inputs={},
                cold_water_sources={"mains water": self.coldwatersource},
                wwhrs={},
                energy_supplies={},
                event_schedules={},
                hot_water_sources=cast(
                    dict[str, HotWaterSource],
                    {
                        "hw cylinder": HotWaterSourceMock(
                            cold_feed=self.cold_water_sources["mains water"]
                        )
                    },
                ),
            )

    def test_init_invalid_wwhrs_name_shower(self):
        """Test that invalid WWHRS name raises ValueError"""
        expected_message = "Shower 'shower1': WWHRS 'invalid_name' not found"
        with pytest.raises(ValueError, match=expected_message):
            DHWDemand(
                showers_dict={
                    "shower1": {
                        "type": "MixerShower",
                        "ColdWaterSource": "mains water",
                        "WWHRS": "invalid_name",
                    }
                },
                baths_dict={},
                other_hw_users_dict={},
                hw_pipework_inputs={},
                cold_water_sources={"mains water": self.coldwatersource},
                wwhrs={},
                energy_supplies={},
                event_schedules={},
                hot_water_sources=cast(
                    dict[str, HotWaterSource],
                    {
                        "hw cylinder": HotWaterSourceMock(
                            cold_feed=self.cold_water_sources["mains water"]
                        )
                    },
                ),
            )

    def test_init_invalid_energysupply_name_shower(self):
        """Test that invalid EnergySupply name raised ValueError"""
        expected_message = "Shower 'shower1': Energy supply 'invalid_name' not found"
        with pytest.raises(ValueError, match=expected_message):
            DHWDemand(
                showers_dict={
                    "shower1": {
                        "type": "InstantElecShower",
                        "ColdWaterSource": "mains water",
                        "EnergySupply": "invalid_name",
                    }
                },
                baths_dict={},
                other_hw_users_dict={},
                hw_pipework_inputs={},
                cold_water_sources={"mains water": self.coldwatersource},
                wwhrs={},
                energy_supplies={},
                event_schedules={},
                hot_water_sources=cast(
                    dict[str, HotWaterSource],
                    {
                        "hw cylinder": HotWaterSourceMock(
                            cold_feed=self.cold_water_sources["mains water"]
                        )
                    },
                ),
            )

    def test_init_missing_cold_water_source_shower(self):
        """Test that missing cold water source for shower raises ValueError"""
        expected_message = "Invalid cold water source name for shower shower1: nonexistent"
        with pytest.raises(ValueError, match=expected_message):
            DHWDemand(
                showers_dict={"shower1": {"type": "MixerShower", "ColdWaterSource": "nonexistent"}},
                baths_dict={},
                other_hw_users_dict={},
                hw_pipework_inputs={},
                cold_water_sources={"mains water": self.coldwatersource},
                wwhrs={},
                energy_supplies={},
                event_schedules={},
                hot_water_sources=cast(
                    dict[str, HotWaterSource],
                    {
                        "hw cylinder": HotWaterSourceMock(
                            cold_feed=self.cold_water_sources["mains water"]
                        )
                    },
                ),
            )

    def test_init_missing_cold_water_source_bath(self):
        """Test that missing cold water source for bath raises ValueError"""
        expected_message = "Bath 'bath1': Cold water source 'nonexistent' not found"
        with pytest.raises(ValueError, match=expected_message):
            DHWDemand(
                showers_dict={},
                baths_dict={"bath1": {"ColdWaterSource": "nonexistent"}},
                other_hw_users_dict={},
                hw_pipework_inputs={},
                cold_water_sources={"mains water": self.coldwatersource},
                wwhrs={},
                energy_supplies={},
                event_schedules={},
                hot_water_sources=cast(
                    dict[str, HotWaterSource],
                    {
                        "hw cylinder": HotWaterSourceMock(
                            cold_feed=self.cold_water_sources["mains water"]
                        )
                    },
                ),
            )

    def test_init_missing_cold_water_source_other_water_use(self):
        """Test that missing cold water source for other water use raises ValueError"""
        expected_message = "Other water use 'other1': Cold water source 'nonexistent' not found"
        with pytest.raises(ValueError, match=expected_message):
            DHWDemand(
                showers_dict={},
                baths_dict={},
                other_hw_users_dict={"other1": {"ColdWaterSource": "nonexistent"}},
                hw_pipework_inputs={},
                cold_water_sources={"mains water": self.coldwatersource},
                wwhrs={},
                energy_supplies={},
                event_schedules={},
                hot_water_sources=cast(
                    dict[str, HotWaterSource],
                    {
                        "hw cylinder": HotWaterSourceMock(
                            cold_feed=self.cold_water_sources["mains water"]
                        )
                    },
                ),
            )

    def test_create_water_distribution_pipework_no_tapping_points(self):
        """Test that creating pipework with no tapping points raises ValueError"""
        with pytest.raises(
            ValueError, match="Cannot create pipework: no hot water tapping points defined"
        ):
            DHWDemand(
                showers_dict={},
                baths_dict={},
                other_hw_users_dict={},
                hw_pipework_inputs=self.hw_pipework_list,
                cold_water_sources={"cold1": self.coldwatersource},
                wwhrs={},
                energy_supplies={},
                event_schedules={},
                hot_water_sources=cast(
                    dict[str, HotWaterSource],
                    {
                        "hw cylinder": HotWaterSourceMock(
                            cold_feed=self.cold_water_sources["mains water"]
                        )
                    },
                ),
            )

    def test_hot_water_demand_with_other_event_new_temp(self):
        """Test hot water demand with Other event at new temperature for coverage"""
        # Create a custom event schedule with an "Other" event at a unique temperature
        event_schedules_with_other = {
            0: None,
            1: None,
            2: None,
            3: None,
            4: None,
            5: None,
            6: None,
            7: None,
            8: None,
            9: None,
            10: None,
            11: None,
            12: None,
            13: [
                {"start": 13, "duration": 2, "temperature": 38.0, "type": "Other", "name": "other"}
            ],
            14: None,
            15: None,
            16: None,
            17: None,
            18: None,
            19: None,
            20: None,
            21: None,
            22: None,
            23: None,
        }

        # Create fresh energy supplies to avoid connection conflicts
        fresh_energy_supplies = {
            "_unmet_demand": EnergySupply(
                fuel_type=FuelType.UNMET_DEMAND, simulation_time=self.simtime
            ),
            "mains elec": EnergySupply(
                fuel_type=FuelType.ELECTRICITY, simulation_time=self.simtime
            ),
        }

        # Create a new DHWDemand instance with the custom event schedule
        dhw_demand_other = DHWDemand(
            showers_dict=self.shower_dict,
            baths_dict=self.baths_dict,
            other_hw_users_dict=self.other_hw_users_dict,
            hw_pipework_inputs=self.hw_pipework_list,
            cold_water_sources=self.cold_water_sources,
            wwhrs=self.wwhrs,
            energy_supplies=fresh_energy_supplies,
            event_schedules=event_schedules_with_other,
            hot_water_sources=cast(
                dict[str, HotWaterSource],
                {"hw cylinder": HotWaterSourceMockWithUniqueHotWaterTemperature()},
            ),
        )

        # Test timestep 13 with Other event
        result = dhw_demand_other.hot_water_demand(t_idx=13)
        # Verify that the Other event was processed
        self.assertIsNotNone(result[4]["hw cylinder"])  # events list should not be None
        self.assertEqual(len(result[4]["hw cylinder"]), 2)  # should have 1 event + 1 pipe flush
        self.assertEqual(result[4]["hw cylinder"][0].type, "Other")

    def test_hot_water_demand_mixer_new_temp(self):
        """Test mixer shower with new temperature for coverage of line 186"""
        # Create event schedule with mixer shower at a unique temperature
        event_schedules_mixer_new = {
            0: None,
            1: None,
            2: None,
            3: None,
            4: None,
            5: None,
            6: None,
            7: None,
            8: None,
            9: None,
            10: None,
            11: None,
            12: None,
            13: None,
            14: [
                {"start": 14, "duration": 5, "temperature": 43.0, "type": "Shower", "name": "mixer"}
            ],
            15: None,
            16: None,
            17: None,
            18: None,
            19: None,
            20: None,
            21: None,
            22: None,
            23: None,
        }

        # Create fresh energy supplies to avoid connection conflicts
        fresh_energy_supplies = {
            "_unmet_demand": EnergySupply(
                fuel_type=FuelType.UNMET_DEMAND, simulation_time=self.simtime
            ),
            "mains elec": EnergySupply(
                fuel_type=FuelType.ELECTRICITY, simulation_time=self.simtime
            ),
        }

        # Create a new DHWDemand instance with the custom event schedule
        dhw_demand_mixer = DHWDemand(
            showers_dict=self.shower_dict,
            baths_dict=self.baths_dict,
            other_hw_users_dict=self.other_hw_users_dict,
            hw_pipework_inputs=self.hw_pipework_list,
            cold_water_sources=self.cold_water_sources,
            wwhrs=self.wwhrs,
            energy_supplies=fresh_energy_supplies,
            event_schedules=event_schedules_mixer_new,
            hot_water_sources=cast(
                dict[str, HotWaterSource],
                {"hw cylinder": HotWaterSourceMockWithUniqueHotWaterTemperature()},
            ),
        )

        # Test timestep 14 with mixer shower at new temperature
        result = dhw_demand_mixer.hot_water_demand(t_idx=14)
        # Verify that the mixer shower event was processed
        self.assertIsNotNone(result[4]["hw cylinder"])  # events list should not be None
        self.assertEqual(len(result[4]["hw cylinder"]), 2)  # should have 1 event + 1 pipe flush
        self.assertEqual(result[4]["hw cylinder"][0].type, "Shower")

    def test_hot_water_demand_multiple_mixer_same_temp(self):
        """Test multiple mixer showers with same temperature for line 186 coverage"""
        # Create event schedule with multiple mixer showers at same temperature in same timestep
        event_schedules_multi_mixer = {
            0: None,
            1: None,
            2: None,
            3: None,
            4: None,
            5: None,
            6: None,
            7: None,
            8: None,
            9: None,
            10: None,
            11: None,
            12: None,
            13: [
                {
                    "start": 13,
                    "duration": 3,
                    "temperature": 42.0,
                    "type": "Shower",
                    "name": "mixer",
                },
                {
                    "start": 13.2,
                    "duration": 2,
                    "temperature": 42.0,
                    "type": "Shower",
                    "name": "mixer",
                },
            ],
            14: None,
            15: None,
            16: None,
            17: None,
            18: None,
            19: None,
            20: None,
            21: None,
            22: None,
            23: None,
        }

        # Create fresh energy supplies to avoid connection conflicts
        fresh_energy_supplies = {
            "_unmet_demand": EnergySupply(
                fuel_type=FuelType.UNMET_DEMAND, simulation_time=self.simtime
            ),
            "mains elec": EnergySupply(
                fuel_type=FuelType.ELECTRICITY, simulation_time=self.simtime
            ),
        }

        # Create a new DHWDemand instance with the custom event schedule
        dhw_demand_multi = DHWDemand(
            showers_dict=self.shower_dict,
            baths_dict=self.baths_dict,
            other_hw_users_dict=self.other_hw_users_dict,
            hw_pipework_inputs=self.hw_pipework_list,
            cold_water_sources=self.cold_water_sources,
            wwhrs=self.wwhrs,
            energy_supplies=fresh_energy_supplies,
            event_schedules=event_schedules_multi_mixer,
            hot_water_sources=cast(
                dict[str, HotWaterSource],
                {"hw cylinder": HotWaterSourceMockWithUniqueHotWaterTemperature()},
            ),
        )

        # Test timestep 13 with multiple mixer showers at same temperature
        result = dhw_demand_multi.hot_water_demand(t_idx=13)

        # Verify that both mixer shower events were processed
        self.assertIsNotNone(result[4]["hw cylinder"])  # events list should not be None
        self.assertEqual(len(result[4]["hw cylinder"]), 4)  # should have 2 events + 2 pipe flushes
        self.assertEqual(result[4]["hw cylinder"][0].type, "Shower")
        self.assertEqual(result[4]["hw cylinder"][1].type, "PipeFlush")
        self.assertEqual(result[4]["hw cylinder"][2].type, "Shower")
        self.assertEqual(result[4]["hw cylinder"][3].type, "PipeFlush")

    def test_hot_water_demand_invalid_events(self):
        event_schedules = {
            0: None,
            1: None,
            2: None,
            3: None,
            4: None,
            5: None,
            6: None,
            7: None,
            8: None,
            9: None,
            10: None,
            11: None,
            12: None,
            13: [
                {
                    "start": 13,
                    "duration": 3,
                    "temperature": 42.0,
                    "type": "Invalid_type",
                    "name": "mixer",
                },
            ],
            14: [
                {
                    "start": 14,
                    "duration": 5,
                    "temperature": 43.0,
                    "type": "Shower",
                    "name": "invalid_name",
                }
            ],
            15: None,
            16: None,
            17: None,
            18: None,
            19: None,
            20: None,
            21: None,
            22: None,
            23: None,
        }

        # Create fresh energy supplies to avoid connection conflicts
        fresh_energy_supplies = {
            "_unmet_demand": EnergySupply(
                fuel_type=FuelType.UNMET_DEMAND, simulation_time=self.simtime
            ),
            "mains elec": EnergySupply(
                fuel_type=FuelType.ELECTRICITY, simulation_time=self.simtime
            ),
        }

        # Create a new DHWDemand instance with the custom event schedule
        dhw_demand = DHWDemand(
            showers_dict=self.shower_dict,
            baths_dict=self.baths_dict,
            other_hw_users_dict=self.other_hw_users_dict,
            hw_pipework_inputs=self.hw_pipework_list,
            cold_water_sources=self.cold_water_sources,
            wwhrs=self.wwhrs,
            energy_supplies=fresh_energy_supplies,
            event_schedules=event_schedules,
            hot_water_sources={"hw cylinder": MagicMock(spec=HotWaterSource)},
        )

        # Test timestep 13 and 14
        with self.assertRaises(ValueError):
            dhw_demand.hot_water_demand(t_idx=13)
        with self.assertRaises(ValueError):
            dhw_demand.hot_water_demand(t_idx=14)

    def test_hot_water_source_assignment(self):
        # Use unique, minimal test data
        showers_dict = {
            "sh2": {
                "type": "MixerShower",
                "flowrate": 8.0,
                "ColdWaterSource": "cw2",
                "HotWaterSource": "hw_cylinder",
            }
        }
        baths_dict = {}
        other_hw_users_dict = {
            "oth1": {"flowrate": 10.0, "ColdWaterSource": "cw2", "HotWaterSource": "combi_boiler"}
        }
        hw_pipework_list = {"hw_cylinder": [], "combi_boiler": []}
        cold_water_sources = {"cw2": self.coldwatersource}
        wwhrs = {}
        energy_supplies = {
            "es2": EnergySupply(fuel_type=FuelType.ELECTRICITY, simulation_time=self.simtime),
            "_unmet_demand": EnergySupply(
                fuel_type=FuelType.UNMET_DEMAND, simulation_time=self.simtime
            ),
        }
        event_schedules = {}
        dhw = DHWDemand(
            showers_dict=showers_dict,
            baths_dict=baths_dict,
            other_hw_users_dict=other_hw_users_dict,
            hw_pipework_inputs=hw_pipework_list,
            cold_water_sources=cold_water_sources,
            wwhrs=wwhrs,
            energy_supplies=energy_supplies,
            event_schedules=event_schedules,
            hot_water_sources={
                "hw_cylinder": MagicMock(spec=HotWaterSource),
                "combi_boiler": MagicMock(spec=HotWaterSource),
            },
        )
        assert dhw._DHWDemand__source_supplying_outlet[(OutletType.SHOWER, "sh2")] == "hw_cylinder"  # type: ignore[AttributeAccessIssue]
        assert dhw._DHWDemand__source_supplying_outlet[(OutletType.OTHER, "oth1")] == "combi_boiler"  # type: ignore[AttributeAccessIssue]

    def test_default_hot_water_source_assignment(self):
        """Test default HotWaterSource is used if outlet does not specify one."""
        # Use unique, minimal test data
        showers_dict = {"sh3": {"type": "MixerShower", "flowrate": 8.0, "ColdWaterSource": "cw3"}}
        baths_dict = {}
        other_hw_users_dict = {}
        hw_pipework_list = []
        cold_water_sources = {"cw3": self.coldwatersource}
        wwhrs = {}
        energy_supplies = {
            "es3": EnergySupply(fuel_type=FuelType.ELECTRICITY, simulation_time=self.simtime),
            "_unmet_demand": EnergySupply(
                fuel_type=FuelType.UNMET_DEMAND, simulation_time=self.simtime
            ),
        }
        event_schedules = {}
        dhw = DHWDemand(
            showers_dict=showers_dict,
            baths_dict=baths_dict,
            other_hw_users_dict=other_hw_users_dict,
            hw_pipework_inputs=hw_pipework_list,
            cold_water_sources=cold_water_sources,
            wwhrs=wwhrs,
            energy_supplies=energy_supplies,
            event_schedules=event_schedules,
            hot_water_sources={"hw_cylinder": MagicMock(spec=HotWaterSource)},
        )
        assert dhw._DHWDemand__source_supplying_outlet[(OutletType.SHOWER, "sh3")] == "hw_cylinder"  # type: ignore[AttributeAccessIssue]

    def test_invalid_hot_water_source_assignment(self):
        # Use unique, minimal test data
        showers_dict = {
            "sh2": {
                "type": "MixerShower",
                "flowrate": 8.0,
                "ColdWaterSource": "cw2",
                "HotWaterSource": "invalid_name",
            }
        }
        baths_dict = {}
        other_hw_users_dict = {}
        hw_pipework_list = {"hw_cylinder": [], "combi_boiler": []}
        cold_water_sources = {"cw2": self.coldwatersource}
        wwhrs = {}
        energy_supplies = {
            "es2": EnergySupply(fuel_type=FuelType.ELECTRICITY, simulation_time=self.simtime),
            "_unmet_demand": EnergySupply(
                fuel_type=FuelType.UNMET_DEMAND, simulation_time=self.simtime
            ),
        }
        event_schedules = {}

        expected_message = "Invalid HotWaterSource specified for tapping point sh2 of type Shower"
        with pytest.raises(ValueError, match=re.escape(expected_message)):
            DHWDemand(
                showers_dict=showers_dict,
                baths_dict=baths_dict,
                other_hw_users_dict=other_hw_users_dict,
                hw_pipework_inputs=hw_pipework_list,
                cold_water_sources=cold_water_sources,
                wwhrs=wwhrs,
                energy_supplies=energy_supplies,
                event_schedules=event_schedules,
                hot_water_sources={
                    "hw_cylinder": MagicMock(spec=HotWaterSource),
                    "combi_boiler": MagicMock(spec=HotWaterSource),
                },
            )

    def test_missing_hot_water_source_assignment(self):
        # Use unique, minimal test data
        showers_dict = {"sh2": {"type": "MixerShower", "flowrate": 8.0, "ColdWaterSource": "cw2"}}
        baths_dict = {}
        other_hw_users_dict = {}
        hw_pipework_list = {"hw_cylinder": [], "combi_boiler": []}
        cold_water_sources = {"cw2": self.coldwatersource}
        wwhrs = {}
        energy_supplies = {
            "es2": EnergySupply(fuel_type=FuelType.ELECTRICITY, simulation_time=self.simtime),
            "_unmet_demand": EnergySupply(
                fuel_type=FuelType.UNMET_DEMAND, simulation_time=self.simtime
            ),
        }
        event_schedules = {}

        expected_message = "HotWaterSource not specified for tapping point sh2 of type Shower"
        with pytest.raises(ValueError, match=re.escape(expected_message)):
            DHWDemand(
                showers_dict=showers_dict,
                baths_dict=baths_dict,
                other_hw_users_dict=other_hw_users_dict,
                hw_pipework_inputs=hw_pipework_list,
                cold_water_sources=cold_water_sources,
                wwhrs=wwhrs,
                energy_supplies=energy_supplies,
                event_schedules=event_schedules,
                hot_water_sources={
                    "hw_cylinder": MagicMock(spec=HotWaterSource),
                    "combi_boiler": MagicMock(spec=HotWaterSource),
                },
            )
