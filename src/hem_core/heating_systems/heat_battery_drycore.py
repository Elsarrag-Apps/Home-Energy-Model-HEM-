#!/usr/bin/env python3

"""
This module provides the base class for dry core heat storage systems.
This includes the common functionality for electrical storage and discharge
that is shared between Electric Storage Heaters and Dry Core Heat Batteries.
"""

import math
from abc import ABC, abstractmethod
from enum import Enum

import numpy as np
from scipy.integrate import solve_ivp
from scipy.interpolate import interp1d

import hem_core.units as units
import hem_core.water_heat_demand.misc as misc
from hem_core.controls.time_control import ChargeControl, SetpointTimeControl
from hem_core.energy_supply.energy_supply import EnergySupply, EnergySupplyConnection
from hem_core.heating_systems.enums import HeatingServiceType
from hem_core.input_output.enums import (
    ControlLogicType,
)
from hem_core.material_properties import WATER
from hem_core.simulation_time import SimulationTime
from hem_core.water_heat_demand.cold_water_source import ColdWaterSource
from hem_core.water_heat_demand.misc import WaterEventResult


class OutputMode(Enum):
    MIN = "min"
    MAX = "max"


class HeatStorageDryCore(ABC):
    """Base class for dry core heat storage systems"""

    def __init__(
        self,
        pwr_in: float,
        storage_capacity: float,
        n_units: int,
        simulation_time: SimulationTime,
        charge_control: ChargeControl,
        dry_core_min_output: list[list[float]],
        dry_core_max_output: list[list[float]],
        state_of_charge_init: float,
    ):
        """Construct a HeatStorageDryCore object

        Arguments:
        pwr_in               -- in kW (Charging)
        storage_capacity     -- in kWh
        n_units              -- number of units installed
        simulation_time      -- reference to SimulationTime object
        charge_control       -- reference to a ChargeControl object
        dry_core_min_output       -- Data from test showing the output from the storage heater when not actively
                                outputting heat, i.e. case losses only (with units kW)
        dry_core_max_output       -- Data from test showing the output from the storage heater when it is actively
                                outputting heat, e.g. damper open / fan running (with units kW)
        state_of_charge_init -- state of charge at initialisation of dry core heat storage
        """

        self.__pwr_in: float = pwr_in
        self.__storage_capacity: float = storage_capacity
        self.__n_units: int = n_units
        self.__simulation_time: SimulationTime = simulation_time
        self.__charge_control: ChargeControl = charge_control

        # Initialising other variables
        # Parameters
        self.__state_of_charge = state_of_charge_init
        # This represents the temperature difference between the core and the room on the first column
        # and the fraction of air flow relating to the nominal as defined above on the second column
        self.__dry_core_min_output = dry_core_min_output
        self.__dry_core_max_output = dry_core_max_output
        self.__energy_in: float = 0.0

        # Relevant for HHRSH
        self.__demand_met = 0.0
        self.__demand_unmet = 0.0
        self.__prev_timestep = -1

        # Convert dry_core_max_output to NumPy arrays without sorting
        self.__soc_max_array = np.array([pair[0] for pair in self.__dry_core_max_output])
        self.__power_max_array = np.array([pair[1] for pair in self.__dry_core_max_output])

        # Convert dry_core_min_output to NumPy arrays without sorting
        self.__soc_min_array = np.array([pair[0] for pair in self.__dry_core_min_output])
        self.__power_min_array = np.array([pair[1] for pair in self.__dry_core_min_output])

        # Validate that both SOC arrays are in strictly increasing order
        if not np.all(self.__soc_max_array[:-1] <= self.__soc_max_array[1:]):
            raise ValueError(
                "dry_core_max_output SOC values must be in increasing order (from 0.0 to 1.0)."
            )
        if not np.all(self.__soc_min_array[:-1] <= self.__soc_min_array[1:]):
            raise ValueError(
                "dry_core_min_output SOC values must be in increasing order (from 0.0 to 1.0)."
            )

        # Validate that both SOC arrays start at 0.0 and end at 1.0
        if not np.isclose(self.__soc_max_array[0], 0.0):
            raise ValueError(
                "The first SOC value in dry_core_max_output must be 0.0 (fully discharged)."
            )
        if not np.isclose(self.__soc_max_array[-1], 1.0):
            raise ValueError(
                "The last SOC value in dry_core_max_output must be 1.0 (fully charged)."
            )
        if not np.isclose(self.__soc_min_array[0], 0.0):
            raise ValueError(
                "The first SOC value in dry_core_min_output must be 0.0 (fully discharged)."
            )
        if not np.isclose(self.__soc_min_array[-1], 1.0):
            raise ValueError(
                "The last SOC value in dry_core_min_output must be 1.0 (fully charged)."
            )

        # Validate that for any SOC, power_max >= power_min
        # Sample a fine grid of SOCs and ensure power_max >= power_min
        fine_soc = np.linspace(0.0, 1.0, 100)
        power_max_fine = interp1d(
            self.__soc_max_array,
            self.__power_max_array,
            kind="linear",
            fill_value="extrapolate",
            bounds_error=False,
            assume_sorted=True,
        )(fine_soc)
        power_min_fine = interp1d(
            self.__soc_min_array,
            self.__power_min_array,
            kind="linear",
            fill_value=(0, 0),  # Ensures SOC outside bounds returns 0 power
            bounds_error=False,  # No errors for SOC values outside the bounds
            assume_sorted=True,  # Assume the SOC array is sorted
        )(fine_soc)

        if not np.all(power_max_fine >= power_min_fine):
            raise ValueError(
                "At all SOC levels, dry_core_max_output must be >= dry_core_min_output."
            )

        # Create interpolation functions for Power(SOC)
        self.__power_max_func = interp1d(
            self.__soc_max_array,
            self.__power_max_array,
            kind="linear",
            fill_value=(self.__power_max_array[0], self.__power_max_array[-1]),
            bounds_error=False,
            assume_sorted=True,
        )

        self.__power_min_func = interp1d(
            self.__soc_min_array,
            self.__power_min_array,
            kind="linear",
            fill_value=(self.__power_min_array[0], self.__power_min_array[-1]),
            bounds_error=False,
            assume_sorted=True,
        )

        self.__heat_retention_ratio = self.__heat_retention_output()

    def __convert_to_kwh(self, power: float, time: float) -> float:
        """
        Converts power value supplied to the correct energy unit
        Arguments
        power -- Power value in watts
        time -- length of the time active

        returns -- Energy in kWh
        """
        return power / units.W_per_kW * time

    def __heat_retention_output(self) -> float:
        """
        Simulates the heat retention over 16 hours in OutputMode.MIN.

        Starts with a SOC of 1.0 and calculates the SOC after 16 hours.
        This is a self-contained function, and the SOC is not stored in self.__state_of_charge.

        :return: Final SOC after 16 hours.
        """
        # Set initial state of charge to 1.0 (fully charged)
        initial_soc = 1.0

        # Total time for the simulation (16 hours)
        total_time = (
            16.0  # This is the value from BS EN 60531 for determining heat retention ability
        )

        # Select the SOC and power arrays for OutputMode.MIN
        soc_array = self.__soc_min_array
        power_values: np.ndarray = self.__power_min_func(self.__soc_min_array)

        # Set up interpolation function for Power vs SOC
        power_interp = interp1d(
            soc_array,
            power_values,  # Ensure power_func(soc_array) is correct
            kind="linear",
            fill_value="extrapolate",  # We still use extrapolate, but let's check the bounds
            bounds_error=False,
            assume_sorted=True,
        )

        # Define the ODE for SOC and energy delivered (no charging, only discharging)
        def soc_ode(t: float, y: np.ndarray) -> np.ndarray:
            soc = y  # y[0] is SOC, y[1] is total energy delivered

            # Ensure SOC stays within bounds
            soc = np.clip(soc, 0, 1)

            # Discharging: calculate power used based on SOC
            discharge_rate = -power_interp(soc)
            # Track the total energy delivered (discharged energy)
            ddelivered_dt = -discharge_rate  # Energy delivered (positive value)

            # SOC rate of change (discharging), divided by storage capacity
            dsoc_dt = -ddelivered_dt / self.__storage_capacity

            return dsoc_dt

        # Solve the ODE for SOC and cumulative energy delivered
        sol = solve_ivp(
            soc_ode, [0, total_time], [initial_soc], method="RK45", rtol=1e-1, atol=1e-3
        )

        # Final state of charge after 16 hours
        final_soc = sol.y[0][-1]

        # Clip the final SOC to ensure it's between 0 and 1
        final_soc = np.clip(final_soc, 0.0, 1.0)

        # Return the final state of charge after 16 hours
        return final_soc

    def __energy_output(
        self,
        mode: OutputMode,
        time_remaining: float | None = None,
        target_energy: float | None = None,
    ) -> tuple[float, float, float, float]:
        """
        Calculates the energy that can be delivered based on the mode ('min' or 'max'),
        and also returns the energy charged during the same timestep.

        :param mode: 'min' for minimum energy delivery, 'max' for maximum energy delivery.
        :param time_remaining: Maximum time available for the operation (hours)
        :param target_energy: Target energy to deliver (kWh). If specified, solver stops when this is reached.
        :return: Tuple containing (energy_delivered in kWh, time_used in hours, energy_charged in kWh, final_soc).
        """

        if mode == OutputMode.MIN:
            soc_array = self.__soc_min_array
            power_func = self.__power_min_func
        elif mode == OutputMode.MAX:
            soc_array = self.__soc_max_array
            power_func = self.__power_max_func
        else:
            raise ValueError("Invalid mode. Choose Mode.MIN or Mode.MAX.")

        power_values = power_func(soc_array)
        power_values = np.asarray(power_values, dtype=float)

        # Set up interpolation function for Power vs SOC
        power_interp = interp1d(
            soc_array,
            power_values,  # Ensure power_func(soc_array) is correct
            kind="linear",
            fill_value="extrapolate",
            bounds_error=False,
            assume_sorted=True,
        )

        # Charging: determine the maximum power available for charging
        target_charge = self.__target_electric_charge(time=self.__simulation_time.current_hour())
        if target_charge > 0:
            charge_rate = self.__pwr_in
            soc_max = target_charge
        else:
            charge_rate = 0
            soc_max = 1.0

        # Define the ODE for SOC, total energy charged, and total energy delivered
        def soc_ode(t: float, y: np.ndarray) -> np.ndarray:
            soc, energy_charged, energy_delivered = (
                y  # y[0] is SOC, y[1] is total energy charged, y[2] is total energy delivered
            )

            # Ensure SOC stays within bounds
            soc = np.clip(soc, 0, soc_max)

            if math.isclose(soc, 0.0, abs_tol=1e-10):
                soc = 0.0

            if math.isclose(soc, soc_max, abs_tol=1e-10):
                soc = soc_max

            # Discharging: calculate power used based on SOC
            discharge_rate = -power_interp(soc)
            # Track the total energy delivered (discharged energy)
            ddelivered_dt = (
                -discharge_rate.item()
            )  # Energy delivered (positive value) is tracked separately

            # Track the total energy charged
            if soc < soc_max:
                dcharged_dt = charge_rate
            else:
                if target_charge > 0 and not math.isclose(target_charge, 0.0, abs_tol=1e-10):
                    dcharged_dt = min(ddelivered_dt, charge_rate)
                else:
                    dcharged_dt = 0.0  # pragma: no cover

            # Net SOC rate of change (discharge + charge), divided by storage capacity
            dsoc_dt = (-ddelivered_dt + dcharged_dt) / self.__storage_capacity
            return np.array([dsoc_dt, dcharged_dt, ddelivered_dt])

        # Event function to stop the solver when SOC reaches 0
        def soc_zero_event(t: float, y: np.ndarray) -> float:
            soc = y[0]
            return soc  # This will trigger when soc reaches 0

        # Set the event to terminate the integration when SOC reaches 0
        soc_zero_event.terminal = True  # type: ignore[FunctionMemberAccess]
        soc_zero_event.direction = (  # type: ignore[FunctionMemberAccess]
            -1
        )  # Detects when SOC is decreasing and crosses zero

        # NEW: Event function to stop when target energy is delivered
        def target_energy_event(t: float, y: np.ndarray) -> float:
            energy_delivered = y[2]
            return target_energy - energy_delivered if target_energy is not None else 1.0

        target_energy_event.terminal = True  # type: ignore[FunctionMemberAccess]
        target_energy_event.direction = (  # type: ignore[FunctionMemberAccess]
            -1
        )  # Triggers when crossing from positive to negative

        # Combine events
        events = [soc_zero_event]
        if (
            target_energy is not None
            and target_energy > 0.0
            and not math.isclose(target_energy, 0.0, abs_tol=1e-10)
        ):
            events.append(target_energy_event)

        # Set initial conditions
        current_soc = self.__state_of_charge
        initial_energy_charged = 0.0  # No energy charged initially
        initial_energy_delivered = 0.0  # No energy delivered initially
        if time_remaining is None:
            time_remaining = self.__simulation_time.timestep()  # in hours

        # Solve the ODE for SOC, cumulative energy charged, and cumulative energy delivered
        sol = solve_ivp(
            soc_ode,
            [0, time_remaining],
            [current_soc, initial_energy_charged, initial_energy_delivered],
            method="RK45",
            rtol=1e-4,
            atol=1e-6,
            events=events,
        )

        final_soc = sol.y[0][-1]

        # Total energy charged during the timestep
        total_energy_charged = sol.y[1][-1]

        # Total energy delivered during the timestep
        total_energy_delivered = sol.y[2][-1]

        # Determine actual time used
        if isinstance(sol.t_events, list) and sol.t_events[0].size > 0:  # SOC reached 0
            time_used = sol.t_events[0][0]
        elif (
            target_energy is not None
            and isinstance(sol.t_events, list)
            and len(sol.t_events) > 1
            and sol.t_events[1].size > 0
        ):
            # Target energy reached
            time_used = sol.t_events[1][0]
        else:
            time_used = sol.t[-1]

        return (
            total_energy_delivered,
            time_used,
            total_energy_charged,
            final_soc,
        )

    def __energy_output_with_losses(
        self,
        mode: OutputMode,
        time_remaining: float | None = None,
        target_energy: float | None = None,
    ) -> tuple[float, float, float, float, float]:
        """
        Private method: Enhanced version of __energy_output that separately tracks losses.

        Returns: Tuple containing (energy_delivered, time_used, energy_charged, final_soc, energy_lost)
        """
        if mode == OutputMode.MIN:
            soc_array = self.__soc_min_array
            power_func = self.__power_min_func
        elif mode == OutputMode.MAX:
            soc_array = self.__soc_max_array
            power_func = self.__power_max_func
        else:
            raise ValueError("Invalid mode. Choose Mode.MIN or Mode.MAX.")

        power_values: np.ndarray = power_func(soc_array)
        # Set up interpolation functions
        power_interp = interp1d(
            soc_array,
            power_values,
            kind="linear",
            fill_value="extrapolate",
            bounds_error=False,
            assume_sorted=True,
        )

        power_values: np.ndarray = self.__power_min_func(self.__soc_min_array)
        # Also need the MIN power function for tracking losses
        power_min_interp = interp1d(
            self.__soc_min_array,
            power_values,
            kind="linear",
            fill_value="extrapolate",
            bounds_error=False,
            assume_sorted=True,
        )

        # Charging setup
        target_charge = self.__target_electric_charge(time=self.__simulation_time.current_hour())
        if target_charge > 0.0 and not math.isclose(target_charge, 0.0, abs_tol=1e-10):
            charge_rate = self.__pwr_in
            soc_max = target_charge
        else:
            charge_rate = 0
            soc_max = 1.0

        # Enhanced ODE that tracks losses separately
        def soc_ode(t: float, y: np.ndarray) -> np.ndarray:
            soc, energy_charged, energy_delivered, energy_lost = y

            # Ensure SOC stays within bounds
            soc = np.clip(soc, 0, soc_max)

            # Calculate the instantaneous loss rate (always based on MIN output)
            loss_rate = power_min_interp(soc)  # This is the continuous loss
            dlost_dt = loss_rate

            # Calculate the active discharge rate
            if mode == OutputMode.MAX:
                # Total power output when actively delivering
                total_discharge_rate = power_interp(soc)
                # The useful energy delivered is the difference between MAX and MIN
                # (since MIN represents the losses that happen anyway)
                useful_discharge_rate = total_discharge_rate - loss_rate
                ddelivered_dt = useful_discharge_rate.item()
            else:
                # In MIN mode, all output is considered losses
                ddelivered_dt = 0.0
                dlost_dt = power_interp(soc)  # All MIN output is losses

            # Charging
            if soc < soc_max:
                dcharged_dt = charge_rate
            else:
                dcharged_dt = (
                    min(ddelivered_dt + dlost_dt.item(), charge_rate) if target_charge > 0 else 0.0
                )

            # Net SOC rate of change
            dsoc_dt = (-ddelivered_dt - dlost_dt + dcharged_dt) / self.__storage_capacity

            return np.array([dsoc_dt, dcharged_dt, ddelivered_dt, dlost_dt])

        # Event functions
        def soc_zero_event(t, y):
            return y[0]  # Trigger when SOC reaches 0

        soc_zero_event.terminal = True  # type: ignore[FunctionMemberAccess]
        soc_zero_event.direction = -1  # type: ignore[FunctionMemberAccess]

        def target_energy_event(t: float, y: np.ndarray) -> float:
            energy_delivered = y[2]
            return target_energy - energy_delivered if target_energy is not None else 1.0

        target_energy_event.terminal = True  # type: ignore[FunctionMemberAccess]
        target_energy_event.direction = -1  # type: ignore[FunctionMemberAccess]

        events = [soc_zero_event]
        if target_energy is not None and target_energy > 0:
            events.append(target_energy_event)

        # Initial conditions
        current_soc = self.__state_of_charge
        initial_conditions = [current_soc, 0.0, 0.0, 0.0]  # [SOC, charged, delivered, lost]

        if time_remaining is None:
            time_remaining = self.__simulation_time.timestep()

        # Solve the ODE
        sol = solve_ivp(
            soc_ode,
            [0, time_remaining],
            initial_conditions,
            method="RK45",
            rtol=1e-4,
            atol=1e-6,
            events=events,
        )

        final_soc = sol.y[0][-1]
        total_energy_charged = sol.y[1][-1]
        total_energy_delivered = sol.y[2][-1]
        total_energy_lost = sol.y[3][-1]

        # Determine actual time used
        if isinstance(sol.t_events, list) and sol.t_events[0].size > 0:  # SOC reached 0
            time_used = sol.t_events[0][0]
        elif (
            target_energy is not None
            and isinstance(sol.t_events, list)
            and len(sol.t_events) > 1
            and sol.t_events[1].size > 0
        ):
            time_used = sol.t_events[1][0]
        else:
            time_used = sol.t[-1]

        return (
            total_energy_delivered,
            time_used,
            total_energy_charged,
            final_soc,
            total_energy_lost,
        )

    def energy_output_min(self) -> float:
        """
        Calculates the minimum energy that must be delivered based on dry_core_min_output.

        :return: np.float64 (minimum energy deliverable in kWh * __n_units).
        """
        return (
            self.__energy_output(OutputMode.MIN)[0] * self.__n_units
        )  # called externally, factoring in all units

    def __target_electric_charge(self, time: float) -> float:
        """
        Calculates target charge from potential to charge system
        Arguments
        time -- current time period that we are looking at

        returns -- target charge
        """
        temp_air = self._get_temp_for_charge_control()

        if self.__charge_control.logic_type() == ControlLogicType.MANUAL:
            # Implements the "Manual" control logic for ESH
            target_charge: float = self.__charge_control.target_charge()

        elif self.__charge_control.logic_type() == ControlLogicType.AUTOMATIC:
            # Implements the "Automatic" control logic for ESH
            # Automatic charge control can be achieved using internal thermostat(s) to
            # control the extent of charging of the heaters.
            # Availability of electricity to the heaters may be controlled by the electricity
            # supplier on the basis of daily weather predictions (see 24-hour tariff, 12.4.3);
            # this should be treated as automatic charge control.
            # This is currently included by the schedule parameter in charge control object

            # TODO: Check and implement if external temperature sensors are also used for Automatic controls.

            target_charge: float = self.__charge_control.target_charge(temp_air=temp_air)

        elif self.__charge_control.logic_type() == ControlLogicType.CELECT:
            # Implements the "CELECT" control logic for ESH
            # A CELECT-type controller has electronic sensors throughout the dwelling linked
            # to a central control device. It monitors the individual room sensors and optimises
            # the charging of all the storage heaters individually (and may select direct acting
            # heaters in preference to storage heaters).

            target_charge = self.__charge_control.target_charge(temp_air=temp_air)

        elif self.__charge_control.logic_type() == ControlLogicType.HHRSH:
            # Implements the "HHRSH" control logic for ESH
            # A 'high heat retention storage heater' is one with heat retention not less
            # than 45% measured according to BS EN 60531. It incorporates a timer, electronic
            # room thermostat and fan to control the heat output. It is also able to estimate
            # the next day's heating demand based on external temperature, room temperature
            # settings and heat demand periods.

            energy_to_store = self.__charge_control.energy_to_store(
                energy_demand=self.__demand_met + self.__demand_unmet,
                base_temp=self._get_zone_setpoint(),
            )

            # None means not enough past data to do the calculation (Initial 24h of the calculation)
            # We go for a full load of the hhrsh
            if energy_to_store is None:
                energy_to_store = self.__pwr_in * units.hours_per_day

            if energy_to_store > 0:
                if self.__heat_retention_ratio is None:
                    raise ValueError("Heat retention ratio is required for HHRSH.")

                energy_stored = self.__state_of_charge * self.__storage_capacity  # kWh

                if self.__heat_retention_ratio <= 0:
                    energy_to_add = self.__storage_capacity - energy_stored  # kWh
                else:
                    energy_to_add = (1.0 / self.__heat_retention_ratio) * (
                        energy_to_store - energy_stored
                    )  # kWh

                target_charge_hhrsh = (
                    self.__state_of_charge + energy_to_add / self.__storage_capacity
                )
                target_charge_hhrsh = np.clip(target_charge_hhrsh, 0, 1.0)
            else:
                target_charge_hhrsh = 0
            # target_charge (from input file, or zero when control is off) applied here
            # is treated as an upper limit for target charge
            target_charge: float = min(
                self.__charge_control.target_charge(temp_air=None), target_charge_hhrsh
            )

        elif self.__charge_control.logic_type() == ControlLogicType.HEAT_BATTERY:
            # Implements the "HEAT_BATTERY" control logic
            # A 'high heat retention storage battery' is one with heat retention not less
            # than 45% measured according to BS EN 60531. It incorporates a timer
            # and fan to control the heat output. It is also able to estimate
            # the next day's heating demand based on external temperature, room temperature
            # settings and heat demand periods.

            energy_to_store = self.__charge_control.energy_to_store(
                energy_demand=self.__demand_met + self.__demand_unmet,
                base_temp=self._get_zone_setpoint(),
            )

            # None means not enough past data to do the calculation (Initial 24h of the calculation)
            # We go for a full load of the heat battery
            if energy_to_store is None:
                energy_to_store = self.__pwr_in * units.hours_per_day

            if energy_to_store > 0:
                if self.__heat_retention_ratio is None:
                    raise ValueError(
                        "Heat retention ratio is required for Dry Core Heat Batteries."
                    )

                energy_stored = self.__state_of_charge * self.__storage_capacity  # kWh

                if self.__heat_retention_ratio <= 0:
                    energy_to_add = self.__storage_capacity - energy_stored  # kWh
                else:
                    energy_to_add = (1.0 / self.__heat_retention_ratio) * (
                        energy_to_store - energy_stored
                    )  # kWh

                target_charge_hb = self.__state_of_charge + energy_to_add / self.__storage_capacity
                target_charge_hb = np.clip(target_charge_hb, 0, 1.0)
            else:
                target_charge_hb = 0
            # target_charge (from input file, or zero when control is off) applied here
            # is treated as an upper limit for target charge
            target_charge: float = min(
                self.__charge_control.target_charge(temp_air=None), target_charge_hb
            )

        else:
            raise ValueError(
                "Invalid logic type for charge control assigned to HeatStorageDryCore."
            )

        return target_charge

    @abstractmethod
    def _get_temp_for_charge_control(self) -> float | None:
        """Get temperature for charge control calculations.

        Subclasses should override this to provide appropriate temperature
        (e.g., zone air temperature for ESH, or None for heat batteries).
        """
        pass

    @abstractmethod
    def _get_zone_setpoint(self) -> float:
        """Get zone setpoint for HHRSH calculations.

        Subclasses should override this to provide appropriate setpoint.
        """
        pass

    @abstractmethod
    def demand_energy(self, energy_demand: float) -> float:
        """
        Process energy demand. Must be implemented by subclasses.
        """
        pass

    # Accessors for subclasses to use protected attributes
    def _get_state_of_charge(self) -> float:
        return self.__state_of_charge

    def _set_state_of_charge(self, soc: float):
        if math.isclose(soc, 0.0, abs_tol=1e-10):
            soc = 0.0  # pragma: no cover
        self.__state_of_charge = np.clip(soc, 0.0, 1.0)

    def _get_storage_capacity(self) -> float:
        return self.__storage_capacity

    def _get_pwr_in(self) -> float:
        return self.__pwr_in

    def _get_n_units(self) -> int:
        return self.__n_units

    def _get_simulation_time(self) -> SimulationTime:
        return self.__simulation_time

    def _get_demand_met(self) -> float:
        return self.__demand_met

    def _set_demand_met(self, value: float):
        self.__demand_met = value

    def _get_demand_unmet(self) -> float:
        return self.__demand_unmet

    def _set_demand_unmet(self, value: float):
        self.__demand_unmet = value

    def _get_power_max_func(self) -> interp1d:
        """Protected accessor for maximum power interpolation function"""
        return self.__power_max_func

    def _get_power_min_func(self) -> interp1d:
        """Protected accessor for minimum power interpolation function"""
        return self.__power_min_func

    def _energy_output(
        self,
        mode: OutputMode,
        time_remaining: float | None = None,
        target_energy: float | None = None,
    ) -> tuple[float, float, float, float]:
        """Protected method for subclasses to access __energy_output
        :param mode: 'min' for minimum energy delivery, 'max' for maximum energy delivery.
        :param time_remaining: Maximum time available for the operation (hours)
        :param target_energy: Target energy to deliver (kWh). If specified, solver stops when this is reached.
        :return: Tuple containing (energy_delivered in kWh, time_used in hours, energy_charged in kWh, final_soc).
        """
        return self.__energy_output(mode, time_remaining, target_energy)

    def _energy_output_with_losses(
        self,
        mode: OutputMode,
        time_remaining: float | None = None,
        target_energy: float | None = None,
    ) -> tuple[float, float, float, float, float]:
        """
        Protected method for subclasses to access __energy_output_with_losses.
        This method separately tracks energy losses during operation.

        :param mode: 'min' for minimum energy delivery, 'max' for maximum energy delivery.
        :param time_remaining: Maximum time available for the operation (hours)
        :param target_energy: Target energy to deliver (kWh). If specified, solver stops when this is reached.
        :return: Tuple containing (energy_delivered in kWh, time_used in hours, energy_charged in kWh, final_soc, energy_lost in kWh).
        """
        return self.__energy_output_with_losses(
            mode=mode, time_remaining=time_remaining, target_energy=target_energy
        )

    def _energy_output_max(
        self, time_remaining: float | None = None, target_energy: float | None = None
    ) -> tuple[float, float, float, float]:
        """Protected method for subclasses to access __energy_output_max
        :param time_remaining: Maximum time available for the operation (hours)
        :param target_energy: Target energy to deliver (kWh). If specified, solver stops when this is reached.
        :return: Tuple containing (energy_delivered in kWh, time_used in hours, energy_charged in kWh, final_soc).
        """
        return self.__energy_output(
            mode=OutputMode.MAX, time_remaining=time_remaining, target_energy=target_energy
        )

    def _convert_to_kwh(self, power: float, time: float) -> float:
        """Protected version of convert_to_kwh for subclasses"""
        return self.__convert_to_kwh(power=power, time=time)


# Base class for dry core heat battery services
class HeatBatteryDryCoreService:
    """Base class for services provided by dry core heat battery."""

    def __init__(
        self,
        heat_battery: "HeatBatteryDryCore",
        service_name: str,
        control: SetpointTimeControl | None = None,
    ):
        """Construct a HeatBatteryDryCoreService object

        Arguments:
        heat_battery -- reference to the HeatBatteryDryCore object providing the service
        service_name -- name of the service demanding energy from the heat battery
        control -- reference to a control object which must implement is_on() func
        """
        self._heat_battery = heat_battery
        self._service_name = service_name
        self._control = control

    def is_on(self) -> bool:
        if self._control is not None:
            return self._control.is_on()
        else:
            return True


# Updated service classes inheriting from base
class HeatBatteryDryCoreServiceWaterRegular(HeatBatteryDryCoreService):
    """Wrapper for DHW service from dry core heat battery."""

    def __init__(
        self,
        heat_battery: "HeatBatteryDryCore",
        service_name: str,
        cold_feed: ColdWaterSource,
        simulation_time: SimulationTime,
        controlmin: SetpointTimeControl,
        controlmax: SetpointTimeControl,
    ):
        super().__init__(heat_battery=heat_battery, service_name=service_name, control=controlmin)
        self._cold_feed = cold_feed
        self._simulation_time = simulation_time
        self._controlmin = controlmin
        self._controlmax = controlmax
        self._service_name = service_name

    def setpnt(self) -> tuple[float | None, float | None]:
        """Return setpoint (not necessarily temperature)"""
        return self._controlmin.setpnt(), self._controlmax.setpnt()

    def demand_energy(
        self,
        energy_demand: float,
        temp_flow: float,
        temp_return: float,
        update_heat_source_state: bool = True,
    ) -> float:
        """Demand energy (in kWh) from the heat_battery"""
        service_on = self.is_on()
        if not service_on:
            energy_demand = 0.0

        return self._heat_battery._HeatBatteryDryCore__demand_energy(  # type: ignore[AttributeAccessIssue]
            service_name=self._service_name,
            service_type=HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
            energy_output_required=energy_demand,
            temp_return_feed=temp_return,
            temp_output=temp_flow,
            service_on=service_on,
            update_heat_source_state=update_heat_source_state,
        )

    def energy_output_max(self, temp_flow: float, temp_return: float) -> float:
        """Calculate the maximum energy output of the heat_battery"""
        service_on = self.is_on()
        if not service_on:
            return 0.0

        return self._heat_battery._HeatBatteryDryCore__energy_output_max(temp_output=temp_flow)  # type: ignore[AttributeAccessIssue]


class HeatBatteryDryCoreServiceWaterDirect(HeatBatteryDryCoreService):
    """An object to represent a direct water heating service provided by a dry core heat battery.

    This is similar to a combi boiler or HIU providing hot water on demand.
    """

    def __init__(
        self,
        heat_battery: "HeatBatteryDryCore",
        service_name: str,
        setpoint_temp: float,
        cold_feed: ColdWaterSource,
        simulation_time: SimulationTime,
    ):
        """Construct a HeatBatteryDryCoreServiceWaterDirect object

        Arguments:
        heat_battery    -- reference to the HeatBatteryDryCore object providing the service
        service_name    -- name of the service demanding energy from the heat battery
        setpoint_temp   -- temperature of hot water to be provided, in deg C
        cold_feed       -- reference to ColdWaterSource object
        simulation_time -- reference to SimulationTime object
        """
        super().__init__(heat_battery=heat_battery, service_name=service_name, control=None)
        self.__setpoint_temp = setpoint_temp
        self.__cold_feed = cold_feed
        self.__simulation_time = simulation_time
        self.__service_name = service_name

    def get_cold_water_source(self) -> ColdWaterSource:
        return self.__cold_feed

    def get_temp_hot_water(
        self, volume_req: float, volume_req_already: float = 0.0
    ) -> list[tuple[float, float]]:
        """Return temperature of hot water at outlet"""
        if math.isclose(volume_req, 0.0, abs_tol=1e-10):
            raise ValueError("volume_req must be non-zero")

        def temp_hot_water(volume: float) -> float:
            list_temp_vol = self.__cold_feed.get_temp_cold_water(volume_needed=volume)
            inlet_temp = misc.calculate_volume_weighted_average_temperature(
                temp_volume_pairs=list_temp_vol,
                expected_volume=volume,  # This validates the volume matches
            )

            return self._heat_battery._HeatBatteryDryCore__get_temp_hot_water(  # type: ignore[AttributeAccessIssue]
                inlet_temp=inlet_temp,
                volume=volume,
                setpoint_temp=self.__setpoint_temp,
            )

        volume_req_cumulative = volume_req + volume_req_already
        temp_hot_water_cumulative = temp_hot_water(volume=volume_req_cumulative)

        # Base temperature on the part of the draw-off for volume_req, and
        # ignore any volume previously considered
        if math.isclose(volume_req_already, 0.0, abs_tol=1e-10):
            temp_hot_water_req = temp_hot_water_cumulative
        else:
            temp_hot_water_req_already = temp_hot_water(volume=volume_req_already)
            temp_hot_water_req = (
                temp_hot_water_cumulative * volume_req_cumulative
                - temp_hot_water_req_already * volume_req_already
            ) / volume_req

        return [(temp_hot_water_req, volume_req)]

    def demand_hot_water(self, usage_events: list[WaterEventResult] | None) -> float:
        """Process hot water demand directly from dry core heat battery"""
        energy_demand = 0.0
        total_volume = 0.0
        weighted_cold_temp_sum = 0.0

        if usage_events is not None:
            for event in usage_events:
                if math.isclose(event.volume_hot, 0.0, abs_tol=1e-10):
                    continue

                hot_temp = self.get_temp_hot_water(event.volume_hot)[0][0]

                list_temp_vol = self.__cold_feed.draw_off_water(volume_needed=event.volume_hot)
                cold_temp = misc.calculate_volume_weighted_average_temperature(
                    temp_volume_pairs=list_temp_vol,
                    expected_volume=event.volume_hot,  # This validates the volume
                )

                # Calculate energy needed to heat water
                energy_demand += misc.water_demand_to_kWh(
                    litres_demand=event.volume_hot,
                    demand_temperature=hot_temp,
                    cold_temperature=cold_temp,
                )

                # Accumulate for weighted average cold water temperature
                total_volume += event.volume_hot
                weighted_cold_temp_sum += cold_temp * event.volume_hot

        # Calculate weighted average cold water temperature
        if total_volume > 0:
            cold_water_temp = weighted_cold_temp_sum / total_volume
        else:
            # Fallback to sampling method if no events processed
            cold_water_temp_vol = self.__cold_feed.get_temp_cold_water(1.0)
            cold_water_temp = misc.calculate_volume_weighted_average_temperature(
                temp_volume_pairs=cold_water_temp_vol,
                expected_volume=1.0,  # This validates the sampled volume
            )

        # Demand energy from heat battery
        return self._heat_battery._HeatBatteryDryCore__demand_energy(  # type: ignore[AttributeAccessIssue]
            service_name=self.__service_name,
            service_type=HeatingServiceType.DOMESTIC_HOT_WATER_DIRECT,
            energy_output_required=energy_demand,
            temp_return_feed=cold_water_temp,  # return temperature (cold water inlet)
            temp_output=None,
            service_on=True,
            update_heat_source_state=True,
        )


class HeatBatteryDryCoreServiceSpace(HeatBatteryDryCoreService):
    """Wrapper for space heating service from dry core heat battery."""

    def __init__(
        self,
        heat_battery: "HeatBatteryDryCore",
        service_name: str,
        control: SetpointTimeControl | None = None,
    ):
        super().__init__(heat_battery=heat_battery, service_name=service_name, control=control)

    def temp_setpnt(self) -> float | None:
        return self._control.setpnt() if self._control is not None else None

    def in_required_period(self) -> bool | None:
        return self._control.in_required_period() if self._control is not None else None

    def demand_energy(
        self,
        energy_demand: float,
        temp_flow: float,
        temp_return: float,
        time_start: float = 0.0,
        update_heat_source_state: bool = True,
    ) -> float:
        """Process space heating demand through dry core heat battery."""
        service_on = self.is_on()
        if not service_on:
            energy_demand = 0.0

        return self._heat_battery._HeatBatteryDryCore__demand_energy(  # type: ignore[AttributeAccessIssue]
            service_name=self._service_name,
            service_type=HeatingServiceType.SPACE,
            energy_output_required=energy_demand,
            temp_return_feed=temp_return,
            temp_output=temp_flow,
            service_on=service_on,
            update_heat_source_state=update_heat_source_state,
        )

    def energy_output_max(
        self, temp_output: float, temp_return_feed: float, time_start: float = 0.0
    ) -> float:
        """Calculate maximum energy output for space heating."""
        if not self.is_on():
            return 0.0

        return self._heat_battery._HeatBatteryDryCore__energy_output_max(  # type: ignore[AttributeAccessIssue]
            temp_output=temp_output, time_start=time_start
        )


class HeatBatteryDryCore(HeatStorageDryCore):
    """Class to represent dry core heat batteries.

    These batteries use electrical storage similar to ESH but provide
    heating through water services (space heating via (e.g.) radiators and DHW).
    """

    def __init__(
        self,
        heat_battery_dict: dict,
        charge_control: ChargeControl,
        energy_supply: EnergySupply,
        energy_supply_conn: EnergySupplyConnection,
        simulation_time: SimulationTime,
        n_units: int = 1,
        output_detailed_results: bool = False,
    ):
        """Construct a HeatBatteryDryCore object

        Arguments:
        heat_battery_dict     -- dict with heat battery properties
            pwr_in                   -- Charging power (kW)
            heat_storage_capacity    -- Heat storage capacity (kWh)
            dry_core_min_output      --
                Minimum output of the electric storage heater. (Unit: kW)
                Data from test showing the output from the storage heater when not actively
                outputting heat, i.e. case losses only
            dry_core_max_output      --
                Maximum output of the electric storage heater. (Unit: kW)
                Data from test showing the output from the storage heater when it is actively
                outputting heat, e.g. damper open / fan running.
            fan_pwr                  -- Fan power (unit: W)
            rated_power_instant      -- Rated instantaneous power output (kW)
            state_of_charge_init     -- State of charge at initialisation of dry core heat storage (ratio)
            electricity_circ_pump    --
            electricity_standby      --
            setpoint_temp_water      -- Water setpoint temperature (°C)
        charge_control        -- reference to ChargeControl object
        energy_supply         -- reference to EnergySupply object
        energy_supply_conn    -- reference to EnergySupplyConnection object
        simulation_time       -- reference to SimulationTime object
        n_units              -- number of units installed
        output_detailed_results -- flag for detailed output
        """
        # Extract parameters from dict
        pwr_in = heat_battery_dict["pwr_in"]
        storage_capacity = heat_battery_dict["heat_storage_capacity"]
        dry_core_min_output = heat_battery_dict["dry_core_min_output"]
        dry_core_max_output = heat_battery_dict["dry_core_max_output"]
        self.__fan_pwr = heat_battery_dict["fan_pwr"]
        self.__pwr_instant = heat_battery_dict["rated_power_instant"]

        # Initialize base class
        super().__init__(
            pwr_in=pwr_in,
            storage_capacity=storage_capacity,
            n_units=n_units,
            simulation_time=simulation_time,
            charge_control=charge_control,
            dry_core_min_output=dry_core_min_output,
            dry_core_max_output=dry_core_max_output,
            state_of_charge_init=heat_battery_dict["state_of_charge_init"],
        )

        # Dry core specific attributes
        self.__energy_supply = energy_supply
        self.__energy_supply_conn = energy_supply_conn
        self.__energy_supply_connections = {}

        # Heat transfer parameters
        self.__power_circ_pump = heat_battery_dict.get("electricity_circ_pump", 0.06)
        self.__power_standby = heat_battery_dict.get("electricity_standby", 0.024)

        # Service tracking
        self.__service_results = []
        self.__total_time_running_current_timestep = 0.0
        self.__pump_running_time_current_timestep = 0.0
        self.__flag_first_call = True
        self.__battery_losses = 0.0

        # Zone temperature initialization (for HHRSH control)
        self.__zone_temp_init = 21.0  # Default, will be updated if needed

        # Detailed results
        self.__output_detailed_results = output_detailed_results
        if output_detailed_results:
            self.__detailed_results = []
        else:
            self.__detailed_results = None

    def _get_temp_for_charge_control(self) -> float | None:
        """Get temperature for charge control calculations."""
        # For heat batteries, return None as they don't have direct zone temperature sensing
        return None

    def _get_zone_setpoint(self) -> float:
        """Get zone setpoint for HEAT_BATTERY calculations."""
        return self.__zone_temp_init

    def __create_service_connection(self, service_name: str):
        """Create an EnergySupplyConnection for the service."""
        if service_name in self.__energy_supply_connections.keys():
            raise ValueError(f"Service name already used: {service_name}")

        self.__energy_supply_connections[service_name] = self.__energy_supply.connection(
            end_user_name=service_name
        )

    def create_service_hot_water_regular(
        self,
        service_name: str,
        cold_feed: ColdWaterSource,
        controlmin: SetpointTimeControl,
        controlmax: SetpointTimeControl,
    ) -> HeatBatteryDryCoreServiceWaterRegular:
        """Return a HeatBatteryDryCoreServiceWaterRegular object for DHW."""
        self.__create_service_connection(service_name=service_name)

        return HeatBatteryDryCoreServiceWaterRegular(
            self,
            service_name=service_name,
            cold_feed=cold_feed,
            simulation_time=self._get_simulation_time(),
            controlmin=controlmin,
            controlmax=controlmax,
        )

    def create_service_hot_water_direct(
        self,
        service_name: str,
        setpoint_temp: float,
        cold_feed: ColdWaterSource,
    ) -> HeatBatteryDryCoreServiceWaterDirect:
        """Return a HeatBatteryDryCoreServiceWaterDirect object and create an EnergySupplyConnection for it

        Arguments:
        service_name  -- name of the service demanding energy from the heat battery
        setpoint_temp -- temperature of hot water to be provided, in deg C
        cold_feed     -- reference to ColdWaterSource object
        """
        self.__create_service_connection(service_name=service_name)
        return HeatBatteryDryCoreServiceWaterDirect(
            self,
            service_name=service_name,
            setpoint_temp=setpoint_temp,
            cold_feed=cold_feed,
            simulation_time=self._get_simulation_time(),
        )

    def create_service_space_heating(
        self,
        service_name: str,
        control: SetpointTimeControl,
    ) -> HeatBatteryDryCoreServiceSpace:
        """Return a HeatBatteryDryCoreServiceSpace object for space heating."""
        self.__create_service_connection(service_name=service_name)

        return HeatBatteryDryCoreServiceSpace(
            self,
            service_name=service_name,
            control=control,
        )

    def get_battery_losses(self) -> float:
        """Return battery losses"""
        battery_losses = self.__battery_losses * self._get_n_units()
        self.__battery_losses = 0.0
        return battery_losses

    def __time_available(self, time_start: float, timestep: float) -> float:
        """Calculate time available for the current service"""
        # Assumes that time spent on other services is evenly spread throughout
        # the timestep so the adjustment for start time below is a proportional
        # reduction of the overall time available, not simply a subtraction
        time_available = (timestep - self.__total_time_running_current_timestep) * (
            1.0 - time_start / timestep
        )
        return time_available

    def demand_energy(self, energy_demand: float) -> float:
        """This should not be called directly for heat battery services."""
        raise NotImplementedError("Use service-specific demand methods instead")

    def __demand_energy(
        self,
        service_name: str,
        service_type: HeatingServiceType,
        energy_output_required: float,
        temp_return_feed: float,
        temp_output: float,
        service_on: bool,
        time_start: float = 0.0,
        update_heat_source_state: bool = True,
        volume_hot_water: float = 0.0,
    ) -> float:
        # Calculate how much energy can be delivered based on SOC
        timestep = self._get_simulation_time().timestep()
        time_remaining = self.__time_available(time_start=time_start, timestep=timestep)

        energy_charged = 0
        energy_output_required = energy_output_required / self._get_n_units()
        self.__energy_instant: float = 0.0
        self.__energy_for_fan: float = 0.0
        time_running_current_service = 0

        """Process energy demand from a specific service."""
        if (
            not service_on
            or energy_output_required < 0
            or math.isclose(energy_output_required, 0.0, abs_tol=1e-10)
        ):
            if update_heat_source_state:
                self.__service_results.append(
                    {
                        "service_name": service_name,
                        "service_type": service_type,
                        "service_on": service_on,
                        "energy_output_required": energy_output_required * self._get_n_units(),
                        "energy_delivered": 0.0,
                        "temp_output": temp_output,
                        "temp_inlet": temp_return_feed,
                        "time_running": 0,
                        "demand_unmet": self._get_demand_unmet() * self._get_n_units(),
                        "energy_delivered_HB": 0.0,
                        "energy_delivered_backup": 0.0,
                        "energy_delivered_total": 0.0,
                        "energy_charged_during_service": 0.0,
                        "dry_core_soc": self._get_state_of_charge(),
                        "current_hb_power": "",
                    }
                )
            return 0.0

        if time_remaining < 0 or math.isclose(time_remaining, 0.0, abs_tol=1e-10):
            # No time left to run this service
            energy_delivered_HB = 0.0
            energy_lost = 0.0
            # Update demand tracking
            self._set_demand_met(0.0)
            self._set_demand_unmet(energy_output_required)
        else:
            # Use the enhanced energy output method with loss tracking
            # First check maximum available energy
            q_released_max, time_used_max, energy_charged_max, final_soc, losses_max = (
                self._energy_output_with_losses(mode=OutputMode.MAX, time_remaining=time_remaining)
            )

            # For DHW direct, no charging during same timestep
            # if service_type == HeatingServiceType.DOMESTIC_HOT_WATER_DIRECT:
            #     q_released_max -= energy_charged_max
            #     q_released_max = max(0, q_released_max)

            # Determine how to deliver the energy
            if q_released_max > energy_output_required or math.isclose(
                q_released_max - energy_output_required, 0.0, abs_tol=1e-10
            ):
                # Can meet demand - use exact target with loss tracking
                (
                    energy_delivered_HB,
                    time_running_current_service,
                    energy_charged,
                    final_soc,
                    energy_lost,
                ) = self._energy_output_with_losses(
                    mode=OutputMode.MAX,
                    time_remaining=time_remaining,
                    target_energy=energy_output_required,
                )
                energy_delivered_HB = min(energy_delivered_HB, energy_output_required)

            else:
                # Not enough energy in storage - deliver what we can
                energy_delivered_HB = q_released_max
                time_running_current_service = time_used_max
                energy_charged = energy_charged_max
                energy_lost = losses_max

                # Top up with instant heater if available
                if self.__pwr_instant:
                    self.__energy_instant = min(
                        energy_output_required - energy_delivered_HB,
                        self.__pwr_instant * time_remaining,
                    )  # kWh
                    time_instant = self.__energy_instant / self.__pwr_instant
                    time_running_current_service += time_instant
                    time_running_current_service = min(time_running_current_service, time_remaining)

            # The losses are now accurately integrated during the service delivery
            self.__battery_losses += energy_lost

            # Update state of charge (the ODE has already integrated everything accurately)
            self._set_state_of_charge(soc=final_soc)

            # Update demand tracking
            self._set_demand_met(energy_delivered_HB + self.__energy_instant)
            self._set_demand_unmet(
                max(0, energy_output_required - energy_delivered_HB - self.__energy_instant)
            )

            # Calculate fan energy
            self.__energy_for_fan = self._convert_to_kwh(
                power=self.__fan_pwr, time=time_running_current_service
            )
            # Add energy for fan to internal gains or core or service... TBD

            if update_heat_source_state:
                # Track time running
                self.__total_time_running_current_timestep += time_running_current_service

                # Track pump running time (only for regular DHW and space heating)
                # Direct DHW services don't use circulation pumps
                if service_type in (
                    HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR,
                    HeatingServiceType.SPACE,
                ):
                    self.__pump_running_time_current_timestep += time_running_current_service
                elif service_type == HeatingServiceType.DOMESTIC_HOT_WATER_DIRECT:
                    pass  # Direct DHW doesn't use circulation pump
                else:
                    raise ValueError(f"Unexpected service type: {service_type}")  # pragma: no cover

        if update_heat_source_state:
            # Log the energy charged, fan energy, and total energy delivered
            self.__energy_supply_conn.demand_energy(
                amount_demanded=self._get_n_units()
                * (energy_charged + self.__energy_instant + self.__energy_for_fan)
            )

            current_hb_power = ""
            if time_running_current_service > 0:
                current_hb_power = (
                    energy_delivered_HB * units.seconds_per_hour / time_running_current_service
                )

            # Record service results with accurate loss tracking
            self.__service_results.append(
                {
                    "service_name": service_name,
                    "service_type": service_type,
                    "service_on": service_on,
                    "energy_output_required": energy_output_required * self._get_n_units(),
                    "temp_output": temp_output,
                    "temp_inlet": temp_return_feed,
                    "time_running": time_running_current_service,
                    "demand_unmet": self._get_demand_unmet() * self._get_n_units(),
                    "energy_delivered_HB": energy_delivered_HB * self._get_n_units(),
                    "energy_delivered_backup": self.__energy_instant * self._get_n_units(),
                    "energy_delivered_total": (energy_delivered_HB + self.__energy_instant)
                    * self._get_n_units(),
                    "energy_charged_during_service": energy_charged * self._get_n_units(),
                    "energy_for_fans": self.__energy_for_fan * self._get_n_units(),
                    "dry_core_soc": self._get_state_of_charge(),
                    "current_hb_power": current_hb_power * self._get_n_units(),
                    "energy_lost": energy_lost * self._get_n_units(),  # Now accurately integrated
                }
            )

        return (energy_delivered_HB + self.__energy_instant) * self._get_n_units()

    def __calculate_max_deliverable_temp(
        self, inlet_temp: float, volume: float, setpoint_temp: float
    ) -> float:
        """Calculate maximum temperature that can be delivered based on SOC and inlet conditions.

        This method calculates the maximum outlet temperature achievable based on:

        Args:
            inlet_temp      -- Inlet water temperature (°C)
            volume          -- Volume of DHW required (l)
            setpoint_temp   -- temperature of hot water to be provided (°C)
        Returns:
            Maximum outlet temperature achievable (°C)
        """
        # Get maximum power output at current SOC using the accessor method
        max_power_kw = self._get_power_max_func()(self._get_state_of_charge())

        flow_rate_kg_per_s = (
            volume / self._HeatStorageDryCore__simulation_time.timestep()  # type: ignore[AttributeAccessIssue]
        ) * WATER.density()
        # Calculate maximum temperature rise using heat transfer equation
        # Q = ṁ × c_p × ΔT
        # Rearranged: ΔT = Q / (ṁ × c_p)
        # Note: specific_heat_capacity_kWh() gives kWh/(kg·K), multiply by 3600 to get kJ/(kg·K)
        if flow_rate_kg_per_s > 0:
            specific_heat_kj_per_kg_k = WATER.specific_heat_capacity_kWh() * units.kJ_per_kWh
            max_temp_rise = max_power_kw / (
                flow_rate_kg_per_s * specific_heat_kj_per_kg_k / units.W_per_kW
            )  # kW = kJ/s
            max_outlet_temp = inlet_temp + max_temp_rise
        else:
            # No flow means no heat transfer possible
            max_outlet_temp = inlet_temp

        # Cap at maximum design temperature to prevent unrealistic values
        # and ensure system safety limits are respected
        return min(max_outlet_temp, setpoint_temp)

    def __energy_output_with_losses(
        self,
        mode: OutputMode,
        time_remaining: float | None = None,
        target_energy: float | None = None,
    ) -> tuple[float, float, float, float, float]:
        """
        Method for subclasses to access HeatStorageDryCore _energy_output_with_losses.
        This method separately tracks energy losses during operation.

        :param mode: 'min' for minimum energy delivery, 'max' for maximum energy delivery.
        :param time_remaining: Maximum time available for the operation (hours)
        :param target_energy: Target energy to deliver (kWh). If specified, solver stops when this is reached.
        :return: Tuple containing (energy_delivered in kWh, time_used in hours, energy_charged in kWh, final_soc, energy_lost in kWh).
        """
        return self._energy_output_with_losses(
            mode=mode, time_remaining=time_remaining, target_energy=target_energy
        )

    def __energy_output(
        self,
        mode: OutputMode,
        time_remaining: float | None = None,
        target_energy: float | None = None,
    ) -> tuple[float, float, float, float]:
        """
        Method for subclasses to access HeatStorageDryCore _energy_output_with_losses.
        This method separately tracks energy losses during operation.

        :param mode: 'min' for minimum energy delivery, 'max' for maximum energy delivery.
        :param time_remaining: Maximum time available for the operation (hours)
        :param target_energy: Target energy to deliver (kWh). If specified, solver stops when this is reached.
        :return: Tuple containing (energy_delivered in kWh, time_used in hours, energy_charged in kWh, final_soc, energy_lost in kWh).
        """
        return self._energy_output(
            mode=mode, time_remaining=time_remaining, target_energy=target_energy
        )

    def __energy_output_max(self, temp_output: float, time_start: float = 0.0) -> float:
        """Calculate maximum energy output for current SOC and temperature requirements.

        Args:
            temp_output: Required output temperature (°C)
            time_start: Start time within timestep (unused currently)

        Returns:
            Maximum energy output (kWh)
        """
        timestep = self._get_simulation_time().timestep()
        time_remaining = self.__time_available(time_start=time_start, timestep=timestep)
        # First, get the base class calculation which includes charging logic
        q_released_max, __, __, __ = self._energy_output_max(time_remaining=time_remaining)

        if self.__pwr_instant:
            self.__energy_instant = self.__pwr_instant * time_remaining
        else:
            self.__energy_instant = 0.0

        # Can only provide energy if we can achieve the required output temperature
        return (q_released_max + self.__energy_instant) * self._get_n_units()

    def __get_temp_hot_water(self, inlet_temp: float, volume: float, setpoint_temp: float) -> float:
        """Calculate hot water temperature achievable."""
        return self.__calculate_max_deliverable_temp(
            inlet_temp=inlet_temp, volume=volume, setpoint_temp=setpoint_temp
        )

    def timestep_end(self):
        """Calculations to be done at the end of each timestep."""
        timestep = self._get_simulation_time().timestep()
        time_remaining = timestep - self.__total_time_running_current_timestep

        # Calculate auxiliary energy
        energy_aux = self.__pump_running_time_current_timestep * self.__power_circ_pump
        energy_aux += self.__power_standby * time_remaining
        self.__energy_supply_conn.demand_energy(amount_demanded=energy_aux)

        energy_charged = 0.0
        final_losses = 0.0

        # Handle charging and losses at end of timestep if needed
        # The base class _energy_output_with _losses handles simultaneous charging during discharge,
        # but we may need additional charging at the end of timestep

        if time_remaining > 0:
            # Use the enhanced method to get accurate losses during idle time
            _, _, energy_charged, final_soc, final_losses = self._energy_output_with_losses(
                mode=OutputMode.MIN, time_remaining=time_remaining
            )

            self.__energy_supply_conn.demand_energy(
                amount_demanded=energy_charged * self._get_n_units()
            )
            self._set_state_of_charge(soc=final_soc)

        self.__battery_losses += final_losses

        # Save detailed results if required
        if self.__detailed_results is not None:
            self.__detailed_results.append(
                {
                    "timestep": self._get_simulation_time().index(),
                    "services": self.__service_results,
                    "soc": self._get_state_of_charge(),
                    "energy_aux": energy_aux * self._get_n_units(),
                    "non_service_energy_lost": final_losses * self._get_n_units(),
                    "non_service_charge": energy_charged * self._get_n_units(),
                }
            )

        # Reset for next timestep
        self.__total_time_running_current_timestep = 0.0
        self.__pump_running_time_current_timestep = 0.0
        self.__service_results = []
        self.__flag_first_call = True

    def output_detailed_results(
        self,
        hot_water_energy_output: dict[str, list[float]],
        hot_water_source_name_for_heat_battery_service: dict[str, str],
    ) -> tuple[
        dict[str, dict[tuple[str, str], list[float | int]]],
        dict[str, dict[tuple[str, str], float | int]],
    ]:
        """Output detailed results of heat battery calculation."""
        output_parameters = [
            ("service_name", None, False),
            ("service_type", None, False),
            ("service_on", None, False),
            ("energy_output_required", "kWh", True),
            ("temp_output", "degC", False),
            ("temp_inlet", "degC", False),
            ("time_running", "secs", True),
            ("unmet_demand", "kWh", True),
            ("energy_delivered_HB", "kWh", True),
            ("energy_delivered_backup", "kWh", True),
            ("energy_delivered_total", "kWh", True),
            ("energy_charged_during_service", "kWh", True),
            ("energy_for_fans", "kWh", True),
            ("dry_core_soc", "ratio", False),
            ("current_hb_power", "kW", False),
            ("energy_lost", "kWh", True),
        ]
        aux_parameters = [
            ("energy_aux", "kWh", True),
            ("soc", "ratio", False),
            ("non_service_energy_lost", "kWh", True),
            ("non_service_charge", "kWh", True),
        ]

        results_per_timestep = {"auxiliary": {}}
        # Report auxiliary parameters (not specific to a service)
        for parameter, param_unit, _ in aux_parameters:
            results_per_timestep["auxiliary"][(parameter, param_unit)] = []
            for timestep_data in self.__detailed_results or []:
                # For dry core, auxiliary data is stored directly in the timestep dict
                if parameter in timestep_data:
                    result = timestep_data[parameter]
                else:
                    # Calculate energy_aux if not directly stored
                    result = timestep_data.get("energy_aux", 0.0)
                results_per_timestep["auxiliary"][(parameter, param_unit)].append(result)

        # For each service, report required output parameters
        service_names = list(self.__energy_supply_connections.keys())
        for _service_idx, service_name in enumerate(service_names):
            results_per_timestep[service_name] = {}
            # Look up each required parameter
            for parameter, param_unit, _ in output_parameters:
                results_per_timestep[service_name][(parameter, param_unit)] = []
                # Look up value of required parameter in each timestep
                for timestep_data in self.__detailed_results or []:
                    services_list = timestep_data["services"]
                    # Find the service data for this service
                    service_data = None
                    for service in services_list:
                        if service["service_name"] == service_name:
                            service_data = service
                            break

                    if service_data is not None and parameter in service_data:
                        result = service_data[parameter]
                    else:
                        # Default value if parameter not found
                        result = 0.0 if param_unit else ""
                    results_per_timestep[service_name][(parameter, param_unit)].append(result)

        results_annual = {
            "Overall": {
                (parameter, param_units): 0.0
                for parameter, param_units, incl_in_annual in output_parameters
                if incl_in_annual
            },
            "auxiliary": {},
        }

        # Report auxiliary parameters (not specific to a service)
        for parameter, param_unit, incl_in_annual in aux_parameters:
            if incl_in_annual:
                results_annual["auxiliary"][(parameter, param_unit)] = math.fsum(
                    results_per_timestep["auxiliary"][(parameter, param_unit)]
                )

        # For each service, report required output parameters
        for service_name in service_names:
            results_annual[service_name] = {}
            for parameter, param_unit, incl_in_annual in output_parameters:
                if incl_in_annual:
                    parameter_annual_total = math.fsum(
                        results_per_timestep[service_name][(parameter, param_unit)]
                    )
                    results_annual[service_name][(parameter, param_unit)] = parameter_annual_total
                    results_annual["Overall"][(parameter, param_unit)] += parameter_annual_total

        return results_per_timestep, results_annual
