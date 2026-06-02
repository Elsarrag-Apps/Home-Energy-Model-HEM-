from pathlib import Path

path = Path("ui/utils/results_parser.py")
text = path.read_text(encoding="utf-8")

# Fix peak electricity parser: value is parts[1], not parts[2]
text = text.replace(
    '''            if len(parts) >= 3:
                try:
                    return float(parts[2])
                except ValueError:
                    return 0.0
''',
    '''            if len(parts) >= 2:
                try:
                    return float(parts[1])
                except ValueError:
                    return 0.0
''',
)

# Add delivered energy rows helper if missing
if "def extract_delivered_energy_rows" not in text:
    text += '''


def extract_delivered_energy_rows(summary_csv_path):
    """Return delivered energy end-use rows from HEM summary CSV."""
    rows = []
    lines = read_summary_lines(summary_csv_path)

    in_delivered_section = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("Delivered energy by end-use"):
            in_delivered_section = True
            continue

        if in_delivered_section and (
            stripped.startswith("Hot water system")
            or stripped.startswith("Space heating system")
            or stripped.startswith("Energy Demand Summary")
            or stripped.startswith("Energy Supply Summary")
        ):
            break

        if not in_delivered_section:
            continue

        parts = [part.strip() for part in line.split(",")]

        if len(parts) < 2:
            continue

        row_name = parts[0]

        if row_name == "" or row_name.lower() == "total":
            continue

        try:
            total = float(parts[1])
        except ValueError:
            continue

        rows.append(
            {
                "end_use": row_name,
                "total_kwh_m2": total,
                "mains_elec_kwh_m2": float(parts[3]) if len(parts) > 3 and parts[3] not in ["", "DIV/0"] else 0.0,
            }
        )

    return rows


def extract_hot_water_energy_by_names(summary_csv_path, dhw_end_use_names):
    """Return DHW energy using explicit DHW end-use names."""
    return extract_delivered_energy_end_use(summary_csv_path, dhw_end_use_names)
'''

path.write_text(text, encoding="utf-8")
print("Fixed peak parser and added delivered-energy row helpers.")