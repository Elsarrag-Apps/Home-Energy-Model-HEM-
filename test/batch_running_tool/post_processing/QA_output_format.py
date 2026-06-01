#!/usr/bin/env python3

"""
This script processes output files and produces a csv file
with results formated to populate the QA team phase 1 excel spreadsheet.
"""

import os
import sys
import csv
import json
import pandas as pd

from post_processing_tools import expand_results_df, expand_heat_balance_df
from format_dates import convert_timestep_to_datetime


def create_QA_output_format_columns():
    """
    This function creates an empty data frame where columns are organised as required by
    the QA sensitivity analysis spreadsheet.
    """
    columns = [
        "Run_id",
        "Mean Internal Temperature",
        "Opaque Fabric Element Losses",
        "Transparent Fabric Element Losses",
        "Ground Fabric Element Losses",
        "Thermally Controlled Element Losses",
        "Non-Thermally Controlled Element Losses",
        "Thermal Bridge Losses",
        "Infiltration and Ventilation Losses",
        "",
        "Solar Gains",
        "Internal Gains",
        "Space Heating Demand",
        "Space Heating Energy Use",
        "Unmet Demand",
        "",
        "Distribution Losses",
        "Primary Pipework Losses",
        "Heat Source Output",
        "DHW Demand",
        "Total DHW Energy Use",
        "",
        "Window Hours Open",
        "Space Cooling Demand",
        "Space Cooling Use",
        "",
        "Ventilation Systems",
        "Space/DHW Pumping Energy",
        "Appliances",
        "Cooking",
        "Lighting",
        "",
        "Ductwork",
        "",
        "",
        "PV Generation",
        "",
        "",
        "",
        "",
    ]

    monthly_headers = [
        "Mean Internal Temperature",
        "Opaque Fabric Element Losses",
        "Transparent Fabric Element Losses",
        "Ground Fabric Element Losses",
        "Thermally Controlled Element Losses",
        "Non-Thermally Controlled Element Losses",
        "Thermal Bridge Losses",
        "Infiltration and Ventilation Losses",
        "",
        "Solar Gains",
        "Internal Gains",
        "Space Heating Demand",
        "Space Heating Energy Use",
    ]

    monthly_columns = []
    for month in range(1, 13):
        monthly_columns += [f"Month: {month} {item}" for item in monthly_headers]
    columns = columns + monthly_columns

    return columns


def postproc_QA_output_format(folderpath):
    """
    This function will loop through the results file of a given folder
    to create a CSV output file that collects output data in a format
    compatible with the QA sensitivity analysis spreadsheet.

    Args:
        folderpath - folder path to the input JSON and results folder created
                     via the batch_tool script.
    """

    postproc_cols = create_QA_output_format_columns()
    postproc_list = []

    run_filenames = [f for f in os.listdir(folderpath) if f.endswith(".json")]

    for run_file in run_filenames:
        json_path = os.path.join(folderpath, run_file)
        with open(json_path) as json_file:
            project_dict = json.load(json_file)

        run_id = run_file.split(".")[0]
        results_folder = os.path.join(folderpath, run_id + "__results")

        results_filepath = os.path.join(results_folder, run_id + "__core__results.csv")
        results_df = pd.read_csv(results_filepath, skiprows=[1])
        results_df = results_df.astype(float)
        # expand results df with additional summary columns such as whole dwelling totals etc.
        results_df = expand_results_df(results_df, project_dict)

        heat_balance_filepath = os.path.join(
            results_folder, run_id + "__core__results_heat_balance_external_boundary.csv"
        )
        heat_balance_df = pd.read_csv(heat_balance_filepath, skiprows=[0, 1, 2, 3, 5, 6])
        heat_balance_df = heat_balance_df.astype(float)
        heat_balance_df = expand_heat_balance_df(heat_balance_df, project_dict)
        heat_balance_df.to_csv("expanded_HP.csv", index=True)

        # create panda series for new row in postproc_df
        new_row = pd.Series({key: None for key in postproc_cols})
        new_row["Run_id"] = run_id

        new_row["Space Heating Energy Use"] = results_df["Space Heating Energy Use"].sum()
        new_row["Total DHW Energy Use"] = results_df["DHW Energy Use"].sum()
        new_row["Space/DHW Pumping Energy"] = results_df["Pumps and Fans Energy Use"].sum()
        new_row["Ventilation Systems"] = results_df["Ventilation Systems"].sum()
        new_row["Cooking"] = results_df["Cooking Energy Use"].sum()
        new_row["Appliances"] = results_df["Appliances Energy Use"].sum()
        new_row["Lighting"] = results_df["Lighting Energy Use"].sum()
        new_row["Space Heating Demand"] = results_df["space heat demand Total"].sum()
        new_row["Heat Source Output"] = results_df["Space Heat Output"].sum()
        new_row["Space Cooling Demand"] = results_df["space cool demand Total"].sum()
        new_row["DHW Demand"] = results_df[
            "DHW: demand energy (including distribution pipework losses)"
        ].sum()
        new_row["Unmet Demand"] = results_df["_unmet_demand: total"].sum()
        new_row["Ductwork"] = results_df["Ventilation: Ductwork gains"].sum()
        new_row["PV Generation"] = results_df["PV Generation"].sum()
        new_row["Mean Internal Temperature"] = results_df["internal air temp Average"].mean()

        new_row["Opaque Fabric Element Losses"] = heat_balance_df["Total opaque_fabric_ext"].sum()
        new_row["Transparent Fabric Element Losses"] = heat_balance_df[
            "Total transparent_fabric_ext"
        ].sum()
        new_row["Ground Fabric Element Losses"] = heat_balance_df["Total ground_fabric_ext"].sum()
        new_row["Thermally Controlled Element Losses"] = heat_balance_df[
            "Total ZTC_fabric_ext"
        ].sum()
        new_row["Non-Thermally Controlled Element Losses"] = heat_balance_df[
            "Total ZTU_fabric_ext"
        ].sum()
        new_row["Thermal Bridge Losses"] = heat_balance_df["Total thermal_bridges"].sum()
        new_row["Infiltration and Ventilation Losses"] = heat_balance_df[
            "Total infiltration_ventilation"
        ].sum()
        new_row["Solar Gains"] = heat_balance_df["Total solar gains"].sum()
        new_row["Internal Gains"] = heat_balance_df["Total internal gains"].sum()

        for month in range(1, 13):
            current_month_results_df = results_df[results_df["datetime"].dt.month == month]
            new_row[f"Month: {month} Mean Internal Temperature"] = current_month_results_df[
                "internal air temp Average"
            ].mean()
            new_row[f"Month: {month} Space Heating Demand"] = current_month_results_df[
                "space heat demand Total"
            ].sum()
            new_row[f"Month: {month} Space Heating Energy Use"] = current_month_results_df[
                "Space Heating Energy Use"
            ].sum()

            current_month_heat_balance_df = heat_balance_df[
                heat_balance_df["datetime"].dt.month == month
            ]
            new_row[f"Month: {month} Solar Gains"] = current_month_heat_balance_df[
                "Total solar gains"
            ].sum()
            new_row[f"Month: {month} Internal Gains"] = current_month_heat_balance_df[
                "Total internal gains"
            ].sum()
            new_row[f"Month: {month} Thermal Bridge Losses"] = current_month_heat_balance_df[
                "Total thermal_bridges"
            ].sum()
            new_row[f"Month: {month} Infiltration and Ventilation Losses"] = (
                current_month_heat_balance_df["Total infiltration_ventilation"].sum()
            )
            new_row[f"Month: {month} Opaque Fabric Element Losses"] = current_month_heat_balance_df[
                "Total opaque_fabric_ext"
            ].sum()
            new_row[f"Month: {month} Transparent Fabric Element Losses"] = (
                current_month_heat_balance_df["Total transparent_fabric_ext"].sum()
            )
            new_row[f"Month: {month} Ground Fabric Element Losses"] = current_month_heat_balance_df[
                "Total ground_fabric_ext"
            ].sum()
            new_row[f"Month: {month} Thermally Controlled Element Losses"] = (
                current_month_heat_balance_df["Total ZTC_fabric_ext"].sum()
            )
            new_row[f"Month: {month} Non-Thermally Controlled Element Losses"] = (
                current_month_heat_balance_df["Total ZTU_fabric_ext"].sum()
            )

        postproc_list.append(pd.DataFrame([new_row]))
        postproc_df = pd.concat(postproc_list, ignore_index=True)

    csv_out_filepath = os.path.join(folderpath, "results_QA_format.csv")
    columns_order = create_QA_output_format_columns()
    postproc_df = postproc_df.reindex(columns=columns_order)
    postproc_df.to_csv(csv_out_filepath, index=True)
