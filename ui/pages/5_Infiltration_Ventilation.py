import json
import sys
from pathlib import Path

import streamlit as st

CURRENT_DIR = Path(__file__).resolve().parent
UI_DIR = CURRENT_DIR.parent
UTILS_DIR = UI_DIR / "utils"
sys.path.append(str(UTILS_DIR))

from input_builder import build_generated_hem_input
from model_runner import run_hem_model


st.set_page_config(
    page_title="Infiltration & Ventilation - HEM",
    layout="wide",
)

st.title("Infiltration & Ventilation - HEM Connected")

st.write(
    "This page maps infiltration and ventilation inputs directly into a valid HEM JSON, "
    "runs HEM, and displays the HEM-generated outputs. No ventilation result is calculated "
    "by the UI."
)

BASE_JSON_PATH = Path("test/e2e/demo_files/short/demo.json")
WEATHER_FILE = Path("test/e2e/demo_files/London_weather_CIBSE_format.csv")
GENERATED_INPUT_PATH = Path("ui/temp/generated_ventilation_case.json")
SUMMARY_PATH = Path(
    "ui/temp/generated_ventilation_case__results/"
    "generated_ventilation_case__core__results_summary.csv"
)
CORE_RESULTS_PATH = Path(
    "ui/temp/generated_ventilation_case__results/"
    "generated_ventilation_case__core__results.csv"
)

st.info(
    "Base HEM case: test/e2e/demo_files/short/demo.json. "
    "This page replaces only the InfiltrationVentilation section."
)


st.header("1. Leakage / airtightness")

with st.form("hem_airtightness_form"):
    col1, col2, col3 = st.columns(3)

    with col1:
        q50 = st.number_input(
            "q50 test result (m³/h.m² at 50 Pa)",
            min_value=0.01,
            value=1.20,
            step=0.10,
            format="%.2f",
        )

        test_pressure = st.number_input(
            "Test pressure (Pa)",
            min_value=1.0,
            value=50.0,
            step=5.0,
        )

    with col2:
        envelope_area = st.number_input(
            "Envelope area (m²)",
            min_value=1.0,
            value=220.0,
            step=1.0,
        )

        ventilation_zone_height = st.number_input(
            "Ventilation zone height (m)",
            min_value=0.1,
            value=6.0,
            step=0.5,
        )

    with col3:
        ventilation_zone_base_height = st.number_input(
            "Ventilation zone base height (m)",
            min_value=0.0,
            value=2.5,
            step=0.5,
        )

        altitude = st.number_input(
            "Altitude (m)",
            min_value=0.0,
            value=30.0,
            step=5.0,
        )

    st.subheader("Exposure")

    col4, col5, col6 = st.columns(3)

    with col4:
        shield_class = st.selectbox(
            "Shield class",
            [
                "Open / exposed",
                "Normal / suburban",
                "Shielded / dense urban",
            ],
            index=1,
        )

    with col5:
        terrain_class = st.selectbox(
            "Terrain class",
            [
                "Open water",
                "Open country",
                "Suburban",
                "Urban",
            ],
            index=1,
        )

    with col6:
        cross_ventilation = st.checkbox(
            "Cross ventilation possible",
            value=True,
        )

    save_airtightness = st.form_submit_button("Save leakage and exposure inputs")


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

    st.success("HEM leakage and exposure inputs saved.")


st.header("2. Background vents")

if "hem_background_vents" not in st.session_state:
    st.session_state["hem_background_vents"] = []

with st.form("hem_background_vent_form"):
    col1, col2, col3 = st.columns(3)

    with col1:
        vent_name = st.text_input("Vent name", "vent1")
        area_cm2 = st.number_input(
            "Equivalent area (cm²)",
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

    add_vent = st.form_submit_button("Add HEM vent")


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

    st.success(f"Added HEM vent: {vent_name}")


if st.session_state["hem_background_vents"]:
    st.subheader("HEM vents to be written into JSON")
    st.dataframe(st.session_state["hem_background_vents"], use_container_width=True)

    if st.button("Clear HEM vents"):
        st.session_state["hem_background_vents"] = []
        st.rerun()


st.header("3. Mechanical ventilation")

with st.form("hem_mechanical_ventilation_form"):
    col1, col2, col3 = st.columns(3)

    with col1:
        vent_type = st.selectbox(
            "HEM mechanical ventilation type",
            [
                "None",
                "Intermittent MEV",
                "Centralised continuous MEV",
                "Decentralised continuous MEV",
                "MVHR",
                "Positive input ventilation",
            ],
            index=0,
        )

        energy_supply = st.selectbox(
            "Energy supply",
            [
                "mains elec",
            ],
        )

    with col2:
        design_flow_l_s = st.number_input(
            "Design outdoor air-flow rate (l/s)",
            min_value=0.0,
            value=25.0,
            step=1.0,
            help="The builder converts this to m³/h for HEM.",
        )

        sfp = st.number_input(
            "Specific fan power SFP (W/l/s)",
            min_value=0.01,
            value=0.50,
            step=0.05,
            format="%.2f",
        )

    with col3:
        sfp_in_use_factor = st.number_input(
            "SFP in-use factor",
            min_value=1.0,
            value=1.0,
            step=0.05,
            format="%.2f",
        )

        mvhr_efficiency_percent = st.number_input(
            "MVHR efficiency (%)",
            min_value=0.0,
            max_value=100.0,
            value=85.0,
            step=1.0,
        )

    st.subheader("Mechanical ventilation position")

    col4, col5, col6 = st.columns(3)

    with col4:
        mvhr_location = st.selectbox(
            "MVHR location",
            [
                "inside",
                "outside",
            ],
        )

        intake_orientation = st.selectbox(
            "Intake orientation",
            [
                "North",
                "East",
                "South",
                "West",
                "Roof / horizontal",
            ],
            index=0,
        )

    with col5:
        intake_pitch = st.number_input(
            "Intake pitch (degrees)",
            min_value=0.0,
            max_value=180.0,
            value=90.0,
            step=1.0,
        )

        intake_mid_height = st.number_input(
            "Intake mid-height (m)",
            min_value=0.01,
            value=2.0,
            step=0.1,
        )

    with col6:
        exhaust_orientation = st.selectbox(
            "Exhaust orientation",
            [
                "North",
                "East",
                "South",
                "West",
                "Roof / horizontal",
            ],
            index=2,
        )

        exhaust_pitch = st.number_input(
            "Exhaust pitch (degrees)",
            min_value=0.0,
            max_value=180.0,
            value=90.0,
            step=1.0,
        )

        exhaust_mid_height = st.number_input(
            "Exhaust mid-height (m)",
            min_value=0.01,
            value=2.0,
            step=0.1,
        )

    save_mech = st.form_submit_button("Save mechanical ventilation inputs")


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

    st.success("HEM mechanical ventilation inputs saved.")


st.header("4. Build HEM JSON and run")

can_run = "hem_airtightness_exposure" in st.session_state

if not can_run:
    st.warning("Save leakage and exposure inputs before building the HEM JSON.")
else:
    if st.button("Build generated HEM JSON"):
        generated_input = build_generated_hem_input(
            base_json_path=BASE_JSON_PATH,
            output_json_path=GENERATED_INPUT_PATH,
            airtightness_exposure=st.session_state["hem_airtightness_exposure"],
            background_vents=st.session_state["hem_background_vents"],
            mechanical_ventilation=st.session_state.get(
                "hem_mechanical_ventilation"
            ),
        )

        st.session_state["generated_ventilation_input_ready"] = True

        st.success(f"Generated HEM input saved to: {GENERATED_INPUT_PATH}")

        with st.expander("Preview generated InfiltrationVentilation JSON", expanded=True):
            st.json(generated_input["InfiltrationVentilation"])

    if st.session_state.get("generated_ventilation_input_ready"):
        if st.button("Run HEM with generated ventilation input"):
            with st.spinner("Running HEM..."):
                result = run_hem_model(GENERATED_INPUT_PATH, WEATHER_FILE)

            if result.returncode == 0:
                st.success("HEM run completed successfully.")

                if SUMMARY_PATH.exists():
                    summary_text = SUMMARY_PATH.read_text(encoding="utf-8")

                    st.subheader("HEM summary output")
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


st.header("5. Saved HEM input state")

state_preview = {
    "airtightness_exposure": st.session_state.get("hem_airtightness_exposure"),
    "background_vents": st.session_state.get("hem_background_vents"),
    "mechanical_ventilation": st.session_state.get("hem_mechanical_ventilation"),
}

st.json(state_preview)