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


def _run_first_available(commands: list[list[str]]):
    last_error = None

    for command in commands:
        try:
            return subprocess.run(
                command,
                capture_output=True,
                text=True,
                shell=False,
            )
        except FileNotFoundError as exc:
            last_error = exc
            continue

    raise FileNotFoundError(
        "Could not find a working HEM runner. Tried uv, python -m hem_core.hem, "
        "and python src/hem_core/hem.py. Original error: " + str(last_error)
    )


def run_hem_model(input_json_path: Path, weather_file: Path):
    """Run HEM with a generated input JSON and weather file."""
    input_json_path = Path(input_json_path)
    weather_file = Path(weather_file)

    if not input_json_path.exists():
        raise FileNotFoundError(f"HEM input JSON not found: {input_json_path}")

    if not weather_file.exists():
        raise FileNotFoundError(f"Weather file not found: {weather_file}")

    weather_args = get_weather_argument(weather_file)

    commands = [
        ["uv", "run", "hem-core", str(input_json_path), *weather_args],
        [sys.executable, "-m", "hem_core.hem", str(input_json_path), *weather_args],
        [sys.executable, "src/hem_core/hem.py", str(input_json_path), *weather_args],
    ]

    return _run_first_available(commands)
