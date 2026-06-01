#!/usr/bin/env python3

"""
This module contains unit tests for the bath module
"""

# Standard library imports
import unittest

# Local imports
from hem_core.simulation_time import SimulationTime
from hem_core.water_heat_demand.bath import Bath
from hem_core.water_heat_demand.cold_water_source import ColdWaterSource


def func_temp_hot_water_fixed(t):
    """Function to return a fixed hot water temperature"""
    return 52.0


class TestBath(unittest.TestCase):
    """Unit tests for Bath class"""

    def setUp(self):
        """Create Bath object to be tested"""
        self.simtime = SimulationTime(start_time=0, end_time=3, step=1)
        coldwatertemps = [2.0, 3.0, 4.0]
        self.coldwatersource = ColdWaterSource(
            cold_water_temps=coldwatertemps,
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )
        self.bath = Bath(size=100.0, cold_water_source=self.coldwatersource, flowrate=4.5)

    def test_get_cold_water_source(self):
        """Test the cold water source is created as expected"""
        self.assertIs(
            self.coldwatersource,
            self.bath.get_cold_water_source(),
            "cold water source not returned",
        )

    def test_hot_water_demand(self):
        """Test that Bath object returns correct hot water demand"""
        self.assertEqual(
            self.bath.hot_water_demand(
                event={"volume": 75.0, "temperature": 40.0},
                func_temp_hot_water=func_temp_hot_water_fixed,
            ),
            (57.0, 75.0, 16.666666666666668),
            "incorrect hot water demand returned",
        )
        self.assertEqual(
            self.bath.hot_water_demand(
                event={"volume": 200.0, "temperature": 40.0},
                func_temp_hot_water=func_temp_hot_water_fixed,
            ),
            (76.0, 100.0, 44.44444444444444),
            "incorrect hot water demand returned for bath fill volume > bath tub volume",
        )
        self.assertEqual(
            self.bath.hot_water_demand(
                event={"duration": 16.666666666666667, "temperature": 40.0},
                func_temp_hot_water=func_temp_hot_water_fixed,
            ),
            (57.0, 75.0, 16.666666666666668),
            "incorrect hot water demand returned",
        )
        with self.assertRaises(ValueError):
            self.bath.hot_water_demand(
                event={"temperature": 40.0}, func_temp_hot_water=func_temp_hot_water_fixed
            )
