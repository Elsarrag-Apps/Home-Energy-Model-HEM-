from pathlib import Path

path = Path("ui/utils/results_parser.py")

path.write_text(
    '''
from pathlib import Path


def format_number(value, decimals=3):
    """Format numbers for Streamlit metric cards."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "0.000"

    return f"{value:.{decimals}f}"


def read_summary_lines(summary_csv_path):
    path = Path(summary_csv_path)

    if not path.exists():
        return []

    return path.read_text(encoding="utf-8").splitlines()


def extract_energy_demand_value(summary_csv_path, row_name):
    """Extract a value from the Energy Demand Summary section."""
    lines = read_summary_lines(summary_csv_path)
    target = row_name.strip().lower()

    in_section = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("Energy Demand Summary"):
            in_section = True
            continue

        if in_section and stripped.startswith("Energy Supply Summary"):
            break

        if not in_section:
            continue

        parts = [part.strip() for part in line.split(",")]

        if len(parts) < 3:
            continue

        if parts[0].strip().lower() == target:
            try:
                return float(parts[2])
            except ValueError:
                return 0.0

    return 0.0


def extract_peak_electricity(summary_csv_path):
    """Extract peak electricity consumption from the Energy Supply Summary section."""
    lines = read_summary_lines(summary_csv_path)

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("Peak consumption (electricity)"):
            parts = [part.strip() for part in line.split(",")]

            if len(parts) >= 3:
                try:
                    return float(parts[2])
                except ValueError:
                    return 0.0

    return 0.0


def extract_delivered_energy_total(summary_csv_path):
    """Extract total delivered energy from Delivered Energy Summary."""
    lines = read_summary_lines(summary_csv_path)

    in_section = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("Delivered energy by end-use"):
            in_section = True
            continue

        if in_section and (
            stripped.startswith("Hot water system")
            or stripped.startswith("Space heating system")
        ):
            break

        if not in_section:
            continue

        parts = [part.strip() for part in line.split(",")]

        if len(parts) < 2:
            continue

        if parts[0].strip().lower() == "total":
            try:
                return float(parts[1])
            except ValueError:
                return 0.0

    return 0.0


def extract_delivered_energy_end_use(summary_csv_path, end_use_names):
    """Extract delivered energy by end-use from HEM summary CSV."""
    if isinstance(end_use_names, str):
        end_use_names = [end_use_names]

    wanted = {str(name).strip().lower() for name in end_use_names}
    total = 0.0

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

        row_name = parts[0].strip().lower()

        if row_name in wanted:
            try:
                total += float(parts[1])
            except ValueError:
                pass

    return total


def extract_hot_water_energy(summary_csv_path):
    """Return approximate DHW-related delivered energy in kWh/m2."""
    return extract_delivered_energy_end_use(
        summary_csv_path,
        [
            "immersion",
            "IES",
            "instant electric shower",
            "hot_water",
            "hot water",
            "dhw",
        ],
    )


def extract_mechanical_ventilation_energy(summary_csv_path):
    """Extract mechanical ventilation delivered energy in kWh/m2."""
    return extract_delivered_energy_end_use(
        summary_csv_path,
        [
            "mech_vent_1",
            "mechanical ventilation",
            "mech_vent",
        ],
    )


def compare_summary_metrics(base_summary_path, generated_summary_path):
    """Compare key HEM summary metrics between baseline and generated case."""
    metrics = []

    metric_specs = [
        {
            "metric": "Space heat demand",
            "unit": "kWh/m2",
            "base": extract_energy_demand_value(base_summary_path, "Space heat demand"),
            "generated": extract_energy_demand_value(generated_summary_path, "Space heat demand"),
        },
        {
            "metric": "Space cool demand",
            "unit": "kWh/m2",
            "base": extract_energy_demand_value(base_summary_path, "Space cool demand"),
            "generated": extract_energy_demand_value(generated_summary_path, "Space cool demand"),
        },
        {
            "metric": "Peak electricity consumption",
            "unit": "kWh",
            "base": extract_peak_electricity(base_summary_path),
            "generated": extract_peak_electricity(generated_summary_path),
        },
        {
            "metric": "Delivered energy total",
            "unit": "kWh/m2",
            "base": extract_delivered_energy_total(base_summary_path),
            "generated": extract_delivered_energy_total(generated_summary_path),
        },
        {
            "metric": "Mechanical ventilation energy",
            "unit": "kWh/m2",
            "base": extract_mechanical_ventilation_energy(base_summary_path),
            "generated": extract_mechanical_ventilation_energy(generated_summary_path),
        },
        {
            "metric": "Hot water energy",
            "unit": "kWh/m2",
            "base": extract_hot_water_energy(base_summary_path),
            "generated": extract_hot_water_energy(generated_summary_path),
        },
    ]

    for item in metric_specs:
        metrics.append(
            {
                "metric": item["metric"],
                "unit": item["unit"],
                "base_value": item["base"],
                "generated_value": item["generated"],
                "difference": item["generated"] - item["base"],
            }
        )

    return metrics
'''.strip() + "\n",
    encoding="utf-8",
)

print("Restored ui/utils/results_parser.py")