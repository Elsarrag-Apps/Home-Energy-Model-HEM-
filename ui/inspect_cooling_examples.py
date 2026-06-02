import json
import pathlib
import pprint

files = []

for p in pathlib.Path("test").rglob("*.json"):
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        continue

    if "SpaceCoolSystem" in data:
        files.append(p)

print("SpaceCoolSystem examples found:", len(files))

for p in files[:10]:
    print()
    print("FILE:", p)
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    pprint.pp(data["SpaceCoolSystem"])