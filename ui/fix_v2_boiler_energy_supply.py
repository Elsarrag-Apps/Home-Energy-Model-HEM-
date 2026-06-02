from pathlib import Path

path = Path("ui/utils/hvac_mapper.py")
text = path.read_text(encoding="utf-8")

old = '''def apply_form_heating_to_hem_input(
    hem_input: dict,
    heating_data: dict,
    zone_name: str = "zone 1",
) -> dict:
    space_heat, heat_source_wet, controls = build_heating_from_app(heating_data)

    if not space_heat:
        return hem_input

    hem_input["SpaceHeatSystem"] = space_heat

    if heat_source_wet:
        hem_input["HeatSourceWet"] = heat_source_wet
    elif "HeatSourceWet" in hem_input:
        # Direct electric heating does not need HeatSourceWet.
        del hem_input["HeatSourceWet"]

    if "Control" not in hem_input or not isinstance(hem_input["Control"], dict):
        hem_input["Control"] = {}

    hem_input["Control"].update(controls)

    if "Zone" in hem_input and isinstance(hem_input["Zone"], dict):
        if zone_name not in hem_input["Zone"]:
            zone_name = next(iter(hem_input["Zone"].keys()))

        system_name = next(iter(space_heat.keys()))
        hem_input["Zone"][zone_name]["SpaceHeatSystem"] = system_name

    return hem_input
'''

new = '''def ensure_energy_supply_exists(hem_input: dict, supply_name: str) -> dict:
    """Ensure a referenced EnergySupply exists in the generated HEM input."""
    if not supply_name:
        return hem_input

    if "EnergySupply" not in hem_input or not isinstance(hem_input["EnergySupply"], dict):
        hem_input["EnergySupply"] = {}

    if supply_name in hem_input["EnergySupply"]:
        return hem_input

    supply_lower = str(supply_name).lower()

    if "gas" in supply_lower:
        hem_input["EnergySupply"][supply_name] = {
            "fuel": "mains gas",
            "is_export_capable": False,
        }
    elif "elec" in supply_lower:
        hem_input["EnergySupply"][supply_name] = {
            "fuel": "electricity",
            "is_export_capable": True,
        }
    else:
        hem_input["EnergySupply"][supply_name] = {
            "fuel": supply_name,
            "is_export_capable": False,
        }

    return hem_input


def apply_form_heating_to_hem_input(
    hem_input: dict,
    heating_data: dict,
    zone_name: str = "zone 1",
) -> dict:
    space_heat, heat_source_wet, controls = build_heating_from_app(heating_data)

    if not space_heat:
        return hem_input

    hem_input["SpaceHeatSystem"] = space_heat

    # Ensure all energy supplies referenced by generated heating exist.
    for system in space_heat.values():
        if isinstance(system, dict) and system.get("EnergySupply"):
            hem_input = ensure_energy_supply_exists(
                hem_input,
                system.get("EnergySupply"),
            )

    if heat_source_wet:
        hem_input["HeatSourceWet"] = heat_source_wet

        for source in heat_source_wet.values():
            if not isinstance(source, dict):
                continue

            if source.get("EnergySupply"):
                hem_input = ensure_energy_supply_exists(
                    hem_input,
                    source.get("EnergySupply"),
                )

            if source.get("EnergySupply_aux"):
                hem_input = ensure_energy_supply_exists(
                    hem_input,
                    source.get("EnergySupply_aux"),
                )

    elif "HeatSourceWet" in hem_input:
        # Direct electric heating does not need HeatSourceWet.
        del hem_input["HeatSourceWet"]

    if "Control" not in hem_input or not isinstance(hem_input["Control"], dict):
        hem_input["Control"] = {}

    hem_input["Control"].update(controls)

    if "Zone" in hem_input and isinstance(hem_input["Zone"], dict):
        if zone_name not in hem_input["Zone"]:
            zone_name = next(iter(hem_input["Zone"].keys()))

        system_name = next(iter(space_heat.keys()))
        hem_input["Zone"][zone_name]["SpaceHeatSystem"] = system_name

    return hem_input
'''

if old not in text:
    raise RuntimeError("Could not find apply_form_heating_to_hem_input block in hvac_mapper.py")

text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")

print("Added automatic EnergySupply creation for generated heating systems.")