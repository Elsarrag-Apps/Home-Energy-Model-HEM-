#!/usr/bin/env python3

"""
This module contains unit tests for the Ductwork module
"""

# Standard library imports
import unittest

from hem_core.ductwork import Ductwork
from hem_core.input_output.enums import DuctShape, DuctType

# Local imports
from hem_core.simulation_time import SimulationTime


class TestDuctworkCircular(unittest.TestCase):
    """Unit tests for Ductwork class"""

    def setUp(self) -> None:
        """Create Ductwork objects to be tested"""
        duct_perimeter = None
        internal_diameter = 0.025
        external_diameter = 0.027
        length = 0.4
        k_insulation = 0.02
        thickness_insulation = 0.022
        reflective = False
        self.ductwork = Ductwork(
            cross_section_shape=DuctShape.CIRCULAR,
            duct_perimeter=duct_perimeter,
            internal_diameter=internal_diameter,
            external_diameter=external_diameter,
            length=length,
            k_insulation=k_insulation,
            thickness_insulation=thickness_insulation,
            reflective=reflective,
            duct_type=DuctType.EXHAUST,
        )
        self.ductwork2 = Ductwork(
            cross_section_shape=DuctShape.CIRCULAR,
            duct_perimeter=duct_perimeter,
            internal_diameter=internal_diameter,
            external_diameter=external_diameter,
            length=length,
            k_insulation=k_insulation,
            thickness_insulation=thickness_insulation,
            reflective=reflective,
            duct_type=DuctType.INTAKE,
        )
        self.ductwork3 = Ductwork(
            cross_section_shape=DuctShape.CIRCULAR,
            duct_perimeter=duct_perimeter,
            internal_diameter=internal_diameter,
            external_diameter=external_diameter,
            length=length,
            k_insulation=k_insulation,
            thickness_insulation=thickness_insulation,
            reflective=reflective,
            duct_type=DuctType.SUPPLY,
        )
        self.ductwork4 = Ductwork(
            cross_section_shape=DuctShape.CIRCULAR,
            duct_perimeter=duct_perimeter,
            internal_diameter=internal_diameter,
            external_diameter=external_diameter,
            length=length,
            k_insulation=k_insulation,
            thickness_insulation=thickness_insulation,
            reflective=reflective,
            duct_type=DuctType.EXTRACT,
        )
        self.ductwork5 = Ductwork(
            cross_section_shape=DuctShape.CIRCULAR,
            duct_perimeter=duct_perimeter,
            internal_diameter=internal_diameter,
            external_diameter=external_diameter,
            length=length,
            k_insulation=k_insulation,
            thickness_insulation=thickness_insulation,
            reflective=reflective,
            duct_type=DuctType.EXHAUST,
        )
        self.ductwork6 = Ductwork(
            cross_section_shape=DuctShape.CIRCULAR,
            duct_perimeter=duct_perimeter,
            internal_diameter=internal_diameter,
            external_diameter=external_diameter,
            length=length,
            k_insulation=k_insulation,
            thickness_insulation=thickness_insulation,
            reflective=reflective,
            duct_type=DuctType.INTAKE,
        )
        self.ductwork7 = Ductwork(
            cross_section_shape=DuctShape.CIRCULAR,
            duct_perimeter=duct_perimeter,
            internal_diameter=internal_diameter,
            external_diameter=external_diameter,
            length=length,
            k_insulation=k_insulation,
            thickness_insulation=thickness_insulation,
            reflective=reflective,
            duct_type=DuctType.SUPPLY,
        )
        self.ductwork8 = Ductwork(
            cross_section_shape=DuctShape.CIRCULAR,
            duct_perimeter=duct_perimeter,
            internal_diameter=internal_diameter,
            external_diameter=external_diameter,
            length=length,
            k_insulation=k_insulation,
            thickness_insulation=thickness_insulation,
            reflective=reflective,
            duct_type=DuctType.EXTRACT,
        )
        self.simtime = SimulationTime(0, 8, 1)

    def test_invalid_cross_section_shape(self) -> None:
        """Test that the constructor throws on an invalid cross section shape"""
        with self.assertRaises(ValueError):
            Ductwork(
                cross_section_shape="invalid",  # type: ignore [arg-type] # Is used to test error handling when invalid cross section shape is passed
                duct_perimeter=None,
                internal_diameter=1,
                external_diameter=1,
                length=1,
                k_insulation=1,
                thickness_insulation=1,
                reflective=True,
                duct_type=DuctType.EXHAUST,
            )

    def test_get_duct_type(self) -> None:
        """Test that the correct duct type is returned from get_duct_type"""
        self.assertEqual(self.ductwork.get_duct_type(), DuctType.EXHAUST)
        self.assertEqual(self.ductwork2.get_duct_type(), DuctType.INTAKE)
        self.assertEqual(self.ductwork3.get_duct_type(), DuctType.SUPPLY)
        self.assertEqual(self.ductwork4.get_duct_type(), DuctType.EXTRACT)

    def test_duct_heat_loss(self) -> None:
        """Test that correct heat loss is returned when queried"""
        outside_temp = [20.0, 19.5, 19.0, 18.5, 19.0, 19.5, 20.0, 20.5]
        inside_temp = [5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0]
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertAlmostEqual(
                    self.ductwork.duct_heat_loss(inside_temp[t_idx], outside_temp[t_idx]),
                    [
                        -0.669369,
                        -0.602432,
                        -0.535495,
                        -0.468558,
                        -0.446246,
                        -0.423933,
                        -0.401621,
                        -0.379309,
                    ][t_idx],
                    5,
                    "incorrect heat loss returned",
                )


class TestDuctworkRectangular(unittest.TestCase):
    """Unit tests for Ductwork class"""

    def setUp(self) -> None:
        """Create Ductwork objects to be tested"""
        self.ductwork = Ductwork(
            cross_section_shape=DuctShape.RECTANGULAR,
            duct_perimeter=0.1,
            internal_diameter=None,
            external_diameter=None,
            length=0.4,
            k_insulation=0.02,
            thickness_insulation=0.022,
            reflective=False,
            duct_type=DuctType.EXHAUST,
        )
        self.simtime = SimulationTime(0, 8, 1)

    def test_get_duct_type(self) -> None:
        """Test that the correct duct type is returned from get_duct_type"""
        self.assertEqual(self.ductwork.get_duct_type(), DuctType.EXHAUST)

    def test_duct_heat_loss(self) -> None:
        """Test that correct heat loss is returned when queried"""
        outside_temp = [20.0, 19.5, 19.0, 18.5, 19.0, 19.5, 20.0, 20.5]
        inside_temp = [5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0]
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertAlmostEqual(
                    self.ductwork.duct_heat_loss(inside_temp[t_idx], outside_temp[t_idx]),
                    [
                        -0.87482,
                        -0.787339,
                        -0.69986,
                        -0.61237,
                        -0.58321,
                        -0.55405,
                        -0.52489,
                        -0.49573,
                    ][t_idx],
                    5,
                    "incorrect heat loss returned",
                )
