#!/usr/bin/env python3

"""
This module contains unit tests for the other water uses module
"""

# Standard library imports
import unittest

# Local imports
from hem_core.simulation_time import SimulationTime
from hem_core.water_heat_demand.cold_water_source import ColdWaterSource
from hem_core.water_heat_demand.other_hot_water_uses import OtherHotWater


def func_temp_hot_water_fixed(t):
    """Function to return a fixed hot water temperature"""
    return 52.0


class TestOtherHotWater(unittest.TestCase):
    """Unit tests for OtherHotWater class"""

    def setUp(self):
        """Create OtherWaterUses object to be tested"""
        self.simtime = SimulationTime(start_time=0, end_time=3, step=1)
        coldwatertemps = [2.0, 3.0, 4.0]
        self.coldwatersource = ColdWaterSource(
            cold_water_temps=coldwatertemps,
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )
        self.otherhotwater = OtherHotWater(flowrate=5.0, cold_water_source=self.coldwatersource)

    def test_get_cold_water_source(self):
        """Test the cold water source is created as expected"""
        self.assertIs(
            self.coldwatersource,
            self.otherhotwater.get_cold_water_source(),
            "cold water source not returned",
        )

    def test_hot_water_demand(self):
        """Test that OtherWaterUses object returns correct hot water demand"""
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                result = self.otherhotwater.hot_water_demand(
                    event={
                        "temperature": 40.0,
                        "duration": 4.0,
                        "start": 0,
                        "type": "Other",
                        "name": "other",
                    },
                    func_temp_hot_water=func_temp_hot_water_fixed,
                )[0]
                assert result is not None, (
                    "hot_water_demand() returned None when a float was expected"
                )
                self.assertAlmostEqual(
                    result,
                    [15.2, 15.102, 15.0][t_idx],
                    3,
                    "incorrect hot water demand returned",
                )
