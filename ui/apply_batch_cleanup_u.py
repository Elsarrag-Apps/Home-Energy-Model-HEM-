from pathlib import Path


def write_file(path, content):
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"Updated {file_path}")


write_file(
    "ui/utils/hvac_mapper.py",
    """
from copy import deepcopy


def safe_float(value, default=0.0):
    try:
        if value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def build_space_cool_system_from_app(cooling_data: dict) -> dict:
    \"\"\"Build a valid HEM SpaceCoolSystem dictionary from app cooling inputs.

    Current supported HEM cooling type from inspected examples:
    - AirConditioning
    \"\"\"
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
    \"\"\"Build a HEM cooling setpoint control from app cooling inputs.\"\"\"
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
    \"\"\"Apply generated SpaceCoolSystem, cooling Control, and Zone reference.\"\"\"
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
    \"\"\"Return simple UI insight metrics for cooling inputs.\"\"\"
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
""",
)


# Patch full_case_builder.py
full_case_path = Path("ui/utils/full_case_builder.py")
text = full_case_path.read_text(encoding="utf-8")

if "from hvac_mapper import apply_space_cooling_to_hem_input" not in text:
    text = text.replace(
        "from input_builder import (\n",
        "from hvac_mapper import apply_space_cooling_to_hem_input\nfrom input_builder import (\n",
        1,
    )

if "cooling_systems = project_sections.get(\"cooling_systems\", {})" not in text:
    text = text.replace(
        "    energy_supply = project_sections.get(\"energy_supply\", {})\n",
        "    energy_supply = project_sections.get(\"energy_supply\", {})\n    cooling_systems = project_sections.get(\"cooling_systems\", {})\n",
        1,
    )

if "hem_input = apply_space_cooling_to_hem_input(" not in text:
    text = text.replace(
        """    hem_input = apply_energy_supply_to_case(
        hem_input=hem_input,
        energy_supply=energy_supply,
    )

    save_json(output_json_path, hem_input)
""",
        """    hem_input = apply_energy_supply_to_case(
        hem_input=hem_input,
        energy_supply=energy_supply,
    )

    hem_input = apply_space_cooling_to_hem_input(
        hem_input=hem_input,
        cooling_data=cooling_systems,
        zone_name="zone 1",
    )

    save_json(output_json_path, hem_input)
""",
        1,
    )

full_case_path.write_text(text, encoding="utf-8")
print("Patched ui/utils/full_case_builder.py")


# Patch Heating & Cooling page to clarify cooling is now connected
hvac_page = Path("ui/pages/6_Heating_Cooling_Systems.py")
text = hvac_page.read_text(encoding="utf-8")

if "from hvac_mapper import summarise_cooling_inputs" not in text:
    text = text.replace(
        "from hem_extractors import (\n",
        "from hvac_mapper import summarise_cooling_inputs\nfrom hem_extractors import (\n",
        1,
    )

text = text.replace(
    """st.write(
    "Review and edit heating systems from the active HEM case, and record cooling "
    "system intent. Heating is currently connected to HEM through SpaceHeatSystem. "
    "Cooling will be written to HEM once a valid SpaceCoolSystem schema example is available."
)
""",
    """st.write(
    "Review and edit heating systems from the active HEM case, and configure active cooling. "
    "Heating is currently preserved through SpaceHeatSystem. Cooling is mapped to HEM "
    "using the validated SpaceCoolSystem AirConditioning pattern."
)
""",
)

text = text.replace(
    """st.info(
    "No SpaceCoolSystem section was found in the uploaded demo HEM JSON. "
    "Cooling settings below are saved in the app project for now, but are not "
    "yet written into the generated HEM JSON until a valid HEM cooling schema is confirmed."
)
""",
    """st.info(
    "Cooling is now connected using the HEM AirConditioning SpaceCoolSystem schema. "
    "The generated HEM file will include SpaceCoolSystem, a cooling control, and a "
    "Zone reference when cooling is enabled."
)
""",
)

# Add frac_convective field after COP input if not already present
if "Cooling convective fraction" not in text:
    text = text.replace(
        """        cooling_cop = st.number_input(
            "Cooling COP / EER",
            min_value=0.0,
            value=float(saved_cooling.get("cooling_cop", 3.0)),
            step=0.1,
        )
""",
        """        cooling_cop = st.number_input(
            "Cooling COP / EER",
            min_value=0.0,
            value=float(saved_cooling.get("cooling_cop", 3.0)),
            step=0.1,
        )

        frac_convective = st.number_input(
            "Cooling convective fraction",
            min_value=0.0,
            max_value=1.0,
            value=float(saved_cooling.get("frac_convective", 0.95)),
            step=0.05,
        )
""",
        1,
    )

# Add mapper fields to saved cooling data
text = text.replace(
    """        "cooling_cop": cooling_cop,
        "cooling_setpoint_c": cooling_setpoint_c,
        "cooling_energy_supply": cooling_energy_supply,
        "cooling_notes": cooling_notes,
        "hem_connection_status": "not_written_until_space_cool_schema_confirmed",
""",
    """        "cooling_cop": cooling_cop,
        "frac_convective": frac_convective,
        "cooling_setpoint_c": cooling_setpoint_c,
        "cooling_energy_supply": cooling_energy_supply,
        "cooling_notes": cooling_notes,
        "hem_system_name": "cooling system 1",
        "hem_control_name": "cooling_system_1_control",
        "hem_connection_status": "written_to_space_cool_system_when_enabled",
""",
)

# Add cooling insight block before project save status
if "Cooling input insight" not in text:
    text = text.replace(
        """st.header("4. Project save status")
""",
        """st.subheader("Cooling input insight")

current_cooling = get_project_data_section("cooling_systems", {}) or {}
project_setup = get_project_data_section("project_setup", {}) or {}
floor_area = float(project_setup.get("floor_area_m2", 0) or 0)
cooling_summary = summarise_cooling_inputs(current_cooling, floor_area_m2=floor_area)

ci1, ci2, ci3, ci4 = st.columns(4)

with ci1:
    st.metric("Cooling enabled", "Yes" if cooling_summary["enabled"] else "No")

with ci2:
    st.metric("Cooling capacity", f"{cooling_summary['capacity_kw']:.2f} kW")

with ci3:
    st.metric("Cooling COP/EER", f"{cooling_summary['cop']:.2f}")

with ci4:
    st.metric("Capacity intensity", f"{cooling_summary['capacity_w_m2']:.1f} W/m2")

if cooling_summary["status"] == "OK":
    st.success("Cooling input check: OK")
else:
    st.warning(cooling_summary["status"])

st.header("4. Project save status")
""",
        1,
    )

hvac_page.write_text(text, encoding="utf-8")
print("Patched ui/pages/6_Heating_Cooling_Systems.py")


# Patch validation to catch invalid cooling before build
validation_path = Path("ui/utils/project_validation.py")
text = validation_path.read_text(encoding="utf-8")

if "def validate_cooling" not in text:
    insert_after = """def validate_ventilation(project_data: dict) -> list[dict]:
"""
    validator = """
def validate_cooling(project_data: dict) -> list[dict]:
    messages = []

    cooling = project_data.get("cooling_systems", {}) or {}

    if not cooling:
        return messages

    if not cooling.get("cooling_enabled", False):
        return messages

    capacity = safe_float(cooling.get("cooling_capacity_kw"), 0.0)
    cop = safe_float(cooling.get("cooling_cop"), 0.0)
    cooling_type = str(cooling.get("cooling_type", "None")).strip()

    if cooling_type.lower() == "none":
        messages.append(
            {
                "level": "error",
                "section": "Cooling",
                "message": "Cooling is enabled, but cooling system type is None.",
            }
        )

    if capacity is None or capacity <= 0:
        messages.append(
            {
                "level": "error",
                "section": "Cooling",
                "message": "Cooling is enabled, but cooling capacity is not greater than zero.",
            }
        )

    if cop is None or cop <= 0:
        messages.append(
            {
                "level": "error",
                "section": "Cooling",
                "message": "Cooling is enabled, but COP/EER is not greater than zero.",
            }
        )

    return messages


"""
    text = text.replace(insert_after, validator + insert_after, 1)

if "messages.extend(validate_cooling(project_data))" not in text:
    text = text.replace(
        "    messages.extend(validate_ventilation(project_data))\n",
        "    messages.extend(validate_ventilation(project_data))\n    messages.extend(validate_cooling(project_data))\n",
        1,
    )

validation_path.write_text(text, encoding="utf-8")
print("Patched ui/utils/project_validation.py")


print("Batch U complete.")