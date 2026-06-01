#!/usr/bin/env python3

"""
This module contains unit tests for the misc module
"""

# Standard library imports
import math
import unittest

import pytest

from hem_core.simulation_time import SimulationTime

# Local imports
from hem_core.water_heat_demand.misc import (
    calc_fraction_hot_water,
    calculate_volume_weighted_average_temperature,
    water_demand_to_kWh,
)


class TestMisc(unittest.TestCase):
    """Unit tests for functions in the misc.py file"""

    def test_frac_hot_water(self):
        self.assertEqual(
            calc_fraction_hot_water(temperature_target=40, temperature_hot=55, temperature_cold=5),
            0.7,
            "incorrect fraction of hot water returned",
        )

        with self.assertRaises(ValueError):
            calc_fraction_hot_water(
                temperature_target=60.0, temperature_hot=55.0, temperature_cold=5.0
            )
        with self.assertRaises(ValueError):
            calc_fraction_hot_water(
                temperature_target=0.0, temperature_hot=55.0, temperature_cold=5.0
            )

    def test_water_demand_to_kWh(self):
        """Test that correct water demand to kWh is returned when queried"""
        litres_demand = [5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0]
        demand_temperatures = [40.0, 35.0, 37.0, 39.0, 40.0, 38.0, 39.0, 40.0]
        cold_temperatures = [5.0, 4.0, 5.0, 6.0, 5.0, 4.0, 3.0, 4.0]
        for t_idx, _, _ in SimulationTime(start_time=0, end_time=8, step=1):
            with self.subTest(i=t_idx):
                self.assertAlmostEqual(
                    water_demand_to_kWh(
                        litres_demand=litres_demand[t_idx],
                        demand_temperature=demand_temperatures[t_idx],
                        cold_temperature=cold_temperatures[t_idx],
                    ),
                    [0.20339, 0.36029, 0.55787, 0.76707, 1.01694, 1.18547, 1.46440, 1.67360][t_idx],
                    5,
                    msg="incorrect water demand to kWh returned",
                )


class TestVolumeWeightedAverageTemperature:
    """Test cases for the new helper function"""

    def test_valid_calculation(self):
        """Test normal volume-weighted average calculation"""
        temp_vol_pairs = [(10.0, 5.0), (20.0, 3.0), (30.0, 2.0)]
        expected_temp = 17.0

        result = calculate_volume_weighted_average_temperature(temp_vol_pairs)
        assert math.isclose(result, expected_temp)

    def test_volume_validation_success(self):
        """Test that volume validation passes when volumes match"""
        temp_vol_pairs = [(15.0, 3.0), (25.0, 7.0)]
        expected_volume = 10.0

        result = calculate_volume_weighted_average_temperature(
            temp_vol_pairs, expected_volume=expected_volume
        )
        assert math.isclose(result, 22.0)

    def test_volume_validation_failure(self):
        """Test that volume validation fails when volumes don't match"""
        temp_vol_pairs = [(15.0, 3.0), (25.0, 7.0)]  # Total = 10.0
        expected_volume = 5.0  # Different from actual total

        with pytest.raises(ValueError, match="Volume mismatch: expected 5.0, got 10.0"):
            calculate_volume_weighted_average_temperature(
                temp_vol_pairs, expected_volume=expected_volume
            )

    def test_empty_list_error(self):
        """Test that empty list raises appropriate error"""
        with pytest.raises(ValueError, match="temp_volume_pairs is empty"):
            calculate_volume_weighted_average_temperature([])

    def test_zero_volume_error(self):
        """Test that zero total volume raises appropriate error"""
        temp_vol_pairs = [(15.0, 0.0), (25.0, 0.0)]

        with pytest.raises(ValueError, match="total volume is zero"):
            calculate_volume_weighted_average_temperature(temp_vol_pairs)
