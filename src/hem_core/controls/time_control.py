#!/usr/bin/env python3

"""
This module provides objects to model time controls.
"""

import math
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Mapping
from heapq import nsmallest
from math import ceil, floor, fsum
from typing import Any, Generic, Sequence, TypeVar

# Local imports
from hem_core import units
from hem_core.external_conditions import ExternalConditions
from hem_core.input_output.enums import (
    ControlCombinationOperation,
    ControlLogicType,
)
from hem_core.schedule import validate_schedule_length
from hem_core.simulation_time import SimulationTime

type TimeControl = (
    OnOffTimeControl | SetpointTimeControl | OnOffCostMinimisingTimeControl | CombinationTimeControl
)


class ControlSimple(ABC):
    @abstractmethod
    def is_on(self) -> bool: ...


class ControlCharge(ABC):
    @abstractmethod
    def target_charge(self, temp_air: float | None = None) -> float: ...


class ControlSetPoint(ControlSimple, ABC):
    @abstractmethod
    def setpnt(self) -> float | None: ...

    @abstractmethod
    def in_required_period(self) -> bool: ...


T_ControlSchedule = TypeVar("T_ControlSchedule", bool, float, float | None)


class BaseTimeControl(Generic[T_ControlSchedule], ControlSimple, ABC):
    def __init__(
        self,
        schedule: Sequence[T_ControlSchedule],
        simulation_time: SimulationTime,
        start_day: int,
        time_series_step: float,
    ):
        validate_schedule_length(
            schedule=list(schedule),
            expected_length=simulation_time.total_steps_based_on_step(
                start_day=start_day, step=time_series_step
            ),
        )
        self._schedule = schedule
        self._simulation_time = simulation_time
        self._start_day = start_day
        self._time_series_step = time_series_step


class BoolTimeControl(BaseTimeControl[bool], ABC):
    def is_on(self) -> bool:
        """Return true if control will allow system to run"""
        return self._schedule[
            self._simulation_time.time_series_idx(
                start_day=self._start_day, time_series_step=self._time_series_step
            )
        ]


class FloatTimeControl(BaseTimeControl[float], ABC):
    pass


class FloatOrNoneTimeControl(BaseTimeControl[float | None], ABC):
    pass


class OnOffTimeControl(BoolTimeControl):
    """An object to model a time-only control with on/off (not modulating) operation"""

    def __init__(
        self,
        schedule: Sequence[bool],
        simulation_time: SimulationTime,
        start_day: int,
        time_series_step: float,
    ):
        """Construct an OnOffTimeControl object

        Arguments:
        schedule         -- list of boolean values where true means "on" (one entry per hour)
        simulation_time  -- reference to SimulationTime object
        start_day        -- first day of the time series, day of the year, 0 to 365 (single value)
        time_series_step -- timestep of the time series data, in hours
        """
        super().__init__(
            schedule=schedule,
            simulation_time=simulation_time,
            start_day=start_day,
            time_series_step=time_series_step,
        )


class ChargeControl(BoolTimeControl, ControlCharge):
    """An object to model a control that governs electrical charging of a heat storage device
    that can respond to signals from the grid, for example when carbon intensity is low"""

    def __init__(
        self,
        logic_type: ControlLogicType,
        schedule: Sequence[bool],
        simulation_time: SimulationTime,
        start_day: int,
        time_series_step: float,
        charge_level: list[float],
        temp_charge_cut: float | None = None,
        temp_charge_cut_delta: list[float] | None = None,
        extcond: ExternalConditions | None = None,
        external_sensor: dict[str, Any] | None = None,
        charge_calc_time: float = 21,
    ):
        """Construct a ChargeControl object

        Arguments:
        logic_type       -- ControlLogicType enum
        schedule         -- list of boolean values where true means "on" (one entry per hour)
        simulation_time  -- reference to SimulationTime object
        start_day        -- first day of the time series, day of the year, 0 to 365 (single value)
        time_series_step -- timestep of the time series data, in hours__get_heat_cool_systems_for_zone
        charge_level     -- Proportion of the charge targeted for each day
        temp_charge_cut  -- Room temperature at which, if sensed during a charging hour, the control stops charging
                            (Required for AUTOMATIC, CELECT, and HHRSH logic types only)
        temp_charge_cut_delta -- array with values for a temperature adjustment which is applied
                                 to the nominal internal air temperature above which the control stops
                                 charging the device with heat.
                                 (Optional for AUTOMATIC, CELECT, and HHRSH logic types)
        extcond               -- reference to ExternalConditions object (for HHRSH and HEAT_BATTERY logic)
        external_sensor       -- external weather sensor that acts as a limiting device to prevent storage
                                 heaters from overcharging (for AUTOMATIC and CELECT logic)
        charge_calc_time -- Indicates from which hour of the day the system starts to target the charge level
                            for the next day rather than the current day
        """
        super().__init__(
            schedule=schedule,
            simulation_time=simulation_time,
            start_day=start_day,
            time_series_step=time_series_step,
        )
        if temp_charge_cut_delta is not None:
            validate_schedule_length(
                schedule=temp_charge_cut_delta,
                expected_length=simulation_time.total_steps_based_on_step(
                    start_day=start_day, step=time_series_step
                ),
            )
        self.__logic_type = logic_type
        self.__charge_level = charge_level
        self.__temp_charge_cut = temp_charge_cut
        self.__temp_charge_cut_delta = temp_charge_cut_delta
        self.__charge_calc_time = charge_calc_time

        self.__external_conditions = extcond
        self.__external_sensor = external_sensor

        # Check definition is complete for chosen control logic
        if self.__logic_type == ControlLogicType.MANUAL:
            # Manual control doesn't require any additional parameters
            pass
        elif self.__logic_type == ControlLogicType.AUTOMATIC:
            if self.__temp_charge_cut is None:
                raise ValueError("automatic ChargeControl definition is missing input parameters.")

        elif self.__logic_type == ControlLogicType.CELECT:
            if self.__temp_charge_cut is None:
                raise ValueError("celect ChargeControl definition is missing input parameters.")

        elif self.__logic_type == ControlLogicType.HHRSH:
            # HHRSH requires temp_charge_cut
            if self.__temp_charge_cut is None:
                raise ValueError(
                    "hhrsh ChargeControl definition is missing temp_charge_cut parameter."
                )
            if self.__external_conditions is None:
                raise ValueError("hhrsh ChargeControl definition is missing external conditions.")
            # Initialize HHRSH-specific attributes
            self.__steps_day = int(units.hours_per_day / self._simulation_time.timestep())
            self.__demand: deque[float] = deque(maxlen=self.__steps_day)
            self.__past_ext_temp: deque[float | None] = deque(
                [None] * self.__steps_day, maxlen=self.__steps_day
            )
            self.__future_ext_temp: deque[float | None] = deque(
                [0.0] * self.__steps_day, maxlen=self.__steps_day
            )
            for i in range(self.__steps_day):
                self.__future_ext_temp.append(self.__external_conditions.air_temp(idx_offset=i))
            self.__energy_to_store = 0.0

            # TODO: Consider adding solar data for HHRSH logic in addition to heating degree hours.
        elif self.__logic_type == ControlLogicType.HEAT_BATTERY:
            # Heat battery doesn't require temp_charge_cut but needs other parameters
            if self.__external_conditions is None:
                raise ValueError(
                    "heat_battery ChargeControl definition is missing external conditions."
                )
            # Initialize heat battery-specific attributes
            self.__steps_day = int(units.hours_per_day / self._simulation_time.timestep())
            self.__demand: deque[float] = deque(maxlen=self.__steps_day)
            self.__past_ext_temp: deque[float | None] = deque(
                [None] * self.__steps_day, maxlen=self.__steps_day
            )
            self.__future_ext_temp: deque[float | None] = deque(
                [0.0] * self.__steps_day, maxlen=self.__steps_day
            )
            for i in range(self.__steps_day):
                self.__future_ext_temp.append(self.__external_conditions.air_temp(idx_offset=i))
            self.__energy_to_store = 0.0

        else:
            raise ValueError("Invalid logic type for charge control.")  # PRAGMA: nocover

    def logic_type(self) -> ControlLogicType:
        """Return the logic type for this control"""
        return self.__logic_type

    def target_charge(self, temp_air: float | None = None) -> float:
        """Return the charge level value from the list given in inputs; one value per day"""

        # Calculate target charge nominal when unit is on
        if self.is_on():
            target_charge_nominal = self.__charge_level[
                self._simulation_time.time_series_idx_days(
                    start_day=self._start_day, charge_calc_time=self.__charge_calc_time
                )
            ]
        else:
            # If unit is off send 0.0 for target charge
            target_charge_nominal = 0.0

        target_charge = target_charge_nominal
        if self.__logic_type == ControlLogicType.MANUAL:
            target_charge = target_charge_nominal
        else:
            """ automatic, celect and hhrsh control include temperature charge cut logic """
            temp_charge_cut = self.temp_charge_cut_corr()

            if (
                temp_charge_cut is not None
                and temp_air is not None
                and (
                    temp_air > temp_charge_cut
                    or math.isclose(temp_air, temp_charge_cut, abs_tol=1e-10)
                )
            ):
                # Control logic cut when temp_air is over temp_charge cut
                target_charge_nominal = 0.0

        if self.__logic_type == ControlLogicType.AUTOMATIC:
            # Automatic charge control can be achieved using internal thermostat(s) to
            # control the extent of charging of the heaters. All or nothing approach

            # Controls can also be supplemented by an external weather sensor,
            # which tends to act as a limiting device to prevent the storage heaters from overcharging.
            if self.__external_sensor is not None and self.__external_conditions is not None:
                limit = self.__get_limit_factor(self.__external_conditions.air_temp())
                target_charge = target_charge_nominal * limit
            else:
                target_charge = target_charge_nominal

        elif self.__logic_type == ControlLogicType.CELECT:
            # A CELECT-type controller has electronic sensors throughout the dwelling linked
            # to a central control device. It monitors the individual room sensors and optimises
            # the charging of all the storage heaters individually (and may select direct acting
            # heaters in preference to storage heaters).

            # Initial CELECT-type logic based on AUTOMATIC until additional literature for
            # CELECT types is identified

            # Controls can also be supplemented by an external weather sensor,
            # which tends to act as a limiting device to prevent the storage heaters from overcharging.
            if self.__external_sensor is not None and self.__external_conditions is not None:
                limit = self.__get_limit_factor(self.__external_conditions.air_temp())
                target_charge = target_charge_nominal * limit
            else:
                target_charge = target_charge_nominal

        elif self.__logic_type in (ControlLogicType.HHRSH, ControlLogicType.HEAT_BATTERY):
            # A ‘high heat retention storage heater’ is one with heat retention not less
            # than 45% measured according to BS EN 60531. It incorporates a timer, electronic
            # room thermostat and fan to control the heat output. It is also able to estimate
            # the next day’s heating demand based on external temperature, room temperature
            # settings and heat demand periods.

            target_charge = 1 if target_charge_nominal else 0

        return target_charge

    def energy_to_store(self, energy_demand: float, base_temp: float) -> float | None:
        """
        Returns energy estimated to be stored for HHRSH in each timestep
        """
        self.__demand.append(energy_demand)
        if self.__external_conditions:
            self.__future_ext_temp.append(
                self.__external_conditions.air_temp(idx_offset=self.__steps_day)
            )
            self.__past_ext_temp.append(self.__external_conditions.air_temp())

        future_hdh = self.__calculate_heating_degree_hours(
            temps=self.__future_ext_temp, base_temp=base_temp
        )
        past_hdh = self.__calculate_heating_degree_hours(
            temps=self.__past_ext_temp, base_temp=base_temp
        )

        if future_hdh is None or past_hdh is None:
            self.__energy_to_store = None
        elif past_hdh == 0:
            self.__energy_to_store = (
                0  # Can't calculate tomorrow's demand if no past_hdh, so assume zero to store
            )
        else:
            self.__energy_to_store = future_hdh / past_hdh * fsum(self.__demand)

        # No energy can be added when control is off
        if not self.is_on():
            self.__energy_to_store = 0.0

        return self.__energy_to_store

    def temp_charge_cut_corr(self):
        """
        Correct nominal/json temp_charge_cut with monthly table
        Arguments

        returns -- temp_charge_cut (corrected)
        """
        # Return None if temp_charge_cut is not set (e.g., for heat batteries)
        if self.__temp_charge_cut is None:
            return None

        if self.__temp_charge_cut_delta is not None:
            temp_charge_cut_delta = self.__temp_charge_cut_delta[
                self._simulation_time.time_series_idx(
                    start_day=self._start_day, time_series_step=self._time_series_step
                )
            ]
        else:
            temp_charge_cut_delta = 0.0

        temp_charge_cut = self.__temp_charge_cut + temp_charge_cut_delta

        return temp_charge_cut

    def __calculate_heating_degree_hours(
        self, temps: deque[float | None], base_temp: float
    ) -> float | None:
        total_hdh = 0
        for temp in temps:
            if temp is None:
                return None

            hdh = max(base_temp - temp, 0)
            total_hdh += hdh
        return total_hdh

    def __get_limit_factor(self, external_temp: float) -> float:
        if not self.__external_sensor:
            raise ValueError(
                "External sensor data is required for limit factor calculation."
            )  # pragma: no cover

        correlation = self.__external_sensor["correlation"]

        # Edge cases: If temperature is below the first point or above the last point
        if external_temp < correlation[0]["temperature"] or math.isclose(
            external_temp, correlation[0]["temperature"], abs_tol=1e-10
        ):
            return correlation[0]["max_charge"]
        elif external_temp > correlation[-1]["temperature"] or math.isclose(
            external_temp, correlation[-1]["temperature"], abs_tol=1e-10
        ):
            return correlation[-1]["max_charge"]

        # Linear interpolation
        for i in range(1, len(correlation)):
            temp_1 = correlation[i - 1]["temperature"]
            max_charge_1 = correlation[i - 1]["max_charge"]
            temp_2 = correlation[i]["temperature"]
            max_charge_2 = correlation[i]["max_charge"]

            if (
                not math.isclose(temp_1, temp_2)
                and (temp_1 < external_temp or math.isclose(temp_1, external_temp, abs_tol=1e-10))
                and (external_temp < temp_2 or math.isclose(temp_2, external_temp, abs_tol=1e-10))
            ):
                # Perform linear interpolation
                slope = (max_charge_2 - max_charge_1) / (temp_2 - temp_1)
                limit = max_charge_1 + slope * (external_temp - temp_1)
                return limit

        raise RuntimeError(
            "Calculation of limiting factor linked to external sensor for automatic control failed."
        )


class OnOffCostMinimisingTimeControl(BoolTimeControl):
    def __init__(
        self,
        schedule: Sequence[float],
        simulation_time: SimulationTime,
        start_day: int,
        time_series_step: float,
        time_on_daily: float,
    ):
        """Construct an OnOffCostMinimisingControl object

        Arguments:
        schedule         -- list of cost values (one entry per time_series_step)
        simulation_time  -- reference to SimulationTime object
        start_day        -- first day of the time series, day of the year, 0 to 365 (single value)
        time_series_step -- timestep of the time series data, in hours
        time_on_daily    -- number of "on" hours to be set per day
        """
        self.__time_on_daily = time_on_daily

        validate_schedule_length(
            schedule,
            simulation_time.total_steps_based_on_step(start_day=start_day, step=time_series_step),
        )

        timesteps_per_day = int(units.hours_per_day / time_series_step)
        timesteps_on_daily = int(time_on_daily / time_series_step)
        time_series_len_days = ceil(len(schedule) * time_series_step / units.hours_per_day)

        # For each day of schedule, find the specified number of hours with the lowest cost
        on_off_schedule: list[bool] = []
        for day in range(0, time_series_len_days):
            # Get part of the schedule for current day
            schedule_day_start = day * timesteps_per_day
            schedule_day_end = schedule_day_start + timesteps_per_day
            schedule_day = schedule[schedule_day_start:schedule_day_end]

            # Find required number of timesteps with lowest costs
            schedule_day_cost_lowest = sorted(set(nsmallest(timesteps_on_daily, schedule_day)))

            # Initialise boolean schedule for day
            schedule_onoff_day = [False] * timesteps_per_day

            # Set lowest cost times to True, then next lowest etc. until required
            # number of timesteps have been set to True
            timesteps_to_be_allocated = timesteps_on_daily
            for cost in schedule_day_cost_lowest:
                for idx, entry in enumerate(schedule_day):
                    if timesteps_to_be_allocated < 1:
                        break
                    if entry == cost:
                        schedule_onoff_day[idx] = True
                        timesteps_to_be_allocated -= 1

            # Add day of schedule to overall
            on_off_schedule.extend(schedule_onoff_day)

        super().__init__(
            schedule=on_off_schedule,
            simulation_time=simulation_time,
            start_day=start_day,
            time_series_step=time_series_step,
        )


class SetpointTimeControl(FloatOrNoneTimeControl, ControlSetPoint):
    """An object to model a control with a setpoint which varies per timestep"""

    def __init__(
        self,
        schedule: Sequence[float | None],
        simulation_time: SimulationTime,
        start_day: int,
        time_series_step: float,
        setpoint_min: float | None = None,
        setpoint_max: float | None = None,
        default_to_max: bool | None = None,
        duration_advanced_start: float = 0.0,
    ):
        """Construct a SetpointTimeControl object

        Arguments:
        schedule         -- list of float values (one entry per hour)
        simulation_time  -- reference to SimulationTime object
        start_day        -- first day of the time series, day of the year, 0 to 365 (single value)
        time_series_step -- timestep of the time series data, in hours
        setpoint_min -- min setpoint allowed
        setpoint_max -- max setpoint allowed
        default_to_max -- if both min and max limits are set but setpoint isn't,
                          whether to default to min (False) or max (True)
        duration_advanced_start -- how long before heating period the system
                                   should switch on, in hours
        """
        super().__init__(
            schedule=schedule,
            simulation_time=simulation_time,
            start_day=start_day,
            time_series_step=time_series_step,
        )
        self.__setpoint_min = setpoint_min
        self.__setpoint_max = setpoint_max
        self.__default_to_max = default_to_max
        self.__timesteps_advstart = round(
            duration_advanced_start / self._simulation_time.timestep()
        )

    def in_required_period(self) -> bool:
        """Return true if current time is inside specified time for heating/cooling

        (not including timesteps where system is only on due to min or max
        setpoint or advanced start)
        """
        schedule_idx = self._simulation_time.time_series_idx(
            start_day=self._start_day,
            time_series_step=self._time_series_step,
        )
        setpnt = self._schedule[schedule_idx]
        return setpnt is not None

    def is_on(self) -> bool:
        """Return true if control will allow system to run"""
        schedule_idx = self._simulation_time.time_series_idx(
            start_day=self._start_day,
            time_series_step=self._time_series_step,
        )
        setpnt = self._schedule[schedule_idx]

        if setpnt is None:
            # Look ahead for duration of warmup period: system is on if setpoint
            # is not None heating period if found
            for timesteps_ahead in range(1, 1 + self.__timesteps_advstart):
                if len(self._schedule) <= schedule_idx + timesteps_ahead:
                    # Stop looking ahead if we have reached the end of the schedule
                    break
                if self._schedule[schedule_idx + timesteps_ahead] is not None:
                    # If heating period starts within duration of warmup period
                    # from now, system is on
                    return True

        # For this type of control, system is always on if min or max are set
        if setpnt is None and self.__setpoint_min is None and self.__setpoint_max is None:
            return False
        else:
            return True

    def setpnt(self) -> float | None:
        """Return setpoint for the current timestep"""
        schedule_idx = self._simulation_time.time_series_idx(
            self._start_day,
            self._time_series_step,
        )
        setpnt = self._schedule[schedule_idx]

        if setpnt is None:
            # Look ahead for duration of warmup period and use setpoint from
            # start of heating period if found
            for timesteps_ahead in range(1, 1 + self.__timesteps_advstart):
                if len(self._schedule) <= schedule_idx + timesteps_ahead:
                    # Stop looking ahead if we have reached the end of the schedule
                    break
                if self._schedule[schedule_idx + timesteps_ahead] is not None:
                    # If heating period starts within duration of warmup period
                    # from now, use setpoint from start of heating period
                    setpnt = self._schedule[schedule_idx + timesteps_ahead]
                    break

        if setpnt is None:
            # If no setpoint value is in the schedule, use the min/max if set
            if self.__setpoint_max is None and self.__setpoint_min is None:
                pass  # Use setpnt None
            elif self.__setpoint_max is not None and self.__setpoint_min is None:
                setpnt = self.__setpoint_max
            elif self.__setpoint_min is not None and self.__setpoint_max is None:
                setpnt = self.__setpoint_min
            else:  # min and max both set
                if self.__default_to_max is None:
                    raise ValueError(
                        "ERROR: Setpoint not set but min and max both set, "
                        "and which to use by default not specified"
                    )
                elif self.__default_to_max:
                    setpnt = self.__setpoint_max
                else:
                    setpnt = self.__setpoint_min
        else:
            # If there is a maximum limit, take the lower of this and the schedule value
            if self.__setpoint_max is not None:
                setpnt = min(self.__setpoint_max, setpnt)
            # If there is a minimum limit, take the higher of this and the schedule value
            if self.__setpoint_min is not None:
                setpnt = max(self.__setpoint_min, setpnt)
        return setpnt


class SmartApplianceControl:
    """An object for managing loadshifting appliances"""

    def __init__(
        self,
        power_timeseries: dict[str, list[float]],
        timeseries_step: float,
        simulation_time: SimulationTime,
        non_appliance_demand_24hr: dict[str, list[float]],
        battery_24hr: dict[str, dict[str, list[float]]],
        energysupplies: dict[str, Any],
        appliances: list[str],
    ):
        """Construct a SmartApplianceControl object

        Arguments:
        power_timeseries          - dictionary of lists containing expected power for appliances
                                    for each energy supply, for the entire length of the simulation
        timeseries_step           - timestep of the power timeseries
                                    (not necessarily equal to simulation_time.timestep())
        simulation_time           - reference to a SimulationTime object
        non_appliance_demand_24hr - dictionary of lists containing 24 hour buffers of
                                    demand per end user for each energy supply
        battery_24hr              - dictionary of lists containing 24 hour buffers of
                                    battery state of charge for each energy supply
        energysupplies            - dictionary of energysupply objects in the simulation
        appliances                - list of names of all appliance objects in the simulation
        """

        self.__appliances = appliances
        self.__energy_supplies = {
            key: data for (key, data) in energysupplies.items() if key in power_timeseries
        }
        self.__batteries = {}
        for name, supply in self.__energy_supplies.items():
            if supply.has_battery():
                # keep track of battery charge if an energysupply has a battery
                self.__batteries[name] = {
                    "battery_state_of_charge": battery_24hr["battery_state_of_charge"][name]
                }
        for energysupply in self.__energy_supplies.keys():
            if (
                len(power_timeseries[energysupply]) * timeseries_step
                < simulation_time.total_steps() * simulation_time.timestep()
            ):
                raise ValueError(
                    "ERROR: loadshifting power timeseries shorter than simulation length"
                )

        # timeseries objects
        self.__ts_power = power_timeseries
        self.__ts_step = timeseries_step
        self._simulation_time = simulation_time
        # timeseries may have time resolution different to that of the HEM calculation
        self.__ts_step_ratio = simulation_time.timestep() / timeseries_step

        # buffer objects
        self.__non_appliance_demand_24hr = non_appliance_demand_24hr
        self.__buffer_length = len(list(non_appliance_demand_24hr.values())[0])

    def ts_step(self, t_idx: int) -> int:
        # converts index of simulation time to index of demand or weight timeseries
        return floor(self.__ts_step_ratio * t_idx)

    def get_ts_demand(self, energysupply: str, t_idx: int) -> float:
        # returns average energy demand from powerts over the current simulation timestep
        return (
            self.__ts_power[energysupply][self.ts_step(t_idx)]
            / units.W_per_kW
            * self._simulation_time.timestep()
        )

    def get_demand(self, t_idx: int, energysupply: str) -> float:
        # returns the sum of the anticipated appliance demand,
        # the demand buffer, and the (negative) battery charge

        idx_24hr = t_idx % self.__buffer_length
        demand = (
            self.get_ts_demand(energysupply=energysupply, t_idx=t_idx)
            + self.__non_appliance_demand_24hr[energysupply][idx_24hr]
        )

        if energysupply in self.__batteries:
            return demand - self.__batteries[energysupply]["battery_state_of_charge"][idx_24hr]
        return demand

    def add_appliance_demand(self, t_idx: int, demand: float, energysupply: str) -> None:
        # convert demand from appliance usage event to average power over the demand series timestep
        # and add it to the series
        self.__ts_power[energysupply][self.ts_step(t_idx)] += (
            demand * units.W_per_kW / self.__ts_step
        )

        # update our prediction of battery charge over the next 24 hours
        if energysupply in self.__batteries:
            # if we expect there will be charge in the battery when this demand occurs, assume
            # the battery supplies as much of it as possible
            idx_24hr = t_idx % self.__buffer_length
            max_capacity = self.__energy_supplies[energysupply].get_battery_max_capacity()
            # max_discharge is a linear function however states it requires input as a 0-1 proportion of total,
            # so divide and then multiply by max capacity in case of future changes
            maxdischarge = (
                -self.__energy_supplies[energysupply].get_battery_max_discharge(
                    charge=self.__batteries[energysupply]["battery_state_of_charge"][idx_24hr]
                    / max_capacity
                )
                * max_capacity
            )
            # the maths here follows charge_discharge_battery() in ElectricBattery
            dischargeeff = self.__energy_supplies[energysupply].get_battery_discharge_efficiency()
            charge_utilised = min(
                max(self.__batteries[energysupply]["battery_state_of_charge"][idx_24hr], 0),
                min(maxdischarge, demand) * dischargeeff,
            )
            # now subtract charge_utilised from the charge stored at every step in the buffer of battery charge.
            # if the battery is already expected to empty at a later time, this will result in the buffer
            # reporting negative charge stored in the battery during the times it is expected to be empty
            # and appliance preferentially not being used at those times
            self.__batteries[energysupply]["battery_state_of_charge"] = [
                charge - charge_utilised
                for charge in self.__batteries[energysupply]["battery_state_of_charge"]
            ]

    def update_demand_buffer(self, t_idx: int) -> None:
        idx_24hr = t_idx % self.__buffer_length
        for name, supply in self.__energy_supplies.items():
            # total up results for this energy supply but exclude demand from appliances
            # (the demand for which we already know accurately in advance
            # energy generated is negative and if the generation exceeds demand for a given timestep, the total
            # will be negative, and appliance usage events will preferentially be scheduled at that time
            # TODO - it is possible to apply a weighting factor to energy generated in the dwelling here
            # (users for whom demand is negative)
            # to make it more or less preferable to use it immediately or export/charge battery
            self.__non_appliance_demand_24hr[name][idx_24hr] = fsum(
                user
                for (name, user) in supply.results_by_end_user_single_step(t_idx).items()
                if name not in self.__appliances
            )

            if supply.has_battery():
                # TODO - communicate with charge control
                charge = supply.get_battery_available_charge()
                chargeeff = supply.get_battery_charge_efficiency()
                self.__batteries[name]["battery_state_of_charge"][idx_24hr] = charge * chargeeff


class CombinationTimeControl(ControlCharge, ControlSetPoint):
    """An object to model a control with nested combinations of other control types"""

    def __init__(
        self,
        combination: Mapping[str, dict[str, str | list[str]]],
        controls: Mapping[str, TimeControl],
        simulation_time: SimulationTime,
    ):
        """Construct a CombinationTimeControl object

        Arguments:
        combination      -- mapping of combination names to combination configurations (read-only)
        controls         -- mapping of control names to control instances (read-only)
        simulation_time  -- reference to SimulationTime object
        """
        self.__combination = combination
        self.__controls = controls
        self._simulation_time = simulation_time

    def __evaluate_boolean_operation_is_on(
        self, operation: ControlCombinationOperation, control_results: list[bool]
    ) -> bool:
        """Evaluate a Boolean operation given the operation type and results"""
        if operation == ControlCombinationOperation.AND_:
            return all(control_results)
        if operation == ControlCombinationOperation.OR_:
            return any(control_results)
        elif operation == ControlCombinationOperation.XOR:
            return control_results.count(True) % 2 == 1
        elif operation == ControlCombinationOperation.NOT_:
            if len(control_results) != 1:
                raise ValueError("NOT operation requires exactly one operand.")
            return not control_results[0]
        else:
            raise ValueError(f"Unsupported Boolean operation: {operation}")

    def __evaluate_control_is_on(self, control_name: str) -> bool:
        """Evaluate a single control"""
        control = self.__controls[control_name]
        return control.is_on()

    def __evaluate_combination_is_on(self, combination_name: str) -> bool:
        """Evaluate a combination of controls"""
        combination = self.__combination[combination_name]
        operation = ControlCombinationOperation(combination["operation"])
        controls = combination["controls"]

        results: list[bool] = []
        for control in controls:
            if control in self.__combination:
                # If the control is a combination, recursively evaluate it
                # Infinite recursion has been avoided by adding checks during control onbject creation
                result = self.__evaluate_combination_is_on(combination_name=control)
            else:
                # Otherwise, evaluate a single control
                result = self.__evaluate_control_is_on(control_name=control)
            results.append(result)

        if operation in {
            ControlCombinationOperation.AND_,
            ControlCombinationOperation.OR_,
            ControlCombinationOperation.XOR,
            ControlCombinationOperation.NOT_,
        }:
            return self.__evaluate_boolean_operation_is_on(
                operation=operation, control_results=results
            )

        # If the operation is MAX,MIN or MEAN then OR is performed
        elif operation in {
            ControlCombinationOperation.MAX,
            ControlCombinationOperation.MIN,
            ControlCombinationOperation.MEAN,
        }:
            return any(results)

        else:
            raise ValueError(
                f"Unsupported operation in combination: {operation}"
            )  # PRAGMA: nocover

    def __evaluate_control_in_req_period(self, control_name: str) -> bool:
        """Evaluate a single control"""

        control = self.__controls[control_name]
        if (
            isinstance(control, OnOffTimeControl)
            or isinstance(control, OnOffCostMinimisingTimeControl)
            or isinstance(control, ChargeControl)
        ):
            return control.is_on()
        elif isinstance(control, SetpointTimeControl):
            return control.in_required_period()
        else:
            raise ValueError(f"Unsupported control type for {control_name}")

    def __evaluate_combination_in_req_period(self, combination_name: str) -> bool:
        """
        This function processes a combination of control elements applying boolean logic (AND, OR, XOR, etc.) to their evaluation results.
        It checks the type of controls , validates allowed combinations and returns the evaluation result based on the specified operation.
        Unsupported combinations or operations raise an error.
        """
        combination = self.__combination[combination_name]
        operation = ControlCombinationOperation(combination["operation"])
        controls = combination["controls"]

        results: list[bool] = []
        has_onoff = False
        has_setpoint = False

        for control in controls:
            if control in self.__combination:
                result = self.__evaluate_combination_in_req_period(combination_name=control)
            else:
                # Track the types of controls for logic enforcement
                control_instance = self.__controls[control]
                if (
                    isinstance(control_instance, OnOffTimeControl)
                    or isinstance(control_instance, OnOffCostMinimisingTimeControl)
                    or isinstance(control_instance, ChargeControl)
                ):
                    has_onoff = True
                if isinstance(control_instance, SetpointTimeControl):
                    has_setpoint = True
                result = self.__evaluate_control_in_req_period(control_name=control)

            results.append(result)
        # Ensure valid combinations
        if has_onoff:
            if has_setpoint:
                if operation != ControlCombinationOperation.AND_:
                    raise ValueError(
                        "OnOff + Setpoint combination in_req_period() only supports the AND operation"
                    )
                # Combine results using AND for OnOff + Setpoint combination
                return all(results)
            else:
                raise ValueError(
                    "OnOff + OnOff combination is not applicable for in_req_period() operation"
                )
        else:
            if not has_setpoint:
                raise ValueError("No OnOff or Setpoint in in_req_period()")
            # Apply operations for Setpoint + Setpoint combinations based on the operation
            if operation == ControlCombinationOperation.AND_:
                return all(results)
            elif operation == ControlCombinationOperation.OR_:
                return any(results)
            elif operation == ControlCombinationOperation.XOR:
                return sum(results) == 1  # XOR is true if exactly one result is True
            elif operation in {
                ControlCombinationOperation.MAX,
                ControlCombinationOperation.MIN,
                ControlCombinationOperation.MEAN,
            }:
                # MAX/MIN/MEAN are numeric operations for setpoints.
                # In boolean context (in_required_period), use OR logic:
                # "is any of the combined controls in its required period?"
                return any(results)
            else:
                raise ValueError(f"Unsupported operation: {operation}")  # PRAGMA: nocover

    def __evaluate_control_setpnt(self, control_name: str) -> float | None:
        """Evaluate a single control"""
        control = self.__controls[control_name]
        if (
            isinstance(control, OnOffTimeControl)
            or isinstance(control, OnOffCostMinimisingTimeControl)
            or isinstance(control, ChargeControl)
        ):
            return control.is_on()
        elif isinstance(control, SetpointTimeControl):
            return control.setpnt()
        else:
            raise ValueError(f"Unsupported control type for {control_name}")

    def __evaluate_combination_setpnt(self, combination_name: str) -> float | None:
        """Evaluate a combination of controls"""
        combination = self.__combination[combination_name]
        operation = ControlCombinationOperation(combination["operation"])
        controls = combination["controls"]

        results = []
        has_onoff = False
        has_setpoint = False

        for control in controls:
            if control in self.__combination:
                result = self.__evaluate_combination_setpnt(combination_name=control)
            else:
                # Track the types of controls for logic enforcement
                control_instance = self.__controls[control]
                if (
                    isinstance(control_instance, OnOffTimeControl)
                    or isinstance(control_instance, OnOffCostMinimisingTimeControl)
                    or isinstance(control_instance, ChargeControl)
                ):
                    has_onoff = True
                if isinstance(control_instance, SetpointTimeControl):
                    has_setpoint = True
                result = self.__evaluate_control_setpnt(control_name=control)
            results.append(result)
        # Check a setpnt result is available from previous combination
        if any(
            isinstance(result, (int, float)) and not isinstance(result, bool) for result in results
        ):
            has_setpoint = True

        # Ensure valid combinations
        if has_onoff:
            if has_setpoint:
                if operation == ControlCombinationOperation.AND_:
                    setpnt_value = [item for item in results if isinstance(item, float)]
                    bool_value = [item for item in results if isinstance(item, bool)]
                    if len(setpnt_value) > 1:
                        raise ValueError("Only one numerical value allowed in AND operation")
                    if all(bool_value):
                        return setpnt_value[0]
                    else:
                        return None
                else:
                    raise ValueError(
                        "OnOff + Setpoint combination setpnt() only supports the AND operation"
                    )
            else:
                raise ValueError(
                    "OnOff + OnOff combination is not applicable for in_req_period() operation"
                )
        else:
            if not has_setpoint:
                raise ValueError("No OnOff or Setpoint in in_req_period()")
            # Apply operations for Setpoint + Setpoint combinations based on the operation
            if operation == ControlCombinationOperation.MAX:
                return max(results)
            elif operation == ControlCombinationOperation.MIN:
                return min(results)
            elif operation == ControlCombinationOperation.MEAN:
                return fsum(results) / len(results) > 0.5  # Mean evaluates to True if average > 0.5
            else:
                raise ValueError(f"Unsupported operation: {operation}")

    def __evaluate_control_target_charge(
        self, control_name: str, temp_air: float | None
    ) -> float | None:
        control = self.__controls[control_name]
        if isinstance(control, ChargeControl):
            return control.target_charge(temp_air=temp_air)
        else:
            return None

    def __evaluate_combination_target_charge(
        self, combination_name: str, temp_air: float | None
    ) -> float:
        """Evaluate the combination for target charge"""
        combination = self.__combination[combination_name]
        controls = combination["controls"]
        results = []

        for control in controls:
            if control in self.__combination:
                # If the control is a combination, recursively evaluate it
                # Infinite recursion has been avoided by adding checks during control onbject creation
                result = self.__evaluate_combination_target_charge(
                    combination_name=control, temp_air=temp_air
                )
            else:
                result = self.__evaluate_control_target_charge(
                    control_name=control, temp_air=temp_air
                )
            results.append(result)

        # Check if the combination has a maximum one one ChargeControl object to return target_charge
        if all(item is None for item in results):
            raise ValueError(
                "Requires atleast one ChargeControl object in combination to determine target charge"
            )
        elif sum(item is not None for item in results) > 1:
            raise ValueError(
                "CombinationControl cannot have more than one ChargeControl object to determine target charge"
            )
        else:
            return [item for item in results if item is not None][0]

    def is_on(self) -> bool:
        """Evaluate if the overall control is active"""
        return self.__evaluate_combination_is_on(combination_name="main")

    def in_required_period(self) -> bool:
        """Evaluate if the overall control is active"""
        return self.__evaluate_combination_in_req_period(combination_name="main")

    def setpnt(self) -> float | None:
        """Return the setpoint for the current timestep"""
        return self.__evaluate_combination_setpnt(combination_name="main")

    def target_charge(self, temp_air: float | None = None) -> float:
        return self.__evaluate_combination_target_charge(combination_name="main", temp_air=temp_air)
