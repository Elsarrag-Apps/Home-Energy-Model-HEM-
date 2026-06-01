import shutil
from pathlib import Path

import pytest

from .config import DemoFileConfig, E2EConfig, Tolerance, get_e2e_config

PATH_ROOT = Path(__file__).parent.parent.parent


def pytest_addoption(parser: pytest.Parser):
    parser.addoption(
        "--all-demos-with-epw",
        action="store_true",
        default=False,
        help="Test all demo files with the EPW weather file. If not set, only a subset of demo files will be tested.",
    )


@pytest.fixture(scope="session")
def e2e_config() -> E2EConfig:
    return get_e2e_config()


@pytest.fixture
def demo_file_config(demo_file: Path, e2e_config: E2EConfig) -> DemoFileConfig:
    return e2e_config.get_config_for_demo_file(demo_file)


@pytest.fixture
def hem_arguments(
    demo_file_config: DemoFileConfig,
) -> list[str]:
    return demo_file_config.hem_arguments


@pytest.fixture
def hem_arguments_epw(hem_arguments: list[str]) -> list[str]:
    modified_hem_arguments = []
    for argument in hem_arguments:
        match argument:
            case "--CIBSE-weather-file":
                modified_hem_arguments.append("--epw-file")
            case "test/e2e/demo_files/London_weather_CIBSE_format.csv":
                modified_hem_arguments.append(
                    "test/e2e/demo_files/London_weather_EnergyPlus_format.epw"
                )
            case _:
                modified_hem_arguments.append(argument)
    return modified_hem_arguments


@pytest.fixture
def tolerance(demo_file_config: DemoFileConfig) -> Tolerance:
    return demo_file_config.tolerance


@pytest.fixture
def results_directory_name(demo_name: str) -> str:
    return f"{demo_name}__results"


@pytest.fixture
def isolated_demo_file(demo_file: Path, tmp_path: Path) -> Path:
    """
    Isolates the demo file in a temporary directory for the test, to avoid the results directory clashing with
    another worker.
    This does make debugging the results files difficult, but prevents parallel workers treading on each others toes.
    """
    temp_demo_file = tmp_path / demo_file.name
    shutil.copyfile(demo_file, temp_demo_file)
    return temp_demo_file


@pytest.fixture
def isolated_results_directory(results_directory_name: Path, tmp_path: Path) -> Path:
    return tmp_path / results_directory_name
