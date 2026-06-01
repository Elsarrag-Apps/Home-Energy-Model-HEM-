#!/usr/bin/env python3

"""
This module contains unit tests for the heat_pump module
"""

import unittest
from copy import deepcopy
from unittest.mock import ANY, MagicMock, Mock, PropertyMock, patch

from hem_core.controls.time_control import OnOffTimeControl, SetpointTimeControl
from hem_core.energy_supply.energy_supply import EnergySupply, EnergySupplyConnection
from hem_core.external_conditions import ExternalConditions
from hem_core.heating_systems.boiler import Boiler, BoilerServiceSpace, BoilerServiceWaterCombi
from hem_core.heating_systems.enums import HeatingServiceType
from hem_core.heating_systems.heat_pump import (
    BufferTank,
    HeatPump,
    HeatPump_HWOnly,
    HeatPumpCharacteristics,
    HeatPumpData,
    HeatPumpEmitterType,
    HeatPumpService,
    HeatPumpServiceSpace,
    HeatPumpServiceWater,
    HeatPumpTestData,
    HeatPumpWarmAir,
    HWHeatPumpData,
    SourceType,
    interpolate_exhaust_air_heat_pump_test_data,
)
from hem_core.input_output.enums import (
    FuelType,
    HeatPumpBackupControlType,
    HeatPumpSinkType,
    HeatSourceLocation,
)
from hem_core.material_properties import WATER
from hem_core.simulation_time import SimulationTime
from hem_core.units import Celcius2Kelvin, Orientation360
from hem_core.water_heat_demand.cold_water_source import ColdWaterSource


class Test_BufferTank(unittest.TestCase):
    """Unit tests for BufferTank class"""

    def setUp(self):
        """Create BufferTank object to be tested"""
        self.simtime = SimulationTime(start_time=0, end_time=8, step=1)
        self.buffertank = BufferTank(
            daily_losses=1.68,
            volume=50,
            pump_fixed_flow_rate=15,
            pump_power_at_flow_rate=0.040,
            number_of_zones=2,
            simulation_time=self.simtime,
            contents=WATER,
            initial_temp=20,
            output_detailed_results=True,
        )
        # emitters data needed to run buffer tank calculations
        self.emitters_data_for_buffer_tank = [
            {
                "temp_emitter_req": 43.32561228292832,
                "power_req_from_buffer_tank": 6.325422354229758,
                "design_flow_temp": 55,
                "target_flow_temp": 48.54166666666667,
                "temp_rm_prev": 22.488371468978006,
                "variable_flow": True,
                "min_flow_rate": 0.05,
                "max_flow_rate": 0.3,
                "temp_diff_emit_dsgn": 10.0,
            },
            {
                "temp_emitter_req": 30.778566169260767,
                "power_req_from_buffer_tank": 4.036801431329545,
                "design_flow_temp": 55,
                "target_flow_temp": 48.54166666666667,
                "temp_rm_prev": 22.61181775388348,
                "variable_flow": True,
                "min_flow_rate": 0.05,
                "max_flow_rate": 0.3,
                "temp_diff_emit_dsgn": 10.0,
            },
            {
                "temp_emitter_req": 50.248361664005266,
                "power_req_from_buffer_tank": 8.808940459526795,
                "design_flow_temp": 55,
                "target_flow_temp": 49.375,
                "temp_rm_prev": 17.736483875769345,
                "variable_flow": True,
                "min_flow_rate": 0.05,
                "max_flow_rate": 0.3,
                "temp_diff_emit_dsgn": 10.0,
            },
            {
                "temp_emitter_req": 30.723032018863076,
                "power_req_from_buffer_tank": 6.444185473658857,
                "design_flow_temp": 55,
                "target_flow_temp": 49.375,
                "temp_rm_prev": 16.85636993835381,
                "variable_flow": True,
                "min_flow_rate": 0.05,
                "max_flow_rate": 0.3,
                "temp_diff_emit_dsgn": 10.0,
            },
            {
                "temp_emitter_req": 29.646908204800425,
                "power_req_from_buffer_tank": 5.00550934831923,
                "design_flow_temp": 55,
                "target_flow_temp": 48.75,
                "temp_rm_prev": 17.22290169647781,
                "variable_flow": True,
                "min_flow_rate": 0.05,
                "max_flow_rate": 0.3,
                "temp_diff_emit_dsgn": 10.0,
            },
            {
                "temp_emitter_req": 30.42417311801241,
                "power_req_from_buffer_tank": 2.5923631086027457,
                "design_flow_temp": 55,
                "target_flow_temp": 48.22916666666667,
                "temp_rm_prev": 21.897823675853978,
                "variable_flow": True,
                "min_flow_rate": 0.05,
                "max_flow_rate": 0.3,
                "temp_diff_emit_dsgn": 10.0,
            },
            {
                "temp_emitter_req": 39.38823309970535,
                "power_req_from_buffer_tank": 1.9107311055974638,
                "design_flow_temp": 55,
                "target_flow_temp": 48.4375,
                "temp_rm_prev": 22.36470513987037,
                "variable_flow": True,
                "min_flow_rate": 0.05,
                "max_flow_rate": 0.3,
                "temp_diff_emit_dsgn": 10.0,
            },
            {
                "temp_emitter_req": 28.934946810199524,
                "power_req_from_buffer_tank": 1.711635686322881,
                "design_flow_temp": 55,
                "target_flow_temp": 48.4375,
                "temp_rm_prev": 22.425363294403255,
                "variable_flow": True,
                "min_flow_rate": 0.05,
                "max_flow_rate": 0.3,
                "temp_diff_emit_dsgn": 10.0,
            },
        ]

    def test_buffer_loss(self):
        """Test the buffer loss over the simulation time"""
        # temperatures required to calculate buffer tank thermal losses
        temp_ave_buffer = [
            42.13174056962889,
            39.15850036184071,
            47.90592627854362,
            46.396261107092855,
            44.393784168519964,
            41.113688636784985,
            38.05323632350841,
            34.94802876725388,
            37.658992822855524,
            34.3155583742916,
        ]
        temp_rm_prev = [
            22.503414923272768,
            22.629952417028925,
            18.606533490587633,
            17.3014761483025,
            16.89603650204302,
            22.631060393299737,
            22.434635318905773,
            22.736995736582873,
            22.603763288379653,
            22.89241467168529,
        ]
        # Expected results
        heat_loss_buffer_kWh = [
            0.01620674285529469,
            0.0063519154341823356,
            0.025287016057516827,
            0.010785181618173873,
            0.009663116173139813,
            0.0066316051216787795,
            0.01324052174653832,
            0.005063009401174876,
        ]
        flow_temp_increase_due_to_buffer = [
            3.952751095382638,
            6.140725209053976,
            1.5784508035116716,
            3.8392108282420097,
            5.2146182138439485,
            7.521641387569073,
            7.370102324208936,
            6.569653721125626,
        ]
        expected_thermal_losses = [
            0.015266475502721427,
            0.012855537290409166,
            0.022788416612854655,
            0.02262927719017028,
            0.02138713707392651,
            0.014375377522710748,
            0.012147800781357604,
            0.00949747013496634,
        ]
        expected_internal_gains = [
            24.31011428294203,
            9.527873151273504,
            37.93052408627524,
            16.17777242726081,
            14.494674259709718,
            9.947407682518168,
            19.86078261980748,
            7.594514101762314,
        ]

        # Simulate updating buffer loss over time
        for t_idx, _, _ in self.simtime:
            buffer_results = self.buffertank.calc_buffer_tank(
                service_name="test service",
                emitters_data_for_buffer_tank=self.emitters_data_for_buffer_tank[t_idx],
            )
            internal_gains = self.buffertank.internal_gains()
            thermal_losses = self.buffertank.thermal_losses(
                temp_average_buffer=temp_ave_buffer[t_idx], temp_rm_prev=temp_rm_prev[t_idx]
            )

            with self.subTest(i=t_idx):
                self.assertAlmostEqual(
                    buffer_results[t_idx]["heat_loss_buffer_kWh"],
                    heat_loss_buffer_kWh[t_idx],
                    msg=f"Incorrect buffer loss at timestep {t_idx}",
                )

            with self.subTest(i=t_idx):
                self.assertAlmostEqual(
                    buffer_results[t_idx]["flow_temp_increase_due_to_buffer"],
                    flow_temp_increase_due_to_buffer[t_idx],
                    msg=f"Incorrect flow temperature increase due to buffer at timestep {t_idx}",
                )

            with self.subTest(i=t_idx):
                self.assertAlmostEqual(
                    thermal_losses,
                    expected_thermal_losses[t_idx],
                    msg=f"Incorrect buffer tank thermal losses at timestep {t_idx}",
                )

            with self.subTest(i=t_idx):
                self.assertAlmostEqual(
                    internal_gains,
                    expected_internal_gains[t_idx],
                    msg=f"Incorrect buffer tank internal gains at timestep {t_idx}",
                )

    def test_update_buffer_loss(self):
        self.buffertank.update_buffer_loss(buffer_loss=5)
        self.assertEqual(self.buffertank.get_buffer_loss(), 5)

    def test_calc_buffer_tank_over_max_flow(self):
        """Test calc_buffer_tank returns the correct values with hp_flow above max_flow_rate"""
        data = self.emitters_data_for_buffer_tank[0]

        data["max_flow_rate"] = 0.1

        results = self.buffertank.calc_buffer_tank(
            service_name="new_service", emitters_data_for_buffer_tank=data
        )[0]

        self.assertEqual(results["service_name"], "new_service_buffer_tank")
        self.assertAlmostEqual(results["power_req_from_buffer_tank"], 6.325422354229758)
        self.assertAlmostEqual(results["temp_emitter_req"], 43.32561228292832)
        self.assertAlmostEqual(results["buffer_emitter_circ_flow_rate"], 15)
        self.assertAlmostEqual(results["flow_temp_increase_due_to_buffer"], 9.109608401991274)
        self.assertAlmostEqual(results["pump_power_at_flow_rate"], 0.04)
        self.assertAlmostEqual(results["heat_loss_buffer_kWh"], 0.01620674285529469)

    def test_calc_buffer_tank_over_variable_flow(self):
        """Test calc_buffer_tank returns the correct values with variable flow"""
        data = self.emitters_data_for_buffer_tank[0]

        data["variable_flow"] = False

        results = self.buffertank.calc_buffer_tank(
            service_name="new_service", emitters_data_for_buffer_tank=data
        )[0]

        self.assertEqual(results["service_name"], "new_service_buffer_tank")
        self.assertAlmostEqual(results["power_req_from_buffer_tank"], 6.325422354229758)
        self.assertAlmostEqual(results["temp_emitter_req"], 43.32561228292832)
        self.assertAlmostEqual(results["buffer_emitter_circ_flow_rate"], 15)
        self.assertAlmostEqual(results["flow_temp_increase_due_to_buffer"], 24.26646570859991)
        self.assertAlmostEqual(results["pump_power_at_flow_rate"], 0.04)
        self.assertAlmostEqual(results["heat_loss_buffer_kWh"], 0.01620674285529469)

    def test_calc_buffer_tank_no_power_req(self):
        """Test calc_buffer_tank returns the correct values with 0 req from buffer tank"""
        data = self.emitters_data_for_buffer_tank[0]

        data["power_req_from_buffer_tank"] = 0

        results = self.buffertank.calc_buffer_tank(
            service_name="new_service", emitters_data_for_buffer_tank=data
        )[0]

        self.assertEqual(results["service_name"], "new_service_buffer_tank")
        self.assertAlmostEqual(results["power_req_from_buffer_tank"], 0)
        self.assertAlmostEqual(results["temp_emitter_req"], 43.32561228292832)
        self.assertAlmostEqual(results["buffer_emitter_circ_flow_rate"], 15)
        self.assertAlmostEqual(results["flow_temp_increase_due_to_buffer"], 0)
        self.assertAlmostEqual(results["pump_power_at_flow_rate"], 0)
        self.assertAlmostEqual(results["heat_loss_buffer_kWh"], -0.0019354000314273378)

    def test_calc_buffer_tank_over_emitter_flow(self):
        """Test calc_buffer_tank throws when over the emitter flow"""
        data = self.emitters_data_for_buffer_tank[0]

        data["variable_flow"] = False
        data["max_flow_rate"] = 5
        data["min_flow_rate"] = 10

        with self.assertRaises(ValueError):
            self.buffertank.calc_buffer_tank(
                service_name="new_service", emitters_data_for_buffer_tank=data
            )[0]

    def test_calc_buffer_tank_detailed_results(self):
        """Test that calc_buffer_tank updates detailed_results with the results"""
        data = self.emitters_data_for_buffer_tank[0]

        self.buffertank.calc_buffer_tank(
            service_name="new_service", emitters_data_for_buffer_tank=data
        )[0]

        results = self.buffertank.detailed_results
        assert results is not None

        self.assertEqual(len(results), 1)
        self.assertEqual(len(results[0]), 1)

        self.assertEqual(results[0][0]["service_name"], "new_service_buffer_tank")
        self.assertAlmostEqual(results[0][0]["power_req_from_buffer_tank"], 6.325422354229758)
        self.assertAlmostEqual(results[0][0]["temp_emitter_req"], 43.32561228292832)
        self.assertAlmostEqual(results[0][0]["buffer_emitter_circ_flow_rate"], 15)
        self.assertAlmostEqual(results[0][0]["flow_temp_increase_due_to_buffer"], 3.952751095382638)
        self.assertAlmostEqual(results[0][0]["pump_power_at_flow_rate"], 0.04)
        self.assertAlmostEqual(results[0][0]["heat_loss_buffer_kWh"], 0.01620674285529469)


class TestHeatPumpFreeFunctions(unittest.TestCase):
    """Unit tests for free functions in heat_pump module"""

    def test_interpolate_exhaust_air_heat_pump_test_data(self):
        """Test interpolation of exhaust air heat pump test data"""
        data_eahp = [
            HeatPumpData(
                {
                    "air_flow_rate": 100.0,
                    "test_letter": "A",
                    "capacity": 5.0,
                    "cop": 2.0,
                    "design_flow_temp": 55,
                    "temp_outlet": 55,
                    "temp_source": 20,
                    "temp_test": -7,
                    "eahp_mixed_ext_air_ratio": 0.25,
                }
            ),
            HeatPumpData(
                {
                    "air_flow_rate": 200.0,
                    "test_letter": "A",
                    "capacity": 6.0,
                    "cop": 2.5,
                    "design_flow_temp": 55,
                    "temp_outlet": 55,
                    "temp_source": 20,
                    "temp_test": -7,
                    "eahp_mixed_ext_air_ratio": 0.75,
                }
            ),
            HeatPumpData(
                {
                    "air_flow_rate": 100.0,
                    "test_letter": "B",
                    "capacity": 5.5,
                    "cop": 2.4,
                    "design_flow_temp": 35,
                    "temp_outlet": 34,
                    "temp_source": 20,
                    "temp_test": 2,
                    "eahp_mixed_ext_air_ratio": 0.25,
                }
            ),
            HeatPumpData(
                {
                    "air_flow_rate": 200.0,
                    "test_letter": "B",
                    "capacity": 6.0,
                    "cop": 3.0,
                    "design_flow_temp": 35,
                    "temp_outlet": 34,
                    "temp_source": 20,
                    "temp_test": 2,
                    "eahp_mixed_ext_air_ratio": 0.75,
                }
            ),
        ]
        data_eahp_interpolated = [
            {
                "test_letter": "A",
                "capacity": 5.4,
                "cop": 2.2,
                "design_flow_temp": 55,
                "temp_outlet": 55,
                "temp_source": 20,
                "temp_test": -7,
                "eahp_mixed_ext_air_ratio": 0.45,
            },
            {
                "test_letter": "B",
                "capacity": 5.7,
                "cop": 2.64,
                "design_flow_temp": 35,
                "temp_outlet": 34,
                "temp_source": 20,
                "temp_test": 2,
                "eahp_mixed_ext_air_ratio": 0.45,
            },
        ]
        source_type = SourceType("ExhaustAirMixed")
        lowest_air_flow_rate_in_test_data, data_eahp_func_result = (
            interpolate_exhaust_air_heat_pump_test_data(
                throughput_exhaust_air=140.0, hp_test_data=data_eahp, source_type=source_type
            )
        )

        self.assertEqual(
            lowest_air_flow_rate_in_test_data,
            100.0,
            "incorrect lowest air flow rate identified",
        )

        self.maxDiff = None
        self.assertEqual(
            data_eahp_func_result,
            data_eahp_interpolated,
            "incorrect interpolation of exhaust air heat pump test data",
        )

        # Test for warning when different test points provided for different air flow rates
        with self.assertLogs("hem_core.heating_systems.heat_pump", "WARNING") as cm:
            data_eahp[1]["temp_source"] = 21
            interpolate_exhaust_air_heat_pump_test_data(
                throughput_exhaust_air=140.0, hp_test_data=data_eahp, source_type=source_type
            )
            self.assertEqual(
                cm.output,
                [
                    "WARNING:hem_core.heating_systems.heat_pump:Different test points have been provided for different air flow rates"
                ],
            )

    def test_interpolate_exhaust_air_heat_pump_test_data_error(self):
        source_type = SourceType("ExhaustAirMixed")
        with self.assertRaises(ValueError):
            _, _ = interpolate_exhaust_air_heat_pump_test_data(
                throughput_exhaust_air=140.0, hp_test_data=[], source_type=source_type
            )


# Before defining the code to run the tests, we define the data to be parsed
# and the sorted/processed data structure it should be transformed into. Note
# that the data for design flow temp of 55 has an extra record (test letter F2)
# to test that the code can handle more than 2 records with the same temp_test
# value properly. This probably won't occur in practice.
data_unsorted: list[HeatPumpData] = [
    {
        "test_letter": "A",
        "capacity": 8.4,
        "cop": 4.6,
        "design_flow_temp": 35,
        "temp_outlet": 34,
        "temp_source": 0,
        "temp_test": -7,
    },
    {
        "test_letter": "B",
        "capacity": 8.3,
        "cop": 4.9,
        "design_flow_temp": 35,
        "temp_outlet": 30,
        "temp_source": 0,
        "temp_test": 2,
    },
    {
        "test_letter": "C",
        "capacity": 8.3,
        "cop": 5.1,
        "design_flow_temp": 35,
        "temp_outlet": 27,
        "temp_source": 0,
        "temp_test": 7,
    },
    {
        "test_letter": "D",
        "capacity": 8.2,
        "cop": 5.4,
        "design_flow_temp": 35,
        "temp_outlet": 24,
        "temp_source": 0,
        "temp_test": 12,
    },
    {
        "test_letter": "F",
        "capacity": 8.4,
        "cop": 4.6,
        "design_flow_temp": 35,
        "temp_outlet": 34,
        "temp_source": 0,
        "temp_test": -7,
    },
    {
        "test_letter": "A",
        "capacity": 8.8,
        "cop": 3.2,
        "design_flow_temp": 55,
        "temp_outlet": 52,
        "temp_source": 0,
        "temp_test": -7,
    },
    {
        "test_letter": "B",
        "capacity": 8.6,
        "cop": 3.6,
        "design_flow_temp": 55,
        "temp_outlet": 42,
        "temp_source": 0,
        "temp_test": 2,
    },
    {
        "test_letter": "C",
        "capacity": 8.5,
        "cop": 3.9,
        "design_flow_temp": 55,
        "temp_outlet": 36,
        "temp_source": 0,
        "temp_test": 7,
    },
    {
        "test_letter": "D",
        "capacity": 8.5,
        "cop": 4.3,
        "design_flow_temp": 55,
        "temp_outlet": 30,
        "temp_source": 0,
        "temp_test": 12,
    },
    {
        "test_letter": "F",
        "capacity": 8.8,
        "cop": 3.2,
        "design_flow_temp": 55,
        "temp_outlet": 52,
        "temp_source": 0,
        "temp_test": -7,
    },
    {
        "test_letter": "F2",
        "capacity": 8.8,
        "cop": 3.2,
        "design_flow_temp": 55,
        "temp_outlet": 52,
        "temp_source": 0,
        "temp_test": -7,
    },
]
data_sorted = {
    35: [
        {
            "test_letter": "A",
            "capacity": 8.4,
            "carnot_cop": 9.033823529411764,
            "cop": 4.6,
            "design_flow_temp": 35,
            "exergetic_eff": 0.5091974605241738,
            "temp_outlet": 34,
            "temp_source": 0,
            "temp_test": -7,
            "theoretical_load_ratio": 1.0,
        },
        {
            "test_letter": "F",
            "capacity": 8.4,
            "carnot_cop": 9.033823529438331,
            "cop": 4.6,
            "design_flow_temp": 35,
            "exergetic_eff": 0.5091974605226763,
            "temp_outlet": 34,
            "temp_source": 0.0000000001,
            "temp_test": -6.9999999999,
            "theoretical_load_ratio": 1.0000000000040385,
        },
        {
            "test_letter": "B",
            "capacity": 8.3,
            "carnot_cop": 10.104999999999999,
            "cop": 4.9,
            "design_flow_temp": 35,
            "exergetic_eff": 0.48490846115784275,
            "temp_outlet": 30,
            "temp_source": 0,
            "temp_test": 2,
            "theoretical_load_ratio": 1.1634388356892613,
        },
        {
            "test_letter": "C",
            "capacity": 8.3,
            "carnot_cop": 11.116666666666665,
            "cop": 5.1,
            "design_flow_temp": 35,
            "exergetic_eff": 0.4587706146926537,
            "temp_outlet": 27,
            "temp_source": 0,
            "temp_test": 7,
            "theoretical_load_ratio": 1.3186802349509577,
        },
        {
            "test_letter": "D",
            "capacity": 8.2,
            "carnot_cop": 12.38125,
            "cop": 5.4,
            "design_flow_temp": 35,
            "exergetic_eff": 0.43614336193841496,
            "temp_outlet": 24,
            "temp_source": 0,
            "temp_test": 12,
            "theoretical_load_ratio": 1.513621351820552,
        },
    ],
    55: [
        {
            "test_letter": "A",
            "capacity": 8.8,
            "carnot_cop": 6.252884615384615,
            "cop": 3.2,
            "design_flow_temp": 55,
            "exergetic_eff": 0.5117638013224666,
            "temp_outlet": 52,
            "temp_source": 0,
            "temp_test": -7,
            "theoretical_load_ratio": 1.0,
        },
        {
            "test_letter": "F",
            "capacity": 8.8,
            "carnot_cop": 6.252884615396638,
            "cop": 3.2,
            "design_flow_temp": 55,
            "exergetic_eff": 0.5117638013214826,
            "temp_outlet": 52,
            "temp_source": 0.0000000001,
            "temp_test": -6.9999999999,
            "theoretical_load_ratio": 1.0000000000030207,
        },
        {
            "test_letter": "F2",
            "capacity": 8.8,
            "carnot_cop": 6.252884615408662,
            "cop": 3.2,
            "design_flow_temp": 55,
            "exergetic_eff": 0.5117638013204985,
            "temp_outlet": 52,
            "temp_source": 0.0000000002,
            "temp_test": -6.9999999998,
            "theoretical_load_ratio": 1.0000000000060418,
        },
        {
            "test_letter": "B",
            "capacity": 8.6,
            "carnot_cop": 7.503571428571428,
            "cop": 3.6,
            "design_flow_temp": 55,
            "exergetic_eff": 0.4797715373631604,
            "temp_outlet": 42,
            "temp_source": 0,
            "temp_test": 2,
            "theoretical_load_ratio": 1.3179136223360988,
        },
        {
            "test_letter": "C",
            "capacity": 8.5,
            "carnot_cop": 8.587499999999999,
            "cop": 3.9,
            "design_flow_temp": 55,
            "exergetic_eff": 0.4541484716157206,
            "temp_outlet": 36,
            "temp_source": 0,
            "temp_test": 7,
            "theoretical_load_ratio": 1.5978273764295179,
        },
        {
            "test_letter": "D",
            "capacity": 8.5,
            "carnot_cop": 10.104999999999999,
            "cop": 4.3,
            "design_flow_temp": 55,
            "exergetic_eff": 0.4255319148936171,
            "temp_outlet": 30,
            "temp_source": 0,
            "temp_test": 12,
            "theoretical_load_ratio": 1.9940427298329144,
        },
    ],
}


class TestHeatPumpTestData(unittest.TestCase):
    """Unit tests for HeatPumpTestData class"""

    # TODO Test handling of case where test data for only 1 design flow temp has been provided

    def setUp(self):
        """Create HeatPumpTestData object to be tested"""
        self.hp_testdata = HeatPumpTestData(hp_test_data=data_unsorted)
        self.design_flow_temp_op_cond = 45.0
        self.design_flow_temp_op_cond_K = self.design_flow_temp_op_cond + 273.15

    def test_init(self):
        """Test that internal data structures have been populated correctly.

        This includes parsing and sorting the test data records, and producing
        sorted list of the design flow temperatures for which the data records
        apply.
        """
        self.maxDiff = None
        self.assertEqual(
            self.hp_testdata.design_flow_temperatures,
            [35, 55],
            "list of design flow temps populated incorrectly",
        )
        self.assertEqual(
            self.hp_testdata.test_data,
            data_sorted,
            "list of test data records populated incorrectly",
        )

    def test_init_no_temps(self):
        """Test that init throws if there is no data"""
        with self.assertRaises(ValueError):
            HeatPumpTestData([])

    def test_init_expected_five_letters(self):
        """Test that init throws if there aren't 5 records for each design flow temperature"""
        data: list[HeatPumpData] = [
            {
                "test_letter": "A",
                "capacity": 8.4,
                "cop": 4.6,
                "design_flow_temp": 35,
                "temp_outlet": 34,
                "temp_source": 0,
                "temp_test": -7,
            },
            {
                "test_letter": "B",
                "capacity": 8.3,
                "cop": 4.9,
                "design_flow_temp": 35,
                "temp_outlet": 30,
                "temp_source": 0,
                "temp_test": 2,
            },
            {
                "test_letter": "C",
                "capacity": 8.3,
                "cop": 5.1,
                "design_flow_temp": 35,
                "temp_outlet": 27,
                "temp_source": 0,
                "temp_test": 7,
            },
            {
                "test_letter": "D",
                "capacity": 8.2,
                "cop": 5.4,
                "design_flow_temp": 35,
                "temp_outlet": 24,
                "temp_source": 0,
                "temp_test": 12,
            },
            {
                "test_letter": "F",
                "capacity": 8.4,
                "cop": 4.6,
                "design_flow_temp": 35,
                "temp_outlet": 34,
                "temp_source": 0,
                "temp_test": -7,
            },
            {
                "test_letter": "A",
                "capacity": 8.8,
                "cop": 3.2,
                "design_flow_temp": 55,
                "temp_outlet": 52,
                "temp_source": 0,
                "temp_test": -7,
            },
            {
                "test_letter": "B",
                "capacity": 8.6,
                "cop": 3.6,
                "design_flow_temp": 55,
                "temp_outlet": 42,
                "temp_source": 0,
                "temp_test": 2,
            },
            {
                "test_letter": "C",
                "capacity": 8.5,
                "cop": 3.9,
                "design_flow_temp": 55,
                "temp_outlet": 36,
                "temp_source": 0,
                "temp_test": 7,
            },
            {
                "test_letter": "D",
                "capacity": 8.5,
                "cop": 4.3,
                "design_flow_temp": 55,
                "temp_outlet": 30,
                "temp_source": 0,
                "temp_test": 12,
            },
        ]

        with self.assertRaises(ValueError):
            HeatPumpTestData(hp_test_data=data)

    def test_init_maximum_design_flow(self):
        """Test that init prints a warning with more than 4 design flow temperatures"""
        data: list[HeatPumpData] = [
            {
                "test_letter": "A",
                "capacity": 8.4,
                "cop": 4.6,
                "design_flow_temp": 35,
                "temp_outlet": 34,
                "temp_source": 0,
                "temp_test": -7,
            },
            {
                "test_letter": "B",
                "capacity": 8.3,
                "cop": 4.9,
                "design_flow_temp": 35,
                "temp_outlet": 30,
                "temp_source": 0,
                "temp_test": 2,
            },
            {
                "test_letter": "C",
                "capacity": 8.3,
                "cop": 5.1,
                "design_flow_temp": 35,
                "temp_outlet": 27,
                "temp_source": 0,
                "temp_test": 7,
            },
            {
                "test_letter": "D",
                "capacity": 8.2,
                "cop": 5.4,
                "design_flow_temp": 35,
                "temp_outlet": 24,
                "temp_source": 0,
                "temp_test": 12,
            },
            {
                "test_letter": "F",
                "capacity": 8.4,
                "cop": 4.6,
                "design_flow_temp": 35,
                "temp_outlet": 34,
                "temp_source": 0,
                "temp_test": -7,
            },
            {
                "test_letter": "A",
                "capacity": 8.4,
                "cop": 4.6,
                "design_flow_temp": 45,
                "temp_outlet": 34,
                "temp_source": 0,
                "temp_test": -7,
            },
            {
                "test_letter": "B",
                "capacity": 8.3,
                "cop": 4.9,
                "design_flow_temp": 45,
                "temp_outlet": 30,
                "temp_source": 0,
                "temp_test": 2,
            },
            {
                "test_letter": "C",
                "capacity": 8.3,
                "cop": 5.1,
                "design_flow_temp": 45,
                "temp_outlet": 27,
                "temp_source": 0,
                "temp_test": 7,
            },
            {
                "test_letter": "D",
                "capacity": 8.2,
                "cop": 5.4,
                "design_flow_temp": 45,
                "temp_outlet": 24,
                "temp_source": 0,
                "temp_test": 12,
            },
            {
                "test_letter": "F",
                "capacity": 8.4,
                "cop": 4.6,
                "design_flow_temp": 45,
                "temp_outlet": 34,
                "temp_source": 0,
                "temp_test": -7,
            },
            {
                "test_letter": "A",
                "capacity": 8.4,
                "cop": 4.6,
                "design_flow_temp": 55,
                "temp_outlet": 34,
                "temp_source": 0,
                "temp_test": -7,
            },
            {
                "test_letter": "B",
                "capacity": 8.3,
                "cop": 4.9,
                "design_flow_temp": 55,
                "temp_outlet": 30,
                "temp_source": 0,
                "temp_test": 2,
            },
            {
                "test_letter": "C",
                "capacity": 8.3,
                "cop": 5.1,
                "design_flow_temp": 55,
                "temp_outlet": 27,
                "temp_source": 0,
                "temp_test": 7,
            },
            {
                "test_letter": "D",
                "capacity": 8.2,
                "cop": 5.4,
                "design_flow_temp": 55,
                "temp_outlet": 24,
                "temp_source": 0,
                "temp_test": 12,
            },
            {
                "test_letter": "F",
                "capacity": 8.4,
                "cop": 4.6,
                "design_flow_temp": 55,
                "temp_outlet": 34,
                "temp_source": 0,
                "temp_test": -7,
            },
            {
                "test_letter": "A",
                "capacity": 8.4,
                "cop": 4.6,
                "design_flow_temp": 20,
                "temp_outlet": 34,
                "temp_source": 0,
                "temp_test": -7,
            },
            {
                "test_letter": "B",
                "capacity": 8.3,
                "cop": 4.9,
                "design_flow_temp": 20,
                "temp_outlet": 30,
                "temp_source": 0,
                "temp_test": 2,
            },
            {
                "test_letter": "C",
                "capacity": 8.3,
                "cop": 5.1,
                "design_flow_temp": 20,
                "temp_outlet": 27,
                "temp_source": 0,
                "temp_test": 7,
            },
            {
                "test_letter": "D",
                "capacity": 8.2,
                "cop": 5.4,
                "design_flow_temp": 20,
                "temp_outlet": 24,
                "temp_source": 0,
                "temp_test": 12,
            },
            {
                "test_letter": "F",
                "capacity": 8.4,
                "cop": 4.6,
                "design_flow_temp": 20,
                "temp_outlet": 34,
                "temp_source": 0,
                "temp_test": -7,
            },
            {
                "test_letter": "A",
                "capacity": 8.4,
                "cop": 4.6,
                "design_flow_temp": 65,
                "temp_outlet": 34,
                "temp_source": 0,
                "temp_test": -7,
            },
            {
                "test_letter": "B",
                "capacity": 8.3,
                "cop": 4.9,
                "design_flow_temp": 65,
                "temp_outlet": 30,
                "temp_source": 0,
                "temp_test": 2,
            },
            {
                "test_letter": "C",
                "capacity": 8.3,
                "cop": 5.1,
                "design_flow_temp": 65,
                "temp_outlet": 27,
                "temp_source": 0,
                "temp_test": 7,
            },
            {
                "test_letter": "D",
                "capacity": 8.2,
                "cop": 5.4,
                "design_flow_temp": 65,
                "temp_outlet": 24,
                "temp_source": 0,
                "temp_test": 12,
            },
            {
                "test_letter": "F",
                "capacity": 8.4,
                "cop": 4.6,
                "design_flow_temp": 65,
                "temp_outlet": 34,
                "temp_source": 0,
                "temp_test": -7,
            },
        ]

        with self.assertLogs("hem_core.heating_systems.heat_pump", "WARNING") as cm:
            HeatPumpTestData(hp_test_data=data)
            self.assertEqual(
                cm.output,
                [
                    "WARNING:hem_core.heating_systems.heat_pump:Test data for a maximum of 4 design flow temperatures is expected. 5 have been provided."
                ],
            )

    def test_init_expected_letter(self):
        """Test that init throws when test letter F missing"""
        data: list[HeatPumpData] = [
            {
                "test_letter": "A",
                "capacity": 8.4,
                "cop": 4.6,
                "design_flow_temp": 35,
                "temp_outlet": 34,
                "temp_source": 0,
                "temp_test": -7,
            },
            {
                "test_letter": "B",
                "capacity": 8.3,
                "cop": 4.9,
                "design_flow_temp": 35,
                "temp_outlet": 30,
                "temp_source": 0,
                "temp_test": 2,
            },
            {
                "test_letter": "C",
                "capacity": 8.3,
                "cop": 5.1,
                "design_flow_temp": 35,
                "temp_outlet": 27,
                "temp_source": 0,
                "temp_test": 7,
            },
            {
                "test_letter": "D",
                "capacity": 8.2,
                "cop": 5.4,
                "design_flow_temp": 35,
                "temp_outlet": 24,
                "temp_source": 0,
                "temp_test": 12,
            },
            {
                "test_letter": "F",
                "capacity": 8.4,
                "cop": 4.6,
                "design_flow_temp": 35,
                "temp_outlet": 34,
                "temp_source": 0,
                "temp_test": -7,
            },
            {
                "test_letter": "A",
                "capacity": 8.8,
                "cop": 3.2,
                "design_flow_temp": 55,
                "temp_outlet": 52,
                "temp_source": 0,
                "temp_test": -7,
            },
            {
                "test_letter": "B",
                "capacity": 8.6,
                "cop": 3.6,
                "design_flow_temp": 55,
                "temp_outlet": 42,
                "temp_source": 0,
                "temp_test": 2,
            },
            {
                "test_letter": "C",
                "capacity": 8.5,
                "cop": 3.9,
                "design_flow_temp": 55,
                "temp_outlet": 36,
                "temp_source": 0,
                "temp_test": 7,
            },
            {
                "test_letter": "D",
                "capacity": 8.5,
                "cop": 4.3,
                "design_flow_temp": 55,
                "temp_outlet": 30,
                "temp_source": 0,
                "temp_test": 12,
            },
            {
                "test_letter": "E",
                "capacity": 8.5,
                "cop": 4.3,
                "design_flow_temp": 55,
                "temp_outlet": 30,
                "temp_source": 0,
                "temp_test": 12,
            },
        ]

        with self.assertRaises(ValueError):
            HeatPumpTestData(hp_test_data=data)

    def test_init_four_distinct_records(self):
        """Test that init throws if there aren't four distinct records for each design flow temperature"""
        data: list[HeatPumpData] = [
            {
                "test_letter": "A",
                "capacity": 8.4,
                "cop": 4.6,
                "design_flow_temp": 35,
                "temp_outlet": 34,
                "temp_source": 0,
                "temp_test": 1,
            },
            {
                "test_letter": "B",
                "capacity": 8.3,
                "cop": 4.9,
                "design_flow_temp": 35,
                "temp_outlet": 30,
                "temp_source": 0,
                "temp_test": 1,
            },
            {
                "test_letter": "C",
                "capacity": 8.3,
                "cop": 5.1,
                "design_flow_temp": 35,
                "temp_outlet": 27,
                "temp_source": 0,
                "temp_test": 1,
            },
            {
                "test_letter": "D",
                "capacity": 8.2,
                "cop": 5.4,
                "design_flow_temp": 35,
                "temp_outlet": 24,
                "temp_source": 0,
                "temp_test": 1,
            },
            {
                "test_letter": "F",
                "capacity": 8.4,
                "cop": 4.6,
                "design_flow_temp": 35,
                "temp_outlet": 34,
                "temp_source": 0,
                "temp_test": 1,
            },
        ]

        with self.assertRaises(ValueError):
            HeatPumpTestData(hp_test_data=data)

    def test_init_regression_coeffs(self):
        """Test that regression coefficients have been populated correctly"""
        results_expected = {
            35: [4.810017281274474, 0.03677543129969712, 0.0009914765238219557],
            55: [3.4857982546529747, 0.050636568790103545, 0.0014104955583514216],
        }
        for flow_temp, reg_coeffs in self.hp_testdata.regression_coefficients.items():
            for i, coeff in enumerate(reg_coeffs):
                with self.subTest(msg="flow temp = " + str(flow_temp) + ", i = " + str(i)):
                    self.assertAlmostEqual(
                        coeff,
                        results_expected[flow_temp][i],
                        msg="list of regression coefficients populated incorrectly",
                    )

    def test_average_capacity(self):
        """Test that correct average capacity is returned for the flow temp"""
        results = [8.3, 8.375, 8.45, 8.525, 8.6]

        for i, flow_temp in enumerate([35, 40, 45, 50, 55]):
            with self.subTest(i=i):
                self.assertAlmostEqual(
                    self.hp_testdata.average_capacity(
                        design_flow_temp_op_cond=Celcius2Kelvin(temp_C=flow_temp)
                    ),
                    results[i],
                    msg="incorrect average capacity returned",
                )

    def test_temp_spread_test_conditions(self):
        """Test that correct temp spread at test conditions is returned for the flow temp"""
        results = [5.0, 5.75, 6.5, 7.25, 8.0]

        for i, flow_temp in enumerate([35, 40, 45, 50, 55]):
            with self.subTest(i=i):
                self.assertEqual(
                    self.hp_testdata.temp_spread_test_conditions(
                        design_flow_temp_op_cond=Celcius2Kelvin(temp_C=flow_temp)
                    ),
                    results[i],
                    msg="incorrect temp spread at test conditions returned",
                )

    def test_find_test_record_index(self):
        with self.assertRaises(ValueError):
            self.hp_testdata._HeatPumpTestData__find_test_record_index(  # type: ignore[AttributeAccessIssue]
                test_condition="x", design_flow_temp=55
            )

    def test_carnot_cop_at_test_condition(self):
        """Test that correct Carnot CoP is returned for the flow temp and test condition"""
        # TODO Test conditions other than just coldest
        i = -1
        for flow_temp, test_condition, result in [
            [35, "cld", 9.033823529411764],
            [40, "cld", 8.338588800904978],
            [45, "cld", 7.643354072398189],
            [50, "cld", 6.948119343891403],
            [55, "cld", 6.252884615384615],
            [45, "A", 7.643354072398189],
            [45, "B", 8.804285714285713],
            [45, "C", 9.852083333333333],
            [45, "D", 11.243125],
            [45, "F", 7.643354072417485],
        ]:
            # TODO Note that the result above for condition F is different to
            #      that for condition A, despite the source and outlet temps in
            #      the inputs being the same for both, because of the adjustment
            #      to the source temp applied in the HeatPumpTestData __init__
            #      function when duplicate records are found. This may not be
            #      the desired behaviour (see the TODO comment in that function)
            #      but in that case the problem is not with the function that
            #      is being tested here, so for now we set the result so that
            #      the test passes.
            i += 1
            flow_temp = Celcius2Kelvin(temp_C=flow_temp)
            with self.subTest(i=i):
                self.assertEqual(
                    self.hp_testdata.carnot_cop_at_test_condition(
                        test_condition=test_condition, design_flow_temp_op_cond=flow_temp
                    ),
                    result,
                    "incorrect Carnot CoP at condition " + test_condition + " returned",
                )

    def test_outlet_temp_at_test_condition(self):
        """Test that correct outlet temp is returned for the flow temp and test condition"""
        # TODO Test conditions other than just coldest
        i = -1
        for flow_temp, test_condition, result in [
            [35, "cld", 307.15],
            [40, "cld", 311.65],
            [45, "cld", 316.15],
            [50, "cld", 320.65],
            [55, "cld", 325.15],
            [45, "A", 316.15],
            [45, "B", 309.15],
            [45, "C", 304.65],
            [45, "D", 300.15],
            [45, "F", 316.15],
        ]:
            i += 1
            flow_temp = Celcius2Kelvin(temp_C=flow_temp)
            with self.subTest(i=i):
                self.assertEqual(
                    self.hp_testdata.outlet_temp_at_test_condition(
                        test_condition=test_condition, design_flow_temp_op_cond=flow_temp
                    ),
                    result,
                    "incorrect outlet temp at condition " + test_condition + " returned",
                )

    def test_source_temp_at_test_condition(self):
        """Test that correct source temp is returned for the flow temp and test condition"""
        # TODO Test conditions other than just coldest
        i = -1
        for flow_temp, test_condition, result in [
            [35, "cld", 273.15],
            [40, "cld", 273.15],
            [45, "cld", 273.15],
            [50, "cld", 273.15],
            [55, "cld", 273.15],
            [45, "A", 273.15],
            [45, "B", 273.15],
            [45, "C", 273.15],
            [45, "D", 273.15],
            [45, "F", 273.15000000009996],
        ]:
            # TODO Note that the result above for condition F is different to
            #      that for condition A, despite the source and outlet temps in
            #      the inputs being the same for both, because of the adjustment
            #      to the source temp applied in the HeatPumpTestData __init__
            #      function when duplicate records are found. This may not be
            #      the desired behaviour (see the TODO comment in that function)
            #      but in that case the problem is not with the function that
            #      is being tested here, so for now we set the result so that
            #      the test passes.
            i += 1
            flow_temp = Celcius2Kelvin(flow_temp)
            with self.subTest(i=i):
                self.assertEqual(
                    self.hp_testdata.source_temp_at_test_condition(
                        test_condition=test_condition, design_flow_temp_op_cond=flow_temp
                    ),
                    result,
                    "incorrect source temp at condition " + test_condition + " returned",
                )

    def test_capacity_at_test_condition(self):
        """Test that correct capacity is returned for the flow temp and test condition"""
        i = -1
        for flow_temp, test_condition, result in [
            [35, "cld", 8.4],
            [40, "cld", 8.5],
            [45, "cld", 8.6],
            [50, "cld", 8.7],
            [55, "cld", 8.8],
            [45, "A", 8.6],
            [45, "B", 8.45],
            [45, "C", 8.4],
            [45, "D", 8.35],
            [45, "F", 8.6],
        ]:
            i += 1
            flow_temp = Celcius2Kelvin(temp_C=flow_temp)
            with self.subTest(i=i):
                self.assertAlmostEqual(
                    self.hp_testdata.capacity_at_test_condition(
                        test_condition=test_condition, design_flow_temp_op_cond=flow_temp
                    ),
                    result,
                    msg="incorrect capacity at condition " + test_condition + " returned",
                )

    def test_lr_op_cond(self):
        """Test that correct load ratio at operating conditions is returned"""
        i = -1
        for flow_temp, temp_source, carnot_cop_op_cond, result in [
            [35.0, 283.15, 12.326, 2.579601322115558],
            [40.0, 293.15, 15.6575, 3.464991021429274],
            [45.0, 278.15, 7.95375, 1.4337736417538745],
            [50.0, 288.15, 9.23285714285714, 1.765821306168971],
            [55.0, 273.15, 5.96636363636364, 0.9282465711109492],
        ]:
            i += 1
            flow_temp = Celcius2Kelvin(temp_C=flow_temp)
            with self.subTest(i=i):
                self.assertAlmostEqual(
                    self.hp_testdata._HeatPumpTestData__lr_op_cond(  # type: ignore[AttributeAccessIssue]
                        temp_output=flow_temp,
                        temp_source=temp_source,
                        carnot_cop_op_cond=carnot_cop_op_cond,
                        design_flow_temp=self.design_flow_temp_op_cond_K,
                    ),
                    result,
                    msg="incorrect load ratio at operating conditions returned",
                )

    def test_lr_eff_either_side_of_op_cond(self):
        """Test that correct test results either side of operating conditions are returned"""
        results_lr_below = [
            1.1634388356892613,
            1.0000000000060418,
            1.3186802349509577,
            1.3179136223360988,
            1.3186802349509577,
            1.5978273764295179,
        ]
        results_lr_above = [
            1.3186802349509577,
            1.3179136223360988,
            1.513621351820552,
            1.5978273764295179,
            1.513621351820552,
            1.9940427298329144,
        ]
        results_eff_below = [
            0.48490846115784275,
            0.5117638013204985,
            0.4587706146926537,
            0.4797715373631604,
            0.4587706146926537,
            0.4541484716157206,
        ]
        results_eff_above = [
            0.4587706146926537,
            0.4797715373631604,
            0.43614336193841496,
            0.4541484716157206,
            0.43614336193841496,
            0.4255319148936171,
        ]

        i = -1
        for exergy_lr_op_cond in [1.2, 1.4, 1.6]:
            for flow_temp in [35, 55]:
                i += 1
                with self.subTest(i=i):
                    lr_below, lr_above, eff_below, eff_above = (
                        self.hp_testdata._HeatPumpTestData__lr_eff_either_side_of_op_cond(  # type: ignore[AttributeAccessIssue]
                            design_flow_temp=flow_temp,
                            exergy_lr_op_cond=exergy_lr_op_cond,
                        )
                    )
                    self.assertEqual(
                        lr_below,
                        results_lr_below[i],
                        "incorrect load ratio below operating conditions returned",
                    )
                    self.assertEqual(
                        lr_above,
                        results_lr_above[i],
                        "incorrect load ratio above operating conditions returned",
                    )
                    self.assertEqual(
                        eff_below,
                        results_eff_below[i],
                        "incorrect efficiency below operating conditions returned",
                    )
                    self.assertEqual(
                        eff_above,
                        results_eff_above[i],
                        "incorrect efficiency above operating conditions returned",
                    )

        # first load ratio in the test data cannot be greater than the load ratio at operating conditions
        self.hp_testdata = HeatPumpTestData(hp_test_data=data_unsorted)
        self.assertAlmostEqual(
            self.hp_testdata._HeatPumpTestData__lr_eff_either_side_of_op_cond(  # type: ignore[AttributeAccessIssue]
                design_flow_temp=55.0,
                exergy_lr_op_cond=0.9,
            ),
            (1.0, 1.0000000000030207, 0.5117638013224666, 0.5117638013214826),
        )

    def test_cop_op_cond_if_not_air_source(self):
        """Test that correct CoP at operating conditions (not air source) is returned"""
        results = [
            6.717150897917277,
            8.121968575142535,
            4.60977003063163,
            5.748091483057522,
            3.579953030724001,
        ]

        i = -1
        for temp_diff_limit_low, temp_ext, temp_source, temp_output in [
            [8.0, 0.00, 283.15, 308.15],
            [7.0, -5.0, 293.15, 313.15],
            [6.0, 5.00, 278.15, 318.15],
            [5.0, 10.0, 288.15, 323.15],
            [4.0, 7.50, 273.15, 328.15],
        ]:
            i += 1
            with self.subTest(i=i):
                self.assertAlmostEqual(
                    self.hp_testdata.cop_op_cond_if_not_air_source(
                        temp_diff_limit_low=temp_diff_limit_low,
                        temp_ext_C=temp_ext,
                        temp_source=temp_source,
                        temp_output=temp_output,
                        design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,
                    ),
                    results[i],
                    msg="incorrect CoP at operating conditions (not air source) returned",
                )

    def test_capacity_op_cond_var_flow_or_source_temp(self):
        """Test that correct capacity at operating conditions is returned"""
        results = [
            10.390871958470573,
            8.241818181818182,
            8.95014809894768,
            9.495814072084585,
            8.830454545454547,
        ]

        i = -1
        for mod_ctrl, temp_source, temp_output in [
            [True, 283.15, 308.15],
            [False, 293.15, 313.15],
            [True, 278.15, 318.15],
            [True, 288.15, 323.15],
            [False, 273.15, 328.15],
        ]:
            i += 1
            with self.subTest(i=i):
                self.assertAlmostEqual(
                    self.hp_testdata.capacity_op_cond_var_flow_or_source_temp(
                        temp_output=temp_output,
                        temp_source=temp_source,
                        mod_ctrl=mod_ctrl,
                        design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,
                    ),
                    results[i],
                    msg="incorrect capacity at operating conditions returned",
                )

    def test_temp_spread_correction(self):
        """Test that correct temperature spread correction factor is returned"""
        results = [
            1.0872913992297817,
            1.0698529411764706,
            1.05822498586772,
            1.0499171499585749,
            1.043684710351377,
        ]
        temp_source = 275.15
        temp_diff_evaporator = -15.0
        temp_diff_condenser = 5.0
        temp_spread_emitter = 10.0

        for i, temp_output in enumerate([308.15, 313.15, 318.15, 323.15, 328.15]):
            with self.subTest(i=i):
                self.assertAlmostEqual(
                    self.hp_testdata.temp_spread_correction(
                        temp_source=temp_source,
                        temp_output=temp_output,
                        temp_diff_evaporator=temp_diff_evaporator,
                        temp_diff_condenser=temp_diff_condenser,
                        temp_spread_emitter=temp_spread_emitter,
                        design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,
                    ),
                    results[i],
                    msg="incorrect temperature spread correction factor returned",
                )


class TestHeatPumpService(unittest.TestCase):
    """Unit tests for HeatPumpService"""

    def setUp(self):
        simtime = SimulationTime(start_time=0, end_time=1, step=1)

        self.heat_pump = MagicMock()
        self.service_name = "new_service"
        self.control_on = OnOffTimeControl(
            schedule=[True], simulation_time=simtime, start_day=0, time_series_step=1
        )
        self.control_off = OnOffTimeControl(
            schedule=[False], simulation_time=simtime, start_day=0, time_series_step=1
        )

    def test_is_on(self):
        """Test that is_on returns the correct values"""
        self.assertTrue(
            HeatPumpService(
                heat_pump=self.heat_pump, service_name=self.service_name, control=self.control_on
            ).is_on()
        )
        self.assertTrue(
            HeatPumpService(
                heat_pump=self.heat_pump, service_name=self.service_name, control=None
            ).is_on()
        )
        self.assertFalse(
            HeatPumpService(
                heat_pump=self.heat_pump, service_name=self.service_name, control=self.control_off
            ).is_on()
        )


class TestHeatPumpServiceWater(unittest.TestCase):
    """Unit tests for HeatPumpServiceWater"""

    def setUp(self):
        simtime = SimulationTime(start_time=0, end_time=1, step=1)

        self.heat_pump = MagicMock()
        self.service_name = "new_service"
        self.control_min = SetpointTimeControl(
            schedule=[10], simulation_time=simtime, start_day=0, time_series_step=1
        )
        self.control_max = SetpointTimeControl(
            schedule=[20], simulation_time=simtime, start_day=0, time_series_step=1
        )
        self.cold_feed = MagicMock()

        self.heatPumpServiceWater = HeatPumpServiceWater(
            heat_pump=self.heat_pump,
            service_name=self.service_name,
            temp_limit_upper=30,
            cold_feed=self.cold_feed,
            controlmin=self.control_min,
            controlmax=self.control_max,
        )

    def test_setpnt(self):
        """Test that setpnt returns the control setpoints"""
        setpnt_min, setpnt_max = self.heatPumpServiceWater.setpnt()
        self.assertEqual(setpnt_min, 10)
        self.assertEqual(setpnt_max, 20)

    def test_setpnt_errors(self):
        simtime = SimulationTime(start_time=0, end_time=1, step=1)
        self.heatPumpServiceWater._HeatPumpServiceWater__controlmin = OnOffTimeControl(  # type: ignore[AttributeAccessIssue]
            schedule=[True], simulation_time=simtime, start_day=0, time_series_step=1
        )
        with self.assertRaises(TypeError):
            self.heatPumpServiceWater.setpnt()

        self.heatPumpServiceWater._HeatPumpServiceWater__controlmin = self.control_min  # type: ignore[AttributeAccessIssue]
        self.heatPumpServiceWater._HeatPumpServiceWater__controlmax = OnOffTimeControl(  # type: ignore[AttributeAccessIssue]
            schedule=[True], simulation_time=simtime, start_day=0, time_series_step=1
        )
        with self.assertRaises(TypeError):
            self.heatPumpServiceWater.setpnt()

    def test_energy_output_max(self):
        """Test that energy_output_max returns the correct values from the heat pump service"""
        self.heat_pump._HeatPump__energy_output_max.return_value = 5

        self.assertEqual(
            self.heatPumpServiceWater.energy_output_max(temp_flow=50, temp_return=40), 5
        )
        self.heat_pump._HeatPump__energy_output_max.assert_called_once_with(
            temp_output=323.15,
            temp_return_feed=313.15,
            design_flow_temp_op_cond=323.15,
            hybrid_boiler_service=None,
            service_type=HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
            service_name="new_service",
        )

    def test_energy_output_max_no_temp_return(self):
        """Test that energy_output_max returns 0 with no temp_return"""
        self.heat_pump._HeatPump__energy_output_max.return_value = 5

        self.assertEqual(
            self.heatPumpServiceWater.energy_output_max(temp_flow=50, temp_return=None), 0
        )

    def test_demand_energy(self):
        """Test that demand_energy returns the correct values from the heat pump service"""
        self.heat_pump._HeatPump__demand_energy.return_value = 5
        self.cold_feed.get_temp_cold_water.return_value = [(10, 10.0)]

        self.assertEqual(
            self.heatPumpServiceWater.demand_energy(energy_demand=5, temp_flow=50, temp_return=40),
            5,
        )

        self.heat_pump._HeatPump__demand_energy.assert_called_once_with(
            service_name="new_service",
            service_type=HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
            energy_output_required=5,
            temp_output=323.15,
            temp_return_feed=313.15,
            temp_limit_upper=303.15,
            design_flow_temp_op_cond=323.15,
            time_constant_for_service=1560,
            service_on=True,
            temp_used_for_scaling=283.15,
            hybrid_boiler_service=None,
        )

    def test_demand_energy_no_temp_return(self):
        """Test that demand_energy returns the correct values from the heat pump service with no temp_return"""
        self.heat_pump._HeatPump__demand_energy.return_value = 2
        self.cold_feed.draw_off_water.return_value = [(10, 10.0)]
        self.cold_feed.get_temp_cold_water.return_value = [(10, 10.0)]

        self.assertEqual(
            self.heatPumpServiceWater.demand_energy(
                energy_demand=5, temp_flow=50, temp_return=None
            ),
            2,
        )

        self.heat_pump._HeatPump__demand_energy.assert_called_once_with(
            service_name="new_service",
            service_type=HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
            energy_output_required=0.0,
            temp_output=323.15,
            temp_return_feed=None,
            temp_limit_upper=303.15,
            design_flow_temp_op_cond=323.15,
            time_constant_for_service=1560,
            service_on=True,
            temp_used_for_scaling=283.15,
            hybrid_boiler_service=None,
        )

    def test_demand_energy_no_temp_flow(self):
        """Test that demand_energy throws when temp_flow is None"""
        self.cold_feed.draw_off_water.return_value = [(10, 10.0)]

        with self.assertRaises(ValueError):
            self.heatPumpServiceWater.demand_energy(energy_demand=5, temp_flow=None, temp_return=30)


class TestHeatPumpServiceSpace(unittest.TestCase):
    """Unit tests for HeatPumpServiceSpace"""

    def setUp(self):
        self.simtime = SimulationTime(0, 2, 1)
        self.heat_pump = MagicMock()
        self.service_name = "new_service"
        self.control = SetpointTimeControl(
            schedule=[20, None], simulation_time=self.simtime, start_day=0, time_series_step=1
        )
        self.design_flow_temp_op_cond = 55.0
        self.design_flow_temp_op_cond_K = 55.0 + 273.15

        self.heatPumpServiceSpace = HeatPumpServiceSpace(
            heat_pump=self.heat_pump,
            service_name=self.service_name,
            emitter_type=HeatPumpEmitterType.RADIATORS_UFH,
            temp_limit_upper=50,
            temp_diff_emit_design=MagicMock(),
            design_flow_temp_op_cond=self.design_flow_temp_op_cond,
            control=self.control,
            volume_heated=100,
        )

    def test_setpnt(self):
        """Test that temp_setpnt returns the setpoint from the control"""
        self.assertEqual(self.heatPumpServiceSpace.temp_setpnt(), 20)

    def test_in_required_period(self):
        """Test that in_required_period returns the correct values based on the control"""
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.heatPumpServiceSpace.in_required_period(), [True, False][t_idx]
                )

    def test_control_errors(self):
        on_off_control = OnOffTimeControl(
            schedule=[True],
            simulation_time=SimulationTime(start_time=0, end_time=1, step=1),
            start_day=0,
            time_series_step=1,
        )
        with self.assertRaises(TypeError):
            HeatPumpServiceSpace(
                heat_pump=self.heat_pump,
                service_name=self.service_name,
                emitter_type=HeatPumpEmitterType.RADIATORS_UFH,
                temp_limit_upper=50,
                temp_diff_emit_design=MagicMock(),
                design_flow_temp_op_cond=self.design_flow_temp_op_cond,
                control=on_off_control,
                volume_heated=100,
            )

    def test_energy_output_max(self):
        """Test that energy_output_max returns the correct values from the heat pump service"""
        self.heat_pump._HeatPump__energy_output_max.return_value = 10

        self.assertEqual(
            self.heatPumpServiceSpace.energy_output_max(
                temp_output=50, temp_return_feed=40, time_start=0.1
            ),
            10,
        )

        self.heat_pump._HeatPump__energy_output_max.assert_called_with(
            temp_output=323.15,
            temp_return_feed=40,
            design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,
            hybrid_boiler_service=None,
            service_type=HeatingServiceType.SPACE,
            temp_spread_correction=ANY,
            time_start=0.1,
            emitters_data_for_buffer_tank=None,
            service_name="new_service",
        )

    def test_energy_output_max_off(self):
        """Test that energy_output_max returns 0 if the service if off"""
        self.control = SetpointTimeControl(
            schedule=[None, None], simulation_time=self.simtime, start_day=0, time_series_step=1
        )
        self.heatPumpServiceSpace = HeatPumpServiceSpace(
            heat_pump=self.heat_pump,
            service_name=self.service_name,
            emitter_type=HeatPumpEmitterType.RADIATORS_UFH,
            temp_limit_upper=50,
            temp_diff_emit_design=MagicMock(),
            design_flow_temp_op_cond=self.design_flow_temp_op_cond,
            control=self.control,
            volume_heated=100,
        )

        self.assertEqual(
            self.heatPumpServiceSpace.energy_output_max(temp_output=50, temp_return_feed=40), 0
        )

    def test_demand_energy(self):
        """Test that demand_energy returns the correct values"""
        self.heat_pump._HeatPump__sink_type = HeatPumpSinkType.WATER
        self.heat_pump._HeatPump__demand_energy.return_value = 10

        self.assertEqual(
            self.heatPumpServiceSpace.demand_energy(
                energy_demand=100, temp_flow=50, temp_return=40, time_start=0.2
            ),
            10,
        )

        self.heat_pump._HeatPump__demand_energy.assert_called_with(
            service_name="new_service",
            service_type=HeatingServiceType.SPACE,
            energy_output_required=100,
            temp_output=323.15,
            temp_return_feed=313.15,
            temp_limit_upper=323.15,
            design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,
            time_constant_for_service=1370,
            service_on=True,
            temp_spread_correction=ANY,
            time_start=0.2,
            hybrid_boiler_service=None,
            emitters_data_for_buffer_tank=None,
            update_heat_source_state=True,
        )

    def test_demand_energy_off(self):
        """Test that demand_energy passes 0 energy demand if the service is off"""
        self.heat_pump._HeatPump__sink_type = HeatPumpSinkType.WATER
        self.heat_pump._HeatPump__demand_energy.return_value = 0
        self.control = SetpointTimeControl(
            schedule=[None, None], simulation_time=self.simtime, start_day=0, time_series_step=1
        )
        self.heatPumpServiceSpace = HeatPumpServiceSpace(
            heat_pump=self.heat_pump,
            service_name=self.service_name,
            emitter_type=HeatPumpEmitterType.RADIATORS_UFH,
            temp_limit_upper=50,
            temp_diff_emit_design=MagicMock(),
            design_flow_temp_op_cond=self.design_flow_temp_op_cond,
            control=self.control,
            volume_heated=100,
        )

        self.assertEqual(
            self.heatPumpServiceSpace.demand_energy(
                energy_demand=100, temp_flow=50, temp_return=40
            ),
            0,
        )

    def test_running_time_throughput_factor(self):
        """Test that running_time_throughput_factor returns the correct values"""
        self.heat_pump._HeatPump__sink_type = HeatPumpSinkType.WATER
        self.heat_pump._HeatPump__running_time_throughput_factor.return_value = 10

        self.assertEqual(
            self.heatPumpServiceSpace.running_time_throughput_factor(
                space_heat_running_time_cumulative=5, energy_demand=10, temp_flow=50, temp_return=40
            ),
            10,
        )

        self.heat_pump._HeatPump__running_time_throughput_factor.assert_called_with(
            space_heat_running_time_cumulative=5,
            service_name="new_service",
            service_type=HeatingServiceType.SPACE,
            energy_output_required=10,
            temp_output=323.15,
            temp_return_feed=313.15,
            temp_limit_upper=323.15,
            design_flow_temp_op_cond=328.15,
            time_constant_for_service=1370,
            service_on=True,
            volume_heated_by_service=100,
            temp_spread_correction=ANY,
            time_start=0.0,
        )

    def test_running_time_throughput_factor_off(self):
        """Test that running_time_throughput_factor passes 0 energy demand if the service is off"""
        self.heat_pump._HeatPump__sink_type = HeatPumpSinkType.WATER
        self.heat_pump._HeatPump__running_time_throughput_factor.return_value = 10
        self.control = SetpointTimeControl(
            schedule=[None, None], simulation_time=self.simtime, start_day=0, time_series_step=1
        )
        self.heatPumpServiceSpace = HeatPumpServiceSpace(
            heat_pump=self.heat_pump,
            service_name=self.service_name,
            emitter_type=HeatPumpEmitterType.RADIATORS_UFH,
            temp_limit_upper=50,
            temp_diff_emit_design=MagicMock(),
            design_flow_temp_op_cond=self.design_flow_temp_op_cond,
            control=self.control,
            volume_heated=100,
        )

        self.assertEqual(
            self.heatPumpServiceSpace.running_time_throughput_factor(
                space_heat_running_time_cumulative=5, energy_demand=10, temp_flow=50, temp_return=40
            ),
            10,
        )

    def test_temp_spread_correction_air(self):
        """Test that temp_spread_correction returns the correct values with an air source"""
        self.heat_pump._HeatPump__source_type = SourceType.EXHAUST_AIR_MIXED
        self.heatPumpServiceSpace._HeatPumpService__hp._HeatPump__test_data.temp_spread_correction.return_value = 10  # type: ignore[AttributeAccessIssue]

        self.assertEqual(
            self.heatPumpServiceSpace.temp_spread_correction(
                temp_output=40,
                temp_source=50,
                design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,
            ),
            10,
        )

        self.heatPumpServiceSpace._HeatPumpService__hp._HeatPump__test_data.temp_spread_correction.assert_called_with(  # type: ignore[AttributeAccessIssue]
            temp_source=50,
            temp_output=40,
            temp_diff_evaporator=15.0,
            temp_diff_condenser=5.0,
            temp_spread_emitter=ANY,
            design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,
        )

    def test_temp_spread_correction_water(self):
        """Test that temp_spread_correction returns the correct values with a water source"""
        self.heat_pump._HeatPump__source_type = SourceType.WATER_GROUND
        self.heatPumpServiceSpace.heat_pump._HeatPump__test_data.temp_spread_correction.return_value = 10  # type: ignore[AttributeAccessIssue]

        self.assertEqual(
            self.heatPumpServiceSpace.temp_spread_correction(
                temp_output=40,
                temp_source=50,
                design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,
            ),
            10,
        )

        self.heatPumpServiceSpace.heat_pump._HeatPump__test_data.temp_spread_correction.assert_called_with(  # type: ignore[AttributeAccessIssue]
            temp_source=50,
            temp_output=40,
            temp_diff_evaporator=10.0,
            temp_diff_condenser=5.0,
            temp_spread_emitter=ANY,
            design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,
        )

    def test_temp_spread_correction_invalid(self):
        """Test that temp_spread_correction raises on an invalid source"""
        self.heat_pump._HeatPump__source_type = SourceType.OUTSIDE_AIR

        with self.assertRaises(ValueError):
            with patch.object(
                SourceType, "source_fluid_is_air", new_callable=PropertyMock
            ) as mock_source_type:
                mock_source_type.return_value = False
                self.heatPumpServiceSpace.temp_spread_correction(
                    temp_output=40,
                    temp_source=50,
                    design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,
                )


class TestHeatPumpWarmAir(unittest.TestCase):
    """Unit tests for HeatPumpWarmAir"""

    def setUp(self):
        self.heatPumpWarmAir = HeatPumpWarmAir(
            heat_pump=MagicMock(HeatPump),
            service_name="new_service",
            temp_diff_emit_design=10,
            design_flow_temp_op_cond=25.0,
            control=MagicMock(SetpointTimeControl),
            temp_flow=10,
            frac_convective=0.7,
            volume_heated=12,
        )

    def test_temp_setpnt(self):
        with patch(
            "hem_core.heating_systems.heat_pump.HeatPumpServiceSpace.temp_setpnt"
        ) as mock_temp_setpnt:
            self.assertEqual(self.heatPumpWarmAir.temp_setpnt(), mock_temp_setpnt.return_value)
            mock_temp_setpnt.assert_called_once()

    def test_in_required_period(self):
        with patch(
            "hem_core.heating_systems.heat_pump.HeatPumpServiceSpace.in_required_period"
        ) as mock_in_required_period:
            self.assertEqual(
                self.heatPumpWarmAir.in_required_period(),
                mock_in_required_period.return_value,
            )
            mock_in_required_period.assert_called_once()

    def test_frac_convective(self):
        """Test that frac_convective returns the correct value"""
        self.assertEqual(self.heatPumpWarmAir.frac_convective(), 0.7)

    def test_energy_output_min(self):
        """Test that energy_output_min returns 0"""
        self.assertEqual(self.heatPumpWarmAir.energy_output_min(), 0)

    def test_demand_energy(self):
        """Test that demand_energy returns the correct values using HeatPumpServiceSpace"""
        with patch(
            "hem_core.heating_systems.heat_pump.HeatPumpServiceSpace.demand_energy"
        ) as mock_demand_energy:
            mock_demand_energy.return_value = 4
            self.assertEqual(self.heatPumpWarmAir.demand_energy(energy_demand=100), 4)
            mock_demand_energy.assert_called_once_with(
                energy_demand=100, temp_flow=10, temp_return=10
            )

    def test_control_is_none(self):
        with patch("hem_core.heating_systems.heat_pump.HeatPumpServiceSpace.control", None):
            self.assertIsNone(self.heatPumpWarmAir.temp_setpnt())
            self.assertIsNone(self.heatPumpWarmAir.in_required_period())


class TestHeatPump(unittest.TestCase):
    def setUp(self):
        self.heat_dict: HeatPumpCharacteristics = {
            "source_type": "OutsideAir",
            "sink_type": HeatPumpSinkType.WATER,
            "backup_ctrl_type": HeatPumpBackupControlType.TOP_UP,
            "temp_distribution_heat_network": 20.0,
            "eahp_mixed_max_temp": 10,
            "eahp_mixed_min_temp": 0,
            "time_delay_backup": 1.0,
            "modulating_control": True,
            "min_modulation_rate_20": 20.0,
            "min_modulation_rate_35": 0.35,
            "min_modulation_rate_55": 0.4,
            "time_constant_onoff_operation": 140,
            "temp_return_feed_max": 70,
            "temp_lower_operating_limit": -5.0,
            "min_temp_diff_flow_return_for_hp_to_operate": 0.0,
            "var_flow_temp_ctrl_during_test": False,
            "power_heating_circ_pump": 0.015,
            "power_source_circ_pump": 0.01,
            "power_standby": 0.015,
            "power_crankcase_heater": 0.01,
            "power_off": 0.015,
            "power_max_backup": 3.0,
            "test_data_EN14825": [
                {
                    "test_letter": "A",
                    "capacity": 8.4,
                    "cop": 4.6,
                    "design_flow_temp": 35,
                    "temp_outlet": 34,
                    "temp_source": 0,
                    "temp_test": -7,
                },
                {
                    "test_letter": "B",
                    "capacity": 8.3,
                    "cop": 4.9,
                    "design_flow_temp": 35,
                    "temp_outlet": 30,
                    "temp_source": 0,
                    "temp_test": 2,
                },
                {
                    "test_letter": "C",
                    "capacity": 8.3,
                    "cop": 5.1,
                    "design_flow_temp": 35,
                    "temp_outlet": 27,
                    "temp_source": 0,
                    "temp_test": 7,
                },
                {
                    "test_letter": "D",
                    "capacity": 8.2,
                    "cop": 5.4,
                    "design_flow_temp": 35,
                    "temp_outlet": 24,
                    "temp_source": 0,
                    "temp_test": 12,
                },
                {
                    "test_letter": "F",
                    "capacity": 8.4,
                    "cop": 4.6,
                    "design_flow_temp": 35,
                    "temp_outlet": 34,
                    "temp_source": 0,
                    "temp_test": -7,
                },
                {
                    "test_letter": "A",
                    "capacity": 8.8,
                    "cop": 3.2,
                    "design_flow_temp": 55,
                    "temp_outlet": 52,
                    "temp_source": 0,
                    "temp_test": -7,
                },
                {
                    "test_letter": "B",
                    "capacity": 8.6,
                    "cop": 3.6,
                    "design_flow_temp": 55,
                    "temp_outlet": 42,
                    "temp_source": 0,
                    "temp_test": 2,
                },
                {
                    "test_letter": "C",
                    "capacity": 8.5,
                    "cop": 3.9,
                    "design_flow_temp": 55,
                    "temp_outlet": 36,
                    "temp_source": 0,
                    "temp_test": 7,
                },
                {
                    "test_letter": "D",
                    "capacity": 8.5,
                    "cop": 4.3,
                    "design_flow_temp": 55,
                    "temp_outlet": 30,
                    "temp_source": 0,
                    "temp_test": 12,
                },
                {
                    "test_letter": "F",
                    "capacity": 8.8,
                    "cop": 3.2,
                    "design_flow_temp": 55,
                    "temp_outlet": 52,
                    "temp_source": 0,
                    "temp_test": -7,
                },
            ],
        }
        self.simtime = SimulationTime(start_time=0, end_time=2, step=1)
        self.energysupply = EnergySupply(fuel_type=FuelType.MAINS_GAS, simulation_time=self.simtime)
        self.energy_supply_conn_name_auxiliary = "HeatPump_auxiliary: hp"
        self.windspeed = [3.7, 3.8]
        self.wind_direction = [
            Orientation360(200.0),
            Orientation360(220.0),
        ]
        self.airtemp = [0.0, 2.5]
        self.diffuse_horizontal_radiation = [333.0, 610.0]
        self.direct_beam_radiation = [420.0, 750.0]
        self.solar_reflectivity_of_ground = [0.2] * 8760
        self.latitude = 51.42
        self.longitude = -0.75
        self.timezone = 0
        self.start_day = 0
        self.end_day = 0
        self.time_series_step = 1
        self.january_first = 1
        self.daylight_savings = "not applicable"
        self.leap_day_included = False
        self.direct_beam_conversion_needed = False
        self.shading_segments = [
            {"number": 1, "start": 180, "end": 135},
            {"number": 2, "start": 135, "end": 90},
        ]
        self.extcond = ExternalConditions(
            simulation_time=self.simtime,
            air_temps=self.airtemp,
            wind_speeds=self.windspeed,
            wind_directions=self.wind_direction,
            diffuse_horizontal_radiation=self.diffuse_horizontal_radiation,
            direct_beam_radiation=self.direct_beam_radiation,
            solar_reflectivity_of_ground=self.solar_reflectivity_of_ground,
            latitude=self.latitude,
            longitude=self.longitude,
            timezone=self.timezone,
            start_day=self.start_day,
            end_day=self.end_day,
            time_series_step=self.time_series_step,
            january_first=self.january_first,
            daylight_savings=self.daylight_savings,
            leap_day_included=self.leap_day_included,
            direct_beam_conversion_needed=self.direct_beam_conversion_needed,
            shading_segments=self.shading_segments,
        )
        self.number_of_zones = 2

        self.heat_pump = HeatPump(
            hp_dict=self.heat_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
        )

        # Test data for heat_neatwork
        self.heat_dict_heat_nw: HeatPumpCharacteristics = {
            "source_type": "HeatNetwork",
            "sink_type": HeatPumpSinkType.WATER,
            "backup_ctrl_type": HeatPumpBackupControlType.TOP_UP,
            "temp_distribution_heat_network": 20.0,
            "eahp_mixed_max_temp": 10,
            "eahp_mixed_min_temp": 0,
            "time_delay_backup": 2.0,
            "modulating_control": True,
            "min_modulation_rate_35": 0.35,
            "min_modulation_rate_20": 20.0,
            "min_modulation_rate_55": 0.4,
            "time_constant_onoff_operation": 140,
            "temp_return_feed_max": 70.0,
            "temp_lower_operating_limit": -5.0,
            "min_temp_diff_flow_return_for_hp_to_operate": 0.0,
            "var_flow_temp_ctrl_during_test": False,
            "power_heating_circ_pump": 0.015,
            "power_source_circ_pump": 0.01,
            "power_standby": 0.015,
            "power_crankcase_heater": 0.01,
            "power_off": 0.015,
            "power_max_backup": 3.0,
            "test_data_EN14825": [
                {
                    "test_letter": "A",
                    "capacity": 8.4,
                    "cop": 4.6,
                    "design_flow_temp": 35,
                    "temp_outlet": 34,
                    "temp_source": 0,
                    "temp_test": -7,
                },
                {
                    "test_letter": "B",
                    "capacity": 8.3,
                    "cop": 4.9,
                    "design_flow_temp": 35,
                    "temp_outlet": 30,
                    "temp_source": 0,
                    "temp_test": 2,
                },
                {
                    "test_letter": "C",
                    "capacity": 8.3,
                    "cop": 5.1,
                    "design_flow_temp": 35,
                    "temp_outlet": 27,
                    "temp_source": 0,
                    "temp_test": 7,
                },
                {
                    "test_letter": "D",
                    "capacity": 8.2,
                    "cop": 5.4,
                    "design_flow_temp": 35,
                    "temp_outlet": 24,
                    "temp_source": 0,
                    "temp_test": 12,
                },
                {
                    "test_letter": "F",
                    "capacity": 8.4,
                    "cop": 4.6,
                    "design_flow_temp": 35,
                    "temp_outlet": 34,
                    "temp_source": 0,
                    "temp_test": -7,
                },
            ],
        }
        # Test data for exhaust heat pump
        self.heat_dict_exhaust: HeatPumpCharacteristics = {
            "source_type": SourceType.EXHAUST_AIR_MIXED,
            "sink_type": HeatPumpSinkType.WATER,
            "backup_ctrl_type": HeatPumpBackupControlType.SUBSTITUTE,
            "temp_distribution_heat_network": 1.0,
            "time_delay_backup": 2.0,
            "modulating_control": True,
            "min_modulation_rate_20": 20.0,
            "min_modulation_rate_35": 0.35,
            "min_modulation_rate_55": 0.4,
            "time_constant_onoff_operation": 140,
            "temp_return_feed_max": 70,
            "temp_lower_operating_limit": -5.0,
            "min_temp_diff_flow_return_for_hp_to_operate": 0.0,
            "var_flow_temp_ctrl_during_test": True,
            "power_heating_circ_pump": 0.015,
            "power_source_circ_pump": 0.01,
            "power_standby": 0.015,
            "power_crankcase_heater": 0.01,
            "power_off": 0.015,
            "power_max_backup": 3.0,
            "eahp_mixed_max_temp": 10,
            "eahp_mixed_min_temp": 0,
            "test_data_EN14825": [
                {
                    "air_flow_rate": 100.0,
                    "test_letter": "A",
                    "capacity": 8.4,
                    "cop": 4.6,
                    "design_flow_temp": 35,
                    "temp_outlet": 34,
                    "temp_source": 0,
                    "temp_test": -7,
                    "eahp_mixed_ext_air_ratio": 0.62,
                },
                {
                    "air_flow_rate": 100.0,
                    "test_letter": "B",
                    "capacity": 8.3,
                    "cop": 4.9,
                    "design_flow_temp": 35,
                    "temp_outlet": 30,
                    "temp_source": 0,
                    "temp_test": 2,
                    "eahp_mixed_ext_air_ratio": 0.62,
                },
                {
                    "air_flow_rate": 100.0,
                    "test_letter": "C",
                    "capacity": 8.3,
                    "cop": 5.1,
                    "design_flow_temp": 35,
                    "temp_outlet": 27,
                    "temp_source": 0,
                    "temp_test": 7,
                    "eahp_mixed_ext_air_ratio": 0.62,
                },
                {
                    "air_flow_rate": 100.0,
                    "test_letter": "D",
                    "capacity": 8.2,
                    "cop": 5.4,
                    "design_flow_temp": 35,
                    "temp_outlet": 24,
                    "temp_source": 0,
                    "temp_test": 12,
                    "eahp_mixed_ext_air_ratio": 0.62,
                },
                {
                    "air_flow_rate": 100.0,
                    "test_letter": "F",
                    "capacity": 8.4,
                    "cop": 4.6,
                    "design_flow_temp": 35,
                    "temp_outlet": 34,
                    "temp_source": 0,
                    "temp_test": -7,
                    "eahp_mixed_ext_air_ratio": 0.62,
                },
            ],
        }
        self.heat_dict_sinktype_air: HeatPumpCharacteristics = {
            "source_type": "OutsideAir",
            "sink_type": HeatPumpSinkType.AIR,
            "backup_ctrl_type": HeatPumpBackupControlType.TOP_UP,
            "temp_distribution_heat_network": 1.0,
            "time_delay_backup": 2.0,
            "eahp_mixed_max_temp": 10,
            "eahp_mixed_min_temp": 0,
            "modulating_control": True,
            "min_modulation_rate_35": 0.35,
            "min_modulation_rate_55": 0.4,
            "time_constant_onoff_operation": 140,
            "temp_return_feed_max": 70.0,
            "temp_lower_operating_limit": -5.0,
            "min_temp_diff_flow_return_for_hp_to_operate": 0.0,
            "var_flow_temp_ctrl_during_test": True,
            "power_heating_circ_pump": 0.015,
            "power_source_circ_pump": 0.01,
            "power_standby": 0.015,
            "power_crankcase_heater": 0.01,
            "power_off": 0.015,
            "power_max_backup": 3.0,
            "min_modulation_rate_20": 20.0,
            "test_data_EN14825": [
                {
                    "test_letter": "A",
                    "capacity": 8.4,
                    "cop": 4.6,
                    "design_flow_temp": 35,
                    "temp_outlet": 34,
                    "temp_source": 0,
                    "temp_test": -7,
                },
                {
                    "test_letter": "B",
                    "capacity": 8.3,
                    "cop": 4.9,
                    "design_flow_temp": 35,
                    "temp_outlet": 30,
                    "temp_source": 0,
                    "temp_test": 2,
                },
                {
                    "test_letter": "C",
                    "capacity": 8.3,
                    "cop": 5.1,
                    "design_flow_temp": 35,
                    "temp_outlet": 27,
                    "temp_source": 0,
                    "temp_test": 7,
                },
                {
                    "test_letter": "D",
                    "capacity": 8.2,
                    "cop": 5.4,
                    "design_flow_temp": 35,
                    "temp_outlet": 24,
                    "temp_source": 0,
                    "temp_test": 12,
                },
                {
                    "test_letter": "F",
                    "capacity": 8.4,
                    "cop": 4.6,
                    "design_flow_temp": 35,
                    "temp_outlet": 34,
                    "temp_source": 0,
                    "temp_test": -7,
                },
            ],
        }

        self.boiler_dict = {
            "EnergySupply": "mains gas",
            "EnergySupply_aux": "mains elec",
            "rated_power": 24.0,
            "efficiency_full_load": 0.891,
            "efficiency_part_load": 0.991,
            "boiler_location": HeatSourceLocation.INTERNAL,
            "modulation_load": 0.3,
            "electricity_circ_pump": 0.06,
            "electricity_part_load": 0.0131,
            "electricity_full_load": 0.0388,
            "electricity_standby": 0.0244,
        }

        self.design_flow_temp_op_cond = 55.0
        self.design_flow_temp_op_cond_K = self.design_flow_temp_op_cond + 273.15

    def test_init_no_backup_ctrl_type(self):
        """Test that power_max_backup is 0 if there is HeatPumpBackupControlType is None"""

        self.heat_dict["backup_ctrl_type"] = HeatPumpBackupControlType.NONE
        self.energysupply = EnergySupply(fuel_type=FuelType.MAINS_GAS, simulation_time=self.simtime)

        self.heat_pump = HeatPump(
            hp_dict=self.heat_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
        )

        self.assertEqual(self.heat_pump.backup_heater_max_power, 0)

    def test_init_missing_heat_network(self):
        """Test that the constructor throws if the heat network isn't specified"""
        self.heat_dict["source_type"] = "HeatNetwork"
        self.energysupply = EnergySupply(fuel_type=FuelType.MAINS_GAS, simulation_time=self.simtime)

        with self.assertRaises(ValueError):
            self.heat_pump = HeatPump(
                hp_dict=self.heat_dict,
                energy_supply=self.energysupply,
                energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
                simulation_time=self.simtime,
                external_conditions=self.extcond,
                number_of_zones=self.number_of_zones,
            )

    def test_init_overvent_ratio_too_high(self):
        """Test that the constructor throws if the overvent ratio is above 1"""
        self.heat_dict["source_type"] = "ExhaustAirMVHR"
        self.heat_dict["test_data_EN14825"] = [
            {
                "test_letter": "A",
                "air_flow_rate": 1050,
                "design_flow_temp": 45,
                "temp_outlet": 35,
                "temp_source": 40,
                "temp_test": 40,
                "capacity": 10,
                "cop": 1,
            },
            {
                "test_letter": "B",
                "air_flow_rate": 1050,
                "design_flow_temp": 45,
                "temp_outlet": 35,
                "temp_source": 41,
                "temp_test": 41,
                "capacity": 11,
                "cop": 1,
            },
            {
                "test_letter": "C",
                "air_flow_rate": 1050,
                "design_flow_temp": 45,
                "temp_outlet": 35,
                "temp_source": 42,
                "temp_test": 42,
                "capacity": 12,
                "cop": 1,
            },
            {
                "test_letter": "D",
                "air_flow_rate": 1050,
                "design_flow_temp": 45,
                "temp_outlet": 35,
                "temp_source": 43,
                "temp_test": 43,
                "capacity": 13,
                "cop": 1,
            },
            {
                "test_letter": "F",
                "air_flow_rate": 1050,
                "design_flow_temp": 45,
                "temp_outlet": 35,
                "temp_source": 44,
                "temp_test": 44,
                "capacity": 14,
                "cop": 1,
            },
        ]
        self.energysupply = EnergySupply(fuel_type=FuelType.MAINS_GAS, simulation_time=self.simtime)

        with self.assertRaises(ValueError):
            self.heat_pump = HeatPump(
                hp_dict=self.heat_dict,
                energy_supply=self.energysupply,
                energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
                simulation_time=self.simtime,
                external_conditions=self.extcond,
                number_of_zones=self.number_of_zones,
                throughput_exhaust_air=1000,
            )

    def test_init_air_flow_rate(self):
        """Test that the constructor throws there is unexpected air flow rate test data"""
        self.heat_dict["source_type"] = "Ground"
        self.heat_dict["test_data_EN14825"] = [
            {
                "test_letter": "A",
                "air_flow_rate": 50,
                "capacity": 14,
                "cop": 1,
                "design_flow_temp": 45,
                "temp_outlet": 35,
                "temp_source": 44,
                "temp_test": 44,
            },
            {
                "test_letter": "B",
                "air_flow_rate": 50,
                "capacity": 14,
                "cop": 1,
                "design_flow_temp": 45,
                "temp_outlet": 35,
                "temp_source": 44,
                "temp_test": 44,
            },
            {
                "test_letter": "C",
                "air_flow_rate": 50,
                "capacity": 14,
                "cop": 1,
                "design_flow_temp": 45,
                "temp_outlet": 35,
                "temp_source": 44,
                "temp_test": 44,
            },
            {
                "test_letter": "D",
                "air_flow_rate": 50,
                "capacity": 14,
                "cop": 1,
                "design_flow_temp": 45,
                "temp_outlet": 35,
                "temp_source": 44,
                "temp_test": 44,
            },
            {
                "test_letter": "F",
                "air_flow_rate": 50,
                "capacity": 14,
                "cop": 1,
                "design_flow_temp": 45,
                "temp_outlet": 35,
                "temp_source": 44,
                "temp_test": 44,
            },
        ]
        self.energysupply = EnergySupply(fuel_type=FuelType.MAINS_GAS, simulation_time=self.simtime)

        with self.assertRaises(ValueError):
            self.heat_pump = HeatPump(
                hp_dict=self.heat_dict,
                energy_supply=self.energysupply,
                energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
                simulation_time=self.simtime,
                external_conditions=self.extcond,
                number_of_zones=self.number_of_zones,
                throughput_exhaust_air=1000,
            )

    def test_init_unique_air_ratio(self):
        """Test that the constructor throws there is unique air_flow_rate test data"""
        self.heat_dict["source_type"] = SourceType.EXHAUST_AIR_MIXED
        self.heat_dict["eahp_mixed_min_temp"] = 20
        self.heat_dict["eahp_mixed_max_temp"] = 30
        self.heat_dict["test_data_EN14825"] = [
            {
                "test_letter": "A",
                "eahp_mixed_ext_air_ratio": 0.5,
                "air_flow_rate": 50,
                "design_flow_temp": 45,
                "temp_outlet": 35,
                "temp_source": 40,
                "temp_test": 40,
                "capacity": 10,
                "cop": 1,
            },
            {
                "test_letter": "B",
                "eahp_mixed_ext_air_ratio": 0.5,
                "air_flow_rate": 50,
                "design_flow_temp": 45,
                "temp_outlet": 35,
                "temp_source": 41,
                "temp_test": 41,
                "capacity": 11,
                "cop": 1,
            },
            {
                "test_letter": "C",
                "eahp_mixed_ext_air_ratio": 0.5,
                "air_flow_rate": 50,
                "design_flow_temp": 45,
                "temp_outlet": 35,
                "temp_source": 42,
                "temp_test": 42,
                "capacity": 12,
                "cop": 1,
            },
            {
                "test_letter": "D",
                "eahp_mixed_ext_air_ratio": 0.5,
                "air_flow_rate": 50,
                "design_flow_temp": 45,
                "temp_outlet": 35,
                "temp_source": 43,
                "temp_test": 43,
                "capacity": 13,
                "cop": 1,
            },
            {
                "test_letter": "F",
                "eahp_mixed_ext_air_ratio": 0.6,
                "air_flow_rate": 50,
                "design_flow_temp": 45,
                "temp_outlet": 35,
                "temp_source": 44,
                "temp_test": 44,
                "capacity": 14,
                "cop": 1,
            },
        ]
        self.energysupply = EnergySupply(fuel_type=FuelType.MAINS_GAS, simulation_time=self.simtime)

        with self.assertRaises(ValueError):
            self.heat_pump = HeatPump(
                hp_dict=self.heat_dict,
                energy_supply=self.energysupply,
                energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
                simulation_time=self.simtime,
                external_conditions=self.extcond,
                number_of_zones=self.number_of_zones,
                throughput_exhaust_air=1000,
            )

    def test_source_is_exhaust_air(self):
        self.heat_pump.__source_type = SourceType.OUTSIDE_AIR
        self.assertEqual(self.heat_pump.source_is_exhaust_air(), False)

    def test_init_buffer_tank(self):
        """Test that the buffer tank is initialised if given"""
        self.heat_dict["BufferTank"] = {
            "daily_losses": 10,
            "volume": 100,
            "pump_fixed_flow_rate": 5,
            "pump_power_at_flow_rate": 10,
        }
        self.energysupply = EnergySupply(fuel_type=FuelType.MAINS_GAS, simulation_time=self.simtime)
        # Create a mock project object with the required methods
        mock_project = Mock()
        # Mock the private method _Project__update_temp_internal_air
        mock_project._Project__update_temp_internal_air = Mock(return_value=None)
        # Mock temp_internal_air_prev_timestep to return 20°C
        mock_project.temp_internal_air_prev_timestep = Mock(return_value=20.0)

        self.heat_pump = HeatPump(
            hp_dict=self.heat_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            throughput_exhaust_air=1000,
            project=mock_project,  # Pass the mock project object
        )
        assert self.heat_pump.buffer_tank is not None
        self.assertEqual(self.heat_pump.buffer_tank.volume, 100)

    def test_buffer_int_gains(self):
        """Test that buffer_int_gains returns the gains from the buffer tank"""
        self.heat_dict["BufferTank"] = {
            "daily_losses": 10,
            "volume": 100,
            "pump_fixed_flow_rate": 5,
            "pump_power_at_flow_rate": 10,
        }
        self.energysupply = EnergySupply(fuel_type=FuelType.MAINS_GAS, simulation_time=self.simtime)
        # Create a mock project object with the required methods
        mock_project = Mock()
        # Mock the private method _Project__update_temp_internal_air
        mock_project._Project__update_temp_internal_air = Mock(return_value=None)
        # Mock temp_internal_air_prev_timestep to return 20°C
        mock_project.temp_internal_air_prev_timestep = Mock(return_value=20.0)

        self.heat_pump = HeatPump(
            hp_dict=self.heat_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            throughput_exhaust_air=1000,
            project=mock_project,  # Pass the mock project object
        )
        self.heat_pump._HeatPump__buffer_tank = MagicMock()  # type: ignore[AttributeAccessIssue]
        self.heat_pump._HeatPump__buffer_tank.internal_gains.return_value = 3  # type: ignore[AttributeAccessIssue]

        self.assertEqual(self.heat_pump.buffer_int_gains(), 3)

    def test_buffer_int_gains_no_buffer_tank(self):
        """Test that buffer_int_gains returns 0 if there is no buffer tank"""
        self.energysupply = EnergySupply(fuel_type=FuelType.MAINS_GAS, simulation_time=self.simtime)
        self.heat_pump = HeatPump(
            hp_dict=self.heat_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            throughput_exhaust_air=1000,
        )

        self.assertEqual(self.heat_pump.buffer_int_gains(), 0)

    def test_create_service_connection(self):
        """Test creation of EnergySupplyConnection for the service name given"""
        self.service_name = "new_service"
        # Ensure the service name does not exist in __energy_supply_connections
        self.assertNotIn(self.service_name, self.heat_pump.energy_supply_connections)
        # Call the method under test
        self.heat_pump._HeatPump__create_service_connection(service_name=self.service_name)  # type: ignore[AttributeAccessIssue]
        # Check that the service name was added to __energy_supply_connections
        self.assertIn(self.service_name, self.heat_pump.energy_supply_connections)
        # Check system exit when connection is created with exiting service name
        with self.assertRaises(ValueError):
            self.heat_pump._HeatPump__create_service_connection(service_name=self.service_name)  # type: ignore[AttributeAccessIssue]

        # Check with heat_network
        self.energy_supply_conn_name_auxiliary = "HeatPump_auxiliary: hp1"
        self.energy_supply_heat_source = EnergySupply(
            simulation_time=self.simtime, fuel_type=FuelType.CUSTOM
        )
        self.heat_pump_nw = HeatPump(
            hp_dict=self.heat_dict_heat_nw,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            energy_supply_heat_source=self.energy_supply_heat_source,
        )
        # Call the method under test
        self.heat_pump_nw._HeatPump__create_service_connection(service_name="new_service_nw")  # type: ignore[AttributeAccessIssue]
        self.assertIn("new_service_nw", self.heat_pump_nw.energy_supply_connections)

    def test_create_service_hot_water_combi(self):
        """Check BoilerServiceWaterCombi object is created correctly"""

        self.energy_supply_conn_name_auxiliary = MagicMock(spec=EnergySupplyConnection)
        self.boiler = Boiler(
            boiler_dict=self.boiler_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_aux=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            ext_cond=self.extcond,
        )
        self.heat_pump_with_boiler = HeatPump(
            hp_dict=self.heat_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            boiler=self.boiler,
        )

        self.service_name = "service_hot_water_combi"
        self.coldfeed = ColdWaterSource(
            cold_water_temps=[1.0, 1.2],
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )
        self.temp_hot_water = 50
        self.boiler_data = {
            "type": "CombiBoiler",
            "ColdWaterSource": "mains water",
            "HeatSourceWet": "hp",
            "Control": "hw timer",
            "separate_DHW_tests": "M&L",
            "rejected_energy_1": 0.0004,
            "fuel_energy_2": 13.078,
            "rejected_energy_2": 0.0004,
            "storage_loss_factor_2": 0.91574,
            "rejected_factor_3": 0,
            "daily_HW_usage": 120,
            "setpoint_temp": 60.0,
        }
        boiler_service_WaterCombi_obj = self.heat_pump_with_boiler.create_service_hot_water_combi(
            boiler_data=self.boiler_data,
            service_name=self.service_name,
            temp_hot_water=self.temp_hot_water,
            cold_feed=self.coldfeed,
        )

        self.assertTrue(isinstance(boiler_service_WaterCombi_obj, BoilerServiceWaterCombi))

        # Check function does system exit if boiler object is not defined
        self.energy_supply_conn_name_auxiliary = "HeatPump_auxiliary: boiler1"
        self.heat_pump = HeatPump(
            hp_dict=self.heat_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
        )
        with self.assertRaises(ValueError):
            self.heat_pump.create_service_hot_water_combi(
                boiler_data=self.boiler_data,
                service_name=self.service_name,
                temp_hot_water=self.temp_hot_water,
                cold_feed=self.coldfeed,
            )

    def test_create_service_hot_water(self):
        """Check the function returns HeatPumpServiceWater object"""

        self.energy_supply_conn_name_auxiliary = "HeatPump_auxiliary: HotWater"
        self.heat_pump = HeatPump(
            hp_dict=self.heat_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
        )
        self.service_name = "service_hot_water"
        self.temp_limit_upper = 60.0
        self.coldfeed = ColdWaterSource(
            cold_water_temps=[1.0, 1.2],
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )
        self.temp_hot_water = 50

        controlmin = SetpointTimeControl(
            schedule=[52, 52, None, 52],
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )
        controlmax = SetpointTimeControl(
            schedule=[60, 60, 60, 60], simulation_time=self.simtime, start_day=0, time_series_step=1
        )

        heatpump_servicewater_obj = self.heat_pump.create_service_hot_water(
            service_name=self.service_name,
            temp_limit_upper=self.temp_limit_upper,
            cold_feed=self.coldfeed,
            controlmin=controlmin,
            controlmax=controlmax,
        )

        self.assertTrue(isinstance(heatpump_servicewater_obj, HeatPumpServiceWater))

        self.assertIn(self.service_name, self.heat_pump.energy_supply_connections)

        # Check the with boiler data in heat pump
        self.energy_supply_conn_name_auxiliary = "HeatPump_auxiliary: HotWater_boiler"

        self.heat_pump_with_boiler = HeatPump(
            hp_dict=self.heat_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            boiler=MagicMock(),
        )
        self.service_name = "service_hot_water_boiler"
        self.heat_pump_with_boiler.create_service_hot_water(
            service_name=self.service_name,
            temp_limit_upper=self.temp_limit_upper,
            cold_feed=self.coldfeed,
            controlmin=controlmin,
            controlmax=controlmax,
        )
        assert self.heat_pump_with_boiler.boiler is not None
        assert isinstance(
            self.heat_pump_with_boiler.boiler.create_service_hot_water_regular, MagicMock
        )
        self.heat_pump_with_boiler.boiler.create_service_hot_water_regular.assert_called_once_with(
            service_name=self.service_name,
            cold_feed=self.coldfeed,
            controlmin=controlmin,
            controlmax=controlmax,
        )

    def test_create_service_space_heating(self):
        """Check the function returns HeatPumpServiceSpace object"""

        self.service_name = "service_space"
        self.temp_limit_upper = 50.0
        self.temp_diff_emit_design = 50.0
        self.control = None
        self.volume_heated = 250.0

        heatpump_servicespace_obj = self.heat_pump.create_service_space_heating(
            service_name=self.service_name,
            emitter_type=HeatPumpEmitterType.RADIATORS_UFH,
            temp_limit_upper=self.temp_limit_upper,
            temp_diff_emit_design=self.temp_diff_emit_design,
            design_flow_temp_op_cond=self.design_flow_temp_op_cond,
            control=self.control,
            volume_heated=self.volume_heated,
        )

        self.assertTrue(isinstance(heatpump_servicespace_obj, HeatPumpServiceSpace))

        self.assertIn(self.service_name, self.heat_pump.energy_supply_connections)

        # Check the with boiler data in heat pump
        self.energy_supply_conn_name_auxiliary = "HeatPump_auxiliary: SpaceHeating_boiler"

        self.heat_pump_with_boiler = HeatPump(
            hp_dict=self.heat_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            boiler=MagicMock(),
        )
        self.service_name = "service_space_boiler"
        self.heat_pump_with_boiler.create_service_space_heating(
            service_name=self.service_name,
            emitter_type=HeatPumpEmitterType.RADIATORS_UFH,
            temp_limit_upper=self.temp_limit_upper,
            temp_diff_emit_design=self.temp_diff_emit_design,
            design_flow_temp_op_cond=self.design_flow_temp_op_cond,
            control=self.control,
            volume_heated=self.volume_heated,
        )
        assert self.heat_pump_with_boiler.boiler is not None
        assert isinstance(self.heat_pump_with_boiler.boiler.create_service_space_heating, MagicMock)
        self.heat_pump_with_boiler.boiler.create_service_space_heating.assert_called_once_with(
            service_name=self.service_name, control=self.control
        )
        self.assertIn(self.service_name, self.heat_pump_with_boiler.energy_supply_connections)

        # Check with exhaust air heat pump
        self.energy_supply_conn_name_auxiliary = "HeatPump_auxiliary: exhaust_service_space"
        self.heat_pump_exhaust = HeatPump(
            hp_dict=self.heat_dict_exhaust,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            throughput_exhaust_air=101,
        )

        self.service_name = "service_space_exhaust"
        self.heat_pump_exhaust.create_service_space_heating(
            service_name=self.service_name,
            emitter_type=HeatPumpEmitterType.RADIATORS_UFH,
            temp_limit_upper=self.temp_limit_upper,
            temp_diff_emit_design=self.temp_diff_emit_design,
            design_flow_temp_op_cond=self.design_flow_temp_op_cond,
            control=self.control,
            volume_heated=self.volume_heated,
        )
        self.assertAlmostEqual(self.heat_pump_exhaust.volume_heated_all_services, 250.0)

    def test_create_service_space_heating_warm_air(self):
        """Check HeatPumpWarmAir object is returned"""
        self.service_name = "service_space_warmair"
        self.control = None
        self.volume_heated = 250.0
        self.frac_convective = 0.9
        # Check the system exit is raised when Sink type is not air
        with self.assertRaises(ValueError):
            self.heat_pump.create_service_space_heating_warm_air(
                service_name=self.service_name,
                control=self.control,
                frac_convective=self.frac_convective,
                volume_heated=self.volume_heated,
            )

        # Check without boiler object and sink type 'AIR'
        self.energy_supply_conn_name_auxiliary = MagicMock(spec=EnergySupplyConnection)
        self.heat_pump_sink_air = HeatPump(
            hp_dict=self.heat_dict_sinktype_air,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
        )
        heatpump_servicespace_warmair_obj = (
            self.heat_pump_sink_air.create_service_space_heating_warm_air(
                service_name=self.service_name,
                control=self.control,
                frac_convective=self.frac_convective,
                volume_heated=self.volume_heated,
            )
        )

        self.assertTrue(isinstance(heatpump_servicespace_warmair_obj, HeatPumpWarmAir))

        self.assertIn(self.service_name, self.heat_pump_sink_air.energy_supply_connections)

        # Check that warm air hybrid heat pump service cannot be created
        boiler = Boiler(
            boiler_dict=self.boiler_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_aux=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            ext_cond=self.extcond,
        )
        hybrid_warm_air_hp = HeatPump(
            hp_dict=self.heat_dict_sinktype_air,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary="Aux EnergySupply connection name",
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            boiler=boiler,
        )
        self.assertRaises(
            ValueError,
            hybrid_warm_air_hp.create_service_space_heating_warm_air,
            "Hybrid HP warm air service",
            self.control,
            self.frac_convective,
            self.volume_heated,
        )

    def test_create_service_space_heating_warm_air_exhaust_air(self):
        """Test that create_service_space_heating_warm_air updates __volume_heated_all_services for exhaust air"""
        self.heat_dict["source_type"] = SourceType.EXHAUST_AIR_MIXED
        self.heat_dict["eahp_mixed_min_temp"] = 20
        self.heat_dict["eahp_mixed_max_temp"] = 30
        self.heat_dict["test_data_EN14825"] = [
            {
                "test_letter": "A",
                "eahp_mixed_ext_air_ratio": 0.5,
                "air_flow_rate": 50,
                "design_flow_temp": 45,
                "temp_outlet": 35,
                "temp_source": 40,
                "temp_test": 40,
                "capacity": 10,
                "cop": 1,
            },
            {
                "test_letter": "B",
                "eahp_mixed_ext_air_ratio": 0.5,
                "air_flow_rate": 50,
                "design_flow_temp": 45,
                "temp_outlet": 35,
                "temp_source": 41,
                "temp_test": 41,
                "capacity": 11,
                "cop": 1,
            },
            {
                "test_letter": "C",
                "eahp_mixed_ext_air_ratio": 0.5,
                "air_flow_rate": 50,
                "design_flow_temp": 45,
                "temp_outlet": 35,
                "temp_source": 42,
                "temp_test": 42,
                "capacity": 12,
                "cop": 1,
            },
            {
                "test_letter": "D",
                "eahp_mixed_ext_air_ratio": 0.5,
                "air_flow_rate": 50,
                "design_flow_temp": 45,
                "temp_outlet": 35,
                "temp_source": 43,
                "temp_test": 43,
                "capacity": 13,
                "cop": 1,
            },
            {
                "test_letter": "F",
                "eahp_mixed_ext_air_ratio": 0.5,
                "air_flow_rate": 50,
                "design_flow_temp": 45,
                "temp_outlet": 35,
                "temp_source": 44,
                "temp_test": 44,
                "capacity": 14,
                "cop": 1,
            },
        ]
        self.energysupply = EnergySupply(fuel_type=FuelType.MAINS_GAS, simulation_time=self.simtime)

        self.heat_pump = HeatPump(
            hp_dict=self.heat_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            throughput_exhaust_air=1000,
        )

        self.heat_pump._HeatPump__sink_type = HeatPumpSinkType("Air")  # type: ignore[AttributeAccessIssue]

        self.heat_pump.create_service_space_heating_warm_air(
            service_name="mains_gas", control=None, frac_convective=0.5, volume_heated=100
        )

        self.assertEqual(self.heat_pump.volume_heated_all_services, 100)

    def test_get_temp_source(self):
        # Check with source_type OutsideAir
        self.assertAlmostEqual(self.heat_pump._HeatPump__get_temp_source(), 273.15)  # type: ignore[AttributeAccessIssue]
        # Check with ExhaustAirMixed
        self.energy_supply_conn_name_auxiliary = "HeatPump_auxiliary: exhaust_source"
        throughput_exhaust_air = 101
        project = MagicMock()
        project.temp_internal_air_prev_timestep.return_value = 20
        self.heat_pump_exhaust = HeatPump(
            hp_dict=self.heat_dict_exhaust,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            throughput_exhaust_air=throughput_exhaust_air,
            project=project,
        )
        self.assertAlmostEqual(self.heat_pump_exhaust._HeatPump__get_temp_source(), 280.75)  # type: ignore[AttributeAccessIssue]
        # Check with heat_network
        self.energy_supply_conn_name_auxiliary = "HeatPump_auxiliary: heat_nw"
        self.energy_supply_heat_source = EnergySupply(
            simulation_time=self.simtime, fuel_type=FuelType.CUSTOM
        )
        self.heat_pump_nw = HeatPump(
            hp_dict=self.heat_dict_heat_nw,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            energy_supply_heat_source=self.energy_supply_heat_source,
        )
        self.assertAlmostEqual(self.heat_pump_nw._HeatPump__get_temp_source(), 293.15)  # type: ignore[AttributeAccessIssue]

    def test_get_temp_source_waterground(self):
        """Test that get_temp_source returns the correct values for WaterGround"""
        self.extcond = MagicMock()
        self.extcond.air_temp_annual.return_value = 25

        self.heat_dict["source_type"] = "WaterGround"
        self.energy_supply_conn_name_auxiliary = "HeatPump_auxiliary: heat_nw"
        self.energy_supply_heat_source = EnergySupply(
            fuel_type=FuelType.CUSTOM, simulation_time=self.simtime
        )
        self.heat_pump = HeatPump(
            hp_dict=self.heat_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            energy_supply_heat_source=self.energy_supply_heat_source,
        )
        self.assertAlmostEqual(self.heat_pump._HeatPump__get_temp_source(), 298.15)  # type: ignore[AttributeAccessIssue]

    def test_get_temp_source_watersurface(self):
        """Test that get_temp_source returns the correct values for WaterSurface"""
        self.extcond = MagicMock()
        self.extcond.air_temp_monthly.return_value = 26

        self.heat_dict["source_type"] = "WaterSurface"
        self.energy_supply_conn_name_auxiliary = "HeatPump_auxiliary: heat_nw"
        self.energy_supply_heat_source = EnergySupply(
            fuel_type=FuelType.CUSTOM, simulation_time=self.simtime
        )
        self.heat_pump = HeatPump(
            hp_dict=self.heat_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            energy_supply_heat_source=self.energy_supply_heat_source,
        )
        self.assertAlmostEqual(self.heat_pump._HeatPump__get_temp_source(), 299.15)  # type: ignore[AttributeAccessIssue]

    def test_get_temp_source_airmvhr(self):
        """Test that get_temp_source returns the correct values for ExhaustAirMwhr"""
        self.extcond = MagicMock()
        project = MagicMock()
        project.temp_internal_air_prev_timestep.return_value = 20

        self.heat_dict["source_type"] = "Ground"
        self.energy_supply_conn_name_auxiliary = "HeatPump_auxiliary: heat_nw"
        self.energy_supply_heat_source = EnergySupply(
            fuel_type=FuelType.CUSTOM, simulation_time=self.simtime
        )
        self.heat_pump = HeatPump(
            hp_dict=self.heat_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            energy_supply_heat_source=self.energy_supply_heat_source,
            project=project,
        )
        self.heat_pump._HeatPump__source_type = SourceType.EXHAUST_AIR_MVHR  # type: ignore[AttributeAccessIssue]
        self.assertAlmostEqual(self.heat_pump._HeatPump__get_temp_source(), 293.15)  # type: ignore[AttributeAccessIssue]

    def test_get_temp_source_ground(self):
        """Test that get_temp_source returns the correct values for Ground"""
        self.extcond = MagicMock()
        self.extcond.air_temp.return_value = 27

        self.heat_dict["source_type"] = "Ground"
        self.energy_supply_conn_name_auxiliary = "HeatPump_auxiliary: heat_nw"
        self.energy_supply_heat_source = EnergySupply(
            fuel_type=FuelType.CUSTOM, simulation_time=self.simtime
        )
        self.heat_pump = HeatPump(
            hp_dict=self.heat_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            energy_supply_heat_source=self.energy_supply_heat_source,
        )
        self.assertAlmostEqual(self.heat_pump._HeatPump__get_temp_source(), 281.15)  # type: ignore[AttributeAccessIssue]

    def test_get_temp_source_airmev(self):
        """Test that get_temp_source returns the correct values for ExhaustAirMev"""
        self.extcond = MagicMock()
        project = MagicMock()
        project.temp_internal_air_prev_timestep.return_value = 20

        self.heat_dict["source_type"] = "Ground"
        self.energy_supply_conn_name_auxiliary = "HeatPump_auxiliary: heat_nw"
        self.energy_supply_heat_source = EnergySupply(
            fuel_type=FuelType.CUSTOM, simulation_time=self.simtime
        )
        self.heat_pump = HeatPump(
            hp_dict=self.heat_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            energy_supply_heat_source=self.energy_supply_heat_source,
            project=project,
        )
        self.heat_pump._HeatPump__source_type = SourceType.EXHAUST_AIR_MEV  # type: ignore[AttributeAccessIssue]
        self.assertAlmostEqual(self.heat_pump._HeatPump__get_temp_source(), 293.15)  # type: ignore[AttributeAccessIssue]

    def test_thermal_capacity_op_cond(self):
        # Check with source_type OutsideAir
        self.assertAlmostEqual(
            self.heat_pump._HeatPump__thermal_capacity_op_cond(  # type: ignore[AttributeAccessIssue]
                temp_output=290.0,
                temp_source=260.0,
                design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,
            ),
            10.69686174950112,
        )

        # Check with ExhaustAirMixed
        self.energy_supply_conn_name_auxiliary = "HeatPump_auxiliary: exhaust_source_capacity"
        throughput_exhaust_air = 101
        project = MagicMock()
        self.heat_pump_exhaust = HeatPump(
            hp_dict=self.heat_dict_exhaust,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            throughput_exhaust_air=throughput_exhaust_air,
            project=project,
        )
        self.assertAlmostEqual(
            self.heat_pump_exhaust._HeatPump__thermal_capacity_op_cond(  # type: ignore[AttributeAccessIssue]
                temp_output=300.0,
                temp_source=270.0,
                design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,
            ),
            8.70672362099314,
        )

    def test_backup_energy_output_max(self):
        # With TopUp backup control
        temp_output = 300.0
        temp_return_feed = 290.0
        time_available = 1.0
        time_start = 0.0

        self.assertAlmostEqual(
            self.heat_pump._HeatPump__backup_energy_output_max(  # type: ignore[AttributeAccessIssue]
                temp_output=temp_output,
                temp_return_feed=temp_return_feed,
                time_available=time_available,
                time_start=time_start,
            ),
            3.0,
        )

        # With substitute backup control
        self.energy_supply_conn_name_auxiliary = "HeatPump_auxiliary: exhaust_backup_energy"
        self.heat_pump_exhaust = HeatPump(
            hp_dict=self.heat_dict_exhaust,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            throughput_exhaust_air=101,
        )
        self.assertAlmostEqual(
            self.heat_pump._HeatPump__backup_energy_output_max(  # type: ignore[AttributeAccessIssue]
                temp_output=temp_output,
                temp_return_feed=temp_return_feed,
                time_available=time_available,
                time_start=time_start,
            ),
            3.0,
        )

        # With a hybrid boiler
        self.energy_supply_conn_name_auxiliary = MagicMock(spec=EnergySupplyConnection)
        self.boiler = Boiler(
            boiler_dict=self.boiler_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_aux=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            ext_cond=self.extcond,
        )
        self.ctrl = SetpointTimeControl(
            schedule=[21.0, 22.0],
            simulation_time=self.simtime,
            start_day=0,  # start_day
            time_series_step=1.0,  # time_series_step
        )
        self.boilerservicespace = self.boiler.create_service_space_heating(
            service_name="service_boilerspace", control=self.ctrl
        )
        self.heat_pump_with_boiler = HeatPump(
            hp_dict=self.heat_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            boiler=self.boiler,
        )
        self.assertAlmostEqual(
            self.heat_pump_with_boiler._HeatPump__backup_energy_output_max(  # type: ignore[AttributeAccessIssue]
                temp_output=temp_output,
                temp_return_feed=temp_return_feed,
                time_available=time_available,
                time_start=time_start,
                hybrid_boiler_service=self.boilerservicespace,
            ),
            24.0,
        )

        # Test with boiler service water regular
        self.boilerservicewaterregular = self.boiler.create_service_hot_water_regular(
            service_name="service_boilerwater",
            cold_feed=MagicMock(),
            controlmin=self.ctrl,
            controlmax=self.ctrl,
        )
        self.assertAlmostEqual(
            self.heat_pump_with_boiler._HeatPump__backup_energy_output_max(  # type: ignore[AttributeAccessIssue]
                temp_output=temp_output,
                temp_return_feed=temp_return_feed,
                time_available=time_available,
                time_start=time_start,
                hybrid_boiler_service=self.boilerservicewaterregular,
            ),
            24.0,
        )

        # Should throw on an invalid backup ctrl
        self.heat_pump_with_boiler._HeatPump__backup_ctrl = None  # type: ignore[AttributeAccessIssue]
        with self.assertRaises(ValueError):
            self.heat_pump_with_boiler._HeatPump__backup_energy_output_max(  # type: ignore[AttributeAccessIssue]
                temp_output=temp_output,
                temp_return_feed=temp_return_feed,
                time_available=time_available,
                time_start=time_start,
                hybrid_boiler_service=self.boilerservicespace,
            )

    def test_energy_output_max(self):
        """Check the maximum energy output"""
        temp_output = 300.0
        temp_return_feed = 295.0
        hybrid_boiler_service = BoilerServiceSpace(
            boiler=MagicMock(), service_name="boiler_service_space", control=MagicMock()
        )

        # self.simtime_copy = copy.deepcopy(self.simtime)
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertAlmostEqual(
                    self.heat_pump._HeatPump__energy_output_max(  # type: ignore[AttributeAccessIssue]
                        temp_output=temp_output,
                        temp_return_feed=temp_return_feed,
                        design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,
                        hybrid_boiler_service=hybrid_boiler_service,
                        service_name="hp_service",
                    ),
                    [11.203924743692589, 11.51438002341549][t_idx],
                )

        # Check with backup SUBSTITUTE
        self.energy_supply_conn_name_auxiliary = "HeatPump_auxiliary: backup_substitute"
        project = MagicMock()
        project.temp_internal_air_prev_timestep.return_value = 30
        self.heat_pump_exhaust = HeatPump(
            hp_dict=self.heat_dict_exhaust,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            throughput_exhaust_air=101,
            project=project,
        )
        self.simtime.reset()
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertAlmostEqual(
                    self.heat_pump_exhaust._HeatPump__energy_output_max(  # type: ignore[AttributeAccessIssue]
                        temp_output=temp_output,
                        temp_return_feed=temp_return_feed,
                        design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,
                        hybrid_boiler_service=hybrid_boiler_service,
                        service_name="heat_pump_exhaust_service",
                    ),
                    [10.191526455038767, 10.358981076999134][t_idx],
                )

        # Test that backup heater takes over when HP source temp lower than operating limit
        project.temp_internal_air_prev_timestep.return_value = -7
        self.simtime.reset()
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertAlmostEqual(
                    self.heat_pump_exhaust._HeatPump__energy_output_max(  # type: ignore[AttributeAccessIssue]
                        temp_output=temp_output,
                        temp_return_feed=temp_return_feed,
                        design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,
                        hybrid_boiler_service=None,
                        service_name="heat_pump_exhaust_service",
                    ),
                    [3.0, 3.0][t_idx],
                )

    def test_energy_output_max_buffer_tank(self):
        """Test that energy_output_max returns the correct values with a buffer tank"""
        temp_output = 300.0
        temp_return_feed = 295.0
        hybrid_boiler_service = MagicMock()

        emitters_data_for_buffer_tank = {
            "temp_emitter_req": 43.32561228292832,
            "power_req_from_buffer_tank": 6.325422354229758,
            "design_flow_temp": 55,
            "target_flow_temp": 48.54166666666667,
            "temp_rm_prev": 22.488371468978006,
            "variable_flow": True,
            "min_flow_rate": 0.05,
            "max_flow_rate": 0.3,
            "temp_diff_emit_dsgn": 10.0,
            "results": [],
        }

        self.heat_dict["BufferTank"] = {
            "daily_losses": 10,
            "volume": 100,
            "pump_fixed_flow_rate": 50,
            "pump_power_at_flow_rate": 10,
        }
        self.energysupply = EnergySupply(fuel_type=FuelType.MAINS_GAS, simulation_time=self.simtime)
        # Create a mock project object with the required methods
        mock_project = Mock()
        # Mock the private method _Project__update_temp_internal_air
        mock_project._Project__update_temp_internal_air = Mock(return_value=None)
        # Mock temp_internal_air_prev_timestep to return 20°C
        mock_project.temp_internal_air_prev_timestep = Mock(return_value=20.0)

        self.heat_pump = HeatPump(
            hp_dict=self.heat_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            throughput_exhaust_air=1000,
            project=mock_project,  # Pass the mock project object
        )

        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                energy, emitters_data_for_buffer_tank = self.heat_pump._HeatPump__energy_output_max(  # type: ignore[AttributeAccessIssue]
                    temp_output=temp_output,
                    temp_return_feed=temp_return_feed,
                    design_flow_temp_op_cond=emitters_data_for_buffer_tank["design_flow_temp"],
                    hybrid_boiler_service=hybrid_boiler_service,
                    emitters_data_for_buffer_tank=emitters_data_for_buffer_tank,
                    service_name="boiler_service_space",
                )
                self.assertAlmostEqual(energy, [8.2191174037396, 8.449538231375868][t_idx])

                self.assertEqual(
                    emitters_data_for_buffer_tank["results"]["flow_temp_increase_due_to_buffer"],
                    8.185825328614797,
                )
                self.assertEqual(
                    emitters_data_for_buffer_tank["results"]["pump_power_at_flow_rate"], 10
                )
                self.assertEqual(
                    emitters_data_for_buffer_tank["results"]["heat_loss_buffer_kWh"],
                    0.0964687074719922,
                )

    def test_energy_output_max_cost_schedule_hybrid_hp(self):
        """Test that energy_output_max returns the correct values with a cost_schedule_hybrid_hp"""
        temp_output = 300.0
        temp_return_feed = 295.0
        self.boiler = Boiler(
            boiler_dict=self.boiler_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_aux=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            ext_cond=self.extcond,
        )
        hybrid_boiler_service = BoilerServiceSpace(
            boiler=self.boiler, service_name="boiler_service_space", control=MagicMock()
        )

        cost_schedule_hybrid_hp = {
            "cost_schedule_start_day": 0,
            "cost_schedule_time_series_step": 1,
            "cost_schedule_hp": {"main": [16, 18, 24, {"value": 16, "repeat": 5}]},
            "cost_schedule_boiler": {"main": [{"value": 4, "repeat": 8}]},
        }

        self.energysupply = EnergySupply(fuel_type=FuelType.MAINS_GAS, simulation_time=self.simtime)
        self.heat_pump = HeatPump(
            hp_dict=self.heat_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            throughput_exhaust_air=1000,
            cost_schedule_hybrid_hp=cost_schedule_hybrid_hp,
            boiler=self.boiler,
        )

        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                energy = self.heat_pump._HeatPump__energy_output_max(  # type: ignore[AttributeAccessIssue]
                    temp_output=temp_output,
                    temp_return_feed=temp_return_feed,
                    design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,
                    hybrid_boiler_service=hybrid_boiler_service,
                    service_name="boiler_service_space",
                )
                self.assertAlmostEqual(energy, [11.203924743692589, 11.51438002341549][t_idx])

    def test_energy_output_max_cost_schedule_hybrid_hp_not_cost_effective(self):
        """Test that energy_output_max returns the correct values with a cost_schedule_hybrid_hp and not cost effective"""
        temp_output = 300.0
        temp_return_feed = 295.0
        self.boiler = Boiler(
            boiler_dict=self.boiler_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_aux=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            ext_cond=self.extcond,
        )
        hybrid_boiler_service = BoilerServiceSpace(
            boiler=self.boiler, service_name="boiler_service_space", control=MagicMock()
        )

        cost_schedule_hybrid_hp = {
            "cost_schedule_start_day": 0,
            "cost_schedule_time_series_step": 1,
            "cost_schedule_hp": {"main": [{"value": 40, "repeat": 8}]},
            "cost_schedule_boiler": {"main": [{"value": 5, "repeat": 8}]},
        }

        self.energysupply = EnergySupply(fuel_type=FuelType.MAINS_GAS, simulation_time=self.simtime)
        self.heat_pump = HeatPump(
            hp_dict=self.heat_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            throughput_exhaust_air=1000,
            cost_schedule_hybrid_hp=cost_schedule_hybrid_hp,
            boiler=self.boiler,
        )

        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                energy = self.heat_pump._HeatPump__energy_output_max(  # type: ignore[AttributeAccessIssue]
                    temp_output=temp_output,
                    temp_return_feed=temp_return_feed,
                    design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,
                    hybrid_boiler_service=hybrid_boiler_service,
                    service_name="boiler_service_space",
                )
                self.assertAlmostEqual(energy, [24.0, 24.0][t_idx])

    def test_energy_output_max_topup(self):
        """Test that energy_output_max returns the correct values with a TOPUP backup control type"""
        temp_output = 300.0
        temp_return_feed = 295.0
        self.extcond = MagicMock()
        self.boiler = Boiler(
            boiler_dict=self.boiler_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_aux=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            ext_cond=self.extcond,
        )
        hybrid_boiler_service = BoilerServiceSpace(
            boiler=self.boiler, service_name="boiler_service_space", control=MagicMock()
        )

        self.extcond.air_temp.return_value = -5

        self.heat_dict["backup_ctrl_type"] = HeatPumpBackupControlType.TOP_UP

        self.energysupply = EnergySupply(fuel_type=FuelType.MAINS_GAS, simulation_time=self.simtime)
        self.heat_pump = HeatPump(
            hp_dict=self.heat_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            throughput_exhaust_air=1000,
            boiler=self.boiler,
        )

        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                energy = self.heat_pump._HeatPump__energy_output_max(  # type: ignore[AttributeAccessIssue]
                    temp_output=temp_output,
                    temp_return_feed=temp_return_feed,
                    design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,
                    hybrid_boiler_service=hybrid_boiler_service,
                    service_name="boiler_service_space",
                )
                self.assertAlmostEqual(energy, [24.0, 24.0][t_idx])

    def test_cop_op_cond(self):
        """Check CoP at operating conditions"""
        # Check with type service type SPACE
        temp_spread_correction = MagicMock(return_value=1.0)
        service_type = (HeatingServiceType.SPACE,)
        temp_output = 320
        temp_source = 275

        cop_op_cond = self.heat_pump._HeatPump__cop_op_cond(  # type: ignore[AttributeAccessIssue]
            service_type=service_type,
            temp_output=temp_output,  # Kelvin
            temp_source=temp_source,  # Kelvin
            temp_spread_correction=temp_spread_correction,
            design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,  # Kelvin
        )
        self.assertAlmostEqual(cop_op_cond, 3.4835975137798934)

        # Check with sink type 'AIR'
        self.energy_supply_conn_name_auxiliary = "auxillary_cop_eff"
        self.heat_pump_sink_air = HeatPump(
            hp_dict=self.heat_dict_sinktype_air,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
        )
        service_type = HeatingServiceType.SPACE
        cop_op_cond = self.heat_pump_sink_air._HeatPump__cop_op_cond(  # type: ignore[AttributeAccessIssue]
            service_type=service_type,
            temp_output=temp_output,  # Kelvin
            temp_source=temp_source,  # Kelvin
            temp_spread_correction=temp_spread_correction,
            design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,  # Kelvin
        )
        self.assertAlmostEqual(cop_op_cond, 4.384741326956177)

    def test_cop_op_cond_lr_equal(self):
        """Test results for cop_op_cond if lr_below equals lr_above"""

        for data in self.heat_pump._HeatPump__test_data._HeatPumpTestData__testdata.values():  # type: ignore[AttributeAccessIssue]
            for value in data:
                value["theoretical_load_ratio"] = 1.1

        temp_spread_correction = MagicMock(return_value=1.0)
        service_type = (HeatingServiceType.SPACE,)
        temp_output = 320
        temp_source = 275
        cop_op_cond = self.heat_pump._HeatPump__cop_op_cond(  # type: ignore[AttributeAccessIssue]
            service_type=service_type,
            temp_output=temp_output,  # Kelvin
            temp_source=temp_source,  # Kelvin
            temp_spread_correction=temp_spread_correction,
            design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,  # Kelvin
        )
        self.assertAlmostEqual(cop_op_cond, 3.2295002426006794)

    def test_energy_output_limited(self):
        """Check energy output limited by upper temperature"""
        energy_output_required = 1.5
        temp_output = 320.0
        temp_used_for_scaling = 310.0
        temp_limit_upper = 340.0

        self.assertAlmostEqual(
            self.heat_pump._HeatPump__energy_output_limited(  # type: ignore[AttributeAccessIssue]
                energy_output_required=energy_output_required,
                temp_output=temp_output,
                temp_used_for_scaling=temp_used_for_scaling,
                temp_limit_upper=temp_limit_upper,
            ),
            1.5,
        )

        energy_output_required = 1.5
        temp_output = 320.0
        temp_used_for_scaling = 50.0
        temp_limit_upper = 310.0

        self.assertAlmostEqual(
            self.heat_pump._HeatPump__energy_output_limited(  # type: ignore[AttributeAccessIssue]
                energy_output_required=energy_output_required,
                temp_output=temp_output,
                temp_used_for_scaling=temp_used_for_scaling,
                temp_limit_upper=temp_limit_upper,
            ),
            1.4444444444444444,
        )

        energy_output_required = 1.5
        temp_output = 320.0
        temp_used_for_scaling = 320.0
        temp_limit_upper = 310.0

        self.assertAlmostEqual(
            self.heat_pump._HeatPump__energy_output_limited(  # type: ignore[AttributeAccessIssue]
                energy_output_required=energy_output_required,
                temp_output=temp_output,
                temp_used_for_scaling=temp_used_for_scaling,
                temp_limit_upper=temp_limit_upper,
            ),
            1.5,
        )
        energy_output_required = 1.5
        temp_output = 310
        temp_used_for_scaling = 320.0
        temp_limit_upper = 300.0

        self.assertAlmostEqual(
            self.heat_pump._HeatPump__energy_output_limited(  # type: ignore[AttributeAccessIssue]
                energy_output_required=energy_output_required,
                temp_output=temp_output,
                temp_used_for_scaling=temp_used_for_scaling,
                temp_limit_upper=temp_limit_upper,
            ),
            0,
        )

    def test_backup_heater_delay_time_elapsed(self):
        """Check if backup heater is available or still in delay period"""

        self.heat_pump._HeatPump__create_service_connection("service_backupheater")  # type: ignore[AttributeAccessIssue]
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.heat_pump._HeatPump__demand_energy(  # type: ignore[AttributeAccessIssue]
                    service_name="service_backupheater",
                    service_type=HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                    energy_output_required=500.0,
                    temp_output=330.0,  # Kelvin
                    temp_return_feed=330.0,  # Kelvin
                    temp_limit_upper=340.0,  # Kelvin
                    design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,  # Kelvin
                    time_constant_for_service=1560,
                    service_on=True,
                    temp_spread_correction=1.0,
                    temp_used_for_scaling=None,
                    hybrid_boiler_service=None,
                    emitters_data_for_buffer_tank=None,
                )

                self.assertEqual(
                    self.heat_pump._HeatPump__backup_heater_delay_time_elapsed(),  # type: ignore[AttributeAccessIssue]
                    [False, True][t_idx],
                )

                self.heat_pump.timestep_end()

    def test_outside_operating_limits(self):
        self.assertFalse(self.heat_pump._HeatPump__outside_operating_limits(temp_return_feed=300.0))  # type: ignore[AttributeAccessIssue]
        # Check with less temp_return_feed_max
        self.heat_dict_exhaust = {
            "source_type": SourceType.EXHAUST_AIR_MIXED,
            "sink_type": HeatPumpSinkType.WATER,
            "backup_ctrl_type": HeatPumpBackupControlType.SUBSTITUTE,
            "time_delay_backup": -1,
            "min_modulation_rate_20": 20.0,
            "temp_distribution_heat_network": 1.0,
            "modulating_control": True,
            "min_modulation_rate_35": 0.35,
            "min_modulation_rate_55": 0.4,
            "time_constant_onoff_operation": 140,
            "temp_return_feed_max": 10,
            "temp_lower_operating_limit": -5.0,
            "min_temp_diff_flow_return_for_hp_to_operate": 0.0,
            "var_flow_temp_ctrl_during_test": True,
            "power_heating_circ_pump": 0.015,
            "power_source_circ_pump": 0.01,
            "power_standby": 0.015,
            "power_crankcase_heater": 0.01,
            "power_off": 0.015,
            "power_max_backup": 3.0,
            "eahp_mixed_max_temp": 10,
            "eahp_mixed_min_temp": 0,
            "test_data_EN14825": [
                {
                    "air_flow_rate": 100.0,
                    "test_letter": "A",
                    "capacity": 8.4,
                    "cop": 4.6,
                    "design_flow_temp": 35,
                    "temp_outlet": 34,
                    "temp_source": 0,
                    "temp_test": -7,
                    "eahp_mixed_ext_air_ratio": 0.62,
                },
                {
                    "air_flow_rate": 100.0,
                    "test_letter": "B",
                    "capacity": 8.3,
                    "cop": 4.9,
                    "design_flow_temp": 35,
                    "temp_outlet": 30,
                    "temp_source": 0,
                    "temp_test": 2,
                    "eahp_mixed_ext_air_ratio": 0.62,
                },
                {
                    "air_flow_rate": 100.0,
                    "test_letter": "C",
                    "capacity": 8.3,
                    "cop": 5.1,
                    "design_flow_temp": 35,
                    "temp_outlet": 27,
                    "temp_source": 0,
                    "temp_test": 7,
                    "eahp_mixed_ext_air_ratio": 0.62,
                },
                {
                    "air_flow_rate": 100.0,
                    "test_letter": "D",
                    "capacity": 8.2,
                    "cop": 5.4,
                    "design_flow_temp": 35,
                    "temp_outlet": 24,
                    "temp_source": 0,
                    "temp_test": 12,
                    "eahp_mixed_ext_air_ratio": 0.62,
                },
                {
                    "air_flow_rate": 100.0,
                    "test_letter": "F",
                    "capacity": 8.4,
                    "cop": 4.6,
                    "design_flow_temp": 35,
                    "temp_outlet": 34,
                    "temp_source": 0,
                    "temp_test": -7,
                    "eahp_mixed_ext_air_ratio": 0.62,
                },
            ],
        }
        project = MagicMock()
        project.temp_internal_air_prev_timestep.return_value = 20
        self.energy_supply_conn_name_auxiliary = "aux_outside_operating_limit"
        self.heat_pump_exhaust = HeatPump(
            hp_dict=self.heat_dict_exhaust,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            throughput_exhaust_air=101,
            project=project,
        )

        self.assertTrue(
            self.heat_pump_exhaust._HeatPump__outside_operating_limits(temp_return_feed=300.0)  # type: ignore[AttributeAccessIssue]
        )

    def test_outside_operating_limits_sinktypes(self):
        """Test that outside_operating_limits returns the correct values for different sink types"""
        self.heat_pump._HeatPump__sink_type = HeatPumpSinkType.WATER  # type: ignore[AttributeAccessIssue]
        self.assertFalse(self.heat_pump._HeatPump__outside_operating_limits(temp_return_feed=300))  # type: ignore[AttributeAccessIssue]

        self.heat_pump._HeatPump__sink_type = HeatPumpSinkType.WATER  # type: ignore[AttributeAccessIssue]
        self.assertTrue(self.heat_pump._HeatPump__outside_operating_limits(temp_return_feed=350))  # type: ignore[AttributeAccessIssue]

        self.heat_pump._HeatPump__sink_type = HeatPumpSinkType.AIR  # type: ignore[AttributeAccessIssue]
        self.assertFalse(self.heat_pump._HeatPump__outside_operating_limits(temp_return_feed=350))  # type: ignore[AttributeAccessIssue]

    def test_outside_operating_limits_invalid_sinktype(self):
        """Test that outside_operating_limits throws on an invalid sink type"""
        with self.assertRaises(ValueError):
            self.heat_pump._HeatPump__sink_type = None  # type: ignore[AttributeAccessIssue]
            self.heat_pump._HeatPump__outside_operating_limits(temp_return_feed=350)  # type: ignore[AttributeAccessIssue]

    def test_load_ratio_and_mode(self):
        """Test that load_ratio_and_mode returns the correct values"""
        # Test without modulating ctrl
        self.heat_pump._HeatPump__modulating_ctrl = False  # type: ignore[AttributeAccessIssue]
        load_ratio, load_ratio_continuous_min, hp_operating_in_onoff_mode = (
            self.heat_pump._HeatPump__load_ratio_and_mode(  # type: ignore[AttributeAccessIssue]
                time_running_current_service=1.0,
                time_available_for_current_service=1.0,
                temp_output=50,
            )
        )

        self.assertAlmostEqual(load_ratio, 1.0)
        self.assertAlmostEqual(load_ratio_continuous_min, 1.0)
        self.assertAlmostEqual(hp_operating_in_onoff_mode, False)

        # Test with modulating ctrl
        self.heat_pump._HeatPump__modulating_ctrl = True  # type: ignore[AttributeAccessIssue]
        load_ratio, load_ratio_continuous_min, hp_operating_in_onoff_mode = (
            self.heat_pump._HeatPump__load_ratio_and_mode(  # type: ignore[AttributeAccessIssue]
                time_running_current_service=0.6,
                time_available_for_current_service=0.8,
                temp_output=50,
            )
        )

        self.assertAlmostEqual(load_ratio, 0.75)
        self.assertAlmostEqual(load_ratio_continuous_min, 0.35)
        self.assertAlmostEqual(hp_operating_in_onoff_mode, False)

        # Test with zero time available
        load_ratio, load_ratio_continuous_min, hp_operating_in_onoff_mode = (
            self.heat_pump._HeatPump__load_ratio_and_mode(  # type: ignore[AttributeAccessIssue]
                time_running_current_service=0.0,
                time_available_for_current_service=0.0,
                temp_output=50,
            )
        )

        self.assertAlmostEqual(load_ratio, 0.0)
        self.assertAlmostEqual(load_ratio_continuous_min, 0.35)
        self.assertAlmostEqual(hp_operating_in_onoff_mode, False)

        # Test with zero time available and non-zero running time
        self.assertRaises(ValueError, self.heat_pump._HeatPump__load_ratio_and_mode, 0.2, 0.0, 50)  # type: ignore[AttributeAccessIssue]

        # Test HP with no test data for 55 degC design flow temp
        heat_pump_no_55deg_data = HeatPump(
            hp_dict=self.heat_dict_heat_nw,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary="arbitrary name for testing",
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            energy_supply_heat_source=EnergySupply(
                simulation_time=self.simtime, fuel_type=FuelType.CUSTOM
            ),
        )
        load_ratio, load_ratio_continuous_min, hp_operating_in_onoff_mode = (
            heat_pump_no_55deg_data._HeatPump__load_ratio_and_mode(  # type: ignore[AttributeAccessIssue]
                time_running_current_service=0.2,
                time_available_for_current_service=0.8,
                temp_output=45,
            )
        )

        self.assertAlmostEqual(load_ratio, 0.25)
        self.assertAlmostEqual(load_ratio_continuous_min, 0.35)
        self.assertAlmostEqual(hp_operating_in_onoff_mode, True)

    def test_energy_input_compressor(self):
        """Test that energy_input_compressor returns the correct values for different parameters and sink types"""
        energy_input_HP, compressor_power_min_load = (
            self.heat_pump._HeatPump__energy_input_compressor(  # type: ignore[AttributeAccessIssue]
                service_on=True,
                use_backup_heater_only=False,
                hp_operating_in_onoff_mode=False,
                energy_delivered_HP=8.4,
                energy_delivered_HP_aggregated=8.4,
                thermal_capacity_op_cond=8.4,
                cop_op_cond=2.9,
                time_available_for_current_service=1.0,
                load_ratio=1.0,
                load_ratio_continuous_min=0.4,
                time_constant_for_service=1560,
                service_type=HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
            )
        )
        self.assertAlmostEqual(energy_input_HP, 2.896551724137931)
        self.assertAlmostEqual(compressor_power_min_load, 1.1586206896551725)

        energy_input_HP, compressor_power_min_load = (
            self.heat_pump._HeatPump__energy_input_compressor(  # type: ignore[AttributeAccessIssue]
                service_on=False,
                use_backup_heater_only=False,
                hp_operating_in_onoff_mode=False,
                energy_delivered_HP=8.4,
                energy_delivered_HP_aggregated=8.4,
                thermal_capacity_op_cond=8.4,
                cop_op_cond=2.9,
                time_available_for_current_service=1.0,
                load_ratio=1.0,
                load_ratio_continuous_min=0.4,
                time_constant_for_service=1560,
                service_type=HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
            )
        )
        self.assertAlmostEqual(energy_input_HP, 0.0)
        self.assertAlmostEqual(compressor_power_min_load, 1.1586206896551725)

        energy_input_HP, compressor_power_min_load = (
            self.heat_pump._HeatPump__energy_input_compressor(  # type: ignore[AttributeAccessIssue]
                service_on=False,
                use_backup_heater_only=False,
                hp_operating_in_onoff_mode=False,
                energy_delivered_HP=8.4,
                energy_delivered_HP_aggregated=8.4,
                thermal_capacity_op_cond=None,
                cop_op_cond=2.9,
                time_available_for_current_service=1.0,
                load_ratio=1.0,
                load_ratio_continuous_min=0.4,
                time_constant_for_service=1560,
                service_type=HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
            )
        )
        self.assertAlmostEqual(energy_input_HP, 0.0)
        self.assertAlmostEqual(compressor_power_min_load, 0.0)

        energy_input_HP, compressor_power_min_load = (
            self.heat_pump._HeatPump__energy_input_compressor(  # type: ignore[AttributeAccessIssue]
                service_on=True,
                use_backup_heater_only=False,
                hp_operating_in_onoff_mode=True,
                energy_delivered_HP=8.4,
                energy_delivered_HP_aggregated=8.4,
                thermal_capacity_op_cond=0.4,
                cop_op_cond=2.9,
                time_available_for_current_service=1.0,
                load_ratio=1.0,
                load_ratio_continuous_min=0.4,
                time_constant_for_service=1560,
                service_type=HeatingServiceType.SPACE,
            )
        )
        self.assertAlmostEqual(energy_input_HP, 0.13793103448275862)
        self.assertAlmostEqual(compressor_power_min_load, 0.05517241379310345)

        energy_input_HP, compressor_power_min_load = (
            self.heat_pump._HeatPump__energy_input_compressor(  # type: ignore[AttributeAccessIssue]
                service_on=True,
                use_backup_heater_only=False,
                hp_operating_in_onoff_mode=True,
                energy_delivered_HP=8.4,
                energy_delivered_HP_aggregated=8.4,
                thermal_capacity_op_cond=0.4,
                cop_op_cond=2.9,
                time_available_for_current_service=1.0,
                load_ratio=1.0,
                load_ratio_continuous_min=0.4,
                time_constant_for_service=1560,
                service_type=HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
            )
        )
        self.assertAlmostEqual(energy_input_HP, 0.13793103448275862)
        self.assertAlmostEqual(compressor_power_min_load, 0.05517241379310345)

        self.heat_pump._HeatPump__sink_type = HeatPumpSinkType.AIR  # type: ignore[AttributeAccessIssue]

        energy_input_HP, compressor_power_min_load = (
            self.heat_pump._HeatPump__energy_input_compressor(  # type: ignore[AttributeAccessIssue]
                service_on=True,
                use_backup_heater_only=False,
                hp_operating_in_onoff_mode=True,
                energy_delivered_HP=8.4,
                energy_delivered_HP_aggregated=12.0,
                thermal_capacity_op_cond=0.4,
                cop_op_cond=2.9,
                time_available_for_current_service=1.0,
                load_ratio=1.0,
                load_ratio_continuous_min=0.4,
                time_constant_for_service=1560,
                service_type=HeatingServiceType.SPACE,
            )
        )
        self.assertAlmostEqual(energy_input_HP, 0.09655172413793105)
        self.assertAlmostEqual(compressor_power_min_load, 0.05517241379310345)

        energy_input_HP, compressor_power_min_load = (
            self.heat_pump._HeatPump__energy_input_compressor(  # type: ignore[AttributeAccessIssue]
                service_on=True,
                use_backup_heater_only=False,
                hp_operating_in_onoff_mode=True,
                energy_delivered_HP=8.4,
                energy_delivered_HP_aggregated=8.4,
                thermal_capacity_op_cond=0.4,
                cop_op_cond=2.9,
                time_available_for_current_service=1.0,
                load_ratio=1.0,
                load_ratio_continuous_min=0.4,
                time_constant_for_service=1560,
                service_type=HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
            )
        )
        self.assertAlmostEqual(energy_input_HP, 0.13793103448275862)
        self.assertAlmostEqual(compressor_power_min_load, 0.05517241379310345)

    def test_inadequate_capacity(self):
        energy_output_required = 5.0
        thermal_capacity_op_cond = 5.0
        temp_output = 310.0
        time_available = 1.0
        temp_return_feed = 315.0
        hybrid_boiler_service = None
        time_start = 0.0

        self.assertFalse(
            self.heat_pump._HeatPump__inadequate_capacity(  # type: ignore[AttributeAccessIssue]
                energy_output_required=energy_output_required,
                thermal_capacity_op_cond=thermal_capacity_op_cond,
                temp_output=temp_output,
                time_available=time_available,
                temp_return_feed=temp_return_feed,
                time_start=time_start,
                hybrid_boiler_service=hybrid_boiler_service,
            )
        )

    @patch.object(HeatPump, "_HeatPump__backup_heater_delay_time_elapsed", return_value=True)
    @patch.object(HeatPump, "_HeatPump__backup_energy_output_max", return_value=5.0)
    def test_inadequate_capacity_TOP_UP(
        self, mock_backup_energy_output_max, mock_backup_heater_delay_time_elapsed
    ):
        """Function __inadequate_capacity can be tested with Mock as its function call
        __backup_energy_output_max references BoilerServiceWaterRegular/BoilerServiceSpace
        which inherits Boiler object.Inherited parameters cannot be accessed from TestHeatPump class"""

        self.heat_pump.__backup_ctrl = HeatPumpBackupControlType.TOP_UP
        result = self.heat_pump._HeatPump__inadequate_capacity(  # type: ignore[AttributeAccessIssue]
            energy_output_required=5.0,
            thermal_capacity_op_cond=1.0,
            temp_output=343,
            time_available=2,
            time_start=0.0,
            temp_return_feed=313,
            hybrid_boiler_service=None,
        )
        self.assertTrue(result)
        mock_backup_heater_delay_time_elapsed.assert_called_once()
        mock_backup_energy_output_max.assert_called_once_with(
            temp_output=343,
            temp_return_feed=313,
            time_available=2,
            time_start=0.0,
            hybrid_boiler_service=None,
        )

    @patch.object(HeatPump, "_HeatPump__backup_heater_delay_time_elapsed", return_value=True)
    @patch.object(HeatPump, "_HeatPump__backup_energy_output_max", return_value=5.0)
    def test_inadequate_capacity_substitute(
        self, mock_backup_energy_output_max, mock_backup_heater_delay_time_elapsed
    ):
        self.heat_pump.__backup_ctrl = HeatPumpBackupControlType.SUBSTITUTE
        result = self.heat_pump._HeatPump__inadequate_capacity(  # type: ignore[AttributeAccessIssue]
            energy_output_required=5.0,
            thermal_capacity_op_cond=1,
            temp_output=343,
            temp_return_feed=313,
            time_available=2,
            time_start=0.0,
            hybrid_boiler_service=None,
        )
        self.assertTrue(result)
        mock_backup_heater_delay_time_elapsed.assert_called_once()
        mock_backup_energy_output_max.assert_called_once_with(
            temp_output=343,
            temp_return_feed=313,
            time_available=2,
            time_start=0.0,
            hybrid_boiler_service=None,
        )

    @patch.object(HeatPump, "_HeatPump__backup_heater_delay_time_elapsed", return_value=False)
    @patch.object(HeatPump, "_HeatPump__backup_energy_output_max", return_value=5.0)
    def test_inadequate_capacity_no_delay_elapsed(
        self, mock_backup_energy_output_max, mock_backup_heater_delay_time_elapsed
    ):
        self.heat_pump.__backup_ctrl = HeatPumpBackupControlType.TOP_UP
        result = self.heat_pump._HeatPump__inadequate_capacity(  # type: ignore[AttributeAccessIssue]
            energy_output_required=5.0,
            thermal_capacity_op_cond=5.0,
            temp_output=343,
            temp_return_feed=313,
            time_available=2,
            time_start=0.0,
            hybrid_boiler_service=None,
        )
        self.assertFalse(result)
        mock_backup_heater_delay_time_elapsed.assert_called_once()
        mock_backup_energy_output_max.assert_called_once()

    @patch.object(HeatPump, "_HeatPump__backup_heater_delay_time_elapsed", return_value=True)
    @patch.object(HeatPump, "_HeatPump__backup_energy_output_max", return_value=5.0)
    def test_inadequate_capacity_insufficient_backup(
        self, mock_backup_energy_output_max, mock_backup_heater_delay_time_elapsed
    ):
        self.heat_pump.__backup_ctrl = HeatPumpBackupControlType.SUBSTITUTE
        result = self.heat_pump._HeatPump__inadequate_capacity(  # type: ignore[AttributeAccessIssue]
            energy_output_required=5.0,
            thermal_capacity_op_cond=5.0,
            temp_output=343,
            temp_return_feed=313,
            time_available=2,
            time_start=0.0,
            hybrid_boiler_service=None,
        )
        self.assertFalse(result)
        mock_backup_heater_delay_time_elapsed.assert_called_once()
        mock_backup_energy_output_max.assert_called_once_with(
            temp_output=343,
            temp_return_feed=313,
            time_available=2,
            time_start=0.0,
            hybrid_boiler_service=None,
        )

    def test_is_heat_pump_cost_effective_equal_cost(self):
        cop_op_cond = 3.0
        boiler_eff = 0.9
        self.cost_schedule_hybrid_hp = {
            "cost_schedule_start_day": 0,
            "cost_schedule_time_series_step": 1,
            "cost_schedule_hp": {"main": [16, 20, 24, {"value": 16, "repeat": 5}]},
            "cost_schedule_boiler": {"main": [{"value": 4, "repeat": 8}]},
        }

        self.energy_supply_conn_name_auxiliary = "HeatPump_auxiliary: CostSchedule"

        self.heat_pump_with_cost_schedule = HeatPump(
            hp_dict=self.heat_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            cost_schedule_hybrid_hp=self.cost_schedule_hybrid_hp,
        )

        self.heat_pump_with_cost_schedule.__backup_ctrl = HeatPumpBackupControlType.SUBSTITUTE
        self.assertFalse(
            self.heat_pump_with_cost_schedule._HeatPump__is_heat_pump_cost_effective(  # type: ignore[AttributeAccessIssue]
                cop_op_cond=cop_op_cond, boiler_eff=boiler_eff
            )
        )

        cop_op_cond = 16
        boiler_eff = 2.0

        self.assertTrue(
            self.heat_pump_with_cost_schedule._HeatPump__is_heat_pump_cost_effective(  # type: ignore[AttributeAccessIssue]
                cop_op_cond=cop_op_cond, boiler_eff=boiler_eff
            )
        )

    def test_use_backup_heater_only(self):
        cop_op_cond = 3.0
        energy_output_required = 4.0
        thermal_capacity_op_cond = 4.0
        temp_output = 320.0
        time_available = 1.0
        temp_return_feed = 320.0
        time_start = 0.0

        self.assertFalse(
            self.heat_pump._HeatPump__use_backup_heater_only(  # type: ignore[AttributeAccessIssue]
                cop_op_cond=cop_op_cond,
                energy_output_required=energy_output_required,
                thermal_capacity_op_cond=thermal_capacity_op_cond,
                temp_output=temp_output,
                time_available=time_available,
                time_start=time_start,
                temp_return_feed=temp_return_feed,
            )
        )

        self.cost_schedule_hybrid_hp = {
            "cost_schedule_start_day": 0,
            "cost_schedule_time_series_step": 1,
            "cost_schedule_hp": {"main": [16, 20, 24, {"value": 16, "repeat": 5}]},
            "cost_schedule_boiler": {"main": [{"value": 4, "repeat": 8}]},
        }

        self.energy_supply_conn_name_auxiliary = "HeatPump_auxiliary: CostSchedule_1"

        self.heat_pump_with_cost_schedule = HeatPump(
            hp_dict=self.heat_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            cost_schedule_hybrid_hp=self.cost_schedule_hybrid_hp,
        )

        self.assertTrue(
            self.heat_pump_with_cost_schedule._HeatPump__use_backup_heater_only(  # type: ignore[AttributeAccessIssue]
                cop_op_cond=cop_op_cond,
                energy_output_required=energy_output_required,
                thermal_capacity_op_cond=thermal_capacity_op_cond,
                temp_output=temp_output,
                time_available=time_available,
                time_start=time_start,
                temp_return_feed=temp_return_feed,
                boiler_eff=3.0,
            )
        )

    def test_run_demand_energy_calc(self):
        # Test with hybrid_boiler_service and boiler_eff
        self.energy_supply_conn_name_auxiliary = MagicMock(spec=EnergySupplyConnection)
        self.boiler = Boiler(
            boiler_dict=self.boiler_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_aux=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            ext_cond=self.extcond,
        )

        self.ctrl = SetpointTimeControl(
            schedule=[21.0, 22.0],
            simulation_time=self.simtime,
            start_day=0,  # start_day
            time_series_step=1.0,  # time_series_step
        )
        self.boilerservicespace = self.boiler.create_service_space_heating(
            service_name="service_boilerspace", control=self.ctrl
        )

        self.heat_pump_with_boiler = HeatPump(
            hp_dict=self.heat_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            boiler=self.boiler,
        )
        self.simtime.reset()
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.heat_pump_with_boiler._HeatPump__run_demand_energy_calc(  # type: ignore[AttributeAccessIssue]
                        service_name="service_boilerspace",
                        service_type=HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                        energy_output_required=1.0,
                        temp_output=320.0,  # Kelvin
                        temp_return_feed=310.0,  # Kelvin
                        temp_limit_upper=340.0,  # Kelvin
                        design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,  # Kelvin
                        time_constant_for_service=1560,
                        service_on=True,  # bool - is service allowed to run?
                        temp_spread_correction=1.0,
                        temp_used_for_scaling=None,
                        hybrid_boiler_service=self.boilerservicespace,
                        boiler_eff=1.0,
                        additional_time_unavailable=0.0,
                    ),
                    [
                        {
                            "service_name": "service_boilerspace",
                            "service_type": HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                            "service_on": True,
                            "energy_output_required": 1.0,
                            "temp_output": 320.0,
                            "temp_source": 273.15,
                            "cop_op_cond": 3.39519472564502,
                            "thermal_capacity_op_cond": 9.231749514150996,
                            "time_running_full_load": 0.10832182984028522,
                            "time_available_for_capacity_calc": 1.0,
                            "time_available_for_load_ratio_calc": 1.0,
                            "time_constant_for_service": 1560,
                            "use_backup_heater_only": False,
                            "energy_delivered_HP": 1.0,
                            "energy_input_backup": 0.0,
                            "energy_delivered_backup": 0.0,
                            "energy_delivered_total": 1.0,
                            "energy_heating_circ_pump": 0.0016248274476042782,
                            "energy_source_circ_pump": 0.0010832182984028523,
                            "energy_output_required_boiler": 0.0,
                            "energy_heating_warm_air_fan": 0,
                        },
                        {
                            "service_name": "service_boilerspace",
                            "service_type": HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                            "service_on": True,
                            "energy_output_required": 1.0,
                            "temp_output": 320.0,
                            "temp_source": 275.65,
                            "cop_op_cond": 3.5153226325240556,
                            "thermal_capacity_op_cond": 9.487556781989081,
                            "time_running_full_load": 0.10540121371377431,
                            "time_available_for_capacity_calc": 1.0,
                            "time_available_for_load_ratio_calc": 1.0,
                            "time_constant_for_service": 1560,
                            "use_backup_heater_only": False,
                            "energy_delivered_HP": 1.0,
                            "energy_input_backup": 0.0,
                            "energy_delivered_backup": 0.0,
                            "energy_delivered_total": 1.0,
                            "energy_heating_circ_pump": 0.0015810182057066145,
                            "energy_source_circ_pump": 0.0010540121371377432,
                            "energy_output_required_boiler": 0.0,
                            "energy_heating_warm_air_fan": 0,
                        },
                    ][t_idx],
                )

        # Check without boiler and service_on True
        self.simtime.reset()
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.heat_pump._HeatPump__run_demand_energy_calc(  # type: ignore[AttributeAccessIssue]
                        service_name="service_no_boiler",
                        service_type=HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                        energy_output_required=1.0,
                        temp_output=330.0,  # Kelvin
                        temp_return_feed=330.0,  # Kelvin
                        temp_limit_upper=340.0,  # Kelvin
                        design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,  # Kelvin
                        time_constant_for_service=1560,
                        service_on=True,  # bool - is service allowed to run?
                        temp_spread_correction=1.0,
                        temp_used_for_scaling=None,
                        hybrid_boiler_service=None,
                        boiler_eff=None,
                        additional_time_unavailable=0.0,
                    ),
                    [
                        {
                            "service_name": "service_no_boiler",
                            "service_type": HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                            "service_on": True,
                            "energy_output_required": 1.0,
                            "temp_output": 330.0,
                            "temp_source": 273.15,
                            "cop_op_cond": 3.1824426759289044,
                            "thermal_capacity_op_cond": 8.417674488123662,
                            "time_running_full_load": 0.11879765621857688,
                            "time_available_for_capacity_calc": 1.0,
                            "time_available_for_load_ratio_calc": 1.0,
                            "time_constant_for_service": 1560,
                            "use_backup_heater_only": False,
                            "energy_delivered_HP": 0.9999999999999999,
                            "energy_input_backup": 0.0,
                            "energy_delivered_backup": 0.0,
                            "energy_delivered_total": 0.9999999999999999,
                            "energy_heating_circ_pump": 0.001781964843278653,
                            "energy_source_circ_pump": 0.0011879765621857687,
                            "energy_output_required_boiler": 0.0,
                            "energy_heating_warm_air_fan": 0,
                        },
                        {
                            "service_name": "service_no_boiler",
                            "service_type": HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                            "service_on": True,
                            "energy_output_required": 1.0,
                            "temp_output": 330.0,
                            "temp_source": 275.65,
                            "cop_op_cond": 3.197134104416267,
                            "thermal_capacity_op_cond": 8.650924134797519,
                            "time_running_full_load": 0.11559458670751663,
                            "time_available_for_capacity_calc": 1.0,
                            "time_available_for_load_ratio_calc": 1.0,
                            "time_constant_for_service": 1560,
                            "use_backup_heater_only": False,
                            "energy_delivered_HP": 1.0,
                            "energy_input_backup": 0.0,
                            "energy_delivered_backup": 0.0,
                            "energy_delivered_total": 1.0,
                            "energy_heating_circ_pump": 0.0017339188006127494,
                            "energy_source_circ_pump": 0.0011559458670751662,
                            "energy_output_required_boiler": 0.0,
                            "energy_heating_warm_air_fan": 0,
                        },
                    ][t_idx],
                )

        # Check without modulating control
        self.heat_dict_modcontrol: HeatPumpCharacteristics = {
            "source_type": "OutsideAir",
            "eahp_mixed_max_temp": 1.0,
            "eahp_mixed_min_temp": 1.0,
            "min_modulation_rate_20": 20.0,
            "temp_distribution_heat_network": 1.0,
            "sink_type": HeatPumpSinkType.WATER,
            "backup_ctrl_type": HeatPumpBackupControlType.SUBSTITUTE,
            "time_delay_backup": 2.0,
            "modulating_control": False,
            "min_modulation_rate_35": 0.35,
            "min_modulation_rate_55": 0.4,
            "time_constant_onoff_operation": 140,
            "temp_return_feed_max": 70.0,
            "temp_lower_operating_limit": -5.0,
            "min_temp_diff_flow_return_for_hp_to_operate": 0.0,
            "var_flow_temp_ctrl_during_test": True,
            "power_heating_circ_pump": 0.015,
            "power_source_circ_pump": 0.01,
            "power_standby": 0.015,
            "power_crankcase_heater": 0.01,
            "power_off": 0.015,
            "power_max_backup": 3.0,
            "test_data_EN14825": [
                {
                    "test_letter": "A",
                    "capacity": 8.4,
                    "cop": 4.6,
                    "design_flow_temp": 35,
                    "temp_outlet": 34,
                    "temp_source": 0,
                    "temp_test": -7,
                },
                {
                    "test_letter": "B",
                    "capacity": 8.3,
                    "cop": 4.9,
                    "design_flow_temp": 35,
                    "temp_outlet": 30,
                    "temp_source": 0,
                    "temp_test": 2,
                },
                {
                    "test_letter": "C",
                    "capacity": 8.3,
                    "cop": 5.1,
                    "design_flow_temp": 35,
                    "temp_outlet": 27,
                    "temp_source": 0,
                    "temp_test": 7,
                },
                {
                    "test_letter": "D",
                    "capacity": 8.2,
                    "cop": 5.4,
                    "design_flow_temp": 35,
                    "temp_outlet": 24,
                    "temp_source": 0,
                    "temp_test": 12,
                },
                {
                    "test_letter": "F",
                    "capacity": 8.4,
                    "cop": 4.6,
                    "design_flow_temp": 35,
                    "temp_outlet": 34,
                    "temp_source": 0,
                    "temp_test": -7,
                },
            ],
        }

        self.energy_supply_conn_name_auxiliary = "HeatPump_auxiliary: modulating_control"

        self.heat_pump_mod_ctrl = HeatPump(
            hp_dict=self.heat_dict_modcontrol,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
        )
        self.simtime.reset()
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.heat_pump_mod_ctrl._HeatPump__run_demand_energy_calc(  # type: ignore[AttributeAccessIssue]
                        service_name="service_backup_modctrl",
                        service_type=HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                        energy_output_required=1.0,
                        temp_output=330.0,  # Kelvin
                        temp_return_feed=330.0,  # Kelvin
                        temp_limit_upper=340.0,  # Kelvin
                        design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,  # Kelvin
                        time_constant_for_service=1560,
                        service_on=True,
                        temp_spread_correction=1.0,
                        temp_used_for_scaling=None,
                        hybrid_boiler_service=None,
                        boiler_eff=None,
                        additional_time_unavailable=0.0,
                    ),
                    [
                        {
                            "service_name": "service_backup_modctrl",
                            "service_type": HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                            "service_on": True,
                            "energy_output_required": 1.0,
                            "temp_output": 330.0,
                            "temp_source": 273.15,
                            "cop_op_cond": 3.9929681311183423,
                            "thermal_capacity_op_cond": 8.857000000000003,
                            "time_available_for_capacity_calc": 1.0,
                            "time_available_for_load_ratio_calc": 1.0,
                            "time_running_full_load": 0.11290504685559441,
                            "time_constant_for_service": 1560,
                            "use_backup_heater_only": False,
                            "energy_delivered_HP": 1.0,
                            "energy_input_backup": 0.0,
                            "energy_delivered_backup": 0.0,
                            "energy_delivered_total": 1.0,
                            "energy_heating_circ_pump": 0.0016935757028339162,
                            "energy_source_circ_pump": 0.0011290504685559442,
                            "energy_output_required_boiler": 0.0,
                            "energy_heating_warm_air_fan": 0,
                        },
                        {
                            "service_name": "service_backup_modctrl",
                            "service_type": HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                            "service_on": True,
                            "energy_output_required": 1.0,
                            "temp_output": 330.0,
                            "temp_source": 275.65,
                            "cop_op_cond": 4.089173762601537,
                            "thermal_capacity_op_cond": 8.807000000000002,
                            "time_running_full_load": 0.1135460429204042,
                            "time_available_for_capacity_calc": 1.0,
                            "time_available_for_load_ratio_calc": 1.0,
                            "time_constant_for_service": 1560,
                            "use_backup_heater_only": False,
                            "energy_delivered_HP": 1.0,
                            "energy_input_backup": 0.0,
                            "energy_delivered_backup": 0.0,
                            "energy_delivered_total": 1.0,
                            "energy_heating_circ_pump": 0.001703190643806063,
                            "energy_source_circ_pump": 0.001135460429204042,
                            "energy_output_required_boiler": 0.0,
                            "energy_heating_warm_air_fan": 0,
                        },
                    ][t_idx],
                )

        self.simtime.reset()
        # Check the results with service off and more energy_output_required
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.heat_pump._HeatPump__run_demand_energy_calc(  # type: ignore[AttributeAccessIssue]
                        service_name="service_erengy_output_required",
                        service_type=HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                        energy_output_required=50,
                        temp_output=330.0,  # Kelvin
                        temp_return_feed=330.0,  # Kelvin
                        temp_limit_upper=340.0,  # Kelvin
                        design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,  # Kelvin
                        time_constant_for_service=1560,
                        service_on=False,  # bool - is service allowed to run?
                        temp_spread_correction=1.0,
                        temp_used_for_scaling=None,
                        hybrid_boiler_service=None,
                        boiler_eff=None,
                        additional_time_unavailable=0.0,
                    ),
                    [
                        {
                            "service_name": "service_erengy_output_required",
                            "service_type": HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                            "service_on": False,
                            "energy_output_required": 50.0,
                            "temp_output": 330.0,
                            "temp_source": 273.15,
                            "cop_op_cond": 3.1824426759289044,
                            "thermal_capacity_op_cond": 8.417674488123662,
                            "time_running_full_load": 0.0,
                            "time_available_for_capacity_calc": 1.0,
                            "time_available_for_load_ratio_calc": 1.0,
                            "time_constant_for_service": 1560,
                            "use_backup_heater_only": False,
                            "energy_delivered_HP": 0.0,
                            "energy_input_backup": 0.0,
                            "energy_delivered_backup": 0.0,
                            "energy_delivered_total": 0.0,
                            "energy_heating_circ_pump": 0.0,
                            "energy_source_circ_pump": 0.0,
                            "energy_output_required_boiler": 0.0,
                            "energy_heating_warm_air_fan": 0,
                        },
                        {
                            "service_name": "service_erengy_output_required",
                            "service_type": HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                            "service_on": False,
                            "energy_output_required": 50.0,
                            "temp_output": 330.0,
                            "temp_source": 275.65,
                            "cop_op_cond": 3.197134104416267,
                            "thermal_capacity_op_cond": 8.650924134797519,
                            "time_running_full_load": 0.0,
                            "time_available_for_capacity_calc": 1.0,
                            "time_available_for_load_ratio_calc": 1.0,
                            "time_constant_for_service": 1560,
                            "use_backup_heater_only": False,
                            "energy_delivered_HP": 0.0,
                            "energy_input_backup": 0.0,
                            "energy_delivered_backup": 0.0,
                            "energy_delivered_total": 0.0,
                            "energy_heating_circ_pump": 0.0,
                            "energy_source_circ_pump": 0.0,
                            "energy_output_required_boiler": 0.0,
                            "energy_heating_warm_air_fan": 0,
                        },
                    ][t_idx],
                )

        # Check service off with boiler
        self.energy_supply_conn_name_auxiliary = MagicMock(spec=EnergySupplyConnection)
        self.boiler = Boiler(
            boiler_dict=self.boiler_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_aux=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            ext_cond=self.extcond,
        )

        self.ctrl = SetpointTimeControl(
            schedule=[21.0, 22.0],
            simulation_time=self.simtime,
            start_day=0,  # start_day
            time_series_step=1.0,  # time_series_step
        )
        self.boilerservicespace = self.boiler.create_service_space_heating(
            service_name="service_boilerspace_service_off", control=self.ctrl
        )

        self.heat_pump_with_boiler = HeatPump(
            hp_dict=self.heat_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            boiler=self.boiler,
        )
        self.simtime.reset()
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.heat_pump_with_boiler._HeatPump__run_demand_energy_calc(  # type: ignore[AttributeAccessIssue]
                        service_name="service_boilerspace_service_off",
                        service_type=HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                        energy_output_required=1.0,
                        temp_output=330.0,  # Kelvin
                        temp_return_feed=330.0,  # Kelvin
                        temp_limit_upper=340.0,  # Kelvin
                        design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,  # Kelvin
                        time_constant_for_service=1560,
                        service_on=False,  # bool - is service allowed to run?
                        temp_spread_correction=1.0,
                        temp_used_for_scaling=None,
                        hybrid_boiler_service=self.boilerservicespace,
                        boiler_eff=1.0,
                        additional_time_unavailable=0.0,
                    ),
                    [
                        {
                            "service_name": "service_boilerspace_service_off",
                            "service_type": HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                            "service_on": False,
                            "energy_output_required": 1.0,
                            "temp_output": 330.0,
                            "temp_source": 273.15,
                            "cop_op_cond": 3.1824426759289044,
                            "thermal_capacity_op_cond": 8.417674488123662,
                            "time_running_full_load": 0.0,
                            "time_available_for_capacity_calc": 1.0,
                            "time_available_for_load_ratio_calc": 1.0,
                            "time_constant_for_service": 1560,
                            "use_backup_heater_only": False,
                            "energy_delivered_HP": 0.0,
                            "energy_input_backup": 0.0,
                            "energy_delivered_backup": 0.0,
                            "energy_delivered_total": 0.0,
                            "energy_heating_circ_pump": 0.0,
                            "energy_source_circ_pump": 0.0,
                            "energy_output_required_boiler": 0.0,
                            "energy_heating_warm_air_fan": 0,
                        },
                        {
                            "service_name": "service_boilerspace_service_off",
                            "service_type": HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                            "service_on": False,
                            "energy_output_required": 1.0,
                            "temp_output": 330.0,
                            "temp_source": 275.65,
                            "cop_op_cond": 3.197134104416267,
                            "thermal_capacity_op_cond": 8.650924134797519,
                            "time_running_full_load": 0.0,
                            "time_available_for_capacity_calc": 1.0,
                            "time_available_for_load_ratio_calc": 1.0,
                            "time_constant_for_service": 1560,
                            "use_backup_heater_only": False,
                            "energy_delivered_HP": 0.0,
                            "energy_input_backup": 0.0,
                            "energy_delivered_backup": 0.0,
                            "energy_delivered_total": 0.0,
                            "energy_heating_circ_pump": 0.0,
                            "energy_source_circ_pump": 0.0,
                            "energy_output_required_boiler": 0.0,
                            "energy_heating_warm_air_fan": 0,
                        },
                    ][t_idx],
                )

        # Check wtih backup_ctrl_type Substitute
        self.heat_dict_with_sub: HeatPumpCharacteristics = {
            "temp_distribution_heat_network": 1.0,
            "eahp_mixed_max_temp": 1.0,
            "eahp_mixed_min_temp": 1.0,
            "source_type": SourceType.OUTSIDE_AIR,
            "sink_type": HeatPumpSinkType.WATER,
            "backup_ctrl_type": HeatPumpBackupControlType.SUBSTITUTE,
            "time_delay_backup": 2.0,
            "modulating_control": True,
            "min_modulation_rate_35": 0.35,
            "min_modulation_rate_55": 0.4,
            "min_modulation_rate_20": 20.0,
            "time_constant_onoff_operation": 140,
            "temp_return_feed_max": 70.0,
            "temp_lower_operating_limit": -5.0,
            "min_temp_diff_flow_return_for_hp_to_operate": 0.0,
            "var_flow_temp_ctrl_during_test": True,
            "power_heating_circ_pump": 0.015,
            "power_source_circ_pump": 0.01,
            "power_standby": 0.015,
            "power_crankcase_heater": 0.01,
            "power_off": 0.015,
            "power_max_backup": 3.0,
            "test_data_EN14825": [
                {
                    "test_letter": "A",
                    "capacity": 8.4,
                    "cop": 4.6,
                    "design_flow_temp": 35,
                    "temp_outlet": 34,
                    "temp_source": 0,
                    "temp_test": -7,
                },
                {
                    "test_letter": "B",
                    "capacity": 8.3,
                    "cop": 4.9,
                    "design_flow_temp": 35,
                    "temp_outlet": 30,
                    "temp_source": 0,
                    "temp_test": 2,
                },
                {
                    "test_letter": "C",
                    "capacity": 8.3,
                    "cop": 5.1,
                    "design_flow_temp": 35,
                    "temp_outlet": 27,
                    "temp_source": 0,
                    "temp_test": 7,
                },
                {
                    "test_letter": "D",
                    "capacity": 8.2,
                    "cop": 5.4,
                    "design_flow_temp": 35,
                    "temp_outlet": 24,
                    "temp_source": 0,
                    "temp_test": 12,
                },
                {
                    "test_letter": "F",
                    "capacity": 8.4,
                    "cop": 4.6,
                    "design_flow_temp": 35,
                    "temp_outlet": 34,
                    "temp_source": 0,
                    "temp_test": -7,
                },
            ],
        }
        self.energy_supply_conn_name_auxiliary = "HeatPump_auxiliary: backup"

        self.heat_pump_backup = HeatPump(
            hp_dict=self.heat_dict_with_sub,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
        )
        self.simtime.reset()
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.heat_pump_backup._HeatPump__run_demand_energy_calc(  # type: ignore[AttributeAccessIssue]
                        service_name="service_backup_substitute",
                        service_type=HeatingServiceType.SPACE,
                        energy_output_required=1.0,
                        temp_output=330.0,  # Kelvin
                        temp_return_feed=330.0,  # Kelvin
                        temp_limit_upper=340.0,  # Kelvin
                        design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,  # Kelvin
                        time_constant_for_service=1560,
                        service_on=True,
                        temp_spread_correction=1.0,
                        temp_used_for_scaling=None,
                        hybrid_boiler_service=None,
                        boiler_eff=None,
                        additional_time_unavailable=0.0,
                    ),
                    [
                        {
                            "service_name": "service_backup_substitute",
                            "service_type": HeatingServiceType.SPACE,
                            "service_on": True,
                            "energy_output_required": 1.0,
                            "temp_output": 330.0,
                            "temp_source": 273.15,
                            "cop_op_cond": 3.9929681311183423,
                            "thermal_capacity_op_cond": 6.773123981338176,
                            "time_running_full_load": 0.1476423586450323,
                            "time_available_for_capacity_calc": 1.0,
                            "time_available_for_load_ratio_calc": 1.0,
                            "time_constant_for_service": 1560,
                            "use_backup_heater_only": False,
                            "energy_delivered_HP": 1.0,
                            "energy_input_backup": 0.0,
                            "energy_delivered_backup": 0.0,
                            "energy_delivered_total": 1.0,
                            "energy_heating_circ_pump": 0.0022146353796754846,
                            "energy_source_circ_pump": 0.0014764235864503231,
                            "energy_output_required_boiler": 0.0,
                            "energy_heating_warm_air_fan": 0,
                        },
                        {
                            "service_name": "service_backup_substitute",
                            "service_type": HeatingServiceType.SPACE,
                            "service_on": True,
                            "energy_output_required": 1.0,
                            "temp_output": 330.0,
                            "temp_source": 275.65,
                            "cop_op_cond": 4.089173762601537,
                            "thermal_capacity_op_cond": 6.9608039370972525,
                            "time_running_full_load": 0.1436615668300253,
                            "time_available_for_capacity_calc": 1.0,
                            "time_available_for_load_ratio_calc": 1.0,
                            "time_constant_for_service": 1560,
                            "use_backup_heater_only": False,
                            "energy_delivered_HP": 1.0,
                            "energy_input_backup": 0.0,
                            "energy_delivered_backup": 0.0,
                            "energy_delivered_total": 1.0,
                            "energy_heating_circ_pump": 0.002154923502450379,
                            "energy_source_circ_pump": 0.0014366156683002528,
                            "energy_output_required_boiler": 0.0,
                            "energy_heating_warm_air_fan": 0,
                        },
                    ][t_idx],
                )

    def test_run_demand_energy_calc_other(self):
        """Test the results of the remaining branches in run_demand_energy_calc"""

        emitters_data_for_buffer_tank = {
            "temp_emitter_req": 43,
            "power_req_from_buffer_tank": 6,
            "design_flow_temp": 55,
            "target_flow_temp": 48,
            "temp_rm_prev": 22,
            "variable_flow": True,
            "min_flow_rate": 0.05,
            "max_flow_rate": 0.3,
            "temp_diff_emit_dsgn": 10.0,
            "results": {
                "flow_temp_increase_due_to_buffer": 10,
                "pump_power_at_flow_rate": 20,
                "heat_loss_buffer_kWh": 30,
            },
        }

        self.energy_supply_conn_name_auxiliary = MagicMock(spec=EnergySupplyConnection)
        self.boiler = Boiler(
            boiler_dict=self.boiler_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_aux=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            ext_cond=self.extcond,
        )

        self.ctrl = SetpointTimeControl(
            schedule=[21.0, 22.0], simulation_time=self.simtime, start_day=0, time_series_step=1.0
        )
        self.boilerservicespace = self.boiler.create_service_space_heating(
            service_name="service_boilerspace", control=self.ctrl
        )

        self.heat_pump_with_boiler = HeatPump(
            hp_dict=self.heat_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            boiler=self.boiler,
        )

        # Test with HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR
        results = self.heat_pump_with_boiler._HeatPump__run_demand_energy_calc(  # type: ignore[AttributeAccessIssue]
            service_name="service_boilerspace",
            service_type=HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
            energy_output_required=1.0,
            temp_output=320.0,
            temp_return_feed=310.0,
            temp_limit_upper=340.0,
            design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,
            time_constant_for_service=1560,
            service_on=True,
            temp_spread_correction=1.0,
            temp_used_for_scaling=None,
            hybrid_boiler_service=self.boilerservicespace,
            boiler_eff=1.0,
            additional_time_unavailable=0.0,
        )

        self.assertEqual(
            results,
            {
                "service_name": "service_boilerspace",
                "service_type": HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                "service_on": True,
                "energy_output_required": 1.0,
                "time_constant_for_service": 1560,
                "temp_output": 320.0,
                "temp_source": 273.15,
                "cop_op_cond": 3.39519472564502,
                "thermal_capacity_op_cond": 9.231749514150996,
                "time_available_for_capacity_calc": 1.0,
                "time_available_for_load_ratio_calc": 1.0,
                "time_running_full_load": 0.10832182984028522,
                "use_backup_heater_only": False,
                "energy_delivered_HP": 1.0,
                "energy_input_backup": 0.0,
                "energy_delivered_backup": 0.0,
                "energy_delivered_total": 1.0,
                "energy_heating_circ_pump": 0.0016248274476042782,
                "energy_source_circ_pump": 0.0010832182984028523,
                "energy_output_required_boiler": 0.0,
                "energy_heating_warm_air_fan": 0,
            },
        )

        # Test with service_on set to false
        results = self.heat_pump_with_boiler._HeatPump__run_demand_energy_calc(  # type: ignore[AttributeAccessIssue]
            service_name="service_boilerspace",
            service_type=HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
            energy_output_required=1.0,
            temp_output=None,
            temp_return_feed=310.0,
            temp_limit_upper=340.0,
            design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,
            time_constant_for_service=1560,
            service_on=False,
            temp_spread_correction=1.0,
            temp_used_for_scaling=None,
            hybrid_boiler_service=self.boilerservicespace,
            boiler_eff=1.0,
            additional_time_unavailable=0.0,
        )

        self.assertEqual(
            results,
            {
                "service_name": "service_boilerspace",
                "service_type": HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                "service_on": False,
                "energy_output_required": 1.0,
                "time_constant_for_service": 1560,
                "temp_output": None,
                "temp_source": 273.15,
                "cop_op_cond": None,
                "thermal_capacity_op_cond": None,
                "time_available_for_capacity_calc": 1.0,
                "time_available_for_load_ratio_calc": 1.0,
                "time_running_full_load": 0.0,
                "use_backup_heater_only": False,
                "energy_delivered_HP": 0.0,
                "energy_input_backup": 0.0,
                "energy_delivered_backup": 0.0,
                "energy_delivered_total": 0.0,
                "energy_heating_circ_pump": 0.0,
                "energy_source_circ_pump": 0.0,
                "energy_output_required_boiler": 0.0,
                "energy_heating_warm_air_fan": 0,
            },
        )

        # Test with an invalid backup_ctrl
        self.heat_pump_with_boiler._HeatPump__backup_ctrl = None  # type: ignore[AttributeAccessIssue]
        with self.assertRaises(ValueError):
            self.heat_pump_with_boiler._HeatPump__run_demand_energy_calc(  # type: ignore[AttributeAccessIssue]
                service_name="service_boilerspace",
                service_type=HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                energy_output_required=1.0,
                temp_output=300,
                temp_return_feed=310.0,
                temp_limit_upper=340.0,
                design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,
                time_constant_for_service=1560,
                service_on=False,
                temp_spread_correction=1.0,
                temp_used_for_scaling=None,
                hybrid_boiler_service=self.boilerservicespace,
                boiler_eff=1.0,
                additional_time_unavailable=0.0,
            )

        self.assertEqual(
            results,
            {
                "service_name": "service_boilerspace",
                "service_type": HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                "service_on": False,
                "energy_output_required": 1.0,
                "time_constant_for_service": 1560,
                "temp_output": None,
                "temp_source": 273.15,
                "cop_op_cond": None,
                "thermal_capacity_op_cond": None,
                "time_available_for_capacity_calc": 1.0,
                "time_available_for_load_ratio_calc": 1.0,
                "time_running_full_load": 0.0,
                "use_backup_heater_only": False,
                "energy_delivered_HP": 0.0,
                "energy_input_backup": 0.0,
                "energy_delivered_backup": 0.0,
                "energy_delivered_total": 0.0,
                "energy_heating_circ_pump": 0.0,
                "energy_source_circ_pump": 0.0,
                "energy_output_required_boiler": 0.0,
                "energy_heating_warm_air_fan": 0,
            },
        )

        # Test with an invalid backup_ctrl
        with self.assertRaises(ValueError):
            self.heat_pump_with_boiler._HeatPump__run_demand_energy_calc(  # type: ignore[AttributeAccessIssue]
                service_name="service_boilerspace",
                service_type=HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                energy_output_required=1.0,
                temp_output=330,
                temp_return_feed=310.0,
                temp_limit_upper=340.0,
                design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,
                time_constant_for_service=1560,
                service_on=True,
                temp_spread_correction=1.0,
                temp_used_for_scaling=None,
                hybrid_boiler_service=self.boilerservicespace,
                boiler_eff=1.0,
                additional_time_unavailable=0.0,
            )

        # Test with HeatPumpBackupControlType.SUBSTITUTE and HeatPumpSinkType.AIR
        self.heat_pump_with_boiler._HeatPump__backup_ctrl = HeatPumpBackupControlType.SUBSTITUTE  # type: ignore[AttributeAccessIssue]
        self.heat_pump_with_boiler._HeatPump__sink_type = HeatPumpSinkType.AIR  # type: ignore[AttributeAccessIssue]
        results = self.heat_pump_with_boiler._HeatPump__run_demand_energy_calc(  # type: ignore[AttributeAccessIssue]
            service_name="service_boilerspace",
            service_type=HeatingServiceType.SPACE,
            energy_output_required=1.0,
            temp_output=320.0,
            temp_return_feed=310.0,
            temp_limit_upper=340.0,
            design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,
            time_constant_for_service=1560,
            service_on=True,
            temp_spread_correction=1.0,
            temp_used_for_scaling=None,
            hybrid_boiler_service=self.boilerservicespace,
            boiler_eff=1.0,
            additional_time_unavailable=0.0,
        )

        self.assertEqual(
            results,
            {
                "service_name": "service_boilerspace",
                "service_type": HeatingServiceType.SPACE,
                "service_on": True,
                "energy_output_required": 1.0,
                "time_constant_for_service": 1560,
                "temp_output": 320.0,
                "temp_source": 273.15,
                "cop_op_cond": 3.39519472564502,
                "thermal_capacity_op_cond": 9.231749514150996,
                "time_available_for_capacity_calc": 1.0,
                "time_available_for_load_ratio_calc": 1.0,
                "time_running_full_load": 0.10832182984028522,
                "use_backup_heater_only": False,
                "energy_delivered_HP": 1.0,
                "energy_input_backup": 0.0,
                "energy_delivered_backup": 0.0,
                "energy_delivered_total": 1.0,
                "energy_heating_circ_pump": 0,
                "energy_source_circ_pump": 0.0010832182984028523,
                "energy_output_required_boiler": 0.0,
                "energy_heating_warm_air_fan": 0.0,
            },
        )

        buffer_tank = MagicMock()
        buffer_tank.get_buffer_loss.return_value = 5
        self.heat_pump_with_boiler._HeatPump__buffer_tank = buffer_tank  # type: ignore[AttributeAccessIssue]

        # Test with a buffer tank and emitters_data_for_buffer_tank
        self.heat_pump_with_boiler._HeatPump__time_running_continuous = 1  # type: ignore[AttributeAccessIssue]
        results = self.heat_pump_with_boiler._HeatPump__run_demand_energy_calc(  # type: ignore[AttributeAccessIssue]
            service_name="service_boilerspace",
            service_type=HeatingServiceType.SPACE,
            energy_output_required=1.0,
            temp_output=320.0,
            temp_return_feed=310.0,
            temp_limit_upper=340.0,
            design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,
            time_constant_for_service=1560,
            service_on=True,
            temp_spread_correction=1.0,
            temp_used_for_scaling=None,
            hybrid_boiler_service=self.boilerservicespace,
            boiler_eff=1.0,
            additional_time_unavailable=0.0,
            emitters_data_for_buffer_tank=emitters_data_for_buffer_tank,
        )

        buffer_tank.update_buffer_loss.assert_called_with(buffer_loss=35.0)

        self.assertEqual(
            results,
            {
                "service_name": "service_boilerspace",
                "service_type": HeatingServiceType.SPACE,
                "service_on": True,
                "energy_output_required": 36.0,
                "time_constant_for_service": 1560,
                "temp_output": 330.0,
                "temp_source": 273.15,
                "cop_op_cond": 3.1824426759289044,
                "thermal_capacity_op_cond": 8.417674488123662,
                "time_available_for_capacity_calc": 1.0,
                "time_available_for_load_ratio_calc": 1.0,
                "time_running_full_load": 0.0,
                "use_backup_heater_only": True,
                "energy_delivered_HP": 0.0,
                "energy_input_backup": 0.0,
                "energy_delivered_backup": 0.0,
                "energy_delivered_total": 0.0,
                "energy_heating_circ_pump": 0,
                "energy_source_circ_pump": 0.0,
                "energy_output_required_boiler": 24.0,
                "energy_heating_warm_air_fan": 0.0,
            },
        )

        # Test with a buffer tank and emitters_data_for_buffer_tank, and service_on set to False
        results = self.heat_pump_with_boiler._HeatPump__run_demand_energy_calc(  # type: ignore[AttributeAccessIssue]
            service_name="service_boilerspace",
            service_type=HeatingServiceType.SPACE,
            energy_output_required=1.0,
            temp_output=320.0,
            temp_return_feed=310.0,
            temp_limit_upper=340.0,
            design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,
            time_constant_for_service=1560,
            service_on=False,
            temp_spread_correction=1.0,
            temp_used_for_scaling=None,
            hybrid_boiler_service=self.boilerservicespace,
            boiler_eff=1.0,
            additional_time_unavailable=0.0,
            emitters_data_for_buffer_tank=emitters_data_for_buffer_tank,
        )

        buffer_tank.update_buffer_loss.assert_called_with(buffer_loss=0.0)

        self.assertEqual(
            results,
            {
                "service_name": "service_boilerspace",
                "service_type": HeatingServiceType.SPACE,
                "service_on": False,
                "energy_output_required": 1.0,
                "time_constant_for_service": 1560,
                "temp_output": 330.0,
                "temp_source": 273.15,
                "cop_op_cond": 3.1824426759289044,
                "thermal_capacity_op_cond": 8.417674488123662,
                "time_available_for_capacity_calc": 1.0,
                "time_available_for_load_ratio_calc": 1.0,
                "time_running_full_load": 0.0,
                "use_backup_heater_only": False,
                "energy_delivered_HP": 0.0,
                "energy_input_backup": 0.0,
                "energy_delivered_backup": 0.0,
                "energy_delivered_total": 0.0,
                "energy_heating_circ_pump": 0,
                "energy_source_circ_pump": 0.0,
                "energy_output_required_boiler": 0.0,
                "energy_heating_warm_air_fan": 0.0,
            },
        )

        # Test with a buffer tank and energy delivered greater than buffer heat loss.
        results = self.heat_pump_with_boiler._HeatPump__run_demand_energy_calc(  # type: ignore[AttributeAccessIssue]
            service_name="service_boilerspace",
            service_type=HeatingServiceType.SPACE,
            energy_output_required=1.0,
            temp_output=100.0,
            temp_return_feed=310.0,
            temp_limit_upper=340.0,
            design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,
            time_constant_for_service=1560,
            service_on=True,
            temp_spread_correction=1.0,
            temp_used_for_scaling=None,
            hybrid_boiler_service=self.boilerservicespace,
            boiler_eff=1.0,
            additional_time_unavailable=0,
            emitters_data_for_buffer_tank=emitters_data_for_buffer_tank,
        )

        buffer_tank.update_buffer_loss.assert_called_with(buffer_loss=0.0)

        self.assertEqual(
            results,
            {
                "service_name": "service_boilerspace",
                "service_type": HeatingServiceType.SPACE,
                "service_on": True,
                "energy_output_required": 36.0,
                "time_constant_for_service": 1560,
                "temp_output": 110.0,
                "temp_source": 273.15,
                "cop_op_cond": 1.0,
                "thermal_capacity_op_cond": 227.27721117933888,
                "time_available_for_capacity_calc": 1.0,
                "time_available_for_load_ratio_calc": 1.0,
                "time_running_full_load": 0.1583968749581025,
                "use_backup_heater_only": False,
                "energy_delivered_HP": 36.0,
                "energy_input_backup": 0.0,
                "energy_delivered_backup": 0.0,
                "energy_delivered_total": 1.0,
                "energy_heating_circ_pump": 0,
                "energy_source_circ_pump": 0.0015839687495810251,
                "energy_output_required_boiler": 0.0,
                "energy_heating_warm_air_fan": 0.0,
            },
        )

    def test_demand_energy(self):
        self.energy_supply_conn_name_auxiliary = MagicMock(spec=EnergySupplyConnection)
        self.boiler = Boiler(
            boiler_dict=self.boiler_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_aux=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            ext_cond=self.extcond,
        )

        self.ctrl = SetpointTimeControl(
            schedule=[21.0, 22.0],
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1.0,
        )
        self.boilerservicespace = self.boiler.create_service_space_heating(
            service_name="service_boilerspace", control=self.ctrl
        )

        self.heat_pump_with_boiler = HeatPump(
            hp_dict=self.heat_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            boiler=self.boiler,
        )
        self.heat_pump_with_boiler._HeatPump__create_service_connection(  # type: ignore[AttributeAccessIssue]
            service_name="service_boiler_demand_energy"
        )

        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertAlmostEqual(
                    self.heat_pump_with_boiler._HeatPump__demand_energy(  # type: ignore[AttributeAccessIssue]
                        service_name="service_boiler_demand_energy",
                        service_type=HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                        energy_output_required=1.0,
                        temp_output=330.0,  # Kelvin
                        temp_return_feed=330.0,  # Kelvin
                        temp_limit_upper=340.0,  # Kelvin
                        design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,  # Kelvin
                        time_constant_for_service=1560,
                        service_on=True,
                        temp_spread_correction=1.0,
                        temp_used_for_scaling=None,
                        hybrid_boiler_service=self.boilerservicespace,
                    ),
                    [1.0, 1.0][t_idx],
                )
        self.assertEqual(
            self.heat_pump_with_boiler.service_results,
            [
                {
                    "service_name": "service_boiler_demand_energy",
                    "service_type": HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                    "service_on": True,
                    "energy_output_required": 1.0,
                    "temp_output": 330.0,
                    "temp_source": 273.15,
                    "cop_op_cond": 3.1824426759289044,
                    "thermal_capacity_op_cond": 8.417674488123662,
                    "time_running_full_load": 0.11879765621857688,
                    "time_available_for_capacity_calc": 1.0,
                    "time_available_for_load_ratio_calc": 1.0,
                    "time_constant_for_service": 1560,
                    "use_backup_heater_only": False,
                    "energy_delivered_HP": 0.9999999999999999,
                    "energy_input_backup": 0.0,
                    "energy_delivered_backup": 0.0,
                    "energy_delivered_total": 0.9999999999999999,
                    "energy_heating_circ_pump": 0.001781964843278653,
                    "energy_source_circ_pump": 0.0011879765621857687,
                    "energy_output_required_boiler": 0.0,
                    "energy_heating_warm_air_fan": 0,
                    "energy_output_delivered_boiler": 0.0,
                },
                {
                    "service_name": "service_boiler_demand_energy",
                    "service_type": HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                    "service_on": True,
                    "energy_output_required": 1.0,
                    "temp_output": 330.0,
                    "temp_source": 275.65,
                    "cop_op_cond": 3.197134104416267,
                    "thermal_capacity_op_cond": 8.650924134797519,
                    "time_running_full_load": 0.11559458670751663,
                    "time_available_for_capacity_calc": 0.8812023437814231,
                    "time_available_for_load_ratio_calc": 0.8812023437814231,
                    "time_constant_for_service": 1560,
                    "use_backup_heater_only": False,
                    "energy_delivered_HP": 1.0,
                    "energy_input_backup": 0.0,
                    "energy_delivered_backup": 0.0,
                    "energy_delivered_total": 1.0,
                    "energy_heating_circ_pump": 0.0017339188006127494,
                    "energy_source_circ_pump": 0.0011559458670751662,
                    "energy_output_required_boiler": 0.0,
                    "energy_heating_warm_air_fan": 0,
                    "energy_output_delivered_boiler": 0.0,
                },
            ],
        )

    def test_demand_energy_hybrid_boiler_service(self):
        """Test that demand_energy returns the correct results for different types of hybrid boiler services and backup ctrls"""
        self.energy_supply_conn_name_auxiliary = MagicMock(spec=EnergySupplyConnection)
        self.boiler = Boiler(
            boiler_dict=self.boiler_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_aux=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            ext_cond=self.extcond,
        )

        self.ctrl = SetpointTimeControl(
            schedule=[21.0, 22.0],
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1.0,
        )
        self.boilerservicespace = self.boiler.create_service_space_heating(
            service_name="service_boilerspace", control=self.ctrl
        )

        self.boilerservicespace = self.boiler.create_service_hot_water_regular(
            service_name="service_water",
            cold_feed=MagicMock(),
            controlmin=self.ctrl,
            controlmax=self.ctrl,
        )

        self.heat_pump_with_boiler = HeatPump(
            hp_dict=self.heat_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            boiler=self.boiler,
        )
        self.heat_pump_with_boiler._HeatPump__create_service_connection(  # type: ignore[AttributeAccessIssue]
            service_name="service_boiler_demand_energy"
        )

        self.heat_pump_with_boiler._HeatPump__backup_ctrl = None  # type: ignore[AttributeAccessIssue]

        with self.assertRaises(ValueError):
            self.heat_pump_with_boiler._HeatPump__demand_energy(  # type: ignore[AttributeAccessIssue]
                service_name="service_boiler_demand_energy",
                service_type=HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                energy_output_required=1.0,
                temp_output=330.0,  # Kelvin
                temp_return_feed=330.0,  # Kelvin
                temp_limit_upper=340.0,  # Kelvin
                design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,  # Kelvin
                time_constant_for_service=1560,
                service_on=True,
                temp_spread_correction=1.0,
                temp_used_for_scaling=None,
                hybrid_boiler_service=self.boilerservicespace,
            )

        self.heat_pump_with_boiler._HeatPump__backup_ctrl = HeatPumpBackupControlType.SUBSTITUTE  # type: ignore[AttributeAccessIssue]

        results = self.heat_pump_with_boiler._HeatPump__demand_energy(  # type: ignore[AttributeAccessIssue]
            service_name="service_boiler_demand_energy",
            service_type=HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
            energy_output_required=1.0,
            temp_output=330.0,  # Kelvin
            temp_return_feed=330.0,  # Kelvin
            temp_limit_upper=340.0,  # Kelvin
            design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,  # Kelvin
            time_constant_for_service=1560,
            service_on=True,
            temp_spread_correction=1.0,
            temp_used_for_scaling=None,
            hybrid_boiler_service=self.boilerservicespace,
        )

        self.assertAlmostEqual(results, 1.0)

        self.assertEqual(
            self.heat_pump_with_boiler.total_time_running_current_timestep_full_load,
            0.11879765621857688,
        )

    def test_throughput_factor(self):
        """Test that throughput_factor returns the correct values based on the time running and overvent ratio"""
        self.heat_pump._HeatPump__total_time_running_current_timestep_full_load = 2  # type: ignore[AttributeAccessIssue]
        self.heat_pump._HeatPump__overvent_ratio = 0.8  # type: ignore[AttributeAccessIssue]
        self.assertAlmostEqual(self.heat_pump.throughput_factor(), 0.6)

        self.heat_pump._HeatPump__total_time_running_current_timestep_full_load = 3  # type: ignore[AttributeAccessIssue]
        self.heat_pump._HeatPump__overvent_ratio = 0.7  # type: ignore[AttributeAccessIssue]
        self.assertAlmostEqual(self.heat_pump.throughput_factor(), 0.09999999999999964)

    def test_running_time_throughput_factor(self):
        """Check the cumulative running time and throughput factor (exhaust air HPs only)"""

        self.energy_supply_conn_name_auxiliary = "HeatPump_auxiliary: exhaust_runtime_throughput"
        project = MagicMock()
        project.temp_internal_air_prev_timestep.return_value = 30

        self.heat_pump_exhaust = HeatPump(
            hp_dict=self.heat_dict_exhaust,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            throughput_exhaust_air=101,
            project=project,
        )

        time_running, throughput_factor_zone = (
            self.heat_pump_exhaust._HeatPump__running_time_throughput_factor(  # type: ignore[AttributeAccessIssue]
                space_heat_running_time_cumulative=0,
                service_name="service_runtime_throughput",
                service_type=HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                energy_output_required=1.0,
                temp_output=330.0,  # Kelvin
                temp_return_feed=330.0,  # Kelvin
                temp_limit_upper=340.0,  # Kelvin
                design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,  # Kelvin
                time_constant_for_service=1350,
                service_on=True,
                volume_heated_by_service=100.0,
                temp_spread_correction=1.0,
            )
        )
        self.assertAlmostEqual(time_running, 0.1305986895949177)
        self.assertAlmostEqual(throughput_factor_zone, 1.0)

    def test_calc_throughput_factor(self):
        self.assertAlmostEqual(
            self.heat_pump._HeatPump__calc_throughput_factor(time_running=10),  # type: ignore[AttributeAccessIssue]
            1.0,
        )

    def test_calc_energy_input(self):
        self.heat_pump._HeatPump__energy_supply_connections = {  # type: ignore[AttributeAccessIssue]
            "service_water": MagicMock(),
            "service1": MagicMock(),
            "service2": MagicMock(),
        }
        self.heat_pump._HeatPump__service_results = [  # type: ignore[AttributeAccessIssue]
            {
                "service_name": "service_water",
                "service_type": HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                "service_on": True,
                "energy_output_required": 1.0,
                "temp_output": 330.0,
                "temp_source": 273.15,
                "cop_op_cond": 2.9706605881515196,
                "thermal_capacity_op_cond": 8.417674488123662,
                "time_available_for_capacity_calc": 0.5,
                "time_available_for_load_ratio_calc": 0.5,
                "time_running_full_load": 0.11879765621857688,
                "time_constant_for_service": 1560,
                "use_backup_heater_only": False,
                "energy_delivered_HP": 0.9999999999999999,
                "energy_input_backup": 0.0,
                "energy_delivered_backup": 0.0,
                "energy_delivered_total": 0.9999999999999999,
                "energy_heating_circ_pump": 0.001781964843278653,
                "energy_source_circ_pump": 0.0011879765621857687,
                "energy_output_required_boiler": 0.0,
                "energy_heating_warm_air_fan": 0,
                "energy_output_delivered_boiler": 0.0,
            },
            {
                "service_name": "service1",
                "service_type": HeatingServiceType.SPACE,
                "service_on": True,
                "energy_output_required": 1.0,
                "temp_output": 330.0,
                "temp_source": 275.65,
                "cop_op_cond": 3.091723311370327,
                "thermal_capacity_op_cond": 6.9608039370972525,
                "time_available_for_capacity_calc": 0.38120234378142312,
                "time_available_for_load_ratio_calc": 0.38120234378142312,
                "time_running_full_load": 0.07,
                "time_constant_for_service": 1560,
                "use_backup_heater_only": False,
                "energy_delivered_HP": 1.0,
                "energy_input_backup": 0.0,
                "energy_delivered_backup": 0.0,
                "energy_delivered_total": 1.0,
                "energy_heating_circ_pump": 0.0022146353796754846,
                "energy_source_circ_pump": 0.0014764235864503231,
                "energy_output_required_boiler": 0.0,
                "energy_heating_warm_air_fan": 0,
            },
            {
                "service_name": "service2",
                "service_type": HeatingServiceType.SPACE,
                "service_on": True,
                "energy_output_required": 0.97,
                "temp_output": 330.0,
                "temp_source": 275.65,
                "cop_op_cond": 3.091723311370327,
                "thermal_capacity_op_cond": 6.9608039370972525,
                "time_available_for_capacity_calc": 0.23355998513639082,
                "time_available_for_load_ratio_calc": 0.23355998513639082,
                "time_running_full_load": 0.05,
                "time_constant_for_service": 1560,
                "use_backup_heater_only": False,
                "energy_delivered_HP": 1.0,
                "energy_input_backup": 0.0,
                "energy_delivered_backup": 0.0,
                "energy_delivered_total": 1.0,
                "energy_heating_circ_pump": 0.002154923502450379,
                "energy_source_circ_pump": 0.0014366156683002528,
                "energy_output_required_boiler": 0.0,
                "energy_heating_warm_air_fan": 0,
            },
        ]
        self.heat_pump._HeatPump__calc_energy_input()  # type: ignore[AttributeAccessIssue]
        self.assertEqual(
            self.heat_pump.service_results,
            [
                {
                    "service_name": "service_water",
                    "service_type": HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                    "service_on": True,
                    "energy_output_required": 1.0,
                    "temp_output": 330.0,
                    "temp_source": 273.15,
                    "cop_op_cond": 2.9706605881515196,
                    "thermal_capacity_op_cond": 8.417674488123662,
                    "time_available_for_capacity_calc": 0.5,
                    "time_available_for_load_ratio_calc": 0.5,
                    "time_running_full_load": 0.11879765621857688,
                    "time_running_part_load": 0.11879765621857688,
                    "compressor_power_min_load": 2.83360358355901,
                    "time_constant_for_service": 1560,
                    "use_backup_heater_only": False,
                    "hp_operating_in_onoff_mode": False,
                    "load_ratio": 1.0,
                    "load_ratio_continuous_min": 1.0,
                    "energy_input_HP": 0.33662546437937074,
                    "energy_delivered_HP": 0.9999999999999999,
                    "energy_input_backup": 0.0,
                    "energy_delivered_backup": 0.0,
                    "energy_input_total": 0.33959540578483516,
                    "energy_delivered_total": 0.9999999999999999,
                    "energy_heating_circ_pump": 0.001781964843278653,
                    "energy_source_circ_pump": 0.0011879765621857687,
                    "energy_output_required_boiler": 0.0,
                    "energy_heating_warm_air_fan": 0,
                    "energy_output_delivered_boiler": 0.0,
                },
                {
                    "service_name": "service1",
                    "service_type": HeatingServiceType.SPACE,
                    "service_on": True,
                    "energy_output_required": 1.0,
                    "temp_output": 330.0,
                    "temp_source": 275.65,
                    "time_constant_for_service": 1560,
                    "cop_op_cond": 3.091723311370327,
                    "thermal_capacity_op_cond": 6.9608039370972525,
                    "time_available_for_capacity_calc": 0.38120234378142315,
                    "time_available_for_load_ratio_calc": 0.38120234378142315,
                    "time_running_full_load": 0.07,
                    "time_running_part_load": 0.17500000000000002,
                    "compressor_power_min_load": 0.9005726885711587,
                    "load_ratio_continuous_min": 0.4,
                    "load_ratio": 0.3147934475156495,
                    "use_backup_heater_only": False,
                    "hp_operating_in_onoff_mode": True,
                    "energy_input_HP": 0.13840863263212141,
                    "energy_delivered_HP": 1.0,
                    "energy_input_backup": 0.0,
                    "energy_delivered_backup": 0.0,
                    "energy_input_total": 0.1420996915982472,
                    "energy_delivered_total": 1.0,
                    "energy_heating_circ_pump": 0.0022146353796754846,
                    "energy_source_circ_pump": 0.0014764235864503231,
                    "energy_output_required_boiler": 0.0,
                    "energy_heating_warm_air_fan": 0,
                },
                {
                    "service_name": "service2",
                    "service_type": HeatingServiceType.SPACE,
                    "service_on": True,
                    "energy_output_required": 0.97,
                    "temp_output": 330.0,
                    "temp_source": 275.65,
                    "time_constant_for_service": 1560,
                    "cop_op_cond": 3.091723311370327,
                    "thermal_capacity_op_cond": 6.9608039370972525,
                    "time_available_for_capacity_calc": 0.2335599851363908,
                    "time_available_for_load_ratio_calc": 0.2335599851363908,
                    "time_running_full_load": 0.05,
                    "time_running_part_load": 0.125,
                    "compressor_power_min_load": 0.9005726885711587,
                    "load_ratio_continuous_min": 0.4,
                    "load_ratio": 0.3147934475156495,
                    "use_backup_heater_only": False,
                    "hp_operating_in_onoff_mode": True,
                    "energy_input_HP": 0.13840863263212141,
                    "energy_delivered_HP": 1.0,
                    "energy_input_backup": 0.0,
                    "energy_delivered_backup": 0.0,
                    "energy_input_total": 0.14200017180287205,
                    "energy_delivered_total": 1.0,
                    "energy_heating_circ_pump": 0.002154923502450379,
                    "energy_source_circ_pump": 0.0014366156683002528,
                    "energy_output_required_boiler": 0.0,
                    "energy_heating_warm_air_fan": 0,
                },
            ],
        )
        self.heat_pump._HeatPump__energy_supply_connections[  # type: ignore[AttributeAccessIssue]
            "service_water"
        ].demand_energy.assert_called_once_with(amount_demanded=0.33959540578483516)
        self.heat_pump._HeatPump__energy_supply_connections[  # type: ignore[AttributeAccessIssue]
            "service1"
        ].demand_energy.assert_called_once_with(amount_demanded=0.1420996915982472)
        self.heat_pump._HeatPump__energy_supply_connections[  # type: ignore[AttributeAccessIssue]
            "service2"
        ].demand_energy.assert_called_once_with(amount_demanded=0.14200017180287205)

    def test_calculate_energy_input_error(self):
        self.heat_pump._HeatPump__service_results = [  # type: ignore[AttributeAccessIssue]
            {
                "service_name": "service_water",
                "service_type": HeatingServiceType.DOMESTIC_HOT_WATER_COMBI,
                "service_on": True,
                "energy_output_required": 1.0,
                "temp_output": 330.0,
                "temp_source": 273.15,
                "cop_op_cond": 2.9706605881515196,
                "thermal_capacity_op_cond": 8.417674488123662,
                "time_available_for_capacity_calc": 0.5,
                "time_available_for_load_ratio_calc": 0.5,
                "time_running_full_load": 0.11879765621857688,
                "time_constant_for_service": 1560,
                "use_backup_heater_only": False,
                "energy_delivered_HP": 0.9999999999999999,
                "energy_input_backup": 0.0,
                "energy_delivered_backup": 0.0,
                "energy_delivered_total": 0.9999999999999999,
                "energy_heating_circ_pump": 0.001781964843278653,
                "energy_source_circ_pump": 0.0011879765621857687,
                "energy_output_required_boiler": 0.0,
                "energy_heating_warm_air_fan": 0,
                "energy_output_delivered_boiler": 0.0,
            }
        ]

        with self.assertRaises(ValueError):
            self.heat_pump._HeatPump__calc_energy_input()  # type: ignore[AttributeAccessIssue]

    def test_calc_auxiliary_energy(self):
        energy_standby, energy_crankcase_heater_mode, energy_off_mode = (
            self.heat_pump._HeatPump__calc_auxiliary_energy(  # type: ignore[AttributeAccessIssue]
                timestep=1,
                time_remaining_current_timestep_part_load=0.5,
            )
        )

        self.assertAlmostEqual(energy_standby, 0.0)
        self.assertAlmostEqual(energy_crankcase_heater_mode, 0.0)
        self.assertAlmostEqual(energy_off_mode, 0.015)

    def test_calc_auxiliary_energy_invalid_service_type(self):
        """Test that calc_auxiliary_energy throws on an invalid service type"""
        with self.assertRaises(ValueError):
            self.heat_pump._HeatPump__service_results = [{"service_type": None}]  # type: ignore[AttributeAccessIssue]
            self.heat_pump._HeatPump__calc_auxiliary_energy(  # type: ignore[AttributeAccessIssue]
                timestep=1, time_remaining_current_timestep_part_load=0.5
            )

    def test_extract_energy_from_source(self):
        self.energy_supply_conn_name_auxiliary = "HeatPump_auxiliary: hp1"

        self.energy_supply_heat_source = EnergySupply(
            simulation_time=self.simtime, fuel_type=FuelType.CUSTOM
        )
        self.heat_pump_with_nw = HeatPump(
            hp_dict=self.heat_dict_heat_nw,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            energy_supply_heat_source=self.energy_supply_heat_source,
        )

        self.heat_pump_with_nw._HeatPump__create_service_connection(  # type: ignore[AttributeAccessIssue]
            service_name="service_extract_energy"
        )
        self.heat_pump_with_nw._HeatPump__demand_energy(  # type: ignore[AttributeAccessIssue]
            service_name="service_extract_energy",
            service_type=HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
            energy_output_required=1.0,
            temp_output=330.0,  # Kelvin
            temp_return_feed=330.0,  # Kelvin
            temp_limit_upper=340.0,  # Kelvin
            design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,  # Kelvin
            time_constant_for_service=1560,
            service_on=True,
            temp_spread_correction=1.0,
            temp_used_for_scaling=None,
            hybrid_boiler_service=None,
        )
        self.heat_pump_with_nw._HeatPump__calc_energy_input()  # type: ignore[AttributeAccessIssue]
        test_service_results = self.heat_pump_with_nw.service_results
        # Call the method under test
        self.heat_pump_with_nw._HeatPump__extract_energy_from_source()  # type: ignore[AttributeAccessIssue]
        actual_service_results = self.heat_pump_with_nw.service_results

        self.assertEqual(test_service_results, actual_service_results)

        # Check demand_energy function is called
        self.heat_pump._HeatPump__service_results = [  # type: ignore[AttributeAccessIssue]
            {"service_name": "service1", "energy_delivered_HP": 100, "energy_input_HP": 30},
        ]
        self.heat_pump._HeatPump__energy_supply_heat_source_connections = {  # type: ignore[AttributeAccessIssue]
            "service1": MagicMock(),
        }
        self.heat_pump._HeatPump__extract_energy_from_source()  # type: ignore[AttributeAccessIssue]
        self.heat_pump.energy_supply_heat_source_connections[
            "service1"
        ].demand_energy.assert_called_once_with(amount_demanded=100 - 30)

        # Test that value is set to zero when energy_delivered_HP < energy_input_HP
        self.heat_pump._HeatPump__service_results = [  # type: ignore[AttributeAccessIssue]
            {"service_name": "service1", "energy_delivered_HP": 30, "energy_input_HP": 100},
        ]
        self.heat_pump._HeatPump__extract_energy_from_source()  # type: ignore[AttributeAccessIssue]
        self.heat_pump.energy_supply_heat_source_connections[
            "service1"
        ].demand_energy.assert_called_with(amount_demanded=0.0)

    def test_timestep_end(self):
        # Call demand_energy function to record the state of variables
        self.heat_pump._HeatPump__create_service_connection(  # type: ignore[AttributeAccessIssue]
            service_name="servicetimestep_demand_energy"
        )
        self.heat_pump._HeatPump__demand_energy(  # type: ignore[AttributeAccessIssue]
            service_name="servicetimestep_demand_energy",
            service_type=HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
            energy_output_required=5.0,
            temp_output=330.0,  # Kelvin
            temp_return_feed=330.0,  # Kelvin
            temp_limit_upper=340.0,  # Kelvin
            design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,  # Kelvin
            time_constant_for_service=1560,
            service_on=True,
            temp_spread_correction=1.0,
            temp_used_for_scaling=None,
            hybrid_boiler_service=None,
        )

        self.assertAlmostEqual(
            self.heat_pump.total_time_running_current_timestep_full_load,
            0.5939882810928845,
        )
        self.assertEqual(
            self.heat_pump.service_results,
            [
                {
                    "service_name": "servicetimestep_demand_energy",
                    "service_type": HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                    "service_on": True,
                    "energy_output_required": 5.0,
                    "temp_output": 330.0,
                    "temp_source": 273.15,
                    "cop_op_cond": 3.1824426759289044,
                    "thermal_capacity_op_cond": 8.417674488123662,
                    "time_running_full_load": 0.5939882810928845,
                    "time_available_for_capacity_calc": 1.0,
                    "time_available_for_load_ratio_calc": 1.0,
                    "time_constant_for_service": 1560,
                    "use_backup_heater_only": False,
                    "energy_delivered_HP": 5.0,
                    "energy_input_backup": 0.0,
                    "energy_delivered_backup": 0.0,
                    "energy_delivered_total": 5.0,
                    "energy_heating_circ_pump": 0.008909824216393266,
                    "energy_source_circ_pump": 0.005939882810928845,
                    "energy_output_required_boiler": 0.0,
                    "energy_heating_warm_air_fan": 0,
                    "energy_output_delivered_boiler": 0.0,
                }
            ],
        )

        # Call the method under test
        self.heat_pump.timestep_end()

        self.assertAlmostEqual(self.heat_pump.total_time_running_current_timestep_full_load, 0.0)
        self.assertEqual(self.heat_pump.service_results, [])

    def test_timestep_end_extract_energy(self):
        """Test that timestep_end extracts energy from source for energy_supply_heat_source"""

        with patch.object(
            self.heat_pump, "_HeatPump__extract_energy_from_source"
        ) as mock_extract_energy_from_source:
            self.heat_pump.timestep_end()
            mock_extract_energy_from_source.assert_not_called()

        self.heat_pump._HeatPump__energy_supply_heat_source = MagicMock()  # type: ignore[AttributeAccessIssue]

        with patch.object(
            self.heat_pump, "_HeatPump__extract_energy_from_source"
        ) as mock_extract_energy_from_source:
            self.heat_pump.timestep_end()
            mock_extract_energy_from_source.assert_called_once()

    def test_output_detailed_results_water(self):
        """Check that output_detailed_results returns the correct results for water types"""
        self.energysupply = EnergySupply(fuel_type=FuelType.MAINS_GAS, simulation_time=self.simtime)

        self.heat_pump = HeatPump(
            hp_dict=self.heat_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            output_detailed_results=True,
        )

        self.heat_pump._HeatPump__create_service_connection(  # type: ignore[AttributeAccessIssue]
            service_name="servicetimestep_demand_energy"
        )

        for _ in self.simtime:
            self.heat_pump._HeatPump__demand_energy(  # type: ignore[AttributeAccessIssue]
                service_name="servicetimestep_demand_energy",
                service_type=HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                energy_output_required=5.0,
                temp_output=330.0,  # Kelvin
                temp_return_feed=330.0,  # Kelvin
                temp_limit_upper=340.0,  # Kelvin
                design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,  # Kelvin
                time_constant_for_service=1560,
                service_on=True,
                temp_spread_correction=1.0,
                temp_used_for_scaling=None,
                hybrid_boiler_service=None,
            )

            self.heat_pump.timestep_end()

        expected_results_per_timestep = {
            "auxiliary": {
                ("energy_standby", "kWh"): [0.006090175783606732, 0.006330405996936252],
                ("energy_crankcase_heater_mode", "kWh"): [0.0, 0.0],
                ("energy_off_mode", "kWh"): [0.0, 0.0],
            },
            "servicetimestep_demand_energy": {
                ("service_name", None): [
                    "servicetimestep_demand_energy",
                    "servicetimestep_demand_energy",
                ],
                ("service_type", None): [
                    HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                    HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                ],
                ("service_on", None): [True, True],
                ("energy_output_required", "kWh"): [5.0, 5.0],
                ("temp_output", "K"): [330.0, 330.0],
                ("temp_source", "K"): [273.15, 275.65],
                ("thermal_capacity_op_cond", "kW"): [8.417674488123662, 8.650924134797519],
                ("cop_op_cond", None): [3.1824426759289044, 3.197134104416267],
                ("time_running_full_load", "hours"): [0.5939882810928845, 0.5779729335375832],
                ("time_running_part_load", "hours"): [0.5939882810928845, 0.5779729335375832],
                ("load_ratio", None): [1.0, 1.0],
                ("hp_operating_in_onoff_mode", None): [False, False],
                ("energy_delivered_HP", "kWh"): [5.0, 5.0],
                ("energy_delivered_backup", "kWh"): [0.0, 0.0],
                ("energy_delivered_total", "kWh"): [5.0, 5.0],
                ("energy_input_HP", "kWh"): [1.5711202083288365, 1.5639006174603056],
                ("energy_input_backup", "kWh"): [0.0, 0.0],
                ("energy_heating_circ_pump", "kWh"): [0.008909824216393266, 0.008669594003063746],
                ("energy_source_circ_pump", "kWh"): [0.005939882810928845, 0.005779729335375832],
                ("energy_heating_warm_air_fan", "kWh"): [0, 0],
                ("energy_input_total", "kWh"): [1.5859699153561586, 1.5783499407987451],
                ("energy_output_delivered_boiler", "kWh"): [0.0, 0.0],
                ("energy_delivered_H5", "kWh"): [100],
            },
        }

        expected_results_annual = {
            "Overall": {
                ("energy_output_required", "kWh"): 10.0,
                ("time_running_full_load", "hours"): 1.1719612146304677,
                ("time_running_part_load", "hours"): 1.1719612146304677,
                ("energy_delivered_HP", "kWh"): 10.0,
                ("energy_delivered_backup", "kWh"): 0.0,
                ("energy_delivered_total", "kWh"): 10.0,
                ("energy_input_HP", "kWh"): 3.135020825789142,
                ("energy_input_backup", "kWh"): 0.0,
                ("energy_heating_circ_pump", "kWh"): 0.017579418219457014,
                ("energy_source_circ_pump", "kWh"): 0.011719612146304677,
                ("energy_heating_warm_air_fan", "kWh"): 0.0,
                ("energy_input_total", "kWh"): 3.1643198561549037,
                ("energy_output_delivered_boiler", "kWh"): 0.0,
                ("energy_delivered_H5", "kWh"): 100.0,
                ("CoP (H1)", None): 3.1771838471558898,
                ("CoP (H2)", None): 3.1653973753129576,
                ("CoP (H3)", None): 3.1653973753129576,
                ("CoP (H4)", None): 3.1478807272334057,
                (
                    "CoP (H5)",
                    "Note: For water heating services, only valid when HP is only heat source",
                ): 31.478807272334056,
            },
            "auxiliary": {
                ("energy_standby", "kWh"): 0.012420581780542984,
                ("energy_crankcase_heater_mode", "kWh"): 0.0,
                ("energy_off_mode", "kWh"): 0.0,
            },
            "servicetimestep_demand_energy": {
                ("energy_output_required", "kWh"): 10.0,
                ("time_running_full_load", "hours"): 1.1719612146304677,
                ("time_running_part_load", "hours"): 1.1719612146304677,
                ("energy_delivered_HP", "kWh"): 10.0,
                ("energy_delivered_backup", "kWh"): 0.0,
                ("energy_delivered_total", "kWh"): 10.0,
                ("energy_input_HP", "kWh"): 3.135020825789142,
                ("energy_input_backup", "kWh"): 0.0,
                ("energy_heating_circ_pump", "kWh"): 0.017579418219457014,
                ("energy_source_circ_pump", "kWh"): 0.011719612146304677,
                ("energy_heating_warm_air_fan", "kWh"): 0,
                ("energy_input_total", "kWh"): 3.1643198561549037,
                ("energy_output_delivered_boiler", "kWh"): 0.0,
                ("energy_delivered_H5", "kWh"): 100,
                ("CoP (H1)", None): 3.1897714738411085,
                ("CoP (H2)", None): 3.1778915983807448,
                ("CoP (H3)", None): 3.1778915983807448,
                ("CoP (H4)", None): 3.160236782178972,
                (
                    "CoP (H5)",
                    "Note: For water heating services, only valid when HP is only heat source",
                ): 31.602367821789723,
            },
        }

        results_per_timestep, results_annual = self.heat_pump.output_detailed_results(
            hot_water_energy_output={"hwsname": [100]},
            hotwatersource_name_for_heatpump_service={"servicetimestep_demand_energy": "hwsname"},
        )

        self.assertEqual(results_per_timestep.keys(), expected_results_per_timestep.keys())
        self.assertEqual(results_annual.keys(), results_annual.keys())

        def checkValues(actual, expected):
            if isinstance(expected, list):
                self.assertEqual(len(actual), len(expected))
                for a, e in zip(actual, expected, strict=False):
                    self.assertAlmostEqual(a, e)
            elif isinstance(expected, float):
                self.assertAlmostEqual(actual, expected)
            else:
                self.assertEqual(actual, expected)

        for key in expected_results_per_timestep.keys():
            self.assertEqual(
                results_per_timestep[key].keys(), expected_results_per_timestep[key].keys()
            )
            for value in expected_results_per_timestep[key]:
                checkValues(
                    results_per_timestep[key][value], expected_results_per_timestep[key][value]
                )

        for key in expected_results_annual.keys():
            self.assertEqual(results_annual[key].keys(), expected_results_annual[key].keys())
            for value in expected_results_annual[key]:
                checkValues(results_annual[key][value], expected_results_annual[key][value])

        # === Test case where hot water source is not in hot water energy source data ===

        expected_results_per_timestep["servicetimestep_demand_energy"][
            ("energy_delivered_H5", "kWh")
        ] = [None, None]
        expected_results_annual["servicetimestep_demand_energy"][("energy_delivered_H5", "kWh")] = (
            None
        )
        expected_results_annual["Overall"][("energy_delivered_H5", "kWh")] = None
        del expected_results_annual["servicetimestep_demand_energy"][
            (
                "CoP (H5)",
                "Note: For water heating services, only valid when HP is only heat source",
            )
        ]
        del expected_results_annual["Overall"][
            (
                "CoP (H5)",
                "Note: For water heating services, only valid when HP is only heat source",
            )
        ]
        expected_results_annual["servicetimestep_demand_energy"][
            ("CoP (H5)", "Note: Cannot calculate CoP (H5) when HP is heating a pre-heat tank")
        ] = None
        expected_results_annual["Overall"][
            ("CoP (H5)", "Note: Cannot calculate CoP (H5) when HP is heating a pre-heat tank")
        ] = None

        results_per_timestep, results_annual = self.heat_pump.output_detailed_results(
            hot_water_energy_output={"hwsname": [100]},
            hotwatersource_name_for_heatpump_service={
                "servicetimestep_demand_energy": "hwsname_other"
            },
        )

        self.assertEqual(results_per_timestep.keys(), expected_results_per_timestep.keys())
        self.assertEqual(results_annual.keys(), results_annual.keys())

        for key in expected_results_per_timestep.keys():
            self.assertEqual(
                results_per_timestep[key].keys(), expected_results_per_timestep[key].keys()
            )
            for value in expected_results_per_timestep[key]:
                checkValues(
                    results_per_timestep[key][value], expected_results_per_timestep[key][value]
                )

        for key in expected_results_annual.keys():
            self.assertEqual(results_annual[key].keys(), expected_results_annual[key].keys())
            for value in expected_results_annual[key]:
                checkValues(results_annual[key][value], expected_results_annual[key][value])

    def test_output_detailed_results_space(self):
        """Check that output_detailed_results returns the correct results for space types"""
        self.energysupply = EnergySupply(fuel_type=FuelType.MAINS_GAS, simulation_time=self.simtime)

        self.heat_pump = HeatPump(
            hp_dict=self.heat_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            output_detailed_results=True,
        )

        self.heat_pump._HeatPump__create_service_connection(  # type: ignore[AttributeAccessIssue]
            service_name="servicetimestep_demand_energy"
        )

        for _ in self.simtime:
            self.heat_pump._HeatPump__demand_energy(  # type: ignore[AttributeAccessIssue]
                service_name="servicetimestep_demand_energy",
                service_type=HeatingServiceType.SPACE,
                energy_output_required=5.0,
                temp_output=330.0,  # Kelvin
                temp_return_feed=330.0,  # Kelvin
                temp_limit_upper=340.0,  # Kelvin
                design_flow_temp_op_cond=self.design_flow_temp_op_cond_K,  # Kelvin
                time_constant_for_service=1560,
                service_on=True,
                temp_spread_correction=1.0,
                temp_used_for_scaling=None,
                hybrid_boiler_service=None,
            )

            self.heat_pump.timestep_end()

        expected_results_per_timestep = {
            "auxiliary": {
                ("energy_standby", "kWh"): [0.0, 0.0],
                ("energy_crankcase_heater_mode", "kWh"): [0.0, 0.0],
                ("energy_off_mode", "kWh"): [0.0, 0.0],
            },
            "servicetimestep_demand_energy": {
                ("service_name", None): [
                    "servicetimestep_demand_energy",
                    "servicetimestep_demand_energy",
                ],
                ("service_type", None): [HeatingServiceType.SPACE, HeatingServiceType.SPACE],
                ("service_on", None): [True, True],
                ("energy_output_required", "kWh"): [5.0, 5.0],
                ("temp_output", "K"): [330.0, 330.0],
                ("temp_source", "K"): [273.15, 275.65],
                ("thermal_capacity_op_cond", "kW"): [8.417674488123662, 8.650924134797519],
                ("cop_op_cond", None): [3.1824426759289044, 3.197134104416267],
                ("time_running_full_load", "hours"): [0.5939882810928845, 0.5779729335375832],
                ("time_running_part_load", "hours"): [1.0, 1.0],
                ("load_ratio", None): [0.5939882810928845, 0.5779729335375832],
                ("hp_operating_in_onoff_mode", None): [False, False],
                ("energy_delivered_HP", "kWh"): [5.0, 5.000000000000001],
                ("energy_delivered_backup", "kWh"): [0.0, 0.0],
                ("energy_delivered_total", "kWh"): [5.0, 5.000000000000001],
                ("energy_input_HP", "kWh"): [1.5711202083288365, 1.5639006174603056],
                ("energy_input_backup", "kWh"): [0.0, 0.0],
                ("energy_heating_circ_pump", "kWh"): [0.008909824216393266, 0.008669594003063746],
                ("energy_source_circ_pump", "kWh"): [0.005939882810928845, 0.005779729335375832],
                ("energy_heating_warm_air_fan", "kWh"): [0, 0],
                ("energy_input_total", "kWh"): [1.5859699153561586, 1.5783499407987451],
                ("energy_output_delivered_boiler", "kWh"): [0.0, 0.0],
                ("energy_delivered_H5", "kWh"): [5.0, 5.000000000000001],
            },
        }

        expected_results_annual = {
            "Overall": {
                ("energy_output_required", "kWh"): 10.0,
                ("time_running_full_load", "hours"): 1.1719612146304677,
                ("time_running_part_load", "hours"): 2.0,
                ("energy_delivered_HP", "kWh"): 10.0,
                ("energy_delivered_backup", "kWh"): 0.0,
                ("energy_delivered_total", "kWh"): 10.0,
                ("energy_input_HP", "kWh"): 3.135020825789142,
                ("energy_input_backup", "kWh"): 0.0,
                ("energy_heating_circ_pump", "kWh"): 0.017579418219457014,
                ("energy_source_circ_pump", "kWh"): 0.011719612146304677,
                ("energy_heating_warm_air_fan", "kWh"): 0.0,
                ("energy_input_total", "kWh"): 3.1643198561549037,
                ("energy_output_delivered_boiler", "kWh"): 0.0,
                ("energy_delivered_H5", "kWh"): 10.0,
                ("CoP (H1)", None): 3.1897714738411085,
                ("CoP (H2)", None): 3.1778915983807448,
                ("CoP (H3)", None): 3.1778915983807448,
                ("CoP (H4)", None): 3.160236782178972,
                (
                    "CoP (H5)",
                    "Note: For water heating services, only valid when HP is only heat source",
                ): 3.160236782178972,
            },
            "auxiliary": {
                ("energy_standby", "kWh"): 0.0,
                ("energy_crankcase_heater_mode", "kWh"): 0.0,
                ("energy_off_mode", "kWh"): 0.0,
            },
            "servicetimestep_demand_energy": {
                ("energy_output_required", "kWh"): 10.0,
                ("time_running_full_load", "hours"): 1.1719612146304677,
                ("time_running_part_load", "hours"): 2.0,
                ("energy_delivered_HP", "kWh"): 10.0,
                ("energy_delivered_backup", "kWh"): 0.0,
                ("energy_delivered_total", "kWh"): 10.0,
                ("energy_input_HP", "kWh"): 3.135020825789142,
                ("energy_input_backup", "kWh"): 0.0,
                ("energy_heating_circ_pump", "kWh"): 0.017579418219457014,
                ("energy_source_circ_pump", "kWh"): 0.011719612146304677,
                ("energy_heating_warm_air_fan", "kWh"): 0,
                ("energy_input_total", "kWh"): 3.1643198561549037,
                ("energy_output_delivered_boiler", "kWh"): 0.0,
                ("energy_delivered_H5", "kWh"): 10.0,
                ("CoP (H1)", None): 3.1897714738411085,
                ("CoP (H2)", None): 3.1778915983807448,
                ("CoP (H3)", None): 3.1778915983807448,
                ("CoP (H4)", None): 3.160236782178972,
                (
                    "CoP (H5)",
                    "Note: For water heating services, only valid when HP is only heat source",
                ): 3.160236782178972,
            },
        }

        results_per_timestep, results_annual = self.heat_pump.output_detailed_results(
            hot_water_energy_output={"hwsname": [100]}, hotwatersource_name_for_heatpump_service={}
        )

        self.assertEqual(results_per_timestep.keys(), expected_results_per_timestep.keys())
        self.assertEqual(results_annual.keys(), results_annual.keys())

        def checkValues(actual, expected):
            if isinstance(expected, list):
                self.assertEqual(len(actual), len(expected))
                for a, e in zip(actual, expected, strict=False):
                    self.assertAlmostEqual(a, e)
            elif isinstance(expected, float):
                self.assertAlmostEqual(actual, expected)
            else:
                self.assertEqual(actual, expected)

        for key in expected_results_per_timestep.keys():
            self.assertEqual(
                results_per_timestep[key].keys(), expected_results_per_timestep[key].keys()
            )
            for value in expected_results_per_timestep[key]:
                checkValues(
                    results_per_timestep[key][value], expected_results_per_timestep[key][value]
                )

        for key in expected_results_annual.keys():
            self.assertEqual(results_annual[key].keys(), expected_results_annual[key].keys())
            for value in expected_results_annual[key]:
                checkValues(results_annual[key][value], expected_results_annual[key][value])

    def test_calc_service_cop_zero_values(self):
        """Check that calc_service_cop returns the correct values with zero values"""
        self.energysupply = EnergySupply(fuel_type=FuelType.MAINS_GAS, simulation_time=self.simtime)

        self.heat_pump = HeatPump(
            hp_dict=self.heat_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=self.energy_supply_conn_name_auxiliary,
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            output_detailed_results=True,
        )

        results_totals: dict[tuple[str, str | None], float] = {
            ("energy_delivered_HP", "kWh"): 0.0,
            ("energy_input_HP", "kWh"): 0.0,
            ("energy_source_circ_pump", "kWh"): 0.0,
            ("energy_delivered_backup", "kWh"): 0.0,
            ("energy_input_backup", "kWh"): 0.0,
            ("energy_delivered_H5", "kWh"): 0.0,
            ("energy_heating_circ_pump", "kWh"): 0.0,
            ("energy_heating_warm_air_fan", "kWh"): 0.0,
        }

        self.heat_pump._HeatPump__calc_service_cop(results_totals=results_totals)  # type: ignore[AttributeAccessIssue]

        self.assertEqual(results_totals[("CoP (H1)", None)], 0)
        self.assertEqual(results_totals[("CoP (H2)", None)], 0)
        self.assertEqual(results_totals[("CoP (H3)", None)], 0)
        self.assertEqual(results_totals[("CoP (H4)", None)], 0)
        self.assertEqual(results_totals[("CoP (H5)", None)], 0)

    def test_backup_only_operation(self):
        """Check that correct running time is calculated when in backup-only operation"""
        temp_limit_upper = 65.0
        control = SetpointTimeControl(
            schedule=[20, 20], simulation_time=self.simtime, start_day=0, time_series_step=1
        )
        self.extcond = ExternalConditions(
            simulation_time=self.simtime,
            air_temps=[-10.0, 2.5],
            wind_speeds=self.windspeed,
            wind_directions=self.wind_direction,
            diffuse_horizontal_radiation=self.diffuse_horizontal_radiation,
            direct_beam_radiation=self.direct_beam_radiation,
            solar_reflectivity_of_ground=self.solar_reflectivity_of_ground,
            latitude=self.latitude,
            longitude=self.longitude,
            timezone=self.timezone,
            start_day=self.start_day,
            end_day=self.end_day,
            time_series_step=self.time_series_step,
            january_first=self.january_first,
            daylight_savings=self.daylight_savings,
            leap_day_included=self.leap_day_included,
            direct_beam_conversion_needed=self.direct_beam_conversion_needed,
            shading_segments=self.shading_segments,
        )

        heat_dict = deepcopy(self.heat_dict)
        heat_dict["backup_ctrl_type"] = HeatPumpBackupControlType.SUBSTITUTE
        heat_pump = HeatPump(
            hp_dict=heat_dict,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary="hp_aux",
            simulation_time=self.simtime,
            external_conditions=self.extcond,
            number_of_zones=self.number_of_zones,
            throughput_exhaust_air=101,
        )
        hp_service_space1 = heat_pump.create_service_space_heating(
            service_name="hp_space_heating_1",
            emitter_type=HeatPumpEmitterType.RADIATORS_UFH,
            temp_limit_upper=temp_limit_upper,
            temp_diff_emit_design=5.0,
            design_flow_temp_op_cond=self.design_flow_temp_op_cond,
            control=control,
            volume_heated=120.0,
        )
        hp_service_space2 = heat_pump.create_service_space_heating(
            service_name="hp_space_heating_2",
            emitter_type=HeatPumpEmitterType.RADIATORS_UFH,
            temp_limit_upper=temp_limit_upper,
            temp_diff_emit_design=5.0,
            design_flow_temp_op_cond=self.design_flow_temp_op_cond,
            control=control,
            volume_heated=120.0,
        )

        hp_service_space1.demand_energy(
            energy_demand=2.0,
            temp_flow=35.0,
            temp_return=30.0,
            time_start=0.0,
        )
        hp_service_space2.demand_energy(
            energy_demand=2.0,
            temp_flow=35.0,
            temp_return=30.0,
            time_start=0.25,
        )
        self.maxDiff = None
        self.assertEqual(
            heat_pump.service_results,
            [
                {
                    "service_name": "hp_space_heating_1",
                    "service_type": HeatingServiceType.SPACE,
                    "service_on": True,
                    "energy_output_required": 2.0,
                    "time_constant_for_service": 1370,
                    "temp_output": 308.15,
                    "temp_source": 263.15,
                    "cop_op_cond": 3.3171919477244307,
                    "thermal_capacity_op_cond": 9.243872347406562,
                    "time_running_full_load": 0.6666666666666666,
                    "time_available_for_capacity_calc": 1.0,
                    "time_available_for_load_ratio_calc": 1.0,
                    "use_backup_heater_only": True,
                    "energy_delivered_HP": 0.0,
                    "energy_input_backup": 2.0,
                    "energy_delivered_backup": 2.0,
                    "energy_delivered_total": 2.0,
                    "energy_heating_circ_pump": 0.009999999999999998,
                    "energy_source_circ_pump": 0.0,
                    "energy_output_required_boiler": 0.0,
                    "energy_heating_warm_air_fan": 0,
                    "energy_output_delivered_boiler": 0.0,
                },
                {
                    "service_name": "hp_space_heating_2",
                    "service_type": HeatingServiceType.SPACE,
                    "service_on": True,
                    "energy_output_required": 2.0,
                    "time_constant_for_service": 1370,
                    "temp_output": 308.15,
                    "temp_source": 263.15,
                    "cop_op_cond": 3.3171919477244307,
                    "thermal_capacity_op_cond": 9.243872347406562,
                    "time_running_full_load": 0.25,
                    "time_available_for_capacity_calc": 0.25,
                    "time_available_for_load_ratio_calc": 0.33333333333333337,
                    "use_backup_heater_only": True,
                    "energy_delivered_HP": 0.0,
                    "energy_input_backup": 0.75,
                    "energy_delivered_backup": 0.75,
                    "energy_delivered_total": 0.75,
                    "energy_heating_circ_pump": 0.00375,
                    "energy_source_circ_pump": 0.0,
                    "energy_output_required_boiler": 0.0,
                    "energy_heating_warm_air_fan": 0,
                    "energy_output_delivered_boiler": 0.0,
                },
            ],
            "",
        )
        heat_pump.timestep_end()


class TestHeatPump_HWOnly(unittest.TestCase):
    def setUp(self):
        self.heat_dict = {
            "M": {
                "cop_dhw": 2.7,
                "hw_tapping_prof_daily_total": 5.845,
                "energy_input_measured": 2.15,
                "power_standby": 0.02,
                "hw_vessel_loss_daily": 1.18,
            },
            "L": {
                "cop_dhw": 2.5,
                "hw_tapping_prof_daily_total": 11.655,
                "energy_input_measured": 4.6,
                "power_standby": 0.03,
                "hw_vessel_loss_daily": 1.6,
            },
        }
        self.simtime = SimulationTime(start_time=0, end_time=2, step=1)
        self.energysupply = EnergySupply(fuel_type=FuelType.MAINS_GAS, simulation_time=self.simtime)
        self.energy_supply_conn_name = "HeatPump: hp"
        self.energysupplyconnection = self.energysupply.connection(end_user_name="end_user_name")

        self.power_max = 3.0
        self.vol_daily_average = 150.0
        self.tank_volume = 200.0
        self.daily_losses = 1.5
        self.heat_exchanger_surface_area = 1.2
        self.in_use_factor_mismatch = 0.6
        self.tank_volume_declared = 180.0
        self.heat_exchanger_surface_area_declared = 1.0
        self.daily_losses_declared = 1.2

        self.controlmin = SetpointTimeControl(
            schedule=[52, 52, None, 52],
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )
        self.controlmax = SetpointTimeControl(
            schedule=[60, 60, 60, 60], simulation_time=self.simtime, start_day=0, time_series_step=1
        )

        self.heat_pump = HeatPump_HWOnly(
            power_max=self.power_max,
            test_data=self.heat_dict,
            vol_daily_average=self.vol_daily_average,
            tank_volume=self.tank_volume,
            daily_losses=self.daily_losses,
            heat_exchanger_surface_area=self.heat_exchanger_surface_area,
            in_use_factor_mismatch=self.in_use_factor_mismatch,
            tank_volume_declared=self.tank_volume_declared,
            heat_exchanger_surface_area_declared=self.heat_exchanger_surface_area_declared,
            daily_losses_declared=self.daily_losses_declared,
            energy_supply_conn=self.energysupplyconnection,
            simulation_time=self.simtime,
            controlmin=self.controlmin,
            controlmax=self.controlmax,
        )

    def test_init_efficiencies(self):
        """Test that initial_efficiency is initialised to the correct value based on heat_dict and vol_daily_average"""

        heat_dict: dict[str, HWHeatPumpData] = {
            "M": {
                "cop_dhw": 2.7,
                "hw_tapping_prof_daily_total": 5.845,
                "energy_input_measured": 2.15,
                "power_standby": 0.02,
                "hw_vessel_loss_daily": 1.18,
            }
        }

        self.heat_pump = HeatPump_HWOnly(
            power_max=self.power_max,
            test_data=heat_dict,
            vol_daily_average=self.vol_daily_average,
            tank_volume=self.tank_volume,
            daily_losses=self.daily_losses,
            heat_exchanger_surface_area=self.heat_exchanger_surface_area,
            in_use_factor_mismatch=self.in_use_factor_mismatch,
            tank_volume_declared=self.tank_volume_declared,
            heat_exchanger_surface_area_declared=self.heat_exchanger_surface_area_declared,
            daily_losses_declared=self.daily_losses_declared,
            energy_supply_conn=self.energysupplyconnection,
            simulation_time=self.simtime,
            controlmin=self.controlmin,
            controlmax=self.controlmax,
        )

        self.assertEqual(self.heat_pump.initial_efficiency, 3.0478653375963884)

        heat_dict: dict[str, HWHeatPumpData] = {
            "M": {
                "cop_dhw": 2.7,
                "hw_tapping_prof_daily_total": 5.845,
                "energy_input_measured": 2.15,
                "power_standby": 0.02,
                "hw_vessel_loss_daily": 1.18,
            },
            "L": {
                "cop_dhw": 2.5,
                "hw_tapping_prof_daily_total": 11.655,
                "energy_input_measured": 4.6,
                "power_standby": 0.03,
                "hw_vessel_loss_daily": 1.6,
            },
        }

        self.vol_daily_average = 90

        self.heat_pump = HeatPump_HWOnly(
            power_max=self.power_max,
            test_data=heat_dict,
            vol_daily_average=self.vol_daily_average,
            tank_volume=self.tank_volume,
            daily_losses=self.daily_losses,
            heat_exchanger_surface_area=self.heat_exchanger_surface_area,
            in_use_factor_mismatch=self.in_use_factor_mismatch,
            tank_volume_declared=self.tank_volume_declared,
            heat_exchanger_surface_area_declared=self.heat_exchanger_surface_area_declared,
            daily_losses_declared=self.daily_losses_declared,
            energy_supply_conn=self.energysupplyconnection,
            simulation_time=self.simtime,
            controlmin=self.controlmin,
            controlmax=self.controlmax,
        )

        self.assertEqual(self.heat_pump.initial_efficiency, 3.0478653375963884)

        self.vol_daily_average = 200

        self.heat_pump = HeatPump_HWOnly(
            power_max=self.power_max,
            test_data=heat_dict,
            vol_daily_average=self.vol_daily_average,
            tank_volume=self.tank_volume,
            daily_losses=self.daily_losses,
            heat_exchanger_surface_area=self.heat_exchanger_surface_area,
            in_use_factor_mismatch=self.in_use_factor_mismatch,
            tank_volume_declared=self.tank_volume_declared,
            heat_exchanger_surface_area_declared=self.heat_exchanger_surface_area_declared,
            daily_losses_declared=self.daily_losses_declared,
            energy_supply_conn=self.energysupplyconnection,
            simulation_time=self.simtime,
            controlmin=self.controlmin,
            controlmax=self.controlmax,
        )

        self.assertEqual(self.heat_pump.initial_efficiency, 2.7473226825842696)

    def test_init_efficiencies_invalid(self):
        """Test that the constructor throws on invalid heat_dict data"""
        self.heat_dict: dict[str, HWHeatPumpData] = {}
        with self.assertRaises(ValueError):
            self.heat_pump = HeatPump_HWOnly(
                power_max=self.power_max,
                test_data=self.heat_dict,
                vol_daily_average=self.vol_daily_average,
                tank_volume=self.tank_volume,
                daily_losses=self.daily_losses,
                heat_exchanger_surface_area=self.heat_exchanger_surface_area,
                in_use_factor_mismatch=self.in_use_factor_mismatch,
                tank_volume_declared=self.tank_volume_declared,
                heat_exchanger_surface_area_declared=self.heat_exchanger_surface_area_declared,
                daily_losses_declared=self.daily_losses_declared,
                energy_supply_conn=self.energysupplyconnection,
                simulation_time=self.simtime,
                controlmin=self.controlmin,
                controlmax=self.controlmax,
            )

    def test_calc_efficiency(self):
        self.assertAlmostEqual(self.heat_pump.calc_efficiency(), 1.738556406)

    def test_calc_efficiency_criteria(self):
        """Test that calc_efficiency returns the correct value if the heat pump does not meet criteria"""
        self.heat_pump._HeatPump_HWOnly__daily_losses = 1.1  # type: ignore[AttributeAccessIssue]

        self.assertAlmostEqual(self.heat_pump.calc_efficiency(), 2.8975940100903292)

    def test_setpnt(self):
        """Test that setpnt returns the setpoints from the controls"""
        minsetpnt, maxsetpnt = self.heat_pump.setpnt()
        self.assertEqual(minsetpnt, 52)
        self.assertEqual(maxsetpnt, 60)

    def test_setpnt_errors(self):
        simtime = SimulationTime(start_time=0, end_time=1, step=1)
        self.heat_pump._HeatPump_HWOnly__controlmin = OnOffTimeControl(  # type: ignore[AttributeAccessIssue]
            schedule=[True], simulation_time=simtime, start_day=0, time_series_step=1
        )
        with self.assertRaises(TypeError):
            self.heat_pump.setpnt()

        self.heat_pump._HeatPump_HWOnly__controlmin = self.controlmin  # type: ignore[AttributeAccessIssue]
        self.heat_pump._HeatPump_HWOnly__controlmax = OnOffTimeControl(  # type: ignore[AttributeAccessIssue]
            schedule=[True], simulation_time=simtime, start_day=0, time_series_step=1
        )
        with self.assertRaises(TypeError):
            self.heat_pump.setpnt()

    def test_demand_energy(self):
        """Test that demand_energy returns the correct value"""
        self.assertAlmostEqual(
            self.heat_pump.demand_energy(energy_demand=10, temp_flow=50, temp_return=40), 3.0
        )

    def test_demand_energy_off(self):
        """test that demand_energy returns 0 if the control is off"""
        self.heat_pump._HeatPump_HWOnly__controlmin = OnOffTimeControl(  # type: ignore[AttributeAccessIssue]
            schedule=[False, False], simulation_time=self.simtime, start_day=0, time_series_step=1
        )

        self.assertAlmostEqual(
            self.heat_pump.demand_energy(energy_demand=10, temp_flow=50, temp_return=40), 0
        )

    def test_energy_output_max(self):
        """Test that energy_output_max returns the correct value"""
        self.assertAlmostEqual(self.heat_pump.energy_output_max(temp_flow=50, temp_return=40), 3.0)

    def test_energy_output_max_off(self):
        """Test that energy_output_max returns 0 if the control is off"""
        self.heat_pump._HeatPump_HWOnly__controlmin = OnOffTimeControl(  # type: ignore[AttributeAccessIssue]
            schedule=[False, False], simulation_time=self.simtime, start_day=0, time_series_step=1
        )

        self.assertAlmostEqual(self.heat_pump.energy_output_max(temp_flow=50, temp_return=40), 0)

    def test_init_with_null_heat_exchanger_surface_area_declared(self):
        """Test that heat_exchanger_surface_area_declared defaults to 0.0 when None"""
        heat_pump = HeatPump_HWOnly(
            power_max=self.power_max,
            test_data=self.heat_dict,
            vol_daily_average=self.vol_daily_average,
            tank_volume=self.tank_volume,
            daily_losses=self.daily_losses,
            heat_exchanger_surface_area=self.heat_exchanger_surface_area,
            in_use_factor_mismatch=self.in_use_factor_mismatch,
            tank_volume_declared=self.tank_volume_declared,
            heat_exchanger_surface_area_declared=None,  # Pass None here
            daily_losses_declared=self.daily_losses_declared,
            energy_supply_conn=self.energysupplyconnection,
            simulation_time=self.simtime,
            controlmin=self.controlmin,
            controlmax=self.controlmax,
        )

        self.assertAlmostEqual(heat_pump.calc_efficiency(), 1.738556406)
