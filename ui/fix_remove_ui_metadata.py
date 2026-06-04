from pathlib import Path

# Patch weather_mapper.py so it no longer writes _ui_metadata into HEM JSON
path = Path("ui/utils/weather_mapper.py")
text = path.read_text(encoding="utf-8")

old = '''    hem_input.setdefault("_ui_metadata", {})
    hem_input["_ui_metadata"]["weather_simulation"] = {
        "run_type": run_type,
        "simulation_hours": hours,
        "weather_file": weather_file,
        "weather_file_type": weather_file_type,
        "weather_rows_available": rows_available,
        "is_annual": hours >= 8760,
    }

    return hem_input
'''

new = '''    return hem_input
'''

if old in text:
    text = text.replace(old, new, 1)
else:
    print("Metadata block not found in weather_mapper.py; adding final pop only.")

path.write_text(text, encoding="utf-8")
print("Removed _ui_metadata writer from weather_mapper.py")


# Add final safety removal in full_case_builder.py
path = Path("ui/utils/full_case_builder.py")
text = path.read_text(encoding="utf-8")

if "hem_input.pop(\"_ui_metadata\", None)" not in text:
    text = text.replace(
        '''    hem_input = clean_transparent_elements_in_case(hem_input)
    hem_input = clean_ground_elements_in_case(hem_input)

    save_json(output_json_path, hem_input)
''',
        '''    hem_input = clean_transparent_elements_in_case(hem_input)
    hem_input = clean_ground_elements_in_case(hem_input)

    # Remove app-only metadata before HEM validation.
    hem_input.pop("_ui_metadata", None)

    save_json(output_json_path, hem_input)
''',
        1,
    )

path.write_text(text, encoding="utf-8")
print("Added final _ui_metadata removal before saving generated HEM JSON.")