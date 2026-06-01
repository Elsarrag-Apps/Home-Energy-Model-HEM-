#!/usr/bin/env python3

"""
This module contains unit tests for the heat network module
"""

# Standard library imports
from unittest.mock import MagicMock, call

import pytest

# Local imports
from hem_core.controls.time_control import SetpointTimeControl
from hem_core.energy_supply.energy_supply import EnergySupply, EnergySupplyConnection
from hem_core.heating_systems.enums import HeatingServiceType
from hem_core.heating_systems.heat_network import (
    HeatNetwork,
    HeatNetworkService,
    HeatNetworkServiceSpace,
    HeatNetworkServiceWaterDirect,
    HeatNetworkServiceWaterStorage,
)
from hem_core.input_output.enums import FuelType
from hem_core.simulation_time import SimulationTime
from hem_core.water_heat_demand.cold_water_source import ColdWaterSource
from hem_core.water_heat_demand.dhw_demand import WaterEventResult


class TestHeatNetworkService:
    @pytest.fixture(autouse=True)
    def setup_heat_network(self) -> None:
        self.simtime = SimulationTime(start_time=0, end_time=2, step=1)
        self.energysupply = EnergySupply(fuel_type=FuelType.CUSTOM, simulation_time=self.simtime)
        self.heat_network = HeatNetwork(
            power_max=10.0,
            daily_loss=1.0,
            power_circ_pump=0,
            power_aux=0,
            building_level_distribution_losses=0.8,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary="aux",
            energy_supply_conn_name_building_level_distribution_losses="dist_loss",
            simulation_time=self.simtime,
        )
        self.service_name = "heat_network_service"

    def test_service_is_on(self) -> None:
        # Test when control is provided and returns True
        # Set up HeatNetworkServiceSpace
        ctrl = SetpointTimeControl(
            schedule=[21.0, 21.0, None],
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1.0,
        )

        heat_network_service = HeatNetworkService(
            heat_network=self.heat_network, service_name=self.service_name, control=ctrl
        )
        assert heat_network_service.is_on()

        # Create a service without control
        heat_network_service_no_control = HeatNetworkService(
            heat_network=self.heat_network, service_name=self.service_name
        )
        assert heat_network_service_no_control.is_on()


class TestHeatNetworkServiceWaterDirect:
    """Unit tests for HeatNetworkServiceWaterDirect class"""

    @pytest.fixture(autouse=True)
    def set_heat_network_service_water_direct(self) -> None:
        """Create HeatNetworkServiceWaterDirect object to be tested"""
        self.simtime = SimulationTime(start_time=0, end_time=2, step=1)
        self.energysupply = EnergySupply(fuel_type=FuelType.CUSTOM, simulation_time=self.simtime)
        energy_supply_conn_name_auxiliary = "heat_network_auxiliary"
        energy_supply_conn_name_building_level_distribution_losses = (
            "HeatNetwork_building_level_distribution_losses"
        )

        self.heat_network = HeatNetwork(
            power_max=18.0,
            daily_loss=1.0,
            power_circ_pump=0,
            power_aux=0,
            building_level_distribution_losses=0.8,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=energy_supply_conn_name_auxiliary,
            energy_supply_conn_name_building_level_distribution_losses=energy_supply_conn_name_building_level_distribution_losses,
            simulation_time=self.simtime,
        )

        coldwatertemps = [1.0, 1.2]
        self.coldfeed = ColdWaterSource(
            cold_water_temps=coldwatertemps,
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )
        return_temp = 60

        self.heat_network_service_water_direct = self.heat_network.create_service_hot_water_direct(
            service_name="heat_network_test",
            temp_hot_water=return_temp,
            cold_feed=self.coldfeed,
        )

    def test_heat_network_service_water(self) -> None:
        """Test that HeatNetwork object returns correct hot water energy demand"""
        expected_demand = [7.5834, 2.2279]
        usage_events = [
            [
                WaterEventResult(
                    type="Other",
                    temperature_warm=60.0,
                    volume_warm=34.93868988826640,
                    volume_hot=34.93868988826640,
                    event_duration=0.0,
                ),
                WaterEventResult(
                    type="Other",
                    temperature_warm=60.0,
                    volume_warm=75.65325966014560,
                    volume_hot=75.65325966014560,
                    event_duration=0.0,
                ),
                WaterEventResult(
                    type="Other",
                    temperature_warm=60.0,
                    volume_warm=0.0,
                    volume_hot=0.0,
                    event_duration=0.0,
                ),
            ],
            [
                WaterEventResult(
                    type="Other",
                    temperature_warm=60.0,
                    volume_warm=32.60190808710678,
                    volume_hot=32.60190808710678,
                    event_duration=0.0,
                ),
            ],
        ]
        for t_idx, _, _ in self.simtime:
            assert self.heat_network_service_water_direct.demand_hot_water(
                usage_events=usage_events[t_idx]
            ) == pytest.approx(expected_demand[t_idx], abs=1e-3), "incorrect energy_output_provided"
            self.heat_network.timestep_end()

    def test_get_cold_water_source(self) -> None:
        """Test that the given cold water source is returned from get_cold_water_source"""
        assert self.heat_network_service_water_direct.get_cold_water_source() == self.coldfeed

    def test_get_temp_hot_water(self) -> None:
        """Test that the correct temperature is returned from get_temp_hot_water"""
        assert self.heat_network_service_water_direct.get_temp_hot_water(12.0) == [(60, 12.0)]

    def test_demand_hot_water_empty_volume_demanded_target(self) -> None:
        """Test that a zero value is returned from demand_hot_water without 'temp_hot_water'"""
        assert self.heat_network_service_water_direct.demand_hot_water(usage_events=[]) == 0


class TestHeatNetworkServiceWaterStorage:
    """Unit tests for HeatNetworkServiceWaterStorage class"""

    @pytest.fixture(autouse=True)
    def setup_heat_network_service_water_storage(self) -> None:
        """Create HeatNetworkServiceWaterStorage object to be tested"""
        self.simtime = SimulationTime(start_time=0, end_time=2, step=1)
        self.energysupply = EnergySupply(fuel_type=FuelType.CUSTOM, simulation_time=self.simtime)
        energy_supply_conn_name_auxiliary = "heat_network_auxiliary"
        energy_supply_conn_name_building_level_distribution_losses = (
            "HeatNetwork_building_level_distribution_losses"
        )

        self.controlmin = SetpointTimeControl(
            schedule=[52, 52], simulation_time=self.simtime, start_day=0, time_series_step=1
        )
        self.controlmax = SetpointTimeControl(
            schedule=[60, 60], simulation_time=self.simtime, start_day=0, time_series_step=1
        )

        # Set up HeatNetwork
        self.heat_network = HeatNetwork(
            power_max=7.0,
            daily_loss=1.0,
            power_circ_pump=0,
            power_aux=0,
            building_level_distribution_losses=0.8,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=energy_supply_conn_name_auxiliary,
            energy_supply_conn_name_building_level_distribution_losses=energy_supply_conn_name_building_level_distribution_losses,
            simulation_time=self.simtime,
        )
        self.heat_network_service_water_storage = (
            self.heat_network.create_service_hot_water_storage(
                service_name="heat_network_test",
                controlmin=self.controlmin,
                controlmax=self.controlmax,
            )
        )

    def test_heat_network_service_water_storage(self) -> None:
        """Test that HeatNetwork object returns correct energy demand for the storage tank"""
        # TODO update results
        energy_demanded = [10.0, 2.0]
        expected_demand = [7.0, 2.0]
        for t_idx, _, _ in self.simtime:
            assert self.heat_network_service_water_storage.demand_energy(
                energy_demand=energy_demanded[t_idx],
                temp_flow=None,
                temp_return=None,
            ) == pytest.approx(expected_demand[t_idx]), "incorrect energy_output_provided"
            self.heat_network.timestep_end()

    def test_energy_output_max(self) -> None:
        """Test that Heat Network object returns correct energy output"""
        temp_flow = [15.0, 20.0]
        temp_return = [10.0, 15.0]
        expected_output = [7.0, 7.0]
        for t_idx, _, _ in self.simtime:
            assert self.heat_network_service_water_storage.energy_output_max(
                temp_flow=temp_flow[t_idx],
                temp_return=temp_return[t_idx],
            ) == pytest.approx(expected_output[t_idx]), "incorrect energy_output_provided"
            self.heat_network.timestep_end()

    def test_demand_energy_if_off(self) -> None:
        """Test that there is no demand when the control is off"""
        control_mock = MagicMock()
        control_mock.is_on.return_value = False

        heat_network_service_water_storage = HeatNetworkServiceWaterStorage(
            heat_network=self.heat_network,
            service_name="heat_network_test",
            controlmin=control_mock,
            controlmax=self.controlmax,
        )

        assert (
            heat_network_service_water_storage.demand_energy(
                energy_demand=10, temp_flow=None, temp_return=None
            )
            == 0
        )

    def test_energy_output_max_if_off(self) -> None:
        """Test that the maximum energy output is zero when the control is off"""
        control_mock = MagicMock()
        control_mock.is_on.return_value = False

        heat_network_service_water_storage = HeatNetworkServiceWaterStorage(
            heat_network=self.heat_network,
            service_name="heat_network_test",
            controlmin=control_mock,
            controlmax=self.controlmax,
        )

        assert (
            heat_network_service_water_storage.energy_output_max(temp_flow=10, temp_return=10) == 0
        )


class TestHeatNetworkServiceSpace:
    """Unit tests for HeatNetworkServiceSpace class"""

    @pytest.fixture(autouse=True)
    def setup_heat_network_space(self) -> None:
        """Create HeatNetworkServiceSpace object to be tested"""
        self.simtime = SimulationTime(start_time=0, end_time=3, step=1)
        self.energysupply = EnergySupply(fuel_type=FuelType.MAINS_GAS, simulation_time=self.simtime)
        energy_supply_conn_name_auxiliary = "Boiler_auxiliary"
        energy_supply_conn_name_building_level_distribution_losses = (
            "HeatNetwork_building_level_distribution_losses"
        )

        # Set up HeatNetwork
        self.heat_network = HeatNetwork(
            power_max=5.0,
            daily_loss=1.0,
            power_circ_pump=0,
            power_aux=0,
            building_level_distribution_losses=0.8,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=energy_supply_conn_name_auxiliary,
            energy_supply_conn_name_building_level_distribution_losses=energy_supply_conn_name_building_level_distribution_losses,
            simulation_time=self.simtime,
        )
        self.ctrl = SetpointTimeControl(
            schedule=[21.0, 21.0, None],
            simulation_time=self.simtime,
            start_day=0,  # start_day
            time_series_step=1.0,  # time_series_step
        )
        self.heat_network_service_space = self.heat_network.create_service_space_heating(
            service_name="heat_network_test",
            control=self.ctrl,
        )

    def test_heat_network_service_space(self) -> None:
        """Test that HeatNetworkServiceSpace object returns correct space heating energy demand"""
        energy_demanded = [10.0, 2.0, 2.0]
        temp_flow = [55.0, 65.0, 65.0]
        temp_return = [50.0, 60.0, 60.0]
        for t_idx, _, _ in self.simtime:
            assert self.heat_network_service_space.demand_energy(
                energy_demand=energy_demanded[t_idx],
                temp_flow=temp_flow[t_idx],
                temp_return=temp_return[t_idx],
            ) == pytest.approx([5.0, 0.0, 0.0][t_idx])

    def test_energy_output_max(self) -> None:
        """Test that HeatNetworkServiceSpace object returns correct energy output"""
        temp_output = [55.0, 65.0, 65.0]
        temp_return_feed = [10.0, 15.0, 20.0]
        for t_idx, _, _ in self.simtime:
            assert self.heat_network_service_space.energy_output_max(
                temp_output=temp_output[t_idx], temp_return_feed=temp_return_feed[t_idx]
            ) == pytest.approx([5.0, 5.0, 0.0][t_idx])

            self.heat_network.timestep_end()

    def test_temp_setpnt(self) -> None:
        """Test that the correct setpoints are returned from temp_setpnt"""
        expected_results = [21, 21, None]
        for t_idx, _, _ in self.simtime:
            assert self.heat_network_service_space.temp_setpnt() == expected_results[t_idx]

    def test_in_required_period(self) -> None:
        """Test that the correct values are returned from in_required_period"""
        expected_results = [True, True, False]
        for t_idx, _, _ in self.simtime:
            assert self.heat_network_service_space.in_required_period() == expected_results[t_idx]


class TestHeatNetwork:
    """Unit tests for HeatNetwork class"""

    @pytest.fixture(autouse=True)
    def setup_heat_network(self) -> None:
        """Create HeatNetwork object to be tested"""
        self.simtime = SimulationTime(start_time=0, end_time=2, step=1)
        self.energysupply = EnergySupply(fuel_type=FuelType.CUSTOM, simulation_time=self.simtime)
        energy_supply_conn_name_auxiliary = "heat_network_auxiliary"
        energy_supply_conn_name_building_level_distribution_losses = (
            "HeatNetwork_building_level_distribution_losses"
        )

        # Set up HeatNetwork object
        self.heat_network = HeatNetwork(
            power_max=6.0,
            daily_loss=0.24,
            power_circ_pump=0.08,
            power_aux=0.04,
            building_level_distribution_losses=0.8,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary=energy_supply_conn_name_auxiliary,
            energy_supply_conn_name_building_level_distribution_losses=energy_supply_conn_name_building_level_distribution_losses,
            simulation_time=self.simtime,
        )

        self.heat_network.create_service_space_heating(
            service_name="heat_network_test", control=MagicMock()
        )

    def test_energy_output_provided(self):
        """Test energy demand and auxiliary fuel calculations."""
        required = [2.0, 10.0]
        expected_provided = [2.0, 6.0]
        expected_aux = [0.07666, 0.13]
        for t_idx, _, _ in self.simtime:
            provided = self.heat_network.demand_energy(
                service_name="heat_network_test",
                service_type=HeatingServiceType.SPACE,
                energy_output_required=required[t_idx],
            )
            assert provided == pytest.approx(expected_provided[t_idx])
            self.heat_network.timestep_end()

            results = self.energysupply.results_by_end_user()
            assert results["heat_network_test"][t_idx] == pytest.approx(expected_provided[t_idx])
            assert results["heat_network_auxiliary"][t_idx] == pytest.approx(
                expected_aux[t_idx], abs=1e-5
            )

    def test_HIU_loss(self) -> None:
        """Test that HeatNetwork object returns correct HIU loss"""
        assert self.heat_network.HIU_loss() == pytest.approx(0.01), "incorrect HIU loss returned"

    def test_building_level_distribution_losses(self) -> None:
        """Test that HeatNetwork object returns correct building level distribution loss"""
        assert self.heat_network.building_level_loss() == 0.0008, (
            "incorrect building level distribution losses returned"
        )

    def test_create_service_connection(self) -> None:
        """Test that creating a duplicate service name raises ValueError."""
        service_connection_name = "new_service"

        self.heat_network.create_service_space_heating(
            service_name=service_connection_name, control=MagicMock()
        )

        with pytest.raises(ValueError):
            self.heat_network.create_service_space_heating(
                service_name=service_connection_name, control=MagicMock()
            )

    def test_create_service_hot_water_direct(self) -> None:
        """Test a HeatNetworkSeriviceWaterStorage object is created with EnergySupplyConnection"""
        service_name = "hot_water_direct"
        temp_hot_water = 50
        cold_feed = MagicMock()

        obj = self.heat_network.create_service_hot_water_direct(
            service_name=service_name, temp_hot_water=temp_hot_water, cold_feed=cold_feed
        )
        assert isinstance(obj, HeatNetworkServiceWaterDirect)

    def test_create_service_space_heating(self) -> None:
        """Test a HeatNetworkServiceSpace object is created with EnergySupplyConnection"""
        service_name = "hot_water_space"
        control = MagicMock()

        obj = self.heat_network.create_service_space_heating(
            service_name=service_name, control=control
        )
        assert isinstance(obj, HeatNetworkServiceSpace)

    def test_timestep_end(self) -> None:
        """Test at end of timestep appropriate functions are called"""
        mock_aux_conn = MagicMock(spec=EnergySupplyConnection)
        mock_dist_loss_conn = MagicMock(spec=EnergySupplyConnection)
        self.heat_network._HeatNetwork__energy_supply_connection_aux = mock_aux_conn  # type: ignore -> we need to use _HeatNetwork__ to access private attributes
        self.heat_network._HeatNetwork__energy_supply_connection_building_level_distribution_losses = mock_dist_loss_conn  # type: ignore -> we need to use _HeatNetwork__ to access private attributes
        self.heat_network._HeatNetwork__total_time_running_current_timestep = 0.25  # type: ignore -> we need to use _HeatNetwork__ to access private attributes

        self.heat_network.HIU_loss = MagicMock(return_value=10)
        self.heat_network.building_level_loss = MagicMock(return_value=20)

        self.heat_network.timestep_end()

        assert self.heat_network._HeatNetwork__total_time_running_current_timestep == 0.0  # noqa: float-compare  # type: ignore -> we need to use _HeatNetwork__ to access private attributes
        mock_aux_conn.demand_energy.assert_has_calls(
            [call(amount_demanded=10), call(amount_demanded=0.04)]
        )
        mock_dist_loss_conn.demand_energy.assert_called_once_with(amount_demanded=20)

    def test_create_service_hot_water_storage(self) -> None:
        """Test that the correct set points are returned from setpnt"""
        controlmin = SetpointTimeControl(
            schedule=[52, 52], simulation_time=self.simtime, start_day=0, time_series_step=1
        )
        controlmax = SetpointTimeControl(
            schedule=[60, 60], simulation_time=self.simtime, start_day=0, time_series_step=1
        )
        water_storage = self.heat_network.create_service_hot_water_storage(
            service_name="name", controlmin=controlmin, controlmax=controlmax
        )
        assert water_storage.setpnt() == (52, 60)

    def test_demand_energy_with_zero_power(self) -> None:
        """Test that there is zero demand energy when the maximum power is zero"""
        heat_network = HeatNetwork(
            power_max=0,
            daily_loss=0.24,
            power_circ_pump=0,
            power_aux=0,
            building_level_distribution_losses=0.8,
            energy_supply=self.energysupply,
            energy_supply_conn_name_auxiliary="heat_network_auxiliary_new",
            energy_supply_conn_name_building_level_distribution_losses="HeatNetwork_building_level_distribution_losses_new",
            simulation_time=self.simtime,
        )

        heat_network.create_service_space_heating(service_name="name", control=MagicMock())

        assert (
            heat_network.demand_energy(
                service_name="name",
                service_type=HeatingServiceType.SPACE,
                energy_output_required=10,
            )
            == 0
        )
