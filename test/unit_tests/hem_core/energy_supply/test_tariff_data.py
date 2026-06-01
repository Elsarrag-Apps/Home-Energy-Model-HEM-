#!/usr/bin/env python3

"""
This module contains unit tests for the tariff_data module
"""

# Standard library imports
from pathlib import Path

import pytest

# Local imports
from hem_core.energy_supply.tariff_data import TariffData

from test.conftest import PATH_DEMO_FILES

TARIFF_PATH = PATH_DEMO_FILES / "tariff_data_25-06-2024.csv"


class TestEnergySupply:
    """Unit tests for TariffData class"""

    @pytest.fixture(autouse=True)
    def setup_tariff_data(self):
        self.tariff_data = TariffData(TARIFF_PATH)

    @pytest.mark.parametrize(
        "tariff_name, t_idx, expected_price",
        [
            ("Standard Tariff", 0, 25.16),
            ("7-Hour Off Peak Tariff", 0, 14.6),
            ("10-Hour Off Peak Tariff", 0, 16.04),
            ("Variable Time of Day Tariff", 0, 10.87017271),
            ("Standard Tariff", 17519, 25.16),
            ("7-Hour Off Peak Tariff", 17519, 29.8),
            ("10-Hour Off Peak Tariff", 17519, 35.01),
            ("Variable Time of Day Tariff", 17519, 17.75781834),
        ],
    )
    def test_get_price(self, tariff_name: str, t_idx: int, expected_price: float):
        """Test that the tariff values are read correctly"""
        assert self.tariff_data.get_price(tariff_name=tariff_name, t_idx=t_idx) == expected_price

    def test_get_price_out_of_range(self):
        """Test exceptions are thrown with out of range values"""
        with pytest.raises(ValueError):
            self.tariff_data.get_price(tariff_name="", t_idx=0)
        with pytest.raises(KeyError):
            self.tariff_data.get_price(tariff_name="Standard Tariff", t_idx=18000)
