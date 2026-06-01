#!/usr/bin/env python3

"""
This module provides objects to represent boilers. The calculations are based
on the hourly method developed for calculating efficiency improvements for
different classes of boiler controls in SAP 10 Appendix D2.2 (described in the
SAP 10 technical paper S10TP-12). This in turn was based on a combination of
the DAHPSE method for heat pumps (itself based on a draft of
BS EN 15316-4-2:2017 and described in the SAP calculation method CALCM-01) and
the Energy Balance Validation (EBV) method (described in the SAP 2009 technical
paper STP09/B02).
"""

# Standard library imports
from __future__ import annotations

import math
from typing import Any, Literal, overload

from numpy import interp

# Local imports
import hem_core.units as units
import hem_core.water_heat_demand.misc as misc
from hem_core.controls.time_control import CombinationTimeControl, SetpointTimeControl, TimeControl
from hem_core.energy_supply.energy_supply import EnergySupply, EnergySupplyConnection
from hem_core.external_conditions import ExternalConditions
from hem_core.heating_systems.enums import HeatingServiceType
from hem_core.input_output.enums import BoilerHotWaterTest, FuelType, HeatSourceLocation
from hem_core.simulation_time import SimulationTime
from hem_core.water_heat_demand.cold_water_source import ColdWaterSource
from hem_core.water_heat_demand.misc import FRAC_DHW_ENERGY_INTERNAL_GAINS, WaterEventResult


class BoilerService:
    """A base class for objects representing services (e.g. water heating) provided by a boiler.

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
        self, boiler: Boiler, service_name: str, control: (TimeControl | None) = None
    ) -> None:
        """Construct a BoilerService object

        Arguments:
        boiler       -- reference to the Boiler object providing the service
        service_name -- name of the service demanding energy from the boiler
        control -- reference to a control object which must implement is_on() func
        """
        self._boiler = boiler
        self._service_name = service_name
        self.__control = control

    def is_on(self) -> bool:
        if self.__control is not None:
            service_on = self.__control.is_on()
        else:
            service_on = True
        return service_on


class BoilerServiceWaterCombi(BoilerService):
    """An object to represent a water heating service provided by a combi boiler.

    This object contains the parts of the boiler calculation that are
    specific to providing hot water.
    """

    def __init__(
        self,
        boiler: Boiler,
        boiler_data: dict[str, Any],
        service_name: str,
        temp_hot_water: float,
        cold_feed: ColdWaterSource,
        simulation_time: SimulationTime,
    ) -> None:
        """Construct a BoilerServiceWaterCombi object

        Arguments:
        boiler       -- reference to the Boiler object providing the service
        boiler_data       -- combi boiler heating properties
        service_name -- name of the service demanding energy from the boiler_data
        temp_hot_water -- temperature of the hot water to be provided, in deg C
        cold_feed -- reference to ColdWaterSource object
        simulation_time -- reference to SimulationTime object
        """
        super().__init__(boiler, service_name)

        self.__temp_hot_water = temp_hot_water
        self.__cold_feed = cold_feed
        self.__service_name = service_name
        self.__simulation_time = simulation_time

        # TODO daily hot water use is currently a single value user input.
        # It is an average of the daily use as provided in the
        # hot water events in the same input file.
        # Ideally, we should be processing the hot water events provided
        # and repeatedly recalculating this value. TBD if this should be
        # once for each calendar day, or on a rolling basis centred at each
        # hot water event.
        self.__daily_HW_usage = boiler_data["daily_HW_usage"]

        hw_tests = boiler_data["separate_DHW_tests"]
        self.__separate_DHW_tests = BoilerHotWaterTest(hw_tests)

        # values derived from tapping profiles in BS EN 13203-2:2018
        M_energy = 5.845
        M_num_continuous_events = 20
        M_average_temp_rise = 18
        M_average_HW_flowrate = 1.26
        S_num_events = 11
        M_num_events = 23
        L_num_events = 24

        if (self.__separate_DHW_tests == BoilerHotWaterTest.M_L) or (
            self.__separate_DHW_tests == BoilerHotWaterTest.M_S
        ):
            # tapping cycle M and S, or M and L
            self.__rejected_energy_1 = boiler_data["rejected_energy_1"]
            self.__storage_loss_factor_2 = boiler_data["storage_loss_factor_2"]
            self.__rejected_factor_3 = boiler_data["rejected_factor_3"]

            # create adjusted loss factors for use with instantaeous type combis.
            # currently we can do this just once, during boiler init.
            # if, in the future, daily_HW_usage is repeatedly recalculated from HW events
            # instead of being a user input of average daily HW usage, then adjustments
            # to loss factors for some combis tested to two profiles will also need to be
            # repeated.
            daily_vol_factor = self.get_daily_vol_factor()
            # r1 is adjusted to give us a value per event, per degree temp rise,
            # per l/min flow rate.
            self.__rejected_energy_1_adj = (
                (self.__rejected_energy_1 + daily_vol_factor * self.__rejected_factor_3) * M_energy
            ) / (M_num_continuous_events * M_average_temp_rise * M_average_HW_flowrate)

            # the daily loss factors from the PCDB are divided by the number of HW
            # events in the relevant testing profile to give us loss factors per event
            if self.__separate_DHW_tests == BoilerHotWaterTest.M_S:
                self.__storage_loss_factor_2_adj = self.__storage_loss_factor_2 / S_num_events
            elif self.__separate_DHW_tests == BoilerHotWaterTest.M_L:
                self.__storage_loss_factor_2_adj = self.__storage_loss_factor_2 / L_num_events

        elif (self.__separate_DHW_tests == BoilerHotWaterTest.M_ONLY) or (
            self.__separate_DHW_tests == BoilerHotWaterTest.NO_ADDITIONAL_TESTS
        ):
            # tapping cycle M only test results
            self.__rejected_energy_1 = boiler_data["rejected_energy_1"]
            self.__storage_loss_factor_1 = boiler_data["storage_loss_factor_1"]

            # create adjusted loss factors for use with instantaeous type combis
            # r1 is adjusted to give us a value per event, per degree temp rise,
            # per l/min flow rate.
            self.__rejected_energy_1_adj = (self.__rejected_energy_1 * M_energy) / (
                M_num_continuous_events * M_average_temp_rise * M_average_HW_flowrate
            )

            # daily loss factor 1 divided by 23 (events in test profile M)
            self.__storage_loss_factor_1_adj = self.__storage_loss_factor_1 / M_num_events

        else:
            raise ValueError("Invalid hot water test option")  # PRAGMA: nocover

    def get_daily_vol_factor(self):
        """The daily volume factor (DVF) is used in loss factor adjustments for combi boilers
        tested to two tapping profiles."""

        # Equivalent hot water litres at 60C for HW load profiles
        hw_litres_S_profile = 36.0
        hw_litres_M_profile = 100.2
        hw_litres_L_profile = 199.8

        daily_vol_factor = hw_litres_M_profile - self.__daily_HW_usage
        if (
            self.__separate_DHW_tests == BoilerHotWaterTest.M_S
            and self.__daily_HW_usage < hw_litres_S_profile
        ):
            daily_vol_factor = 64.2
        elif (
            self.__separate_DHW_tests == BoilerHotWaterTest.M_L
            and self.__daily_HW_usage < hw_litres_M_profile
        ) or (
            self.__separate_DHW_tests == BoilerHotWaterTest.M_S
            and self.__daily_HW_usage > hw_litres_M_profile
        ):
            daily_vol_factor = 0
        elif (
            self.__separate_DHW_tests == BoilerHotWaterTest.M_L
            and self.__daily_HW_usage > hw_litres_L_profile
        ):
            daily_vol_factor = -99.6

        return daily_vol_factor

    def get_cold_water_source(self) -> ColdWaterSource:
        return self.__cold_feed

    def get_temp_hot_water(
        self, volume_req: float, volume_req_already: float = 0.0
    ) -> list[tuple[float, float]]:
        # Always supplies the whole volume at the same temperature, so list has a single element
        return [(self.__temp_hot_water, volume_req)]

    def demand_hot_water(self, usage_events: list[WaterEventResult]) -> float | tuple[float, float]:
        """Demand volume from boiler. Currently combi only"""

        energy_demand = 0.0
        self.__combi_loss = 0.0
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

            # skip the combi loss calculation for pipeflush events as these
            # are part of the preceeding event and do not cause additional losses
            if event.type != "PipeFlush":
                # get the required temperature rise and the hot water
                # flow rate through the combi boiler for calculating combi losses
                deltaT = event.temperature_warm - temp_cold_water
                flowrate_hot = event.volume_hot / event.event_duration

                combi_loss = self.boiler_combi_loss(
                    deltaT=deltaT, flowrate=flowrate_hot, event_type=event.type
                )
                energy_demand = energy_demand + combi_loss
                self.__combi_loss += combi_loss

        return self._boiler._demand_energy(
            service_name=self.__service_name,
            service_type=HeatingServiceType.DOMESTIC_HOT_WATER_COMBI,
            energy_output_required=energy_demand,
            temp_return_feed=self.__temp_hot_water,
        )

    def boiler_combi_loss(self, deltaT: float, flowrate: float, event_type: str) -> float:
        # for basin type events (currently in HEM this is only Bath events)
        # all heated water is useful so there is no loss due to rejected energy
        if event_type == "Bath":
            rejected_energy = 0.0
        else:
            rejected_energy = self.__rejected_energy_1_adj

        combi_loss = 0.0
        if (self.__separate_DHW_tests == BoilerHotWaterTest.M_L) or (
            self.__separate_DHW_tests == BoilerHotWaterTest.M_S
        ):
            # combi loss calculation with tapping cycle M and S, or M and L
            combi_loss = (rejected_energy * deltaT * flowrate) + self.__storage_loss_factor_2_adj

        elif (self.__separate_DHW_tests == BoilerHotWaterTest.M_ONLY) or (
            self.__separate_DHW_tests == BoilerHotWaterTest.NO_ADDITIONAL_TESTS
        ):
            # combi loss calculation with tapping cycle M only test results
            combi_loss = (rejected_energy * deltaT * flowrate) + self.__storage_loss_factor_1_adj

        else:
            raise ValueError("Invalid hot water test option")

        self.__combi_loss = combi_loss
        return combi_loss

    def internal_gains(self) -> float:
        gain_internal = (
            FRAC_DHW_ENERGY_INTERNAL_GAINS
            * self.__combi_loss
            * units.W_per_kW
            / self.__simulation_time.timestep()
        )
        self.__combi_loss = 0.0
        return gain_internal

    def energy_output_max(self) -> float:
        """Calculate the maximum energy output of the boiler"""
        return self._boiler._energy_output_max()


class BoilerServiceWaterRegular(BoilerService):
    """An object to represent a water heating service provided by a regular boiler.

    This object contains the parts of the boiler calculation that are
    specific to providing hot water.
    """

    def __init__(
        self,
        boiler: Boiler,
        service_name: str,
        cold_feed: ColdWaterSource,
        simulation_time: SimulationTime,
        controlmin: (SetpointTimeControl | CombinationTimeControl),
        controlmax: (SetpointTimeControl | CombinationTimeControl),
    ) -> None:
        """Construct a BoilerServiceWaterRegular object

        Arguments:
        boiler       -- reference to the Boiler object providing the service
        service_name -- name of the service demanding energy from the boiler_data
        cold_feed -- reference to ColdWaterSource object
        simulation_time -- reference to SimulationTime object
        controlmin            -- reference to a control object which must select current
                                the minimum timestep temperature
        controlmax            -- reference to a control object which must select current
                                the maximum timestep temperature
        """
        super().__init__(boiler, service_name=service_name, control=controlmin)

        self.__cold_feed = cold_feed
        self.__service_name = service_name
        self.__simulation_time = simulation_time
        self.__controlmin = controlmin
        self.__controlmax = controlmax

    def setpnt(self) -> tuple[float | None, float | None]:
        """Return setpoint (not necessarily temperature)"""
        return self.__controlmin.setpnt(), self.__controlmax.setpnt()

    @overload
    def demand_energy(
        self,
        energy_demand: float,
        temp_flow: float,
        temp_return: float,
        hybrid_service: Literal[False],
        time_elapsed_hp: (float | None) = None,
        update_heat_source_state: bool = True,
    ) -> float: ...

    @overload
    def demand_energy(
        self,
        energy_demand: float,
        temp_flow: float,
        temp_return: float,
        hybrid_service: Literal[True],
        time_elapsed_hp: (float | None) = None,
        update_heat_source_state: bool = True,
    ) -> tuple[float, float]: ...

    def demand_energy(
        self,
        energy_demand: float,
        temp_flow: float,
        temp_return: float,
        hybrid_service: bool = False,
        time_elapsed_hp: (float | None) = None,
        update_heat_source_state: bool = True,
    ) -> float | tuple[float, float]:
        """Demand energy (in kWh) from the boiler"""
        service_on = self.is_on()
        if not service_on:
            energy_demand = 0.0

        if temp_return is None and not math.isclose(energy_demand, 0.0, abs_tol=1e-10):
            raise ValueError("temp_return is None and energy_demand is not 0.0")

        return self._boiler._demand_energy(
            service_name=self.__service_name,
            service_type=HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
            energy_output_required=energy_demand,
            temp_return_feed=temp_return,
            hybrid_service=hybrid_service,
            time_elapsed_hp=time_elapsed_hp,
            update_heat_source_state=update_heat_source_state,
        )

    def energy_output_max(
        self, temp_flow: float, temp_return: float, time_elapsed_hp: (float | None) = None
    ) -> float:
        """Calculate the maximum energy output of the boiler"""
        service_on = self.is_on()
        if not service_on:
            return 0.0

        return self._boiler._energy_output_max(
            time_elapsed_hp=time_elapsed_hp,
        )


class BoilerServiceSpace(BoilerService):
    """An object to represent a space heating service provided by a boiler to e.g. a cylinder.

    This object contains the parts of the boiler calculation that are
    specific to providing space heating-.
    """

    def __init__(
        self,
        boiler: Boiler,
        service_name: str,
        control: SetpointTimeControl | CombinationTimeControl | None,
    ) -> None:
        """Construct a BoilerServiceSpace object

        Arguments:
        boiler       -- reference to the Boiler object providing the service
        service_name -- name of the service demanding energy from the boiler
        control -- reference to a control object which must implement is_on() and setpnt() funcs
        """
        super().__init__(boiler=boiler, service_name=service_name, control=control)
        self.__service_name = service_name
        self.__control = control

    def temp_setpnt(self) -> float | None:
        if self.__control is not None:
            return self.__control.setpnt()

    def in_required_period(self) -> bool | None:
        if self.__control is not None:
            return self.__control.in_required_period()

    @overload
    def demand_energy(
        self,
        energy_demand: float,
        temp_flow: float,
        temp_return: float,
        hybrid_service: Literal[False],
        time_start: float = 0.0,
        time_elapsed_hp: (float | None) = None,
        update_heat_source_state: (bool | None) = True,
    ) -> float: ...

    @overload
    def demand_energy(
        self,
        energy_demand: float,
        temp_flow: float,
        temp_return: float,
        hybrid_service: Literal[True] = True,
        time_start: float = 0.0,
        time_elapsed_hp: (float | None) = None,
        update_heat_source_state: (bool | None) = True,
    ) -> tuple[float, float]: ...

    def demand_energy(
        self,
        energy_demand: float,
        temp_flow: float,
        temp_return: float,
        hybrid_service: (bool | None) = False,
        time_start: float = 0.0,
        time_elapsed_hp: (float | None) = None,
        update_heat_source_state: (bool | None) = True,
    ) -> float | tuple[float, float]:
        """Demand energy (in kWh) from the boiler"""
        if not self.is_on():
            energy_demand = 0.0

        return self._boiler._demand_energy(
            service_name=self.__service_name,
            service_type=HeatingServiceType.SPACE,
            energy_output_required=energy_demand,
            temp_return_feed=temp_return,
            time_start=time_start,
            hybrid_service=hybrid_service,
            time_elapsed_hp=time_elapsed_hp,
            update_heat_source_state=update_heat_source_state,
        )

    def energy_output_max(
        self,
        temp_output: float,
        temp_return_feed: float,
        time_start: float,
        time_elapsed_hp: (float | None) = None,
    ) -> float:
        """Calculate the maximum energy output of the boiler"""
        if not self.is_on():
            return 0.0

        return self._boiler._energy_output_max(
            time_start=time_start, time_elapsed_hp=time_elapsed_hp
        )


class Boiler:
    """An object to represent a boiler"""

    def __init__(
        self,
        boiler_dict: dict[str, Any],
        energy_supply: EnergySupply,
        energy_supply_conn_aux: EnergySupplyConnection,
        simulation_time: SimulationTime,
        ext_cond: ExternalConditions,
    ) -> None:
        """Construct a Boiler object"""
        self.__energy_supply = energy_supply
        self.__simulation_time = simulation_time
        self.__external_conditions = ext_cond
        self.__energy_supply_connections = {}
        self.__energy_supply_connection_aux = energy_supply_conn_aux
        self.__service_results = []

        # boiler properties
        self.__boiler_location = HeatSourceLocation(boiler_dict["boiler_location"])
        self.__min_modulation_load = boiler_dict["modulation_load"]
        self.__boiler_power = boiler_dict["rated_power"]
        full_load_gross = boiler_dict["efficiency_full_load"]
        part_load_gross = boiler_dict["efficiency_part_load"]
        self.__fuel_code = self.__energy_supply.fuel_type()

        # electricity properties
        self.__power_circ_pump = boiler_dict["electricity_circ_pump"]
        self.__power_part_load = boiler_dict["electricity_part_load"]
        self.__power_full_load = boiler_dict["electricity_full_load"]
        self.__power_standby = boiler_dict["electricity_standby"]
        self.__total_time_running_current_timestep = 0.0
        self.__pump_running_time_current_timestep = 0.0

        # high value correction
        net_to_gross = self.net_to_gross()
        full_load_net = full_load_gross / net_to_gross
        part_load_net = part_load_gross / net_to_gross
        corrected_full_load_net = self.high_value_correction_full_load(
            net_efficiency_full_load=full_load_net
        )
        corrected_part_load_net = self.high_value_correction_part_load(
            net_efficiency_part_load=part_load_net
        )
        self.__corrected_full_load_gross = corrected_full_load_net * net_to_gross
        corrected_part_load_gross = corrected_part_load_net * net_to_gross

        # SAP model properties
        self.__room_temp = 19.5  # TODO use actual room temp instead of hard coding

        # Nominal temperature difference between boiler and test room
        # during standby loss test (EN15502-1 or EN15034)
        self.__temp_rise_standby_loss = 50.0
        # boiler standby heat loss power law index
        self.__sby_loss_idx = 1.25

        # Calculate offset for EBV curves
        average_measured_eff = (corrected_part_load_gross + self.__corrected_full_load_gross) / 2.0
        # test conducted at return temperature 30C
        temp_part_load_test = 30.0
        # test conducted at return temperature 60C
        temp_full_load_test = 60.0
        offset_for_theoretical_eff = 0.0
        theoretical_eff_part_load = self.effvsreturntemp(
            return_temp=temp_part_load_test, offset=offset_for_theoretical_eff
        )
        theoretical_eff_full_load = self.effvsreturntemp(
            return_temp=temp_full_load_test, offset=offset_for_theoretical_eff
        )
        average_theoretical_eff = (theoretical_eff_part_load + theoretical_eff_full_load) / 2.0
        self.__offset = average_theoretical_eff - average_measured_eff

    def __create_service_connection(self, service_name: str) -> None:
        """Create an EnergySupplyConnection for the service name given"""
        # Check that service_name is not already registered
        if service_name in self.__energy_supply_connections.keys():
            raise ValueError("Error: Service name already used: " + service_name)
            # TODO Exit just the current case instead of whole program entirely?

        # Set up EnergySupplyConnection for this service
        self.__energy_supply_connections[service_name] = self.__energy_supply.connection(
            end_user_name=service_name
        )

    def create_service_hot_water_combi(
        self,
        boiler_data: dict[str, Any],
        service_name: str,
        temp_hot_water: float,
        cold_feed: ColdWaterSource,
    ) -> BoilerServiceWaterCombi:
        """Return a BoilerServiceWater object and create an EnergySupplyConnection for it

        Arguments:
        boiler_data -- boiler hot water heating properties
        service_name -- name of the service demanding energy from the boiler
        temp_hot_water -- temperature of the hot water to be provided, in deg C
        cold_feed -- reference to ColdWaterSource object
        """
        self.__create_service_connection(service_name=service_name)
        return BoilerServiceWaterCombi(
            self,
            boiler_data=boiler_data,
            service_name=service_name,
            temp_hot_water=temp_hot_water,
            cold_feed=cold_feed,
            simulation_time=self.__simulation_time,
        )

    def create_service_hot_water_regular(
        self,
        service_name: str,
        cold_feed: ColdWaterSource,
        controlmin: (SetpointTimeControl | CombinationTimeControl),
        controlmax: (SetpointTimeControl | CombinationTimeControl),
    ) -> BoilerServiceWaterRegular:
        """Return a BoilerServiceWaterRegular object and create an EnergySupplyConnection for it

        Arguments:
        service_name -- name of the service demanding energy from the boiler
        temp_limit_upper -- upper operating limit for temperature, in deg C
        cold_feed -- reference to ColdWaterSource object
        controlmin      -- reference to a control object which must select current
                        the minimum timestep temperature
        controlmax      -- reference to a control object which must select current
                        the maximum timestep temperature
        """

        self.__create_service_connection(service_name=service_name)
        return BoilerServiceWaterRegular(
            self,
            service_name=service_name,
            cold_feed=cold_feed,
            simulation_time=self.__simulation_time,
            controlmin=controlmin,
            controlmax=controlmax,
        )

    def create_service_space_heating(
        self,
        service_name: str,
        control: SetpointTimeControl | CombinationTimeControl | None,
    ) -> BoilerServiceSpace:
        """Return a BoilerServiceSpace object and create an EnergySupplyConnection for it

        Arguments:
        service_name -- name of the service demanding energy from the boiler
        control -- reference to a control object which must implement is_on() and setpnt() funcs
        """
        self.__create_service_connection(service_name=service_name)
        return BoilerServiceSpace(
            self,
            service_name=service_name,
            control=control,
        )

    def __cycling_adjustment(
        self,
        temp_return_feed: float,
        standing_loss: float,
        prop_of_timestep_at_min_rate: float,
        temp_boiler_loc: float,
    ) -> float:
        ton_toff = (1.0 - prop_of_timestep_at_min_rate) / prop_of_timestep_at_min_rate
        cycling_adjustment = (
            standing_loss
            * ton_toff
            * ((temp_return_feed - temp_boiler_loc) / (self.__temp_rise_standby_loss))
            ** self.__sby_loss_idx
        )

        return cycling_adjustment

    def location_adjustment(
        self, temp_return_feed: float, standing_loss: float, temp_boiler_loc: float
    ) -> float:
        # If boiler location is not colder than return feed, no location adjustment needed
        if temp_return_feed < temp_boiler_loc or math.isclose(
            temp_return_feed, temp_boiler_loc, abs_tol=1e-10
        ):
            return 0.0

        # If return feed is not above room temperature, no location adjustment needed
        if temp_return_feed < self.__room_temp or math.isclose(
            temp_return_feed, self.__room_temp, abs_tol=1e-10
        ):
            return 0.0

        location_adjustment = max(
            (
                standing_loss
                / self.__temp_rise_standby_loss**self.__sby_loss_idx
                * (
                    (temp_return_feed - temp_boiler_loc) ** self.__sby_loss_idx
                    - (temp_return_feed - self.__room_temp) ** self.__sby_loss_idx
                )
            ),
            0.0,
        )
        return location_adjustment

    def __calc_current_boiler_power(
        self, energy_output_provided: float, time_available: float
    ) -> float:
        if time_available <= 0:
            return 0.0

        min_power = self.__boiler_power * self.__min_modulation_load

        current_boiler_power = max(energy_output_provided / time_available, min_power)

        return current_boiler_power

    def calc_boiler_eff(
        self,
        service_type: HeatingServiceType | None,
        temp_return_feed: float,
        energy_output_required: float,
        time_start: float = 0.0,
        time_elapsed_hp: (float | None) = None,
    ) -> float:
        time_available = self.__time_available(time_start, time_elapsed_hp)
        return self.__calc_boiler_eff(
            service_type=service_type,
            temp_return_feed=temp_return_feed,
            energy_output_required=energy_output_required,
            time_available=time_available,
        )

    def __calc_boiler_eff(
        self,
        service_type: HeatingServiceType | None,
        temp_return_feed: float,
        energy_output_required: float,
        time_available: float,
    ) -> float:
        energy_output_provided = self.__calc_energy_output_provided(
            energy_output_required=energy_output_required, time_available=time_available
        )

        current_boiler_power = self.__calc_current_boiler_power(
            energy_output_provided=energy_output_provided, time_available=time_available
        )

        # The efficiency of the boiler depends on whether it cycles on/off.
        # If this occurs, an adjustment is calculated for the calculation
        # timestep as follows (when the boiler is firing continuously no
        # adjustment is necessary so cycling_adjustment=0).
        if time_available <= 0.0:
            prop_of_timestep_at_min_rate = 0.0
        else:
            prop_of_timestep_at_min_rate = min(
                energy_output_required
                / (self.__boiler_power * self.__min_modulation_load * time_available),
                1.0,
            )

        # Default value for the stand-by heat losses as a function of the current boiler power
        # Equation 5 in EN15316-4-1
        # fgen = (c5*(Pn)^c6)/100
        # where c5 = 4.0, c6 = -0.4 and Pn is the current boiler power
        if math.isclose(current_boiler_power, 0.0, abs_tol=1e-10):
            standing_loss = 0.0
        else:
            standing_loss = (4.0 * (current_boiler_power) ** -0.4) / 100.0

        # use weather temperature at timestep
        outside_temp = self.__external_conditions.air_temp()

        # A boiler’s efficiency reduces when installed outside due to an increase in case heat loss.
        # The following adjustment is made when the boiler is located outside
        # (when installed inside no adjustment is necessary so location_adjustment=0)
        temps_based_on_boiler_location = {
            HeatSourceLocation.EXTERNAL: outside_temp,
            HeatSourceLocation.INTERNAL: self.__room_temp,
        }
        temp_boiler_loc = temps_based_on_boiler_location[self.__boiler_location]

        # Calculate location adjustment
        location_adjustment = 0.0
        if self.__boiler_location == HeatSourceLocation.EXTERNAL:
            location_adjustment = self.location_adjustment(
                temp_return_feed=temp_return_feed,
                standing_loss=standing_loss,
                temp_boiler_loc=temp_boiler_loc,
            )

        # Calculate cycling adjustment
        cycling_adjustment = 0.0
        if (
            0.0 < prop_of_timestep_at_min_rate < 1.0
        ) and service_type != HeatingServiceType.DOMESTIC_HOT_WATER_COMBI:
            cycling_adjustment = self.__cycling_adjustment(
                temp_return_feed=temp_return_feed,
                standing_loss=standing_loss,
                prop_of_timestep_at_min_rate=prop_of_timestep_at_min_rate,
                temp_boiler_loc=temp_boiler_loc,
            )

        # Calculate combined cyclic and location adjustment
        cyclic_location_adjustment = cycling_adjustment + location_adjustment

        # Calculate boiler efficiency based on the return temperature and offset
        boiler_eff = self.effvsreturntemp(return_temp=temp_return_feed, offset=self.__offset)

        # If boiler starts cycling use the corrected full load efficiency
        # as the boiler eff before cycling adjustment is applied.
        if cycling_adjustment > 0.0:
            boiler_eff = self.__corrected_full_load_gross

        # Calculate the final boiler efficiency
        blr_eff_final = 1.0 / ((1.0 / boiler_eff) + cyclic_location_adjustment)

        return blr_eff_final

    def __calc_energy_output_provided(
        self, energy_output_required: float, time_available: float
    ) -> float:
        energy_output_max_power = self.__boiler_power * time_available
        energy_output_provided = min(energy_output_required, energy_output_max_power)

        return energy_output_provided

    def __time_available(self, time_start: float, time_elapsed_hp: (float | None) = None) -> float:
        """Calculate time available for the current service"""
        # Assumes that time spent on other services is evenly spread throughout
        # the timestep so the adjustment for start time below is a proportional
        # reduction of the overall time available, not simply a subtraction
        timestep = self.__simulation_time.timestep()
        total_time_running_current_timestep = (
            time_elapsed_hp
            if time_elapsed_hp is not None
            else self.__total_time_running_current_timestep
        )
        time_available = (timestep - total_time_running_current_timestep) * (
            1.0 - time_start / timestep
        )
        return time_available

    def __time_running(self, energy_output_provided: float, time_available: float) -> float:
        # Calculate running time of Boiler
        current_boiler_power = self.__calc_current_boiler_power(
            energy_output_provided=energy_output_provided, time_available=time_available
        )
        if current_boiler_power <= 0.0:
            time_running_current_service = 0.0
        else:
            time_running_current_service = min(
                energy_output_provided / current_boiler_power, time_available
            )
        return time_running_current_service

    def _demand_energy(
        self,
        service_name: str,
        service_type: HeatingServiceType,
        energy_output_required: float,
        temp_return_feed: float,
        hybrid_service: bool | None = False,
        time_start: float = 0.0,
        time_elapsed_hp: (float | None) = None,
        update_heat_source_state: (bool | None) = True,
    ) -> float | tuple[float, float]:
        """Calculate energy required by boiler to satisfy demand for the service indicated."""
        # Account for time control where present. If no control present, assume
        # system is always active (except for basic thermostatic control, which
        # is implicit in demand calculation).
        # if self.__control is None or self.__control.is_on():
        #     # Energy that heater is able to supply is limited by power rating
        #     energy_output_provided = min(energy_output_required, self.__boiler_power * self.__simulation_time.timestep())
        # else:
        #     energy_output_provided = 0.0

        time_available = self.__time_available(
            time_start=time_start, time_elapsed_hp=time_elapsed_hp
        )

        energy_output_provided = self.__calc_energy_output_provided(
            energy_output_required=energy_output_required, time_available=time_available
        )

        # TODO Ideally, the boiler power used for the running time calculation
        #      would account for space heating demand for all zones, but the
        #      calculation flow does not allow for this without circularity.
        #      Therefore, the value for time running returned from this function
        #      (used in the hybrid HP calculation) will be slightly inaccurate.
        time_running_current_service = self.__time_running(
            energy_output_provided=energy_output_provided, time_available=time_available
        )

        if update_heat_source_state:
            self.__total_time_running_current_timestep += time_running_current_service

            # Track pump running time (only for regular DHW and space heating)
            # Combi services don't use circulation pumps
            if service_type in (
                HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                HeatingServiceType.SPACE,
            ):
                self.__pump_running_time_current_timestep += time_running_current_service
            elif service_type == HeatingServiceType.DOMESTIC_HOT_WATER_COMBI:
                pass  # Direct DHW doesn't use circulation pump
            else:
                raise ValueError(f"Unexpected service type: {service_type}")  # pragma: no cover

            # Save results that are needed later (in the timestep_end function)
            self.__service_results.append(
                {
                    "service_name": service_name,
                    "service_type": service_type,
                    "temp_return_feed": temp_return_feed,
                    "energy_output_required": energy_output_required,
                    "energy_output_provided": energy_output_provided,
                    "time_available": time_available,
                    "time_start": time_start,
                    "time_elapsed_hp": time_elapsed_hp,
                }
            )

        if hybrid_service:
            return energy_output_provided, time_running_current_service
        else:
            return energy_output_provided

    def __sum_space_heating_service_results(self, varname: str) -> float:
        return math.fsum(
            x[varname]
            for x in self.__service_results
            if x["service_type"] == HeatingServiceType.SPACE
        )

    def __fuel_demand(self) -> None:
        """Calculate boiler fuel demand for all services (excl. auxiliary),
        and request this from relevant EnergySupplyConnection
        """
        for service_data in self.__service_results:
            service_name = service_data["service_name"]
            service_type = service_data["service_type"]
            temp_return_feed = service_data["temp_return_feed"]
            energy_output_provided = service_data["energy_output_provided"]

            # Aggregate space heating services
            # TODO This is only necessary because the model cannot handle an
            #      emitter circuit that serves more than one zone. If/when this
            #      capability is added, there will no longer be separate space
            #      heating services for each zone and this aggregation can be
            #      removed as it will not be necessary. At that point, the other
            #      contents of this function could also be moved back to their
            #      original locations
            if service_type == HeatingServiceType.SPACE:
                combined_energy_output_required = self.__sum_space_heating_service_results(
                    varname="energy_output_required"
                )
                # Get max time available from all space heating services to use
                # as overall time available for all space heating services. Note
                # that for this assumption to be valid, the space heating
                # services must be called consecutively, with no services of
                # another type called in between.
                time_available = max(
                    x["time_available"]
                    for x in self.__service_results
                    if x["service_type"] == HeatingServiceType.SPACE
                )
            else:
                combined_energy_output_required = service_data["energy_output_required"]
                time_available = service_data["time_available"]

            if temp_return_feed is not None:
                blr_eff_final = self.__calc_boiler_eff(
                    service_type=service_type,
                    temp_return_feed=temp_return_feed,
                    energy_output_required=combined_energy_output_required,
                    time_available=time_available,
                )

                fuel_demand = energy_output_provided / blr_eff_final

            else:
                fuel_demand = 0.0
            self.__energy_supply_connections[service_name].demand_energy(
                amount_demanded=fuel_demand
            )

    def __calc_auxiliary_energy(
        self, timestep: float, time_remaining_current_timestep: float
    ) -> None:
        """Calculation of boiler electrical consumption"""

        # Energy used by circulation pump (for regular hot water and space heating services)
        energy_aux = self.__pump_running_time_current_timestep * self.__power_circ_pump

        # Energy used in standby mode
        energy_aux += self.__power_standby * time_remaining_current_timestep

        # Energy used by flue fan
        # Flue fan electricity for on-off boilers
        elec_energy_flue_fan = self.__total_time_running_current_timestep * self.__power_full_load

        # Overwrite flue fan electricity if boiler modulates
        # TODO does cycling below part load decrease elec consumption
        space_heat_services_processed = False
        for _service_no, service_data in enumerate(self.__service_results):
            # Aggregate space heating services
            # TODO This is only necessary because the model cannot handle an
            #      emitter circuit that serves more than one zone. If/when this
            #      capability is added, there will no longer be separate space
            #      heating services for each zone and this aggregation can be
            #      removed as it will not be necessary. At that point, the other
            #      contents of this function could also be moved back to their
            #      original locations
            if service_data["service_type"] == HeatingServiceType.SPACE:
                if space_heat_services_processed:
                    continue
                space_heat_services_processed = True

                combined_energy_output_provided = self.__sum_space_heating_service_results(
                    varname="energy_output_provided"
                )
                # Get max time available from all space heating services to use
                # as overall time available for all space heating services. Note
                # that for this assumption to be valid, the space heating
                # services must be called consecutively, with no services of
                # another type called in between.
                time_available = max(
                    x["time_available"]
                    for x in self.__service_results
                    if x["service_type"] == HeatingServiceType.SPACE
                )
            else:
                combined_energy_output_provided = service_data["energy_output_provided"]
                time_available = service_data["time_available"]

            current_boiler_power = self.__calc_current_boiler_power(
                energy_output_provided=combined_energy_output_provided,
                time_available=time_available,
            )
            modulation_ratio = min(current_boiler_power / self.__boiler_power, 1.0)
            if self.__min_modulation_load < 1:
                x_axis = [self.__min_modulation_load, 1.0]
                y_axis = [self.__power_part_load, self.__power_full_load]

                # Uses numpy interp
                flue_fan_el = interp(modulation_ratio, x_axis, y_axis)
                time_running = self.__time_running(
                    energy_output_provided=combined_energy_output_provided,
                    time_available=time_available,
                )
                elec_energy_flue_fan = time_running * flue_fan_el
                energy_aux += elec_energy_flue_fan

        self.__energy_supply_connection_aux.demand_energy(amount_demanded=energy_aux)

    def timestep_end(self) -> None:
        """ " Calculations to be done at the end of each timestep"""
        self.__fuel_demand()

        timestep = self.__simulation_time.timestep()
        time_remaining_current_timestep = timestep - self.__total_time_running_current_timestep

        self.__calc_auxiliary_energy(
            timestep=timestep, time_remaining_current_timestep=time_remaining_current_timestep
        )

        # Variabales below need to be reset at the end of each timestep
        self.__total_time_running_current_timestep = 0.0
        self.__pump_running_time_current_timestep = 0.0
        self.__service_results = []

    def _energy_output_max(
        self, time_start: float = 0.0, time_elapsed_hp: (float | None) = None
    ) -> float:
        time_available = self.__time_available(time_start, time_elapsed_hp)
        return self.__boiler_power * time_available

    def effvsreturntemp(self, return_temp: float, offset: float) -> float:
        """Return boiler efficiency at different return temperatures"""
        mains_gas_dewpoint = 52.2
        lpg_dewpoint = 48.3
        # TODO: add remaining fuels
        if self.__fuel_code == FuelType.MAINS_GAS:
            if return_temp < mains_gas_dewpoint:
                theoretical_eff = -0.0000686 * (return_temp) ** 2 + 0.00175 * return_temp + 0.97845
            else:
                theoretical_eff = -0.000619 * return_temp + 0.91250229
        elif self.__fuel_code in (
            FuelType.LPG_BULK,
            FuelType.LPG_BOTTLED,
            FuelType.LPG_CONDITION_11_F,
        ):
            if return_temp < lpg_dewpoint:
                theoretical_eff = -0.00006118 * (return_temp) ** 2 + 0.00126 * return_temp + 0.98586
            else:
                theoretical_eff = -0.00062 * return_temp + 0.9332
        else:
            raise ValueError("Fuel code does not exist")
        blr_theoretical_eff = theoretical_eff - offset

        return blr_theoretical_eff

    def high_value_correction_part_load(self, net_efficiency_part_load: float) -> float:
        """Return a Boiler efficiency corrected for high values"""
        if self.__fuel_code == FuelType.MAINS_GAS:
            maximum_part_load_eff = 1.08
        elif self.__fuel_code in (
            FuelType.LPG_BULK,
            FuelType.LPG_BOTTLED,
            FuelType.LPG_CONDITION_11_F,
        ):
            maximum_part_load_eff = 1.06
        else:
            raise ValueError("Unknown fuel code " + str(self.__fuel_code))
        corrected_net_efficiency_part_load = min(
            net_efficiency_part_load - 0.213 * (net_efficiency_part_load - 0.966),
            maximum_part_load_eff,
        )
        return corrected_net_efficiency_part_load

    def high_value_correction_full_load(self, net_efficiency_full_load: float) -> float:
        corrected_net_efficiency_full_load = min(
            net_efficiency_full_load - 0.673 * (net_efficiency_full_load - 0.955), 0.98
        )
        return corrected_net_efficiency_full_load

    def net_to_gross(self) -> float:
        """Returns net to gross factor"""
        if self.__fuel_code == FuelType.MAINS_GAS:
            net_to_gross = 0.901
        elif self.__fuel_code in (
            FuelType.LPG_BULK,
            FuelType.LPG_BOTTLED,
            FuelType.LPG_CONDITION_11_F,
        ):
            net_to_gross = 0.921
        else:
            raise ValueError("Unknown fuel code " + str(self.__fuel_code))
        return net_to_gross
