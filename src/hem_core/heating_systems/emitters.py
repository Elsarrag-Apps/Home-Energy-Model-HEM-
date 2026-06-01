#!/usr/bin/env python3

"""
This module provides objects to represent radiator, underfloor and fancoil emitter systems.
"""

import logging
import math
import sys
import warnings

import numpy as np
from numpy import ndarray

# Third-party imports
from scipy.integrate import solve_ivp
from scipy.interpolate import interp1d
from scipy.optimize import fsolve, root
from scipy.optimize._zeros_py import bisect

import hem_core.units as units
from hem_core.heating_systems import SpaceHeatSystem

# Import enums from the shared enums module
from hem_core.input_output.enums import (
    EcoDesignControllerClass,
    WetEmitterType,
)
from hem_core.input_output.output import OutputEmitters
from hem_core.material_properties import WATER
from hem_core.pipework import Pipework

logger = logging.getLogger(__name__)


def convert_flow_to_return_temp(flow_temp_celsius: float) -> float:
    """
    Convert flow temperature to return temperature using the 6/7th rule.

    Parameters:
    flow_temp_celsius (float): Flow temperature in degrees Celsius.

    Returns:
    float: Return temperature in degrees Celsius.
    """
    return (6.0 / 7.0) * flow_temp_celsius


class Emitters(SpaceHeatSystem):
    def __init__(
        self,
        thermal_mass,
        emitters,
        pipework,
        temp_diff_emit_dsgn,
        variable_flow,
        design_flow_rate,
        min_flow_rate,
        max_flow_rate,
        bypass_fraction_recirculated,
        heat_source,
        zone,
        ext_cond,
        ecodesign_controller,
        design_flow_temp,
        simulation_time,
        initial_temp: float,
        energy_supply_fan_coil_conn=None,
        output_detailed_results=False,
        with_buffer_tank=False,
    ):
        """Construct an Emitters object

        Arguments:
        thermal_mass -- thermal mass of emitters, in kWh / K
        emitters -- list of each emiiter characteristics, i.e.
                        wet_emitter_type -- type of emitter: radiator, ufh (under floor heating), fancoil
                    For Radiators:
                        c -- constant from characteristic equation of emitters
                            (e.g. derived from BS EN 442 tests)
                        n -- exponent from characteristic equation of emitters
                            (e.g. derived from BS EN 442 tests)
                        frac_convective -- convective fraction for heating
                    For UFH:
                        equivalent_specific_thermal_mass -- Equivalent thermal mass per m² of floor area for under-floor heating systems in kJ/m²K
                                                            calculated according to BEAMA guidance
                        system_performance_factor -- Heat output per m² of floor area for under-floor heating systems in W/m²K
                                                    (i.e. Kh from EN1264)
                        emitter_floor_area -- Floor area of UFH emitter
                        frac_convective -- convective fraction for heating (optional)
                    For Fancoils:
                        n_units -- Number of units of this specification of fancoil in Zone
                        fancoil_test_data -- Manufacturer's data for fancoil unit
        pipework -- list of each distribution pipework characteristics as required by pipework.py with diameters in mm instead of m
        temp_diff_emit_dsgn -- design temperature difference across the emitters, in deg C or K
        variable_flow -- the heat source can modulate flow rate.
        design_flow_rate -- constant flow rate if the heat source can´t modulate flow rate.
        min_flow_rate -- minimum flow rate allowed.
        max_flow_rate -- maximum flow rate allowed.
        bypass_fraction_recirculated -- fraction of return back into flow water.
        heat_source -- reference to an object representing the system (e.g.
                       boiler or heat pump) providing heat to the emitters
        zone -- reference to the Zone object representing the zone in which the
                emitters are located
        simulation_time -- reference to SimulationTime object
        energy_supply_fan_coil_conn   -- reference to EnergySupplyConnection object to capture fan energy
                                   from Fancoil units.
        output_detailed_results -- flag to create detailed emitter output results
        with_buffer_tank -- True/False the emitters loop include a buffer tank (Only for HPs)

        Other variables:
        temp_emitter_prev -- temperature of the emitters at the end of the
                             previous timestep, in deg C
        """
        # TODO What if emitter system has several emitters with different specs?
        # TODO What if emitter system serves more than one zone? What would flow temp be?
        # TODO Is it possible to have both radiators and fancoils in the same zone?
        self.__thermal_mass = thermal_mass
        self.__emitters = emitters
        self.__pipework = pipework
        self.__temp_diff_emit_dsgn = temp_diff_emit_dsgn
        self.__variable_flow = variable_flow
        if self.__variable_flow:
            if min_flow_rate is None or max_flow_rate is None:
                raise ValueError(
                    "min_flow_rate and max_flow_rate are required when variable_flow is True"
                )
            self.__min_flow_rate = (
                min_flow_rate / units.seconds_per_minute
            )  # l/min in input file, here converted to l/s
            self.__max_flow_rate = (
                max_flow_rate / units.seconds_per_minute
            )  # l/min in input file, here converted to l/s
        else:
            if design_flow_rate is None:
                raise ValueError("design_flow_rate is required when variable_flow is False")
            self.__design_flow_rate = (
                design_flow_rate / units.seconds_per_minute
            )  # l/min in input file, here converted to l/s
            # For buffer tank calculations
            self.__min_flow_rate = self.__design_flow_rate
            self.__max_flow_rate = self.__design_flow_rate

        if bypass_fraction_recirculated is None:
            self.__bypass_fraction_recirculated = 0.0
        else:
            self.__bypass_fraction_recirculated = bypass_fraction_recirculated

        if self.__bypass_fraction_recirculated < 0.0 or self.__bypass_fraction_recirculated > 1.0:
            raise ValueError("bypass_fraction_recirculated must be between 0 and 1")

        self.__heat_source = heat_source
        self.__zone = zone
        self.__simtime = simulation_time
        self.__external_conditions = ext_cond
        self.__output_detailed_results = output_detailed_results
        self.__with_buffer_tank = with_buffer_tank
        self.__energy_supply_fan_coil_conn = energy_supply_fan_coil_conn

        self.__design_flow_temp = design_flow_temp
        self.__ecodesign_control_class = EcoDesignControllerClass(
            ecodesign_controller["ecodesign_control_class"]
        )
        if self.__ecodesign_control_class in (
            EcoDesignControllerClass.CLASS_II,
            EcoDesignControllerClass.CLASS_III,
            EcoDesignControllerClass.CLASS_VI,
            EcoDesignControllerClass.CLASS_VII,
        ):
            self.__min_outdoor_temp = ecodesign_controller["min_outdoor_temp"]
            self.__max_outdoor_temp = ecodesign_controller["max_outdoor_temp"]
            self.__min_flow_temp = ecodesign_controller["min_flow_temp"]
            self.__max_flow_temp = self.__design_flow_temp

        # Set initial values
        self.__temp_emitter_prev = initial_temp

        # Create instance variable for emitter detailed output
        if self.__output_detailed_results:
            self.__emitters_detailed_results = {}
        else:
            self.__emitters_detailed_results = None

        # Pre-processing parameters for All emitters
        floor_area = self.__zone.area()
        total_emitter_floor_area = 0.0
        self.__fancoil = None
        self.__flag_fancoil = False
        number_of_elements = 0

        for emitter in self.__emitters:
            emitter["wet_emitter_type"] = WetEmitterType(emitter["wet_emitter_type"])

        # 1. Process Radiators First
        for emitter in self.__emitters:
            if emitter["wet_emitter_type"] == WetEmitterType.RADIATOR:
                number_of_elements += 1  # Increment the number of emitters

                # Calculate c from c_per_m if it is set
                if "c_per_m" in emitter:
                    emitter["c"] = emitter["c_per_m"] * emitter["length"]

                # Calculate thermal_mass from thermal_mass_per_m if it is set
                if "thermal_mass_per_m" in emitter:
                    emitter["thermal_mass"] = emitter["thermal_mass_per_m"] * emitter["length"]

                # Accumulate individual radiator thermal mass into system total
                if "thermal_mass" in emitter:
                    if self.__thermal_mass is None:
                        self.__thermal_mass = 0.0
                    self.__thermal_mass += emitter["thermal_mass"]

        # Validation check after radiator processing - only if radiators exist
        has_radiators = any(
            emitter["wet_emitter_type"] == WetEmitterType.RADIATOR for emitter in self.__emitters
        )
        if has_radiators and self.__thermal_mass is None:
            raise ValueError("Thermal Mass is required for Radiator type emitters.")
            # Thermal_mass is a required input for radiators -
            # not underfloor. This is because the thermal mass of UFH is
            # included in the UFH-only 'equivalent_specific_thermal_mass' input.
            # The latter can only be calculated for UFH systems, by definition,
            # so could not mistakenly be entered for a radiator system.
            # But for a system containing mix of radiators and UFH, the thermal_mass
            # input is required - including only the thermal mass of the radiators.

        # 2. Process UFH Emitters Next
        for emitter in self.__emitters:
            # Handle UFH after Radiators so thermal_mass check occurs first
            if emitter["wet_emitter_type"] == WetEmitterType.UFH:
                number_of_elements += 1
                emitter["n"] = (
                    1  # For UFH, BS EN 1264 and 11855 define this as 1 under normal circumstances
                )
                emitter["c"] = (
                    emitter["system_performance_factor"]
                    * emitter["emitter_floor_area"]
                    / units.W_per_kW
                )
                total_emitter_floor_area += emitter["emitter_floor_area"]

                # The thermal_mass input from assessor only includes radiators.
                # The equivalent_specific_thermal_mass for UFH (once converted to
                # the same units) needs to be added to this to get the total.
                if self.__thermal_mass is None:
                    self.__thermal_mass = 0.0
                self.__thermal_mass += (
                    emitter["equivalent_specific_thermal_mass"]
                    * emitter["emitter_floor_area"]
                    / units.kJ_per_kWh
                )

        # 3. Process Fancoils Last
        for emitter in self.__emitters:
            if emitter["wet_emitter_type"] == WetEmitterType.FANCOIL:
                number_of_elements += 1
                self.__flag_fancoil = True

                if "fancoil_test_data" not in emitter:
                    raise ValueError("Fancoil emitter type requires manufacturer data.")

                if "n_units" not in emitter:
                    emitter["n_units"] = 1

                # Attribute to hold fan coil manufacturer data.
                emitter = self.add_temperature_diff_zero(emitter)
                emitter["temperature_data"], emitter["fan_power_data"] = (
                    self.format_fancoil_manufacturer_data(emitter["fancoil_test_data"])
                )

                # Only one specification in initial implementation
                self.__fancoil = emitter

            # Ensure frac_convective is provided
            if "frac_convective" not in emitter:
                raise ValueError("frac_convective expected for emitters.")
            # TODO Calculate convective fraction for UFH from floor surface temperature Tf,
            # and the room air temperature, according the formula below.
            # Ta = self.__zone.temp_internal_air()  # room_air_temp
            # self.__frac_convective = ((8.92 * (Tf - Ta) ** 1.1 / (Tf - Ta)) - 5.5) / (8.92 * ( Tf - Ta ) ** 1.1 / ( Tf - Ta ))
            # Need to come up with a method to calculate floor surface temperature.

        # Pre-processing internal pipeworks into equivalent emitters
        self.__pipework_list = []
        for pipework in self.__pipework:
            if pipework["location"] == "internal":
                pipework_emitter = Pipework(
                    location=pipework["location"],
                    internal_diameter=pipework["internal_diameter_mm"] / units.mm_per_m,
                    external_diameter=pipework["external_diameter_mm"] / units.mm_per_m,
                    length=pipework["length"],
                    insulation_thermal_conductivity=pipework["insulation_thermal_conductivity"],
                    insulation_thickness=pipework["insulation_thickness_mm"] / units.mm_per_m,
                    reflective=pipework["surface_reflectivity"],
                    contents=pipework["pipe_contents"],
                )
                if self.__flag_fancoil:
                    self.__pipework_list.append(pipework_emitter)
                else:
                    # Currently only uninsulated pipework are considered for distribution losses when combined with radiators
                    if pipework["insulation_thickness_mm"] > 0:
                        logger.warning(
                            "Heat loss from insulated pipework to heat emitters is currently ignored - only uninsulated pipework is currently considered."
                        )
                    else:
                        pw_c, pw_n, pw_thermal_mass = pipework_emitter.c_n_equivalence()
                        # Create a new radiator entry
                        new_radiator = {
                            "wet_emitter_type": "radiator",
                            "c": pw_c,
                            "n": pw_n,
                            "frac_convective": 0.7,
                        }
                        self.__thermal_mass += pw_thermal_mass

                        # Add it to the emitters list
                        self.__emitters.append(new_radiator)
                        number_of_elements += 1
        # Final initialisation checks:

        # Ensure total UFH area does not exceed zone area
        if total_emitter_floor_area > floor_area:
            raise ValueError(
                f"Total UFH area ({total_emitter_floor_area}) is bigger than Zone area ({floor_area})"
            )

        # Considering the big differences in the calculation for c, n type emitters (like Radiators and UFH)
        # and fancoils that use a implicit (manufacturer data driven) approach, the initial implementation
        # of several types of emitters does not allow for the mix of fancoils with other systems. This is
        # currently enforced through using flag_fancoil.
        # Ensure only one fancoil is defined and it is the sole emitter type
        if self.__flag_fancoil and number_of_elements > 1:
            raise ValueError(
                "Only one fancoil specification can be defined, and it must be the sole emitter type for the zone."
            )

    def add_temperature_diff_zero(self, emitter):
        """
        This function appends the product data with a row for delta_T = 0.0, if missing.
        At a delta_T = 0, the heat output is assumed to be equal to the fan power only
        """
        # Extract the fan speed data and fan power for the emitter
        fan_speed_data = emitter["fancoil_test_data"]["fan_speed_data"]
        fan_power_W = emitter["fancoil_test_data"]["fan_power_W"]

        # Check if temperature_diff 0.0 exists in the fan_speed_data
        if not any(item["temperature_diff"] == 0.0 for item in fan_speed_data):  # noqa: float-compare
            # If missing, create the new entry with power_output as fan_power_W / 1000
            power_output_zero = [fpw / units.W_per_kW for fpw in fan_power_W]
            new_entry = {"temperature_diff": 0.0, "power_output": power_output_zero}
            # Add the new entry to fan_speed_data
            fan_speed_data.append(new_entry)

        # Return the modified emitters data
        return emitter

    def temp_setpnt(self):
        return self.__heat_source.temp_setpnt()

    def in_required_period(self):
        return self.__heat_source.in_required_period()

    def frac_convective(self):
        if self.__flag_fancoil:
            return self.__fancoil["frac_convective"]

        # For other systems
        frac_convective = []  # list to store values of convective fraction for emitters.
        for emitter in self.__emitters:
            frac_convective.append(emitter["frac_convective"])

        # weighted average for each emitter
        power_total_weight = self.power_output_emitter_weight()

        frac_convective_weighted = math.fsum(
            [power_total_weight[i] * frac_convective[i] for i in range(len(frac_convective))]
        )
        return frac_convective_weighted

    def power_output_emitter_weight(self):
        """Weighted average of emitter power output"""
        # initialise
        T_rm = 20  # assumed internal air temperature
        power_total = 0
        power_emitter = 0
        power_total_list = []

        # flow and return temperatures
        flow_temp, return_temp = self.temp_flow_return()
        T_E = (flow_temp + return_temp) / 2

        if T_E > T_rm:
            # sum up power for all emitters
            for emitter in self.__emitters:
                power_emitter = emitter["c"] * (T_E - T_rm) ** emitter["n"]
                power_total += power_emitter
                power_total_list.append(power_emitter)

            power_total_weight = [power_emitter / power_total for power_emitter in power_total_list]

        else:
            # If there is no power output from any emitters at the assumed
            # temperature difference, apply equal weighting to all emitters
            power_total_weight = [1.0 / len(self.__emitters)] * len(self.__emitters)

        weight_sum = math.fsum(power_total_weight)
        if not math.isclose(weight_sum, 1.0, abs_tol=1e-6):
            # If this error is triggered, then there is probably an error in the code above
            raise RuntimeError(
                "ERROR: Sum of emitter weightings should equal 1.0, not " + str(weight_sum)
            )  # PRAGMA: nocover
        return power_total_weight

    def temp_flow_return(self):
        """Calculate flow and return temperature based on ecodesign control class"""
        if self.__ecodesign_control_class in (
            EcoDesignControllerClass.CLASS_II,
            EcoDesignControllerClass.CLASS_III,
            EcoDesignControllerClass.CLASS_VI,
            EcoDesignControllerClass.CLASS_VII,
        ):
            # A heater flow temperature control that varies the flow temperature of
            # water leaving the heat dependant upon prevailing outside temperature
            # and selected weather compensation curve.

            # They feature provision for manual adjustment of the weather
            # compensation curves and therby introduce a technical risk that optimal
            # minimised flow temperatures are not always achieved.

            # TODO Ecodesign class VI has additional benefits from the use of an
            # indoor temperature sensor to restrict boiler temperatures during
            # low heat demand but not during high demand.

            # use weather temperature at the timestep
            outside_temp = self.__external_conditions.air_temp()

            # Set outdoor and flow temp limits for weather compensation curve
            if outside_temp < self.__min_outdoor_temp:
                flow_temp = self.__max_flow_temp
            elif outside_temp > self.__max_outdoor_temp:
                flow_temp = self.__min_flow_temp
            else:
                # Interpolate
                # Note: A previous version used numpy interpolate, but this
                #       seemed to be giving incorrect results, so interpolation
                #       is implemented manually here.
                flow_temp = self.__min_flow_temp + (outside_temp - self.__max_outdoor_temp) * (
                    (self.__max_flow_temp - self.__min_flow_temp)
                    / (self.__min_outdoor_temp - self.__max_outdoor_temp)
                )

        elif self.__ecodesign_control_class in (
            EcoDesignControllerClass.CLASS_I,
            EcoDesignControllerClass.CLASS_IV,
            EcoDesignControllerClass.CLASS_V,
            EcoDesignControllerClass.CLASS_VIII,
        ):
            flow_temp = self.__design_flow_temp

        else:
            raise ValueError(
                f"Ecodesign control class ({self.__ecodesign_control_class}) not valid"
            )  # PRAGMA: nocover

        # Needed for initialisation (initial guess) of flow and return temperatures
        return_temp = convert_flow_to_return_temp(flow_temp)
        if flow_temp > 70.0 or math.isclose(flow_temp, 70.0):
            return_temp = 60.0

        return flow_temp, return_temp

    def power_output_emitter(self, temp_emitter, temp_rm):
        """Calculate emitter output at given emitter and room temp

        Power output from emitter (eqn from 2020 ASHRAE Handbook p644):
            power_output = c * (T_E - T_rm) ^ n
        where:
            T_E is mean emitter temperature
            T_rm is air temperature in the room/zone
            c and n are characteristic of the emitters (e.g. derived from BS EN 442 tests)
        """
        # initialise the total required power output
        power_total = 0
        # sum up power for all emitters
        for emitter in self.__emitters:
            power_total += emitter["c"] * max(0, (temp_emitter - temp_rm)) ** emitter["n"]
        return power_total

    def temp_emitter_req(self, power_emitter_req, temp_rm):
        """Calculate emitter temperature that gives required power output at given room temp

        Power output from emitter (eqn from 2020 ASHRAE Handbook p644):
            power_output = c * (T_E - T_rm) ^ n
        where:
            T_E is mean emitter temperature
            T_rm is air temperature in the room/zone
            c and n are characteristic of the emitters (e.g. derived from BS EN 442 tests)
        Rearrange to solve for T_E
        """

        # consider multiple emitters and solve for T_E iteratively
        def func_temp_emitter_req(T_E: np.typing.NDArray[float] | float):
            T_E_scalar = T_E.item() if hasattr(T_E, "item") else T_E
            return power_emitter_req - math.fsum(
                emitter["c"] * (T_E_scalar - temp_rm) ** emitter["n"] for emitter in self.__emitters
            )

        # solve for T_E using fsolve, temp_rm + 10 is inital guess for T_E
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("error", category=RuntimeWarning)
                temp_emitter_req = fsolve(
                    func_temp_emitter_req,
                    temp_rm + 10,
                )[0]
        except Exception as e:
            raise RuntimeError(
                f"{str(e)} - Module: {__name__}; Line: {sys._getframe().f_lineno}"
            ) from e
        return temp_emitter_req

    def __func_temp_emitter_change_rate(self, power_input):
        """Differential eqn for change rate of emitter temperature, to be solved iteratively

        Derivation:

        Heat balance equation for radiators:
            (T_E(t) - T_E(t-1)) * K_E / timestep = power_input - power_output
        where:
            T_E is mean emitter temperature
            K_E is thermal mass of emitters

        Power output from emitter (eqn from 2020 ASHRAE Handbook p644):
            power_output = c * (T_E(t) - T_rm) ^ n
        where:
            T_rm is air temperature in the room/zone
            c and n are characteristic of the emitters (e.g. derived from BS EN 442 tests)

        Substituting power output eqn into heat balance eqn gives:
            (T_E(t) - T_E(t-1)) * K_E / timestep = power_input - c * (T_E(t) - T_rm) ^ n

        Rearranging gives:
            (T_E(t) - T_E(t-1)) / timestep = (power_input - c * (T_E(t) - T_rm) ^ n) / K_E
        which gives the differential equation as timestep goes to zero:
            d(T_E)/dt = (power_input - c * (T_E - T_rm) ^ n) / K_E

        If T_rm is assumed to be constant over the time period, then the rate of
        change of T_E is the same as the rate of change of deltaT, where:
            deltaT = T_E - T_rm

        Therefore, the differential eqn can be expressed in terms of deltaT:
            d(deltaT)/dt = (power_input - c * deltaT(t) ^ n) / K_E

        This can be solved for deltaT over a specified time period using the
        solve_ivp function from scipy.
        """
        # Apply min value of zero to temp_diff because the power law does not
        # work for negative temperature difference
        # consider multiple emitters and solve for temp_diff iteratively
        return lambda t, temp_diff: (
            (
                power_input
                - math.fsum(
                    emitter["c"] * max(0, temp_diff[0]) ** emitter["n"]
                    for emitter in self.__emitters
                )
            )
            / self.__thermal_mass
        )

    def temp_emitter(
        self,
        time_start,
        time_end,
        temp_emitter_start,
        temp_rm,
        power_input,
        temp_emitter_max=None,
    ):
        """Calculate emitter temperature after specified time with specified power input"""
        # Calculate emitter temp at start of timestep
        temp_diff_start = temp_emitter_start - temp_rm

        if temp_emitter_max is not None:
            temp_diff_max = temp_emitter_max - temp_rm

            # Define event where emitter reaches max. temp (event occurs when func returns zero)
            def temp_diff_max_reached(t, y):
                return y[0] - temp_diff_max

            temp_diff_max_reached.terminal = True

            events = temp_diff_max_reached
        else:
            events = None

        # Get function representing change rate equation and solve iteratively
        func_temp_emitter_change_rate = self.__func_temp_emitter_change_rate(power_input)
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("error", category=RuntimeWarning)
                temp_diff_emitter_rm_results = solve_ivp(
                    func_temp_emitter_change_rate,
                    (time_start, time_end),
                    (temp_diff_start,),
                    events=events,
                )
        except Exception as e:
            raise RuntimeError(
                [str(e), "- Module:", __name__, "; Line:", sys._getframe().f_lineno]
            ) from e

        # Get time at which emitters reach max. temp
        time_temp_diff_max_reached = None
        if temp_emitter_max is not None:
            t_events = temp_diff_emitter_rm_results.t_events[0]
            if len(t_events) > 0:
                time_temp_diff_max_reached = temp_diff_emitter_rm_results.t_events[0][-1]

        # Get emitter temp at end of timestep
        temp_diff_emitter_rm_final = temp_diff_emitter_rm_results.y[0][-1]
        temp_emitter = temp_rm + temp_diff_emitter_rm_final
        return temp_emitter, time_temp_diff_max_reached

    def format_fancoil_manufacturer_data(self, fancoil_test_data):
        """
        Return the product data in two numpy array.
        power output in temperature_data
        fan_power_data
        """
        # Extract fan speed data and fan power
        fan_speed_data = fancoil_test_data["fan_speed_data"]
        fan_power_W = fancoil_test_data["fan_power_W"]

        # Create a list to hold rows of the new array
        rows = []

        # Add fan speed data rows
        for entry in fan_speed_data:
            row = [entry["temperature_diff"]] + [speed for speed in entry["power_output"]]
            rows.append(row)

        # Check all the fan speed lists are of the same length
        lists_length = all(len(i) == len(rows[0]) for i in rows)
        if not lists_length:
            raise ValueError("Fan speed lists of fancoil manufacturer data differ in length")

        # Prepare fan_power data
        fan_power_row = ["Fan power (W)"] + [power for power in fan_power_W]

        # Check if the length of fan power matches the number of power outputs
        if (
            len(fan_power_W) != len(rows[0]) - 1
        ):  # Subtract 1 because of the "temperature_diff" column
            raise ValueError("Fan power data length does not match the length of fan speed data.")

        # Convert to NumPy array
        temperature_data = np.array(rows)
        fan_power_data = np.array(fan_power_row)

        return temperature_data, fan_power_data

    def fancoil_output(
        self, delta_T_fancoil, temperature_data, fan_power_data, power_req_from_fan_coil
    ):
        """
        Calculate the power output (kW) from fan coil manufacturer data.
        For a given delta T, interpolate values for each fan speed column, and
        the maximum is calculated. The actual power output is the minimum between this maximum and
        the heat demanded.

        Parameters:
        delta_T_fancoil (float): temp dif between primary circuit water temp (average of flow and return temp)
        and room air temp.
        temperature_data (array): product data relating to temperature diff from manufacturer.
        fan_power_data (array): product data relating to fan power from manufacturer
        power_req_from_fan_coil (float): in kW.

        Returns:
        Tuple containing the actual power output, fan power and fraction of timestep running.

        """
        interpolated_outputs = []

        # First column in temperature data, delta T.
        delta_T_values = list(temperature_data[:, 0])
        delta_T_values = [float(i) for i in delta_T_values]

        fan_power_values = [float(i) for i in fan_power_data[1:]]

        # Parsing product data to get outputs and fan speeds.
        for col in range(1, temperature_data.shape[1]):
            output_values_for_fan_speed = list(
                temperature_data[:, col]
            )  # Output values column (fan speed), last row removed.
            output_values_for_fan_speed = [float(i) for i in output_values_for_fan_speed]
            delta_T_output_pairs = zip(delta_T_values, output_values_for_fan_speed, strict=False)
            unique_delta_T_output_pairs = list(
                set(delta_T_output_pairs)
            )  # Remove duplicate tuples.
            sorted_delta_T_output_pairs = sorted(
                unique_delta_T_output_pairs
            )  # Ensure output values are in increasing sequence.
            sorted_delta_T_values = [i for (i, j) in sorted_delta_T_output_pairs]
            sorted_output_values_for_fan_speed = [j for (i, j) in sorted_delta_T_output_pairs]

            # Find the min and max values from the output
            min_output_value = min(sorted_output_values_for_fan_speed)
            max_output_value = max(sorted_output_values_for_fan_speed)

            # TODO: Currently interpolation follows a linear equation. We think it can be improved with
            # an equation of the form output = c + a * deltaT ^ b that gives a good fit (where c is the fan power)

            # Interpolate value for the given delta T and fan speed output column
            interpolator = interp1d(
                sorted_delta_T_values,
                sorted_output_values_for_fan_speed,
                bounds_error=False,  # Do not raise an error for out-of-bounds values.
                fill_value=(
                    min_output_value,
                    max_output_value,
                ),  # Below range returns min, above range returns max.
                kind="linear",  # data is slightly non-linear, but non-linear fits can be unstable
            )

            # Get the interpolated (or bounded) value
            interpolated_output_value = float(interpolator(delta_T_fancoil))

            interpolated_outputs.append(interpolated_output_value)

        fancoil_max_output = max(interpolated_outputs)
        fancoil_min_output = min(interpolated_outputs)

        actual_output = min(power_req_from_fan_coil, fancoil_max_output)
        if fancoil_min_output == 0:
            fraction_timestep_running = 1
        else:
            fraction_timestep_running = min(1, actual_output / fancoil_min_output)

        # Interpolate/extrapolate fan power value for the actual output
        if actual_output < 0 or math.isclose(actual_output, 0.0, abs_tol=1e-10):
            fan_power_value = 0
            actual_output = 0
        else:
            interpolated_output_pairs = zip(interpolated_outputs, fan_power_values, strict=False)
            unique_interpolated_output_pairs = list(
                set(interpolated_output_pairs)
            )  # Remove duplicate tuples.
            sorted_interpolated_output_pairs = sorted(
                unique_interpolated_output_pairs
            )  # Ensure output values are in increasing sequence.
            sorted_interpolated_outputs = [i for (i, j) in sorted_interpolated_output_pairs]
            sorted_fan_power_values = [j for (i, j) in sorted_interpolated_output_pairs]

            # Find the min and max fan power values
            min_fan_power_value = min(sorted_fan_power_values)
            max_fan_power_value = max(sorted_fan_power_values)

            # TODO: Currently interpolation follows a linear equation. We think it can be improved with
            # an equation of form to be determined that gives a better fit

            # Interpolate fan power without extrapolation
            interpolator = interp1d(
                sorted_interpolated_outputs,
                sorted_fan_power_values,
                bounds_error=False,  # Allow out-of-bounds inputs without raising an error
                fill_value=(
                    min_fan_power_value,
                    max_fan_power_value,
                ),  # Below range returns min, above range returns max
                kind="linear",  # data is slightly non-linear, but non-linear fits can be unstable
            )

            fan_power_value = float(interpolator(actual_output))

        return actual_output, fan_power_value, fraction_timestep_running

    def __energy_required_from_heat_source(
        self,
        energy_demand_heating_period,
        time_heating_start,
        timestep,
        temp_rm_prev,
        temp_emitter_heating_start,
        temp_emitter_req,
        temp_emitter_max,
        temp_return,
        temp_flow_target: float,
    ):
        # When there is some demand, calculate max. emitter temperature
        # achievable and emitter temperature required, and base calculation
        # on the lower of the two.

        # Calculate extra energy required for emitters to reach temp required
        if self.__flag_fancoil:
            energy_req_to_warm_emitters = 0.0
        else:
            energy_req_to_warm_emitters = self.__thermal_mass * (
                temp_emitter_req - temp_emitter_heating_start
            )

        # Calculate energy input required to meet energy demand
        energy_req_from_heat_source = max(
            energy_req_to_warm_emitters + energy_demand_heating_period, 0.0
        )
        # potential demand from buffer tank

        energy_req_from_buffer_tank = energy_req_from_heat_source

        # === Limit energy to account for maximum emitter temperature ===
        emitters_data_for_buffer_tank = None

        if (
            self.__flag_fancoil
            or temp_emitter_heating_start < temp_emitter_max
            or math.isclose(temp_emitter_heating_start, temp_emitter_max, abs_tol=1e-10)
        ):
            # If emitters are below max. temp for this timestep, then max energy
            # required from heat source will depend on maximum warm-up rate,
            # which depends on the maximum energy output from the heat source
            if self.__with_buffer_tank:
                # Call to HeatSourceServiceSpace with buffer_tank relevant data
                if (timestep - time_heating_start) < 0.0 or math.isclose(
                    timestep, time_heating_start
                ):
                    # If there is no time remaining in the timestep, then there
                    # is no power requirement (and we need to avoid div-by-zero)
                    power_req_from_buffer_tank = 0.0
                else:
                    power_req_from_buffer_tank = energy_req_from_buffer_tank / (
                        timestep - time_heating_start
                    )
                emitters_data_for_buffer_tank = {
                    "temp_emitter_req": temp_emitter_req,
                    "power_req_from_buffer_tank": power_req_from_buffer_tank,
                    "design_flow_temp": self.__design_flow_temp,
                    "target_flow_temp": temp_flow_target,
                    "temp_rm_prev": temp_rm_prev,
                    "variable_flow": self.__variable_flow,
                    "min_flow_rate": self.__min_flow_rate,
                    "max_flow_rate": self.__max_flow_rate,
                    "temp_diff_emit_dsgn": self.__temp_diff_emit_dsgn,
                }

                energy_provided_by_heat_source_max_min, emitters_data_for_buffer_tank = (
                    self.__heat_source.energy_output_max(
                        temp_flow_target,
                        temp_return,
                        time_start=time_heating_start,
                        emitters_data_for_buffer_tank=emitters_data_for_buffer_tank,
                    )
                )
            else:
                energy_provided_by_heat_source_max_min = self.__heat_source.energy_output_max(
                    temp_flow_target,
                    temp_return,
                    time_start=time_heating_start,
                )
        else:
            # If emitters are already above max. temp for this timestep,
            # then heat source should provide no energy until emitter temp
            # falls to maximum
            energy_provided_by_heat_source_max_min = 0.0

        if self.__flag_fancoil:
            energy_req_from_heat_source_max = energy_req_from_heat_source
            temp_emitter_max_is_final_temp = True
        else:  # Radiators and/or UFH
            # Calculate time to reach max. emitter temp at max heat source output
            power_output_max_min = energy_provided_by_heat_source_max_min / timestep
            temp_emitter, time_temp_emitter_max_reached = self.temp_emitter(
                time_heating_start,
                timestep,
                temp_emitter_heating_start,
                temp_rm_prev,
                power_output_max_min,
                temp_emitter_max,
            )
            if time_temp_emitter_max_reached is None:
                time_in_warmup_cooldown_phase = timestep - time_heating_start
                temp_emitter_max_reached = False
            else:
                time_in_warmup_cooldown_phase = time_temp_emitter_max_reached - time_heating_start
                temp_emitter_max_reached = True

            # Before this time, energy output from heat source is maximum
            energy_req_from_heat_source_before_temp_emitter_max_reached = (
                power_output_max_min * time_in_warmup_cooldown_phase
            )

            # After this time, energy output is amount needed to maintain
            # emitter temp (based on emitter output at constant emitter temp)
            # Note: the time at steady state in the equation below is the time
            #       remaining after the heating start and warmup/cooldown period
            #       and equals either:
            #       - zero, when time_temp_emitter_max_reached is None
            #       - (timestep - time_temp_emitter_max_reached), for other cases
            energy_req_from_heat_source_after_temp_emitter_max_reached = self.power_output_emitter(
                temp_emitter, temp_rm_prev
            ) * (timestep - time_heating_start - time_in_warmup_cooldown_phase)

            # Total energy input req from heat source is therefore sum of energy
            # output required before and after max emitter temp reached
            energy_req_from_heat_source_max = (
                energy_req_from_heat_source_before_temp_emitter_max_reached
                + energy_req_from_heat_source_after_temp_emitter_max_reached
            )

            if temp_emitter_max_reached and temp_emitter_req > temp_emitter_max:
                temp_emitter_max_is_final_temp = True
            else:
                temp_emitter_max_is_final_temp = False

        # Total energy input req from heat source is therefore lower of:
        # - energy output required to meet space heating demand
        # - energy output when emitters reach maximum temperature
        return (
            min(energy_req_from_heat_source, energy_req_from_heat_source_max),
            temp_emitter_max_is_final_temp,
            emitters_data_for_buffer_tank,
        )

    def __energy_surplus_during_cooldown(
        self, time_cooldown, timestep, energy_demand, temp_rm_prev
    ):
        # Handle "DeprecationWarning: Conversion of an array with ndim > 0 to a
        # scalar is deprecated, and will error in future. Ensure you extract a
        # single element from your array before performing this operation.
        # (Deprecated NumPy 1.25.)". The fsolve function which calls this one
        # iteratively seems to provide the iterated argument as a single-element
        # ndarray, which seems to trigger an incompatibility with the underlying
        # numpy functions.
        if isinstance(time_cooldown, ndarray) and len(time_cooldown) == 1:
            time_cooldown = time_cooldown[0]

        # Calculate emitter temperature after specified time with no heat input
        temp_emitter_no_heat_input, _ = self.temp_emitter(
            0.0,
            time_cooldown,
            self.__temp_emitter_prev,
            temp_rm_prev,
            0.0,  # No heat from heat source during initial cool-down
        )
        energy_released_from_emitters = self.__thermal_mass * (
            self.__temp_emitter_prev - temp_emitter_no_heat_input
        )
        energy_demand_cooldown = energy_demand * time_cooldown / timestep

        return energy_released_from_emitters - energy_demand_cooldown

    def __calc_emitter_cooldown(self, energy_demand, temp_emitter_req, temp_rm_prev, timestep):
        """Calculate emitter cooling time and emitter temperature at this time"""
        if self.__temp_emitter_prev < temp_emitter_req:
            # If emitters are below target temperature, then heat source starts
            # from start of timestep
            time_heating_start = 0.0
            temp_emitter_heating_start = self.__temp_emitter_prev
        else:
            # Calculate time that emitters are cooling down (accounting for
            # undershoot), during which the heat source does not provide any
            # heat, by iterating to find the end time which leads to the heat
            # output matching the energy demand accumulated so far during the
            # timestep
            # TODO Is there a more efficient way to do this than iterating?
            with warnings.catch_warnings():
                warnings.filterwarnings("error", category=RuntimeWarning)
                # The starting guess below is the end of the timestep rather
                # than the start because at the start of the timestep the
                # function being solved will effectively be 0 minus 0, which
                # is not the result we are seeking (unless no other exists)
                result = root(
                    self.__energy_surplus_during_cooldown,
                    timestep,  # Starting guess: end of timestep
                    (timestep, energy_demand, temp_rm_prev),
                    tol=1e-8,  # Required to avoid oversensitivty causing failure to solve
                )
                time_cooldown = result.x[0]

            # Limit cooldown time to be within timestep
            time_heating_start = max(0.0, min(time_cooldown, timestep))
            # Calculate emitter temperature at heating start time
            temp_emitter_heating_start, _ = self.temp_emitter(
                0.0,
                time_heating_start,
                self.__temp_emitter_prev,
                temp_rm_prev,
                0.0,  # No heat from heat source during initial cool-down
            )
        return time_heating_start, temp_emitter_heating_start

    def demand_energy_flow_return(
        self,
        energy_demand,
        temp_flow_target,
        temp_return_target,
        update_heat_source_state=True,
        update_temp_emitter_prev=True,
        blended_temp_flow=None,
    ):
        """Demand energy from emitters and calculate how much energy can be provided.
            This function is called in a loop inside each timestep, where the return temp
            is recalculated in each iteration.

        Arguments:
        energy_demand -- in kWh
        temp_flow_target -- flow temp in C
        temp_return_target -- return temp in C
        update_heat_source_state -- if False, when heat_source.demand_energy is called,
                                    the heat source state does not change.
        update_temp_emitter_prev -- if False, the emitter temperature is not
                                     saved for next timestep.
        blended_temp_flow -- temp when there is bypass recirculated water.
                            If no recirculated water, the it will be equal to the flow temp.
        """
        timestep = self.__simtime.timestep()
        temp_rm_prev = self.__zone.temp_internal_air()

        # Calculate target flow and return temperature
        temp_emitter_max = (temp_flow_target + temp_return_target) / 2.0
        if blended_temp_flow:
            temp_emitter_max = (blended_temp_flow + temp_return_target) / 2.0

        # Calculate emitter temperature required
        power_emitter_req = energy_demand / timestep
        if self.__flag_fancoil:
            temp_emitter_req = temp_emitter_max
        else:
            temp_emitter_req = self.temp_emitter_req(power_emitter_req, temp_rm_prev)

        emitters_data_for_buffer_tank = None

        if energy_demand < 0 or math.isclose(energy_demand, 0.0, abs_tol=1e-10):
            # Emitters (radiators and ufh) cooling down or (also for fancoils) at steady-state with heating off
            time_heating_start = 0.0
            temp_emitter_heating_start = self.__temp_emitter_prev
            energy_req_from_heat_source = 0.0
            temp_emitter_max_is_final_temp = False

            fan_energy_kWh = 0
            if self.__flag_fancoil:
                temp_emitter = "n/a"
        else:
            if self.__flag_fancoil:
                delta_T_fancoil = temp_emitter_max - temp_rm_prev
                temp_emitter = "n/a"

                # Removing pipework internal distribution losses in space from energy demand to be delivered by fancoil
                pw_heat_loss = 0.0
                for pipework in self.__pipework_list:
                    pw_heat_loss += (
                        pipework.calculate_steady_state_heat_loss(temp_flow_target, temp_rm_prev)
                        * timestep
                        / units.W_per_kW
                    )
                energy_demand -= pw_heat_loss

                power_req_from_fan_coil = energy_demand / self.__fancoil["n_units"] / timestep
                power_delivered_by_fancoil, fan_power_single_unit, fraction_timestep_running = (
                    self.fancoil_output(
                        delta_T_fancoil,
                        self.__fancoil["temperature_data"],
                        self.__fancoil["fan_power_data"],
                        power_req_from_fan_coil,
                    )
                )
                # Adding back pipework internal distribution losses to power required from heat source
                power_req_from_heat_source = (
                    power_delivered_by_fancoil - fan_power_single_unit
                ) * self.__fancoil["n_units"] + pw_heat_loss / timestep
                fan_power = fan_power_single_unit * self.__fancoil["n_units"]
                energy_demand = (power_req_from_heat_source + fan_power) * timestep
                fan_energy_kWh = fan_power / units.W_per_kW * timestep * fraction_timestep_running
                if update_heat_source_state:
                    self.__energy_supply_fan_coil_conn.demand_energy(fan_energy_kWh)

                # Emitters (fancoils) don't have a warming up or cooling down period:
                time_heating_start = 0.0
                temp_emitter_heating_start = self.__temp_emitter_prev
            else:
                fan_energy_kWh = 0
                # Emitters (radiators and ufh) warming up or cooling down to a target temperature:
                # - First we calculate the time taken for the emitters to cool
                #   before the heating system activates, and the temperature that
                #   the emitters reach at this time. Note that the emitters will
                #   cool to below the target temperature so that the total heat
                #   output in this cooling period matches the demand accumulated so
                #   far in the timestep (assumed to be proportional to the fraction
                #   of the timestep that has elapsed)
                time_heating_start, temp_emitter_heating_start = self.__calc_emitter_cooldown(
                    energy_demand, temp_emitter_req, temp_rm_prev, timestep
                )

            #   Then, we calculate the energy required from the heat source in
            #   the remaining part of the timestep - (full timestep for fancoils)
            (
                energy_req_from_heat_source,
                temp_emitter_max_is_final_temp,
                emitters_data_for_buffer_tank,
            ) = self.__energy_required_from_heat_source(
                (energy_demand - fan_energy_kWh) * (1.0 - time_heating_start / timestep),
                time_heating_start,
                timestep,
                temp_rm_prev,
                temp_emitter_heating_start,
                temp_emitter_req,
                temp_emitter_max,
                temp_return_target,
                temp_flow_target,
            )

        # Get energy output of heat source (i.e. energy input to emitters)
        # TODO Instead of passing temp_flow_req into heating system module,
        #      calculate average flow temp achieved across timestep?

        # Catering for the possibility of a BufferTank in the emitters' loop
        if self.__with_buffer_tank:
            # Call to HeatSourceServiceSpace with buffer_tank relevant data
            energy_provided_by_heat_source = self.__heat_source.demand_energy(
                energy_req_from_heat_source,
                temp_flow_target,
                temp_return_target,
                time_start=time_heating_start,
                emitters_data_for_buffer_tank=emitters_data_for_buffer_tank,
                update_heat_source_state=update_heat_source_state,
            )
        else:
            energy_provided_by_heat_source = self.__heat_source.demand_energy(
                energy_req_from_heat_source,
                temp_flow_target,
                temp_return_target,
                time_start=time_heating_start,
                update_heat_source_state=update_heat_source_state,
            )

        if self.__flag_fancoil:
            energy_released_from_emitters = energy_provided_by_heat_source + fan_energy_kWh
        else:
            # Calculate emitter temperature achieved at end of timestep.
            # Do not allow emitter temp to rise above maximum
            # Do not allow emitter temp to fall below room temp
            if temp_emitter_max_is_final_temp:
                temp_emitter = temp_emitter_max
            else:
                power_provided_by_heat_source = energy_provided_by_heat_source / (
                    timestep - time_heating_start
                )
                temp_emitter, time_temp_target_reached = self.temp_emitter(
                    time_heating_start,
                    timestep,
                    temp_emitter_heating_start,
                    temp_rm_prev,
                    power_provided_by_heat_source,
                    temp_emitter_req,
                )
                # If target emitter temperature is reached on warm-up, assume that
                # this is maintained to the end of the timestep. This accounts for
                # overshoot and stabilisation without having to model it explicitly
                if (
                    temp_emitter_heating_start < temp_emitter_req
                    and time_temp_target_reached is not None
                ):
                    temp_emitter = temp_emitter_req
            temp_emitter = max(temp_emitter, temp_rm_prev)

            # Calculate emitter output achieved at end of timestep.
            energy_released_from_emitters = energy_provided_by_heat_source + self.__thermal_mass * (
                self.__temp_emitter_prev - temp_emitter
            )

            # Save emitter temperature for next timestep
            if update_temp_emitter_prev:
                self.__temp_emitter_prev = temp_emitter

        # If detailed results flag is set populate dict with values
        if self.__output_detailed_results and update_heat_source_state:
            dr_list = OutputEmitters(
                simulation_time_idx=self.__simtime.index(),
                energy_demand=energy_demand,
                temp_emitter_required=temp_emitter_req,
                time_heating_start=time_heating_start,
                energy_provided_by_heat_source=energy_provided_by_heat_source,
                temp_emitter=temp_emitter,
                temp_emitter_max=temp_emitter_max,
                energy_released_from_emitters=energy_released_from_emitters,
                temp_flow_target=temp_flow_target,
                temp_return_target=temp_return_target,
                temp_emitter_max_is_final_temp=temp_emitter_max_is_final_temp,
                energy_required_from_heat_source=energy_req_from_heat_source,
                fan_energy_kWh=fan_energy_kWh,
            )

            self.__emitters_detailed_results[self.__simtime.index()] = dr_list

        return energy_released_from_emitters, energy_req_from_heat_source

    def demand_energy(self, energy_demand):
        """Energy released from emitters after doing a previous loop
        that updates the return temperature.
        """

        # ecodesign controls to determine flow temperature,
        # and 6/7th rule to calculate the initial return temperature
        temp_flow_target, temp_return_target = self.temp_flow_return()

        temp_return_target, blended_temp_flow, flow_rate_m3s = self.return_temp_from_flow_rate(
            energy_demand, temp_flow_target, temp_return_target
        )

        # Last call to demand_energy_flow_return that updates the heat source state and other internal variables
        # before going to the next timestep.
        energy_released_from_emitters, __ = self.demand_energy_flow_return(
            energy_demand,
            temp_flow_target,
            temp_return_target,
            update_heat_source_state=True,
            update_temp_emitter_prev=True,
            blended_temp_flow=blended_temp_flow,
        )

        return energy_released_from_emitters

    def return_temp_from_flow_rate(self, energy_demand, temp_flow_target, temp_return_target):
        """Calculate the return temperature for a given flow temp.
        If, for a given design delta T, the corresponding flow rate is in
        the allowed range, then the return temp is given directly.
        If the flow rate is out of the allowed range or the flow rate is fixed,
        (no change with timesteps) then the return temp is calculated by iteration.
        If there is bypass recirculated water the blended temperature is returned too.

        Arguments:
        energy_demand -- in kWh
        temp_flow_target -- flow temp in C
        temp_return_target -- return temp in C
        """
        update_heat_source_state = False  # heat source state not updated.
        update_temp_emitter_prev = False  # emitter temperature is not updated for next time step.
        specific_heat_capacity = WATER.specific_heat_capacity() / units.J_per_kJ
        density = WATER.density() * units.litres_per_cubic_metre

        # The heat source can modulate the flow rate.
        if self.__variable_flow:
            # The return temperature is calculated from temp_diff_emit_dsgn (not the 6/7th rule).
            temp_return_target = temp_flow_target - self.__temp_diff_emit_dsgn
            energy_released_from_emitters, energy_required_from_heat_source = (
                self.demand_energy_flow_return(
                    energy_demand,
                    temp_flow_target,
                    temp_return_target,
                    update_heat_source_state,
                    update_temp_emitter_prev,
                )
            )
            if (
                energy_released_from_emitters < 0
                or energy_required_from_heat_source < 0
                or math.isclose(energy_required_from_heat_source, 0.0, abs_tol=1e-10)
            ):
                temp_return_target = temp_flow_target
                blended_temp_flow_target = temp_flow_target
                flow_rate_m3s = 0.0
                return temp_return_target, blended_temp_flow_target, flow_rate_m3s
            else:
                # The flow rate is calculated from energy_released_from_emitters and delta T.
                power_released_from_emitters = (
                    energy_released_from_emitters / self.__simtime.timestep()
                )
                flow_rate_m3s = power_released_from_emitters / (
                    specific_heat_capacity * density * self.__temp_diff_emit_dsgn
                )  # m3/s
                flow_rate = flow_rate_m3s * units.litres_per_cubic_metre  # l/s

                flow_rate_in_range = True
                if flow_rate < self.__min_flow_rate:
                    flow_rate = self.__min_flow_rate  # l/s
                    flow_rate_in_range = False

                elif flow_rate > self.__max_flow_rate:
                    flow_rate = self.__max_flow_rate  # l/s
                    flow_rate_in_range = False

                flow_rate_m3s = flow_rate / units.litres_per_cubic_metre  # m3/s
                if (
                    flow_rate_in_range
                ):  # The heat source can operate at this flow rate, so no need of loop.
                    # If there is bypass recirculated water, blended temp is calculated and return temp reduced accordingly.
                    blended_temp_flow_target = self.blended_temp(
                        temp_flow_target, temp_return_target, self.__bypass_fraction_recirculated
                    )
                    temp_return_target = temp_return_target - abs(
                        blended_temp_flow_target - temp_flow_target
                    )
                    return temp_return_target, blended_temp_flow_target, flow_rate_m3s

        else:
            energy_released_from_emitters, energy_required_from_heat_source = (
                self.demand_energy_flow_return(
                    energy_demand,
                    temp_flow_target,
                    temp_return_target,
                    update_heat_source_state,
                    update_temp_emitter_prev,
                )
            )
            if energy_required_from_heat_source < 0 or math.isclose(
                energy_required_from_heat_source, 0.0, abs_tol=1e-10
            ):
                # There is no flow when heat source is not required.
                temp_return_target = temp_flow_target
                blended_temp_flow_target = temp_flow_target
                flow_rate_m3s = 0.0
                return temp_return_target, blended_temp_flow_target, flow_rate_m3s
            else:
                flow_rate_m3s = self.__design_flow_rate / units.litres_per_cubic_metre

        # Loop when the flow rate is constant (design_flow_rate). The initial return temp is the 6/7th rule.
        # Also, for the case of variable flow rate with flow rate out of the allowed range.
        # In this case the initial return temp is calculated from the temp_diff_emit_dsgn.
        temp_return_target = self.update_return_temp(
            energy_demand,
            temp_flow_target,
            temp_return_target,
            specific_heat_capacity,
            density,
            flow_rate_m3s,
            update_heat_source_state,
            update_temp_emitter_prev,
        )

        # If there is bypass recirculated water, blended temp is calculated and return temp reduced accordingly.
        blended_temp_flow_target = self.blended_temp(
            temp_flow_target, temp_return_target, self.__bypass_fraction_recirculated
        )
        temp_return_target = temp_return_target - abs(blended_temp_flow_target - temp_flow_target)

        if self.__bypass_fraction_recirculated > 0:
            # Loop again but this time using blended temp and initial reduced return temp.
            temp_return_target = self.update_return_temp(
                energy_demand,
                blended_temp_flow_target,
                temp_return_target,
                specific_heat_capacity,
                density,
                flow_rate_m3s,
                update_heat_source_state,
                update_temp_emitter_prev,
            )

        return temp_return_target, blended_temp_flow_target, flow_rate_m3s

    def blended_temp(self, temp_flow_target, temp_return_target, bypass_fraction_recirculated):
        """When there is bypass recirculated water, the blended temperature is calculated following
        the formula of final temperature of the water mixture T(final)=(m1*T1+m2*T2)/(m1+m2)
        """
        return (
            1 - bypass_fraction_recirculated
        ) * temp_flow_target + bypass_fraction_recirculated * temp_return_target

    def update_return_temp(
        self,
        energy_demand,
        temp_flow_target,
        temp_return_target,
        specific_heat_capacity,
        density,
        flow_rate_m3s,
        update_heat_source_state,
        update_temp_emitter_prev,
    ):
        """
        Calculate the return temperature for a given flow temperature using fsolve.

        Arguments:
        energy_demand -- in kWh
        temp_flow_target -- flow temp in C
        temp_return_target -- initial guess for the return temperature.
        specific_heat_capacity -- water specific heat capacity (kJ/KgC)
        density -- water density (kg/m3)
        flow_rate_m3s -- flow rate (m3/s)
        update_heat_source_state --  if False then heat source state not updated.
        update_temp_emitter_prev --  if False then emitter temperature is not updated for next time step.
        """

        def energy_difference(temp_return):
            energy_released_from_emitters, __ = self.demand_energy_flow_return(
                energy_demand,
                temp_flow_target,
                temp_return[0],  # Pass scalar value to avoid array depth issue
                update_heat_source_state,
                update_temp_emitter_prev,
            )
            power_released_from_emitters = energy_released_from_emitters / self.__simtime.timestep()
            calculated_power = (
                specific_heat_capacity
                * density
                * flow_rate_m3s
                * (temp_flow_target - temp_return[0])
            )

            # Should be zero at the correct temp_return
            diff = power_released_from_emitters - calculated_power

            if math.isclose(diff, 0, abs_tol=1e-6):
                return 0

            return diff

        if energy_difference([temp_flow_target]) < 0:
            return temp_flow_target  # PRAGMA: nocover

        # Use bisect to find the return temperature that makes energy_difference zero
        temp_return_target = bisect(
            lambda t: energy_difference([t]), 0, temp_flow_target, xtol=1e-6
        )

        if (
            temp_return_target > temp_flow_target
        ):  # This happens when energy_released_from_emitters < 0
            temp_return_target = temp_flow_target  # PRAGMA: nocover

        return temp_return_target

    # TODO: the changes required to this function should be much the same as the ones
    #       that were made to the demand_energy function and demand_energy_flow_return.
    # def running_time_throughput_factor(
    #         self,
    #         energy_demand,
    #         space_heat_running_time_cumulative,
    #         ):
    #     """ Return the cumulative running time and throughput factor for the heat source
    #
    #     Arguments:
    #     energy_demand -- in kWh
    #     space_heat_running_time_cumulative
    #         -- running time spent on higher-priority space heating services
    #     """
    #     timestep = self.__simtime.timestep()
    #     temp_rm_prev = self.__zone.temp_internal_air()
    #
    #     # Calculate target flow and return temperature
    #     temp_flow_target, temp_return_target = self.temp_flow_return()
    #     temp_emitter_max = (temp_flow_target + temp_return_target) / 2.0
    #
    #     # Calculate emitter temperature required
    #     power_emitter_req = energy_demand / timestep
    #     temp_emitter_req = self.temp_emitter_req(power_emitter_req, temp_rm_prev)
    #
    #     if energy_demand < 0 or math.isclose(energy_demand, 0.0, abs_tol=1e-10):
    #         # Emitters cooling down or at steady-state with heating off
    #         time_heating_start = 0.0
    #         temp_emitter_heating_start = self.__temp_emitter_prev
    #         energy_req_from_heat_source = 0.0
    #     else:
    #         # Emitters warming up or cooling down to a target temperature:
    #         # - First we calculate the time taken for the emitters to cool
    #         #   before the heating system activates, and the temperature that
    #         #   the emitters reach at this time. Note that the emitters will
    #         #   cool to below the target temperature so that the total heat
    #         #   output in this cooling period matches the demand accumulated so
    #         #   far in the timestep (assumed to be proportional to the fraction
    #         #   of the timestep that has elapsed)
    #         # - Then, we calculate the energy required from the heat source in
    #         #   the remaining part of the timestep
    #         time_heating_start, temp_emitter_heating_start \
    #             = self.__calc_emitter_cooldown(energy_demand, temp_emitter_req, temp_rm_prev, timestep)
    #         energy_req_from_heat_source, _, _ \
    #             = self.__energy_required_from_heat_source(
    #                 energy_demand * (1.0 - time_heating_start / timestep),
    #                 time_heating_start,
    #                 timestep,
    #                 temp_rm_prev,
    #                 temp_emitter_heating_start,
    #                 temp_emitter_req,
    #                 temp_emitter_max,
    #                 temp_return_target,
    #                 )
    #     return self.__heat_source.running_time_throughput_factor(
    #         space_heat_running_time_cumulative,
    #         energy_req_from_heat_source,
    #         temp_flow_target,
    #         temp_return_target,
    #         time_heating_start,
    #         )

    def output_emitter_results(self):
        """Return the data dictionary containing detailed emitter results"""
        return self.__emitters_detailed_results

    def energy_output_min(self):
        """Calculate minimum possible energy output"""
        if self.__flag_fancoil:
            energy_released_from_emitters = 0
        else:  # radiators and/or ufh
            timestep = self.__simtime.timestep()
            temp_rm_prev = self.__zone.temp_internal_air()

            temp_emitter, _ = self.temp_emitter(
                0.0,
                timestep,
                self.__temp_emitter_prev,
                temp_rm_prev,
                0.0,  # No energy input to emitters from heat source
            )
            temp_emitter = max(temp_emitter, temp_rm_prev)

            # Calculate emitter output achieved at end of timestep.
            energy_released_from_emitters = self.__thermal_mass * (
                self.__temp_emitter_prev - temp_emitter
            )
        return energy_released_from_emitters
