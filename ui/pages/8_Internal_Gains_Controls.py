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

with st.form("internal_gains_form_ui"):
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



