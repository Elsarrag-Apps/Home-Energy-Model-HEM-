from pathlib import Path

path = Path("ui/utils/full_case_builder.py")
text = path.read_text(encoding="utf-8")

old = '''    hem_input = apply_form_hot_water_to_hem_input(
        hem_input=hem_input,
        hot_water_data=hot_water_form,
    )

    hem_input = apply_energy_supply_to_case(
'''

new = '''    hem_input = apply_form_hot_water_to_hem_input(
        hem_input=hem_input,
        hot_water_data=hot_water_form,
    )

    # Re-apply form heating after hot water and controls so the generated
    # SpaceHeatSystem control reference is guaranteed to exist.
    hem_input = apply_form_heating_to_hem_input(
        hem_input=hem_input,
        heating_data=heating_form,
        zone_name="zone 1",
    )

    hem_input = apply_energy_supply_to_case(
'''

if old not in text:
    raise RuntimeError("Could not find hot-water-to-energy-supply block in full_case_builder.py")

text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print("Re-applied generated heating after hot water/control sections.")