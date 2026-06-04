from __future__ import annotations


ORIENTATION_TO_DEGREES = {
    "North": 0,
    "North East": 45,
    "East": 90,
    "South East": 135,
    "South": 180,
    "South West": 225,
    "West": 270,
    "North West": 315,
}


def as_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in ["true", "yes", "1", "y"]


def as_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def apply_ventilation_to_hem_input(hem_input: dict, project_data: dict) -> dict:
    """Apply HEM-native ventilation mapping.

    HEM requirements:
    - design_outdoor_air_flow_rate is m3/hour
    - SFP is W/(L/s)
    - MVHR needs intake/exhaust positions, ductwork, airflow/temp controls, and location
    """
    ventilation = project_data.get("ventilation", {}) or {}
    mech = ventilation.get("mechanical_ventilation", {}) or {}

    if not isinstance(mech, dict):
        return hem_input

    vent_type = mech.get("vent_type", "None")

    iv = hem_input.get("InfiltrationVentilation", {})
    if not isinstance(iv, dict):
        iv = {}

    if str(vent_type).lower() in ["none", "natural", ""]:
        iv.pop("MechanicalVentilation", None)
        hem_input["InfiltrationVentilation"] = iv
        return hem_input

    design_flow_m3_h = as_float(
        mech.get(
            "design_flow_m3_h",
            mech.get(
                "design_outdoor_air_flow_rate",
                mech.get(
                    "design_flow_l_s",
                    mech.get("design_flow", 0.0),
                ),
            ),
        ),
        0.0,
    )

    sfp = as_float(mech.get("sfp_w_l_s", mech.get("SFP", 0.0)), 0.0)

    if design_flow_m3_h <= 0 or sfp <= 0:
        iv.pop("MechanicalVentilation", None)
        hem_input["InfiltrationVentilation"] = iv
        return hem_input

    intake_orientation = ORIENTATION_TO_DEGREES.get(
        mech.get("intake_orientation", "North"),
        0,
    )

    exhaust_orientation = ORIENTATION_TO_DEGREES.get(
        mech.get("exhaust_orientation", "South"),
        180,
    )

    mvhr_eff = as_float(
        mech.get("mvhr_efficiency_percent", mech.get("mvhr_eff", 80.0)),
        80.0,
    )

    if mvhr_eff > 1.0:
        mvhr_eff = mvhr_eff / 100.0

    item = {
        "vent_type": vent_type,
        "EnergySupply": mech.get("energy_supply", mech.get("EnergySupply", "mains elec")),
        "design_outdoor_air_flow_rate": design_flow_m3_h,
        "SFP": sfp,
        "SFP_in_use_factor": as_float(
            mech.get("sfp_in_use_factor", mech.get("SFP_in_use_factor", 1.0)),
            1.0,
        ),
        "ductwork": mech.get("ductwork", []),
        "sup_air_flw_ctrl": mech.get("sup_air_flw_ctrl", "ODA"),
        "sup_air_temp_ctrl": mech.get("sup_air_temp_ctrl", "NO_CTRL"),
    }

    if str(vent_type).upper() == "MVHR":
        item.update(
            {
                "mvhr_eff": mvhr_eff,
                "mvhr_location": mech.get("mvhr_location", "inside"),
                "position_intake": {
                    "mid_height_air_flow_path": as_float(mech.get("intake_mid_height_m", 2.0), 2.0),
                    "orientation360": intake_orientation,
                    "pitch": as_float(mech.get("intake_pitch", 90.0), 90.0),
                },
                "position_exhaust": {
                    "mid_height_air_flow_path": as_float(mech.get("exhaust_mid_height_m", 2.0), 2.0),
                    "orientation360": exhaust_orientation,
                    "pitch": as_float(mech.get("exhaust_pitch", 90.0), 90.0),
                },
            }
        )

    iv["MechanicalVentilation"] = {"mech_vent_1": item}
    hem_input["InfiltrationVentilation"] = iv

    hem_input.setdefault("EnergySupply", {})
    hem_input["EnergySupply"].setdefault(
        item["EnergySupply"],
        {"fuel": "electricity", "is_export_capable": True},
    )

    return hem_input


def apply_professional_mappers_to_case(hem_input: dict, project_data: dict) -> dict:
    hem_input = apply_energy_supply_to_hem_input(hem_input, project_data)
    hem_input = apply_internal_gains_to_hem_input(hem_input, project_data)
    hem_input = apply_ventilation_to_hem_input(hem_input, project_data)
    return hem_input


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
