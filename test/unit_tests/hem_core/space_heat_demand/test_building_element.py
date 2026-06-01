#!/usr/bin/env python3

"""
This module contains unit tests for the building_element module
"""

# Standard library imports
import math
import unittest
from unittest.mock import MagicMock

# Local imports
from hem_core.external_conditions import ExternalConditions
from hem_core.input_output.enums import (
    EdgeInsulationDirection,
    FloorType,
    HeatFlowDirection,
    MassDistributionClass,
    WindShieldLocation,
)
from hem_core.simulation_time import SimulationTime
from hem_core.space_heat_demand.building_element import (
    BuildingElement,
    BuildingElementAdjacentConditionedSpace,
    BuildingElementAdjacentUnconditionedSpace_Simple,
    BuildingElementGround,
    BuildingElementOpaque,
    BuildingElementPartyWall,
    BuildingElementTransparent,
    HeatTransferInternal,
    HeatTransferOtherSide,
    HeatTransferThrough3Plus2Nodes,
    HeatTransferThrough5Nodes,
    SolarRadiationInteraction,
    SolarRadiationInteractionAbsorbed,
    SolarRadiationInteractionTransmitted,
)
from hem_core.units import Orientation360


class TestBuildingElement(unittest.TestCase):
    """Unit tests for BuildingElement class"""

    def setUp(self):
        self.simtime = SimulationTime(start_time=0, end_time=4, step=1)

        external_conditions = MagicMock(ExternalConditions)

        self.be_a = BuildingElement(
            ext_cond=external_conditions, area=3.0, pitch=0
        )  # solar_absorption_coeff=0.6, f_sky=0)
        self.be_b = BuildingElement(
            ext_cond=external_conditions, area=6.0, pitch=45
        )  # solar_absorption_coeff=0.7, f_sky=0.5)
        self.be_c = BuildingElement(
            ext_cond=external_conditions, area=6.0, pitch=90
        )  # solar_absorption_coeff=0.7, f_sky=0.5)
        self.be_d = BuildingElement(
            ext_cond=external_conditions, area=6.0, pitch=180
        )  # solar_absorption_coeff=0.7, f_sky=0.5)

    def test_convert_uvalue_to_resistance(self):
        self.assertAlmostEqual(
            BuildingElement.convert_uvalue_to_resistance(2, 40), 0.35985829616804244
        )


class TestHeatTransferInternal(unittest.TestCase):
    """Unit tests for HeatTransferInternal class"""

    def setUp(self):
        class HeatTransferInternalConcrete(HeatTransferInternal):
            def r_se(self) -> float:
                raise NotImplementedError  # pragma: no cover

        self.be_a = HeatTransferInternalConcrete()
        self.be_a._pitch = 0
        self.be_b = HeatTransferInternalConcrete()
        self.be_b._pitch = 45
        self.be_c = HeatTransferInternalConcrete()
        self.be_c._pitch = 90
        self.be_d = HeatTransferInternalConcrete()
        self.be_d._pitch = 180

    def test_heat_flow_direction(self):
        self.assertEqual(
            self.be_b.heat_flow_direction(temp_int_air=20, temp_int_surface=25),
            HeatFlowDirection.DOWNWARDS,
        )

        self.assertEqual(
            self.be_c.heat_flow_direction(temp_int_air=20, temp_int_surface=25),
            HeatFlowDirection.HORIZONTAL,
        )

        self.assertEqual(
            self.be_d.heat_flow_direction(temp_int_air=20, temp_int_surface=25),
            HeatFlowDirection.UPWARDS,
        )

    def test_convert_uvalue_to_resistance(self):
        """Test that convert_uvalue_to_resistance returns the correct value"""
        self.assertEqual(
            self.be_a.convert_uvalue_to_resistance(u_value=1, pitch=180), 0.7870483926665635
        )

    def test_r_si(self):
        self.assertEqual(self.be_a.r_si(), 0.0987166831194472)

    def test_r_si_pitch(self):
        # r_si_horizontal
        result = self.be_a._HeatTransferInternal__r_si(pitch=90.0)
        self.assertEqual(result, 0.1310615989515072)

        # r_si_upwards
        result = self.be_a._HeatTransferInternal__r_si(pitch=30.0)
        self.assertEqual(result, 0.0987166831194472)

        # r_si_downwards
        result = self.be_a._HeatTransferInternal__r_si(pitch=150.0)
        self.assertEqual(result, 0.17152658662092624)

    def test_r_si_invalid_pitch(self):
        """Test that r_si throws with an invalid pitch"""
        with self.assertRaises(ValueError):
            self.be_a._HeatTransferInternal__r_si(math.nan)

    def test_pitch_class(self):
        self.assertEqual(self.be_a.pitch_class(pitch=90.0), HeatFlowDirection.HORIZONTAL)
        self.assertEqual(self.be_a.pitch_class(pitch=30.0), HeatFlowDirection.UPWARDS)
        self.assertEqual(self.be_a.pitch_class(pitch=150.0), HeatFlowDirection.DOWNWARDS)

    def test_pitch_class_invalid(self):
        """Test that pitch_class throws on an invalid pitch"""
        with self.assertRaises(ValueError):
            self.be_a.pitch_class(pitch=math.nan)

    def test_h_ri(self):
        self.assertEqual(self.be_a.h_ri(), 5.13)


class TestHeatTransferThrough5Nodes(unittest.TestCase):
    def test_init_invalid_mass_distribution_class(self):
        """Test that the constructor throws on an invalid mass_distribution_class"""

        class HeatTransferThrough5NodesConcrete(HeatTransferThrough5Nodes):
            def r_se(self) -> float:
                raise NotImplementedError  # pragma: no cover

            def r_si(self) -> float:
                raise NotImplementedError  # pragma: no cover

        with self.assertRaises(ValueError):
            HeatTransferThrough5NodesConcrete(
                thermal_resistance_construction=1,
                mass_distribution_class="Invalid",  # type: ignore[arg-type] # Testing error handling for invalid type
                areal_heat_capacity=1,
            )


class TestHeatTransferThrough3Plus2Nodes(unittest.TestCase):
    def test_init_invalid_mass_distribution_class(self):
        class HeatTransferThrough3Plus2NodesConcrete(HeatTransferThrough3Plus2Nodes):
            def r_se(self) -> float:
                raise NotImplementedError  # pragma: no cover

            def r_si(self) -> float:
                raise NotImplementedError  # pragma: no cover

        """Test that the constructor throws on an invalid mass_distribution_class"""
        with self.assertRaises(ValueError):
            HeatTransferThrough3Plus2NodesConcrete(
                thermal_resistance_floor_construction=1,
                r_gr=1,
                mass_distribution_class="Invalid",  # type: ignore[arg-type] # Testing error handling for invalid type
                k_gr=1,
                areal_heat_capacity=1,
            )


class TestHeatTransferOtherSide(unittest.TestCase):
    """Unit tests for HeatTransferOtherSide class"""

    def setUp(self):
        class HeatTransferOtherSideConcrete(HeatTransferOtherSide):
            def __init__(self, f_sky: float = 0):
                super().__init__(f_sky)

            def r_si(self) -> float:
                raise NotImplementedError  # pragma: no cover

        self.be_a = HeatTransferOtherSideConcrete(f_sky=0)
        self.be_b = HeatTransferOtherSideConcrete(f_sky=0.5)
        self.be_c = HeatTransferOtherSideConcrete(f_sky=0.5)
        self.be_d = HeatTransferOtherSideConcrete(f_sky=0.5)

    def test_r_se(self):
        self.assertEqual(self.be_a.r_se(), 0.041425020712510356)

    def test_h_ce(self):
        self.assertEqual(self.be_a.h_ce(), 20.0)

    def test_h_re(self):
        self.assertEqual(self.be_a.h_re(), 4.14)

    def test_fabric_heat_loss(self):
        """Test that fabric_heat_loss can't be called and always raises."""
        with self.assertRaises(RuntimeError):
            self.be_a.fabric_heat_loss()


class TestBuildingElementOpaque(unittest.TestCase):
    """Unit tests for BuildingElementOpaque class"""

    def setUp(self):
        """Create BuildingElementOpaque objects to be tested"""
        self.simtime = SimulationTime(start_time=0, end_time=4, step=1)
        ec = ExternalConditions(
            simulation_time=self.simtime,
            air_temps=[0.0, 5.0, 10.0, 15.0],
            wind_speeds=[],
            wind_directions=[],
            diffuse_horizontal_radiation=[0.0] * 4,
            direct_beam_radiation=[0.0] * 4,
            solar_reflectivity_of_ground=[],
            latitude=55.0,
            longitude=0.0,
            timezone=0,
            start_day=0,
            end_day=0,
            time_series_step=1,
            january_first=1,
            daylight_savings=None,
            leap_day_included=False,
            direct_beam_conversion_needed=False,
            shading_segments=False,
        )
        # TODO implement rest of external conditions in unit tests

        # Create an object for each mass distribution class
        be_I = BuildingElementOpaque(
            area=20,
            is_unheated_pitched_roof=False,
            pitch=180,
            solar_absorption_coeff=0.60,
            thermal_resistance_construction=0.25,
            areal_heat_capacity=19000.0,
            mass_distribution_class=MassDistributionClass.I,
            orientation=Orientation360.create_from_180(0),
            base_height=0,
            height=2,
            width=10,
            ext_cond=ec,
        )
        be_E = BuildingElementOpaque(
            area=22.5,
            is_unheated_pitched_roof=False,
            pitch=135,
            solar_absorption_coeff=0.61,
            thermal_resistance_construction=0.50,
            areal_heat_capacity=18000.0,
            mass_distribution_class=MassDistributionClass.E,
            orientation=Orientation360.create_from_180(180),
            base_height=0,
            height=2.25,
            width=10,
            ext_cond=ec,
        )
        be_IE = BuildingElementOpaque(
            area=25,
            is_unheated_pitched_roof=False,
            pitch=90,
            solar_absorption_coeff=0.62,
            thermal_resistance_construction=0.75,
            areal_heat_capacity=17000.0,
            mass_distribution_class=MassDistributionClass.IE,
            orientation=Orientation360.create_from_180(90),
            base_height=0,
            height=2.5,
            width=10,
            ext_cond=ec,
        )
        be_D = BuildingElementOpaque(
            area=27.5,
            is_unheated_pitched_roof=True,
            pitch=45,
            solar_absorption_coeff=0.63,
            thermal_resistance_construction=0.80,
            areal_heat_capacity=16000.0,
            mass_distribution_class=MassDistributionClass.D,
            orientation=Orientation360.create_from_180(-90),
            base_height=0,
            height=2.75,
            width=10,
            ext_cond=ec,
        )
        be_M = BuildingElementOpaque(
            area=30,
            is_unheated_pitched_roof=False,
            pitch=0,
            solar_absorption_coeff=0.64,
            thermal_resistance_construction=0.40,
            areal_heat_capacity=15000.0,
            mass_distribution_class=MassDistributionClass.M,
            orientation=Orientation360.create_from_180(0),
            base_height=0,
            height=3,
            width=10,
            ext_cond=ec,
        )

        # Put objects in a list that can be iterated over
        self.test_be_objs = [be_I, be_E, be_IE, be_D, be_M]

    def test_no_of_nodes(self):
        """Test that number of nodes (total and inside) have been calculated correctly"""
        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertEqual(be.no_of_nodes(), 5, "incorrect number of nodes")
                self.assertEqual(be.no_of_inside_nodes(), 3, "incorrect number of inside nodes")

    def test_area(self):
        """Test that correct area is returned when queried"""
        # Define increment between test cases
        area_inc = 2.5

        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertAlmostEqual(be.area, 20.0 + i * area_inc, msg="incorrect area returned")

    def test_heat_flow_direction(self):
        """Test that correct heat flow direction is returned when queried"""
        temp_int_air = 20.0
        temp_int_surface = [19.0, 21.0, 22.0, 21.0, 19.0]
        results = [
            HeatFlowDirection.DOWNWARDS,
            HeatFlowDirection.UPWARDS,
            HeatFlowDirection.HORIZONTAL,
            HeatFlowDirection.DOWNWARDS,
            HeatFlowDirection.UPWARDS,
        ]

        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertEqual(
                    be.heat_flow_direction(
                        temp_int_air=temp_int_air, temp_int_surface=temp_int_surface[i]
                    ),
                    results[i],
                    msg="incorrect heat flow direction returned",
                )

    def test_r_si(self):
        """Test that correct r_si is returned when queried"""
        results = [0.17, 0.17, 0.13, 0.10, 0.10]

        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertAlmostEqual(be.r_si(), results[i], 2, msg="incorrect r_si returned")

    def test_h_ci(self):
        """Test that correct h_ci is returned when queried"""
        temp_int_air = 20.0
        temp_int_surface = [19.0, 21.0, 22.0, 21.0, 19.0]
        results = [0.7, 5.0, 2.5, 0.7, 5.0]

        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertAlmostEqual(
                    be.h_ci(temp_int_air=temp_int_air, temp_int_surface=temp_int_surface[i]),
                    results[i],
                    msg="incorrect h_ci returned",
                )

    def test_h_ri(self):
        """Test that correct h_ri is returned when queried"""
        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertAlmostEqual(be.h_ri(), 5.13, msg="incorrect h_ri returned")

    def test_h_ce(self):
        """Test that correct h_ce is returned when queried"""
        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertAlmostEqual(be.h_ce(), 20.0, msg="incorrect h_ce returned")

    def test_h_re(self):
        """Test that correct h_re is returned when queried"""
        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertAlmostEqual(be.h_re(), 4.14, msg="incorrect h_re returned")

    def test_solar_absorption_coeff(self):
        """Test that correct solar_absorption_coeff is returned when queried"""
        # Define increment between test cases
        solar_absorption_coeff_inc = 0.01

        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertAlmostEqual(
                    be.solar_absorption_coeff,
                    0.6 + i * solar_absorption_coeff_inc,
                    msg="incorrect solar_absorption_coeff returned",
                )

    def test_therm_rad_to_sky(self):
        """Test that correct therm_rad_to_sky is returned when queried"""
        results = [0.0, 6.6691785923823135, 22.77, 38.87082140761768, 45.54]

        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertAlmostEqual(
                    be.therm_rad_to_sky,
                    results[i],
                    msg="incorrect therm_rad_to_sky returned",
                )

    def test_h_pli(self):
        """Test that correct h_pli list is returned when queried"""
        results = [
            [24.0, 12.0, 12.0, 24.0],
            [12.0, 6.0, 6.0, 12.0],
            [8.0, 4.0, 4.0, 8.0],
            [7.5, 3.75, 3.75, 7.5],
            [15.0, 7.5, 7.5, 15.0],
        ]
        for i, be in enumerate(self.test_be_objs):
            for j in range(0, be.no_of_nodes() - 1):
                with self.subTest(i=i * (be.no_of_nodes() - 1) + j):
                    self.assertEqual(be.h_pli(j), results[i][j], "incorrect h_pli returned")

    def test_k_pli(self):
        """Test that correct k_pli list is returned when queried"""
        results = [
            [0.0, 0.0, 0.0, 0.0, 19000.0],
            [18000.0, 0.0, 0.0, 0.0, 0.0],
            [8500.0, 0.0, 0.0, 0.0, 8500.0],
            [2000.0, 4000.0, 4000.0, 4000.0, 2000.0],
            [0.0, 0.0, 15000.0, 0.0, 0.0],
        ]
        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertEqual(be.k_pli, results[i], "incorrect k_pli list returned")

    def test_temp_ext(self):
        """Test that the correct external temperature is returned when queried"""
        for i, be in enumerate(self.test_be_objs):
            for t_idx, _, _ in self.simtime:
                with self.subTest(i=i * t_idx):
                    self.assertEqual(be.temp_ext(), t_idx * 5.0, "incorrect ext temp returned")

    def test_fabric_heat_loss(self):
        """Test that the correct fabric heat loss is returned when queried"""
        results = [43.20, 31.56, 27.10, 29.25, 55.54]

        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertAlmostEqual(
                    be.fabric_heat_loss(), results[i], 2, "incorrect fabric heat loss returned"
                )

    def test_heat_capacity(self):
        """Test that the correct heat capacity is returned when queried"""
        results = [380, 405, 425, 440, 450]

        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertEqual(be.heat_capacity(), results[i], "incorrect heat capacity returned")


class TestBuildingElementAdjacentConditionedSpace(unittest.TestCase):
    """Unit tests for BuildingElementAdjacentConditionedSpace class"""

    def setUp(self):
        """Create BuildingElementAdjacentConditionedSpace objects to be tested"""
        self.simtime = SimulationTime(start_time=0, end_time=4, step=1)
        ec = ExternalConditions(
            simulation_time=self.simtime,
            air_temps=[0.0, 5.0, 10.0, 15.0],
            wind_speeds=[],
            wind_directions=[],
            diffuse_horizontal_radiation=[0.0] * 4,
            direct_beam_radiation=[0.0] * 4,
            solar_reflectivity_of_ground=[],
            latitude=55.0,
            longitude=0.0,
            timezone=0,
            start_day=0,
            end_day=0,
            time_series_step=1,
            january_first=1,
            daylight_savings=None,
            leap_day_included=False,
            direct_beam_conversion_needed=False,
            shading_segments=None,
        )

        # Create an object for each mass distribution class
        be_I = BuildingElementAdjacentConditionedSpace(
            area=20.0,
            pitch=180,
            thermal_resistance_construction=0.25,
            areal_heat_capacity=19000.0,
            mass_distribution_class=MassDistributionClass.I,
            ext_cond=ec,
        )
        be_E = BuildingElementAdjacentConditionedSpace(
            area=22.5,
            pitch=135,
            thermal_resistance_construction=0.50,
            areal_heat_capacity=18000.0,
            mass_distribution_class=MassDistributionClass.E,
            ext_cond=ec,
        )
        be_IE = BuildingElementAdjacentConditionedSpace(
            area=25.0,
            pitch=90,
            thermal_resistance_construction=0.75,
            areal_heat_capacity=17000.0,
            mass_distribution_class=MassDistributionClass.IE,
            ext_cond=ec,
        )
        be_D = BuildingElementAdjacentConditionedSpace(
            area=27.5,
            pitch=45,
            thermal_resistance_construction=0.80,
            areal_heat_capacity=16000.0,
            mass_distribution_class=MassDistributionClass.D,
            ext_cond=ec,
        )
        be_M = BuildingElementAdjacentConditionedSpace(
            area=30.0,
            pitch=0,
            thermal_resistance_construction=0.40,
            areal_heat_capacity=15000.0,
            mass_distribution_class=MassDistributionClass.M,
            ext_cond=ec,
        )

        # Put objects in a list that can be iterated over
        self.test_be_objs = [be_I, be_E, be_IE, be_D, be_M]

    def test_no_of_nodes(self):
        """Test that number of nodes (total and inside) have been calculated correctly"""
        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertEqual(be.no_of_nodes(), 5, "incorrect number of nodes")
                self.assertEqual(be.no_of_inside_nodes(), 3, "incorrect number of inside nodes")

    def test_area(self):
        """Test that correct area is returned when queried"""
        # Define increment between test cases
        area_inc = 2.5

        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertAlmostEqual(be.area, 20.0 + i * area_inc, msg="incorrect area returned")

    def test_heat_flow_direction(self):
        """Test that correct heat flow direction is returned when queried"""
        temp_int_air = 20.0
        temp_int_surface = [19.0, 21.0, 22.0, 21.0, 19.0]
        results = [
            HeatFlowDirection.DOWNWARDS,
            HeatFlowDirection.UPWARDS,
            HeatFlowDirection.HORIZONTAL,
            HeatFlowDirection.DOWNWARDS,
            HeatFlowDirection.UPWARDS,
        ]

        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertEqual(
                    be.heat_flow_direction(
                        temp_int_air=temp_int_air, temp_int_surface=temp_int_surface[i]
                    ),
                    results[i],
                    msg="incorrect heat flow direction returned",
                )

    def test_r_si(self):
        """Test that correct r_si is returned when queried"""
        results = [0.17, 0.17, 0.13, 0.10, 0.10]

        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertAlmostEqual(be.r_si(), results[i], 2, msg="incorrect r_si returned")

    def test_h_ci(self):
        """Test that correct h_ci is returned when queried"""
        temp_int_air = 20.0
        temp_int_surface = [19.0, 21.0, 22.0, 21.0, 19.0]
        results = [0.7, 5.0, 2.5, 0.7, 5.0]

        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertAlmostEqual(
                    be.h_ci(temp_int_air=temp_int_air, temp_int_surface=temp_int_surface[i]),
                    results[i],
                    msg="incorrect h_ci returned",
                )

    def test_h_ri(self):
        """Test that correct h_ri is returned when queried"""
        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertAlmostEqual(be.h_ri(), 5.13, msg="incorrect h_ri returned")

    def test_h_ce(self):
        """Test that correct h_ce is returned when queried"""
        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertAlmostEqual(be.h_ce(), 0.0, msg="incorrect h_ce returned")

    def test_h_re(self):
        """Test that correct h_re is returned when queried"""
        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertAlmostEqual(be.h_re(), 0.0, msg="incorrect h_re returned")

    def test_solar_absorption_coeff(self):
        """Test that correct solar_absorption_coeff is returned when queried"""
        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertAlmostEqual(
                    be.solar_absorption_coeff, 0.0, msg="incorrect solar_absorption_coeff returned"
                )

    def test_therm_rad_to_sky(self):
        """Test that correct therm_rad_to_sky is returned when queried"""
        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertAlmostEqual(
                    be.therm_rad_to_sky,
                    0.0,
                    msg="incorrect therm_rad_to_sky returned",
                )

    def test_h_pli(self):
        """Test that correct h_pli list is returned when queried"""
        results = [
            [24.0, 12.0, 12.0, 24.0],
            [12.0, 6.0, 6.0, 12.0],
            [8.0, 4.0, 4.0, 8.0],
            [7.5, 3.75, 3.75, 7.5],
            [15.0, 7.5, 7.5, 15.0],
        ]
        for i, be in enumerate(self.test_be_objs):
            for j in range(be.no_of_nodes() - 1):
                with self.subTest(i=i * (be.no_of_nodes() - 1) + j):
                    self.assertEqual(be.h_pli(j), results[i][j], "incorrect h_pli returned")

    def test_k_pli(self):
        """Test that correct k_pli list is returned when queried"""
        results = [
            [0.0, 0.0, 0.0, 0.0, 19000.0],
            [18000.0, 0.0, 0.0, 0.0, 0.0],
            [8500.0, 0.0, 0.0, 0.0, 8500.0],
            [2000.0, 4000.0, 4000.0, 4000.0, 2000.0],
            [0.0, 0.0, 15000.0, 0.0, 0.0],
        ]
        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertEqual(be.k_pli, results[i], "incorrect k_pli list returned")

    # No test for temp_ext - not relevant as the external wall bounds ZTC not the external environment

    def test_fabric_heat_loss(self):
        """Test that the correct fabric heat loss is returned when queried"""
        results = [0.0, 0.0, 0.0, 0.0, 0.0]

        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertEqual(
                    be.fabric_heat_loss(), results[i], "incorrect fabric heat loss returned"
                )

    def test_heat_capacity(self):
        """Test that the correct heat capacity is returned when queried"""
        results = [380, 405, 425, 440, 450]

        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertEqual(be.heat_capacity(), results[i], "incorrect heat capacity returned")


class TestBuildingElementGround(unittest.TestCase):
    """Unit tests for BuildingElementGround class"""

    def setUp(self):
        """Create BuildingElementGround objects to be tested"""
        self.simtime = SimulationTime(start_time=742, end_time=746, step=1)

        air_temp_day_Jan = [
            0.0,
            0.5,
            1.0,
            1.5,
            2.0,
            2.5,
            3.0,
            3.5,
            4.0,
            4.5,
            5.0,
            7.5,
            10.0,
            12.5,
            15.0,
            19.5,
            17.0,
            15.0,
            12.0,
            10.0,
            7.0,
            5.0,
            3.0,
            1.0,
        ]
        air_temp_day_Feb = [x + 1.0 for x in air_temp_day_Jan]
        air_temp_day_Mar = [x + 2.0 for x in air_temp_day_Jan]
        air_temp_day_Apr = [x + 3.0 for x in air_temp_day_Jan]
        air_temp_day_May = [x + 4.0 for x in air_temp_day_Jan]
        air_temp_day_Jun = [x + 5.0 for x in air_temp_day_Jan]
        air_temp_day_Jul = [x + 6.0 for x in air_temp_day_Jan]
        air_temp_day_Aug = [x + 6.0 for x in air_temp_day_Jan]
        air_temp_day_Sep = [x + 5.0 for x in air_temp_day_Jan]
        air_temp_day_Oct = [x + 4.0 for x in air_temp_day_Jan]
        air_temp_day_Nov = [x + 3.0 for x in air_temp_day_Jan]
        air_temp_day_Dec = [x + 2.0 for x in air_temp_day_Jan]

        airtemp = []
        airtemp.extend(air_temp_day_Jan * 31)
        airtemp.extend(air_temp_day_Feb * 28)
        airtemp.extend(air_temp_day_Mar * 31)
        airtemp.extend(air_temp_day_Apr * 30)
        airtemp.extend(air_temp_day_May * 31)
        airtemp.extend(air_temp_day_Jun * 30)
        airtemp.extend(air_temp_day_Jul * 31)
        airtemp.extend(air_temp_day_Aug * 31)
        airtemp.extend(air_temp_day_Sep * 30)
        airtemp.extend(air_temp_day_Oct * 31)
        airtemp.extend(air_temp_day_Nov * 30)
        airtemp.extend(air_temp_day_Dec * 31)

        ec = ExternalConditions(
            simulation_time=self.simtime,
            air_temps=airtemp,
            wind_speeds=[2] * 8760,
            wind_directions=[180] * 8760,
            diffuse_horizontal_radiation=[0.0] * 8760,
            direct_beam_radiation=[0.0] * 8760,
            solar_reflectivity_of_ground=[],
            latitude=55.0,
            longitude=0.0,
            timezone=0,
            start_day=0,
            end_day=0,
            time_series_step=1,
            january_first=0,
            daylight_savings=False,
            leap_day_included=False,
            direct_beam_conversion_needed=False,
            shading_segments=None,
        )
        # TODO implement rest of external conditions in unit tests

        # Create an object for each mass distribution class
        be_I = BuildingElementGround(
            total_area=20.0,
            area=20.0,
            pitch=180,
            u_value=1.5,
            thermal_resistance_floor_construction=0.1,
            areal_heat_capacity=19000.0,
            mass_distribution_class=MassDistributionClass.I,
            floor_type=FloorType.SUSPENDED_FLOOR,
            edge_insulation=None,
            h_upper=0.5,
            u_f_s=0.0,
            u_w=0.5,
            area_per_perimeter_vent=0.01,
            shield_fact_location=WindShieldLocation.SHELTERED,
            d_we=0.3,
            r_f_ins=7,
            z_b=0.0,
            r_w_b=0.0,
            h_w=0.0,
            perimeter=18.0,
            psi_wall_floor_junc=0.5,
            ext_cond=ec,
            simulation_time=self.simtime,
        )
        be_E = BuildingElementGround(
            total_area=22.5,
            area=22.5,
            pitch=135,
            u_value=1.4,
            thermal_resistance_floor_construction=0.2,
            areal_heat_capacity=18000.0,
            mass_distribution_class=MassDistributionClass.E,
            floor_type=FloorType.SLAB_NO_EDGE_INSULATION,
            edge_insulation=None,
            h_upper=0.0,
            u_f_s=0.0,
            u_w=0.0,
            area_per_perimeter_vent=0.0,
            shield_fact_location=None,
            d_we=0.3,
            r_f_ins=0.0,
            z_b=0.0,
            r_w_b=0.0,
            h_w=0.0,
            perimeter=19.0,
            psi_wall_floor_junc=0.6,
            ext_cond=ec,
            simulation_time=self.simtime,
        )
        be_IE = BuildingElementGround(
            total_area=25.0,
            area=25.0,
            pitch=90,
            u_value=1.33,
            thermal_resistance_floor_construction=0.2,
            areal_heat_capacity=17000.0,
            mass_distribution_class=MassDistributionClass.IE,
            floor_type=FloorType.SLAB_EDGE_INSULATION,
            edge_insulation=[
                {
                    "type": EdgeInsulationDirection.HORIZONTAL,
                    "width": 3.0,
                    "edge_thermal_resistance": 2.0,
                },
                {
                    "type": EdgeInsulationDirection.VERTICAL,
                    "depth": 1.0,
                    "edge_thermal_resistance": 2.0,
                },
            ],
            h_upper=0.0,
            u_f_s=0.0,
            u_w=0.0,
            area_per_perimeter_vent=0.0,
            shield_fact_location=None,
            d_we=0.3,
            r_f_ins=0.0,
            z_b=0.0,
            r_w_b=0.0,
            h_w=0.0,
            perimeter=20.0,
            psi_wall_floor_junc=0.7,
            ext_cond=ec,
            simulation_time=self.simtime,
        )
        be_D = BuildingElementGround(
            total_area=27.5,
            area=27.5,
            pitch=45,
            u_value=1.25,
            thermal_resistance_floor_construction=0.2,
            areal_heat_capacity=16000.0,
            mass_distribution_class=MassDistributionClass.D,
            floor_type=FloorType.HEATED_BASEMENT,
            edge_insulation=None,
            h_upper=0.0,
            u_f_s=0.0,
            u_w=0.0,
            area_per_perimeter_vent=0.0,
            shield_fact_location=None,
            d_we=0.3,
            r_f_ins=0.0,
            z_b=2.3,
            r_w_b=6,
            h_w=0.0,
            perimeter=21.0,
            psi_wall_floor_junc=0.8,
            ext_cond=ec,
            simulation_time=self.simtime,
        )
        be_M = BuildingElementGround(
            total_area=30.0,
            area=30.0,
            pitch=0,
            u_value=1.0,
            thermal_resistance_floor_construction=0.3,
            areal_heat_capacity=15000.0,
            mass_distribution_class=MassDistributionClass.M,
            floor_type=FloorType.UNHEATED_BASEMENT,
            edge_insulation=None,
            h_upper=0.0,
            u_f_s=1.2,
            u_w=0.5,
            area_per_perimeter_vent=0.0,
            shield_fact_location=None,
            d_we=0.3,
            r_f_ins=0.0,
            z_b=2.3,
            r_w_b=0.15,
            h_w=2.3,
            perimeter=22.0,
            psi_wall_floor_junc=0.9,
            ext_cond=ec,
            simulation_time=self.simtime,
        )

        # Put objects in a list that can be iterated over
        self.test_be_objs = [be_I, be_E, be_IE, be_D, be_M]

    def test_init_invalid_floor_type(self):
        """That that the constructor throws on an invalid floor type"""
        with self.assertRaises(ValueError):
            BuildingElementGround(
                total_area=30.0,
                area=30.0,
                pitch=0,
                u_value=1.0,
                thermal_resistance_floor_construction=0.3,
                areal_heat_capacity=15000.0,
                mass_distribution_class=MassDistributionClass.M,
                floor_type="invalid",  # type: ignore[arg-type] # Testing error handling for invalid type
                edge_insulation=None,
                h_upper=0.0,
                u_f_s=1.2,
                u_w=0.5,
                area_per_perimeter_vent=0.0,
                shield_fact_location=None,
                d_we=0.3,
                r_f_ins=0.0,
                z_b=2.3,
                r_w_b=0.15,
                h_w=2.3,
                perimeter=22.0,
                psi_wall_floor_junc=0.9,
                ext_cond=MagicMock(ExternalConditions),
                simulation_time=self.simtime,
            )

    def test_init_invalid_edge_type(self):
        """Test that the constructor throws on an invalid edge type"""
        with self.assertRaises(ValueError):
            edges = [{"type": "invalid"}]
            BuildingElementGround(
                total_area=30.0,
                area=30.0,
                pitch=0,
                u_value=1.0,
                thermal_resistance_floor_construction=0.3,
                areal_heat_capacity=15000.0,
                mass_distribution_class=MassDistributionClass.M,
                floor_type=FloorType.SLAB_EDGE_INSULATION,
                edge_insulation=edges,
                h_upper=0.0,
                u_f_s=1.2,
                u_w=0.5,
                area_per_perimeter_vent=0.0,
                shield_fact_location=None,
                d_we=0.3,
                r_f_ins=0.0,
                z_b=2.3,
                r_w_b=0.15,
                h_w=2.3,
                perimeter=22.0,
                psi_wall_floor_junc=0.9,
                ext_cond=MagicMock(ExternalConditions),
                simulation_time=self.simtime,
            )

    def test_wind_shield_fact(self):
        """Test that the shield_fact_location affects the wind_s_factor from h_pi and h_pe values"""

        expected = {
            WindShieldLocation.SHELTERED: [21.76809338521401, 5208.393950400433],
            WindShieldLocation.AVERAGE: [20.285704885671986, 26144.01441657715],
            WindShieldLocation.EXPOSED: [19.75335084679448, 96370.39574909392],
        }

        ec = ExternalConditions(
            simulation_time=self.simtime,
            air_temps=[1] * 8760,
            wind_speeds=[1] * 8760,
            wind_directions=[],
            diffuse_horizontal_radiation=[0.0] * 8760,
            direct_beam_radiation=[0.0] * 8760,
            solar_reflectivity_of_ground=[],
            latitude=55.0,
            longitude=0.0,
            timezone=0,
            start_day=0,
            end_day=0,
            time_series_step=1,
            january_first=0,
            daylight_savings=False,
            leap_day_included=False,
            direct_beam_conversion_needed=False,
            shading_segments=None,
        )

        for shield_fact_location in expected.keys():
            with self.subTest(shield_fact_location=shield_fact_location):
                element = BuildingElementGround(
                    total_area=30.0,
                    area=30.0,
                    pitch=0,
                    u_value=1.0,
                    thermal_resistance_floor_construction=0.3,
                    areal_heat_capacity=15000.0,
                    mass_distribution_class=MassDistributionClass.M,
                    floor_type=FloorType.SUSPENDED_FLOOR,
                    edge_insulation=None,
                    h_upper=1,
                    u_f_s=1.2,
                    u_w=0.5,
                    area_per_perimeter_vent=1,
                    shield_fact_location=shield_fact_location,
                    d_we=0.3,
                    r_f_ins=1,
                    z_b=2.3,
                    r_w_b=0.15,
                    h_w=2.3,
                    perimeter=22.0,
                    psi_wall_floor_junc=0.9,
                    ext_cond=ec,
                    simulation_time=self.simtime,
                )

                self.assertAlmostEqual(
                    element._HeatTransferOtherSideGround__h_pi, expected[shield_fact_location][0]
                )
                self.assertAlmostEqual(
                    element._HeatTransferOtherSideGround__h_pe, expected[shield_fact_location][1]
                )

    def test_wind_shield_fact_invalid_location(self):
        """Test that the constructor throws on an invalid shield_fact_location"""

        ec = ExternalConditions(
            simulation_time=self.simtime,
            air_temps=[1] * 8760,
            wind_speeds=[1] * 8760,
            wind_directions=[],
            diffuse_horizontal_radiation=[0.0] * 8760,
            direct_beam_radiation=[0.0] * 8760,
            solar_reflectivity_of_ground=[],
            latitude=55.0,
            longitude=0.0,
            timezone=0,
            start_day=0,
            end_day=0,
            time_series_step=1,
            january_first=0,
            daylight_savings=False,
            leap_day_included=False,
            direct_beam_conversion_needed=False,
            shading_segments=None,
        )

        with self.assertRaises(ValueError):
            BuildingElementGround(
                total_area=30.0,
                area=30.0,
                pitch=0,
                u_value=1.0,
                thermal_resistance_floor_construction=0.3,
                areal_heat_capacity=15000.0,
                mass_distribution_class=MassDistributionClass.M,
                floor_type=FloorType.SUSPENDED_FLOOR,
                edge_insulation=None,
                h_upper=1,
                u_f_s=1.2,
                u_w=0.5,
                area_per_perimeter_vent=1,
                shield_fact_location="invalid",  # type: ignore[arg-type] # Testing error handling for invalid type
                d_we=0.3,
                r_f_ins=1,
                z_b=2.3,
                r_w_b=0.15,
                h_w=2.3,
                perimeter=22.0,
                psi_wall_floor_junc=0.9,
                ext_cond=ec,
                simulation_time=self.simtime,
            )

    def test_no_of_nodes(self):
        """Test that number of nodes (total and inside) have been calculated correctly"""
        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertEqual(be.no_of_nodes(), 5, "incorrect number of nodes")
                self.assertEqual(be.no_of_inside_nodes(), 3, "incorrect number of inside nodes")

    def test_area(self):
        """Test that correct area is returned when queried"""
        # Define increment between test cases
        area_inc = 2.5

        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertAlmostEqual(be.area, 20.0 + i * area_inc, msg="incorrect area returned")

    def test_heat_flow_direction(self):
        """Test that correct heat flow direction is returned when queried"""
        temp_int_air = 20.0
        temp_int_surface = [19.0, 21.0, 22.0, 21.0, 19.0]
        results = [
            HeatFlowDirection.DOWNWARDS,
            HeatFlowDirection.UPWARDS,
            HeatFlowDirection.HORIZONTAL,
            HeatFlowDirection.DOWNWARDS,
            HeatFlowDirection.UPWARDS,
        ]

        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertEqual(
                    be.heat_flow_direction(
                        temp_int_air=temp_int_air, temp_int_surface=temp_int_surface[i]
                    ),
                    results[i],
                    msg="incorrect heat flow direction returned",
                )

    def test_r_si(self):
        """Test that correct r_si is returned when queried"""
        results = [0.17, 0.17, 0.13, 0.10, 0.10]

        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertAlmostEqual(be.r_si(), results[i], 2, msg="incorrect r_si returned")

    def test_h_ci(self):
        """Test that correct h_ci is returned when queried"""
        temp_int_air = 20.0
        temp_int_surface = [19.0, 21.0, 22.0, 21.0, 19.0]
        results = [0.7, 5.0, 2.5, 0.7, 5.0]

        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertAlmostEqual(
                    be.h_ci(temp_int_air, temp_int_surface[i]),
                    results[i],
                    msg="incorrect h_ci returned",
                )

    def test_h_ri(self):
        """Test that correct h_ri is returned when queried"""
        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertAlmostEqual(be.h_ri(), 5.13, msg="incorrect h_ri returned")

    def test_h_ce(self):
        """Test that correct h_ce is returned when queried"""
        results = [15.78947368, 91.30434783, 20.59886422, 10.34482759, 5.084745763]

        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertAlmostEqual(be.h_ce(), results[i], msg="incorrect h_ce returned")

    def test_h_re(self):
        """Test that correct h_re is returned when queried"""
        # Define increment between test cases
        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertAlmostEqual(be.h_re(), 0.0, msg="incorrect h_re returned")

    def test_solar_absorption_coeff(self):
        """Test that correct solar_absorption_coeff is returned when queried"""
        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertAlmostEqual(
                    be.solar_absorption_coeff, 0.0, msg="incorrect solar_absorption_coeff returned"
                )

    def test_therm_rad_to_sky(self):
        """Test that correct therm_rad_to_sky is returned when queried"""
        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertAlmostEqual(
                    be.therm_rad_to_sky,
                    0.0,
                    msg="incorrect therm_rad_to_sky returned",
                )

    def test_h_pli(self):
        """Test that correct h_pli list is returned when queried"""
        results = [
            [6.0, 5.217391304347826, 20.0, 40.0],
            [6.0, 4.615384615384615, 10.0, 20.0],
            [6.0, 4.615384615384615, 10.0, 20.0],
            [6.0, 4.615384615384615, 10.0, 20.0],
            [6.0, 4.137931034482759, 6.666666666666667, 13.333333333333334],
        ]
        for i, be in enumerate(self.test_be_objs):
            for j in range(be.no_of_nodes() - 1):
                with self.subTest(i=i * (be.no_of_nodes() - 1) + j):
                    self.assertEqual(be.h_pli(j), results[i][j], "incorrect h_pli returned")

    def test_k_pli(self):
        """Test that correct k_pli list is returned when queried"""
        results = [
            [0.0, 1500000.0, 0.0, 0.0, 19000.0],
            [0.0, 1500000.0, 18000.0, 0.0, 0.0],
            [0.0, 1500000.0, 8500.0, 0.0, 8500.0],
            [0.0, 1500000.0, 4000.0, 8000.0, 4000.0],
            [0.0, 1500000.0, 0.0, 15000.0, 0.0],
        ]
        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertEqual(be.k_pli, results[i], "incorrect k_pli list returned")

    def test_temp_ext(self):
        """Test that the correct external temperature is returned when queried"""
        results = [
            [-0.6471789638993641, -0.6471789638993641, 2.505131315506123, 2.505131315506123],
            [7.428039862980361, 7.428039862980361, 8.234778286483786, 8.234778286483786],
            [7.732888552541917, 7.732888552541917, 8.448604706949336, 8.448604706949336],
            [8.366361777378224, 8.366361777378224, 8.86671506616569, 8.86671506616569],
            [6.293446005722892, 6.293446005722892, 7.413004622032444, 7.413004622032444],
        ]
        for t_idx, _, _ in self.simtime:
            for i, be in enumerate(self.test_be_objs):
                with self.subTest(i=i + len(self.test_be_objs) * t_idx):
                    self.assertEqual(
                        be.temp_ext(), results[i][t_idx], "incorrect ext temp returned"
                    )

    def test_fabric_heat_loss(self):
        """Test that the correct fabric heat loss is returned when queried"""
        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertAlmostEqual(
                    be.fabric_heat_loss(),
                    [30.0, 31.5, 33.25, 34.375, 30.0][i],
                    2,
                    "incorrect fabric heat loss returned",
                )

    def test_heat_capacity(self):
        """Test that the correct heat capacity is returned when queried"""
        results = [380, 405, 425, 440, 450]

        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertEqual(be.heat_capacity(), results[i], "incorrect heat capacity returned")


class TestSolarRadiationInteraction(unittest.TestCase):
    def setUp(self):
        class SolarRadiationInteractionConcrete(SolarRadiationInteraction):
            def r_se(self) -> float:
                raise NotImplementedError  # pragma: no cover

            def r_si(self) -> float:
                raise NotImplementedError  # pragma: no cover

        self.solarRadiationInteraction = SolarRadiationInteractionConcrete(
            pitch=0.0,
            orientation=None,
            shading=None,
            base_height=0.0,
            projected_height=0.0,
            width=0.0,
            solar_absorption_coeff=0.0,
        )

    def test_i_sol_dir_dif(self):
        """Test that i_sol_dir_dif returns the defaults of 0"""
        self.assertEqual(self.solarRadiationInteraction.i_sol_dir_dif(), (0, 0))

    def test_solar_gains(self):
        """Test that solar_gains returns the default of 0"""
        self.assertEqual(self.solarRadiationInteraction.solar_gains(), 0)

    def test_shading_factors_direct_diffuse(self):
        """Test that shading_factors_direct_diffuse returns the defaults of 1"""
        self.assertEqual(self.solarRadiationInteraction.shading_factors_direct_diffuse(), (1, 1))


class TestSolarRadiationInteractionAbsorbed(unittest.TestCase):
    def test_orientation_none(self):
        class SolarRadiationInteractionAbsorbedTest(SolarRadiationInteractionAbsorbed):
            def r_se(self) -> float:
                raise NotImplementedError  # pragma: no cover

            def r_si(self) -> float:
                raise NotImplementedError  # pragma: no cover

        solarRadiationInteractionAbsorbed = SolarRadiationInteractionAbsorbedTest(
            pitch=30,
            orientation=None,
            shading=None,
            base_height=0.5,
            projected_height=0.5,
            width=0.3,
            solar_absorption_coeff=0.1,
        )

        self.assertEqual(solarRadiationInteractionAbsorbed._orientation, None)
        with self.assertRaises(ValueError):
            solarRadiationInteractionAbsorbed.i_sol_dir_dif()

        with self.assertRaises(ValueError):
            solarRadiationInteractionAbsorbed.shading_factors_direct_diffuse()


class TestSolarRadiationInteractionTransmitted(unittest.TestCase):
    def test_convert_g_value(self):
        """Test that convert_g_value converts its g_value based on a factor of 0.9"""
        simtime = SimulationTime(start_time=0, end_time=4, step=1)

        class SolarRadiationInteractionTransmittedConcrete(SolarRadiationInteractionTransmitted):
            def r_se(self) -> float:
                raise NotImplementedError  # pragma: no cover

            def r_si(self) -> float:
                raise NotImplementedError  # pragma: no cover

        s = SolarRadiationInteractionTransmittedConcrete(
            simtime=simtime,
            pitch=40,
            orientation=Orientation360.create_from_180(50),
            shading={},
            base_height=1,
            projected_height=2,
            width=2,
            solar_absorption_coeff=0.8,
        )
        s._g_value = 0.5

        self.assertAlmostEqual(s.convert_g_value(), 0.45)

    def test_solar_gains(self):
        """Test that solar_gains returns the correct value based on the SolarRadiationInteractionTransmitted parameters"""
        ec = MagicMock()
        ec.surface_irradiance.return_value = 0.5
        simtime = SimulationTime(start_time=0, end_time=4, step=1)

        class SolarRadiationInteractionTransmittedConcrete(SolarRadiationInteractionTransmitted):
            def r_se(self) -> float:
                raise NotImplementedError  # pragma: no cover

            def r_si(self) -> float:
                raise NotImplementedError  # pragma: no cover

        s = SolarRadiationInteractionTransmittedConcrete(
            simtime=simtime,
            pitch=40,
            orientation=Orientation360.create_from_180(50),
            shading={},
            base_height=1,
            projected_height=2,
            width=2,
            solar_absorption_coeff=0.8,
        )
        s._g_value = 0.5
        s._pitch = 20
        s._external_conditions = ec
        s.area = 5
        s._frame_area_fraction = 0.2

        self.assertAlmostEqual(s.solar_gains(), 0.9)

    def test_solar_gains_error(self):
        simtime = SimulationTime(0, 4, 1)

        class SolarRadiationInteractionTransmittedConcrete(SolarRadiationInteractionTransmitted):
            def r_se(self) -> float:
                raise NotImplementedError  # pragma: no cover

            def r_si(self) -> float:
                raise NotImplementedError  # pragma: no cover

        s_test1 = SolarRadiationInteractionTransmittedConcrete(
            simtime=simtime,
            pitch=40,
            orientation=None,
            shading=[],
            base_height=1,
            projected_height=2,
            width=2,
            solar_absorption_coeff=0.8,
        )
        s_test2 = SolarRadiationInteractionTransmittedConcrete(
            simtime=simtime,
            pitch=40,
            orientation=Orientation360.create_from_180(50),
            shading=None,
            base_height=1,
            projected_height=2,
            width=2,
            solar_absorption_coeff=0.8,
        )
        s_test1._g_value = 0.5
        s_test2._g_value = 0.5

        with self.assertRaises(ValueError):
            s_test1.solar_gains()
        with self.assertRaises(ValueError):
            s_test2.solar_gains()
        with self.assertRaises(ValueError):
            s_test1.shading_factors_direct_diffuse()
        with self.assertRaises(ValueError):
            s_test2.shading_factors_direct_diffuse()


class TestBuildingElementTransparent(unittest.TestCase):
    """Unit tests for BuildingElementTransparent class"""

    def setUp(self):
        """Create BuildingElementTransparent object to be tested"""
        self.simtime = SimulationTime(start_time=0, end_time=4, step=1)
        self.ec = ExternalConditions(
            simulation_time=self.simtime,
            air_temps=[0.0, 5.0, 10.0, 15.0],
            wind_speeds=[],
            wind_directions=[],
            diffuse_horizontal_radiation=[0.0] * 4,
            direct_beam_radiation=[0.0] * 4,
            solar_reflectivity_of_ground=[0.0] * 4,
            latitude=55.0,
            longitude=0.0,
            timezone=0,
            start_day=0,
            end_day=0,
            time_series_step=1,
            january_first=1,
            daylight_savings=None,
            leap_day_included=False,
            direct_beam_conversion_needed=False,
            shading_segments=None,
        )

        # TODO implement rest of external conditions in unit tests
        self.be = BuildingElementTransparent(
            pitch=90,
            thermal_resistance_construction=0.4,
            orientation=Orientation360.create_from_180(180),
            g_value=0.75,
            frame_area_fraction=0.25,
            base_height=1,
            height=1.25,
            width=4,
            shading={},
            treatment=[],
            ext_cond=self.ec,
            simtime=self.simtime,
        )

    def test_no_of_nodes(self):
        """Test that number of nodes (total and inside) have been calculated correctly"""
        self.assertEqual(self.be.no_of_nodes(), 2, "incorrect number of nodes")
        self.assertEqual(self.be.no_of_inside_nodes(), 0, "incorrect number of inside nodes")

    def test_area(self):
        """Test that correct area is returned when queried"""
        self.assertEqual(self.be.area, 5.0, "incorrect area returned")

    def test_heat_flow_direction(self):
        """Test that correct heat flow direction is returned when queried"""
        self.assertEqual(
            self.be.heat_flow_direction(temp_int_air=10.0, temp_int_surface=10.0),
            HeatFlowDirection.HORIZONTAL,
            "incorrect heat flow direction returned",
        )

    def test_r_si(self):
        """Test that correct r_si is returned when queried"""
        self.assertAlmostEqual(self.be.r_si(), 0.13, 2, "incorrect r_si returned")

    def test_h_ci(self):
        """Test that correct h_ci is returned when queried"""
        self.assertEqual(
            self.be.h_ci(temp_int_air=10.0, temp_int_surface=10.0), 2.5, "incorrect h_ci returned"
        )

    def test_h_ri(self):
        """Test that correct h_ri is returned when queried"""
        self.assertEqual(self.be.h_ri(), 5.13, "incorrect h_ri returned")

    def test_h_ce(self):
        """Test that correct h_ce is returned when queried"""
        self.assertEqual(self.be.h_ce(), 20.0, "incorrect h_ce returned")

    def test_h_re(self):
        """Test that correct h_re is returned when queried"""
        self.assertEqual(self.be.h_re(), 4.14, "incorrect h_re returned")

    def test_solar_absorption_coeff(self):
        """Test that correct solar_absorption_coeff is returned when queried"""
        self.assertEqual(
            self.be.solar_absorption_coeff, 0.0, "non-zero solar_absorption_coeff returned"
        )

    def test_therm_rad_to_sky(self):
        """Test that correct therm_rad_to_sky is returned when queried"""
        self.assertEqual(self.be.therm_rad_to_sky, 22.77, "incorrect therm_rad_to_sky returned")

    def test_h_pli(self):
        """Test that correct h_pli list is returned when queried"""
        for i in range(0, self.be.no_of_nodes() - 1):
            with self.subTest(i=i):
                self.assertEqual(self.be.h_pli(i), [2.5, 0.0][i], "incorrect h_pli returned")

    def test_h_pli_with_treatment(self):
        """Test that correct h_pli list is returned when queried"""
        treatment = [
            {
                "type": "curtains",
                "is_open": False,
                "delta_r": 0.2,
                "controls": "manual",
                "Control_open": None,
                "Control_opening_irrad": None,
                "Control_closing_irrad": None,
            }
        ]

        self.be = BuildingElementTransparent(
            pitch=90,
            thermal_resistance_construction=0.4,
            orientation=Orientation360.create_from_180(180),
            g_value=0.75,
            frame_area_fraction=0.25,
            base_height=1,
            height=1.25,
            width=4,
            shading={},
            treatment=treatment,
            ext_cond=self.ec,
            simtime=self.simtime,
        )

        for i in range(0, self.be.no_of_nodes() - 1):
            with self.subTest(i=i):
                self.assertEqual(
                    self.be.h_pli(i), [1.6666666666666665, 0.0][i], "incorrect h_pli returned"
                )

    def test_k_pli(self):
        """Test that correct k_pli list is returned when queried"""
        self.assertEqual(self.be.k_pli, [0.0, 0.0], "non-zero k_pli list returned")

    def test_temp_ext(self):
        """Test that the correct external temperature is returned when queried"""
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.be.temp_ext(),
                    t_idx * 5.0,
                    "incorrect ext temp returned",
                )

    def test_solar_gains(self):
        """Test that the correct solar_gains is returned when queried"""
        ec = MagicMock()
        ec.surface_irradiance.return_value = 10

        self.be = BuildingElementTransparent(
            pitch=90,
            thermal_resistance_construction=0.4,
            orientation=Orientation360.create_from_180(180),
            g_value=0.75,
            frame_area_fraction=0.25,
            base_height=1,
            height=1.25,
            width=4,
            shading={},
            treatment=[],
            ext_cond=ec,
            simtime=self.simtime,
        )
        self.assertEqual(self.be.solar_gains(), 25.3125)

    def test_solar_gains_with_treatment(self):
        """Test that the correct solar_gains is returned for open and non-open treatments"""
        ec = MagicMock()
        ec.surface_irradiance.return_value = 10

        treatment = [
            {
                "type": "curtains",
                "is_open": False,
                "delta_r": 0.2,
                "controls": "manual",
                "Control_open": None,
                "Control_opening_irrad": None,
                "Control_closing_irrad": None,
                "trans_red": 0.3,
            }
        ]

        self.be = BuildingElementTransparent(
            pitch=90,
            thermal_resistance_construction=0.4,
            orientation=Orientation360.create_from_180(180),
            g_value=0.75,
            frame_area_fraction=0.25,
            base_height=1,
            height=1.25,
            width=4,
            shading={},
            treatment=treatment,
            ext_cond=ec,
            simtime=self.simtime,
        )
        self.assertEqual(self.be.solar_gains(), 17.71875)

        treatment[0]["is_open"] = True
        self.assertEqual(self.be.solar_gains(), 25.3125)

    def test_adjust_treatment_open(self):
        """Test that _adjust_treatment opens when control is on"""
        ec = MagicMock()
        ec.surface_irradiance.return_value = 10

        control = MagicMock()
        control.is_on.return_value = True
        control.setpnt.return_value = 20

        treatment = [
            {
                "type": "curtains",
                "is_open": False,
                "delta_r": 0.2,
                "controls": "manual",
                "Control_open": control,
                "Control_opening_irrad": control,
                "Control_closing_irrad": control,
                "trans_red": 0.3,
            }
        ]

        self.be = BuildingElementTransparent(
            pitch=90,
            thermal_resistance_construction=0.4,
            orientation=Orientation360.create_from_180(180),
            g_value=0.75,
            frame_area_fraction=0.25,
            base_height=1,
            height=1.25,
            width=4,
            shading={},
            treatment=treatment,
            ext_cond=ec,
            simtime=self.simtime,
        )

        self.be._adjust_treatment()

        self.assertTrue(treatment[0]["is_open"])

    def test_adjust_treatment_not_opened(self):
        """Test that _adjust_treatment doesn't open when control is off"""
        ec = MagicMock()
        ec.surface_irradiance.return_value = 10

        control = MagicMock()
        control.is_on.return_value = False
        control.setpnt.return_value = 20

        treatment = [
            {
                "type": "curtains",
                "is_open": False,
                "delta_r": 0.2,
                "controls": "manual",
                "Control_open": control,
                "Control_opening_irrad": control,
                "Control_closing_irrad": control,
                "trans_red": 0.3,
            }
        ]

        self.be = BuildingElementTransparent(
            pitch=90,
            thermal_resistance_construction=0.4,
            orientation=Orientation360.create_from_180(180),
            g_value=0.75,
            frame_area_fraction=0.25,
            base_height=1,
            height=1.25,
            width=4,
            shading={},
            treatment=treatment,
            ext_cond=ec,
            simtime=self.simtime,
        )

        self.be._adjust_treatment()

        self.assertFalse(treatment[0]["is_open"])

    def test_adjust_treatment_close(self):
        """Test that _adjust_treatment closes when control is off"""
        ec = MagicMock()
        ec.surface_irradiance.return_value = 10

        control = MagicMock()
        control.is_on.return_value = False
        control.setpnt.return_value = 20

        treatment = [
            {
                "type": "curtains",
                "is_open": True,
                "delta_r": 0.2,
                "controls": "manual",
                "Control_open": control,
                "Control_opening_irrad": control,
                "Control_closing_irrad": control,
                "trans_red": 0.3,
            }
        ]

        self.be = BuildingElementTransparent(
            pitch=90,
            thermal_resistance_construction=0.4,
            orientation=Orientation360.create_from_180(180),
            g_value=0.75,
            frame_area_fraction=0.25,
            base_height=1,
            height=1.25,
            width=4,
            shading={},
            treatment=treatment,
            ext_cond=ec,
            simtime=self.simtime,
        )

        self.be._adjust_treatment()

        self.assertFalse(treatment[0]["is_open"])

    def test_adjust_treatment_not_closed(self):
        """Test that _adjust_treatment doesn't close when control is on"""
        ec = MagicMock()
        ec.surface_irradiance.return_value = 30

        control = MagicMock()
        control.is_on.return_value = True
        control.setpnt.return_value = 20

        treatment = [
            {
                "type": "curtains",
                "is_open": True,
                "delta_r": 0.2,
                "controls": "manual",
                "Control_open": control,
                "Control_opening_irrad": control,
                "Control_closing_irrad": control,
                "trans_red": 0.3,
            }
        ]

        self.be = BuildingElementTransparent(
            pitch=90,
            thermal_resistance_construction=0.4,
            orientation=Orientation360.create_from_180(180),
            g_value=0.75,
            frame_area_fraction=0.25,
            base_height=1,
            height=1.25,
            width=4,
            shading={},
            treatment=treatment,
            ext_cond=ec,
            simtime=self.simtime,
        )

        self.be._adjust_treatment()

        self.assertTrue(treatment[0]["is_open"])

    def test_adjust_treatment_open_irrad(self):
        """Test that _adjust_treatment opens from irradiance values"""
        ec = MagicMock()
        ec.surface_irradiance.return_value = 30

        control = MagicMock()
        control.is_on.return_value = False
        control.setpnt.return_value = 40

        treatment = [
            {
                "type": "curtains",
                "is_open": False,
                "delta_r": 0.2,
                "controls": "manual",
                "Control_open": None,
                "Control_opening_irrad": control,
                "Control_closing_irrad": control,
                "opening_delay_hrs": 0,
                "trans_red": 0.3,
            }
        ]

        self.be = BuildingElementTransparent(
            pitch=90,
            thermal_resistance_construction=0.4,
            orientation=Orientation360.create_from_180(180),
            g_value=0.75,
            frame_area_fraction=0.25,
            base_height=1,
            height=1.25,
            width=4,
            shading={},
            treatment=treatment,
            ext_cond=ec,
            simtime=self.simtime,
        )

        self.be._adjust_treatment()

        self.assertTrue(treatment[0]["is_open"])

    def test_adjust_treatment_close_irrad(self):
        """Test that _adjust_treatment closes from irradiance values"""
        ec = MagicMock()
        ec.surface_irradiance.return_value = 30

        control = MagicMock()
        control.is_on.return_value = False
        control.setpnt.return_value = 20

        treatment = [
            {
                "type": "curtains",
                "is_open": True,
                "delta_r": 0.2,
                "controls": "manual",
                "Control_open": None,
                "Control_opening_irrad": control,
                "Control_closing_irrad": control,
                "trans_red": 0.3,
            }
        ]

        self.be = BuildingElementTransparent(
            pitch=90,
            thermal_resistance_construction=0.4,
            orientation=Orientation360.create_from_180(180),
            g_value=0.75,
            frame_area_fraction=0.25,
            base_height=1,
            height=1.25,
            width=4,
            shading={},
            treatment=treatment,
            ext_cond=ec,
            simtime=self.simtime,
        )

        self.be._adjust_treatment()

        self.assertFalse(treatment[0]["is_open"])

    def test_adjust_treatment_invalid_control(self):
        """That that _adjust_treatment throws on invalid control value"""
        ec = MagicMock()
        ec.surface_irradiance.return_value = 30

        control = MagicMock()
        control.is_on.return_value = "Invalid"

        treatment = [
            {
                "type": "curtains",
                "is_open": False,
                "delta_r": 0.2,
                "controls": "manual",
                "Control_closing_irrad": None,
                "Control_opening_irrad": None,
                "Control_open": control,
                "opening_delay_hrs": 0,
                "trans_red": 0.3,
            }
        ]

        self.be = BuildingElementTransparent(
            pitch=90,
            thermal_resistance_construction=0.4,
            orientation=Orientation360.create_from_180(180),
            g_value=0.75,
            frame_area_fraction=0.25,
            base_height=1,
            height=1.25,
            width=4,
            shading={},
            treatment=treatment,
            ext_cond=ec,
            simtime=self.simtime,
        )

        with self.assertRaises(ValueError):
            self.be._adjust_treatment()

    def test_adjust_treatment_orientation_shading_error(self):
        ec = MagicMock()
        self.be_test1 = BuildingElementTransparent(
            pitch=90,
            thermal_resistance_construction=0.4,
            orientation=None,
            g_value=0.75,
            frame_area_fraction=0.25,
            base_height=1,
            height=1.25,
            width=4,
            shading=[],
            treatment=[],
            ext_cond=ec,
            simtime=self.simtime,
        )
        self.be_test2 = BuildingElementTransparent(
            pitch=90,
            thermal_resistance_construction=0.4,
            orientation=Orientation360.create_from_180(180),
            g_value=0.75,
            frame_area_fraction=0.25,
            base_height=1,
            height=1.25,
            width=4,
            shading=None,
            treatment=[],
            ext_cond=ec,
            simtime=self.simtime,
        )

        with self.assertRaises(ValueError):
            self.be_test1._adjust_treatment()
        with self.assertRaises(ValueError):
            self.be_test2._adjust_treatment()

    def test_fabric_heat_loss(self):
        """Test that correct fabric heat loss is returned when queried"""
        self.assertAlmostEqual(
            self.be.fabric_heat_loss(), 8.16, 2, msg="incorrect fabric heat loss returned"
        )

    def test_heat_capacity(self):
        """Test that the correct heat capacity is returned when queried"""
        self.assertEqual(self.be.heat_capacity(), 0, msg="incorrect heat capacity returned")

    def test_projected_height(self):
        """Test that the correct projected_height is returned when queried"""
        self.assertAlmostEqual(
            self.be.projected_height(), 1.25, msg="incorrect projected_height returned"
        )

    def test_mid_height(self):
        """Test that the correct mid_height is returned when queried"""
        self.assertAlmostEqual(self.be.mid_height(), 1.625, msg="incorrect min_height returned")

    def test_orientation(self):
        """Test that the correct orientation is returned when queried"""
        self.assertEqual(
            self.be.orientation().transform_to_180(), 180, msg="incorrect orientation returned"
        )


class TestBuildingElementAdjacentUnconditionedSpace_Simple(unittest.TestCase):
    def setUp(self):
        """Create BuildingElementAdjacentConditionedSpace_Simple objects to be tested"""
        self.simtime = SimulationTime(start_time=0, end_time=4, step=1)
        ec = ExternalConditions(
            simulation_time=self.simtime,
            air_temps=[0.0, 5.0, 10.0, 15.0],
            wind_speeds=[],
            wind_directions=[],
            diffuse_horizontal_radiation=[0.0] * 4,
            direct_beam_radiation=[0.0] * 4,
            solar_reflectivity_of_ground=[],
            latitude=55.0,
            longitude=0.0,
            timezone=0,
            start_day=0,
            end_day=0,
            time_series_step=1,
            january_first=0,
            daylight_savings=False,
            leap_day_included=False,
            direct_beam_conversion_needed=False,
            shading_segments=None,
        )
        # Create an object for each mass distribution class
        be_I = BuildingElementAdjacentUnconditionedSpace_Simple(
            area=20.0,
            pitch=180,
            thermal_resistance_construction=0.25,
            thermal_resistance_unconditioned_space=0.5,
            areal_heat_capacity=19000.0,
            mass_distribution_class=MassDistributionClass.I,
            ext_cond=ec,
        )
        be_E = BuildingElementAdjacentUnconditionedSpace_Simple(
            area=22.5,
            pitch=135,
            thermal_resistance_construction=0.50,
            thermal_resistance_unconditioned_space=1,
            areal_heat_capacity=18000.0,
            mass_distribution_class=MassDistributionClass.E,
            ext_cond=ec,
        )
        be_IE = BuildingElementAdjacentUnconditionedSpace_Simple(
            area=25.0,
            pitch=90,
            thermal_resistance_construction=0.75,
            thermal_resistance_unconditioned_space=1.5,
            areal_heat_capacity=17000.0,
            mass_distribution_class=MassDistributionClass.IE,
            ext_cond=ec,
        )
        be_D = BuildingElementAdjacentUnconditionedSpace_Simple(
            area=27.5,
            pitch=45,
            thermal_resistance_construction=0.80,
            thermal_resistance_unconditioned_space=2,
            areal_heat_capacity=16000.0,
            mass_distribution_class=MassDistributionClass.D,
            ext_cond=ec,
        )
        be_M = BuildingElementAdjacentUnconditionedSpace_Simple(
            area=30.0,
            pitch=0,
            thermal_resistance_construction=0.40,
            thermal_resistance_unconditioned_space=2.5,
            areal_heat_capacity=15000.0,
            mass_distribution_class=MassDistributionClass.M,
            ext_cond=ec,
        )

        # Put objects in a list that can be iterated over
        self.test_be_objs = [be_I, be_E, be_IE, be_D, be_M]

    def test_h_ce(self):
        """Test that correct h_ce is returned when queried"""

        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertAlmostEqual(
                    be.h_ce(),
                    [
                        1.8469778117827087,
                        0.960222752585521,
                        0.6487503359312012,
                        0.4898538961038961,
                        0.39348003259983705,
                    ][i],
                    msg="incorrect h_ce returned",
                )

    def test_h_re(self):
        """Test that correct h_re is returned when queried"""

        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertAlmostEqual(
                    be.h_re(), [0.0, 0.0, 0.0, 0.0, 0.0][i], msg="incorrect h_re returned"
                )

    def test_temp_ext(self):
        """Test that the correct external temperature is returned when queried"""
        results = [
            [0.0, 5.0, 10.0, 15.0],
            [0.0, 5.0, 10.0, 15.0],
            [0.0, 5.0, 10.0, 15.0],
            [0.0, 5.0, 10.0, 15.0],
            [0.0, 5.0, 10.0, 15.0],
        ]
        for t_idx, _, _ in self.simtime:
            for i, be in enumerate(self.test_be_objs):
                with self.subTest(i=i + len(self.test_be_objs) * t_idx):
                    self.assertAlmostEqual(be.temp_ext(), results[i][t_idx])

    def test_fabric_heat_loss(self):
        """Test that the correct fabric heat loss is returned when queried"""
        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertAlmostEqual(
                    be.fabric_heat_loss(),
                    [43.20, 31.56, 27.10, 29.25, 55.54][i],
                    2,
                    "incorrect fabric heat loss returned",
                )

    def test_heat_capacity(self):
        """Test that the correct heat capacity is returned when queried"""
        results = [380, 405, 425, 440, 450]

        for i, be in enumerate(self.test_be_objs):
            with self.subTest(i=i):
                self.assertEqual(be.heat_capacity(), results[i], "incorrect heat capacity returned")


class TestBuildingElementPartyWall(unittest.TestCase):
    """Tests to cover functionality in BuildingElementPartyWall"""

    def setUp(self):
        """Set up test fixtures"""
        self.simtime = SimulationTime(start_time=0, end_time=4, step=1)
        self.external_conditions = MagicMock(ExternalConditions)
        self.external_conditions.air_temp.return_value = 10.0

        # Standard test parameters
        self.area = 10.0
        self.pitch = 90
        self.thermal_resistance_construction = 0.5
        self.areal_heat_capacity = 10000
        self.mass_distribution_class = MassDistributionClass.D

    def test_calculate_cavity_resistance_defined_resistance_with_value(self):
        """Test cavity resistance with defined_resistance type"""
        thermal_resistance_cavity = 3.0
        party_wall = BuildingElementPartyWall(
            area=self.area,
            pitch=self.pitch,
            thermal_resistance_construction=self.thermal_resistance_construction,
            party_wall_cavity_type="defined_resistance",
            party_wall_lining_type=None,
            thermal_resistance_cavity=thermal_resistance_cavity,
            areal_heat_capacity=self.areal_heat_capacity,
            mass_distribution_class=self.mass_distribution_class,
            ext_cond=self.external_conditions,
        )

        # Check that h_ce reflects the custom resistance value
        # h_ce = 1 / (R_se + R_cavity) where R_se = 1/(H_CE + H_RE) = 1/24.14 ≈ 0.0414
        # h_ce = 1 / (0.0414 + 3.0) = 1 / 3.0414 ≈ 0.3287932443475892
        self.assertAlmostEqual(party_wall.h_ce(), 0.3287932443475892)

    def test_calculate_cavity_resistance_invalid_type_raises_error(self):
        """Test that invalid cavity type raises ValueError"""
        with self.assertRaises(ValueError) as context:
            BuildingElementPartyWall(
                area=self.area,
                pitch=self.pitch,
                thermal_resistance_construction=self.thermal_resistance_construction,
                party_wall_cavity_type="invalid_type",
                party_wall_lining_type=None,
                thermal_resistance_cavity=None,
                areal_heat_capacity=self.areal_heat_capacity,
                mass_distribution_class=self.mass_distribution_class,
                ext_cond=self.external_conditions,
            )
        self.assertIn("'invalid_type' is not a valid PartyWallCavityType", str(context.exception))

    def test_calculate_cavity_resistance_invalid_lining_type_raises_error(self):
        """Test that invalid cavity type raises ValueError"""
        with self.assertRaises(ValueError) as context:
            BuildingElementPartyWall(
                area=self.area,
                pitch=self.pitch,
                thermal_resistance_construction=self.thermal_resistance_construction,
                party_wall_cavity_type="unfilled_unsealed",
                party_wall_lining_type="invalid_type",
                thermal_resistance_cavity=None,
                areal_heat_capacity=self.areal_heat_capacity,
                mass_distribution_class=self.mass_distribution_class,
                ext_cond=self.external_conditions,
            )
        self.assertIn("party_wall_lining_type not recognised", str(context.exception))

    def test_calculate_cavity_resistance_incompatible_lining_type_raises_error(self):
        """Test that invalid cavity type raises ValueError"""
        with self.assertRaises(ValueError) as context:
            BuildingElementPartyWall(
                area=self.area,
                pitch=self.pitch,
                thermal_resistance_construction=self.thermal_resistance_construction,
                party_wall_cavity_type="solid",
                party_wall_lining_type="wet_plaster",
                thermal_resistance_cavity=None,
                areal_heat_capacity=self.areal_heat_capacity,
                mass_distribution_class=self.mass_distribution_class,
                ext_cond=self.external_conditions,
            )
        self.assertIn(
            "invalid combination of party wall cavity type and party wall lining type",
            str(context.exception),
        )

    def test_calculate_cavity_resistance_solid_type(self):
        """Test cavity resistance with solid type (effectively infinite resistance)"""
        party_wall = BuildingElementPartyWall(
            area=self.area,
            pitch=self.pitch,
            thermal_resistance_construction=self.thermal_resistance_construction,
            party_wall_cavity_type="solid",
            party_wall_lining_type=None,
            thermal_resistance_cavity=None,
            areal_heat_capacity=self.areal_heat_capacity,
            mass_distribution_class=self.mass_distribution_class,
            ext_cond=self.external_conditions,
        )

        # For solid type, cavity resistance should be 999999, making h_ce effectively zero
        self.assertEqual(party_wall.h_ce(), 0.0)

        # Fabric heat loss should be zero (no heat loss through party wall)
        self.assertAlmostEqual(party_wall.fabric_heat_loss(), 0.0)

    def test_calculate_cavity_resistance_unfilled_unsealed_dry_lined(self):
        """Test cavity resistance with unfilled_unsealed dry_lined type (R_cavity ≈ 1.5)"""
        party_wall = BuildingElementPartyWall(
            area=self.area,
            pitch=self.pitch,
            thermal_resistance_construction=self.thermal_resistance_construction,
            party_wall_cavity_type="unfilled_unsealed",
            party_wall_lining_type="dry_lined",
            thermal_resistance_cavity=None,
            areal_heat_capacity=self.areal_heat_capacity,
            mass_distribution_class=self.mass_distribution_class,
            ext_cond=self.external_conditions,
        )

        # Check h_ce value for unsealed cavity (R_cavity = 1.2)
        # h_ce = 1 / (R_se + R_cavity) = 1 / (0.0414 + 1.2) ≈ 0.805542
        self.assertAlmostEqual(party_wall.h_ce(), 0.8055258942872398)

        # Check fabric heat loss calculation
        expected_heat_loss = 5.340492100175494
        self.assertAlmostEqual(party_wall.fabric_heat_loss(), expected_heat_loss)

    def test_calculate_cavity_resistance_unfilled_sealed_dry_lined(self):
        """Test cavity resistance with unfilled_sealed dry_lined type (R_cavity ≈ 4.5)"""
        party_wall = BuildingElementPartyWall(
            area=self.area,
            pitch=self.pitch,
            thermal_resistance_construction=self.thermal_resistance_construction,
            party_wall_cavity_type="unfilled_sealed",
            party_wall_lining_type="dry_lined",
            thermal_resistance_cavity=None,
            areal_heat_capacity=self.areal_heat_capacity,
            mass_distribution_class=self.mass_distribution_class,
            ext_cond=self.external_conditions,
        )

        # Check h_ce value for sealed cavity (R_cavity = 4.5)
        self.assertAlmostEqual(party_wall.h_ce(), 0.2201952)

        # Check fabric heat loss calculation
        expected_heat_loss = 1.933306112766621
        self.assertAlmostEqual(party_wall.fabric_heat_loss(), expected_heat_loss)

    def test_calculate_cavity_resistance_filled_unsealed_dry_lined(self):
        """Test cavity resistance with unfilled_sealed dry_lined type (R_cavity ≈ 4.5)"""
        party_wall = BuildingElementPartyWall(
            area=self.area,
            pitch=self.pitch,
            thermal_resistance_construction=self.thermal_resistance_construction,
            party_wall_cavity_type="filled_unsealed",
            party_wall_lining_type="dry_lined",
            thermal_resistance_cavity=None,
            areal_heat_capacity=self.areal_heat_capacity,
            mass_distribution_class=self.mass_distribution_class,
            ext_cond=self.external_conditions,
        )

        # Check h_ce value for sealed cavity (R_cavity = 4.5)
        self.assertAlmostEqual(party_wall.h_ce(), 0.2201952)

        # Check fabric heat loss calculation
        expected_heat_loss = 1.933306112766621
        self.assertAlmostEqual(party_wall.fabric_heat_loss(), expected_heat_loss)

    def test_calculate_cavity_resistance_unfilled_unsealed_wet_plaster(self):
        """Test cavity resistance with unfilled_unsealed wet_plaster type (R_cavity ≈ 1.5)"""
        party_wall = BuildingElementPartyWall(
            area=self.area,
            pitch=self.pitch,
            thermal_resistance_construction=self.thermal_resistance_construction,
            party_wall_cavity_type="unfilled_unsealed",
            party_wall_lining_type="wet_plaster",
            thermal_resistance_cavity=None,
            areal_heat_capacity=self.areal_heat_capacity,
            mass_distribution_class=self.mass_distribution_class,
            ext_cond=self.external_conditions,
        )

        # Check h_ce value for unsealed cavity (R_cavity = 4.5)
        self.assertAlmostEqual(party_wall.h_ce(), 0.2201952)

        # Check fabric heat loss calculation
        expected_heat_loss = 1.933306112766621
        self.assertAlmostEqual(party_wall.fabric_heat_loss(), expected_heat_loss)

    def test_calculate_cavity_resistance_unfilled_sealed_wet_plaster(self):
        """Test cavity resistance with unfilled_sealed wet_plaster type (R_cavity ≈ 4.5)"""
        party_wall = BuildingElementPartyWall(
            area=self.area,
            pitch=self.pitch,
            thermal_resistance_construction=self.thermal_resistance_construction,
            party_wall_cavity_type="unfilled_sealed",
            party_wall_lining_type="wet_plaster",
            thermal_resistance_cavity=None,
            areal_heat_capacity=self.areal_heat_capacity,
            mass_distribution_class=self.mass_distribution_class,
            ext_cond=self.external_conditions,
        )

        # Check h_ce value for sealed cavity (R_cavity = 4.5)
        self.assertAlmostEqual(party_wall.h_ce(), 0.2201952)

        # Check fabric heat loss calculation
        expected_heat_loss = 1.933306112766621
        self.assertAlmostEqual(party_wall.fabric_heat_loss(), expected_heat_loss)

    def test_calculate_cavity_resistance_filled_unsealed_wet_plaster(self):
        """Test cavity resistance with filled_unsealed wet_plaster type (R_cavity ≈ 4.5)"""
        party_wall = BuildingElementPartyWall(
            area=self.area,
            pitch=self.pitch,
            thermal_resistance_construction=self.thermal_resistance_construction,
            party_wall_cavity_type="filled_unsealed",
            party_wall_lining_type="wet_plaster",
            thermal_resistance_cavity=None,
            areal_heat_capacity=self.areal_heat_capacity,
            mass_distribution_class=self.mass_distribution_class,
            ext_cond=self.external_conditions,
        )

        # Check h_ce value for sealed cavity (R_cavity = 4.5)
        self.assertAlmostEqual(party_wall.h_ce(), 0.2201952)

        # Check fabric heat loss calculation
        expected_heat_loss = 1.933306112766621
        self.assertAlmostEqual(party_wall.fabric_heat_loss(), expected_heat_loss)

    def test_calculate_cavity_resistance_filled_sealed(self):
        """Test cavity resistance with filled_sealed type (effectively infinite resistance)"""
        party_wall = BuildingElementPartyWall(
            area=self.area,
            pitch=self.pitch,
            thermal_resistance_construction=self.thermal_resistance_construction,
            party_wall_cavity_type="filled_sealed",
            party_wall_lining_type=None,
            thermal_resistance_cavity=None,
            areal_heat_capacity=self.areal_heat_capacity,
            mass_distribution_class=self.mass_distribution_class,
            ext_cond=self.external_conditions,
        )

        # For filled_sealed type, cavity resistance should be 999999, making h_ce zero
        self.assertEqual(party_wall.h_ce(), 0.0)

        # Fabric heat loss should be zero (no heat loss through party wall)
        self.assertAlmostEqual(party_wall.fabric_heat_loss(), 0.0)

    def test_all_party_wall_cavity_types_valid(self):
        """Test that all valid party wall cavity types can be constructed"""
        valid_types = [
            "solid",
            "unfilled_unsealed",
            "unfilled_sealed",
            "filled_sealed",
            "filled_unsealed",
            "defined_resistance",
        ]

        for cavity_type in valid_types:
            with self.subTest(cavity_type=cavity_type):
                thermal_resistance = 2.5 if cavity_type == "defined_resistance" else None
                lining_type = (
                    "dry_lined"
                    if (
                        cavity_type == "unfilled_unsealed"
                        or cavity_type == "filled_unsealed"
                        or cavity_type == "unfilled_sealed"
                    )
                    else None
                )

                party_wall = BuildingElementPartyWall(
                    area=self.area,
                    pitch=self.pitch,
                    thermal_resistance_construction=self.thermal_resistance_construction,
                    party_wall_cavity_type=cavity_type,
                    party_wall_lining_type=lining_type,
                    thermal_resistance_cavity=thermal_resistance,
                    areal_heat_capacity=self.areal_heat_capacity,
                    mass_distribution_class=self.mass_distribution_class,
                    ext_cond=self.external_conditions,
                )

                self.assertIsNotNone(party_wall)
                self.assertEqual(party_wall.area, self.area)
                self.assertEqual(party_wall._pitch, self.pitch)

    def test_h_ce_returns_zero_for_solid_type(self):
        """Test that h_ce returns 0.0 for solid party wall cavity type"""
        party_wall = BuildingElementPartyWall(
            area=self.area,
            pitch=self.pitch,
            thermal_resistance_construction=self.thermal_resistance_construction,
            party_wall_cavity_type="solid",
            party_wall_lining_type=None,
            thermal_resistance_cavity=None,
            areal_heat_capacity=self.areal_heat_capacity,
            mass_distribution_class=self.mass_distribution_class,
            ext_cond=self.external_conditions,
        )

        self.assertEqual(party_wall.h_ce(), 0.0)
        # Also verify h_re is zero (no radiative transfer)
        self.assertEqual(party_wall.h_re(), 0.0)

    def test_h_ce_returns_zero_for_filled_sealed_type(self):
        """Test that h_ce returns 0.0 for filled_sealed party wall cavity type"""
        party_wall = BuildingElementPartyWall(
            area=self.area,
            pitch=self.pitch,
            thermal_resistance_construction=self.thermal_resistance_construction,
            party_wall_cavity_type="filled_sealed",
            party_wall_lining_type=None,
            thermal_resistance_cavity=None,
            areal_heat_capacity=self.areal_heat_capacity,
            mass_distribution_class=self.mass_distribution_class,
            ext_cond=self.external_conditions,
        )

        self.assertEqual(party_wall.h_ce(), 0.0)
        # Also verify h_re is zero (no radiative transfer)
        self.assertEqual(party_wall.h_re(), 0.0)

    def test_h_ce_returns_parent_value_for_unfilled_unsealed_type(self):
        """Test that h_ce uses parent class behaviour for unfilled_unsealed type"""
        party_wall = BuildingElementPartyWall(
            area=self.area,
            pitch=self.pitch,
            thermal_resistance_construction=self.thermal_resistance_construction,
            party_wall_cavity_type="unfilled_unsealed",
            party_wall_lining_type="dry_lined",
            thermal_resistance_cavity=None,
            areal_heat_capacity=self.areal_heat_capacity,
            mass_distribution_class=self.mass_distribution_class,
            ext_cond=self.external_conditions,
        )

        self.assertAlmostEqual(party_wall.h_ce(), 0.8055258942872398)
        # Verify this is consistent with R_cavity = 1.2
        expected_h_ce = 0.8055258942872398
        self.assertAlmostEqual(party_wall.h_ce(), expected_h_ce)

    def test_h_ce_returns_parent_value_for_unfilled_sealed_type(self):
        """Test that h_ce uses parent class behaviour for unfilled_sealed type"""
        party_wall = BuildingElementPartyWall(
            area=self.area,
            pitch=self.pitch,
            thermal_resistance_construction=self.thermal_resistance_construction,
            party_wall_cavity_type="unfilled_sealed",
            party_wall_lining_type="dry_lined",
            thermal_resistance_cavity=None,
            areal_heat_capacity=self.areal_heat_capacity,
            mass_distribution_class=self.mass_distribution_class,
            ext_cond=self.external_conditions,
        )

        self.assertAlmostEqual(party_wall.h_ce(), 0.22019520204323634)
        # Verify this is consistent with R_cavity = 4.5
        expected_h_ce = 0.22019520204323634
        self.assertAlmostEqual(party_wall.h_ce(), expected_h_ce)

    def test_h_ce_returns_parent_value_for_defined_resistance_type(self):
        """Test that h_ce uses parent class behaviour for defined_resistance type"""
        thermal_resistance_cavity = 2.0
        party_wall = BuildingElementPartyWall(
            area=self.area,
            pitch=self.pitch,
            thermal_resistance_construction=self.thermal_resistance_construction,
            party_wall_cavity_type="defined_resistance",
            party_wall_lining_type=None,
            thermal_resistance_cavity=thermal_resistance_cavity,
            areal_heat_capacity=self.areal_heat_capacity,
            mass_distribution_class=self.mass_distribution_class,
            ext_cond=self.external_conditions,
        )

        self.assertAlmostEqual(party_wall.h_ce(), 0.4898538961038961)
        # Verify this is consistent with the specified R_cavity
        expected_h_ce = 0.4898538961038961
        self.assertAlmostEqual(party_wall.h_ce(), expected_h_ce)

    def test_fabric_heat_loss_comparison_across_types(self):
        """Test that fabric heat loss decreases from unsealed to sealed to solid"""
        party_wall_unsealed = BuildingElementPartyWall(
            area=self.area,
            pitch=self.pitch,
            thermal_resistance_construction=self.thermal_resistance_construction,
            party_wall_cavity_type="unfilled_unsealed",
            party_wall_lining_type="dry_lined",
            thermal_resistance_cavity=None,
            areal_heat_capacity=self.areal_heat_capacity,
            mass_distribution_class=self.mass_distribution_class,
            ext_cond=self.external_conditions,
        )

        party_wall_sealed = BuildingElementPartyWall(
            area=self.area,
            pitch=self.pitch,
            thermal_resistance_construction=self.thermal_resistance_construction,
            party_wall_cavity_type="unfilled_sealed",
            party_wall_lining_type="dry_lined",
            thermal_resistance_cavity=None,
            areal_heat_capacity=self.areal_heat_capacity,
            mass_distribution_class=self.mass_distribution_class,
            ext_cond=self.external_conditions,
        )

        party_wall_solid = BuildingElementPartyWall(
            area=self.area,
            pitch=self.pitch,
            thermal_resistance_construction=self.thermal_resistance_construction,
            party_wall_cavity_type="solid",
            party_wall_lining_type=None,
            thermal_resistance_cavity=None,
            areal_heat_capacity=self.areal_heat_capacity,
            mass_distribution_class=self.mass_distribution_class,
            ext_cond=self.external_conditions,
        )

        heat_loss_unsealed = party_wall_unsealed.fabric_heat_loss()
        heat_loss_sealed = party_wall_sealed.fabric_heat_loss()
        heat_loss_solid = party_wall_solid.fabric_heat_loss()

        # Verify heat loss decreases as cavity resistance increases
        self.assertGreater(heat_loss_unsealed, heat_loss_sealed)
        self.assertGreater(heat_loss_sealed, heat_loss_solid)
        self.assertAlmostEqual(heat_loss_solid, 0.0)

    def test_heat_capacity_calculation(self):
        """Test that heat capacity is calculated correctly"""
        party_wall = BuildingElementPartyWall(
            area=self.area,
            pitch=self.pitch,
            thermal_resistance_construction=self.thermal_resistance_construction,
            party_wall_cavity_type="unfilled_unsealed",
            party_wall_lining_type="dry_lined",
            thermal_resistance_cavity=None,
            areal_heat_capacity=self.areal_heat_capacity,
            mass_distribution_class=self.mass_distribution_class,
            ext_cond=self.external_conditions,
        )

        # Heat capacity = area * (areal_heat_capacity / 1000)
        # Heat capacity = 10.0 * (10000 / 1000) = 100.0 kJ/K
        expected_heat_capacity = self.area * (self.areal_heat_capacity / 1000.0)
        self.assertAlmostEqual(party_wall.heat_capacity(), expected_heat_capacity)

    def test_r_si_calculation(self):
        """Test that internal surface resistance is calculated correctly for vertical wall"""
        party_wall = BuildingElementPartyWall(
            area=self.area,
            pitch=self.pitch,  # 90 degrees = vertical
            thermal_resistance_construction=self.thermal_resistance_construction,
            party_wall_cavity_type="unfilled_unsealed",
            party_wall_lining_type="dry_lined",
            thermal_resistance_cavity=None,
            areal_heat_capacity=self.areal_heat_capacity,
            mass_distribution_class=self.mass_distribution_class,
            ext_cond=self.external_conditions,
        )

        # For vertical walls (60 < pitch < 120), R_si = R_SI_HORIZONTAL
        # R_SI_HORIZONTAL = 1 / (H_RI + H_CI_HORIZONTAL) = 1 / (5.13 + 2.5) ≈ 0.131
        expected_r_si = 1.0 / (5.13 + 2.5)
        self.assertAlmostEqual(party_wall.r_si(), expected_r_si)

    def test_no_of_nodes(self):
        """Test that party wall uses 5-node model"""
        party_wall = BuildingElementPartyWall(
            area=self.area,
            pitch=self.pitch,
            thermal_resistance_construction=self.thermal_resistance_construction,
            party_wall_cavity_type="unfilled_unsealed",
            party_wall_lining_type="dry_lined",
            thermal_resistance_cavity=None,
            areal_heat_capacity=self.areal_heat_capacity,
            mass_distribution_class=self.mass_distribution_class,
            ext_cond=self.external_conditions,
        )

        # 5-node model has 5 nodes total, 3 inside nodes
        self.assertEqual(party_wall.no_of_nodes(), 5)
        self.assertEqual(party_wall.no_of_inside_nodes(), 3)

    def test_node_conductances_h_pli(self):
        """Test that node conductances are calculated correctly"""
        party_wall = BuildingElementPartyWall(
            area=self.area,
            pitch=self.pitch,
            thermal_resistance_construction=self.thermal_resistance_construction,
            party_wall_cavity_type="unfilled_unsealed",
            party_wall_lining_type="dry_lined",
            thermal_resistance_cavity=None,
            areal_heat_capacity=self.areal_heat_capacity,
            mass_distribution_class=self.mass_distribution_class,
            ext_cond=self.external_conditions,
        )

        # For 5-node model:
        # h_pli[0] = 6 / R_c (outer)
        # h_pli[1] = 3 / R_c (inner)
        # h_pli[2] = 3 / R_c (inner)
        # h_pli[3] = 6 / R_c (outer)
        h_outer = 6.0 / self.thermal_resistance_construction
        h_inner = 3.0 / self.thermal_resistance_construction

        self.assertAlmostEqual(party_wall.h_pli(0), h_outer)
        self.assertAlmostEqual(party_wall.h_pli(1), h_inner)
        self.assertAlmostEqual(party_wall.h_pli(2), h_inner)
        self.assertAlmostEqual(party_wall.h_pli(3), h_outer)

    def test_equivalent_u_values_match_sap_guidance(self):
        """Test that equivalent U-values approximately match SAP 10.2 table 3.10"""
        # Create party walls with standard construction assumptions
        # Assume R_c represents typical party wall construction

        # Test unsealed cavity: should give equivalent U ≈ 0.5 W/m²K
        party_wall_unsealed = BuildingElementPartyWall(
            area=self.area,
            pitch=self.pitch,
            thermal_resistance_construction=self.thermal_resistance_construction,
            party_wall_cavity_type="unfilled_unsealed",
            party_wall_lining_type="dry_lined",
            thermal_resistance_cavity=None,
            areal_heat_capacity=self.areal_heat_capacity,
            mass_distribution_class=self.mass_distribution_class,
            ext_cond=self.external_conditions,
        )

        u_unsealed = 0.5340492100175493
        heat_loss_unsealed = party_wall_unsealed.fabric_heat_loss()
        calculated_u_unsealed = heat_loss_unsealed / self.area

        # Check U-value is in reasonable range for unsealed cavity
        self.assertAlmostEqual(calculated_u_unsealed, u_unsealed)

        # Test sealed cavity: should give equivalent U ≈ 0.2 W/m²K
        party_wall_sealed = BuildingElementPartyWall(
            area=self.area,
            pitch=self.pitch,
            thermal_resistance_construction=self.thermal_resistance_construction,
            party_wall_cavity_type="unfilled_sealed",
            party_wall_lining_type="dry_lined",
            thermal_resistance_cavity=None,
            areal_heat_capacity=self.areal_heat_capacity,
            mass_distribution_class=self.mass_distribution_class,
            ext_cond=self.external_conditions,
        )

        u_sealed = 0.1933306112766621
        heat_loss_sealed = party_wall_sealed.fabric_heat_loss()
        calculated_u_sealed = heat_loss_sealed / self.area

        # Check U-value is in reasonable range for sealed cavity
        self.assertAlmostEqual(calculated_u_sealed, u_sealed)
