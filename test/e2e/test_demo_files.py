"""
End to End tests for HEM Core and the Future Homes Standard wrapper.

This file uses fixtures to provide the main test function (test_demo_file) with the
inputs it requires. This simplified the test-function itself and separates out the logic
for determining the inputs.
"""

import csv
import shlex
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas.testing
import pytest

from hem_core import hem
from hem_core.hem import safe_path

from .config import PATH_DEMO_FILES, PATH_EXPECTED_RESULTS, DemoFileConfig, Tolerance

PATH_ROOT = safe_path(Path(__file__).parent.parent.parent)
PATH_DEMO_FILES_SHORT = safe_path(PATH_DEMO_FILES / "short")
PATH_SRC = safe_path(PATH_ROOT / "src")
PATH_BUILD = safe_path(PATH_ROOT / "build_directory")


def test_demo_file(
    demo_name: str,
    demo_file: Path,  # Parameterised fixture for each demo file
    hem_arguments: list[str],
    actual_results_directory: Path,
    expected_results_directory: Path,
    tolerance: Tolerance,
    is_pdb_enabled: bool,
) -> None:
    """
    Run HEM for each demo file, and check their results against the expected results.
    """
    # Before running HEM, delete the results path, to avoid past results affecting this run.
    if actual_results_directory.exists():
        shutil.rmtree(actual_results_directory)
    _run_hem(
        demo_files=[demo_file],
        arguments=hem_arguments,
        use_subprocess=not is_pdb_enabled,
    )
    _compare_results(
        demo_name=demo_name,
        actual_results_directory=actual_results_directory,
        expected_results_directory=expected_results_directory,
        tolerance=tolerance,
    )


def test_demo_files_in_parallel(
    parallel_demo_files: list[Path],
    is_pdb_enabled: bool,
    tmp_path: Path,
) -> None:
    """
    Run HEM for several demo files in parallel mode, and check their results against the expected results.
    These are run isolated in tmp_path, to avoid crossover with the main test_demo_file().
    """
    default_demo_config = DemoFileConfig()
    arguments = default_demo_config.hem_arguments
    arguments += ["--parallel", "2"]

    # Copy the demo files to the tmp_path
    tmp_demo_files: list[Path] = []
    for demo_file in parallel_demo_files:
        tmp_file = tmp_path / demo_file.name
        shutil.copyfile(demo_file, tmp_file)
        tmp_demo_files.append(tmp_file)

    _run_hem(
        demo_files=tmp_demo_files,
        arguments=arguments,
        # Enables debugging into hem.py, but not into the inner multiprocessing job for each demo file.
        use_subprocess=not is_pdb_enabled,
    )
    for index, demo_file in enumerate(parallel_demo_files):
        demo_name = demo_file.stem
        isolated_results_directory = safe_path(_actual_results_directory(tmp_demo_files[index]))
        _compare_results(
            demo_name=demo_name,
            actual_results_directory=isolated_results_directory,
            expected_results_directory=_expected_results_directory(demo_file),
            tolerance=Tolerance(),
        )


def test_demo_file_with_epw_weather_file(
    demo_name: str,
    isolated_demo_file: Path,
    hem_arguments_epw: list[str],
    isolated_results_directory: Path,
    expected_results_directory: Path,
    tolerance: Tolerance,
    is_pdb_enabled: bool,
    request: pytest.FixtureRequest,
):
    """
    Run demo files with the EPW weather file, instead of the CIBSE weather file. The expected results should be consistent.
    Unlike test_demo_files(), this test isolated the demo file with tmp_path, to avoid conflicting with the results
    of temp_demo_files(). Ideally temp_demo_files would also do this...
    """
    if (
        not request.config.getoption("--all-demos-with-epw", default=False)
        and "24hrs" not in demo_name
    ):
        pytest.skip()  # Skip any non-24hrs demo files without the flag.

    _run_hem(
        demo_files=[isolated_demo_file],
        arguments=hem_arguments_epw,
        use_subprocess=not is_pdb_enabled,
    )
    _compare_results(
        demo_name=demo_name,
        actual_results_directory=safe_path(isolated_results_directory),
        expected_results_directory=expected_results_directory,
        tolerance=tolerance,
    )


@pytest.fixture
def actual_results_directory(demo_file: Path) -> Path:
    return _actual_results_directory(demo_file)


def _actual_results_directory(demo_file: Path) -> Path:
    return safe_path(demo_file.parent / f"{demo_file.stem}__results")


@pytest.fixture
def expected_results_directory(demo_file: Path) -> Path:
    return _expected_results_directory(demo_file)


def _expected_results_directory(demo_file: Path) -> Path:
    relative_parent_path = demo_file.parent.relative_to(PATH_DEMO_FILES)
    return safe_path(PATH_EXPECTED_RESULTS / relative_parent_path / f"{demo_file.stem}__results")


@pytest.fixture
def parallel_demo_files() -> list[Path]:
    """
    Returns a list of isolated demo files and their isolated results directories, to be tested in parallel.
    Isolate the demo files into the tmp_path so they don't interfere with the main test_demo_file() runs.
    """
    demo_files = list(PATH_DEMO_FILES_SHORT.glob("demo_24hrs_August_WWHRS*.json"))
    assert len(demo_files) == 4, "Expected there to be 4 WWHRS demo files"
    return demo_files


def _run_hem(
    demo_files: list[Path],
    arguments: list[str],
    use_subprocess: bool,
) -> None:
    files = [str(file) for file in demo_files]
    if use_subprocess:
        process = subprocess.Popen(
            args=["hem-core"] + files + arguments,  # Use arguments to get string escaping.
        )
        return_code = process.wait()
    else:
        return_code = hem.main(files + arguments)
    if return_code != 0:
        pytest.fail(f"""
        HEM exited with non-zero status code: {return_code}
        Command:
        {shlex.join(["hem-core"] + files + arguments)}
        """)


def _compare_results(
    demo_name: str,
    actual_results_directory: Path,
    expected_results_directory: Path,
    tolerance: Tolerance,
) -> None:
    assert expected_results_directory.is_relative_to(PATH_EXPECTED_RESULTS)
    assert not actual_results_directory.is_relative_to(PATH_EXPECTED_RESULTS)

    # Static results file
    static_results_file_name = f"{demo_name}__core__results_static.csv"
    _compare_structured_csv(
        actual=actual_results_directory / static_results_file_name,
        expected=expected_results_directory / static_results_file_name,
        tolerance=tolerance,
        read_csv_config={
            "header": None,
            "index_col": 0,
            "dtype": {0: str, 1: str, 2: np.float64},
        },
    )
    # Main results file
    main_results_file_name = f"{demo_name}__core__results.csv"
    _compare_structured_csv(
        actual=actual_results_directory / main_results_file_name,
        expected=expected_results_directory / main_results_file_name,
        tolerance=tolerance,
        read_csv_config={
            "header": [0, 1],
            "dtype": np.float64,
        },
    )
    # Compare summary file after full results, to make it easier to track down calculation errors Vs summary errors.
    summary_results_file_name = f"{demo_name}__core__results_summary.csv"
    _compare_unstructured_csv(
        actual=actual_results_directory / summary_results_file_name,
        expected=expected_results_directory / summary_results_file_name,
        tolerance=tolerance,
    )
    # Compare detailed output files, if present
    ventilation_results_file_name = f"{demo_name}__core__ventilation_results.csv"
    if (expected_results_directory / ventilation_results_file_name).exists():
        _compare_structured_csv(
            actual=actual_results_directory / ventilation_results_file_name,
            expected=expected_results_directory / ventilation_results_file_name,
            tolerance=tolerance,
            read_csv_config={
                "header": [0, 1],
                "dtype": {
                    1: str,
                },
            },
        )
    # Compare detailed heat balance files, if present
    for file_name in [
        f"{demo_name}__core__results_heat_balance_air_node.csv",
        f"{demo_name}__core__results_heat_balance_external_boundary.csv",
        f"{demo_name}__core__results_heat_balance_internal_boundary.csv",
    ]:
        if (expected_results_directory / file_name).exists():
            _compare_unstructured_csv(
                actual=actual_results_directory / file_name,
                expected=expected_results_directory / file_name,
                tolerance=tolerance,
            )
        else:
            assert not (actual_results_directory / file_name).exists()
    # Compare detailed heat source wet files, if present
    expected_heat_source_wet_files = expected_results_directory.glob(
        f"{demo_name}__core__results_heat_source_wet__*.csv"
    )
    for expected_file in expected_heat_source_wet_files:
        file_name = expected_file.name
        assert (actual_results_directory / file_name).exists()
        _compare_unstructured_csv(
            actual=actual_results_directory / file_name,
            expected=expected_file,
            tolerance=tolerance,
        )
    # Compare detailed heat source wet summary files, if present
    expected_heat_source_wet_summary_files = expected_results_directory.glob(
        f"{demo_name}__core__results_heat_source_wet_summary__*.csv"
    )
    for expected_file in expected_heat_source_wet_summary_files:
        file_name = expected_file.name
        assert (actual_results_directory / file_name).exists()
        _compare_unstructured_csv(
            actual=actual_results_directory / file_name,
            expected=expected_file,
            tolerance=tolerance,
        )
    # Compare detailed hot water source summary files, if present
    expected_hot_water_source_summary_files = expected_results_directory.glob(
        f"{demo_name}__core__results_hot_water_source_summary__*.csv"
    )
    for expected_file in expected_hot_water_source_summary_files:
        file_name = expected_file.name
        assert (actual_results_directory / file_name).exists()
        _compare_structured_csv(
            actual=actual_results_directory / file_name,
            expected=expected_file,
            tolerance=tolerance,
            read_csv_config={
                "header": [0, 1],
                "dtype": {5: str},
            },
        )
    # Compare detailed emitters files, if present
    expected_emitters_files = expected_results_directory.glob(
        f"{demo_name}__core__results_emitters__*.csv"
    )
    for expected_file in expected_emitters_files:
        file_name = expected_file.name
        assert (actual_results_directory / file_name).exists()
        _compare_structured_csv(
            actual=actual_results_directory / file_name,
            expected=expected_file,
            tolerance=tolerance,
            read_csv_config={
                "header": [0, 1],
                "dtype": np.float64,
            },
        )
    # Compare detailed ESH files, if present
    expected_esh_files = expected_results_directory.glob(f"{demo_name}__core__results_esh__*.csv")
    for expected_file in expected_esh_files:
        file_name = expected_file.name
        assert (actual_results_directory / file_name).exists()
        _compare_structured_csv(
            actual=actual_results_directory / file_name,
            expected=expected_file,
            tolerance=tolerance,
            read_csv_config={
                "header": [0, 1],
                "dtype": np.float64,
            },
        )


def _compare_structured_csv(
    actual: Path,
    expected: Path,
    tolerance: Tolerance,
    read_csv_config: dict[str, Any] | None = None,
) -> None:
    actual = safe_path(actual)
    expected = safe_path(expected)
    assert expected.exists(), f"Expected results file not found:\n{expected}"
    assert actual.exists(), f"Actual results file not found:\n{actual}"
    assert expected.is_relative_to(PATH_EXPECTED_RESULTS)
    assert not actual.is_relative_to(PATH_EXPECTED_RESULTS)

    if read_csv_config is None:
        read_csv_config = {}
    if "dtype" in read_csv_config and isinstance(read_csv_config["dtype"], dict):
        dtype_with_default = defaultdict(lambda: np.float64)
        for key, value in read_csv_config["dtype"].items():
            dtype_with_default[key] = value
        read_csv_config["dtype"] = dtype_with_default

    try:
        actual_df = pandas.read_csv(actual, **read_csv_config)
    except Exception as ex:
        ex.add_note(f"Actual results file: {actual}")
        raise ex
    try:
        expected_df = pandas.read_csv(expected, **read_csv_config)
    except Exception as ex:
        ex.add_note(f"Expected results file: {expected}")
        raise ex

    # Re-order the columns. The column order is not guaranteed, and this reduces diffs if demo files change slightly
    # (e.g. the order of inputs changes)
    actual_df_reordered = actual_df.reindex(columns=expected_df.columns)

    try:
        pandas.testing.assert_frame_equal(
            actual_df_reordered,
            expected_df,
            atol=tolerance.atol,
            rtol=tolerance.rtol,
            check_like=True,  # Ignore column/index order in the dataframes, but assert the corresponding values for each colum and row match.
        )
    except AssertionError as ex:
        ex.add_note(f"Actual file: {actual.relative_to(PATH_ROOT)}")
        ex.add_note(f"Expected file: {expected.relative_to(PATH_ROOT)}")
        raise ex


def _compare_unstructured_csv(actual: Path, expected: Path, tolerance: Tolerance) -> None:
    def _parse_numbers(rows: Iterable[list[str]]) -> list[list[str | float]]:
        parsed: list[list] = []
        for row_idx, row in enumerate(rows):
            parsed.append(row)
            for item_idx, item in enumerate(row):
                try:
                    parsed[row_idx][item_idx] = float(item)
                except ValueError:
                    pass
        return parsed

    with (
        open(actual) as actual_file,
        open(expected) as expected_file,
    ):
        actual_rows = _parse_numbers(csv.reader(actual_file))
        expected_rows = _parse_numbers(csv.reader(expected_file))

    try:
        for index, row in enumerate(actual_rows):
            assert row == pytest.approx(
                expected_rows[index], abs=tolerance.atol, rel=tolerance.rtol
            ), f"Row {index} different to expected"
    except AssertionError as ex:
        ex.add_note(f"Actual file: {actual.relative_to(PATH_ROOT)}")
        ex.add_note(f"Expected file: {expected.relative_to(PATH_ROOT)}")
        raise ex
