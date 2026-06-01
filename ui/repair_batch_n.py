from pathlib import Path


def write_file(path, content):
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"Updated {file_path}")


def replace_once(path, old, new):
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")

    if old not in text:
        raise RuntimeError(f"Could not find expected text in {file_path}")

    text = text.replace(old, new, 1)
    file_path.write_text(text, encoding="utf-8")
    print(f"Patched {file_path}")


write_file(
    "ui/utils/energy_extractors.py",
    """
import json
from pathlib import Path


def load_json_file(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_energy_supply_from_hem(hem_json_path: Path) -> dict:
    hem_input = load_json_file(hem_json_path)
    return hem_input.get("EnergySupply", {})


def summarise_energy_supply(energy_supply: dict) -> list[dict]:
    rows = []

    for name, supply in (energy_supply or {}).items():
        if isinstance(supply, dict):
            rows.append(
                {
                    "name": name,
                    "type": supply.get("type", "Unknown"),
                    "fuel": supply.get("fuel", supply.get("Fuel", "")),
                    "has_diverter": "diverter" in supply or "Diverter" in supply,
                    "has_battery": "battery" in supply or "Battery" in supply,
                    "has_generation": "generation" in supply or "Generation" in supply,
                }
            )
        else:
            rows.append(
                {
                    "name": name,
                    "type": type(supply).__name__,
                    "fuel": "",
                    "has_diverter": False,
                    "has_battery": False,
                    "has_generation": False,
                }
            )

    return rows
""",
)


write_file(
    "ui/pages/8_Energy_Supply_PV_Battery.py",
    """
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

CURRENT_DIR = Path(__file__).resolve().parent
UI_DIR = CURRENT_DIR.parent
UTILS_DIR = UI_DIR / "utils"
sys.path.append(str(UTILS_DIR))

from energy_extractors import extract_energy_supply_from_hem, summarise_energy_supply
from project_store import get_project_data_section, update_project_data


st.set_page_config(
    page_title="Energy Supply / PV / Battery",
    layout="wide",
)

st.title("Energy Supply / PV / Battery")

st.write(
    "Review and edit the EnergySupply section loaded from the active HEM case. "
    "This first connected version preserves the official HEM JSON structure. "
    "Later, this can be expanded into simplified forms for electricity supply, "
    "PV, batteries, diverters and export settings."
)

BASE_JSON_PATH = Path("ui/temp/active_hem_input.json")

if not BASE_JSON_PATH.exists():
    st.error(
        "No active HEM input found. Go to the Home page and upload/load a HEM JSON first."
    )
    st.stop()


def load_energy_defaults_into_state(force_reload: bool = False) -> None:
    already_loaded = st.session_state.get("energy_supply_defaults_loaded", False)

    if already_loaded and not force_reload:
        return

    project_energy_supply = get_project_data_section("energy_supply", None)

    if project_energy_supply and not force_reload:
        st.session_state["energy_supply"] = project_energy_supply
    else:
        st.session_state["energy_supply"] = extract_energy_supply_from_hem(
            BASE_JSON_PATH
        )

    st.session_state["energy_supply_defaults_loaded"] = True


def clear_energy_state() -> None:
    for key in [
        "energy_supply",
        "energy_supply_defaults_loaded",
    ]:
        if key in st.session_state:
            del st.session_state[key]


load_energy_defaults_into_state(force_reload=False)

st.header("1. Input source")

col1, col2 = st.columns(2)

with col1:
    if st.button("Restore energy supply from uploaded HEM JSON"):
        load_energy_defaults_into_state(force_reload=True)
        update_project_data("energy_supply", st.session_state["energy_supply"])
        st.success("Energy supply restored from uploaded HEM JSON.")
        st.rerun()

with col2:
    if st.button("Clear energy supply"):
        clear_energy_state()
        update_project_data("energy_supply", {})
        st.warning("Energy supply cleared. The uploaded HEM case is still loaded.")
        st.rerun()

energy_supply = st.session_state.get("energy_supply", {})

st.header("2. Energy supply summary")

summary_rows = summarise_energy_supply(energy_supply)

if summary_rows:
    st.dataframe(
        pd.DataFrame(summary_rows),
        use_container_width=True,
        hide_index=True,
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric("Energy supplies", len(summary_rows))

    with c2:
        st.metric(
            "Generation entries",
            sum(1 for row in summary_rows if row["has_generation"]),
        )

    with c3:
        st.metric(
            "Battery entries",
            sum(1 for row in summary_rows if row["has_battery"]),
        )

    with c4:
        st.metric(
            "Diverter entries",
            sum(1 for row in summary_rows if row["has_diverter"]),
        )
else:
    st.info("No EnergySupply entries found in the active HEM case.")

st.header("3. Edit EnergySupply JSON")

st.caption(
    "This editor preserves the official HEM EnergySupply structure. "
    "Only edit this JSON if you know the HEM schema."
)

energy_json_text = st.text_area(
    "EnergySupply JSON",
    value=json.dumps(energy_supply, indent=2),
    height=520,
)

col_save, col_validate = st.columns(2)

with col_validate:
    if st.button("Validate EnergySupply JSON"):
        try:
            parsed = json.loads(energy_json_text)
            if not isinstance(parsed, dict):
                st.error("EnergySupply JSON must be a JSON object/dictionary.")
            else:
                st.success("EnergySupply JSON is valid JSON.")
        except json.JSONDecodeError as exc:
            st.error("EnergySupply JSON is not valid.")
            st.code(str(exc))

with col_save:
    if st.button("Save energy supply to project"):
        try:
            parsed = json.loads(energy_json_text)
            if not isinstance(parsed, dict):
                st.error("EnergySupply JSON must be a JSON object/dictionary.")
            else:
                st.session_state["energy_supply"] = parsed
                update_project_data("energy_supply", parsed)
                st.success("EnergySupply saved to the app project.")
        except json.JSONDecodeError as exc:
            st.error("EnergySupply JSON is not valid.")
            st.code(str(exc))

st.header("4. Project save status")

if st.session_state.get("energy_supply"):
    st.success("Energy supply is available for the central Run HEM / Results page.")
else:
    st.info("No energy supply is currently saved.")

with st.expander("Developer/debug: view saved energy supply", expanded=False):
    st.json(st.session_state.get("energy_supply", {}))
""",
)


replace_once(
    "ui/utils/full_case_builder.py",
    """def apply_gains_controls_to_case(hem_input: dict, gains_controls: dict) -> dict:
    if not isinstance(gains_controls, dict):
        return hem_input

    for section_name in ["InternalGains", "ApplianceGains", "Events", "Control"]:
        section_value = gains_controls.get(section_name)

        if isinstance(section_value, dict):
            hem_input[section_name] = deepcopy(section_value)

    return hem_input
""",
    """def apply_gains_controls_to_case(hem_input: dict, gains_controls: dict) -> dict:
    if not isinstance(gains_controls, dict):
        return hem_input

    for section_name in ["InternalGains", "ApplianceGains", "Events", "Control"]:
        section_value = gains_controls.get(section_name)

        if isinstance(section_value, dict):
            hem_input[section_name] = deepcopy(section_value)

    return hem_input


def apply_energy_supply_to_case(hem_input: dict, energy_supply: dict) -> dict:
    if isinstance(energy_supply, dict) and energy_supply:
        hem_input["EnergySupply"] = deepcopy(energy_supply)

    return hem_input
""",
)


replace_once(
    "ui/utils/full_case_builder.py",
    """    gains_controls = project_sections.get("gains_controls", {})
""",
    """    gains_controls = project_sections.get("gains_controls", {})
    energy_supply = project_sections.get("energy_supply", {})
""",
)


replace_once(
    "ui/utils/full_case_builder.py",
    """    hem_input = apply_gains_controls_to_case(
        hem_input=hem_input,
        gains_controls=gains_controls,
    )

    save_json(output_json_path, hem_input)
""",
    """    hem_input = apply_gains_controls_to_case(
        hem_input=hem_input,
        gains_controls=gains_controls,
    )

    hem_input = apply_energy_supply_to_case(
        hem_input=hem_input,
        energy_supply=energy_supply,
    )

    save_json(output_json_path, hem_input)
""",
)


replace_once(
    "ui/utils/project_validation.py",
    """    section_checks = {
        "space_heat_systems": "Heating systems",
        "hot_water": "Hot water",
        "gains_controls": "Internal gains, controls and events",
    }
""",
    """    section_checks = {
        "space_heat_systems": "Heating systems",
        "hot_water": "Hot water",
        "gains_controls": "Internal gains, controls and events",
        "energy_supply": "Energy supply",
    }
""",
)


replace_once(
    "ui/pages/9_Run_HEM_Results.py",
    """gains_controls = project_data.get("gains_controls", {})
""",
    """gains_controls = project_data.get("gains_controls", {})
energy_supply = project_data.get("energy_supply", {})
""",
)


replace_once(
    "ui/pages/9_Run_HEM_Results.py",
    """col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
""",
    """col1, col2, col3, col4, col5, col6, col7, col8 = st.columns(8)
""",
)


replace_once(
    "ui/pages/9_Run_HEM_Results.py",
    """with col7:
    st.metric(
        "Weather",
        "Yes" if weather_settings.get("weather_file") else "Default",
    )
""",
    """with col7:
    st.metric("Energy supply", "Yes" if energy_supply else "No")

with col8:
    st.metric(
        "Weather",
        "Yes" if weather_settings.get("weather_file") else "Default",
    )
""",
)


print("Batch N repair complete.")