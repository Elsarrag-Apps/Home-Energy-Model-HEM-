import pandas as pd
import argparse
import os
import warnings

import reformat_data_historic_results as reformat_data_historic
import impact_assessment_figures as figures


def perform_impact_assessment(
    results_folder,
    model_version_summary_path,
    archetypes,
    impact_testing_results_folder,
):
    """
    This function performs the impact assessment.
    It calls upon functions to collate all output CSV files
    into master dataframes.
    Then calls functions to filter the master dataframes into
    sub-dataframes to produce figures of interest.

    Args:
        results_folder        - folder path to all JSON files from
                                previous HEM versions and their results.
        model_version_summary - content of a CSV file holding information on the
                                results_folder content.
                                The file holds a simple table with the following column:
                                commit_id, test_suite_id, commit date, description
        archetypes            - list of JSON filenames held within the results_folder to be tested.
        impact_testing_results_folder - path to the folder that will hold all impact assessment outputs.
    """
    # TODO improve docstring once script will be finalised.

    # trigger warning message
    warnings.warn(
        "The impact assessment tool was developed for compatibility with "
        "input and result files up to HEM v0.32, "
        "and was tested on a limited set of files.",
        stacklevel=2,
    )

    # read in model version summary table
    model_version_summary = reformat_data_historic.read_model_version_summary(
        model_version_summary_path
    )

    # create master datafreames
    all_results_df, all_heat_balance_air_node_results_df, all_heat_balance_external_results_df = (
        reformat_data_historic.create_master_dataframes(
            results_folder,
            model_version_summary,
            archetypes,
            impact_testing_results_folder,
        )
    )

    annual_energy_df = figures.create_annual_energy_df(
        all_results_df, impact_testing_results_folder
    )

    figures.create_annual_energy_use_figures(
        annual_energy_df,
        archetypes,
        impact_testing_results_folder,
    )

    figures.create_annual_demand_figures(
        annual_energy_df,
        archetypes,
        impact_testing_results_folder,
    )

    heat_balance_dict = {
        "heat_balance_air_node": all_heat_balance_air_node_results_df,
        "heat_balance_external_boundary": all_heat_balance_external_results_df,
    }
    for name, df in heat_balance_dict.items():
        # break down master dataframes to create charts
        figures.create_annual_heat_balance_figures(
            df,
            archetypes,
            impact_testing_results_folder,
            f"annual_{name}",
        )

        figures.create_monthly_heat_balance_figures(
            df,
            archetypes,
            impact_testing_results_folder,
            f"monthly_{name}",
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HEM Impact Assessment")

    parser.add_argument(
        "older_results_folder_path",
        type=str,
        help="path to folder holding results from previous versions of HEM.",
    )

    parser.add_argument(
        "model_version_summary",
        type=str,
        help="path to file holding commit IDs and description. "
        + "The columns to the file should be: commit_id, test_suite_id, date, description",
    )

    parser.add_argument(
        "archetypes",
        type=str,
        nargs="+",
        help="list of JSON filenames to test "
        + "held within the older_results_folder_path (first argument). "
        + "The filenames should be given without their extension .json and separated by a space. "
        + "Fore example: DE DA VF",
    )
    cli_args = parser.parse_args()

    # filepath to model outputs
    results_folder = cli_args.older_results_folder_path
    model_version_summary_path = cli_args.model_version_summary
    archetypes = cli_args.archetypes

    impact_testing_results_folder = model_version_summary_path.replace(".csv", "__results")
    if not os.path.exists(impact_testing_results_folder):
        os.makedirs(impact_testing_results_folder)

    perform_impact_assessment(
        results_folder,
        model_version_summary_path,
        archetypes,
        impact_testing_results_folder,
    )
