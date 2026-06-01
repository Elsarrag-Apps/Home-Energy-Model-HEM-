from pathlib import Path

import streamlit as st


st.set_page_config(
    page_title="Weather & Simulation",
    layout="wide"
)

st.title("Weather & Simulation")

st.write(
    "Select the weather file and define the simulation period. "
    "For now, this page stores the settings for later use by the HEM runner."
)

DEFAULT_WEATHER_FILE = Path("test/e2e/demo_files/London_weather_CIBSE_format.csv")

with st.form("weather_simulation_form"):
    st.subheader("Weather file")

    weather_mode = st.radio(
        "Weather source",
        [
            "Use default London CIBSE demo weather file",
            "Enter custom weather file path",
        ],
    )

    if weather_mode == "Use default London CIBSE demo weather file":
        weather_file = str(DEFAULT_WEATHER_FILE)
        st.info(f"Using default weather file: {weather_file}")
    else:
        weather_file = st.text_input(
            "Custom weather file path",
            value=str(DEFAULT_WEATHER_FILE),
            help="Enter the path to a CIBSE-format weather CSV file.",
        )

    st.subheader("Simulation period")

    col1, col2, col3 = st.columns(3)

    with col1:
        run_type = st.selectbox(
            "Run type",
            [
                "24-hour test",
                "168-hour weekly test",
                "Full annual run",
                "Custom run",
            ],
        )

    with col2:
        start_day = st.number_input(
            "Start day of year",
            min_value=1,
            max_value=365,
            value=1,
            step=1,
        )

    with col3:
        if run_type == "24-hour test":
            simulation_hours = 24
        elif run_type == "168-hour weekly test":
            simulation_hours = 168
        elif run_type == "Full annual run":
            simulation_hours = 8760
        else:
            simulation_hours = st.number_input(
                "Simulation length (hours)",
                min_value=1,
                value=24,
                step=1,
            )

        st.number_input(
            "Simulation length used (hours)",
            min_value=1,
            value=int(simulation_hours),
            step=1,
            disabled=True,
        )

    st.subheader("Output settings")

    output_prefix = st.text_input(
        "Output case name",
        value="hem_input",
        help="This will be used later to organise output files.",
    )

    save_button = st.form_submit_button("Save weather and simulation settings")

if save_button:
    st.session_state["weather_simulation"] = {
        "weather_mode": weather_mode,
        "weather_file": weather_file,
        "run_type": run_type,
        "start_day": start_day,
        "simulation_hours": simulation_hours,
        "output_prefix": output_prefix,
    }

    st.success("Weather and simulation settings saved.")

if "weather_simulation" in st.session_state:
    st.subheader("Saved weather and simulation settings")
    st.json(st.session_state["weather_simulation"])