#!/usr/bin/env python3

"""
This module contains data on the energy tariffs
"""

import csv
import os
from pathlib import Path


class TariffData:
    def __init__(self, relative_path: Path):
        """Construct a TariffData object."""
        self.__tariff_data_file_csv = os.path.normpath(relative_path)

        self.__tariff_mapping = self.__create_tariff_mapping()
        self.__elec_prices = self.__load_prices()

    def __create_tariff_mapping(self) -> dict[str, int]:
        """Create a mapping of tariff names to columns."""
        with open(self.__tariff_data_file_csv, "r") as elec_prices_csv:
            reader = csv.reader(elec_prices_csv)
            headers = next(reader)
            tariff_mapping = {header: idx for idx, header in enumerate(headers)}
        return tariff_mapping

    def __load_prices(self) -> dict[int, dict[str, float]]:
        """Load electricity prices from data file into a dictionary."""
        elec_prices = {}
        with open(self.__tariff_data_file_csv, "r") as elec_prices_csv:
            elec_prices_reader = csv.DictReader(elec_prices_csv, delimiter=",")
            for row in elec_prices_reader:
                timestep = int(row["timestep"])  # Convert timestep to integer for better indexing
                elec_prices[timestep] = {
                    tariff: float(row[tariff]) for tariff in row if tariff != "timestep"
                }
        return elec_prices

    def get_price(self, tariff_name: str, t_idx: int) -> float:
        if tariff_name in self.__tariff_mapping:
            return self.__elec_prices[t_idx][tariff_name]
            # TODO Current solution is based on tariff data file that has at least as many timesteps (whatever length)
            #      as the simtime object in the json file. This will need to be revisited when tariffs move to
            #      PCDB and its processing is integrated alongside other database objects.
        else:
            raise ValueError(f"Tariff ({tariff_name}) not found")
