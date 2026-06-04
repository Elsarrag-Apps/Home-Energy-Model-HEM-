# -*- coding: utf-8 -*-
from pathlib import Path


def write(path, content):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"Wrote {p}")


# ---------------------------------------------------------------------
# 1. Add energy-supply mapper to hem_mappers.py
# ---------------------------------------------------------------------
mapper = Path("ui/utils/hem_mappers.py")

if not mapper.exists():
    raise FileNotFoundError("ui/utils/hem_mappers.py not found. Apply AC1 first.")

text = mapper.read_text(encoding="utf-8")

if "def as_bool" not in text:
    text = text.replace(
        "def as_float(value, default=0.0):",
        """def as_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in ["true", "yes", "1", "y"]


def as_float(value, default=0.0):""",
        1,
    )

if "def apply_energy_supply_to_hem_input" not in text:
    text += r'''


def apply_energy_supply_to_hem_input(hem_input: dict, project_data: dict) -> dict:
    """Apply schema-safe HEM EnergySupply objects.

    This mapper writes confirmed EnergySupply definitions only.
    PV and battery settings are saved in the project for preview/reporting and
    future detailed schema mapping, but are not injected into HEM here until
    their exact HEM schema is verified.
    """
    form = project_data.get("energy_supply_form", {}) or {}

    energy_supply = hem_input.get("EnergySupply", {})
    if not isinstance(energy_supply, dict):
        energy_supply = {}

    include_mains_elec = as_bool(form.get("include_mains_elec", True), True)
    export_capable = as_bool(form.get("electricity_export_capable", True), True)

    if include_mains_elec:
        energy_supply["mains elec"] = {
            "fuel": "electricity",
            "is_export_capable": export_capable,
        }

    if as_bool(form.get("include_mains_gas", False), False):
        energy_supply["mains gas"] = {
            "fuel": "mains_gas",
            "is_export_capable": False,
        }

    if as_bool(form.get("include_lpg_bulk", False), False):
        energy_supply["LPG bulk"] = {
            "fuel": "LPG_bulk",
            "is_export_capable": False,
        }

    if as_bool(form.get("include_lpg_bottled", False), False):
        energy_supply["LPG bottled"] = {
            "fuel": "LPG_bottled",
            "is_export_capable": False,
        }

    if as_bool(form.get("include_heat_network", False), False):
        energy_supply["heat network"] = {
            "fuel": "custom",
            "is_export_capable": False,
        }

    # Preserve special HEM pseudo-supplies when already present.
    if "_unmet_demand" in energy_supply:
        energy_supply["_unmet_demand"] = energy_supply["_unmet_demand"]

    if "_energy_from_environment" in energy_supply:
        energy_supply["_energy_from_environment"] = energy_supply["_energy_from_environment"]

    hem_input["EnergySupply"] = energy_supply
    return hem_input
'''

old_hook = """def apply_professional_mappers_to_case(hem_input: dict, project_data: dict) -> dict:
    hem_input = apply_internal_gains_to_hem_input(hem_input, project_data)
    hem_input = apply_ventilation_to_hem_input(hem_input, project_data)
    return hem_input
"""

new_hook = """def apply_professional_mappers_to_case(hem_input: dict, project_data: dict) -> dict:
    hem_input = apply_energy_supply_to_hem_input(hem_input, project_data)
    hem_input = apply_internal_gains_to_hem_input(hem_input, project_data)
    hem_input = apply_ventilation_to_hem_input(hem_input, project_data)
    return hem_input
"""

if old_hook in text:
    text = text.replace(old_hook, new_hook)
elif "apply_energy_supply_to_hem_input(hem_input, project_data)" not in text:
    old_hook_2 = """def apply_professional_mappers_to_case(hem_input: dict, project_data: dict) -> dict:
    hem_input = apply_ventilation_to_hem_input(hem_input, project_data)
    return hem_input
"""
    new_hook_2 = """def apply_professional_mappers_to_case(hem_input: dict, project_data: dict) -> dict:
    hem_input = apply_energy_supply_to_hem_input(hem_input, project_data)
    hem_input = apply_ventilation_to_hem_input(hem_input, project_data)
    return hem_input
"""
    if old_hook_2 in text:
        text = text.replace(old_hook_2, new_hook_2)
    else:
        raise RuntimeError("Could not patch apply_professional_mappers_to_case in hem_mappers.py")

mapper.write_text(text, encoding="utf-8")
print("Patched hem_mappers.py with energy supply mapper.")


# ---------------------------------------------------------------------
# 2. Replace Energy Supply page with comprehensive UI
# ---------------------------------------------------------------------
write(
    "ui/pages/9_Energy_Supply_PV_Battery.py",
    r'''
import sys
from pathlib import Path

import streamlit as st

CURRENT_DIR = Path(__file__).resolve().parent
UI_DIR = CURRENT_DIR.parent
UTILS_DIR = UI_DIR / "utils"
sys.path.append(str(UTILS_DIR))

from project_store import get_active_project, get_project_data_section, update_project_data


st.set_page_config(page_title="Energy Supply / PV / Battery", layout="wide")

st.title("Energy Supply / PV / Battery")

st.write(
    "Configure energy supplies, PV and battery assumptions. "
    "This page writes schema-safe HEM EnergySupply definitions now, while saving PV and battery settings for detailed mapping once the exact HEM schema is verified."
)

active_project = get_active_project()

if active_project is None:
    st.warning("No active project loaded.")
else:
    st.success("Active project loaded.")

saved = get_project_data_section("energy_supply_form", {}) or {}

st.header("1. Energy supply definitions")

with st.form("energy_supply_form_ui"):
    c1, c2, c3 = st.columns(3)

    with c1:
        include_mains_elec = st.checkbox(
            "Mains electricity",
            value=bool(saved.get("include_mains_elec", True)),
        )

        electricity_export_capable = st.checkbox(
            "Electricity export capable",
            value=bool(saved.get("electricity_export_capable", True)),
        )

        electricity_supply_name = st.text_input(
            "Electricity supply name used in HEM",
            value=saved.get("electricity_supply_name", "mains elec"),
        )

    with c2:
        include_mains_gas = st.checkbox(
            "Mains gas",
            value=bool(saved.get("include_mains_gas", False)),
        )

        include_heat_network = st.checkbox(
            "Heat network / district heat",
            value=bool(saved.get("include_heat_network", False)),
        )

        heat_network_name = st.text_input(
            "Heat network supply name used in HEM",
            value=saved.get("heat_network_name", "heat network"),
        )

    with c3:
        include_lpg_bulk = st.checkbox(
            "LPG bulk",
            value=bool(saved.get("include_lpg_bulk", False)),
        )

        include_lpg_bottled = st.checkbox(
            "LPG bottled",
            value=bool(saved.get("include_lpg_bottled", False)),
        )

        include_custom_supply = st.checkbox(
            "Custom supply placeholder",
            value=bool(saved.get("include_custom_supply", False)),
        )

        custom_supply_name = st.text_input(
            "Custom supply name",
            value=saved.get("custom_supply_name", "custom supply"),
        )

    st.header("2. PV system inputs")

    pv_enabled = st.checkbox(
        "PV present",
        value=bool(saved.get("pv_enabled", False)),
    )

    pv1, pv2, pv3, pv4 = st.columns(4)

    with pv1:
        pv_kwp = st.number_input(
            "PV capacity (kWp)",
            min_value=0.0,
            value=float(saved.get("pv_kwp", 0.0)),
            step=0.5,
        )

    with pv2:
        pv_orientation = st.selectbox(
            "PV orientation",
            ["North", "East", "South", "West"],
            index=["North", "East", "South", "West"].index(saved.get("pv_orientation", "South"))
            if saved.get("pv_orientation", "South") in ["North", "East", "South", "West"] else 2,
        )

    with pv3:
        pv_tilt = st.number_input(
            "PV tilt (degrees)",
            min_value=0.0,
            max_value=90.0,
            value=float(saved.get("pv_tilt", 30.0)),
            step=5.0,
        )

    with pv4:
        pv_inverter_efficiency = st.number_input(
            "PV inverter efficiency",
            min_value=0.0,
            max_value=1.0,
            value=float(saved.get("pv_inverter_efficiency", 0.96)),
            step=0.01,
        )

    pv5, pv6, pv7 = st.columns(3)

    with pv5:
        pv_export_allowed = st.checkbox(
            "PV export allowed",
            value=bool(saved.get("pv_export_allowed", True)),
        )

    with pv6:
        pv_self_consumption_priority = st.checkbox(
            "Prioritise self-consumption",
            value=bool(saved.get("pv_self_consumption_priority", True)),
        )

    with pv7:
        pv_notes = st.text_input(
            "PV notes",
            value=saved.get("pv_notes", ""),
        )

    st.header("3. Battery system inputs")

    battery_enabled = st.checkbox(
        "Battery present",
        value=bool(saved.get("battery_enabled", False)),
    )

    b1, b2, b3, b4 = st.columns(4)

    with b1:
        battery_capacity_kwh = st.number_input(
            "Battery usable capacity (kWh)",
            min_value=0.0,
            value=float(saved.get("battery_capacity_kwh", 0.0)),
            step=0.5,
        )

    with b2:
        battery_charge_power_kw = st.number_input(
            "Max charge power (kW)",
            min_value=0.0,
            value=float(saved.get("battery_charge_power_kw", 0.0)),
            step=0.5,
        )

    with b3:
        battery_discharge_power_kw = st.number_input(
            "Max discharge power (kW)",
            min_value=0.0,
            value=float(saved.get("battery_discharge_power_kw", 0.0)),
            step=0.5,
        )

    with b4:
        battery_roundtrip_efficiency = st.number_input(
            "Round-trip efficiency",
            min_value=0.0,
            max_value=1.0,
            value=float(saved.get("battery_roundtrip_efficiency", 0.90)),
            step=0.01,
        )

    b5, b6, b7 = st.columns(3)

    with b5:
        battery_initial_soc = st.number_input(
            "Initial state of charge",
            min_value=0.0,
            max_value=1.0,
            value=float(saved.get("battery_initial_soc", 0.50)),
            step=0.05,
        )

    with b6:
        battery_min_soc = st.number_input(
            "Minimum state of charge",
            min_value=0.0,
            max_value=1.0,
            value=float(saved.get("battery_min_soc", 0.10)),
            step=0.05,
        )

    with b7:
        battery_max_soc = st.number_input(
            "Maximum state of charge",
            min_value=0.0,
            max_value=1.0,
            value=float(saved.get("battery_max_soc", 1.00)),
            step=0.05,
        )

    st.header("4. Tariff / reporting assumptions")

    t1, t2, t3 = st.columns(3)

    with t1:
        import_tariff_p_per_kwh = st.number_input(
            "Import tariff (p/kWh)",
            min_value=0.0,
            value=float(saved.get("import_tariff_p_per_kwh", 30.0)),
            step=1.0,
        )

    with t2:
        export_tariff_p_per_kwh = st.number_input(
            "Export tariff (p/kWh)",
            min_value=0.0,
            value=float(saved.get("export_tariff_p_per_kwh", 5.0)),
            step=1.0,
        )

    with t3:
        grid_carbon_kgco2e_per_kwh = st.number_input(
            "Grid carbon factor (kgCO2e/kWh)",
            min_value=0.0,
            value=float(saved.get("grid_carbon_kgco2e_per_kwh", 0.15)),
            step=0.01,
        )

    save = st.form_submit_button("Save energy supply, PV and battery settings")

if save:
    data = {
        "include_mains_elec": include_mains_elec,
        "electricity_export_capable": electricity_export_capable,
        "electricity_supply_name": electricity_supply_name,
        "include_mains_gas": include_mains_gas,
        "include_heat_network": include_heat_network,
        "heat_network_name": heat_network_name,
        "include_lpg_bulk": include_lpg_bulk,
        "include_lpg_bottled": include_lpg_bottled,
        "include_custom_supply": include_custom_supply,
        "custom_supply_name": custom_supply_name,
        "pv_enabled": pv_enabled,
        "pv_kwp": pv_kwp,
        "pv_orientation": pv_orientation,
        "pv_tilt": pv_tilt,
        "pv_inverter_efficiency": pv_inverter_efficiency,
        "pv_export_allowed": pv_export_allowed,
        "pv_self_consumption_priority": pv_self_consumption_priority,
        "pv_notes": pv_notes,
        "battery_enabled": battery_enabled,
        "battery_capacity_kwh": battery_capacity_kwh,
        "battery_charge_power_kw": battery_charge_power_kw,
        "battery_discharge_power_kw": battery_discharge_power_kw,
        "battery_roundtrip_efficiency": battery_roundtrip_efficiency,
        "battery_initial_soc": battery_initial_soc,
        "battery_min_soc": battery_min_soc,
        "battery_max_soc": battery_max_soc,
        "import_tariff_p_per_kwh": import_tariff_p_per_kwh,
        "export_tariff_p_per_kwh": export_tariff_p_per_kwh,
        "grid_carbon_kgco2e_per_kwh": grid_carbon_kgco2e_per_kwh,
    }

    update_project_data("energy_supply_form", data)
    st.success("Energy supply, PV and battery settings saved.")

current = get_project_data_section("energy_supply_form", {}) or saved

st.header("5. HEM EnergySupply preview")

energy_preview = {}

if current.get("include_mains_elec", True):
    energy_preview[current.get("electricity_supply_name", "mains elec")] = {
        "fuel": "electricity",
        "is_export_capable": bool(current.get("electricity_export_capable", True)),
    }

if current.get("include_mains_gas", False):
    energy_preview["mains gas"] = {
        "fuel": "mains_gas",
        "is_export_capable": False,
    }

if current.get("include_lpg_bulk", False):
    energy_preview["LPG bulk"] = {
        "fuel": "LPG_bulk",
        "is_export_capable": False,
    }

if current.get("include_lpg_bottled", False):
    energy_preview["LPG bottled"] = {
        "fuel": "LPG_bottled",
        "is_export_capable": False,
    }

if current.get("include_heat_network", False):
    energy_preview[current.get("heat_network_name", "heat network")] = {
        "fuel": "custom",
        "is_export_capable": False,
    }

if current.get("include_custom_supply", False):
    energy_preview[current.get("custom_supply_name", "custom supply")] = {
        "fuel": "custom",
        "is_export_capable": False,
    }

st.json(energy_preview)

st.header("6. PV and battery project preview")

pv_battery_preview = {
    "PV": {
        "enabled": bool(current.get("pv_enabled", False)),
        "capacity_kWp": current.get("pv_kwp", 0.0),
        "orientation": current.get("pv_orientation", "South"),
        "tilt_degrees": current.get("pv_tilt", 30.0),
        "inverter_efficiency": current.get("pv_inverter_efficiency", 0.96),
        "export_allowed": current.get("pv_export_allowed", True),
    },
    "Battery": {
        "enabled": bool(current.get("battery_enabled", False)),
        "usable_capacity_kWh": current.get("battery_capacity_kwh", 0.0),
        "max_charge_power_kW": current.get("battery_charge_power_kw", 0.0),
        "max_discharge_power_kW": current.get("battery_discharge_power_kw", 0.0),
        "roundtrip_efficiency": current.get("battery_roundtrip_efficiency", 0.90),
        "initial_soc": current.get("battery_initial_soc", 0.50),
        "min_soc": current.get("battery_min_soc", 0.10),
        "max_soc": current.get("battery_max_soc", 1.00),
    },
}

st.json(pv_battery_preview)

st.info(
    "PV and battery fields are saved now, but not yet injected into HEM. "
    "This avoids invalid HEM JSON until the exact PV and battery schema is mapped from examples."
)

with st.expander("Saved energy supply form", expanded=False):
    st.json(current)
''',
)

print("AC3 complete.")