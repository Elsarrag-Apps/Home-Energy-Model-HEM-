from pathlib import Path

import pandas as pd


def _find_column(df, candidates):
    """Find a weather column using flexible name matching."""
    cols = list(df.columns)
    lower_map = {str(c).strip().lower(): c for c in cols}

    for candidate in candidates:
        candidate_lower = candidate.lower()
        for col_lower, original in lower_map.items():
            if candidate_lower in col_lower:
                return original

    return None


def _clean_numeric_series(series, default=0.0):
    return pd.to_numeric(series, errors="coerce").fillna(default).astype(float).tolist()


def _repeat_or_trim(values, hours, default=0.0):
    if not values:
        return [default] * hours

    if len(values) >= hours:
        return values[:hours]

    repeated = []
    while len(repeated) < hours:
        repeated.extend(values)

    return repeated[:hours]


def _read_weather_csv_with_detected_header(path: Path) -> pd.DataFrame:
    """Read normal CSV or CIBSE/BRE-style CSV with metadata before the table."""
    # First try normal CSV.
    df = pd.read_csv(path)
    first_cols = [str(c).lower() for c in df.columns]

    if any(
        key in " ".join(first_cols)
        for key in ["temperature", "dry bulb", "drybulb", "temp", "dbt"]
    ):
        return df

    # CIBSE/BRE weather files often have metadata rows before the real table.
    lines = path.read_text(errors="ignore").splitlines()

    header_markers = [
        "dry bulb",
        "dry-bulb",
        "drybulb",
        "temperature",
        "air temp",
        "wind speed",
        "diffuse",
        "direct",
        "global",
    ]

    for i, line in enumerate(lines[:200]):
        lower = line.lower()

        marker_count = sum(marker in lower for marker in header_markers)

        if marker_count >= 2:
            return pd.read_csv(path, skiprows=i)

    # If no labelled header is found, try common CIBSE fixed skip locations.
    for skip in [10, 12, 14, 16, 18, 20, 24, 25, 26, 27, 28, 29, 30]:
        try:
            candidate = pd.read_csv(path, skiprows=skip)
            cols_joined = " ".join(str(c).lower() for c in candidate.columns)

            if any(
                key in cols_joined
                for key in ["temperature", "dry bulb", "drybulb", "temp", "wind", "diffuse"]
            ):
                return candidate
        except Exception:
            continue

    # Last resort: read as no-header numeric table and assign broad CIBSE-like columns.
    raw = pd.read_csv(path, header=None, comment="#")
    raw = raw.dropna(axis=0, how="all").dropna(axis=1, how="all")

    # Keep rows that appear mostly numeric.
    numeric = raw.apply(pd.to_numeric, errors="coerce")
    numeric_count = numeric.notna().sum(axis=1)
    numeric = numeric.loc[numeric_count >= 4].copy()

    if numeric.empty:
        raise ValueError(
            "Could not identify the weather data table in the CSV file. "
            "Please upload an EPW file or a CSV with clear weather headers."
        )

    numeric = numeric.reset_index(drop=True)

    # Use generic names; later logic will use positional fallback.
    numeric.columns = [f"col_{i}" for i in range(len(numeric.columns))]
    return numeric


def read_csv_weather(weather_file_path: str, hours: int) -> dict:
    path = Path(weather_file_path)

    if not path.exists():
        raise FileNotFoundError(f"Weather file not found: {weather_file_path}")

    df = _read_weather_csv_with_detected_header(path)

    # Drop fully empty columns and rows.
    df = df.dropna(axis=1, how="all").dropna(axis=0, how="all")

    temp_col = _find_column(
        df,
        [
            "dry bulb",
            "drybulb",
            "air temperature",
            "air_temperature",
            "temperature",
            "temp",
        ],
    )

    wind_col = _find_column(
        df,
        [
            "wind speed",
            "windspeed",
            "wind_speed",
            "wind",
        ],
    )

    diffuse_col = _find_column(
        df,
        [
            "diffuse horizontal",
            "diffuse_horizontal",
            "dhi",
            "diffuse",
        ],
    )

    direct_col = _find_column(
        df,
        [
            "direct beam",
            "direct normal",
            "direct_beam",
            "dni",
            "beam",
        ],
    )

    # Positional fallback for CIBSE/BRE numeric tables with no usable headers.
    if temp_col is None and all(str(c).startswith("col_") for c in df.columns):
        # In many weather tables, dry-bulb temperature is among the early numeric columns.
        # Use the first column with realistic external temperature range and variability.
        best_col = None

        for col in df.columns:
            series = pd.to_numeric(df[col], errors="coerce")
            valid = series.dropna()

            if len(valid) < 8:
                continue

            if valid.between(-30, 50).mean() > 0.95 and valid.nunique() > 3:
                best_col = col
                break

        temp_col = best_col

    if temp_col is None:
        raise ValueError(
            "Could not identify an air temperature column in the CSV weather file. "
            "For CIBSE CSV, the app could not detect the table header or a realistic "
            "temperature column. Upload an EPW file or paste the first 80 lines so the "
            "column mapping can be added."
        )

    air_temperatures = _clean_numeric_series(df[temp_col], default=10.0)
    wind_speeds = (
        _clean_numeric_series(df[wind_col], default=3.0)
        if wind_col is not None
        else [3.0] * len(air_temperatures)
    )
    diffuse = (
        _clean_numeric_series(df[diffuse_col], default=0.0)
        if diffuse_col is not None
        else [0.0] * len(air_temperatures)
    )
    direct = (
        _clean_numeric_series(df[direct_col], default=0.0)
        if direct_col is not None
        else [0.0] * len(air_temperatures)
    )

    # If this was a no-header numeric fallback, try rough positional radiation/wind fallbacks.
    if all(str(c).startswith("col_") for c in df.columns):
        numeric_cols = list(df.columns)

        # Keep default wind if no reliable column was detected.
        # Try to find radiation columns by values mostly between 0 and 1200.
        radiation_candidates = []

        for col in numeric_cols:
            series = pd.to_numeric(df[col], errors="coerce").dropna()

            if len(series) < 8:
                continue

            if series.between(0, 1400).mean() > 0.95 and series.max() > 50:
                radiation_candidates.append(col)

        if len(radiation_candidates) >= 1 and diffuse_col is None:
            diffuse = _clean_numeric_series(df[radiation_candidates[0]], default=0.0)

        if len(radiation_candidates) >= 2 and direct_col is None:
            direct = _clean_numeric_series(df[radiation_candidates[1]], default=0.0)

    return {
        "air_temperatures": _repeat_or_trim(air_temperatures, hours, 10.0),
        "wind_speeds": _repeat_or_trim(wind_speeds, hours, 3.0),
        "diffuse_horizontal_radiation": _repeat_or_trim(diffuse, hours, 0.0),
        "direct_beam_radiation": _repeat_or_trim(direct, hours, 0.0),
        "weather_rows_available": len(air_temperatures),
    }


def read_epw_weather(weather_file_path: str, hours: int) -> dict:
    path = Path(weather_file_path)

    if not path.exists():
        raise FileNotFoundError(f"Weather file not found: {weather_file_path}")

    # EPW has 8 header rows. Standard columns:
    # 6 dry bulb, 14 direct normal radiation, 15 diffuse horizontal radiation, 21 wind speed
    df = pd.read_csv(path, skiprows=8, header=None)

    air_temperatures = _clean_numeric_series(df.iloc[:, 6], default=10.0)
    direct = _clean_numeric_series(df.iloc[:, 14], default=0.0)
    diffuse = _clean_numeric_series(df.iloc[:, 15], default=0.0)
    wind_speeds = _clean_numeric_series(df.iloc[:, 21], default=3.0)

    return {
        "air_temperatures": _repeat_or_trim(air_temperatures, hours, 10.0),
        "wind_speeds": _repeat_or_trim(wind_speeds, hours, 3.0),
        "diffuse_horizontal_radiation": _repeat_or_trim(diffuse, hours, 0.0),
        "direct_beam_radiation": _repeat_or_trim(direct, hours, 0.0),
        "weather_rows_available": len(air_temperatures),
    }


def apply_weather_simulation_to_case(hem_input: dict, weather_simulation: dict) -> dict:
    """Apply Weather & Simulation page settings to generated HEM input."""
    if not isinstance(weather_simulation, dict) or not weather_simulation:
        return hem_input

    run_type = weather_simulation.get("run_type", "24-hour test")

    if run_type == "Annual run":
        hours = 8760
    elif run_type == "168-hour test":
        hours = 168
    elif run_type == "24-hour test":
        hours = 24
    else:
        hours = int(weather_simulation.get("simulation_hours", 24) or 24)

    start_day = int(weather_simulation.get("start_day", 1) or 1)
    start_hour = max(0, (start_day - 1) * 24)
    end_hour = start_hour + hours

    weather_file = weather_simulation.get("weather_file", "")
    weather_file_type = str(weather_simulation.get("weather_file_type", "csv")).lower()

    if weather_file:
        if weather_file_type == "epw":
            weather = read_epw_weather(weather_file, end_hour)
        else:
            weather = read_csv_weather(weather_file, end_hour)

        air_temperatures = weather["air_temperatures"][start_hour:end_hour]
        wind_speeds = weather["wind_speeds"][start_hour:end_hour]
        diffuse = weather["diffuse_horizontal_radiation"][start_hour:end_hour]
        direct = weather["direct_beam_radiation"][start_hour:end_hour]
        rows_available = weather["weather_rows_available"]
    else:
        existing_external = hem_input.get("ExternalConditions", {})
        air_temperatures = _repeat_or_trim(existing_external.get("air_temperatures", []), hours, 10.0)
        wind_speeds = _repeat_or_trim(existing_external.get("wind_speeds", []), hours, 3.0)
        diffuse = _repeat_or_trim(existing_external.get("diffuse_horizontal_radiation", []), hours, 0.0)
        direct = _repeat_or_trim(existing_external.get("direct_beam_radiation", []), hours, 0.0)
        rows_available = len(existing_external.get("air_temperatures", []))

    hem_input["SimulationTime"] = {
        "start": 0,
        "end": hours,
        "step": 1,
    }

    external = hem_input.get("ExternalConditions", {})
    if not isinstance(external, dict):
        external = {}

    external["air_temperatures"] = air_temperatures
    external["wind_speeds"] = wind_speeds
    external["diffuse_horizontal_radiation"] = diffuse
    external["direct_beam_radiation"] = direct
    external["solar_reflectivity_of_ground"] = [0.2] * hours

    external.setdefault("latitude", 51.42)
    external.setdefault("longitude", -0.75)
    external.setdefault("direct_beam_conversion_needed", False)

    hem_input["ExternalConditions"] = external

    return hem_input
