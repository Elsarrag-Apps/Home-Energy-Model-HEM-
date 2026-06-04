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

            if len(parts) >= 2:
                try:
                    return float(parts[1])
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



def read_core_results_dataframe(results_csv_path):
    """Read HEM detailed core results CSV and remove the units row."""
    import pandas as pd

    path = Path(results_csv_path)

    if not path.exists():
        return pd.DataFrame()

    df = pd.read_csv(path)

    if df.empty:
        return df

    # HEM result CSV usually has a first row containing units such as [kWh].
    if str(df.iloc[0].get("Timestep", "")).startswith("["):
        df = df.iloc[1:].copy()

    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="ignore")

    if "Timestep" in df.columns:
        df["Timestep"] = pd.to_numeric(df["Timestep"], errors="coerce")

    return df.reset_index(drop=True)


def get_delivered_energy_chart_rows(summary_csv_path):
    """Return delivered energy end-use rows suitable for charting."""
    rows = extract_delivered_energy_rows(summary_csv_path)

    clean_rows = []

    for row in rows:
        end_use = row.get("end_use", "")
        value = row.get("total_kwh_m2", 0.0)

        if end_use and value is not None:
            clean_rows.append(
                {
                    "End use": end_use,
                    "Delivered energy (kWh/m2)": value,
                }
            )

    return clean_rows


def find_columns_containing(df, patterns):
    """Return columns containing any supplied case-insensitive patterns."""
    if df is None or df.empty:
        return []

    if isinstance(patterns, str):
        patterns = [patterns]

    patterns = [p.lower() for p in patterns]

    cols = []

    for col in df.columns:
        col_lower = str(col).lower()

        if any(pattern in col_lower for pattern in patterns):
            cols.append(col)

    return cols



def format_small_number(value, decimals=6):
    """Format small energy values without hiding them as 0.000."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "0.000000"

    if abs(value) < 0.001 and value != 0:
        return f"{value:.{decimals}f}"

    return f"{value:.3f}"


def get_simulation_summary_from_case(case_json_path):
    """Return simulation period summary from generated HEM input."""
    import json

    path = Path(case_json_path)

    if not path.exists():
        return {
            "start": None,
            "end": None,
            "step": None,
            "timesteps": 0,
            "is_annual": False,
            "message": "Generated HEM input not found.",
        }

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "start": None,
            "end": None,
            "step": None,
            "timesteps": 0,
            "is_annual": False,
            "message": "Could not read generated HEM input.",
        }

    sim = data.get("SimulationTime", {}) or {}
    external = data.get("ExternalConditions", {}) or {}

    start = sim.get("start")
    end = sim.get("end")
    step = sim.get("step", 1)

    try:
        timesteps = int((float(end) - float(start)) / float(step))
    except Exception:
        timesteps = 0

    weather_lengths = {}

    for key in [
        "air_temperatures",
        "wind_speeds",
        "diffuse_horizontal_radiation",
        "direct_beam_radiation",
    ]:
        value = external.get(key)

        if isinstance(value, list):
            weather_lengths[key] = len(value)

    is_annual = timesteps >= 8760

    if is_annual:
        message = "Annual or near-annual simulation period."
    else:
        message = (
            f"Short test-period simulation: {timesteps} timestep(s). "
            "This is not an annual result."
        )

    return {
        "start": start,
        "end": end,
        "step": step,
        "timesteps": timesteps,
        "is_annual": is_annual,
        "weather_lengths": weather_lengths,
        "message": message,
    }
