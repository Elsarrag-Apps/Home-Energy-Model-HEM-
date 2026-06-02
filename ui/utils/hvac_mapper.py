from copy import deepcopy


def safe_float(value, default=0.0):
    try:
        if value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def build_space_cool_system_from_app(cooling_data: dict) -> dict:
    """Build a valid HEM SpaceCoolSystem dictionary from app cooling inputs.

    Current supported HEM cooling type from inspected examples:
    - AirConditioning
    """
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
    """Build a HEM cooling setpoint control from app cooling inputs."""
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
    """Apply generated SpaceCoolSystem, cooling Control, and Zone reference."""
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
    """Return simple UI insight metrics for cooling inputs."""
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
