#!/usr/bin/env python3

"""
This module contains unit tests for the Photovoltaic System module
"""

# Standard library imports
import re
import unittest
from unittest.mock import MagicMock

import pytest

from hem_core.energy_supply.energy_supply import EnergySupply
from hem_core.energy_supply.inverter import Inverter
from hem_core.energy_supply.pv import PhotovoltaicPanel, PhotovoltaicSystem
from hem_core.external_conditions import ExternalConditions
from hem_core.input_output.enums import FuelType, InverterType

# Local imports
from hem_core.simulation_time import SimulationTime
from hem_core.units import Orientation360


class TestPhotovoltaicSystem(unittest.TestCase):
    """Unit tests for PhotovoltaicSystem class"""

    def setUp(self):
        """Create PhotovoltaicSystem object to be tested"""
        # simulation time: start, end, step
        self.simtime = SimulationTime(start_time=0, end_time=8, step=1)
        proj_dict = {
            "ExternalConditions": {
                "air_temperatures": [0.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 20.0],
                "wind_speeds": [3.9, 3.8, 3.9, 4.1, 3.8, 4.2, 4.3, 4.1],
                "wind_directions": [
                    Orientation360(220),
                    Orientation360(230),
                    Orientation360(240),
                    Orientation360(250),
                    Orientation360(260),
                    Orientation360(270),
                    Orientation360(270),
                    Orientation360(280),
                ],
                "diffuse_horizontal_radiation": [11, 25, 42, 52, 60, 44, 28, 15],
                "direct_beam_radiation": [11, 25, 42, 52, 60, 44, 28, 15],
                "solar_reflectivity_of_ground": [0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2],
                "latitude": 51.42,
                "longitude": -0.75,
                "timezone": 0,
                "start_day": 0,
                "end_day": 0,
                "time_series_step": 1,
                "january_first": 1,
                "daylight_savings": "not applicable",
                "leap_day_included": False,
                "direct_beam_conversion_needed": False,
                "shading_segments": [
                    {
                        "number": 1,
                        "start360": Orientation360.create_from_180(180),
                        "end360": Orientation360.create_from_180(135),
                    },
                    {
                        "number": 2,
                        "start360": Orientation360.create_from_180(135),
                        "end360": Orientation360.create_from_180(90),
                        "shading": [{"type": "overhang", "height": 2.2, "distance": 6}],
                    },
                    {
                        "number": 3,
                        "start360": Orientation360.create_from_180(90),
                        "end360": Orientation360.create_from_180(45),
                    },
                    {
                        "number": 4,
                        "start360": Orientation360.create_from_180(45),
                        "end360": Orientation360.create_from_180(0),
                        "shading": [
                            {"type": "obstacle", "height": 40, "distance": 4},
                            {"type": "overhang", "height": 3, "distance": 7},
                        ],
                    },
                    {
                        "number": 5,
                        "start360": Orientation360.create_from_180(0),
                        "end360": Orientation360.create_from_180(-45),
                        "shading": [
                            {"type": "obstacle", "height": 3, "distance": 8},
                        ],
                    },
                    {
                        "number": 6,
                        "start360": Orientation360.create_from_180(-45),
                        "end360": Orientation360.create_from_180(-90),
                    },
                    {
                        "number": 7,
                        "start360": Orientation360.create_from_180(-90),
                        "end360": Orientation360.create_from_180(-135),
                    },
                    {
                        "number": 8,
                        "start360": Orientation360.create_from_180(-135),
                        "end360": Orientation360.create_from_180(-180),
                    },
                ],
            }
        }
        self.__external_conditions = ExternalConditions(
            simulation_time=self.simtime,
            air_temps=proj_dict["ExternalConditions"]["air_temperatures"],
            wind_speeds=proj_dict["ExternalConditions"]["wind_speeds"],
            wind_directions=proj_dict["ExternalConditions"]["wind_directions"],
            diffuse_horizontal_radiation=proj_dict["ExternalConditions"][
                "diffuse_horizontal_radiation"
            ],
            direct_beam_radiation=proj_dict["ExternalConditions"]["direct_beam_radiation"],
            solar_reflectivity_of_ground=proj_dict["ExternalConditions"][
                "solar_reflectivity_of_ground"
            ],
            latitude=proj_dict["ExternalConditions"]["latitude"],
            longitude=proj_dict["ExternalConditions"]["longitude"],
            timezone=proj_dict["ExternalConditions"]["timezone"],
            start_day=proj_dict["ExternalConditions"]["start_day"],
            end_day=proj_dict["ExternalConditions"]["end_day"],
            time_series_step=proj_dict["ExternalConditions"]["time_series_step"],
            january_first=proj_dict["ExternalConditions"]["january_first"],
            daylight_savings=proj_dict["ExternalConditions"]["daylight_savings"],
            leap_day_included=proj_dict["ExternalConditions"]["leap_day_included"],
            direct_beam_conversion_needed=proj_dict["ExternalConditions"][
                "direct_beam_conversion_needed"
            ],
            shading_segments=proj_dict["ExternalConditions"]["shading_segments"],
        )
        self.energysupply = EnergySupply(
            fuel_type=FuelType.ELECTRICITY, simulation_time=self.simtime
        )
        self.energysupplyconn = self.energysupply.connection(
            end_user_name="pv generation without shading"
        )
        self.pv_inverter = Inverter(
            energy_supply_conn=self.energysupplyconn,
            simulation_time=self.simtime,
            inverter_peak_power_dc=2.5,
            inverter_peak_power_ac=0.05,
            inverter_is_inside=False,
            inverter_type=InverterType.OPTIMISED_INVERTER,
        )
        self.pv_system = PhotovoltaicSystem(
            ext_cond=self.__external_conditions,
            simulation_time=self.simtime,
            panels=[
                PhotovoltaicPanel(
                    peak_power=2.5,
                    ventilation_strategy="moderately_ventilated",
                    pitch=30,
                    orientation=Orientation360.create_from_180(0),
                    base_height=10,
                    height=2,
                    width=3,
                    shading=[],
                )
            ],
            inverter=self.pv_inverter,
        )

        self.energysupplyconn = self.energysupply.connection(
            end_user_name="pv generation with shading"
        )

        self.pv_inverter_with_shading = Inverter(
            energy_supply_conn=self.energysupplyconn,
            simulation_time=self.simtime,
            inverter_peak_power_dc=2.5,
            inverter_peak_power_ac=0.02,
            inverter_is_inside=True,
            inverter_type=InverterType.STRING_INVERTER,
        )
        self.pv_system_with_shading = PhotovoltaicSystem(
            ext_cond=self.__external_conditions,
            simulation_time=self.simtime,
            panels=[
                PhotovoltaicPanel(
                    peak_power=2.5,
                    ventilation_strategy="moderately_ventilated",
                    pitch=30,
                    orientation=Orientation360.create_from_180(0),
                    base_height=10,
                    height=2,
                    width=3,
                    shading=[
                        {"type": "overhang", "depth": 0.5, "distance": 0.5},
                        {"type": "sidefinleft", "depth": 0.25, "distance": 0.1},
                        {"type": "sidefinright", "depth": 0.25, "distance": 0.1},
                    ],
                )
            ],
            inverter=self.pv_inverter_with_shading,
        )

    def test_is_inside(self):
        """Test that the PhotovoltaicSystem object 'is inside' flag is being returned correctly"""
        self.assertFalse(self.pv_system.inverter_is_inside())
        self.assertTrue(self.pv_system_with_shading.inverter_is_inside())

    def test_produce_energy(self):
        """Test that PhotovoltaicSystem object returns correct electricity generated kWh
        Note: produced energy stored as a negative demand"""
        expected_results = [
            -0.002911179810082315,
            -0.01585915973389526,
            -0.03631681332778666,
            -0.0462218185635626,
            -0.05,
            -0.03841528069730012,
            -0.019985927280177524,
            -0.014819433057321862,
        ]
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.pv_system.produce_energy()
                self.assertAlmostEqual(
                    self.energysupply.results_by_end_user()["pv generation without shading"][t_idx],
                    expected_results[t_idx],
                    places=6,
                    msg="incorrect electricity produced from pv returned",
                )

    def test_produce_energy_multiple_panels(self):
        """Test that PhotovoltaicSystem object with multiple panels returns correct electricity generated kWh
        Note: produced energy stored as a negative demand"""
        self.energysupply = EnergySupply(
            fuel_type=FuelType.ELECTRICITY, simulation_time=self.simtime
        )
        self.energysupplyconn = self.energysupply.connection(end_user_name="pv generation")
        self.pv_inverter = Inverter(
            energy_supply_conn=self.energysupplyconn,
            simulation_time=self.simtime,
            inverter_peak_power_dc=2.5,
            inverter_peak_power_ac=0.05,
            inverter_is_inside=False,
            inverter_type=InverterType.OPTIMISED_INVERTER,
        )
        self.pv_system = PhotovoltaicSystem(
            ext_cond=self.__external_conditions,
            simulation_time=self.simtime,
            panels=[
                PhotovoltaicPanel(
                    peak_power=2.5,
                    ventilation_strategy="moderately_ventilated",
                    pitch=30,
                    orientation=Orientation360.create_from_180(0),
                    base_height=10,
                    height=2,
                    width=3,
                    shading=[],
                ),
                PhotovoltaicPanel(
                    peak_power=3.5,
                    ventilation_strategy="moderately_ventilated",
                    pitch=32,
                    orientation=Orientation360.create_from_180(0),
                    base_height=12,
                    height=2,
                    width=3,
                    shading=[],
                ),
            ],
            inverter=self.pv_inverter,
        )
        expected_results = [
            -0.015826768143293042,
            -0.05,
            -0.05,
            -0.05,
            -0.05,
            -0.05,
            -0.05,
            -0.05,
        ]
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.pv_system.produce_energy()
                self.assertAlmostEqual(
                    self.energysupply.results_by_end_user()["pv generation"][t_idx],
                    expected_results[t_idx],
                    places=6,
                    msg="incorrect electricity produced from pv returned",
                )

    def test_produce_energy_with_shading(self):
        """Test that PhotovoltaicSystem object with shading returns correct electricity
        generated kWh
        Note: produced energy stored as a negative demand"""
        expected_results = [
            -0.0015507260447403823,
            -0.008732593505451556,
            -0.02,
            -0.02,
            -0.02,
            -0.013971934370722397,
            -0.006779589823217942,
            -0.007020372160065822,
        ]
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.pv_system_with_shading.produce_energy()
                self.assertAlmostEqual(
                    self.energysupply.results_by_end_user()["pv generation with shading"][t_idx],
                    expected_results[t_idx],
                    places=6,
                    msg="incorrect electricity produced from pv returned",
                )

    def test_produce_energy_produced_and_lost(self):
        """Test that PhotovoltaicSystem object returns correct electricity produced and lost (in kWh)"""
        expected_energy_produced = [
            0.002911179810082315,
            0.01585915973389526,
            0.03631681332778666,
            0.0462218185635626,
            0.05,
            0.03841528069730012,
            0.019985927280177524,
            0.014819433057321862,
        ]
        expected_energy_lost = [
            0.012982394066666526,
            0.022261865114937766,
            0.024010573568482414,
            0.023376882776544372,
            0.02560556391283768,
            0.02392305675244094,
            0.023189444399645136,
            0.021949092776458276,
        ]
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                energy_produced, energy_lost = self.pv_system.produce_energy()
                self.assertAlmostEqual(
                    energy_produced,
                    expected_energy_produced[t_idx],
                    places=6,
                    msg=f"incorrect electricity produced from pv returned for timestep {t_idx}",
                )
                self.assertAlmostEqual(
                    energy_lost,
                    expected_energy_lost[t_idx],
                    places=6,
                    msg=f"incorrect electricity lost from pv returned for timestep {t_idx}",
                )

    def test_inverter_efficiency_lookup(self):
        """Test that each combination of inverter efficiency types are correct below and above thresholds"""
        self.pv_system._PhotovoltaicSystem__inverter._Inverter__inverter_type = (
            InverterType.STRING_INVERTER
        )
        self.assertAlmostEqual(
            self.pv_system.inverter_efficiency_lookup(f_sh_dir=0.9), 0.8613180000000007
        )
        self.assertAlmostEqual(
            self.pv_system.inverter_efficiency_lookup(f_sh_dir=0.5), 0.7419000000000002
        )

        self.pv_system._PhotovoltaicSystem__inverter._Inverter__inverter_type = (
            InverterType.OPTIMISED_INVERTER
        )
        self.assertAlmostEqual(self.pv_system.inverter_efficiency_lookup(f_sh_dir=0.9), 0.993716)
        self.assertAlmostEqual(self.pv_system.inverter_efficiency_lookup(f_sh_dir=0.3), 1)

    def test_inverter_efficiency_lookup_invalid_type(self):
        """Test that an invalid inverter efficiency returns None from inverter_efficiency_lookup"""
        self.pv_system._PhotovoltaicSystem__inverter._Inverter__inverter_type = "invalid"
        with self.assertRaises(ValueError):
            self.pv_system.inverter_efficiency_lookup(f_sh_dir=0.5)

    def test_produce_energy_invalid_inverter_type(self):
        """Test that an invalid inverter efficiency throws from produce_energy"""
        invalid_inverter_type = "invalid-type"

        self.pv_system._PhotovoltaicSystem__external_conditions = MagicMock()
        self.pv_system._PhotovoltaicSystem__external_conditions.shading_reduction_factor_direct_diffuse.return_value = (
            0.8,
            1,
        )
        self.pv_system._PhotovoltaicSystem__external_conditions.calculated_direct_diffuse_total_irradiance.return_value = (
            0.5,
            0.5,
            0.5,
            None,
        )
        self.pv_system._PhotovoltaicSystem__inverter._Inverter__inverter_type = (
            invalid_inverter_type
        )

        expected_options = [inverter_type.value for inverter_type in InverterType]
        expected_message = (
            f"Invalid inverter type: {invalid_inverter_type}. Valid options are: {expected_options}"
        )

        with pytest.raises(ValueError, match=re.escape(expected_message)):
            self.pv_system.produce_energy()

    def test_product_energy_zero_ratio_of_rated_output(self):
        """Test that ratio_of_rated_output of 0 returns 0 energy"""
        self.pv_inverter = Inverter(
            energy_supply_conn=self.energysupplyconn,
            simulation_time=self.simtime,
            inverter_peak_power_dc=2.5,
            inverter_peak_power_ac=0.02,
            inverter_is_inside=True,
            inverter_type=InverterType.STRING_INVERTER,
        )
        self.pv_system = PhotovoltaicSystem(
            ext_cond=self.__external_conditions,
            simulation_time=self.simtime,
            panels=[
                PhotovoltaicPanel(
                    0, "moderately_ventilated", 30, Orientation360.create_from_180(0), 10, 2, 3, []
                )
            ],
            inverter=self.pv_inverter,
        )
        self.assertEqual(self.pv_system.produce_energy(), (0, 0))

    def test_produce_energy_weighted_shading_multiple_panels(self):
        """Test that PhotovoltaicSystem with multiple panels uses weighted average shading factor
        rather than individual panel shading factors.

        This test uses two panels with different shading to verify that the weighted average
        shading factor is calculated and applied correctly to both panels.
        """
        self.energysupply = EnergySupply(
            fuel_type=FuelType.ELECTRICITY, simulation_time=self.simtime
        )
        self.energysupplyconn = self.energysupply.connection(
            end_user_name="pv generation with weighted shading"
        )
        self.pv_inverter = Inverter(
            energy_supply_conn=self.energysupplyconn,
            simulation_time=self.simtime,
            inverter_peak_power_dc=5.0,
            inverter_peak_power_ac=0.05,
            inverter_is_inside=False,
            inverter_type=InverterType.OPTIMISED_INVERTER,
        )
        # Create system with two panels: one with heavy shading, one with no shading
        self.pv_system = PhotovoltaicSystem(
            ext_cond=self.__external_conditions,
            simulation_time=self.simtime,
            panels=[
                PhotovoltaicPanel(
                    peak_power=2.5,
                    ventilation_strategy="moderately_ventilated",
                    pitch=30,
                    orientation=Orientation360.create_from_180(0),
                    base_height=10,
                    height=2,
                    width=3,
                    shading=[
                        {"type": "overhang", "depth": 1.5, "distance": 0.5},
                    ],
                ),
                PhotovoltaicPanel(
                    peak_power=2.5,
                    ventilation_strategy="moderately_ventilated",
                    pitch=30,
                    orientation=Orientation360.create_from_180(0),
                    base_height=10,
                    height=2,
                    width=3,
                    shading=[],  # No shading on second panel
                ),
            ],
            inverter=self.pv_inverter,
        )

        # These expected results reflect the weighted average shading being applied
        # If the bug were present, results would differ because each panel would use
        # its own shading factor instead of the weighted average
        expected_results = [
            -0.005487138157454144,
            -0.030091653956970398,
            -0.05,
            -0.05,
            -0.05,
            -0.05,
            -0.03798231211493309,
            -0.02867743809548659,
        ]

        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.pv_system.produce_energy()
                self.assertAlmostEqual(
                    self.energysupply.results_by_end_user()["pv generation with weighted shading"][
                        t_idx
                    ],
                    expected_results[t_idx],
                    msg=f"incorrect electricity produced from weighted shading pv at timestep {t_idx}",
                )
