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
