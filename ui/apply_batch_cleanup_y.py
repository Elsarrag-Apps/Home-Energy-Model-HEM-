from pathlib import Path


# Patch results_parser.py with detailed CSV helpers
path = Path("ui/utils/results_parser.py")
text = path.read_text(encoding="utf-8")

if "def read_core_results_dataframe" not in text:
    text += '''


def read_core_results_dataframe(results_csv_path):
    """Read HEM detailed core results CSV and remove the units row."""
    import pandas as pd

    path = Path(results_csv_path)

    if not path.exists():
        return pd.DataFrame()

    df = pd.read_csv(path)

    if df.empty:
        return df

    # HEM result CSV usually has a first row containing units such as [kWh].
    if str(df.iloc[0].get("Timestep", "")).startswith("["):
        df = df.iloc[1:].copy()

    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="ignore")

    if "Timestep" in df.columns:
        df["Timestep"] = pd.to_numeric(df["Timestep"], errors="coerce")

    return df.reset_index(drop=True)


def get_delivered_energy_chart_rows(summary_csv_path):
    """Return delivered energy end-use rows suitable for charting."""
    rows = extract_delivered_energy_rows(summary_csv_path)

    clean_rows = []

    for row in rows:
        end_use = row.get("end_use", "")
        value = row.get("total_kwh_m2", 0.0)

        if end_use and value is not None:
            clean_rows.append(
                {
                    "End use": end_use,
                    "Delivered energy (kWh/m2)": value,
                }
            )

    return clean_rows


def find_columns_containing(df, patterns):
    """Return columns containing any supplied case-insensitive patterns."""
    if df is None or df.empty:
        return []

    if isinstance(patterns, str):
        patterns = [patterns]

    patterns = [p.lower() for p in patterns]

    cols = []

    for col in df.columns:
        col_lower = str(col).lower()

        if any(pattern in col_lower for pattern in patterns):
            cols.append(col)

    return cols
'''

path.write_text(text, encoding="utf-8")
print("Patched ui/utils/results_parser.py")


# Patch Run HEM Results page
path = Path("ui/pages/10_Run_HEM_Results.py")
text = path.read_text(encoding="utf-8")

text = text.replace(
    "from results_parser import compare_summary_metrics, extract_delivered_energy_rows, extract_hot_water_energy, extract_hot_water_energy_by_names, format_number",
    "from results_parser import compare_summary_metrics, extract_delivered_energy_rows, extract_hot_water_energy, extract_hot_water_energy_by_names, find_columns_containing, format_number, get_delivered_energy_chart_rows, read_core_results_dataframe",
)

if "import pandas as pd" not in text:
    text = text.replace(
        "import streamlit as st",
        "import pandas as pd\nimport streamlit as st",
    )

if "GENERATED_CORE_RESULTS_PATH" not in text:
    text = text.replace(
        '''GENERATED_SUMMARY_PATH = Path(
    "ui/temp/generated_full_project_case__results/"
    "generated_full_project_case__core__results_summary.csv"
)
''',
        '''GENERATED_SUMMARY_PATH = Path(
    "ui/temp/generated_full_project_case__results/"
    "generated_full_project_case__core__results_summary.csv"
)

GENERATED_CORE_RESULTS_PATH = Path(
    "ui/temp/generated_full_project_case__results/"
    "generated_full_project_case__core__results.csv"
)
''',
    )

old = '''                with st.expander("Delivered energy by end-use", expanded=False):
                    delivered_rows = extract_delivered_energy_rows(GENERATED_SUMMARY_PATH)

                    if delivered_rows:
                        st.dataframe(
                            delivered_rows,
                            use_container_width=True,
                            hide_index=True,
                        )
                    else:
                        st.write("No delivered-energy end-use rows found.")

                    st.caption(
                        "Hot water energy is estimated from the generated HotWaterSource "
                        "heat-source names plus common DHW rows such as IES and immersion."
                    )

                with st.expander("View full HEM summary output", expanded=False):
                    st.text(summary_text)
'''

new = '''                with st.expander("Delivered energy by end-use", expanded=True):
                    delivered_rows = extract_delivered_energy_rows(GENERATED_SUMMARY_PATH)

                    if delivered_rows:
                        delivered_df = pd.DataFrame(delivered_rows)

                        st.dataframe(
                            delivered_df,
                            use_container_width=True,
                            hide_index=True,
                        )

                        chart_rows = get_delivered_energy_chart_rows(GENERATED_SUMMARY_PATH)

                        if chart_rows:
                            chart_df = pd.DataFrame(chart_rows).set_index("End use")
                            st.bar_chart(chart_df)

                    else:
                        st.write("No delivered-energy end-use rows found.")

                    st.caption(
                        "Hot water energy is estimated from the generated HotWaterSource "
                        "heat-source names plus common DHW rows such as IES and immersion."
                    )

                st.subheader("Hourly / timestep results")

                detailed_df = read_core_results_dataframe(GENERATED_CORE_RESULTS_PATH)

                if detailed_df.empty:
                    st.info("Detailed timestep results CSV was not found.")
                else:
                    profile_tabs = st.tabs(
                        [
                            "Energy profiles",
                            "Zone temperatures",
                            "Hot water profiles",
                            "Raw timestep data",
                        ]
                    )

                    with profile_tabs[0]:
                        energy_columns = [
                            col
                            for col in detailed_df.columns
                            if str(col).startswith("mains elec:")
                            and any(
                                key in str(col).lower()
                                for key in [
                                    "main",
                                    "ies",
                                    "heat pump",
                                    "lighting",
                                    "cooking",
                                    "mech",
                                    "total",
                                ]
                            )
                        ]

                        if energy_columns:
                            energy_df = detailed_df[["Timestep"] + energy_columns].set_index("Timestep")
                            st.line_chart(energy_df)
                        else:
                            st.info("No energy profile columns found.")

                    with profile_tabs[1]:
                        temp_columns = find_columns_containing(
                            detailed_df,
                            [
                                "operative temp",
                                "internal air temp",
                                "space heat demand",
                                "space cool demand",
                                "solar gains",
                                "internal gains",
                            ],
                        )

                        if temp_columns:
                            temp_df = detailed_df[["Timestep"] + temp_columns].set_index("Timestep")
                            st.line_chart(temp_df)
                        else:
                            st.info("No zone temperature or gain columns found.")

                    with profile_tabs[2]:
                        hw_columns = find_columns_containing(
                            detailed_df,
                            [
                                "hot water",
                                "storage losses",
                                "pipework losses",
                                "number of events",
                                "total event duration",
                            ],
                        )

                        if hw_columns:
                            hw_df = detailed_df[["Timestep"] + hw_columns].set_index("Timestep")
                            st.line_chart(hw_df)
                        else:
                            st.info("No hot-water timestep columns found.")

                    with profile_tabs[3]:
                        st.dataframe(
                            detailed_df,
                            use_container_width=True,
                            hide_index=True,
                        )

                with st.expander("View full HEM summary output", expanded=False):
                    st.text(summary_text)
'''

if old in text:
    text = text.replace(old, new, 1)
else:
    print("Warning: expected dashboard insertion block was not found. It may already be patched.")

path.write_text(text, encoding="utf-8")
print("Patched ui/pages/10_Run_HEM_Results.py")

print("Batch Y complete.")