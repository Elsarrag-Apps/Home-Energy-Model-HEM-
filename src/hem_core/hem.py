#!/usr/bin/env python3

"""
This module provides the entry point to the program and defines the command-line interface.
"""

# Standard library imports
import argparse
import calendar
import csv
import importlib.metadata
import json
import logging
import math
import os
import platform
import re
import shutil
import sys
import warnings
from enum import StrEnum
from pathlib import Path
from traceback import print_exc
from typing import Any, List

# Third-party imports
import numpy as np
from pydantic import ValidationError

# Local imports
import hem_core.units as units
from hem_core.input_output.input import Input, StrictBaseModel
from hem_core.input_output.input import StorageTank as InputStorageTank
from hem_core.input_output.output import (
    Output,
    OutputEmitters,
    OutputHotWaterSystems,
    OutputStatic,
    OutputZoneData,
)
from hem_core.input_output.read_weather_file import (
    cibse_weather_data_to_dict,
    epw_weather_data_to_dict,
)
from hem_core.log_config import setup_logging
from hem_core.project import Project

logger = logging.getLogger(__name__)

# Ensure numpy errors get raised properly
# np.seterr('raise')


class OutputFormat(StrEnum):
    JSON = "json"
    CSV = "csv"


class CsvWriter:
    def __init__(self, f):
        self.writer = csv.writer(f)

    def writerow(self, row: list):
        def format_value(v):
            if type(v) in (float, np.float64):
                if math.isclose(v, 0, abs_tol=1e-10):
                    v = 0.0
                else:
                    # Round any floating point numbers to 10 significant figures
                    v = float(f"{v:.10g}")
            return v

        self.writer.writerow(map(format_value, row))

    def writerows(self, rows: List[list]):
        for row in rows:
            self.writerow(row)


def validate_json_input(project_dict: dict[str, Any], permissive_validation: bool) -> Input:
    """
    Validate the project dictionary against the Input schema.

    Args:
        project_dict: The loaded JSON project dictionary
        permissive_validation: Whether to allow extra fields
    Returns:
        Input
    Raises:
        ValidationError: If validation fails
    """
    if permissive_validation:
        for sub_cls in StrictBaseModel.__subclasses__():
            sub_cls.model_config["extra"] = "allow"
            sub_cls.model_rebuild(force=True)

    input = Input.model_validate(project_dict)
    return input


def run_project_from_input_file(
    input_file: Path,
    external_conditions_dict: dict[str, Any] | None,
    output_formats: list[OutputFormat] | None,
    heat_balance: bool,
    detailed_output_heating_cooling: bool,
    use_fast_solver: bool,
    tariff_data_filename: Path | None,
    display_progress: bool,
    skip_validation: bool = False,
):
    if not input_file.exists():
        logger.error("Error: Input file does not exist!︝")
        return
    logger.info(input_file)

    project_name = input_file.stem
    with open(input_file) as file:
        project_dict = json.load(file)

    try:
        project_input, output = run_project(
            project_dict=project_dict,
            permissive_validation=skip_validation,
            external_conditions_dict=external_conditions_dict,
            heat_balance=heat_balance,
            detailed_output_heating_cooling=detailed_output_heating_cooling,
            use_fast_solver=use_fast_solver,
            tariff_data_filename=tariff_data_filename,
            display_progress=display_progress,
        )
    except ValidationError as e:
        exception_text = f"""
            ✗ JSON validation failed for {input_file}
            Use --permissive-json to allow extra fields.
            """
        raise RuntimeError(exception_text) from e

    if output_formats is not None:
        output_path = input_file.parent / f"{project_name}__results"
        output_path.mkdir(exist_ok=True)

        write_project_outputs(
            output=output,
            project_name=project_name,
            project_input=project_input,
            output_path=output_path,
            output_formats=output_formats,
            heat_balance=heat_balance,
            detailed_output_heating_cooling=detailed_output_heating_cooling,
        )
        if OutputFormat.JSON in output_formats:
            # Copy the input file to the output path
            shutil.copy2(input_file, output_path)


def run_project(
    project_dict: dict[str, Any],
    permissive_validation: bool = False,
    external_conditions_dict: dict[str, Any] | None = None,
    heat_balance: bool = False,
    detailed_output_heating_cooling: bool = False,
    use_fast_solver: bool = True,
    tariff_data_filename: Path | None = None,
    display_progress: bool = False,
) -> tuple[Input, Output]:
    project_input = validate_json_input(
        project_dict=project_dict, permissive_validation=permissive_validation
    )
    logger.info("✓ JSON validation passed")

    if external_conditions_dict is None:
        if not project_input.external_conditions.are_all_fields_set():
            logger.error(
                "No weather data found. Please provide a weather file or complete weather data in the input file."
            )
            exit(1)

    if external_conditions_dict is not None:
        # Note: Shading segments are an assessor input regardless, so save them
        # before overwriting the ExternalConditions and re-insert after
        # Check if shading_segments exists in the current ExternalConditions
        shading_segments = project_dict["ExternalConditions"].get("shading_segments")
        project_dict["ExternalConditions"] = external_conditions_dict
        if shading_segments:
            project_dict["ExternalConditions"]["shading_segments"] = shading_segments

    project = Project(
        proj_dict=project_dict,
        project_input=project_input,
        print_heat_balance=heat_balance,
        detailed_output_heating_cooling=detailed_output_heating_cooling,
        use_fast_solver=use_fast_solver,
        tariff_data_filename=tariff_data_filename,
        display_progress=display_progress,
    )

    # Run project
    output = project.run()

    return project_input, output


def write_project_outputs(
    output: Output,
    project_name: str,
    project_input: Input,
    output_path: Path,
    output_formats: list[OutputFormat] | None,
    heat_balance: bool,
    detailed_output_heating_cooling: bool,
    output_file_run_name: str = "core",
):
    output_filename_prefix = _output_filename_prefix(
        output_file_run_name=output_file_run_name, project_name=project_name
    )

    if output_formats is not None and OutputFormat.JSON in output_formats:
        write_output_json_file(
            path=output_path / f"{output_filename_prefix}output.json",
            output=output,
        )

    if output_formats is not None and OutputFormat.CSV in output_formats:
        write_static_output_file(
            path=output_path / f"{output_filename_prefix}results_static.csv",
            output=output.static,
        )

        write_core_output_file(
            path=output_path / f"{output_filename_prefix}results.csv",
            output=output,
        )

        write_core_output_file_summary(
            path=output_path / f"{output_filename_prefix}results_summary.csv",
            output=output,
            project_input=project_input,
        )

        if heat_balance:
            for hb_name, hb_dict in output.core.heat_balance_all.items():
                write_heat_balance_output_file(
                    heat_balance_output_file=output_path
                    / f"{output_filename_prefix}results_heat_balance_{hb_name}.csv",
                    timestep_array=output.core.timestep_array,
                    hour_per_step=project_input.simulation_time.step,
                    heat_balance_dict=hb_dict,
                )

        if detailed_output_heating_cooling:
            for (
                heat_source_wet_name,
                heat_source_wet_results,
            ) in output.core.heat_source_wet_results.items():
                write_heat_source_wet_output_file(
                    output_file=output_path
                    / f"{output_filename_prefix}results_heat_source_wet__{heat_source_wet_name}.csv",
                    timestep_array=output.core.timestep_array,
                    heat_source_wet_results=heat_source_wet_results,
                )
            for (
                heat_source_wet_name,
                heat_source_wet_results_annual,
            ) in output.core.heat_source_wet_results_annual.items():
                write_heat_source_wet_summary_output_file(
                    output_file=output_path
                    / f"{output_filename_prefix}results_heat_source_wet_summary__{heat_source_wet_name}.csv",
                    heat_source_wet_results_annual=heat_source_wet_results_annual,
                )
            # Function call to write detailed ventilation results
            vent_output_file = output_path / f"{output_filename_prefix}ventilation_results.csv"
            write_ventilation_detailed_output(
                vent_output_file=vent_output_file, vent_output_list=output.core.ventilation
            )
            for (
                hot_water_source_name,
                hot_water_source_results,
            ) in output.core.hot_water_source_results.items():
                escaped_name = re.sub(r" ", r"_", hot_water_source_name)
                write_hot_water_source_output_file(
                    output_file=output_path
                    / f"{output_filename_prefix}results_hot_water_source__{escaped_name}.csv",
                    hot_water_source_results=hot_water_source_results,
                )

        # Create a file for emitters detailed output and write
        if detailed_output_heating_cooling:
            write_emitters_detailed_output_file(
                output_path=output_path,
                filename_prefix=output_filename_prefix + "results_emitters_",
                emitters_output_dict=output.core.emitters,
            )

        # Create a file for esh detailed output and write
        if detailed_output_heating_cooling:
            write_esh_detailed_output_file(
                output_path=output_path,
                filename_prefix=f"{output_filename_prefix}results_esh_",
                esh_output_dict=output.core.electric_storage_heaters,
            )


def _output_filename_prefix(output_file_run_name: str, project_name: str) -> str:
    return f"{project_name}__{output_file_run_name}__"


def safe_path(path: Path) -> Path:
    r"""Adds \\?\ to the beginning of absolute paths in Windows to allow access to paths over 260 characters"""
    path = path.resolve()

    if platform.system() == "Windows":
        path_str = str(path)
        if path_str.startswith("\\\\?\\"):
            # Already added. Return unmodified.
            return path
        if path_str.startswith("\\\\"):
            # Network share path. Return UNC path.
            return Path("\\\\?\\UNC" + path_str[1:])
        return Path("\\\\?\\" + path_str)
    return path


def write_static_output_file(
    path: Path,
    output: OutputStatic,
):
    # Note: need to specify newline='' below, otherwise an extra carriage return
    # character is written when running on Windows
    with open(safe_path(path), "w", newline="") as f:
        writer = CsvWriter(f)
        writer.writerow(["Heat transfer coefficient", "W / K", output.heat_transfer_coefficient])
        writer.writerow(["Heat loss parameter", "W / m2.K", output.heat_loss_param])
        writer.writerow(["Heat capacity parameter", "kJ / m2.K", output.heat_capacity_param])
        writer.writerow(["Heat loss form factor", "", output.heat_loss_form_factor])
        writer.writerow(["Assumptions used for HTC/HLP calculation:"])
        writer.writerow(["Internal air temperature", "Celsius", output.temperature_air_internal])
        writer.writerow(["External air temperature", "Celsius", output.temperature_air_external])


def write_heat_balance_output_file(
    heat_balance_output_file: Path,
    timestep_array: list[float],
    hour_per_step: float,
    heat_balance_dict: dict[str, dict[str, list[float]]],
):
    # Note: need to specify newline='' below, otherwise an extra carriage return
    # character is written when running on Windows
    with open(safe_path(heat_balance_output_file), "w", newline="") as f:
        writer = CsvWriter(f)
        headings = ["Timestep"]
        units_row = ["index"]
        rows: list[Any] = [""]

        headings_annual = [""]
        units_annual = [""]
        annual_totals: list[Any] = [""]

        nbr_of_zones = 0
        for z_name, heat_loss_gain_dict in heat_balance_dict.items():
            for heat_loss_gain_name in heat_loss_gain_dict.keys():
                headings.append(f"{z_name}: {heat_loss_gain_name}")
                units_row.append("[W]")
            nbr_of_zones += 1

        for z_name, heat_loss_gain_dict in heat_balance_dict.items():
            annual_totals = [0] * (len(heat_loss_gain_dict.keys()) * nbr_of_zones)
            annual_totals.insert(
                0, ""
            )  # TODO this is overwritten for each zone when its only needed once
            for heat_loss_gain_name in heat_loss_gain_dict.keys():
                headings_annual.append(f"{z_name}: total {heat_loss_gain_name}")
                units_annual.append("[kWh]")

        for t_idx in range(len(timestep_array)):
            row: list[Any] = [t_idx]
            annual_totals_index = 1
            for heat_loss_gain_dict in heat_balance_dict.values():
                for heat_loss_gain_name in heat_loss_gain_dict.keys():
                    row.append(heat_loss_gain_dict[heat_loss_gain_name][t_idx])
                    annual_totals[annual_totals_index] += (
                        heat_loss_gain_dict[heat_loss_gain_name][t_idx]
                        * hour_per_step
                        / units.W_per_kW
                    )
                    annual_totals_index += 1
            rows.append(row)

        writer.writerow(headings_annual)
        writer.writerow(units_annual)
        writer.writerow(annual_totals)
        writer.writerow([""])
        writer.writerow(headings)
        writer.writerow(units_row)
        writer.writerows(rows)


def write_heat_source_wet_output_file(
    output_file: Path, timestep_array: list, heat_source_wet_results: dict
):
    # Repeat column headings for each service
    col_headings = ["Timestep"]
    col_units_row = ["count"]
    columns = {}
    for service_name, service_results in heat_source_wet_results.items():
        columns[service_name] = [col for col in service_results.keys()]
        col_headings += [
            f"{service_name}: {col_heading}" for col_heading, _ in columns[service_name]
        ]
        col_units_row += [col_unit for _, col_unit in columns[service_name]]

    # Note: need to specify newline='' below, otherwise an extra carriage return
    # character is written when running on Windows
    with open(safe_path(output_file), "w", newline="") as f:
        writer = CsvWriter(f)

        # Write column headings and units
        writer.writerow(col_headings)
        writer.writerow(col_units_row)

        # Write rows
        for t_idx in range(0, len(timestep_array)):
            row = [t_idx]
            for service_name, service_results in heat_source_wet_results.items():
                row += [service_results[col][t_idx] for col in columns[service_name]]
            writer.writerow(row)


def write_heat_source_wet_summary_output_file(
    output_file: Path, heat_source_wet_results_annual: dict[str, float | dict]
):
    # Note: need to specify newline='' below, otherwise an extra carriage return
    # character is written when running on Windows
    with open(safe_path(output_file), "w", newline="") as f:
        writer = CsvWriter(f)

        for service_name, service_results in heat_source_wet_results_annual.items():
            writer.writerow([service_name])
            if isinstance(service_results, dict):
                for name, value in service_results.items():
                    writer.writerow([name[0], name[1], value])
                writer.writerow("")  # type: ignore[reportArgumentType]


def write_emitters_detailed_output_file(
    output_path: Path,
    filename_prefix: str,
    emitters_output_dict: dict[str, dict[int, OutputEmitters]],
):
    """The function writes detailed emitter output results in csv format.
    Specific file is created for every heat_system"""
    for emitter, emitter_output in emitters_output_dict.items():
        # Create CSV file with specified emitter name
        with open(
            safe_path(output_path / f"{filename_prefix}_{emitter}.csv"), "w", newline=""
        ) as file:
            writer = CsvWriter(file)
            headings = [
                "timestep",
                "demand_energy",
                "temp_emitter_req",
                "time_before_heating_start",
                "energy_provided_by_heat_source",
                "temp_emitter",
                "temp_emitter_max",
                "energy_released_from_emitters",
                "temp_flow_target",
                "temp_return_target",
                "temp_emitter_max_is_final_temp",
                "energy_req_from_heat_source",
                "fan_energy_kWh",
            ]
            units_row = [
                "[count]",
                "[kWh]",
                "[Celsius]",
                "[hours]",
                "[kWh]",
                "[Celsius]",
                "[Celsius]",
                "[kWh]",
                "[Celsius]",
                "[Celsius]",
                "[Boolean]",
                "[kWh]",
                "[kWh]",
            ]
            writer.writerow(headings)
            writer.writerow(units_row)
            for emitter_results in emitter_output.values():
                writer.writerow(list(emitter_results.__dict__.values()))


def write_esh_detailed_output_file(output_path: Path, filename_prefix: str, esh_output_dict: dict):
    """The function writes detailed esh output results in csv format.
    Specific file is created for every heat_system"""
    for esh, esh_output in esh_output_dict.items():
        # Create CSV file with specified emitter name
        specific_file_name = f"{filename_prefix}_{esh}.csv"

        with open(safe_path(output_path / specific_file_name), "w", newline="") as f:
            writer = CsvWriter(f)
            headings = [
                "timestep",
                "n_units",
                "demand_energy",
                "energy_delivered",
                "energy_instant",
                "energy_charged",
                "energy_for_fan",
                "state_of_charge",
                "final_soc_ivp",
                "time_used_max",
            ]
            units_row = [
                "[count]",
                "[count]",
                "[kWh]",
                "[kWh]",
                "[kWh]",
                "[kWh]",
                "[kWh]",
                "[ratio]",
                "[ratio]",
                "[hours]",
            ]
            writer.writerow(headings)
            writer.writerow(units_row)
            for esh_results in esh_output.values():
                writer.writerow(esh_results)


def write_ventilation_detailed_output(vent_output_file: Path, vent_output_list: list[list[Any]]):
    """The function writes detailed ventilation output in csv format"""

    with open(safe_path(vent_output_file), "w", newline="") as f:
        writer = CsvWriter(f)
        headings = [
            "Timestep",
            "Incoming air changes per hour",
            "Vent opening ratio",
            "incoming air flow",
            "total_volume",
            "air changes per hour",
            "Internal temperature",
            "Internal reference pressure",
            "Air mass flow rate entering through window opening",
            "Air mass flow rate leaving through window opening",
            "Air mass flow rate entering through vents (openings in the external envelope)",
            "Air mass flow rate leaving through vents (openings in the external envelope)",
            "Air mass flow rate entering through envelope leakage",
            "Air mass flow rate leaving through envelope leakage",
            "Air mass flow rate entering through combustion appliances",
            "Air mass flow rate leaving through combustion appliances",
            "Air mass flow rate entering through passive or hybrid duct",
            "Air mass flow rate leaving through passive or hybrid duct",
            "Supply air mass flow rate going to ventilation zone",
            "Extract air mass flow rate from a ventilation zone",
            "Extract air mass flow rate from heat recovery",
            "Total air mass flow rate entering the zone",
            "Total air mass flow rate leaving the zone",
        ]
        units_row = [
            "[count]",
            "[indicator]",
            "[ratio]",
            "[m3/h]",
            "[m3]",
            "[ACH]",
            "[Celsius]",
            "[Pa]",
            "[kg/h]",
            "[kg/h]",
            "[kg/h]",
            "[kg/h]",
            "[kg/h]",
            "[kg/h]",
            "[kg/h]",
            "[kg/h]",
            "[kg/h]",
            "[kg/h]",
            "[kg/h]",
            "[kg/h]",
            "[kg/h]",
            "[kg/h]",
            "[kg/h]",
        ]
        writer.writerow(headings)
        writer.writerow(units_row)
        for ventilation_results in vent_output_list:
            writer.writerow(ventilation_results)


def write_hot_water_source_output_file(
    output_file, hot_water_source_results: list[list[str | float | None]]
):
    # Note: need to specify newline='' below, otherwise an extra carriage return
    # character is written when running on Windows
    with open(safe_path(output_file), "w", newline="") as f:
        writer = CsvWriter(f)

        for row in hot_water_source_results:
            writer.writerow(row)


def write_core_output_file(
    path: Path,
    output: Output,
):
    """Writes the core output file."""
    # Note: need to specify newline='' below, otherwise an extra carriage return
    # character is written when running on Windows
    with open(safe_path(path), "w", newline="") as f:
        writer = CsvWriter(f)
        headings = ["Timestep"]
        units_row = ["[count]"]

        # Dictionary for most of the units (future output headings need respective units)
        unitsDict = {
            "internal gains": "[W]",
            "solar gains": "[W]",
            "operative temp": "[deg C]",
            "internal air temp": "[deg C]",
            "space heat demand": "[kWh]",
            "space cool demand": "[kWh]",
            "hot water volume required from hot water source": "[litres]",
            "hot water energy demand at hot water source": "[kWh]",
            "hot water energy demand at connected tapping points": "[kWh]",
            "total event duration": "[mins]",
            "number of events": "[count]",
            "distribution pipework losses": "[kWh]",
            "primary pipework losses": "[kWh]",
            "storage losses": "[kWh]",
        }

        # Headings mapping for each hot water system.
        for field_name, field_info in OutputHotWaterSystems.model_fields.items():
            # Column order determined by field order on OutputHotWaterSystems
            if field_info.alias is None:
                warnings.warn(
                    f"OutputHotWaterSystems field {field_name} does not define an alias for the output file column heading! Falling back on the field name.",
                    stacklevel=2,
                )
                field_info.alias = field_name
            for hws_name in getattr(output.core.hot_water_systems, field_name).keys():
                headings.append(f"{hws_name}: {field_info.alias}")
                if field_info.alias in unitsDict:
                    try:
                        units_row.append(unitsDict[field_info.alias])
                    except KeyError:
                        units_row.append(unitsDict.get(field_name, ""))
                        warnings.warn(
                            f'field_info.alias ("{field_info.alias}") missing from dict, using field_name ("{field_name}") instead',
                            stacklevel=2,
                        )
                else:
                    this_filename = os.path.basename(__file__)
                    warnings.warn(
                        f"Unit for {field_name} ({field_info.alias}) not found in unitsDict",
                        stacklevel=2,
                    )
                    units_row.append(f"Unit not defined (add to unitsDict {this_filename}")

        headings.append("Ventilation: Ductwork gains")
        units_row.append("[W]")

        for zone in output.core.zone_list:
            for field_name in (
                OutputZoneData.model_fields.keys()
            ):  # Order follows the field definition on OutputZoneData.
                output_name = field_name.replace("_", " ")
                zone_headings = f"{zone}: {output_name}"
                headings.append(zone_headings)
                if output_name in unitsDict:
                    units_row.append(unitsDict[output_name])
                else:
                    this_filename = os.path.basename(__file__)
                    units_row.append(f"Unit not defined (unitsDict {this_filename})")

        # OutputHeatingCoolingSystem holds heating demand and output as first level keys
        # and the system name as second level keys.
        # Reorganising this dictionary so system names can be grouped together

        # Initialize the reorganized dictionary for grouping systems from OutputHeatingCoolingSystem
        reorganized_dict = {}

        # Iterate over the original structures
        for key, value in {
            "heating_system_output": output.core.heating_cooling_system.heating_system_output,
            "cooling_system_output": output.core.heating_cooling_system.cooling_system_output,
        }.items():
            # Iterate over the nested dictionary
            for nested_key, nested_value in value.items():
                # Check if the nested_key already exists in reorganized_dict
                if nested_key not in reorganized_dict:
                    # If not, create a new entry
                    reorganized_dict[nested_key] = {}
                # Add the nested_value to the corresponding entry in reorganized_dict
                reorganized_dict[nested_key][key] = nested_value

        # Loop over reorganised dictionary to add  column and unit headers
        # Check if the system name is set ,else add a designated empty 'None' string
        for system in reorganized_dict:
            if system is not None:
                for hc_name in reorganized_dict[system].keys():
                    if hc_name == "heating_system_output" or hc_name == "cooling_system_output":
                        alternate_name = "energy output"
                        hc_system = f"{system}: {alternate_name}"
                    else:
                        hc_system = f"{system}: {hc_name}"
                    headings.append(hc_system)
                    units_row.append("[kWh]")
            else:
                for hc_name in reorganized_dict[system].keys():
                    if hc_name == "heating_system_output" or hc_name == "cooling_system_output":
                        alternate_name = "energy output"
                        hc_system = f"None: {alternate_name}"
                    else:
                        hc_system = f"None: {hc_name}"
                    headings.append(hc_system)
                    units_row.append("[kWh]")

        for totals_key in output.core.results_totals.keys():
            totals_header = f"{totals_key}: total"
            headings.append(totals_header)
            units_row.append("[kWh]")
            for end_user_key in output.core.results_end_user[totals_key].keys():
                headings.append(f"{totals_key}: {end_user_key}")
                units_row.append("[kWh]")
            headings.append(f"{totals_key}: import")
            units_row.append("[kWh]")
            headings.append(f"{totals_key}: export")
            units_row.append("[kWh]")
            headings.append(f"{totals_key}: generation to grid")
            units_row.append("[kWh]")
            headings.append(f"{totals_key}: generated and consumed")
            units_row.append("[kWh]")
            headings.append(f"{totals_key}: beta factor")
            units_row.append("[ratio]")
            headings.append(f"{totals_key}: generation to storage")
            units_row.append("[kWh]")
            headings.append(f"{totals_key}: from storage")
            units_row.append("[kWh]")
            headings.append(f"{totals_key}: grid to storage")
            units_row.append("[kWh]")
            headings.append(f"{totals_key}: battery charge level")
            units_row.append("[ratio]")
            headings.append(f"{totals_key}: diverted")
            units_row.append("[kWh]")

        # Write headings & units to output file
        writer.writerow(headings)
        writer.writerow(units_row)

        for t_idx in range(len(output.core.timestep_array)):
            energy_use_row = []
            zone_row = []
            hc_system_row = []
            dhw_row = []
            energy_shortfall = []  # TODO this seem to never be populated ???
            # Loop over end use totals
            for totals_key in output.core.results_totals:
                energy_use_row.append(output.core.results_totals[totals_key][t_idx])
                for end_user_key in output.core.results_end_user[totals_key]:
                    energy_use_row.append(
                        output.core.results_end_user[totals_key][end_user_key][t_idx]
                    )
                energy_use_row.append(output.core.energy_import[totals_key][t_idx])
                energy_use_row.append(output.core.energy_export[totals_key][t_idx])
                energy_use_row.append(output.core.generation_to_grid[totals_key][t_idx])
                energy_use_row.append(output.core.energy_generated_consumed[totals_key][t_idx])
                energy_use_row.append(output.core.beta_factor[totals_key][t_idx])
                energy_use_row.append(output.core.energy_to_storage[totals_key][t_idx])
                energy_use_row.append(output.core.energy_from_storage[totals_key][t_idx])
                energy_use_row.append(output.core.storage_from_grid[totals_key][t_idx])
                energy_use_row.append(output.core.battery_state_of_charge[totals_key][t_idx])
                energy_use_row.append(output.core.energy_diverted[totals_key][t_idx])

            # Loop over results separated by zone
            for zone in output.core.zone_list:
                for zone_outputs in OutputZoneData.model_fields.keys():
                    zone_row.append(getattr(output.core.zone_data, zone_outputs)[zone][t_idx])
            # Loop over system names and print the heating and cooling energy demand and output
            for system in reorganized_dict:
                for hc_name in reorganized_dict[system]:
                    hc_system_row.append(reorganized_dict[system][hc_name][t_idx])

            # Column order determined by field order on OutputHotWaterSystems
            for field_name in OutputHotWaterSystems.model_fields.keys():
                field = getattr(output.core.hot_water_systems, field_name)
                for hws_name in field.keys():
                    dhw_row.append(field[hws_name][t_idx])

            row = (
                [t_idx]
                + dhw_row
                + [output.core.ductwork_gains[t_idx]]
                + energy_shortfall
                + zone_row
                + hc_system_row
                + energy_use_row
            )

            # row = [t_idx] + hw_system_row + hw_system_row_energy_with_pipework_losses + hw_system_row_energy + \
            #       hw_system_row_duration + hw_system_row_events +  pw_losses_row + primary_pw_losses_row + \
            #       storage_losses_row + ductwork_row + energy_shortfall + zone_row + hc_system_row + energy_use_row
            writer.writerow(row)


def write_core_output_file_summary(
    path: Path,
    output: Output,
    project_input: Input,
):
    delivered_energy_rows_title = ["Delivered energy by end-use (below) and fuel (right) [kWh/m2]"]
    delivered_energy_rows: list[list[str | float]] = [["total"]]
    for fuel, end_uses in output.summary.delivered_energy_by_floor_area.items():
        delivered_energy_rows_title.append(fuel)
        index = delivered_energy_rows_title.index(fuel)
        for row in delivered_energy_rows:
            row.append("0")
        for end_use, value in end_uses.items():
            end_use_found = False
            for row in delivered_energy_rows:
                if end_use in row:
                    end_use_found = True
                    row[index] = value
            if not end_use_found:
                new_row: list[str | float] = ["0"] * len(delivered_energy_rows_title)
                new_row[0] = end_use
                new_row[index] = value
                delivered_energy_rows.append(new_row)

    # Output "DIV/0" in place of None.
    heat_cop_rows: list[Any] = [
        (h_name, "DIV/0" if h_cop is None else h_cop)
        for h_name, h_cop in output.core.cop.space_heating_system.items()
    ]
    cool_cop_rows: list[Any] = [
        (c_name, "DIV/0" if c_cop is None else c_cop)
        for c_name, c_cop in output.core.cop.space_cooling_system.items()
    ]
    dhw_cop_rows: list[Any] = [
        [hw_name, "DIV/0" if hw_cop is None else hw_cop]
        for hw_name, hw_cop in output.core.cop.hot_water_system.items()
    ]

    # Note: need to specify newline='' below, otherwise an extra carriage return
    # character is written when running on Windows
    with open(safe_path(path), "w", newline="") as file:
        writer = CsvWriter(file)
        writer.writerow(["Energy Demand Summary"])
        writer.writerow(["", "", "Total"])
        writer.writerow(
            ["Space heat demand", "kWh/m2", output.summary.space_heat_demand_by_floor_area]
        )
        writer.writerow(
            ["Space cool demand", "kWh/m2", output.summary.space_cool_demand_by_floor_area]
        )
        writer.writerow([])
        writer.writerow(["Energy Supply Summary"])
        writer.writerow(["", "kWh", "timestep", "month", "day", "hour of day"])

        peak_consumption = output.summary.electricity_peak_consumption
        writer.writerow(
            [
                "Peak consumption (electricity)",
                peak_consumption.peak,
                peak_consumption.index,
                calendar.month_abbr[peak_consumption.month].upper(),
                peak_consumption.day,
                peak_consumption.hour,
            ]
        )
        writer.writerow([])

        energy_summary_header_row = ["", "Total"]
        for key in output.summary.energy_supply.keys():
            energy_summary_header_row.append(key)
        writer.writerow(energy_summary_header_row)

        fields = [
            # Label, unit, OutputSummaryEnergySupply field.
            ("Consumption", "kWh", "consumption"),
            ("Generation", "kWh", "generation"),
            (
                "Generation to consumption (immediate excl. diverter)",
                "kWh",
                "generation_to_consumption",
            ),
            ("Generation to storage", "kWh", "generation_to_storage"),
            ("Generation to diverter", "kWh", "generation_to_diverter"),
            ("Generation to grid", "kWh", "generation_to_grid"),
            ("Storage to consumption", "kWh", "storage_to_consumption"),
            ("Grid to storage", "kWh", "grid_to_storage"),
            ("Grid to consumption", "kWh", "grid_to_consumption"),
            ("Total gross import", "kWh", "total_gross_import"),
            ("Total gross export", "kWh", "total_gross_export"),
            ("Net import", "kWh", "net_import"),
            ("Storage round-trip efficiency", "ratio", "storage_efficiency"),
        ]
        for label, unit, field in fields:
            row = [label, unit]
            for _, stats in output.summary.energy_supply.items():
                value = getattr(stats, field)
                if field == "storage_efficiency" and value is None:
                    value = "DIV/0"  # COULDDO replace hard-coded error value in CSV with something more useful.
                row.append(value)
            writer.writerow(row)
        writer.writerow([])
        writer.writerow(["Delivered Energy Summary"])
        writer.writerow(delivered_energy_rows_title)
        writer.writerows(delivered_energy_rows)

        if dhw_cop_rows:
            writer.writerow([])
            writer.writerow(
                [
                    "Hot water system",
                    "Overall CoP",
                    "Daily HW demand ([kWh] 75th percentile)",
                    "HW cylinder volume (litres)",
                ]
            )
            for row in dhw_cop_rows:
                hws_name = row[0]
                row.append(output.summary.hot_water_demand_daily_75th_percentile[hws_name])
                hot_water_source = project_input.hot_water_source[hws_name]
                if isinstance(hot_water_source, InputStorageTank):
                    row.append(hot_water_source.volume)
                else:
                    row.append("N/A")
            writer.writerows(dhw_cop_rows)
        if heat_cop_rows:
            writer.writerow([])
            writer.writerow(["Space heating system", "Overall CoP"])
            writer.writerows(heat_cop_rows)
        if cool_cop_rows:
            writer.writerow([])
            writer.writerow(["Space cooling system", "Overall CoP"])
            writer.writerows(cool_cop_rows)


def write_output_json_file(path: Path, output: Output):
    def fallback_json_serialisation(value: Any) -> Any:
        # Some numpy values don't cast automatically.
        if isinstance(value, np.bool):
            return bool(value)
        return value

    with open(safe_path(path), "w", newline="") as file:
        file.write(
            output.model_dump_json(indent=2, by_alias=True, fallback=fallback_json_serialisation)
        )


def define_cli_argument_parser():
    parser = argparse.ArgumentParser(
        prog="hem-core",
        description="Home Energy Model (HEM)",
    )
    parser.add_argument(
        "--epw-file",
        "-w",
        action="store",
        default=None,
        help=("path to weather file in .epw format"),
    )
    parser.add_argument(
        "--CIBSE-weather-file",
        action="store",
        default=None,
        help=("path to CIBSE weather file in .csv format"),
    )
    parser.add_argument(
        "--tariff-file",
        action="store",
        default=None,
        help=("path to tariff data file in .csv format"),
    )
    parser.add_argument(
        "input_file",
        nargs="*",
        help=("path(s) to file(s) containing building specifications to run"),
    )
    parser.add_argument(
        "--parallel",
        "-p",
        action="store",
        type=int,
        default=0,
        help=(
            "run calculations for different input files in parallel"
            "(specify no of files to run simultaneously)"
        ),
    )
    parser.add_argument(
        "--output",
        nargs="+",
        choices=OutputFormat,
        default=[OutputFormat.CSV],
        help="output format(s): csv, json, or both; default to csv",
    )
    parser.add_argument(
        "--heat-balance",
        action="store_true",
        default=False,
        help="output heat balance for each zone",
    )
    parser.add_argument(
        "--detailed-output-heating-cooling",
        action="store_true",
        default=False,
        help=(
            "output detailed calculation results for heating and cooling "
            "system objects (including HeatSourceWet objects) where the "
            "relevant objects have this functionality"
        ),
    )
    parser.add_argument(
        "--no-fast-solver",
        action="store_true",
        default=False,
        help=(
            "disable optimised solver (results may differ slightly due "
            "to reordering of floating-point ops); this option is "
            "provided to facilitate verification and debugging of the "
            "optimised version"
        ),
    )
    parser.add_argument(
        "--display-progress",
        action="store_true",
        default=False,
        help=("display progress for the json input file currently running"),
    )
    parser.add_argument(
        "--permissive-json",
        action="store_true",
        default=False,
        help="Allow extra fields in Pydantic models (useful during development)",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        default=False,
        help=("stop running as soon as an error is encountered "),
    )
    parser.add_argument(
        "--log-level",
        action="store",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="set the logging level for the application",
    )
    parser.add_argument(
        "--version",
        "-v",
        action="store_true",
        help="show the version",
    )
    return parser


def main(args: list[str] | None = None) -> int:
    parser = define_cli_argument_parser()
    cli_args = parser.parse_args(args)
    version = cli_args.version
    if version is True:
        print(f"hem-core {importlib.metadata.version('hem-core')}")
        exit(0)
    if not cli_args.input_file:
        logger.error("Error: the following arguments are required: input_file")
        exit(1)
    inp_files = [Path(filename) for filename in cli_args.input_file]
    epw_filename = Path(cli_args.epw_file) if cli_args.epw_file else None
    cibse_weather_filename = (
        Path(cli_args.CIBSE_weather_file) if cli_args.CIBSE_weather_file else None
    )
    tariff_data_filename = Path(cli_args.tariff_file) if cli_args.tariff_file else None
    parallel_threads = cli_args.parallel
    output = cli_args.output
    heat_balance = cli_args.heat_balance
    detailed_output_heating_cooling = cli_args.detailed_output_heating_cooling
    use_fast_solver = not cli_args.no_fast_solver
    display_progress = cli_args.display_progress
    skip_validation = cli_args.permissive_json
    fail_fast = cli_args.fail_fast
    log_level = cli_args.log_level

    setup_logging(log_level)

    return run(
        input_files=inp_files,
        epw_filename=epw_filename,
        cibse_weather_filename=cibse_weather_filename,
        parallel_threads=parallel_threads,
        output_formats=output,
        heat_balance=heat_balance,
        detailed_output_heating_cooling=detailed_output_heating_cooling,
        use_fast_solver=use_fast_solver,
        tariff_data_filename=tariff_data_filename,
        display_progress=display_progress,
        skip_validation=skip_validation,
        fail_fast=fail_fast,
    )


def load_weather_data_from_file(
    epw_filename: Path | None = None, cibse_weather_filename: Path | None = None
):
    if epw_filename is not None:
        return epw_weather_data_to_dict(weather_file=epw_filename)
    elif cibse_weather_filename is not None:
        return cibse_weather_data_to_dict(weather_file=cibse_weather_filename)
    else:
        return None


def run(
    input_files: list[Path],
    epw_filename: Path | None,
    cibse_weather_filename: Path | None,
    parallel_threads: int,
    output_formats: list[OutputFormat] | None,
    heat_balance: bool,
    detailed_output_heating_cooling: bool,
    use_fast_solver: bool,
    tariff_data_filename: Path | None,
    display_progress: bool,
    skip_validation: bool,
    fail_fast: bool,
) -> int:
    exit_code = 0
    external_conditions_dict = load_weather_data_from_file(
        epw_filename=epw_filename, cibse_weather_filename=cibse_weather_filename
    )
    if parallel_threads == 0:
        logger.info(f"Running {len(input_files)} cases in series")
        for input_file in input_files:
            try:
                run_project_from_input_file(
                    input_file=input_file,
                    external_conditions_dict=external_conditions_dict,
                    output_formats=output_formats,
                    heat_balance=heat_balance,
                    detailed_output_heating_cooling=detailed_output_heating_cooling,
                    use_fast_solver=use_fast_solver,
                    tariff_data_filename=tariff_data_filename,
                    display_progress=display_progress,
                    skip_validation=skip_validation,
                )
            except Exception as e:
                if fail_fast:
                    raise e
                logger.error(f"Error running {input_file}")
                print_exc()
                exit_code = 1

    else:
        import multiprocessing as mp

        logger.info(f"Running {len(input_files)} cases in parallel ({parallel_threads} at a time)")

        run_project_args = [
            (
                input_file,
                external_conditions_dict,
                output_formats,
                heat_balance,
                detailed_output_heating_cooling,
                use_fast_solver,
                tariff_data_filename,
                False,  # Do not display progress when running in parallel mode
                skip_validation,
            )
            for input_file in input_files
        ]

        pool = mp.Pool(
            processes=parallel_threads,
            initializer=setup_logging,
            initargs=(logging.getLevelName(logger.level),),
        )
        results = []

        def handle_error(e):
            logger.error(f"Worker failed with error: {e}\n ")
            if fail_fast:
                logger.info(
                    "--fail-fast option is set, all workers will be terminated so other input files may not be completed."
                )
                pool.terminate()  # Stop all workers immediately

        try:
            for args in run_project_args:
                res = pool.apply_async(
                    run_project_from_input_file, args=args, error_callback=handle_error
                )
                results.append(res)

            if not fail_fast:
                for r in results:
                    try:
                        r.get()
                    except Exception:
                        print_exc()
                        exit_code = 1
            pool.close()
            pool.join()

        except Exception as e:
            logger.error(f"Error during parallel execution:\n{e}")
            pool.terminate()
            pool.join()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
