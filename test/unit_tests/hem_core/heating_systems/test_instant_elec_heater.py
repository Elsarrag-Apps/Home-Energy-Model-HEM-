#!/usr/bin/env python3

"""
This module contains unit tests for the Instant Electric Heater module
"""

# Standard library imports
import unittest

from hem_core.controls.time_control import SetpointTimeControl
from hem_core.energy_supply.energy_supply import EnergySupply
from hem_core.heating_systems.instant_elec_heater import InstantElecHeater
from hem_core.input_output.enums import FuelType

# Local imports
from hem_core.simulation_time import SimulationTime


class TestInstantElecHeater(unittest.TestCase):
    """Unit tests for InstantElecHeater class"""

    def setUp(self):
        """Create InstantElecHeater object to be tested"""
        self.simtime = SimulationTime(start_time=0, end_time=4, step=1)
        energysupply = EnergySupply(fuel_type=FuelType.ELECTRICITY, simulation_time=self.simtime)
        energysupplyconn = energysupply.connection(end_user_name="shower")
        control = SetpointTimeControl(
            schedule=[21.0, 21.0, None, 21.0],
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1.0,
        )
        self.inselecheater = InstantElecHeater(
            rated_power=50,
            frac_convective=0.4,
            energy_supply_conn=energysupplyconn,
            simulation_time=self.simtime,
            control=control,
        )

    def test_demand_energy(self):
        """Test that InstantElecHeater object returns correct energy supplied"""
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.inselecheater.demand_energy([40.0, 100.0, 30.0, 20.0][t_idx]),
                    [40.0, 50.0, 0.0, 20.0][t_idx],
                    msg="incorrect energy supplied returned",
                )

    def test_temp_setpnt(self):
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(self.inselecheater.temp_setpnt(), [21.0, 21.0, None, 21.0][t_idx])

    def test_in_required_period(self):
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.inselecheater.in_required_period(), [True, True, False, True][t_idx]
                )

    def test_frac_convective(self):
        self.assertEqual(self.inselecheater.frac_convective(), 0.4)

    def test_energy_output_min(self):
        self.assertEqual(self.inselecheater.energy_output_min(), 0.0)
