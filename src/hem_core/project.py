#!/usr/bin/env python3

"""
This module provides the high-level control flow for the core calculation, and
initialises the relevant objects in the core model.
"""

# Standard library imports
import importlib.metadata
import logging
import sys
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timedelta
from math import ceil, fsum, isclose
from pathlib import Path

# Third-party imports
import numpy as np

# Local imports
import hem_core.heating_systems.wwhrs as wwhrs_module
import hem_core.input_output.enums as enums
import hem_core.units as units
from hem_core.controls.time_control import (
    ChargeControl,
    CombinationTimeControl,
    OnOffCostMinimisingTimeControl,
    OnOffTimeControl,
    SetpointTimeControl,
    SmartApplianceControl,
)
from hem_core.cooling_systems.air_conditioning import AirConditioning, SpaceCoolSystemBase
from hem_core.energy_supply.elec_battery import ElectricBattery
from hem_core.energy_supply.energy_supply import EnergySupply
from hem_core.energy_supply.inverter import Inverter
from hem_core.energy_supply.pv import OnSiteGenerationBase, PhotovoltaicPanel, PhotovoltaicSystem
from hem_core.external_conditions import create_external_conditions
from hem_core.heating_systems.boiler import Boiler
from hem_core.heating_systems.elec_storage_heater import ElecStorageHeater
from hem_core.heating_systems.emitters import Emitters, WetEmitterType
from hem_core.heating_systems.enums import SourceType
from hem_core.heating_systems.heat_battery_drycore import HeatBatteryDryCore
from hem_core.heating_systems.heat_battery_pcm import HeatBatteryPCM
from hem_core.heating_systems.heat_network import HeatNetwork
from hem_core.heating_systems.heat_pump import HeatPump, HeatPump_HWOnly, HeatPumpEmitterType
from hem_core.heating_systems.instant_elec_heater import InstantElecHeater
from hem_core.heating_systems.point_of_use import PointOfUse
from hem_core.heating_systems.storage_tank import (
    ImmersionHeater,
    PVDiverter,
    SmartHotWaterTank,
    SolarThermalSystem,
    StorageTank,
)
from hem_core.input_output.input import Input
from hem_core.input_output.output import (
    Output,
    OutputCOP,
    OutputCore,
    OutputHeatingCoolingSystem,
    OutputHotWaterSystems,
    OutputMetadata,
    OutputStatic,
    OutputSummary,
    OutputSummaryEnergySupply,
    OutputSummaryPeakElectricityConsumption,
    OutputZoneData,
)
from hem_core.material_properties import WATER
from hem_core.schedule import expand_events, expand_schedule
from hem_core.simulation_time import SimulationTime, create_simulation_time
from hem_core.space_heat_demand.building_element import (
    H_CE,
    H_RE,
    PITCH_LIMIT_HORIZ_CEILING,
    PITCH_LIMIT_HORIZ_FLOOR,
    R_SI_DOWNWARDS,
    R_SI_HORIZONTAL,
    R_SI_UPWARDS,
    BuildingElement,
    BuildingElementAdjacentConditionedSpace,
    BuildingElementAdjacentUnconditionedSpace_Simple,
    BuildingElementGround,
    BuildingElementOpaque,
    BuildingElementPartyWall,
    BuildingElementTransparent,
    calculate_cavity_resistance,
)
from hem_core.space_heat_demand.internal_gains import (
    ApplianceGains,
    EventApplianceGains,
    InternalGains,
)
from hem_core.space_heat_demand.thermal_bridge import ThermalBridgeLinear, ThermalBridgePoint
from hem_core.space_heat_demand.ventilation import create_infiltration_ventilation
from hem_core.space_heat_demand.zone import Zone, calc_vent_heat_transfer_coeff
from hem_core.units import Kelvin2Celcius
from hem_core.water_heat_demand.cold_water_source import ColdWaterSource
from hem_core.water_heat_demand.dhw_demand import ELECTRIC_SHOWERS_HWS_NAME, DHWDemand

from .input_dependency_resolvers import (
    build_preheated_water_source_dependency_graph,
    topological_sort_preheated_water_sources,
)

logger = logging.getLogger(__name__)

# Constants
# Set heating setpoint to absolute zero to ensure no heating demand
temp_setpnt_heat_none = Kelvin2Celcius(0.0)
# Set cooling setpoint to Planck temperature to ensure no cooling demand
temp_setpnt_cool_none = Kelvin2Celcius(1.4e32)


def progress_bar(t_idx, total_steps):
    bar_length = 40  # Length of the progress bar in characters
    percentage = (t_idx + 1) / total_steps * 100
    filled_length = int(bar_length * percentage // 100)
    bar = "█" * filled_length + "-" * (bar_length - filled_length)

    # Display the progress bar and the timesteps completed vs total
    sys.stdout.write(
        f"\rProgress: |{bar}| {percentage:.2f}% Complete - Timesteps completed: {t_idx + 1} / {total_steps}"
    )
    sys.stdout.flush()


def dict_to_ctrl(name: str, data: dict, simtime: SimulationTime, extcond, data_control: dict):
    """Parse dictionary of control data and return appropriate control object"""
    ctrl_type = data["type"]
    if ctrl_type == enums.TimeControlType.ON_OFF_TIME:
        nullable = data["allow_null"] if "allow_null" in data.keys() else False
        sched = expand_schedule(bool, data["schedule"], "main", nullable)
        ctrl = OnOffTimeControl(
            schedule=sched,
            simulation_time=simtime,
            start_day=data["start_day"],
            time_series_step=data["time_series_step"],
        )
    elif ctrl_type == enums.TimeControlType.SETPOINT_TIME:
        sched = expand_schedule(float, data["schedule"], "main", True)

        setpoint_min = None
        setpoint_max = None
        default_to_max = None
        advanced_start = 0.0
        if "setpoint_min" in data:
            setpoint_min = data["setpoint_min"]
        if "setpoint_max" in data:
            setpoint_max = data["setpoint_max"]
        if "default_to_max" in data:
            default_to_max = data["default_to_max"]
        if "advanced_start" in data:
            advanced_start = data["advanced_start"]

        ctrl = SetpointTimeControl(
            schedule=sched,
            simulation_time=simtime,
            start_day=data["start_day"],
            time_series_step=data["time_series_step"],
            setpoint_min=setpoint_min,
            setpoint_max=setpoint_max,
            default_to_max=default_to_max,
            duration_advanced_start=advanced_start,
        )
    elif ctrl_type == enums.TimeControlType.CHARGE:
        sched = expand_schedule(bool, data["schedule"], "main", False)
        if "temp_charge_cut_delta" in data:
            temp_charge_cut_delta = expand_schedule(
                float, data["temp_charge_cut_delta"], "main", False
            )
        else:
            temp_charge_cut_delta = None

        if "logic_type" in data:
            logic_type = enums.ControlLogicType(data["logic_type"])
        else:
            logic_type = enums.ControlLogicType.MANUAL

        # Simulating manual charge control
        # Set charge_level to 1.0 (max) for each day of simulation (plus 1)
        charge_level = [1.0] * ceil(
            (simtime.total_steps() * simtime.timestep()) / units.hours_per_day + 1
        )
        # If charge_level is present in the input file overwrite initial vector
        # User can specify a vector with all days (plus 1), or as a single float value to be used for each day
        if "charge_level" in data:
            # Determine the required length for charge_level
            required_length = ceil(
                (simtime.total_steps() * simtime.timestep()) / units.hours_per_day + 1
            )

            # Check if the input is a schedule
            if isinstance(data["charge_level"], dict) and "main" in data["charge_level"]:
                # Process the schedule using the expand_schedule function
                charge_level = expand_schedule(float, data["charge_level"], "main", 1.0)

            # If the input is a list or tuple, use it directly
            elif isinstance(data["charge_level"], (list, tuple)):
                charge_level = data["charge_level"]

            # If the input is a single value, use that value for each day of simulation
            else:
                charge_level = [data["charge_level"]] * required_length

            # Ensure charge_level has the required length by appending the last value as many times as necessary
            if len(charge_level) < required_length:
                charge_level.extend([charge_level[-1]] * (required_length - len(charge_level)))

        ctrl = ChargeControl(
            logic_type,
            schedule=sched,
            simulation_time=simtime,
            start_day=data["start_day"],
            time_series_step=data["time_series_step"],
            charge_level=charge_level,
            temp_charge_cut=data.get("temp_charge_cut"),
            temp_charge_cut_delta=temp_charge_cut_delta,
            extcond=extcond,
            external_sensor=data.get("external_sensor"),
            charge_calc_time=data.get("charge_calc_time", 21),
        )
    elif ctrl_type == enums.TimeControlType.ON_OFF_COST_MINIMISING:
        sched = expand_schedule(float, data["schedule"], "main", False)
        ctrl = OnOffCostMinimisingTimeControl(
            sched,
            simtime,
            data["start_day"],
            data["time_series_step"],
            data["time_on_daily"],
        )
    elif ctrl_type == enums.TimeControlType.COMBINATION:

        def collect_controls(control_dict, current_key, visited=None):
            """
            Recursively collects all unique controls from the combination control dictionary.

            Args:
                control_dict (dict): The combination control dictionary.
                current_key (str): The current key to process in the dictionary.
                visited (set): A set to track visited keys to detect circular references.
            Returns:
                set: A set of unique control identifiers.
            """
            if visited is None:
                visited = set()

            controls = set()
            control_instances = {}

            if current_key in visited:
                raise ValueError(
                    f"Circular reference detected involving '{current_key}' in CombinationTimeControl"
                )

            visited.add(current_key)

            if current_key in control_dict:
                control = control_dict[current_key]
                if "controls" in control:
                    for ctrl in control["controls"]:
                        if ctrl in control_dict:  # If the control is another combination
                            controls.update(collect_controls(control_dict, ctrl, visited))
                        else:
                            controls.add(ctrl)

            # Get instances of all controls
            for control_name in controls:
                control_instances[control_name] = dict_to_ctrl(
                    control_name, data_control[control_name], simtime, extcond, data_control
                )
            visited.remove(current_key)
            return control_instances

        # Collect controls from the main combination
        resolved_controls = collect_controls(data["combination"], "main")

        # Initialize CombinationTimeControl with the resolved controls
        ctrl = CombinationTimeControl(
            combination=data["combination"],
            controls=resolved_controls,
            simulation_time=simtime,
        )
    else:
        raise ValueError(f"Control type: '{ctrl_type}' not recognised for control: '{name}'")
    return ctrl


def init_resistance_or_u_value(name: str, data: dict) -> float:
    """
    Return thermal resistance of construction (thermal_resistance_construction) based on alternative inputs
    User will either provide thermal_resistance_construction directly or provide u_value which needs to be converted
    """
    # If thermal_resistance_construction has been provided directly, then use it, and warning if
    # u_value has been provided in addition
    if "thermal_resistance_construction" in data.keys():
        if "u_value" in data.keys():
            logger.warning(
                f"Warning: For BuildingElement input object {name} both thermal_resistance_construction and u_value have been provided. The value for thermal_resistance_construction will be used."
            )
        return data["thermal_resistance_construction"]
    # If only u_value has been provided, use it to calculate thermal_resistance_construction
    else:
        if "u_value" in data.keys():
            return BuildingElement.convert_uvalue_to_resistance(data["u_value"], data["pitch"])
        else:
            raise ValueError(
                f"BuildingElement '{name}' must specify either 'thermal_resistance_construction' or 'u_value'"
            )


def calc_HTC_HLP(proj_dict: dict):
    """Calculate heat transfer coefficient (HTC) and heat loss parameter (HLP)
    according to the SAP10.2 specification"""

    simtime = create_simulation_time(proj_dict["SimulationTime"])

    external_conditions = create_external_conditions(proj_dict["ExternalConditions"], simtime)

    energy_supplies = {}
    energy_supply_unmet_demand = EnergySupply(enums.FuelType.UNMET_DEMAND, simtime)
    energy_supplies["_unmet_demand"] = energy_supply_unmet_demand
    diverters = {}
    for name, data in proj_dict["EnergySupply"].items():
        if "tariff" not in data:
            data["tariff"] = None
        if "threshold_charges" not in data:
            data["threshold_charges"] = None
        if "threshold_prices" not in data:
            data["threshold_prices"] = None
        energy_supplies[name] = EnergySupply(
            enums.FuelType(data["fuel"]),
            simtime,
        )
        # TODO Consider replacing fuel type string with fuel type object

        if "diverter" in data:
            diverters[name] = data["diverter"]

    controls = {}
    for name, data in proj_dict["Control"].items():
        controls[name] = dict_to_ctrl(
            name, data, simtime, external_conditions, proj_dict["Control"]
        )

    ventilation = create_infiltration_ventilation(
        proj_dict["InfiltrationVentilation"],
        proj_dict["Zone"],
        simtime,
        False,
        energy_supplies,
        controls,
    )

    HTC_dict = {}
    HLP_dict = {}
    zone_area = {}

    def calc_heatloss(name, data):
        building_element_type = data["type"]
        # Calculate thermal_resistance_construction from u_value if only the latter has been provided
        data["thermal_resistance_construction"] = init_resistance_or_u_value(name, data)

        if data["pitch"] >= PITCH_LIMIT_HORIZ_CEILING and data["pitch"] <= PITCH_LIMIT_HORIZ_FLOOR:
            data["r_si"] = R_SI_HORIZONTAL
        elif data["pitch"] < PITCH_LIMIT_HORIZ_CEILING:
            data["r_si"] = R_SI_UPWARDS
        elif data["pitch"] > PITCH_LIMIT_HORIZ_FLOOR:
            data["r_si"] = R_SI_DOWNWARDS
        else:
            raise ValueError(f"Pitch class not recognised for building element: '{name}'")

        data["r_se"] = 1.0 / (H_CE + H_RE)

        if building_element_type == "BuildingElementOpaque":
            U_value = 1.0 / (data["thermal_resistance_construction"] + data["r_se"] + data["r_si"])
            fabric_heat_loss = data["area"] * U_value

        elif building_element_type == "BuildingElementTransparent":
            r_curtains_blinds = 0.04
            U_value = 1.0 / (
                data["thermal_resistance_construction"]
                + data["r_se"]
                + data["r_si"]
                + r_curtains_blinds
            )
            data["area"] = data["height"] * data["width"]
            fabric_heat_loss = data["area"] * U_value

        elif building_element_type == "BuildingElementGround":
            fabric_heat_loss = data["area"] * data["u_value"]

        elif building_element_type == "BuildingElementAdjacentConditionedSpace":
            fabric_heat_loss = 0.0

        elif building_element_type == "BuildingElementAdjacentUnconditionedSpace_Simple":
            U_value = 1.0 / (data["thermal_resistance_construction"] + data["r_se"] + data["r_si"])
            fabric_heat_loss = data["area"] * U_value

        elif building_element_type == "BuildingElementPartyWall":
            # Party wall calculations follow same approach as adjacent unconditioned space
            r_se = calculate_cavity_resistance(
                data["party_wall_cavity_type"],
                data.get("party_wall_lining_type"),
                data.get("thermal_resistance_cavity"),
            )
            U_value = 1.0 / (data["thermal_resistance_construction"] + r_se + data["r_si"])
            fabric_heat_loss = data["area"] * U_value
        else:
            raise ValueError(
                f"Building element type: '{building_element_type}' not recognised for building element: '{name}'"
            )

        return fabric_heat_loss

    def calc_heat_transfer_coeff(data: dict | float):
        # If data is for individual thermal bridges, initialise the relevant
        # objects and return a list of them. Otherwise, just use the overall
        # figure given.
        if isinstance(data, dict):
            thermal_bridging = 0.0
            for tb_name, tb_data in data.items():
                tb_type = tb_data["type"]
                if tb_type == enums.ThermalBridgingType.LINEAR:
                    heat_trans_coeff = tb_data["linear_thermal_transmittance"] * tb_data["length"]
                elif tb_type == enums.ThermalBridgingType.POINT:
                    heat_trans_coeff = tb_data["heat_transfer_coeff"]
                else:
                    raise ValueError(
                        f"Thermal bridge type: '{tb_type}' not recognised for thermal bridge: '{tb_name}'"
                    )
                thermal_bridging += heat_trans_coeff
        else:
            thermal_bridging = data

        return thermal_bridging

    def calc_HTC(proj_dict_zone: dict):
        wind_speed = external_conditions.wind_speed_annual()
        wind_direction = external_conditions.wind_direction_annual()
        temp_int_air = proj_dict["temp_internal_air_static_calcs"]
        temp_ext_air = external_conditions.air_temp_annual_daily_average_min()
        ach_min = proj_dict["InfiltrationVentilation"].get("ach_min_static_calcs")
        ach_max = proj_dict["InfiltrationVentilation"].get("ach_max_static_calcs")
        initial_R_v_arg = proj_dict["InfiltrationVentilation"].get("vent_opening_ratio_init", 1)

        # Adjust vent position if required to attempt to meet min or max ach
        R_v_arg = ventilation.find_R_v_arg_within_bounds(
            ach_min,
            ach_max,
            initial_R_v_arg,
            wind_speed,
            wind_direction,
            temp_int_air,
            temp_ext_air,
            R_w_arg=0,
            initial_p_z_ref_guess=0,
            reporting_flag=None,
        )

        air_changes_per_hour = ventilation.calc_air_changes_per_hour(
            wind_speed,
            wind_direction,
            temp_int_air,
            temp_ext_air,
            R_v_arg,
            R_w_arg=0,
            initial_p_z_ref_guess=0,
            reporting_flag="min",
            report_effective_flow_rate=True,
        )

        total_vent_heat_loss = calc_vent_heat_transfer_coeff(
            proj_dict_zone["volume"], air_changes_per_hour
        )

        # Calculate fabric heat loss and total floor area
        building_elements_HTC = []
        for building_element_name, building_element_data in proj_dict_zone[
            "BuildingElement"
        ].items():
            building_elements_HTC.append(
                calc_heatloss(building_element_name, building_element_data)
            )
        total_fabric_heat_loss = fsum(building_elements_HTC)

        # Read in thermal bridging data
        tb_heat_trans_coeff = calc_heat_transfer_coeff(proj_dict_zone["ThermalBridging"])

        return total_fabric_heat_loss, tb_heat_trans_coeff, total_vent_heat_loss

    # Calculate the total fabric heat loss, total heat capacity, total ventilation heat
    # loss and total heat transfer coeffient for thermal bridges across all zones
    for z_name, zone in proj_dict["Zone"].items():
        fabric_heat_loss, thermal_bridges, vent_heat_loss = calc_HTC(zone)
        # Calculate the heat transfer coefficent (HTC), in W / K
        # TODO check ventilation losses are correct
        HTC = fabric_heat_loss + thermal_bridges + vent_heat_loss
        # Calculate the HLP, in W / m2 K
        HLP = HTC / zone["area"]
        HTC_dict[z_name] = HTC
        HLP_dict[z_name] = HLP
        zone_area[z_name] = zone["area"]

    total_HTC = fsum(HTC_dict.values())
    total_floor_area = fsum(zone_area.values())
    total_HLP = total_HTC / total_floor_area

    return total_HTC, total_HLP, HTC_dict, HLP_dict


class Project:
    """An object to represent the overall model to be simulated"""

    def __init__(
        self,
        proj_dict: dict,
        project_input: Input,
        print_heat_balance: bool,
        detailed_output_heating_cooling: bool,
        use_fast_solver: bool,
        tariff_data_filename: Path | None,
        display_progress: bool = False,
    ):
        """Construct a Project object and the various components of the simulation

        Arguments:
        proj_dict -- dictionary of project data, containing nested dictionaries
                     and lists of input data for system components, external
                     conditions, occupancy etc.
        print_heat_balance -- flag to idindicate whether to print the heat balance outputs
        detailed_output_heating_cooling -- flag to indicate whether detailed output should be
                                           provided for heating and cooling (where possible)
        use_fast_solver -- flag to indicate whether to use the optimised solver (results
                           may differ slightly due to reordering of floating-point ops)
        tariff_data_filename -- relative path to tariff data file
        display_progress -- flag to show progress bar when running the calculation.

        Other (self.__) variables:
        simtime            -- SimulationTime object for this Project
        external_conditions -- ExternalConditions object for this Project
        cold_water_sources -- dictionary of ColdWaterSource objects with names as keys
        energy_supplies    -- dictionary of EnergySupply objects with names as keys
        controls           -- dictionary of control objects (of varying types) with names as keys
        hot_water_sources  -- dictionary of hot water source objects (of varying types)
                              with names as keys
        showers            -- dictionary of shower objects (of varying types) with names as keys
        space_heat_systems -- dictionary of space heating system objects (of varying
                              types) with names as keys
        zones              -- dictionary of Zone objects with names as keys
        """
        # Create a deep copy as init_resistance_or_uvalue() will add u_value & r_c
        # which will raise warning when called second time.
        self.__project_dict_original = deepcopy(proj_dict)

        self.__project_input: Input = project_input

        self.__detailed_output_heating_cooling = detailed_output_heating_cooling
        self.__display_progress = display_progress

        self.__simtime = create_simulation_time(proj_dict["SimulationTime"])

        self.__external_conditions = create_external_conditions(
            proj_dict["ExternalConditions"], self.__simtime
        )

        # Loop trough zones to sum up volume to avoid infiltration redundant input.
        total_volume = 0
        for zone_data in proj_dict["Zone"].values():
            total_volume += zone_data["volume"]

        self.__cold_water_sources = {}
        for name, data in proj_dict["ColdWaterSource"].items():
            self.__cold_water_sources[name] = ColdWaterSource(
                data["temperatures"], self.__simtime, data["start_day"], data["time_series_step"]
            )

        self.__energy_supplies = {}
        energy_supply_unmet_demand = EnergySupply(enums.FuelType.UNMET_DEMAND, self.__simtime)
        self.__energy_supplies["_unmet_demand"] = energy_supply_unmet_demand
        energy_supply_from_environment = EnergySupply(
            enums.FuelType.ENERGY_FROM_ENVIRONMENT, self.__simtime
        )
        self.__energy_supplies["_energy_from_environment"] = energy_supply_from_environment
        diverters = {}
        for name, data in proj_dict["EnergySupply"].items():
            if "tariff" not in data:
                data["tariff"] = None
            if "threshold_charges" not in data:
                data["threshold_charges"] = None
            if "threshold_prices" not in data:
                data["threshold_prices"] = None
            if "ElectricBattery" in data:
                electric_battery = ElectricBattery(
                    capacity=data["ElectricBattery"]["capacity"],
                    charge_discharge_efficiency=data["ElectricBattery"][
                        "charge_discharge_efficiency_round_trip"
                    ],
                    battery_age=data["ElectricBattery"]["battery_age"],
                    minimum_charge_rate=data["ElectricBattery"]["minimum_charge_rate_one_way_trip"],
                    maximum_charge_rate=data["ElectricBattery"]["maximum_charge_rate_one_way_trip"],
                    maximum_discharge_rate=data["ElectricBattery"][
                        "maximum_discharge_rate_one_way_trip"
                    ],
                    battery_location=enums.BatteryLocation(
                        data["ElectricBattery"]["battery_location"]
                    ),
                    grid_charging_possible=data["ElectricBattery"]["grid_charging_possible"],
                    simulation_time=self.__simtime,
                    external_conditions=self.__external_conditions,
                )
            else:
                electric_battery = None
            self.__energy_supplies[name] = EnergySupply(
                enums.FuelType(data["fuel"]),
                self.__simtime,
                tariff_data_filename,
                data["tariff"],
                data["threshold_charges"],
                data["threshold_prices"],
                electric_battery,
                data.get("priority"),
                data["is_export_capable"],
            )
            # TODO Consider replacing fuel type string with fuel type object

            if "diverter" in data:
                diverters[name] = data["diverter"]

        self.__controls = {}
        for name, data in proj_dict["Control"].items():
            self.__controls[name] = dict_to_ctrl(
                name, data, self.__simtime, self.__external_conditions, proj_dict["Control"]
            )

        def dict_to_wwhrs(name, data):
            """Parse dictionary of WWHRS source data and return appropriate WWHRS source object"""
            wwhrs_source_type = data["type"]

            if wwhrs_source_type == "WWHRS_Instantaneous":
                cold_water_source = self.__cold_water_sources[data["ColdWaterSource"]]

                # Get efficiency data for all systems if provided
                system_a_efficiencies = data.get("efficiencies", data.get("system_a_efficiencies"))
                system_a_utilisation_factor = data.get(
                    "utilisation_factor", data.get("system_a_utilisation_factor")
                )

                # Optional system-specific data
                system_b_efficiencies = data.get("system_b_efficiencies")
                system_b_utilisation_factor = data.get("system_b_utilisation_factor")
                system_c_efficiencies = data.get("system_c_efficiencies")
                system_c_utilisation_factor = data.get("system_c_utilisation_factor")

                # Efficiency reduction factors (use defaults if not specified)
                system_b_efficiency_factor = data.get("system_b_efficiency_factor", 0.81)
                system_c_efficiency_factor = data.get("system_c_efficiency_factor", 0.88)

                the_wwhrs = wwhrs_module.WWHRS_Instantaneous(
                    flow_rates=data["flow_rates"],
                    system_a_efficiencies=system_a_efficiencies,
                    cold_water_source=cold_water_source,
                    system_a_utilisation_factor=system_a_utilisation_factor,
                    system_b_efficiencies=system_b_efficiencies,
                    system_b_utilisation_factor=system_b_utilisation_factor,
                    system_c_efficiencies=system_c_efficiencies,
                    system_c_utilisation_factor=system_c_utilisation_factor,
                    system_b_efficiency_factor=system_b_efficiency_factor,
                    system_c_efficiency_factor=system_c_efficiency_factor,
                )
            else:
                raise ValueError(
                    f"WWHRS type: '{wwhrs_source_type}' not recognised for WWHRS: '{name}'"
                )

            return the_wwhrs

        if "WWHRS" in proj_dict:
            self.__wwhrs = {}
            for name, data in proj_dict["WWHRS"].items():
                self.__wwhrs[name] = dict_to_wwhrs(name, data)
        else:
            self.__wwhrs = None

        def dict_to_event_schedules(data, name, event_type, existing_schedule):
            """Process list of events (for hot water draw-offs, appliance use etc.)"""
            sim_timestep = self.__simtime.timestep()
            tot_timesteps = self.__simtime.total_steps()

            # Initialise schedule of events with no events taking place if no existing schedule is provided
            if existing_schedule is None:
                schedule = {t_idx: None for t_idx in range(tot_timesteps)}
            else:
                schedule = existing_schedule

            return expand_events(data, sim_timestep, tot_timesteps, name, event_type, schedule)

        self.__event_schedules = None
        for sched_type, schedules in proj_dict["Events"].items():
            for name, data in schedules.items():
                self.__event_schedules = dict_to_event_schedules(
                    data, name, sched_type, self.__event_schedules
                )

        def dict_to_building_element(name, data):
            building_element_type = data["type"]

            # Calculate thermal_resistance_construction from u_value if only the latter has been provided
            data["thermal_resistance_construction"] = init_resistance_or_u_value(name, data)

            if building_element_type == "BuildingElementOpaque":
                if data["pitch"] < PITCH_LIMIT_HORIZ_CEILING:
                    is_unheated_pitched_roof = data["is_unheated_pitched_roof"]
                else:
                    is_unheated_pitched_roof = False

                building_element = BuildingElementOpaque(
                    data["area"],
                    is_unheated_pitched_roof,
                    data["pitch"],
                    data["solar_absorption_coeff"],
                    data["thermal_resistance_construction"],
                    data["areal_heat_capacity"],
                    enums.MassDistributionClass(data["mass_distribution_class"]),
                    units.Orientation360(data["orientation360"]),
                    data["base_height"],
                    data["height"],
                    data["width"],
                    self.__external_conditions,
                )
            elif building_element_type == "BuildingElementTransparent":
                if "treatment" in data.keys():
                    treatment = data["treatment"]
                    for t in treatment:
                        t["Control_open"] = (
                            self.__controls[t["Control_open"]] if "Control_open" in t else None
                        )
                        t["Control_closing_irrad"] = (
                            self.__controls[t["Control_closing_irrad"]]
                            if "Control_closing_irrad" in t
                            else None
                        )
                        t["Control_opening_irrad"] = (
                            self.__controls[t["Control_opening_irrad"]]
                            if "Control_opening_irrad" in t
                            else None
                        )
                else:
                    treatment = None
                building_element = BuildingElementTransparent(
                    data["pitch"],
                    data["thermal_resistance_construction"],
                    units.Orientation360(data["orientation360"]),
                    data["g_value"],
                    data["frame_area_fraction"],
                    data["base_height"],
                    data["height"],
                    data["width"],
                    data["shading"],
                    treatment,
                    self.__external_conditions,
                    self.__simtime,
                )
            elif building_element_type == "BuildingElementGround":
                if data["floor_type"] == enums.FloorType.SLAB_NO_EDGE_INSULATION:
                    edge_insulation = None
                    height_upper_surface = None
                    thermal_transm_envi_base = None
                    thermal_transm_walls = None
                    area_per_perimeter_vent = None
                    shield_fact_location = None
                    thickness_walls = data["thickness_walls"]
                    thermal_resist_insul = None
                    depth_basement_floor = None
                    thermal_resist_walls_base = None
                    height_basement_walls = None

                elif data["floor_type"] == enums.FloorType.SLAB_EDGE_INSULATION:
                    edge_insulation = data["edge_insulation"]
                    height_upper_surface = None
                    thermal_transm_envi_base = None
                    thermal_transm_walls = None
                    area_per_perimeter_vent = None
                    shield_fact_location = None
                    thickness_walls = data["thickness_walls"]
                    thermal_resist_insul = None
                    depth_basement_floor = None
                    thermal_resist_walls_base = None
                    height_basement_walls = None

                elif data["floor_type"] == enums.FloorType.SUSPENDED_FLOOR:
                    edge_insulation = None
                    height_upper_surface = data["height_upper_surface"]
                    thermal_transm_envi_base = None
                    thermal_transm_walls = data["thermal_transm_walls"]
                    area_per_perimeter_vent = data["area_per_perimeter_vent"]
                    shield_fact_location = enums.WindShieldLocation(data["shield_fact_location"])
                    thickness_walls = data["thickness_walls"]
                    thermal_resist_insul = data["thermal_resist_insul"]
                    depth_basement_floor = None
                    thermal_resist_walls_base = None
                    height_basement_walls = None

                elif data["floor_type"] == enums.FloorType.HEATED_BASEMENT:
                    edge_insulation = None
                    height_upper_surface = None
                    thermal_transm_envi_base = None
                    thermal_transm_walls = None
                    area_per_perimeter_vent = None
                    shield_fact_location = None
                    thickness_walls = data["thickness_walls"]
                    thermal_resist_insul = None
                    depth_basement_floor = data["depth_basement_floor"]
                    thermal_resist_walls_base = data["thermal_resist_walls_base"]
                    height_basement_walls = None

                elif data["floor_type"] == enums.FloorType.UNHEATED_BASEMENT:
                    edge_insulation = None
                    height_upper_surface = None
                    thermal_transm_envi_base = data["thermal_transm_envi_base"]
                    thermal_transm_walls = data["thermal_transm_walls"]
                    area_per_perimeter_vent = None
                    shield_fact_location = None
                    thickness_walls = data["thickness_walls"]
                    thermal_resist_insul = None
                    depth_basement_floor = data["depth_basement_floor"]
                    thermal_resist_walls_base = data["thermal_resist_walls_base"]
                    height_basement_walls = data["height_basement_walls"]

                else:
                    raise ValueError(f"Floor type: {data['floor_type']} is not valid")

                building_element = BuildingElementGround(
                    data["total_area"],
                    data["area"],
                    data["pitch"],
                    data["u_value"],
                    data["thermal_resistance_floor_construction"],
                    data["areal_heat_capacity"],
                    enums.MassDistributionClass(data["mass_distribution_class"]),
                    enums.FloorType(data["floor_type"]),
                    edge_insulation,
                    height_upper_surface,
                    thermal_transm_envi_base,
                    thermal_transm_walls,
                    area_per_perimeter_vent,
                    shield_fact_location,
                    thickness_walls,
                    thermal_resist_insul,
                    depth_basement_floor,
                    thermal_resist_walls_base,
                    height_basement_walls,
                    data["perimeter"],
                    data["psi_wall_floor_junc"],
                    self.__external_conditions,
                    self.__simtime,
                )
            elif building_element_type == "BuildingElementAdjacentConditionedSpace":
                building_element = BuildingElementAdjacentConditionedSpace(
                    data["area"],
                    data["pitch"],
                    data["thermal_resistance_construction"],
                    data["areal_heat_capacity"],
                    enums.MassDistributionClass(data["mass_distribution_class"]),
                    self.__external_conditions,
                )
            elif building_element_type == "BuildingElementAdjacentUnconditionedSpace_Simple":
                building_element = BuildingElementAdjacentUnconditionedSpace_Simple(
                    data["area"],
                    data["pitch"],
                    data["thermal_resistance_construction"],
                    data["thermal_resistance_unconditioned_space"],
                    data["areal_heat_capacity"],
                    enums.MassDistributionClass(data["mass_distribution_class"]),
                    self.__external_conditions,
                )
            elif building_element_type == "BuildingElementPartyWall":
                # Handle party wall with automatic or manual cavity resistance
                building_element = BuildingElementPartyWall(
                    data["area"],
                    data["pitch"],
                    data["thermal_resistance_construction"],
                    data["party_wall_cavity_type"],
                    data.get("party_wall_lining_type"),
                    data.get("thermal_resistance_cavity"),
                    data["areal_heat_capacity"],
                    enums.MassDistributionClass(data["mass_distribution_class"]),
                    self.__external_conditions,
                )
            else:
                raise ValueError(
                    f"Building element type: '{building_element_type}' not recognised for building element: '{name}'"
                )
            return building_element

        if proj_dict["InfiltrationVentilation"].get("Control_WindowAdjust") is not None:
            self.__control_WindowAdjust = self.__controls[
                proj_dict["InfiltrationVentilation"]["Control_WindowAdjust"]
            ]
        else:
            self.__control_WindowAdjust = None
        if proj_dict["InfiltrationVentilation"].get("Control_VentAdjustMin") is not None:
            self.__control_VentAdjustMin = self.__controls[
                proj_dict["InfiltrationVentilation"].get("Control_VentAdjustMin")
            ]
        else:
            self.__control_VentAdjustMin = None
        if proj_dict["InfiltrationVentilation"].get("Control_VentAdjustMax") is not None:
            self.__control_VentAdjustMax = self.__controls[
                proj_dict["InfiltrationVentilation"].get("Control_VentAdjustMax")
            ]
        else:
            self.__control_VentAdjustMax = None
        self.__R_v_arg = proj_dict["InfiltrationVentilation"].get(
            "vent_opening_ratio_init", 1
        )  # Default to 1 if not specified

        self.__ventilation = create_infiltration_ventilation(
            proj_dict["InfiltrationVentilation"],
            proj_dict["Zone"],
            self.__simtime,
            self.__detailed_output_heating_cooling,
            self.__energy_supplies,
            self.__controls,
        )
        self.__mech_vents = self.__ventilation.mech_vents()

        if "required_vent" in proj_dict["Control"]:
            req_vent_dict = proj_dict["Control"]["required_vent"]
            self.__sched_req_vent = expand_schedule(float, req_vent_dict["schedule"], "main", True)
            self.__req_vent_start_day = req_vent_dict["start_day"]
            self.__req_vent_time_series_step = req_vent_dict["time_series_step"]
        else:
            req_vent_dict = None
            self.__sched_req_vent = None

        def dict_to_thermal_bridging(data):
            # If data is for individual thermal bridges, initialise the relevant
            # objects and return a list of them. Otherwise, just use the overall
            # figure given.
            if isinstance(data, dict):
                thermal_bridging = []
                for tb_name, tb_data in data.items():
                    tb_type = tb_data["type"]
                    if tb_type == enums.ThermalBridgingType.LINEAR:
                        tb = ThermalBridgeLinear(
                            tb_data["linear_thermal_transmittance"], tb_data["length"]
                        )
                    elif tb_type == enums.ThermalBridgingType.POINT:
                        tb = ThermalBridgePoint(tb_data["heat_transfer_coeff"])
                    else:
                        raise ValueError(
                            f"Thermal bridge type: '{tb_type}' not recognised for thermal bridge: '{tb_name}'"
                        )
                    thermal_bridging.append(tb)
            else:
                thermal_bridging = data
            return thermal_bridging

        self.__heat_system_name_for_zone = {}
        self.__cool_system_name_for_zone = {}
        opening_area_total = 0.0
        for z_data in proj_dict["Zone"].values():
            for building_element_data in z_data["BuildingElement"].values():
                if building_element_data["type"] == "BuildingElementTransparent":
                    opening_area_total += (
                        building_element_data["height"] * building_element_data["width"]
                    )

        def dict_to_zone(name, data):
            # Record which heating and cooling system this zone is heated/cooled by (if applicable)
            if "SpaceHeatSystem" in data:
                # Check that no heating system has been assigned to more than one zone
                # Each zone has a list of heating systems associated with it. This
                # compares the list for the zone currently being processed with the
                # lists for zones that have already been processed.
                if not isinstance(data["SpaceHeatSystem"], list):
                    data["SpaceHeatSystem"] = [data["SpaceHeatSystem"]]
                if len(data["SpaceHeatSystem"]) != len(set(data["SpaceHeatSystem"])):
                    raise ValueError(
                        f"Invalid input: duplicate entry in SpaceHeatSystem list for zone '{name}'"
                    )
                for zone_h_name in self.__heat_system_name_for_zone.values():
                    h_overassigned = set(data["SpaceHeatSystem"]).intersection(zone_h_name)
                    if h_overassigned:
                        raise ValueError(
                            f"Invalid input: SpaceHeatSystem ({h_overassigned}) has been assigned to more than one zone"
                        )
                self.__heat_system_name_for_zone[name] = data["SpaceHeatSystem"]
            else:
                self.__heat_system_name_for_zone[name] = [None]
            if "SpaceCoolSystem" in data:
                # Check that no cooling system has been assigned to more than one zone
                # Each zone has a list of cooling systems associated with it. This
                # compares the list for the zone currently being processed with the
                # lists for zones that have already been processed.
                if not isinstance(data["SpaceCoolSystem"], list):
                    data["SpaceCoolSystem"] = [data["SpaceCoolSystem"]]
                if len(data["SpaceCoolSystem"]) != len(set(data["SpaceCoolSystem"])):
                    raise ValueError(
                        f"Invalid input: duplicate entry in SpaceCoolSystem list for zone '{name}'"
                    )
                for zone_c_name in self.__cool_system_name_for_zone.values():
                    c_overassigned = set(data["SpaceCoolSystem"]).intersection(zone_c_name)
                    if c_overassigned:
                        raise ValueError(
                            f"Invalid input: SpaceCoolSystem ({c_overassigned}) has been assigned to more than one zone"
                        )
                self.__cool_system_name_for_zone[name] = data["SpaceCoolSystem"]
            else:
                self.__cool_system_name_for_zone[name] = [None]

            # Read in building elements and add to list
            building_elements = []
            for building_element_name, building_element_data in data["BuildingElement"].items():
                building_elements.append(
                    dict_to_building_element(building_element_name, building_element_data)
                )

            # Read in thermal bridging data
            thermal_bridging = dict_to_thermal_bridging(data["ThermalBridging"])

            # Default setpoint basis to 'operative' if not provided in input
            if "temp_setpnt_basis" not in data:
                data["temp_setpnt_basis"] = "operative"

            return Zone(
                data["area"],
                data["volume"],
                building_elements,
                thermal_bridging,
                self.__ventilation,
                self.__external_conditions.air_temp(),
                data["temp_setpnt_init"],
                data["temp_setpnt_basis"],
                self.__control_WindowAdjust,
                print_heat_balance=print_heat_balance,
                use_fast_solver=use_fast_solver,
            )

        self.__zones = {}
        self.__energy_supply_conn_unmet_demand_zone = {}

        for name, data in proj_dict["Zone"].items():
            self.__zones[name] = dict_to_zone(name, data)
            self.__energy_supply_conn_unmet_demand_zone[name] = self.__energy_supplies[
                "_unmet_demand"
            ].connection(name)

        self.__total_floor_area = fsum(zone.area() for zone in self.__zones.values())
        self.__total_volume = fsum(zone.volume() for zone in self.__zones.values())
        self.__update_temp_internal_air()

        def convert_energy_to_Wm2(data):
            # Convert energy supplied to appliances from W to W / m2
            total_energy_supply = []
            for energy_data in expand_schedule(float, data["schedule"], "main", False):
                total_energy_supply.append(energy_data / self.__total_floor_area)
            return total_energy_supply

        # Internal gains is an ordered dict. This is because load shifting behaviours
        # of appliance gains depend on other energy demand in the dwelling at any given time,
        # so depend on the order in which gains are considered by the engine. See check_priority() below
        self.__internal_gains = OrderedDict()
        if "InternalGains" in proj_dict:
            for name, data in proj_dict["InternalGains"].items():
                self.__internal_gains[name] = InternalGains(
                    convert_energy_to_Wm2(data),
                    self.__simtime,
                    data["start_day"],
                    data["time_series_step"],
                )

        # setup smart control for loadshifting
        self.__smart_appliance_controls = {}
        if "SmartApplianceControls" in proj_dict.keys():
            for smartappname, smartappctrldata in proj_dict["SmartApplianceControls"].items():
                try:
                    # TODO - power_timeseries is a redundant input,
                    # we could obtain power_timeseries here from the list smartappctrldata['Appliances'],
                    # by looking up each string in the list in proj_dict['ApplianceGains'], and
                    # summing together the demand schedules of listed items
                    # this will require the use of EventApplianceGains.__event_to_schedule()
                    # for event based appliance use
                    self.__smart_appliance_controls[smartappname] = SmartApplianceControl(
                        smartappctrldata["power_timeseries"],
                        smartappctrldata["time_series_step"],
                        self.__simtime,
                        smartappctrldata["non_appliance_demand_24hr"],
                        smartappctrldata["battery24hr"],
                        self.__energy_supplies,
                        smartappctrldata["Appliances"],
                    )
                except (ValueError, KeyError, TypeError) as err:
                    raise ValueError(
                        f"Invalid appliance load shifting inputs for '{smartappname}': {str(err)}"
                    ) from err

        # Add internal gains from applicances to the internal gains dictionary and
        # create an energy supply connection for appliances
        # work out order in which to process loadshifting appliances
        def check_priority(appliancegains_dict):
            defined_priority = [
                app for app, x in appliancegains_dict.items() if "priority" in x.keys()
            ]
            lowest_priority = max(
                [appliancegains_dict[p]["priority"] for p in defined_priority] + [0]
            )
            for appliance in appliancegains_dict.keys():
                if appliance in defined_priority:
                    continue
                else:
                    lowest_priority += 1
                    appliancegains_dict[appliance]["priority"] = lowest_priority
            return appliancegains_dict

        for name, data in sorted(
            check_priority(proj_dict["ApplianceGains"]).items(),
            key=lambda d: d[1]["priority"],
            reverse=True,
        ):
            energy_supply = self.__energy_supplies[data["EnergySupply"]]
            # TODO Need to handle error if EnergySupply name is invalid.

            if "Events" in data.keys() and "Standby" in data.keys():
                self.__internal_gains[name] = EventApplianceGains(
                    energy_supply_conn=energy_supply.connection(name),
                    simulation_time=self.__simtime,
                    appliance_data=data,
                    TFA=self.__total_floor_area,
                    smartcontrol=self.__smart_appliance_controls.get(
                        data["loadshifting"].get("Control")
                    )
                    if "loadshifting" in data.keys()
                    else None,
                )
            else:
                # Convert energy supplied to appliances from W to W / m2
                self.__internal_gains[name] = ApplianceGains(
                    total_energy_supply=convert_energy_to_Wm2(data),
                    energy_supply_conn=energy_supply.connection(name),
                    gains_fraction=data["gains_fraction"],
                    simulation_time=self.__simtime,
                    start_day=data["start_day"],
                    time_series_step=data["time_series_step"],
                )

        # Where wet distribution heat source provide more than one service, some
        # calculations can only be performed after all services have been
        # calculated. Give these systems a timestep_end function and add these
        # systems to the following list, which will be iterated over later.
        self.__timestep_end_calcs = []

        # Register WWHRS objects for timestep_end calls
        if self.__wwhrs is not None:
            for wwhrs in self.__wwhrs.values():
                self.__timestep_end_calcs.append(wwhrs)

        def dict_to_heat_source_wet(
            name: str, data: dict
        ) -> HeatPump | Boiler | HeatNetwork | HeatBatteryPCM | HeatBatteryDryCore:
            heat_source_type = data["type"]

            if heat_source_type == enums.HeatSourceWetType.HEAT_PUMP:
                throughput_exhaust_air = None
                proj_obj = None
                source_type = SourceType(data["source_type"])
                if source_type.is_exhaust_air:
                    # Check that ventilation system exists and is compatible with exhaust air HP
                    if self.__mech_vents is not None:
                        for mech_vent in self.__mech_vents:
                            if mech_vent.vent_type in (
                                enums.MechVentType.INTERMITTENT_MEV,
                                enums.MechVentType.DECENTRALISED_CONTINUOUS_MEV,
                            ):
                                raise ValueError(
                                    "Exhaust air heat pump does not work with Intermittent MEV or Decentralised continuous MEV."
                                )
                            else:
                                throughput_exhaust_air = mech_vent.design_outdoor_air_flow_rate_m3_h
                                # Record heat source as potentially requiring overventilation
                                self.__heat_source_wet_names_requiring_overvent.append(name)
                                # Pass in proj_obj into HeatPump class for exhaust air hps
                                proj_obj = self
                    else:
                        raise ValueError("Ventilation object does not exist")

                if SourceType(data["source_type"]) == SourceType.HEAT_NETWORK:
                    energy_supply_heat_source = self.__energy_supplies[
                        data["EnergySupply_heat_network"]
                    ]
                    # TODO Check that EnergySupply object representing heat source
                    #      has an appropriate fuel type
                else:
                    energy_supply_heat_source = self.__energy_supplies["_energy_from_environment"]

                if "boiler" in data:
                    energy_supply_boiler = self.__energy_supplies[data["boiler"]["EnergySupply"]]
                    energy_supply_aux_boiler = self.__energy_supplies[
                        data["boiler"]["EnergySupply_aux"]
                    ]
                    boiler = Boiler(
                        boiler_dict=data["boiler"],
                        energy_supply=energy_supply_boiler,
                        energy_supply_conn_aux=energy_supply_aux_boiler.connection(
                            "Boiler_auxiliary: " + name
                        ),
                        simulation_time=self.__simtime,
                        ext_cond=self.__external_conditions,
                    )

                    if "cost_schedule_hybrid" in data["boiler"]:
                        cost_schedule_hybrid_hp = data["boiler"]["cost_schedule_hybrid"]
                    else:
                        cost_schedule_hybrid_hp = None

                    self.__timestep_end_calcs.append(boiler)
                else:
                    cost_schedule_hybrid_hp = None
                    boiler = None

                energy_supply = self.__energy_supplies[data["EnergySupply"]]
                energy_supply_conn_name_auxiliary = "HeatPump_auxiliary: " + name
                if "BufferTank" in data:
                    self.__heat_sources_wet_with_buffer_tank.append(name)
                    # Pass in proj_obj into HeatPump class for Initialisation of Buffer Tank temperature
                    proj_obj = self
                heat_source = HeatPump(
                    hp_dict=data,
                    energy_supply=energy_supply,
                    energy_supply_conn_name_auxiliary=energy_supply_conn_name_auxiliary,
                    simulation_time=self.__simtime,
                    external_conditions=self.__external_conditions,
                    number_of_zones=len(proj_dict["Zone"].items()),
                    throughput_exhaust_air=throughput_exhaust_air,
                    energy_supply_heat_source=energy_supply_heat_source,
                    output_detailed_results=self.__detailed_output_heating_cooling,
                    boiler=boiler,
                    cost_schedule_hybrid_hp=cost_schedule_hybrid_hp,
                    project=proj_obj,
                )
                self.__timestep_end_calcs.append(heat_source)

            elif heat_source_type == "Boiler":
                energy_supply = self.__energy_supplies[data["EnergySupply"]]
                energy_supply_aux = self.__energy_supplies[data["EnergySupply_aux"]]
                heat_source = Boiler(
                    boiler_dict=data,
                    energy_supply=energy_supply,
                    energy_supply_conn_aux=energy_supply_aux.connection(
                        "Boiler_auxiliary: " + name
                    ),
                    simulation_time=self.__simtime,
                    ext_cond=self.__external_conditions,
                )
                self.__timestep_end_calcs.append(heat_source)

            elif heat_source_type == "HIU":
                energy_supply = self.__energy_supplies[data["EnergySupply"]]
                energy_supply_conn_name_auxiliary = "HeatNetwork_auxiliary: " + name
                energy_supply_conn_name_building_level_distribution_losses = (
                    "HeatNetwork_building_level_distribution_losses: " + name
                )
                heat_source = HeatNetwork(
                    power_max=data["power_max"],
                    daily_loss=data["HIU_daily_loss"],
                    power_circ_pump=data.get("power_circ_pump", 0.06),
                    power_aux=data.get("power_aux", 0),
                    building_level_distribution_losses=data["building_level_distribution_losses"],
                    energy_supply=energy_supply,
                    energy_supply_conn_name_auxiliary=energy_supply_conn_name_auxiliary,
                    energy_supply_conn_name_building_level_distribution_losses=energy_supply_conn_name_building_level_distribution_losses,
                    simulation_time=self.__simtime,
                )
                self.__timestep_end_calcs.append(heat_source)
                # Create list of internal gains for each hour of the year, in W / m2
                internal_gains_HIU = [
                    heat_source.HIU_loss() * units.W_per_kW / self.__total_floor_area
                ]
                total_internal_gains_HIU = (
                    internal_gains_HIU * units.days_per_year * units.hours_per_day
                )
                # Append internal gains object to self.__internal_gains dictionary
                if name in self.__internal_gains.keys():
                    raise ValueError(
                        "Name of HIU duplicates name of an existing InternalGains object"
                    )
                self.__internal_gains[name] = InternalGains(
                    total_internal_gains_HIU,
                    self.__simtime,
                    0,  # Start day of internal gains time series
                    1.0,  # Timestep of internal gains time series
                )

            elif heat_source_type == "HeatBattery":
                energy_supply = self.__energy_supplies[data["EnergySupply"]]
                # TODO Need to handle error if EnergySupply name is invalid.
                charge_control: ChargeControl = self.__controls[data["ControlCharge"]]

                # Check battery type and create appropriate instance
                battery_type = data["battery_type"]

                if battery_type == "dry_core":
                    heat_source = HeatBatteryDryCore(
                        heat_battery_dict=data,
                        charge_control=charge_control,
                        energy_supply=energy_supply,
                        energy_supply_conn=energy_supply.connection(name),
                        simulation_time=self.__simtime,
                        n_units=data.get("number_of_units", 1),
                        output_detailed_results=self.__detailed_output_heating_cooling,
                    )
                elif battery_type == "pcm":
                    heat_source = HeatBatteryPCM(
                        heat_battery_dict=data,
                        charge_control=charge_control,
                        energy_supply=energy_supply,
                        energy_supply_conn=energy_supply.connection(name),
                        simulation_time=self.__simtime,
                        ext_cond=self.__external_conditions,
                        output_detailed_results=self.__detailed_output_heating_cooling,
                    )
                else:
                    raise ValueError(
                        f"Heat battery type: '{battery_type}' not recognised for heat battery: '{name}'"
                    )
                self.__timestep_end_calcs.append(heat_source)
            else:
                raise ValueError(
                    f"Heat source type: '{heat_source_type}' not recognised for heat source: '{name}'"
                )
            return heat_source

        # If one or more wet distribution heat sources have been provided, add them to the project
        self.__heat_sources_wet = {}
        self.__heat_sources_wet_with_buffer_tank = []
        self.__heat_source_wet_names_requiring_overvent = []
        # If no wet distribution heat sources have been provided, then skip.
        if "HeatSourceWet" in proj_dict:
            for key, value in proj_dict["HeatSourceWet"].items():
                self.__heat_sources_wet[key] = dict_to_heat_source_wet(name=key, data=value)

        def dict_to_heat_source(
            name,
            hot_water_source_name,
            data,
            cold_water_source,
            volume,
            daily_losses,
            heat_exchanger_surface_area=None,
        ):
            """Parse dictionary of heat source data and return approprate heat source object"""
            heat_source_type = data["type"]
            if heat_source_type == "SolarThermalSystem":
                ctrlmax = self.__controls[data["Controlmax"]]
            else:
                ctrlmin = self.__controls[data["Controlmin"]]
                ctrlmax = self.__controls[data["Controlmax"]]
                # TODO Need to handle error if Control name is invalid.

            if heat_source_type == "ImmersionHeater":
                energy_supply = self.__energy_supplies[data["EnergySupply"]]
                # TODO Need to handle error if EnergySupply name is invalid.
                energy_supply_conn_name = name

                heat_source = ImmersionHeater(
                    rated_power=data["power"],
                    energy_supply_conn=energy_supply.connection(name),
                    simulation_time=self.__simtime,
                    controlmin=ctrlmin,
                    controlmax=ctrlmax,
                )
            elif heat_source_type == "SolarThermalSystem":
                energy_supply = self.__energy_supplies[data["EnergySupply"]]
                # TODO Need to handle error if EnergySupply name is invalid.
                energy_supply_conn_name = name
                energy_supply_from_environment = self.__energy_supplies["_energy_from_environment"]

                contents = WATER
                heat_source = SolarThermalSystem(
                    sol_loc=enums.SolarCollectorLoopLocation(data["sol_loc"]),
                    area_module=data["area_module"],
                    modules=data["modules"],
                    peak_collector_efficiency=data["peak_collector_efficiency"],
                    incidence_angle_modifier=data["incidence_angle_modifier"],
                    first_order_hlc=data["first_order_hlc"],
                    second_order_hlc=data["second_order_hlc"],
                    collector_mass_flow_rate=data["collector_mass_flow_rate"],
                    power_pump=data["power_pump"],
                    power_pump_control=data["power_pump_control"],
                    energy_supply_conn=energy_supply.connection(name),
                    tilt=data["tilt"],
                    orientation=units.Orientation360(data["orientation360"]),
                    solar_loop_piping_hlc=data["solar_loop_piping_hlc"],
                    ext_cond=self.__external_conditions,
                    simulation_time=self.__simtime,
                    project=self,
                    controlmax=ctrlmax,
                    contents=contents,
                    energy_supply_from_environment_conn=energy_supply_from_environment.connection(
                        name
                    ),
                )

            elif heat_source_type == "HeatSourceWet":
                energy_supply_conn_name = data["name"] + "_water_heating: " + hot_water_source_name
                self.__hotwatersource_name_for_heatsourcewet_service[energy_supply_conn_name] = (
                    hot_water_source_name
                )

                heat_source_wet = self.__heat_sources_wet[data["name"]]
                if isinstance(heat_source_wet, HeatPump):
                    heat_source = heat_source_wet.create_service_hot_water(
                        energy_supply_conn_name,
                        data["temp_flow_limit_upper"],
                        cold_water_source,
                        ctrlmin,
                        ctrlmax,
                    )
                elif isinstance(heat_source_wet, Boiler):
                    heat_source = heat_source_wet.create_service_hot_water_regular(
                        energy_supply_conn_name, cold_water_source, ctrlmin, ctrlmax
                    )
                elif isinstance(heat_source_wet, HeatNetwork):
                    # Add heat network hot water service for feeding hot water cylinder
                    heat_source = heat_source_wet.create_service_hot_water_storage(
                        energy_supply_conn_name, ctrlmin, ctrlmax
                    )
                elif isinstance(heat_source_wet, HeatBatteryPCM):
                    heat_source = heat_source_wet.create_service_hot_water_regular(
                        energy_supply_conn_name, cold_water_source, ctrlmin, ctrlmax
                    )
                elif isinstance(heat_source_wet, HeatBatteryDryCore):
                    heat_source = heat_source_wet.create_service_hot_water_regular(
                        energy_supply_conn_name, cold_water_source, ctrlmin, ctrlmax
                    )
                else:
                    raise ValueError(
                        f"Heat source type: '{heat_source_type}' not recognised for heat source: '{name}'"
                    )
            elif heat_source_type == "HeatPump_HWOnly":
                energy_supply = self.__energy_supplies[data["EnergySupply"]]
                # TODO Need to handle error if EnergySupply name is invalid.
                energy_supply_conn_name = name

                heat_source = HeatPump_HWOnly(
                    power_max=data["power_max"],
                    test_data=data["test_data"],
                    vol_daily_average=data["vol_hw_daily_average"],
                    tank_volume=volume,
                    daily_losses=daily_losses,
                    heat_exchanger_surface_area=heat_exchanger_surface_area,
                    in_use_factor_mismatch=data["in_use_factor_mismatch"],
                    tank_volume_declared=data["tank_volume_declared"],
                    heat_exchanger_surface_area_declared=data[
                        "heat_exchanger_surface_area_declared"
                    ],
                    daily_losses_declared=data["daily_losses_declared"],
                    energy_supply_conn=energy_supply.connection(name),
                    simulation_time=self.__simtime,
                    controlmin=ctrlmin,
                    controlmax=ctrlmax,
                )
            else:
                raise ValueError(
                    f"Heat source type: '{heat_source_type}' not recognised for heat source: '{name}'"
                )
            return heat_source, energy_supply_conn_name

        # List of diverter objects (for end-of-timestep calculations
        self.__diverters = []

        def dict_to_hot_water_source(name, data):
            """Parse dictionary of HW source data and return approprate HW source object"""
            energy_supply_conn_names = []

            hw_source_type = data["type"]
            if hw_source_type == "StorageTank" or hw_source_type == "SmartHotWaterTank":
                # Try to get the cold water source from the available sources
                cold_water_source = self.__cold_water_sources.get(data["ColdWaterSource"])
                if cold_water_source is None:
                    cold_water_source = self.__pre_heated_water_sources.get(
                        data["ColdWaterSource"]
                    ) or self.__wwhrs.get(data["ColdWaterSource"])
                    # If cold water source is a pre-heat source or WWHRS, check if it has already
                    # been used, and record its first use if not
                    if cold_water_source is not None:
                        if data["ColdWaterSource"] in cold_water_sources_already_allocated:
                            raise ValueError(
                                "Cannot allocate PreHeatedWaterSource or WWHRS to more than one HotWaterSource: "
                                + str(data["ColdWaterSource"])
                            )
                        else:
                            cold_water_sources_already_allocated.add(data["ColdWaterSource"])

                # Check if a valid cold water source was found
                if cold_water_source is None:
                    raise ValueError("Invalid cold water source for Storage Tank.")

                if "primary_pipework" in data:
                    primary_pipework_lst = data["primary_pipework"]
                    for pipework_data in primary_pipework_lst:
                        pipework_data["internal_diameter"] = (
                            pipework_data["internal_diameter_mm"] / units.mm_per_m
                        )
                        pipework_data["external_diameter"] = (
                            pipework_data["external_diameter_mm"] / units.mm_per_m
                        )
                        pipework_data["insulation_thickness"] = (
                            pipework_data["insulation_thickness_mm"] / units.mm_per_m
                        )
                else:
                    primary_pipework_lst = []

                for heat_source_data in data["HeatSource"].values():
                    # heat exchanger area
                    if "HeatPump_HWOnly" in heat_source_data["type"]:
                        heat_exchanger_surface_area = data["heat_exchanger_surface_area"]
                    else:
                        heat_exchanger_surface_area = None

                heat_source_dict = {}
                heat_source_names_dict = {}
                # With pre-heated tanks we allow now tanks not to have a heat source as the 'cold' feed
                # coudl be a pre-heated source or wwhr that might be enough
                if "HeatSource" in data:
                    for heat_source_name, heat_source_data in data["HeatSource"].items():
                        heat_source, conn_name = dict_to_heat_source(
                            heat_source_name,
                            name,
                            heat_source_data,
                            cold_water_source,
                            data["volume"],
                            data["daily_losses"],
                            heat_exchanger_surface_area,
                        )
                        if hw_source_type == "SmartHotWaterTank":
                            heat_source_dict[heat_source] = (
                                heat_source_data["heater_position"],
                                None,
                            )
                        elif hw_source_type == "StorageTank":
                            heat_source_dict[heat_source] = (
                                heat_source_data["heater_position"],
                                heat_source_data["thermostat_position"],
                            )
                        energy_supply_conn_names.append(conn_name)
                        heat_source_names_dict[heat_source_name] = heat_source

                if hw_source_type == "SmartHotWaterTank":
                    values = [value[0] for value in heat_source_dict.values()]
                    if len(set(values)) != 1:
                        raise ValueError(
                            "For SmartHotWaterTank, heater position must be the same for all heat sources"
                        )

                    energy_supply_pump = self.__energy_supplies[data["EnergySupply_pump"]]
                    hw_source = SmartHotWaterTank(
                        volume=data["volume"],
                        losses=data["daily_losses"],
                        init_temp=data["init_temp"],
                        power_pump_kW=data["power_pump_kW"],
                        max_flow_rate_pump_l_per_min=data["max_flow_rate_pump_l_per_min"],
                        temp_usable=data["temp_usable"],
                        temp_setpnt_max=self.__controls[data["temp_setpnt_max"]],
                        cold_feed=cold_water_source,
                        simulation_time=self.__simtime,
                        heat_source_dict=heat_source_dict,
                        project=self,
                        external_conditions=self.__external_conditions,
                        detailed_output=self.__detailed_output_heating_cooling,
                        nb_vol=100,
                        primary_pipework_lst=primary_pipework_lst,
                        energy_supply_conn_pump=energy_supply_pump.connection(
                            "Smart_hot_water_tank_pump: " + name
                        ),
                    )
                elif hw_source_type == "StorageTank":
                    hw_source = StorageTank(
                        volume=data["volume"],
                        losses=data["daily_losses"],
                        init_temp=data["init_temp"],
                        cold_feed=cold_water_source,
                        simulation_time=self.__simtime,
                        heat_source_dict=heat_source_dict,
                        project=self,
                        external_conditions=self.__external_conditions,
                        detailed_output=self.__detailed_output_heating_cooling,
                        nb_vol=24,
                        primary_pipework_lst=primary_pipework_lst,
                    )
                else:
                    raise ValueError(f"Unknown hot water source type: {hw_source_type}")

                energy_supply_conn_names.append(name)

                # With pre-heated tanks we allow now tanks not to have a heat source as the 'cold' feed
                # coudl be a pre-heated source or wwhr that might be enough
                if "HeatSource" in data:
                    for heat_source_name, heat_source_data in data["HeatSource"].items():
                        if heat_source_name in self.__used_heat_source_names:
                            raise ValueError(
                                "Duplicate heat source name detected: " + str(heat_source_name)
                            )
                        self.__used_heat_source_names.add(heat_source_name)
                        # HeatSourceWet types do not have their own EnergySupply
                        # — the energy supply is on the parent HeatSourceWet object.
                        # PV diverters only connect to non-wet heat sources (e.g.
                        # immersion heaters), so skip the diverter check.
                        heat_source_type = heat_source_data["type"]
                        if heat_source_type == "HeatSourceWet":
                            continue
                        energy_supply_name = heat_source_data["EnergySupply"]
                        if energy_supply_name in diverters:
                            diverter = diverters[energy_supply_name]
                            if diverter["HeatSource"] == heat_source_name:
                                energy_supply = self.__energy_supplies[energy_supply_name]
                                controlmax = self.__controls[diverter["Controlmax"]]
                                pv_diverter = PVDiverter(
                                    hw_source,
                                    heat_source_names_dict[heat_source_name],
                                    controlmax,
                                )
                                energy_supply.connect_diverter(pv_diverter)
                                self.__diverters.append(pv_diverter)

            elif hw_source_type == "CombiBoiler":
                energy_supply_conn_name = data["HeatSourceWet"] + "_water_heating"
                energy_supply_conn_names.append(energy_supply_conn_name)
                cold_water_source = self.__cold_water_sources[data["ColdWaterSource"]]
                hw_source = self.__heat_sources_wet[
                    data["HeatSourceWet"]
                ].create_service_hot_water_combi(
                    data, energy_supply_conn_name, data["setpoint_temp"], cold_water_source
                )
            elif hw_source_type == "PointOfUse":
                energy_supply = self.__energy_supplies[data["EnergySupply"]]
                # TODO Need to handle error if EnergySupply name is invalid.
                energy_supply_conn_name = name
                energy_supply_conn_names.append(energy_supply_conn_name)
                cold_water_source = self.__cold_water_sources[data["ColdWaterSource"]]
                hw_source = PointOfUse(
                    efficiency=data["efficiency"],
                    energy_supply_conn=energy_supply.connection(name),
                    simulation_time=self.__simtime,
                    cold_feed=cold_water_source,
                    temp_hot_water=data["setpoint_temp"],
                )
            elif hw_source_type == "HIU":
                energy_supply_conn_name = data["HeatSourceWet"] + "_water_heating"
                energy_supply_conn_names.append(energy_supply_conn_name)
                cold_water_source = self.__cold_water_sources[data["ColdWaterSource"]]
                hw_source = self.__heat_sources_wet[
                    data["HeatSourceWet"]
                ].create_service_hot_water_direct(
                    energy_supply_conn_name,
                    data["setpoint_temp"],
                    cold_water_source,
                )
            elif hw_source_type == "HeatBattery":
                energy_supply_conn_name = data["HeatSourceWet"] + "_water_heating"
                energy_supply_conn_names.append(energy_supply_conn_name)
                cold_water_source = self.__cold_water_sources[data["ColdWaterSource"]]
                hw_source = self.__heat_sources_wet[
                    data["HeatSourceWet"]
                ].create_service_hot_water_direct(
                    energy_supply_conn_name, data["setpoint_temp"], cold_water_source
                )
            else:
                raise ValueError(
                    f"Hot water source type: '{hw_source_type}' not recognised for hot water source: '{name}'"
                )
            return hw_source, energy_supply_conn_names

        # Connection for pre-heated and hot water sources
        self.__energy_supply_conn_names_for_hot_water_source = {}
        # Record which hot water source is supplied by each heatsourcewet service
        self.__hotwatersource_name_for_heatsourcewet_service = {}
        # Track the heat sources to ensure heat source object must have unique names
        self.__used_heat_source_names = set()
        # Track pre-heat sources and WWHRS allocated to ensure single allocation only
        # This is required to avoid double-counting of the saving without significant additional
        # book-keeping code or a complete re-conceptualisation of the water heating calculation,
        # to handle an arrangement which is unlikely to occur in practice
        cold_water_sources_already_allocated = set()

        # Processing Pre-heated sources.
        self.__pre_heated_water_sources = {}
        if "PreHeatedWaterSource" in proj_dict:
            preheated_sources = proj_dict["PreHeatedWaterSource"]

            preheated_water_source_dependency_graph = build_preheated_water_source_dependency_graph(
                preheated_sources_dict=preheated_sources,
            )

            try:
                init_order = topological_sort_preheated_water_sources(
                    dependency_graph=preheated_water_source_dependency_graph,
                )
            except ValueError as err:
                raise ValueError(
                    f"PreHeatedWaterSource dependency resolution failed: {err}"
                ) from err

            for name in init_order:
                data = preheated_sources[name]
                (
                    self.__pre_heated_water_sources[name],
                    self.__energy_supply_conn_names_for_hot_water_source[name],
                ) = dict_to_hot_water_source(name, data)

        self.__hot_water_sources = {}

        for name, data in proj_dict["HotWaterSource"].items():
            (
                self.__hot_water_sources[name],
                self.__energy_supply_conn_names_for_hot_water_source[name],
            ) = dict_to_hot_water_source(name, data)

        hw_pipework_dict = proj_dict["HotWaterDemand"]["Distribution"]

        baths = proj_dict.get("HotWaterDemand", {}).get("Bath", {})
        showers = proj_dict.get("HotWaterDemand", {}).get("Shower", {})
        others = proj_dict.get("HotWaterDemand", {}).get("Other", {})

        self.__dhw_demand = DHWDemand(
            showers,
            baths,
            others,
            hw_pipework_dict,
            self.__cold_water_sources,
            self.__wwhrs,
            self.__energy_supplies,
            self.__event_schedules,
            self.__hot_water_sources,
            self.__pre_heated_water_sources,
        )

        # Some systems (e.g. exhaust air heat pumps) may require overventilation
        # so initialise an empty list to hold the names of these systems
        self.__heat_system_names_requiring_overvent = []

        def dict_to_space_heat_system(name, data):
            space_heater_type = data["type"]

            # Setting flag on the existence of a buffer tank in the emitter's loop
            # This is currently only considered in the case of HP as heat source.
            with_buffer_tank = False

            # ElecStorageHeater needs extra controllers
            if space_heater_type == "ElecStorageHeater" and "ControlCharger" in data.keys():
                charge_control = self.__controls[data["ControlCharger"]]

            ctrl = self.__controls[data["Control"]]

            if space_heater_type == "InstantElecHeater":
                energy_supply = self.__energy_supplies[data["EnergySupply"]]
                # TODO Need to handle error if EnergySupply name is invalid.
                energy_supply_conn_name = name
                space_heater = InstantElecHeater(
                    rated_power=data["rated_power"],
                    frac_convective=data["frac_convective"],
                    energy_supply_conn=energy_supply.connection(name),
                    simulation_time=self.__simtime,
                    control=ctrl,
                )
            elif space_heater_type == "ElecStorageHeater":
                energy_supply = self.__energy_supplies[data["EnergySupply"]]
                # TODO Need to handle error if EnergySupply name is invalid.
                energy_supply_conn_name = name
                space_heater = ElecStorageHeater(
                    pwr_in=data["pwr_in"],
                    rated_power_instant=data["rated_power_instant"],
                    storage_capacity=data["storage_capacity"],
                    air_flow_type=enums.AirFlowType(data["air_flow_type"]),
                    frac_convective=data["frac_convective"],
                    fan_pwr=data["fan_pwr"],
                    n_units=data["n_units"],
                    zone=self.__zones[data["Zone"]],
                    energy_supply_conn=energy_supply.connection(name),
                    simulation_time=self.__simtime,
                    control=ctrl,
                    charge_control=charge_control,
                    dry_core_min_output=data["dry_core_min_output"],
                    dry_core_max_output=data["dry_core_max_output"],
                    state_of_charge_init=data["state_of_charge_init"],
                    output_detailed_results=self.__detailed_output_heating_cooling,
                )
            elif space_heater_type == "WetDistribution":
                energy_supply_conn_name = data["HeatSource"]["name"] + "_space_heating: " + name
                heat_source = self.__heat_sources_wet[data["HeatSource"]["name"]]
                if isinstance(heat_source, HeatPump):
                    # For HPs, need to know emitter type for inertia calculations
                    fan_coils = any(
                        True if emitter["wet_emitter_type"] == WetEmitterType.FANCOIL else False
                        for emitter in data["emitters"]
                    )
                    emitter_type = (
                        HeatPumpEmitterType.FAN_COILS
                        if fan_coils
                        else HeatPumpEmitterType.RADIATORS_UFH
                    )

                    # For HPs, checking if there's a buffer tank to inform both the service space heating
                    # and the emitters of its presence.
                    if data["HeatSource"]["name"] in self.__heat_sources_wet_with_buffer_tank:
                        with_buffer_tank = True

                    # If EAHP, feed zone volume into function below
                    volume_heated = self.__total_volume_heated_by_system(name)

                    heat_source_service = heat_source.create_service_space_heating(
                        energy_supply_conn_name,
                        emitter_type,
                        data["HeatSource"]["temp_flow_limit_upper"],
                        data["temp_diff_emit_dsgn"],
                        data["design_flow_temp"],
                        ctrl,
                        volume_heated,
                    )
                    if heat_source.source_is_exhaust_air():
                        # Record heating system as potentially requiring overventilation
                        self.__heat_system_names_requiring_overvent.append(name)

                elif isinstance(heat_source, Boiler):
                    heat_source_service = heat_source.create_service_space_heating(
                        energy_supply_conn_name,
                        ctrl,
                    )
                elif isinstance(heat_source, HeatNetwork):
                    heat_source_service = heat_source.create_service_space_heating(
                        energy_supply_conn_name,
                        ctrl,
                    )
                elif isinstance(heat_source, HeatBatteryPCM):
                    heat_source_service = heat_source.create_service_space_heating(
                        energy_supply_conn_name,
                        ctrl,
                    )
                elif isinstance(heat_source, HeatBatteryDryCore):
                    heat_source_service = heat_source.create_service_space_heating(
                        energy_supply_conn_name,
                        ctrl,
                    )
                else:
                    raise ValueError(f"HeatSource type not recognised for {name}")
                    # TODO Exit just the current case instead of whole program entirely?

                energy_supply_FC = data.get("EnergySupply")
                if energy_supply_FC is not None:
                    energy_supply = self.__energy_supplies[energy_supply_FC]
                    energy_supply_FC_conn_name = "FC_fan " + name
                    energy_supply_FC_conn = energy_supply.connection(energy_supply_FC_conn_name)
                else:
                    energy_supply_FC_conn = None

                space_heater = Emitters(
                    data.get(
                        "thermal_mass"
                    ),  # if thermal mass does not exit in json file return None.
                    data["emitters"],
                    data["pipework"],
                    data["temp_diff_emit_dsgn"],
                    data.get("variable_flow"),
                    data.get("design_flow_rate"),
                    data.get("min_flow_rate"),
                    data.get("max_flow_rate"),
                    data.get("bypass_fraction_recirculated"),  # if does not exit return None
                    heat_source_service,
                    self.__zones[data["Zone"]],
                    self.__external_conditions,
                    data["ecodesign_controller"],
                    data["design_flow_temp"],
                    self.__simtime,
                    self.temp_internal_air_prev_timestep(),  # Air temperature for initialisation of emitters
                    energy_supply_FC_conn,
                    self.__detailed_output_heating_cooling,
                    with_buffer_tank,
                )

            elif space_heater_type == "WarmAir":
                energy_supply_conn_name = data["HeatSource"]["name"] + "_space_heating: " + name
                heat_source = self.__heat_sources_wet[data["HeatSource"]["name"]]
                if isinstance(heat_source, HeatPump):
                    volume_heated = self.__total_volume_heated_by_system(name)
                    space_heater = heat_source.create_service_space_heating_warm_air(
                        energy_supply_conn_name,
                        ctrl,
                        data["frac_convective"],
                        volume_heated,
                    )
                    if heat_source.source_is_exhaust_air():
                        # Record heating system as potentially requiring overventilation
                        self.__heat_system_names_requiring_overvent.append(name)
                else:
                    raise ValueError(f"HeatSource type not recognised for {name}")
                    # TODO Exit just the current case instead of whole program entirely?
            else:
                raise ValueError(
                    f"Space heating system type: '{space_heater_type}' not recognised for {name}"
                )

            return space_heater, energy_supply_conn_name

        # If one or more space heating systems have been provided, add them to the project
        self.__space_heat_systems = {}
        self.__energy_supply_conn_name_for_space_heat_system = {}
        # If no space heating systems have been provided, then skip. This
        # facilitates running the simulation with no heating systems at all
        if "SpaceHeatSystem" in proj_dict:
            for name, data in proj_dict["SpaceHeatSystem"].items():
                # Only initialise systems that are actually used
                h_found = False
                for zone_h_names in self.__heat_system_name_for_zone.values():
                    if name in zone_h_names:
                        h_found = True
                        break
                if h_found:
                    (
                        self.__space_heat_systems[name],
                        self.__energy_supply_conn_name_for_space_heat_system[name],
                    ) = dict_to_space_heat_system(name, data)
                else:
                    logger.warning(
                        f"Warning: SpaceHeatSystem {str(name)} has been defined but is not assigned to any Zone"
                    )

        def dict_to_space_cool_system(name, data) -> tuple[SpaceCoolSystemBase, str]:
            ctrl = self.__controls[data["Control"]]

            cooling_system_type = data["type"]
            if cooling_system_type == "AirConditioning":
                energy_supply = self.__energy_supplies[data["EnergySupply"]]
                # TODO Need to handle error if EnergySupply name is invalid.
                energy_supply_conn_name = name
                cooling_system = AirConditioning(
                    cooling_capacity=data["cooling_capacity"],
                    efficiency=data["efficiency"],
                    frac_convective=data["frac_convective"],
                    energy_supply_conn=energy_supply.connection(name),
                    simulation_time=self.__simtime,
                    control=ctrl,
                )
            else:
                raise ValueError(f"CoolSystem type not recognised for {name}")

            return cooling_system, energy_supply_conn_name

        self.__space_cool_systems = {}
        self.__energy_supply_conn_name_for_space_cool_system = {}
        # If no space cooling systems have been provided, then skip. This
        # facilitates running the simulation with no cooling systems at all
        if "SpaceCoolSystem" in proj_dict:
            for name, data in proj_dict["SpaceCoolSystem"].items():
                # Only initialise systems that are actually used
                c_found = False
                for zone_c_names in self.__cool_system_name_for_zone.values():
                    if name in zone_c_names:
                        c_found = True
                        break
                if c_found:
                    (
                        self.__space_cool_systems[name],
                        self.__energy_supply_conn_name_for_space_cool_system[name],
                    ) = dict_to_space_cool_system(name, data)
                else:
                    logger.warning(
                        f"Warning: SpaceCoolSystem {str(name)} has been defined but is not assigned to any Zone"
                    )

        def dict_to_on_site_generation(name, data) -> OnSiteGenerationBase:
            """Parse dictionary of on site generation data and
            return approprate on site generation object"""
            on_site_generation_type = data["type"]
            if on_site_generation_type == "PhotovoltaicSystem":
                energy_supply = self.__energy_supplies[data["EnergySupply"]]
                # TODO Need to handle error if EnergySupply name is invalid.

                panels = []
                if "panels" in data:
                    for panel in data["panels"]:
                        panels.append(
                            PhotovoltaicPanel(
                                peak_power=panel["peak_power"],
                                ventilation_strategy=panel["ventilation_strategy"],
                                pitch=panel["pitch"],
                                orientation=units.Orientation360(panel["orientation360"]),
                                base_height=panel["base_height"],
                                height=panel["height"],
                                width=panel["width"],
                                shading=panel["shading"],
                            )
                        )
                else:
                    panels.append(
                        PhotovoltaicPanel(
                            peak_power=data["peak_power"],
                            ventilation_strategy=data["ventilation_strategy"],
                            pitch=data["pitch"],
                            orientation=units.Orientation360(data["orientation360"]),
                            base_height=data["base_height"],
                            height=data["height"],
                            width=data["width"],
                            shading=data["shading"],
                        )
                    )

                pv_inverter = Inverter(
                    energy_supply_conn=energy_supply.connection(name),
                    simulation_time=self.__simtime,
                    inverter_peak_power_dc=data["inverter_peak_power_dc"],
                    inverter_peak_power_ac=data["inverter_peak_power_ac"],
                    inverter_is_inside=data["inverter_is_inside"],
                    inverter_type=enums.InverterType(data["inverter_type"]),
                )

                pv_system = PhotovoltaicSystem(
                    ext_cond=self.__external_conditions,
                    simulation_time=self.__simtime,
                    panels=panels,
                    inverter=pv_inverter,
                )
            else:
                raise ValueError(
                    f"On site generation type: '{on_site_generation_type}' not recognised for {name}"
                )
            return pv_system

        self.__on_site_generation = {}
        # If no on site generation have been provided, then skip.
        if "OnSiteGeneration" in proj_dict:
            for name, data in proj_dict["OnSiteGeneration"].items():
                self.__on_site_generation[name] = dict_to_on_site_generation(name, data)

    def total_floor_area(self):
        return self.__total_floor_area

    def __total_volume_heated_by_system(self, heat_system_name):
        return fsum(
            zone.volume()
            for z_name, zone in self.__zones.items()
            if heat_system_name in self.__heat_system_name_for_zone[z_name]
        )

    def calc_HCP(self):
        """Calculate the total heat capacity normalised for floor area"""
        # TODO party walls and solid doors should be exluded according to SAP spec - if party walls are
        # assumed to be ZTU building elements this could be set to zero?

        # Initialise variable
        total_heat_capacity = 0

        # Calculate the total heat capacity and total zone area
        for zone in self.__zones.values():
            total_heat_capacity += zone.total_heat_capacity()

        # Calculate the thermal mass parameter, in kJ / m2 K
        HCP = total_heat_capacity / self.__total_floor_area

        return HCP

    def calc_HLFF(self):
        """Calculate the heat loss form factor, defined as exposed area / floor area"""

        total_heat_loss_area = 0
        for zone in self.__zones.values():
            total_heat_loss_area += zone.total_heat_loss_area()
        HLFF = total_heat_loss_area / self.__total_floor_area
        return HLFF

    def external_conditions(self):
        """Return the external conditions object"""
        return self.__external_conditions

    def __update_temp_internal_air(self):
        # Initialise internal air temperature and total area of all zones
        internal_air_temperature = 0

        # TODO here we are treating overall indoor temperature as average of all zones
        for zone in self.__zones.values():
            internal_air_temperature += zone.temp_internal_air() * zone.volume()

        internal_air_temperature /= self.__total_volume  # average internal temperature
        self.__temp_internal_air_prev = internal_air_temperature

    def temp_internal_air_prev_timestep(self) -> float:
        """Return the volume-weighted average internal air temperature from the previous timestep

        Some parts of the calculation rely on the whole-dwelling internal air
        temperature before it has been calculated for the current timestep, so
        we use the air temperature calculated in the previous timestep as an
        approximation. Note that this returns a stored value rather than
        calculating from the internal air temperature of each Zone object,
        because this function may be called after the temperatures of some Zone
        objects have been updated for the current timestep but before the
        temperatures of other Zone objects have been updated, which would be
        inconsistent.
        """
        return self.__temp_internal_air_prev

    def __calc_internal_gains_buffer_tank(self):
        """Calculate the losses in the buffer tank"""
        internal_gains_buffer_tanks = 0.0
        for h_name in self.__heat_sources_wet_with_buffer_tank:
            internal_gains_buffer_tanks += self.__heat_sources_wet[h_name].buffer_int_gains()

        return internal_gains_buffer_tanks

    def __calc_internal_gains_ductwork(self) -> float:
        """Calculate the losses/gains in the MVHR ductwork, in Watts"""
        temp_outdoor_air = self.__external_conditions.air_temp()
        temp_indoor_air = self.temp_internal_air_prev_timestep()
        return self.__ventilation.calc_internal_gains_ductwork(temp_outdoor_air, temp_indoor_air)

    def __space_heat_internal_gains_for_zone(
        self,
        zone: Zone,
        gains_internal_dhw_on_site_generation: float,
        gains_internal_hb: float,
        internal_gains_ductwork_per_m3: float,
        gains_internal_buffer_tank: float,
    ):
        # Initialise to dhw internal gains split proportionally to zone floor area
        gains_internal_zone = (
            (gains_internal_buffer_tank + gains_internal_dhw_on_site_generation + gains_internal_hb)
            * zone.area()
            / self.__total_floor_area
        )
        for internal_gains_object in self.__internal_gains.values():
            gains_internal_zone += internal_gains_object.total_internal_gain(zone.area())

        # Add total gains from all ventilation ductwork (calculated previously)
        gains_internal_zone += internal_gains_ductwork_per_m3 * zone.volume()

        # Add gains from ventilation fans (also calculates elec demand from fans)
        # TODO Remove the branch on the type of ventilation (find a better way)
        if self.__mech_vents is not None:
            for mech_vent in self.__mech_vents:
                gains_internal_zone += mech_vent.fans(zone.volume(), self.__total_volume)

        return gains_internal_zone

    def __get_heat_cool_systems_for_zone(self, z_name):
        """Look up relevant heating and cooling systems for the specified zone"""
        (
            temp_setpnt_heat_system,
            temp_setpnt_cool_system,
            frac_convective_heat_system,
            frac_convective_cool_system,
        ) = self.__get_setpoints_and_convective_fractions(
            self.__heat_system_name_for_zone[z_name],
            self.__cool_system_name_for_zone[z_name],
        )

        # Sort heating and cooling systems by setpoint (highest first for
        # heating, lowest first for cooling)
        # Note: In the event of two systems having the same setpoint, the one
        #       listed first by the user takes priority. According to the Python
        #       documentation, "sorts are guaranteed to be stable", so this is
        #       the standard behaviour anyway.
        h_name_list_sorted = sorted(
            temp_setpnt_heat_system, key=lambda x: temp_setpnt_heat_system[x], reverse=True
        )
        c_name_list_sorted = sorted(
            temp_setpnt_cool_system, key=lambda x: temp_setpnt_cool_system[x], reverse=False
        )

        return (
            h_name_list_sorted,
            c_name_list_sorted,
            temp_setpnt_heat_system,
            temp_setpnt_cool_system,
            frac_convective_heat_system,
            frac_convective_cool_system,
        )

    def __get_setpoints_and_convective_fractions(self, h_name_list, c_name_list):
        """Look up convective fractions and setpoints for heating/cooling"""
        # Use default setpoints when there is no heat/cool system or
        # there is no setpoint for the current timestep
        frac_convective_heat = {}
        frac_convective_cool = {}
        temp_setpnt_heat = {}
        temp_setpnt_cool = {}
        for h_name in h_name_list:
            if h_name is not None:
                frac_convective_heat[h_name] = self.__space_heat_systems[h_name].frac_convective()
                temp_setpnt_heat[h_name] = self.__space_heat_systems[h_name].temp_setpnt()
            else:
                frac_convective_heat[h_name] = 1.0
                temp_setpnt_heat[h_name] = None
            if temp_setpnt_heat[h_name] is None:
                temp_setpnt_heat[h_name] = temp_setpnt_heat_none

        for c_name in c_name_list:
            if c_name is not None:
                frac_convective_cool[c_name] = self.__space_cool_systems[c_name].frac_convective()
                temp_setpnt_cool[c_name] = self.__space_cool_systems[c_name].temp_setpnt()
            else:
                frac_convective_cool[c_name] = 1.0
                temp_setpnt_cool[c_name] = None
            if temp_setpnt_cool[c_name] is None:
                temp_setpnt_cool[c_name] = temp_setpnt_cool_none

        return temp_setpnt_heat, temp_setpnt_cool, frac_convective_heat, frac_convective_cool

    def __gains_heat_cool(self, delta_t_h, hc_output_convective, hc_output_radiative):
        gains_heat_cool_convective = (
            fsum(hc_output_convective.values()) * units.W_per_kW / delta_t_h
        )
        gains_heat_cool_radiative = fsum(hc_output_radiative.values()) * units.W_per_kW / delta_t_h
        return gains_heat_cool_convective, gains_heat_cool_radiative

    def __calc_air_changes_per_hour(
        self,
        wind_speed,
        wind_direction,
        temp_int_air,
        temp_ext_air,
        R_v_arg,
        R_w_arg,
        initial_p_z_ref_guess,
        reporting_flag,
    ):
        """Calculate the incoming air changes per hour
           intial_p_z_ref_guess is used for calculation in first timestep.
           Later timesteps use the previous timesteps p_z_ref of max and min ACH ,respective to calc.

        arg R_w_arg --
        arg intial_p_z_ref_guess --
        arg reporting_flag --
        """
        if self.__initial_loop:
            self.__internal_pressure_window[reporting_flag] = (
                self.__ventilation.calculate_internal_reference_pressure(
                    initial_p_z_ref_guess,
                    wind_speed,
                    wind_direction,
                    temp_int_air,
                    temp_ext_air,
                    R_v_arg,
                    R_w_arg,
                )
            )
        else:
            self.__internal_pressure_window[reporting_flag] = (
                self.__ventilation.calculate_internal_reference_pressure(
                    self.__internal_pressure_window[reporting_flag],
                    wind_speed,
                    wind_direction,
                    temp_int_air,
                    temp_ext_air,
                    R_v_arg,
                    R_w_arg,
                )
            )

        incoming_air_flow = self.__ventilation.incoming_air_flow(
            self.__internal_pressure_window[reporting_flag],
            wind_speed,
            wind_direction,
            temp_int_air,
            temp_ext_air,
            R_v_arg,
            R_w_arg,
            reporting_flag,
            report_effective_flow_rate=True,
        )
        air_changes_per_hour = incoming_air_flow / self.__total_volume
        return float(air_changes_per_hour)

    def __heat_cool_system_output_min(
        self,
        h_name_list_sorted_zone,
        c_name_list_sorted_zone,
        frac_convective_heat_zone_system,
        frac_convective_cool_zone_system,
        z_name,
    ):
        """Get minimum output for each heating/cooling system in the specified zone"""
        h_output_min = {
            h_name: self.__space_heat_systems[h_name].energy_output_min()
            for h_name in h_name_list_sorted_zone[z_name]
            if h_name is not None
        }
        c_output_min = {
            c_name: self.__space_cool_systems[c_name].energy_output_min()
            for c_name in c_name_list_sorted_zone[z_name]
            if c_name is not None
        }
        hc_output_min = {**h_output_min, **c_output_min, None: 0.0}
        frac_convective_system = {
            **frac_convective_heat_zone_system[z_name],
            **frac_convective_cool_zone_system[z_name],
        }
        hc_output_convective = {
            hc_name: hc_output_min[hc_name] * frac_convective_system[hc_name]
            for hc_name in h_name_list_sorted_zone[z_name] + c_name_list_sorted_zone[z_name]
        }
        hc_output_radiative = {
            hc_name: hc_output_min[hc_name] - hc_output_convective[hc_name]
            for hc_name in h_name_list_sorted_zone[z_name] + c_name_list_sorted_zone[z_name]
        }
        return hc_output_convective, hc_output_radiative, hc_output_min

    def __calc_space_heating(
        self,
        delta_t_h: float,
        gains_internal_dhw_on_site_generation: float,
        gains_internal_hb: float,
    ):
        """Calculate space heating demand, heating system output and temperatures

        Arguments:
        delta_t_h -- calculation timestep, in hours
        gains_internal_dhw_on_site_generation -- internal gains from hot water system and on site generation for this timestep, in W
        gains_internal_hb  -- internal gains from central heat battery systems for this timestep, in W
        """
        wind_speed = self.__external_conditions.wind_speed()
        wind_direction = self.__external_conditions.wind_direction()
        temp_int_air = self.temp_internal_air_prev_timestep()
        temp_ext_air = self.__external_conditions.air_temp()
        if self.__control_VentAdjustMin is not None:
            ach_min = self.__control_VentAdjustMin.setpnt()
        else:
            ach_min = None
        if self.__control_VentAdjustMax is not None:
            ach_max = self.__control_VentAdjustMax.setpnt()
        else:
            ach_max = None

        # Calculate timestep in seconds
        delta_t = delta_t_h * units.seconds_per_hour

        internal_gains_ductwork = self.__calc_internal_gains_ductwork()
        internal_gains_ductwork_per_m3 = internal_gains_ductwork / self.__total_volume

        internal_gains_buffer_tank = self.__calc_internal_gains_buffer_tank()

        # Adjust vent position if required to attempt to meet min or max ach
        self.__R_v_arg = self.__ventilation.find_R_v_arg_within_bounds(
            ach_min,
            ach_max,
            self.__R_v_arg,
            wind_speed,
            wind_direction,
            temp_int_air,
            temp_ext_air,
            R_w_arg=0,
            initial_p_z_ref_guess=0,
            reporting_flag=None,
        )

        # Windows shut
        ach_windows_shut = self.__calc_air_changes_per_hour(
            wind_speed,
            wind_direction,
            temp_int_air,
            temp_ext_air,
            self.__R_v_arg,
            R_w_arg=0,
            initial_p_z_ref_guess=0,
            reporting_flag="min",
        )

        # Windows fully open
        ach_windows_open = self.__calc_air_changes_per_hour(
            wind_speed,
            wind_direction,
            temp_int_air,
            temp_ext_air,
            self.__R_v_arg,
            R_w_arg=1,
            initial_p_z_ref_guess=0,
            reporting_flag="max",
        )

        # To indicate the future loop should involve the p_Z_ref from previous calc
        self.__initial_loop = False

        if self.__sched_req_vent is not None:
            ach_target = self.__sched_req_vent[
                self.__simtime.time_series_idx(
                    self.__req_vent_start_day, self.__req_vent_time_series_step
                )
            ]

            ach_target = max(ach_windows_shut, min(ach_target, ach_windows_open))
        else:
            ach_target = ach_windows_shut

        gains_internal_zone = {}
        gains_solar_zone = {}
        h_name_list_sorted_zone = {}
        c_name_list_sorted_zone = {}
        temp_setpnt_heat_zone_system = {}
        temp_setpnt_cool_zone_system = {}
        frac_convective_heat_zone_system = {}
        frac_convective_cool_zone_system = {}
        ach_cooling_zone = {}
        ach_to_trigger_heating_zone = {}
        internal_air_temp = {}
        operative_temp = {}
        space_heat_demand_zone = {}
        space_cool_demand_zone = {}
        space_heat_provided_system = {}
        space_cool_provided_system = {}
        heat_balance_dict = {}

        # Average supply temperature
        avg_air_supply_temp = self.__external_conditions.air_temp()

        for z_name, zone in self.__zones.items():
            # Calculate internal and solar gains
            gains_internal_zone[z_name] = self.__space_heat_internal_gains_for_zone(
                zone,
                gains_internal_dhw_on_site_generation,
                gains_internal_hb,
                internal_gains_ductwork_per_m3,
                internal_gains_buffer_tank,
            )
            gains_solar_zone[z_name] = zone.gains_solar()

            # Get heating and cooling characteristics for the current zone
            (
                h_name_list_sorted_zone[z_name],
                c_name_list_sorted_zone[z_name],
                temp_setpnt_heat_zone_system[z_name],
                temp_setpnt_cool_zone_system[z_name],
                frac_convective_heat_zone_system[z_name],
                frac_convective_cool_zone_system[z_name],
            ) = self.__get_heat_cool_systems_for_zone(z_name)

            # Calculate space heating demand based on highest-priority systems,
            # assuming no output from any other systems
            (
                space_heat_demand_zone[z_name],
                space_cool_demand_zone[z_name],
                ach_cooling_zone[z_name],
                ach_to_trigger_heating_zone[z_name],
            ) = zone.space_heat_cool_demand(
                delta_t_h,
                temp_ext_air,
                gains_internal_zone[z_name],
                gains_solar_zone[z_name],
                frac_convective_heat_zone_system[z_name][h_name_list_sorted_zone[z_name][0]],
                frac_convective_cool_zone_system[z_name][c_name_list_sorted_zone[z_name][0]],
                temp_setpnt_heat_zone_system[z_name][h_name_list_sorted_zone[z_name][0]],
                temp_setpnt_cool_zone_system[z_name][c_name_list_sorted_zone[z_name][0]],
                avg_air_supply_temp=avg_air_supply_temp,
                ach_windows_open=ach_windows_open,
                ach_target=ach_target,
            )

        # Ventilation required, including for cooling
        is_heating_demand = False
        for demand in space_heat_demand_zone.values():
            if demand > 0.0:
                is_heating_demand = True
        is_cooling_demand = False
        for demand in space_cool_demand_zone.values():
            if demand < 0.0:
                is_cooling_demand = True
        if is_heating_demand:
            # Do not open windows any further than required for ventilation
            # requirement if there is any heating demand in any zone
            ach_cooling = ach_target
        elif is_cooling_demand:
            # Do not open windows any further than required for ventilation
            # requirement if there is any cooling demand in any zone
            ach_cooling = ach_target

            # In this case, will need to recalculate space cooling demand for
            # each zone, this time assuming no window opening for all zones
            # TODO There might be a way to make this more efficient and reduce
            #      the number of times the heat balance solver has to run, but
            #      this would require a wider refactoring of the zone module's
            #      space_heat_cool_demand function
            for z_name, zone in self.__zones.items():
                space_heat_demand_zone[z_name], space_cool_demand_zone[z_name], _, _ = (
                    zone.space_heat_cool_demand(
                        delta_t_h,
                        temp_ext_air,
                        gains_internal_zone[z_name],
                        gains_solar_zone[z_name],
                        frac_convective_heat_zone_system[z_name][
                            h_name_list_sorted_zone[z_name][0]
                        ],
                        frac_convective_cool_zone_system[z_name][
                            c_name_list_sorted_zone[z_name][0]
                        ],
                        temp_setpnt_heat_zone_system[z_name][h_name_list_sorted_zone[z_name][0]],
                        temp_setpnt_cool_zone_system[z_name][c_name_list_sorted_zone[z_name][0]],
                        avg_air_supply_temp=avg_air_supply_temp,
                        ach_cooling=ach_cooling,
                    )
                )
        else:
            # Subject to the above/below limits, take the maximum required window
            # opening from across all the zones
            ach_cooling = max(ach_cooling_zone.values())

            # Do not open windows to an extent where it would cause any zone
            # temperature to fall below the heating setpoint for that zone
            ach_to_trigger_heating_list = [
                x for x in ach_to_trigger_heating_zone.values() if x is not None
            ]
            if len(ach_to_trigger_heating_list) > 0:
                ach_cooling = min(min(ach_to_trigger_heating_list), ach_cooling)

            # Do not reduce air change rate below ventilation requirement even
            # if it would help with temperature regulation
            ach_cooling = max(ach_cooling, ach_target)

        # Calculate heating/cooling system response and temperature achieved in each zone
        for z_name, zone in self.__zones.items():
            # Check for name clash between heating and cooling systems
            heat_cool_names = set(h_name_list_sorted_zone[z_name]).intersection(
                c_name_list_sorted_zone[z_name]
            )
            if any(name is not None for name in heat_cool_names):
                raise ValueError("All heating and cooling systems must have unique names")
            # Initialise system outputs to minimum output for each heating and cooling system
            hc_output_convective, hc_output_radiative, hc_output_min = (
                self.__heat_cool_system_output_min(
                    h_name_list_sorted_zone,
                    c_name_list_sorted_zone,
                    frac_convective_heat_zone_system,
                    frac_convective_cool_zone_system,
                    z_name,
                )
            )

            space_heat_demand_zone_system = {
                h_name: 0.0 for h_name in h_name_list_sorted_zone[z_name]
            }
            space_cool_demand_zone_system = {
                c_name: 0.0 for c_name in c_name_list_sorted_zone[z_name]
            }
            space_heat_provided_zone_system = {
                h_name: 0.0 for h_name in h_name_list_sorted_zone[z_name]
            }
            space_cool_provided_zone_system = {
                c_name: 0.0 for c_name in c_name_list_sorted_zone[z_name]
            }
            h_idx = 0
            c_idx = 0
            while h_idx < len(h_name_list_sorted_zone[z_name]) and c_idx < len(
                c_name_list_sorted_zone[z_name]
            ):
                h_name = h_name_list_sorted_zone[z_name][h_idx]
                c_name = c_name_list_sorted_zone[z_name][c_idx]
                frac_convective_heat = frac_convective_heat_zone_system[z_name][h_name]
                frac_convective_cool = frac_convective_cool_zone_system[z_name][c_name]
                temp_setpnt_heat = temp_setpnt_heat_zone_system[z_name][h_name]
                temp_setpnt_cool = temp_setpnt_cool_zone_system[z_name][c_name]

                # Calculate space heating/cooling demand, accounting for any
                # output from systems (either output already calculated for
                # higher-priority systems, or min output of current or
                # lower-priority systems).
                gains_heat_cool_convective, gains_heat_cool_radiative = self.__gains_heat_cool(
                    delta_t_h, hc_output_convective, hc_output_radiative
                )
                if isclose(gains_heat_cool_convective, 0.0, abs_tol=1e-10) and isclose(
                    gains_heat_cool_radiative, 0.0, abs_tol=1e-10
                ):
                    # If there is no output from any systems, then don't need to
                    # calculate demand again
                    space_heat_demand_zone_system[h_name] = space_heat_demand_zone[z_name]
                    space_cool_demand_zone_system[c_name] = space_cool_demand_zone[z_name]
                else:
                    (
                        space_heat_demand_zone_system[h_name],
                        space_cool_demand_zone_system[c_name],
                        ach_cooling_zone[z_name],
                        _,
                    ) = zone.space_heat_cool_demand(
                        delta_t_h,
                        temp_ext_air,
                        gains_internal_zone[z_name],
                        gains_solar_zone[z_name],
                        frac_convective_heat,
                        frac_convective_cool,
                        temp_setpnt_heat,
                        temp_setpnt_cool,
                        avg_air_supply_temp=avg_air_supply_temp,
                        gains_heat_cool_convective=gains_heat_cool_convective,
                        gains_heat_cool_radiative=gains_heat_cool_radiative,
                        ach_cooling=ach_cooling,
                    )
                    # Space heating/cooling demand calculated above already assumes
                    # minimum output from all systems, so we need to add this on
                    # for the current system. If minimum output is enough to meet
                    # demand, then demand calculated above will be zero. This is
                    # okay because calling the demand_energy function for the
                    # heating/cooling system later with an input of zero will still
                    # result in the minimum output being provided.
                    if space_heat_demand_zone_system[h_name] > 0.0:
                        space_heat_demand_zone_system[h_name] += hc_output_min[h_name]
                    elif space_cool_demand_zone_system[c_name] < 0.0:
                        space_cool_demand_zone_system[c_name] += hc_output_min[c_name]

                # If any heating systems potentially require overventilation,
                # calculate running time and throughput factor for current service
                # based on space heating demand assuming only overventilation
                # required for DHW
                # TODO For now, disable overventilation calculation. Only used
                #      for exhaust air heat pump when conditions are out of
                #      range of test data, which is disallowed for now. May also
                #      be needed for combustion appliances in the future but
                #      none of these have been implemented yet. Calculations
                #      using throughput factor have been removed to simplify
                #      ventilation calculations
                # TODO Note that the commented-out code below has not been
                #      updated to account for minimum output in the case of
                #      multiple heating/cooling systems.
                """
                if h_name in self.__heat_system_names_requiring_overvent:
                    time_running_space, throughput_factor_zone \
                        = self.__space_heat_systems[h_name].running_time_throughput_factor(
                            space_heat_demand_zone_system[h_name],
                            space_heat_running_time_cumulative,
                            )
                    # Add running time for the current space heating service to
                    # the cumulative total
                    space_heat_running_time_cumulative += time_running_space

                    # Combine throughput factors for space and water heating.
                    # Note that any additional ventilation due to water heating
                    # is apportioned to the zones in proportion to their volume,
                    # while any additional ventilation due to space heating is
                    # assigned to the zone that the heating demand originates
                    # from, in order to simplify the calculation. If the
                    # additional ventilation for space heating was assigned on a
                    # whole-dwelling basis, then handling any system requiring
                    # overventilation would require recalculation of demand and
                    # system response for the other zone, if it has already been
                    # calculated. This may mean rolling back (or finding a way
                    # to calculate but not commit) system calculations until all
                    # system calculations have been done for both zones.
                    # TODO Make sure this works with more than one system
                    #      requiring overventilation.
                    throughput_factor_zone_overall \
                        = (throughput_factor_zone - 1.0) \
                        + (throughput_factor_dhw - 1.0) \
                        + 1.0

                # If there is overventilation due to heating or hot water system (e.g.
                # exhaust air heat pump) then recalculate space heating/cooling demand
                # with additional ventilation calculated based on throughput factor
                # based on original space heating demand calculation. Note the
                # additional ventilation throughput is the result of the HP running
                # to satisfy both space and water heating demand but will affect
                # space heating demand only
                # TODO The space heating demand is only recalculated once, rather
                #      than feeding back in to the throughput factor calculation
                #      above to get a further-refined space heating demand. This is
                #      consistent with the approach in SAP 10.2 and keeps the
                #      execution time of the calculation bounded. However, the
                #      merits of iterating over this calculation until converging on
                #      a solution should be considered in the future.
                if throughput_factor_zone_overall > 1.0:
                    # Add additional gains from ventilation fans
                    # TODO Remove the branch on the type of ventilation (find a better way)
                    if self.__ventilation is not None \
                    and not isinstance(self.__ventilation, NaturalVentilation):
                        gains_internal_zone[z_name] \
                            += self.__ventilation.fans(
                                zone.volume(),
                                throughput_factor_zone_overall - 1.0,
                                )
                    space_heat_demand_zone_system[h_name], space_cool_demand_zone_system[c_name], _ \
                        = zone.space_heat_cool_demand(
                            delta_t_h,
                            temp_ext_air,
                            gains_internal_zone[z_name],
                            gains_solar_zone[z_name],
                            frac_convective_heat,
                            frac_convective_cool,
                            temp_setpnt_heat,
                            temp_setpnt_cool,
                            gains_heat_cool_convective = fsum(hc_output_convective.values()) * units.W_per_kW / delta_t_h,
                            gains_heat_cool_radiative = fsum(hc_output_radiative.values()) * units.W_per_kW / delta_t_h,
                            throughput_factor = throughput_factor_zone_overall,
                            )
                    # Need to recalculate space heating demand on zone to account
                    # for extra ventilation, for reporting purposes
                    space_heat_demand_zone[z_name], _, _ \
                        = zone.space_heat_cool_demand(
                            delta_t_h,
                            temp_ext_air,
                            gains_internal_zone[z_name],
                            gains_solar_zone[z_name],
                            frac_convective_heat_zone_system[z_name][h_name_list_sorted_zone[z_name][0]],
                            frac_convective_cool_zone_system[z_name][c_name_list_sorted_zone[z_name][0]],
                            temp_setpnt_heat_zone_system[z_name][h_name_list_sorted_zone[z_name][0]],
                            temp_setpnt_cool_zone_system[z_name][c_name_list_sorted_zone[z_name][0]],
                            throughput_factor = throughput_factor_zone_overall,
                            )
                """

                # Calculate heating/cooling provided
                if space_heat_demand_zone_system[h_name] > 0.0:
                    space_heat_provided_zone_system[h_name] = self.__space_heat_systems[
                        h_name
                    ].demand_energy(
                        space_heat_demand_zone_system[h_name],
                    )
                    hc_output_convective[h_name] = (
                        space_heat_provided_zone_system[h_name] * frac_convective_heat
                    )
                    hc_output_radiative[h_name] = space_heat_provided_zone_system[h_name] * (
                        1.0 - frac_convective_heat
                    )
                    # If heating has been provided, then next iteration of loop
                    # should use next-priority heating system
                    h_idx += 1
                if space_cool_demand_zone_system[c_name] < 0.0:
                    space_cool_provided_zone_system[c_name] = self.__space_cool_systems[
                        c_name
                    ].demand_energy(
                        space_cool_demand_zone_system[c_name],
                    )
                    hc_output_convective[c_name] = (
                        space_cool_provided_zone_system[c_name] * frac_convective_cool
                    )
                    hc_output_radiative[c_name] = space_cool_provided_zone_system[c_name] * (
                        1.0 - frac_convective_cool
                    )
                    # If cooling has been provided, then next iteration of loop
                    # should use next-priority cooling system
                    c_idx += 1

                # Terminate loop if there is no more demand
                if (
                    space_heat_demand_zone_system[h_name] <= 0.0
                    and space_cool_demand_zone_system[c_name] >= 0.0
                ):
                    break

            # Call any remaining heating and cooling systems with zero demand
            for h_name in h_name_list_sorted_zone[z_name][h_idx:]:
                if h_name is not None:
                    space_heat_provided_zone_system[h_name] = self.__space_heat_systems[
                        h_name
                    ].demand_energy(0.0)
                else:
                    space_heat_provided_zone_system[h_name] = 0.0
                hc_output_convective[h_name] = (
                    space_heat_provided_zone_system[h_name] * frac_convective_heat
                )
                hc_output_radiative[h_name] = space_heat_provided_zone_system[h_name] * (
                    1.0 - frac_convective_heat
                )
            for c_name in c_name_list_sorted_zone[z_name][c_idx:]:
                if c_name is not None:
                    space_cool_provided_zone_system[c_name] = self.__space_cool_systems[
                        c_name
                    ].demand_energy(0.0)
                else:
                    space_cool_provided_zone_system[c_name] = 0.0
                hc_output_convective[c_name] = (
                    space_cool_provided_zone_system[c_name] * frac_convective_cool
                )
                hc_output_radiative[c_name] = space_cool_provided_zone_system[c_name] * (
                    1.0 - frac_convective_cool
                )

            # Calculate unmet demand
            self.__unmet_demand(
                delta_t_h,
                temp_ext_air,
                z_name,
                zone,
                gains_internal_zone[z_name],
                gains_solar_zone[z_name],
                temp_setpnt_heat_zone_system[z_name],
                temp_setpnt_cool_zone_system[z_name],
                frac_convective_heat_zone_system[z_name],
                frac_convective_cool_zone_system[z_name],
                h_name_list_sorted_zone[z_name],
                c_name_list_sorted_zone[z_name],
                space_heat_demand_zone[z_name],
                space_cool_demand_zone[z_name],
                hc_output_convective,
                hc_output_radiative,
                ach_windows_open,
                ach_target,
                avg_air_supply_temp,
            )

            # Sum heating gains (+ve) and cooling gains (-ve) and convert from kWh to W
            hc_output_convective_total = fsum(hc_output_convective.values())
            hc_output_radiative_total = fsum(hc_output_radiative.values())
            gains_heat_cool = (
                (hc_output_convective_total + hc_output_radiative_total)
                * units.W_per_kW
                / delta_t_h
            )
            if not isclose(gains_heat_cool, 0.0, abs_tol=1e-10):
                frac_convective = hc_output_convective_total / (
                    hc_output_convective_total + hc_output_radiative_total
                )
            else:
                frac_convective = 1.0

            # Calculate final temperatures achieved
            heat_balance_dict[z_name] = zone.update_temperatures(
                delta_t,
                temp_ext_air,
                gains_internal_zone[z_name],
                gains_solar_zone[z_name],
                gains_heat_cool,
                frac_convective,
                ach_cooling,
                avg_air_supply_temp,
            )
            internal_air_temp[z_name] = zone.temp_internal_air()
            operative_temp[z_name] = zone.temp_operative()

            for h_name in h_name_list_sorted_zone[z_name]:
                if h_name not in space_heat_provided_system.keys():
                    space_heat_provided_system[h_name] = 0.0
                space_heat_provided_system[h_name] += space_heat_provided_zone_system[h_name]
            for c_name in c_name_list_sorted_zone[z_name]:
                if c_name not in space_cool_provided_system.keys():
                    space_cool_provided_system[c_name] = 0.0
                space_cool_provided_system[c_name] += space_cool_provided_zone_system[c_name]

        return (
            gains_internal_zone,
            gains_solar_zone,
            operative_temp,
            internal_air_temp,
            space_heat_demand_zone,
            space_cool_demand_zone,
            space_heat_provided_system,
            space_cool_provided_system,
            internal_gains_ductwork,
            heat_balance_dict,
        )

    def __get_highest_priority_required_system(self, hc_name_list_sorted, space_heatcool_systems):
        """Determine highest-priority system that is in its required heating
        or cooling period (and not just the setback period)

        Arguments:
        hc_name_list_sorted -- list of heating or cooling systems (not combined
                               list), sorted in order of priority
        space_heatcool_systems -- dict of space heating or cooling system objects
                                  (not combined list)
        """
        hc_name_highest_req = None
        for hc_name in hc_name_list_sorted:
            if hc_name is not None and space_heatcool_systems[hc_name].in_required_period():
                hc_name_highest_req = hc_name
                break
        return hc_name_highest_req

    def __unmet_demand(
        self,
        delta_t_h,
        temp_ext_air,
        z_name,
        zone,
        gains_internal,
        gains_solar,
        temp_setpnt_heat_system,
        temp_setpnt_cool_system,
        frac_convective_heat_system,
        frac_convective_cool_system,
        h_name_list_sorted,
        c_name_list_sorted,
        space_heat_demand,
        space_cool_demand,
        hc_output_convective,
        hc_output_radiative,
        ach_max,
        ach_target,
        avg_air_supply_temp,
    ):
        """Calculate how much space heating / cooling demand is unmet"""
        # Note: Use demand calculated based on highest-priority systems
        # Note: Demand is not considered unmet if it is outside the
        #       required heating/cooling period (which does not include
        #       times when the system is on due to setback or advanced
        #       start). If different systems have different required
        #       heating/cooling periods, unmet demand will be based on the
        #       system with the highest setpoint, ignoring any systems that
        #       are not in required periods (e.g. systems that are in
        #       setback or advanced start periods.
        # Note: Need to check that demand is non-zero, to avoid
        #       reporting unmet demand when heating system is absorbing
        #       energy from zone or cooling system is releasing energy
        #       to zone, which may be the case in some timesteps for
        #       systems with significant thermal mass.

        # Determine highest-priority system that is in its required heating
        # or cooling period (and not just the setback period)
        h_name_highest_req = self.__get_highest_priority_required_system(
            h_name_list_sorted,
            self.__space_heat_systems,
        )
        c_name_highest_req = self.__get_highest_priority_required_system(
            c_name_list_sorted,
            self.__space_cool_systems,
        )

        gains_heat = fsum(
            hc_output_convective[h_name] + hc_output_radiative[h_name]
            for h_name in h_name_list_sorted
        )
        gains_cool = fsum(
            hc_output_convective[c_name] + hc_output_radiative[c_name]
            for c_name in c_name_list_sorted
        )
        energy_shortfall_heat = max(0, space_heat_demand - gains_heat)
        energy_shortfall_cool = max(0, -(space_cool_demand - gains_cool))

        if (
            h_name_highest_req is not None
            and space_heat_demand > 0.0
            and energy_shortfall_heat > 0.0
        ) or (
            c_name_highest_req is not None
            and space_cool_demand < 0.0
            and energy_shortfall_cool > 0.0
        ):
            if (
                energy_shortfall_heat > 0.0
                and h_name_highest_req != h_name_list_sorted[0]
                or energy_shortfall_cool > 0.0
                and c_name_highest_req != c_name_list_sorted[0]
            ):
                # If the highest-priority system is not in required heating
                # period, but a lower-priority system is, calculate demand
                # based on the highest-priority system that is in required
                # heating period

                # Handle case where no heating/cooling system is in required
                # period. In this case, there will be no heat output anyway so
                # the convective fraction doesn't matter
                if h_name_highest_req is None:
                    frac_convective_heat = 1.0
                    temp_setpnt_heat = temp_setpnt_heat_none
                else:
                    frac_convective_heat = frac_convective_heat_system[h_name_highest_req]
                    temp_setpnt_heat = temp_setpnt_heat_system[h_name_highest_req]
                if c_name_highest_req is None:
                    frac_convective_cool = 1.0
                    temp_setpnt_cool = temp_setpnt_cool_none
                else:
                    frac_convective_cool = frac_convective_cool_system[c_name_highest_req]
                    temp_setpnt_cool = temp_setpnt_cool_system[c_name_highest_req]

                space_heat_demand_req, space_cool_demand_req, _, _ = zone.space_heat_cool_demand(
                    delta_t_h,
                    temp_ext_air,
                    gains_internal,
                    gains_solar,
                    frac_convective_heat,
                    frac_convective_cool,
                    temp_setpnt_heat,
                    temp_setpnt_cool,
                    avg_air_supply_temp=avg_air_supply_temp,
                    ach_windows_open=ach_max,
                    ach_target=ach_target,
                )
                unmet_demand_heat = max(0, space_heat_demand_req - gains_heat)
                unmet_demand_cool = max(0, -(space_cool_demand_req - gains_cool))
            else:
                # If highest-priority system is in required heating period,
                # use the demand already calculated for the zone
                unmet_demand_heat = energy_shortfall_heat
                unmet_demand_cool = energy_shortfall_cool

            self.__energy_supply_conn_unmet_demand_zone[z_name].demand_energy(
                unmet_demand_heat + unmet_demand_cool,
            )

    def run(self) -> Output:
        """Run the simulation"""
        timestep_array = []
        gains_internal_dict = {}
        gains_solar_dict = {}
        operative_temp_dict = {}
        internal_air_temp_dict = {}
        space_heat_demand_dict = {}
        space_cool_demand_dict = {}
        space_heat_provided_dict = {}
        space_cool_provided_dict = {}
        zone_list = []
        heat_balance_all_dict = {"air_node": {}, "internal_boundary": {}, "external_boundary": {}}
        heat_source_wet_results_dict = {}
        heat_source_wet_results_annual_dict = {}
        emitters_output_dict = {}
        esh_output_dict = {}
        vent_output_list = []
        hot_water_source_results = {}

        for z_name in self.__zones.keys():
            gains_internal_dict[z_name] = []
            gains_solar_dict[z_name] = []
            operative_temp_dict[z_name] = []
            internal_air_temp_dict[z_name] = []
            space_heat_demand_dict[z_name] = []
            space_cool_demand_dict[z_name] = []
            zone_list.append(z_name)
            for hb_name in heat_balance_all_dict.keys():
                heat_balance_all_dict[hb_name][z_name] = {}

        for z_h_names in self.__heat_system_name_for_zone.values():
            for h_name in z_h_names:
                space_heat_provided_dict[h_name] = []

        for z_c_names in self.__cool_system_name_for_zone.values():
            for c_name in z_c_names:
                space_cool_provided_dict[c_name] = []

        list_hot_water_source_names_incl_electric_showers = list(
            self.__hot_water_sources.keys()
        ) + [ELECTRIC_SHOWERS_HWS_NAME]
        hot_water_demand = {
            hws_name: [] for hws_name in list_hot_water_source_names_incl_electric_showers
        }
        hot_water_energy_demand_at_tapping_points = {
            hws_name: [] for hws_name in list_hot_water_source_names_incl_electric_showers
        }
        hot_water_energy_demand_at_hot_water_source = {
            hws_name: [] for hws_name in self.__hot_water_sources.keys()
        }
        hot_water_energy_output = {hws_name: [] for hws_name in self.__hot_water_sources.keys()}
        hot_water_duration = {
            hws_name: [] for hws_name in list_hot_water_source_names_incl_electric_showers
        }
        hot_water_no_events = {
            hws_name: [] for hws_name in list_hot_water_source_names_incl_electric_showers
        }
        hot_water_pipework = {
            hws_name: [] for hws_name in list_hot_water_source_names_incl_electric_showers
        }
        hot_water_primary_pipework = {hws_name: [] for hws_name in self.__hot_water_sources.keys()}
        hot_water_storage_losses = {hws_name: [] for hws_name in self.__hot_water_sources.keys()}
        ductwork_gains_list = []
        self.__initial_loop = True
        self.__internal_pressure_window = {}

        # Loop over each timestep
        for t_idx, t_current, delta_t_h in self.__simtime:
            timestep_array.append(t_current)
            self.__update_temp_internal_air()

            (
                hw_demand_vol,
                hw_duration,
                no_events,
                hw_energy_demand_at_tapping_points,
                hw_energy_demand_at_hot_water_source,
                hw_energy_output,
                pw_losses_total,
                primary_pw_losses,
                storage_losses,
                gains_internal_dhw,
            ) = self.__dhw_demand.calc_water_heating(
                t_idx,
                delta_t_h,
                self.temp_internal_air_prev_timestep(),
                self.__external_conditions.air_temp(),
            )

            gains_internal_dhw_on_site_generation = fsum(gains_internal_dhw.values())

            gains_internal_hb = 0.0
            # Adding heat battery losses to internal gains
            for __, heat_source_wet in self.__heat_sources_wet.items():
                if isinstance(heat_source_wet, HeatBatteryPCM) or isinstance(
                    heat_source_wet, HeatBatteryDryCore
                ):
                    gains_internal_hb += (
                        heat_source_wet.get_battery_losses()
                        * units.W_per_kW
                        / self.__simtime.timestep()
                    )

            # loop through on-site energy generation
            for g_name in self.__on_site_generation.keys():
                pv = self.__on_site_generation[g_name]
                # Get energy produced for the current timestep
                energy_produced, energy_lost = pv.produce_energy()
                # Add the energy lost figure to the internal gains if it is considered inside the building
                if pv.inverter_is_inside():
                    gains_internal_dhw_on_site_generation += (
                        energy_lost * units.W_per_kW / self.__simtime.timestep()
                    )

            (
                gains_internal_zone,
                gains_solar_zone,
                operative_temp,
                internal_air_temp,
                space_heat_demand_zone,
                space_cool_demand_zone,
                space_heat_provided,
                space_cool_provided,
                ductwork_gains,
                heat_balance_dict,
            ) = self.__calc_space_heating(
                delta_t_h, gains_internal_dhw_on_site_generation, gains_internal_hb
            )

            # Perform calculations that can only be done after all heating
            # services have been calculated.
            for system in self.__timestep_end_calcs:
                system.timestep_end()

            for z_name, gains_internal in gains_internal_zone.items():
                gains_internal_dict[z_name].append(gains_internal)

            for z_name, gains_solar in gains_solar_zone.items():
                gains_solar_dict[z_name].append(gains_solar)

            for z_name, temp in operative_temp.items():
                operative_temp_dict[z_name].append(temp)

            for z_name, temp in internal_air_temp.items():
                internal_air_temp_dict[z_name].append(temp)

            for z_name, demand in space_heat_demand_zone.items():
                space_heat_demand_dict[z_name].append(demand)

            for z_name, demand in space_cool_demand_zone.items():
                space_cool_demand_dict[z_name].append(demand)

            for h_name, output in space_heat_provided.items():
                space_heat_provided_dict[h_name].append(output)

            for c_name, output in space_cool_provided.items():
                space_cool_provided_dict[c_name].append(output)

            for z_name, hb_dict in heat_balance_dict.items():
                if hb_dict is not None:
                    for hb_name, gains_losses_dict in hb_dict.items():
                        for (
                            heat_gains_losses_name,
                            heat_gains_losses_value,
                        ) in gains_losses_dict.items():
                            if (
                                heat_gains_losses_name
                                in heat_balance_all_dict[hb_name][z_name].keys()
                            ):
                                heat_balance_all_dict[hb_name][z_name][
                                    heat_gains_losses_name
                                ].append(heat_gains_losses_value)
                            else:
                                heat_balance_all_dict[hb_name][z_name][heat_gains_losses_name] = [
                                    heat_gains_losses_value
                                ]

            def append_dict_vals_to_dict_lists(dest, orig):
                for key in orig.keys():
                    dest[key].append(orig[key])

            append_dict_vals_to_dict_lists(hot_water_demand, hw_demand_vol)
            append_dict_vals_to_dict_lists(
                hot_water_energy_demand_at_tapping_points, hw_energy_demand_at_tapping_points
            )
            append_dict_vals_to_dict_lists(
                hot_water_energy_demand_at_hot_water_source, hw_energy_demand_at_hot_water_source
            )
            append_dict_vals_to_dict_lists(hot_water_energy_output, hw_energy_output)
            append_dict_vals_to_dict_lists(hot_water_duration, hw_duration)
            append_dict_vals_to_dict_lists(hot_water_no_events, no_events)
            append_dict_vals_to_dict_lists(hot_water_pipework, pw_losses_total)
            append_dict_vals_to_dict_lists(hot_water_primary_pipework, primary_pw_losses)
            append_dict_vals_to_dict_lists(hot_water_storage_losses, storage_losses)

            ductwork_gains_list.append(ductwork_gains)

            for _, supply in self.__energy_supplies.items():
                supply.calc_energy_import_export_betafactor()
                supply.calc_energy_import_from_grid_to_battery()
                supply.timestep_end()

            for diverter in self.__diverters:
                diverter.timestep_end()

            for name in self.__smart_appliance_controls.keys():
                self.__smart_appliance_controls[name].update_demand_buffer(t_idx)

            if self.__display_progress:
                progress_bar(t_idx, self.__simtime.total_steps())
                if t_idx + 1 == self.__simtime.total_steps():
                    print("\nRun complete.")

        # Report detailed outputs from heat source wet objects, if requested and available
        if self.__detailed_output_heating_cooling:
            for name, heat_source_wet in self.__heat_sources_wet.items():
                if hasattr(heat_source_wet, "output_detailed_results") and callable(
                    heat_source_wet.output_detailed_results
                ):
                    (
                        heat_source_wet_results_dict[name],
                        heat_source_wet_results_annual_dict[name],
                    ) = heat_source_wet.output_detailed_results(
                        hot_water_energy_output,
                        self.__hotwatersource_name_for_heatsourcewet_service,
                    )

            # Emitter detailed output results are stored with respect to heat_system_name
            for heat_system_name, heat_system in self.__space_heat_systems.items():
                if hasattr(heat_system, "output_emitter_results") and callable(
                    heat_system.output_emitter_results
                ):
                    emitters_output_dict[heat_system_name] = heat_system.output_emitter_results()

            # ESH detailed output results are stored with respect to heat_system_name
            for heat_system_name, heat_system in self.__space_heat_systems.items():
                if hasattr(heat_system, "output_esh_results") and callable(
                    heat_system.output_esh_results
                ):
                    esh_output_dict[heat_system_name] = heat_system.output_esh_results()

            # Detailed ventilation results collected from ventilation class function
            if hasattr(self.__ventilation, "output_vent_results") and callable(
                self.__ventilation.output_vent_results
            ):
                vent_output_list = self.__ventilation.output_vent_results()

            if self.__hot_water_sources:
                for name, hot_water_source in self.__hot_water_sources.items():
                    # Detailed output results collected from storage tank class function
                    if hasattr(hot_water_source, "output_results") and callable(
                        hot_water_source.output_results
                    ):
                        hot_water_source_results[name] = hot_water_source.output_results()

        # Return results from all energy supplies
        results_totals = {}
        results_end_user = {}
        energy_import = {}
        energy_export = {}
        grid_to_consumption = {}
        generation_to_grid = {}
        energy_generated_consumed = {}
        energy_to_storage = {}
        energy_from_storage = {}
        storage_from_grid = {}
        battery_state_of_charge = {}
        energy_diverted = {}
        betafactor = {}
        for name, supply in self.__energy_supplies.items():
            results_totals[name] = supply.results_total()
            results_end_user[name] = supply.results_by_end_user()
            energy_import[name] = supply.get_energy_import()
            energy_export[name] = supply.get_energy_export()
            grid_to_consumption[name] = supply.get_grid_to_consumption()
            generation_to_grid[name] = supply.get_energy_export_from_generation()
            energy_generated_consumed[name] = supply.get_energy_generated_consumed()
            (
                energy_to_storage[name],
                energy_from_storage[name],
                storage_from_grid[name],
                battery_state_of_charge[name],
            ) = supply.get_energy_to_from_battery()
            energy_diverted[name] = supply.get_energy_diverted()
            betafactor[name] = supply.get_beta_factor()

        dhw_cop_dict = self.__heat_cool_cop(
            hot_water_energy_output,
            results_end_user,
            self.__energy_supply_conn_names_for_hot_water_source,
        )
        heat_cop_dict = self.__heat_cool_cop(
            space_heat_provided_dict,
            results_end_user,
            self.__energy_supply_conn_name_for_space_heat_system,
        )
        cool_cop_dict = self.__heat_cool_cop(
            space_cool_provided_dict,
            results_end_user,
            self.__energy_supply_conn_name_for_space_cool_system,
        )

        output_core = OutputCore(
            timestep_array=timestep_array,
            results_totals=results_totals,
            results_end_user=results_end_user,
            energy_import=energy_import,
            energy_export=energy_export,
            grid_to_consumption=grid_to_consumption,
            generation_to_grid=generation_to_grid,
            energy_generated_consumed=energy_generated_consumed,
            energy_to_storage=energy_to_storage,
            energy_from_storage=energy_from_storage,
            storage_from_grid=storage_from_grid,
            battery_state_of_charge=battery_state_of_charge,
            energy_diverted=energy_diverted,
            beta_factor=betafactor,
            zone_data=OutputZoneData(
                internal_gains=gains_internal_dict,
                solar_gains=gains_solar_dict,
                operative_temp=operative_temp_dict,
                internal_air_temp=internal_air_temp_dict,
                space_heat_demand=space_heat_demand_dict,
                space_cool_demand=space_cool_demand_dict,
            ),
            zone_list=zone_list,
            heating_cooling_system=OutputHeatingCoolingSystem(
                heating_system_output=space_heat_provided_dict,
                cooling_system_output=space_cool_provided_dict,
            ),
            hot_water_systems=OutputHotWaterSystems(
                demand=hot_water_demand,
                energy_demand_at_hot_water_source=hot_water_energy_demand_at_hot_water_source,
                energy_demand_at_tapping_points=hot_water_energy_demand_at_tapping_points,
                duration=hot_water_duration,
                events_count=hot_water_no_events,
                losses_pipework=hot_water_pipework,
                losses_primary_pipework=hot_water_primary_pipework,
                losses_storage=hot_water_storage_losses,
            ),
            cop=OutputCOP(
                space_heating_system=heat_cop_dict,
                space_cooling_system=cool_cop_dict,
                hot_water_system=dhw_cop_dict,
            ),
            ductwork_gains=ductwork_gains_list,
            heat_balance_all=heat_balance_all_dict,  # TODO could be output object too fixed keys...
            heat_source_wet_results=heat_source_wet_results_dict,
            heat_source_wet_results_annual=heat_source_wet_results_annual_dict,
            hot_water_source_results=hot_water_source_results,
            emitters=emitters_output_dict,
            electric_storage_heaters=esh_output_dict,
            ventilation=vent_output_list,
        )

        return Output(
            static=self.__calculate_output_static(),
            core=output_core,
            summary=self.__calculate_output_summary(output_core),
            metadata=OutputMetadata(hem_core_version=importlib.metadata.version("hem-core")),
        )

    def __heat_cool_cop(
        self,
        energy_provided_dict,
        results_end_user,
        energy_supply_conn_name_for_space_hc_system,
    ):
        """Calculate overall CoP over calculation period for each heating and cooling system"""
        # Loop over heating systems, get energy output and input, and calculate CoP
        hc_output_overall = {}
        hc_input_overall = {}
        cop_dict = {}
        for hc_name, hc_output in energy_provided_dict.items():
            if hc_name is None:
                continue
            # Take absolute value because cooling system output is reported as a negative value
            hc_output_overall[hc_name] = abs(fsum(hc_output))
            hc_input_overall[hc_name] = 0.0
            energy_supply_conn_names = energy_supply_conn_name_for_space_hc_system[hc_name]
            if not isinstance(energy_supply_conn_names, list):
                energy_supply_conn_names = [energy_supply_conn_names]
            for fuel_name, fuel_summary in results_end_user.items():
                if fuel_name in ("_unmet_demand", "_energy_from_environment"):
                    continue
                for conn_name, energy_cons in fuel_summary.items():
                    if conn_name in energy_supply_conn_names:
                        hc_input_overall[hc_name] += fsum(energy_cons)

            if hc_input_overall[hc_name] > 0:
                cop_dict[hc_name] = hc_output_overall[hc_name] / hc_input_overall[hc_name]
            else:
                # Replaced with "DIV/0" in the output CSVs by write_core_output_file_summary in hem.py
                cop_dict[hc_name] = None

        return cop_dict

    def __calculate_output_static(self) -> OutputStatic:
        heat_trans_coeff, heat_loss_param, HTC_dict, HLP_dict = calc_HTC_HLP(
            # Use original deep copy, as init_resistance_or_uvalue() will add u_value & r_c.
            self.__project_dict_original
        )

        heat_capacity_param = self.calc_HCP()
        heat_loss_form_factor = self.calc_HLFF()

        return OutputStatic(
            heat_transfer_coefficient=heat_trans_coeff,
            heat_loss_param=heat_loss_param,
            heat_capacity_param=heat_capacity_param,
            heat_loss_form_factor=heat_loss_form_factor,
            temperature_air_internal=self.__project_dict_original["temp_internal_air_static_calcs"],
            temperature_air_external=self.external_conditions().air_temp_annual_daily_average_min(),
        )

    def __calculate_output_summary(self, output_core: OutputCore) -> OutputSummary:
        energy_supply_stats: dict[str, OutputSummaryEnergySupply] = {}
        for key in output_core.results_end_user.keys():
            total_generated = 0
            total_consumed = 0
            for arr in output_core.results_end_user[key].values():
                sum_arr = fsum(arr)
                if sum_arr < 0:
                    total_generated += abs(sum_arr)
                else:
                    total_consumed += sum_arr
            grid_to_consumption = fsum(output_core.grid_to_consumption[key])
            generation_to_grid = abs(fsum(output_core.generation_to_grid[key]))
            gen_to_storage = fsum(output_core.energy_to_storage[key])
            storage_to_consumption = abs(fsum(output_core.energy_from_storage[key]))
            gen_to_diverter = fsum(output_core.energy_diverted[key])
            total_gross_import = fsum(output_core.energy_import[key])
            total_gross_export = fsum(output_core.energy_export[key])

            total_energy_into_battery = gen_to_storage + fsum(output_core.storage_from_grid[key])
            if total_energy_into_battery > 0.0:
                storage_eff = storage_to_consumption / total_energy_into_battery
            else:
                storage_eff = None  # TODO map to 'DIV/0'

            energy_supply_stats[key] = OutputSummaryEnergySupply(
                generation=total_generated,
                consumption=total_consumed,
                generation_to_consumption=sum(output_core.energy_generated_consumed[key]),
                generation_to_grid=generation_to_grid,
                grid_to_consumption=grid_to_consumption,
                net_import=total_gross_import + total_gross_export,
                generation_to_storage=gen_to_storage,
                storage_to_consumption=storage_to_consumption,
                grid_to_storage=abs(fsum(output_core.storage_from_grid[key])),
                generation_to_diverter=gen_to_diverter,
                storage_efficiency=storage_eff,
                total_gross_import=total_gross_import,
                total_gross_export=total_gross_export,
            )

        # Delivered energy by end-use and by fuel
        # TODO: Ensure end_uses not consuming fuel directly are filtered out on this report
        delivered_energy_dict: dict[str, dict[str, float]] = {"total": {"total": 0.0}}
        for fuel, end_uses in output_core.results_end_user.items():
            # TODO are these keys EnergySupplyType ? Why hot water source names too?
            if fuel not in ["_unmet_demand"] + list(self.__hot_water_sources.keys()):
                delivered_energy_dict[fuel] = {}
                delivered_energy_dict[fuel]["total"] = 0.0
                for end_use, delivered_energy in end_uses.items():
                    sum_delivered_energy = fsum(delivered_energy)
                    if sum_delivered_energy > 0 or isclose(
                        sum_delivered_energy, 0.0, abs_tol=1e-10
                    ):
                        delivered_energy_dict[fuel][end_use] = fsum(delivered_energy)
                        delivered_energy_dict[fuel]["total"] += fsum(delivered_energy)
                        if end_use not in delivered_energy_dict["total"].keys():
                            delivered_energy_dict["total"][end_use] = fsum(delivered_energy)
                        else:
                            delivered_energy_dict["total"][end_use] += fsum(delivered_energy)
                        delivered_energy_dict["total"]["total"] += fsum(delivered_energy)

        hot_water_demand_daily_75th_percentile_dict = {}
        for hws_name in self.__hot_water_sources.keys():
            daily_hw_demand = units.convert_profile_to_daily(
                output_core.hot_water_systems.energy_demand_at_hot_water_source[hws_name],
                self.__project_input.simulation_time.step,
            )
            hot_water_demand_daily_75th_percentile_dict[hws_name] = np.percentile(
                daily_hw_demand, 75
            )

        space_heat_demand_total = fsum(
            fsum(data) for data in output_core.zone_data.space_heat_demand.values()
        )
        space_cool_demand_total = fsum(
            fsum(data) for data in output_core.zone_data.space_cool_demand.values()
        )

        return OutputSummary(
            total_floor_area=self.__total_floor_area,
            space_heat_demand_total=space_heat_demand_total,
            space_cool_demand_total=space_cool_demand_total,
            electricity_peak_consumption=self.__calculate_peak_electricity_consumption(output_core),
            delivered_energy=delivered_energy_dict,
            energy_supply=energy_supply_stats,
            hot_water_demand_daily_75th_percentile=hot_water_demand_daily_75th_percentile_dict,
        )

    def __calculate_peak_electricity_consumption(
        self, output_core: OutputCore
    ) -> OutputSummaryPeakElectricityConsumption:
        """
        Finds the peak electricity consumption from the simulation output.
        """
        # Initialize the SimulationTime object
        timestep_to_date: dict[float, datetime] = {}
        # Set the base for any non-leap year
        base_time = datetime(year=2023, month=1, day=1, hour=0)
        # The step must reflect hour or half hour in the year (hour 0 to hour 8759)
        # Starts on the start timestep.
        step = self.__project_input.simulation_time.start
        for hours in output_core.timestep_array:
            timestep_to_date[step] = base_time + timedelta(hours=hours)
            step += 1

        # Get peak electricity consumption, and when it happens.
        # Initialize the SimulationTime object
        start_timestep = self.__project_input.simulation_time.start
        stepping = self.__project_input.simulation_time.step

        # Get Energy Supply objects with fuel type 'electricity'.
        electricity_keys = [
            key
            for key, value in self.__project_input.energy_supply.items()
            if value.fuel == enums.FuelType.ELECTRICITY
        ]
        # Calculate net import per timestep by adding gross import and export figures.
        # Add because export figures already negative.
        net_import_per_timestep = [
            fsum(
                output_core.energy_import[key][i] + output_core.energy_export[key][i]
                for key in electricity_keys
            )
            for i in range(len(output_core.timestep_array))
        ]

        # Find peak electricity consumption
        peak_elec_consumption = max(net_import_per_timestep)
        index_peak_elec_consumption = net_import_per_timestep.index(peak_elec_consumption)
        # must reflect hour or half hour in the year (hour 0 to hour 8759)
        # to work with the dictionary below timestep_to_date
        # hence + start_timestep
        peak_step = index_peak_elec_consumption + start_timestep
        peak_datetime = timestep_to_date[peak_step]

        return OutputSummaryPeakElectricityConsumption(
            peak=peak_elec_consumption,
            index=index_peak_elec_consumption,
            month=peak_datetime.month,
            day=peak_datetime.day,
            hour=(peak_step % (24 / stepping)) * stepping,
        )
