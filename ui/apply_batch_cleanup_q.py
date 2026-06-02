from pathlib import Path


def write_file(path, content):
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"Updated {file_path}")


write_file(
    "ui/pages/10_Run_HEM_Results.py",
    """
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
from project_validation import (
    has_blocking_errors,
    split_messages,
    validate_project_before_run,
)
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
    st.error("No active project loaded. Go to Project Setup and upload/load a JSON first.")
    st.stop()

if not ACTIVE_HEM_INPUT_PATH.exists():
    st.error("No active HEM input file found. Go to Project Setup and upload/load a HEM JSON first.")
    st.stop()

project_data = active_project.get("project_data", {})
project_setup = project_data.get("project_setup", {})


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
        f"Heating systems: {len(space_heat_systems) if isinstance(space_heat_systems, dict) else 0}"
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

    return "\\n".join(lines)


st.header("1. Project build summary")

fabric_rows = project_data.get("fabric_elements", [])
ventilation = project_data.get("ventilation", {})
thermal_bridges = project_data.get("thermal_bridges", [])
weather_settings = project_data.get("weather_simulation", {})
space_heat_systems = project_data.get("space_heat_systems", {})
hot_water = project_data.get("hot_water", {})
gains_controls = project_data.get("gains_controls", {})
energy_supply = project_data.get("energy_supply", {})

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
        len(space_heat_systems) if isinstance(space_heat_systems, dict) else 0,
    )

with col5:
    st.metric("Hot water", "Yes" if hot_water else "No")

with col6:
    st.metric("Gains/controls", "Yes" if gains_controls else "No")

with col7:
    st.metric("Energy supply", "Yes" if energy_supply else "No")

with col8:
    st.metric(
        "Weather",
        "Yes" if weather_settings.get("weather_file") else "Default",
    )


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

            if GENERATED_SUMMARY_PATH.exists():
                summary_text = GENERATED_SUMMARY_PATH.read_text(encoding="utf-8")

                st.session_state["last_hem_summary_text"] = summary_text

                st.subheader("Results comparison")

                if BASE_SUMMARY_PATH.exists():
                    comparison = compare_summary_metrics(
                        BASE_SUMMARY_PATH,
                        GENERATED_SUMMARY_PATH,
                    )

                    st.session_state["last_results_comparison"] = comparison

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
""",
)

print("Batch Q complete.")