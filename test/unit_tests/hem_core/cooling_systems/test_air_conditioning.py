#!/usr/bin/env python3

"""
This module contains unit tests for the air conditioning module
"""

# Standard library imports
import unittest

from hem_core.controls.time_control import SetpointTimeControl
from hem_core.cooling_systems.air_conditioning import AirConditioning
from hem_core.energy_supply.energy_supply import EnergySupply
from hem_core.input_output.enums import FuelType

# Local imports
from hem_core.simulation_time import SimulationTime


class TestAirConditioning(unittest.TestCase):
    """Unit tests for AirConditioning class"""

    def setUp(self) -> None:
        """Create AirConditioning object to be tested"""
        self.simtime = SimulationTime(start_time=0, end_time=4, step=1)
        self.energysupply = EnergySupply(
            fuel_type=FuelType.ELECTRICITY, simulation_time=self.simtime
        )
        energysupplyconn = self.energysupply.connection(end_user_name="aircon")
        control = SetpointTimeControl(
            schedule=[21.0, 21.0, None, 21.0],
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1.0,
        )
        self.aircon = AirConditioning(
            cooling_capacity=50,
            efficiency=2.0,
            frac_convective=0.4,
            energy_supply_conn=energysupplyconn,
            simulation_time=self.simtime,
            control=control,
        )

    def test_demand_energy(self) -> None:
        """Test that AirConditioning object returns correct energy supplied"""
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                # Note: Cooling demands are negative by convention
                self.assertEqual(
                    self.aircon.demand_energy(cooling_demand=[-40.0, -100.0, -30.0, -20.0][t_idx]),
                    [-40.0, -50.0, 0.0, -20.0][t_idx],
                    "incorrect cooling energy supplied returned",
                )
                self.assertEqual(
                    self.energysupply.results_by_end_user()["aircon"][t_idx],
                    [20.0, 25.0, 0.0, 10.0][t_idx],
                    "incorrect delivered energy demand returned",
                )

    def test_energy_output_min(self) -> None:
        self.assertEqual(self.aircon.energy_output_min(), 0.0)

    def test_temp_setpnt(self) -> None:
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(self.aircon.temp_setpnt(), [21.0, 21.0, None, 21.0][t_idx])

    def test_in_required_period(self) -> None:
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(self.aircon.in_required_period(), [True, True, False, True][t_idx])

    def test_frac_convective(self) -> None:
        self.assertEqual(self.aircon.frac_convective(), 0.4)
