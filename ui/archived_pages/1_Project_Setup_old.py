import sys
from pathlib import Path

import streamlit as st

CURRENT_DIR = Path(__file__).resolve().parent
UI_DIR = CURRENT_DIR.parent
UTILS_DIR = UI_DIR / "utils"
sys.path.append(str(UTILS_DIR))

from project_store import get_active_project, get_project_data_section, update_project_data


st.set_page_config(
    page_title="Project Setup",
    layout="wide",
)

st.title("Project Setup")

st.write(
    "Set the main project details used by the app. These values are saved into "
    "the app project JSON and can be reused later."
)

active_project = get_active_project()

if active_project is None:
    st.warning("No active project loaded. You can still enter values manually, or go to Home and load a JSON file.")
else:
    st.success("Active project loaded.")

saved_setup = get_project_data_section("project_setup", {}) or {}

hem_input = active_project.get("hem_input", {}) if active_project else {}
zones = hem_input.get("Zone", {})
first_zone = next(iter(zones.values()), {}) if zones else {}

default_floor_area = float(saved_setup.get("floor_area_m2", first_zone.get("area", 90.0)))
default_volume = float(saved_setup.get("internal_volume_m3", first_zone.get("volume", 225.0)))

st.header("1. Project information")

with st.form("project_setup_form"):
    col1, col2, col3 = st.columns(3)

    with col1:
        project_name = st.text_input(
            "Project name",
            value=saved_setup.get("project_name", "Demo dwelling - HL"),
        )

        case_id = st.text_input(
            "Case ID",
            value=saved_setup.get("case_id", "CASE-001"),
        )

        assessor = st.text_input(
            "Assessor",
            value=saved_setup.get("assessor", "Esam Elsarrag"),
        )

    with col2:
        dwelling_type = st.selectbox(
            "Dwelling type",
            ["Flat", "Detached house", "Semi-detached house", "Terraced house", "Other"],
            index=["Flat", "Detached house", "Semi-detached house", "Terraced house", "Other"].index(
                saved_setup.get("dwelling_type", "Flat")
            )
            if saved_setup.get("dwelling_type", "Flat") in ["Flat", "Detached house", "Semi-detached house", "Terraced house", "Other"]
            else 0,
        )

        assessment_type = st.selectbox(
            "Assessment type",
            ["Design assessment", "Existing dwelling", "Retrofit assessment", "Scenario test"],
            index=["Design assessment", "Existing dwelling", "Retrofit assessment", "Scenario test"].index(
                saved_setup.get("assessment_type", "Design assessment")
            )
            if saved_setup.get("assessment_type", "Design assessment") in ["Design assessment", "Existing dwelling", "Retrofit assessment", "Scenario test"]
            else 0,
        )

        number_of_zones = st.number_input(
            "Number of zones",
            min_value=1,
            value=int(saved_setup.get("number_of_zones", max(1, len(zones)))),
            step=1,
        )

    with col3:
        floor_area_m2 = st.number_input(
            "Floor area (m2)",
            min_value=0.0,
            value=default_floor_area,
            step=1.0,
        )

        internal_volume_m3 = st.number_input(
            "Internal volume (m3)",
            min_value=0.0,
            value=default_volume,
            step=1.0,
        )

        simulation_mode = st.selectbox(
            "Simulation mode",
            ["Short test run", "Annual run", "Custom"],
            index=["Short test run", "Annual run", "Custom"].index(
                saved_setup.get("simulation_mode", "Short test run")
            )
            if saved_setup.get("simulation_mode", "Short test run") in ["Short test run", "Annual run", "Custom"]
            else 0,
        )

    save_setup = st.form_submit_button("Save project setup")


if save_setup:
    project_setup = {
        "project_name": project_name,
        "case_id": case_id,
        "assessor": assessor,
        "dwelling_type": dwelling_type,
        "assessment_type": assessment_type,
        "floor_area_m2": floor_area_m2,
        "internal_volume_m3": internal_volume_m3,
        "number_of_zones": number_of_zones,
        "simulation_mode": simulation_mode,
    }

    st.session_state["project_setup"] = project_setup
    update_project_data("project_setup", project_setup)

    st.success("Project setup saved.")

st.header("2. Saved project setup")

current_setup = st.session_state.get(
    "project_setup",
    get_project_data_section("project_setup", {}) or {},
)

if current_setup:
    st.json(current_setup)
else:
    st.info("No project setup has been saved yet.")
