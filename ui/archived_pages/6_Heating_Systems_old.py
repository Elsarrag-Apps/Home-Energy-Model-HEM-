import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

CURRENT_DIR = Path(__file__).resolve().parent
UI_DIR = CURRENT_DIR.parent
UTILS_DIR = UI_DIR / "utils"
sys.path.append(str(UTILS_DIR))

from hem_extractors import (
    extract_space_heating_systems_from_hem,
    summarise_space_heating_systems,
)
from project_store import get_project_data_section, update_project_data


st.set_page_config(
    page_title="Heating Systems",
    layout="wide",
)

st.title("Heating Systems")

st.write(
    "Review and edit the space heating systems loaded from the active HEM case. "
    "For this first connected version, the HEM heating-system JSON is preserved "
    "and can be edited directly. Later, this will be simplified into user-friendly "
    "heating-system forms."
)

BASE_JSON_PATH = Path("ui/temp/active_hem_input.json")

if not BASE_JSON_PATH.exists():
    st.error(
        "No active HEM input found. Go to the Home page and upload/load a HEM JSON first."
    )
    st.stop()


def load_heating_defaults_into_state(force_reload: bool = False) -> None:
    already_loaded = st.session_state.get("heating_defaults_loaded", False)

    if already_loaded and not force_reload:
        return

    project_systems = get_project_data_section("space_heat_systems", None)

    if project_systems and not force_reload:
        st.session_state["space_heat_systems"] = project_systems
    else:
        st.session_state["space_heat_systems"] = extract_space_heating_systems_from_hem(
            BASE_JSON_PATH
        )

    st.session_state["heating_defaults_loaded"] = True


def clear_heating_state() -> None:
    for key in [
        "space_heat_systems",
        "heating_defaults_loaded",
    ]:
        if key in st.session_state:
            del st.session_state[key]


load_heating_defaults_into_state(force_reload=False)

st.header("1. Input source")

col1, col2 = st.columns(2)

with col1:
    if st.button("Restore heating systems from uploaded HEM JSON"):
        load_heating_defaults_into_state(force_reload=True)
        update_project_data("space_heat_systems", st.session_state["space_heat_systems"])
        st.success("Heating systems restored from uploaded HEM JSON.")
        st.rerun()

with col2:
    if st.button("Clear heating systems"):
        clear_heating_state()
        update_project_data("space_heat_systems", {})
        st.warning("Heating systems cleared. The uploaded HEM case is still loaded.")
        st.rerun()

space_heat_systems = st.session_state.get("space_heat_systems", {})

st.header("2. Heating system summary")

summary_rows = summarise_space_heating_systems(space_heat_systems)

if summary_rows:
    st.dataframe(
        pd.DataFrame(summary_rows),
        use_container_width=True,
        hide_index=True,
    )

    s1, s2 = st.columns(2)

    with s1:
        st.metric("Heating systems", len(summary_rows))

    with s2:
        main_types = ", ".join(
            sorted(
                {
                    str(row.get("type", "Unknown"))
                    for row in summary_rows
                    if row.get("type")
                }
            )
        )
        st.metric("Detected system types", main_types or "Unknown")

else:
    st.info("No SpaceHeatSystem entries found in the active HEM case.")

st.header("3. Edit heating-system JSON")

st.caption(
    "This editor preserves the official HEM SpaceHeatSystem structure. "
    "Only edit this JSON if you know the HEM schema. A simplified heating form "
    "will be added in a later batch."
)

heating_json_text = st.text_area(
    "SpaceHeatSystem JSON",
    value=json.dumps(space_heat_systems, indent=2),
    height=450,
)

col_save, col_validate = st.columns(2)

with col_validate:
    if st.button("Validate heating JSON"):
        try:
            parsed = json.loads(heating_json_text)
            if not isinstance(parsed, dict):
                st.error("Heating JSON must be a JSON object/dictionary.")
            else:
                st.success("Heating JSON is valid JSON.")
        except json.JSONDecodeError as exc:
            st.error("Heating JSON is not valid.")
            st.code(str(exc))

with col_save:
    if st.button("Save heating systems to project"):
        try:
            parsed = json.loads(heating_json_text)
            if not isinstance(parsed, dict):
                st.error("Heating JSON must be a JSON object/dictionary.")
            else:
                st.session_state["space_heat_systems"] = parsed
                update_project_data("space_heat_systems", parsed)
                st.success("Heating systems saved to the app project.")
        except json.JSONDecodeError as exc:
            st.error("Heating JSON is not valid.")
            st.code(str(exc))

st.header("4. Project save status")

if st.session_state.get("space_heat_systems"):
    st.success("Heating systems are available for the central Run HEM / Results page.")
else:
    st.info("No heating systems are currently saved.")

with st.expander("Developer/debug: view saved heating systems", expanded=False):
    st.json(st.session_state.get("space_heat_systems", {}))
