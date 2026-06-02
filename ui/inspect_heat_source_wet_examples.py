import json
import pathlib
import pprint
from collections import defaultdict

types = defaultdict(list)

for p in pathlib.Path("test").rglob("*.json"):
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        continue

    heat_sources = data.get("HeatSourceWet", {})

    if isinstance(heat_sources, dict):
        for name, source in heat_sources.items():
            if isinstance(source, dict):
                source_type = source.get("type", "UNKNOWN")
                types[source_type].append((p, name, source))

print("HeatSourceWet types found:")
for source_type, examples in sorted(types.items()):
    print(f"- {source_type}: {len(examples)} examples")

print()
print("Example for each HeatSourceWet type:")
for source_type, examples in sorted(types.items()):
    p, name, source = examples[0]
    print()
    print("TYPE:", source_type)
    print("FILE:", p)
    print("NAME:", name)
    pprint.pp(source)