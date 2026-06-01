"""
The hem-core CLI arguments should remain compatible within major versions.

If you have only added new arguments/options, or edited the help text,
then you may update the expected help text by running:

    pytest test/integration/test_hem_core_cli.py -n0 --update-expected-public-interface

"""

from argparse import ArgumentParser
from pathlib import Path

import pytest

import hem_core.hem


@pytest.fixture(scope="session")
def hem_argument_parser() -> ArgumentParser:
    return hem_core.hem.define_cli_argument_parser()


@pytest.fixture(scope="session")
def path_cli_help(path_expected: Path) -> Path:
    return path_expected / "cli_help.txt"


@pytest.fixture(autouse=True, scope="session")
def __update_expected_arguments(
    request: pytest.FixtureRequest, hem_argument_parser: ArgumentParser, path_cli_help: Path
):
    """
    An auto-use fixture (which runs before the tests) to update the expected cli arguments JSON file.
    """
    if not request.config.getoption(name="--update-expected-public-interface", default=False):
        return
    usage = hem_argument_parser.format_help()
    with open(path_cli_help, mode="w+", encoding="utf-8") as file:
        file.write(usage)


@pytest.fixture(scope="session")
def expected_cli_usage(path_cli_help: Path) -> str:
    with open(path_cli_help, mode="r", encoding="utf-8") as file:
        return file.read()


def test_cli_arguments(hem_argument_parser: ArgumentParser, expected_cli_usage: str):
    assert hem_argument_parser.format_help() == expected_cli_usage
