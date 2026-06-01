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
