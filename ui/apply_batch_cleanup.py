from pathlib import Path


def write_file(path: str, content: str) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"Updated {file_path}")


write_file(
    "ui/utils/project_store.py",
    r'''
import json
from pathlib import Path

import streamlit as st


APP_PROJECT_VERSION = "0.1"

TEMP_DIR = Path("ui/temp")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

ACTIVE_HEM_INPUT_PATH = TEMP_DIR / "active_hem_input.json"
ACTIVE_APP_PROJECT_PATH = TEMP_DIR / "active_app_project.json"


def is_hem_input_json(data: dict) -> bool:
    """Detect whether a JSON object looks like an official HEM input file."""
    if not isinstance(data, dict):
        return False

    hem_keys = {
        "metadata",
        "SimulationTime",
        "ExternalConditions",
        "Zone",
        "InfiltrationVentilation",
        "EnergySupply",
        "Control",
        "HotWaterSource",
        "HotWaterDemand",
        "SpaceHeatSystem",
    }

    matched_keys = hem_keys.intersection(set(data.keys()))
    return len(matched_keys) >= 2 and "Zone" in data


def is_app_project_json(data: dict) -> bool:
    """Detect whether a JSON object looks like a saved app project file."""
    if not isinstance(data, dict):
        return False

    return "app_project_version" in data and "project_data" in data


def create_blank_project() -> dict:
    """Create a blank app project structure."""
    return {
        "app_project_version": APP_PROJECT_VERSION,
        "project_type": "blank_app_project",
        "active_hem_source": None,
        "project_data": {
            "project_setup": {},
            "weather_simulation": {},
            "fabric_elements": [],
            "ventilation": {},
            "thermal_bridges": [],
            "heating_hot_water": {},
            "renewables_battery": {},
        },
    }


def create_app_project_from_hem_input(hem_data: dict, source_name: str) -> dict:
    """Create an app project wrapper around an uploaded HEM input file."""
    return {
        "app_project_version": APP_PROJECT_VERSION,
        "project_type": "hem_input_template",
        "active_hem_source": source_name,
        "project_data": {
            "project_setup": {},
            "weather_simulation": {},
            "fabric_elements": [],
            "ventilation": {},
            "thermal_bridges": [],
            "heating_hot_water": {},
            "renewables_battery": {},
        },
        "hem_input": hem_data,
    }


def load_uploaded_json(uploaded_file) -> dict:
    """Load uploaded JSON from Streamlit file uploader."""
    uploaded_file.seek(0)
    raw_bytes = uploaded_file.read()

    if isinstance(raw_bytes, bytes):
        raw_text = raw_bytes.decode("utf-8-sig")
    else:
        raw_text = raw_bytes

    return json.loads(raw_text)


def set_active_project(project_data: dict) -> None:
    """Set active app project in Streamlit session state and save temp file."""
    st.session_state["active_app_project"] = project_data

    with open(ACTIVE_APP_PROJECT_PATH, "w", encoding="utf-8") as f:
        json.dump(project_data, f, indent=2)

    if "hem_input" in project_data:
        st.session_state["active_hem_input"] = project_data["hem_input"]

        with open(ACTIVE_HEM_INPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(project_data["hem_input"], f, indent=2)


def load_json_as_project(uploaded_file, source_name: str) -> tuple[str, dict]:
    """Load either HEM JSON or saved app project JSON."""
    data = load_uploaded_json(uploaded_file)

    if is_app_project_json(data):
        set_active_project(data)
        return "app_project", data

    if is_hem_input_json(data):
        project_data = create_app_project_from_hem_input(data, source_name)
        set_active_project(project_data)
        return "hem_input", project_data

    detected_keys = list(data.keys())[:20] if isinstance(data, dict) else []

    raise ValueError(
        "Uploaded JSON was not recognised as either a HEM input JSON "
        "or a saved app project JSON. "
        f"Detected top-level keys: {detected_keys}"
    )


def start_blank_project() -> dict:
    """Start a blank app project."""
    project_data = create_blank_project()
    set_active_project(project_data)
    return project_data


def clear_active_project() -> None:
    """Clear active project from session state and temp files."""
    keys_to_clear = [
        "active_app_project",
        "active_hem_input",
        "project_setup",
        "weather_simulation",
        "fabric_elements",
        "hem_airtightness_exposure",
        "hem_background_vents",
        "hem_mechanical_ventilation",
        "ventilation_defaults_loaded",
        "generated_ventilation_input_ready",
        "last_generated_ventilation_json",
        "thermal_bridges",
        "generated_fabric_input_ready",
    ]

    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]

    for path in [ACTIVE_HEM_INPUT_PATH, ACTIVE_APP_PROJECT_PATH]:
        if path.exists():
            path.unlink()


def get_active_project() -> dict | None:
    """Return active app project if available."""
    return st.session_state.get("active_app_project")


def get_active_hem_input() -> dict | None:
    """Return active HEM input if available."""
    return st.session_state.get("active_hem_input")


def update_project_data(section_name: str, section_data) -> None:
    """Update a user-friendly section inside the active app project."""
    project = get_active_project()

    if project is None:
        project = create_blank_project()

    project.setdefault("project_data", {})
    project["project_data"][section_name] = section_data

    set_active_project(project)


def get_project_data_section(section_name: str, default=None):
    """Read a user-friendly section from the active app project."""
    project = get_active_project()

    if project is None:
        return default

    return project.get("project_data", {}).get(section_name, default)


def save_current_project_to_file(output_path: Path) -> Path:
    """Save the active app project to a JSON file."""
    project_data = get_active_project()

    if project_data is None:
        raise ValueError("No active project to save.")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(project_data, f, indent=2)

    return output_path
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
    "ui/app.py",
    r'''
import json
import sys
from pathlib import Path

import streamlit as st

CURRENT_DIR = Path(__file__).resolve().parent
UTILS_DIR = CURRENT_DIR / "utils"
sys.path.append(str(UTILS_DIR))

from hem_extractors import summarise_active_hem_case
from project_store import (
    ACTIVE_HEM_INPUT_PATH,
    clear_active_project,
    get_active_project,
    load_json_as_project,
    save_current_project_to_file,
    start_blank_project,
)


st.set_page_config(
    page_title="Home Energy Model Desktop App",
    layout="wide",
)

st.title("Home Energy Model Desktop App")

st.write(
    "Upload a HEM JSON file or a saved app project JSON, then use the input tabs "
    "to review, edit, prepare and run HEM cases."
)

st.header("1. Load or start project")

col_load, col_blank = st.columns(2)

with col_load:
    st.subheader("Upload / load JSON")

    uploaded_file = st.file_uploader(
        "Upload HEM input JSON or saved app project JSON",
        type=["json"],
    )

    if uploaded_file is not None:
        if st.button("Load uploaded JSON"):
            try:
                file_type, project_data = load_json_as_project(
                    uploaded_file,
                    source_name=uploaded_file.name,
                )

                if file_type == "hem_input":
                    st.success("Loaded uploaded file as a HEM input template.")
                else:
                    st.success("Loaded uploaded file as a saved app project.")

            except Exception as exc:
                st.error("Could not load uploaded JSON.")
                st.exception(exc)

with col_blank:
    st.subheader("Start manually")

    st.write(
        "Start a blank app project if you want to enter inputs manually rather "
        "than using an existing HEM case as the starting point."
    )

    if st.button("Start blank project"):
        start_blank_project()
        st.success("Blank project started.")


st.header("2. Active project status")

active_project = get_active_project()

if active_project is None:
    st.warning("No active project loaded yet.")
else:
    project_type = active_project.get("project_type", "unknown")
    hem_source = active_project.get("active_hem_source")
    has_hem_input = "hem_input" in active_project

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Project type", project_type)

    with col2:
        st.metric("Loaded source", hem_source or "Manual / blank")

    with col3:
        st.metric("HEM template loaded", "Yes" if has_hem_input else "No")

    if has_hem_input and ACTIVE_HEM_INPUT_PATH.exists():
        summary = summarise_active_hem_case(ACTIVE_HEM_INPUT_PATH)

        st.subheader("Loaded HEM case summary")

        s1, s2, s3, s4 = st.columns(4)

        with s1:
            st.metric("Zones", summary["zone_count"])

        with s2:
            st.metric("Opaque elements", summary["fabric_counts"]["opaque"])

        with s3:
            st.metric("Windows / transparent", summary["fabric_counts"]["transparent"])

        with s4:
            st.metric("Background vents", summary["background_vent_count"])

        detected_sections = [
            section
            for section in [
                "SimulationTime",
                "ExternalConditions",
                "Zone",
                "InfiltrationVentilation",
                "EnergySupply",
                "SpaceHeatSystem",
                "HotWaterSource",
                "HotWaterDemand",
            ]
            if section in active_project["hem_input"]
        ]

        st.info(
            "HEM input loaded. Detected sections: "
            + ", ".join(detected_sections)
        )

    with st.expander("Developer/debug: view active project JSON", expanded=False):
        st.json(active_project)


st.header("3. Save or clear project")

if active_project is not None:
    project_json = json.dumps(active_project, indent=2)

    st.download_button(
        label="Download current app project JSON",
        data=project_json,
        file_name="saved_app_project.json",
        mime="application/json",
    )

    if st.button("Save current project locally"):
        try:
            output_path = save_current_project_to_file(
                Path("ui/temp/saved_app_project.json")
            )
            st.success(f"Project saved locally to: {output_path}")
        except Exception as exc:
            st.error("Could not save project.")
            st.exception(exc)

    if st.button("Clear active project"):
        clear_active_project()
        st.success("Active project cleared.")
        st.rerun()
''',
)


write_file(
    "ui/pages/5_Infiltration_Ventilation.py",
    r'''
import sys
from pathlib import Path

import streamlit as st

CURRENT_DIR = Path(__file__).resolve().parent
UI_DIR = CURRENT_DIR.parent
UTILS_DIR = UI_DIR / "utils"
sys.path.append(str(UTILS_DIR))

from hem_extractors import extract_ventilation_defaults_from_hem
from input_builder import build_generated_hem_input
from model_runner import run_hem_model
from project_store import update_project_data
from results_parser import compare_summary_metrics, format_number


st.set_page_config(
    page_title="Infiltration & Ventilation",
    layout="wide",
)

st.title("Infiltration & Ventilation")

st.write(
    "Review and edit the ventilation inputs loaded from the active HEM case. "
    "The app prepares a HEM input file from these values, runs HEM, and compares "
    "the result with the uploaded baseline case."
)

BASE_JSON_PATH = Path("ui/temp/active_hem_input.json")
WEATHER_FILE = Path("test/e2e/demo_files/London_weather_CIBSE_format.csv")
GENERATED_INPUT_PATH = Path("ui/temp/generated_ventilation_case.json")

SUMMARY_PATH = Path(
    "ui/temp/generated_ventilation_case__results/"
    "generated_ventilation_case__core__results_summary.csv"
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


def load_ventilation_defaults_into_state(force_reload: bool = False) -> None:
    already_loaded = st.session_state.get("ventilation_defaults_loaded", False)

    if already_loaded and not force_reload:
        return

    defaults = extract_ventilation_defaults_from_hem(BASE_JSON_PATH)

    st.session_state["hem_airtightness_exposure"] = defaults[
        "airtightness_exposure"
    ]
    st.session_state["hem_background_vents"] = defaults["background_vents"]
    st.session_state["hem_mechanical_ventilation"] = defaults[
        "mechanical_ventilation"
    ]

    st.session_state["ventilation_defaults_loaded"] = True


def clear_ventilation_state() -> None:
    for key in [
        "hem_airtightness_exposure",
        "hem_background_vents",
        "hem_mechanical_ventilation",
        "generated_ventilation_input_ready",
        "ventilation_defaults_loaded",
        "last_generated_ventilation_json",
    ]:
        if key in st.session_state:
            del st.session_state[key]


def save_ventilation_to_project() -> None:
    update_project_data(
        "ventilation",
        {
            "airtightness_exposure": st.session_state.get(
                "hem_airtightness_exposure", {}
            ),
            "background_vents": st.session_state.get("hem_background_vents", []),
            "mechanical_ventilation": st.session_state.get(
                "hem_mechanical_ventilation", {}
            ),
        },
    )


load_ventilation_defaults_into_state(force_reload=False)

st.header("1. Input source")

col_source_1, col_source_2, col_source_3 = st.columns(3)

with col_source_1:
    st.success("Ventilation values loaded from the active HEM case.")

with col_source_2:
    if st.button("Restore from uploaded HEM JSON"):
        load_ventilation_defaults_into_state(force_reload=True)
        st.success("Ventilation values restored from uploaded HEM JSON.")
        st.rerun()

with col_source_3:
    if st.button("Clear this ventilation form"):
        clear_ventilation_state()
        st.warning(
            "Ventilation form values cleared. The uploaded HEM case is still loaded."
        )
        st.rerun()

st.caption(
    "Restore brings back the values from the uploaded HEM JSON. "
    "Clear removes only this page's form values so you can enter manually."
)

airtightness_defaults = st.session_state.get(
    "hem_airtightness_exposure",
    {
        "q50_m3_h_m2": 1.2,
        "test_pressure_pa": 50,
        "envelope_area_m2": 220,
        "ventilation_zone_height_m": 6,
        "zone_base_height_m": 2.5,
        "altitude_m": 30,
        "shield_class": "Normal / suburban",
        "terrain_class": "Open country",
        "cross_ventilation": True,
    },
)

mechanical_defaults = st.session_state.get(
    "hem_mechanical_ventilation",
    {
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
    },
)

if "hem_background_vents" not in st.session_state:
    st.session_state["hem_background_vents"] = []

st.header("2. Leakage and exposure")

with st.form("hem_airtightness_form"):
    col1, col2, col3 = st.columns(3)

    with col1:
        q50 = st.number_input(
            "q50 test result (m3/h.m2 at 50 Pa)",
            min_value=0.01,
            value=float(airtightness_defaults["q50_m3_h_m2"]),
            step=0.10,
            format="%.2f",
        )

        test_pressure = st.number_input(
            "Test pressure (Pa)",
            min_value=1.0,
            value=float(airtightness_defaults["test_pressure_pa"]),
            step=5.0,
        )

    with col2:
        envelope_area = st.number_input(
            "Envelope area (m2)",
            min_value=1.0,
            value=float(airtightness_defaults["envelope_area_m2"]),
            step=1.0,
        )

        ventilation_zone_height = st.number_input(
            "Ventilation zone height (m)",
            min_value=0.1,
            value=float(airtightness_defaults["ventilation_zone_height_m"]),
            step=0.5,
        )

    with col3:
        ventilation_zone_base_height = st.number_input(
            "Ventilation zone base height (m)",
            min_value=0.0,
            value=float(airtightness_defaults["zone_base_height_m"]),
            step=0.5,
        )

        altitude = st.number_input(
            "Altitude (m)",
            min_value=0.0,
            value=float(airtightness_defaults["altitude_m"]),
            step=5.0,
        )

    st.subheader("Exposure")

    shield_options = [
        "Open / exposed",
        "Normal / suburban",
        "Shielded / dense urban",
    ]

    terrain_options = [
        "Open water",
        "Open country",
        "Suburban",
        "Urban",
    ]

    col4, col5, col6 = st.columns(3)

    with col4:
        shield_class = st.selectbox(
            "Shield class",
            shield_options,
            index=shield_options.index(
                airtightness_defaults.get("shield_class", "Normal / suburban")
            ),
        )

    with col5:
        terrain_class = st.selectbox(
            "Terrain class",
            terrain_options,
            index=terrain_options.index(
                airtightness_defaults.get("terrain_class", "Open country")
            ),
        )

    with col6:
        cross_ventilation = st.checkbox(
            "Cross ventilation possible",
            value=bool(airtightness_defaults["cross_ventilation"]),
        )

    save_airtightness = st.form_submit_button("Save leakage and exposure values")

if save_airtightness:
    st.session_state["hem_airtightness_exposure"] = {
        "q50_m3_h_m2": q50,
        "test_pressure_pa": test_pressure,
        "envelope_area_m2": envelope_area,
        "ventilation_zone_height_m": ventilation_zone_height,
        "zone_base_height_m": ventilation_zone_base_height,
        "altitude_m": altitude,
        "shield_class": shield_class,
        "terrain_class": terrain_class,
        "cross_ventilation": cross_ventilation,
    }

    save_ventilation_to_project()
    st.success("Leakage and exposure values saved.")

st.header("3. Background vents")

with st.form("hem_background_vent_form"):
    vent_count = len(st.session_state["hem_background_vents"])
    default_vent_name = f"vent{vent_count + 1}"

    col1, col2, col3 = st.columns(3)

    with col1:
        vent_name = st.text_input("Vent name", default_vent_name)
        area_cm2 = st.number_input(
            "Equivalent area (cm2)",
            min_value=0.01,
            value=100.0,
            step=10.0,
        )

    with col2:
        pressure_difference_ref = st.number_input(
            "Reference pressure difference (Pa)",
            min_value=0.1,
            value=20.0,
            step=1.0,
        )

        mid_height = st.number_input(
            "Mid-height air-flow path (m)",
            min_value=0.01,
            value=1.5,
            step=0.1,
        )

    with col3:
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
            ],
            index=4,
        )

        pitch = st.number_input(
            "Pitch (degrees)",
            min_value=0.0,
            max_value=180.0,
            value=60.0,
            step=1.0,
        )

    add_vent = st.form_submit_button("Add background vent")

if add_vent:
    st.session_state["hem_background_vents"].append(
        {
            "name": vent_name,
            "area_cm2": area_cm2,
            "pressure_difference_ref": pressure_difference_ref,
            "mid_height_m": mid_height,
            "orientation": orientation,
            "pitch": pitch,
        }
    )

    save_ventilation_to_project()
    st.success(f"Added background vent: {vent_name}")

if st.session_state["hem_background_vents"]:
    st.subheader("Background vents")

    st.dataframe(
        st.session_state["hem_background_vents"],
        use_container_width=True,
        hide_index=True,
    )

    if st.button("Clear background vents"):
        st.session_state["hem_background_vents"] = []
        save_ventilation_to_project()
        st.rerun()

st.header("4. Mechanical ventilation")

with st.form("hem_mechanical_ventilation_form"):
    vent_type_options = [
        "None",
        "Intermittent MEV",
        "Centralised continuous MEV",
        "Decentralised continuous MEV",
        "MVHR",
        "Positive input ventilation",
    ]

    col1, col2, col3 = st.columns(3)

    with col1:
        vent_type = st.selectbox(
            "Mechanical ventilation type",
            vent_type_options,
            index=vent_type_options.index(
                mechanical_defaults.get("vent_type", "None")
            ),
        )

        energy_supply = st.selectbox("Fan energy supply", ["mains elec"], index=0)

    with col2:
        design_flow_l_s = st.number_input(
            "Design outdoor air-flow rate (l/s)",
            min_value=0.0,
            value=float(mechanical_defaults["design_flow_l_s"]),
            step=1.0,
            help="The app converts this to m3/h when preparing the HEM input.",
        )

        sfp = st.number_input(
            "Specific fan power, SFP (W/l/s)",
            min_value=0.01,
            value=float(mechanical_defaults["sfp_w_l_s"]),
            step=0.05,
            format="%.2f",
        )

    with col3:
        sfp_in_use_factor = st.number_input(
            "SFP in-use factor",
            min_value=1.0,
            value=float(mechanical_defaults["sfp_in_use_factor"]),
            step=0.05,
            format="%.2f",
        )

        mvhr_efficiency_percent = st.number_input(
            "MVHR heat recovery efficiency (%)",
            min_value=0.0,
            max_value=100.0,
            value=float(mechanical_defaults["mvhr_efficiency_percent"]),
            step=1.0,
        )

    st.subheader("Mechanical ventilation position")

    col4, col5, col6 = st.columns(3)

    with col4:
        mvhr_location = st.selectbox(
            "MVHR location",
            ["inside", "outside"],
            index=0
            if mechanical_defaults.get("mvhr_location", "inside") == "inside"
            else 1,
        )

        intake_options = ["North", "East", "South", "West", "Roof / horizontal"]

        intake_orientation = st.selectbox(
            "Intake orientation",
            intake_options,
            index=intake_options.index(
                mechanical_defaults.get("intake_orientation", "North")
            )
            if mechanical_defaults.get("intake_orientation", "North")
            in intake_options
            else 0,
        )

    with col5:
        intake_pitch = st.number_input(
            "Intake pitch (degrees)",
            min_value=0.0,
            max_value=180.0,
            value=float(mechanical_defaults["intake_pitch"]),
            step=1.0,
        )

        intake_mid_height = st.number_input(
            "Intake mid-height (m)",
            min_value=0.01,
            value=float(mechanical_defaults["intake_mid_height_m"]),
            step=0.1,
        )

    with col6:
        exhaust_options = ["North", "East", "South", "West", "Roof / horizontal"]

        exhaust_orientation = st.selectbox(
            "Exhaust orientation",
            exhaust_options,
            index=exhaust_options.index(
                mechanical_defaults.get("exhaust_orientation", "South")
            )
            if mechanical_defaults.get("exhaust_orientation", "South")
            in exhaust_options
            else 2,
        )

        exhaust_pitch = st.number_input(
            "Exhaust pitch (degrees)",
            min_value=0.0,
            max_value=180.0,
            value=float(mechanical_defaults["exhaust_pitch"]),
            step=1.0,
        )

        exhaust_mid_height = st.number_input(
            "Exhaust mid-height (m)",
            min_value=0.01,
            value=float(mechanical_defaults["exhaust_mid_height_m"]),
            step=0.1,
        )

    save_mech = st.form_submit_button("Save mechanical ventilation values")

if save_mech:
    st.session_state["hem_mechanical_ventilation"] = {
        "vent_type": vent_type,
        "energy_supply": energy_supply,
        "design_flow_l_s": design_flow_l_s,
        "sfp_w_l_s": sfp,
        "sfp_in_use_factor": sfp_in_use_factor,
        "mvhr_efficiency_percent": mvhr_efficiency_percent,
        "mvhr_location": mvhr_location,
        "intake_orientation": intake_orientation,
        "intake_pitch": intake_pitch,
        "intake_mid_height_m": intake_mid_height,
        "exhaust_orientation": exhaust_orientation,
        "exhaust_pitch": exhaust_pitch,
        "exhaust_mid_height_m": exhaust_mid_height,
    }

    save_ventilation_to_project()
    st.success("Mechanical ventilation values saved.")

st.header("5. Prepare and run HEM")

can_prepare = "hem_airtightness_exposure" in st.session_state

if not can_prepare:
    st.warning("Save leakage and exposure values before preparing the HEM input.")
else:
    if st.button("Prepare HEM input from these ventilation values"):
        generated_input = build_generated_hem_input(
            base_json_path=BASE_JSON_PATH,
            output_json_path=GENERATED_INPUT_PATH,
            airtightness_exposure=st.session_state["hem_airtightness_exposure"],
            background_vents=st.session_state["hem_background_vents"],
            mechanical_ventilation=st.session_state.get("hem_mechanical_ventilation"),
        )

        st.session_state["generated_ventilation_input_ready"] = True
        st.session_state["last_generated_ventilation_json"] = generated_input[
            "InfiltrationVentilation"
        ]

        st.success("HEM input prepared successfully from these ventilation values.")

    if st.session_state.get("generated_ventilation_input_ready"):
        st.info("Prepared case is ready. You can now run HEM and compare results.")

        if st.button("Run HEM and compare with uploaded case"):
            with st.spinner("Running HEM..."):
                result = run_hem_model(GENERATED_INPUT_PATH, WEATHER_FILE)

            if result.returncode == 0:
                st.success("HEM run completed successfully.")

                if SUMMARY_PATH.exists():
                    summary_text = SUMMARY_PATH.read_text(encoding="utf-8")

                    st.subheader("Results comparison")

                    if BASE_SUMMARY_PATH.exists():
                        comparison = compare_summary_metrics(
                            BASE_SUMMARY_PATH,
                            SUMMARY_PATH,
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
                            "Base summary file was not found. "
                            "Run the baseline case first if comparison is needed."
                        )

                    with st.expander("View full HEM summary output", expanded=False):
                        st.text(summary_text)

                    st.download_button(
                        "Download HEM summary CSV",
                        data=summary_text,
                        file_name="generated_ventilation_case__core__results_summary.csv",
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

with st.expander("Advanced: view generated HEM ventilation JSON", expanded=False):
    generated_json = st.session_state.get("last_generated_ventilation_json")

    if generated_json is None:
        st.write("No generated ventilation JSON has been prepared yet.")
    else:
        st.json(generated_json)

with st.expander("Developer/debug: view saved ventilation state", expanded=False):
    state_preview = {
        "airtightness_exposure": st.session_state.get("hem_airtightness_exposure"),
        "background_vents": st.session_state.get("hem_background_vents"),
        "mechanical_ventilation": st.session_state.get("hem_mechanical_ventilation"),
    }

    st.json(state_preview)
''',
)

print("Batch cleanup A complete.")