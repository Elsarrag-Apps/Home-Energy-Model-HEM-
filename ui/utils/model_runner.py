import subprocess
import sys
from pathlib import Path


def get_weather_argument(weather_file: Path) -> list[str]:
    """Return the correct HEM weather command argument for CSV or EPW files."""
    suffix = weather_file.suffix.lower()

    if suffix == ".csv":
        return ["--CIBSE-weather-file", str(weather_file)]

    if suffix == ".epw":
        return ["--epw-file", str(weather_file)]

    raise ValueError(
        f"Unsupported weather file type: {suffix}. Expected .csv or .epw."
    )


def run_hem_model(input_json_path: Path, weather_file: Path):
    """Run HEM with a generated input JSON and weather file."""
    input_json_path = Path(input_json_path)
    weather_file = Path(weather_file)

    if not input_json_path.exists():
        raise FileNotFoundError(f"HEM input JSON not found: {input_json_path}")

    if not weather_file.exists():
        raise FileNotFoundError(f"Weather file not found: {weather_file}")

    command = [
        "uv",
        "run",
        "hem-core",
        str(input_json_path),
        *get_weather_argument(weather_file),
    ]

    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        shell=False,
    )
