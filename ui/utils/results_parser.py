import csv
from pathlib import Path


def format_number(value: str) -> str:
    """Format numeric strings safely for display."""
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return value


def read_summary_metrics(summary_csv_path: Path) -> dict:
    """Extract selected headline metrics from the HEM summary CSV."""
    metrics = {}

    if not summary_csv_path.exists():
        return metrics

    with open(summary_csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)

        for row in reader:
            if not row:
                continue

            label = row[0].strip() if len(row) > 0 else ""

            if label == "Space heat demand" and len(row) >= 3:
                metrics["Space heat demand"] = {
                    "value": row[2],
                    "unit": row[1],
                }

            elif label == "Space cool demand" and len(row) >= 3:
                metrics["Space cool demand"] = {
                    "value": row[2],
                    "unit": row[1],
                }

            elif label == "Peak consumption (electricity)" and len(row) >= 2:
                metrics["Peak electricity consumption"] = {
                    "value": row[1],
                    "unit": "kWh",
                }

    return metrics