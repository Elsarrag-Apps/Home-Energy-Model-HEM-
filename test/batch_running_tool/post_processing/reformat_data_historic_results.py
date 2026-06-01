import pandas as pd
import reformat_data
import warnings
import os

from format_dates import convert_timestep_to_datetime
from post_processing_tools import get_kwh_headings, get_temperature_headings


def read_model_version_summary(path):
    """
    Read in model_version_summary CSV with columns commit_id, test_suite_id, description and date.
    Args:
        path: string; path to model version summary.
    Returns:
        model_version_summary CSV as dataframe ordered by date with:
        -  with text columns formatted as category
        - date column formatted as date

    """
    df = pd.read_csv(
        filepath_or_buffer=path,
        dtype={"commit_id": "object", "test_suite_id": "string", "description": "string"},
        parse_dates=["date"],
    )
    df = df.sort_values(by=["date"])

    return df


def get_TFA(project_dict):
    """
    Calculates the total floor area (TFA) from the input project_dict.

    Args:
        project_dict - dictionary created from an input JSON file.

    Returns:
        TFA - total floor area, m2
    """
    TFA = 0
    for z_n, zone_data in project_dict["Zone"].items():
        TFA += zone_data["area"]
    return TFA


def add_run_ID_and_chronology_column(df, model_version_summary):
    """
    This function includes the test suite ID and chronology of HEM versions
    defined in model_version_summary to a given master dataframe of results.
    The test suite ID helps describing the commit ID.
    The chronology helps sorting results in chronological order
    (the date is not always suitable as some commits branch off older
    versions of the engine).

    Args:
        df - a dataframe created by functions:
             create_all_results_df
             create_all_heat_balance_results_df
        model_version_summary - summary of commit IDs,
             commit date, test suite IDs and description
             as created by the function read_model_version_summary
    Returns:
        df - dataframe with added index for test suite ID
    """
    # commit_id as index and add blank units index to model_version_summary columns (needed for join)
    model_version_summary = model_version_summary.set_index("commit_id")

    model_version_summary.columns = pd.MultiIndex.from_product(
        [model_version_summary.columns, [""]]
    )

    df = df.join(model_version_summary, on="commit_id", how="left")
    df = df.set_index(["chronology", "test_suite_id"], append=True)

    return df


def expand_results_df(all_results_df, results_dict):
    """
    For a given all_results_df, the function
    adds relevant columns to get whole dwelling
    total energy use/demand/output per end-uses
    whole dwelling volume weighted temperatures.


    Args:
        results_dict     - dictionary created by function
                           create_results_dictionary
        all_results_df   - dataframe created by function
                           create_all_results_df

    Returns:
        all_results_df   - all_results_df with additional columns
    """
    all_results_df = all_results_df.sort_index()

    for commit_id, archetypes in results_dict.items():
        for archetype, archetype_dict in archetypes.items():
            project_dict = archetype_dict["input_dict"]

            # add columns for whole dwelling volume-weighted avergae temperatures

            headings_dict_no_units = get_temperature_headings(project_dict)
            # create headings_dict which is based on headings_dict_no_units
            # but with column names as tuples like: ("column name", "units")
            headings_dict = {}
            for new_column, columns in headings_dict_no_units.items():
                for columns_dict in columns:
                    columns_dict["column"] = (columns_dict["column"], "[deg C]")
                headings_dict[(new_column, "[deg C]")] = columns

            # loop through the headings_dict to create additional columns
            # for volume weighted average temperatures
            for column, columns_volumes_list in headings_dict.items():
                if column not in all_results_df.columns:
                    all_results_df[column] = 0.0
                # Calculate operative temperature and internal temperature for each zone, and for the whole dwelling (weighted average)
                volume_tot = 0
                for columns_volumes_dict in columns_volumes_list:
                    all_results_df.loc[pd.IndexSlice[archetype, commit_id, :], column] = (
                        all_results_df.loc[
                            pd.IndexSlice[archetype, commit_id, :], columns_volumes_dict["column"]
                        ]
                        * columns_volumes_dict["volume"]
                    ) + all_results_df.loc[pd.IndexSlice[archetype, commit_id, :], column]
                    volume_tot += columns_volumes_dict["volume"]
                all_results_df.loc[pd.IndexSlice[archetype, commit_id, :], column] = (
                    all_results_df.loc[pd.IndexSlice[archetype, commit_id, :], column].div(
                        volume_tot
                    )
                )

            # add columns for whole dwelling kWh figures
            #
            # collect headings_dict_no_units for kWh figures
            # get the results_df for the specific archetype
            results_df = all_results_df.loc[pd.IndexSlice[archetype, :], :]
            # remove the units row for compatibility with function get_kwh_headings
            results_df.columns = results_df.columns.droplevel(1)
            headings_dict_no_units = get_kwh_headings(project_dict, results_df)

            # Initialised the headings_dict
            headings_dict = {}
            # convert headings_dict items to tuples like: ("column name", "units")
            for new_column, columns in headings_dict_no_units.items():
                headings_dict[(new_column, "[kWh]")] = [(x, "[kWh]") for x in columns]

            # loop through the headings_dict to create additional columns
            # for whole dwelling energy use/demand/output per end-uses
            for column, results_columns in headings_dict.items():
                # add the new column name to all_results_df if it doesn't exist
                if column not in all_results_df.columns:
                    all_results_df[column] = 0.0
                # populate the relevant new column
                all_results_df.loc[pd.IndexSlice[archetype, commit_id, :], column] = (
                    all_results_df.loc[pd.IndexSlice[archetype, commit_id, :], results_columns].sum(
                        axis=1
                    )
                )

            # add column for total floor area (used to get kWh/m2 figures)
            TFA = get_TFA(project_dict)
            column_TFA = ("Total: floor area", "[m2]")
            all_results_df.loc[pd.IndexSlice[archetype, :], column_TFA] = TFA

            # add columns for zone area
            for z_name, z_dict in project_dict["Zone"].items():
                floor_area = z_dict["area"]
                column_area = (f"{z_name}: floor area", "[m2]")
                all_results_df.loc[pd.IndexSlice[archetype, :], column_area] = floor_area

    # add a datetime column
    all_results_df.loc[:, ("datetime", "[yyyy-mm-dd  hh:mm:ss]")] = convert_timestep_to_datetime(
        timestep=all_results_df.loc[:, ("Timestep", "[count]")],
        start_timestep=project_dict["SimulationTime"]["start"],
        step_size=project_dict["SimulationTime"]["step"],
    )

    return all_results_df


def expand_heat_balance_df(heat_balance_df, project_dict):
    """
    For a given heat_balance_df, the function :
        - Converts data in every column from W to kWh/m2.
        - creates additional columns to adds up
          zone breakdowns for whole dwelling totals.

    heat_balance_df is a dataframe created from
    a heat balance output CSV file i.e. output file ending with either:
        _heat_balance_air_node.csv
        __heat_balance_external_boundary.csv
        __heat_balance_internal_boundary.csv

    Args:
        project_dict      - dictionary from HEM input JSON file
        heat_balance_df   - data frame created from a heat balance results CSV
                            associated with the project_dict.
    Returns:
        heat_balance_df   - data frame with converted units and additional
                            columns for whole dwelling totals.
    """

    # Convert all columns to kWh/m2
    TFA = get_TFA(project_dict)
    stepping = project_dict["SimulationTime"]["step"]
    heat_balance_df.loc[:, heat_balance_df.columns.get_level_values(0) != "Timestep"] = (
        heat_balance_df.loc[:, heat_balance_df.columns.get_level_values(0) != "Timestep"].mul(
            stepping / 1000 / TFA
        )
    )

    # rename units from W to kWh
    w_to_kwh = lambda col: "[kWh/m2]" if col == "[W]" else col
    heat_balance_df = heat_balance_df.rename(w_to_kwh, axis="columns")

    # the external boundary heat balance has additional breakdowns for fabric
    # heat loss. Sum the relevant fabric columns to print one summary fabric column
    for z_name in project_dict["Zone"].keys():
        fabric_columns = [
            (f"{z_name}: fabric_ext_air_convective", "[kWh/m2]"),
            (f"{z_name}: fabric_ext_air_radiative", "[kWh/m2]"),
            (f"{z_name}: fabric_ext_sol", "[kWh/m2]"),
            (f"{z_name}: fabric_ext_sky", "[kWh/m2]"),
        ]
        if fabric_columns[0] in heat_balance_df.columns:
            heat_balance_df[(f"{z_name}: fabric", "[kWh/m2]")] = heat_balance_df[
                fabric_columns
            ].sum(axis=1)

            # delete redundant fabric columns
            fabric_columns = [
                (f"{z_name}: fabric_ext_air_convective", "[kWh/m2]"),
                (f"{z_name}: fabric_ext_air_radiative", "[kWh/m2]"),
                (f"{z_name}: fabric_ext_sol", "[kWh/m2]"),
                (f"{z_name}: fabric_ext_sky", "[kWh/m2]"),
                (f"{z_name}: opaque_fabric_ext", "[kWh/m2]"),
                (f"{z_name}: transparent_fabric_ext", "[kWh/m2]"),
                (f"{z_name}: ground_fabric_ext", "[kWh/m2]"),
                (f"{z_name}: ZTC_fabric_ext", "[kWh/m2]"),
                (f"{z_name}: ZTU_fabric_ext", "[kWh/m2]"),
            ]
            for i in fabric_columns:
                del heat_balance_df[i]
        else:
            break
    # create whole dwelling total columns
    # collect relevant variable names
    zone_ref = list(project_dict["Zone"].keys())[0]
    variables = [
        s.replace(f"{zone_ref}: ", "")
        for s in list(
            filter(lambda col: zone_ref in col, heat_balance_df.columns.get_level_values(0))
        )
    ]

    # sum the zone columns for the variable to populate the relevant total column
    zone_names = project_dict["Zone"].keys()
    for variable in variables:
        heat_balance_df[(f"Total: {variable}", "[kWh/m2]")] = heat_balance_df[
            [(f"{z_n}: {variable}", "[kWh/m2]") for z_n in zone_names]
        ].sum(axis=1)

    # add a date time column
    heat_balance_df[("datetime", "[yyyy-mm-dd  hh:mm:ss]")] = convert_timestep_to_datetime(
        timestep=heat_balance_df[("Timestep", "index")],
        start_timestep=project_dict["SimulationTime"]["start"],
        step_size=project_dict["SimulationTime"]["step"],
    )

    # fix index name for compatiblitity with function get_columns_dataframe
    heat_balance_df.columns = pd.MultiIndex.from_tuples(
        heat_balance_df.set_axis(heat_balance_df.columns.values, axis=1)
        .rename(
            columns={
                ("Timestep", "index"): ("Timestep", "[count]"),
            }
        )
        .columns
    )

    return heat_balance_df


def fix_shifted_column_names(df, column_name_to_remove):
    """
    Removes redundant column name and shifts subsequent column names left.
    Args:
        df: dataframe
        column_name_to_remove: tuple; column to remove
    Returns:
        Corrected df
    """
    # get index of column to remove
    col_index = df.columns.get_loc(column_name_to_remove)

    # create multi-index with column name removed
    old_multiindex = df.set_axis(df.columns.values, axis=1).columns
    new_multiindex = pd.MultiIndex.from_tuples(old_multiindex.delete(col_index))

    # drop empty last column
    df = df.iloc[:, :-1]

    # reassign column names
    df.columns = new_multiindex

    return df


def swap_column_names(df, first_column, second_column):
    """
    Swap column names.
    Args:
        df: pandas dataframe with columns you want to swap
        first_column: name of first column
        second_column: name of second column
    Returns:
        df with names of first_column and second_column swapped (note the index number of each column is unchanged).
    """
    df.loc[:, [second_column, first_column]] = df[[first_column, second_column]].to_numpy()
    return df


def sum_columns_heat_balance(df, columns_to_sum, new_column):
    """
    Add columns into a new column.

    Args:
        df - dataframe to edit
        columns_to_sum - list of columns to sum
        new_column - new column name.
    """
    df[new_column] = df[columns_to_sum].sum(axis=1)
    df = df.drop(columns=columns_to_sum)

    return df


def create_results_dictionary(
    results_folder_path,
    commit_ids,
    archetypes,
):
    """
    Collect all the results and input jsons into a nested dictionary with the same file structure.

    Args:
        results_folder_path: string; path to results folder
        commit_ids: list of commit_ids (i.e. subfolder names)
        archetypes: list of archetypes (i.e. json files without file extensions)

    Returns:
        Dictionary with the same structure as the results folder.
        Results are read in as pandas dataframes.
        Input jsons are read in as dictionaries.

        i.e. this structure:
        {'commit_id_1': {
            'archetype_1': {
                'results_df': results_dataframe_1,
                'input_json': input_json_1
            },
        'archetype_2': {
                'results_df': results_dataframe_2,
                'input_json': input_json_2}},
        'commit_id_2': {
            'archetype_1': {
                'results_df': results_dataframe_1,
                'input_json': input_json_1
            },
        'archetype_2': {
                'results_df': results_dataframe_2,
                'input_json': input_json_2}}}
    """
    results_dict = {}

    for commit_id in commit_ids:
        commit_dict = {}

        for archetype in archetypes:
            # initialise archetype dictionary
            archetype_dict = {}

            # construct filepaths
            folder = os.path.join(
                os.path.join(results_folder_path, commit_id), f"{archetype}__results"
            )

            if not os.path.exists(folder):
                os.sys.exit(
                    f"Results folder missing for archetype {archetype} and commit_id {commit_id}."
                )

            # read in results files and input json and add to archetype dictionary
            json_filepath = os.path.join(folder, f"{archetype}.json")
            input_dict = reformat_data.read_run_json(json_filepath)

            if os.path.exists(json_filepath.replace(".json", "__core__results.csv")):
                results_df = pd.read_csv(
                    filepath_or_buffer=json_filepath.replace(".json", "__core__results.csv"),
                    header=[0, 1],
                )
                heat_balance_air_node_results_df = pd.read_csv(
                    filepath_or_buffer=json_filepath.replace(
                        ".json", "__core__results_heat_balance_air_node.csv"
                    ),
                    header=[4, 5],
                ).astype(float)
                heat_balance_external_results_df = pd.read_csv(
                    filepath_or_buffer=json_filepath.replace(
                        ".json", "__core__results_heat_balance_external_boundary.csv"
                    ),
                    header=[4, 5],
                ).astype(float)
            else:
                warnings.warn(
                    f"Results missing for archetype {archetype} and commit_id {commit_id}."
                )

            archetype_dict["results_df"] = results_df
            archetype_dict["heat_balance_air_node_results_df"] = heat_balance_air_node_results_df
            archetype_dict["heat_balance_external_results_df"] = heat_balance_external_results_df
            archetype_dict["input_dict"] = input_dict
            commit_dict[archetype] = archetype_dict
            results_df = None
            input_dict = None
            archetype_dict = None

        results_dict[commit_id] = commit_dict

    return results_dict


def get_columns_dataframe(df):
    """
    Creates a dataframe summarising which metrics are available in dataframe df.

    Args:
        df, a results dataframe which includes the Timestep and [count] columns.

    Returns:
        A dataframe with columns for metric and units.
    """
    # take just one row of data
    df = df.iloc[[0], :]

    # pivot data to get dataframe of available columns
    if ("Timestep", "index") in df.columns:
        t = ("Timestep", "index")
    else:
        t = ("Timestep", "[count]")
    df = pd.melt(df, id_vars=[t])
    # tidy up column names
    df = df.rename(
        columns={
            "variable_0": "metric",
            "variable_1": "units",
        }
    )[["metric", "units"]]

    return df


def get_columns_summary_dataframe(
    results_dict,
    df_name,
):
    """
    Creates dataframe summarising which metrics are available in the main results file for different commits.
    Args:
        results_dict: dictionary created by create_results_dictionary function.
    Returns:
        dataframe with rows for each metric and boolean columns for each commit & archetype combination to indicate if column is present.
    """

    metric_df = pd.DataFrame(columns=["metric", "units"])

    for commit_id, commit_dict in results_dict.items():
        for archetype, archetype_dict in commit_dict.items():
            if df_name not in archetype_dict.keys():
                print(f"{archetype} not available for {commit_id}")
            elif df_name in archetype_dict.keys():
                # create a pivoted dataframe with columns for metric, units, commit ID and archetype
                df = get_columns_dataframe(archetype_dict[df_name])

                # add columns to indicate metrics are available for specified commit_id and archetype
                df[f"{commit_id} {archetype}"] = True

                # add to overall metric df
                metric_df = pd.merge(left=metric_df, right=df, how="outer", on=["metric", "units"])
                df = None
    return metric_df


def reformat_results_post_ground_changes(df, input_dict):
    """Changes format of results dataframe from pre 2024-04-18 to post 2024-04-18

    Args:
        df: pandas dataframe, raw main results file as pandas dataframe

    Returns:
        df dataframe with columns renamed to match 2024-04-18 version of the code (post ground changes).

    """
    update_columns_dict = {
        ("Ductwork gains", "[kWh]"): ("Ventilation: Ductwork gains", "[kWh]"),
        ("Hot Water Events", "[count]"): ("DHW: number of events", "[count]"),
        ("Hot water demand", "[litres]"): (
            "DHW: demand volume (including distribution pipework losses)",
            "[litres]",
        ),
        ("Hot water duration", "[mins]"): ("DHW: total event duration", "[mins]"),
        ("Hot water energy demand", "[kWh]"): (
            "DHW: demand energy (excluding distribution pipework losses)",
            "[kWh]",
        ),
        ("Pipework losses", "[kWh]"): ("DHW: distribution pipework losses", "[kWh]"),
        ("Ventilation system", "[kWh]"): ("mains elec: Ventilation system", "[kWh]"),
        ("_unmet_demand beta factor", "[ratio]"): ("_unmet_demand: beta factor", "[ratio]"),
        ("_unmet_demand diverted", "[kWh]"): ("_unmet_demand: diverted", "[kWh]"),
        ("_unmet_demand export", "[kWh]"): ("_unmet_demand: export", "[kWh]"),
        ("_unmet_demand from storage", "[kWh]"): ("_unmet_demand: from storage", "[kWh]"),
        ("_unmet_demand generated and consumed", "[kWh]"): (
            "_unmet_demand: generated and consumed",
            "[kWh]",
        ),
        ("_unmet_demand import", "[kWh]"): ("_unmet_demand: import", "[kWh]"),
        ("_unmet_demand to storage", "[kWh]"): ("_unmet_demand: to storage", "[kWh]"),
        ("_unmet_demand total", "[kWh]"): ("_unmet_demand: total", "[kWh]"),
    }

    for space_heat_system in input_dict["SpaceHeatSystem"].keys():
        update_columns_dict[(f"Heating system {space_heat_system}", "[kWh]")] = (
            f"{space_heat_system}: energy demand",
            "[kWh]",
        )
        update_columns_dict[(f"Heating system output {space_heat_system}", "[kWh]")] = (
            f"{space_heat_system}: energy output",
            "[kWh]",
        )

        if "EnergySupply" in input_dict["SpaceHeatSystem"][space_heat_system].keys():
            SH_energy_supply = input_dict["SpaceHeatSystem"][space_heat_system]["EnergySupply"]
            update_columns_dict[(f"{space_heat_system}", "[kWh]")] = (
                f"{SH_energy_supply}: {space_heat_system}",
                "[kWh]",
            )

    if "HeatSourceWet" in input_dict.keys():
        for heat_source_wet in input_dict["HeatSourceWet"].keys():
            HSW_energy_supply = input_dict["HeatSourceWet"][heat_source_wet]["EnergySupply"]
            update_columns_dict[(f"HeatPump_auxiliary: {heat_source_wet}", "[kWh]")] = (
                f"{HSW_energy_supply}: HeatPump_auxiliary: {heat_source_wet}",
                "[kWh]",
            )
            update_columns_dict[(f"{heat_source_wet}_water_heating", "[kWh]")] = (
                f"{HSW_energy_supply}: {heat_source_wet}_water_heating",
                "[kWh]",
            )
            for space_heat_system, SHS_dict in input_dict["SpaceHeatSystem"].items():
                if "HeatSource" in SHS_dict and SHS_dict["HeatSource"]["name"] == heat_source_wet:
                    update_columns_dict[
                        (f"{heat_source_wet}_space_heating: {space_heat_system}", "[kWh]")
                    ] = (
                        f"{HSW_energy_supply}: {heat_source_wet}_space_heating: {space_heat_system}",
                        "[kWh]",
                    )

    for zone in input_dict["Zone"].keys():
        update_columns_dict[(f"Internal air temp {zone}", "[deg C]")] = (
            f"{zone}: internal air temp",
            "[deg C]",
        )
        update_columns_dict[(f"Internal gains {zone}", "[W]")] = (f"{zone}: internal gains", "[W]")
        update_columns_dict[(f"Operative temp {zone}", "[deg C]")] = (
            f"{zone}: operative temp",
            "[deg C]",
        )
        update_columns_dict[(f"Solar gains {zone}", "[W]")] = (f"{zone}: solar gains", "[W]")
        update_columns_dict[(f"Space cool demand {zone}", "[kWh]")] = (
            f"{zone}: space cool demand",
            "[kWh]",
        )
        update_columns_dict[(f"Space heat demand {zone}", "[kWh]")] = (
            f"{zone}: space heat demand",
            "[kWh]",
        )
        update_columns_dict[(f"{zone}", "[kWh]")] = (f"_unmet_demand: {zone}", "[kWh]")

    for appliance, app_dict in input_dict["ApplianceGains"].items():
        app_energy_supply = app_dict["EnergySupply"]
        update_columns_dict[(f"{appliance}", "[kWh]")] = (
            f"{app_energy_supply}: {appliance}",
            "[kWh]",
        )

    energy_supplies = ["_unmet_demand"]
    energy_supplies += [es for es in input_dict["EnergySupply"].keys()]
    for energy_supply in energy_supplies:
        update_columns_dict[(f"{energy_supply} beta factor", "[ratio]")] = (
            f"{energy_supply}: beta factor",
            "[ratio]",
        )
        update_columns_dict[(f"{energy_supply} diverted", "[kWh]")] = (
            f"{energy_supply}: diverted",
            "[kWh]",
        )
        update_columns_dict[(f"{energy_supply} export", "[kWh]")] = (
            f"{energy_supply}: export",
            "[kWh]",
        )
        update_columns_dict[(f"{energy_supply} from storage", "[kWh]")] = (
            f"{energy_supply}: from storage",
            "[kWh]",
        )
        update_columns_dict[(f"{energy_supply} generated and consumed", "[kWh]")] = (
            f"{energy_supply}: generated and consumed",
            "[kWh]",
        )
        update_columns_dict[(f"{energy_supply} import", "[kWh]")] = (
            f"{energy_supply}: import",
            "[kWh]",
        )
        update_columns_dict[(f"{energy_supply} to storage", "[kWh]")] = (
            f"{energy_supply}: to storage",
            "[kWh]",
        )
        update_columns_dict[(f"{energy_supply} total", "[kWh]")] = (
            f"{energy_supply}: total",
            "[kWh]",
        )
    update_columns_dict[("hw cylinder", "[kWh]")] = ("_unmet_demand: hw cylinder", "[kWh]")

    if "HeatSource" in input_dict["HotWaterSource"]["hw cylinder"].keys():
        for cylinder_source, c_source_dict in input_dict["HotWaterSource"]["hw cylinder"][
            "HeatSource"
        ].items():
            if c_source_dict["type"] != "HeatSourceWet":
                c_energy_supply = c_source_dict["EnergySupply"]
                update_columns_dict[(f"{cylinder_source}", "[kWh]")] = (
                    f"{c_energy_supply}: {cylinder_source}",
                    "[kWh]",
                )
    elif input_dict["HotWaterSource"]["hw cylinder"]["type"] == "PointOfUse":
        energy_supply = input_dict["HotWaterSource"]["hw cylinder"]["EnergySupply"]
        update_columns_dict[("hw cylinder", "[kWh]")] = (f"{energy_supply}: hw cylinder", "[kWh]")

    for shower_name, shower_dict in input_dict["HotWaterDemand"]["Shower"].items():
        if shower_dict["type"] == "InstantElecShower":
            energy_supply = shower_dict["EnergySupply"]
            update_columns_dict[(f"{shower_name}", "[kWh]")] = (
                f"{energy_supply}: {shower_name}",
                "[kWh]",
            )

    df.columns = pd.MultiIndex.from_tuples(
        df.set_axis(df.columns.values, axis=1).rename(columns=update_columns_dict).columns
    )
    return df


def reformat_results_post_20240628(df, input_dict):
    """
    Changes format of results dataframe from pre 2024-06-28 to post 2024-06-28
    Changes introduced with commit ID: 49071ec9

    Args:
        df: pandas dataframe, raw main results file as pandas dataframe

    Returns:
        df dataframe with columns renamed to match 2024-06-28 version of the code.

    """
    update_columns_dict = {}
    energy_supplies = ["_unmet_demand"]
    energy_supplies += [es for es in input_dict["EnergySupply"].keys()]
    for energy_supply in energy_supplies:
        update_columns_dict[(f"{energy_supply}: to storage", "[kWh]")] = (
            f"{energy_supply}: generation to storage",
            "[kWh]",
        )

    df.columns = pd.MultiIndex.from_tuples(
        df.set_axis(df.columns.values, axis=1).rename(columns=update_columns_dict).columns
    )
    return df


def reformat_air_node_hb_results(df):
    """Changes format of results dataframe from pre 2024-04-18 to post 2024-04-18

    Args:
        df: pandas dataframe, raw main results file as pandas dataframe

    Returns:
        df dataframe with columns renamed to match 2024-04-18 version of the code (post ground changes).

    """

    # values are given as absolutes, but we need losses to be negative for charts
    change_sign = [column for column in df.columns.get_level_values(0) if "loss" in column]
    df.loc[:, change_sign] = df.loc[:, change_sign] * -1

    df.columns = pd.MultiIndex.from_tuples(
        df.set_axis(df.columns.values, axis=1)
        .rename(
            columns={
                ("zone 1: heat loss through thermal bridges", "[W]"): (
                    "zone 1: thermal_bridges",
                    "[W]",
                ),
                ("zone 1: heat loss through infiltration_ventilation", "[W]"): (
                    "zone 1: infiltration_ventilation",
                    "[W]",
                ),
                ("zone 1: fabric heat loss", "[W]"): ("zone 1: fabric", "[W]"),
                ("zone 2: heat loss through thermal bridges", "[W]"): (
                    "zone 2: thermal_bridges",
                    "[W]",
                ),
                ("zone 2: heat loss through infiltration_ventilation", "[W]"): (
                    "zone 2: infiltration_ventilation",
                    "[W]",
                ),
                ("zone 2: fabric heat loss", "[W]"): ("zone 2: fabric", "[W]"),
            }
        )
        .columns
    )

    return df


def create_all_results_df(
    results_dict,
    model_version_summary,
    df_name,
):
    """
    Collects all the results dataframes into a single dataframe.

    Args:
        results_dict: dictionary of results created by create_results_dictionary function
        model_version_summary: dataframe with list of commit IDs and dates (in order)

    Returns:
        dataframe with results from all runs with additional columns for commit_id and archetype.
    """

    print(f"Processing: {df_name}")
    # initialise dataframe to collect results
    all_results_df = pd.DataFrame(columns=["archetype", "commit_id"]).set_index(
        ["archetype", "commit_id"]
    )

    # looping through commit ids using  model_version_summary as it's critical results from each commit are processed chronologically
    for index, model_version in model_version_summary.iterrows():
        commit_id = model_version["commit_id"]
        # collect results for all the archetypes
        results_for_current_commit = pd.DataFrame(columns=["archetype"]).set_index("archetype")
        for archetype, archetype_dict in results_dict[model_version["commit_id"]].items():
            results_df = archetype_dict[df_name].copy()
            input_dict = archetype_dict["input_dict"]

            if df_name == "results_df":
                # reorganise the Shower input for compatibility with functions that require input_dict
                if "Shower" in input_dict.keys():
                    # Older input files had Showers specified at high level,
                    # They need to be placed under HotWaterDemand for the post_proc_tools script
                    input_dict["HotWaterDemand"] = {"Shower": input_dict["Shower"]}

                # apply result format changes implemented as part of the ground release
                if model_version["date"] <= pd.to_datetime(["2024-05-08"]):
                    results_df = reformat_results_post_ground_changes(results_df, input_dict)
                if model_version["date"] < pd.to_datetime(["2024-06-28"]):
                    results_df = reformat_results_post_20240628(results_df, input_dict)

                # correct column header error
                column_name_to_remove = (
                    "Hot water energy demand incl pipework_loss",
                    "Unit not defined (add to unitsDict hem.py)",
                )
                if column_name_to_remove in results_df.columns:
                    results_df = fix_shifted_column_names(
                        df=results_df, column_name_to_remove=column_name_to_remove
                    )

                # correct mismapped columns
                if model_version["date"] >= pd.to_datetime(["2024-05-08"]) and model_version[
                    "date"
                ] < pd.to_datetime(["2024-05-17"]):
                    results_df = swap_column_names(
                        results_df,
                        ("DHW: demand energy (excluding distribution pipework losses)", "[kWh]"),
                        ("DHW: demand energy (including distribution pipework losses)", "[kWh]"),
                    )

                if "Ventilation" in input_dict.keys():
                    if "EnergySupply" in input_dict["Ventilation"].keys():
                        energy_supply = input_dict["Ventilation"]["EnergySupply"]
                    else:
                        energy_supply = "mains elec"
                    input_dict["InfiltrationVentilation"] = {
                        "MechanicalVentilation": {
                            "Ventilation system": {"EnergySupply": energy_supply}
                        }
                    }
                    if (f"{energy_supply}: Ventilation system", "kWh") not in results_df.columns:
                        results_df[(f"{energy_supply}: Ventilation system", "[kWh]")] = 0.0

            if df_name == "heat_balance_air_node_results_df":
                # correct mismapped columns
                if (
                    model_version["date"] < pd.to_datetime(["2024-05-18"])
                    and commit_id != "58116a26"
                ):
                    prefixes = [z_name for z_name in input_dict["Zone"].keys()]
                    for prefix in prefixes:
                        results_df = sum_columns_heat_balance(
                            results_df,
                            [
                                (f"{prefix}: heat loss through infiltration", "[W]"),
                                (f"{prefix}: heat loss through ventilation", "[W]"),
                            ],
                            (f"{prefix}: heat loss through infiltration_ventilation", "[W]"),
                        )

                # sign & name correction for commits pre
                if model_version["date"] < pd.to_datetime(["2024-06-07"]):
                    reformat_air_node_hb_results(results_df)

                # Convert data in every column from W to kWh.
                # Add up zone breakdowns for whole dwelling totals
                results_df = expand_heat_balance_df(results_df, input_dict)

            if df_name == "heat_balance_external_results_df":
                # correct mismapped columns
                if (
                    model_version["date"] < pd.to_datetime(["2024-05-18"])
                    and commit_id != "58116a26"
                ):
                    prefixes = [z_name for z_name in input_dict["Zone"].keys()]
                    for prefix in prefixes:
                        results_df = sum_columns_heat_balance(
                            results_df,
                            [(f"{prefix}: infiltration", "[W]"), (f"{prefix}: ventilation", "[W]")],
                            (f"{prefix}: infiltration_ventilation", "[W]"),
                        )

                # Convert data in every column from W to kWh.
                # Add up zone breakdowns for whole dwelling totals
                results_df = expand_heat_balance_df(results_df, input_dict)

            # add archetype column to track where results came from
            results_df["archetype"] = archetype
            results_df = results_df.set_index("archetype")

            # collect results for the current commit ID
            results_for_current_commit = pd.concat(
                [
                    results_for_current_commit,
                    results_df,
                ],
                axis=0,
            )

        # add column to indicate which commit the results came from
        results_for_current_commit["commit_id"] = model_version["commit_id"]
        results_for_current_commit = results_for_current_commit.reset_index()
        results_for_current_commit = results_for_current_commit.set_index(
            ["archetype", "commit_id"]
        )

        # add all the results for the current commit to all_results_df
        # first get which columns are different
        if not all_results_df.empty:
            all_results_cols = get_columns_dataframe(all_results_df)

            all_results_cols["previous_results"] = True
            results_for_current_commit_cols = get_columns_dataframe(results_for_current_commit)
            results_for_current_commit_cols["current_commit"] = True

            cols_df = pd.merge(
                left=all_results_cols,
                right=results_for_current_commit_cols,
                how="outer",
                on=["metric", "units"],
            )

            new_cols = cols_df[pd.isna(cols_df["previous_results"])][["metric", "units"]]
            removed_cols = cols_df[pd.isna(cols_df["current_commit"])][["metric", "units"]]
            if not new_cols.empty:
                print(
                    f"\n Results columns new in commit ID {model_version['commit_id']}:\n {new_cols}"
                )
            if not removed_cols.empty:
                print(
                    f"\nExisting results columns not present in commit ID {model_version['commit_id']}:\n {removed_cols}"
                )

        all_results_df = pd.concat(
            [all_results_df, results_for_current_commit],
            axis=0,
        )
    return all_results_df


def create_master_dataframes(
    results_folder,
    model_version_summary,
    archetypes,
    impact_testing_results_folder,
):
    """
    This function aggregates the following results files for all results folders
        - __results.csv
        - __results_heat_balance_external_boundary.csv
    In the following two dataframes, built with additional
    indexes archetype and commit_id.:
        - all_results_df
        - all_heat_balance_results_df
    The function also writes those master dataframes into CSV files,
    stored in the folder impact_testing_results_folder.

    Args:
        results_folder        - folder path to all JSON files from
                                previous HEM versions and their results.
        model_version_summary - content of a CSV file holding information on the
                                results_folder content.
                                The file holds a simple table with the following column:
                                commit_id, test_suite_id, commit date, description
        archetypes            - list of JSON filenames held within the results_folder to be tested.
        impact_testing_results_folder - path to the folder that will hold all impact assessment outputs.

    Returns:
        - all_results_df - pandas dataframe holding all results
                           from __results.csv output files.
        - all_heat_balance_results_df - pandas dataframe holding all results from
                                        __results_heat_balance_external_boundary.csv output files.
    """
    # read results and json input files into nested dictionary with same file structure as folders
    results_dict = create_results_dictionary(
        results_folder_path=results_folder,
        commit_ids=model_version_summary["commit_id"],
        archetypes=archetypes,
    )

    dataframes_to_return = []

    for df_name in [
        "results_df",
        "heat_balance_air_node_results_df",
        "heat_balance_external_results_df",
    ]:
        # summarise what columns are available in which output file versions (pre-corrections)
        columns_summary = get_columns_summary_dataframe(results_dict, df_name)
        columns_summary.to_csv(
            os.path.join(impact_testing_results_folder, f"column_summary_{df_name}.csv"),
            index=False,
        )

        # process results.csv
        # collect results into single results dataframe
        all_results_df = create_all_results_df(
            results_dict=results_dict,
            model_version_summary=model_version_summary,
            df_name=df_name,
        )

        if df_name == "results_df":
            # Convert data in every column from W to kWh.
            # Add up zone breakdowns for whole dwelling totals
            all_results_df = expand_results_df(all_results_df, results_dict)

        all_results_df = add_run_ID_and_chronology_column(all_results_df, model_version_summary)

        # write results dataframe out to CSV
        all_results_df.reset_index().to_csv(
            os.path.join(impact_testing_results_folder, f"all_{df_name}.csv"), index=False
        )

        dataframes_to_return.append(all_results_df)

    return tuple(dataframes_to_return)
