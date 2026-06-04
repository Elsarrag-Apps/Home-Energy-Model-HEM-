from pathlib import Path

path = Path("ui/utils/full_case_builder.py")
text = path.read_text(encoding="utf-8")

if "def clean_transparent_elements_in_case" not in text:
    insert_after = '''def apply_heat_source_wet_to_case(hem_input: dict, heat_source_wet: dict) -> dict:
    """Apply saved HeatSourceWet dictionary to a HEM input."""
    if isinstance(heat_source_wet, dict) and heat_source_wet:
        hem_input["HeatSourceWet"] = deepcopy(heat_source_wet)

    return hem_input
'''

    block = insert_after + '''


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
'''

    if insert_after not in text:
        raise RuntimeError("Could not find HeatSourceWet block in full_case_builder.py")

    text = text.replace(insert_after, block, 1)

if "hem_input = clean_transparent_elements_in_case(hem_input)" not in text:
    text = text.replace(
        '''    save_json(output_json_path, hem_input)
''',
        '''    hem_input = clean_transparent_elements_in_case(hem_input)

    save_json(output_json_path, hem_input)
''',
        1,
    )

path.write_text(text, encoding="utf-8")
print("Added final transparent-element sanitizer before saving generated HEM JSON.")