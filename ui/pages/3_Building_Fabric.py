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
