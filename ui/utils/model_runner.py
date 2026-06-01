import subprocess
from pathlib import Path


def run_hem_model(input_path: Path, weather_file: Path):
    """Run the HEM engine using uv and return the completed process."""

    command = [
        "uv",
        "run",
        "hem-core",
        str(input_path),
        "--CIBSE-weather-file",
        str(weather_file),
    ]

    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        shell=False,
    )