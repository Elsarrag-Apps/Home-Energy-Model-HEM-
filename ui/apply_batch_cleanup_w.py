from pathlib import Path


def write_file(path, content):
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"Updated {file_path}")


write_file(
    "ui/utils/hot_water_mapper.py",
    """
def safe_float(value, default=0.0):
    try:
        if value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value, default=0):
    try:
        if value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def ensure_energy_supply_exists(hem_input: dict, supply_name: str) -> dict:
    if not supply_name:
        return hem_input

    if "EnergySupply" not in hem_input or not isinstance(hem_input["EnergySupply"], dict):
        hem_input["EnergySupply"] = {}

    if supply_name in hem_input["EnergySupply"]:
        return hem_input

    supply_lower = str(supply_name).lower()

    if "elec" in supply_lower:
        hem_input["EnergySupply"][supply_name] = {
            "fuel": "electricity",
            "is_export_capable": True,
        }
    elif "gas" in supply_lower:
        hem_input["EnergySupply"][supply_name] = {
            "fuel": "mains_gas",
            "is_export_capable": False,
        }
    else:
        hem_input["EnergySupply"][supply_name] = {
            "fuel": "custom",
            "is_export_capable": False,
        }

    return hem_input


def parse_temperature_profile(text: str) -> list[float]:
    if not text:
        return [10.0, 10.1, 10.2, 10.5, 10.6, 11.0, 11.5, 12.1]

    values = []

    for item in text.replace("\\n", ",").split(","):
        item = item.strip()
        if not item:
            continue
        values.append(safe_float(item, 10.0))

    return values or [10.0, 10.1, 10.2, 10.5, 10.6, 11.0, 11.5, 12.1]


def build_hot_water_from_app(hot_water_data: dict) -> dict:
    if not isinstance(hot_water_data, dict):
        return {}

    if not hot_water_data.get("use_form_hot_water", False):
        return {}

    cold_water_name = hot_water_data.get("cold_water_source_name", "mains water")
    cylinder_name = hot_water_data.get("cylinder_name", "hw cylinder")
    immersion_name = hot_water_data.get("immersion_name", "immersion")
    immersion_supply = hot_water_data.get("immersion_energy_supply", "mains elec")
    ies_supply = hot_water_data.get("instant_shower_energy_supply", "mains elec")

    min_control = hot_water_data.get("min_control_name", "hw_min_temp_control")
    max_control = hot_water_data.get("max_control_name", "hw_max_temp_control")

    cold_water_profile = parse_temperature_profile(
        hot_water_data.get("cold_water_temperatures", "")
    )

    hot_water_source = {
        cylinder_name: {
            "type": "StorageTank",
            "volume": safe_float(hot_water_data.get("cylinder_volume_litres"), 80.0),
            "daily_losses": safe_float(hot_water_data.get("daily_losses_kwh"), 1.68),
            "init_temp": safe_float(hot_water_data.get("initial_temperature_c"), 55.0),
            "ColdWaterSource": cold_water_name,
            "HeatSource": {
                immersion_name: {
                    "type": "ImmersionHeater",
                    "power": safe_float(hot_water_data.get("immersion_power_kw"), 3.0),
                    "EnergySupply": immersion_supply,
                    "Controlmin": min_control,
                    "Controlmax": max_control,
                    "heater_position": safe_float(
                        hot_water_data.get("heater_position"), 0.1
                    ),
                    "thermostat_position": safe_float(
                        hot_water_data.get("thermostat_position"), 0.33
                    ),
                }
            },
        }
    }

    hot_water_demand = {
        "Shower": {
            "mixer": {
                "type": "MixerShower",
                "flowrate": safe_float(hot_water_data.get("mixer_shower_flow_l_min"), 8.0),
                "ColdWaterSource": cold_water_name,
            },
            "IES": {
                "type": "InstantElecShower",
                "rated_power": safe_float(
                    hot_water_data.get("instant_shower_power_kw"), 9.0
                ),
                "ColdWaterSource": cold_water_name,
                "EnergySupply": ies_supply,
            },
        },
        "Bath": {
            "medium": {
                "size": safe_float(hot_water_data.get("bath_size_litres"), 100.0),
                "ColdWaterSource": cold_water_name,
                "flowrate": safe_float(hot_water_data.get("bath_flow_l_min"), 8.0),
            }
        },
        "Other": {
            "other": {
                "flowrate": safe_float(hot_water_data.get("other_flow_l_min"), 8.0),
                "ColdWaterSource": cold_water_name,
            }
        },
        "Distribution": [
            {
                "location": "internal",
                "internal_diameter_mm": safe_float(
                    hot_water_data.get("internal_pipe_diameter_mm"), 25.0
                ),
                "length": safe_float(hot_water_data.get("internal_pipe_length_m"), 8.0),
            },
            {
                "location": "external",
                "internal_diameter_mm": safe_float(
                    hot_water_data.get("external_pipe_diameter_mm"), 25.0
                ),
                "length": safe_float(hot_water_data.get("external_pipe_length_m"), 8.0),
            },
        ],
    }

    cold_water_source = {
        cold_water_name: {
            "start_day": 0,
            "temperatures": cold_water_profile,
            "time_series_step": 1,
        }
    }

    controls = {
        min_control: {
            "type": "SetpointTimeControl",
            "start_day": 0,
            "time_series_step": 1,
            "schedule": {
                "main": [
                    {
                        "repeat": 8760,
                        "value": safe_float(hot_water_data.get("min_temperature_c"), 52.0),
                    }
                ]
            },
        },
        max_control: {
            "type": "SetpointTimeControl",
            "start_day": 0,
            "time_series_step": 1,
            "schedule": {
                "main": [
                    {
                        "repeat": 8760,
                        "value": safe_float(hot_water_data.get("max_temperature_c"), 55.0),
                    }
                ]
            },
        },
    }

    events = {
        "Shower": {
            "IES": [
                {
                    "start": safe_float(hot_water_data.get("ies_shower_start"), 6.0),
                    "duration": safe_float(hot_water_data.get("ies_shower_duration_min"), 6.0),
                    "temperature": safe_float(hot_water_data.get("shower_temperature_c"), 41.0),
                }
            ],
            "mixer": [
                {
                    "start": safe_float(hot_water_data.get("mixer_shower_start"), 7.0),
                    "duration": safe_float(hot_water_data.get("mixer_shower_duration_min"), 6.0),
                    "temperature": safe_float(hot_water_data.get("shower_temperature_c"), 41.0),
                }
            ],
        },
        "Bath": {
            "medium": [
                {
                    "start": safe_float(hot_water_data.get("bath_start"), 6.0),
                    "temperature": safe_float(hot_water_data.get("bath_temperature_c"), 41.0),
                    "volume": safe_float(hot_water_data.get("bath_event_volume_litres"), 73.0),
                    "duration": safe_float(hot_water_data.get("bath_duration_min"), 9.0),
                }
            ]
        },
        "Other": {
            "other": [
                {
                    "start": safe_float(hot_water_data.get("other_start"), 7.0),
                    "duration": safe_float(hot_water_data.get("other_duration_min"), 1.0),
                    "temperature": safe_float(hot_water_data.get("other_temperature_c"), 41.0),
                }
            ]
        },
    }

    return {
        "HotWaterSource": hot_water_source,
        "HotWaterDemand": hot_water_demand,
        "ColdWaterSource": cold_water_source,
        "Control": controls,
        "Events": events,
        "energy_supplies": [immersion_supply, ies_supply],
    }


def apply_form_hot_water_to_hem_input(hem_input: dict, hot_water_data: dict) -> dict:
    generated = build_hot_water_from_app(hot_water_data)

    if not generated:
        return hem_input

    hem_input["HotWaterSource"] = generated["HotWaterSource"]
    hem_input["HotWaterDemand"] = generated["HotWaterDemand"]
    hem_input["ColdWaterSource"] = generated["ColdWaterSource"]

    if "Control" not in hem_input or not isinstance(hem_input["Control"], dict):
        hem_input["Control"] = {}

    hem_input["Control"].update(generated["Control"])

    if "Events" not in hem_input or not isinstance(hem_input["Events"], dict):
        hem_input["Events"] = {}

    hem_input["Events"].update(generated["Events"])

    for supply_name in generated.get("energy_supplies", []):
        hem_input = ensure_energy_supply_exists(hem_input, supply_name)

    return hem_input


def summarise_hot_water_inputs(hot_water_data: dict) -> dict:
    if not isinstance(hot_water_data, dict) or not hot_water_data.get("use_form_hot_water"):
        return {
            "mode": "Preserve uploaded HEM hot water",
            "cylinder_volume": 0.0,
            "daily_losses": 0.0,
            "immersion_power": 0.0,
            "status": "Using uploaded/preserved HEM hot water JSON",
        }

    volume = safe_float(hot_water_data.get("cylinder_volume_litres"), 0.0)
    losses = safe_float(hot_water_data.get("daily_losses_kwh"), 0.0)
    power = safe_float(hot_water_data.get("immersion_power_kw"), 0.0)

    status = "OK"

    if volume <= 0:
        status = "Cylinder volume must be greater than zero."
    elif losses < 0:
        status = "Daily losses cannot be negative."
    elif power <= 0:
        status = "Immersion power must be greater than zero."
    elif losses > 4:
        status = "Daily cylinder losses appear high. Check units."

    return {
        "mode": "Form-generated hot water",
        "cylinder_volume": volume,
        "daily_losses": losses,
        "immersion_power": power,
        "status": status,
    }
""",
)


# Patch full_case_builder.py
full_case_path = Path("ui/utils/full_case_builder.py")
text = full_case_path.read_text(encoding="utf-8")

if "from hot_water_mapper import apply_form_hot_water_to_hem_input" not in text:
    text = text.replace(
        "from hvac_mapper import",
        "from hot_water_mapper import apply_form_hot_water_to_hem_input\nfrom hvac_mapper import",
        1,
    )

if 'hot_water_form = project_sections.get("hot_water_form", {})' not in text:
    text = text.replace(
        '    hot_water_sections = project_sections.get("hot_water", {})\n',
        '    hot_water_sections = project_sections.get("hot_water", {})\n    hot_water_form = project_sections.get("hot_water_form", {})\n',
        1,
    )

if "hem_input = apply_form_hot_water_to_hem_input(" not in text:
    text = text.replace(
        """    hem_input = apply_gains_controls_to_case(
        hem_input=hem_input,
        gains_controls=gains_controls,
    )
""",
        """    hem_input = apply_gains_controls_to_case(
        hem_input=hem_input,
        gains_controls=gains_controls,
    )

    hem_input = apply_form_hot_water_to_hem_input(
        hem_input=hem_input,
        hot_water_data=hot_water_form,
    )
""",
        1,
    )

full_case_path.write_text(text, encoding="utf-8")
print("Patched ui/utils/full_case_builder.py")


# Patch project_validation.py
validation_path = Path("ui/utils/project_validation.py")
text = validation_path.read_text(encoding="utf-8")

if "def validate_hot_water_form" not in text:
    text = text.replace(
        "def validate_json_sections(project_data: dict) -> list[dict]:\n",
        """
def validate_hot_water_form(project_data: dict) -> list[dict]:
    messages = []

    hot_water = project_data.get("hot_water_form", {}) or {}

    if not hot_water:
        return messages

    if not hot_water.get("use_form_hot_water", False):
        return messages

    volume = safe_float(hot_water.get("cylinder_volume_litres"), 0.0)
    power = safe_float(hot_water.get("immersion_power_kw"), 0.0)
    losses = safe_float(hot_water.get("daily_losses_kwh"), 0.0)
    min_temp = safe_float(hot_water.get("min_temperature_c"), 52.0)
    max_temp = safe_float(hot_water.get("max_temperature_c"), 55.0)

    if volume is None or volume <= 0:
        messages.append(
            {
                "level": "error",
                "section": "Hot water",
                "message": "Cylinder volume must be greater than zero.",
            }
        )

    if power is None or power <= 0:
        messages.append(
            {
                "level": "error",
                "section": "Hot water",
                "message": "Immersion heater power must be greater than zero.",
            }
        )

    if losses is None or losses < 0:
        messages.append(
            {
                "level": "error",
                "section": "Hot water",
                "message": "Cylinder daily losses cannot be negative.",
            }
        )

    if min_temp is not None and max_temp is not None and min_temp > max_temp:
        messages.append(
            {
                "level": "error",
                "section": "Hot water",
                "message": "Minimum cylinder control temperature cannot exceed maximum temperature.",
            }
        )

    return messages


def validate_json_sections(project_data: dict) -> list[dict]:
""",
        1,
    )

if "messages.extend(validate_hot_water_form(project_data))" not in text:
    text = text.replace(
        "    messages.extend(validate_weather(project_data, default_weather_file))\n",
        "    messages.extend(validate_weather(project_data, default_weather_file))\n    messages.extend(validate_hot_water_form(project_data))\n",
        1,
    )

if '"hot_water_form": "Generated hot water form"' not in text:
    text = text.replace(
        '        "hot_water": "Hot water",\n',
        '        "hot_water": "Hot water",\n        "hot_water_form": "Generated hot water form",\n',
        1,
    )

validation_path.write_text(text, encoding="utf-8")
print("Patched ui/utils/project_validation.py")


# Rewrite Hot Water page
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
    "Configure domestic hot water using user-friendly inputs. The app can either "
    "preserve the uploaded HEM hot-water JSON or generate HEM-compatible "
    "HotWaterSource, HotWaterDemand, ColdWaterSource, Events and Control sections."
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


def clear_hot_water_state() -> None:
    for key in [
        "hot_water_sections",
        "hot_water_defaults_loaded",
    ]:
        if key in st.session_state:
            del st.session_state[key]


load_hot_water_defaults_into_state(force_reload=False)

hot_water_sections = st.session_state.get("hot_water_sections", {})
saved_form = get_project_data_section("hot_water_form", {}) or {}

st.header("1. Hot water input mode")

mode_options = [
    "Preserve uploaded HEM hot water",
    "Use form-generated hot water",
]

default_mode = saved_form.get("mode", "Preserve uploaded HEM hot water")

input_mode = st.radio(
    "How should hot water be defined in the generated HEM input?",
    mode_options,
    index=mode_options.index(default_mode) if default_mode in mode_options else 0,
)

use_form_hot_water = input_mode == "Use form-generated hot water"

if use_form_hot_water:
    st.success(
        "Form-generated hot water is enabled. The app will generate HEM-compatible "
        "hot water source, demand, cold water, events and controls."
    )
else:
    st.info(
        "The generated HEM file will preserve the uploaded HEM hot-water sections."
    )

st.header("2. Hot water form")

with st.form("hot_water_form"):
    st.subheader("Cylinder / storage tank")

    c1, c2, c3 = st.columns(3)

    with c1:
        cylinder_volume_litres = st.number_input(
            "Cylinder volume (litres)",
            min_value=0.0,
            value=float(saved_form.get("cylinder_volume_litres", 80.0)),
            step=5.0,
        )

        daily_losses_kwh = st.number_input(
            "Cylinder daily losses (kWh/day)",
            min_value=0.0,
            value=float(saved_form.get("daily_losses_kwh", 1.68)),
            step=0.1,
        )

        initial_temperature_c = st.number_input(
            "Initial cylinder temperature (degC)",
            min_value=0.0,
            max_value=90.0,
            value=float(saved_form.get("initial_temperature_c", 55.0)),
            step=1.0,
        )

    with c2:
        min_temperature_c = st.number_input(
            "Minimum control temperature (degC)",
            min_value=0.0,
            max_value=90.0,
            value=float(saved_form.get("min_temperature_c", 52.0)),
            step=1.0,
        )

        max_temperature_c = st.number_input(
            "Maximum control temperature (degC)",
            min_value=0.0,
            max_value=90.0,
            value=float(saved_form.get("max_temperature_c", 55.0)),
            step=1.0,
        )

        cold_water_source_name = st.text_input(
            "Cold water source name",
            value=saved_form.get("cold_water_source_name", "mains water"),
        )

    with c3:
        immersion_power_kw = st.number_input(
            "Immersion heater power (kW)",
            min_value=0.0,
            value=float(saved_form.get("immersion_power_kw", 3.0)),
            step=0.5,
        )

        immersion_energy_supply = st.selectbox(
            "Immersion energy supply",
            ["mains elec", "other"],
            index=0 if saved_form.get("immersion_energy_supply", "mains elec") == "mains elec" else 1,
        )

        instant_shower_energy_supply = st.selectbox(
            "Instant shower energy supply",
            ["mains elec", "other"],
            index=0 if saved_form.get("instant_shower_energy_supply", "mains elec") == "mains elec" else 1,
        )

    with st.expander("Advanced cylinder positions", expanded=False):
        p1, p2 = st.columns(2)

        with p1:
            heater_position = st.number_input(
                "Heater position",
                min_value=0.0,
                max_value=1.0,
                value=float(saved_form.get("heater_position", 0.1)),
                step=0.05,
            )

        with p2:
            thermostat_position = st.number_input(
                "Thermostat position",
                min_value=0.0,
                max_value=1.0,
                value=float(saved_form.get("thermostat_position", 0.33)),
                step=0.05,
            )

    st.subheader("Hot water demand")

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

    st.subheader("Pipework distribution")

    pipe1, pipe2 = st.columns(2)

    with pipe1:
        internal_pipe_length_m = st.number_input(
            "Internal pipe length (m)",
            min_value=0.0,
            value=float(saved_form.get("internal_pipe_length_m", 8.0)),
            step=0.5,
        )

        internal_pipe_diameter_mm = st.number_input(
            "Internal pipe diameter (mm)",
            min_value=0.0,
            value=float(saved_form.get("internal_pipe_diameter_mm", 25.0)),
            step=1.0,
        )

    with pipe2:
        external_pipe_length_m = st.number_input(
            "External pipe length (m)",
            min_value=0.0,
            value=float(saved_form.get("external_pipe_length_m", 8.0)),
            step=0.5,
        )

        external_pipe_diameter_mm = st.number_input(
            "External pipe diameter (mm)",
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

    save_form = st.form_submit_button("Save hot water form to project")

if save_form:
    hot_water_form = {
        "mode": input_mode,
        "use_form_hot_water": use_form_hot_water,
        "cylinder_name": "hw cylinder",
        "immersion_name": "immersion",
        "cold_water_source_name": cold_water_source_name,
        "cylinder_volume_litres": cylinder_volume_litres,
        "daily_losses_kwh": daily_losses_kwh,
        "initial_temperature_c": initial_temperature_c,
        "min_temperature_c": min_temperature_c,
        "max_temperature_c": max_temperature_c,
        "immersion_power_kw": immersion_power_kw,
        "immersion_energy_supply": immersion_energy_supply,
        "instant_shower_energy_supply": instant_shower_energy_supply,
        "heater_position": heater_position,
        "thermostat_position": thermostat_position,
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
    st.success("Hot water form saved to the app project.")

st.header("3. Hot water input insight")

current_form = get_project_data_section("hot_water_form", {}) or {}
summary = summarise_hot_water_inputs(current_form)

m1, m2, m3, m4 = st.columns(4)

with m1:
    st.metric("Hot water mode", summary["mode"])

with m2:
    st.metric("Cylinder volume", f"{summary['cylinder_volume']:.1f} litres")

with m3:
    st.metric("Daily losses", f"{summary['daily_losses']:.2f} kWh/day")

with m4:
    st.metric("Immersion power", f"{summary['immersion_power']:.1f} kW")

if summary["status"] == "OK":
    st.success("Hot water input check: OK")
else:
    st.info(summary["status"])

st.header("4. Uploaded HEM hot water summary")

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

st.header("5. Project save status")

if current_form:
    st.success("Hot water form is saved.")
else:
    st.info("Hot water form is not saved yet.")

with st.expander("Developer/debug: view saved hot water data", expanded=False):
    st.subheader("Hot water form")
    st.json(get_project_data_section("hot_water_form", {}) or {})

    st.subheader("Preserved HEM hot water sections")
    st.json(st.session_state.get("hot_water_sections", {}))
""",
)

print("Batch W complete.")