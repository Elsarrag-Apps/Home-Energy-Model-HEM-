from pathlib import Path

path = Path("ui/utils/input_builder.py")
text = path.read_text(encoding="utf-8")

# Add a final sanitizer if it does not already exist.
if "def clean_building_element_for_hem" not in text:
    text += '''


def clean_building_element_for_hem(element: dict) -> dict:
    """Remove fields that are not valid for specific HEM BuildingElement types."""
    if not isinstance(element, dict):
        return element

    element_type = element.get("type", "")

    if element_type == "BuildingElementTransparent":
        # Transparent elements calculate area from height and width.
        # HEM validator rejects these opaque/summary fields.
        element.pop("area", None)
        element.pop("areal_heat_capacity", None)
        element.pop("mass_distribution_class", None)
        element.pop("solar_absorption_coeff", None)

    return element
'''

# Patch build_hem_building_elements so every generated element is cleaned.
if "clean_building_element_for_hem(hem_element)" not in text:
    text = text.replace(
        "        hem_elements[element_name] = hem_element\n",
        "        hem_elements[element_name] = clean_building_element_for_hem(hem_element)\n",
    )

path.write_text(text, encoding="utf-8")
print("Patched input_builder.py to clean transparent window fields.")