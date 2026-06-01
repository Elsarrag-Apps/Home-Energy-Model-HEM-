import sys
from pathlib import Path

import pandas as pd
import streamlit as st

CURRENT_DIR = Path(__file__).resolve().parent
UI_DIR = CURRENT_DIR.parent
UTILS_DIR = UI_DIR / "utils"
sys.path.append(str(UTILS_DIR))

from input_builder import (
    build_generated_fabric_input,
    get_zone_building_elements,
    summarise_building_elements_for_table,
)
from model_runner import run_hem_model
from results_parser import compare_summary_metrics, format_number


st.set_page_config(
    page_title="Building Fabric - HEM",
    layout="wide",
)

st.title("Building Fabric - HEM Connected")

st.write(
    "Add building fabric elements and generate a HEM-compatible BuildingElement "
    "section. The UI collects inputs; HEM performs the final calculation."
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


if "fabric_elements" not in st.session_state:
    st.session_state["fabric_elements"] = []


st.info
st.header("Existing HEM fabric elements")

try:
    existing_elements = get_zone_building_elements(BASE_JSON_PATH, zone_name="zone 1")
    existing_table = summarise_building_elements_for_table(existing_elements)

    st.write(
        "These are the current BuildingElement entries in the base HEM file. "
        "Use them as a reference before deciding whether to replace all elements "
        "or add new UI elements to the existing model."
    )

    st.dataframe(
        existing_table,
        use_container_width=True,
        hide_index=True,
    )

except Exception as exc:
    st.warning("Could not load existing HEM BuildingElement data.")
    st.exception(exc)


st.header("Fabric update mode")

fabric_update_mode = st.radio(
    "How should the generated HEM file handle existing fabric elements?",
    [
        "Add new UI elements to existing HEM elements",
        "Replace all existing elements",
    ],
    index=0,
)

if fabric_update_mode == "Add new UI elements to existing HEM elements":
    st.info(
        "Safer mode: the generated file keeps the existing HEM elements and adds "
        "the new elements you enter below."
    )
else:
    st.warning(
        "Replace mode: the generated file will replace all existing BuildingElement "
        "entries in zone 1 with the elements you enter below."
    )

st.header("1. Add fabric element")

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
            "Area (m²)",
            min_value=0.01,
            value=20.0,
            step=0.5,
        )

        u_value = st.number_input(
            "U-value (W/m²K)",
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
            [
                "Lightweight",
                "Medium",
                "Heavy",
                "Very heavy",
                "Unknown",
            ],
            index=1,
        )

    st.subheader("Thermal mass")

    col4, col5 = st.columns(2)

    with col4:
        areal_heat_capacity_kj_m2k = st.number_input(
            "Areal heat capacity (kJ/m²K)",
            min_value=0.0,
            value=145.0 if element_type == "External wall" else 75.0,
            step=5.0,
        )

    with col5:
        notes = st.text_input("Notes", "")

    extra_data = {}

    if is_external_opaque(element_type):
        st.subheader("Opaque external surface properties")

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
            g_value = st.number_input(
                "g-value",
                min_value=0.0,
                max_value=1.0,
                value=0.71,
                step=0.01,
                format="%.2f",
            )

        with g2:
            frame_factor = st.number_input(
                "Frame factor",
                min_value=0.0,
                max_value=1.0,
                value=0.70,
                step=0.01,
                format="%.2f",
            )

        with g3:
            openable_fraction = st.number_input(
                "Openable fraction",
                min_value=0.0,
                max_value=1.0,
                value=0.0,
                step=0.05,
                format="%.2f",
            )

        with g4:
            free_area_height_m = st.number_input(
                "Free area height (m)",
                min_value=0.0,
                value=0.2,
                step=0.1,
            )

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
            perimeter_m = st.number_input(
                "Perimeter (m)",
                min_value=0.0,
                value=28.0,
                step=0.5,
            )

        with g2:
            thickness_walls_m = st.number_input(
                "Wall thickness at floor edge (m)",
                min_value=0.0,
                value=0.1705,
                step=0.01,
                format="%.4f",
            )

        with g3:
            psi_wall_floor_junc = st.number_input(
                "ψ wall-floor junction (W/mK)",
                value=0.0,
                step=0.01,
                format="%.3f",
            )

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
        st.subheader("Party wall properties")

        party_wall_cavity_type = st.selectbox(
            "Party wall cavity type",
            [
                "solid",
                "unfilled_unsealed",
                "filled",
                "defined_resistance",
            ],
        )

        extra_data.update(
            {
                "party_wall_cavity_type": party_wall_cavity_type,
            }
        )

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

    st.success(f"Added fabric element: {element_name}")


st.header("2. Fabric elements to be written to HEM")

if not st.session_state["fabric_elements"]:
    st.warning("No fabric elements added yet.")
else:
    df = pd.DataFrame(st.session_state["fabric_elements"])

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )

    total_area = df["area_m2"].sum()
    fabric_hlc = (df["area_m2"] * df["u_value_w_m2k"]).sum()
    average_u = fabric_hlc / total_area if total_area > 0 else 0

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total area", f"{total_area:.1f} m²")

    with col2:
        st.metric("Input HLC indicator", f"{fabric_hlc:.1f} W/K")

    with col3:
        st.metric("Area-weighted U-value", f"{average_u:.3f} W/m²K")

    st.subheader("Input HLC contribution")
    chart_df = df.copy()
    chart_df["hlc_w_k"] = chart_df["area_m2"] * chart_df["u_value_w_m2k"]
    st.bar_chart(chart_df[["name", "hlc_w_k"]].set_index("name"))

    if st.button("Clear all fabric elements"):
        st.session_state["fabric_elements"] = []
        st.rerun()


st.header("3. Build HEM JSON and run")

if not st.session_state["fabric_elements"]:
    st.warning("Add at least one fabric element before building the HEM JSON.")
else:
    if st.button("Build generated fabric HEM JSON"):
        try:
            generated_input = build_generated_fabric_input(
                base_json_path=BASE_JSON_PATH,
                output_json_path=GENERATED_FABRIC_INPUT_PATH,
                fabric_elements=st.session_state["fabric_elements"],
                zone_name="zone 1",
                update_mode=fabric_update_mode,
            )

            st.session_state["generated_fabric_input_ready"] = True

            st.success(f"Generated HEM input saved to: {GENERATED_FABRIC_INPUT_PATH}")

            with st.expander(
                "Preview generated Zone -> zone 1 -> BuildingElement JSON",
                expanded=True,
            ):
                st.json(generated_input["Zone"]["zone 1"]["BuildingElement"])

        except Exception as exc:
            st.error("Failed to build generated HEM fabric input.")
            st.exception(exc)

    if st.session_state.get("generated_fabric_input_ready"):
        if st.button("Run HEM with generated fabric input"):
            with st.spinner("Running HEM..."):
                result = run_hem_model(GENERATED_FABRIC_INPUT_PATH, WEATHER_FILE)

            if result.returncode == 0:
                st.success("HEM run completed successfully.")

                if FABRIC_SUMMARY_PATH.exists():
                    summary_text = FABRIC_SUMMARY_PATH.read_text(encoding="utf-8")

                    st.subheader("HEM result comparison")

                    if BASE_SUMMARY_PATH.exists():
                        comparison = compare_summary_metrics(
                            BASE_SUMMARY_PATH,
                            FABRIC_SUMMARY_PATH,
                        )

                        col1, col2, col3 = st.columns(3)

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

                        with col1:
                            st.metric(
                                "Space heat demand",
                                (
                                    f"{format_number(space_heat['generated_value'])} "
                                    f"{space_heat['unit']}"
                                ),
                                (
                                    f"{format_number(space_heat['difference'])} "
                                    f"{space_heat['unit']}"
                                ),
                            )

                        with col2:
                            st.metric(
                                "Peak electricity",
                                (
                                    f"{format_number(peak_elec['generated_value'])} "
                                    f"{peak_elec['unit']}"
                                ),
                                (
                                    f"{format_number(peak_elec['difference'])} "
                                    f"{peak_elec['unit']}"
                                ),
                            )

                        with col3:
                            st.metric(
                                "Delivered energy",
                                (
                                    f"{format_number(delivered['generated_value'])} "
                                    f"{delivered['unit']}"
                                ),
                                (
                                    f"{format_number(delivered['difference'])} "
                                    f"{delivered['unit']}"
                                ),
                            )

                        st.subheader("Base vs generated case comparison")

                        comparison_rows = []
                        for item in comparison:
                            comparison_rows.append(
                                {
                                    "Metric": item["metric"],
                                    "Base value": item["base_value"],
                                    "Generated value": item["generated_value"],
                                    "Difference": item["difference"],
                                    "Percent change": item["percent_change"],
                                    "Unit": item["unit"],
                                }
                            )

                        st.dataframe(
                            comparison_rows,
                            use_container_width=True,
                            hide_index=True,
                        )

                    else:
                        st.warning(
                            "Base summary file was not found. "
                            "Run the base demo case first if comparison is needed."
                        )

                    st.subheader("HEM summary output")
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


st.header("4. Saved fabric input state")

st.json(st.session_state.get("fabric_elements", []))