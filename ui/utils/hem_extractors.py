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
    """Convert HEM orientation degrees to nearest UI orientation label."""
    try:
        degrees = int(round(float(value) / 45) * 45) % 360
    except (TypeError, ValueError):
        return "North"

    return DEGREES_TO_ORIENTATION.get(degrees, "North")


def u_value_from_resistance(value, fallback=0.21) -> float:
    """Convert HEM thermal resistance to approximate U-value."""
    try:
        resistance = float(value)
        if resistance > 0:
            return 1.0 / resistance
    except (TypeError, ValueError):
        pass

    return fallback


def element_type_from_hem(name: str, element: dict) -> str:
    """Map HEM BuildingElement type to user-facing element type."""
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
    """Extract editable fabric rows from HEM Zone -> BuildingElement."""
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
            "party_wall_cavity_type": element.get(
                "party_wall_cavity_type",
                "solid",
            ),
            "notes": "Loaded from uploaded HEM JSON",
        }

        rows.append(row)

    return rows


def extract_ventilation_defaults_from_hem(hem_json_path: Path) -> dict:
    """Extract UI-friendly infiltration and ventilation defaults from HEM JSON."""
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
                "pressure_difference_ref": float(
                    vent.get("pressure_difference_ref", 20)
                ),
                "mid_height_m": float(
                    vent.get("mid_height_air_flow_path", 1.5)
                ),
                "orientation": orientation_from_degrees(
                    vent.get("orientation360", 180)
                ),
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


def summarise_active_hem_case(hem_json_path: Path) -> dict:
    """Return a user-friendly summary of the active HEM case."""
    hem_input = load_json_file(hem_json_path)

    zones = hem_input.get("Zone", {})
    infil = hem_input.get("InfiltrationVentilation", {})

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
        "fabric_counts": fabric_counts,
    }
