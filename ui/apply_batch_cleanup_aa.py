from pathlib import Path


def write_file(path, content):
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"Updated {file_path}")


write_file(
    "ui/utils/weather_mapper.py",
    r'''
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


def read_csv_weather(weather_file_path: str, hours: int) -> dict:
    path = Path(weather_file_path)

    if not path.exists():
        raise FileNotFoundError(f"Weather file not found: {weather_file_path}")

    df = pd.read_csv(path)

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

    if temp_col is None:
        raise ValueError(
            "Could not identify an air temperature column in the CSV weather file. "
            "Expected a column containing words like temperature, dry bulb, or temp."
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

    hem_input.setdefault("_ui_metadata", {})
    hem_input["_ui_metadata"]["weather_simulation"] = {
        "run_type": run_type,
        "simulation_hours": hours,
        "weather_file": weather_file,
        "weather_file_type": weather_file_type,
        "weather_rows_available": rows_available,
        "is_annual": hours >= 8760,
    }

    return hem_input
''',
)


# Patch Weather Simulation page so Annual run forces 8760 in the UI
weather_page = Path("ui/pages/2_Weather_Simulation.py")
text = weather_page.read_text(encoding="utf-8")

text = text.replace(
    '''        simulation_hours = st.number_input(
            "Simulation hours",
            min_value=1,
            value=int(saved_settings.get("simulation_hours", default_hours)),
            step=1,
        )
''',
    '''        if run_type == "Annual run":
            simulation_hours = 8760
            st.metric("Simulation hours", simulation_hours)
            st.caption("Annual run is fixed at 8760 hourly timesteps.")
        elif run_type in ["24-hour test", "168-hour test"]:
            simulation_hours = default_hours
            st.metric("Simulation hours", simulation_hours)
            st.caption("Test run length is fixed by the selected run type.")
        else:
            simulation_hours = st.number_input(
                "Simulation hours",
                min_value=1,
                value=int(saved_settings.get("simulation_hours", default_hours)),
                step=1,
            )
''',
)

weather_page.write_text(text, encoding="utf-8")
print("Patched ui/pages/2_Weather_Simulation.py")


# Patch full_case_builder.py
builder_path = Path("ui/utils/full_case_builder.py")
text = builder_path.read_text(encoding="utf-8")

if "from weather_mapper import apply_weather_simulation_to_case" not in text:
    text = text.replace(
        "from hot_water_mapper import apply_form_hot_water_to_hem_input",
        "from weather_mapper import apply_weather_simulation_to_case\nfrom hot_water_mapper import apply_form_hot_water_to_hem_input",
        1,
    )

if 'weather_simulation = project_sections.get("weather_simulation", {})' not in text:
    text = text.replace(
        '    weather_settings = project_sections.get("weather", {})\n',
        '    weather_settings = project_sections.get("weather", {})\n    weather_simulation = project_sections.get("weather_simulation", {})\n',
        1,
    )

if "hem_input = apply_weather_simulation_to_case(" not in text:
    text = text.replace(
        '''    hem_input = apply_fabric_to_case(
''',
        '''    hem_input = apply_weather_simulation_to_case(
        hem_input=hem_input,
        weather_simulation=weather_simulation,
    )

    hem_input = apply_fabric_to_case(
''',
        1,
    )

builder_path.write_text(text, encoding="utf-8")
print("Patched ui/utils/full_case_builder.py")

print("Batch AA complete.")