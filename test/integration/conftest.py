from pathlib import Path

import pytest


def pytest_addoption(parser: pytest.Parser):
    parser.addoption(
        "--update-expected-public-interface",
        action="store_true",
        default=False,
        help="Update the expected public interface before running the tests.",
    )


@pytest.fixture(scope="session")
def path_expected() -> Path:
    return Path(__file__).parent / "expected"
