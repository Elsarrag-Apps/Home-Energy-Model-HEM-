from pathlib import Path


def write_file(path: str, content: str) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"Updated {file_path}")


write_file(
    "ui/utils/hem_extractors.py",
    r'''
import json
from pathlib import Path


HEM_SHIELD_TO_UI = {
    "Open": "Open / exposed",
    "Normal": "Normal / suburban",
    "Shielded": "Shielded / dense urban",
}


HEM_TERRAIN_TO_UI = {
    "OpenWater": "Open water",
    "OpenField": "Open country",
    "Suburban": "Suburban",
    "Urban": "Urban",
}


HEM_MECH_TO_UI = {
    "Intermittent MEV": "Intermittent MEV",
    "Centralised continuous MEV": "Centralised continuous MEV",
    "Decentralised continuous MEV": "Decentralised continuous MEV",
    "MVHR": "MVHR",
    "Positive input ventilation": "Positive input ventilation",
}


DEGREES_TO_ORIENTATION = {
    0: "North",
    45: "North East",
    90: "East",
    135: "South East",
    180: "South",
    225: "South West",
    270: "West",
    315: "North West",
}


def load_json_file(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def orientation_from_degrees(value) -> str:
    try:
        degrees = int(round(float(value) / 45) * 45) % 360
    except (TypeError, ValueError):
        return "North"

    return DEGREES_TO_ORIENTATION.get(degrees, "North")


def u_value_from_resistance(value, fallback=0.21) -> float:
    try:
        resistance = float(value)
        if resistance > 0:
            return 1.0 / resistance
    except (TypeError, ValueError):
        pass

    return fallback


def element_type_from_hem(name: str, element: dict) -> str:
    hem_type = element.get("type")

    if hem_type == "BuildingElementTransparent":
        pitch = float(element.get("pitch", 90))
        return "Rooflight" if pitch < 75 else "Window"

    if hem_type == "BuildingElementGround":
        return "Ground floor"

    if hem_type == "BuildingElementPartyWall":
        return "Party wall"

    if hem_type == "BuildingElementOpaque":
        pitch = float(element.get("pitch", 90))
        if pitch < 45:
            return "Roof"
        if pitch > 135:
            return "Exposed floor"
        if "door" in name.lower():
            return "External door"
        return "External wall"

    return "External wall"


def extract_fabric_elements_from_hem(
    hem_json_path: Path,
    zone_name: str = "zone 1",
) -> list[dict]:
    hem_input = load_json_file(hem_json_path)
    zones = hem_input.get("Zone", {})

    if zone_name not in zones:
        if not zones:
            return []
        zone_name = next(iter(zones.keys()))

    building_elements = zones[zone_name].get("BuildingElement", {})
    rows = []

    for name, element in building_elements.items():
        hem_type = element.get("type")
        element_type = element_type_from_hem(name, element)

        area = element.get("area", element.get("total_area", 0.0))

        if hem_type == "BuildingElementGround":
            u_value = float(element.get("u_value", 0.15))
        else:
            fallback = 1.2 if hem_type == "BuildingElementTransparent" else 0.21
            u_value = u_value_from_resistance(
                element.get("thermal_resistance_construction"),
                fallback=fallback,
            )

        height = float(element.get("height", 2.7))
        width = float(element.get("width", 0.0))

        if width <= 0 and height > 0:
            width = float(area) / height

        row = {
            "source_name": name,
            "name": name,
            "type": element_type,
            "area_m2": float(area),
            "u_value_w_m2k": float(u_value),
            "orientation": orientation_from_degrees(
                element.get("orientation360", 0)
            )
            if "orientation360" in element
            else "Not applicable",
            "pitch_degrees": float(element.get("pitch", 90.0)),
            "base_height_m": float(element.get("base_height", 0.0)),
            "height_m": height,
            "width_m": width,
            "mass_class": "Medium",
            "areal_heat_capacity_kj_m2k": float(
                element.get("areal_heat_capacity", 75000)
            )
            / 1000,
            "solar_absorption_coeff": float(
                element.get("solar_absorption_coeff", 0.6)
            ),
            "g_value": float(element.get("g_value", 0.71)),
            "frame_factor": 1.0 - float(element.get("frame_area_fraction", 0.0)),
            "openable_fraction": 0.0,
            "free_area_height_m": float(element.get("free_area_height", 0.2)),
            "perimeter_m": float(element.get("perimeter", 28.0)),
            "thickness_walls_m": float(element.get("thickness_walls", 0.1705)),
            "psi_wall_floor_junc": float(element.get("psi_wall_floor_junc", 0.0)),
            "floor_type": element.get("floor_type", "Slab_no_edge_insulation"),
            "party_wall_cavity_type": element.get("party_wall_cavity_type", "solid"),
            "notes": "Loaded from uploaded HEM JSON",
        }

        rows.append(row)

    return rows


def extract_ventilation_defaults_from_hem(hem_json_path: Path) -> dict:
    hem_input = load_json_file(hem_json_path)
    infil = hem_input.get("InfiltrationVentilation", {})
    leaks = infil.get("Leaks", {})

    airtightness_exposure = {
        "q50_m3_h_m2": float(leaks.get("test_result", 1.2)),
        "test_pressure_pa": float(leaks.get("test_pressure", 50)),
        "envelope_area_m2": float(leaks.get("env_area", 220)),
        "ventilation_zone_height_m": float(leaks.get("ventilation_zone_height", 6)),
        "zone_base_height_m": float(infil.get("ventilation_zone_base_height", 2.5)),
        "altitude_m": float(infil.get("altitude", 30)),
        "shield_class": HEM_SHIELD_TO_UI.get(
            infil.get("shield_class", "Normal"),
            "Normal / suburban",
        ),
        "terrain_class": HEM_TERRAIN_TO_UI.get(
            infil.get("terrain_class", "OpenField"),
            "Open country",
        ),
        "cross_ventilation": bool(infil.get("cross_vent_possible", True)),
    }

    background_vents = []

    for name, vent in infil.get("Vents", {}).items():
        background_vents.append(
            {
                "name": name,
                "area_cm2": float(vent.get("area_cm2", 100)),
                "pressure_difference_ref": float(vent.get("pressure_difference_ref", 20)),
                "mid_height_m": float(vent.get("mid_height_air_flow_path", 1.5)),
                "orientation": orientation_from_degrees(vent.get("orientation360", 180)),
                "pitch": float(vent.get("pitch", 60)),
            }
        )

    mechanical_ventilation = {
        "vent_type": "None",
        "energy_supply": "mains elec",
        "design_flow_l_s": 0.0,
        "sfp_w_l_s": 0.5,
        "sfp_in_use_factor": 1.0,
        "mvhr_efficiency_percent": 0.0,
        "mvhr_location": "inside",
        "intake_orientation": "North",
        "intake_pitch": 90.0,
        "intake_mid_height_m": 2.0,
        "exhaust_orientation": "South",
        "exhaust_pitch": 90.0,
        "exhaust_mid_height_m": 2.0,
    }

    mech_section = infil.get("MechanicalVentilation", {})

    if mech_section:
        first_mech = next(iter(mech_section.values()))
        hem_vent_type = first_mech.get("vent_type", "None")

        mechanical_ventilation["vent_type"] = HEM_MECH_TO_UI.get(
            hem_vent_type,
            "None",
        )
        mechanical_ventilation["energy_supply"] = first_mech.get(
            "EnergySupply",
            "mains elec",
        )
        mechanical_ventilation["design_flow_l_s"] = (
            float(first_mech.get("design_outdoor_air_flow_rate", 0.0)) / 3.6
        )
        mechanical_ventilation["sfp_w_l_s"] = float(first_mech.get("SFP", 0.5))
        mechanical_ventilation["sfp_in_use_factor"] = float(
            first_mech.get("SFP_in_use_factor", 1.0)
        )
        mechanical_ventilation["mvhr_efficiency_percent"] = (
            float(first_mech.get("mvhr_eff", 0.0)) * 100
        )
        mechanical_ventilation["mvhr_location"] = first_mech.get(
            "mvhr_location",
            "inside",
        )

        intake = first_mech.get("position_intake", {})
        exhaust = first_mech.get("position_exhaust", {})

        mechanical_ventilation["intake_orientation"] = orientation_from_degrees(
            intake.get("orientation360", 0)
        )
        mechanical_ventilation["intake_pitch"] = float(intake.get("pitch", 90))
        mechanical_ventilation["intake_mid_height_m"] = float(
            intake.get("mid_height_air_flow_path", 2.0)
        )
        mechanical_ventilation["exhaust_orientation"] = orientation_from_degrees(
            exhaust.get("orientation360", 180)
        )
        mechanical_ventilation["exhaust_pitch"] = float(exhaust.get("pitch", 90))
        mechanical_ventilation["exhaust_mid_height_m"] = float(
            exhaust.get("mid_height_air_flow_path", 2.0)
        )

    return {
        "airtightness_exposure": airtightness_exposure,
        "background_vents": background_vents,
        "mechanical_ventilation": mechanical_ventilation,
    }


def extract_space_heating_systems_from_hem(hem_json_path: Path) -> dict:
    hem_input = load_json_file(hem_json_path)
    return hem_input.get("SpaceHeatSystem", {})


def summarise_space_heating_systems(space_heat_systems: dict) -> list[dict]:
    rows = []

    for name, system in (space_heat_systems or {}).items():
        if isinstance(system, dict):
            rows.append(
                {
                    "name": name,
                    "type": system.get("type", "Unknown"),
                    "energy_supply": system.get("EnergySupply", system.get("energy_supply", "")),
                    "rated_power": system.get("rated_power", ""),
                    "control": system.get("Control", system.get("control", "")),
                }
            )

    return rows


def extract_hot_water_sections_from_hem(hem_json_path: Path) -> dict:
    hem_input = load_json_file(hem_json_path)

    return {
        "HotWaterSource": hem_input.get("HotWaterSource", {}),
        "HotWaterDemand": hem_input.get("HotWaterDemand", {}),
        "ColdWaterSource": hem_input.get("ColdWaterSource", {}),
    }


def summarise_hot_water_sections(hot_water_sections: dict) -> dict:
    hot_sources = hot_water_sections.get("HotWaterSource", {})
    hot_demands = hot_water_sections.get("HotWaterDemand", {})
    cold_sources = hot_water_sections.get("ColdWaterSource", {})

    return {
        "hot_water_source_count": len(hot_sources) if isinstance(hot_sources, dict) else 0,
        "hot_water_demand_count": len(hot_demands) if isinstance(hot_demands, dict) else 0,
        "cold_water_source_count": len(cold_sources) if isinstance(cold_sources, dict) else 0,
    }


def summarise_active_hem_case(hem_json_path: Path) -> dict:
    hem_input = load_json_file(hem_json_path)

    zones = hem_input.get("Zone", {})
    infil = hem_input.get("InfiltrationVentilation", {})
    space_heat = hem_input.get("SpaceHeatSystem", {})
    hot_water_source = hem_input.get("HotWaterSource", {})
    hot_water_demand = hem_input.get("HotWaterDemand", {})

    fabric_counts = {
        "opaque": 0,
        "transparent": 0,
        "ground": 0,
        "party_wall": 0,
    }

    for zone in zones.values():
        for element in zone.get("BuildingElement", {}).values():
            element_type = element.get("type")

            if element_type == "BuildingElementOpaque":
                fabric_counts["opaque"] += 1
            elif element_type == "BuildingElementTransparent":
                fabric_counts["transparent"] += 1
            elif element_type == "BuildingElementGround":
                fabric_counts["ground"] += 1
            elif element_type == "BuildingElementPartyWall":
                fabric_counts["party_wall"] += 1

    return {
        "zone_count": len(zones),
        "has_infiltration_ventilation": bool(infil),
        "background_vent_count": len(infil.get("Vents", {})),
        "mechanical_ventilation_count": len(infil.get("MechanicalVentilation", {})),
        "space_heating_system_count": len(space_heat),
        "hot_water_source_count": len(hot_water_source),
        "hot_water_demand_count": len(hot_water_demand),
        "fabric_counts": fabric_counts,
    }
''',
)


write_file(
    "ui/utils/full_case_builder.py",
    r'''
import json
from copy import deepcopy
from pathlib import Path

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


def apply_hot_water_to_case(hem_input: dict, hot_water_sections: dict) -> dict:
    if not isinstance(hot_water_sections, dict):
        return hem_input

    for section_name in ["HotWaterSource", "HotWaterDemand", "ColdWaterSource"]:
        section_value = hot_water_sections.get(section_name)

        if isinstance(section_value, dict) and section_value:
            hem_input[section_name] = deepcopy(section_value)

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
    hot_water_sections = project_sections.get("hot_water", {})

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

    hem_input = apply_hot_water_to_case(
        hem_input=hem_input,
        hot_water_sections=hot_water_sections,
    )

    save_json(output_json_path, hem_input)
    return hem_input
''',
)


write_file(
    "ui/pages/7_Hot_Water.py",
    r'''
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
from project_store import get_project_data_section, update_project_data


st.set_page_config(
    page_title="Hot Water",
    layout="wide",
)

st.title("Hot Water")

st.write(
    "Review and edit the hot water sections loaded from the active HEM case. "
    "For this first connected version, the official HEM JSON structure is preserved. "
    "Later, this can be converted into simplified hot-water input forms."
)

BASE_JSON_PATH = Path("ui/temp/active_hem_input.json")

if not BASE_JSON_PATH.exists():
    st.error(
        "No active HEM input found. Go to the Home page and upload/load a HEM JSON first."
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

st.header("1. Input source")

col1, col2 = st.columns(2)

with col1:
    if st.button("Restore hot water sections from uploaded HEM JSON"):
        load_hot_water_defaults_into_state(force_reload=True)
        update_project_data("hot_water", st.session_state["hot_water_sections"])
        st.success("Hot water sections restored from uploaded HEM JSON.")
        st.rerun()

with col2:
    if st.button("Clear hot water sections"):
        clear_hot_water_state()
        update_project_data("hot_water", {})
        st.warning("Hot water sections cleared. The uploaded HEM case is still loaded.")
        st.rerun()

hot_water_sections = st.session_state.get("hot_water_sections", {})

st.header("2. Hot water summary")

summary = summarise_hot_water_sections(hot_water_sections)

c1, c2, c3 = st.columns(3)

with c1:
    st.metric("Hot water sources", summary["hot_water_source_count"])

with c2:
    st.metric("Hot water demand entries", summary["hot_water_demand_count"])

with c3:
    st.metric("Cold water sources", summary["cold_water_source_count"])

st.header("3. Edit hot-water JSON")

st.caption(
    "This editor preserves the official HEM HotWaterSource, HotWaterDemand and "
    "ColdWaterSource structure. Only edit this JSON if you know the HEM schema."
)

hot_water_json_text = st.text_area(
    "Hot water JSON",
    value=json.dumps(hot_water_sections, indent=2),
    height=520,
)

col_save, col_validate = st.columns(2)

with col_validate:
    if st.button("Validate hot-water JSON"):
        try:
            parsed = json.loads(hot_water_json_text)
            if not isinstance(parsed, dict):
                st.error("Hot water JSON must be a JSON object/dictionary.")
            else:
                st.success("Hot water JSON is valid JSON.")
        except json.JSONDecodeError as exc:
            st.error("Hot water JSON is not valid.")
            st.code(str(exc))

with col_save:
    if st.button("Save hot water to project"):
        try:
            parsed = json.loads(hot_water_json_text)
            if not isinstance(parsed, dict):
                st.error("Hot water JSON must be a JSON object/dictionary.")
            else:
                st.session_state["hot_water_sections"] = parsed
                update_project_data("hot_water", parsed)
                st.success("Hot water sections saved to the app project.")
        except json.JSONDecodeError as exc:
            st.error("Hot water JSON is not valid.")
            st.code(str(exc))

st.header("4. Project save status")

if st.session_state.get("hot_water_sections"):
    st.success("Hot water sections are available for the central Run HEM / Results page.")
else:
    st.info("No hot water sections are currently saved.")

with st.expander("Developer/debug: view saved hot water sections", expanded=False):
    st.json(st.session_state.get("hot_water_sections", {}))
''',
)


write_file(
    "ui/pages/9_Run_HEM_Results.py",
    r'''
import json
import sys
from pathlib import Path

import streamlit as st

CURRENT_DIR = Path(__file__).resolve().parent
UI_DIR = CURRENT_DIR.parent
UTILS_DIR = UI_DIR / "utils"
sys.path.append(str(UTILS_DIR))

from full_case_builder import build_full_project_case
from model_runner import run_hem_model
from project_store import ACTIVE_HEM_INPUT_PATH, get_active_project
from results_parser import compare_summary_metrics, format_number


st.set_page_config(
    page_title="Run HEM / Results",
    layout="wide",
)

st.title("Run HEM / Results")

st.write(
    "Build one full HEM input file from the active uploaded case and the saved "
    "inputs from each tab, then run HEM and compare the generated case against "
    "the uploaded baseline."
)

GENERATED_FULL_CASE_PATH = Path("ui/temp/generated_full_project_case.json")

GENERATED_SUMMARY_PATH = Path(
    "ui/temp/generated_full_project_case__results/"
    "generated_full_project_case__core__results_summary.csv"
)

BASE_SUMMARY_PATH = Path(
    "test/e2e/demo_files/short/demo__results/"
    "demo__core__results_summary.csv"
)

DEFAULT_WEATHER_FILE = Path("test/e2e/demo_files/London_weather_CIBSE_format.csv")

active_project = get_active_project()

if active_project is None:
    st.error("No active project loaded. Go to the Home page and upload/load a JSON first.")
    st.stop()

if not ACTIVE_HEM_INPUT_PATH.exists():
    st.error("No active HEM input file found. Go to the Home page and upload/load a HEM JSON first.")
    st.stop()

project_data = active_project.get("project_data", {})

st.header("1. Project build summary")

fabric_rows = project_data.get("fabric_elements", [])
ventilation = project_data.get("ventilation", {})
thermal_bridges = project_data.get("thermal_bridges", [])
weather_settings = project_data.get("weather_simulation", {})
space_heat_systems = project_data.get("space_heat_systems", {})
hot_water = project_data.get("hot_water", {})

col1, col2, col3, col4, col5, col6 = st.columns(6)

with col1:
    st.metric("Fabric rows", len(fabric_rows))

with col2:
    st.metric(
        "Ventilation",
        "Yes" if ventilation.get("airtightness_exposure") else "No",
    )

with col3:
    st.metric("Thermal bridges", len(thermal_bridges))

with col4:
    st.metric(
        "Heating systems",
        len(space_heat_systems) if isinstance(space_heat_systems, dict) else 0,
    )

with col5:
    st.metric(
        "Hot water",
        "Yes" if hot_water else "No",
    )

with col6:
    st.metric(
        "Weather",
        "Yes" if weather_settings.get("weather_file") else "Default",
    )

st.header("2. Weather used for this run")

weather_file = Path(
    weather_settings.get(
        "weather_file",
        str(DEFAULT_WEATHER_FILE),
    )
)

if not weather_file.exists():
    st.warning(
        f"Saved weather file was not found: {weather_file}. "
        "The run will use the default London CIBSE demo weather file."
    )
    weather_file = DEFAULT_WEATHER_FILE

w1, w2 = st.columns(2)

with w1:
    st.metric("Weather file type", weather_file.suffix.lower().replace(".", "") or "unknown")

with w2:
    st.write(str(weather_file))

st.header("3. Build generated HEM input")

if st.button("Build full HEM input from saved project values"):
    try:
        generated_case = build_full_project_case(
            base_json_path=ACTIVE_HEM_INPUT_PATH,
            output_json_path=GENERATED_FULL_CASE_PATH,
            project_data=active_project,
        )

        st.session_state["generated_full_case_ready"] = True
        st.session_state["last_generated_full_case"] = generated_case

        st.success(f"Generated full HEM input saved to: {GENERATED_FULL_CASE_PATH}")

    except Exception as exc:
        st.error("Failed to build full HEM input.")
        with st.expander("Developer/debug: build error", expanded=True):
            st.exception(exc)

if st.session_state.get("generated_full_case_ready"):
    st.info("Generated HEM input is ready to run.")

    with st.expander("Advanced: view generated full HEM JSON", expanded=False):
        generated_case = st.session_state.get("last_generated_full_case")

        if generated_case is not None:
            st.json(generated_case)
        elif GENERATED_FULL_CASE_PATH.exists():
            st.json(json.loads(GENERATED_FULL_CASE_PATH.read_text(encoding="utf-8")))
        else:
            st.write("No generated case found.")

st.header("4. Run HEM and compare results")

if not st.session_state.get("generated_full_case_ready"):
    st.warning("Build the full HEM input before running HEM.")
else:
    if st.button("Run HEM and compare full project case"):
        with st.spinner("Running HEM..."):
            result = run_hem_model(GENERATED_FULL_CASE_PATH, weather_file)

        if result.returncode == 0:
            st.success("HEM run completed successfully.")

            if GENERATED_SUMMARY_PATH.exists():
                summary_text = GENERATED_SUMMARY_PATH.read_text(encoding="utf-8")

                st.subheader("Results comparison")

                if BASE_SUMMARY_PATH.exists():
                    comparison = compare_summary_metrics(
                        BASE_SUMMARY_PATH,
                        GENERATED_SUMMARY_PATH,
                    )

                    col1, col2, col3, col4 = st.columns(4)

                    space_heat = next(
                        item
                        for item in comparison
                        if item["metric"] == "Space heat demand"
                    )

                    peak_elec = next(
                        item
                        for item in comparison
                        if item["metric"] == "Peak electricity consumption"
                    )

                    delivered = next(
                        item
                        for item in comparison
                        if item["metric"] == "Delivered energy total"
                    )

                    mech_vent = next(
                        item
                        for item in comparison
                        if item["metric"] == "Mechanical ventilation energy"
                    )

                    with col1:
                        st.metric(
                            "Space heat demand",
                            f"{format_number(space_heat['generated_value'])} {space_heat['unit']}",
                            f"{format_number(space_heat['difference'])} {space_heat['unit']}",
                        )

                    with col2:
                        st.metric(
                            "Peak electricity",
                            f"{format_number(peak_elec['generated_value'])} {peak_elec['unit']}",
                            f"{format_number(peak_elec['difference'])} {peak_elec['unit']}",
                        )

                    with col3:
                        st.metric(
                            "Delivered energy",
                            f"{format_number(delivered['generated_value'])} {delivered['unit']}",
                            f"{format_number(delivered['difference'])} {delivered['unit']}",
                        )

                    with col4:
                        st.metric(
                            "Mechanical ventilation",
                            f"{format_number(mech_vent['generated_value'])} {mech_vent['unit']}",
                            f"{format_number(mech_vent['difference'])} {mech_vent['unit']}",
                        )

                    with st.expander("Detailed comparison table", expanded=False):
                        st.dataframe(
                            comparison,
                            use_container_width=True,
                            hide_index=True,
                        )

                else:
                    st.warning(
                        "Baseline summary file was not found. "
                        "Run a baseline case first if comparison is needed."
                    )

                with st.expander("View full HEM summary output", expanded=False):
                    st.text(summary_text)

                st.download_button(
                    "Download HEM summary CSV",
                    data=summary_text,
                    file_name="generated_full_project_case__core__results_summary.csv",
                    mime="text/csv",
                )

                generated_json_text = GENERATED_FULL_CASE_PATH.read_text(
                    encoding="utf-8"
                )

                st.download_button(
                    "Download generated HEM input JSON",
                    data=generated_json_text,
                    file_name="generated_full_project_case.json",
                    mime="application/json",
                )

            else:
                st.warning("HEM ran, but the expected summary file was not found.")

        else:
            st.error("HEM run failed.")
            st.subheader("Error output")
            st.code(result.stderr)

            if result.stdout:
                st.subheader("Model output")
                st.code(result.stdout)

with st.expander("Developer/debug: saved project data used for this run", expanded=False):
    st.json(project_data)
''',
)


print("Batch cleanup J complete.")