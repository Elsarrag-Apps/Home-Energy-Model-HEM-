import json
from pathlib import Path


ORIENTATION_TO_DEGREES = {
    "North": 0,
    "North East": 45,
    "East": 90,
    "South East": 135,
    "South": 180,
    "South West": 225,
    "West": 270,
    "North West": 315,
    "Roof / horizontal": 0,
    "Horizontal": 0,
    "Not applicable": 0,
}


SHIELD_CLASS_TO_HEM = {
    "Open / exposed": "Open",
    "Normal / suburban": "Normal",
    "Shielded / dense urban": "Shielded",
}


TERRAIN_CLASS_TO_HEM = {
    "Open water": "OpenWater",
    "Open country": "OpenField",
    "Suburban": "Suburban",
    "Urban": "Urban",
}


MECHANICAL_TYPE_TO_HEM = {
    "None": None,
    "Intermittent MEV": "Intermittent MEV",
    "Centralised continuous MEV": "Centralised continuous MEV",
    "Decentralised continuous MEV": "Decentralised continuous MEV",
    "MVHR": "MVHR",
    "Positive input ventilation": "Positive input ventilation",
}


MASS_CLASS_TO_HEM = {
    "External": "I",
    "Internal": "I",
    "Lightweight": "D",
    "Medium": "I",
    "Heavy": "I",
    "Very heavy": "I",
    "Unknown": "I",
}


def load_base_hem_json(base_json_path: Path) -> dict:
    """Load a base HEM input JSON file."""
    with open(base_json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def u_value_to_resistance(u_value: float) -> float:
    """Convert a UI U-value to a simple thermal resistance.

    This is a first-pass mapping for HEM input generation. Later, if needed,
    this can be refined to account for HEM's surface resistance convention.
    """
    if u_value <= 0:
        raise ValueError("U-value must be greater than zero.")
    return 1.0 / u_value


def build_hem_infiltration_ventilation(
    airtightness_exposure: dict,
    background_vents: list,
    mechanical_ventilation: dict | None = None,
) -> dict:
    """Build the HEM InfiltrationVentilation section from UI inputs."""

    vents = {}

    for index, vent in enumerate(background_vents, start=1):
        vent_name = f"vent{index}"

        area_cm2 = vent.get("area_cm2", vent.get("equivalent_area_cm2"))

        if area_cm2 is None:
            raise KeyError(
                "Vent area is missing. Expected 'area_cm2' or "
                f"'equivalent_area_cm2'. Vent data received: {vent}"
            )

        vents[vent_name] = {
            "mid_height_air_flow_path": float(vent["mid_height_m"]),
            "area_cm2": float(area_cm2),
            "pressure_difference_ref": float(vent["pressure_difference_ref"]),
            "orientation360": ORIENTATION_TO_DEGREES.get(
                vent["orientation"],
                0,
            ),
            "pitch": float(vent["pitch"]),
        }

    infiltration_ventilation = {
        "cross_vent_possible": bool(airtightness_exposure["cross_ventilation"]),
        "shield_class": SHIELD_CLASS_TO_HEM[airtightness_exposure["shield_class"]],
        "terrain_class": TERRAIN_CLASS_TO_HEM[airtightness_exposure["terrain_class"]],
        "ventilation_zone_base_height": float(
            airtightness_exposure["zone_base_height_m"]
        ),
        "altitude": float(airtightness_exposure["altitude_m"]),
        "Vents": vents,
        "Leaks": {
            "ventilation_zone_height": float(
                airtightness_exposure["ventilation_zone_height_m"]
            ),
            "test_pressure": float(airtightness_exposure["test_pressure_pa"]),
            "test_result": float(airtightness_exposure["q50_m3_h_m2"]),
            "env_area": float(airtightness_exposure["envelope_area_m2"]),
        },
    }

    if mechanical_ventilation and mechanical_ventilation.get("vent_type") != "None":
        vent_type = MECHANICAL_TYPE_TO_HEM[mechanical_ventilation["vent_type"]]

        mech_system = {
            "EnergySupply": mechanical_ventilation["energy_supply"],
            "SFP": float(mechanical_ventilation["sfp_w_l_s"]),
            "SFP_in_use_factor": float(mechanical_ventilation["sfp_in_use_factor"]),
            "design_outdoor_air_flow_rate": float(
                mechanical_ventilation["design_flow_l_s"]
            )
            * 3.6,
            "vent_type": vent_type,
            "ductwork": [],
            "sup_air_flw_ctrl": "ODA",
            "sup_air_temp_ctrl": "NO_CTRL",
        }

        if vent_type == "MVHR":
            mech_system["mvhr_eff"] = (
                float(mechanical_ventilation["mvhr_efficiency_percent"]) / 100
            )
            mech_system["mvhr_location"] = mechanical_ventilation["mvhr_location"]

            mech_system["position_intake"] = {
                "orientation360": ORIENTATION_TO_DEGREES[
                    mechanical_ventilation["intake_orientation"]
                ],
                "pitch": float(mechanical_ventilation["intake_pitch"]),
                "mid_height_air_flow_path": float(
                    mechanical_ventilation["intake_mid_height_m"]
                ),
            }

            mech_system["position_exhaust"] = {
                "orientation360": ORIENTATION_TO_DEGREES[
                    mechanical_ventilation["exhaust_orientation"]
                ],
                "pitch": float(mechanical_ventilation["exhaust_pitch"]),
                "mid_height_air_flow_path": float(
                    mechanical_ventilation["exhaust_mid_height_m"]
                ),
            }

        else:
            mech_system["orientation360"] = ORIENTATION_TO_DEGREES[
                mechanical_ventilation["exhaust_orientation"]
            ]
            mech_system["pitch"] = float(mechanical_ventilation["exhaust_pitch"])
            mech_system["mid_height_air_flow_path"] = float(
                mechanical_ventilation["exhaust_mid_height_m"]
            )

        infiltration_ventilation["MechanicalVentilation"] = {
            "mech_vent_1": mech_system
        }

    return infiltration_ventilation


def build_generated_hem_input(
    base_json_path: Path,
    output_json_path: Path,
    airtightness_exposure: dict,
    background_vents: list,
    mechanical_ventilation: dict | None = None,
) -> dict:
    """Load base HEM JSON, replace InfiltrationVentilation, and save new JSON."""

    hem_input = load_base_hem_json(base_json_path)

    hem_input["InfiltrationVentilation"] = build_hem_infiltration_ventilation(
        airtightness_exposure=airtightness_exposure,
        background_vents=background_vents,
        mechanical_ventilation=mechanical_ventilation,
    )

    output_json_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(hem_input, f, indent=2)

    return hem_input


def build_hem_building_elements(fabric_elements: list) -> dict:
    """Build HEM Zone -> BuildingElement dictionary from UI fabric inputs."""

    building_elements = {}

    wall_count = 0
    roof_count = 0
    window_count = 0
    party_wall_count = 0
    ground_count = 0

    for element in fabric_elements:
        element_type = element["type"]
        area = float(element["area_m2"])
        u_value = float(element["u_value_w_m2k"])
        resistance = u_value_to_resistance(u_value)
        pitch = float(element["pitch_degrees"])
        orientation = ORIENTATION_TO_DEGREES.get(element["orientation"], 0)

        height = float(element.get("height_m", 2.7))
        width = float(element.get("width_m", area / height if height > 0 else area))
        base_height = float(element.get("base_height_m", 0.0))

        areal_heat_capacity = float(
            element.get("areal_heat_capacity_j_m2k")
            or element.get("areal_heat_capacity_kj_m2k", 75.0) * 1000
        )

        mass_class = MASS_CLASS_TO_HEM.get(
            element.get("mass_class", "Medium"),
            "I",
        )

        if element_type in ["External wall", "Roof", "External door", "Exposed floor"]:
            if element_type == "Roof":
                name = f"roof {roof_count}"
                roof_count += 1
            else:
                name = f"wall {wall_count}"
                wall_count += 1

            element_json = {
                "type": "BuildingElementOpaque",
                "solar_absorption_coeff": float(
                    element.get("solar_absorption_coeff") or 0.6
                ),
                "thermal_resistance_construction": resistance,
                "areal_heat_capacity": areal_heat_capacity,
                "mass_distribution_class": mass_class,
                "pitch": pitch,
                "orientation360": orientation,
                "base_height": base_height,
                "height": height,
                "width": width,
                "area": area,
            }

            if element_type == "Roof":
                element_json["is_unheated_pitched_roof"] = False

            building_elements[name] = element_json

        elif element_type in ["Window", "Rooflight"]:
            name = f"window {window_count}"
            window_count += 1

            frame_factor = float(element.get("frame_factor") or 0.70)
            frame_area_fraction = max(0.0, min(1.0, 1.0 - frame_factor))

            openable_fraction = float(element.get("openable_fraction") or 0.0)
            max_window_open_area = area * openable_fraction

            mid_height = base_height + height / 2

            building_elements[name] = {
                "type": "BuildingElementTransparent",
                "thermal_resistance_construction": resistance,
                "pitch": pitch,
                "orientation360": orientation,
                "g_value": float(element.get("g_value") or 0.63),
                "frame_area_fraction": frame_area_fraction,
                "base_height": base_height,
                "height": height,
                "width": width,
                "free_area_height": float(element.get("free_area_height_m") or 0.2),
                "mid_height": mid_height,
                "max_window_open_area": max_window_open_area,
                "window_part_list": [
                    {
                        "mid_height_air_flow_path": mid_height,
                    }
                ],
                "shading": [],
            }

        elif element_type == "Ground floor":
            name = "ground" if ground_count == 0 else f"ground {ground_count}"
            ground_count += 1

            perimeter = float(element.get("perimeter_m") or 28.0)

            building_elements[name] = {
                "type": "BuildingElementGround",
                "total_area": area,
                "area": area,
                "pitch": 180.0,
                "u_value": u_value,
                "thermal_resistance_floor_construction": resistance,
                "areal_heat_capacity": areal_heat_capacity,
                "mass_distribution_class": mass_class,
                "floor_type": element.get("floor_type") or "Slab_no_edge_insulation",
                "thickness_walls": float(element.get("thickness_walls_m") or 0.1705),
                "perimeter": perimeter,
                "psi_wall_floor_junc": float(element.get("psi_wall_floor_junc") or 0.0),
            }

        elif element_type == "Party wall":
            name = f"wall {wall_count + party_wall_count}"
            party_wall_count += 1

            building_elements[name] = {
                "type": "BuildingElementPartyWall",
                "thermal_resistance_construction": resistance,
                "party_wall_cavity_type": element.get("party_wall_cavity_type")
                or "solid",
                "areal_heat_capacity": areal_heat_capacity,
                "mass_distribution_class": mass_class,
                "pitch": pitch,
                "area": area,
            }

        else:
            # Skip unsupported element types in the first HEM-connected fabric pass.
            continue

    return building_elements


def build_generated_fabric_input(
    base_json_path: Path,
    output_json_path: Path,
    fabric_elements: list,
    zone_name: str = "zone 1",
) -> dict:
    """Load base HEM JSON, replace Zone -> BuildingElement, and save new JSON."""

    hem_input = load_base_hem_json(base_json_path)

    if "Zone" not in hem_input:
        raise KeyError("Base HEM input does not contain a Zone section.")

    if zone_name not in hem_input["Zone"]:
        raise KeyError(f"Zone '{zone_name}' not found in base HEM input.")

    building_elements = build_hem_building_elements(fabric_elements)

    if not building_elements:
        raise ValueError("No supported fabric elements were provided.")

    hem_input["Zone"][zone_name]["BuildingElement"] = building_elements

    # Update zone area and volume roughly from ground/floor area if available.
    floor_areas = [
        float(element["area_m2"])
        for element in fabric_elements
        if element["type"] == "Ground floor"
    ]

    if floor_areas:
        floor_area = sum(floor_areas)
        hem_input["Zone"][zone_name]["area"] = floor_area
        hem_input["Zone"][zone_name]["volume"] = floor_area * 2.7

    output_json_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(hem_input, f, indent=2)

    return hem_input