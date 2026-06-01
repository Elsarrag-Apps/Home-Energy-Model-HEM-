#!/usr/bin/env python3

"""
This module contains unit tests for the thermal_bridge module
"""

# Standard library imports
import unittest

# Local imports
from hem_core.space_heat_demand.thermal_bridge import ThermalBridgeLinear, ThermalBridgePoint


class TestThermalBridgeLinear(unittest.TestCase):
    """Unit tests for ThermalBridgeLinear class"""

    def setUp(self) -> None:
        """Create ThermalBridgeLinear object to be tested"""
        self.tb = ThermalBridgeLinear(linear_therm_trans=0.28, length=5.0)

    def test_heat_trans_coeff(self) -> None:
        self.assertAlmostEqual(
            self.tb.heat_trans_coeff(), 1.4, msg="incorrect heat transfer coeff returned"
        )


class TestThermalBridgePoint(unittest.TestCase):
    """Unit tests for ThermalBridgePoint class"""

    def setUp(self) -> None:
        """Create ThermalBridgePoint object to be tested"""
        self.tb = ThermalBridgePoint(heat_transfer_coeff=1.4)

    def test_heat_trans_coeff(self) -> None:
        self.assertEqual(self.tb.heat_trans_coeff(), 1.4, "incorrect heat transfer coeff returned")
