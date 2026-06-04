import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

CURRENT_DIR = Path(__file__).resolve().parent
UI_DIR = CURRENT_DIR.parent
UTILS_DIR = UI_DIR / "utils"
sys.path.append(str(UTILS_DIR))

from full_case_builder import build_full_project_case
from model_runner import run_hem_model
from project_store import ACTIVE_HEM_INPUT_PATH, get_active_project
from project_validation import (
    has_blocking_errors,
    split_messages,
    validate_project_before_run,
)
from results_parser import compare_summary_metrics, extract_delivered_energy_rows, extract_hot_water_energy, extract_hot_water_energy_by_names, find_columns_containing, format_number, format_small_number, get_delivered_energy_chart_rows, get_simulation_summary_from_case, read_core_results_dataframe




def get_existing_result_files(results_dir: Path) -> dict:
    """Return known HEM result files if they exist."""
    if not results_dir.exists():
        return {}

    summary_files = list(results_dir.glob("*__results_summary.csv"))
    timestep_files = list(results_dir.glob("*__results.csv"))
    static_files = list(results_dir.glob("*__results_static.csv"))

    return {
        "summary": summary_files[0] if summary_files else None,
        "timestep": timestep_files[0] if timestep_files else None,
        "static": static_files[0] if static_files else None,
    }


def has_existing_results(results_dir: Path) -> bool:
    files = get_existing_result_files(results_dir)
    return bool(files.get("summary") and files.get("timestep"))


def select_hot_water_profile_columns(columns) -> list[str]:
    """Select useful hot-water plotting columns only.

    This avoids plotting event-count/duration columns together with kWh/volume columns,
    which makes annual hot-water charts look flat or meaningless.
    """
    selected = []

    include_terms = [
        "hot water energy demand",
        "hot water volume required",
        "storage losses",
        "distribution pipework losses",
        "primary pipework losses",
    ]

    exclude_terms = [
        "number of events",
        "total event duration",
        "_electric_showers",
    ]

    for col in columns:
        lower = col.lower()

        if any(term in lower for term in exclude_terms):
            continue

        if any(term in lower for term in include_terms):
            selected.append(col)

    return selected


def numeric_timestep_dataframe(csv_path: Path):
    import pandas as pd

    df = pd.read_csv(csv_path)
    if "Timestep" not in df.columns:
        return df

    mask = pd.to_numeric(df["Timestep"], errors="coerce").notna()
    df = df.loc[mask].copy()
    df["Timestep"] = pd.to_numeric(df["Timestep"], errors="coerce").astype(int)

    for col in df.columns:
        if col != "Timestep":
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


st.set_page_config(
    page_title="Run HEM / Results",
    layout="wide",
)

st.title("Run HEM / Results")

st.write(
    "Build one full HEM input file from the active uploaded case and the saved "
    "inputs from each tab, then run HEM and compare the generated case against "
    "the uploaded baseline."
)

GENERATED_FULL_CASE_PATH = Path("ui/temp/generated_full_project_case.json")

# Existing result detection for persistence across page navigation.
GENERATED_RESULTS_DIR = Path("ui/temp/generated_full_project_case__results")
existing_result_files = get_existing_result_files(GENERATED_RESULTS_DIR)
existing_results_available = has_existing_results(GENERATED_RESULTS_DIR)


GENERATED_SUMMARY_PATH = Path(
    "ui/temp/generated_full_project_case__results/"
    "generated_full_project_case__core__results_summary.csv"
)

GENERATED_CORE_RESULTS_PATH = Path(
    "ui/temp/generated_full_project_case__results/"
    "generated_full_project_case__core__results.csv"
)

BASE_SUMMARY_PATH = Path(
    "test/e2e/demo_files/short/demo__results/"
    "demo__core__results_summary.csv"
)

DEFAULT_WEATHER_FILE = Path("test/e2e/demo_files/London_weather_CIBSE_format.csv")

active_project = get_active_project()

if active_project is None:
    st.error("No active project loaded. Go to Project Setup and upload/load a JSON first.")
    st.stop()

if not ACTIVE_HEM_INPUT_PATH.exists():
    st.error("No active HEM input file found. Go to Project Setup and upload/load a HEM JSON first.")
    st.stop()

project_data = active_project.get("project_data", {})
project_setup = project_data.get("project_setup", {})


def get_dhw_end_use_names_from_generated_case(generated_case_path: Path) -> list[str]:
    """Identify likely DHW end-use rows from generated HEM HotWaterSource."""
    names = ["immersion", "IES", "instant electric shower", "hw cylinder", "heat pump 1"]

    if not generated_case_path.exists():
        return names

    try:
        generated = json.loads(generated_case_path.read_text(encoding="utf-8"))
    except Exception:
        return names

    hot_water_sources = generated.get("HotWaterSource", {})

    if not isinstance(hot_water_sources, dict):
        return names

    for source_name, source in hot_water_sources.items():
        if isinstance(source, dict):
            names.append(source_name)

            heat_sources = source.get("HeatSource", {})
            if isinstance(heat_sources, dict):
                for heat_source_name in heat_sources.keys():
                    names.append(heat_source_name)

    seen = set()
    clean_names = []

    for name in names:
        key = str(name).strip().lower()
        if key and key not in seen:
            seen.add(key)
            clean_names.append(str(name).strip())

    return clean_names



def build_project_report_text(
    active_project_data: dict,
    generated_case_path: Path,
    summary_path: Path,
    weather_file: Path,
) -> str:
    project_sections = active_project_data.get("project_data", {})
    setup = project_sections.get("project_setup", {})

    fabric_rows = project_sections.get("fabric_elements", [])
    ventilation = project_sections.get("ventilation", {})
    thermal_bridges = project_sections.get("thermal_bridges", [])
    space_heat_systems = project_sections.get("space_heat_systems", {})
    hot_water = project_sections.get("hot_water", {})
    gains_controls = project_sections.get("gains_controls", {})
    energy_supply = project_sections.get("energy_supply", {})

    lines = []
    lines.append("Home Energy Model App - Project Summary")
    lines.append("=" * 45)
    lines.append("")
    lines.append("Project details")
    lines.append("-" * 15)
    lines.append(f"Project name: {setup.get('project_name', 'Not set')}")
    lines.append(f"Case ID: {setup.get('case_id', 'Not set')}")
    lines.append(f"Assessor: {setup.get('assessor', 'Not set')}")
    lines.append(f"Dwelling type: {setup.get('dwelling_type', 'Not set')}")
    lines.append(f"Assessment type: {setup.get('assessment_type', 'Not set')}")
    lines.append(f"Floor area: {setup.get('floor_area_m2', 'Not set')} m2")
    lines.append(f"Internal volume: {setup.get('internal_volume_m3', 'Not set')} m3")
    lines.append("")
    lines.append("Saved model inputs")
    lines.append("-" * 18)
    lines.append(f"Fabric rows: {len(fabric_rows)}")
    lines.append(
        "Ventilation: "
        + ("saved" if ventilation.get("airtightness_exposure") else "not saved")
    )
    lines.append(f"Thermal bridges: {len(thermal_bridges)}")
    lines.append(
        f"Heating systems: {1 if space_heat_systems else 0}"
    )
    lines.append("Hot water: " + ("saved" if hot_water else "not saved"))
    lines.append("Internal gains / controls: " + ("saved" if gains_controls else "not saved"))
    lines.append("Energy supply: " + ("saved" if energy_supply else "not saved"))
    lines.append("")
    lines.append("Run setup")
    lines.append("-" * 9)
    lines.append(f"Weather file: {weather_file}")
    lines.append(f"Generated HEM input: {generated_case_path}")
    lines.append(f"HEM summary output: {summary_path}")
    lines.append("")

    if summary_path.exists():
        lines.append("HEM summary output")
        lines.append("-" * 18)
        lines.append(summary_path.read_text(encoding="utf-8"))
    else:
        lines.append("HEM summary output: not available yet.")

    return "\n".join(lines)


st.header("1. Project build summary")

fabric_rows = project_data.get("fabric_elements", [])
ventilation = project_data.get("ventilation", {})
thermal_bridges = project_data.get("thermal_bridges", [])
weather_settings = project_data.get("weather_simulation", {})
space_heat_systems = project_data.get("space_heat_systems", {}) or project_data.get("heating_form", {})
heat_source_wet = project_data.get("heat_source_wet", {}) or project_data.get("heating_form", {})
hot_water = project_data.get("hot_water", {})
gains_controls = project_data.get("gains_controls", {}) or project_data.get("internal_gains_form", {})
energy_supply = project_data.get("energy_supply", {}) or project_data.get("energy_supply_form", {}) or project_data.get("renewables_battery", {})

if project_setup:
    st.subheader("Project")
    p1, p2, p3, p4 = st.columns(4)

    with p1:
        st.metric("Project name", project_setup.get("project_name", "Not set"))

    with p2:
        st.metric("Case ID", project_setup.get("case_id", "Not set"))

    with p3:
        st.metric("Floor area", f"{project_setup.get('floor_area_m2', 'Not set')} m2")

    with p4:
        st.metric("Dwelling type", project_setup.get("dwelling_type", "Not set"))

st.subheader("Saved input status")

col1, col2, col3, col4, col5, col6, col7, col8 = st.columns(8)

with col1:
    st.metric("Fabric rows", len(fabric_rows))

with col2:
    st.metric(
        "Ventilation",
        "Yes" if ventilation.get("airtightness_exposure") else "No",
    )

with col3:
    st.metric("Thermal bridges", len(thermal_bridges))

with col4:
    st.metric(
        "Heating",
        1 if space_heat_systems else 0,
    )

with col5:
    st.metric(
        "Heat sources",
        1 if heat_source_wet else 0,
    )

with col6:
    st.metric("Hot water", "Yes" if (hot_water or project_data.get("hot_water_form") or project_data.get("heating_hot_water") or project_data.get("hot_water") or project_data.get("HotWaterSource")) else "No")

with col7:
    st.metric("Gains/controls", "Yes" if gains_controls else "No")

with col8:
    st.metric("Energy supply", "Yes" if energy_supply else "No")


st.header("2. Pre-run checks")

validation_messages = validate_project_before_run(
    project_data=project_data,
    default_weather_file=DEFAULT_WEATHER_FILE,
)

validation_errors, validation_warnings = split_messages(validation_messages)

if not validation_messages:
    st.success("Pre-run checks passed.")
else:
    if validation_errors:
        st.error("Some inputs need attention before HEM can run.")

        for message in validation_errors:
            st.warning(f"{message['section']}: {message['message']}")

    if validation_warnings:
        st.info("Warnings / notes:")

        for message in validation_warnings:
            st.caption(f"{message['section']}: {message['message']}")

blocking_errors = has_blocking_errors(validation_messages)


st.header("3. Weather used for this run")

weather_file = Path(
    weather_settings.get(
        "weather_file",
        str(DEFAULT_WEATHER_FILE),
    )
)

if not weather_file.exists():
    weather_file = DEFAULT_WEATHER_FILE

w1, w2 = st.columns(2)

with w1:
    st.metric("Weather file type", weather_file.suffix.lower().replace(".", "") or "unknown")

with w2:
    st.write(str(weather_file))


st.header("4. Build generated HEM input")

if blocking_errors:
    st.warning("Fix the input issues above before building the HEM input.")
else:
    if st.button("Build full HEM input from saved project values"):
        try:
            generated_case = build_full_project_case(
                base_json_path=ACTIVE_HEM_INPUT_PATH,
                output_json_path=GENERATED_FULL_CASE_PATH,
                project_data=active_project,
            )

            st.session_state["generated_full_case_ready"] = True
            st.session_state["last_generated_full_case"] = generated_case

            st.success(f"Generated full HEM input saved to: {GENERATED_FULL_CASE_PATH}")

        except Exception as exc:
            st.error(
                "HEM input could not be prepared. Check the saved inputs, especially "
                "any advanced JSON sections."
            )
            with st.expander("Developer/debug: build error", expanded=False):
                st.exception(exc)

if st.session_state.get("generated_full_case_ready"):
    st.info("Generated HEM input is ready to run.")

    with st.expander("Advanced: view generated full HEM JSON", expanded=False):
        generated_case = st.session_state.get("last_generated_full_case")

        if generated_case is not None:
            st.json(generated_case)
        elif GENERATED_FULL_CASE_PATH.exists():
            st.json(json.loads(GENERATED_FULL_CASE_PATH.read_text(encoding="utf-8")))
        else:
            st.write("No generated case found.")


st.header("5. Run HEM and compare results")


if existing_results_available:
    st.info(
        "Previous HEM results are available and will remain visible until a new run overwrites them."
    )


if blocking_errors:
    st.warning("HEM cannot run until the input issues above are fixed.")
elif not st.session_state.get("generated_full_case_ready"):
    st.warning("Build the full HEM input before running HEM.")
else:
    if st.button("Run HEM and compare full project case"):
        with st.spinner("Running HEM..."):
            result = run_hem_model(GENERATED_FULL_CASE_PATH, weather_file)

        if result.returncode == 0:
            st.success("HEM run completed successfully.")
            st.session_state["last_hem_results_dir"] = str(GENERATED_RESULTS_DIR)
            st.session_state["last_hem_run_success"] = True

            if GENERATED_SUMMARY_PATH.exists():
                summary_text = GENERATED_SUMMARY_PATH.read_text(encoding="utf-8")

                st.session_state["last_hem_summary_text"] = summary_text

                st.subheader("Results comparison for current simulation period")

                if BASE_SUMMARY_PATH.exists():
                    comparison = compare_summary_metrics(
                        BASE_SUMMARY_PATH,
                        GENERATED_SUMMARY_PATH,
                    )

                    st.session_state["last_results_comparison"] = comparison

                    col1, col2, col3, col4, col5, col6 = st.columns(6)

                    space_heat = next(
                        item
                        for item in comparison
                        if item["metric"] == "Space heat demand"
                    )

                    space_cool = next(
                        item
                        for item in comparison
                        if item["metric"] == "Space cool demand"
                    )

                    peak_elec = next(
                        item
                        for item in comparison
                        if item["metric"] == "Peak electricity consumption"
                    )

                    delivered = next(
                        item
                        for item in comparison
                        if item["metric"] == "Delivered energy total"
                    )

                    mech_vent = next(
                        item
                        for item in comparison
                        if item["metric"] == "Mechanical ventilation energy"
                    )

                    dhw_end_use_names = get_dhw_end_use_names_from_generated_case(
                        GENERATED_FULL_CASE_PATH
                    )

                    hot_water_generated = extract_hot_water_energy_by_names(
                        GENERATED_SUMMARY_PATH,
                        dhw_end_use_names,
                    )

                    hot_water_baseline = (
                        extract_hot_water_energy_by_names(
                            BASE_SUMMARY_PATH,
                            dhw_end_use_names,
                        )
                        if BASE_SUMMARY_PATH.exists()
                        else 0.0
                    )

                    hot_water_difference = hot_water_generated - hot_water_baseline

                    with col1:
                        st.metric(
                            "Space heat demand",
                            f"{format_number(space_heat['generated_value'])} {space_heat['unit']}",
                            f"{format_number(space_heat['difference'])} {space_heat['unit']}",
                        )

                    with col2:
                        st.metric(
                            "Space cool demand",
                            f"{format_number(space_cool['generated_value'])} {space_cool['unit']}",
                            f"{format_number(space_cool['difference'])} {space_cool['unit']}",
                        )

                    with col3:
                        st.metric(
                            "Hot water energy",
                            f"{format_number(hot_water_generated)} kWh/m2",
                            f"{format_number(hot_water_difference)} kWh/m2",
                        )

                    with col4:
                        st.metric(
                            "Peak electricity",
                            f"{format_number(peak_elec['generated_value'])} {peak_elec['unit']}",
                            f"{format_number(peak_elec['difference'])} {peak_elec['unit']}",
                        )

                    with col5:
                        st.metric(
                            "Delivered energy",
                            f"{format_number(delivered['generated_value'])} {delivered['unit']}",
                            f"{format_number(delivered['difference'])} {delivered['unit']}",
                        )

                    with col6:
                        st.metric(
                            "Mechanical ventilation",
                            f"{format_small_number(mech_vent['generated_value'])} {mech_vent['unit']}",
                            f"{format_small_number(mech_vent['difference'])} {mech_vent['unit']}",
                        )

                    with st.expander("Detailed comparison table", expanded=False):
                        st.dataframe(
                            comparison,
                            use_container_width=True,
                            hide_index=True,
                        )

                else:
                    st.warning(
                        "Baseline summary file was not found. "
                        "Run a baseline case first if comparison is needed."
                    )

                with st.expander("Delivered energy by end-use", expanded=True):
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
                        st.markdown("#### Zone temperatures")
                        temperature_columns = find_columns_containing(
                            detailed_df,
                            [
                                "operative temp",
                                "internal air temp",
                            ],
                        )

                        if temperature_columns:
                            temperature_df = detailed_df[
                                ["Timestep"] + temperature_columns
                            ].set_index("Timestep")
                            st.line_chart(temperature_df)
                        else:
                            st.info("No zone temperature columns found.")

                        st.markdown("#### Zone gains")
                        gain_columns = find_columns_containing(
                            detailed_df,
                            [
                                "solar gains",
                                "internal gains",
                            ],
                        )

                        if gain_columns:
                            gains_df = detailed_df[
                                ["Timestep"] + gain_columns
                            ].set_index("Timestep")
                            st.line_chart(gains_df)
                        else:
                            st.info("No zone gain columns found.")

                        st.markdown("#### Space heating / cooling demand")
                        demand_columns = find_columns_containing(
                            detailed_df,
                            [
                                "space heat demand",
                                "space cool demand",
                            ],
                        )

                        if demand_columns:
                            demand_df = detailed_df[
                                ["Timestep"] + demand_columns
                            ].set_index("Timestep")
                            st.line_chart(demand_df)
                        else:
                            st.info("No heating/cooling demand columns found.")

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

            else:
                st.warning("HEM ran, but the expected summary file was not found.")

        else:
            st.error(
                "HEM run failed. The model returned an error. "
                "A short issue summary is shown below; detailed output is hidden."
            )

            if "design_outdoor_air_flow_rate" in result.stderr:
                st.warning(
                    "Ventilation issue: mechanical ventilation is selected, but the "
                    "design outdoor air-flow rate is not greater than zero."
                )
            elif "ValidationError" in result.stderr:
                st.warning(
                    "The generated HEM JSON did not pass HEM validation. "
                    "Check any advanced JSON sections that were edited manually."
                )
            else:
                st.warning(
                    "HEM reported an error that was not recognised by the app."
                )

            with st.expander("Developer/debug: full HEM error output", expanded=False):
                st.code(result.stderr)

                if result.stdout:
                    st.subheader("Model output")
                    st.code(result.stdout)


st.header("6. Downloads and project report")

project_json = json.dumps(active_project, indent=2)

download_col1, download_col2, download_col3 = st.columns(3)

with download_col1:
    st.download_button(
        "Download saved app project JSON",
        data=project_json,
        file_name="saved_app_project.json",
        mime="application/json",
    )

with download_col2:
    if GENERATED_FULL_CASE_PATH.exists():
        st.download_button(
            "Download generated HEM input JSON",
            data=GENERATED_FULL_CASE_PATH.read_text(encoding="utf-8"),
            file_name="generated_full_project_case.json",
            mime="application/json",
        )
    else:
        st.caption("Generated HEM input is not available yet.")

with download_col3:
    if GENERATED_SUMMARY_PATH.exists():
        st.download_button(
            "Download HEM summary CSV",
            data=GENERATED_SUMMARY_PATH.read_text(encoding="utf-8"),
            file_name="generated_full_project_case__core__results_summary.csv",
            mime="text/csv",
        )
    else:
        st.caption("HEM summary CSV is not available yet.")

report_text = build_project_report_text(
    active_project_data=active_project,
    generated_case_path=GENERATED_FULL_CASE_PATH,
    summary_path=GENERATED_SUMMARY_PATH,
    weather_file=weather_file,
)

st.download_button(
    "Download simple project report TXT",
    data=report_text,
    file_name="hem_project_summary_report.txt",
    mime="text/plain",
)

with st.expander("Preview simple project report", expanded=False):
    st.text(report_text)

with st.expander("Developer/debug: saved project data used for this run", expanded=False):
    st.json(project_data)



# Fallback: show previous HEM results after page navigation if files exist.
if existing_results_available and not st.session_state.get("last_hem_results_rendered_this_pass", False):
    with st.expander("View previous HEM summary output", expanded=False):
        summary_path = existing_result_files.get("summary")
        if summary_path and summary_path.exists():
            st.text(summary_path.read_text(encoding="utf-8", errors="ignore"))

    timestep_path = existing_result_files.get("timestep")
    if timestep_path and timestep_path.exists():
        try:
            prev_df = numeric_timestep_dataframe(timestep_path)
            st.subheader("Previous hourly / timestep results")

            tab_energy, tab_temp, tab_hw, tab_raw = st.tabs(
                ["Energy profiles", "Zone temperatures", "Hot water profiles", "Raw timestep data"]
            )

            with tab_energy:
                energy_cols = [
                    c for c in prev_df.columns
                    if c != "Timestep"
                    and (
                        "mains elec:" in c.lower()
                        or "space heat demand" in c.lower()
                        or "space cool demand" in c.lower()
                    )
                ]
                if energy_cols:
                    st.line_chart(prev_df.set_index("Timestep")[energy_cols])
                else:
                    st.info("No energy profile columns found in previous results.")

            with tab_temp:
                temp_cols = [c for c in prev_df.columns if "temp" in c.lower()]
                if temp_cols:
                    st.line_chart(prev_df.set_index("Timestep")[temp_cols])
                else:
                    st.info("No temperature columns found in previous results.")

            with tab_hw:
                hw_cols = select_hot_water_profile_columns(prev_df.columns)
                if hw_cols:
                    st.line_chart(prev_df.set_index("Timestep")[hw_cols])
                    with st.expander("Hot water column totals", expanded=False):
                        st.dataframe(prev_df[hw_cols].sum(numeric_only=True).sort_values(ascending=False))
                else:
                    st.info("No non-zero hot-water profile columns found in previous results.")

            with tab_raw:
                st.dataframe(prev_df, width="stretch")

        except Exception as exc:
            st.warning(f"Previous timestep results could not be loaded: {exc}")

