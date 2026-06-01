from pathlib import Path


def write_file(path: str, content: str) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"Updated {file_path}")


write_file(
    "ui/utils/full_case_builder.py",
    r'''
import json
from pathlib import Path

from input_builder import (
    build_hem_building_elements,
    build_hem_infiltration_ventilation,
)


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return path


def apply_fabric_to_case(
    hem_input: dict,
    fabric_elements: list,
    update_mode: str = "Replace all existing elements",
    zone_name: str = "zone 1",
) -> dict:
    """Apply saved fabric rows to a HEM input dictionary."""
    if not fabric_elements:
        return hem_input

    if "Zone" not in hem_input:
        raise KeyError("HEM input does not contain a Zone section.")

    if zone_name not in hem_input["Zone"]:
        zone_name = next(iter(hem_input["Zone"].keys()))

    existing_elements = hem_input["Zone"][zone_name].get("BuildingElement", {})

    if update_mode == "Add new UI elements to existing HEM elements":
        updated_elements = existing_elements.copy()
        new_elements = build_hem_building_elements(
            fabric_elements,
            existing_elements=existing_elements,
        )
        updated_elements.update(new_elements)
    else:
        updated_elements = build_hem_building_elements(fabric_elements)

    hem_input["Zone"][zone_name]["BuildingElement"] = updated_elements

    floor_areas = [
        float(element.get("area_m2", 0))
        for element in fabric_elements
        if element.get("type") == "Ground floor"
    ]

    if floor_areas and update_mode == "Replace all existing elements":
        floor_area = sum(floor_areas)
        hem_input["Zone"][zone_name]["area"] = floor_area
        hem_input["Zone"][zone_name]["volume"] = floor_area * 2.7

    return hem_input


def apply_ventilation_to_case(
    hem_input: dict,
    ventilation_data: dict,
) -> dict:
    """Apply saved ventilation data to a HEM input dictionary."""
    if not ventilation_data:
        return hem_input

    airtightness_exposure = ventilation_data.get("airtightness_exposure")
    background_vents = ventilation_data.get("background_vents", [])
    mechanical_ventilation = ventilation_data.get("mechanical_ventilation")

    if not airtightness_exposure:
        return hem_input

    hem_input["InfiltrationVentilation"] = build_hem_infiltration_ventilation(
        airtightness_exposure=airtightness_exposure,
        background_vents=background_vents,
        mechanical_ventilation=mechanical_ventilation,
    )

    return hem_input


def build_full_project_case(
    base_json_path: Path,
    output_json_path: Path,
    project_data: dict,
) -> dict:
    """Build one full HEM input case from saved app project data."""
    hem_input = load_json(base_json_path)

    project_sections = project_data.get("project_data", {})

    fabric_elements = project_sections.get("fabric_elements", [])
    fabric_update_mode = project_sections.get(
        "fabric_update_mode",
        "Replace all existing elements",
    )

    ventilation_data = project_sections.get("ventilation", {})

    hem_input = apply_fabric_to_case(
        hem_input=hem_input,
        fabric_elements=fabric_elements,
        update_mode=fabric_update_mode,
        zone_name="zone 1",
    )

    hem_input = apply_ventilation_to_case(
        hem_input=hem_input,
        ventilation_data=ventilation_data,
    )

    save_json(output_json_path, hem_input)

    return hem_input
''',
)


write_file(
    "ui/pages/9_Run_HEM_Results.py",
    r'''
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

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Fabric rows saved", len(fabric_rows))

with col2:
    st.metric(
        "Ventilation saved",
        "Yes" if ventilation.get("airtightness_exposure") else "No",
    )

with col3:
    st.metric("Thermal bridges saved", len(thermal_bridges))

with col4:
    st.metric(
        "Weather saved",
        "Yes" if weather_settings.get("weather_file") else "Default",
    )

if thermal_bridges:
    st.info(
        "Thermal bridges are saved in the app project, but are not yet written into "
        "the generated HEM JSON. That connection will be added in the next batch."
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
''',
)

print("Batch cleanup D complete.")