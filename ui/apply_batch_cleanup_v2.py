from pathlib import Path


def write_file(path, content):
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"Updated {file_path}")


write_file(
    "ui/utils/hvac_mapper.py",
    """
from copy import deepcopy


def safe_float(value, default=0.0):
    try:
        if value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in ["true", "yes", "1", "y"]


def build_heating_control_from_app(heating_data: dict) -> dict:
    if not isinstance(heating_data, dict):
        return {}

    if not heating_data.get("use_form_heating", False):
        return {}

    control_name = heating_data.get("hem_control_name", "heating_system_1_control")
    setpoint = safe_float(heating_data.get("heating_setpoint_c"), 21.0)

    return {
        control_name: {
            "type": "SetpointTimeControl",
            "start_day": 0,
            "time_series_step": 1,
            "schedule": {
                "main": [
                    {
                        "repeat": 8760,
                        "value": setpoint,
                    }
                ]
            },
        }
    }


def build_boiler_heat_source(heating_data: dict) -> dict:
    source_name = heating_data.get("hem_heat_source_name", "boiler")

    return {
        source_name: {
            "type": "Boiler",
            "EnergySupply": heating_data.get("boiler_energy_supply", "mains gas"),
            "EnergySupply_aux": heating_data.get("aux_energy_supply", "mains elec"),
            "rated_power": safe_float(heating_data.get("rated_power_kw"), 24.0),
            "efficiency_full_load": safe_float(
                heating_data.get("boiler_efficiency_full_load"), 0.891
            ),
            "efficiency_part_load": safe_float(
                heating_data.get("boiler_efficiency_part_load"), 0.991
            ),
            "boiler_location": heating_data.get("boiler_location", "internal"),
            "modulation_load": safe_float(heating_data.get("modulation_load"), 0.3),
            "electricity_circ_pump": safe_float(
                heating_data.get("electricity_circ_pump"), 0.06
            ),
            "electricity_part_load": safe_float(
                heating_data.get("electricity_part_load"), 0.0131
            ),
            "electricity_full_load": safe_float(
                heating_data.get("electricity_full_load"), 0.0388
            ),
            "electricity_standby": safe_float(
                heating_data.get("electricity_standby"), 0.0244
            ),
        }
    }


def build_heat_pump_heat_source(heating_data: dict) -> dict:
    source_name = heating_data.get("hem_heat_source_name", "heat_pump")
    nominal_capacity = safe_float(heating_data.get("rated_power_kw"), 5.5)
    nominal_cop = safe_float(heating_data.get("heat_pump_nominal_cop"), 3.2)

    # Valid EN14825-style template based on inspected HEM examples.
    # The UI exposes key user inputs and keeps the detailed test points safe.
    test_data = [
        {
            "capacity": nominal_capacity,
            "cop": max(1.0, nominal_cop * 0.75),
            "design_flow_temp": 35,
            "temp_outlet": 34.0,
            "temp_source": -7.0,
            "temp_test": -7.0,
            "test_letter": "A",
        },
        {
            "capacity": nominal_capacity * 0.6,
            "cop": nominal_cop,
            "design_flow_temp": 35,
            "temp_outlet": 30.0,
            "temp_source": 2.0,
            "temp_test": 2.0,
            "test_letter": "B",
        },
        {
            "capacity": nominal_capacity * 0.58,
            "cop": nominal_cop * 1.25,
            "design_flow_temp": 35,
            "temp_outlet": 27.0,
            "temp_source": 7.0,
            "temp_test": 7.0,
            "test_letter": "C",
        },
        {
            "capacity": nominal_capacity * 0.6,
            "cop": nominal_cop * 1.45,
            "design_flow_temp": 35,
            "temp_outlet": 24.0,
            "temp_source": 12.0,
            "temp_test": 12.0,
            "test_letter": "D",
        },
        {
            "capacity": nominal_capacity,
            "cop": max(1.0, nominal_cop * 0.75),
            "design_flow_temp": 35,
            "temp_outlet": 34.0,
            "temp_source": -7.0,
            "temp_test": -7.0,
            "test_letter": "F",
        },
        {
            "capacity": nominal_capacity * 0.96,
            "cop": max(1.0, nominal_cop * 0.62),
            "design_flow_temp": 55,
            "temp_outlet": 52.0,
            "temp_source": -7.0,
            "temp_test": -7.0,
            "test_letter": "A",
        },
        {
            "capacity": nominal_capacity * 0.6,
            "cop": max(1.0, nominal_cop * 0.85),
            "design_flow_temp": 55,
            "temp_outlet": 42.0,
            "temp_source": 2.0,
            "temp_test": 2.0,
            "test_letter": "B",
        },
        {
            "capacity": nominal_capacity * 0.55,
            "cop": nominal_cop,
            "design_flow_temp": 55,
            "temp_outlet": 36.0,
            "temp_source": 7.0,
            "temp_test": 7.0,
            "test_letter": "C",
        },
        {
            "capacity": nominal_capacity * 0.6,
            "cop": nominal_cop * 1.25,
            "design_flow_temp": 55,
            "temp_outlet": 30.0,
            "temp_source": 12.0,
            "temp_test": 12.0,
            "test_letter": "D",
        },
        {
            "capacity": nominal_capacity * 0.96,
            "cop": max(1.0, nominal_cop * 0.62),
            "design_flow_temp": 55,
            "temp_outlet": 52.0,
            "temp_source": -7.0,
            "temp_test": -7.0,
            "test_letter": "F",
        },
    ]

    return {
        source_name: {
            "type": "HeatPump",
            "EnergySupply": heating_data.get("heat_pump_energy_supply", "mains elec"),
            "source_type": heating_data.get("heat_pump_source_type", "OutsideAir"),
            "sink_type": "Water",
            "backup_ctrl_type": "None",
            "min_modulation_rate_35": safe_float(
                heating_data.get("min_modulation_rate_35"), 0.35
            ),
            "min_modulation_rate_55": safe_float(
                heating_data.get("min_modulation_rate_55"), 0.35
            ),
            "min_temp_diff_flow_return_for_hp_to_operate": 0,
            "modulating_control": True,
            "power_crankcase_heater": 0.0,
            "power_heating_circ_pump": safe_float(
                heating_data.get("power_heating_circ_pump"), 0.014
            ),
            "power_heating_warm_air_fan": None,
            "power_max_backup": None,
            "power_off": 0.0,
            "power_source_circ_pump": 0.0,
            "power_standby": 0.0,
            "temp_lower_operating_limit": safe_float(
                heating_data.get("temp_lower_operating_limit"), -10.0
            ),
            "temp_return_feed_max": safe_float(
                heating_data.get("temp_return_feed_max"), 70.0
            ),
            "test_data_EN14825": test_data,
            "time_constant_onoff_operation": 140,
            "time_delay_backup": 1,
            "var_flow_temp_ctrl_during_test": True,
        }
    }


def build_wet_distribution_system(heating_data: dict) -> dict:
    system_name = heating_data.get("hem_system_name", "space_heat_system_1")
    control_name = heating_data.get("hem_control_name", "heating_system_1_control")
    source_name = heating_data.get("hem_heat_source_name", "heat_pump")
    zone_name = heating_data.get("zone_name", "zone 1")

    emitter_type = heating_data.get("wet_emitter_type", "radiator")

    return {
        system_name: {
            "type": "WetDistribution",
            "HeatSource": {
                "name": source_name,
                "temp_flow_limit_upper": safe_float(
                    heating_data.get("temp_flow_limit_upper"), 65.0
                ),
            },
            "Control": control_name,
            "Zone": zone_name,
            "advanced_start": safe_float(heating_data.get("advanced_start"), 2),
            "design_flow_temp": safe_float(heating_data.get("design_flow_temp"), 45.0),
            "ecodesign_controller": {
                "ecodesign_control_class": int(
                    safe_float(heating_data.get("ecodesign_control_class"), 2)
                ),
                "max_outdoor_temp": safe_float(
                    heating_data.get("max_outdoor_temp"), 20.0
                ),
                "min_flow_temp": safe_float(heating_data.get("min_flow_temp"), 30.0),
                "min_outdoor_temp": safe_float(
                    heating_data.get("min_outdoor_temp"), 0.0
                ),
            },
            "pipework": [],
            "emitters": [
                {
                    "wet_emitter_type": emitter_type,
                    "c": safe_float(heating_data.get("emitter_c"), 0.02),
                    "n": safe_float(heating_data.get("emitter_n"), 1.33),
                    "frac_convective": safe_float(
                        heating_data.get("frac_convective"), 0.7
                    ),
                }
            ],
            "max_flow_rate": safe_float(heating_data.get("max_flow_rate"), 14.0),
            "min_flow_rate": safe_float(heating_data.get("min_flow_rate"), 2.4),
            "temp_diff_emit_dsgn": safe_float(
                heating_data.get("temp_diff_emit_dsgn"), 5.0
            ),
            "temp_setback": safe_float(heating_data.get("temp_setback"), 18.0),
            "thermal_mass": safe_float(heating_data.get("thermal_mass"), 0.019),
            "variable_flow": safe_bool(heating_data.get("variable_flow"), True),
        }
    }


def build_direct_electric_heating_system(heating_data: dict) -> dict:
    system_name = heating_data.get("hem_system_name", "main")
    control_name = heating_data.get("hem_control_name", "heating_system_1_control")
    zone_name = heating_data.get("zone_name", "zone 1")

    return {
        system_name: {
            "type": "InstantElecHeater",
            "rated_power": safe_float(heating_data.get("rated_power_kw"), 6.0),
            "frac_convective": safe_float(heating_data.get("frac_convective"), 0.4),
            "Control": control_name,
            "EnergySupply": heating_data.get("direct_electric_energy_supply", "mains elec"),
            "Zone": zone_name,
        }
    }


def build_heating_from_app(heating_data: dict) -> tuple[dict, dict, dict]:
    if not isinstance(heating_data, dict):
        return {}, {}, {}

    if not heating_data.get("use_form_heating", False):
        return {}, {}, {}

    heating_mode = heating_data.get("heating_mode", "Preserve uploaded HEM heating")

    controls = build_heating_control_from_app(heating_data)

    if heating_mode == "Direct electric heater":
        return build_direct_electric_heating_system(heating_data), {}, controls

    if heating_mode == "Wet central heating - boiler":
        heat_source = build_boiler_heat_source(heating_data)
        space_heat = build_wet_distribution_system(heating_data)
        return space_heat, heat_source, controls

    if heating_mode == "Wet central heating - heat pump":
        heat_source = build_heat_pump_heat_source(heating_data)
        space_heat = build_wet_distribution_system(heating_data)
        return space_heat, heat_source, controls

    return {}, {}, {}


def apply_form_heating_to_hem_input(
    hem_input: dict,
    heating_data: dict,
    zone_name: str = "zone 1",
) -> dict:
    space_heat, heat_source_wet, controls = build_heating_from_app(heating_data)

    if not space_heat:
        return hem_input

    hem_input["SpaceHeatSystem"] = space_heat

    if heat_source_wet:
        hem_input["HeatSourceWet"] = heat_source_wet
    elif "HeatSourceWet" in hem_input:
        # Direct electric heating does not need HeatSourceWet.
        del hem_input["HeatSourceWet"]

    if "Control" not in hem_input or not isinstance(hem_input["Control"], dict):
        hem_input["Control"] = {}

    hem_input["Control"].update(controls)

    if "Zone" in hem_input and isinstance(hem_input["Zone"], dict):
        if zone_name not in hem_input["Zone"]:
            zone_name = next(iter(hem_input["Zone"].keys()))

        system_name = next(iter(space_heat.keys()))
        hem_input["Zone"][zone_name]["SpaceHeatSystem"] = system_name

    return hem_input


def summarise_heating_inputs(heating_data: dict, floor_area_m2: float | None = None) -> dict:
    if not isinstance(heating_data, dict) or not heating_data.get("use_form_heating"):
        return {
            "enabled": False,
            "mode": "Preserve uploaded HEM heating",
            "capacity_kw": 0.0,
            "capacity_w_m2": 0.0,
            "efficiency": "",
            "status": "Using uploaded/preserved HEM heating JSON",
        }

    mode = heating_data.get("heating_mode", "Unknown")
    capacity_kw = safe_float(heating_data.get("rated_power_kw"), 0.0)

    capacity_w_m2 = 0.0
    if floor_area_m2 and floor_area_m2 > 0:
        capacity_w_m2 = capacity_kw * 1000 / floor_area_m2

    if mode == "Wet central heating - boiler":
        efficiency = safe_float(heating_data.get("boiler_efficiency_full_load"), 0.0)
    elif mode == "Wet central heating - heat pump":
        efficiency = safe_float(heating_data.get("heat_pump_nominal_cop"), 0.0)
    else:
        efficiency = "1.0"

    status = "OK"
    if capacity_kw <= 0:
        status = "Heating capacity must be greater than zero."
    elif capacity_w_m2 > 250:
        status = "Heating capacity intensity appears high. Check units."
    elif capacity_w_m2 < 20 and capacity_w_m2 > 0:
        status = "Heating capacity intensity appears low. Check design intent."

    return {
        "enabled": True,
        "mode": mode,
        "capacity_kw": capacity_kw,
        "capacity_w_m2": capacity_w_m2,
        "efficiency": efficiency,
        "status": status,
    }


def build_space_cool_system_from_app(cooling_data: dict) -> dict:
    if not isinstance(cooling_data, dict):
        return {}

    if not cooling_data.get("cooling_enabled", False):
        return {}

    cooling_type = cooling_data.get("cooling_type", "None")

    if cooling_type in ["None", "", None]:
        return {}

    system_name = cooling_data.get("hem_system_name", "cooling system 1")
    control_name = cooling_data.get("hem_control_name", "cooling_system_1_control")

    capacity = safe_float(cooling_data.get("cooling_capacity_kw"), 0.0)
    efficiency = safe_float(cooling_data.get("cooling_cop"), 0.0)
    frac_convective = safe_float(cooling_data.get("frac_convective"), 0.95)
    energy_supply = cooling_data.get("cooling_energy_supply", "mains elec")

    if capacity <= 0 or efficiency <= 0:
        return {}

    return {
        system_name: {
            "type": "AirConditioning",
            "cooling_capacity": capacity,
            "efficiency": efficiency,
            "frac_convective": frac_convective,
            "EnergySupply": energy_supply,
            "Control": control_name,
        }
    }


def build_cooling_control_from_app(cooling_data: dict) -> dict:
    if not isinstance(cooling_data, dict):
        return {}

    if not cooling_data.get("cooling_enabled", False):
        return {}

    cooling_type = cooling_data.get("cooling_type", "None")

    if cooling_type in ["None", "", None]:
        return {}

    capacity = safe_float(cooling_data.get("cooling_capacity_kw"), 0.0)
    efficiency = safe_float(cooling_data.get("cooling_cop"), 0.0)

    if capacity <= 0 or efficiency <= 0:
        return {}

    control_name = cooling_data.get("hem_control_name", "cooling_system_1_control")
    setpoint = safe_float(cooling_data.get("cooling_setpoint_c"), 26.0)

    return {
        control_name: {
            "type": "SetpointTimeControl",
            "start_day": 0,
            "time_series_step": 1,
            "schedule": {
                "main": [
                    {
                        "repeat": 8760,
                        "value": setpoint,
                    }
                ]
            },
        }
    }


def apply_space_cooling_to_hem_input(
    hem_input: dict,
    cooling_data: dict,
    zone_name: str = "zone 1",
) -> dict:
    if not isinstance(cooling_data, dict):
        return hem_input

    space_cool_system = build_space_cool_system_from_app(cooling_data)

    if not space_cool_system:
        return hem_input

    cooling_controls = build_cooling_control_from_app(cooling_data)

    hem_input["SpaceCoolSystem"] = space_cool_system

    if "Control" not in hem_input or not isinstance(hem_input["Control"], dict):
        hem_input["Control"] = {}

    hem_input["Control"].update(cooling_controls)

    if "Zone" not in hem_input or not isinstance(hem_input["Zone"], dict):
        return hem_input

    if zone_name not in hem_input["Zone"]:
        zone_name = next(iter(hem_input["Zone"].keys()))

    system_name = next(iter(space_cool_system.keys()))
    hem_input["Zone"][zone_name]["SpaceCoolSystem"] = system_name

    return hem_input


def summarise_cooling_inputs(cooling_data: dict, floor_area_m2: float | None = None) -> dict:
    if not isinstance(cooling_data, dict) or not cooling_data.get("cooling_enabled"):
        return {
            "enabled": False,
            "capacity_kw": 0.0,
            "cop": 0.0,
            "capacity_w_m2": 0.0,
            "status": "Cooling not enabled",
        }

    capacity_kw = safe_float(cooling_data.get("cooling_capacity_kw"), 0.0)
    cop = safe_float(cooling_data.get("cooling_cop"), 0.0)

    capacity_w_m2 = 0.0
    if floor_area_m2 and floor_area_m2 > 0:
        capacity_w_m2 = capacity_kw * 1000 / floor_area_m2

    status = "OK"

    if capacity_kw <= 0:
        status = "Cooling capacity must be greater than zero."
    elif cop <= 0:
        status = "Cooling COP/EER must be greater than zero."
    elif capacity_w_m2 > 250:
        status = "Cooling capacity intensity appears high. Check units."
    elif capacity_w_m2 < 20 and capacity_w_m2 > 0:
        status = "Cooling capacity intensity appears low. Check design intent."

    return {
        "enabled": True,
        "capacity_kw": capacity_kw,
        "cop": cop,
        "capacity_w_m2": capacity_w_m2,
        "status": status,
    }
""",
)


# Patch full_case_builder.py to apply form heating after preserved heating
full_case_path = Path("ui/utils/full_case_builder.py")
text = full_case_path.read_text(encoding="utf-8")

if "apply_form_heating_to_hem_input" not in text:
    text = text.replace(
        "from hvac_mapper import apply_space_cooling_to_hem_input\n",
        "from hvac_mapper import apply_form_heating_to_hem_input, apply_space_cooling_to_hem_input\n",
        1,
    )
elif "from hvac_mapper import apply_space_cooling_to_hem_input" in text and "apply_form_heating_to_hem_input" not in text.split("from hvac_mapper import", 1)[1].split("\\n", 1)[0]:
    text = text.replace(
        "from hvac_mapper import apply_space_cooling_to_hem_input\n",
        "from hvac_mapper import apply_form_heating_to_hem_input, apply_space_cooling_to_hem_input\n",
        1,
    )

if 'heating_form = project_sections.get("heating_form", {})' not in text:
    text = text.replace(
        '    heat_source_wet = project_sections.get("heat_source_wet", {})\n',
        '    heat_source_wet = project_sections.get("heat_source_wet", {})\n    heating_form = project_sections.get("heating_form", {})\n',
        1,
    )

if "hem_input = apply_form_heating_to_hem_input(" not in text:
    text = text.replace(
        """    hem_input = apply_heat_source_wet_to_case(
        hem_input=hem_input,
        heat_source_wet=heat_source_wet,
    )
""",
        """    hem_input = apply_heat_source_wet_to_case(
        hem_input=hem_input,
        heat_source_wet=heat_source_wet,
    )

    hem_input = apply_form_heating_to_hem_input(
        hem_input=hem_input,
        heating_data=heating_form,
        zone_name="zone 1",
    )
""",
        1,
    )

full_case_path.write_text(text, encoding="utf-8")
print("Patched ui/utils/full_case_builder.py")


# Patch validation.py for form heating
validation_path = Path("ui/utils/project_validation.py")
text = validation_path.read_text(encoding="utf-8")

if "def validate_heating_form" not in text:
    text = text.replace(
        "def validate_cooling(project_data: dict) -> list[dict]:\n",
        """
def validate_heating_form(project_data: dict) -> list[dict]:
    messages = []

    heating = project_data.get("heating_form", {}) or {}

    if not heating:
        return messages

    if not heating.get("use_form_heating", False):
        return messages

    mode = str(heating.get("heating_mode", "")).strip()
    capacity = safe_float(heating.get("rated_power_kw"), 0.0)

    if mode in ["", "Preserve uploaded HEM heating"]:
        messages.append(
            {
                "level": "error",
                "section": "Heating",
                "message": "Form-based heating is enabled, but no generated heating mode is selected.",
            }
        )

    if capacity is None or capacity <= 0:
        messages.append(
            {
                "level": "error",
                "section": "Heating",
                "message": "Heating capacity must be greater than zero.",
            }
        )

    if mode == "Wet central heating - heat pump":
        cop = safe_float(heating.get("heat_pump_nominal_cop"), 0.0)
        if cop is None or cop <= 0:
            messages.append(
                {
                    "level": "error",
                    "section": "Heating",
                    "message": "Heat pump nominal COP must be greater than zero.",
                }
            )

    if mode == "Wet central heating - boiler":
        eff = safe_float(heating.get("boiler_efficiency_full_load"), 0.0)
        if eff is None or eff <= 0:
            messages.append(
                {
                    "level": "error",
                    "section": "Heating",
                    "message": "Boiler full-load efficiency must be greater than zero.",
                }
            )

    return messages


def validate_cooling(project_data: dict) -> list[dict]:
""",
        1,
    )

if "messages.extend(validate_heating_form(project_data))" not in text:
    text = text.replace(
        "    messages.extend(validate_ventilation(project_data))\n",
        "    messages.extend(validate_ventilation(project_data))\n    messages.extend(validate_heating_form(project_data))\n",
        1,
    )

if '"heating_form": "Generated heating form"' not in text:
    text = text.replace(
        '        "heat_source_wet": "Wet heat sources",\n',
        '        "heat_source_wet": "Wet heat sources",\n        "heating_form": "Generated heating form",\n',
        1,
    )

validation_path.write_text(text, encoding="utf-8")
print("Patched ui/utils/project_validation.py")


# Rewrite Heating & Cooling page to be form-first
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
""",
)

print("Batch V2 complete.")