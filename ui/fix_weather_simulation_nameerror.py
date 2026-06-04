from pathlib import Path

path = Path("ui/utils/full_case_builder.py")
text = path.read_text(encoding="utf-8")

# Add a defensive definition immediately before the weather mapper is called.
needle = '''    hem_input = apply_weather_simulation_to_case(
        hem_input=hem_input,
        weather_simulation=weather_simulation,
    )
'''

replacement = '''    weather_simulation = project_sections.get("weather_simulation", {})

    hem_input = apply_weather_simulation_to_case(
        hem_input=hem_input,
        weather_simulation=weather_simulation,
    )
'''

if needle not in text:
    raise RuntimeError("Could not find apply_weather_simulation_to_case call.")

text = text.replace(needle, replacement, 1)

path.write_text(text, encoding="utf-8")
print("Fixed weather_simulation NameError in full_case_builder.py")