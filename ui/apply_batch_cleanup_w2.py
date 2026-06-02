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
    elif "heat network" in supply_lower:
        hem_input["EnergySupply"][supply_name] = {
            "fuel": "custom",
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
        if item:
            values.append(safe_float(item, 10.0))

    return values or [10.0, 10.1, 10.2, 10.5, 10.6, 11.0, 11.5, 12.1]


def build_hw_controls(hot_water_data: dict) -> dict:
    min_control = hot_water_data.get("min_control_name", "hw_min_temp_control")
    max_control = hot_water_data.get("max_control_name", "hw_max_temp_control")

    return {
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
                        "value": safe_float(hot_water_data.get("max_temperature_c"), 60.0),
                    }
                ]
            },
        },
    }


def build_cold_water_source(hot_water_data: dict) -> dict:
    cold_water_name = hot_water_data.get("cold_water_source_name", "mains water")
    return {
        cold_water_name: {
            "start_day": 0,
            "temperatures": parse_temperature_profile(
                hot_water_data.get("cold_water_temperatures", "")
            ),
            "time_series_step": 1,
        }
    }


def build_hot_water_demand(hot_water_data: dict) -> dict:
    cold_water_name = hot_water_data.get("cold_water_source_name", "mains water")
    ies_supply = hot_water_data.get("instant_shower_energy_supply", "mains elec")

    return {
        "Shower": {
            "mixer": {
                "type": "MixerShower",
                "flowrate": safe_float(hot_water_data.get("mixer_shower_flow_l_min"), 8.0),
                "ColdWaterSource": cold_water_name,
            },
            "IES": {
                "type": "InstantElecShower",
                "rated_power": safe_float(hot_water_data.get("instant_shower_power_kw"), 9.0),
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
                "internal_diameter_mm": safe_float(hot_water_data.get("internal_pipe_diameter_mm"), 25.0),
                "length": safe_float(hot_water_data.get("internal_pipe_length_m"), 8.0),
            },
            {
                "location": "external",
                "internal_diameter_mm": safe_float(hot_water_data.get("external_pipe_diameter_mm"), 25.0),
                "length": safe_float(hot_water_data.get("external_pipe_length_m"), 8.0),
            },
        ],
    }


def build_hot_water_events(hot_water_data: dict) -> dict:
    return {
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


def build_primary_pipework(hot_water_data: dict) -> list[dict]:
    return [
        {
            "location": "internal",
            "internal_diameter_mm": safe_float(hot_water_data.get("primary_internal_diameter_mm"), 20.2),
            "external_diameter_mm": safe_float(hot_water_data.get("primary_external_diameter_mm"), 22.0),
            "length": safe_float(hot_water_data.get("primary_internal_length_m"), 8.0),
            "insulation_thermal_conductivity": safe_float(hot_water_data.get("primary_insulation_lambda"), 0.035),
            "insulation_thickness_mm": safe_float(hot_water_data.get("primary_insulation_thickness_mm"), 25.0),
            "surface_reflectivity": False,
            "pipe_contents": "water",
        }
    ]


def build_storage_tank_base(hot_water_data: dict) -> dict:
    cold_water_name = hot_water_data.get("cold_water_source_name", "mains water")
    return {
        "type": "StorageTank",
        "volume": safe_float(hot_water_data.get("cylinder_volume_litres"), 150.0),
        "daily_losses": safe_float(hot_water_data.get("daily_losses_kwh"), 1.68),
        "init_temp": safe_float(hot_water_data.get("initial_temperature_c"), 55.0),
        "ColdWaterSource": cold_water_name,
    }


def build_hot_water_source(hot_water_data: dict) -> tuple[dict, list[str]]:
    system_type = hot_water_data.get("hot_water_system_type", "Electric cylinder with immersion heater")
    source_name = hot_water_data.get("hot_water_source_name", "hw cylinder")
    cold_water_name = hot_water_data.get("cold_water_source_name", "mains water")
    min_control = hot_water_data.get("min_control_name", "hw_min_temp_control")
    max_control = hot_water_data.get("max_control_name", "hw_max_temp_control")

    energy_supplies = []

    if system_type == "Electric cylinder with immersion heater":
        immersion_supply = hot_water_data.get("immersion_energy_supply", "mains elec")
        energy_supplies.append(immersion_supply)

        tank = build_storage_tank_base(hot_water_data)
        tank["min_temp"] = safe_float(hot_water_data.get("min_temperature_c"), 52.0)
        tank["setpoint_temp"] = safe_float(hot_water_data.get("max_temperature_c"), 60.0)
        tank["HeatSource"] = {
            "immersion": {
                "type": "ImmersionHeater",
                "power": safe_float(hot_water_data.get("immersion_power_kw"), 3.0),
                "EnergySupply": immersion_supply,
                "Control": hot_water_data.get("hw_timer_control_name", "hw_timer_control"),
                "heater_position": safe_float(hot_water_data.get("heater_position"), 0.1),
                "thermostat_position": safe_float(hot_water_data.get("thermostat_position"), 0.33),
            }
        }
        return {source_name: tank}, energy_supplies

    if system_type == "Storage cylinder heated by wet heat source":
        wet_source_name = hot_water_data.get("linked_wet_heat_source_name", "heat_pump")
        tank = build_storage_tank_base(hot_water_data)
        tank["primary_pipework"] = build_primary_pipework(hot_water_data)
        tank["HeatSource"] = {
            wet_source_name: {
                "type": "HeatSourceWet",
                "name": wet_source_name,
                "temp_flow_limit_upper": safe_float(hot_water_data.get("temp_flow_limit_upper"), 65.0),
                "EnergySupply": hot_water_data.get("wet_source_energy_supply", "mains elec"),
                "Controlmin": min_control,
                "Controlmax": max_control,
                "heater_position": safe_float(hot_water_data.get("heater_position"), 0.1),
                "thermostat_position": safe_float(hot_water_data.get("thermostat_position"), 0.5),
            }
        }
        energy_supplies.append(hot_water_data.get("wet_source_energy_supply", "mains elec"))
        return {source_name: tank}, energy_supplies

    if system_type == "Combi boiler hot water":
        wet_source_name = hot_water_data.get("linked_wet_heat_source_name", "boiler")
        return {
            source_name: {
                "type": "CombiBoiler",
                "ColdWaterSource": cold_water_name,
                "HeatSourceWet": wet_source_name,
                "separate_DHW_tests": hot_water_data.get("separate_dhw_tests", "M&L"),
                "rejected_energy_1": safe_float(hot_water_data.get("rejected_energy_1"), 0.0004),
                "storage_loss_factor_2": safe_float(hot_water_data.get("storage_loss_factor_2"), 0.91574),
                "rejected_factor_3": safe_float(hot_water_data.get("rejected_factor_3"), 0.0),
                "setpoint_temp": safe_float(hot_water_data.get("max_temperature_c"), 60.0),
                "daily_HW_usage": safe_float(hot_water_data.get("daily_hw_usage_litres"), 120.0),
            }
        }, energy_supplies

    if system_type == "Point-of-use water heater":
        pou_supply = hot_water_data.get("point_of_use_energy_supply", "mains elec")
        energy_supplies.append(pou_supply)

        return {
            source_name: {
                "type": "PointOfUse",
                "min_temp": safe_float(hot_water_data.get("min_temperature_c"), 52.0),
                "setpoint_temp": safe_float(hot_water_data.get("max_temperature_c"), 60.0),
                "ColdWaterSource": cold_water_name,
                "power": safe_float(hot_water_data.get("point_of_use_power_kw"), 10.0),
                "efficiency": safe_float(hot_water_data.get("point_of_use_efficiency"), 0.8),
                "EnergySupply": pou_supply,
            }
        }, energy_supplies

    if system_type == "Heat pump water heater":
        hp_supply = hot_water_data.get("heat_pump_hw_energy_supply", "mains elec")
        energy_supplies.append(hp_supply)

        tank = build_storage_tank_base(hot_water_data)
        tank["heat_exchanger_surface_area"] = safe_float(hot_water_data.get("heat_exchanger_area_m2"), 1.0)
        tank["primary_pipework"] = []
        tank["HeatSource"] = {
            "heat pump 1": {
                "type": "HeatPump_HWOnly",
                "power_max": safe_float(hot_water_data.get("heat_pump_hw_power_kw"), 5.0),
                "vol_hw_daily_average": safe_float(hot_water_data.get("daily_hw_usage_litres"), 100.0),
                "tank_volume_declared": safe_float(hot_water_data.get("cylinder_volume_litres"), 100.0),
                "heat_exchanger_surface_area_declared": safe_float(hot_water_data.get("heat_exchanger_area_m2"), 1.5),
                "daily_losses_declared": safe_float(hot_water_data.get("daily_losses_kwh"), 1.05),
                "in_use_factor_mismatch": safe_float(hot_water_data.get("in_use_factor_mismatch"), 0.6),
                "test_data": {
                    "M": {
                        "cop_dhw": safe_float(hot_water_data.get("heat_pump_hw_cop"), 2.5),
                        "hw_tapping_prof_daily_total": 5.845,
                        "energy_input_measured": 2.338,
                        "power_standby": safe_float(hot_water_data.get("heat_pump_hw_standby_kw"), 0.02),
                        "hw_vessel_loss_daily": 2.0,
                    }
                },
                "EnergySupply": hp_supply,
                "Controlmin": min_control,
                "Controlmax": max_control,
                "heater_position": safe_float(hot_water_data.get("heater_position"), 0.1),
                "thermostat_position": safe_float(hot_water_data.get("thermostat_position"), 0.33),
            }
        }
        return {source_name: tank}, energy_supplies

    if system_type == "HIU / heat network hot water":
        wet_source_name = hot_water_data.get("linked_wet_heat_source_name", "HeatNetwork")
        return {
            source_name: {
                "type": "HIU",
                "ColdWaterSource": cold_water_name,
                "HeatSourceWet": wet_source_name,
                "setpoint_temp": safe_float(hot_water_data.get("max_temperature_c"), 52.0),
            }
        }, energy_supplies

    return {}, energy_supplies


def build_hot_water_from_app(hot_water_data: dict) -> dict:
    if not isinstance(hot_water_data, dict):
        return {}

    if not hot_water_data.get("use_form_hot_water", False):
        return {}

    hot_water_source, energy_supplies = build_hot_water_source(hot_water_data)
    if not hot_water_source:
        return {}

    demand = build_hot_water_demand(hot_water_data)
    cold_water = build_cold_water_source(hot_water_data)
    controls = build_hw_controls(hot_water_data)
    events = build_hot_water_events(hot_water_data)

    # Timer control used by immersion-heater examples.
    controls["hw_timer_control"] = {
        "type": "OnOffTimeControl",
        "start_day": 0,
        "time_series_step": 1,
        "schedule": {
            "main": [
                {
                    "repeat": 8760,
                    "value": True,
                }
            ]
        },
    }

    energy_supplies.append(hot_water_data.get("instant_shower_energy_supply", "mains elec"))

    return {
        "HotWaterSource": hot_water_source,
        "HotWaterDemand": demand,
        "ColdWaterSource": cold_water,
        "Control": controls,
        "Events": events,
        "energy_supplies": energy_supplies,
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
            "system_type": "Uploaded HEM system",
            "cylinder_volume": 0.0,
            "daily_losses": 0.0,
            "primary_power": 0.0,
            "status": "Using uploaded/preserved HEM hot water JSON",
        }

    system_type = hot_water_data.get("hot_water_system_type", "Unknown")
    volume = safe_float(hot_water_data.get("cylinder_volume_litres"), 0.0)
    losses = safe_float(hot_water_data.get("daily_losses_kwh"), 0.0)

    if system_type == "Point-of-use water heater":
        primary_power = safe_float(hot_water_data.get("point_of_use_power_kw"), 0.0)
    elif system_type == "Heat pump water heater":
        primary_power = safe_float(hot_water_data.get("heat_pump_hw_power_kw"), 0.0)
    else:
        primary_power = safe_float(hot_water_data.get("immersion_power_kw"), 0.0)

    status = "OK"

    if "cylinder" in system_type.lower() or "heat pump water" in system_type.lower():
        if volume <= 0:
            status = "Cylinder volume must be greater than zero."

    if losses < 0:
        status = "Daily losses cannot be negative."

    if primary_power <= 0 and system_type in [
        "Electric cylinder with immersion heater",
        "Point-of-use water heater",
        "Heat pump water heater",
    ]:
        status = "Primary hot-water power must be greater than zero."

    return {
        "mode": "Form-generated hot water",
        "system_type": system_type,
        "cylinder_volume": volume,
        "daily_losses": losses,
        "primary_power": primary_power,
        "status": status,
    }
""",
)