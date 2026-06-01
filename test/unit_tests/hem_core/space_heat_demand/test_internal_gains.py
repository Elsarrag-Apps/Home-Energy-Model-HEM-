#!/usr/bin/env python3

"""
This module contains unit tests for the Instant Electric Heater module
"""

# Standard library imports
import unittest
from unittest.mock import MagicMock

from hem_core.controls.time_control import SmartApplianceControl
from hem_core.energy_supply.energy_supply import EnergySupply
from hem_core.input_output.enums import FuelType

# Local imports
from hem_core.simulation_time import SimulationTime
from hem_core.space_heat_demand.internal_gains import (
    ApplianceGains,
    EventApplianceGains,
    InternalGains,
)


class TestInternalGains(unittest.TestCase):
    """Unit tests for InternalGains class"""

    def setUp(self) -> None:
        """Create InternalGains object to be tested"""
        self.simtime = SimulationTime(0, 4, 1)
        self.total_internal_gains = [3.2, 4.6, 7.3, 5.2]
        self.internalgains = InternalGains(
            total_internal_gains=self.total_internal_gains,
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )

    def test_total_internal_gain(self) -> None:
        """Test that InternalGains object returns correct internal gains and electricity demand"""
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.internalgains.total_internal_gain(10.0),
                    [32, 46, 73, 52][t_idx],
                    "incorrect internal gains returned",
                )


class TestApplianceGains(unittest.TestCase):
    """Unit tests for ApplianceGains class"""

    def setUp(self) -> None:
        """Create ApplianceGains object to be tested"""
        self.simtime = SimulationTime(0, 4, 1)
        self.energysupply = EnergySupply(FuelType.ELECTRICITY, self.simtime)
        energysupplyconn = self.energysupply.connection("lighting")
        self.total_energy_supply = [32.0, 46.0, 30.0, 20.0]
        self.appliancegains = ApplianceGains(
            total_energy_supply=self.total_energy_supply,
            energy_supply_conn=energysupplyconn,
            gains_fraction=0.5,
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )

    def test_total_internal_gain(self) -> None:
        """Test that ApplianceGains object returns correct internal gains and electricity demand"""
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.appliancegains.total_internal_gain(10.0),
                    [160.0, 230.0, 150.0, 100.0][t_idx],
                    "incorrect internal gains for appliances returned",
                )
                self.assertEqual(
                    self.energysupply.results_by_end_user()["lighting"][t_idx],
                    [0.32, 0.46, 0.30, 0.20][t_idx],
                    "incorrect electricity demand  returned",
                )


class TestEventApplianceGains(unittest.TestCase):
    def setUp(self) -> None:
        """Create EventApplianceGains object to be tested"""

        self.simtime = SimulationTime(0, 24, 0.5)
        self.energy_supply = EnergySupply(FuelType.ELECTRICITY, self.simtime)
        self.energy_supply_conn = self.energy_supply.connection("new_connection")
        self.appliance_data = {
            "type": "Clothes_drying",
            "EnergySupply": "mains elec",
            "start_day": 0,
            "time_series_step": 1,
            "gains_fraction": 0.7,
            "Events": [
                {"start": 0.1, "duration": 1.75, "demand_W": 900.0},
                {"start": 5.3, "duration": 1.50, "demand_W": 900.0},
                {"start": 25.3, "duration": 1.50, "demand_W": 900.0},
            ],
            "Standby": 0.5,
            "loadshifting": {
                "demand_limit_weighted": 0,
                "power_timeseries": [
                    77.70823134533667,
                    70.07710122045972,
                    66.26153469022015,
                    62.445968159980595,
                    58.6304045653432,
                    66.26153469022015,
                    81.52379787557622,
                    872.7293737820189,
                    448.95976141145366,
                    146.38841421163792,
                    150.20398074187744,
                    246.13290374339178,
                    157.8351108667544,
                    146.38841421163792,
                    150.20398074187744,
                    236.48451946096566,
                    1235.1378596577206,
                    257.03982010376774,
                    801.2313187689566,
                    207.4374669530622,
                    192.17520376770614,
                    290.41445627425867,
                    138.757284086761,
                    100.60162759117186,
                    77.70823134533667,
                ],
                "max_shift_hrs": 8,
                "weight": "Tariff",
                "weight_timeseries": [
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                ],
            },
        }
        self.non_appliance_demand_24hr = {
            "mains elec": [
                0.06830825101566576,
                0.060105811973985415,
                0.05305939286989522,
                0.0501236916686892,
                0.011659722362322093,
                0.009841650327447332,
                0.008628179127672608,
                0.00780480411138585,
                0.007342238555297734,
                0.0068683142767418555,
                0.007092339066083696,
                0.0073738789491060025,
                0.00890318157456338,
                0.013196350717229778,
                3.8185258665440713,
                3.686604856404327,
                3.321741503132428,
                2.1009771847288543,
                1.9577604381160962,
                0.982853996628817,
                -0.4690062980892011,
                -0.47106808673125095,
                -0.440083286258449,
                -0.4402744803667663,
                -0.275893537706527,
                -0.27582574287859735,
                -0.02364598193865506,
                -0.022770656131003677,
                0.006386180325667274,
                1.1838622352604393,
                0.016880847238056107,
                0.022939243503258204,
                0.03451315625040322,
                3.6710272517570663,
                3.4183577199797917,
                3.259661970488036,
                2.382744591886866,
                3.347517299485186,
                2.8633293436146374,
                2.194481295688944,
                2.0245859635409174,
                2.160933115928409,
                2.1559541166936143,
                2.078707457615306,
                0.06082872713634447,
                0.05498437799409048,
                0.04615437212925211,
                0.036699730049032445,
            ]
        }
        self.battery24hr = {
            "battery_state_of_charge": {
                "mains elec": [
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                ]
            }
        }
        self.__smartcontrol = SmartApplianceControl(
            power_timeseries={
                "mains elec": self.appliance_data["loadshifting"]["power_timeseries"]
            },
            timeseries_step=self.appliance_data["time_series_step"],
            simulation_time=self.simtime,
            non_appliance_demand_24hr=self.non_appliance_demand_24hr,
            battery_24hr=self.battery24hr,
            energysupplies={"mains elec": self.energy_supply},
            appliances={"Clothes_drying": None},
        )

        self.TFA = 100.0
        self.event_app_gains = EventApplianceGains(
            energy_supply_conn=self.energy_supply_conn,
            simulation_time=self.simtime,
            appliance_data=self.appliance_data,
            TFA=self.TFA,
            smartcontrol=self.__smartcontrol,
        )

    def test__process_event(self) -> None:
        eventdict = {"start": 3, "duration": 1.75, "demand_W": 900.0}

        self.appliance_data["Events"] = []
        self.event_app_gains = EventApplianceGains(
            energy_supply_conn=self.energy_supply_conn,
            simulation_time=self.simtime,
            appliance_data=self.appliance_data,
            TFA=self.TFA,
            smartcontrol=self.__smartcontrol,
        )

        self.assertEqual(
            self.event_app_gains._EventApplianceGains__process_event(eventdict),
            (21, [899.5, 899.5, 899.5, 449.75, 0.0]),
        )

    def test_event_to_schedule(self) -> None:
        eventdict = {"start": 3, "duration": 1.75, "demand_W": 900.0}
        self.assertEqual(
            self.event_app_gains._EventApplianceGains__event_to_schedule(eventdict),
            (6, [899.5, 899.5, 899.5, 449.75, 0.0]),
        )

    def test_total_internal_gain(self) -> None:
        res = [self.event_app_gains.total_internal_gain(self.TFA) for _ in self.simtime]
        self.assertEqual(
            res,
            [
                0.35,
                0.35,
                0.35,
                0.35,
                0.35,
                0.35,
                504.07,
                630.0,
                630.0,
                441.10499999999996,
                0.35,
                0.35,
                0.35,
                0.35,
                0.35,
                0.35,
                0.35,
                0.35,
                0.35,
                0.35,
                252.21000000000018,
                630.0,
                630.0,
                378.1399999999999,
                0.35,
                0.35,
                0.35,
                0.35,
                0.35,
                0.35,
                0.35,
                0.35,
                0.35,
                0.35,
                0.35,
                0.35,
                0.35,
                0.35,
                0.35,
                0.35,
                0.35,
                0.35,
                0.35,
                0.35,
                0.35,
                0.35,
                0.35,
                0.35,
            ],
        )

    def test___shift_iterative(self) -> None:
        eventdict = {"start": 2.33, "duration": 1.0, "demand_W": 900}
        s, a = 5, [600, 300]

        self.appliance_data["Events"] = []
        self.event_app_gains = EventApplianceGains(
            energy_supply_conn=self.energy_supply_conn,
            simulation_time=self.simtime,
            appliance_data=self.appliance_data,
            TFA=self.TFA,
            smartcontrol=self.__smartcontrol,
        )

        self.assertEqual(
            self.event_app_gains._EventApplianceGains__shift_iterative(
                start_idx=s, power_list_over_timesteps=a, eventdict=eventdict
            ),
            15,
        )


class TestEventApplianceGains_total_internal_gain(unittest.TestCase):
    """Unit tests for EventApplianceGains.total_internal_gain"""

    def setUp(self) -> None:
        self.simtime = SimulationTime(0, 12, 1)
        self.energysupply = EnergySupply(FuelType.ELECTRICITY, self.simtime)
        self.energysupplyconn = self.energysupply.connection("lighting")
        self.total_energy_supply = [100.0] * 12
        self.appliancegains = ApplianceGains(
            total_energy_supply=self.total_energy_supply,
            energy_supply_conn=self.energysupplyconn,
            gains_fraction=0.5,
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )

        self.appliance_data = {
            "type": "Clothes_drying",
            "EnergySupply": "mains elec",
            "start_day": 0,
            "time_series_step": 1,
            "gains_fraction": 0.7,
            "loadshifting": {
                "demand_limit_weighted": 0,
                "power_timeseries": [100] * 12,
                "max_shift_hrs": 8,
                "weight": "Tariff",
                "weight_timeseries": [1] * 12,
            },
        }
        self.non_appliance_demand_24hr = {"mains elec": [0] * 12}
        self.battery24hr = {"battery_state_of_charge": {"mains elec": [0] * 12}}
        self.smartcontrol = MagicMock()
        self.smartcontrol.get_demand.return_value = 0

        self.TFA = 100.0

    def test_standby(self) -> None:
        """Test that there are always gains from standby power"""
        zone_area = 10
        standby = 10

        self.appliance_data["Standby"] = standby
        self.appliance_data["Events"] = []

        self.event_app_gains = EventApplianceGains(
            energy_supply_conn=self.energysupplyconn,
            simulation_time=self.simtime,
            appliance_data=self.appliance_data,
            TFA=self.TFA,
            smartcontrol=self.smartcontrol,
        )

        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.event_app_gains.total_internal_gain(zone_area),
                    [0.7, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7][t_idx],
                )

    def test_single_appliance(self) -> None:
        """Test that there are gains from a single appliance"""
        zone_area = 10
        standby = 0

        self.appliance_data["Standby"] = standby
        self.appliance_data["gains_fraction"] = 1
        self.appliance_data["Events"] = [
            {"start": 5, "duration": 2, "demand_W": 900.0},
        ]

        self.event_app_gains = EventApplianceGains(
            energy_supply_conn=self.energysupplyconn,
            simulation_time=self.simtime,
            appliance_data=self.appliance_data,
            TFA=self.TFA,
            smartcontrol=self.smartcontrol,
        )

        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.event_app_gains.total_internal_gain(zone_area),
                    [0, 0, 0, 0, 0, 90, 90, 0, 0, 0, 0, 0][t_idx],
                )

    def test_smart_control_called(self) -> None:
        """Test that smartcontrol.add_appliance_demand is called with the load"""
        zone_area = 10
        standby = 0

        self.appliance_data["Standby"] = standby
        self.appliance_data["gains_fraction"] = 0.5
        self.appliance_data["loadshifting"]["max_shift_hrs"] = 10
        self.appliance_data["Events"] = [
            {"start": 5, "duration": 2, "demand_W": 900.0},
        ]

        self.event_app_gains = EventApplianceGains(
            energy_supply_conn=self.energysupplyconn,
            simulation_time=self.simtime,
            appliance_data=self.appliance_data,
            TFA=self.TFA,
            smartcontrol=self.smartcontrol,
        )

        for _, _, _ in self.simtime:
            self.event_app_gains.total_internal_gain(zone_area)

        calls = self.smartcontrol.add_appliance_demand.call_args_list
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0].kwargs, {"t_idx": 5, "demand": 0.9, "energysupply": "mains elec"})
        self.assertEqual(calls[1].kwargs, {"t_idx": 6, "demand": 0.9, "energysupply": "mains elec"})
        self.assertEqual(calls[2].kwargs, {"t_idx": 7, "demand": 0.0, "energysupply": "mains elec"})

    def test_weighted_loadshifting(self) -> None:
        """Test that the lowest weighted power is used for load shifting"""
        zone_area = 10
        standby = 0

        self.appliance_data["Standby"] = standby
        self.appliance_data["gains_fraction"] = 1
        self.appliance_data["loadshifting"]["max_shift_hrs"] = 10
        self.appliance_data["loadshifting"]["weight_timeseries"] = [
            0,
            0,
            0,
            0,
            0,
            0,
            1,
            1,
            0.2,
            0.2,
            0.2,
            0.2,
        ]
        self.appliance_data["Events"] = [
            {"start": 5, "duration": 2, "demand_W": 900.0},
        ]

        self.event_app_gains = EventApplianceGains(
            energy_supply_conn=self.energysupplyconn,
            simulation_time=self.simtime,
            appliance_data=self.appliance_data,
            TFA=self.TFA,
            smartcontrol=self.smartcontrol,
        )

        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.event_app_gains.total_internal_gain(zone_area),
                    [0, 0, 0, 0, 0, 0, 0, 0, 90, 90, 0, 0][t_idx],
                )

    def test_single_appliance_half_timestep_after(self) -> None:
        """Test that there are partial gains from a partial timestep"""
        zone_area = 10
        standby = 0

        self.appliance_data["Standby"] = standby
        self.appliance_data["gains_fraction"] = 1
        self.appliance_data["Events"] = [
            {"start": 5, "duration": 2.5, "demand_W": 900.0},
        ]

        self.event_app_gains = EventApplianceGains(
            energy_supply_conn=self.energysupplyconn,
            simulation_time=self.simtime,
            appliance_data=self.appliance_data,
            TFA=self.TFA,
            smartcontrol=self.smartcontrol,
        )

        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.event_app_gains.total_internal_gain(zone_area),
                    [0, 0, 0, 0, 0, 90, 90, 45, 0, 0, 0, 0][t_idx],
                )

    def test_single_appliance_half_timestep_before(self) -> None:
        """Test that the gains begin at a whole timestep"""
        zone_area = 10
        standby = 0

        self.appliance_data["Standby"] = standby
        self.appliance_data["gains_fraction"] = 1
        self.appliance_data["Events"] = [
            {"start": 4.5, "duration": 2, "demand_W": 900.0},
        ]

        self.event_app_gains = EventApplianceGains(
            energy_supply_conn=self.energysupplyconn,
            simulation_time=self.simtime,
            appliance_data=self.appliance_data,
            TFA=self.TFA,
            smartcontrol=self.smartcontrol,
        )

        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.event_app_gains.total_internal_gain(zone_area),
                    [0, 0, 0, 0, 45.0, 90.0, 45.0, 0, 0, 0, 0, 0][t_idx],
                )

    def test_two_appliances_loadshifted(self) -> None:
        """Test that two appliances at the same time are separated"""
        zone_area = 10
        standby = 0

        self.appliance_data["Standby"] = standby
        self.appliance_data["gains_fraction"] = 1
        self.appliance_data["Events"] = [
            {"start": 5, "duration": 2, "demand_W": 900.0},
            {"start": 6, "duration": 2, "demand_W": 900.0},
        ]

        self.event_app_gains = EventApplianceGains(
            energy_supply_conn=self.energysupplyconn,
            simulation_time=self.simtime,
            appliance_data=self.appliance_data,
            TFA=self.TFA,
            smartcontrol=self.smartcontrol,
        )

        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.event_app_gains.total_internal_gain(zone_area),
                    [0, 0, 0, 0, 0, 90, 90, 90, 90, 0, 0, 0][t_idx],
                )

    def test_two_appliances_not_loadshifted(self) -> None:
        """Test that appliances aren't shifted with a max_shift_hrs of 0"""
        zone_area = 10
        standby = 0

        self.appliance_data["Standby"] = standby
        self.appliance_data["gains_fraction"] = 1
        self.appliance_data["loadshifting"]["max_shift_hrs"] = 0
        self.appliance_data["Events"] = [
            {"start": 5, "duration": 2, "demand_W": 900.0},
            {"start": 6, "duration": 2, "demand_W": 900.0},
        ]

        self.event_app_gains = EventApplianceGains(
            energy_supply_conn=self.energysupplyconn,
            simulation_time=self.simtime,
            appliance_data=self.appliance_data,
            TFA=self.TFA,
            smartcontrol=self.smartcontrol,
        )

        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.event_app_gains.total_internal_gain(zone_area),
                    [0, 0, 0, 0, 0, 90, 180, 90, 0, 0, 0, 0][t_idx],
                )

    def test_two_appliances_loadshifted_one_hour(self) -> None:
        """Test that appliances are shifted with a max_shift_hrs of 1"""
        zone_area = 10
        standby = 0

        self.appliance_data["Standby"] = standby
        self.appliance_data["gains_fraction"] = 1
        self.appliance_data["loadshifting"]["max_shift_hrs"] = 1
        self.appliance_data["Events"] = [
            {"start": 5, "duration": 3, "demand_W": 900.0},
            {"start": 6, "duration": 3, "demand_W": 900.0},
        ]

        self.event_app_gains = EventApplianceGains(
            energy_supply_conn=self.energysupplyconn,
            simulation_time=self.simtime,
            appliance_data=self.appliance_data,
            TFA=self.TFA,
            smartcontrol=self.smartcontrol,
        )

        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.event_app_gains.total_internal_gain(zone_area),
                    [0, 0, 0, 0, 0, 90, 180, 180, 90, 0, 0, 0][t_idx],
                )

    def test_two_appliances_loadshifted_two_hours(self) -> None:
        """Test that appliances are shifted with a max_shift_hrs of 2"""
        zone_area = 10
        standby = 0

        self.appliance_data["Standby"] = standby
        self.appliance_data["gains_fraction"] = 1
        self.appliance_data["loadshifting"]["max_shift_hrs"] = 2
        self.appliance_data["Events"] = [
            {"start": 5, "duration": 3, "demand_W": 900.0},
            {"start": 6, "duration": 3, "demand_W": 900.0},
        ]

        self.event_app_gains = EventApplianceGains(
            energy_supply_conn=self.energysupplyconn,
            simulation_time=self.simtime,
            appliance_data=self.appliance_data,
            TFA=self.TFA,
            smartcontrol=self.smartcontrol,
        )

        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.event_app_gains.total_internal_gain(zone_area),
                    [0, 0, 0, 0, 0, 90, 90, 90, 90, 90, 90, 0][t_idx],
                )

    def test_loadshifting_disabled(self) -> None:
        """Test that no load shifting occurs when loadshifting isn't set"""
        zone_area = 10
        standby = 0

        self.appliance_data["Standby"] = standby
        self.appliance_data["gains_fraction"] = 1
        del self.appliance_data["loadshifting"]
        self.appliance_data["Events"] = [
            {"start": 5, "duration": 2, "demand_W": 900.0},
            {"start": 6, "duration": 2, "demand_W": 900.0},
        ]

        self.event_app_gains = EventApplianceGains(
            energy_supply_conn=self.energysupplyconn,
            simulation_time=self.simtime,
            appliance_data=self.appliance_data,
            TFA=self.TFA,
            smartcontrol=self.smartcontrol,
        )

        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.event_app_gains.total_internal_gain(zone_area),
                    [0, 0, 0, 0, 0, 90, 180, 90, 0, 0, 0, 0][t_idx],
                )

    def test_past_end_of_simulation(self) -> None:
        """Test that gains past the end of the simulation are assigned to the last timestep"""
        zone_area = 10
        standby = 0

        self.appliance_data["Standby"] = standby
        self.appliance_data["gains_fraction"] = 1
        self.appliance_data["loadshifting"]["max_shift_hrs"] = 1
        self.appliance_data["Events"] = [{"start": 8, "duration": 5, "demand_W": 100.0}]

        self.event_app_gains = EventApplianceGains(
            energy_supply_conn=self.energysupplyconn,
            simulation_time=self.simtime,
            appliance_data=self.appliance_data,
            TFA=self.TFA,
            smartcontrol=self.smartcontrol,
        )

        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.event_app_gains.total_internal_gain(zone_area),
                    [0, 0, 0, 0, 0, 0, 0, 0, 10, 10, 10, 20][t_idx],
                )

    def test_demand_limit(self) -> None:
        """Test that load shifting occurs with a demand_limit_weighted set"""
        zone_area = 10
        standby = 0

        self.appliance_data["Standby"] = standby
        self.appliance_data["gains_fraction"] = 1
        self.appliance_data["loadshifting"]["demand_limit_weighted"] = 1000
        self.appliance_data["loadshifting"]["max_shift_hrs"] = 10
        self.appliance_data["Events"] = [
            {"start": 5, "duration": 2, "demand_W": 900.0},
            {"start": 6, "duration": 2, "demand_W": 900.0},
        ]

        self.event_app_gains = EventApplianceGains(
            energy_supply_conn=self.energysupplyconn,
            simulation_time=self.simtime,
            appliance_data=self.appliance_data,
            TFA=self.TFA,
            smartcontrol=self.smartcontrol,
        )

        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.event_app_gains.total_internal_gain(zone_area),
                    [0, 0, 0, 0, 0, 90, 90, 90, 90, 0, 0, 0][t_idx],
                )

    def test_demand_limit_with_larger_event_first(self) -> None:
        """Test that load shifting occurs with the larger demand first"""
        zone_area = 10
        standby = 0

        self.appliance_data["Standby"] = standby
        self.appliance_data["gains_fraction"] = 1
        self.appliance_data["loadshifting"]["demand_limit_weighted"] = 1000
        self.appliance_data["loadshifting"]["max_shift_hrs"] = 10
        self.appliance_data["Events"] = [
            {"start": 5, "duration": 2, "demand_W": 900.0},
            {"start": 6, "duration": 2, "demand_W": 800.0},
        ]

        self.event_app_gains = EventApplianceGains(
            energy_supply_conn=self.energysupplyconn,
            simulation_time=self.simtime,
            appliance_data=self.appliance_data,
            TFA=self.TFA,
            smartcontrol=self.smartcontrol,
        )

        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.event_app_gains.total_internal_gain(zone_area),
                    [0, 0, 0, 0, 0, 90, 90, 80, 80, 0, 0, 0][t_idx],
                )

    def test_demand_limit_with_larger_event_last(self) -> None:
        """Test that load shifting does not occur with the smaller demand first"""
        zone_area = 10
        standby = 0

        self.appliance_data["Standby"] = standby
        self.appliance_data["gains_fraction"] = 1
        self.appliance_data["loadshifting"]["demand_limit_weighted"] = 1000
        self.appliance_data["loadshifting"]["max_shift_hrs"] = 10
        self.appliance_data["Events"] = [
            {"start": 5, "duration": 2, "demand_W": 800.0},
            {"start": 6, "duration": 2, "demand_W": 900.0},
        ]

        self.event_app_gains = EventApplianceGains(
            energy_supply_conn=self.energysupplyconn,
            simulation_time=self.simtime,
            appliance_data=self.appliance_data,
            TFA=self.TFA,
            smartcontrol=self.smartcontrol,
        )

        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.event_app_gains.total_internal_gain(zone_area),
                    [0, 0, 0, 0, 0, 80, 170, 90, 0, 0, 0, 0][t_idx],
                )

    def test_large_demand_limit(self) -> None:
        """Test that the load shifting does not occur with a large demand_limit_weighted"""
        zone_area = 10
        standby = 0

        self.appliance_data["Standby"] = standby
        self.appliance_data["gains_fraction"] = 1
        self.appliance_data["loadshifting"]["demand_limit_weighted"] = 20000
        self.appliance_data["loadshifting"]["max_shift_hrs"] = 10
        self.appliance_data["Events"] = [
            {"start": 5, "duration": 2, "demand_W": 900.0},
            {"start": 6, "duration": 2, "demand_W": 800.0},
        ]

        self.event_app_gains = EventApplianceGains(
            energy_supply_conn=self.energysupplyconn,
            simulation_time=self.simtime,
            appliance_data=self.appliance_data,
            TFA=self.TFA,
            smartcontrol=self.smartcontrol,
        )

        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.event_app_gains.total_internal_gain(zone_area),
                    [0, 0, 0, 0, 0, 90, 170, 80, 0, 0, 0, 0][t_idx],
                )

    def test_negative_weights(self) -> None:
        """Test that the load shifting does not occur with negative weight_timeseries"""
        zone_area = 10
        standby = 0

        self.appliance_data["Standby"] = standby
        self.appliance_data["gains_fraction"] = 1
        self.appliance_data["loadshifting"]["demand_limit_weighted"] = 100
        self.appliance_data["loadshifting"]["max_shift_hrs"] = 10
        self.appliance_data["loadshifting"]["weight_timeseries"] = [-1] * 12
        self.appliance_data["Events"] = [
            {"start": 5, "duration": 2, "demand_W": 900.0},
            {"start": 6, "duration": 2, "demand_W": 800.0},
        ]

        self.event_app_gains = EventApplianceGains(
            energy_supply_conn=self.energysupplyconn,
            simulation_time=self.simtime,
            appliance_data=self.appliance_data,
            TFA=self.TFA,
            smartcontrol=self.smartcontrol,
        )

        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    self.event_app_gains.total_internal_gain(zone_area),
                    [0, 0, 0, 0, 0, 90, 170, 80, 0, 0, 0, 0][t_idx],
                )
