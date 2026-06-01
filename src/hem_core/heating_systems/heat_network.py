#!/usr/bin/env python3
"""
This module provides objects to model heat networks
"""

from __future__ import annotations

import math

import hem_core.water_heat_demand.misc as misc
from hem_core.controls.time_control import ControlSetPoint, ControlSimple
from hem_core.energy_supply.energy_supply import EnergySupply
from hem_core.heating_systems.enums import HeatingServiceType
from hem_core.simulation_time import SimulationTime
from hem_core.units import W_per_kW, hours_per_day
from hem_core.water_heat_demand.cold_water_source import ColdWaterSource
from hem_core.water_heat_demand.misc import WaterEventResult


class HeatNetworkService:
    """A base class for objects representing services (e.g. water heating) provided by a heat network.

    This object encapsulates the name of the service, meaning that the system
    consuming the energy does not have to specify this on every call, and
    helping to enforce that each service has a unique name.

    Derived objects provide a place to handle parts of the calculation (e.g.
    distribution flow temperature) that may differ for different services.

    Separate subclasses need to be implemented for different types of service
    (e.g. HW and space heating). These should implement the following functions:
    - demand_energy(self, energy_demand)
    """

    def __init__(
        self, heat_network: HeatNetwork, service_name: str, control: ControlSimple | None = None
    ):
        """Construct a HeatNetworkService object

        Arguments:
        heat_network -- reference to the HeatNetwork object providing the service
        service_name -- name of the service demanding energy from the boiler
        control -- reference to a control object which must implement is_on() func
        """
        self._heat_network = heat_network
        self._service_name = service_name
        self.__control = control

    def is_on(self) -> bool:
        if self.__control is not None:
            service_on = self.__control.is_on()
        else:
            service_on = True
        return service_on


class HeatNetworkServiceWaterDirect(HeatNetworkService):
    """An object to represent a water heating service provided by a heat network.

    This object contains the parts of the heat network calculation that are
    specific to providing hot water directly to the dwelling.
    """

    def __init__(
        self,
        heat_network: HeatNetwork,
        service_name: str,
        temp_hot_water: float,
        cold_feed: ColdWaterSource,
        simulation_time: SimulationTime,
    ):
        """Construct a HeatNetworkWater object

        Arguments:
        heat_network       -- reference to the HeatNetwork object providing the service
        service_name       -- name of the service demanding energy from the heat network
        temp_hot_water     -- temperature of the hot water to be provided, in deg C
        cold_feed          -- reference to ColdWaterSource object
        simulation_time    -- reference to SimulationTime object
        """
        super().__init__(heat_network, service_name)

        self.__temp_hot_water = temp_hot_water
        self.__cold_feed = cold_feed
        self.__service_name = service_name
        self.__simulation_time = simulation_time

    def get_cold_water_source(self) -> ColdWaterSource:
        return self.__cold_feed

    def get_temp_hot_water(
        self, volume_req: float, volume_req_already: float = 0.0
    ) -> list[tuple[float, float]]:
        # Always supplies the whole volume at the same temperature, so list has a single element
        return [(self.__temp_hot_water, volume_req)]

    def demand_hot_water(self, usage_events: list[WaterEventResult]) -> float:
        """Demand energy for hot water (in kWh) from the heat network"""
        energy_demand = 0.0
        for event in usage_events:
            if math.isclose(event.volume_hot, 0.0, abs_tol=1e-10):
                continue
            list_temp_vol = self.__cold_feed.draw_off_water(volume_needed=event.volume_hot)
            temp_cold_water = math.fsum(t * v for t, v in list_temp_vol) / math.fsum(
                v for _, v in list_temp_vol
            )

            energy_demand += misc.water_demand_to_kWh(
                litres_demand=event.volume_hot,
                demand_temperature=self.__temp_hot_water,
                cold_temperature=temp_cold_water,
            )
        return self._heat_network.demand_energy(
            service_name=self.__service_name,
            service_type=HeatingServiceType.DOMESTIC_HOT_WATER_DIRECT,
            energy_output_required=energy_demand,
        )


class HeatNetworkServiceWaterStorage(HeatNetworkService):
    """An object to represent a water heating service provided by a heat network.

    This object contains the parts of the heat network calculation that are
    specific to providing hot water to the dwelling via a hot water cylinder.
    """

    def __init__(
        self,
        heat_network: HeatNetwork,
        service_name: str,
        controlmin: ControlSetPoint,
        controlmax: ControlSetPoint,
    ):
        """Construct a HeatNetworkWaterStorage object

        Arguments:
        heat_network -- reference to the HeatNetwork object providing the service
        service_name -- name of the service demanding energy from the heat network
        controlmin   -- reference to a control object which must select current
                     the minimum timestep temperature
        controlmax   -- reference to a control object which must select current
                     the maximum timestep temperature
        """
        super().__init__(heat_network, service_name, controlmin)
        self.__controlmin = controlmin
        self.__controlmax = controlmax

        self.__service_name = service_name

    def setpnt(self) -> tuple[float | None, float | None]:
        """Return setpoint (not necessarily temperature)"""
        return self.__controlmin.setpnt(), self.__controlmax.setpnt()

    def demand_energy(
        self, energy_demand: float, temp_flow: float | None, temp_return: float | None
    ) -> float:
        """Demand energy (in kWh) from the heat network"""
        if not self.is_on():
            return 0.0

        # Calculate energy needed to cover losses
        return self._heat_network.demand_energy(
            service_name=self.__service_name,
            service_type=HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
            energy_output_required=energy_demand,
        )

    def energy_output_max(self, temp_flow: float, temp_return: float) -> float:
        """Calculate the maximum energy output of the heat network"""
        if not self.is_on():
            return 0.0

        return self._heat_network.energy_output_max()


class HeatNetworkServiceSpace(HeatNetworkService):
    """An object to represent a space heating service provided by a heat network.

    This object contains the parts of the heat network calculation that are
    specific to providing space heating-.
    """

    def __init__(self, heat_network: HeatNetwork, service_name: str, control: ControlSetPoint):
        """Construct a HeatNetworkSpace object

        Arguments:
        heat_network -- reference to the HeatNetwork object providing the service
        service_name -- name of the service demanding energy from the heat network
        control -- reference to a control object which must implement is_on() and setpnt() funcs
        """
        super().__init__(heat_network, service_name, control)

        self.__service_name = service_name
        self.__control = control

    def demand_energy(
        self,
        energy_demand: float,
        temp_flow: float,
        temp_return: float,
        time_start: float = 0.0,
        update_heat_source_state: bool = True,
    ) -> float:
        """Demand energy (in kWh) from the heat network"""
        if not self.is_on():
            return 0.0

        return self._heat_network.demand_energy(
            service_name=self.__service_name,
            service_type=HeatingServiceType.SPACE,
            energy_output_required=energy_demand,
            time_start=time_start,
            update_heat_source_state=update_heat_source_state,
        )

    def energy_output_max(
        self, temp_output: float, temp_return_feed: float, time_start: float = 0.0
    ) -> float:
        """Calculate the maximum energy output of the heat network"""
        if not self.is_on():
            return 0.0

        return self._heat_network.energy_output_max(time_start=time_start)

    def temp_setpnt(self) -> float | None:
        return self.__control.setpnt()

    def in_required_period(self) -> bool:
        return self.__control.in_required_period()


class HeatNetwork:
    """An object to represent a heat network"""

    def __init__(
        self,
        power_max: float,
        daily_loss: float,
        power_circ_pump: float,
        power_aux: float,
        building_level_distribution_losses: float,
        energy_supply: EnergySupply,
        energy_supply_conn_name_auxiliary: str,
        energy_supply_conn_name_building_level_distribution_losses: str,
        simulation_time: SimulationTime,
    ):
        """Construct a HeatNetwork object

        Arguments:
        power_max -- maximum power output of HIU, in kW
        daily_loss -- daily loss from the HIU, in kWh/day
        power_circ_pump -- Power consumption of heating circuit pump in kW
        power_aux -- Power consumption of auxiliary electrical usage
        building_level_distribution_losses -- building level distribution losses in Watts
        energy_supply       -- reference to EnergySupply object
        energy_supply_conn_name_auxiliary -- name to use for reporting auxiliary energy use
        energy_supply_conn_name_building_level_distribution_losses
            -- name to use for reporting building level distribution losses energy use
        simulation_time     -- reference to SimulationTime object

        Other variables:
        energy_supply_connections -- dictionary with service name strings as keys and corresponding
                                     EnergySupplyConnection objects as values
        temp_hot_water            -- temperature of the hot water to be provided, in deg C
        cold_feed                 -- reference to ColdWaterSource object
        """
        self.__power_max = power_max
        self.__daily_loss = daily_loss
        self.__power_circ_pump = power_circ_pump
        self.__power_aux = power_aux
        self.__building_level_distribution_losses = building_level_distribution_losses
        self.__energy_supply = energy_supply
        self.__simulation_time = simulation_time
        self.__energy_supply_connections = {}
        self.__energy_supply_connection_aux = self.__energy_supply.connection(
            energy_supply_conn_name_auxiliary
        )
        self.__energy_supply_connection_building_level_distribution_losses = (
            self.__energy_supply.connection(
                energy_supply_conn_name_building_level_distribution_losses
            )
        )
        self.__total_time_running_current_timestep = 0.0
        self.__pump_running_time_current_timestep = 0.0

    def __create_service_connection(self, service_name: str) -> None:
        """Create an EnergySupplyConnection for the service name given"""
        # Check that service_name is not already registered
        if service_name in self.__energy_supply_connections.keys():
            raise ValueError(f"Error: Service name already used: {service_name}")
            # TODO Exit just the current case instead of whole program entirely?

        # Set up EnergySupplyConnection for this service
        self.__energy_supply_connections[service_name] = self.__energy_supply.connection(
            end_user_name=service_name
        )

    def create_service_hot_water_direct(
        self,
        service_name: str,
        temp_hot_water: float,
        cold_feed: ColdWaterSource,
    ) -> HeatNetworkServiceWaterDirect:
        """Return a HeatNetworkSeriviceWaterDirect object and create an EnergySupplyConnection for it

        Arguments:
        service_name      -- name of the service demanding energy from the heat network
        temp_hot_water    -- temperature of the hot water to be provided, in deg C
        cold_feed         -- reference to ColdWaterSource object
        """
        self.__create_service_connection(service_name=service_name)

        return HeatNetworkServiceWaterDirect(
            heat_network=self,
            service_name=service_name,
            temp_hot_water=temp_hot_water,
            cold_feed=cold_feed,
            simulation_time=self.__simulation_time,
        )

    def create_service_hot_water_storage(
        self, service_name: str, controlmin: ControlSetPoint, controlmax: ControlSetPoint
    ) -> HeatNetworkServiceWaterStorage:
        """Return a HeatNetworkSeriviceWaterStorage object and create an EnergySupplyConnection for it

        Arguments:
        service_name -- name of the service demanding energy from the heat network
        controlmin            -- reference to a control object which must select current
                                the minimum timestep temperature
        controlmax            -- reference to a control object which must select current
                                the maximum timestep temperature
        """
        self.__create_service_connection(service_name=service_name)

        return HeatNetworkServiceWaterStorage(
            self, service_name=service_name, controlmin=controlmin, controlmax=controlmax
        )

    def create_service_space_heating(self, service_name: str, control: ControlSetPoint):
        """Return a HeatNetworkServiceSpace object and create an EnergySupplyConnection for it

        Arguments:
        service_name -- name of the service demanding energy from the heat network
        control -- reference to a control object which must implement is_on() and setpnt() funcs
        """
        self.__create_service_connection(service_name=service_name)

        return HeatNetworkServiceSpace(self, service_name=service_name, control=control)

    def energy_output_max(self, time_start: float = 0.0) -> float:
        """Calculate the maximum energy output of the heat network, accounting
            for time spent on higher-priority services.

        Note: Call via a HeatNetworkService object, not directly.
        """
        timestep = self.__simulation_time.timestep()
        time_available = self.__time_available(time_start=time_start, timestep=timestep)
        return self.__power_max * time_available

    def __time_available(self, time_start: float, timestep: float) -> float:
        """Calculate time available for the current service"""
        # Assumes that time spent on other services is evenly spread throughout
        # the timestep so the adjustment for start time below is a proportional
        # reduction of the overall time available, not simply a subtraction
        time_available = (timestep - self.__total_time_running_current_timestep) * (
            1.0 - time_start / timestep
        )
        return time_available

    def demand_energy(
        self,
        service_name: str,
        service_type: HeatingServiceType,
        energy_output_required: float,
        time_start: float = 0.0,
        update_heat_source_state: bool = True,
    ) -> float:
        """Calculate energy required by heat network to satisfy demand for the service indicated."""
        energy_output_max = self.energy_output_max()
        if math.isclose(energy_output_max, 0.0, abs_tol=1e-10):
            return 0.0
        energy_output_provided = max(0.0, min(energy_output_required, energy_output_max))
        if update_heat_source_state:
            self.__energy_supply_connections[service_name].demand_energy(energy_output_provided)

        time_available = self.__time_available(
            time_start=time_start, timestep=self.__simulation_time.timestep()
        )
        if update_heat_source_state:
            time_running = (energy_output_provided / energy_output_max) * time_available
            self.__total_time_running_current_timestep += time_running
            # Track pump running time (only for storage DHW and space heating)
            # Direct DHW services don't use circulation pumps
            if service_type in (
                HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                HeatingServiceType.SPACE,
            ):
                self.__pump_running_time_current_timestep += time_running
            elif service_type == HeatingServiceType.DOMESTIC_HOT_WATER_DIRECT:
                pass  # Direct DHW doesn't use circulation pump
            else:
                raise ValueError(f"Unexpected service type: {service_type}")  # pragma: no cover

        return energy_output_provided

    def timestep_end(self) -> None:
        """Calculations to be done at the end of each timestep"""
        # Energy required to overcome losses
        self.__energy_supply_connection_aux.demand_energy(amount_demanded=self.HIU_loss())
        self.__energy_supply_connection_building_level_distribution_losses.demand_energy(
            amount_demanded=self.building_level_loss()
        )

        timestep = self.__simulation_time.timestep()
        time_remaining_current_timestep = timestep - self.__total_time_running_current_timestep

        self.__calc_auxiliary_energy(
            timestep=timestep, time_remaining_current_timestep=time_remaining_current_timestep
        )

        # Variables below need to be reset at the end of each timestep
        self.__total_time_running_current_timestep = 0.0
        self.__pump_running_time_current_timestep = 0.0

    def HIU_loss(self) -> float:
        """Standing heat loss from the HIU (heat interface unit) in kWh"""
        # daily_loss to be sourced from the PCDB, in kWh/day
        return self.__daily_loss / hours_per_day * self.__simulation_time.timestep()

    def building_level_loss(self) -> float:
        """Converts building level distribution loss from watts to kWh"""
        return (
            self.__building_level_distribution_losses / W_per_kW * self.__simulation_time.timestep()
        )

    def __calc_auxiliary_energy(
        self, timestep: float, time_remaining_current_timestep: float
    ) -> None:
        """Calculation of energy from pump"""
        energy_aux = self.__pump_running_time_current_timestep * self.__power_circ_pump

        energy_aux += timestep * self.__power_aux

        self.__energy_supply_connection_aux.demand_energy(amount_demanded=energy_aux)
