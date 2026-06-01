import multiprocessing
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from functools import cache
from pathlib import Path
from typing import Annotated

import rich.progress
import typer
from rich import print

from hem_core.hem import safe_path

PATH_ROOT = safe_path(Path(__file__).parent.parent)

# Need to add the test directory to the path for importing the e2e config
sys.path.append(str(PATH_ROOT))

from test.e2e.config import (  # noqa: E402  # Needs sys path altering
    PATH_DEMO_FILES,
    PATH_EXPECTED_RESULTS,
    E2EConfig,
    get_e2e_config,
)

IGNORE_RESULTS_FILES = [
    "*results_static.csv",
    "*results_summary.csv",
]

verbose = False  # Global state, set from arguments in main()


class Demo:
    """
    A representation of a demo file, with helper-properties for commonly accessed details
    (like the expected results directory, file-name, etc)
    """

    def __init__(self, path: Path):
        if not path.is_absolute():
            path = PATH_ROOT / path
        if not path.exists():
            raise ValueError(f"Path does not exist: {path}")
        if not path.is_file():
            raise ValueError(f"Path is not a file: {path}")
        self.path = path

    @property
    def name(self) -> str:
        return self.path.stem

    @property
    def relative_path(self) -> Path:
        return self.path.relative_to(PATH_ROOT)

    @property
    def results_dir(self) -> Path:
        return self.path.parent / f"{self.name}__results"

    @property
    def expected_results_dir(self) -> Path:
        subdir = self.path.parent.name
        return PATH_EXPECTED_RESULTS / subdir / f"{self.name}__results"

    @property
    def hem_arguments(self) -> list[str]:
        e2e_config = _get_e2e_config()
        demo_file_config = e2e_config.get_config_for_demo_file(self.path)
        return demo_file_config.hem_arguments


def _run_demo(demo: Demo):
    """
    Run hem-core for a single demo file.
    """

    if verbose:
        print(f"[blue]Running[/blue]: {demo.path.relative_to(PATH_ROOT)}")
    if demo.results_dir.exists():
        # Delete existing results, in case the names or number of files output have changed.
        shutil.rmtree(demo.results_dir)
    start = datetime.now()
    command_args = ["hem-core", str(demo.relative_path)] + demo.hem_arguments

    process = subprocess.Popen(
        args=command_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return_code = process.wait()
    end = datetime.now()
    if return_code != 0:
        std_out, std_err = process.communicate()
        print(f"=== stdout ===\n{std_out}\n=== end ===")
        print(f"=== stderr ===[red]\n{std_err}[/red]\n=== end ===")
        sys.stdout.flush()
        print(f"[red]Error running file:[/red] {demo.path}")
        print(f"Command: [blue]{shlex.join(command_args)}")
        print("See stdout and stderr above")
        raise typer.Exit(2)
    run_time = end - start
    if verbose and run_time > timedelta(seconds=10):
        print(
            f"Run time for file: {demo.path.relative_to(PATH_ROOT)}\n"  # fmt: skip
            f"                         {run_time}"
        )
    return demo


def _copy_results_files(demo: Demo):
    if demo.expected_results_dir.exists():
        # Remove the destination directory and any existing content (easier than deciding which files to keep)
        shutil.rmtree(demo.expected_results_dir)
    shutil.copytree(
        src=demo.results_dir,
        dst=demo.expected_results_dir,
        ignore=shutil.ignore_patterns(
            demo.path.name,  # Skip the demo JSON file itself
        ),
    )


def _run(demos: list[Demo], processes: int):
    with (
        rich.progress.Progress() as progress,
        multiprocessing.Pool(processes=processes) as pool,
    ):
        if verbose and processes > 1:
            print(f"Running with a pool of [blue]{processes}[/blue] workers")
        task_id = progress.add_task("Running demo files...", total=len(demos))
        for demo in pool.imap_unordered(func=_run_demo, iterable=demos):
            _copy_results_files(demo)
            progress.advance(task_id)
            if verbose:
                print(f"[green]Completed[/green]: {demo.path.relative_to(PATH_ROOT)}")

    print("[green]Finished.")


def main(
    all_demo_files: Annotated[
        bool,
        typer.Option(
            "--all",
            help="Run for all demo files.",
        ),
    ] = False,
    file_glob: Annotated[
        str | None,
        typer.Option(
            "--glob",
            help=f"""Run for any demo files matching a file glob.

\b
This glob must be relative to: {PATH_DEMO_FILES.relative_to(PATH_ROOT)}
Example: --glob=test/e2e/demo_files/core/*24hrs*.json
""",
        ),
    ] = None,
    files: Annotated[
        list[Path] | None,
        typer.Option(
            "--file",
            "-f",
            help="Run for specific a demo file (can be specified more than once)",
        ),
    ] = None,
    processes: Annotated[
        int,
        typer.Option(
            "--processes",
            "-p",
            help="Run multiple demo files in parallel (with this many workers)",
        ),
    ] = 1,
    set_verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Print out each file as it is worked on.",
        ),
    ] = False,
):
    """
    Run end-to-end demo files and copy their results to the expected results directory.
    """
    global verbose
    if set_verbose:
        verbose = True

    if all_demo_files:
        demos = [Demo(path=path) for path in PATH_DEMO_FILES.glob("*/*.json")]
    elif file_glob is not None:
        paths = _validate_file_glob(file_glob)
        demos = [Demo(path=path) for path in paths]
    elif files is not None:
        files = _validate_file_list(files)
        demos = [Demo(path=PATH_ROOT / path) for path in files]
    else:
        print("[red]Either --all, --glob or --file must be used")
        raise typer.Exit(code=1)

    _run(demos=demos, processes=processes)


def _validate_file_list(files: list[Path]) -> list[Path]:
    missing_files = []
    for path in files:
        if not path.exists():
            missing_files.append(path)
    if missing_files:
        print("[red]File not found:")
        print(missing_files)
        raise typer.Exit(code=1)
    return files


def _validate_file_glob(file_glob: str) -> list[Path]:
    paths = list(PATH_ROOT.glob(file_glob))
    # Check glob matches are all valid
    glob_valid = True
    if not paths:
        print("[red]Glob does not match any files")
        glob_valid = False
    for path in paths:
        # Glob produces paths relative to CWD so not relative to PATH_DEMO_FILES which is absolute.
        if not path.is_relative_to(PATH_DEMO_FILES):
            print(f"[red]glob matches file not relative to demo_files directory:[/red] {path}")
            glob_valid = False
            continue
        if path.suffix.lower() != ".json":
            print(f"[red]Glob must only match files with .json suffix: {path}")
            glob_valid = False
    if not glob_valid:
        raise typer.Exit(code=1)
    return paths


@cache
def _get_e2e_config() -> E2EConfig:
    return get_e2e_config()


if __name__ == "__main__":
    typer.run(main)
