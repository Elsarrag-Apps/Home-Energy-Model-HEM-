#!/usr/bin/env python3

"""
This module contains unit tests for the energy_supply module
"""

# Standard library imports
import unittest
from unittest.mock import MagicMock

from hem_core.energy_supply.elec_battery import ElectricBattery
from hem_core.energy_supply.energy_supply import EnergySupply
from hem_core.energy_supply.tariff_data import TariffData
from hem_core.external_conditions import ExternalConditions
from hem_core.input_output.enums import BatteryLocation, FuelType

# Local imports
from hem_core.simulation_time import SimulationTime
from test.conftest import PATH_DEMO_FILES

TARIFF_DATA = PATH_DEMO_FILES / "tariff_data_25-06-2024.csv"


class TestFuelCode(unittest.TestCase):
    def test_from_string(self):
        test_cases = [
            ("LPG_bottled", FuelType.LPG_BOTTLED),
            ("LPG_condition_11F", FuelType.LPG_CONDITION_11_F),
            ("energy_from_environment", FuelType.ENERGY_FROM_ENVIRONMENT),
        ]
        for value, expected in test_cases:
            with self.subTest(value=value):
                self.assertEqual(FuelType(value), expected)


class TestEnergySupply(unittest.TestCase):
    """Unit tests for EnergySupply class"""

    def setUp(self):
        """Create EnergySupply object to be tested"""
        self.simtime = SimulationTime(start_time=0, end_time=8, step=1)
        self.energysupply = EnergySupply(fuel_type=FuelType.MAINS_GAS, simulation_time=self.simtime)
        """ Set up two different energy supply connections """
        self.energysupplyconn_1 = self.energysupply.connection("shower")
        self.energysupplyconn_2 = self.energysupply.connection("bath")

        # For battery
        proj_dict = {
            "ExternalConditions": {
                "air_temperatures": [0.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 20.0],
                "wind_speeds": [3.9, 3.8, 3.9, 4.1, 3.8, 4.2, 4.3, 4.1],
                "wind_directions": [0, 20, 40, 60, 0, 20, 40, 60],
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
                    {"number": 1, "start": 180, "end": 135},
                    {
                        "number": 2,
                        "start": 135,
                        "end": 90,
                        "shading": [{"type": "overhang", "height": 2.2, "distance": 6}],
                    },
                    {"number": 3, "start": 90, "end": 45},
                    {
                        "number": 4,
                        "start": 45,
                        "end": 0,
                        "shading": [
                            {"type": "obstacle", "height": 40, "distance": 4},
                            {"type": "overhang", "height": 3, "distance": 7},
                        ],
                    },
                    {
                        "number": 5,
                        "start": 0,
                        "end": -45,
                        "shading": [
                            {"type": "obstacle", "height": 3, "distance": 8},
                        ],
                    },
                    {"number": 6, "start": -45, "end": -90},
                    {"number": 7, "start": -90, "end": -135},
                    {"number": 8, "start": -135, "end": -180},
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

        # Test for EnergySupplyConnection fuel_type
        self.assertEqual(self.energysupplyconn_1.fuel_type(), FuelType.MAINS_GAS)

    def test_no_battery_or_invalid_charging(self):
        """Tests for EnergySupply with no battery or invalid battery charging due to no tariff data"""
        with self.assertRaises(ValueError):
            EnergySupply(
                fuel_type=FuelType.ELECTRICITY,
                simulation_time=self.simtime,
                tariff_path=None,
                electric_battery=ElectricBattery(
                    capacity=2,
                    charge_discharge_efficiency=0.8,
                    battery_age=3,
                    minimum_charge_rate=0.001,
                    maximum_charge_rate=1.5,
                    maximum_discharge_rate=1.5,
                    battery_location=BatteryLocation.INSIDE,
                    grid_charging_possible=True,
                    simulation_time=self.simtime,
                    external_conditions=self.__external_conditions,
                ),
            )
        self.assertFalse(self.energysupply.has_battery())
        self.assertIsNone(self.energysupply.get_battery_max_capacity())
        self.assertIsNone(self.energysupply.get_battery_charge_efficiency())
        self.assertIsNone(self.energysupply.get_battery_discharge_efficiency())
        self.assertIsNone(self.energysupply.get_battery_max_discharge(charge=0.7))
        self.assertIsNone(self.energysupply.get_battery_available_charge())

    def test_connection(self):
        """Test the correct end user name is assigned when creating the
        two different connections.
        """
        self.assertEqual(
            self.energysupplyconn_1._EnergySupplyConnection__end_user_name,  # type: ignore[AttributeAccessIssue]
            "shower",
            "end user name for connection 1 not returned",
        )
        self.assertEqual(
            self.energysupplyconn_2._EnergySupplyConnection__end_user_name,  # type: ignore[AttributeAccessIssue]
            "bath",
            "end user name for connection 2 not returned",
        )

        """ Test the energy supply is created as expected for the two
        different connections.
        """
        self.assertIs(
            self.energysupply,
            self.energysupplyconn_1._EnergySupplyConnection__energy_supply,  # type: ignore[AttributeAccessIssue]
            "energy supply for connection 1 not returned",
        )
        self.assertIs(
            self.energysupply,
            self.energysupplyconn_2._EnergySupplyConnection__energy_supply,  # type: ignore[AttributeAccessIssue]
            "energy supply for connection 2 not returned",
        )

    def test_existing_user_name(self):
        """Test that connecting with an existing end_user_name raises ValueError"""
        with self.assertRaises(ValueError):
            self.energysupply.connection("shower")

    def test_init_demand_list(self):
        """Check the initialised list of zero is returned"""
        self.assertEqual(
            self.energysupply._EnergySupply__init_demand_list(),  # type: ignore[AttributeAccessIssue]
            [0, 0, 0, 0, 0, 0, 0, 0],
        )

    def test_energy_out(self):
        # Check with existing end user name
        amount_demand = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0]
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.energysupply._energy_out(
                    end_user_name="shower", amount_demanded=amount_demand[t_idx]
                )
                self.assertEqual(
                    self.energysupply._EnergySupply__demand_total[t_idx],  # type: ignore[AttributeAccessIssue]
                    [0, 0, 0, 0, 0, 0, 0, 0][t_idx],
                )
                self.assertEqual(
                    self.energysupply._EnergySupply__energy_out_by_end_user["shower"][t_idx],  # type: ignore[AttributeAccessIssue]
                    [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0][t_idx],
                )

                # Check EnergySupplyConnection.energy_out
                self.assertEqual(
                    self.energysupplyconn_1.energy_out(amount_demanded=amount_demand[t_idx]),
                    self.energysupply._energy_out(
                        end_user_name="shower", amount_demanded=amount_demand[t_idx]
                    ),
                )

        # Check a system error is raised with new end user name
        with self.assertRaises(RuntimeError):
            self.energysupply._energy_out(end_user_name="electricshower", amount_demanded=10.0)

    def test_connect_diverter(self):
        self.diverter = MagicMock()
        self.energysupply.connect_diverter(self.diverter)
        self.assertEqual(self.energysupply._EnergySupply__diverter, self.diverter)  # type: ignore[AttributeAccessIssue]
        # Check system exits if diverter is already connected
        with self.assertRaises(RuntimeError):
            self.energysupply.connect_diverter(diverter=self.diverter)

    def test_demand_energy(self):
        amount_demanded = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0]
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.energysupply._demand_energy(
                    end_user_name="shower", amount_demanded=amount_demanded[t_idx]
                )
                self.assertEqual(
                    self.energysupply._EnergySupply__demand_total[t_idx],  # type: ignore[AttributeAccessIssue]
                    [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0][t_idx],
                )
                self.assertEqual(
                    self.energysupply._EnergySupply__demand_by_end_user["shower"][t_idx],  # type: ignore[AttributeAccessIssue]
                    [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0][t_idx],
                )
                with self.assertRaises(RuntimeError):
                    self.energysupply._demand_energy(
                        end_user_name="others", amount_demanded=amount_demanded[t_idx]
                    )

    def test_supply_energy(self):
        amount_produced = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0]
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.energysupply._supply_energy(
                    end_user_name="shower", amount_produced=amount_produced[t_idx]
                )
                self.assertEqual(
                    self.energysupply._EnergySupply__demand_total[t_idx],  # type: ignore[AttributeAccessIssue]
                    [-10.0, -20.0, -30.0, -40.0, -50.0, -60.0, -70.0, -80.0][t_idx],
                )
                self.assertEqual(
                    self.energysupply._EnergySupply__demand_by_end_user["shower"][t_idx],  # type: ignore[AttributeAccessIssue]
                    [-10.0, -20.0, -30.0, -40.0, -50.0, -60.0, -70.0, -80.0][t_idx],
                )

    def test_results_total(self):
        """Check the correct list of the total demand on this energy
        source for each timestep is returned.
        """
        demandtotal = [50.0, 120.0, 190.0, 260.0, 330.0, 400.0, 470.0, 540.0]
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.energysupplyconn_1.demand_energy(amount_demanded=(t_idx + 1.0) * 50.0)
                self.energysupplyconn_2.demand_energy(amount_demanded=t_idx * 20.0)
                self.assertEqual(
                    self.energysupply.results_total()[t_idx],
                    demandtotal[t_idx],
                    "incorrect total demand energy returned",
                )

    def test_results_by_end_user_and_step(self):
        """Check the correct list of the total demand on this energy
        source for each timestep is returned for each connection and time step.
        """
        demandtotal_1 = [50.0, 100.0, 150.0, 200.0, 250.0, 300.0, 350.0, 400.0]
        demandtotal_2 = [0.0, 20.0, 40.0, 60.0, 80.0, 100.0, 120.0, 140.0]
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.energysupplyconn_1.demand_energy(amount_demanded=(t_idx + 1.0) * 50.0)
                self.energysupplyconn_2.demand_energy(amount_demanded=t_idx * 20.0)
                self.assertEqual(
                    self.energysupply.results_by_end_user()["shower"][t_idx],
                    demandtotal_1[t_idx],
                    "incorrect demand by end user returned",
                )
                self.assertEqual(
                    self.energysupply.results_by_end_user()["bath"][t_idx],
                    demandtotal_2[t_idx],
                    "incorrect demand by end user returned",
                )
                self.assertEqual(
                    self.energysupply.results_by_end_user_single_step(t_idx),
                    {
                        self.energysupplyconn_1._EnergySupplyConnection__end_user_name: demandtotal_1[  # type: ignore[AttributeAccessIssue]
                            t_idx
                        ],
                        self.energysupplyconn_2._EnergySupplyConnection__end_user_name: demandtotal_2[  # type: ignore[AttributeAccessIssue]
                            t_idx
                        ],
                    },
                    "incorrect demands from each end user for the timestep returned",
                )

                # Case where end_user is not in __energy_out_by_end_user,
                # (__demand_by_end_user.keys() != __energy_out_by_end_user.keys())
                self.energysupply._EnergySupply__energy_out_by_end_user["others"] = demandtotal_1[  # type: ignore[AttributeAccessIssue]
                    t_idx
                ]
                self.assertEqual(
                    self.energysupply.results_by_end_user()["shower"][t_idx],
                    demandtotal_1[t_idx],
                    "incorrect demands from each end user for the timestep returned",
                )

                # Testing the edge case at the last timestep,
                # to check when an end_user exists only in __demand_by_end_user, not in __energy_out_by_end_user.
                if t_idx == 7:
                    self.energysupply._EnergySupply__demand_by_end_user["others1"] = [0.0] * 8  # type: ignore[AttributeAccessIssue]
                    self.energysupply._EnergySupply__demand_by_end_user["others1"][t_idx] = (  # type: ignore[AttributeAccessIssue]
                        t_idx + 1.0
                    ) * 50.0
                    self.assertEqual(
                        self.energysupply.results_by_end_user_single_step(t_idx),
                        {
                            self.energysupplyconn_1._EnergySupplyConnection__end_user_name: demandtotal_1[  # type: ignore[AttributeAccessIssue]
                                t_idx
                            ],
                            self.energysupplyconn_2._EnergySupplyConnection__end_user_name: demandtotal_2[  # type: ignore[AttributeAccessIssue]
                                t_idx
                            ],
                            "others1": (t_idx + 1.0) * 50.0,
                        },
                    )

    def test_beta_factor(self):
        """check beta factor and surplus supply/demand are calculated correctly"""
        energysupplyconn_3 = self.energysupply.connection("PV")
        betafactor = [
            1.0,
            0.8973610789278808,
            0.4677549807236648,
            0.3297589507351858,
            0.2578125,
            0.2,
            0.16319444444444445,
            0.1377551020408163,
        ]

        surplus = [
            0.0,
            -8.21111368576954,
            -170.3184061684273,
            -482.57355547066624,
            -950.0,
            -1600.0,
            -2410.0,
            -3380.0,
        ]
        generation_to_grid = [
            0.0,
            -8.21111368576954,
            -170.3184061684273,
            -482.57355547066624,
            -950.0,
            -1600.0,
            -2410.0,
            -3380.0,
        ]
        demandnotmet = [
            50.0,
            48.21111368576953,
            40.31840616842726,
            22.573555470666236,
            0.0,
            0.0,
            0.0,
            0.0,
        ]

        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.energysupplyconn_1.demand_energy(amount_demanded=(t_idx + 1.0) * 50.0)
                self.energysupplyconn_2.demand_energy(amount_demanded=t_idx * 20.0)
                energysupplyconn_3.supply_energy(amount_produced=t_idx * t_idx * 80.0)

                self.energysupply.calc_energy_import_export_betafactor()

                self.assertEqual(
                    self.energysupply.get_beta_factor()[t_idx],
                    betafactor[t_idx],
                    "incorrect beta factor returned",
                )
                self.assertEqual(
                    self.energysupply.get_energy_export()[t_idx],
                    surplus[t_idx],
                    "incorrect energy export returned",
                )
                self.assertEqual(
                    self.energysupply.get_energy_export_from_generation()[t_idx],
                    generation_to_grid[t_idx],
                    "incorrect energy export from generation returned",
                )
                self.assertEqual(
                    self.energysupply.get_energy_import()[t_idx],
                    demandnotmet[t_idx],
                    "incorrect energy import returned",
                )

        # When beta_factor_faction is not PV (not captured when calling get_beta_factor())
        with self.assertRaises(ValueError):
            self.energysupply.beta_factor_function(
                supply=1.0, demand=1.0, beta_factor_function="wind"
            )

        # When there is no demand, beta_factor_function returns 0
        self.assertEqual(
            self.energysupply.beta_factor_function(supply=5, demand=0, beta_factor_function="PV"),
            0.0,
            "incorrect beta factor returned",
        )

    def test_battery_with_grid_charging_and_priority(self):
        """Tests for EnergySupply battery with grid_charging, tariffs, and priority"""
        # Valid battery where there is grid charging and tariff_path is set
        self.energysupply = EnergySupply(
            fuel_type=FuelType.ELECTRICITY,
            simulation_time=self.simtime,
            tariff_path=TARIFF_DATA,
            tariff="Variable Time of Day Tariff",
            threshold_charges=[0.8, 0.7, 0.7, 0.8, 0.6, 0.8, 0.7, 0.7, 0.8, 0.7, 0.8, 0.8],
            threshold_prices=[16, 16, 16, 20, 20, 20, 20, 20, 20, 20, 20, 20],
            electric_battery=ElectricBattery(
                capacity=2,
                charge_discharge_efficiency=0.8,
                battery_age=3,
                minimum_charge_rate=0.001,
                maximum_charge_rate=1.5,
                maximum_discharge_rate=1.5,
                battery_location=BatteryLocation.INSIDE,
                grid_charging_possible=True,
                simulation_time=self.simtime,
                external_conditions=self.__external_conditions,
            ),
            priority=["ElectricBattery", "diverter"],
        )

        self.assertIsInstance(self.energysupply._EnergySupply__tariff_data, TariffData)  # type: ignore[AttributeAccessIssue]
        self.assertTrue(self.energysupply.has_battery())

        battery_state_of_health = (
            -0.04 * self.energysupply._EnergySupply__elec_battery._ElectricBattery__battery_age + 1  # type: ignore[AttributeAccessIssue]
        )

        self.assertEqual(
            self.energysupply.get_battery_max_capacity(),
            2 * battery_state_of_health,  # max capacity * state of health
        )
        self.assertEqual(
            self.energysupply.get_battery_charge_efficiency(),
            0.8**0.5
            * battery_state_of_health
            * 1,  # one way efficiency * state of health * air_temp_capacity_factor
        )
        self.assertEqual(
            self.energysupply.get_battery_discharge_efficiency(),
            1
            / (0.8**0.5)
            * battery_state_of_health
            * 1,  # reverse one way efficiency * state of health * air_temp_capacity_factor
        )
        self.assertEqual(
            self.energysupply.get_battery_max_discharge(charge=0.7),
            (1.5 * 1) * -1,  # max discharge rate * discharge factor * timestep * -1
        )
        self.assertEqual(self.energysupply.get_battery_available_charge(), 0)

        expected_charging_state = [
            (True, 0.8, True),  # elec_price/efficiency=13.5877158875 < 16; current charge=0
            (False, 0.8, True),  # elec_price/efficiency=12.16550081375 < 16;
            (False, 0.8, False),  # elec_price/efficiency=18.1486140875 !< 16
            (False, 0.8, True),  # elec_price/efficiency=11.6733265175 < 16
            (False, 0.8, False),  # elec_price/efficiency=25.5426676375 !< 16
            (False, 0.8, False),  # elec_price/efficiency=24.914735325 !< 16
            (False, 0.8, False),  # elec_price/efficiency=24.1577282 !< 16
            (False, 0.8, False),  # elec_price/efficiency=17.394483375 !< 16
        ]
        expected_energy_import_from_grid = [1.5741918561598522, 0, 0, 0, 0, 0, 0, 0]
        expected_diverted_energy = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        expected_generated_energy_into_battery = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        expected_energy_out_of_battery = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        expected_battery_state_of_charge = [0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8]

        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.energysupply.is_charging_from_grid(), expected_charging_state[t_idx]
                )
                self.energysupply.calc_energy_import_from_grid_to_battery()
                self.energysupply.timestep_end()

                # Test for calc_energy_import_export_betafactor when "ElectricBattery" in priority
                self.energysupply.calc_energy_import_export_betafactor()

        self.assertEqual(self.energysupply.get_energy_diverted(), expected_diverted_energy)
        self.assertEqual(
            self.energysupply.get_energy_to_from_battery(),
            (
                expected_generated_energy_into_battery,
                expected_energy_out_of_battery,
                expected_energy_import_from_grid,
                expected_battery_state_of_charge,
            ),
        )

    def test_battery_with_grid_charging_no_priority(self):
        """Tests for battery with grid charging but no priority"""
        self.energysupply = EnergySupply(
            fuel_type=FuelType.ELECTRICITY,
            simulation_time=self.simtime,
            tariff_path=TARIFF_DATA,
            tariff="Variable Time of Day Tariff",
            threshold_charges=[0.8, 0.7, 0.7, 0.8, 0.6, 0.8, 0.7, 0.7, 0.8, 0.7, 0.8, 0.8],
            threshold_prices=[16, 16, 16, 20, 20, 20, 20, 20, 20, 20, 20, 20],
            electric_battery=ElectricBattery(
                capacity=2,
                charge_discharge_efficiency=0.8,
                battery_age=3,
                minimum_charge_rate=0.001,
                maximum_charge_rate=1.5,
                maximum_discharge_rate=1.5,
                battery_location=BatteryLocation.INSIDE,
                grid_charging_possible=True,
                simulation_time=self.simtime,
                external_conditions=self.__external_conditions,
            ),
        )

        expected_generated_energy_into_battery = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        expected_energy_out_of_battery = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        expected_grid_energy_into_battery = [0, 0, 0, 0, 0, 0, 0, 0]
        expected_battery_state_of_charge = [0, 0, 0, 0, 0, 0, 0, 0]

        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.energysupply.calc_energy_import_export_betafactor()

        self.assertEqual(
            self.energysupply.get_energy_to_from_battery(),
            (
                expected_generated_energy_into_battery,
                expected_energy_out_of_battery,
                expected_grid_energy_into_battery,
                expected_battery_state_of_charge,
            ),
        )

    def test_battery_without_grid_charging(self):
        """Tests for battery without import from grid"""
        self.energysupply = EnergySupply(
            fuel_type=FuelType.ELECTRICITY,
            simulation_time=self.simtime,
            electric_battery=ElectricBattery(
                capacity=2,
                charge_discharge_efficiency=0.8,
                battery_age=3,
                minimum_charge_rate=0.001,
                maximum_charge_rate=1.5,
                maximum_discharge_rate=1.5,
                battery_location=BatteryLocation.INSIDE,
                grid_charging_possible=False,
                simulation_time=self.simtime,
                external_conditions=self.__external_conditions,
            ),
        )

        expected_generated_energy_into_battery = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        expected_energy_out_of_battery = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        expected_grid_energy_into_battery = [0, 0, 0, 0, 0, 0, 0, 0]
        expected_battery_state_of_charge = [0, 0, 0, 0, 0, 0, 0, 0]
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.energysupply.calc_energy_import_from_grid_to_battery()
                self.energysupply.timestep_end()

        self.assertEqual(
            self.energysupply.get_energy_to_from_battery(),
            (
                expected_generated_energy_into_battery,
                expected_energy_out_of_battery,
                expected_grid_energy_into_battery,
                expected_battery_state_of_charge,
            ),
        )

    def test_calc_energy_import_export_betafactor(self):
        amount_demanded = [50.0, 100.0, 150.0, 200.0, 250.0, 300.0, 350.0, 400.0]
        amount_produced = [50.0, 90.0, 130.0, 210.0, 2300.0, 290.0, 300.0, 350.0]

        self.elec_battery = ElectricBattery(
            capacity=2,
            charge_discharge_efficiency=0.8,
            battery_age=3,
            minimum_charge_rate=0.001,
            maximum_charge_rate=1.5,
            maximum_discharge_rate=1.5,
            battery_location=BatteryLocation.OUTSIDE,
            grid_charging_possible=False,
            simulation_time=self.simtime,
            external_conditions=self.__external_conditions,
        )
        self.energysupply = EnergySupply(
            fuel_type=FuelType.ELECTRICITY,
            simulation_time=self.simtime,
            electric_battery=self.elec_battery,
        )
        self.energysupply.connection("shower")
        self.energysupply.connection("bath")
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.energysupply._demand_energy(
                    end_user_name="shower", amount_demanded=amount_demanded[t_idx]
                )
                self.energysupply._supply_energy(
                    end_user_name="bath", amount_produced=amount_produced[t_idx]
                )
                self.energysupply.calc_energy_import_export_betafactor()

        expected_generated_energy_into_battery = [
            1.6770509831248424,
            -0.0,
            -0.0,
            -0.0,
            -0.0,
            -0.0,
            -0.0,
            -0.0,
        ]
        expected_energy_out_of_battery = [
            -1.121472,
            -0.2201687864998738,
            -0.0,
            -0.0,
            0.0,
            -0.0,
            -0.0,
            -0.0,
        ]
        expected_diverted_energy = [0, 0, 0, 0, 0, 0, 0, 0]
        expected_grid_energy_into_battery = [
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
        ]  # grid charging not enabled in this case
        expected_battery_state_of_charge = [0, 0, 0, 0, 0, 0, 0, 0]

        self.assertEqual(
            self.energysupply._EnergySupply__demand_total,  # type: ignore[AttributeAccessIssue]
            [0.0, 10.0, 20.0, -10.0, -2050.0, 10.0, 50.0, 50.0],
        )
        self.assertEqual(
            self.energysupply._EnergySupply__demand_not_met,  # type: ignore[AttributeAccessIssue]
            [
                15.138528000000004,
                34.37872423953049,
                52.991809292243516,
                63.07009986960006,
                -2.842170943040401e-14,
                99.5880926222444,
                124.3891811736907,
                140.57522007095577,
            ],
        )
        self.assertEqual(
            self.energysupply._EnergySupply__supply_surplus,  # type: ignore[AttributeAccessIssue]
            [
                -14.582949016875158,
                -24.59889302603037,
                -32.991809292243516,
                -73.07009986960004,
                -2050.0,
                -89.5880926222444,
                -74.38918117369072,
                -90.5752200709558,
            ],
        )
        self.assertEqual(
            self.energysupply.get_energy_generated_consumed(),
            [
                33.739999999999995,
                65.40110697396963,
                97.00819070775648,
                136.92990013039994,
                250.00000000000003,
                200.4119073777556,
                225.6108188263093,
                259.42477992904423,
            ],
        )
        self.assertEqual(
            self.energysupply.get_grid_to_consumption(),
            [
                15.138528000000004,
                34.37872423953049,
                52.991809292243516,
                63.07009986960006,
                -2.842170943040401e-14,
                99.5880926222444,
                124.3891811736907,
                140.57522007095577,
            ],
        )
        self.assertEqual(
            self.energysupply.get_energy_to_from_battery(),
            (
                expected_generated_energy_into_battery,
                expected_energy_out_of_battery,
                expected_grid_energy_into_battery,
                expected_battery_state_of_charge,
            ),
        )
        self.assertEqual(self.energysupply.get_energy_diverted(), expected_diverted_energy)
        self.assertEqual(
            self.energysupply._EnergySupply__beta_factor,  # type: ignore[AttributeAccessIssue]
            [
                0.6748,
                0.7266789663774403,
                0.7462168515981268,
                0.652047143478095,
                0.10869565217391305,
                0.6910755426819158,
                0.7520360627543643,
                0.7412136569401263,
            ],
        )

        # Test with PV diverter
        self.diverter = MagicMock()
        self.energysupply.connect_diverter(diverter=self.diverter)
        self.diverter.divert_surplus.return_value = 10
        self.simtime.reset()
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.energysupply._demand_energy(
                    end_user_name="shower", amount_demanded=amount_demanded[t_idx]
                )
                self.energysupply._supply_energy(
                    end_user_name="bath", amount_produced=amount_produced[t_idx]
                )
                self.energysupply.calc_energy_import_export_betafactor()

        self.assertEqual(
            self.energysupply._EnergySupply__demand_total,  # type: ignore[AttributeAccessIssue]
            [0.0, 20.0, 40.0, -20.0, -4100.0, 20.0, 100.0, 100.0],
        )
        self.assertEqual(
            self.energysupply._EnergySupply__demand_not_met,  # type: ignore[AttributeAccessIssue]
            [
                47.65852800000002,
                103.57651029159123,
                158.97542787673055,
                189.21029960880017,
                -8.526512829121202e-14,
                298.7642778667332,
                373.1675435210721,
                421.7256602128673,
            ],
        )

        self.assertEqual(
            self.energysupply._EnergySupply__supply_surplus,  # type: ignore[AttributeAccessIssue]
            [
                -37.10294901687516,
                -63.79667907809112,
                -88.97542787673055,
                -209.21029960880014,
                -6140.0,
                -258.7642778667332,
                -213.16754352107216,
                -261.7256602128674,
            ],
        )

        self.assertEqual(
            self.energysupply._EnergySupply__energy_generated_consumed,  # type: ignore[AttributeAccessIssue]
            [
                101.21999999999998,
                196.2033209219089,
                291.0245721232694,
                410.78970039119986,
                750.0000000000001,
                601.2357221332668,
                676.832456478928,
                778.2743397871327,
            ],
        )

        self.assertEqual(
            self.energysupply._EnergySupply__energy_into_battery_from_generation,  # type: ignore[AttributeAccessIssue]
            [-0.0, -0.0, -0.0, -0.0, -0.0, -0.0, -0.0, -0.0],
        )
        self.assertEqual(
            self.energysupply._EnergySupply__energy_battery_to_consumption,  # type: ignore[AttributeAccessIssue]
            [-0.0, -0.0, -0.0, -0.0, 0, -0.0, -0.0, -0.0],
        )
        self.assertEqual(
            self.energysupply._EnergySupply__energy_diverted,  # type: ignore[AttributeAccessIssue]
            [10, 10, 10, 10, 10, 10, 10, 10],
        )
        self.assertEqual(
            self.energysupply._EnergySupply__beta_factor,  # type: ignore[AttributeAccessIssue]
            [
                0.6748,
                0.7266789663774403,
                0.7462168515981268,
                0.652047143478095,
                0.10869565217391305,
                0.6910755426819158,
                0.7520360627543643,
                0.7412136569401263,
            ],
        )

        # Set priority
        self.energysupply = EnergySupply(
            fuel_type=FuelType.ELECTRICITY,
            simulation_time=self.simtime,
            electric_battery=self.elec_battery,
            priority=["diverter", "ElectricBattery"],
        )
        self.energysupply.connection("shower")
        self.energysupply.connection("bath")
        self.diverter = MagicMock()
        self.energysupply.connect_diverter(diverter=self.diverter)
        self.diverter.divert_surplus.return_value = 10
        self.simtime.reset()
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.energysupply._demand_energy(
                    end_user_name="shower", amount_demanded=amount_demanded[t_idx]
                )
                self.energysupply._supply_energy(
                    end_user_name="bath", amount_produced=amount_produced[t_idx]
                )
                self.energysupply.calc_energy_import_export_betafactor()

        self.assertEqual(
            self.energysupply._EnergySupply__demand_total,  # type: ignore[AttributeAccessIssue]
            [0.0, 10.0, 20.0, -10.0, -2050.0, 10.0, 50.0, 50.0],
        )
        self.assertEqual(
            self.energysupply._EnergySupply__demand_not_met,  # type: ignore[AttributeAccessIssue]
            [
                16.260000000000005,
                34.59889302603037,
                52.991809292243516,
                63.07009986960006,
                -2.842170943040401e-14,
                99.5880926222444,
                124.3891811736907,
                140.57522007095577,
            ],
        )
        self.assertEqual(
            self.energysupply._EnergySupply__supply_surplus,  # type: ignore[AttributeAccessIssue]
            [
                -6.260000000000002,
                -14.598893026030371,
                -22.991809292243516,
                -63.07009986960004,
                -2040.0,
                -79.5880926222444,
                -64.38918117369072,
                -80.5752200709558,
            ],
        )
        self.assertEqual(
            self.energysupply._EnergySupply__energy_generated_consumed,  # type: ignore[AttributeAccessIssue]
            [
                33.739999999999995,
                65.40110697396963,
                97.00819070775648,
                136.92990013039994,
                250.00000000000003,
                200.4119073777556,
                225.6108188263093,
                259.42477992904423,
            ],
        )
        self.assertEqual(
            self.energysupply._EnergySupply__energy_into_battery_from_generation,  # type: ignore[AttributeAccessIssue]
            [-0.0, -0.0, -0.0, -0.0, -0.0, -0.0, -0.0, -0.0],
        )
        self.assertEqual(
            self.energysupply._EnergySupply__energy_battery_to_consumption,  # type: ignore[AttributeAccessIssue]
            [-0.0, -0.0, -0.0, -0.0, -0.0, -0.0, -0.0, -0.0],
        )
        self.assertEqual(
            self.energysupply._EnergySupply__energy_diverted,  # type: ignore[AttributeAccessIssue]
            [10, 10, 10, 10, 10, 10, 10, 10],
        )
        self.assertEqual(
            self.energysupply._EnergySupply__beta_factor,  # type: ignore[AttributeAccessIssue]
            [
                0.6748,
                0.7266789663774403,
                0.7462168515981268,
                0.652047143478095,
                0.10869565217391305,
                0.6910755426819158,
                0.7520360627543643,
                0.7412136569401263,
            ],
        )


class TestEnergySupplyWithExport(unittest.TestCase):
    """Unit tests for EnergySupply class"""

    def setUp(self):
        """Create EnergySupply object to be tested"""
        self.simtime = SimulationTime(start_time=0, end_time=8, step=1)
        self.energysupply = EnergySupply(
            fuel_type=FuelType.MAINS_GAS, simulation_time=self.simtime, is_export_capable=False
        )
        """ Set up two different energy supply connections """
        self.energysupplyconn_1 = self.energysupply.connection(end_user_name="shower")
        self.energysupplyconn_2 = self.energysupply.connection(end_user_name="bath")

    def test_without_export(self):
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.energysupplyconn_1.demand_energy(amount_demanded=(t_idx + 1.0) * 50.0)
                self.energysupplyconn_2.demand_energy(amount_demanded=t_idx * 20.0)
                self.assertEqual(
                    self.energysupply.get_energy_export()[t_idx],
                    0,
                    "incorrect energy export returned",
                )
