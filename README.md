# Introduction
The Home Energy Model (HEM) is the UK Government’s proposed National Calculation Methodology
for assessing the energy performance of dwellings. HEM was previously known as SAP 11 and any
references to SAP 11 should be interpreted as references to HEM.

Please note that HEM is currently in development and should not be used for any official purpose.

# Getting started

## Supported platforms
This program has been tested on the following platforms:

- Python 3.12 running on Ubuntu 24.04
- Python 3.12 running on Microsoft Windows 11


## Installing dependencies

Python dependencies are defined in `pyproject.toml`, using [uv](https://docs.astral.sh/uv/)
to lock dependency versions and to manage virtual environments.

`uv` does not depend on python being installed on your system, and
[their installation instructions](https://docs.astral.sh/uv/getting-started/installation/)
explain how to install it on most operating systems.

`uv` also manages installing and switching between multiple Python language versions on
your system. ([Documentation](https://docs.astral.sh/uv/concepts/python-versions/))

Once you have `uv` installed, you can quickly set up a virtual environment and install
the necessary dependencies by running the following (with the top level of the repository
as your working directory):

```shell
uv sync
```

This will:
- Create a virtual environment at `.venv`
- Download a compatible version of Python for the virtual-environment
- Download and install the HEM dependencies

You can then to enter the virtual environment.
Ubuntu:
```shell
source .venv/bin/activate
```
Windows:
```shell
.venv\Scripts\activate
```


## Running calculations
To run the program, activate the Virtual Environment if it is not active already, and run the `hem.py`
file, e.g. (assuming the working directory is the top-level folder of the repository):

Alternatively, you can also use either:
- `python -m hem_core`
- `python src/hem_core/hem.py`

Ubuntu:
```shell
uv run hem-core test/e2e/demo_files/core/demo.json --CIBSE-weather-file test/e2e/demo_files/London_weather_CIBSE_format.csv
```
Windows:
```shell
uv run hem-core test\e2e\demo_files\core\demo.json --CIBSE-weather-file test\e2e\demo_files\London_weather_CIBSE_format.csv
```

Note that the above requires an entire year's weather data to be provided in a weather file.
In this example, this is provided in CIBSE format, but HEM also accepts weather files in
EnergyPlus (`.epw`) weather file format, using the `--epw-file` flag in place of the `--CIBSE-weather-file` flag.
It is also possible to specify the weather data in the input file directly, in which case a separate
weather file is not required. This repository does not provide any weather files but files in .epw
format can be downloaded from [climate.onebuilding.org](https://climate.onebuilding.org).

Note that where the input file specifies an electric battery that can be charged from the grid, the
input file specifies the name of an electricity tariff for which data must be provided in a separate
file with the `--tariff-file` parameter, e.g.:

Ubuntu:
```shell
uv run hem-core test/e2e/demo_files/core/demo_elec_battery.json --tariff-file test/e2e/demo_files/tariff_data_25-06-2024.csv --CIBSE-weather-file test/e2e/demo_files/London_weather_CIBSE_format.csv
```
Windows:
```shell
uv run hem-core test\e2e\demo_files\core\demo_elec_battery.json --tariff-file test\e2e\demo_files\tariff_data_25-06-2024.csv --CIBSE-weather-file test\e2e\demo_files\London_weather_CIBSE_format.csv
```

The tariff file can provide data for more than one tariff, with the name of the tariff specified at
the top of each column, and HEM will look up the column where the heading matches the name of the
tariff specified in the input file. The timestep of the data in the tariff file must match the
timestep of the simulation being run, and the data in the tariff file must start at the same
timestep as the simulation being run. For example, if running a half-hourly simulation starting on
1st July, then the tariff file must contain half-hourly data starting on 1st July. Two example
tariff files are provided in test/demo_files for use with the example json files provided:

* `tariff_data_demo_files_24timesteps.csv` provides hourly tariff data for 24 hours
* `tariff_data_25-06-2024.csv` provides half-hourly tariff data for an entire year

### Full list of command-line options
For a full list of command-line options, run the following:

```shell
uv run hem-core --help
```

### Outputs
For each input file, HEM creates a results directory in the same directory as the input file, and saves
output files to this directory. The name of the output directory is based on the name of the input
file, with the file extension removed and "\_\_results" added to the end, so for example if the input
file is `test/e2e/demo_files/core/demo.json` then the outputs will be written to the folder
`test/e2e/demo_files/core/demo__results/` along with a copy of the input file that produced those
results.

When running the core model directly, the names of the output files all start with the name of the input file
(with the file extension removed), followed by `__core__`, followed by the name of the specific output file.

When running the core model as a library with the `run_project` function, the `output_file_run_name` parameter may be
used to replace the `__core__` identifier with a custom identifier, which will be wrapped in `__` in the output file
names.


# Contribute
HEM is currently not at a stage where we are in a position to accept external contributions
to the codebase.

# Developer documentation
Developer documentation can be found in [DEVELOPING.md](DEVELOPING.md).

# Licence
This software is available under the [MIT License](LICENCE.txt).

Contains public sector information licensed under the Open Government Licence v3.0. 
Example weather files derived from MIDAS Open data provided by the Met Office. 
For more information, see the [Open Government Licence](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
