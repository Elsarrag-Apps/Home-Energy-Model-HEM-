import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

CURRENT_DIR = Path(__file__).resolve().parent
UI_DIR = CURRENT_DIR.parent
UTILS_DIR = UI_DIR / "utils"
sys.path.append(str(UTILS_DIR))

from hvac_mapper import summarise_cooling_inputs, summarise_heating_inputs
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
    "Configure heating and cooling using user-friendly forms. Advanced HEM JSON "
    "is still available for schema inspection, but normal users should use the form inputs."
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


load_hvac_defaults_into_state(force_reload=False)

project_setup = get_project_data_section("project_setup", {}) or {}
floor_area = float(project_setup.get("floor_area_m2", 0) or 0)

space_heat_systems = st.session_state.get("space_heat_systems", {})
heat_source_wet = st.session_state.get("heat_source_wet", {})
saved_heating_form = get_project_data_section("heating_form", {}) or {}

st.header("1. Heating system input mode")

heating_mode_options = [
    "Preserve uploaded HEM heating",
    "Direct electric heater",
    "Wet central heating - boiler",
    "Wet central heating - heat pump",
]

default_mode = saved_heating_form.get(
    "heating_mode",
    "Preserve uploaded HEM heating",
)

input_mode = st.radio(
    "How should heating be defined in the generated HEM input?",
    heating_mode_options,
    index=heating_mode_options.index(default_mode)
    if default_mode in heating_mode_options
    else 0,
    horizontal=False,
)

use_form_heating = input_mode != "Preserve uploaded HEM heating"

if not use_form_heating:
    st.info(
        "The generated HEM file will preserve the uploaded SpaceHeatSystem and HeatSourceWet "
        "sections. Use this when the uploaded case already contains the correct detailed HEM heating model."
    )
else:
    st.success(
        "Form-based heating is enabled. The app will generate SpaceHeatSystem, HeatSourceWet "
        "where needed, Control, and Zone heating references."
    )

st.header("2. Heating system form")

with st.form("heating_form"):
    c1, c2, c3 = st.columns(3)

    with c1:
        rated_power_kw = st.number_input(
            "Rated heating capacity (kW)",
            min_value=0.0,
            value=float(saved_heating_form.get("rated_power_kw", 6.0)),
            step=0.5,
        )

        heating_setpoint_c = st.number_input(
            "Heating setpoint (degC)",
            min_value=5.0,
            max_value=35.0,
            value=float(saved_heating_form.get("heating_setpoint_c", 21.0)),
            step=0.5,
        )

        frac_convective = st.number_input(
            "Convective fraction",
            min_value=0.0,
            max_value=1.0,
            value=float(saved_heating_form.get("frac_convective", 0.7 if "Wet" in input_mode else 0.4)),
            step=0.05,
        )

    with c2:
        if input_mode == "Direct electric heater":
            direct_electric_energy_supply = st.selectbox(
                "Energy supply",
                ["mains elec", "other"],
                index=0,
            )

            heat_pump_nominal_cop = 0.0
            boiler_efficiency_full_load = 0.0
            boiler_efficiency_part_load = 0.0
            boiler_energy_supply = "mains gas"
            aux_energy_supply = "mains elec"

        elif input_mode == "Wet central heating - boiler":
            boiler_energy_supply = st.selectbox(
                "Boiler fuel / energy supply",
                ["mains gas", "mains elec", "heat network", "other"],
                index=0,
            )

            aux_energy_supply = st.selectbox(
                "Auxiliary energy supply",
                ["mains elec", "other"],
                index=0,
            )

            boiler_efficiency_full_load = st.number_input(
                "Boiler full-load efficiency",
                min_value=0.0,
                max_value=1.5,
                value=float(saved_heating_form.get("boiler_efficiency_full_load", 0.891)),
                step=0.01,
            )

            boiler_efficiency_part_load = st.number_input(
                "Boiler part-load efficiency",
                min_value=0.0,
                max_value=1.5,
                value=float(saved_heating_form.get("boiler_efficiency_part_load", 0.991)),
                step=0.01,
            )

            direct_electric_energy_supply = "mains elec"
            heat_pump_nominal_cop = 0.0

        elif input_mode == "Wet central heating - heat pump":
            heat_pump_energy_supply = st.selectbox(
                "Heat pump energy supply",
                ["mains elec", "other"],
                index=0,
            )

            heat_pump_source_type = st.selectbox(
                "Heat pump source type",
                ["OutsideAir", "Ground", "Water"],
                index=0,
            )

            heat_pump_nominal_cop = st.number_input(
                "Nominal COP",
                min_value=0.1,
                value=float(saved_heating_form.get("heat_pump_nominal_cop", 3.2)),
                step=0.1,
            )

            temp_lower_operating_limit = st.number_input(
                "Lower operating limit (degC)",
                value=float(saved_heating_form.get("temp_lower_operating_limit", -10.0)),
                step=1.0,
            )

            direct_electric_energy_supply = "mains elec"
            boiler_energy_supply = "mains gas"
            aux_energy_supply = "mains elec"
            boiler_efficiency_full_load = 0.0
            boiler_efficiency_part_load = 0.0

        else:
            direct_electric_energy_supply = "mains elec"
            heat_pump_nominal_cop = 0.0
            boiler_efficiency_full_load = 0.0
            boiler_efficiency_part_load = 0.0
            boiler_energy_supply = "mains gas"
            aux_energy_supply = "mains elec"

    with c3:
        if "Wet central heating" in input_mode:
            wet_emitter_type = st.selectbox(
                "Emitter type",
                ["radiator", "underfloor", "fan_coil"],
                index=0,
            )

            design_flow_temp = st.number_input(
                "Design flow temperature (degC)",
                min_value=20.0,
                max_value=80.0,
                value=float(saved_heating_form.get("design_flow_temp", 45.0)),
                step=1.0,
            )

            temp_diff_emit_dsgn = st.number_input(
                "Emitter design delta-T (K)",
                min_value=1.0,
                max_value=30.0,
                value=float(saved_heating_form.get("temp_diff_emit_dsgn", 5.0)),
                step=1.0,
            )

            variable_flow = st.checkbox(
                "Variable flow",
                value=bool(saved_heating_form.get("variable_flow", True)),
            )

        else:
            wet_emitter_type = "radiator"
            design_flow_temp = 45.0
            temp_diff_emit_dsgn = 5.0
            variable_flow = True

    with st.expander("Advanced wet distribution settings", expanded=False):
        a1, a2, a3 = st.columns(3)

        with a1:
            min_flow_rate = st.number_input(
                "Minimum flow rate",
                min_value=0.0,
                value=float(saved_heating_form.get("min_flow_rate", 2.4)),
                step=0.1,
            )

            max_flow_rate = st.number_input(
                "Maximum flow rate",
                min_value=0.0,
                value=float(saved_heating_form.get("max_flow_rate", 14.0)),
                step=0.5,
            )

        with a2:
            emitter_c = st.number_input(
                "Emitter coefficient c",
                min_value=0.0,
                value=float(saved_heating_form.get("emitter_c", 0.02)),
                step=0.005,
                format="%.3f",
            )

            emitter_n = st.number_input(
                "Emitter exponent n",
                min_value=0.0,
                value=float(saved_heating_form.get("emitter_n", 1.33)),
                step=0.01,
            )

        with a3:
            thermal_mass = st.number_input(
                "Distribution thermal mass",
                min_value=0.0,
                value=float(saved_heating_form.get("thermal_mass", 0.019)),
                step=0.001,
                format="%.3f",
            )

            temp_setback = st.number_input(
                "Setback temperature (degC)",
                min_value=0.0,
                max_value=30.0,
                value=float(saved_heating_form.get("temp_setback", 18.0)),
                step=0.5,
            )

    save_heating_form = st.form_submit_button("Save heating form to project")

if save_heating_form:
    heating_data = {
        "use_form_heating": use_form_heating,
        "heating_mode": input_mode,
        "rated_power_kw": rated_power_kw,
        "heating_setpoint_c": heating_setpoint_c,
        "frac_convective": frac_convective,
        "direct_electric_energy_supply": direct_electric_energy_supply,
        "boiler_energy_supply": boiler_energy_supply,
        "aux_energy_supply": aux_energy_supply,
        "boiler_efficiency_full_load": boiler_efficiency_full_load,
        "boiler_efficiency_part_load": boiler_efficiency_part_load,
        "heat_pump_energy_supply": locals().get("heat_pump_energy_supply", "mains elec"),
        "heat_pump_source_type": locals().get("heat_pump_source_type", "OutsideAir"),
        "heat_pump_nominal_cop": heat_pump_nominal_cop,
        "temp_lower_operating_limit": locals().get("temp_lower_operating_limit", -10.0),
        "wet_emitter_type": wet_emitter_type,
        "design_flow_temp": design_flow_temp,
        "temp_diff_emit_dsgn": temp_diff_emit_dsgn,
        "variable_flow": variable_flow,
        "min_flow_rate": min_flow_rate,
        "max_flow_rate": max_flow_rate,
        "emitter_c": emitter_c,
        "emitter_n": emitter_n,
        "thermal_mass": thermal_mass,
        "temp_setback": temp_setback,
        "hem_system_name": "space_heat_system_1" if "Wet" in input_mode else "main",
        "hem_heat_source_name": "heat_pump" if input_mode == "Wet central heating - heat pump" else "boiler",
        "hem_control_name": "heating_system_1_control",
        "zone_name": "zone 1",
    }

    update_project_data("heating_form", heating_data)
    st.success("Heating form saved to the app project.")

st.subheader("Heating input insight")

current_heating_form = get_project_data_section("heating_form", {}) or {}
heating_summary = summarise_heating_inputs(current_heating_form, floor_area_m2=floor_area)

hi1, hi2, hi3, hi4 = st.columns(4)

with hi1:
    st.metric("Heating mode", heating_summary["mode"])

with hi2:
    st.metric("Heating capacity", f"{heating_summary['capacity_kw']:.2f} kW")

with hi3:
    st.metric("Capacity intensity", f"{heating_summary['capacity_w_m2']:.1f} W/m2")

with hi4:
    st.metric("Efficiency / COP", str(heating_summary["efficiency"]))

if heating_summary["status"] == "OK":
    st.success("Heating input check: OK")
else:
    st.info(heating_summary["status"])

st.header("3. Existing HEM heating model summary")

summary_rows = summarise_space_heating_systems(space_heat_systems)
heat_source_rows = summarise_heat_source_wet(heat_source_wet)

tab_summary_heat, tab_summary_source = st.tabs(["SpaceHeatSystem", "HeatSourceWet"])

with tab_summary_heat:
    if summary_rows:
        st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No SpaceHeatSystem entries found in the active HEM case.")

with tab_summary_source:
    if heat_source_rows:
        st.dataframe(pd.DataFrame(heat_source_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No HeatSourceWet entries found. This is normal for direct electric heating.")

st.header("4. Cooling systems")

saved_cooling = get_project_data_section("cooling_systems", {}) or {}

cooling_type_options = [
    "None",
    "Direct electric cooling",
    "Split air conditioner",
    "Reversible heat pump",
    "Chilled water / fan coil",
    "Other",
]

with st.form("cooling_form"):
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

        cooling_frac_convective = st.number_input(
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
            "Cooling energy supply",
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
        "frac_convective": cooling_frac_convective,
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

st.header("5. Advanced HEM JSON")

with st.expander("Advanced: view / edit preserved HEM heating JSON", expanded=False):
    tab_space_heat, tab_heat_source = st.tabs(["SpaceHeatSystem", "HeatSourceWet"])

    with tab_space_heat:
        heating_json_text = st.text_area(
            "SpaceHeatSystem JSON",
            value=json.dumps(space_heat_systems, indent=2),
            height=300,
        )

        if st.button("Save advanced SpaceHeatSystem JSON"):
            try:
                parsed = json.loads(heating_json_text)
                if not isinstance(parsed, dict):
                    st.error("SpaceHeatSystem JSON must be a dictionary.")
                else:
                    st.session_state["space_heat_systems"] = parsed
                    update_project_data("space_heat_systems", parsed)
                    st.success("Advanced SpaceHeatSystem saved.")
            except json.JSONDecodeError as exc:
                st.error("Invalid JSON.")
                st.code(str(exc))

    with tab_heat_source:
        heat_source_json_text = st.text_area(
            "HeatSourceWet JSON",
            value=json.dumps(heat_source_wet, indent=2),
            height=300,
        )

        if st.button("Save advanced HeatSourceWet JSON"):
            try:
                parsed = json.loads(heat_source_json_text)
                if not isinstance(parsed, dict):
                    st.error("HeatSourceWet JSON must be a dictionary.")
                else:
                    st.session_state["heat_source_wet"] = parsed
                    update_project_data("heat_source_wet", parsed)
                    st.success("Advanced HeatSourceWet saved.")
            except json.JSONDecodeError as exc:
                st.error("Invalid JSON.")
                st.code(str(exc))

st.header("6. Project save status")

status_col1, status_col2, status_col3 = st.columns(3)

with status_col1:
    if current_heating_form:
        st.success("Heating form is saved.")
    else:
        st.info("Heating form not saved yet.")

with status_col2:
    if current_cooling:
        st.success("Cooling settings are saved.")
    else:
        st.info("Cooling settings not saved yet.")

with status_col3:
    st.info("Advanced HEM JSON remains available for expert review.")

with st.expander("Developer/debug: view saved HVAC data", expanded=False):
    st.subheader("Heating form")
    st.json(get_project_data_section("heating_form", {}) or {})

    st.subheader("SpaceHeatSystem")
    st.json(st.session_state.get("space_heat_systems", {}))

    st.subheader("HeatSourceWet")
    st.json(st.session_state.get("heat_source_wet", {}))

    st.subheader("Cooling")
    st.json(get_project_data_section("cooling_systems", {}) or {})
