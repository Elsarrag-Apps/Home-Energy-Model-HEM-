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


def load_base_hem_json(base_json_path: Path) -> dict:
    """Load a base HEM input JSON file."""
    with open(base_json_path, "r", encoding="utf-8") as f:
        return json.load(f)


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