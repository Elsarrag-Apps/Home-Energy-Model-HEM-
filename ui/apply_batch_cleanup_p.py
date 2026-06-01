from pathlib import Path


def write_file(path, content):
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"Updated {file_path}")


write_file(
    "ui/app.py",
    """
import json
import sys
from pathlib import Path

import streamlit as st

CURRENT_DIR = Path(__file__).resolve().parent
UTILS_DIR = CURRENT_DIR / "utils"
sys.path.append(str(UTILS_DIR))

from hem_extractors import summarise_active_hem_case
from project_store import (
    ACTIVE_HEM_INPUT_PATH,
    clear_active_project,
    get_active_project,
    get_project_data_section,
    load_json_as_project,
    save_current_project_to_file,
    start_blank_project,
    update_project_data,
)


st.set_page_config(
    page_title="Project Setup",
    layout="wide",
)

st.title("Project Setup")

st.write(
    "Start a new project, upload an existing HEM JSON or saved app project JSON, "
    "review the active case, and save the main project details."
)


st.header("1. Start or load project")

col_load, col_blank = st.columns(2)

with col_load:
    st.subheader("Upload / load JSON")

    uploaded_file = st.file_uploader(
        "Upload HEM input JSON or saved app project JSON",
        type=["json"],
    )

    if uploaded_file is not None:
        if st.button("Load uploaded JSON"):
            try:
                file_type, project_data = load_json_as_project(
                    uploaded_file,
                    source_name=uploaded_file.name,
                )

                if file_type == "hem_input":
                    st.success("Loaded uploaded file as a HEM input template.")
                else:
                    st.success("Loaded uploaded file as a saved app project.")

                st.rerun()

            except Exception as exc:
                st.error("Could not load uploaded JSON.")
                st.exception(exc)

with col_blank:
    st.subheader("Start manually")

    st.write(
        "Start a blank app project if you want to enter inputs manually rather "
        "than using an existing HEM case as the starting point."
    )

    if st.button("Start blank project"):
        start_blank_project()
        st.success("Blank project started.")
        st.rerun()


st.header("2. Active project status")

active_project = get_active_project()

if active_project is None:
    st.warning("No active project loaded yet.")
else:
    project_type = active_project.get("project_type", "unknown")
    hem_source = active_project.get("active_hem_source")
    has_hem_input = "hem_input" in active_project

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Project type", project_type)

    with col2:
        st.metric("Loaded source", hem_source or "Manual / blank")

    with col3:
        st.metric("HEM template loaded", "Yes" if has_hem_input else "No")

    if has_hem_input and ACTIVE_HEM_INPUT_PATH.exists():
        summary = summarise_active_hem_case(ACTIVE_HEM_INPUT_PATH)

        st.subheader("Loaded HEM case summary")

        s1, s2, s3, s4, s5 = st.columns(5)

        with s1:
            st.metric("Zones", summary["zone_count"])

        with s2:
            st.metric("Opaque elements", summary["fabric_counts"]["opaque"])

        with s3:
            st.metric("Windows", summary["fabric_counts"]["transparent"])

        with s4:
            st.metric("Heating systems", summary.get("space_heating_system_count", 0))

        with s5:
            st.metric("Hot water sources", summary.get("hot_water_source_count", 0))

        detected_sections = [
            section
            for section in [
                "SimulationTime",
                "ExternalConditions",
                "Zone",
                "InfiltrationVentilation",
                "EnergySupply",
                "SpaceHeatSystem",
                "HotWaterSource",
                "HotWaterDemand",
                "InternalGains",
                "ApplianceGains",
                "Events",
                "Control",
            ]
            if section in active_project["hem_input"]
        ]

        st.info(
            "HEM input loaded. Detected sections: "
            + ", ".join(detected_sections)
        )


st.header("3. Project details")

saved_setup = get_project_data_section("project_setup", {}) or {}

hem_input = active_project.get("hem_input", {}) if active_project else {}
zones = hem_input.get("Zone", {})
first_zone = next(iter(zones.values()), {}) if zones else {}

default_floor_area = float(saved_setup.get("floor_area_m2", first_zone.get("area", 90.0)))
default_volume = float(saved_setup.get("internal_volume_m3", first_zone.get("volume", 225.0)))

with st.form("project_setup_form"):
    col1, col2, col3 = st.columns(3)

    with col1:
        project_name = st.text_input(
            "Project name",
            value=saved_setup.get("project_name", "Demo dwelling"),
        )

        case_id = st.text_input(
            "Case ID",
            value=saved_setup.get("case_id", "CASE-001"),
        )

        assessor = st.text_input(
            "Assessor",
            value=saved_setup.get("assessor", ""),
        )

    with col2:
        dwelling_options = [
            "Flat",
            "Detached house",
            "Semi-detached house",
            "Terraced house",
            "Other",
        ]

        dwelling_type = st.selectbox(
            "Dwelling type",
            dwelling_options,
            index=dwelling_options.index(
                saved_setup.get("dwelling_type", "Flat")
            )
            if saved_setup.get("dwelling_type", "Flat") in dwelling_options
            else 0,
        )

        assessment_options = [
            "Design assessment",
            "Existing dwelling",
            "Retrofit assessment",
            "Scenario test",
        ]

        assessment_type = st.selectbox(
            "Assessment type",
            assessment_options,
            index=assessment_options.index(
                saved_setup.get("assessment_type", "Design assessment")
            )
            if saved_setup.get("assessment_type", "Design assessment") in assessment_options
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

        simulation_options = [
            "Short test run",
            "Annual run",
            "Custom",
        ]

        simulation_mode = st.selectbox(
            "Simulation mode",
            simulation_options,
            index=simulation_options.index(
                saved_setup.get("simulation_mode", "Short test run")
            )
            if saved_setup.get("simulation_mode", "Short test run") in simulation_options
            else 0,
        )

    save_setup = st.form_submit_button("Save project details")


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

    st.success("Project details saved.")


st.header("4. Save, export or clear project")

active_project = get_active_project()

if active_project is None:
    st.info("Load or start a project before saving/exporting.")
else:
    project_json = json.dumps(active_project, indent=2)

    col_a, col_b = st.columns(2)

    with col_a:
        st.download_button(
            label="Download current app project JSON",
            data=project_json,
            file_name="saved_app_project.json",
            mime="application/json",
        )

    with col_b:
        if st.button("Save current project locally"):
            try:
                output_path = save_current_project_to_file(
                    Path("ui/temp/saved_app_project.json")
                )
                st.success(f"Project saved locally to: {output_path}")
            except Exception as exc:
                st.error("Could not save project.")
                st.exception(exc)

    if st.button("Clear active project"):
        clear_active_project()
        st.success("Active project cleared.")
        st.rerun()

    with st.expander("Developer/debug: view active project JSON", expanded=False):
        st.json(active_project)
""",
)


old_page = Path("ui/pages/1_Project_Setup.py")
hidden_page = Path("ui/pages/_1_Project_Setup_old.py")

if old_page.exists():
    hidden_page.write_text(
        old_page.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    old_page.unlink()
    print("Moved ui/pages/1_Project_Setup.py to ui/pages/_1_Project_Setup_old.py")

print("Batch P complete.")