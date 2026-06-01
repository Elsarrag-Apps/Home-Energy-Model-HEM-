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
from copy import deepcopy
from pathlib import Path

from input_builder import (
    ORIENTATION_TO_DEGREES,
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


def safe_float(value, default=None):
    try:
        if value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_positive_float(value, default=None):
    number = safe_float(value, default)
    if number is None:
        return default
    if number <= 0:
        return default
    return number


def u_value_to_resistance(u_value):
    u_value = safe_positive_float(u_value)
    if u_value is None:
        return None
    return 1.0 / u_value


def is_valid_fabric_row(row: dict) -> bool:
    if not isinstance(row, dict):
        return False

    element_type = str(row.get("type", "")).strip()
    area = safe_positive_float(row.get("area_m2"))
    u_value = safe_positive_float(row.get("u_value_w_m2k"))

    return bool(element_type) and area is not None and u_value is not None


def clean_fabric_rows(fabric_elements: list) -> list[dict]:
    clean_rows = []

    for row in fabric_elements or []:
        if is_valid_fabric_row(row):
            clean_rows.append(row)

    return clean_rows


def update_existing_hem_element(existing_element: dict, row: dict) -> dict:
    element = deepcopy(existing_element)
    hem_type = element.get("type")

    area = safe_positive_float(row.get("area_m2"))
    u_value = safe_positive_float(row.get("u_value_w_m2k"))
    resistance = u_value_to_resistance(u_value)

    pitch = safe_float(row.get("pitch_degrees"))
    orientation = row.get("orientation")

    height = safe_positive_float(row.get("height_m"))
    width = safe_positive_float(row.get("width_m"))
    base_height = safe_float(row.get("base_height_m"))
    areal_heat_capacity = safe_positive_float(
        row.get("areal_heat_capacity_kj_m2k")
    )

    if area is not None:
        element["area"] = area
        if hem_type == "BuildingElementGround":
            element["total_area"] = area

    if pitch is not None:
        element["pitch"] = pitch

    if orientation and orientation in ORIENTATION_TO_DEGREES and orientation != "Not applicable":
        element["orientation360"] = ORIENTATION_TO_DEGREES[orientation]

    if base_height is not None and "base_height" in element:
        element["base_height"] = base_height

    if height is not None and "height" in element:
        element["height"] = height

    if width is not None and "width" in element:
        element["width"] = width

    if areal_heat_capacity is not None:
        element["areal_heat_capacity"] = areal_heat_capacity * 1000

    if hem_type == "BuildingElementOpaque":
        if resistance is not None:
            element["thermal_resistance_construction"] = resistance

        solar_absorption = safe_float(row.get("solar_absorption_coeff"))
        if solar_absorption is not None:
            element["solar_absorption_coeff"] = solar_absorption

    elif hem_type == "BuildingElementTransparent":
        if resistance is not None:
            element["thermal_resistance_construction"] = resistance

        g_value = safe_float(row.get("g_value"))
        if g_value is not None:
            element["g_value"] = g_value

        frame_factor = safe_float(row.get("frame_factor"))
        if frame_factor is not None:
            element["frame_area_fraction"] = max(0.0, min(1.0, 1.0 - frame_factor))

        free_area_height = safe_float(row.get("free_area_height_m"))
        if free_area_height is not None:
            element["free_area_height"] = free_area_height

        openable_fraction = safe_float(row.get("openable_fraction"), 0.0)
        if area is not None and openable_fraction is not None:
            element["max_window_open_area"] = area * openable_fraction

        if "mid_height" in element and "window_part_list" in element:
            mid_height = element.get("mid_height")
            if mid_height is not None:
                element["window_part_list"] = [
                    {"mid_height_air_flow_path": mid_height}
                ]

    elif hem_type == "BuildingElementPartyWall":
        if resistance is not None:
            element["thermal_resistance_construction"] = resistance

        cavity_type = str(row.get("party_wall_cavity_type", "")).strip()
        if cavity_type:
            element["party_wall_cavity_type"] = cavity_type

    elif hem_type == "BuildingElementGround":
        if u_value is not None:
            element["u_value"] = u_value

        perimeter = safe_float(row.get("perimeter_m"))
        if perimeter is not None:
            element["perimeter"] = perimeter

        wall_thickness = safe_float(row.get("thickness_walls_m"))
        if wall_thickness is not None:
            element["thickness_walls"] = wall_thickness

        psi = safe_float(row.get("psi_wall_floor_junc"))
        if psi is not None:
            element["psi_wall_floor_junc"] = psi

        floor_type = str(row.get("floor_type", "")).strip()
        if floor_type:
            element["floor_type"] = floor_type

    return element


def apply_fabric_to_case(
    hem_input: dict,
    fabric_elements: list,
    update_mode: str = "Replace all existing elements",
    zone_name: str = "zone 1",
) -> dict:
    fabric_elements = clean_fabric_rows(fabric_elements)

    if not fabric_elements:
        return hem_input

    if "Zone" not in hem_input:
        raise KeyError("HEM input does not contain a Zone section.")

    if zone_name not in hem_input["Zone"]:
        zone_name = next(iter(hem_input["Zone"].keys()))

    existing_elements = hem_input["Zone"][zone_name].get("BuildingElement", {})

    updated_elements = {}

    if update_mode == "Add new UI elements to existing HEM elements":
        updated_elements = deepcopy(existing_elements)

    for row in fabric_elements:
        source_name = str(row.get("source_name", "")).strip()

        if source_name and source_name in existing_elements:
            updated_elements[source_name] = update_existing_hem_element(
                existing_elements[source_name],
                row,
            )
        else:
            new_element = build_hem_building_elements(
                [row],
                existing_elements=updated_elements,
            )
            updated_elements.update(new_element)

    if not updated_elements:
        return hem_input

    hem_input["Zone"][zone_name]["BuildingElement"] = updated_elements

    floor_areas = [
        safe_float(element.get("area_m2"), 0.0)
        for element in fabric_elements
        if element.get("type") == "Ground floor"
    ]

    floor_areas = [area for area in floor_areas if area and area > 0]

    if floor_areas and update_mode == "Replace all existing elements":
        floor_area = sum(floor_areas)
        hem_input["Zone"][zone_name]["area"] = floor_area
        hem_input["Zone"][zone_name]["volume"] = floor_area * 2.7

    return hem_input


def apply_ventilation_to_case(
    hem_input: dict,
    ventilation_data: dict,
) -> dict:
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


def clean_thermal_bridge_rows(thermal_bridges: list) -> list[dict]:
    clean_rows = []

    for row in thermal_bridges or []:
        if not isinstance(row, dict):
            continue

        name = str(row.get("name", "")).strip()
        hlc = safe_float(row.get("thermal_bridge_hlc_w_k"))

        if name and hlc is not None:
            clean_rows.append(row)

    return clean_rows


def apply_thermal_bridges_to_case(
    hem_input: dict,
    thermal_bridges: list,
    zone_name: str = "zone 1",
) -> dict:
    """Apply app thermal bridge inputs to HEM Zone -> ThermalBridging.

    First implementation writes equivalent HLC entries. This avoids losing the
    user-entered bridge heat-loss contribution while keeping the structure simple.
    """
    thermal_bridges = clean_thermal_bridge_rows(thermal_bridges)

    if not thermal_bridges:
        return hem_input

    if "Zone" not in hem_input:
        raise KeyError("HEM input does not contain a Zone section.")

    if zone_name not in hem_input["Zone"]:
        zone_name = next(iter(hem_input["Zone"].keys()))

    thermal_bridging = {}

    for index, bridge in enumerate(thermal_bridges, start=1):
        hlc = safe_float(bridge.get("thermal_bridge_hlc_w_k"), 0.0)
        name = str(bridge.get("name", f"thermal_bridge_{index}")).strip()

        thermal_bridging[f"tb_{index}"] = {
            "name": name,
            "heat_transfer_coeff": hlc,
            "source": bridge.get("source", "User-defined"),
            "notes": bridge.get("notes", ""),
        }

    hem_input["Zone"][zone_name]["ThermalBridging"] = thermal_bridging

    return hem_input


def build_full_project_case(
    base_json_path: Path,
    output_json_path: Path,
    project_data: dict,
) -> dict:
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
    thermal_bridges = project_sections.get("thermal_bridges", [])

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

    hem_input = apply_thermal_bridges_to_case(
        hem_input=hem_input,
        thermal_bridges=thermal_bridges,
        zone_name="zone 1",
    )

    save_json(output_json_path, hem_input)

    return hem_input
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
from project_store import get_project_data_section, update_project_data


st.set_page_config(
    page_title="Building Fabric",
    layout="wide",
)

st.title("Building Fabric")

st.write(
    "Review and edit the fabric elements loaded from the active HEM case. "
    "Save the edited rows here, then use the central Run HEM / Results tab to "
    "build and run the full project case."
)

BASE_JSON_PATH = Path("ui/temp/active_hem_input.json")

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

update_project_data("fabric_update_mode", fabric_update_mode)

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
    update_project_data("fabric_update_mode", fabric_update_mode)
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

st.header("5. Project save status")

if st.button("Save all fabric values to project"):
    edited_rows = edited_df.fillna("").to_dict(orient="records")
    st.session_state["fabric_elements"] = edited_rows
    update_project_data("fabric_elements", edited_rows)
    update_project_data("fabric_update_mode", fabric_update_mode)
    st.success("All fabric values saved to the app project.")

if st.session_state.get("fabric_elements"):
    st.success("Fabric data is available for the central Run HEM / Results page.")
else:
    st.info("No fabric data has been saved yet.")

with st.expander("Developer/debug: view saved fabric rows", expanded=False):
    st.json(st.session_state.get("fabric_elements", []))
''',
)


print("Batch cleanup G complete.")