import json
import sys
from pathlib import Path

import streamlit as st

CURRENT_DIR = Path(__file__).resolve().parent
UI_DIR = CURRENT_DIR.parent
UTILS_DIR = UI_DIR / "utils"
sys.path.append(str(UTILS_DIR))

from hem_extractors import (
    extract_hot_water_sections_from_hem,
    summarise_hot_water_sections,
)
from project_store import get_project_data_section, update_project_data


st.set_page_config(
    page_title="Hot Water",
    layout="wide",
)

st.title("Hot Water")

st.write(
    "Review and edit the hot water sections loaded from the active HEM case. "
    "For this first connected version, the official HEM JSON structure is preserved. "
    "Later, this can be converted into simplified hot-water input forms."
)

BASE_JSON_PATH = Path("ui/temp/active_hem_input.json")

if not BASE_JSON_PATH.exists():
    st.error(
        "No active HEM input found. Go to the Home page and upload/load a HEM JSON first."
    )
    st.stop()


def load_hot_water_defaults_into_state(force_reload: bool = False) -> None:
    already_loaded = st.session_state.get("hot_water_defaults_loaded", False)

    if already_loaded and not force_reload:
        return

    project_hot_water = get_project_data_section("hot_water", None)

    if project_hot_water and not force_reload:
        st.session_state["hot_water_sections"] = project_hot_water
    else:
        st.session_state["hot_water_sections"] = extract_hot_water_sections_from_hem(
            BASE_JSON_PATH
        )

    st.session_state["hot_water_defaults_loaded"] = True


def clear_hot_water_state() -> None:
    for key in [
        "hot_water_sections",
        "hot_water_defaults_loaded",
    ]:
        if key in st.session_state:
            del st.session_state[key]


load_hot_water_defaults_into_state(force_reload=False)

st.header("1. Input source")

col1, col2 = st.columns(2)

with col1:
    if st.button("Restore hot water sections from uploaded HEM JSON"):
        load_hot_water_defaults_into_state(force_reload=True)
        update_project_data("hot_water", st.session_state["hot_water_sections"])
        st.success("Hot water sections restored from uploaded HEM JSON.")
        st.rerun()

with col2:
    if st.button("Clear hot water sections"):
        clear_hot_water_state()
        update_project_data("hot_water", {})
        st.warning("Hot water sections cleared. The uploaded HEM case is still loaded.")
        st.rerun()

hot_water_sections = st.session_state.get("hot_water_sections", {})

st.header("2. Hot water summary")

summary = summarise_hot_water_sections(hot_water_sections)

c1, c2, c3 = st.columns(3)

with c1:
    st.metric("Hot water sources", summary["hot_water_source_count"])

with c2:
    st.metric("Hot water demand entries", summary["hot_water_demand_count"])

with c3:
    st.metric("Cold water sources", summary["cold_water_source_count"])

st.header("3. Edit hot-water JSON")

st.caption(
    "This editor preserves the official HEM HotWaterSource, HotWaterDemand and "
    "ColdWaterSource structure. Only edit this JSON if you know the HEM schema."
)

hot_water_json_text = st.text_area(
    "Hot water JSON",
    value=json.dumps(hot_water_sections, indent=2),
    height=520,
)

col_save, col_validate = st.columns(2)

with col_validate:
    if st.button("Validate hot-water JSON"):
        try:
            parsed = json.loads(hot_water_json_text)
            if not isinstance(parsed, dict):
                st.error("Hot water JSON must be a JSON object/dictionary.")
            else:
                st.success("Hot water JSON is valid JSON.")
        except json.JSONDecodeError as exc:
            st.error("Hot water JSON is not valid.")
            st.code(str(exc))

with col_save:
    if st.button("Save hot water to project"):
        try:
            parsed = json.loads(hot_water_json_text)
            if not isinstance(parsed, dict):
                st.error("Hot water JSON must be a JSON object/dictionary.")
            else:
                st.session_state["hot_water_sections"] = parsed
                update_project_data("hot_water", parsed)
                st.success("Hot water sections saved to the app project.")
        except json.JSONDecodeError as exc:
            st.error("Hot water JSON is not valid.")
            st.code(str(exc))

st.header("4. Project save status")

if st.session_state.get("hot_water_sections"):
    st.success("Hot water sections are available for the central Run HEM / Results page.")
else:
    st.info("No hot water sections are currently saved.")

with st.expander("Developer/debug: view saved hot water sections", expanded=False):
    st.json(st.session_state.get("hot_water_sections", {}))
