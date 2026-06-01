"""
This script creates a JSON file using the packages from the batch processing tool
"""

import sys
import json
import os
import argparse
import pandas as pd

# Local imports
from hem_core.input_output.read_weather_file import (
    epw_weather_data_to_dict,
    cibse_weather_data_to_dict,
)
from hem_core.hem import run_project
from post_processing.QA_output_format import postproc_QA_output_format
from post_processing.statistical_analysis import statistical_analysis


def batch_package_folder(packages_folder_path, package_header):
    """
    Identifies the right folder path for the relevant package.

    Args:
        packages_folder_path - path to packages folder
        package_header       - name of relevant package folder

    Returns:
        package_folder_path - path of the relevant package folder (string)
    """
    for folder in os.listdir(packages_folder_path):
        if folder == package_header:
            package_folder_path = os.path.join(packages_folder_path, package_header)
            return package_folder_path
    sys.exit(f"There is no relevant package folder for: {package_header}")


def json_package(package_folder_path, package_name):
    """
    Identifies the relevant package JSON file

    Args:
        package_folder_path - path to the folder containing the relevant packages
        package_name        - name of the relevant package aka JSON file

    Returns:
        json_dict - dictionary of the JSON snippet for the relevant package
    """
    for f in os.listdir(package_folder_path):
        if f.endswith(".json"):
            f_name = f.split(".")[0]
            if package_name == f_name:  # identify the correct JSON file using the config JSON file
                package_json = os.path.join(package_folder_path, f)
                with open(package_json) as json_file:
                    json_dict = json.load(json_file)
                return json_dict
    sys.exit(f'Missing package "{package_name}" in {package_folder_path}.')


def description_package(package_folder_path, package_name):
    """
    Collects the description for a specified package JSON

    Args:
        package_folder_path - path to the folder containing the relevant packages
        package_name        - name of the relevant package aka JSON file

    Return:
        description - string containing the package description
    """
    for f in os.listdir(package_folder_path):
        if f.endswith(".md"):
            f_name = f.split(".")[0]
            if package_name == f_name:  # identify the correct JSON file using the config JSON file
                txt_file = os.path.join(package_folder_path, f)
                with open(txt_file) as file:
                    description = file.read()
                return description
    sys.exit(f'Missing description .md file for package "{package_name}" in {package_folder_path}.')


def merge_dicts(dict1, dict2):
    """
    The function merges dictionary 'dict2' into  dictionary 'dict1'.
    By only overwriting key-value pairs that exist in both dictionaries,
    and appending any key-value pair 1from 'dict2' not present in 'dict1'.
    """
    for key, value in dict2.items():
        if key in dict1:
            if isinstance(value, dict) and isinstance(dict1[key], dict):
                merge_dicts(dict1[key], value)
            else:
                dict1[key] = value
        else:
            dict1[key] = value
    return dict1


def generate_configs(dict_configs, current=None, configs=None):
    """
    This function generates a list of unique configurations for each individual
    test variations for a given input dictionary of configurations.

    For example if the input dict_config is:
    {"test": {
        "base_json":"example_base",
        "energy_generated": ["PV_1", "PV_2"]
        }
    }
    The list of configurations will be:
    [
        {"test": {
            "base_json":"example_base",
            "energy_generated": "PV_1"
            }
        }.
        {"test": {
            "base_json":"example_base",
            "energy_generated": "PV_2"
            }
        }
    ]

    Args:
        dict_configs - dictionary of configurations extracted from the input JSON config file.

    Returns:
        configs - list of unique configuration dictionaries.
    """
    if current == None:
        current = {}
    if configs == None:
        configs = []

    if not dict_configs:
        configs.append(current)
        return

    key, values = dict_configs.popitem()
    for value in values:
        new_current = current.copy()
        new_current[key] = value
        generate_configs(dict_configs.copy(), new_current, configs)
    return configs


def collect_summary(packages_folder_path, run):
    """
    For a given run configuration, this function collects the description
    for each relevant package into a summary dictionary.

    Args:
        packages_folder_path - path to packages folder
        run                  - dictionary describing a single run configuration

    Returns:
        summary - dictionary where keys are relevant packages names for the run,
                  and values are package descriptions
    """
    summary = {}
    for key in run.keys():
        package_header = key
        package_name = run[key]
        package_folder_path = os.path.join(packages_folder_path, package_header)
        summary[package_header] = description_package(package_folder_path, package_name)
    return summary


def delete_r_c_u_value(bd_element_data_dict):
    """
    This function deletes the resistance (r_c) and u-value (u_value)
    variables from a given building element dictionary.

    This function is used in combination with the simplified fabric package
    option. If both the u-value  and resistance are given,
    the engine will use the resistance. To allow to specify r_c or u_value
    in the simplified fabric package, we first remove the variables
    from the project_dict, so that there is no contradiction between the
    base JSON and what is provided in the simplified fabric package.

    Args:
        bd_element_data_dict - a BuildingElement from the project_dict dictionary
    """

    if "r_c" in bd_element_data_dict.keys():
        del bd_element_data_dict["r_c"]
    if "u_value" in bd_element_data_dict.keys():
        del bd_element_data_dict["u_value"]


def create_json(
    run, packages_folder_path, filepath, external_conditions_dict, debug_JSONs, sim_settings
):
    """
    Create JSON input file for a single run

    Args:
        run -                - dictionary describing a single run configuration
                               where keys are package headers (folder name) and values are package names (JSON package name).
        packages_folder_path - path to packages folder.
        filepath             - filepath for collecting the JSON file for the run.
        external_conditions_dict - dictionary holding weather data information extracted from weather file,
                               to be applied to the input JSON file before running the simulation.
        debug_JSONs          - flag to configure input JSON files to run for the first 10 hours of the year,
                               to help debugging faulty packages.
    """
    # collect base json snippet,
    # this will form the core of the base case and
    # should be able to be run as a stand alone JSON input file to the hem engine
    if "base_json" in run.keys():
        base_json_path = batch_package_folder(packages_folder_path, "base_json")
        project_dict = json_package(base_json_path + "/", run["base_json"])
    else:
        sys.exit("The config file must have either a base_json package specified.")

    # apply simplified fabric package if present
    # the simplified fabric approach applies a single heat loss paramter
    # for a given fabric component type to all components of the type
    # for example all walls will get the same u-value
    if "simplified_fabric" in run.keys():
        print(
            "Warning: The simplified_fabric package will apply heat loss paramters "
            + "for a given fabric component type to all components of the type. "
            + "For example all walls will be edited with the same U-value. "
        )
        fab_path = batch_package_folder(packages_folder_path, "simplified_fabric")
        fab_dict = json_package(fab_path + "/", run["simplified_fabric"])

        for zone_name in project_dict["Zone"].keys():
            for tb_name, tb_dict in project_dict["Zone"][zone_name]["ThermalBridging"].items():
                if tb_dict["type"] == "ThermalBridgeLinear":
                    tb_dict["linear_thermal_transmittance"] = fab_dict["ThermalBridging"][
                        "TB_linear"
                    ]["linear_thermal_transmittance"]
                elif tb_dict["type"] == "ThermalBridgePoint":
                    tb_dict["heat_transfer_coeff"] = fab_dict["ThermalBridging"]["TB_point"][
                        "heat_transfer_coeff"
                    ]

        # Identify element type and amend heat loss properties for the relevant type.
        #    Element types are identified from their type and pitch
        #    for example an external wall is a vertical opaque element.
        #    To distinguish between external doors and walls,
        #    the script looks for the word 'door' in the element name.
        for zone_name in project_dict["Zone"].keys():
            for name, data in project_dict["Zone"][zone_name]["BuildingElement"].items():
                if (
                    data["type"] == "BuildingElementOpaque" and data["pitch"] == 90
                ):  # external walls
                    delete_r_c_u_value(data)
                    data.update(fab_dict["wall"])
                if data["type"] == "BuildingElementTransparent":  # windows
                    delete_r_c_u_value(data)
                    data.update(fab_dict["window"])
                if data["type"] == "BuildingElementOpaque" and data["pitch"] == 0:  # roof
                    delete_r_c_u_value(data)
                    data.update(fab_dict["roof"])
                if data["type"] == "BuildingElementGround":  # ground
                    delete_r_c_u_value(data)
                    data.update(fab_dict["ground"])
                if "door" in name.lower() and data["type"] == "BuildingElementOpaque":  # door
                    delete_r_c_u_value(data)
                    data.update(fab_dict["door"])
                if (
                    data["type"] == "BuildingElementAdjacentZTC" and data["pitch"] == 90
                ):  # party walls
                    delete_r_c_u_value(data)
                    data.update(fab_dict["party_wall"])

    # Apply other packages
    for package in run.keys():
        if package not in ["base_json", "simplified_fabric", "tariff_file"]:
            try:
                path = batch_package_folder(packages_folder_path, package)
                dict = json_package(path + "/", run[package])
            except:
                raise Exception(f"Issue with JSON file for the following package: {run[package]}")

            if dict is not None:
                if "HotWaterSource" in dict.keys() or "SpaceHeatSystem" in dict.keys():
                    # These packages should overwrite any existing specifications
                    # from the base json to avoid confusion
                    # for example to avoid having an additional heat source
                    # serving the cylinder when the intension was
                    # to overwrite the existing heat source
                    project_dict.update(dict)
                else:
                    merge_dicts(project_dict, dict)

    # apply weather data
    if external_conditions_dict is not None:
        # Note: Shading segments are an assessor input regardless, so save them
        # before overwriting the ExternalConditions and re-insert after
        # Check if shading_segments exists in the current ExternalConditions
        shading_segments = project_dict["ExternalConditions"].get("shading_segments")
        project_dict["ExternalConditions"] = external_conditions_dict
        if shading_segments:
            project_dict["ExternalConditions"]["shading_segments"] = shading_segments

    # if debug-JSONs flag is True, reduce the number of timesteps to 10.
    if debug_JSONs:
        project_dict["SimulationTime"]["start"] = 0
        project_dict["SimulationTime"]["end"] = 10
        # remove hot water events as schedule crashes if start of hot water event
        # is greater then simulation time end.
        for outlet_type, outlets in project_dict["Events"].items():
            for outlet, events_list in outlets.items():
                outlets[outlet] = []

    with open(filepath, "w") as json_file:
        json.dump(project_dict, json_file, sort_keys=True, indent=4)


def process_config(
    config_filepath,
    packages_folder_path,
    results_path,
    external_conditions_dict,
    variations_only,
    debug_JSONs,
):
    """
    Creates test variations described in a config file and runs them through hem.

    Args:
        config_filepath          - path to the JSON config file
        packages_folder_path     - path to packages folder.
        results_path             - path to a results folder meant to collect
                                   all test variations JSON files and their results.
        external_conditions_dict - dictionary describing the content of a weather file.
        variations_only          - boolean, if true only create JSON variations, without running them
    """
    with open(config_filepath) as json_file:
        inp_dict = json.load(json_file)

    summary = {}  # this dictionary will collect package descriptions for each run
    for run_name in inp_dict:  # run through each variant specified in the config JSON file
        config_count = 0

        configs = generate_configs(inp_dict[run_name])

        for run in configs:
            f_name = f"{run_name}_{str(config_count)}"
            print(f_name)

            summary[f_name] = collect_summary(packages_folder_path, run)

            # if tariff-file needs to be used, use the demo tariff-file.csv
            if "tariff_file" in run.keys():
                folder = os.path.join(packages_folder_path, "tariff_file")
                tariff_filepath = os.path.join(folder, run["tariff_file"] + ".csv")
            else:
                tariff_filepath = None
            sim_settings = [True, True, True, tariff_filepath]

            filepath = os.path.join(results_path, f"{f_name}.json")
            create_json(
                run,
                packages_folder_path,
                filepath,
                external_conditions_dict,
                debug_JSONs,
                sim_settings,
            )
            config_count += 1

            if not variations_only:
                run_project(
                    filepath,
                    None,
                    heat_balance=True,
                    detailed_output_heating_cooling=True,
                    tariff_data_filename=tariff_filepath,
                )

    # write summary to csv
    directory_path, file_name = os.path.split(config_filepath)
    summary_filename = file_name.split(".")[0] + "_summary.csv"
    summary_filepath = os.path.join(results_path, summary_filename)
    df = pd.DataFrame(summary)
    df.to_csv(summary_filepath, index=True)

    return inp_dict


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HEM batch running tool")
    # TODO revise description
    # TODO should accept multiple paths
    parser.add_argument(
        "config_file",
        type=str,
        help="path(s) to config file(s)",
    )
    # TODO make packages path an option
    # if not provided assume in same path as config
    parser.add_argument(
        "packages",
        type=str,
        help="path(s) to folder containing packages",
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
        "--json-variations-only",
        action="store_true",
        default=False,
        help=("Create JSON variations from input config file without running them."),
    )
    parser.add_argument(
        "--QA-output-format",
        action="store_true",
        default=False,
        help="formats outputs in QA spreadsheet format",
    )
    parser.add_argument(
        "--statistical-analysis",
        action="store_true",
        default=False,
        help="report statistical analysis for key metrics, comparing runs of similar variation",
    )
    parser.add_argument(
        "--debug-JSONs",
        action="store_true",
        default=False,
        help="This flag allows to run the JSON configurations for the first 10 hours of the year, to help debugging faulty packages.",
    )
    # TODO allow user to specify an output path
    # TODO for compatibility with git add __results to results filepath
    cli_args = parser.parse_args()

    config_filepath = cli_args.config_file
    packages_folder_path = cli_args.packages
    epw_filename = cli_args.epw_file
    cibse_weather_filename = cli_args.CIBSE_weather_file
    variations_only = cli_args.json_variations_only
    debug_JSONs = cli_args.debug_JSONs

    if epw_filename is not None:
        external_conditions_dict = epw_weather_data_to_dict(epw_filename)
    elif cibse_weather_filename is not None:
        external_conditions_dict = cibse_weather_data_to_dict(cibse_weather_filename)
    else:
        external_conditions_dict = None

    config_filename = os.path.basename(config_filepath).split(".")[0]

    # a documentation file must be provided alongside the config file
    config_md = os.path.join(os.path.dirname(config_filepath), f"{config_filename}.md")
    if not os.path.isfile(config_md):
        sys.exit(
            f"Missing documentation file for {config_filename}. "
            + f"The documentation file must be named {config_filename}.md"
        )

    # the results will be stored in the same location as the input config file
    results_path = os.path.join(os.path.dirname(config_filepath), config_filename + "__results")
    if not os.path.exists(results_path):
        os.mkdir(results_path)

    config_dict = process_config(
        config_filepath,
        packages_folder_path,
        results_path,
        external_conditions_dict,
        variations_only,
        debug_JSONs,
    )

    if cli_args.QA_output_format:
        postproc_QA_output_format(results_path)
    if cli_args.statistical_analysis:
        statistical_analysis(results_path, config_filepath)
