# -*- coding: utf-8 -*-
from pathlib import Path


def write(path, content):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"Wrote {p}")


# ---------------------------------------------------------------------
# 1. Add internal gains functions to hem_mappers.py
# ---------------------------------------------------------------------
mapper = Path("ui/utils/hem_mappers.py")

if not mapper.exists():
    raise FileNotFoundError("ui/utils/hem_mappers.py not found. Apply AC1 first.")

text = mapper.read_text(encoding="utf-8")

if "def simulation_hours" not in text:
    text += r'''


def simulation_hours(hem_input: dict) -> int:
    sim = hem_input.get("SimulationTime", {}) or {}

    try:
        return int((float(sim.get("end", 0)) - float(sim.get("start", 0))) / float(sim.get("step", 1)))
    except Exception:
        return 0


def repeat_to_length(values: list, length: int) -> list:
    if length <= 0:
        return values

    if not values:
        return [0.0] * length

    out = []

    while len(out) < length:
        out.extend(values)

    return out[:length]


def daily_profile(values_24: list, hours: int) -> list:
    values = [float(v) for v in values_24]

    if len(values) != 24:
        values = repeat_to_length(values, 24)

    return repeat_to_length(values, hours)


def simple_daily_shape(peak_w: float, profile_type: str) -> list:
    peak_w = float(peak_w)

    if profile_type == "occupancy":
        factors = [
            0.90, 0.90, 0.90, 0.90, 0.90, 0.80,
            0.65, 0.50, 0.30, 0.20, 0.20, 0.25,
            0.25, 0.25, 0.25, 0.35, 0.55, 0.75,
            0.90, 1.00, 1.00, 1.00, 0.95, 0.90,
        ]
    elif profile_type == "lighting":
        factors = [
            0.15, 0.10, 0.08, 0.08, 0.10, 0.20,
            0.35, 0.30, 0.20, 0.15, 0.10, 0.10,
            0.10, 0.10, 0.12, 0.18, 0.35, 0.65,
            0.90, 1.00, 0.90, 0.65, 0.40, 0.25,
        ]
    elif profile_type == "cooking":
        factors = [
            0.02, 0.01, 0.01, 0.01, 0.02, 0.05,
            0.20, 0.35, 0.08, 0.04, 0.04, 0.15,
            0.35, 0.20, 0.05, 0.05, 0.15, 0.65,
            1.00, 0.65, 0.20, 0.08, 0.04, 0.02,
        ]
    else:
        factors = [
            0.35, 0.30, 0.25, 0.25, 0.25, 0.30,
            0.45, 0.60, 0.50, 0.45, 0.45, 0.50,
            0.55, 0.55, 0.55, 0.60, 0.70, 0.85,
            1.00, 0.95, 0.80, 0.65, 0.50, 0.40,
        ]

    return [round(peak_w * f, 6) for f in factors]


def apply_internal_gains_to_hem_input(hem_input: dict, project_data: dict) -> dict:
    form = project_data.get("internal_gains_form", {}) or {}

    if not form.get("enabled", True):
        return hem_input

    hours = simulation_hours(hem_input)

    if hours <= 0:
        hours = 8760

    occupants = as_float(form.get("occupants", 2.0), 2.0)
    metabolic_w_per_person = as_float(form.get("metabolic_w_per_person", 80.0), 80.0)
    other_internal_peak_w = as_float(form.get("other_internal_peak_w", 150.0), 150.0)

    lighting_peak_w = as_float(form.get("lighting_peak_w", 120.0), 120.0)
    cooking_peak_w = as_float(form.get("cooking_peak_w", 900.0), 900.0)
    equipment_peak_w = as_float(form.get("equipment_peak_w", 250.0), 250.0)

    metabolic_schedule = daily_profile(
        simple_daily_shape(occupants * metabolic_w_per_person, "occupancy"),
        hours,
    )

    other_schedule = daily_profile(
        simple_daily_shape(other_internal_peak_w, "equipment"),
        hours,
    )

    lighting_schedule = daily_profile(
        simple_daily_shape(lighting_peak_w, "lighting"),
        hours,
    )

    cooking_schedule = daily_profile(
        simple_daily_shape(cooking_peak_w, "cooking"),
        hours,
    )

    equipment_schedule = daily_profile(
        simple_daily_shape(equipment_peak_w, "equipment"),
        hours,
    )

    hem_input["InternalGains"] = {
        "metabolic gains": {
            "start_day": 0,
            "time_series_step": 1,
            "schedule": {
                "main": metabolic_schedule,
            },
        },
        "other": {
            "start_day": 0,
            "time_series_step": 1,
            "schedule": {
                "main": other_schedule,
            },
        },
    }

    hem_input.setdefault("EnergySupply", {})
    hem_input["EnergySupply"].setdefault(
        "mains elec",
        {
            "fuel": "electricity",
            "is_export_capable": True,
        },
    )

    hem_input["ApplianceGains"] = {
        "lighting": {
            "start_day": 0,
            "time_series_step": 1,
            "gains_fraction": as_float(form.get("lighting_gains_fraction", 0.5), 0.5),
            "EnergySupply": "mains elec",
            "schedule": {
                "main": lighting_schedule,
            },
        },
        "cooking": {
            "start_day": 0,
            "time_series_step": 1,
            "gains_fraction": as_float(form.get("cooking_gains_fraction", 1.0), 1.0),
            "EnergySupply": "mains elec",
            "schedule": {
                "main": cooking_schedule,
            },
        },
        "equipment": {
            "start_day": 0,
            "time_series_step": 1,
            "gains_fraction": as_float(form.get("equipment_gains_fraction", 0.7), 0.7),
            "EnergySupply": "mains elec",
            "schedule": {
                "main": equipment_schedule,
            },
        },
    }

    return hem_input
'''

# Update professional mapper hook to include internal gains.
old_hook = """def apply_professional_mappers_to_case(hem_input: dict, project_data: dict) -> dict:
    hem_input = apply_ventilation_to_hem_input(hem_input, project_data)
    return hem_input
"""

new_hook = """def apply_professional_mappers_to_case(hem_input: dict, project_data: dict) -> dict:
    hem_input = apply_internal_gains_to_hem_input(hem_input, project_data)
    hem_input = apply_ventilation_to_hem_input(hem_input, project_data)
    return hem_input
"""

if old_hook in text:
    text = text.replace(old_hook, new_hook)
elif "apply_internal_gains_to_hem_input(hem_input, project_data)" not in text:
    raise RuntimeError("Could not patch apply_professional_mappers_to_case in hem_mappers.py")

mapper.write_text(text, encoding="utf-8")
print("Patched ui/utils/hem_mappers.py with internal gains mapper.")


# ---------------------------------------------------------------------
# 2. Replace Internal Gains page with a proper form UI
# ---------------------------------------------------------------------
write(
    "ui/pages/8_Internal_Gains_Controls.py",
    r'''
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

CURRENT_DIR = Path(__file__).resolve().parent
UI_DIR = CURRENT_DIR.parent
UTILS_DIR = UI_DIR / "utils"
sys.path.append(str(UTILS_DIR))

from project_store import get_active_project, get_project_data_section, update_project_data


st.set_page_config(page_title="Internal Gains & Controls", layout="wide")

st.title("Internal Gains & Controls")

st.write(
    "Configure HEM InternalGains and ApplianceGains using form inputs. "
    "The app creates annual schedules from a 24-hour domestic profile."
)

active_project = get_active_project()

if active_project is None:
    st.warning("No active project loaded.")
else:
    st.success("Active project loaded.")

saved = get_project_data_section("internal_gains_form", {}) or {}

st.header("1. Internal gains input mode")

enabled = st.checkbox(
    "Use form-based internal gains in generated HEM input",
    value=bool(saved.get("enabled", True)),
)

st.caption(
    "When enabled, the generated HEM JSON will use the schedules from this page instead of uploaded/demo gains."
)

st.header("2. Occupancy and internal sensible gains")

with st.form("internal_gains_form"):
    c1, c2, c3 = st.columns(3)

    with c1:
        occupants = st.number_input(
            "Typical occupants",
            min_value=0.0,
            value=float(saved.get("occupants", 2.0)),
            step=0.5,
        )

        metabolic_w_per_person = st.number_input(
            "Metabolic gain per person (W/person)",
            min_value=0.0,
            value=float(saved.get("metabolic_w_per_person", 80.0)),
            step=5.0,
        )

        other_internal_peak_w = st.number_input(
            "Other internal sensible gain peak (W)",
            min_value=0.0,
            value=float(saved.get("other_internal_peak_w", 150.0)),
            step=10.0,
        )

    with c2:
        lighting_peak_w = st.number_input(
            "Lighting peak load (W)",
            min_value=0.0,
            value=float(saved.get("lighting_peak_w", 120.0)),
            step=10.0,
        )

        lighting_gains_fraction = st.number_input(
            "Lighting gains fraction to zone",
            min_value=0.0,
            max_value=1.0,
            value=float(saved.get("lighting_gains_fraction", 0.5)),
            step=0.05,
        )

    with c3:
        cooking_peak_w = st.number_input(
            "Cooking peak load (W)",
            min_value=0.0,
            value=float(saved.get("cooking_peak_w", 900.0)),
            step=50.0,
        )

        cooking_gains_fraction = st.number_input(
            "Cooking gains fraction to zone",
            min_value=0.0,
            max_value=1.0,
            value=float(saved.get("cooking_gains_fraction", 1.0)),
            step=0.05,
        )

        equipment_peak_w = st.number_input(
            "Equipment / plug-load peak (W)",
            min_value=0.0,
            value=float(saved.get("equipment_peak_w", 250.0)),
            step=25.0,
        )

        equipment_gains_fraction = st.number_input(
            "Equipment gains fraction to zone",
            min_value=0.0,
            max_value=1.0,
            value=float(saved.get("equipment_gains_fraction", 0.7)),
            step=0.05,
        )

    save = st.form_submit_button("Save internal gains profile")

if save:
    data = {
        "enabled": enabled,
        "occupants": occupants,
        "metabolic_w_per_person": metabolic_w_per_person,
        "other_internal_peak_w": other_internal_peak_w,
        "lighting_peak_w": lighting_peak_w,
        "lighting_gains_fraction": lighting_gains_fraction,
        "cooking_peak_w": cooking_peak_w,
        "cooking_gains_fraction": cooking_gains_fraction,
        "equipment_peak_w": equipment_peak_w,
        "equipment_gains_fraction": equipment_gains_fraction,
    }

    update_project_data("internal_gains_form", data)
    st.session_state["internal_gains_form"] = data
    st.success("Internal gains profile saved.")

current = st.session_state.get(
    "internal_gains_form",
    get_project_data_section("internal_gains_form", {}) or saved,
)

st.header("3. Daily schedule preview")

def profile(peak, profile_type):
    peak = float(peak)

    if profile_type == "occupancy":
        factors = [0.90,0.90,0.90,0.90,0.90,0.80,0.65,0.50,0.30,0.20,0.20,0.25,0.25,0.25,0.25,0.35,0.55,0.75,0.90,1.00,1.00,1.00,0.95,0.90]
    elif profile_type == "lighting":
        factors = [0.15,0.10,0.08,0.08,0.10,0.20,0.35,0.30,0.20,0.15,0.10,0.10,0.10,0.10,0.12,0.18,0.35,0.65,0.90,1.00,0.90,0.65,0.40,0.25]
    elif profile_type == "cooking":
        factors = [0.02,0.01,0.01,0.01,0.02,0.05,0.20,0.35,0.08,0.04,0.04,0.15,0.35,0.20,0.05,0.05,0.15,0.65,1.00,0.65,0.20,0.08,0.04,0.02]
    else:
        factors = [0.35,0.30,0.25,0.25,0.25,0.30,0.45,0.60,0.50,0.45,0.45,0.50,0.55,0.55,0.55,0.60,0.70,0.85,1.00,0.95,0.80,0.65,0.50,0.40]

    return [peak * f for f in factors]

hours = list(range(24))

preview = pd.DataFrame(
    {
        "Hour": hours,
        "Metabolic gains W": profile(
            float(current.get("occupants", 2.0)) * float(current.get("metabolic_w_per_person", 80.0)),
            "occupancy",
        ),
        "Other gains W": profile(float(current.get("other_internal_peak_w", 150.0)), "equipment"),
        "Lighting W": profile(float(current.get("lighting_peak_w", 120.0)), "lighting"),
        "Cooking W": profile(float(current.get("cooking_peak_w", 900.0)), "cooking"),
        "Equipment W": profile(float(current.get("equipment_peak_w", 250.0)), "equipment"),
    }
).set_index("Hour")

st.line_chart(preview)

st.header("4. Generated HEM structure")

st.write("This page generates:")

st.code(
    """
InternalGains:
  metabolic gains
  other

ApplianceGains:
  lighting
  cooking
  equipment
""".strip()
)

with st.expander("Saved internal gains form", expanded=False):
    st.json(current)
''',
)

print("AC2 complete.")