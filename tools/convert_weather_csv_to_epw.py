import argparse
import csv
import sys
from pathlib import Path

from hem_core.input_output.read_weather_file import cibse_weather_data_to_epw


def main(args: list[str] | None = None):
    parser = argparse.ArgumentParser(
        description="Convert a CIBSE CSV file to EPW format. Saves the EPW file in the same directory as the input file by default."
    )
    parser.add_argument(
        "--CIBSE-weather-file", required=True, help="Path to CIBSE weather file in CSV format."
    )
    parser.add_argument("-o", "--output", help="Output file destination of the converted EPW file.")
    arguments = parser.parse_args(args)

    epw_filename = Path(arguments.CIBSE_weather_file).with_suffix(".epw")
    if arguments.output is not None:
        epw_filename = arguments.output

    epw_data = cibse_weather_data_to_epw(arguments.CIBSE_weather_file)
    reader = csv.reader(epw_data.splitlines(), skipinitialspace=True)
    with open(epw_filename, "w") as f:
        writer = csv.writer(f)
        writer.writerows(reader)


if __name__ == "__main__":
    sys.exit(main())
