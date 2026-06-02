from pathlib import Path

path = Path("ui/utils/hvac_mapper.py")
text = path.read_text(encoding="utf-8")

text = text.replace(
    '''        hem_input["EnergySupply"][supply_name] = {
            "fuel": "mains gas",
            "is_export_capable": False,
        }
''',
    '''        hem_input["EnergySupply"][supply_name] = {
            "fuel": "mains_gas",
            "is_export_capable": False,
        }
''',
)

path.write_text(text, encoding="utf-8")
print("Updated generated gas EnergySupply fuel enum to mains_gas.")