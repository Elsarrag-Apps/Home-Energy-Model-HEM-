import json
import sys
from pathlib import Path

import streamlit as st

CURRENT_DIR = Path(__file__).resolve().parent
UI_DIR = CURRENT_DIR.parent
UTILS_DIR = UI_DIR / "utils"
sys.path.append(str(UTILS_DIR))

from full_case_builder import build_full_project_case
from model_runner import run_hem_model
from project_store import ACTIVE_HEM_INPUT_PATH, get_active_project
from results_parser import compare_summary_metrics, format_number


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

GENERATED_SUMMARY_PATH = Path(
    "ui/temp/generated_full_project_case__results/"
    "generated_full_project_case__core__results_summary.csv"
)

BASE_SUMMARY_PATH = Path(
    "test/e2e/demo_files/short/demo__results/"
    "demo__core__results_summary.csv"
)

DEFAULT_WEATHER_FILE = Path("test/e2e/demo_files/London_weather_CIBSE_format.csv")

active_project = get_active_project()

if active_project is None:
    st.error("No active project loaded. Go to the Home page and upload/load a JSON first.")
    st.stop()

if not ACTIVE_HEM_INPUT_PATH.exists():
    st.error("No active HEM input file found. Go to the Home page and upload/load a HEM JSON first.")
    st.stop()

project_data = active_project.get("project_data", {})

st.header("1. Project build summary")

fabric_rows = project_data.get("fabric_elements", [])
ventilation = project_data.get("ventilation", {})
thermal_bridges = project_data.get("thermal_bridges", [])
weather_settings = project_data.get("weather_simulation", {})
space_heat_systems = project_data.get("space_heat_systems", {})
hot_water = project_data.get("hot_water", {})

col1, col2, col3, col4, col5, col6 = st.columns(6)

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
        "Heating systems",
        len(space_heat_systems) if isinstance(space_heat_systems, dict) else 0,
    )

with col5:
    st.metric(
        "Hot water",
        "Yes" if hot_water else "No",
    )

with col6:
    st.metric(
        "Weather",
        "Yes" if weather_settings.get("weather_file") else "Default",
    )

st.header("2. Weather used for this run")

weather_file = Path(
    weather_settings.get(
        "weather_file",
        str(DEFAULT_WEATHER_FILE),
    )
)

if not weather_file.exists():
    st.warning(
        f"Saved weather file was not found: {weather_file}. "
        "The run will use the default London CIBSE demo weather file."
    )
    weather_file = DEFAULT_WEATHER_FILE

w1, w2 = st.columns(2)

with w1:
    st.metric("Weather file type", weather_file.suffix.lower().replace(".", "") or "unknown")

with w2:
    st.write(str(weather_file))

st.header("3. Build generated HEM input")

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
        st.error("Failed to build full HEM input.")
        with st.expander("Developer/debug: build error", expanded=True):
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

st.header("4. Run HEM and compare results")

if not st.session_state.get("generated_full_case_ready"):
    st.warning("Build the full HEM input before running HEM.")
else:
    if st.button("Run HEM and compare full project case"):
        with st.spinner("Running HEM..."):
            result = run_hem_model(GENERATED_FULL_CASE_PATH, weather_file)

        if result.returncode == 0:
            st.success("HEM run completed successfully.")

            if GENERATED_SUMMARY_PATH.exists():
                summary_text = GENERATED_SUMMARY_PATH.read_text(encoding="utf-8")

                st.subheader("Results comparison")

                if BASE_SUMMARY_PATH.exists():
                    comparison = compare_summary_metrics(
                        BASE_SUMMARY_PATH,
                        GENERATED_SUMMARY_PATH,
                    )

                    col1, col2, col3, col4 = st.columns(4)

                    space_heat = next(
                        item
                        for item in comparison
                        if item["metric"] == "Space heat demand"
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

                    with col1:
                        st.metric(
                            "Space heat demand",
                            f"{format_number(space_heat['generated_value'])} {space_heat['unit']}",
                            f"{format_number(space_heat['difference'])} {space_heat['unit']}",
                        )

                    with col2:
                        st.metric(
                            "Peak electricity",
                            f"{format_number(peak_elec['generated_value'])} {peak_elec['unit']}",
                            f"{format_number(peak_elec['difference'])} {peak_elec['unit']}",
                        )

                    with col3:
                        st.metric(
                            "Delivered energy",
                            f"{format_number(delivered['generated_value'])} {delivered['unit']}",
                            f"{format_number(delivered['difference'])} {delivered['unit']}",
                        )

                    with col4:
                        st.metric(
                            "Mechanical ventilation",
                            f"{format_number(mech_vent['generated_value'])} {mech_vent['unit']}",
                            f"{format_number(mech_vent['difference'])} {mech_vent['unit']}",
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

                with st.expander("View full HEM summary output", expanded=False):
                    st.text(summary_text)

                st.download_button(
                    "Download HEM summary CSV",
                    data=summary_text,
                    file_name="generated_full_project_case__core__results_summary.csv",
                    mime="text/csv",
                )

                generated_json_text = GENERATED_FULL_CASE_PATH.read_text(
                    encoding="utf-8"
                )

                st.download_button(
                    "Download generated HEM input JSON",
                    data=generated_json_text,
                    file_name="generated_full_project_case.json",
                    mime="application/json",
                )

            else:
                st.warning("HEM ran, but the expected summary file was not found.")

        else:
            st.error("HEM run failed.")
            st.subheader("Error output")
            st.code(result.stderr)

            if result.stdout:
                st.subheader("Model output")
                st.code(result.stdout)

with st.expander("Developer/debug: saved project data used for this run", expanded=False):
    st.json(project_data)
