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
    "Upload a HEM JSON file or a saved app project JSON, then use the input tabs "
    "to review, edit, prepare and run HEM cases."
)

st.header("1. Load or start project")

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

        s1, s2, s3, s4 = st.columns(4)

        with s1:
            st.metric("Zones", summary["zone_count"])

        with s2:
            st.metric("Opaque elements", summary["fabric_counts"]["opaque"])

        with s3:
            st.metric("Windows / transparent", summary["fabric_counts"]["transparent"])

        with s4:
            st.metric("Background vents", summary["background_vent_count"])

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
            if section in active_project["hem_input"]
        ]

        st.info(
            "HEM input loaded. Detected sections: "
            + ", ".join(detected_sections)
        )

    with st.expander("Developer/debug: view active project JSON", expanded=False):
        st.json(active_project)


st.header("3. Save or clear project")

if active_project is not None:
    project_json = json.dumps(active_project, indent=2)

    st.download_button(
        label="Download current app project JSON",
        data=project_json,
        file_name="saved_app_project.json",
        mime="application/json",
    )

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
