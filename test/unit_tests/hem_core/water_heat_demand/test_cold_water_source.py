#!/usr/bin/env python3

"""
This module contains unit tests for the cold_water_source module
"""

# Standard library imports
import unittest

# Local imports
from hem_core.simulation_time import SimulationTime
from hem_core.water_heat_demand.cold_water_source import ColdWaterSource


class TestColdWaterSource(unittest.TestCase):
    """Unit tests for ColdWaterSource class"""

    def setUp(self):
        """Create ColdWaterSource object to be tested"""
        self.simtime = SimulationTime(start_time=0, end_time=8, step=1)
        self.watertemp = [0.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 20.0]
        self.coldwater = ColdWaterSource(
            cold_water_temps=self.watertemp,
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )

    def test_temperature(self):
        """Test that ColdWaterSource object returns correct water temperatures"""
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.coldwater.draw_off_water(volume_needed=10.0),
                    [(self.watertemp[t_idx], 10.0)],
                    "incorrect water temp returned",
                )
                self.assertEqual(
                    self.coldwater.get_temp_cold_water(volume_needed=10.0),
                    [(self.watertemp[t_idx], 10.0)],
                    "incorrect water temp returned",
                )
