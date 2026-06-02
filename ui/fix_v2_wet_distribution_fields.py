from pathlib import Path

path = Path("ui/utils/hvac_mapper.py")
text = path.read_text(encoding="utf-8")

text = text.replace(
    '''            "advanced_start": safe_float(heating_data.get("advanced_start"), 2),
''',
    "",
)

text = text.replace(
    '''            "temp_setback": safe_float(heating_data.get("temp_setback"), 18.0),
''',
    "",
)

path.write_text(text, encoding="utf-8")
print("Removed unsupported WetDistribution fields: advanced_start and temp_setback")