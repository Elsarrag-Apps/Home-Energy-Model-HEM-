import json
from pathlib import Path


def load_json_file(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_energy_supply_from_hem(hem_json_path: Path) -> dict:
    hem_input = load_json_file(hem_json_path)
    return hem_input.get("EnergySupply", {})


def summarise_energy_supply(energy_supply: dict) -> list[dict]:
    rows = []

    for name, supply in (energy_supply or {}).items():
        if isinstance(supply, dict):
            rows.append(
                {
                    "name": name,
                    "type": supply.get("type", "Unknown"),
                    "fuel": supply.get("fuel", supply.get("Fuel", "")),
                    "has_diverter": "diverter" in supply or "Diverter" in supply,
                    "has_battery": "battery" in supply or "Battery" in supply,
                    "has_generation": "generation" in supply or "Generation" in supply,
                }
            )
        else:
            rows.append(
                {
                    "name": name,
                    "type": type(supply).__name__,
                    "fuel": "",
                    "has_diverter": False,
                    "has_battery": False,
                    "has_generation": False,
                }
            )

    return rows
