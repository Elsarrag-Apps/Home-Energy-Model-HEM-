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
