from pathlib import Path


def write_file(path, content):
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"Updated {file_path}")


# Add heat source extractors
hem_extractors_path = Path("ui/utils/hem_extractors.py")
text = hem_extractors_path.read_text(encoding="utf-8")

if "def extract_heat_source_wet_from_hem" not in text:
    text += """

def extract_heat_source_wet_from_hem(hem_json_path: Path) -> dict:
    \"\"\"Extract HeatSourceWet from uploaded HEM JSON.\"\"\"
    hem_input = load_json_file(hem_json_path)
    return hem_input.get("HeatSourceWet", {})


def summarise_heat_source_wet(heat_source_wet: dict) -> list[dict]:
    \"\"\"Create a summary table for HEM HeatSourceWet entries.\"\"\"
    rows = []

    for name, source in (heat_source_wet or {}).items():
        if not isinstance(source, dict):
            continue

        source_type = source.get("type", "Unknown")

        row = {
            "name": name,
            "type": source_type,
            "energy_supply": source.get("EnergySupply", ""),
            "aux_energy_supply": source.get("EnergySupply_aux", ""),
            "rated_power": source.get(
                "rated_power",
                source.get("power_max", source.get("rated_charge_power", "")),
            ),
            "efficiency_or_cop": "",
            "notes": "",
        }

        if source_type == "Boiler":
            row["efficiency_or_cop"] = source.get("efficiency_full_load", "")
            row["notes"] = f"Part-load efficiency: {source.get('efficiency_part_load', '')}"

        elif source_type == "HeatPump":
            test_data = source.get("test_data_EN14825", [])
            if test_data:
                cops = [
                    item.get("cop")
                    for item in test_data
                    if isinstance(item, dict) and item.get("cop") is not None
                ]
                capacities = [
                    item.get("capacity")
                    for item in test_data
                    if isinstance(item, dict) and item.get("capacity") is not None
                ]

                if cops:
                    row["efficiency_or_cop"] = round(sum(cops) / len(cops), 2)

                if capacities:
                    row["rated_power"] = max(capacities)

                row["notes"] = f"EN14825 points: {len(test_data)}"

            row["aux_energy_supply"] = "mains elec"

        elif source_type == "HIU":
            row["rated_power"] = source.get("power_max", "")
            row["notes"] = f"Daily loss: {source.get('HIU_daily_loss', '')}"

        elif source_type == "HeatBattery":
            row["rated_power"] = source.get("rated_charge_power", "")
            row["notes"] = f"Battery type: {source.get('battery_type', '')}"

        rows.append(row)

    return rows
"""

hem_extractors_path.write_text(text, encoding="utf-8")
print("Patched ui/utils/hem_extractors.py")


# Patch full_case_builder.py
full_case_path = Path("ui/utils/full_case_builder.py")
text = full_case_path.read_text(encoding="utf-8")

if "def apply_heat_source_wet_to_case" not in text:
    marker = """def apply_space_heating_to_case(hem_input: dict, space_heat_systems: dict) -> dict:
    if isinstance(space_heat_systems, dict) and space_heat_systems:
        hem_input["SpaceHeatSystem"] = deepcopy(space_heat_systems)

    return hem_input
"""

    replacement = marker + """

def apply_heat_source_wet_to_case(hem_input: dict, heat_source_wet: dict) -> dict:
    \"\"\"Apply saved HeatSourceWet dictionary to a HEM input.\"\"\"
    if isinstance(heat_source_wet, dict) and heat_source_wet:
        hem_input["HeatSourceWet"] = deepcopy(heat_source_wet)

    return hem_input
"""

    if marker not in text:
        raise RuntimeError("Could not find apply_space_heating_to_case in full_case_builder.py")

    text = text.replace(marker, replacement, 1)

if 'heat_source_wet = project_sections.get("heat_source_wet", {})' not in text:
    text = text.replace(
        '    space_heat_systems = project_sections.get("space_heat_systems", {})\n',
        '    space_heat_systems = project_sections.get("space_heat_systems", {})\n    heat_source_wet = project_sections.get("heat_source_wet", {})\n',
        1,
    )

if "hem_input = apply_heat_source_wet_to_case(" not in text:
    text = text.replace(
        """    hem_input = apply_space_heating_to_case(
        hem_input=hem_input,
        space_heat_systems=space_heat_systems,
    )
""",
        """    hem_input = apply_space_heating_to_case(
        hem_input=hem_input,
        space_heat_systems=space_heat_systems,
    )

    hem_input = apply_heat_source_wet_to_case(
        hem_input=hem_input,
        heat_source_wet=heat_source_wet,
    )
""",
        1,
    )

full_case_path.write_text(text, encoding="utf-8")
print("Patched ui/utils/full_case_builder.py")


# Patch validation
validation_path = Path("ui/utils/project_validation.py")
text = validation_path.read_text(encoding="utf-8")

if '"heat_source_wet": "Wet heat sources"' not in text:
    text = text.replace(
        '''        "space_heat_systems": "Heating systems",
''',
        '''        "space_heat_systems": "Heating systems",
        "heat_source_wet": "Wet heat sources",
''',
        1,
    )

validation_path.write_text(text, encoding="utf-8")
print("Patched ui/utils/project_validation.py")


# Rewrite Heating & Cooling page with HeatSourceWet support while keeping existing cooling UI
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

from hvac_mapper import summarise_cooling_inputs
from hem_extractors import (
    extract_heat_source_wet_from_hem,
    extract_space_heating_systems_from_hem,
    summarise_heat_source_wet,
    summarise_space_heating_systems,
)
from project_store import get_project_data_section, update_project_data


st.set_page_config(
    page_title="Heating & Cooling Systems",
    layout="wide",
)

st.title("Heating & Cooling Systems")

st.write(
    "Review heating distribution systems, wet heat sources and active cooling. "
    "Heating is handled through SpaceHeatSystem and, where applicable, HeatSourceWet. "
    "Cooling is mapped to HEM using the validated SpaceCoolSystem AirConditioning pattern."
)

BASE_JSON_PATH = Path("ui/temp/active_hem_input.json")

if not BASE_JSON_PATH.exists():
    st.error(
        "No active HEM input found. Go to Project Setup and upload/load a HEM JSON first."
    )
    st.stop()


def load_hvac_defaults_into_state(force_reload: bool = False) -> None:
    already_loaded = st.session_state.get("hvac_defaults_loaded", False)

    if already_loaded and not force_reload:
        return

    project_space_heat = get_project_data_section("space_heat_systems", None)
    project_heat_source_wet = get_project_data_section("heat_source_wet", None)

    if project_space_heat and not force_reload:
        st.session_state["space_heat_systems"] = project_space_heat
    else:
        st.session_state["space_heat_systems"] = extract_space_heating_systems_from_hem(
            BASE_JSON_PATH
        )

    if project_heat_source_wet and not force_reload:
        st.session_state["heat_source_wet"] = project_heat_source_wet
    else:
        st.session_state["heat_source_wet"] = extract_heat_source_wet_from_hem(
            BASE_JSON_PATH
        )

    st.session_state["hvac_defaults_loaded"] = True
    st.session_state["heating_defaults_loaded"] = True


def clear_heating_state() -> None:
    for key in [
        "space_heat_systems",
        "heat_source_wet",
        "hvac_defaults_loaded",
        "heating_defaults_loaded",
    ]:
        if key in st.session_state:
            del st.session_state[key]


load_hvac_defaults_into_state(force_reload=False)

st.header("1. Heating input source")

col1, col2 = st.columns(2)

with col1:
    if st.button("Restore heating systems and wet heat sources from uploaded HEM JSON"):
        load_hvac_defaults_into_state(force_reload=True)
        update_project_data("space_heat_systems", st.session_state["space_heat_systems"])
        update_project_data("heat_source_wet", st.session_state["heat_source_wet"])
        st.success("Heating systems and wet heat sources restored from uploaded HEM JSON.")
        st.rerun()

with col2:
    if st.button("Clear heating systems and wet heat sources"):
        clear_heating_state()
        update_project_data("space_heat_systems", {})
        update_project_data("heat_source_wet", {})
        st.warning("Heating systems cleared. The uploaded HEM case is still loaded.")
        st.rerun()

space_heat_systems = st.session_state.get("space_heat_systems", {})
heat_source_wet = st.session_state.get("heat_source_wet", {})

st.header("2. Heating system summary")

summary_rows = summarise_space_heating_systems(space_heat_systems)

if summary_rows:
    st.subheader("SpaceHeatSystem / distribution systems")

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
        st.metric("Distribution/system types", main_types or "Unknown")

    with h3:
        wet_count = sum(
            1
            for row in summary_rows
            if str(row.get("type", "")).lower() == "wetdistribution"
        )
        st.metric("Wet distribution systems", wet_count)

else:
    st.info("No SpaceHeatSystem entries found in the active HEM case.")

heat_source_rows = summarise_heat_source_wet(heat_source_wet)

st.subheader("HeatSourceWet / wet heat generators")

if heat_source_rows:
    st.dataframe(
        pd.DataFrame(heat_source_rows),
        use_container_width=True,
        hide_index=True,
    )

    hs1, hs2, hs3 = st.columns(3)

    with hs1:
        st.metric("Wet heat sources", len(heat_source_rows))

    with hs2:
        heat_source_types = ", ".join(
            sorted(
                {
                    str(row.get("type", "Unknown"))
                    for row in heat_source_rows
                    if row.get("type")
                }
            )
        )
        st.metric("Heat source types", heat_source_types or "Unknown")

    with hs3:
        hp_count = sum(
            1
            for row in heat_source_rows
            if str(row.get("type", "")).lower() == "heatpump"
        )
        st.metric("Heat pumps", hp_count)

else:
    st.info(
        "No HeatSourceWet entries found in the active HEM case. "
        "This is normal for direct electric heating cases."
    )

st.header("3. Heating advanced JSON editors")

st.caption(
    "These editors preserve the official HEM SpaceHeatSystem and HeatSourceWet structures. "
    "Use them only if you know the HEM schema. A form-based heating generator will be added next."
)

tab_space_heat, tab_heat_source = st.tabs(["SpaceHeatSystem", "HeatSourceWet"])

with tab_space_heat:
    heating_json_text = st.text_area(
        "SpaceHeatSystem JSON",
        value=json.dumps(space_heat_systems, indent=2),
        height=360,
    )

    col_save, col_validate = st.columns(2)

    with col_validate:
        if st.button("Validate SpaceHeatSystem JSON"):
            try:
                parsed = json.loads(heating_json_text)
                if not isinstance(parsed, dict):
                    st.error("SpaceHeatSystem JSON must be a JSON object/dictionary.")
                else:
                    st.success("SpaceHeatSystem JSON is valid JSON.")
            except json.JSONDecodeError as exc:
                st.error("SpaceHeatSystem JSON is not valid.")
                st.code(str(exc))

    with col_save:
        if st.button("Save SpaceHeatSystem to project"):
            try:
                parsed = json.loads(heating_json_text)
                if not isinstance(parsed, dict):
                    st.error("SpaceHeatSystem JSON must be a JSON object/dictionary.")
                else:
                    st.session_state["space_heat_systems"] = parsed
                    update_project_data("space_heat_systems", parsed)
                    st.success("SpaceHeatSystem saved to the app project.")
            except json.JSONDecodeError as exc:
                st.error("SpaceHeatSystem JSON is not valid.")
                st.code(str(exc))

with tab_heat_source:
    heat_source_json_text = st.text_area(
        "HeatSourceWet JSON",
        value=json.dumps(heat_source_wet, indent=2),
        height=360,
    )

    col_save_hs, col_validate_hs = st.columns(2)

    with col_validate_hs:
        if st.button("Validate HeatSourceWet JSON"):
            try:
                parsed = json.loads(heat_source_json_text)
                if not isinstance(parsed, dict):
                    st.error("HeatSourceWet JSON must be a JSON object/dictionary.")
                else:
                    st.success("HeatSourceWet JSON is valid JSON.")
            except json.JSONDecodeError as exc:
                st.error("HeatSourceWet JSON is not valid.")
                st.code(str(exc))

    with col_save_hs:
        if st.button("Save HeatSourceWet to project"):
            try:
                parsed = json.loads(heat_source_json_text)
                if not isinstance(parsed, dict):
                    st.error("HeatSourceWet JSON must be a JSON object/dictionary.")
                else:
                    st.session_state["heat_source_wet"] = parsed
                    update_project_data("heat_source_wet", parsed)
                    st.success("HeatSourceWet saved to the app project.")
            except json.JSONDecodeError as exc:
                st.error("HeatSourceWet JSON is not valid.")
                st.code(str(exc))

st.header("4. Cooling systems")

st.info(
    "Cooling is connected using the HEM AirConditioning SpaceCoolSystem schema. "
    "The generated HEM file will include SpaceCoolSystem, a cooling control, and a "
    "Zone reference when cooling is enabled."
)

saved_cooling = get_project_data_section("cooling_systems", {}) or {}

cooling_type_options = [
    "None",
    "Direct electric cooling",
    "Split air conditioner",
    "Reversible heat pump",
    "Chilled water / fan coil",
    "Other",
]

with st.form("cooling_placeholder_form"):
    c1, c2, c3 = st.columns(3)

    with c1:
        cooling_enabled = st.checkbox(
            "Cooling system present",
            value=bool(saved_cooling.get("cooling_enabled", False)),
        )

        cooling_type = st.selectbox(
            "Cooling system type",
            cooling_type_options,
            index=cooling_type_options.index(saved_cooling.get("cooling_type", "None"))
            if saved_cooling.get("cooling_type", "None") in cooling_type_options
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

        frac_convective = st.number_input(
            "Cooling convective fraction",
            min_value=0.0,
            max_value=1.0,
            value=float(saved_cooling.get("frac_convective", 0.95)),
            step=0.05,
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
        "frac_convective": frac_convective,
        "cooling_setpoint_c": cooling_setpoint_c,
        "cooling_energy_supply": cooling_energy_supply,
        "cooling_notes": cooling_notes,
        "hem_system_name": "cooling system 1",
        "hem_control_name": "cooling_system_1_control",
        "hem_connection_status": "written_to_space_cool_system_when_enabled",
    }

    update_project_data("cooling_systems", cooling_data)
    st.success("Cooling settings saved to the app project.")

st.subheader("Cooling input insight")

current_cooling = get_project_data_section("cooling_systems", {}) or {}
project_setup = get_project_data_section("project_setup", {}) or {}
floor_area = float(project_setup.get("floor_area_m2", 0) or 0)
cooling_summary = summarise_cooling_inputs(current_cooling, floor_area_m2=floor_area)

ci1, ci2, ci3, ci4 = st.columns(4)

with ci1:
    st.metric("Cooling enabled", "Yes" if cooling_summary["enabled"] else "No")

with ci2:
    st.metric("Cooling capacity", f"{cooling_summary['capacity_kw']:.2f} kW")

with ci3:
    st.metric("Cooling COP/EER", f"{cooling_summary['cop']:.2f}")

with ci4:
    st.metric("Capacity intensity", f"{cooling_summary['capacity_w_m2']:.1f} W/m2")

if cooling_summary["status"] == "OK":
    st.success("Cooling input check: OK")
else:
    st.warning(cooling_summary["status"])

st.header("5. Project save status")

status_col1, status_col2, status_col3 = st.columns(3)

with status_col1:
    if st.session_state.get("space_heat_systems"):
        st.success("SpaceHeatSystem is available for the central Run HEM / Results page.")
    else:
        st.info("No SpaceHeatSystem is currently saved.")

with status_col2:
    if st.session_state.get("heat_source_wet"):
        st.success("HeatSourceWet is available for the central Run HEM / Results page.")
    else:
        st.info("No HeatSourceWet is currently saved.")

with status_col3:
    saved_cooling = get_project_data_section("cooling_systems", {}) or {}
    if saved_cooling:
        st.success("Cooling settings are saved in the app project.")
    else:
        st.info("No cooling settings are currently saved.")

with st.expander("Developer/debug: view saved HVAC data", expanded=False):
    st.subheader("SpaceHeatSystem")
    st.json(st.session_state.get("space_heat_systems", {}))

    st.subheader("HeatSourceWet")
    st.json(st.session_state.get("heat_source_wet", {}))

    st.subheader("Cooling")
    st.json(get_project_data_section("cooling_systems", {}) or {})
""",
)


# Patch Run HEM results summary status
run_page = Path("ui/pages/10_Run_HEM_Results.py")
text = run_page.read_text(encoding="utf-8")

if 'heat_source_wet = project_data.get("heat_source_wet", {})' not in text:
    text = text.replace(
        'space_heat_systems = project_data.get("space_heat_systems", {})\n',
        'space_heat_systems = project_data.get("space_heat_systems", {})\nheat_source_wet = project_data.get("heat_source_wet", {})\n',
        1,
    )

if 'st.metric("Heat sources", len(heat_source_wet)' not in text:
    text = text.replace(
        '''with col4:
    st.metric(
        "Heating",
        len(space_heat_systems) if isinstance(space_heat_systems, dict) else 0,
    )

with col5:
    st.metric("Hot water", "Yes" if hot_water else "No")
''',
        '''with col4:
    st.metric(
        "Heating",
        len(space_heat_systems) if isinstance(space_heat_systems, dict) else 0,
    )

with col5:
    st.metric(
        "Heat sources",
        len(heat_source_wet) if isinstance(heat_source_wet, dict) else 0,
    )
''',
        1,
    )

    text = text.replace(
        '''with col6:
    st.metric("Gains/controls", "Yes" if gains_controls else "No")
''',
        '''with col6:
    st.metric("Hot water", "Yes" if hot_water else "No")
''',
        1,
    )

    text = text.replace(
        '''with col7:
    st.metric("Energy supply", "Yes" if energy_supply else "No")
''',
        '''with col7:
    st.metric("Gains/controls", "Yes" if gains_controls else "No")
''',
        1,
    )

    text = text.replace(
        '''with col8:
    st.metric(
        "Weather",
        "Yes" if weather_settings.get("weather_file") else "Default",
    )
''',
        '''with col8:
    st.metric("Energy supply", "Yes" if energy_supply else "No")
''',
        1,
    )

run_page.write_text(text, encoding="utf-8")
print("Patched ui/pages/10_Run_HEM_Results.py")


print("Batch V1 complete.")