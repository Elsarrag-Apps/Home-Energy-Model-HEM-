from pathlib import Path


def safe_float(value, default=None):
    try:
        if value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def validate_ventilation(project_data: dict) -> list[dict]:
    """Validate saved ventilation inputs before HEM is built/run."""
    messages = []

    ventilation = project_data.get("ventilation", {}) or {}
    mechanical = ventilation.get("mechanical_ventilation", {}) or {}

    if not mechanical:
        return messages

    vent_type = str(mechanical.get("vent_type", "None")).strip()
    design_flow_l_s = safe_float(mechanical.get("design_flow_l_s"), 0.0)

    if vent_type.lower() != "none" and (design_flow_l_s is None or design_flow_l_s <= 0):
        messages.append(
            {
                "level": "error",
                "section": "Ventilation",
                "message": (
                    "Mechanical ventilation is selected, but the design outdoor "
                    "air-flow rate is 0 l/s. Set a value greater than 0, or change "
                    "mechanical ventilation type to None."
                ),
            }
        )

    if vent_type.lower() == "none" and design_flow_l_s and design_flow_l_s > 0:
        messages.append(
            {
                "level": "warning",
                "section": "Ventilation",
                "message": (
                    "Mechanical ventilation type is None, so the entered fan flow "
                    "will be ignored."
                ),
            }
        )

    return messages


def validate_weather(project_data: dict, default_weather_file: Path) -> list[dict]:
    """Validate weather file path."""
    messages = []

    weather_settings = project_data.get("weather_simulation", {}) or {}
    weather_file = Path(
        weather_settings.get("weather_file", str(default_weather_file))
    )

    if not weather_file.exists():
        messages.append(
            {
                "level": "warning",
                "section": "Weather",
                "message": (
                    f"Saved weather file was not found: {weather_file}. "
                    f"The app will use the default weather file: {default_weather_file}."
                ),
            }
        )

    return messages


def validate_fabric(project_data: dict) -> list[dict]:
    """Validate fabric rows."""
    messages = []

    fabric_rows = project_data.get("fabric_elements", []) or []

    if not fabric_rows:
        messages.append(
            {
                "level": "warning",
                "section": "Fabric",
                "message": (
                    "No edited fabric rows are saved. The generated case will keep "
                    "the fabric from the uploaded HEM JSON."
                ),
            }
        )

    return messages


def validate_json_sections(project_data: dict) -> list[dict]:
    """Validate preserved JSON sections are dictionaries."""
    messages = []

    section_checks = {
        "space_heat_systems": "Heating systems",
        "hot_water": "Hot water",
        "gains_controls": "Internal gains, controls and events",
        "energy_supply": "Energy supply",
    }

    for key, label in section_checks.items():
        section = project_data.get(key)

        if section is not None and section != {} and not isinstance(section, dict):
            messages.append(
                {
                    "level": "error",
                    "section": label,
                    "message": f"{label} data must be a JSON object/dictionary.",
                }
            )

    return messages


def validate_project_before_run(
    project_data: dict,
    default_weather_file: Path,
) -> list[dict]:
    """Run all pre-run validation checks."""
    messages = []

    project_data = project_data or {}

    messages.extend(validate_fabric(project_data))
    messages.extend(validate_ventilation(project_data))
    messages.extend(validate_weather(project_data, default_weather_file))
    messages.extend(validate_json_sections(project_data))

    return messages


def has_blocking_errors(messages: list[dict]) -> bool:
    return any(message.get("level") == "error" for message in messages)


def split_messages(messages: list[dict]) -> tuple[list[dict], list[dict]]:
    errors = [m for m in messages if m.get("level") == "error"]
    warnings = [m for m in messages if m.get("level") == "warning"]
    return errors, warnings
