import json
from pathlib import Path

import streamlit as st


APP_PROJECT_VERSION = "0.1"

TEMP_DIR = Path("ui/temp")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

ACTIVE_HEM_INPUT_PATH = TEMP_DIR / "active_hem_input.json"
ACTIVE_APP_PROJECT_PATH = TEMP_DIR / "active_app_project.json"


def is_hem_input_json(data: dict) -> bool:
    """Detect whether a JSON object looks like an official HEM input file."""
    if not isinstance(data, dict):
        return False

    hem_keys = {
        "metadata",
        "SimulationTime",
        "ExternalConditions",
        "Zone",
        "InfiltrationVentilation",
        "EnergySupply",
        "Control",
        "HotWaterSource",
        "HotWaterDemand",
        "SpaceHeatSystem",
    }

    matched_keys = hem_keys.intersection(set(data.keys()))
    return len(matched_keys) >= 2 and "Zone" in data


def is_app_project_json(data: dict) -> bool:
    """Detect whether a JSON object looks like a saved app project file."""
    if not isinstance(data, dict):
        return False

    return "app_project_version" in data and "project_data" in data


def create_blank_project() -> dict:
    """Create a blank app project structure."""
    return {
        "app_project_version": APP_PROJECT_VERSION,
        "project_type": "blank_app_project",
        "active_hem_source": None,
        "project_data": {
            "project_setup": {},
            "weather_simulation": {},
            "fabric_elements": [],
            "ventilation": {},
            "thermal_bridges": [],
            "heating_hot_water": {},
            "renewables_battery": {},
        },
    }


def create_app_project_from_hem_input(hem_data: dict, source_name: str) -> dict:
    """Create an app project wrapper around an uploaded HEM input file."""
    return {
        "app_project_version": APP_PROJECT_VERSION,
        "project_type": "hem_input_template",
        "active_hem_source": source_name,
        "project_data": {
            "project_setup": {},
            "weather_simulation": {},
            "fabric_elements": [],
            "ventilation": {},
            "thermal_bridges": [],
            "heating_hot_water": {},
            "renewables_battery": {},
        },
        "hem_input": hem_data,
    }


def load_uploaded_json(uploaded_file) -> dict:
    """Load uploaded JSON from Streamlit file uploader."""
    uploaded_file.seek(0)
    raw_bytes = uploaded_file.read()

    if isinstance(raw_bytes, bytes):
        raw_text = raw_bytes.decode("utf-8-sig")
    else:
        raw_text = raw_bytes

    return json.loads(raw_text)


def set_active_project(project_data: dict) -> None:
    """Set active app project in Streamlit session state and save temp file."""
    st.session_state["active_app_project"] = project_data

    with open(ACTIVE_APP_PROJECT_PATH, "w", encoding="utf-8") as f:
        json.dump(project_data, f, indent=2)

    if "hem_input" in project_data:
        st.session_state["active_hem_input"] = project_data["hem_input"]

        with open(ACTIVE_HEM_INPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(project_data["hem_input"], f, indent=2)


def load_json_as_project(uploaded_file, source_name: str) -> tuple[str, dict]:
    """Load either HEM JSON or saved app project JSON."""
    data = load_uploaded_json(uploaded_file)

    if is_app_project_json(data):
        set_active_project(data)
        return "app_project", data

    if is_hem_input_json(data):
        project_data = create_app_project_from_hem_input(data, source_name)
        set_active_project(project_data)
        return "hem_input", project_data

    detected_keys = list(data.keys())[:20] if isinstance(data, dict) else []

    raise ValueError(
        "Uploaded JSON was not recognised as either a HEM input JSON "
        "or a saved app project JSON. "
        f"Detected top-level keys: {detected_keys}"
    )


def start_blank_project() -> dict:
    """Start a blank app project."""
    project_data = create_blank_project()
    set_active_project(project_data)
    return project_data


def clear_active_project() -> None:
    """Clear active project from session state and temp files."""
    keys_to_clear = [
        "active_app_project",
        "active_hem_input",
        "project_setup",
        "weather_simulation",
        "fabric_elements",
        "hem_airtightness_exposure",
        "hem_background_vents",
        "hem_mechanical_ventilation",
        "ventilation_defaults_loaded",
        "generated_ventilation_input_ready",
        "last_generated_ventilation_json",
        "thermal_bridges",
        "generated_fabric_input_ready",
    ]

    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]

    for path in [ACTIVE_HEM_INPUT_PATH, ACTIVE_APP_PROJECT_PATH]:
        if path.exists():
            path.unlink()


def get_active_project() -> dict | None:
    """Return active app project if available."""
    return st.session_state.get("active_app_project")


def get_active_hem_input() -> dict | None:
    """Return active HEM input if available."""
    return st.session_state.get("active_hem_input")


def update_project_data(section_name: str, section_data) -> None:
    """Update a user-friendly section inside the active app project."""
    project = get_active_project()

    if project is None:
        project = create_blank_project()

    project.setdefault("project_data", {})
    project["project_data"][section_name] = section_data

    set_active_project(project)


def get_project_data_section(section_name: str, default=None):
    """Read a user-friendly section from the active app project."""
    project = get_active_project()

    if project is None:
        return default

    return project.get("project_data", {}).get(section_name, default)


def save_current_project_to_file(output_path: Path) -> Path:
    """Save the active app project to a JSON file."""
    project_data = get_active_project()

    if project_data is None:
        raise ValueError("No active project to save.")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(project_data, f, indent=2)

    return output_path
