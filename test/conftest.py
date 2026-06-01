import json
from copy import deepcopy
from pathlib import Path

import pytest

from hem_core.hem import safe_path

from .e2e.config import PATH_DEMO_FILES

PATH_ROOT = safe_path(Path(__file__).parent.parent)


@pytest.fixture(scope="session")
def path_root() -> Path:
    return PATH_ROOT


@pytest.fixture(scope="session")
def path_demo_files() -> Path:
    return PATH_DEMO_FILES


@pytest.fixture(scope="session")
def is_pdb_enabled(request: pytest.FixtureRequest) -> bool:
    """
    Fixture to check if --pdb was used.
    """
    return request.config.getoption(name="--pdb", default=False)


def _demo_file_parameters(*args: Path) -> list[Path]:
    # Generate each JSON demo file in one or more paths
    return [
        file
        # Only JSON files directly within these directories will be run.
        for dir in args
        for file in dir.iterdir()
        if file.is_file() and file.suffix == ".json"
    ]


def _demo_file_label(demo_file: Path) -> str:
    # Generate a pytest id/label for each demo file using the relative path from the ROOT directory
    return str(demo_file.relative_to(PATH_ROOT))


@pytest.fixture(
    scope="function",
    params=_demo_file_parameters(
        PATH_DEMO_FILES / "short",
        PATH_DEMO_FILES / "long",
    ),
    ids=_demo_file_label,
)
def demo_file(request: pytest.FixtureRequest) -> Path:
    """
    This fixture provides all .json files from PATH_DEMO_FILES.
    Pytest params are used, so that pytest can report on each individual test case
    passing/failing, and so that xdist can run them in parallel.
    """
    return safe_path(request.param)


@pytest.fixture
def demo_name(demo_file: Path) -> str:
    return demo_file.stem


@pytest.fixture(scope="session")
def baseline_demo_file(path_demo_files: Path) -> Path:
    """
    Returns a single, consistent demo file for use as a baseline in tests.
    """
    return path_demo_files / "short" / "demo.json"


@pytest.fixture(scope="session")
def baseline_demo_file_json(baseline_demo_file: Path) -> str:
    """
    Returns the JSON string from the baseline demo file, for use as a baseline in tests.
    """
    with open(baseline_demo_file) as file:
        return file.read()


@pytest.fixture(scope="session")
def _baseline_demo_file_dict(baseline_demo_file_json: str) -> dict:
    return json.loads(baseline_demo_file_json)


@pytest.fixture(scope="function")
def baseline_demo_file_dict(_baseline_demo_file_dict: dict) -> dict:
    """
    Returns the JSON string from the baseline demo file, for use as a baseline in tests.
    """
    return deepcopy(
        _baseline_demo_file_dict
    )  # Copy the original so that tests can not alter the session fixture value.
