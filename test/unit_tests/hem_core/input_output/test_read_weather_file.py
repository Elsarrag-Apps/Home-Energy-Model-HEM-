from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from hem_core.input_output import read_weather_file


@pytest.fixture(scope="session")
def cibse_weather_file(path_demo_files: Path) -> Path:
    return path_demo_files / "London_weather_CIBSE_format.csv"


@pytest.fixture(scope="session")
def epw_weather_file(path_demo_files: Path) -> Path:
    return path_demo_files / "London_weather_EnergyPlus_format.epw"


def test_cibse_weather_data_to_dict(cibse_weather_file: Path):
    weather_dict = read_weather_file.cibse_weather_data_to_dict(cibse_weather_file)
    assert weather_dict is not None
    for key, items in weather_dict.items():
        if key not in ["longitude", "latitude", "direct_beam_conversion_needed"]:
            assert len(items) == 8760


def test_weather_data_to_dict(epw_weather_file: Path):
    weather_dict = read_weather_file.epw_weather_data_to_dict(epw_weather_file)
    assert weather_dict is not None
    for key, items in weather_dict.items():
        if key not in ["longitude", "latitude", "direct_beam_conversion_needed"]:
            assert len(items) == 8760


FIELDS = [
    "air_temperatures",
    "diffuse_horizontal_radiation",
    "direct_beam_radiation",
    "wind_speeds",
    "wind_directions",
    "solar_reflectivity_of_ground",
]


@pytest.mark.parametrize(
    "inputs, expected_message",
    [
        (
            {
                **{f: [0.0] * 8760 for f in FIELDS if f != field},
                **{field: [0.0]},
            },
            f"ExternalConditions {field} should contain 8760 values.",
        )
        for field in FIELDS
    ],
)
def test_validate_weather_data(
    inputs: dict[str, Any],
    expected_message: str,
):
    with pytest.raises(ValueError, match=expected_message):
        read_weather_file.validate_weather_data(inputs)


def test_cibse_weather_data_to_epw(cibse_weather_file: Path):
    epw_data = read_weather_file.cibse_weather_data_to_epw(cibse_weather_file)
    assert isinstance(epw_data, str)

    epw_data_df = pd.read_csv(StringIO(epw_data), skiprows=8, header=None)
    assert len(epw_data_df) == 8760


def test_cibse_weather_data_to_epw_with_solar_altitude(cibse_weather_file: Path, tmp_path: Path):
    # Force a scenario where solar_altitude is not None (test file has empty values)
    with open(cibse_weather_file, "r") as f:
        header_lines = [next(f) for _ in range(31)]

    cibse_weather_data = pd.read_csv(cibse_weather_file, skiprows=31, header=0)
    cibse_weather_data.fillna(0, inplace=True)
    cibse_weather_data["Alt"] = [45.0] * len(cibse_weather_data)

    # Write to a temporary file
    tmp_file = tmp_path / "test_weather.epw"
    # Note: need to specify newline='' below, otherwise an extra carriage return
    # character is written when running on Windows
    with open(tmp_file, "w+", newline="") as tmp:
        tmp.writelines(header_lines)
        cibse_weather_data.to_csv(tmp, index=False, header=True)

    epw_data = read_weather_file.cibse_weather_data_to_epw(tmp_file)
    epw_data_df = pd.read_csv(StringIO(epw_data), skiprows=8, header=None)
    assert len(epw_data_df) == 8760


def test_get_cibse_file_misc_data(cibse_weather_file: Path):
    misc_data = read_weather_file._get_cibse_file_misc_data(cibse_weather_file)
    assert misc_data["elevation"] == 33
    assert misc_data["year"] == 2003


def test_weather_dicts_match(cibse_weather_file: Path, epw_weather_file: Path):
    weather_dict_cibse = read_weather_file.cibse_weather_data_to_dict(cibse_weather_file)
    weather_dict_epw = read_weather_file.epw_weather_data_to_dict(epw_weather_file)
    assert weather_dict_epw.keys() == weather_dict_cibse.keys()

    for key in weather_dict_cibse.keys():
        match key:
            case "direct_beam_conversion_needed":
                assert weather_dict_epw[key] is False
                assert weather_dict_cibse[key] is True
            case "direct_beam_radiation":
                # Will be different between the two dicts because EPW should be normal incidence as standard.
                assert weather_dict_epw[key] != weather_dict_cibse[key]
            case _:
                # pytest.approx() makes it easier to find rows with differences, tolerance set absurdly high to ensure equality.
                assert weather_dict_epw[key] == pytest.approx(
                    weather_dict_cibse[key], abs=1e-100, rel=1e-100
                ), f"Different values for weather dict key: {key}"
