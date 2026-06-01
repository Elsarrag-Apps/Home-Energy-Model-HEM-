import json
import sys
from pathlib import Path

import streamlit as st

CURRENT_DIR = Path(__file__).resolve().parent
UTILS_DIR = CURRENT_DIR / "utils"
sys.path.append(str(UTILS_DIR))

from project_store import (
    clear_active_project,
    get_active_project,
    load_json_as_project,
    save_current_project_to_file,
    start_blank_project,
)


st.set_page_config(
    page_title="Home Energy Model Desktop App",
    layout="wide",
)

st.title("Home Energy Model Desktop App")

st.write(
    "Load an existing HEM JSON case, load a saved app project JSON, "
    "or start a blank project and enter inputs manually."
)

st.header("1. Upload / Load JSON")

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

        except Exception as exc:
            st.error("Could not load uploaded JSON.")
            st.exception(exc)


st.header("2. Start blank project")

if st.button("Start blank project"):
    start_blank_project()
    st.success("Blank project started.")


st.header("3. Active project status")

active_project = get_active_project()

if active_project is None:
    st.warning("No active project loaded yet.")
else:
    project_type = active_project.get("project_type", "unknown")
    hem_source = active_project.get("active_hem_source")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Project type", project_type)

    with col2:
        st.metric("HEM source", hem_source or "None")

    with col3:
        has_hem_input = "hem_input" in active_project
        st.metric("HEM template loaded", "Yes" if has_hem_input else "No")

    if "hem_input" in active_project:
        hem_input = active_project["hem_input"]

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
            ]
            if section in hem_input
        ]

        st.info(
            "HEM input loaded. Detected sections: "
            + ", ".join(detected_sections)
        )

    with st.expander("Developer/debug: view active project JSON", expanded=False):
        st.json(active_project)


st.header("4. Save / clear project")

if active_project is not None:
    save_path = Path("ui/temp/saved_app_project.json")

    project_json = json.dumps(active_project, indent=2)

    st.download_button(
        label="Download current app project JSON",
        data=project_json,
        file_name="saved_app_project.json",
        mime="application/json",
    )

    if st.button("Save current project locally"):
        try:
            output_path = save_current_project_to_file(save_path)
            st.success(f"Project saved locally to: {output_path}")
        except Exception as exc:
            st.error("Could not save project.")
            st.exception(exc)

    if st.button("Clear active project"):
        clear_active_project()
        st.success("Active project cleared.")
        st.rerun()