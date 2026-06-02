import json
import pathlib
import pprint

types = {}

for p in pathlib.Path("test").rglob("*.json"):
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        continue

    systems = data.get("SpaceHeatSystem", {})
    if isinstance(systems, dict):
        for name, system in systems.items():
            if isinstance(system, dict):
                system_type = system.get("type", "UNKNOWN")
                types.setdefault(system_type, []).append((p, name, system))

print("SpaceHeatSystem types found:")
for system_type, examples in sorted(types.items()):
    print(f"- {system_type}: {len(examples)} examples")

print()
print("Example for each type:")
for system_type, examples in sorted(types.items()):
    p, name, system = examples[0]
    print()
    print("TYPE:", system_type)
    print("FILE:", p)
    print("NAME:", name)
    pprint.pp(system)