from pathlib import Path


def write_file(path, content):
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"Updated {file_path}")


write_file(
    "ui/pages/6_Heating_Cooling_Systems.py",
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

from hem_extractors import (
    extract_space_heating_systems_from_hem,
    summarise_space_heating_systems,
)
from project_store import get_project_data_section, update_project_data


st.set_page_config(
    page_title="Heating & Cooling Systems",
    layout="wide",
)

st.title("Heating & Cooling Systems")

st.write(
    "Review and edit heating systems from the active HEM case, and record cooling "
    "system intent. Heating is currently connected to HEM through SpaceHeatSystem. "
    "Cooling will be written to HEM once a valid SpaceCoolSystem schema example is available."
)

BASE_JSON_PATH = Path("ui/temp/active_hem_input.json")

if not BASE_JSON_PATH.exists():
    st.error(
        "No active HEM input found. Go to Project Setup and upload/load a HEM JSON first."
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

st.header("1. Heating input source")

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

    h1, h2, h3 = st.columns(3)

    with h1:
        st.metric("Heating systems", len(summary_rows))

    with h2:
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

    with h3:
        rated_power_values = [
            row.get("rated_power")
            for row in summary_rows
            if row.get("rated_power") not in ["", None]
        ]
        st.metric(
            "Rated power entries",
            len(rated_power_values),
        )

else:
    st.info("No SpaceHeatSystem entries found in the active HEM case.")

st.subheader("Heating system editor")

st.caption(
    "Heating is currently schema-safe because the uploaded HEM SpaceHeatSystem "
    "JSON is preserved. Use the advanced editor only if you know the HEM schema."
)

heating_json_text = st.text_area(
    "SpaceHeatSystem JSON",
    value=json.dumps(space_heat_systems, indent=2),
    height=360,
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


st.header("3. Cooling systems")

st.info(
    "No SpaceCoolSystem section was found in the uploaded demo HEM JSON. "
    "Cooling settings below are saved in the app project for now, but are not "
    "yet written into the generated HEM JSON until a valid HEM cooling schema is confirmed."
)

saved_cooling = get_project_data_section("cooling_systems", {}) or {}

with st.form("cooling_placeholder_form"):
    c1, c2, c3 = st.columns(3)

    with c1:
        cooling_enabled = st.checkbox(
            "Cooling system present",
            value=bool(saved_cooling.get("cooling_enabled", False)),
        )

        cooling_type = st.selectbox(
            "Cooling system type",
            [
                "None",
                "Direct electric cooling",
                "Split air conditioner",
                "Reversible heat pump",
                "Chilled water / fan coil",
                "Other",
            ],
            index=[
                "None",
                "Direct electric cooling",
                "Split air conditioner",
                "Reversible heat pump",
                "Chilled water / fan coil",
                "Other",
            ].index(saved_cooling.get("cooling_type", "None"))
            if saved_cooling.get("cooling_type", "None")
            in [
                "None",
                "Direct electric cooling",
                "Split air conditioner",
                "Reversible heat pump",
                "Chilled water / fan coil",
                "Other",
            ]
            else 0,
        )

    with c2:
        cooling_capacity_kw = st.number_input(
            "Cooling capacity (kW)",
            min_value=0.0,
            value=float(saved_cooling.get("cooling_capacity_kw", 0.0)),
            step=0.5,
        )

        cooling_cop = st.number_input(
            "Cooling COP / EER",
            min_value=0.0,
            value=float(saved_cooling.get("cooling_cop", 3.0)),
            step=0.1,
        )

    with c3:
        cooling_setpoint_c = st.number_input(
            "Cooling setpoint (degC)",
            min_value=16.0,
            max_value=35.0,
            value=float(saved_cooling.get("cooling_setpoint_c", 26.0)),
            step=0.5,
        )

        cooling_energy_supply = st.selectbox(
            "Energy supply",
            ["mains elec", "other"],
            index=0
            if saved_cooling.get("cooling_energy_supply", "mains elec") == "mains elec"
            else 1,
        )

    cooling_notes = st.text_input(
        "Cooling notes",
        value=saved_cooling.get("cooling_notes", ""),
    )

    save_cooling = st.form_submit_button("Save cooling settings to project")

if save_cooling:
    cooling_data = {
        "cooling_enabled": cooling_enabled,
        "cooling_type": cooling_type,
        "cooling_capacity_kw": cooling_capacity_kw,
        "cooling_cop": cooling_cop,
        "cooling_setpoint_c": cooling_setpoint_c,
        "cooling_energy_supply": cooling_energy_supply,
        "cooling_notes": cooling_notes,
        "hem_connection_status": "not_written_until_space_cool_schema_confirmed",
    }

    update_project_data("cooling_systems", cooling_data)
    st.success("Cooling settings saved to the app project.")

st.header("4. Project save status")

status_col1, status_col2 = st.columns(2)

with status_col1:
    if st.session_state.get("space_heat_systems"):
        st.success("Heating systems are available for the central Run HEM / Results page.")
    else:
        st.info("No heating systems are currently saved.")

with status_col2:
    saved_cooling = get_project_data_section("cooling_systems", {}) or {}
    if saved_cooling:
        st.success("Cooling settings are saved in the app project.")
    else:
        st.info("No cooling settings are currently saved.")

with st.expander("Developer/debug: view saved heating and cooling data", expanded=False):
    st.subheader("Heating")
    st.json(st.session_state.get("space_heat_systems", {}))

    st.subheader("Cooling")
    st.json(get_project_data_section("cooling_systems", {}) or {})
""",
)


old_page = Path("ui/pages/6_Heating_Systems.py")
archived_page = Path("ui/archived_pages/6_Heating_Systems_old.py")
archived_page.parent.mkdir(parents=True, exist_ok=True)

if old_page.exists():
    archived_page.write_text(old_page.read_text(encoding="utf-8"), encoding="utf-8")
    old_page.unlink()
    print("Moved ui/pages/6_Heating_Systems.py to ui/archived_pages/6_Heating_Systems_old.py")


# Patch Run HEM Results to display cooling demand metric
run_page = Path("ui/pages/10_Run_HEM_Results.py")
text = run_page.read_text(encoding="utf-8")

old = """                    col1, col2, col3, col4 = st.columns(4)
"""

new = """                    col1, col2, col3, col4, col5 = st.columns(5)
"""

if old in text:
    text = text.replace(old, new, 1)

old = """                    peak_elec = next(
                        item
                        for item in comparison
                        if item["metric"] == "Peak electricity consumption"
                    )
"""

new = """                    space_cool = next(
                        item
                        for item in comparison
                        if item["metric"] == "Space cool demand"
                    )

                    peak_elec = next(
                        item
                        for item in comparison
                        if item["metric"] == "Peak electricity consumption"
                    )
"""

if old in text:
    text = text.replace(old, new, 1)

old = """                    with col2:
                        st.metric(
                            "Peak electricity",
                            f"{format_number(peak_elec['generated_value'])} {peak_elec['unit']}",
                            f"{format_number(peak_elec['difference'])} {peak_elec['unit']}",
                        )

                    with col3:
                        st.metric(
                            "Delivered energy",
                            f"{format_number(delivered['generated_value'])} {delivered['unit']}",
                            f"{format_number(delivered['difference'])} {delivered['unit']}",
                        )

                    with col4:
                        st.metric(
                            "Mechanical ventilation",
                            f"{format_number(mech_vent['generated_value'])} {mech_vent['unit']}",
                            f"{format_number(mech_vent['difference'])} {mech_vent['unit']}",
                        )
"""

new = """                    with col2:
                        st.metric(
                            "Space cool demand",
                            f"{format_number(space_cool['generated_value'])} {space_cool['unit']}",
                            f"{format_number(space_cool['difference'])} {space_cool['unit']}",
                        )

                    with col3:
                        st.metric(
                            "Peak electricity",
                            f"{format_number(peak_elec['generated_value'])} {peak_elec['unit']}",
                            f"{format_number(peak_elec['difference'])} {peak_elec['unit']}",
                        )

                    with col4:
                        st.metric(
                            "Delivered energy",
                            f"{format_number(delivered['generated_value'])} {delivered['unit']}",
                            f"{format_number(delivered['difference'])} {delivered['unit']}",
                        )

                    with col5:
                        st.metric(
                            "Mechanical ventilation",
                            f"{format_number(mech_vent['generated_value'])} {mech_vent['unit']}",
                            f"{format_number(mech_vent['difference'])} {mech_vent['unit']}",
                        )
"""

if old in text:
    text = text.replace(old, new, 1)

run_page.write_text(text, encoding="utf-8")
print("Patched ui/pages/10_Run_HEM_Results.py for cooling metric")

print("Batch S complete.")