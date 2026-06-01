#!/usr/bin/env python3

import pandas as pd
import json
from format_dates import convert_timestep_to_datetime


def get_kwh_headings(project_dict, results_df):
    """
    Creates a dictionary headings_dict where:
        keys   - column headings for a data frame that will report total kWh figures
                 either to sum results broken down per zone, or to sum results broken down per end-use
        values - list of relevant column headings from results CSV that should be added up
                 to produce the total figure for the relevant heading held in the key.

    The dictionary is then used in the function get_total_kWh_results_df to create a data frame
    where columns are the dictionary keys and the columns are made of the sum of
    the relevant columns from the results CSV as listed in the list of values.

    For example, if we wish for the data frame that will record totals to have a column
    'Total Space heat demand', assuming we are working with a JSON file that has 2 zones
    named Zone 1 and Zone 2, to fill in a column 'Total Space heat demand', we would need
    the sum of each zone's space heat demand from the results CSV file.
    For this variable, the dictionary of headings would be:
        headings_dict['Total Space heat demand'] = ['Zone 1 Space heat demand',
                                                    'Zone 2 Space heat demand']

    Args:
        project_dict - dictionary produced from a HEM input JSON file
        results_df   - data frame created from the results CSV (file endng __results.csv)
                       associated with the project_dict.

    Returns:
        headings_dict - dictionary as defined above.
    """

    # Initialised the headings_dict
    headings_dict = {}

    # collect headings and column names for space and cooling demand
    # TODO add unmet demand for space heat, cool, and hot water
    space_headings = [
        "space heat demand",
        "space cool demand",
    ]
    headings_dict["space heat unmet demand Total"] = []
    for z_name in project_dict["Zone"].keys():
        headings_dict["space heat unmet demand Total"].append(f"_unmet_demand: {z_name}")
        for space_heading in space_headings:
            if f"{space_heading} Total" in headings_dict.keys():
                headings_dict[f"{space_heading} Total"].append(f"{z_name}: {space_heading}")
            else:
                headings_dict[f"{space_heading} Total"] = [f"{z_name}: {space_heading}"]

    # collect headings and column names for space and cooling system outputs
    headings_dict["Space Heat Output"] = []
    headings_dict["Space Cooling Output"] = []
    if "SpaceHeatSystem" in project_dict.keys():
        for sys_name in project_dict["SpaceHeatSystem"].keys():
            headings_dict["Space Heat Output"].append(f"{sys_name}: energy output")
    if "SpaceCoolSystem" in project_dict.keys():
        for sys_name in project_dict["SpaceCoolSystem"].keys():
            headings_dict["Space Cooling Output"].append(f"{sys_name}: energy output")

    # collect headings and column names for energy consumed variables
    headings_dict["Space Heating Energy Use"] = []
    headings_dict["Space Cooling Energy Use"] = []
    headings_dict["DHW Energy Use"] = []
    headings_dict["Pumps and Fans Energy Use"] = []
    headings_dict["Cooking Energy Use"] = []
    headings_dict["Appliances Energy Use"] = []
    headings_dict["Lighting Energy Use"] = []
    headings_dict["Ventilation Systems"] = []

    for app_name, app_dict in project_dict["ApplianceGains"].items():
        energy_supply = app_dict["EnergySupply"]
        if app_dict["type"] in ("cooking", "Gas_Cooker", "Gas_Oven", "Microwave", "Hobs", "Oven"):
            headings_dict["Cooking Energy Use"].append(f"{energy_supply}: {app_name}")
        elif app_dict["type"] in (
            "appliances",
            "Clothes_drying",
            "Clothes_washing",
            "Dishwasher",
            "Fridge",
            "Freezer",
            "Kettle",
            "Otherdevices",
        ):
            headings_dict["Appliances Energy Use"].append(f"{energy_supply}: {app_name}")
        elif app_dict["type"] == "lighting":
            headings_dict["Lighting Energy Use"].append(f"{energy_supply}: {app_name}")

    for col in results_df.columns:
        if "SpaceHeatSystem" in project_dict.keys():
            for sys_name, sys_dict in project_dict["SpaceHeatSystem"].items():
                if "EnergySupply" in sys_dict.keys():
                    energy_supply = sys_dict["EnergySupply"]
                else:
                    heat_source = sys_dict["HeatSource"]["name"]
                    energy_supply = project_dict["HeatSourceWet"][heat_source]["EnergySupply"]
                if sys_name in col and energy_supply in col:
                    headings_dict["Space Heating Energy Use"].append(col)

        if "SpaceCoolSystem" in project_dict.keys():
            for sys_name in project_dict["SpaceCoolSystem"].keys():
                energy_supply = sys_dict["EnergySupply"]
                if sys_name in col and energy_supply in col:
                    headings_dict["Space Cooling Energy Use"].append(col)

        # Hot water sources that heat a cylinder
        if "_water_heating" in col:
            # handles HeatSourceWet systems heating hot water
            headings_dict["DHW Energy Use"].append(col)
        elif "HeatSource" in project_dict["HotWaterSource"]["hw cylinder"]:
            # handles other heat sources
            for hw_source, source_dict in project_dict["HotWaterSource"]["hw cylinder"][
                "HeatSource"
            ].items():
                if hw_source in col:
                    headings_dict["DHW Energy Use"].append(col)

        # Hot water sources that don't heat a cylinder
        if project_dict["HotWaterSource"]["hw cylinder"]["type"] == "PointOfUse":
            # handles point of use heater
            energy_supply = project_dict["HotWaterSource"]["hw cylinder"]["EnergySupply"]
            headings_dict["DHW Energy Use"].append(f"{energy_supply}: hw cylinder")
        for shower_name, shower_dict in project_dict["HotWaterDemand"]["Shower"].items():
            # handles instant elec showers
            if shower_dict["type"] == "InstantElecShower":
                energy_supply = shower_dict["EnergySupply"]
                headings_dict["DHW Energy Use"].append(f"{energy_supply}: shower_name")

        if "_auxiliary:" in col:
            headings_dict["Pumps and Fans Energy Use"].append(col)

    # Ventilation systems
    for sys_name, sys_dict in project_dict["InfiltrationVentilation"][
        "MechanicalVentilation"
    ].items():
        energy_supply = sys_dict["EnergySupply"]
        headings_dict["Ventilation Systems"].append(f"{energy_supply}: {sys_name}")

    return headings_dict


def get_total_kWh_results_df(results_df, project_dict):
    """
    Add new columns to the results dataframe for
    total kWh figures for the whole dwelling
    and per end-uses where relevant.

    Args:
        project_dict - dictionary produced from a HEM input JSON file
        results_df   - data frame created from the results CSV
                       (file endng __results.csv) associated with
                       the project_dict.
    """
    columns_dict = get_kwh_headings(project_dict, results_df)
    for column, results_columns in columns_dict.items():
        results_df[column] = results_df[results_columns].sum(axis=1)
    return results_df


def get_temperature_headings(project_dict):
    """
    Creates a dictionary headings_dict where:
        keys - column headings for a data frame that will report volume weighted average
               Operative and Internal Air temperatures.
        Values - list of dictionaries made up of the following keys:
                    column_name - column name in the results CSV file (file ending: __results.csv)
                    that records the temperature data for a given zone
                    volume - volume of the zone associated with the column name

    The dictionary is then used to report volume weight average temperatures.

    Args:
        project_dict - dictionary produced from a HEM input JSON file

    Returns:
        headings_dict - dictionary as defined above.
    """
    headings = [
        "operative temp",
        "internal air temp",
    ]
    headings_dict = {}
    for z_name in project_dict["Zone"].keys():
        volume = project_dict["Zone"][z_name]["volume"]
        for heading in headings:
            if f"{heading} Average" in headings_dict.keys():
                headings_dict[f"{heading} Average"].append(
                    {"column": f"{z_name}: {heading}", "volume": volume}
                )
            else:
                headings_dict[f"{heading} Average"] = [
                    {"column": f"{z_name}: {heading}", "volume": volume}
                ]
    return headings_dict


def get_temperature_df(results_df, project_dict):
    """
    Add new columns to the results dataframe for
    volume weighted average internal air and operative temperatures.

    Args:
        project_dict - dictionary from HEM input JSON file
        results_df   - data frame created from the results CSV (file endng __results.csv)
                       associated with the project_dict.
    """
    columns_dict = get_temperature_headings(project_dict)

    for column, columns_volumes_list in columns_dict.items():
        results_df[column] = [0.0 for i in range(len(results_df.index))]
        volume_tot = 0
        for columns_volumes_dict in columns_volumes_list:
            results_df[column] = (
                results_df[columns_volumes_dict["column"]] * columns_volumes_dict["volume"]
            ) + results_df[column]
            volume_tot += columns_volumes_dict["volume"]
        results_df[column] = results_df[column].div(volume_tot)

    return results_df


def get_energy_generated_df(results_df, project_dict):
    """
    Add new columns to the results dataframe for
    total energy generated per renewable heat source category.

    For example output from all PV array will be collected under
    a column named PV Generation.

    Args:
        project_dict - dictionary from HEM input JSON file
        results_df   - data frame created from the results CSV (file endng __results.csv)
                       associated with the project_dict.
    """

    # TODO include other reneable energy sources
    results_df["PV Generation"] = [0.0 for i in range(len(results_df.index))]
    if "OnSiteGeneration" in project_dict.keys():
        for source_name, source_data in project_dict["OnSiteGeneration"].items():
            energy_supply = source_data["EnergySupply"]
            column = f"{energy_supply}: {source_name}"
            if source_data["type"] == "PhotovoltaicSystem":
                results_df["PV Generation"] = results_df[["PV Generation", column]].sum(axis=1)
    return results_df


def expand_results_df(results_df, project_dict):
    """
    This function takes the results dataframe created from
    the main results csv file produced by the HEM engine,
    and adds summary columns for whole dwelling totals and averages.
    It also adds extra columns for formating timesteps into date and time.

    Args:
        project_dict - dictionary from HEM input JSON file
        results_df   - data frame created from the results CSV (file endng __results.csv)
                       associated with the project_dict.
    """

    results_df = get_total_kWh_results_df(results_df, project_dict)
    results_df = get_temperature_df(results_df, project_dict)
    results_df = get_energy_generated_df(results_df, project_dict)

    # convert timesteps to date and time format
    results_df["datetime"] = convert_timestep_to_datetime(
        timestep=results_df["Timestep"],
        start_timestep=project_dict["SimulationTime"]["start"],
        step_size=project_dict["SimulationTime"]["step"],
    )

    return results_df


def expand_heat_balance_df(heat_balance_df, project_dict):
    """
    For a given heat_balance_df, that is a dataframe created from
    a heat balance output CSV file that is a file ending with either:
        _heat_balance_air_node.csv
        __heat_balance_external_boundary.csv
        __heat_balance_internal_boundarycsv
    The function:
        - Converts data in every column from W to kWh.
        - Adds up zone breakdowns for whole dwelling totals.

    Args:
        project_dict      - dictionary from HEM input JSON file
        heat_balance_df   - data frame created from a heat balance results CSV
                            associated with the project_dict.
    Returns:
        energy_generated_df - data frame.
    """

    # Convert all columns to kWh
    stepping = project_dict["SimulationTime"]["step"]
    heat_balance_df.loc[:, heat_balance_df.columns != "Timestep"] = heat_balance_df.loc[
        :, heat_balance_df.columns != "Timestep"
    ].mul(stepping / 1000)

    # create whole dwelling total columns
    # collect relevant variable names
    zone_ref = list(project_dict["Zone"].keys())[0]
    variables = [
        s.replace(f"{zone_ref}: ", "")
        for s in heat_balance_df.loc[:, heat_balance_df.columns.str.contains(zone_ref)].columns
    ]
    # sum the zone columns for the variable to populate the relevant total column
    zone_names = project_dict["Zone"].keys()
    for variable in variables:
        heat_balance_df[f"Total {variable}"] = heat_balance_df[
            [f"{z_n}: {variable}" for z_n in zone_names]
        ].sum(axis=1)

    # add a date time column
    heat_balance_df["datetime"] = convert_timestep_to_datetime(
        timestep=heat_balance_df["Timestep"],
        start_timestep=project_dict["SimulationTime"]["start"],
        step_size=project_dict["SimulationTime"]["step"],
    )

    return heat_balance_df
