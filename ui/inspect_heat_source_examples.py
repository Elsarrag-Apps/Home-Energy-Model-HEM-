import json
import pathlib
import pprint

heat_source_refs = {}
top_level_keys_seen = set()

for p in pathlib.Path("test").rglob("*.json"):
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        continue

    top_level_keys_seen.update(data.keys())

    # Top-level possible heat-source sections
    for key in data.keys():
        if "Heat" in key or "heat" in key or "Boiler" in key or "Pump" in key:
            heat_source_refs.setdefault(key, []).append((p, data[key]))

    # Nested SpaceHeatSystem HeatSource references
    systems = data.get("SpaceHeatSystem", {})
    if isinstance(systems, dict):
        for sys_name, system in systems.items():
            if isinstance(system, dict) and "HeatSource" in system:
                heat_source_refs.setdefault("Nested SpaceHeatSystem.HeatSource", []).append(
                    (p, sys_name, system["HeatSource"], system)
                )

print("Top-level keys containing Heat/heat/Boiler/Pump:")
for key, examples in sorted(heat_source_refs.items()):
    print(f"- {key}: {len(examples)} examples")

print()
print("All top-level keys seen that may be relevant:")
for key in sorted(top_level_keys_seen):
    if any(term.lower() in key.lower() for term in ["heat", "source", "boiler", "pump", "system"]):
        print("-", key)

print()
print("Example nested HeatSource references:")
examples = heat_source_refs.get("Nested SpaceHeatSystem.HeatSource", [])
for item in examples[:10]:
    p, sys_name, heat_source, full_system = item
    print()
    print("FILE:", p)
    print("SYSTEM:", sys_name)
    print("HeatSource:")
    pprint.pp(heat_source)
    print("Full SpaceHeatSystem item:")
    pprint.pp(full_system)