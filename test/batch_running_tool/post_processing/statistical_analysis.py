#!/usr/bin/env python3

"""
This post-processing scripts performs the following statistical analysis on
a list of test runs (with unique IDs) pairs:
    % change for the following metrics
        Annual_SH_Demand,
        Annual_HW_Demand,
        Annual_Ventilation_kWh,
        Annual_Lighting_kWh,
        Annual_Pump/Fan_kWh,
        Annual_PV_Generation,
    CV(RMSE), NMBE, RMSE, MAE on the following metrics:
        Monthly_Average_Air_Temp
        week profiles for a typical winter week, spring week
        and summer week for the following metrics:
            Average_Winter_Week_Op_Temp
            Average_Spring_Week_Op_Temp
            Average_Summer_Week_Op_Temp
            Average_Winter_Week_Air_Temp
            Average_Spring_Week_Air_Temp
            Average_Summer_Week_Air_Temp
            Total_Winter_Week_Heat_Output
            Total_Spring_Week_Heat_Output
            Total_Summer_Week_Heat_Output
            Total_Winter_Week_Cooling_Output
            Total_Spring_Week_Cooling_Output
            Total_Summer_Week_Cooling_Output
"""

import os
import sys
import csv
import json
import pandas as pd
from itertools import combinations, permutations
import numpy as np
from math import sqrt

from post_processing_tools import expand_results_df
from format_dates import (
    convert_timestep_to_datetime,
    typical_winter_week,
    typical_summer_week,
    typical_transition_week,
)


def create_statistical_tests_dfs(folderpath, variables, months=12, ts_in_week=336):
    """
    Creates empty MultiIndex DataFrames that will hold data for relevant key
    metrics of the statistical analysis script.

    Args:
        folderpath - path to the folder holding the input JSON and results
                     created via the batch_tool script.
        months - number of months needed for monthly average air temp
    """
    annual_mi, month_mi, week_mi, zone_mi = create_statistical_tests_df_columns(
        folderpath=folderpath, variables=variables, months=months
    )

    annual_arr, month_arr, week_arr, zone_arr = create_statistical_tests_arrays(
        annual_mi, week_mi, month_mi, zone_mi, ts_in_week=ts_in_week
    )

    annual_df = pd.DataFrame([annual_arr], columns=annual_mi)
    month_df = pd.DataFrame([month_arr], columns=month_mi)
    week_df = pd.DataFrame(week_arr, columns=week_mi, index=np.arange(ts_in_week))
    zone_df = pd.DataFrame(zone_arr, columns=zone_mi, index=np.arange(ts_in_week))

    return annual_df, month_df, week_df, zone_df


def create_statistical_tests_df_columns(folderpath, variables, months=12):
    """
    This function creates MultiIndex column names for DataFrames that will hold
    data for relevant key metrics of the statistical analysis script.

    Args:
        folderpath - path to the folder holding the input JSON and results
                     created via the batch_tool script.
        variables - dictionary of variables to be analysed under annual, month,
                    week and zone results
        months - number of months needed for monthly average air temp
    """

    annual_cols = list(
        zip(
            np.repeat(variables["run_ids"], len(variables["annual_vars"])),
            np.tile(variables["annual_vars"], len(variables["run_ids"])),
        )
    )
    annual_mi = pd.MultiIndex.from_tuples(annual_cols, names=["RunID", "Variable"])

    month_cols = []
    for run in variables["run_ids"]:
        for var in variables["month_vars"]:
            for month in [f"Month{m}" for m in range(1, months + 1)]:
                month_cols.append((run, var, month))
    month_mi = pd.MultiIndex.from_tuples(month_cols, names=["RunID", "Variable", "Month"])

    week_cols = []
    for run in variables["run_ids"]:
        for var in variables["week_vars"]:
            for week in variables["weeks"]:
                week_cols.append((run, var, week))
    week_mi = pd.MultiIndex.from_tuples(week_cols, names=["RunID", "Variable", "Week"])

    # loop through runs to collect all zone names available
    zone_cols = []
    for run_id in variables["run_ids"]:
        json_path = os.path.join(folderpath, run_id + ".json")
        with open(json_path) as json_file:
            project_dict = json.load(json_file)
        for var in variables["zone_vars"]:
            for zone_name in list(project_dict["Zone"].keys()):
                for week in variables["weeks"]:
                    zone_cols.append((run_id, var, zone_name, week))
    zone_mi = pd.MultiIndex.from_tuples(zone_cols, names=["RunID", "Variable", "Zone", "Week"])

    return annual_mi, month_mi, week_mi, zone_mi


def create_statistical_tests_arrays(annual_mi, week_mi, month_mi, zone_mi, ts_in_week=336):
    """
    This function creates empty arrays to hold data for relevant key metrics of
    the statistical analysis script.

    Args:
        folderpath - path to the folder holding the input JSON and results
                     created via the batch_tool script.
        months - number of months needed for monthly average air temp
    """
    annual_arr = np.full(annual_mi.shape, fill_value=np.nan)
    month_arr = np.full(month_mi.shape, fill_value=np.nan)
    week_arr = np.full((ts_in_week, week_mi.shape[0]), fill_value=np.nan)
    zone_arr = np.full((ts_in_week, zone_mi.shape[0]), fill_value=np.nan)

    return annual_arr, month_arr, week_arr, zone_arr


def variables_for_analysis(folderpath, config_filepath):
    """
    Get list variable names to names used for statistics.
    These may optionally be read from a JSON file,
    which should be accompanying the configuration JSON and named as:
    [config filename]_statsvars.json'

    Args:
        folderpath - path to the folder holding results created via the batch_tool
                     script.
        config_filepath - path to the configuration JSON file.
    """

    # if a _statsvars.json file accompanies the config file
    # process the variables specified in the _statsvar,json file
    # otherwise, use defaults variables.

    statsvars_filepath = config_filepath.split(".")[0] + "_statsvars.json"
    if os.path.isfile(statsvars_filepath):
        with open(statsvars_filepath) as json_file:
            json_dict = json.load(json_file)

        vars = json_dict["variables"]
        annual_vars = vars["annual_vars"]
        month_vars = vars["month_vars"]
        week_vars = vars["week_vars"]
        zone_vars = vars["zone_vars"]
        settings = json_dict["settings"]
        weeks = settings["weeks"]

    else:
        annual_vars = [
            "space heat demand Total",
            "DHW: demand energy (including distribution pipework losses)",
            "Ventilation Systems",
            "Lighting Energy Use",
            "Pumps and Fans Energy Use",
            "PV Generation",
        ]
        month_vars = ["internal air temp Average"]
        week_vars = [
            "operative temp Average",
            "internal air temp Average",
            "Space Heat Output",
            "Space Cooling Output",
        ]
        zone_vars = ["operative temp", "internal air temp"]
        weeks = ["Winter_Week", "Spring_Week", "Summer_Week"]

    run_filepaths = [f for f in os.listdir(folderpath) if f.endswith(".json")]
    run_ids = [f.split(".")[0] for f in run_filepaths]

    all_vars = {
        "run_filepaths": run_filepaths,
        "run_ids": run_ids,
        "annual_vars": annual_vars,
        "month_vars": month_vars,
        "week_vars": week_vars,
        "weeks": weeks,
        "zone_vars": zone_vars,
    }

    return all_vars


def statistical_tests_raw_data_df(folderpath, variables, months=12):
    """
    Collects output data for relevant metrics from each test run
    to perform statistical analysis.

    Args:
        folderpath - path to the folder holding the input JSON and results
                     created via the batch_tool script.
        variables - dictionary of variables to be analysed under annual, month,
                    week and zone results
    """
    idx = pd.IndexSlice

    annual_df, month_df, week_df, zone_df = create_statistical_tests_dfs(
        folderpath=folderpath, variables=variables
    )

    for run_file in variables["run_filepaths"]:
        json_path = os.path.join(folderpath, run_file)
        with open(json_path) as json_file:
            project_dict = json.load(json_file)
        RunID = run_file.split(".")[0]
        results_folder = os.path.join(folderpath, RunID + "__results")

        results_filepath = os.path.join(results_folder, RunID + "__core__results.csv")
        results_df = pd.read_csv(results_filepath, skiprows=[1])
        results_df = results_df.astype(float)
        # expand results df with additional summary columns such as whole dwelling totals etc.
        results_df = expand_results_df(results_df, project_dict)
        results_df.to_csv(os.path.join(folderpath, "all_results_dataframe.csv"))

        # Get annual results
        annual_df.loc[:, (RunID, variables["annual_vars"])] = (
            results_df.loc[:, variables["annual_vars"]].sum(axis=0).values
        )

        # Get month results
        for month in range(1, months + 1):
            # NB: mean aggregate might not be suitable for future added variables
            month_df.loc[:, idx[RunID, variables["month_vars"], f"Month{month}"]] = (
                results_df[results_df["datetime"].dt.month == month]
                .mean()[variables["month_vars"]]
                .values.astype(float)
            )

        # Get typical weeks profiles
        weeks = {
            "Winter_Week": typical_winter_week,
            "Spring_Week": typical_transition_week,
            "Summer_Week": typical_summer_week,
        }
        for week_name, week_number in weeks.items():
            week_df.loc[:, idx[RunID, variables["week_vars"], week_name]] = results_df[
                results_df["datetime"].dt.isocalendar().week == week_number
            ][variables["week_vars"]].values

            # Get weekly profiles by zone
            for zone_name in project_dict["Zone"].keys():
                zone_df.loc[:, idx[RunID, variables["zone_vars"], zone_name, week_name]] = (
                    results_df[results_df["datetime"].dt.isocalendar().week == week_number][
                        [f"{zone_name}: {z}" for z in variables["zone_vars"]]
                    ].values
                )

    return annual_df, month_df, week_df, zone_df


def get_run_comparison_pairs(run_ids):
    """
    Create all possible comninations of run_id pairs.
    Meaning all cases created by the conifuration file
    will be compared with eachother.

    Args:
        run_ids - list of all run IDs

    Returns:
        row_pairs - list of test run pairs
    """
    row_pairs = list(combinations(run_ids, 2))
    return row_pairs


def populate_statistical_tests_df(raw_data_df, row_pairs):
    """
    Performs statistical analysis on a set of test run results,
    given a list of test runs pairs to compare.

    Args:
        raw_data_df - dataframe holding raw output results for key metrics
                      on which to perform statistical tests.
        row_pairs   - list of test run pairs on which to perform
                      statistical analysis.

    Returns:
        stat_analysis_df - dataframe with same structure as raw_data_df
                           but which holds statistical test results.
    """

    idx = pd.IndexSlice

    if raw_data_df.shape[0] == 1:
        stat_analysis_sers = []

        for row_pair in row_pairs:
            # from the row data, collect the indexes of the relevant runs to compare
            # i.e. which lines of raw data we will compare
            index_0 = raw_data_df.loc[0, idx[row_pair[0], :, :]].index
            index_1 = raw_data_df.loc[0, idx[row_pair[1], :, :]].index
            # loop through each column of the raw data DataFrame (i.e. through each run results)

            perc_change = (
                raw_data_df.loc[:, index_0].droplevel(0, axis=1)
                - raw_data_df.loc[:, index_1].droplevel(0, axis=1)
            ) / raw_data_df.loc[:, index_0].droplevel(0, axis=1)
            if perc_change.columns.nlevels == 1:
                perc_change = perc_change.rename(
                    columns={var: var + " % change" for var in perc_change.columns},
                    index={perc_change.index.values[0]: row_pair[0] + " and " + row_pair[1]},
                )
            elif perc_change.columns.nlevels == 2:
                perc_change = perc_change.rename(
                    columns={
                        var: var + " % change" for var in perc_change.columns.get_level_values(0)
                    },
                    level=0,
                )
                perc_change = perc_change.rename(
                    index={perc_change.index.values[0]: row_pair[0] + " and " + row_pair[1]}
                )
            # Turn into a series
            perc_change = perc_change.squeeze(axis=0)

            stat_analysis_sers.append(perc_change)

        stat_analysis_df = pd.concat(stat_analysis_sers, axis=1)

        return stat_analysis_df

    elif raw_data_df.shape[0] > 1:
        # empty list for collecting stats dfs for each comparison
        comp_dfs = []

        for row_pair in row_pairs:
            if raw_data_df.columns.nlevels == 3:
                prof_0 = raw_data_df.loc[:, idx[row_pair[0], :, :]].droplevel(0, axis=1)
                prof_1 = raw_data_df.loc[:, idx[row_pair[1], :, :]].droplevel(0, axis=1)
            elif raw_data_df.columns.nlevels == 4:
                prof_0 = raw_data_df.loc[:, idx[row_pair[0], :, :, :]].droplevel(0, axis=1)
                prof_1 = raw_data_df.loc[:, idx[row_pair[1], :, :, :]].droplevel(0, axis=1)

            prof_diff = prof_0 - prof_1
            prof_diff_squared = prof_diff**2

            # CV(RMSE)
            cv_RMSE = np.sqrt(prof_diff_squared.mean(axis=0)) / (
                (prof_0.mean(axis=0) + prof_1.mean(axis=0)) / 2
            )
            cv_RMSE.index = pd.MultiIndex.from_product(
                cv_RMSE.index.levels + [["CV(RMSE)"]], names=list(cv_RMSE.index.names) + ["Stat"]
            )
            # NMBE
            NMBE = prof_diff.mean(axis=0) / ((prof_0.mean(axis=0) + prof_1.mean(axis=0)) / 2)
            NMBE.index = pd.MultiIndex.from_product(
                NMBE.index.levels + [["NMBE"]], names=list(NMBE.index.names) + ["Stat"]
            )
            # RMSE
            RMSE = np.sqrt(prof_diff_squared.mean(axis=0))
            RMSE.index = pd.MultiIndex.from_product(
                RMSE.index.levels + [["RMSE"]], names=list(RMSE.index.names) + ["Stat"]
            )
            # MAE
            MAE = np.abs(prof_diff.mean(axis=0))
            MAE.index = pd.MultiIndex.from_product(
                MAE.index.levels + [["MAE"]], names=list(MAE.index.names) + ["Stat"]
            )

            all_row_pair_stat = pd.concat(objs=[cv_RMSE, NMBE, RMSE, MAE], axis=0)

            all_row_pair_stat = all_row_pair_stat.rename(row_pair[0] + " and " + row_pair[1])

            comp_dfs.append(all_row_pair_stat)

        stats_analysis_df = pd.concat(comp_dfs, axis=1)

        return stats_analysis_df


def statistical_analysis(folderpath, config_filepath):
    """
    Calls upon relevant functions from the module to
    perform statistical analysis and publish results and
    raw data in CSV files.

    Args:
        folderpath      - folder path to the input JSON and results folder created
                          via the batch_tool script.
        config_filepath - file path to the configuration JSON.
    """
    all_vars = variables_for_analysis(folderpath, config_filepath=config_filepath)
    annual_df, month_df, week_df, zone_df = statistical_tests_raw_data_df(
        folderpath, variables=all_vars
    )
    row_pairs = get_run_comparison_pairs(run_ids=all_vars["run_ids"])

    annual_stat_analysis_df = populate_statistical_tests_df(annual_df, row_pairs)
    month_stat_analysis_df = populate_statistical_tests_df(month_df, row_pairs)
    week_stat_analysis_df = populate_statistical_tests_df(week_df, row_pairs)
    zone_stat_analysis_df = populate_statistical_tests_df(zone_df, row_pairs)

    # saved transposed dfs to CSV
    annual_stat_analysis_df.T.to_csv(folderpath + "/annual_statistical_results.csv")
    month_stat_analysis_df.T.to_csv(folderpath + "/month_statistical_results.csv")
    week_stat_analysis_df.T.to_csv(folderpath + "/week_statistical_results.csv")
    zone_stat_analysis_df.T.to_csv(folderpath + "/zone_statistical_results.csv")

    # write raw results to csv
    annual_df.to_csv(folderpath + "/annual_statistical_raw_dataframe.csv")
    month_df.to_csv(folderpath + "/month_statistical_raw_dataframe.csv")
    week_df.to_csv(folderpath + "/week_statistical_raw_dataframe.csv")
    zone_df.to_csv(folderpath + "/zone_statistical_raw_dataframe.csv")
