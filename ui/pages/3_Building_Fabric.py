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
