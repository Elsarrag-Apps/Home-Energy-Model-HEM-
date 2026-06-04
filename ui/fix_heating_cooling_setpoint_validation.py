from pathlib import Path

path = Path("ui/utils/project_validation.py")
text = path.read_text(encoding="utf-8")

if "def validate_heating_cooling_setpoints" not in text:
    insert_before = "def validate_cooling(project_data: dict) -> list[dict]:"

    block = '''
def validate_heating_cooling_setpoints(project_data: dict) -> list[dict]:
    messages = []

    heating = project_data.get("heating_form", {}) or {}
    cooling = project_data.get("cooling_systems", {}) or {}

    if not cooling.get("cooling_enabled", False):
        return messages

    heating_setpoint = safe_float(heating.get("heating_setpoint_c"), 21.0)
    cooling_setpoint = safe_float(cooling.get("cooling_setpoint_c"), 26.0)

    if heating_setpoint is None or cooling_setpoint is None:
        return messages

    if cooling_setpoint <= heating_setpoint:
        messages.append(
            {
                "level": "error",
                "section": "Heating / cooling controls",
                "message": (
                    f"Cooling setpoint ({cooling_setpoint} degC) must be higher than "
                    f"heating setpoint ({heating_setpoint} degC). Increase the cooling "
                    "setpoint or reduce the heating setpoint before running HEM."
                ),
            }
        )

    return messages


'''

    text = text.replace(insert_before, block + insert_before, 1)

if "messages.extend(validate_heating_cooling_setpoints(project_data))" not in text:
    text = text.replace(
        "    messages.extend(validate_heating_form(project_data))\n",
        "    messages.extend(validate_heating_form(project_data))\n    messages.extend(validate_heating_cooling_setpoints(project_data))\n",
        1,
    )

path.write_text(text, encoding="utf-8")
print("Added heating/cooling setpoint validation.")