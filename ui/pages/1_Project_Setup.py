import streamlit as st


st.set_page_config(
    page_title="Project Setup",
    layout="wide"
)

st.title("Project Setup")

st.write(
    "Define the basic project information and simulation setup. "
    "These inputs will later be used to build a valid HEM input JSON."
)

with st.form("project_setup_form"):
    st.subheader("Project information")

    col1, col2 = st.columns(2)

    with col1:
        project_name = st.text_input("Project name", "Demo dwelling")
        case_id = st.text_input("Case ID", "CASE-001")
        assessor = st.text_input("Assessor / user", "Esam Elsarrag")

    with col2:
        dwelling_type = st.selectbox(
            "Dwelling type",
            [
                "Detached house",
                "Semi-detached house",
                "Terraced house",
                "Flat",
                "Maisonette",
                "Bungalow",
            ],
        )

        assessment_type = st.selectbox(
            "Assessment type",
            [
                "Design assessment",
                "Existing dwelling",
                "Retrofit option appraisal",
                "Scenario comparison",
                "HEM test run",
            ],
        )

    st.subheader("Geometry summary")

    col3, col4, col5 = st.columns(3)

    with col3:
        floor_area = st.number_input(
            "Total floor area (m²)",
            min_value=1.0,
            value=90.0,
            step=1.0,
        )

    with col4:
        internal_volume = st.number_input(
            "Internal volume (m³)",
            min_value=1.0,
            value=225.0,
            step=1.0,
        )

    with col5:
        number_of_zones = st.number_input(
            "Number of thermal zones",
            min_value=1,
            value=1,
            step=1,
        )

    st.subheader("Simulation setup")

    col6, col7, col8 = st.columns(3)

    with col6:
        simulation_mode = st.selectbox(
            "Simulation mode",
            [
                "Short test run",
                "Full annual run",
                "Custom period",
            ],
        )

    with col7:
        start_day = st.number_input(
            "Start day of year",
            min_value=1,
            max_value=365,
            value=1,
            step=1,
        )

    with col8:
        simulation_hours = st.number_input(
            "Simulation length (hours)",
            min_value=1,
            value=24,
            step=1,
        )

    submitted = st.form_submit_button("Save project setup")

if submitted:
    st.session_state["project_setup"] = {
        "project_name": project_name,
        "case_id": case_id,
        "assessor": assessor,
        "dwelling_type": dwelling_type,
        "assessment_type": assessment_type,
        "floor_area_m2": floor_area,
        "internal_volume_m3": internal_volume,
        "number_of_zones": number_of_zones,
        "simulation_mode": simulation_mode,
        "start_day": start_day,
        "simulation_hours": simulation_hours,
    }

    st.success("Project setup saved.")

if "project_setup" in st.session_state:
    st.subheader("Saved project setup")
    st.json(st.session_state["project_setup"])