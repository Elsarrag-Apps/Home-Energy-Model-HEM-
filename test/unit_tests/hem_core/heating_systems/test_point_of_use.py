#!/usr/bin/env python3

"""
This module contains unit tests for the Instant Electric Heater module
"""

# Standard library imports
import unittest

# Local imports
from hem_core.energy_supply.energy_supply import EnergySupply
from hem_core.heating_systems.point_of_use import PointOfUse
from hem_core.input_output.enums import FuelType
from hem_core.simulation_time import SimulationTime
from hem_core.water_heat_demand.cold_water_source import ColdWaterSource
from hem_core.water_heat_demand.dhw_demand import WaterEventResult


class TestPointOfUse(unittest.TestCase):
    """Unit tests for PointOfUse class"""

    def setUp(self):
        """Create PointOfUse object to be tested"""
        self.efficiency = 1
        self.simtime = SimulationTime(0, 2, 1)
        self.energysupply = EnergySupply(FuelType.ELECTRICITY, self.simtime)
        self.energysupplyconn = self.energysupply.connection("shower")
        self.coldwatertemps = [15.0, 20.0, 25.0]
        self.coldfeed = ColdWaterSource(self.coldwatertemps, self.simtime, 0, 1)
        self.temp_hot_water = 55

        self.point_of_use = PointOfUse(
            efficiency=self.efficiency,
            energy_supply_conn=self.energysupplyconn,
            simulation_time=self.simtime,
            cold_feed=self.coldfeed,
            temp_hot_water=self.temp_hot_water,
        )

    def test_demand_hot_water(self):
        """Test energy used to meet the temperature demand"""
        # Test when temp_hot_water is set
        usage_events = [
            WaterEventResult(
                type="Other",
                volume_hot=60.0,
                volume_warm=60.0,
                temperature_warm=55.0,
                event_duration=0.0,
            ),
            WaterEventResult(
                type="Other",
                volume_hot=0.0,
                volume_warm=0.0,
                temperature_warm=55.0,
                event_duration=0.0,
            ),
        ]
        self.assertAlmostEqual(
            self.point_of_use.demand_hot_water(usage_events=usage_events), 2.7893333333333334
        )

        # Test when events list is empty
        usage_events = []
        self.assertAlmostEqual(self.point_of_use.demand_hot_water(usage_events=usage_events), 0.0)

    def test_demand_energy(self):
        """Test demand energy for the heater"""
        energy_demand = 2.0
        self.assertAlmostEqual(self.point_of_use.demand_energy(energy_demand=energy_demand), 2.0)

    def test_get_cold_water_source(self):
        """Test that the correct cold water source is returned from get_cold_water_source"""
        self.assertEqual(self.point_of_use.get_cold_water_source(), self.coldfeed)

    def test_get_temp_hot_water(self):
        """Test that the hot water temperature is returned by get_temp_hot_water"""
        self.assertEqual(self.point_of_use.get_temp_hot_water(volume_req=20.0), [(55.0, 20.0)])
