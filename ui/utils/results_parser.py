import csv
from pathlib import Path


def format_number(value: str | float | int) -> str:
    """Format numeric strings safely for display."""
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return str(value)


def safe_float(value) -> float | None:
    """Convert value to float where possible."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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

            elif label == "total" and len(row) >= 2:
                # Delivered Energy Summary total row
                metrics["Delivered energy total"] = {
                    "value": row[1],
                    "unit": "kWh/m2",
                }

            elif label == "mech_vent_1" and len(row) >= 2:
                metrics["Mechanical ventilation energy"] = {
                    "value": row[1],
                    "unit": "kWh/m2",
                }

    return metrics


def compare_summary_metrics(
    base_summary_path: Path,
    generated_summary_path: Path,
) -> list[dict]:
    """Compare selected HEM summary metrics between base and generated cases."""

    base_metrics = read_summary_metrics(base_summary_path)
    generated_metrics = read_summary_metrics(generated_summary_path)

    metric_order = [
        "Space heat demand",
        "Space cool demand",
        "Peak electricity consumption",
        "Delivered energy total",
        "Mechanical ventilation energy",
    ]

    comparison = []

    for metric_name in metric_order:
        base_metric = base_metrics.get(metric_name)
        generated_metric = generated_metrics.get(metric_name)

        base_value = safe_float(base_metric["value"]) if base_metric else 0.0
        generated_value = (
            safe_float(generated_metric["value"]) if generated_metric else 0.0
        )

        if base_value is None:
            base_value = 0.0

        if generated_value is None:
            generated_value = 0.0

        difference = generated_value - base_value

        if abs(base_value) > 1e-12:
            percent_change = difference / base_value * 100
        else:
            percent_change = None

        unit = ""
        if generated_metric:
            unit = generated_metric["unit"]
        elif base_metric:
            unit = base_metric["unit"]

        comparison.append(
            {
                "metric": metric_name,
                "base_value": base_value,
                "generated_value": generated_value,
                "difference": difference,
                "percent_change": percent_change,
                "unit": unit,
            }
        )

    return comparison