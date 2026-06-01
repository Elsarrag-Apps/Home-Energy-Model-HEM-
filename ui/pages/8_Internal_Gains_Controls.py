import json
import sys
from pathlib import Path

import streamlit as st

CURRENT_DIR = Path(__file__).resolve().parent
UI_DIR = CURRENT_DIR.parent
UTILS_DIR = UI_DIR / "utils"
sys.path.append(str(UTILS_DIR))

from hem_extractors import (
    extract_gains_controls_sections_from_hem,
    summarise_gains_controls_sections,
)
from project_store import get_project_data_section, update_project_data


st.set_page_config(
    page_title="Internal Gains & Controls",
    layout="wide",
)

st.title("Internal Gains, Appliances, Controls & Events")

st.write(
    "Review and edit the internal gains, appliance gains, controls and events "
    "loaded from the active HEM case. For this first connected version, the "
    "official HEM JSON structure is preserved."
)

BASE_JSON_PATH = Path("ui/temp/active_hem_input.json")

if not BASE_JSON_PATH.exists():
    st.error(
        "No active HEM input found. Go to the Home page and upload/load a HEM JSON first."
    )
    st.stop()


def load_gains_controls_defaults_into_state(force_reload: bool = False) -> None:
    already_loaded = st.session_state.get("gains_controls_defaults_loaded", False)

    if already_loaded and not force_reload:
        return

    project_sections = get_project_data_section("gains_controls", None)

    if project_sections and not force_reload:
        st.session_state["gains_controls_sections"] = project_sections
    else:
        st.session_state["gains_controls_sections"] = extract_gains_controls_sections_from_hem(
            BASE_JSON_PATH
        )

    st.session_state["gains_controls_defaults_loaded"] = True


def clear_gains_controls_state() -> None:
    for key in [
        "gains_controls_sections",
        "gains_controls_defaults_loaded",
    ]:
        if key in st.session_state:
            del st.session_state[key]


load_gains_controls_defaults_into_state(force_reload=False)

st.header("1. Input source")

col1, col2 = st.columns(2)

with col1:
    if st.button("Restore gains and controls from uploaded HEM JSON"):
        load_gains_controls_defaults_into_state(force_reload=True)
        update_project_data(
            "gains_controls",
            st.session_state["gains_controls_sections"],
        )
        st.success("Gains and controls restored from uploaded HEM JSON.")
        st.rerun()

with col2:
    if st.button("Clear gains and controls"):
        clear_gains_controls_state()
        update_project_data("gains_controls", {})
        st.warning("Gains and controls cleared. The uploaded HEM case is still loaded.")
        st.rerun()

gains_controls_sections = st.session_state.get("gains_controls_sections", {})

st.header("2. Section summary")

summary = summarise_gains_controls_sections(gains_controls_sections)

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("Internal gains", summary["internal_gain_count"])

with c2:
    st.metric("Appliance gains", summary["appliance_gain_count"])

with c3:
    st.metric("Events", summary["event_count"])

with c4:
    st.metric("Controls", summary["control_count"])

st.header("3. Edit gains and controls JSON")

st.caption(
    "This editor preserves the official HEM InternalGains, ApplianceGains, Events "
    "and Control structure. Only edit this JSON if you know the HEM schema."
)

gains_json_text = st.text_area(
    "Gains, controls and events JSON",
    value=json.dumps(gains_controls_sections, indent=2),
    height=560,
)

col_save, col_validate = st.columns(2)

with col_validate:
    if st.button("Validate gains and controls JSON"):
        try:
            parsed = json.loads(gains_json_text)
            if not isinstance(parsed, dict):
                st.error("Gains and controls JSON must be a JSON object/dictionary.")
            else:
                st.success("Gains and controls JSON is valid JSON.")
        except json.JSONDecodeError as exc:
            st.error("Gains and controls JSON is not valid.")
            st.code(str(exc))

with col_save:
    if st.button("Save gains and controls to project"):
        try:
            parsed = json.loads(gains_json_text)
            if not isinstance(parsed, dict):
                st.error("Gains and controls JSON must be a JSON object/dictionary.")
            else:
                st.session_state["gains_controls_sections"] = parsed
                update_project_data("gains_controls", parsed)
                st.success("Gains and controls saved to the app project.")
        except json.JSONDecodeError as exc:
            st.error("Gains and controls JSON is not valid.")
            st.code(str(exc))

st.header("4. Project save status")

if st.session_state.get("gains_controls_sections"):
    st.success(
        "Gains, controls and events are available for the central Run HEM / Results page."
    )
else:
    st.info("No gains and controls are currently saved.")

with st.expander("Developer/debug: view saved gains and controls", expanded=False):
    st.json(st.session_state.get("gains_controls_sections", {}))
