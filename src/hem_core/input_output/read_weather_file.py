#!/usr/bin/env python3

"""
This module reads in an energy + weather file.
"""

import csv
import datetime
import io
import typing
from pathlib import Path
from typing import Any

import pandas as pd

import hem_core.units as units
from hem_core.external_conditions import create_external_conditions
from hem_core.simulation_time import SimulationTime

SOLAR_REFLECTIVITY_OF_GROUND = 0.2


def epw_weather_data_to_dict(weather_file: Path) -> dict:
    """Read EPW weather file, and return dictionary of external conditions."""

    # Column indices for the weather epw file
    column_longitude = 7
    column_latitude = 6
    column_air_temp = 6  # dry bulb temp in degrees
    column_wind_speed = 21  # wind speed in m/sec
    column_wind_direction = 20  # wind direction in degrees
    column_dni_rad = 14  # direct beam normal irradiation in Wh/m2
    column_dif_rad = 15  # diffuse irradiation (horizantal plane) in Wh/m2

    # column_ground_reflect = 32

    longitude: float | None = None
    latitude: float | None = None
    air_temperatures = []
    wind_speeds = []
    wind_directions = []
    diffuse_horizontal_radiation = []
    direct_beam_radiation = []
    ground_solar_reflc = []

    with open(weather_file) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=",")
        line_count = 0
        for row in csv_reader:
            if line_count == 0:
                longitude = float(row[column_longitude])
                latitude = float(row[column_latitude])
            elif line_count >= 8:
                air_temperatures.append(float(row[column_air_temp]))
                wind_speeds.append(float(row[column_wind_speed]))
                wind_directions.append(float(row[column_wind_direction]))
                direct_beam_radiation.append(float(row[column_dni_rad]))
                diffuse_horizontal_radiation.append(float(row[column_dif_rad]))
                ground_solar_reflc.append(SOLAR_REFLECTIVITY_OF_GROUND)
            line_count = line_count + 1

    external_conditions = {
        "air_temperatures": air_temperatures,
        "wind_speeds": wind_speeds,
        "wind_directions": wind_directions,
        "direct_beam_radiation": direct_beam_radiation,
        "diffuse_horizontal_radiation": diffuse_horizontal_radiation,
        "solar_reflectivity_of_ground": ground_solar_reflc,
        "longitude": longitude,
        "latitude": latitude,
        # Conversion is not needed as direct irradiation will be normal plane from this file
        "direct_beam_conversion_needed": False,
    }

    validate_weather_data(weather_data=external_conditions)
    return external_conditions


def cibse_weather_data_to_dict(weather_file: Path) -> dict:
    """Read a CIBSE weather file in CSV format, and return dictionary of external conditions."""

    # Column indices for the CIBSE weather file
    column_longitude = 3
    column_latitude = 1
    column_air_temp = 6  # dry bulb temp in degrees
    column_wind_speed = 11  # in knots
    column_wind_direction = 10  # in degrees
    column_ghi_rad = 12  # global irradiation (horizantal plane) in Wh/m2
    # COLUMN_DNI_RAD = # direct beam normal irradiation in Wh/m2 NOT IN FILE
    # COLUMN_DIR_RAD = # direct beam (horizontal plane) irradiation in Wh/m2 NOT IN FILE
    column_dif_rad = 13  # diffuse irradiation (horizantal plane) in Wh/m2
    # COLUMN_GROUND_REFLECT = # NOT IN FILE. Using 0.2 default

    air_temperatures = []
    wind_speeds = []
    wind_directions = []
    diff_hor_rad = []
    dir_beam_rad = []
    ground_solar_reflc = []
    longitude = 0
    latitude = 0

    with open(weather_file) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=",")
        line_count = 0
        for row in csv_reader:
            if line_count == 5:
                longitude = float(row[column_longitude])
                latitude = float(row[column_latitude])
            elif line_count >= 32:
                air_temperatures.append(float(row[column_air_temp]))
                wind_speeds.append(float(row[column_wind_speed]) / units.knots_per_m_per_sec)
                wind_directions.append(float(row[column_wind_direction]))  # CHECK ORDER
                # no DNI direct irradiation in file need to extract from global and diffuse values
                global_horiz_irr = float(row[column_ghi_rad])
                diffuse_horiz_irr = float(row[column_dif_rad])
                dir_beam_rad.append(global_horiz_irr - diffuse_horiz_irr)
                diff_hor_rad.append(float(row[column_dif_rad]))
                ground_solar_reflc.append(SOLAR_REFLECTIVITY_OF_GROUND)
            line_count = line_count + 1

    external_conditions = {
        "air_temperatures": air_temperatures,
        "wind_speeds": wind_speeds,
        "wind_directions": wind_directions,
        "diffuse_horizontal_radiation": diff_hor_rad,
        "direct_beam_radiation": dir_beam_rad,
        "solar_reflectivity_of_ground": ground_solar_reflc,
        "longitude": longitude,
        "latitude": latitude,
        # Conversion is needed as direct irradiation will be horizontal not normal from this file
        "direct_beam_conversion_needed": True,
    }

    validate_weather_data(weather_data=external_conditions)
    return external_conditions


def cibse_weather_data_to_epw(weather_filename: Path) -> str:
    """Read a CIBSE weather file in CSV format and convert to EPW."""

    external_conditions_dict = cibse_weather_data_to_dict(weather_filename)
    cibse_misc_data = _get_cibse_file_misc_data(weather_filename)
    year = cibse_misc_data["year"]
    start_day = datetime.datetime(year, 1, 1).strftime("%A")

    simulation_time = SimulationTime(
        start_time=0,
        end_time=8760,
        step=1,
    )
    external_conditions = create_external_conditions(
        external_conditions=external_conditions_dict,
        simtime=simulation_time,
    )

    # Calculate the normalised the irradiation from the CIBSE external conditions data.
    direct_beam_radiation = []
    for _ in simulation_time:
        direct_beam_radiation.append(external_conditions.direct_beam_radiation())

    epw_metadata = f"""LOCATION,unknown,-,United Kingdom,unknown,unknown,{external_conditions_dict["latitude"]:.6f},{external_conditions_dict["longitude"]:.6f},0.0,{cibse_misc_data["elevation"]}
DESIGN CONDITIONS,0
TYPICAL/EXTREME PERIODS,0
GROUND TEMPERATURES,0
HOLIDAYS/DAYLIGHT SAVING,No,0,0,0
COMMENTS 1,
COMMENTS 2,
DATA PERIODS,1,1,Data,{start_day},1/1,12/31
"""
    date_time = pd.date_range(
        f"{year}-01-01 00:00", f"{year}-12-31 23:59", freq="h", inclusive="left"
    )

    epw_weather_data = pd.DataFrame(
        {
            "year": date_time.year,  # type: ignore[AttributeAccessIssue]
            "month": date_time.month,  # type: ignore[AttributeAccessIssue]
            "day": date_time.day,  # type: ignore[AttributeAccessIssue]
            "hour": date_time.hour + 1,  # type: ignore[AttributeAccessIssue] # EPW starts with 1:00 but CSV starts at 0:00
            "minute": date_time.minute,  # type: ignore[AttributeAccessIssue]
            "data_source_unct": "",  # not known from CIBSE
            "temp_air": external_conditions_dict["air_temperatures"],
            "temp_dew": "",
            "relative_humidity": "",
            "atmospheric_pressure": "",
            "etr": "",  # extraterrestrial horizontal radiation
            "etrn": "",  # extraterrestrial direct normal radiation
            "ghi_infrared": "",  # horizontal infrared radiation intensity
            "ghi": "",
            "dni": direct_beam_radiation,
            "dhi": external_conditions_dict["diffuse_horizontal_radiation"],
            "global_hor_illum": "",
            "direct_normal_illum": "",
            "diffuse_horizontal_illum": "",
            "zenith_luminance": "",
            "wind_direction": external_conditions_dict["wind_directions"],
            "wind_speed": external_conditions_dict["wind_speeds"],
            "total_sky_cover": "",
            "opaque_sky_cover": "",
            "visibility": "",
            "ceiling_height": "",
            "present_weather_observation": "",
            "present_weather_codes": "",
            "precipitable_water": "",
            "aerosol_optical_depth": "",
            "snow_depth": "",
            "days_since_last_snowfall": "",
            "albedo": external_conditions_dict["solar_reflectivity_of_ground"],
            "liquid_precipitation_depth": "",
            "liquid_precipitation_quantity": "",
        }
    )

    epw_data = io.StringIO()
    epw_data.write(epw_metadata)
    epw_weather_data.to_csv(epw_data, mode="a", header=False, index=False)

    return epw_data.getvalue()


def _get_cibse_file_misc_data(weather_filename: Path) -> dict:
    """
    Get other data and metadata from the CIBSE CSV file
    that are not necessary under ExternalConditions.
    """
    misc_data = {}

    column_year = 0
    column_elevation = 5
    with open(weather_filename) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=",")
        line_count = 0
        for row in csv_reader:
            if line_count == 5:
                misc_data["elevation"] = float(row[column_elevation])
            elif line_count == 32:
                misc_data["year"] = int(row[column_year])

            line_count = line_count + 1

    return misc_data


def validate_weather_data(weather_data: dict[str, Any]):
    for key in [
        "air_temperatures",
        "diffuse_horizontal_radiation",
        "direct_beam_radiation",
        "solar_reflectivity_of_ground",
        "wind_speeds",
        "wind_directions",
    ]:
        values = weather_data.get(key)
        if typing.TYPE_CHECKING:
            assert isinstance(values, list)
        # Data series must always have 8760 entries as some parts of the calculation rely on annual averages
        if len(values) != 8760:
            raise ValueError(f"ExternalConditions {key} should contain 8760 values.")
