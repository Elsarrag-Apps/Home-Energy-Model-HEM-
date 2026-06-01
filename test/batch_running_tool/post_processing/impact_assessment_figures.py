import os
from math import fsum

import pandas as pd
from matplotlib import pyplot as plt
from matplotlib import patches as mpatches

from af_colours import af_colour_palette_categorical


def create_annual_energy_df(
    all_results_df,
    impact_testing_results_folder,
):
    """
    Create a dataframe for annual energy figures in kWh/m2,
    and print the dataframe to CSV.

    Args:
        all_results_df - dataframe created by function
                         create_all_results_df
        impact_testing_results_folder - path to
                          impact assessment output folder.

    Returns:
        annual_energy_use_df - dataframe for annual
                          energy use figures in kWh/m2.
    """
    # convert all kWh columns to kWh/m2
    all_results_df.loc[:, all_results_df.columns.get_level_values(1) == "[kWh]"] = (
        all_results_df.loc[:, all_results_df.columns.get_level_values(1) == "[kWh]"].div(
            all_results_df.loc[:, ("Total: floor area", "[m2]")], axis=0
        )
    )

    # zone break down should be devided by zone area not TFA
    # get zone names
    z_names = []
    for column in all_results_df.columns:
        if "floor area" in column[0] and "Total" not in column[0]:
            z_names.append(column[0].split(":")[0])
    # correct zone breakdowns
    for column in all_results_df.columns:
        column_header = column[0]
        unit = column[1]
        for z_name in z_names:
            if z_name in column_header and unit == "[kWh]":
                all_results_df.loc[:, column] = (
                    all_results_df.loc[:, column]
                    * all_results_df.loc[:, ("Total: floor area", "[m2]")]
                    / all_results_df.loc[:, (f"{z_name}: floor area", "[m2]")]
                )

    # rename units from kWh to kWh/m2
    kwh_to_kwhm2 = lambda col: "[kWh/m2]" if col == "[kWh]" else col
    all_results_df = all_results_df.rename(kwh_to_kwhm2, axis="columns")

    # only keep energy columns
    annual_energy_df = all_results_df.loc[
        :, all_results_df.columns.get_level_values(1) == "[kWh/m2]"
    ]

    # get annual summary and print to CSV
    annual_energy_df = annual_energy_df.groupby(["archetype", "chronology", "test_suite_id"]).sum()
    annual_energy_df = annual_energy_df.sort_values(by=["chronology"])
    annual_energy_df.to_csv(os.path.join(impact_testing_results_folder, "annual_energy.csv"))

    annual_energy_net_df = annual_energy_df.groupby(["archetype"]).diff()
    annual_energy_net_df.to_csv(
        os.path.join(impact_testing_results_folder, "annual_energy_net_change.csv")
    )

    return annual_energy_df


def create_annual_energy_use_figures(
    annual_energy_df,
    archetypes,
    impact_testing_results_folder,
):
    """
    Creates stacked bar charts showing annual energy use in kWh/m2.
    The bar charts are exported as .PNG.

    Args:
        annual_energy_df - dataframe created by function
                         create_annual_energy_df
        archetypes     - list of JSON filenames held within
                         the results_folder to be tested.
        impact_testing_results_folder - path to
                         impact assessment output folder.
    """

    idx = pd.IndexSlice

    filtered_columns = [
        ("Space Heating Energy Use", "[kWh/m2]"),
        ("Space Cooling Energy Use", "[kWh/m2]"),
        ("DHW Energy Use", "[kWh/m2]"),
        ("Pumps and Fans Energy Use", "[kWh/m2]"),
        ("Cooking Energy Use", "[kWh/m2]"),
        ("Appliances Energy Use", "[kWh/m2]"),
        ("Lighting Energy Use", "[kWh/m2]"),
    ]

    annual_energy_use_df = annual_energy_df.loc[:, filtered_columns]

    for archetype in archetypes:
        # create a stacked bar chart for each archetype
        archetype_df = annual_energy_use_df.loc[idx[archetype, :], :]
        archetype_df.plot(kind="bar", stacked=True)
        plt.title(f"Annual Energy Use: {archetype}")
        plt.xlabel("Test suite ID")
        plt.ylabel("[kWh/m2/yr]")
        plt.xticks(
            list(range(archetype_df.shape[0])), archetype_df.index.get_level_values(2).values
        )
        plt.legend(
            labels=[f"{col[0]}" for col in archetype_df.columns.values],
            bbox_to_anchor=(1.05, 1.0),
            loc="upper left",
            fontsize=8,
        )
        fig_filepath = os.path.join(
            impact_testing_results_folder, f"annual_energy_use_{archetype}.png"
        )
        plt.savefig(fig_filepath, format="png", bbox_inches="tight")


def create_annual_demand_figures(
    annual_energy_df,
    archetypes,
    impact_testing_results_folder,
):
    """
    Creates bar charts showing annual energy SH
    and DHW demand in kWh/m2.
    The bar charts are exported as .PNG.

    Args:
        annual_energy_df - dataframe created by function
                         create_annual_energy_df
        archetypes     - list of JSON filenames held within
                         the results_folder to be tested.
        impact_testing_results_folder - path to
                         impact assessment output folder.
    """

    filtered_columns = [
        ("DHW: demand energy (excluding distribution pipework losses)", "[kWh/m2]"),
        ("space heat demand Total", "[kWh/m2]"),
    ]

    annual_energy_use_df = annual_energy_df.loc[:, filtered_columns]

    for archetype in archetypes:
        archetype_df = annual_energy_use_df.loc[pd.IndexSlice[archetype, :], :]
        archetype_df.plot(kind="bar")
        plt.title(f"Annual SH and DHW demand: {archetype}")
        plt.xlabel("Test suite ID")
        plt.ylabel("[kWh/m2/yr]")
        plt.xticks(
            list(range(archetype_df.shape[0])), archetype_df.index.get_level_values(2).values
        )
        plt.legend(
            labels=[f"{col[0]}" for col in archetype_df.columns.values],
            bbox_to_anchor=(1.05, 1.0),
            loc="upper left",
            fontsize=8,
        )
        fig_filepath = os.path.join(
            impact_testing_results_folder, f"annual_SH_DHW_demand_{archetype}.png"
        )
        plt.savefig(fig_filepath, format="png", bbox_inches="tight")


def create_annual_heat_balance_figures(
    all_heat_balance_results_df,
    archetypes,
    impact_testing_results_folder,
    file_name,
):
    """
    Creates a stacked bar chart per archetype showing the annual heat balance breakdown in kWh/m2.
    The function also creates a CSV file recording the annual breakdowns.

    Args:
        all_heat_balance_results_df - dataframe created by function
                                      create_annual_energy_df
        archetypes - list of JSON filenames held within
                     the results_folder to be tested.
        impact_testing_results_folder - path to impact assessment output folder.
        file_name - name to be given to the figure and CSV file.
    """
    # only show whole dwelling totals.
    filtered_columns = [
        column
        for column in all_heat_balance_results_df.columns.get_level_values(0)
        if "Total" in column
    ]
    all_heat_balance_results_df = all_heat_balance_results_df.loc[:, filtered_columns]

    annual_heat_balance_df = all_heat_balance_results_df.groupby(
        ["archetype", "chronology", "test_suite_id"]
    ).sum()
    annual_heat_balance_df = annual_heat_balance_df.sort_values(by=["chronology"])
    annual_heat_balance_df.to_csv(os.path.join(impact_testing_results_folder, f"{file_name}.csv"))

    for archetype in archetypes:
        archetype_df = annual_heat_balance_df.loc[pd.IndexSlice[archetype, :], :]
        archetype_df.plot(kind="bar", stacked=True)
        plt.title(f"{file_name}: {archetype}")
        plt.xlabel("Test suite ID")
        plt.ylabel("[kWh/m2/yr]")
        plt.xticks(
            list(range(archetype_df.shape[0])), archetype_df.index.get_level_values(2).values
        )
        plt.legend(
            labels=[f"{col[0]}" for col in archetype_df.columns.values],
            bbox_to_anchor=(1.05, 1.0),
            loc="upper left",
            fontsize=8,
        )
        fig_filepath = os.path.join(impact_testing_results_folder, f"{file_name}_{archetype}.png")
        plt.savefig(fig_filepath, format="png", bbox_inches="tight")


def create_monthly_heat_balance_figures(
    all_heat_balance_results_df,
    archetypes,
    impact_testing_results_folder,
    file_name,
):
    """
    Creates a stacked bar chart per archetype showing the monthly heat balance breakdown in kWh/m2.

    Args:
        all_heat_balance_results_df - dataframe created by function
                                      create_annual_energy_df
        archetypes - list of JSON filenames held within
                     the results_folder to be tested.
        impact_testing_results_folder - path to impact assessment output folder.
        file_name - name to be given to the figure and CSV file.
    """
    # set datetime as index to facilitate grouping by month
    all_heat_balance_results_df.columns = pd.MultiIndex.from_tuples(
        all_heat_balance_results_df.set_axis(all_heat_balance_results_df.columns.values, axis=1)
        .rename(
            columns={
                ("datetime", "[yyyy-mm-dd  hh:mm:ss]"): ("datetime", ""),
            }
        )
        .columns
    )

    all_heat_balance_results_df = all_heat_balance_results_df.set_index(["datetime"], append=True)

    # only show whole dwelling totals
    filtered_columns = [
        column
        for column in all_heat_balance_results_df.columns.get_level_values(0)
        if "Total" in column
    ]
    all_heat_balance_results_df = all_heat_balance_results_df.loc[:, filtered_columns]

    all_heat_balance_results_df = all_heat_balance_results_df.sort_values(by=["chronology"])

    monthly_heat_balance_df = all_heat_balance_results_df.groupby(
        [
            "archetype",
            all_heat_balance_results_df.index.get_level_values("datetime").month,
            "test_suite_id",
        ]
    ).sum()

    for archetype in archetypes:
        archetype_df = monthly_heat_balance_df.loc[pd.IndexSlice[archetype, :], :]

        # list of commit IDs
        test_suite_IDs = list(
            set(monthly_heat_balance_df.index.get_level_values("test_suite_id").tolist())
        )

        # number of stacks in each group for a tick location
        # i.e. number of commit IDs
        stacks = len(test_suite_IDs)

        # set the width
        w = 0.5

        # function to calculate the x-coordinate for a bar
        def X(m, s):
            # m: month index
            # s: stack index
            return m * (w * (stacks + 1)) + w * s

        # initialise figure and axis for the plot
        fig, ax = plt.subplots()

        # setup list of colors and shadings
        colours_list = list(af_colour_palette_categorical.values())
        colours = {}
        for i, k in enumerate(archetype_df.columns.tolist()):
            colours[k] = colours_list[i]

        for m in range(1, 13):  # loop through each month (X axis groups)
            for s in range(stacks):  # Loop through each commit ID index (Horizontal group items)
                test_suite_ID = test_suite_IDs[s]

                # order column names inline with sorted values for labeling
                col_v_dict = {}
                for col in archetype_df.columns.tolist():
                    col_v_dict[col] = archetype_df.loc[archetype, m, test_suite_ID][col]
                sorted_dict = dict(sorted(col_v_dict.items(), key=lambda x: x[1]))
                sorted_dict = list(sorted_dict.keys())

                values = sorted(archetype_df.loc[archetype, m, test_suite_ID].values)

                # Calculate the very bottom of the negative bars
                bottom = 0
                bottom += fsum(filter(lambda v: v < 0, values))
                for i, v in enumerate(values):  # loop through each value
                    x = X(m, s)  # get x-coordinate of the bar
                    height = abs(v)  # get height of the bar
                    # plot the bar
                    ax.bar(
                        x=x,
                        height=height,
                        width=0.7 * w,
                        bottom=bottom,
                        color=colours[sorted_dict[i]],
                    )
                    bottom += height  # update the bottom for the next bar
                # label the bar
                ax.annotate(
                    str(s + 1),
                    (x, bottom),
                    xytext=(0, 2),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=6,
                )

        # hash bars to identify the commit ID and include legend
        number_labels = "".join(f"{s + 1} - {test_suite_IDs[s]}\n" for s in range(stacks))
        plt.text(
            0.65,
            -0.2,
            number_labels,
            fontsize=8,
            transform=plt.gcf().transFigure,
            bbox=dict(facecolor="none", edgecolor="lightgrey"),
        )

        # include legend for column names
        columns = []
        value_handles = []
        for i, k in enumerate(sorted_dict):
            columns.append(k[0])
            value_handles.append(mpatches.Patch(color=colours[k]))

        ax.legend(
            value_handles,
            columns,
            bbox_to_anchor=(0, -0.1),
            loc="upper left",
            title="Gains and Losses",
            fontsize=8,
        )

        # add ticks for each month and label them 1 to 12
        ticks = [X(m, 1) for m in range(1, 13)]
        labels = [str(m + 1) for m in range(12)]
        ax.set_xticks(ticks)
        ax.set_xticklabels(labels)

        ax.set_xlabel("Month")
        ax.set_ylabel(r"[kWh / m$\mathregular{^2}$]")

        plt.title(f"{file_name}: {archetype}")

        fig_filepath = os.path.join(impact_testing_results_folder, f"{file_name}_{archetype}.png")
        plt.savefig(fig_filepath, format="png", bbox_inches="tight")
