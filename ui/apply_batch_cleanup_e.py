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


def is_valid_fabric_row(row: dict) -> bool:
    """Return True if a fabric row has enough data to be written to HEM."""
    if not isinstance(row, dict):
        return False

    element_type = str(row.get("type", "")).strip()
    area = row.get("area_m2", "")
    u_value = row.get("u_value_w_m2k", "")

    if not element_type:
        return False

    try:
        area_float = float(area)
        u_float = float(u_value)
    except (TypeError, ValueError):
        return False

    return area_float > 0 and u_float > 0


def clean_fabric_rows(fabric_elements: list) -> list[dict]:
    """Remove blank rows left by the editable table before building HEM."""
    clean_rows = []

    for row in fabric_elements or []:
        if is_valid_fabric_row(row):
            clean_rows.append(row)

    return clean_rows


def apply_fabric_to_case(
    hem_input: dict,
    fabric_elements: list,
    update_mode: str = "Replace all existing elements",
    zone_name: str = "zone 1",
) -> dict:
    """Apply saved fabric rows to a HEM input dictionary."""
    fabric_elements = clean_fabric_rows(fabric_elements)

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

    fabric_elements = clean_fabric_rows(
        project_sections.get("fabric_elements", [])
    )

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
from input_builder import build_hem_infiltration_ventilation
from project_store import update_project_data


st.set_page_config(
    page_title="Infiltration & Ventilation",
    layout="wide",
)

st.title("Infiltration & Ventilation")

st.write(
    "Review and edit the ventilation inputs loaded from the active HEM case. "
    "Save the values here, then use the central Run HEM / Results tab to build "
    "and run the full project case."
)

BASE_JSON_PATH = Path("ui/temp/active_hem_input.json")

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
        "ventilation_defaults_loaded",
        "last_generated_ventilation_json",
    ]:
        if key in st.session_state:
            del st.session_state[key]


def current_ventilation_project_data() -> dict:
    return {
        "airtightness_exposure": st.session_state.get(
            "hem_airtightness_exposure", {}
        ),
        "background_vents": st.session_state.get("hem_background_vents", []),
        "mechanical_ventilation": st.session_state.get(
            "hem_mechanical_ventilation", {}
        ),
    }


def save_ventilation_to_project() -> None:
    update_project_data("ventilation", current_ventilation_project_data())


load_ventilation_defaults_into_state(force_reload=False)

st.header("1. Input source")

col_source_1, col_source_2, col_source_3 = st.columns(3)

with col_source_1:
    st.success("Ventilation values loaded from the active HEM case.")

with col_source_2:
    if st.button("Restore from uploaded HEM JSON"):
        load_ventilation_defaults_into_state(force_reload=True)
        save_ventilation_to_project()
        st.success("Ventilation values restored from uploaded HEM JSON.")
        st.rerun()

with col_source_3:
    if st.button("Clear this ventilation form"):
        clear_ventilation_state()
        update_project_data("ventilation", {})
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
    st.success("Leakage and exposure values saved to project.")

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
    st.success("Mechanical ventilation values saved to project.")

st.header("5. Project save status")

if st.button("Save all ventilation values to project"):
    save_ventilation_to_project()
    st.success("All ventilation values saved to the app project.")

if st.session_state.get("hem_airtightness_exposure"):
    st.success("Ventilation data is available for the central Run HEM / Results page.")
else:
    st.info("No ventilation data has been saved yet.")

with st.expander("Advanced: preview HEM ventilation section", expanded=False):
    try:
        preview = build_hem_infiltration_ventilation(
            airtightness_exposure=st.session_state.get(
                "hem_airtightness_exposure", {}
            ),
            background_vents=st.session_state.get("hem_background_vents", []),
            mechanical_ventilation=st.session_state.get(
                "hem_mechanical_ventilation"
            ),
        )
        st.json(preview)
    except Exception:
        st.write("Save leakage and exposure values to preview the HEM ventilation section.")

with st.expander("Developer/debug: view saved ventilation state", expanded=False):
    st.json(current_ventilation_project_data())
''',
)


print("Batch cleanup E complete.")