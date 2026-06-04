from pathlib import Path

path = Path("ui/utils/weather_mapper.py")
text = path.read_text(encoding="utf-8")

old = '''def read_csv_weather(weather_file_path: str, hours: int) -> dict:
    path = Path(weather_file_path)

    if not path.exists():
        raise FileNotFoundError(f"Weather file not found: {weather_file_path}")

    df = pd.read_csv(path)

    # Drop fully empty columns and rows.
    df = df.dropna(axis=1, how="all").dropna(axis=0, how="all")

    temp_col = _find_column(
'''

new = '''def _read_weather_csv_with_detected_header(path: Path) -> pd.DataFrame:
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
'''

if old not in text:
    raise RuntimeError("Could not find read_csv_weather start block in weather_mapper.py")

text = text.replace(old, new, 1)

old2 = '''    if temp_col is None:
        raise ValueError(
            "Could not identify an air temperature column in the CSV weather file. "
            "Expected a column containing words like temperature, dry bulb, or temp."
        )

    air_temperatures = _clean_numeric_series(df[temp_col], default=10.0)
'''

new2 = '''    # Positional fallback for CIBSE/BRE numeric tables with no usable headers.
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
'''

if old2 not in text:
    raise RuntimeError("Could not find temperature error block in weather_mapper.py")

text = text.replace(old2, new2, 1)

# Add fallback wind/diffuse/direct after column detection if generic numeric table.
old3 = '''    wind_speeds = (
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
'''

new3 = '''    wind_speeds = (
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
'''

if old3 not in text:
    raise RuntimeError("Could not find wind/diffuse/direct block in weather_mapper.py")

text = text.replace(old3, new3, 1)

path.write_text(text, encoding="utf-8")
print("Patched weather_mapper.py to read CIBSE/BRE-style CSV weather files.")