import json
import pathlib
import pprint
from collections import defaultdict

source_types = defaultdict(list)
nested_heat_source_types = defaultdict(list)

for p in pathlib.Path("test").rglob("*.json"):
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        continue

    hot_sources = data.get("HotWaterSource", {})

    if isinstance(hot_sources, dict):
        for name, source in hot_sources.items():
            if isinstance(source, dict):
                source_type = source.get("type", "UNKNOWN")
                source_types[source_type].append((p, name, source))

                heat_source = source.get("HeatSource", {})
                if isinstance(heat_source, dict):
                    for hs_name, hs in heat_source.items():
                        if isinstance(hs, dict):
                            nested_type = hs.get("type", "UNKNOWN")
                            nested_heat_source_types[nested_type].append(
                                (p, name, hs_name, hs, source)
                            )

print("HotWaterSource types found:")
for source_type, examples in sorted(source_types.items()):
    print(f"- {source_type}: {len(examples)} examples")

print()
print("Nested HotWaterSource HeatSource types found:")
for nested_type, examples in sorted(nested_heat_source_types.items()):
    print(f"- {nested_type}: {len(examples)} examples")

print()
print("Example for each HotWaterSource type:")
for source_type, examples in sorted(source_types.items()):
    p, name, source = examples[0]
    print()
    print("HOT WATER SOURCE TYPE:", source_type)
    print("FILE:", p)
    print("NAME:", name)
    pprint.pp(source)

print()
print("Example for each nested HeatSource type:")
for nested_type, examples in sorted(nested_heat_source_types.items()):
    p, source_name, hs_name, hs, full_source = examples[0]
    print()
    print("NESTED HEAT SOURCE TYPE:", nested_type)
    print("FILE:", p)
    print("HOT WATER SOURCE:", source_name)
    print("HEAT SOURCE NAME:", hs_name)
    pprint.pp(hs)
    print("FULL HOT WATER SOURCE:")
    pprint.pp(full_source)