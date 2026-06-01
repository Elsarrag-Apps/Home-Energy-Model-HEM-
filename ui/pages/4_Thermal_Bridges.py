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
