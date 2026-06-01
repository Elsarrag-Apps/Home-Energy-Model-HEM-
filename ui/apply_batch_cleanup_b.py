from pathlib import Path


def write_file(path: str, content: str) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"Updated {file_path}")


write_file(
    "ui/pages/1_Project_Setup.py",
    r'''
import sys
from pathlib import Path

import streamlit as st

CURRENT_DIR = Path(__file__).resolve().parent
UI_DIR = CURRENT_DIR.parent
UTILS_DIR = UI_DIR / "utils"
sys.path.append(str(UTILS_DIR))

from project_store import get_active_project, get_project_data_section, update_project_data


st.set_page_config(
    page_title="Project Setup",
    layout="wide",
)

st.title("Project Setup")

st.write(
    "Set the main project details used by the app. These values are saved into "
    "the app project JSON and can be reused later."
)

active_project = get_active_project()

if active_project is None:
    st.warning("No active project loaded. You can still enter values manually, or go to Home and load a JSON file.")
else:
    st.success("Active project loaded.")

saved_setup = get_project_data_section("project_setup", {}) or {}

hem_input = active_project.get("hem_input", {}) if active_project else {}
zones = hem_input.get("Zone", {})
first_zone = next(iter(zones.values()), {}) if zones else {}

default_floor_area = float(saved_setup.get("floor_area_m2", first_zone.get("area", 90.0)))
default_volume = float(saved_setup.get("internal_volume_m3", first_zone.get("volume", 225.0)))

st.header("1. Project information")

with st.form("project_setup_form"):
    col1, col2, col3 = st.columns(3)

    with col1:
        project_name = st.text_input(
            "Project name",
            value=saved_setup.get("project_name", "Demo dwelling - HL"),
        )

        case_id = st.text_input(
            "Case ID",
            value=saved_setup.get("case_id", "CASE-001"),
        )

        assessor = st.text_input(
            "Assessor",
            value=saved_setup.get("assessor", "Esam Elsarrag"),
        )

    with col2:
        dwelling_type = st.selectbox(
            "Dwelling type",
            ["Flat", "Detached house", "Semi-detached house", "Terraced house", "Other"],
            index=["Flat", "Detached house", "Semi-detached house", "Terraced house", "Other"].index(
                saved_setup.get("dwelling_type", "Flat")
            )
            if saved_setup.get("dwelling_type", "Flat") in ["Flat", "Detached house", "Semi-detached house", "Terraced house", "Other"]
            else 0,
        )

        assessment_type = st.selectbox(
            "Assessment type",
            ["Design assessment", "Existing dwelling", "Retrofit assessment", "Scenario test"],
            index=["Design assessment", "Existing dwelling", "Retrofit assessment", "Scenario test"].index(
                saved_setup.get("assessment_type", "Design assessment")
            )
            if saved_setup.get("assessment_type", "Design assessment") in ["Design assessment", "Existing dwelling", "Retrofit assessment", "Scenario test"]
            else 0,
        )

        number_of_zones = st.number_input(
            "Number of zones",
            min_value=1,
            value=int(saved_setup.get("number_of_zones", max(1, len(zones)))),
            step=1,
        )

    with col3:
        floor_area_m2 = st.number_input(
            "Floor area (m2)",
            min_value=0.0,
            value=default_floor_area,
            step=1.0,
        )

        internal_volume_m3 = st.number_input(
            "Internal volume (m3)",
            min_value=0.0,
            value=default_volume,
            step=1.0,
        )

        simulation_mode = st.selectbox(
            "Simulation mode",
            ["Short test run", "Annual run", "Custom"],
            index=["Short test run", "Annual run", "Custom"].index(
                saved_setup.get("simulation_mode", "Short test run")
            )
            if saved_setup.get("simulation_mode", "Short test run") in ["Short test run", "Annual run", "Custom"]
            else 0,
        )

    save_setup = st.form_submit_button("Save project setup")


if save_setup:
    project_setup = {
        "project_name": project_name,
        "case_id": case_id,
        "assessor": assessor,
        "dwelling_type": dwelling_type,
        "assessment_type": assessment_type,
        "floor_area_m2": floor_area_m2,
        "internal_volume_m3": internal_volume_m3,
        "number_of_zones": number_of_zones,
        "simulation_mode": simulation_mode,
    }

    st.session_state["project_setup"] = project_setup
    update_project_data("project_setup", project_setup)

    st.success("Project setup saved.")

st.header("2. Saved project setup")

current_setup = st.session_state.get(
    "project_setup",
    get_project_data_section("project_setup", {}) or {},
)

if current_setup:
    st.json(current_setup)
else:
    st.info("No project setup has been saved yet.")
''',
)


write_file(
    "ui/pages/2_Weather_Simulation.py",
    r'''
import sys
from pathlib import Path

import streamlit as st

CURRENT_DIR = Path(__file__).resolve().parent
UI_DIR = CURRENT_DIR.parent
UTILS_DIR = UI_DIR / "utils"
sys.path.append(str(UTILS_DIR))

from project_store import get_active_project, get_project_data_section, update_project_data


st.set_page_config(
    page_title="Weather & Simulation",
    layout="wide",
)

st.title("Weather & Simulation")

st.write(
    "Set the weather file and simulation run settings used when preparing and running HEM cases."
)

active_project = get_active_project()

if active_project is None:
    st.warning("No active project loaded. You can still enter settings manually, or go to Home and load a JSON file.")
else:
    st.success("Active project loaded.")

saved_settings = get_project_data_section("weather_simulation", {}) or {}

st.header("1. Weather source and run period")

with st.form("weather_simulation_form"):
    col1, col2, col3 = st.columns(3)

    with col1:
        weather_mode = st.selectbox(
            "Weather mode",
            [
                "Use default London CIBSE demo weather file",
                "Use custom CIBSE weather file path",
                "Use weather already defined in HEM JSON",
            ],
            index=[
                "Use default London CIBSE demo weather file",
                "Use custom CIBSE weather file path",
                "Use weather already defined in HEM JSON",
            ].index(saved_settings.get("weather_mode", "Use default London CIBSE demo weather file"))
            if saved_settings.get("weather_mode", "Use default London CIBSE demo weather file") in [
                "Use default London CIBSE demo weather file",
                "Use custom CIBSE weather file path",
                "Use weather already defined in HEM JSON",
            ]
            else 0,
        )

        weather_file = st.text_input(
            "Weather file path",
            value=saved_settings.get(
                "weather_file",
                r"test\e2e\demo_files\London_weather_CIBSE_format.csv",
            ),
        )

    with col2:
        run_type = st.selectbox(
            "Run type",
            ["24-hour test", "168-hour test", "Annual run", "Custom"],
            index=["24-hour test", "168-hour test", "Annual run", "Custom"].index(
                saved_settings.get("run_type", "24-hour test")
            )
            if saved_settings.get("run_type", "24-hour test") in ["24-hour test", "168-hour test", "Annual run", "Custom"]
            else 0,
        )

        start_day = st.number_input(
            "Start day",
            min_value=1,
            value=int(saved_settings.get("start_day", 1)),
            step=1,
        )

    with col3:
        simulation_hours = st.number_input(
            "Simulation hours",
            min_value=1,
            value=int(saved_settings.get("simulation_hours", 24)),
            step=1,
        )

        output_prefix = st.text_input(
            "Output prefix",
            value=saved_settings.get("output_prefix", "generated_case"),
        )

    save_settings = st.form_submit_button("Save weather and simulation settings")


if save_settings:
    weather_simulation = {
        "weather_mode": weather_mode,
        "weather_file": weather_file,
        "run_type": run_type,
        "start_day": start_day,
        "simulation_hours": simulation_hours,
        "output_prefix": output_prefix,
    }

    st.session_state["weather_simulation"] = weather_simulation
    update_project_data("weather_simulation", weather_simulation)

    st.success("Weather and simulation settings saved.")

st.header("2. Saved weather and simulation settings")

current_settings = st.session_state.get(
    "weather_simulation",
    get_project_data_section("weather_simulation", {}) or {},
)

if current_settings:
    st.json(current_settings)
else:
    st.info("No weather and simulation settings have been saved yet.")
''',
)


write_file(
    "ui/pages/3_Building_Fabric.py",
    r'''
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

CURRENT_DIR = Path(__file__).resolve().parent
UI_DIR = CURRENT_DIR.parent
UTILS_DIR = UI_DIR / "utils"
sys.path.append(str(UTILS_DIR))

from hem_extractors import summarise_active_hem_case
from input_builder import build_generated_fabric_input
from model_runner import run_hem_model
from project_store import update_project_data
from results_parser import compare_summary_metrics, format_number


st.set_page_config(
    page_title="Building Fabric",
    layout="wide",
)

st.title("Building Fabric")

st.write(
    "Review and edit fabric inputs. The app converts these values to a HEM "
    "BuildingElement structure, runs HEM, and compares results with the uploaded baseline case."
)

BASE_JSON_PATH = Path("ui/temp/active_hem_input.json")
WEATHER_FILE = Path("test/e2e/demo_files/London_weather_CIBSE_format.csv")
GENERATED_FABRIC_INPUT_PATH = Path("ui/temp/generated_fabric_case.json")

FABRIC_SUMMARY_PATH = Path(
    "ui/temp/generated_fabric_case__results/"
    "generated_fabric_case__core__results_summary.csv"
)

BASE_SUMMARY_PATH = Path(
    "test/e2e/demo_files/short/demo__results/"
    "demo__core__results_summary.csv"
)

if not BASE_JSON_PATH.exists():
    st.error("No active HEM input found. Go to the Home page and upload/load a HEM JSON first.")
    st.stop()

if "fabric_elements" not in st.session_state:
    st.session_state["fabric_elements"] = []

st.header("1. Input source")

try:
    case_summary = summarise_active_hem_case(BASE_JSON_PATH)
    fabric_counts = case_summary["fabric_counts"]

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric("Opaque elements in source", fabric_counts["opaque"])

    with c2:
        st.metric("Transparent elements in source", fabric_counts["transparent"])

    with c3:
        st.metric("Ground elements in source", fabric_counts["ground"])

    with c4:
        st.metric("Party walls in source", fabric_counts["party_wall"])

    st.caption(
        "These are summary counts from the uploaded HEM case. The detailed HEM element table is hidden to avoid confusing it with your editable inputs."
    )

except Exception as exc:
    st.warning("Could not summarise the active HEM fabric data.")
    with st.expander("Developer/debug: source summary error", expanded=False):
        st.exception(exc)

st.header("2. Fabric update mode")

fabric_update_mode = st.radio(
    "How should the generated HEM file handle existing fabric elements?",
    [
        "Add new UI elements to existing HEM elements",
        "Replace all existing elements",
    ],
    index=0,
)

if fabric_update_mode == "Add new UI elements to existing HEM elements":
    st.info("Safer mode: existing HEM elements are kept and your new UI elements are added.")
else:
    st.warning("Replace mode: existing HEM BuildingElement entries in zone 1 will be replaced by your UI elements.")

OPAQUE_ELEMENTS = [
    "External wall",
    "Roof",
    "Ground floor",
    "Exposed floor",
    "External door",
    "Party wall",
]

TRANSPARENT_ELEMENTS = [
    "Window",
    "Rooflight",
]


def default_u_value(element_type: str) -> float:
    values = {
        "External wall": 0.21,
        "Roof": 0.13,
        "Ground floor": 0.15,
        "Exposed floor": 0.15,
        "External door": 1.00,
        "Party wall": 0.50,
        "Window": 1.20,
        "Rooflight": 1.40,
    }
    return values.get(element_type, 0.21)


def default_pitch(element_type: str) -> float:
    if element_type == "Roof":
        return 0.0
    if element_type == "Ground floor":
        return 180.0
    if element_type == "Rooflight":
        return 30.0
    return 90.0


def is_external_opaque(element_type: str) -> bool:
    return element_type in [
        "External wall",
        "Roof",
        "Exposed floor",
        "External door",
    ]


st.header("3. Add fabric element")

element_type = st.selectbox(
    "Element type",
    [
        "External wall",
        "Roof",
        "Ground floor",
        "Exposed floor",
        "Window",
        "Rooflight",
        "External door",
        "Party wall",
    ],
)

with st.form("add_fabric_element_form"):
    col1, col2, col3 = st.columns(3)

    with col1:
        element_name = st.text_input("Element name", element_type)

        area_m2 = st.number_input(
            "Area (m2)",
            min_value=0.01,
            value=20.0,
            step=0.5,
        )

        u_value = st.number_input(
            "U-value (W/m2K)",
            min_value=0.01,
            value=default_u_value(element_type),
            step=0.01,
            format="%.3f",
        )

    with col2:
        orientation = st.selectbox(
            "Orientation",
            [
                "North",
                "North East",
                "East",
                "South East",
                "South",
                "South West",
                "West",
                "North West",
                "Horizontal",
                "Not applicable",
            ],
            index=4 if element_type in TRANSPARENT_ELEMENTS else 9,
        )

        pitch_degrees = st.number_input(
            "Pitch / tilt (degrees)",
            min_value=0.0,
            max_value=180.0,
            value=default_pitch(element_type),
            step=1.0,
        )

        base_height_m = st.number_input(
            "Base height (m)",
            min_value=0.0,
            value=0.0 if element_type != "Roof" else 2.7,
            step=0.1,
        )

    with col3:
        height_m = st.number_input(
            "Height (m)",
            min_value=0.01,
            value=2.7 if element_type not in ["Roof", "Ground floor"] else 6.0,
            step=0.1,
        )

        width_m = st.number_input(
            "Width (m)",
            min_value=0.01,
            value=max(0.1, 20.0 / 2.7),
            step=0.1,
        )

        mass_class = st.selectbox(
            "Mass class",
            ["Lightweight", "Medium", "Heavy", "Very heavy", "Unknown"],
            index=1,
        )

    col4, col5 = st.columns(2)

    with col4:
        areal_heat_capacity_kj_m2k = st.number_input(
            "Areal heat capacity (kJ/m2K)",
            min_value=0.0,
            value=145.0 if element_type == "External wall" else 75.0,
            step=5.0,
        )

    with col5:
        notes = st.text_input("Notes", "")

    extra_data = {}

    if is_external_opaque(element_type):
        st.subheader("External surface properties")

        col6, col7 = st.columns(2)

        with col6:
            solar_absorption_coeff = st.number_input(
                "Solar absorption coefficient",
                min_value=0.0,
                max_value=1.0,
                value=0.60,
                step=0.01,
                format="%.2f",
            )

        with col7:
            surface_finish = st.selectbox(
                "External surface finish",
                [
                    "Light / reflective finish",
                    "Medium colour finish",
                    "Dark brick / dark render",
                    "Very dark / black roof",
                    "User-defined",
                ],
            )

        extra_data.update(
            {
                "solar_absorption_coeff": solar_absorption_coeff,
                "surface_finish": surface_finish,
            }
        )

    if element_type in TRANSPARENT_ELEMENTS:
        st.subheader("Transparent element properties")

        g1, g2, g3, g4 = st.columns(4)

        with g1:
            g_value = st.number_input("g-value", min_value=0.0, max_value=1.0, value=0.71, step=0.01, format="%.2f")

        with g2:
            frame_factor = st.number_input("Frame factor", min_value=0.0, max_value=1.0, value=0.70, step=0.01, format="%.2f")

        with g3:
            openable_fraction = st.number_input("Openable fraction", min_value=0.0, max_value=1.0, value=0.0, step=0.05, format="%.2f")

        with g4:
            free_area_height_m = st.number_input("Free area height (m)", min_value=0.0, value=0.2, step=0.1)

        extra_data.update(
            {
                "g_value": g_value,
                "frame_factor": frame_factor,
                "openable_fraction": openable_fraction,
                "free_area_height_m": free_area_height_m,
            }
        )

    if element_type == "Ground floor":
        st.subheader("Ground floor properties")

        g1, g2, g3 = st.columns(3)

        with g1:
            perimeter_m = st.number_input("Perimeter (m)", min_value=0.0, value=28.0, step=0.5)

        with g2:
            thickness_walls_m = st.number_input("Wall thickness at floor edge (m)", min_value=0.0, value=0.1705, step=0.01, format="%.4f")

        with g3:
            psi_wall_floor_junc = st.number_input("Psi wall-floor junction (W/mK)", value=0.0, step=0.01, format="%.3f")

        floor_type = st.selectbox(
            "Ground floor type",
            [
                "Slab_no_edge_insulation",
                "Slab_edge_insulation",
                "Suspended_floor",
                "Heated_basement",
                "Unheated_basement",
            ],
        )

        extra_data.update(
            {
                "perimeter_m": perimeter_m,
                "thickness_walls_m": thickness_walls_m,
                "psi_wall_floor_junc": psi_wall_floor_junc,
                "floor_type": floor_type,
            }
        )

    if element_type == "Party wall":
        party_wall_cavity_type = st.selectbox(
            "Party wall cavity type",
            ["solid", "unfilled_unsealed", "filled", "defined_resistance"],
        )

        extra_data.update({"party_wall_cavity_type": party_wall_cavity_type})

    add_element = st.form_submit_button("Add fabric element")


if add_element:
    st.session_state["fabric_elements"].append(
        {
            "name": element_name,
            "type": element_type,
            "area_m2": area_m2,
            "u_value_w_m2k": u_value,
            "orientation": orientation,
            "pitch_degrees": pitch_degrees,
            "base_height_m": base_height_m,
            "height_m": height_m,
            "width_m": width_m,
            "mass_class": mass_class,
            "areal_heat_capacity_kj_m2k": areal_heat_capacity_kj_m2k,
            "notes": notes,
            **extra_data,
        }
    )

    update_project_data("fabric_elements", st.session_state["fabric_elements"])
    st.success(f"Added fabric element: {element_name}")

st.header("4. New UI fabric elements")

if not st.session_state["fabric_elements"]:
    st.info("No new fabric elements added yet.")
else:
    df = pd.DataFrame(st.session_state["fabric_elements"])

    st.dataframe(df, use_container_width=True, hide_index=True)

    total_area = df["area_m2"].sum()
    fabric_hlc = (df["area_m2"] * df["u_value_w_m2k"]).sum()
    average_u = fabric_hlc / total_area if total_area > 0 else 0

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("New element area", f"{total_area:.1f} m2")

    with col2:
        st.metric("Input HLC indicator", f"{fabric_hlc:.1f} W/K")

    with col3:
        st.metric("Area-weighted U-value", f"{average_u:.3f} W/m2K")

    chart_df = df.copy()
    chart_df["hlc_w_k"] = chart_df["area_m2"] * chart_df["u_value_w_m2k"]
    st.bar_chart(chart_df[["name", "hlc_w_k"]].set_index("name"))

    if st.button("Clear new fabric elements"):
        st.session_state["fabric_elements"] = []
        update_project_data("fabric_elements", [])
        st.rerun()

st.header("5. Prepare and run HEM")

if not st.session_state["fabric_elements"]:
    st.warning("Add at least one fabric element before preparing the HEM input.")
else:
    if st.button("Prepare HEM input from these fabric values"):
        try:
            generated_input = build_generated_fabric_input(
                base_json_path=BASE_JSON_PATH,
                output_json_path=GENERATED_FABRIC_INPUT_PATH,
                fabric_elements=st.session_state["fabric_elements"],
                zone_name="zone 1",
                update_mode=fabric_update_mode,
            )

            st.session_state["generated_fabric_input_ready"] = True
            st.session_state["last_generated_fabric_json"] = generated_input["Zone"]["zone 1"]["BuildingElement"]

            st.success("HEM input prepared successfully from these fabric values.")

        except Exception as exc:
            st.error("Failed to prepare HEM fabric input.")
            with st.expander("Developer/debug: preparation error", expanded=True):
                st.exception(exc)

    if st.session_state.get("generated_fabric_input_ready"):
        st.info("Prepared case is ready. You can now run HEM and compare results.")

        if st.button("Run HEM and compare fabric case"):
            with st.spinner("Running HEM..."):
                result = run_hem_model(GENERATED_FABRIC_INPUT_PATH, WEATHER_FILE)

            if result.returncode == 0:
                st.success("HEM run completed successfully.")

                if FABRIC_SUMMARY_PATH.exists():
                    summary_text = FABRIC_SUMMARY_PATH.read_text(encoding="utf-8")

                    st.subheader("Results comparison")

                    if BASE_SUMMARY_PATH.exists():
                        comparison = compare_summary_metrics(
                            BASE_SUMMARY_PATH,
                            FABRIC_SUMMARY_PATH,
                        )

                        col1, col2, col3 = st.columns(3)

                        space_heat = next(item for item in comparison if item["metric"] == "Space heat demand")
                        peak_elec = next(item for item in comparison if item["metric"] == "Peak electricity consumption")
                        delivered = next(item for item in comparison if item["metric"] == "Delivered energy total")

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

                        with st.expander("Detailed comparison table", expanded=False):
                            st.dataframe(comparison, use_container_width=True, hide_index=True)

                    else:
                        st.warning("Base summary file was not found. Run the baseline case first if comparison is needed.")

                    with st.expander("View full HEM summary output", expanded=False):
                        st.text(summary_text)

                    st.download_button(
                        "Download HEM summary CSV",
                        data=summary_text,
                        file_name="generated_fabric_case__core__results_summary.csv",
                        mime="text/csv",
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

with st.expander("Advanced: view generated HEM fabric JSON", expanded=False):
    generated_json = st.session_state.get("last_generated_fabric_json")

    if generated_json is None:
        st.write("No generated fabric JSON has been prepared yet.")
    else:
        st.json(generated_json)

with st.expander("Developer/debug: view saved fabric state", expanded=False):
    st.json(st.session_state.get("fabric_elements", []))
''',
)


write_file(
    "ui/pages/4_Thermal_Bridges.py",
    r'''
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

CURRENT_DIR = Path(__file__).resolve().parent
UI_DIR = CURRENT_DIR.parent
UTILS_DIR = UI_DIR / "utils"
sys.path.append(str(UTILS_DIR))

from project_store import get_project_data_section, update_project_data


st.set_page_config(
    page_title="Thermal Bridges",
    layout="wide",
)

st.title("Thermal Bridges")

st.write(
    "Add linear and point thermal bridges. This page saves thermal bridge inputs "
    "to the app project JSON. HEM connection for thermal bridging will be added next."
)

SAP_JUNCTION_DEFAULTS = {
    "Custom / user-defined": None,
    "E1 Steel lintel with perforated steel base plate": 0.50,
    "E2 Other lintel": 0.30,
    "E3 Sill": 0.04,
    "E4 Jamb": 0.05,
    "E5 Ground floor": 0.16,
    "E6 Intermediate floor within dwelling": 0.07,
    "E7 Party floor between dwellings": 0.07,
    "E8 Balcony within wall insulation": 0.02,
    "E9 Balcony outside wall insulation": 0.32,
    "E10 Eaves insulated at ceiling level": 0.06,
    "E11 Eaves insulated at rafter level": 0.04,
    "E12 Gable insulated at ceiling level": 0.24,
    "E13 Gable insulated at rafter level": 0.04,
    "E14 Corner normal": 0.09,
    "E15 Corner inverted": -0.09,
    "E16 Party wall between dwellings": 0.06,
    "E17 Ground floor edge steel/timber frame": 0.32,
}

if "thermal_bridges" not in st.session_state:
    st.session_state["thermal_bridges"] = get_project_data_section(
        "thermal_bridges",
        [],
    ) or []

st.header("1. Add thermal bridge")

bridge_type = st.selectbox("Bridge type", ["Linear bridge", "Point bridge"])

with st.form("add_thermal_bridge_form"):
    col1, col2, col3 = st.columns(3)

    with col1:
        bridge_name = st.text_input("Bridge name / description", "Wall-floor junction")

        junction_category = st.selectbox(
            "Junction category",
            list(SAP_JUNCTION_DEFAULTS.keys()),
        )

    with col2:
        default_psi = SAP_JUNCTION_DEFAULTS.get(junction_category)

        if bridge_type == "Linear bridge":
            psi_value = st.number_input(
                "Psi-value (W/mK)",
                value=float(default_psi) if default_psi is not None else 0.16,
                step=0.001,
                format="%.3f",
            )

            length_m = st.number_input("Length (m)", min_value=0.0, value=10.0, step=0.5)

            chi_value = None
            quantity = None

        else:
            chi_value = st.number_input(
                "Chi-value (W/K)",
                min_value=0.0,
                value=0.02,
                step=0.001,
                format="%.3f",
            )

            quantity = st.number_input("Quantity", min_value=1, value=1, step=1)

            psi_value = None
            length_m = None

    with col3:
        connected_element = st.selectbox(
            "Connected element / location",
            [
                "External wall",
                "Roof",
                "Ground floor",
                "Window / door opening",
                "Balcony",
                "Party wall",
                "Internal junction",
                "Other",
            ],
        )

        source = st.selectbox(
            "Value source",
            [
                "Default value",
                "Manufacturer / accredited detail",
                "Project calculation",
                "User-defined",
                "Unknown",
            ],
        )

    notes = st.text_input("Notes / detail reference", value="")

    add_bridge = st.form_submit_button("Add thermal bridge")

if add_bridge:
    if bridge_type == "Linear bridge":
        hlc_w_k = psi_value * length_m
        display_value = f"Psi={psi_value:.3f} W/mK x {length_m:.2f} m"
    else:
        hlc_w_k = chi_value * quantity
        display_value = f"Chi={chi_value:.3f} W/K x {quantity}"

    st.session_state["thermal_bridges"].append(
        {
            "name": bridge_name,
            "bridge_type": bridge_type,
            "junction_category": junction_category,
            "connected_element": connected_element,
            "source": source,
            "psi_value_w_mk": psi_value,
            "length_m": length_m,
            "chi_value_w_k": chi_value,
            "quantity": quantity,
            "calculation": display_value,
            "thermal_bridge_hlc_w_k": hlc_w_k,
            "notes": notes,
        }
    )

    update_project_data("thermal_bridges", st.session_state["thermal_bridges"])
    st.success(f"Added thermal bridge: {bridge_name}")

st.header("2. Thermal bridge inputs")

if not st.session_state["thermal_bridges"]:
    st.info("No thermal bridges have been added yet.")
else:
    df = pd.DataFrame(st.session_state["thermal_bridges"])

    st.dataframe(df, use_container_width=True, hide_index=True)

    total_bridge_hlc = df["thermal_bridge_hlc_w_k"].sum()
    largest_bridge = df.sort_values("thermal_bridge_hlc_w_k", ascending=False).iloc[0]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total bridge HLC", f"{total_bridge_hlc:.2f} W/K")

    with col2:
        st.metric("Largest bridge", f"{largest_bridge['thermal_bridge_hlc_w_k']:.2f} W/K")

    with col3:
        st.metric("Heat loss at delta T=21K", f"{total_bridge_hlc * 21:.1f} W")

    st.subheader("Bridge HLC contribution")
    st.bar_chart(df[["name", "thermal_bridge_hlc_w_k"]].set_index("name"))

    if st.button("Save thermal bridge inputs"):
        update_project_data("thermal_bridges", st.session_state["thermal_bridges"])
        st.success("Thermal bridge inputs saved to the app project.")

    if st.button("Clear thermal bridges"):
        st.session_state["thermal_bridges"] = []
        update_project_data("thermal_bridges", [])
        st.rerun()

with st.expander("Developer/debug: view saved thermal bridge state", expanded=False):
    st.json(st.session_state.get("thermal_bridges", []))
''',
)

print("Batch cleanup B complete.")