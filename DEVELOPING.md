# Developer documentation

## Development tools
The key development tools used for HEM Core are:

- [uv](#python-virtual-environment) is used for manging dependencies, the virtual environment, and installing different versions of Python for development.
- [pre-commit](#pre-commit) is used for enforcing linting checks etc
- [ruff](#ruff) is used for linting and formatting
- [pytest](#tests) is used for running unit and end-to-end tests

`uv` will install all of these as development dependencies.

### Example commands
- Unless otherwise stated, example commands should be run from the top directory of the project.
- Windows/Unix file paths
  - Where commands are otherwise identical between Windows/Unix, the documentation uses `unix/style/file/paths`.
  - Simply substitute `\` for running them on Windows.
  - Where Windows requires separate commands, these will be documented fully.

# Python virtual environment
We use `uv` to manage creating the virtual environment with `uv sync`.

Some of our pre-commit hooks depend on the virtual environment path being `uv`'s default: `.venv`.

# Dependencies
Because HEM needs to produce consistent calculations, we define our primary dependencies as exact versions,
even though `uv` also locks exact versions.

This forces us to consciously pick, set and test new dependency versions, and avoids `uv` locking to some intermediary
version to resolve the dependency tree.

## Upgrading dependencies

```shell
uv lock --upgrade
```
This will update all packages, within any constraints set in `pyproject.toml`.

# Tests
This project has unit-tests and end-to-end tests, and both are run using [pytest](https://docs.pytest.org/en/stable/).

## Unit tests
The unit tests can be run with:
```shell
pytest test/unit_tests/
```

To run specific tests, you can filter by both file-path:
```shell
pytest test/unit_tests/core/test_ductwork.py
```
But also by test class/name or even keywords, using pytest's `-k` filter.

E.g:
```shell
pytest -k "Duct"
```

## End-to-end tests
In order to run the end-to-end tests, run the following:

```shell
pytest test/e2e
```

The results in the expected_results folder were generated using:

* Python 3.12
* The library versions specified in `requirements_3-12.txt`
* The `London_weather_CIBSE_format.csv` weather file in the `test/e2e/demo_files/` folder

Make sure that the number of tests that ran is greater than zero. If any of the tests failed, the
output from running the pytest module should indicate the issue(s) that need to be resolved.


## Running tests in parallel

The [pytest-xdist plugin](https://pytest-xdist.readthedocs.io/en/stable/distribution.html)
helps with running tests in parallel.

Pytest is configured to automatically run with as many workers as you have physical CPU cores.

You can also configure the number of workers at runtime with: `pytest -n4` (for 4 workers).

Or more permanently you can set the `PYTEST_XDIST_AUTO_NUM_WORKERS` environment variable in your shell.

There are diminishing returns with more than 4-ish workers, as each worker does take a small amount of time to set up.

If you are running a single test, `xdist` will unfortunately still spawn multiple workers, so you can prevent that 
with `pytest -n0 <test-file>`

### Debugging tests

The `--pdb` option for pytest is very useful to drop you into the python debugger on a test-failure.

`xdist` is smart enough to know that if you use `--pdb` it should not spawn multiple workers.

## Coverage
Code-coverage is checked for the **unit tests**, in both a pre-commit hook and on the Azure DevOps CI pipeline.

The standard code coverage threshold is set to 100% for new code, and for existing code which already has full coverage.

Several files also have lower coverage thresholds set ().
This enforces that coverage does not _decrease_ in these files, until they are brought up to 100% coverage.

We allow for pragmatically excluding certain lines from code with `# pragma: no cover` comments
(e.g. error-conditions which should not be reachable under normal operation).

### Tools
Several tools are used for collecting and reporting on code coverage:
- [coverage](https://coverage.readthedocs.io)
  - This the main python code-coverage package.
- [pytest-cov](https://pytest-cov.readthedocs.io)
  - This makes it simple to measure coverage across multiple `pytest-xdist` workers
- [coverage-threshold](https://github.com/DeanWay/coverage-threshold)
  - This enables setting per-file line coverage targets, allowing us to prevent coverage
    decreasing without having to first meet 100% coverage on all files.
  - These thresholds are defined in `pyproject.toml` in the `[tool.coverage-threshold]` section.

### Manually reporting coverage

`coverage` can output several report formats.

First run the unit tests with the `--cov` flag to generate the coverage data:
```shell
pytest test/unit_tests/ --cov
```

By default, this will output a text report with the percentage coverage for each file. This can be made a bit more useful with:
- `--cov-report=term-missing` to show the line numbers which do not have coverage
- `--cov-report=term-missing:skip-covered` to skip reporting files which have 100% coverage

`coverage` can also be used to produce other report formats, the most useful of which is the HTML report:
```shell
coverage html
```
The report can then be viewed at: `htmlcov/index.html`

### Coverage for E2E tests

> ⏳ Slow<br>
> Running the E2E tests with coverage collection _significantly_ increases their run-time by over 4x.<br>
> For this reason, we do not run E2E coverage reporting for every PR.

Running a coverage report for the end-to-end tests is much the same as for the unit tests above:
```shell
pytest test/e2e/ --cov
coverage html
```

### CI pipeline

`.azure-pipelines/ci.yaml` produces a HTML coverage report for the **unit tests** and uses the `pytest-azurepipelines`
plugin to upload the report on the Azure Pipeline run results.

# Running using Cython
[Cython](https://cython.org/) can be used to compile Python code to C, to improve the runtime of HEM.
To do this you need to run slightly different commands.

Before running make sure you have activated the Virtual Environment and installed dependencies.
Then you run the following commands to convert and run the C version of HEM.

## Ubuntu:
1. Convert specific .py files to C using Cython and save them to a new directory called "build_directory":

```shell
python setup.py build_ext --inplace
```

2. Then you can run HEM with a similar command, but looking at the build_directory/ rather than src/:

```shell
python3 build_directory/hem.py test/e2e/demo_files/core/demo.json --epw-file /path/to/weather_files/GBR_ENG_Leeds.Wea.Ctr.033470_TMYx.epw
```

## Windows:
1. Convert specific .py files to C using Cython and save them to a new directory called "build_directory":

```shell
python setup.py build_ext --inplace
```

2. Then you can run HEM with a similar command, but looking at the build_directory/ rather than src/:

```shell
python build_directory\hem.py test\demo_files\core\demo.json --epw-file C:\path\to\weather_files\GBR_ENG_Leeds.Wea.Ctr.033470_TMYx.epw
```

# Linting

We use an AzureDevOps pipeline to enforce linting and formatting checks: `.azure-pipelines/ci.yaml`

## Ruff

We use [Ruff](https://docs.astral.sh/ruff/) for linting and auto-formatting python code.

Most existing files are excluded (in `pyproject.toml` `[tool.ruff]`) until we have full test-coverage and can then
address the linting and formatting issues.

New files should conform to ruff's linting and formatting rules.

If your IDE has a [Ruff integration](https://docs.astral.sh/ruff/editors/)
then it can run Ruff automatically whilst editing, so you'll see it reformat your code and highlight any linting errors
as you work.

## pre-commit
We use [pre-commit](https://pre-commit.com/) to run our linting checks before commit/push,
to avoid re-running AzureDevOps pipelines and eating through the usage quota.

Please install and set up the `pre-commit` hooks before commiting to this repository:

### Installing pre-commit
You will need a system level installation of [git](https://git-scm.com/), so if you are
only using an IDE-plugin then you will also need to install git on your system.

You will then need to run (once):
```shell
uv run pre-commit install --install-hooks
```

After that, our hooks should be triggered whenever the correspinding git actions are run.
`pre-commit install` only needs to be run once per repository, it will handle running and updating the hooks itself
after that.

> 🛠 Note
>
> You will need a system level installation of [git](https://git-scm.com/) to run `pre-commit`.
> The Eclipse EGit plugin (and others?) do not provide a `git` executable in the shell,
> so you will need to [install git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)
> on your system.

---

# Azure Pipelines

## .azure-pipelines/ci.yaml

This pipeline runs continuous integration checks, to be run for each Pull Request targeting the `main` branch.

## .azure-pipelines/build-private.yaml

This pipeline builds and publishes the `hem-core` package to a private Azure Artifacts index. It should be run manually
targeting a git tag (this is enforced in the pipeline).


# A style note on doc strings

To maintain consistent formatting doc string should follow these standard conventions:

  Sinlge line doc strings should be enclosed with """ and end with a period. eg
    """This is a simple doc string."""
  
  Multi line doc strings should begin with """ and end with """ on a new line, eg
    """This is a long doc string with a lot of detail that requires multiple
    lines.
    """
  
  Function/method doc strings that document arguments and return values should use semi colons and indentation for consistent formatting:
    """This is function doc string.

    Args:
      arg1: A description of arg1.
      arg2: A description of arg2.
    
    Returns:
      A description of the return value.
    
    Raises:
      A description of the error raised if needed.
    """
