from hem_mappers import apply_professional_mappers_to_case
import json
from copy import deepcopy
from pathlib import Path

from weather_mapper import apply_weather_simulation_to_case
from hot_water_mapper import apply_form_hot_water_to_hem_input
from hvac_mapper import apply_form_heating_to_hem_input, apply_space_cooling_to_hem_input
from input_builder import (
    ORIENTATION_TO_DEGREES,
    build_hem_building_elements,
    build_hem_infiltration_ventilation,
)


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return path


def safe_float(value, default=None):
    try:
        if value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_positive_float(value, default=None):
    number = safe_float(value, default)
    if number is None:
        return default
    if number <= 0:
        return default
    return number


def u_value_to_resistance(u_value):
    u_value = safe_positive_float(u_value)
    if u_value is None:
        return None
    return 1.0 / u_value


def is_valid_fabric_row(row: dict) -> bool:
    if not isinstance(row, dict):
        return False

    element_type = str(row.get("type", "")).strip()
    area = safe_positive_float(row.get("area_m2"))
    u_value = safe_positive_float(row.get("u_value_w_m2k"))

    return bool(element_type) and area is not None and u_value is not None


def clean_fabric_rows(fabric_elements: list) -> list[dict]:
    return [row for row in (fabric_elements or []) if is_valid_fabric_row(row)]


def update_existing_hem_element(existing_element: dict, row: dict) -> dict:
    element = deepcopy(existing_element)
    hem_type = element.get("type")

    area = safe_positive_float(row.get("area_m2"))
    u_value = safe_positive_float(row.get("u_value_w_m2k"))
    resistance = u_value_to_resistance(u_value)

    pitch = safe_float(row.get("pitch_degrees"))
    orientation = row.get("orientation")

    height = safe_positive_float(row.get("height_m"))
    width = safe_positive_float(row.get("width_m"))
    base_height = safe_float(row.get("base_height_m"))
    areal_heat_capacity = safe_positive_float(row.get("areal_heat_capacity_kj_m2k"))

    if area is not None:
        element["area"] = area
        if hem_type == "BuildingElementGround":
            element["total_area"] = area

    if pitch is not None:
        element["pitch"] = pitch

    if orientation and orientation in ORIENTATION_TO_DEGREES and orientation != "Not applicable":
        element["orientation360"] = ORIENTATION_TO_DEGREES[orientation]

    if base_height is not None and "base_height" in element:
        element["base_height"] = base_height

    if height is not None and "height" in element:
        element["height"] = height

    if width is not None and "width" in element:
        element["width"] = width

    if areal_heat_capacity is not None:
        element["areal_heat_capacity"] = areal_heat_capacity * 1000

    if hem_type == "BuildingElementOpaque":
        if resistance is not None:
            element["thermal_resistance_construction"] = resistance

        solar_absorption = safe_float(row.get("solar_absorption_coeff"))
        if solar_absorption is not None:
            element["solar_absorption_coeff"] = solar_absorption

    elif hem_type == "BuildingElementTransparent":
        if resistance is not None:
            element["thermal_resistance_construction"] = resistance

        g_value = safe_float(row.get("g_value"))
        if g_value is not None:
            element["g_value"] = g_value

        frame_factor = safe_float(row.get("frame_factor"))
        if frame_factor is not None:
            element["frame_area_fraction"] = max(0.0, min(1.0, 1.0 - frame_factor))

        free_area_height = safe_float(row.get("free_area_height_m"))
        if free_area_height is not None:
            element["free_area_height"] = free_area_height

        openable_fraction = safe_float(row.get("openable_fraction"), 0.0)
        if area is not None and openable_fraction is not None:
            element["max_window_open_area"] = area * openable_fraction

        if "mid_height" in element and "window_part_list" in element:
            mid_height = element.get("mid_height")
            if mid_height is not None:
                element["window_part_list"] = [{"mid_height_air_flow_path": mid_height}]

    elif hem_type == "BuildingElementPartyWall":
        if resistance is not None:
            element["thermal_resistance_construction"] = resistance

        cavity_type = str(row.get("party_wall_cavity_type", "")).strip()
        if cavity_type:
            element["party_wall_cavity_type"] = cavity_type

    elif hem_type == "BuildingElementGround":
        if u_value is not None:
            element["u_value"] = u_value

        perimeter = safe_float(row.get("perimeter_m"))
        if perimeter is not None:
            element["perimeter"] = perimeter

        wall_thickness = safe_float(row.get("thickness_walls_m"))
        if wall_thickness is not None:
            element["thickness_walls"] = wall_thickness

        psi = safe_float(row.get("psi_wall_floor_junc"))
        if psi is not None:
            element["psi_wall_floor_junc"] = psi

        floor_type = str(row.get("floor_type", "")).strip()
        if floor_type:
            element["floor_type"] = floor_type

    return element


def apply_fabric_to_case(
    hem_input: dict,
    fabric_elements: list,
    update_mode: str = "Replace all existing elements",
    zone_name: str = "zone 1",
) -> dict:
    fabric_elements = clean_fabric_rows(fabric_elements)

    if not fabric_elements:
        return hem_input

    if "Zone" not in hem_input:
        raise KeyError("HEM input does not contain a Zone section.")

    if zone_name not in hem_input["Zone"]:
        zone_name = next(iter(hem_input["Zone"].keys()))

    existing_elements = hem_input["Zone"][zone_name].get("BuildingElement", {})
    updated_elements = {}

    if update_mode == "Add new UI elements to existing HEM elements":
        updated_elements = deepcopy(existing_elements)

    for row in fabric_elements:
        source_name = str(row.get("source_name", "")).strip()

        if source_name and source_name in existing_elements:
            updated_elements[source_name] = update_existing_hem_element(
                existing_elements[source_name],
                row,
            )
        else:
            new_element = build_hem_building_elements(
                [row],
                existing_elements=updated_elements,
            )
            updated_elements.update(new_element)

    if not updated_elements:
        return hem_input

    hem_input["Zone"][zone_name]["BuildingElement"] = updated_elements

    floor_areas = [
        safe_float(element.get("area_m2"), 0.0)
        for element in fabric_elements
        if element.get("type") == "Ground floor"
    ]
    floor_areas = [area for area in floor_areas if area and area > 0]

    if floor_areas and update_mode == "Replace all existing elements":
        floor_area = sum(floor_areas)
        hem_input["Zone"][zone_name]["area"] = floor_area
        hem_input["Zone"][zone_name]["volume"] = floor_area * 2.7

    return hem_input


def apply_ventilation_to_case(hem_input: dict, ventilation_data: dict) -> dict:
    if not ventilation_data:
        return hem_input

    airtightness_exposure = ventilation_data.get("airtightness_exposure")
    background_vents = ventilation_data.get("background_vents", [])
    mechanical_ventilation = ventilation_data.get("mechanical_ventilation")

    if not airtightness_exposure:
        return hem_input

    hem_input["InfiltrationVentilation"] = build_hem_infiltration_ventilation(
        airtightness_exposure=airtightness_exposure,
        background_vents=background_vents,
        mechanical_ventilation=mechanical_ventilation,
    )

    return hem_input


def clean_thermal_bridge_rows(thermal_bridges: list) -> list[dict]:
    clean_rows = []

    for row in thermal_bridges or []:
        if not isinstance(row, dict):
            continue

        hlc = safe_float(row.get("thermal_bridge_hlc_w_k"))

        if hlc is not None:
            clean_rows.append(row)

    return clean_rows


def apply_thermal_bridges_to_case(
    hem_input: dict,
    thermal_bridges: list,
    zone_name: str = "zone 1",
) -> dict:
    thermal_bridges = clean_thermal_bridge_rows(thermal_bridges)

    if not thermal_bridges:
        return hem_input

    if "Zone" not in hem_input:
        raise KeyError("HEM input does not contain a Zone section.")

    if zone_name not in hem_input["Zone"]:
        zone_name = next(iter(hem_input["Zone"].keys()))

    total_hlc = 0.0

    for bridge in thermal_bridges:
        total_hlc += safe_float(bridge.get("thermal_bridge_hlc_w_k"), 0.0)

    hem_input["Zone"][zone_name]["ThermalBridging"] = total_hlc

    return hem_input


def apply_space_heating_to_case(hem_input: dict, space_heat_systems: dict) -> dict:
    if isinstance(space_heat_systems, dict) and space_heat_systems:
        hem_input["SpaceHeatSystem"] = deepcopy(space_heat_systems)

    return hem_input


def apply_heat_source_wet_to_case(hem_input: dict, heat_source_wet: dict) -> dict:
    """Apply saved HeatSourceWet dictionary to a HEM input."""
    if isinstance(heat_source_wet, dict) and heat_source_wet:
        hem_input["HeatSourceWet"] = deepcopy(heat_source_wet)

    return hem_input



def clean_transparent_elements_in_case(hem_input: dict) -> dict:
    """Remove fields rejected by HEM for BuildingElementTransparent."""
    zones = hem_input.get("Zone", {})

    if not isinstance(zones, dict):
        return hem_input

    for zone in zones.values():
        if not isinstance(zone, dict):
            continue

        elements = zone.get("BuildingElement", {})

        if not isinstance(elements, dict):
            continue

        for element in elements.values():
            if not isinstance(element, dict):
                continue

            if element.get("type") == "BuildingElementTransparent":
                element.pop("area", None)
                element.pop("areal_heat_capacity", None)
                element.pop("mass_distribution_class", None)
                element.pop("solar_absorption_coeff", None)

    return hem_input



def extend_schedule_values(values, hours):
    """Expand HEM schedule lists to cover simulation length."""
    if not isinstance(values, list):
        return values

    expanded = []

    for item in values:
        if isinstance(item, dict) and "repeat" in item and "value" in item:
            repeat = int(item.get("repeat", 1) or 1)
            expanded.extend([item.get("value")] * repeat)
        else:
            expanded.append(item)

    if not expanded:
        return values

    if len(expanded) < hours:
        repeated = []
        while len(repeated) < hours:
            repeated.extend(expanded)
        expanded = repeated[:hours]
    else:
        expanded = expanded[:hours]

    # Compress back to a single repeat block if constant, otherwise keep explicit list.
    if expanded and all(value == expanded[0] for value in expanded):
        return [{"value": expanded[0], "repeat": hours}]

    return expanded


def normalise_mechanical_ventilation_schema(hem_input: dict) -> dict:
    """Convert app-style mechanical ventilation data to HEM MechanicalVentilation schema."""
    iv = hem_input.get("InfiltrationVentilation", {})

    if not isinstance(iv, dict):
        return hem_input

    mech = iv.get("MechanicalVentilation")

    if not isinstance(mech, dict) or not mech:
        return hem_input

    # Already in HEM shape.
    if "mech_vent_1" in mech:
        return hem_input

    vent_type = mech.get("vent_type", "None")

    if str(vent_type).lower() in ["none", "natural", ""]:
        iv.pop("MechanicalVentilation", None)
        return hem_input
    design_flow = float(mech.get("design_flow_m3_h", mech.get("design_flow_l_s", mech.get("design_outdoor_air_flow_rate", 0.0))) or 0.0)
    sfp = float(mech.get("sfp_w_l_s", mech.get("SFP", 0.0)) or 0.0)

    if design_flow <= 0 or sfp <= 0:
        iv.pop("MechanicalVentilation", None)
        return hem_input

    hem_mech = {
        "mech_vent_1": {
            "type": "MechanicalVentilation",
            "vent_type": vent_type,
            "EnergySupply": mech.get("energy_supply", mech.get("EnergySupply", "mains elec")),
            "design_outdoor_air_flow_rate": design_flow,
            "SFP": sfp,
            "SFP_in_use_factor": float(mech.get("sfp_in_use_factor", mech.get("SFP_in_use_factor", 1.0)) or 1.0),
        }
    }

    if str(vent_type).upper() == "MVHR":
        eff = float(mech.get("mvhr_efficiency_percent", mech.get("mvhr_eff", 80.0)) or 80.0)
        if eff > 1.0:
            eff = eff / 100.0
        hem_mech["mech_vent_1"]["mvhr_eff"] = eff

    iv["MechanicalVentilation"] = hem_mech

    hem_input.setdefault("EnergySupply", {})
    hem_input["EnergySupply"].setdefault(
        hem_mech["mech_vent_1"]["EnergySupply"],
        {"fuel": "electricity", "is_export_capable": True},
    )

    return hem_input


def ensure_mechanical_ventilation_in_case(hem_input: dict, ventilation_data: dict) -> dict:
    """Ensure saved mechanical ventilation is written into InfiltrationVentilation."""
    if not isinstance(ventilation_data, dict):
        return hem_input

    mech = None

    for key in ["MechanicalVentilation", "mechanical_ventilation", "mech_vent", "mechanical_ventilation_json"]:
        value = ventilation_data.get(key)
        if isinstance(value, dict) and value:
            mech = value
            break

    # Form-style fallback keys.
    vent_type = ventilation_data.get("mechanical_ventilation_type") or ventilation_data.get("vent_type")
    if mech is None and vent_type and str(vent_type).lower() not in ["none", "natural", "no mechanical ventilation"]:
        mech = {
            "mech_vent_1": {
                "vent_type": vent_type,
                "EnergySupply": ventilation_data.get("energy_supply", "mains elec"),
                "design_outdoor_air_flow_rate": float(ventilation_data.get("design_outdoor_air_flow_rate", 90.0) or 90.0),
                "SFP": float(ventilation_data.get("SFP", ventilation_data.get("sfp", 0.5)) or 0.5),
                "SFP_in_use_factor": float(ventilation_data.get("SFP_in_use_factor", 1.0) or 1.0),
            }
        }
        if str(vent_type).upper() == "MVHR":
            mech["mech_vent_1"]["mvhr_eff"] = float(ventilation_data.get("mvhr_eff", 0.85) or 0.85)

    if not mech:
        return hem_input

    hem_input.setdefault("InfiltrationVentilation", {})
    hem_input["InfiltrationVentilation"]["MechanicalVentilation"] = mech

    hem_input.setdefault("EnergySupply", {})
    hem_input["EnergySupply"].setdefault("mains elec", {"fuel": "electricity", "is_export_capable": True})

    return hem_input


def extend_all_schedules_in_case(hem_input: dict) -> dict:
    """Ensure Control, InternalGains and ApplianceGains schedules cover the simulation length."""
    sim = hem_input.get("SimulationTime", {}) or {}

    try:
        hours = int((float(sim.get("end", 0)) - float(sim.get("start", 0))) / float(sim.get("step", 1)))
    except Exception:
        hours = 0

    if hours <= 0:
        return hem_input

    for section_name in ["Control", "InternalGains", "ApplianceGains"]:
        section = hem_input.get(section_name, {})

        if not isinstance(section, dict):
            continue

        for item in section.values():
            if not isinstance(item, dict):
                continue

            schedule = item.get("schedule")

            if not isinstance(schedule, dict):
                continue

            for schedule_name, values in list(schedule.items()):
                schedule[schedule_name] = extend_schedule_values(values, hours)

            item.setdefault("start_day", 0)
            item.setdefault("time_series_step", 1)

    return hem_input


def extend_cold_water_temperatures_in_case(hem_input: dict) -> dict:
    """Ensure ColdWaterSource temperature arrays cover the simulation length."""
    sim = hem_input.get("SimulationTime", {}) or {}

    try:
        hours = int((float(sim.get("end", 0)) - float(sim.get("start", 0))) / float(sim.get("step", 1)))
    except Exception:
        hours = 0

    if hours <= 0:
        return hem_input

    cold_sources = hem_input.get("ColdWaterSource", {})

    if not isinstance(cold_sources, dict):
        return hem_input

    for source in cold_sources.values():
        if not isinstance(source, dict):
            continue

        temps = source.get("temperatures", [])

        if not isinstance(temps, list):
            temps = []

        if not temps:
            temps = [10.0]

        if len(temps) < hours:
            extended = []
            while len(extended) < hours:
                extended.extend(temps)
            source["temperatures"] = extended[:hours]
        else:
            source["temperatures"] = temps[:hours]

        source.setdefault("start_day", 0)
        source.setdefault("time_series_step", 1)

    return hem_input


def clean_ground_elements_in_case(hem_input: dict) -> dict:
    """Protect HEM validation from invalid generated ground-floor resistance values.

    HEM rejects ground floors where the derived r_vi becomes <= 0. This can happen
    when the simplified fabric UI writes an inconsistent u_value and
    thermal_resistance_floor_construction combination. For now, if a ground element
    has both values and they are clearly inconsistent, remove the explicit u_value
    and let HEM use the construction inputs.
    """
    zones = hem_input.get("Zone", {})

    if not isinstance(zones, dict):
        return hem_input

    for zone in zones.values():
        if not isinstance(zone, dict):
            continue

        elements = zone.get("BuildingElement", {})

        if not isinstance(elements, dict):
            continue

        for element_name, element in elements.items():
            if not isinstance(element, dict):
                continue

            if element.get("type") != "BuildingElementGround":
                continue

            u_value = element.get("u_value")
            r_floor = element.get("thermal_resistance_floor_construction")

            try:
                u_value_f = float(u_value)
                r_floor_f = float(r_floor)
            except (TypeError, ValueError):
                continue

            if u_value_f <= 0:
                element.pop("u_value", None)
                continue

            # If 1/U is less than or equal to the supplied construction resistance,
            # HEM's derived internal resistance can become zero or negative.
            if (1.0 / u_value_f) <= r_floor_f:
                element.pop("u_value", None)

    return hem_input


def apply_hot_water_to_case(hem_input: dict, hot_water_sections: dict) -> dict:
    if not isinstance(hot_water_sections, dict):
        return hem_input

    for section_name in ["HotWaterSource", "HotWaterDemand", "ColdWaterSource"]:
        section_value = hot_water_sections.get(section_name)

        if isinstance(section_value, dict) and section_value:
            hem_input[section_name] = deepcopy(section_value)

    return hem_input


def apply_gains_controls_to_case(hem_input: dict, gains_controls: dict) -> dict:
    if not isinstance(gains_controls, dict):
        return hem_input

    for section_name in ["InternalGains", "ApplianceGains", "Events", "Control"]:
        section_value = gains_controls.get(section_name)

        if isinstance(section_value, dict):
            hem_input[section_name] = deepcopy(section_value)

    return hem_input


def apply_energy_supply_to_case(hem_input: dict, energy_supply: dict) -> dict:
    if isinstance(energy_supply, dict) and energy_supply:
        hem_input["EnergySupply"] = deepcopy(energy_supply)

    return hem_input


def build_full_project_case(
    base_json_path: Path,
    output_json_path: Path,
    project_data: dict,
) -> dict:
    hem_input = load_json(base_json_path)
    project_sections = project_data.get("project_data", {})

    fabric_elements = clean_fabric_rows(project_sections.get("fabric_elements", []))
    fabric_update_mode = project_sections.get(
        "fabric_update_mode",
        "Replace all existing elements",
    )

    ventilation_data = project_sections.get("ventilation", {})
    thermal_bridges = project_sections.get("thermal_bridges", [])
    space_heat_systems = project_sections.get("space_heat_systems", {})
    heat_source_wet = project_sections.get("heat_source_wet", {})
    heating_form = project_sections.get("heating_form", {})
    hot_water_sections = project_sections.get("hot_water", {})
    hot_water_form = project_sections.get("hot_water_form", {})
    gains_controls = project_sections.get("gains_controls", {})
    energy_supply = project_sections.get("energy_supply", {})
    cooling_systems = project_sections.get("cooling_systems", {})

    weather_simulation = project_sections.get("weather_simulation", {})

    hem_input = apply_weather_simulation_to_case(
        hem_input=hem_input,
        weather_simulation=weather_simulation,
    )

    hem_input = apply_fabric_to_case(
        hem_input=hem_input,
        fabric_elements=fabric_elements,
        update_mode=fabric_update_mode,
        zone_name="zone 1",
    )

    hem_input = apply_ventilation_to_case(
        hem_input=hem_input,
        ventilation_data=ventilation_data,
    )

    hem_input = apply_thermal_bridges_to_case(
        hem_input=hem_input,
        thermal_bridges=thermal_bridges,
        zone_name="zone 1",
    )

    hem_input = apply_space_heating_to_case(
        hem_input=hem_input,
        space_heat_systems=space_heat_systems,
    )

    hem_input = apply_heat_source_wet_to_case(
        hem_input=hem_input,
        heat_source_wet=heat_source_wet,
    )

    hem_input = apply_form_heating_to_hem_input(
        hem_input=hem_input,
        heating_data=heating_form,
        zone_name="zone 1",
    )

    hem_input = apply_hot_water_to_case(
        hem_input=hem_input,
        hot_water_sections=hot_water_sections,
    )

    hem_input = apply_gains_controls_to_case(
        hem_input=hem_input,
        gains_controls=gains_controls,
    )

    hem_input = apply_form_hot_water_to_hem_input(
        hem_input=hem_input,
        hot_water_data=hot_water_form,
    )

    # Re-apply form heating after hot water and controls so the generated
    # SpaceHeatSystem control reference is guaranteed to exist.
    hem_input = apply_form_heating_to_hem_input(
        hem_input=hem_input,
        heating_data=heating_form,
        zone_name="zone 1",
    )

    hem_input = apply_energy_supply_to_case(
        hem_input=hem_input,
        energy_supply=energy_supply,
    )

    hem_input = apply_space_cooling_to_hem_input(
        hem_input=hem_input,
        cooling_data=cooling_systems,
        zone_name="zone 1",
    )

    hem_input = ensure_mechanical_ventilation_in_case(hem_input, ventilation_data)

    ventilation_data = project_sections.get("ventilation", {})
    hem_input = ensure_mechanical_ventilation_in_case(hem_input, ventilation_data)

    hem_input = clean_transparent_elements_in_case(hem_input)
    hem_input = clean_ground_elements_in_case(hem_input)
    hem_input = extend_cold_water_temperatures_in_case(hem_input)
    hem_input = extend_all_schedules_in_case(hem_input)
    hem_input = normalise_mechanical_ventilation_schema(hem_input)

    iv = hem_input.get("InfiltrationVentilation", {})
    if isinstance(iv, dict):
        mv = iv.get("MechanicalVentilation", {})
        if isinstance(mv, dict):
            for item in mv.values():
                if isinstance(item, dict):
                    item.pop("type", None)

    iv = hem_input.get("InfiltrationVentilation", {})
    if isinstance(iv, dict):
        mv = iv.get("MechanicalVentilation", {})
        if isinstance(mv, dict):
            for item in mv.values():
                if isinstance(item, dict):
                    item.pop("type", None)
                    if str(item.get("vent_type", "")).upper() == "MVHR":
                        item.setdefault("position_intake", {"mid_height_air_flow_path": 2.0, "orientation360": 0, "pitch": 90})
                        item.setdefault("position_exhaust", {"mid_height_air_flow_path": 2.0, "orientation360": 180, "pitch": 90})
                        item.setdefault("ductwork", [])
                        item.setdefault("sup_air_flw_ctrl", "ODA")
                        item.setdefault("sup_air_temp_ctrl", "NO_CTRL")
                        item.setdefault("mvhr_location", "inside")

    hem_input.pop("_ui_metadata", None)

    hem_input = apply_professional_mappers_to_case(hem_input, project_sections)

    save_json(output_json_path, hem_input)
    return hem_input
