from pathlib import Path


def write_file(path: str, content: str) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"Updated {file_path}")


write_file(
    "ui/utils/model_runner.py",
    r'''
import subprocess
import sys
from pathlib import Path


def get_weather_argument(weather_file: Path) -> list[str]:
    """Return the correct HEM weather command argument for CSV or EPW files."""
    suffix = weather_file.suffix.lower()

    if suffix == ".csv":
        return ["--CIBSE-weather-file", str(weather_file)]

    if suffix == ".epw":
        return ["--epw-file", str(weather_file)]

    raise ValueError(
        f"Unsupported weather file type: {suffix}. Expected .csv or .epw."
    )


def run_hem_model(input_json_path: Path, weather_file: Path):
    """Run HEM with a generated input JSON and weather file."""
    input_json_path = Path(input_json_path)
    weather_file = Path(weather_file)

    if not input_json_path.exists():
        raise FileNotFoundError(f"HEM input JSON not found: {input_json_path}")

    if not weather_file.exists():
        raise FileNotFoundError(f"Weather file not found: {weather_file}")

    command = [
        "uv",
        "run",
        "hem-core",
        str(input_json_path),
        *get_weather_argument(weather_file),
    ]

    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        shell=False,
    )
''',
)


write_file(
    "ui/utils/hem_extractors.py",
    r'''
import json
from pathlib import Path


HEM_SHIELD_TO_UI = {
    "Open": "Open / exposed",
    "Normal": "Normal / suburban",
    "Shielded": "Shielded / dense urban",
}


HEM_TERRAIN_TO_UI = {
    "OpenWater": "Open water",
    "OpenField": "Open country",
    "Suburban": "Suburban",
    "Urban": "Urban",
}


HEM_MECH_TO_UI = {
    "Intermittent MEV": "Intermittent MEV",
    "Centralised continuous MEV": "Centralised continuous MEV",
    "Decentralised continuous MEV": "Decentralised continuous MEV",
    "MVHR": "MVHR",
    "Positive input ventilation": "Positive input ventilation",
}


DEGREES_TO_ORIENTATION = {
    0: "North",
    45: "North East",
    90: "East",
    135: "South East",
    180: "South",
    225: "South West",
    270: "West",
    315: "North West",
}


def load_json_file(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def orientation_from_degrees(value) -> str:
    """Convert HEM orientation degrees to nearest UI orientation label."""
    try:
        degrees = int(round(float(value) / 45) * 45) % 360
    except (TypeError, ValueError):
        return "North"

    return DEGREES_TO_ORIENTATION.get(degrees, "North")


def u_value_from_resistance(value, fallback=0.21) -> float:
    """Convert HEM thermal resistance to approximate U-value."""
    try:
        resistance = float(value)
        if resistance > 0:
            return 1.0 / resistance
    except (TypeError, ValueError):
        pass

    return fallback


def element_type_from_hem(name: str, element: dict) -> str:
    """Map HEM BuildingElement type to user-facing element type."""
    hem_type = element.get("type")

    if hem_type == "BuildingElementTransparent":
        pitch = float(element.get("pitch", 90))
        return "Rooflight" if pitch < 75 else "Window"

    if hem_type == "BuildingElementGround":
        return "Ground floor"

    if hem_type == "BuildingElementPartyWall":
        return "Party wall"

    if hem_type == "BuildingElementOpaque":
        pitch = float(element.get("pitch", 90))
        if pitch < 45:
            return "Roof"
        if pitch > 135:
            return "Exposed floor"
        if "door" in name.lower():
            return "External door"
        return "External wall"

    return "External wall"


def extract_fabric_elements_from_hem(
    hem_json_path: Path,
    zone_name: str = "zone 1",
) -> list[dict]:
    """Extract editable fabric rows from HEM Zone -> BuildingElement."""
    hem_input = load_json_file(hem_json_path)

    zones = hem_input.get("Zone", {})

    if zone_name not in zones:
        if not zones:
            return []
        zone_name = next(iter(zones.keys()))

    building_elements = zones[zone_name].get("BuildingElement", {})

    rows = []

    for name, element in building_elements.items():
        hem_type = element.get("type")
        element_type = element_type_from_hem(name, element)

        area = element.get("area", element.get("total_area", 0.0))

        if hem_type == "BuildingElementGround":
            u_value = float(element.get("u_value", 0.15))
        else:
            fallback = 1.2 if hem_type == "BuildingElementTransparent" else 0.21
            u_value = u_value_from_resistance(
                element.get("thermal_resistance_construction"),
                fallback=fallback,
            )

        height = float(element.get("height", 2.7))
        width = float(element.get("width", 0.0))

        if width <= 0 and height > 0:
            width = float(area) / height

        row = {
            "source_name": name,
            "name": name,
            "type": element_type,
            "area_m2": float(area),
            "u_value_w_m2k": float(u_value),
            "orientation": orientation_from_degrees(
                element.get("orientation360", 0)
            )
            if "orientation360" in element
            else "Not applicable",
            "pitch_degrees": float(element.get("pitch", 90.0)),
            "base_height_m": float(element.get("base_height", 0.0)),
            "height_m": height,
            "width_m": width,
            "mass_class": "Medium",
            "areal_heat_capacity_kj_m2k": float(
                element.get("areal_heat_capacity", 75000)
            )
            / 1000,
            "solar_absorption_coeff": float(
                element.get("solar_absorption_coeff", 0.6)
            ),
            "g_value": float(element.get("g_value", 0.71)),
            "frame_factor": 1.0 - float(element.get("frame_area_fraction", 0.0)),
            "openable_fraction": 0.0,
            "free_area_height_m": float(element.get("free_area_height", 0.2)),
            "perimeter_m": float(element.get("perimeter", 28.0)),
            "thickness_walls_m": float(element.get("thickness_walls", 0.1705)),
            "psi_wall_floor_junc": float(element.get("psi_wall_floor_junc", 0.0)),
            "floor_type": element.get("floor_type", "Slab_no_edge_insulation"),
            "party_wall_cavity_type": element.get(
                "party_wall_cavity_type",
                "solid",
            ),
            "notes": "Loaded from uploaded HEM JSON",
        }

        rows.append(row)

    return rows


def extract_ventilation_defaults_from_hem(hem_json_path: Path) -> dict:
    """Extract UI-friendly infiltration and ventilation defaults from HEM JSON."""
    hem_input = load_json_file(hem_json_path)
    infil = hem_input.get("InfiltrationVentilation", {})

    leaks = infil.get("Leaks", {})

    airtightness_exposure = {
        "q50_m3_h_m2": float(leaks.get("test_result", 1.2)),
        "test_pressure_pa": float(leaks.get("test_pressure", 50)),
        "envelope_area_m2": float(leaks.get("env_area", 220)),
        "ventilation_zone_height_m": float(leaks.get("ventilation_zone_height", 6)),
        "zone_base_height_m": float(infil.get("ventilation_zone_base_height", 2.5)),
        "altitude_m": float(infil.get("altitude", 30)),
        "shield_class": HEM_SHIELD_TO_UI.get(
            infil.get("shield_class", "Normal"),
            "Normal / suburban",
        ),
        "terrain_class": HEM_TERRAIN_TO_UI.get(
            infil.get("terrain_class", "OpenField"),
            "Open country",
        ),
        "cross_ventilation": bool(infil.get("cross_vent_possible", True)),
    }

    background_vents = []

    for name, vent in infil.get("Vents", {}).items():
        background_vents.append(
            {
                "name": name,
                "area_cm2": float(vent.get("area_cm2", 100)),
                "pressure_difference_ref": float(
                    vent.get("pressure_difference_ref", 20)
                ),
                "mid_height_m": float(
                    vent.get("mid_height_air_flow_path", 1.5)
                ),
                "orientation": orientation_from_degrees(
                    vent.get("orientation360", 180)
                ),
                "pitch": float(vent.get("pitch", 60)),
            }
        )

    mechanical_ventilation = {
        "vent_type": "None",
        "energy_supply": "mains elec",
        "design_flow_l_s": 0.0,
        "sfp_w_l_s": 0.5,
        "sfp_in_use_factor": 1.0,
        "mvhr_efficiency_percent": 0.0,
        "mvhr_location": "inside",
        "intake_orientation": "North",
        "intake_pitch": 90.0,
        "intake_mid_height_m": 2.0,
        "exhaust_orientation": "South",
        "exhaust_pitch": 90.0,
        "exhaust_mid_height_m": 2.0,
    }

    mech_section = infil.get("MechanicalVentilation", {})

    if mech_section:
        first_mech = next(iter(mech_section.values()))

        hem_vent_type = first_mech.get("vent_type", "None")

        mechanical_ventilation["vent_type"] = HEM_MECH_TO_UI.get(
            hem_vent_type,
            "None",
        )

        mechanical_ventilation["energy_supply"] = first_mech.get(
            "EnergySupply",
            "mains elec",
        )

        mechanical_ventilation["design_flow_l_s"] = (
            float(first_mech.get("design_outdoor_air_flow_rate", 0.0)) / 3.6
        )

        mechanical_ventilation["sfp_w_l_s"] = float(first_mech.get("SFP", 0.5))

        mechanical_ventilation["sfp_in_use_factor"] = float(
            first_mech.get("SFP_in_use_factor", 1.0)
        )

        mechanical_ventilation["mvhr_efficiency_percent"] = (
            float(first_mech.get("mvhr_eff", 0.0)) * 100
        )

        mechanical_ventilation["mvhr_location"] = first_mech.get(
            "mvhr_location",
            "inside",
        )

        intake = first_mech.get("position_intake", {})
        exhaust = first_mech.get("position_exhaust", {})

        mechanical_ventilation["intake_orientation"] = orientation_from_degrees(
            intake.get("orientation360", 0)
        )
        mechanical_ventilation["intake_pitch"] = float(intake.get("pitch", 90))
        mechanical_ventilation["intake_mid_height_m"] = float(
            intake.get("mid_height_air_flow_path", 2.0)
        )

        mechanical_ventilation["exhaust_orientation"] = orientation_from_degrees(
            exhaust.get("orientation360", 180)
        )
        mechanical_ventilation["exhaust_pitch"] = float(exhaust.get("pitch", 90))
        mechanical_ventilation["exhaust_mid_height_m"] = float(
            exhaust.get("mid_height_air_flow_path", 2.0)
        )

    return {
        "airtightness_exposure": airtightness_exposure,
        "background_vents": background_vents,
        "mechanical_ventilation": mechanical_ventilation,
    }


def summarise_active_hem_case(hem_json_path: Path) -> dict:
    """Return a user-friendly summary of the active HEM case."""
    hem_input = load_json_file(hem_json_path)

    zones = hem_input.get("Zone", {})
    infil = hem_input.get("InfiltrationVentilation", {})

    fabric_counts = {
        "opaque": 0,
        "transparent": 0,
        "ground": 0,
        "party_wall": 0,
    }

    for zone in zones.values():
        for element in zone.get("BuildingElement", {}).values():
            element_type = element.get("type")

            if element_type == "BuildingElementOpaque":
                fabric_counts["opaque"] += 1
            elif element_type == "BuildingElementTransparent":
                fabric_counts["transparent"] += 1
            elif element_type == "BuildingElementGround":
                fabric_counts["ground"] += 1
            elif element_type == "BuildingElementPartyWall":
                fabric_counts["party_wall"] += 1

    return {
        "zone_count": len(zones),
        "has_infiltration_ventilation": bool(infil),
        "background_vent_count": len(infil.get("Vents", {})),
        "mechanical_ventilation_count": len(infil.get("MechanicalVentilation", {})),
        "fabric_counts": fabric_counts,
    }
''',
)


write_file(
    "ui/pages/2_Weather_Simulation.py",
    r'''
import shutil
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
    "Upload or select the weather file used when running HEM. The app supports "
    "CIBSE CSV weather files and EPW weather files."
)

WEATHER_TEMP_DIR = Path("ui/temp/weather")
WEATHER_TEMP_DIR.mkdir(parents=True, exist_ok=True)

active_project = get_active_project()

if active_project is None:
    st.warning(
        "No active project loaded. You can still upload a weather file, but it is best "
        "to load or start a project on the Home page first."
    )
else:
    st.success("Active project loaded.")

saved_settings = get_project_data_section("weather_simulation", {}) or {}

st.header("1. Weather file")

weather_source_mode = st.radio(
    "Weather source",
    [
        "Upload weather file",
        "Use default London CIBSE demo weather file",
        "Use previously saved weather file",
    ],
    index=0,
)

uploaded_weather = None
weather_file_path = saved_settings.get(
    "weather_file",
    r"test\e2e\demo_files\London_weather_CIBSE_format.csv",
)

weather_file_type = saved_settings.get("weather_file_type", "csv")

if weather_source_mode == "Upload weather file":
    uploaded_weather = st.file_uploader(
        "Upload CIBSE CSV or EPW weather file",
        type=["csv", "epw"],
    )

    if uploaded_weather is not None:
        safe_name = Path(uploaded_weather.name).name
        saved_weather_path = WEATHER_TEMP_DIR / safe_name

        with open(saved_weather_path, "wb") as f:
            shutil.copyfileobj(uploaded_weather, f)

        weather_file_path = str(saved_weather_path)
        weather_file_type = saved_weather_path.suffix.lower().replace(".", "")

        st.success(f"Weather file uploaded and saved to: {saved_weather_path}")

elif weather_source_mode == "Use default London CIBSE demo weather file":
    weather_file_path = r"test\e2e\demo_files\London_weather_CIBSE_format.csv"
    weather_file_type = "csv"
    st.info("Using default London CIBSE demo weather file.")

else:
    if weather_file_path:
        st.info(f"Using saved weather file: {weather_file_path}")
    else:
        st.warning("No previously saved weather file found.")

st.header("2. Simulation period")

with st.form("weather_simulation_form"):
    col1, col2, col3 = st.columns(3)

    with col1:
        weather_file_display = st.text_input(
            "Selected weather file",
            value=weather_file_path,
        )

        weather_type_display = st.selectbox(
            "Weather file type",
            ["csv", "epw"],
            index=0 if weather_file_type == "csv" else 1,
        )

    with col2:
        run_type = st.selectbox(
            "Run type",
            ["24-hour test", "168-hour test", "Annual run", "Custom"],
            index=["24-hour test", "168-hour test", "Annual run", "Custom"].index(
                saved_settings.get("run_type", "24-hour test")
            )
            if saved_settings.get("run_type", "24-hour test")
            in ["24-hour test", "168-hour test", "Annual run", "Custom"]
            else 0,
        )

        start_day = st.number_input(
            "Start day",
            min_value=1,
            value=int(saved_settings.get("start_day", 1)),
            step=1,
        )

    with col3:
        default_hours = {
            "24-hour test": 24,
            "168-hour test": 168,
            "Annual run": 8760,
            "Custom": int(saved_settings.get("simulation_hours", 24)),
        }[run_type]

        simulation_hours = st.number_input(
            "Simulation hours",
            min_value=1,
            value=int(saved_settings.get("simulation_hours", default_hours)),
            step=1,
        )

        output_prefix = st.text_input(
            "Output prefix",
            value=saved_settings.get("output_prefix", "generated_case"),
        )

    save_settings = st.form_submit_button("Save weather and simulation settings")

if save_settings:
    weather_simulation = {
        "weather_source_mode": weather_source_mode,
        "weather_file": weather_file_display,
        "weather_file_type": weather_type_display,
        "run_type": run_type,
        "start_day": start_day,
        "simulation_hours": simulation_hours,
        "output_prefix": output_prefix,
    }

    st.session_state["weather_simulation"] = weather_simulation
    update_project_data("weather_simulation", weather_simulation)

    st.success("Weather and simulation settings saved.")

st.header("3. Saved weather and simulation settings")

current_settings = st.session_state.get(
    "weather_simulation",
    get_project_data_section("weather_simulation", {}) or {},
)

if current_settings:
    col_a, col_b, col_c = st.columns(3)

    with col_a:
        st.metric("Weather type", current_settings.get("weather_file_type", "Not set"))

    with col_b:
        st.metric("Run type", current_settings.get("run_type", "Not set"))

    with col_c:
        st.metric("Simulation hours", current_settings.get("simulation_hours", "Not set"))

    with st.expander("View saved weather settings", expanded=False):
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

from hem_extractors import extract_fabric_elements_from_hem, summarise_active_hem_case
from input_builder import build_generated_fabric_input
from model_runner import run_hem_model
from project_store import get_project_data_section, update_project_data
from results_parser import compare_summary_metrics, format_number


st.set_page_config(
    page_title="Building Fabric",
    layout="wide",
)

st.title("Building Fabric")

st.write(
    "Review and edit the fabric elements loaded from the active HEM case. "
    "You can modify the loaded rows, add new rows, prepare a HEM input file, "
    "and compare the result with the uploaded baseline case."
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
    st.error(
        "No active HEM input found. Go to the Home page and upload/load a HEM JSON first."
    )
    st.stop()


def load_fabric_defaults_into_state(force_reload: bool = False) -> None:
    already_loaded = st.session_state.get("fabric_defaults_loaded", False)

    if already_loaded and not force_reload:
        return

    project_rows = get_project_data_section("fabric_elements", None)

    if project_rows and not force_reload:
        st.session_state["fabric_elements"] = project_rows
    else:
        st.session_state["fabric_elements"] = extract_fabric_elements_from_hem(
            BASE_JSON_PATH,
            zone_name="zone 1",
        )

    st.session_state["fabric_defaults_loaded"] = True


def clear_fabric_state() -> None:
    for key in [
        "fabric_elements",
        "fabric_defaults_loaded",
        "generated_fabric_input_ready",
        "last_generated_fabric_json",
    ]:
        if key in st.session_state:
            del st.session_state[key]


load_fabric_defaults_into_state(force_reload=False)

st.header("1. Input source")

try:
    case_summary = summarise_active_hem_case(BASE_JSON_PATH)
    fabric_counts = case_summary["fabric_counts"]

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric("Opaque in uploaded case", fabric_counts["opaque"])

    with c2:
        st.metric("Transparent in uploaded case", fabric_counts["transparent"])

    with c3:
        st.metric("Ground in uploaded case", fabric_counts["ground"])

    with c4:
        st.metric("Party walls in uploaded case", fabric_counts["party_wall"])

except Exception as exc:
    st.warning("Could not summarise the active HEM fabric data.")
    with st.expander("Developer/debug: source summary error", expanded=False):
        st.exception(exc)

col_source_1, col_source_2 = st.columns(2)

with col_source_1:
    if st.button("Restore fabric rows from uploaded HEM JSON"):
        load_fabric_defaults_into_state(force_reload=True)
        update_project_data("fabric_elements", st.session_state["fabric_elements"])
        st.success("Fabric rows restored from uploaded HEM JSON.")
        st.rerun()

with col_source_2:
    if st.button("Clear fabric rows"):
        clear_fabric_state()
        update_project_data("fabric_elements", [])
        st.warning("Fabric rows cleared. The uploaded HEM case is still loaded.")
        st.rerun()

st.caption(
    "The editable rows below are derived from the uploaded HEM JSON. "
    "Editing them changes the generated HEM case, not the original uploaded file."
)

st.header("2. Fabric update mode")

fabric_update_mode = st.radio(
    "How should the generated HEM file handle existing fabric elements?",
    [
        "Replace all existing elements",
        "Add new UI elements to existing HEM elements",
    ],
    index=0,
)

if fabric_update_mode == "Replace all existing elements":
    st.info(
        "Recommended for editing an uploaded case: the generated file uses the edited table below as the fabric model."
    )
else:
    st.warning(
        "Add mode keeps the original HEM fabric elements and adds the rows below as extra elements. "
        "Use carefully to avoid duplicate fabric areas."
    )

st.header("3. Editable fabric rows")

fabric_rows = st.session_state.get("fabric_elements", [])

if not fabric_rows:
    st.info("No fabric rows loaded. Restore from uploaded HEM JSON or add rows manually.")
    df = pd.DataFrame()
else:
    df = pd.DataFrame(fabric_rows)

column_order = [
    "source_name",
    "name",
    "type",
    "area_m2",
    "u_value_w_m2k",
    "orientation",
    "pitch_degrees",
    "height_m",
    "width_m",
    "base_height_m",
    "solar_absorption_coeff",
    "g_value",
    "frame_factor",
    "openable_fraction",
    "areal_heat_capacity_kj_m2k",
    "mass_class",
    "perimeter_m",
    "psi_wall_floor_junc",
    "floor_type",
    "party_wall_cavity_type",
    "notes",
]

for column in column_order:
    if column not in df.columns:
        df[column] = ""

df = df[column_order]

edited_df = st.data_editor(
    df,
    use_container_width=True,
    hide_index=True,
    num_rows="dynamic",
    column_config={
        "type": st.column_config.SelectboxColumn(
            "Type",
            options=[
                "External wall",
                "Roof",
                "Ground floor",
                "Exposed floor",
                "Window",
                "Rooflight",
                "External door",
                "Party wall",
            ],
        ),
        "orientation": st.column_config.SelectboxColumn(
            "Orientation",
            options=[
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
        ),
        "mass_class": st.column_config.SelectboxColumn(
            "Mass class",
            options=["Lightweight", "Medium", "Heavy", "Very heavy", "Unknown"],
        ),
    },
)

if st.button("Save edited fabric rows"):
    edited_rows = edited_df.fillna("").to_dict(orient="records")
    st.session_state["fabric_elements"] = edited_rows
    update_project_data("fabric_elements", edited_rows)
    st.success("Edited fabric rows saved to the app project.")

st.header("4. Fabric input summary")

if edited_df.empty:
    st.info("No fabric rows available for summary.")
else:
    numeric_area = pd.to_numeric(edited_df["area_m2"], errors="coerce").fillna(0)
    numeric_u = pd.to_numeric(edited_df["u_value_w_m2k"], errors="coerce").fillna(0)

    total_area = numeric_area.sum()
    fabric_hlc = (numeric_area * numeric_u).sum()
    average_u = fabric_hlc / total_area if total_area > 0 else 0

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Editable fabric area", f"{total_area:.1f} m2")

    with col2:
        st.metric("Input HLC indicator", f"{fabric_hlc:.1f} W/K")

    with col3:
        st.metric("Area-weighted U-value", f"{average_u:.3f} W/m2K")

    chart_df = edited_df.copy()
    chart_df["hlc_w_k"] = numeric_area * numeric_u
    chart_df["name"] = chart_df["name"].astype(str)
    st.bar_chart(chart_df[["name", "hlc_w_k"]].set_index("name"))

st.header("5. Prepare and run HEM")

fabric_elements_for_run = edited_df.fillna("").to_dict(orient="records")

if not fabric_elements_for_run:
    st.warning("Add or restore fabric rows before preparing the HEM input.")
else:
    if st.button("Prepare HEM input from edited fabric rows"):
        try:
            st.session_state["fabric_elements"] = fabric_elements_for_run
            update_project_data("fabric_elements", fabric_elements_for_run)

            generated_input = build_generated_fabric_input(
                base_json_path=BASE_JSON_PATH,
                output_json_path=GENERATED_FABRIC_INPUT_PATH,
                fabric_elements=fabric_elements_for_run,
                zone_name="zone 1",
                update_mode=fabric_update_mode,
            )

            st.session_state["generated_fabric_input_ready"] = True
            st.session_state["last_generated_fabric_json"] = generated_input[
                "Zone"
            ]["zone 1"]["BuildingElement"]

            st.success("HEM input prepared successfully from edited fabric rows.")

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

                        space_heat = next(
                            item for item in comparison
                            if item["metric"] == "Space heat demand"
                        )
                        peak_elec = next(
                            item for item in comparison
                            if item["metric"] == "Peak electricity consumption"
                        )
                        delivered = next(
                            item for item in comparison
                            if item["metric"] == "Delivered energy total"
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

                        with st.expander("Detailed comparison table", expanded=False):
                            st.dataframe(
                                comparison,
                                use_container_width=True,
                                hide_index=True,
                            )

                    else:
                        st.warning(
                            "Base summary file was not found. Run the baseline case first if comparison is needed."
                        )

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

with st.expander("Developer/debug: view saved fabric rows", expanded=False):
    st.json(st.session_state.get("fabric_elements", []))
''',
)

print("Batch cleanup C complete.")