from pathlib import Path
import json
import re
from collections import defaultdict


PROJECT_ROOT = Path(".")
SRC_DIR = PROJECT_ROOT / "src"
TEST_DIR = PROJECT_ROOT / "test"
TEMP_DIR = PROJECT_ROOT / "ui" / "temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

SECTION_NAMES = [
    "SimulationTime",
    "ExternalConditions",
    "EnergySupply",
    "Control",
    "InternalGains",
    "ApplianceGains",
    "ColdWaterSource",
    "HotWaterSource",
    "HotWaterDemand",
    "Events",
    "SpaceHeatSystem",
    "SpaceCoolSystem",
    "InfiltrationVentilation",
    "Zone",
    "BuildingElement",
    "ThermalBridging",
]

KEY_TYPE_NAMES = [
    "InstantElecHeater",
    "Boiler",
    "HeatPump",
    "StorageHeater",
    "District",
    "Cooling",
    "SpaceCool",
    "StorageTank",
    "ImmersionHeater",
    "MixerShower",
    "InstantElecShower",
    "BuildingElementOpaque",
    "BuildingElementTransparent",
    "BuildingElementGround",
    "BuildingElementPartyWall",
    "MechanicalVentilation",
    "ThermalBridgingLinear",
    "ThermalBridgingPoint",
]


def read_text_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="latin-1")
        except Exception:
            return ""
    except Exception:
        return ""


def iter_files(root: Path, suffixes: tuple[str, ...]):
    if not root.exists():
        return

    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in suffixes:
            yield path


def find_python_classes() -> list[dict]:
    rows = []

    for path in iter_files(SRC_DIR, (".py",)):
        text = read_text_safe(path)
        lines = text.splitlines()

        for idx, line in enumerate(lines, start=1):
            match = re.match(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\s*[\(:]", line)
            if match:
                class_name = match.group(1)

                if any(token.lower() in class_name.lower() for token in [
                    "input",
                    "system",
                    "source",
                    "demand",
                    "control",
                    "heater",
                    "boiler",
                    "pump",
                    "cool",
                    "vent",
                    "element",
                    "thermal",
                    "gain",
                    "event",
                    "zone",
                ]):
                    rows.append(
                        {
                            "file": str(path),
                            "line": idx,
                            "class": class_name,
                            "text": line.strip(),
                        }
                    )

    return rows


def find_section_references() -> dict:
    refs = defaultdict(list)

    for path in iter_files(SRC_DIR, (".py",)):
        text = read_text_safe(path)
        lines = text.splitlines()

        for idx, line in enumerate(lines, start=1):
            for section in SECTION_NAMES:
                if section in line:
                    refs[section].append(
                        {
                            "file": str(path),
                            "line": idx,
                            "text": line.strip(),
                        }
                    )

    return dict(refs)


def find_type_references() -> dict:
    refs = defaultdict(list)

    for path in iter_files(SRC_DIR, (".py",)):
        text = read_text_safe(path)
        lines = text.splitlines()

        for idx, line in enumerate(lines, start=1):
            for type_name in KEY_TYPE_NAMES:
                if type_name.lower() in line.lower():
                    refs[type_name].append(
                        {
                            "file": str(path),
                            "line": idx,
                            "text": line.strip(),
                        }
                    )

    return dict(refs)


def find_test_json_examples() -> dict:
    examples = defaultdict(list)

    for path in iter_files(TEST_DIR, (".json",)):
        text = read_text_safe(path)

        if not text.strip():
            continue

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue

        for section in SECTION_NAMES:
            if section in data:
                examples[section].append(
                    {
                        "file": str(path),
                        "top_level_type": type(data.get(section)).__name__,
                        "top_level_keys": list(data.get(section).keys())
                        if isinstance(data.get(section), dict)
                        else [],
                    }
                )

    return dict(examples)


def find_cooling_examples() -> list[dict]:
    rows = []

    search_terms = [
        "SpaceCoolSystem",
        "cooling",
        "Cooling",
        "cool",
        "SpaceCool",
    ]

    for root in [SRC_DIR, TEST_DIR]:
        for path in iter_files(root, (".py", ".json")):
            text = read_text_safe(path)
            lines = text.splitlines()

            for idx, line in enumerate(lines, start=1):
                if any(term in line for term in search_terms):
                    rows.append(
                        {
                            "file": str(path),
                            "line": idx,
                            "text": line.strip(),
                        }
                    )

    return rows


def count_by_file(rows: list[dict]) -> dict:
    counts = defaultdict(int)

    for row in rows:
        counts[row["file"]] += 1

    return dict(sorted(counts.items(), key=lambda item: item[0]))


def build_inventory() -> dict:
    classes = find_python_classes()
    section_refs = find_section_references()
    type_refs = find_type_references()
    test_examples = find_test_json_examples()
    cooling_examples = find_cooling_examples()

    inventory = {
        "sections": {},
        "python_classes": classes,
        "type_references": type_refs,
        "cooling_search": cooling_examples,
    }

    for section in SECTION_NAMES:
        inventory["sections"][section] = {
            "source_reference_count": len(section_refs.get(section, [])),
            "source_references_sample": section_refs.get(section, [])[:20],
            "test_json_example_count": len(test_examples.get(section, [])),
            "test_json_examples": test_examples.get(section, [])[:20],
        }

    return inventory


def make_markdown_report(inventory: dict) -> str:
    lines = []

    lines.append("# HEM Schema Inventory and App Coverage Report")
    lines.append("")
    lines.append("This report is generated from local HEM source files and test JSON files.")
    lines.append("It is intended to guide proper user-interface design for each HEM section.")
    lines.append("")

    lines.append("## 1. Top-level HEM sections")
    lines.append("")

    lines.append("| Section | Source references | Test JSON examples | Current app status |")
    lines.append("|---|---:|---:|---|")

    current_status = {
        "SimulationTime": "Partly covered via Weather & Simulation",
        "ExternalConditions": "Partly covered via Weather & Simulation",
        "EnergySupply": "Preserved through Energy Supply / PV / Battery page",
        "Control": "Preserved through Internal Gains & Controls page",
        "InternalGains": "Preserved through Internal Gains & Controls page",
        "ApplianceGains": "Preserved through Internal Gains & Controls page",
        "ColdWaterSource": "Preserved through Hot Water page",
        "HotWaterSource": "Preserved through Hot Water page",
        "HotWaterDemand": "Preserved through Hot Water page",
        "Events": "Preserved through Internal Gains & Controls page",
        "SpaceHeatSystem": "Preserved through Heating & Cooling page",
        "SpaceCoolSystem": "Not yet confirmed / placeholder only",
        "InfiltrationVentilation": "Mapped through form inputs",
        "Zone": "Partly covered through fabric and area/volume",
        "BuildingElement": "Mapped through editable fabric table",
        "ThermalBridging": "Mapped as total HLC float",
    }

    for section, data in inventory["sections"].items():
        lines.append(
            f"| {section} | {data['source_reference_count']} | "
            f"{data['test_json_example_count']} | {current_status.get(section, 'Not assessed')} |"
        )

    lines.append("")
    lines.append("## 2. Sections with test JSON examples")
    lines.append("")

    for section, data in inventory["sections"].items():
        examples = data["test_json_examples"]
        if not examples:
            continue

        lines.append(f"### {section}")
        lines.append("")

        for example in examples[:10]:
            keys = ", ".join(example.get("top_level_keys", [])[:20])
            lines.append(f"- `{example['file']}`")
            lines.append(f"  - Type: `{example['top_level_type']}`")
            if keys:
                lines.append(f"  - Keys: `{keys}`")
        lines.append("")

    lines.append("## 3. Python classes likely relevant to the schema")
    lines.append("")

    for row in inventory["python_classes"][:200]:
        lines.append(f"- `{row['class']}` in `{row['file']}` line {row['line']}")
    lines.append("")

    lines.append("## 4. Key type references")
    lines.append("")

    for type_name, refs in inventory["type_references"].items():
        lines.append(f"### {type_name}")
        lines.append("")
        for ref in refs[:10]:
            lines.append(f"- `{ref['file']}` line {ref['line']}: `{ref['text']}`")
        lines.append("")

    lines.append("## 5. Cooling schema search")
    lines.append("")

    cooling_rows = inventory["cooling_search"]

    if not cooling_rows:
        lines.append("No cooling-related references were found in source or test JSON.")
    else:
        lines.append(f"Found {len(cooling_rows)} cooling-related references.")
        lines.append("")
        for row in cooling_rows[:100]:
            lines.append(f"- `{row['file']}` line {row['line']}: `{row['text']}`")

    lines.append("")
    lines.append("## 6. Recommended next steps")
    lines.append("")
    lines.append("1. Confirm valid HEM schema for heating system types from source classes and test examples.")
    lines.append("2. Confirm whether active cooling is supported through `SpaceCoolSystem` or another mechanism.")
    lines.append("3. Replace JSON-first pages with schema-aware forms while keeping advanced JSON preview.")
    lines.append("4. Add validation and insight graphics for capacity, efficiency, schedules and end-use energy.")
    lines.append("5. Build a results dashboard from HEM core results CSV.")

    return "\n".join(lines)


def main():
    inventory = build_inventory()

    json_path = TEMP_DIR / "hem_schema_inventory.json"
    md_path = TEMP_DIR / "hem_schema_inventory.md"

    json_path.write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    md_path.write_text(make_markdown_report(inventory), encoding="utf-8")

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")

    print("")
    print("Top-level section coverage:")
    for section, data in inventory["sections"].items():
        print(
            f"- {section}: "
            f"{data['source_reference_count']} source refs, "
            f"{data['test_json_example_count']} test examples"
        )

    print("")
    print("Cooling references found:", len(inventory["cooling_search"]))


if __name__ == "__main__":
    main()