from pathlib import Path


def write_file(path, content):
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"Updated {file_path}")


write_file(
    "ui/pages/7_Hot_Water.py",
    """
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
from hot_water_mapper import summarise_hot_water_inputs
from project_store import get_project_data_section, update_project_data


st.set_page_config(
    page_title="Hot Water",
    layout="wide",
)

st.title("Hot Water")

st.write(
    "Define the domestic hot water system using a system-first interface. "
    "The app can preserve the uploaded HEM hot-water model or generate common "
    "HEM-compatible hot-water systems from user-friendly inputs."
)

BASE_JSON_PATH = Path("ui/temp/active_hem_input.json")

if not BASE_JSON_PATH.exists():
    st.error(
        "No active HEM input found. Go to Project Setup and upload/load a HEM JSON first."
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


load_hot_water_defaults_into_state(force_reload=False)

hot_water_sections = st.session_state.get("hot_water_sections", {})
saved_form = get_project_data_section("hot_water_form", {}) or {}

system_options = [
    "Preserve uploaded HEM hot water",
    "Electric cylinder with immersion heater",
    "Storage cylinder heated by wet heat source",
    "Combi boiler hot water",
    "Point-of-use water heater",
    "Heat pump water heater",
    "HIU / heat network hot water",
]

default_system = saved_form.get(
    "hot_water_system_type",
    saved_form.get("mode", "Preserve uploaded HEM hot water"),
)

if default_system not in system_options:
    default_system = "Preserve uploaded HEM hot water"

st.header("1. Hot water system")

hot_water_system_type = st.radio(
    "Hot water system type",
    system_options,
    index=system_options.index(default_system),
)

use_form_hot_water = hot_water_system_type != "Preserve uploaded HEM hot water"

if not use_form_hot_water:
    st.info(
        "The generated HEM input will preserve the uploaded HotWaterSource, "
        "HotWaterDemand, ColdWaterSource, Events and Control sections."
    )
else:
    st.success(
        "The app will generate HEM-compatible hot-water sections for the selected system type."
    )

st.header("2. System details")

with st.form("hot_water_system_form"):
    common1, common2, common3 = st.columns(3)

    with common1:
        hot_water_source_name = st.text_input(
            "Hot water source name",
            value=saved_form.get("hot_water_source_name", saved_form.get("cylinder_name", "hw cylinder")),
        )

        cold_water_source_name = st.text_input(
            "Cold water source name",
            value=saved_form.get("cold_water_source_name", "mains water"),
        )

    with common2:
        min_temperature_c = st.number_input(
            "Minimum water temperature (degC)",
            min_value=0.0,
            max_value=90.0,
            value=float(saved_form.get("min_temperature_c", 52.0)),
            step=1.0,
        )

        max_temperature_c = st.number_input(
            "Setpoint / maximum water temperature (degC)",
            min_value=0.0,
            max_value=90.0,
            value=float(saved_form.get("max_temperature_c", 60.0)),
            step=1.0,
        )

    with common3:
        instant_shower_energy_supply = st.selectbox(
            "Instant shower energy supply",
            ["mains elec", "other"],
            index=0 if saved_form.get("instant_shower_energy_supply", "mains elec") == "mains elec" else 1,
        )

    # Defaults used by system-specific sections
    cylinder_volume_litres = float(saved_form.get("cylinder_volume_litres", 150.0))
    daily_losses_kwh = float(saved_form.get("daily_losses_kwh", 1.68))
    initial_temperature_c = float(saved_form.get("initial_temperature_c", 55.0))
    immersion_power_kw = float(saved_form.get("immersion_power_kw", 3.0))
    immersion_energy_supply = saved_form.get("immersion_energy_supply", "mains elec")
    heater_position = float(saved_form.get("heater_position", 0.1))
    thermostat_position = float(saved_form.get("thermostat_position", 0.33))
    linked_wet_heat_source_name = saved_form.get("linked_wet_heat_source_name", "heat_pump")
    wet_source_energy_supply = saved_form.get("wet_source_energy_supply", "mains elec")
    temp_flow_limit_upper = float(saved_form.get("temp_flow_limit_upper", 65.0))
    daily_hw_usage_litres = float(saved_form.get("daily_hw_usage_litres", 120.0))
    point_of_use_power_kw = float(saved_form.get("point_of_use_power_kw", 10.0))
    point_of_use_efficiency = float(saved_form.get("point_of_use_efficiency", 0.8))
    heat_pump_hw_power_kw = float(saved_form.get("heat_pump_hw_power_kw", 5.0))
    heat_pump_hw_cop = float(saved_form.get("heat_pump_hw_cop", 2.5))
    heat_exchanger_area_m2 = float(saved_form.get("heat_exchanger_area_m2", 1.5))
    heat_pump_hw_standby_kw = float(saved_form.get("heat_pump_hw_standby_kw", 0.02))
    in_use_factor_mismatch = float(saved_form.get("in_use_factor_mismatch", 0.6))

    if hot_water_system_type in [
        "Electric cylinder with immersion heater",
        "Storage cylinder heated by wet heat source",
        "Heat pump water heater",
    ]:
        st.subheader("Storage cylinder")

        s1, s2, s3 = st.columns(3)

        with s1:
            cylinder_volume_litres = st.number_input(
                "Cylinder volume (litres)",
                min_value=0.0,
                value=cylinder_volume_litres,
                step=5.0,
            )

            daily_losses_kwh = st.number_input(
                "Cylinder daily losses (kWh/day)",
                min_value=0.0,
                value=daily_losses_kwh,
                step=0.1,
            )

        with s2:
            initial_temperature_c = st.number_input(
                "Initial cylinder temperature (degC)",
                min_value=0.0,
                max_value=90.0,
                value=initial_temperature_c,
                step=1.0,
            )

            heater_position = st.number_input(
                "Heater position",
                min_value=0.0,
                max_value=1.0,
                value=heater_position,
                step=0.05,
            )

        with s3:
            thermostat_position = st.number_input(
                "Thermostat position",
                min_value=0.0,
                max_value=1.0,
                value=thermostat_position,
                step=0.05,
            )

    if hot_water_system_type == "Electric cylinder with immersion heater":
        st.subheader("Heat source: immersion heater")

        i1, i2 = st.columns(2)

        with i1:
            immersion_power_kw = st.number_input(
                "Immersion heater power (kW)",
                min_value=0.0,
                value=immersion_power_kw,
                step=0.5,
            )

        with i2:
            immersion_energy_supply = st.selectbox(
                "Immersion energy supply",
                ["mains elec", "other"],
                index=0 if immersion_energy_supply == "mains elec" else 1,
            )

    elif hot_water_system_type == "Storage cylinder heated by wet heat source":
        st.subheader("Heat source: linked wet heat source")

        w1, w2, w3 = st.columns(3)

        with w1:
            linked_wet_heat_source_name = st.text_input(
                "Linked HeatSourceWet name",
                value=linked_wet_heat_source_name,
                help="This should match a HeatSourceWet entry, e.g. heat_pump or boiler.",
            )

        with w2:
            wet_source_energy_supply = st.selectbox(
                "Wet source energy supply",
                ["mains elec", "mains gas", "heat network", "other"],
                index=0 if wet_source_energy_supply == "mains elec" else 1,
            )

        with w3:
            temp_flow_limit_upper = st.number_input(
                "Flow temperature upper limit (degC)",
                min_value=20.0,
                max_value=90.0,
                value=temp_flow_limit_upper,
                step=1.0,
            )

    elif hot_water_system_type == "Combi boiler hot water":
        st.subheader("System: combi boiler hot water")

        b1, b2, b3 = st.columns(3)

        with b1:
            linked_wet_heat_source_name = st.text_input(
                "Linked boiler HeatSourceWet name",
                value=saved_form.get("linked_wet_heat_source_name", "boiler"),
            )

        with b2:
            daily_hw_usage_litres = st.number_input(
                "Daily hot water usage (litres)",
                min_value=0.0,
                value=daily_hw_usage_litres,
                step=5.0,
            )

        with b3:
            separate_dhw_tests = st.selectbox(
                "Separate DHW test profile",
                ["M&L", "M", "L", "XL"],
                index=0,
            )

    elif hot_water_system_type == "Point-of-use water heater":
        st.subheader("System: point-of-use water heater")

        p1, p2, p3 = st.columns(3)

        with p1:
            point_of_use_power_kw = st.number_input(
                "Point-of-use heater power",
                min_value=0.0,
                value=point_of_use_power_kw,
                step=1.0,
            )

        with p2:
            point_of_use_efficiency = st.number_input(
                "Point-of-use efficiency",
                min_value=0.0,
                max_value=1.5,
                value=point_of_use_efficiency,
                step=0.05,
            )

        with p3:
            point_of_use_energy_supply = st.selectbox(
                "Point-of-use energy supply",
                ["mains elec", "other"],
                index=0 if saved_form.get("point_of_use_energy_supply", "mains elec") == "mains elec" else 1,
            )

    elif hot_water_system_type == "Heat pump water heater":
        st.subheader("System: heat pump water heater")

        hp1, hp2, hp3 = st.columns(3)

        with hp1:
            heat_pump_hw_power_kw = st.number_input(
                "Heat pump DHW power (kW)",
                min_value=0.0,
                value=heat_pump_hw_power_kw,
                step=0.5,
            )

            heat_pump_hw_cop = st.number_input(
                "DHW COP",
                min_value=0.0,
                value=heat_pump_hw_cop,
                step=0.1,
            )

        with hp2:
            heat_exchanger_area_m2 = st.number_input(
                "Heat exchanger area (m2)",
                min_value=0.0,
                value=heat_exchanger_area_m2,
                step=0.1,
            )

            heat_pump_hw_standby_kw = st.number_input(
                "Standby power (kW)",
                min_value=0.0,
                value=heat_pump_hw_standby_kw,
                step=0.01,
            )

        with hp3:
            heat_pump_hw_energy_supply = st.selectbox(
                "Heat pump energy supply",
                ["mains elec", "other"],
                index=0 if saved_form.get("heat_pump_hw_energy_supply", "mains elec") == "mains elec" else 1,
            )

            in_use_factor_mismatch = st.number_input(
                "In-use mismatch factor",
                min_value=0.0,
                max_value=2.0,
                value=in_use_factor_mismatch,
                step=0.1,
            )

    elif hot_water_system_type == "HIU / heat network hot water":
        st.subheader("System: HIU / heat network hot water")

        h1, h2 = st.columns(2)

        with h1:
            linked_wet_heat_source_name = st.text_input(
                "Linked heat network HeatSourceWet name",
                value=saved_form.get("linked_wet_heat_source_name", "HeatNetwork"),
            )

        with h2:
            daily_hw_usage_litres = st.number_input(
                "Indicative daily hot water usage (litres)",
                min_value=0.0,
                value=daily_hw_usage_litres,
                step=5.0,
            )

    st.header("3. Demand, outlets and distribution")

    d1, d2, d3 = st.columns(3)

    with d1:
        mixer_shower_flow_l_min = st.number_input(
            "Mixer shower flow rate (l/min)",
            min_value=0.0,
            value=float(saved_form.get("mixer_shower_flow_l_min", 8.0)),
            step=0.5,
        )

        instant_shower_power_kw = st.number_input(
            "Instant electric shower power (kW)",
            min_value=0.0,
            value=float(saved_form.get("instant_shower_power_kw", 9.0)),
            step=0.5,
        )

        shower_temperature_c = st.number_input(
            "Shower temperature (degC)",
            min_value=0.0,
            max_value=70.0,
            value=float(saved_form.get("shower_temperature_c", 41.0)),
            step=1.0,
        )

    with d2:
        bath_size_litres = st.number_input(
            "Bath size (litres)",
            min_value=0.0,
            value=float(saved_form.get("bath_size_litres", 100.0)),
            step=5.0,
        )

        bath_flow_l_min = st.number_input(
            "Bath flow rate (l/min)",
            min_value=0.0,
            value=float(saved_form.get("bath_flow_l_min", 8.0)),
            step=0.5,
        )

        bath_temperature_c = st.number_input(
            "Bath temperature (degC)",
            min_value=0.0,
            max_value=70.0,
            value=float(saved_form.get("bath_temperature_c", 41.0)),
            step=1.0,
        )

    with d3:
        other_flow_l_min = st.number_input(
            "Other draw-off flow rate (l/min)",
            min_value=0.0,
            value=float(saved_form.get("other_flow_l_min", 8.0)),
            step=0.5,
        )

        other_temperature_c = st.number_input(
            "Other draw-off temperature (degC)",
            min_value=0.0,
            max_value=70.0,
            value=float(saved_form.get("other_temperature_c", 41.0)),
            step=1.0,
        )

    pipe1, pipe2 = st.columns(2)

    with pipe1:
        internal_pipe_length_m = st.number_input(
            "Internal distribution pipe length (m)",
            min_value=0.0,
            value=float(saved_form.get("internal_pipe_length_m", 8.0)),
            step=0.5,
        )

        internal_pipe_diameter_mm = st.number_input(
            "Internal distribution pipe diameter (mm)",
            min_value=0.0,
            value=float(saved_form.get("internal_pipe_diameter_mm", 25.0)),
            step=1.0,
        )

    with pipe2:
        external_pipe_length_m = st.number_input(
            "External distribution pipe length (m)",
            min_value=0.0,
            value=float(saved_form.get("external_pipe_length_m", 8.0)),
            step=0.5,
        )

        external_pipe_diameter_mm = st.number_input(
            "External distribution pipe diameter (mm)",
            min_value=0.0,
            value=float(saved_form.get("external_pipe_diameter_mm", 25.0)),
            step=1.0,
        )

    with st.expander("Events and cold water profile", expanded=False):
        e1, e2, e3 = st.columns(3)

        with e1:
            ies_shower_start = st.number_input(
                "Instant shower start hour",
                min_value=0.0,
                max_value=24.0,
                value=float(saved_form.get("ies_shower_start", 6.0)),
                step=0.1,
            )

            ies_shower_duration_min = st.number_input(
                "Instant shower duration (min)",
                min_value=0.0,
                value=float(saved_form.get("ies_shower_duration_min", 6.0)),
                step=1.0,
            )

        with e2:
            mixer_shower_start = st.number_input(
                "Mixer shower start hour",
                min_value=0.0,
                max_value=24.0,
                value=float(saved_form.get("mixer_shower_start", 7.0)),
                step=0.1,
            )

            mixer_shower_duration_min = st.number_input(
                "Mixer shower duration (min)",
                min_value=0.0,
                value=float(saved_form.get("mixer_shower_duration_min", 6.0)),
                step=1.0,
            )

        with e3:
            bath_start = st.number_input(
                "Bath start hour",
                min_value=0.0,
                max_value=24.0,
                value=float(saved_form.get("bath_start", 6.0)),
                step=0.1,
            )

            bath_event_volume_litres = st.number_input(
                "Bath event volume (litres)",
                min_value=0.0,
                value=float(saved_form.get("bath_event_volume_litres", 73.0)),
                step=5.0,
            )

        cold_water_temperatures = st.text_area(
            "Cold water temperatures, comma separated",
            value=saved_form.get(
                "cold_water_temperatures",
                "10.0, 10.1, 10.2, 10.5, 10.6, 11.0, 11.5, 12.1",
            ),
            height=80,
        )

    save_form = st.form_submit_button("Save hot water system to project")

if save_form:
    hot_water_form = {
        "mode": hot_water_system_type,
        "use_form_hot_water": use_form_hot_water,
        "hot_water_system_type": hot_water_system_type,
        "hot_water_source_name": hot_water_source_name,
        "cylinder_name": hot_water_source_name,
        "cold_water_source_name": cold_water_source_name,
        "min_temperature_c": min_temperature_c,
        "max_temperature_c": max_temperature_c,
        "instant_shower_energy_supply": instant_shower_energy_supply,
        "cylinder_volume_litres": cylinder_volume_litres,
        "daily_losses_kwh": daily_losses_kwh,
        "initial_temperature_c": initial_temperature_c,
        "immersion_power_kw": immersion_power_kw,
        "immersion_energy_supply": immersion_energy_supply,
        "heater_position": heater_position,
        "thermostat_position": thermostat_position,
        "linked_wet_heat_source_name": linked_wet_heat_source_name,
        "wet_source_energy_supply": wet_source_energy_supply,
        "temp_flow_limit_upper": temp_flow_limit_upper,
        "daily_hw_usage_litres": daily_hw_usage_litres,
        "point_of_use_power_kw": point_of_use_power_kw,
        "point_of_use_efficiency": point_of_use_efficiency,
        "point_of_use_energy_supply": locals().get("point_of_use_energy_supply", "mains elec"),
        "heat_pump_hw_power_kw": heat_pump_hw_power_kw,
        "heat_pump_hw_cop": heat_pump_hw_cop,
        "heat_pump_hw_energy_supply": locals().get("heat_pump_hw_energy_supply", "mains elec"),
        "heat_exchanger_area_m2": heat_exchanger_area_m2,
        "heat_pump_hw_standby_kw": heat_pump_hw_standby_kw,
        "in_use_factor_mismatch": in_use_factor_mismatch,
        "separate_dhw_tests": locals().get("separate_dhw_tests", "M&L"),
        "mixer_shower_flow_l_min": mixer_shower_flow_l_min,
        "instant_shower_power_kw": instant_shower_power_kw,
        "shower_temperature_c": shower_temperature_c,
        "bath_size_litres": bath_size_litres,
        "bath_flow_l_min": bath_flow_l_min,
        "bath_temperature_c": bath_temperature_c,
        "other_flow_l_min": other_flow_l_min,
        "other_temperature_c": other_temperature_c,
        "internal_pipe_length_m": internal_pipe_length_m,
        "internal_pipe_diameter_mm": internal_pipe_diameter_mm,
        "external_pipe_length_m": external_pipe_length_m,
        "external_pipe_diameter_mm": external_pipe_diameter_mm,
        "ies_shower_start": ies_shower_start,
        "ies_shower_duration_min": ies_shower_duration_min,
        "mixer_shower_start": mixer_shower_start,
        "mixer_shower_duration_min": mixer_shower_duration_min,
        "bath_start": bath_start,
        "bath_event_volume_litres": bath_event_volume_litres,
        "bath_duration_min": 9.0,
        "other_start": 7.0,
        "other_duration_min": 1.0,
        "cold_water_temperatures": cold_water_temperatures,
        "min_control_name": "hw_min_temp_control",
        "max_control_name": "hw_max_temp_control",
    }

    update_project_data("hot_water_form", hot_water_form)
    st.success("Hot water system saved to the app project.")

st.header("4. Hot water system insight")

current_form = get_project_data_section("hot_water_form", {}) or {}
summary = summarise_hot_water_inputs(current_form)

m1, m2, m3, m4 = st.columns(4)

with m1:
    st.metric("System type", summary["system_type"])

with m2:
    st.metric("Cylinder volume", f"{summary['cylinder_volume']:.1f} litres")

with m3:
    st.metric("Daily losses", f"{summary['daily_losses']:.2f} kWh/day")

with m4:
    st.metric("Primary power", f"{summary['primary_power']:.1f} kW")

if summary["status"] == "OK":
    st.success("Hot water input check: OK")
else:
    st.info(summary["status"])

st.header("5. Uploaded HEM hot water summary")

section_summary = summarise_hot_water_sections(hot_water_sections)

s1, s2, s3 = st.columns(3)

with s1:
    st.metric("Hot water sources", section_summary["hot_water_source_count"])

with s2:
    st.metric("Demand groups", section_summary["hot_water_demand_count"])

with s3:
    st.metric("Cold water sources", section_summary["cold_water_source_count"])

with st.expander("Advanced: view / edit preserved HEM hot-water JSON", expanded=False):
    hot_water_json_text = st.text_area(
        "Hot-water HEM JSON",
        value=json.dumps(hot_water_sections, indent=2),
        height=520,
    )

    col_save, col_validate = st.columns(2)

    with col_validate:
        if st.button("Validate hot-water JSON"):
            try:
                parsed = json.loads(hot_water_json_text)
                if not isinstance(parsed, dict):
                    st.error("Hot-water JSON must be a JSON object/dictionary.")
                else:
                    st.success("Hot-water JSON is valid JSON.")
            except json.JSONDecodeError as exc:
                st.error("Hot-water JSON is not valid.")
                st.code(str(exc))

    with col_save:
        if st.button("Save preserved hot-water JSON to project"):
            try:
                parsed = json.loads(hot_water_json_text)
                if not isinstance(parsed, dict):
                    st.error("Hot-water JSON must be a JSON object/dictionary.")
                else:
                    st.session_state["hot_water_sections"] = parsed
                    update_project_data("hot_water", parsed)
                    st.success("Preserved HEM hot-water JSON saved.")
            except json.JSONDecodeError as exc:
                st.error("Hot-water JSON is not valid.")
                st.code(str(exc))

st.header("6. Project save status")

if current_form:
    st.success("Hot water system form is saved.")
else:
    st.info("Hot water system form is not saved yet.")

with st.expander("Developer/debug: view saved hot water data", expanded=False):
    st.subheader("Hot water form")
    st.json(get_project_data_section("hot_water_form", {}) or {})

    st.subheader("Preserved HEM hot water sections")
    st.json(st.session_state.get("hot_water_sections", {}))
""",
)

print("Batch W2 part 2 complete.")