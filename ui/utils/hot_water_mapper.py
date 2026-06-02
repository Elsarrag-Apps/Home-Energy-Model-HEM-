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

    for item in text.replace("\n", ",").split(","):
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
