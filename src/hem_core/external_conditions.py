#!/usr/bin/env python3

"""
This module provides object(s) to store and look up data on external conditions
(e.g. external air temperature)

Calculation of solar radiation on a surface of a given orientation and tilt is
based on BS EN ISO 52010-1:2017.
"""

import time
from copy import deepcopy
from itertools import product
from math import acos, asin, atan, atan2, cos, degrees, floor, fsum, pi, radians, sin, sqrt, tan
from typing import Any

import numpy as np

import hem_core.units as units
from hem_core.input_output.enums import ShadingObjectType, WindowShadingType
from hem_core.simulation_time import SimulationTime
from hem_core.units import Orientation360


class ExternalConditions:
    """An object to store and look up data on external conditions"""

    def __init__(
        self,
        simulation_time: SimulationTime,
        air_temps: list[float],
        wind_speeds: list[float],
        wind_directions: list[Orientation360],
        diffuse_horizontal_radiation: list[float],
        direct_beam_radiation: list[float],
        solar_reflectivity_of_ground: list[float],
        latitude: float,
        longitude: float,
        timezone: int,
        start_day: int,
        end_day: int,
        time_series_step: float,
        january_first: int | None,
        daylight_savings: str | None,
        leap_day_included: bool | None,
        direct_beam_conversion_needed: bool,
        shading_segments: list[dict[str, Any]] | None = None,
    ):
        """Construct an ExternalConditions object

        Arguments:
        simulation_time -- reference to SimulationTime object
        air_temps       -- list of external air temperatures, in deg C (one entry per hour)
        wind_speeds     -- list of wind speeds, in m/s (one entry per hour)
        wind_directions -- list of wind directions in degrees where North=0, East=90,
                            South=180, West=270. Values range: 0 to 360.
                            Wind direction is reported by the direction from which it originates.
                            E.g, a southerly (180 degree) wind blows from the south to the north.
        diffuse_horizontal_radiation    -- list of diffuse horizontal radiation values, in W/m2 (one entry per hour)
        direct_beam_radiation           -- list of direct beam radiation values, in W/m2 (one entry per hour)
        solar_reflectivity_of_ground    -- list of ground reflectivity values, 0 to 1 (one entry per hour)
        latitude        -- latitude of weather station, angle from south, in degrees (single value)
        longitude       -- longitude of weather station, easterly +ve westerly -ve, in degrees (single value)
        timezone        -- timezone of weather station, -12 to 12 (single value)
        start_day       -- first day of the time series, day of the year, 0 to 365 (single value)
        end_day         -- last day of the time series, day of the year, 0 to 365 (single value)
        time_series_step -- timestep of the time series data, in hours
        january_first   -- day of the week for January 1st, monday to sunday, 1 to 7 (single value)
        daylight_savings    -- handling of daylight savings time, (single value)
                            e.g. applicable and taken into account,
                            applicable but not taken into account,
                            not applicable
        leap_day_included   -- whether climate data includes a leap day, true or false (single value)
        direct_beam_conversion_needed -- A flag to indicate whether direct beam radiation from climate data needs to be
                                        converted from horizontal to normal incidence. If normal direct beam radiation
                                        values are provided then no conversion is needed.
        shading_segments -- data splitting the ground plane into segments (8-36) and giving height
                            and distance to shading objects surrounding the building
        """

        self.__simulation_time = simulation_time
        self.__air_temps = air_temps
        self.__wind_speeds = wind_speeds
        self.__wind_directions = wind_directions
        self.__solar_reflectivity_of_ground = solar_reflectivity_of_ground
        self.__latitude = latitude  # practical  range -90 to +90
        self.__longitude = longitude  # practical range -180 to +180
        self.__timezone = timezone
        self.__start_day = start_day
        self.__end_day = end_day
        self.__january_first = january_first
        self.__daylight_savings = daylight_savings
        self.__leap_day_included = leap_day_included
        self.__direct_beam_conversion_needed = direct_beam_conversion_needed
        self.__shading_segments = shading_segments
        self.__time_series_step = time_series_step
        # Initialise results cache (to improve performance)
        self.__cached_results = {}
        self.__cached_timestep = None

        days_in_year = 366 if leap_day_included else 365
        hours_in_year = days_in_year * 24
        time_shift = self.__init_time_shift()

        # Calculate earth orbit deviation for each day of year
        earth_orbit_deviation = [
            self.__init_earth_orbit_deviation(current_day=current_day)
            for current_day in range(0, days_in_year)
        ]
        # Calculate extra terrestrial radiation
        self.__extra_terrestrial_radiation = [
            self.__init_extra_terrestrial_radiation(
                earth_orbit_deviation=earth_orbit_deviation[current_day]
            )
            for current_day in range(0, days_in_year)
        ]
        # Calculate solar declination for each day of year
        self.__solar_declination = [
            self.__init_solar_declination(earth_orbit_deviation=earth_orbit_deviation[current_day])
            for current_day in range(0, days_in_year)
        ]
        # Calculate equation of time for each day of year
        equation_of_time = [
            self.__init_equation_of_time(current_day=current_day)
            for current_day in range(0, days_in_year)
        ]
        # Calculate solar time for each hour of year
        self.__solar_time = [
            self.__init_solar_time(
                hour_of_day=floor(current_hour % 24),
                equation_of_time=equation_of_time[floor(current_hour / 24)],
                time_shift=time_shift,
            )
            for current_hour in range(0, hours_in_year)
        ]
        # Calculate solar hour angle for each hour of year
        self.__solar_hour_angle = [
            self.__init_solar_hour_angle(solar_time=self.__solar_time[current_hour])
            for current_hour in range(0, hours_in_year)
        ]
        # Calculate solar altitude for each hour of year
        self.__solar_altitude = [
            self.__init_solar_altitude(
                solar_declination=self.__solar_declination[floor(current_hour / 24)],
                solar_hour_angle=self.__solar_hour_angle[current_hour],
            )
            for current_hour in range(0, hours_in_year)
        ]
        # Calculate solar zenith angle for each hour of year
        self.__solar_zenith_angle = [
            self.__init_solar_zenith_angle(solar_altitude=self.__solar_altitude[current_hour])
            for current_hour in range(0, hours_in_year)
        ]
        # Calculate solar azimuth angle for each hour of year
        self.__solar_azimuth_angle = [
            self.__init_solar_azimuth_angle(
                solar_declination=self.__solar_declination[floor(current_hour / 24)],
                solar_hour_angle=self.__solar_hour_angle[current_hour],
                solar_altitude=self.__solar_altitude[current_hour],
            )
            for current_hour in range(0, hours_in_year)
        ]
        # Calculate air mass for each hour of year
        self.__air_mass = [
            self.__init_air_mass(solar_altitude=self.__solar_altitude[current_hour])
            for current_hour in range(0, hours_in_year)
        ]

        # Calculate direct beam radiation for each timestep
        simtime = deepcopy(self.__simulation_time)
        self.__direct_beam_radiation = [
            self.__init_direct_beam_radiation(
                raw_value=direct_beam_radiation[
                    simtime.time_series_idx(
                        start_day=self.__start_day, time_series_step=self.__time_series_step
                    )
                ],
                solar_altitude=self.__solar_altitude[simtime.current_hour()],
            )
            for _, _, _ in simtime
        ]
        # Calculate diffuse horizontal radiation for each timestep
        simtime = deepcopy(self.__simulation_time)
        self.__diffuse_horizontal_radiation = [
            diffuse_horizontal_radiation[
                simtime.time_series_idx(
                    start_day=self.__start_day, time_series_step=self.__time_series_step
                )
            ]
            for _, _, _ in simtime
        ]
        # Calculate dimensionless clearness parameter for each timestep
        simtime = deepcopy(self.__simulation_time)
        self.__dimensionless_clearness_parameter = [
            self.__init_dimensionless_clearness_parameter(
                diffuse_horizontal_radiation=self.__diffuse_horizontal_radiation[t_idx],
                direct_beam_radiation=self.__direct_beam_radiation[t_idx],
                solar_altitude=self.__solar_altitude[simtime.current_hour()],
            )
            for t_idx, _, _ in simtime
        ]
        # Calculate dimensionless sky brightness parameter for each timestep
        simtime = deepcopy(self.__simulation_time)
        self.__dimensionless_sky_brightness_parameter = [
            self.__init_dimensionless_sky_brightness_parameter(
                air_mass=self.__air_mass[simtime.current_hour()],
                diffuse_horizontal_radiation=self.__diffuse_horizontal_radiation[t_idx],
                extra_terrestrial_radiation=self.__extra_terrestrial_radiation[
                    simtime.current_day()
                ],
            )
            for t_idx, _, _ in simtime
        ]
        # Calculate circumsolar brightness coefficient, F1 for each timestep
        simtime = deepcopy(self.__simulation_time)
        self.__F1 = [
            self.__init_F1(
                clearness_parameter=self.__dimensionless_clearness_parameter[t_idx],
                delta=self.__dimensionless_sky_brightness_parameter[t_idx],
                solar_zenith_angle=self.__solar_zenith_angle[simtime.current_hour()],
            )
            for t_idx, _, _ in simtime
        ]
        # Calculate horizontal brightness coefficient, F2 for each timestep
        simtime = deepcopy(self.__simulation_time)
        self.__F2 = [
            self.__init_F2(
                clearness_parameter=self.__dimensionless_clearness_parameter[t_idx],
                delta=self.__dimensionless_sky_brightness_parameter[t_idx],
                solar_zenith_angle=self.__solar_zenith_angle[simtime.current_hour()],
            )
            for t_idx, _, _ in simtime
        ]

    @property
    def direct_beam_conversion_needed(self) -> bool:
        return self.__direct_beam_conversion_needed

    @property
    def latitude(self) -> float:
        return self.__latitude

    @property
    def longitude(self) -> float:
        return self.__longitude

    @property
    def timezone(self) -> int:
        return self.__timezone

    @property
    def start_day(self) -> int:
        return self.__start_day
        # TODO possibly this input sits better within simulation_time
        # but included here until final form decided
        # currently used as the current day value

    @property
    def end_day(self) -> int:
        return self.__end_day
        # TODO possibly this input sits better within simulation_time
        # but included here until final form decided
        # not current used

    @property
    def january_first(self) -> int | None:
        return self.__january_first
        # TODO possibly this input sits better within simulation_time
        # but included here until final form decided
        # not current used

    @property
    def daylight_savings(self) -> str | None:
        return self.__daylight_savings
        # TODO possibly this input sits better within simulation_time
        # but included here until final form decided
        # currently unclear whether this is reffering to a choice by the user
        # or a statement of the contents of the weather data file
        # not current used

    @property
    def leap_day_included(self) -> bool | None:
        return self.__leap_day_included
        # TODO possibly this input sits better within simulation_time
        # but included here until final form decided
        # currently unclear whether this is reffering to a choice by the user
        # or a statement of the contents of the weather data file
        # not current used

    def testoutput_setup(self, tilt: float, orientation: float) -> None:
        """print output to a file for analysis"""

        # call this function once at the start of the calculation to test outputs
        readable = time.ctime()
        with open("test_sunpath.txt", "a") as o:
            o.write("\n")
            o.write("\n")
            o.write("*****************")
            o.write("\n")
            o.write(readable)
            o.write("\n")
            o.write("latitude " + str(self.latitude))
            o.write("\n")
            o.write("longitude " + str(self.longitude))
            o.write("\n")
            o.write("day of year " + str(self.start_day))
            o.write("\n")
            o.write("surface tilt " + str(tilt))
            o.write("\n")
            o.write("surface orientation " + str(orientation))
            o.write("\n")
            o.write(
                "sim hour,solar time,s declination,s hour angle,s altitude,s azimuth,air mass,sun surface azimuth,direct irad,solar angle of incidence,ET irad,F1,F2,E,delta,a over b,diffuse irad,ground reflect irad,circumsolar,final diffuse,final direct"
            )

    def testoutput(self, tilt: float, orientation: Orientation360) -> None:
        """print output to a file for analysis"""

        # call this function once during every timestep to test outputs
        current_timestep = self.__simulation_time.index()
        current_hour = self.__simulation_time.current_hour()
        current_day = self.__simulation_time.current_day()

        # write headers
        with open("test_sunpath.txt", "a") as o:
            o.write("\n")
            o.write(str(self.__simulation_time.hour_of_day()))
            o.write(",")
            o.write(str(self.__solar_time[current_hour]))
            o.write(",")
            o.write(str(self.__solar_declination[current_day]))
            o.write(",")
            o.write(str(self.__solar_hour_angle[current_hour]))
            o.write(",")
            o.write(str(self.__solar_altitude[current_hour]))
            o.write(",")
            o.write(str(self.__solar_azimuth_angle[current_hour]))
            o.write(",")
            o.write(str(self.__air_mass[current_hour]))
            o.write(",")
            o.write(str(self.sun_surface_azimuth(orientation=orientation)))
            o.write(",")
            o.write(str(self.direct_irradiance(tilt=tilt, orientation=orientation)))
            o.write(",")
            o.write(str(self.solar_angle_of_incidence(tilt=tilt, orientation=orientation)))
            o.write(",")
            o.write(str(self.__extra_terrestrial_radiation[current_day]))
            o.write(",")
            o.write(str(self.__F1[current_timestep]))
            o.write(",")
            o.write(str(self.__F2[current_timestep]))
            o.write(",")
            o.write(str(self.__dimensionless_clearness_parameter[current_timestep]))
            o.write(",")
            o.write(str(self.__dimensionless_sky_brightness_parameter[current_timestep]))
            o.write(",")
            o.write(str(self.a_over_b(tilt=tilt, orientation=orientation)))
            o.write(",")
            o.write(str(self.diffuse_irradiance(tilt=tilt, orientation=orientation)[0]))
            o.write(",")
            o.write(str(self.ground_reflection_irradiance(tilt=tilt)))
            o.write(",")
            o.write(str(self.circumsolar_irradiance(tilt=tilt, orientation=orientation)))
            o.write(",")
            o.write(str(self.calculated_diffuse_irradiance(tilt=tilt, orientation=orientation)))
            o.write(",")
            o.write(str(self.calculated_direct_irradiance(tilt=tilt, orientation=orientation)))

    def air_temp(self, idx_offset: int = 0) -> float:
        """Return the external air temperature for the current timestep"""
        idx = (
            self.__simulation_time.time_series_idx(
                start_day=self.__start_day, time_series_step=self.__time_series_step
            )
            + idx_offset
        )
        if idx >= len(self.__air_temps):
            idx = idx - len(self.__air_temps)
        return self.__air_temps[idx]

    def air_temp_annual(self) -> float:
        """Return the average air temperature for the year"""
        assert len(self.__air_temps) == 8760  # Only works if data for whole year has been provided
        return fsum(self.__air_temps) / len(self.__air_temps)

    def air_temp_monthly(self) -> float:
        """Return the average air temperature for the current month"""
        # Get start and end hours for current month
        idx_start, idx_end = self.__simulation_time.current_month_start_end_hour()
        # Get air temperatures for the current month
        air_temps_month = self.__air_temps[idx_start:idx_end]

        return fsum(air_temps_month) / len(air_temps_month)

    def air_temp_annual_daily_average_min(self) -> float:
        """Return the minimum daily average air temperature for the whole year"""
        assert len(self.__air_temps) == 8760  # Only works if data for whole year has been provided
        # Determine the air temperatures for each day
        no_of_days = len(self.__air_temps) // units.hours_per_day
        daily_averages = []
        for i in range(no_of_days):
            daily_averages.append(
                np.average(
                    self.__air_temps[i * units.hours_per_day : (i + 1) * units.hours_per_day]
                )
            )
        return min(daily_averages)

    def wind_speed(self) -> float:
        """Return the wind speed for the current timestep"""
        return self.__wind_speeds[
            self.__simulation_time.time_series_idx(
                start_day=self.__start_day, time_series_step=self.__time_series_step
            )
        ]

    def wind_speed_annual(self) -> float:
        """Return the average wind speed for the year"""
        # Only works if data for whole year has been provided, so assert this is true
        assert (
            len(self.__wind_speeds)
            == units.hours_per_day * units.days_per_year / self.__time_series_step
        )
        return fsum(self.__wind_speeds) / len(self.__wind_speeds)

    def wind_direction(self) -> Orientation360:
        """Return the wind direction for the current timestep"""
        return self.__wind_directions[
            self.__simulation_time.time_series_idx(
                start_day=self.__start_day, time_series_step=self.__time_series_step
            )
        ]

    def wind_direction_annual(self) -> Orientation360:
        """Return the average wind direction for the whole year"""
        assert (
            len(self.__wind_speeds) == len(self.__wind_directions) == 8760
        )  # Only works if data for whole year has been provided
        x_total = y_total = 0
        for wind_speed, wind_direction in zip(
            self.__wind_speeds, self.__wind_directions, strict=False
        ):
            x_total += wind_speed * cos(radians(wind_direction.angle))
            y_total += wind_speed * sin(radians(wind_direction.angle))
        # Take average of x and y for each timestep and then convert back to angle:
        x_average = x_total / len(self.__wind_directions)
        y_average = y_total / len(self.__wind_directions)
        wind_direction_average = degrees(atan2(y_average, x_average))
        return Orientation360(wind_direction_average % 360)

    def diffuse_horizontal_radiation(self) -> float:
        """Return the diffuse_horizontal_radiation for the current timestep"""
        return self.__diffuse_horizontal_radiation[self.__simulation_time.index()]

    def direct_beam_radiation(self) -> float:
        """Return the direct_beam_radiation for the current timestep"""
        return self.__direct_beam_radiation[self.__simulation_time.index()]

    def __init_direct_beam_radiation(self, raw_value: float, solar_altitude: float) -> float:
        # if the climate data to only provide direct horizontal (rather than normal:
        # If only direct (beam) solar irradiance at horizontal plane is available in the climatic data set,
        # it shall be converted to normal incidence by dividing the value by the sine of the solar altitude.
        """ISO 52010 section 6.4.2
        TODO investigate the impact of these notes further. Applicable for weather from CIBSE file.
        NOTE 1 If the solar altitude angle is low, this conversion is very sensative for tiny
        errors in the calculation of the solar altitude. Such tiny errors are feasible given the
        sensitivity for the parameters needed to calculate the solar angle and given the atmospheric
        refraction of solar radiation near the ground. there fore the value at normal incidence is
        preferred.
        NOTE 2 method 1 proved to be most effective in mid-latitude climates
        other models might be more suitable for tropical climates.
        NOTE 3 if the solar altitude angle is low, the conversion from direct horizontal to direct
        normal beam irradiance is very sensative for tiny errors in the calculation of the
        solar altitude."""
        if self.__direct_beam_conversion_needed:
            sin_asol = sin(radians(solar_altitude))
            # prevent division by zero error. if sin_asol = 0 then the sun is lower than the
            # horizon and there will be no direct radiation to convert
            if sin_asol > 0:
                direct_beam_radiation = raw_value / sin_asol
            else:
                direct_beam_radiation = raw_value  # TODO should this be zero?
        else:
            direct_beam_radiation = raw_value

        return direct_beam_radiation

    def solar_reflectivity_of_ground(self) -> float:
        """Return the solar_reflectivity_of_ground for the current timestep"""
        return self.__solar_reflectivity_of_ground[
            self.__simulation_time.time_series_idx(
                start_day=self.__start_day, time_series_step=self.__time_series_step
            )
        ]

    def __init_earth_orbit_deviation(self, current_day: int) -> float:
        """Calculate the earth orbit deviation (Rdc), as a function of the day, in degrees"""

        nday = current_day + 1
        # nday is the day of the year, from 1 to 365 or 366 (leap year)
        # Note that current_day function returns days numbered 0 to 364 or 365,
        # so we need to add 1 above

        rdc = (360 / 365) * nday

        return rdc

    def __init_solar_declination(self, earth_orbit_deviation: float) -> float:
        """Calculate solar declination in degrees"""

        rdc = radians(earth_orbit_deviation)
        # note we convert to radians for the python cos & sin inputs in formula below

        solar_declination = (
            0.33281
            - 22.984 * cos(rdc)
            - 0.3499 * cos(2 * rdc)
            - 0.1398 * cos(3 * rdc)
            + 3.7872 * sin(rdc)
            + 0.03205 * sin(2 * rdc)
            + 0.07187 * sin(3 * rdc)
        )

        return solar_declination

    def __init_equation_of_time(self, current_day: int) -> float:
        """Calculate the equation of time"""

        """ 
        teq is the equation of time, in minutes;
        nday is the day of the year, from 1 to 365 or 366 (leap year)
        """

        nday = current_day + 1
        # nday is the day of the year, from 1 to 365 or 366 (leap year)
        # Note that current_day function returns days numbered 0 to 364 or 365,
        # so we need to add 1 here

        # note we convert the values inside the cos() to radians for the python function
        # even though the 180 / pi is converting from radians into degrees
        # this way the formula remains consistent with as written in the ISO document

        if nday < 21:
            teq = 2.6 + 0.44 * nday
        elif nday < 136:
            teq = 5.2 + 9.0 * cos((nday - 43) * 0.0357)
        elif nday < 241:
            teq = 1.4 - 5.0 * cos((nday - 135) * 0.0449)
        elif nday < 336:
            teq = -6.3 - 10.0 * cos((nday - 306) * 0.036)
        elif nday <= 366:
            teq = 0.45 * (nday - 359)
        else:
            raise ValueError(f"Invalid day of the year: {str(nday)}.")

        return teq

    def __init_time_shift(self) -> float:
        """Calculate the time shift, in hours, resulting from the fact that the
        longitude and the path of the sun are not equal

        NOTE Daylight saving time is disregarded in tshift which is time independent
        """

        tshift = self.timezone - self.longitude / 15
        return tshift

    def __init_solar_time(
        self, hour_of_day: int, equation_of_time: float, time_shift: float
    ) -> float:
        """Calculate the solar time, tsol, as a function of the equation of time,
        the time shift and the hour of the day"""

        """ 
        solar time, in h
        nhour is the actual (clock) time for the location, the hour of the day, in h
        """
        nhour = hour_of_day + 1
        # note we +1 here because the simulation hour of day starts at 0
        # while the sun path standard hour of day starts at 1 (hour 0 to 1)
        solar_time = nhour - (equation_of_time / 60) - time_shift

        return solar_time

    def __init_solar_hour_angle(self, solar_time: float) -> float:
        """Calculate the solar hour angle (in degrees), in the middle of the
        current hour as a function of the solar time"""

        # TODO How is this to be adjusted for timesteps that are not hourly?
        # would allowing solar_time to be a decimal be all that is needed?

        """ 
        Notes from ISO 52020 6.4.1.5
        NOTE 1 The limitation of angles ranging between -180 and +180 degrees is 
        needed to determine which shading objects are in the direction of the sun; 
        see also the calculation of the azimuth angle of the sun in 6.4.1.7.
        NOTE 2 Explanation of "12.5": The hour numbers are actually hour sections: 
        the first hour section of a day runs from 0h to 1h. So, the average position 
        of the sun for the solar radiation measured during (solar) hour section N is 
        at (solar) time = (N -0,5) h of the (solar) day.
        """

        solar_angle = (180 / 12) * (12.5 - solar_time)

        if solar_angle > 180:
            solar_angle = solar_angle - 360
        elif solar_angle < -180:
            solar_angle = solar_angle + 360

        return solar_angle

    def __init_solar_altitude(self, solar_declination: float, solar_hour_angle: float) -> float:
        """the angle between the solar beam and the horizontal surface, determined
        in the middle of the current hour as a function of the solar hour angle,
        the solar declination and the latitude"""

        # TODO How is this to be adjusted for timesteps that are not hourly?
        # would allowing solar_time to be a decimal be all that is needed?

        """ 
        The solar altitude angle is the angle between the solar beam 
        and the horizontal surface, in degrees;
        """

        # note that we convert to radians for the sin & cos python functions and then
        # we need to convert the result back to degrees after the arcsin transformation

        solar_altitude_angle = asin(
            sin(radians(solar_declination)) * sin(radians(self.latitude))
            + cos(radians(solar_declination))
            * cos(radians(self.latitude))
            * cos(radians(solar_hour_angle))
        )

        if degrees(solar_altitude_angle) < 0.0001:
            return 0

        return degrees(solar_altitude_angle)

    def __init_solar_zenith_angle(self, solar_altitude: float) -> float:
        """the complementary angle of the solar altitude"""

        zenith = 90 - solar_altitude

        return zenith

    def __init_solar_azimuth_angle(
        self, solar_declination: float, solar_hour_angle: float, solar_altitude: float
    ) -> float:
        """calculates the solar azimuth angle,
        angle from South, eastwards positive, westwards negative, in degrees"""

        """
        NOTE The azimuth angles range between −180 and +180 degrees; this is needed to determine which shading 
        objects are in the direction of the sun
        """

        sin_aux1_numerator = cos(radians(solar_declination)) * sin(radians(180 - solar_hour_angle))

        cos_aux1_numerator = cos(radians(self.latitude)) * sin(radians(solar_declination)) + sin(
            radians(self.latitude)
        ) * cos(radians(solar_declination)) * cos(radians(180 - solar_hour_angle))

        denominator = cos(asin(sin(radians(solar_altitude))))

        sin_aux1 = sin_aux1_numerator / denominator
        cos_aux1 = cos_aux1_numerator / denominator
        aux2 = degrees(asin(sin_aux1_numerator) / denominator)

        # BS EN ISO 52010-1:2017. Formula 16
        if sin_aux1 >= 0 and cos_aux1 > 0:
            solar_azimuth = 180 - aux2
            if solar_azimuth < 0:
                solar_azimuth = -solar_azimuth
        elif cos_aux1 < 0:
            solar_azimuth = aux2
        else:
            solar_azimuth = -(180 + aux2)

        return solar_azimuth

    def __init_air_mass(self, solar_altitude: float) -> float:
        """calculates the air mass, m, the distance the solar beam travels through the earth atmosphere.
        The air mass is determined as a function of the sine of the solar altitude angle"""

        if solar_altitude >= 10:
            air_mass = 1 / sin(radians(solar_altitude))
        else:
            air_mass = 1 / (
                sin(radians(solar_altitude)) + 0.15 * (solar_altitude + 3.885) ** -1.253
            )

        return air_mass

    def solar_angle_of_incidence(self, tilt: float, orientation: Orientation360) -> float:
        """calculates the solar angle of incidence, which is the angle of incidence of the
        solar beam on an inclined surface and is determined as function of the solar hour angle
        and solar declination

        Arguments:
        tilt           -- is the tilt angle of the inclined surface from horizontal, measured
                          upwards facing, 0 to 180, in degrees;
        orientation    -- is the orientation angle of the inclined surface, expressed as the
                          geographical azimuth angle of the horizontal projection of the inclined
                          surface normal, 0 to 360, in degrees;
                          It will be converted to the -180 to 180 range;
                          Assumed N 180 or -180, E 90, S 0, W -90
        """

        orientation180 = orientation.transform_to_180()
        # set up the parameters first just to make the very long equation slightly more readable
        current_day = self.__simulation_time.current_day()
        solar_declination = self.__solar_declination[current_day]
        sin_declination = sin(radians(solar_declination))
        cos_declination = cos(radians(solar_declination))
        sin_lat = sin(radians(self.latitude))
        cos_lat = cos(radians(self.latitude))
        sin_tilt = sin(radians(tilt))
        cos_tilt = cos(radians(tilt))
        sin_orientation = sin(radians(orientation180))
        cos_orientation = cos(radians(orientation180))
        current_hour = self.__simulation_time.current_hour()
        solar_hour_angle = self.__solar_hour_angle[current_hour]
        sin_sha = sin(radians(solar_hour_angle))
        cos_sha = cos(radians(solar_hour_angle))

        solar_angle_of_incidence = acos(
            sin_declination * sin_lat * cos_tilt
            - sin_declination * cos_lat * sin_tilt * cos_orientation
            + cos_declination * cos_lat * cos_tilt * cos_sha
            + cos_declination * sin_lat * sin_tilt * cos_orientation * cos_sha
            + cos_declination * sin_tilt * sin_orientation * sin_sha
        )

        return degrees(solar_angle_of_incidence)

    def sun_surface_azimuth(self, orientation: Orientation360) -> float:
        """calculates the azimuth angle between sun and the inclined surface,
        needed as input for the calculation of the irradiance in case of solar shading by objects

        Arguments:

        orientation    -- is the orientation angle of the inclined surface, expressed as the
                          geographical azimuth angle of the horizontal projection of the inclined
                          surface normal, 0 to 360, in degrees;
                          It will be converted to the -180 to 180 range;
                          Assumed N 180 or -180, E 90, S 0, W -90

        """
        orientation180 = orientation.transform_to_180()
        current_hour = self.__simulation_time.current_hour()
        test_angle = self.__solar_hour_angle[current_hour] - orientation180

        if test_angle > 180:
            azimuth = -360 + test_angle
        elif test_angle < -180:
            azimuth = 360 + test_angle
        else:
            azimuth = test_angle

        return azimuth

    def sun_surface_tilt(self, tilt: float) -> float:
        """calculates the tilt angle between sun and the inclined surface,
        needed as input for the calculation of the irradiance in case of solar shading by objects

        Arguments:

        tilt           -- is the tilt angle of the inclined surface from horizontal, measured
                          upwards facing, 0 to 180, in degrees;

        """

        current_hour = self.__simulation_time.current_hour()
        test_angle = tilt - self.__solar_zenith_angle[current_hour]

        if test_angle > 180:
            sun_surface_tilt = -360 + test_angle
        elif test_angle < -180:
            sun_surface_tilt = 360 + test_angle
        else:
            sun_surface_tilt = test_angle

        return sun_surface_tilt

    # TODO section 6.4.2 of ISO 52010 is not implemented here as it relates to methods of
    # obtaiing the needed irradiance values if they are not available from the climatic dataset.
    # If we decide this might be useful later then my suggestion would be to implement this as a
    # preprocessing step so that the core calculation always recieves the 'correct' climate data.

    # TODO solar reflectivity of the ground is expected to be initially fixed at 0.2, as per the
    # default listed in ISO 52010 Annex B. However, the implementation here allows for one value
    # per time step so alternative methods can be used in the future. options include taking values
    # from a climatic dataset that contains them, basing the values on ground surface material,
    # or ground cover such as snow. This can be implemented in a preprocess rather than the core.

    def direct_irradiance(self, tilt: float, orientation: Orientation360) -> float:
        """calculates the direct irradiance on the inclined surface, determined as function
        of cosine of the solar angle of incidence and the direct normal (beam) solar irradiance
        NOTE The solar beam irradiance is defined as falling on an surface normal to the solar beam.
        This is not the same as direct horizontal radiation.

        Arguments:
        tilt           -- is the tilt angle of the inclined surface from horizontal, measured
                          upwards facing, 0 to 180, in degrees;
        orientation    -- is the orientation angle of the inclined surface, expressed as the
                          geographical azimuth angle of the horizontal projection of the inclined
                          surface normal, 0 to 360, in degrees;

        """

        direct_irradiance = max(
            0,
            self.direct_beam_radiation()
            * cos(radians(self.solar_angle_of_incidence(tilt=tilt, orientation=orientation))),
        )

        return direct_irradiance

    def __init_extra_terrestrial_radiation(self, earth_orbit_deviation: float) -> float:
        """calculates the extra terrestrial radiation, the normal irradiance out of the atmosphere
        as a function of the day

        """

        # NOTE the ISO 52010 has an error in this formula.
        # it lists Gsol,c as the solar angle of incidence on the inclined surface
        # when it should be the solar constant, given elsewhere as 1367
        # we use the correct version of the formula here

        extra_terrestrial_radiation = 1367 * (1 + 0.033 * cos(radians(earth_orbit_deviation)))

        return extra_terrestrial_radiation

    def brightness_coefficient(
        self, clearness_parameter: float, brightness_coefficient: str
    ) -> float:
        """returns brightness coefficient as a look up from Table 8 in ISO 52010

        Arguments:
        clearness_parameter, E      -- dimensionless clearness parameter
        brightness_coefficient, Fij -- the coefficient to be returned. e.g. f12 or f23
        """

        # TODO I've not had a need for the clearness index parameters contained in this table yet,
        # if they are needed as input or output later then this function can be reworked

        if clearness_parameter < 1.065:
            # overcast
            index = 1
        elif clearness_parameter < 1.23:
            index = 2
        elif clearness_parameter < 1.5:
            index = 3
        elif clearness_parameter < 1.95:
            index = 4
        elif clearness_parameter < 2.8:
            index = 5
        elif clearness_parameter < 4.5:
            index = 6
        elif clearness_parameter < 6.2:
            index = 7
        else:
            # clear
            index = 8

        brightness_coeff_dict = {
            1: {
                "f11": -0.008,
                "f12": 0.588,
                "f13": -0.062,
                "f21": -0.06,
                "f22": 0.072,
                "f23": -0.022,
            },
            2: {
                "f11": 0.13,
                "f12": 0.683,
                "f13": -0.151,
                "f21": -0.019,
                "f22": 0.066,
                "f23": -0.029,
            },
            3: {
                "f11": 0.33,
                "f12": 0.487,
                "f13": -0.221,
                "f21": 0.055,
                "f22": -0.064,
                "f23": -0.026,
            },
            4: {
                "f11": 0.568,
                "f12": 0.187,
                "f13": -0.295,
                "f21": 0.109,
                "f22": -0.152,
                "f23": -0.014,
            },
            5: {
                "f11": 0.873,
                "f12": -0.392,
                "f13": -0.362,
                "f21": 0.226,
                "f22": -0.462,
                "f23": 0.001,
            },
            6: {
                "f11": 1.132,
                "f12": -1.237,
                "f13": -0.412,
                "f21": 0.288,
                "f22": -0.823,
                "f23": 0.056,
            },
            7: {"f11": 1.06, "f12": -1.6, "f13": -0.359, "f21": 0.264, "f22": -1.127, "f23": 0.131},
            8: {
                "f11": 0.678,
                "f12": -0.327,
                "f13": -0.25,
                "f21": 0.156,
                "f22": -1.377,
                "f23": 0.251,
            },
        }

        return brightness_coeff_dict[index][brightness_coefficient]

    def __init_F1(
        self, clearness_parameter: float, delta: float, solar_zenith_angle: float
    ) -> float:
        """returns the circumsolar brightness coefficient, F1

        Arguments:
        clearness_parameter, E -- dimensionless clearness parameter for the current timestep
        delta -- dimensionless sky brightness parameter for the current timestep
        solar_zenith_angle -- solar zenith angle for the current hour
        """

        # brightness coeffs
        f11 = self.brightness_coefficient(
            clearness_parameter=clearness_parameter, brightness_coefficient="f11"
        )
        f12 = self.brightness_coefficient(
            clearness_parameter=clearness_parameter, brightness_coefficient="f12"
        )
        f13 = self.brightness_coefficient(
            clearness_parameter=clearness_parameter, brightness_coefficient="f13"
        )
        # The formulation of F1 is made so as to avoid non-physical negative values
        # that may occur and result in unacceptable distortions if the model is used
        # for very low solar elevation angles
        f1 = max(0, f11 + f12 * delta + f13 * (pi * solar_zenith_angle / 180))

        return f1

    def __init_F2(
        self, clearness_parameter: float, delta: float, solar_zenith_angle: float
    ) -> float:
        """returns the horizontal brightness coefficient, F2

        Arguments:
        clearness_parameter, E  -- dimensionless clearness parameter
        delta                   -- dimensionless sky brightness parameter
        solar_zenith_angle      -- solar zenith angle for the current hour
        """

        # horizontal brightness coefficient, F2
        f21 = self.brightness_coefficient(
            clearness_parameter=clearness_parameter, brightness_coefficient="f21"
        )
        f22 = self.brightness_coefficient(
            clearness_parameter=clearness_parameter, brightness_coefficient="f22"
        )
        f23 = self.brightness_coefficient(
            clearness_parameter=clearness_parameter, brightness_coefficient="f23"
        )
        # F2 does not have the same restriction of max 0 as F1
        # from the EnergyPlus Engineering Reference:
        # The horizon brightening is assumed to be a linear source at the horizon
        # and to be independent of azimuth. In actuality, for clear skies, the
        # horizon brightening is highest at the horizon and decreases in intensity
        # away from the horizon. For overcast skies the horizon brightening has a
        # negative value since for such skies the sky radiance increases rather than
        # decreases away from the horizon.
        f2 = f21 + f22 * delta + f23 * (pi * solar_zenith_angle / 180)

        return f2

    def __init_dimensionless_clearness_parameter(
        self,
        diffuse_horizontal_radiation: float,
        direct_beam_radiation: float,
        solar_altitude: float,
    ) -> float:
        """returns the dimensionless clearness parameter, E, anisotropic sky conditions (Perez model)

        Arguments:
        diffuse_horizontal_radiation -- diffuse horizontal radiation
        direct_beam_radiation   -- direct beam radiation
        solar_altitude          -- solar altitude for the current hour
        """

        # constant parameter for the clearness formula, K, in rad^-3 from table 9 of ISO 52010
        K = 1.014

        if diffuse_horizontal_radiation == 0:
            clearness_parameter = 999
        else:
            clearness_parameter = (
                (
                    (diffuse_horizontal_radiation + direct_beam_radiation)
                    / diffuse_horizontal_radiation
                )
                + K * (pi / 180 * solar_altitude) ** 3
            ) / (1 + K * (pi / 180 * solar_altitude) ** 3)

        return clearness_parameter

    def __init_dimensionless_sky_brightness_parameter(
        self,
        air_mass: float,
        diffuse_horizontal_radiation: float,
        extra_terrestrial_radiation: float,
    ) -> float:
        """calculates the dimensionless sky brightness parameter, delta

        Arguments:
        air_mass -- air mass for the current hour
        diffuse_horizontal_radiation -- diffuse horizontal radiation for the current timestep
        extra_terrestrial_radiation -- extra-terrestrial radiation for the current day
        """

        delta = air_mass * diffuse_horizontal_radiation / extra_terrestrial_radiation

        return delta

    def a_over_b(self, tilt: float, orientation: Orientation360) -> float:
        """calculates the ratio of the parameters a and b

        Arguments:
        tilt           -- is the tilt angle of the inclined surface from horizontal, measured
                          upwards facing, 0 to 180, in degrees;
        orientation    -- is the orientation angle of the inclined surface, expressed as the
                          geographical azimuth angle of the horizontal projection of the inclined
                          surface normal, 0 to 360, in degrees;
        """

        current_hour = self.__simulation_time.current_hour()
        # dimensionless parameters a & b
        # describing the incidence-weighted solid angle sustained by the circumsolar region as seen
        # respectively by the tilted surface and the horizontal.
        a = max(0, cos(radians(self.solar_angle_of_incidence(tilt=tilt, orientation=orientation))))
        b = max(cos(radians(85)), cos(radians(self.__solar_zenith_angle[current_hour])))

        return a / b

    def diffuse_irradiance(
        self, tilt: float, orientation: Orientation360
    ) -> tuple[float, float, float, float]:
        """calculates the diffuse part of the irradiance on the surface (without ground reflection)

        Arguments:
        tilt           -- is the tilt angle of the inclined surface from horizontal, measured
                          upwards facing, 0 to 180, in degrees;
        orientation    -- is the orientation angle of the inclined surface, expressed as the
                          geographical azimuth angle of the horizontal projection of the inclined
                          surface normal, 0 to 360, in degrees;
        """

        # first set up parameters needed for the calculation
        diffuse_horizontal_radiation = self.diffuse_horizontal_radiation()
        f1 = self.__F1[self.__simulation_time.index()]
        f2 = self.__F2[self.__simulation_time.index()]

        # Calculate components of diffuse radiation
        diffuse_irr_sky = diffuse_horizontal_radiation * (1 - f1) * ((1 + cos(radians(tilt))) / 2)
        diffuse_irr_circumsolar = self.circumsolar_irradiance(tilt=tilt, orientation=orientation)
        diffuse_irr_horiz = diffuse_horizontal_radiation * f2 * sin(radians(tilt))

        diffuse_irr_total = diffuse_irr_sky + diffuse_irr_circumsolar + diffuse_irr_horiz

        return diffuse_irr_total, diffuse_irr_sky, diffuse_irr_circumsolar, diffuse_irr_horiz

    def ground_reflection_irradiance(self, tilt: float) -> float:
        """calculates the contribution of the ground reflection to the irradiance on the inclined surface,
        determined as function of global horizontal irradiance, which in this case is calculated from the solar
        altitude, diffuse and beam solar irradiance and the solar reflectivity of the ground

        Arguments:
        tilt           -- is the tilt angle of the inclined surface from horizontal, measured
                          upwards facing, 0 to 180, in degrees;
        """

        # first set up parameters needed for the calculation
        current_hour = self.__simulation_time.current_hour()
        diffuse_horizontal_radiation = self.diffuse_horizontal_radiation()
        direct_beam_radiation = self.direct_beam_radiation()
        solar_altitude = radians(self.__solar_altitude[current_hour])

        ground_reflection_irradiance = (
            (diffuse_horizontal_radiation + direct_beam_radiation * sin(solar_altitude))
            * self.solar_reflectivity_of_ground()
            * ((1 - cos(radians(tilt))) / 2)
        )

        return ground_reflection_irradiance

    def circumsolar_irradiance(self, tilt: float, orientation: Orientation360) -> float:
        """calculates the circumsolar_irradiance

        Arguments:
        tilt           -- is the tilt angle of the inclined surface from horizontal, measured
                          upwards facing, 0 to 180, in degrees;
        orientation    -- is the orientation angle of the inclined surface, expressed as the
                          geographical azimuth angle of the horizontal projection of the inclined
                          surface normal, 0 to 360, in degrees;
        """

        diffuse_horizontal_radiation = self.diffuse_horizontal_radiation()
        f1 = self.__F1[self.__simulation_time.index()]
        a_over_b = self.a_over_b(tilt=tilt, orientation=orientation)

        circumsolar_irradiance = diffuse_horizontal_radiation * f1 * a_over_b

        return circumsolar_irradiance

    def calculated_direct_irradiance(self, tilt: float, orientation: Orientation360) -> float:
        """calculates the total direct irradiance on an inclined surface including circumsolar

        Arguments:
        tilt           -- is the tilt angle of the inclined surface from horizontal, measured
                          upwards facing, 0 to 180, in degrees;
        orientation    -- is the orientation angle of the inclined surface, expressed as the
                          geographical azimuth angle of the horizontal projection of the inclined
                          surface normal, 0 to 360, in degrees;
        """

        calculated_direct_irradiance = self.direct_irradiance(
            tilt=tilt, orientation=orientation
        ) + self.circumsolar_irradiance(tilt=tilt, orientation=orientation)

        return calculated_direct_irradiance

    def calculated_diffuse_irradiance(self, tilt: float, orientation: Orientation360) -> float:
        """calculates the total diffuse irradiance on an inclined surface excluding circumsolar
        and including ground reflected irradiance

        Arguments:
        tilt           -- is the tilt angle of the inclined surface from horizontal, measured
                          upwards facing, 0 to 180, in degrees;
        orientation    -- is the orientation angle of the inclined surface, expressed as the
                          geographical azimuth angle of the horizontal projection of the inclined
                          surface normal, 0 to 360, in degrees;
        """

        diffuse_irr_total, _, diffuse_irr_circumsolar, _ = self.diffuse_irradiance(
            tilt=tilt, orientation=orientation
        )

        calculated_diffuse = (
            diffuse_irr_total
            - diffuse_irr_circumsolar
            + self.ground_reflection_irradiance(tilt=tilt)
        )

        return calculated_diffuse

    def calculated_total_solar_irradiance(self, tilt: float, orientation: Orientation360) -> float:
        """calculates the hemispherical or total solar irradiance on the inclined surface
        without the effect of shading

        Arguments:
        tilt           -- is the tilt angle of the inclined surface from horizontal, measured
                          upwards facing, 0 to 180, in degrees;
        orientation    -- is the orientation angle of the inclined surface, expressed as the
                          geographical azimuth angle of the horizontal projection of the inclined
                          surface normal, 0 to 360, in degrees;

        """

        total_irradiance = self.calculated_direct_irradiance(
            tilt=tilt, orientation=orientation
        ) + self.calculated_diffuse_irradiance(tilt=tilt, orientation=orientation)

        return total_irradiance

    def calculated_direct_diffuse_total_irradiance(
        self, tilt: float, orientation: Orientation360, diffuse_breakdown: bool = False
    ) -> tuple[float, float, float, dict[str, float] | None]:
        t_idx = self.__simulation_time.index()
        if t_idx != self.__cached_timestep:
            # If we have moved on to a new timestep, then clear the cached results
            self.__cached_results = {}
            self.__cached_timestep = t_idx

        orientation180 = orientation.transform_to_180()
        if (tilt, orientation180) in self.__cached_results.keys():
            # Look up cached values if this tilt and orientation has already been calculated
            calculated_direct = self.__cached_results[(tilt, orientation180)]["calculated_direct"]
            calculated_diffuse = self.__cached_results[(tilt, orientation180)]["calculated_diffuse"]
            total_irradiance = self.__cached_results[(tilt, orientation180)]["total_irradiance"]
            diffuse_res_breakdown = self.__cached_results[(tilt, orientation180)][
                "diffuse_res_breakdown"
            ]
        else:
            # Calculate results if this tilt and orientation has not already been calculated
            diffuse_irr_total, diffuse_irr_sky, diffuse_irr_circumsolar, diffuse_irr_horiz = (
                self.diffuse_irradiance(tilt=tilt, orientation=orientation)
            )
            ground_refl_irr = self.ground_reflection_irradiance(tilt=tilt)

            calculated_direct = (
                self.direct_irradiance(tilt=tilt, orientation=orientation) + diffuse_irr_circumsolar
            )
            calculated_diffuse = diffuse_irr_total - diffuse_irr_circumsolar + ground_refl_irr
            total_irradiance = calculated_direct + calculated_diffuse

            diffuse_res_breakdown = {
                "sky": diffuse_irr_sky,
                "circumsolar": diffuse_irr_circumsolar,
                "horiz": diffuse_irr_horiz,
                "ground_refl": ground_refl_irr,
            }

            # Cache calculated results
            self.__cached_results[(tilt, orientation180)] = {}
            self.__cached_results[(tilt, orientation180)]["calculated_direct"] = calculated_direct
            self.__cached_results[(tilt, orientation180)]["calculated_diffuse"] = calculated_diffuse
            self.__cached_results[(tilt, orientation180)]["total_irradiance"] = total_irradiance
            self.__cached_results[(tilt, orientation180)]["diffuse_res_breakdown"] = (
                diffuse_res_breakdown
            )

        if diffuse_breakdown:
            return calculated_direct, calculated_diffuse, total_irradiance, diffuse_res_breakdown
        else:
            return calculated_direct, calculated_diffuse, total_irradiance, None

    # end of sun path calculations from ISO 52010
    # below are overshading calculations from ISO 52016

    def outside_solar_beam(self, tilt: float, orientation: Orientation360) -> bool:
        """checks if the shaded surface is in the view of the solar beam.
        if not, then shading is complete, total direct rad = 0 and no further
        shading calculation needed for this object for this time step. returns
        a flag for whether the surface is outside solar beam

        Arguments:
        tilt           -- is the tilt angle of the inclined surface from horizontal, measured
                          upwards facing, 0 to 180, in degrees;
        orientation    -- is the orientation angle of the inclined surface, expressed as the
                          geographical azimuth angle of the horizontal projection of the
                          inclined surface normal, 0 to 360, in degrees;
                          It will be converted to the -180 to 180 range;
                          Assumed N 180 or -180, E 90, S 0, W -90

        """

        orientation180 = orientation.transform_to_180()
        current_hour = self.__simulation_time.current_hour()
        test1 = orientation180 - self.__solar_azimuth_angle[current_hour]
        test1 = test1 - 360.0 if test1 > +180.0 else test1 + 360.0 if test1 < -180.0 else test1
        test2 = tilt - self.__solar_altitude[current_hour]

        if -90 > test1 or test1 > 90:
            # surface outside solar beam
            return True
        elif -90 > test2 or test2 > 90:
            # surface outside solar beam
            return True
        else:
            # surface inside solar beam
            return False

    def get_segment(self) -> dict[str, Any]:
        """for complex (environment) shading objects, we need to know which
        segment the azimuth of the sun occupies at each timestep

        """

        current_hour = self.__simulation_time.current_hour()
        azimuth = self.__solar_azimuth_angle[current_hour]

        previous_segment_end = None
        if self.__shading_segments:
            for segment in self.__shading_segments:
                if (
                    previous_segment_end is not None
                    and previous_segment_end.angle != segment["start360"].angle
                ):
                    raise ValueError("Gaps or overlaps between segments not allowed.")
                previous_segment_end = segment["end360"]
                if segment["end360"].angle < segment["start360"].angle:
                    raise ValueError(
                        "End orientation is less than the start orientation. Check shading inputs."
                    )
                if (
                    azimuth < segment["start360"].transform_to_180()
                    and azimuth > segment["end360"].transform_to_180()
                ):
                    return segment
            # if not exited function yet then segment has not been found and there
            # is some sort of error
            raise ValueError("Solar segment not found. Check shading inputs.")
        else:
            raise ValueError("Cannot get segments. self.__shading_segments is None.")

    def obstacle_shading_height(
        self, base_height: float, shading_obstacle_height: float, surface_obstacle_distance: float
    ) -> float:
        """calculates the height of the shading on the shaded surface (k),
        from the shading obstacle in segment i at time t. Note that "obstacle"
        has a specific meaning in ISO 52016 Annex F

        Arguments:
        base_height               -- is the base height of the shaded surface k, in m
        shading_obstacle_height   -- is the height of the shading obstacle, p, in segment i, in m
        surface_obstacle_distance -- is the horizontal distance between the shaded surface k, in m
                         and the shading obstacle p in segment i, in m
        """

        current_hour = self.__simulation_time.current_hour()
        shading_height = max(
            0,
            shading_obstacle_height
            - base_height
            - surface_obstacle_distance * tan(radians(self.__solar_altitude[current_hour])),
        )
        return shading_height

    def overhang_shading_height(
        self,
        shaded_surface_height: float,
        base_height: float,
        overhang_lowest_height: float,
        surface_overhang_distance: float,
    ) -> float:
        """calculates the height of the shading on the shaded surface (k),
        from the shading overhang in segment i at time t. Note that "overhang"
        has a specific meaning in ISO 52016 Annex F

        Arguments:
        shaded_surface_height     -- is the height of the shaded surface, k, in m
        base_height               -- is the base height of the shaded surface k, in m
        overhang_lowest_height    -- is the lowest height of the overhang q, in segment i, in m
        surface_overhang_distance -- is the horizontal distance between the shaded surface k
                         and the shading overhang, q, in segment i, in m
        """

        current_hour = self.__simulation_time.current_hour()
        shading_height = max(
            0,
            shaded_surface_height
            + base_height
            - overhang_lowest_height
            + surface_overhang_distance * tan(radians(self.__solar_altitude[current_hour])),
        )
        return shading_height

    def direct_shading_reduction_factor(
        self,
        base_height: float,
        height: float,
        width: float,
        orientation: Orientation360,
        window_shading: list[dict[str, Any]],
    ) -> float:
        """calculates the shading factor of direct radiation due to external
        shading objects

        Arguments:
        base_height    -- is the base height of the shaded surface k, in m
        height         -- is the height of the shaded surface (if surface is tilted then
                          this must be the vertical projection of the height), in m
        width          -- is the width of the shaded surface, in m
        orientation    -- is the orientation angle of the inclined surface, expressed as the
                          geographical azimuth angle of the horizontal projection of the
                          inclined surface normal, 0 to 360, in degrees;
                          It will be converted to the -180 to 180 range;
                          Assumed N 180 or -180, E 90, S 0, W -90
        window_shading -- data on overhangs and side fins associated to this building element
                          includes the shading object type, depth, anf distance from element
        """

        orientation180 = orientation.transform_to_180()
        # start with default assumption of no shading
        Hshade_obst = 0
        Hshade_ovh = 0
        WfinR = 0
        WfinL = 0

        # first process the distant (environment) shading for this building element

        # get the shading segment we are currently in
        segment = self.get_segment()

        # check for any shading objects in this segment
        if "shading" in segment.keys():
            for shade_obj in segment["shading"]:
                if shade_obj["type"] == ShadingObjectType.OBSTACLE:
                    new_shade_height = self.obstacle_shading_height(
                        base_height=base_height,
                        shading_obstacle_height=shade_obj["height"],
                        surface_obstacle_distance=shade_obj["distance"],
                    )

                    Hshade_obst = max(Hshade_obst, new_shade_height)
                elif shade_obj["type"] == ShadingObjectType.OVERHANG:
                    new_shade_height = self.overhang_shading_height(
                        shaded_surface_height=height,
                        base_height=base_height,
                        overhang_lowest_height=shade_obj["height"],
                        surface_overhang_distance=shade_obj["distance"],
                    )

                    Hshade_ovh = max(Hshade_ovh, new_shade_height)
                else:
                    raise ValueError(f"Invalid ShadingObjectType: {shade_obj['type']}.")

        # then check if there is any simple shading on this building element
        # (note only applicable to transparent building elements so window_shading
        # will always be False for other elements)
        if window_shading:
            current_hour = self.__simulation_time.current_hour()
            altitude = self.__solar_altitude[current_hour]
            azimuth = self.__solar_azimuth_angle[current_hour]
            # if there is then loop through all objects and calc shading heights/widths
            for shade_obj in window_shading:
                if shade_obj["type"] == ShadingObjectType.OBSTACLE:
                    # For nearby obstacles, skip this loop. These will be dealt with later
                    continue
                depth = shade_obj["depth"]
                distance = shade_obj["distance"]
                if shade_obj["type"] == WindowShadingType.OVERHANG:
                    new_shade_height = (
                        depth * tan(radians(altitude)) / cos(radians(azimuth - orientation180))
                    ) - distance

                    Hshade_ovh = max(Hshade_ovh, new_shade_height)
                elif shade_obj["type"] == WindowShadingType.SIDEFINRIGHT:
                    # check if the sun is in the opposite direction
                    check = azimuth - orientation180
                    if check > 0:
                        new_finRshade = 0
                    else:
                        new_finRshade = depth * tan(radians(azimuth - orientation180)) - distance
                    WfinR = max(WfinR, new_finRshade)
                elif shade_obj["type"] == WindowShadingType.SIDEFINLEFT:
                    # check if the sun is in the opposite direction
                    check = azimuth - orientation180
                    if check < 0:
                        new_finLshade = 0
                    else:
                        new_finLshade = depth * tan(radians(azimuth - orientation180)) - distance
                    WfinL = max(WfinL, new_finLshade)
                else:
                    raise ValueError(f"Invalid WindowShadingType: {shade_obj['type']}.")

        # The height of the shade on the shaded surface from all obstacles is the
        # largest of all, with as maximum value the height of the shaded object
        Hk_obst = min(height, Hshade_obst)

        # The height of the shade on the shaded surface from all overhangs is the
        # largest of all, with as maximum value the height of the shaded object
        Hk_ovh = min(height, Hshade_ovh)

        # The height of the remaining sunlit area on the shaded surface from
        # all obstacles and all overhangs
        Hk_sun = max(0, height - (Hk_obst + Hk_ovh))

        # The width of the shade on the shaded surface from all right side fins
        # is the largest of all, with as maximum value the width of the shaded object
        Wk_finR = min(width, WfinR)

        # The width of the shade on the shaded surface from all left side fins
        # is the largest of all, with as maximum value the width of the shaded object
        Wk_finL = min(width, WfinL)

        # The width of the remaining sunlit area on the shaded surface from all
        # right hand side fins and all left hand side fins
        Wk_sun = max(0, width - (Wk_finR + Wk_finL))

        # And then the direct shading reduction factor of the shaded surface for
        # obstacles, overhangs and side fins
        direct_shading_reduction_factor = (Hk_sun * Wk_sun) / (height * width)

        if window_shading:
            for shade_obj in window_shading:
                if shade_obj["type"] == ShadingObjectType.OBSTACLE:
                    new_shade_height = self.obstacle_shading_height(
                        base_height=base_height,
                        shading_obstacle_height=shade_obj["height"],
                        surface_obstacle_distance=shade_obj["distance"],
                    )

                    new_shade_trans = shade_obj["transparency"]

                    # Repeat Fdir (direct_shading_reduction_factor) assessment for each near obstacle to find largest shading effect
                    Hk_obst = min(height, new_shade_height)
                    Hk_sun = max(0, height - (Hk_obst + Hk_ovh)) + (
                        min(Hk_obst, height - Hk_ovh) * new_shade_trans
                    )

                    direct_shading_reduction_factor = min(
                        direct_shading_reduction_factor, (Hk_sun * Wk_sun) / (height * width)
                    )

        return direct_shading_reduction_factor

    def diffuse_shading_reduction_factor(
        self,
        diffuse_breakdown: dict[str, Any],
        tilt: float,
        height: float,
        base_height: float,
        width: float,
        orientation: Orientation360,
        window_shading: list[dict[str, Any]],
        f_sky: float,
    ) -> float:
        """Calculates the shading factor of diffuse radiation due to external
        shading objects

        Arguments:
        diffuse_breakdown --
        tilt           -- is the tilt angle of the inclined surface from horizontal, measured
                          upwards facing, 0 to 180, in degrees;
        height         -- is the height of the shaded surface (if surface is tilted then
                          this must be the vertical projection of the height), in m
        base_height    -- is the base height of the shaded surface k, in m
        width          -- is the width of the shaded surface, in m
        orientation    -- is the orientation angle of the inclined surface, expressed as the
                          geographical azimuth angle of the horizontal projection of the
                          inclined surface normal, 0 to 360, in degrees;
        window_shading -- data on overhangs and side fins associated to this building element
                          includes the shading object type, depth, and distance from element
        f_sky          --
        """
        # Note: Shading factor for circumsolar radiation is same as for direct.
        #       As circumsolar radiation will be subtracted from diffuse and
        #       added to direct later on, we don't need to do anything for
        #       circumsolar radiation here and it is excluded.
        diffuse_irr_sky = diffuse_breakdown["sky"]
        diffuse_irr_hor = diffuse_breakdown["horiz"]
        diffuse_irr_ref = diffuse_breakdown["ground_refl"]
        diffuse_irr_total = diffuse_irr_sky + diffuse_irr_hor + diffuse_irr_ref

        if diffuse_irr_total == 0:
            raise ValueError("Zero diffuse radiation with non-zero direct radiation.")

        # PD CEN ISO/TR 52016-2:2017 Section F.6.2 is not clearly defined and has been ignored.
        # Calculation for remote obstacles uses a similar method to the simple facade object
        # and self-shading corrections in F6.3. Equation F.7 is now assumed to include a
        # further term of (FvW - FvRM), where FvRM is the view factor between the element
        # and a remote obstacle.

        # Assumes for all elements that the angle between element and baseline horizon is 0.
        # Any significant height variation between element and unobstructed horizon should
        # be considered as an obstacle to be included.

        # Any element height that projects above obstruction is consider unobstructed. The
        # shading angle to the sky is taken from the midpoint of the section of element
        # below the obstruction.

        def interval_intersect(a: list[float], b: list[float]) -> float:
            """Returns intersection between element shaded arc and shading segment"""
            return max(0, min(a[1], b[1]) - max(a[0], b[0]))

        def arc_angle_ranges(
            arc_start: float, arc_end: float
        ) -> tuple[list[list[float]], list[list[float]], float]:
            """Returns angle ranges included in element shaded arc with 0/360 crossover"""
            """ split if required plus total angle of arc """
            # Define front arc as single arc and split rear arc either side of 0/360 boundary
            if arc_start < arc_end:
                arc1 = [arc_start, arc_end]
                arc2 = [0.0, 0.0]
                deg_arc = arc_end - arc_start
                rarc1 = [arc_end, 360.0]
                rarc2 = [0.0, arc_start]
            # Define rear arc as single arc and split front arc either side of 0/360 boundary
            else:
                arc1 = [arc_start, 360.0]
                arc2 = [0.0, arc_end]
                deg_arc = (360.0 - arc_start) + arc_end
                rarc1 = [arc_end, arc_start]
                rarc2 = [0.0, 0.0]

            arc_angle = [arc1, arc2]
            rear_arc_angle = [rarc1, rarc2]

            return arc_angle, rear_arc_angle, deg_arc

        def segment_angle_ranges(
            segment_start: float, segment_end: float
        ) -> tuple[list[list[float]], float]:
            """Returns angle ranges included in shading segment with 0/360 crossover"""
            """ split if required plus total angle of segment """
            if segment_start < segment_end:
                seg1 = [segment_start, segment_end]
                seg2 = [0.0, 0.0]
                deg_seg = segment_end - segment_start
            else:  # Treat as separate segments either side of 0/360 boundary
                seg1 = [segment_start, 360.0]
                seg2 = [0.0, segment_end]
                deg_seg = (360.0 - segment_start) + segment_end

            segment_angle = [seg1, seg2]

            return segment_angle, deg_seg

        # Determine start and end orientations for potential forward shading arc by remote obstacles
        # 180deg arc assumed unless horizontal

        # Default arc values
        arc_start = 0.0
        arc_end = 360.0

        if tilt > 0.0:  # All non-horizontal elements
            orient360 = orientation.angle
            if orient360 >= 90.0 and orient360 <= 270.0:
                arc_start = orient360 - 90.0  # Shaded arc start angle (clockwise)
                arc_end = orient360 + 90.0  # Shaded arc end angle (clockwise)
            elif orient360 < 90.0:
                arc_start = orient360 + 270.0
                arc_end = orient360 + 90.0
            elif orient360 > 270.0:
                arc_start = orient360 - 90.0
                arc_end = orient360 - 270.0

        # Define arcs to the front and rear of element
        arc_angle, rear_arc_angle, deg_arc = arc_angle_ranges(arc_start=arc_start, arc_end=arc_end)

        f_sky_new = 0.0  # Initialise new f_sky value
        if self.__shading_segments:
            for segment in self.__shading_segments:
                segment_start = segment["start360"].angle  # Segment start angle (clockwise)
                segment_end = segment["end360"].angle  # Segment end angle (clockwise)

                # Define segment
                segment_angle, deg_seg = segment_angle_ranges(
                    segment_start=segment_start, segment_end=segment_end
                )

                # Compare sub-arcs and sub-segments for overlap - front
                ap00 = interval_intersect(a=arc_angle[0], b=segment_angle[0])
                ap11 = interval_intersect(a=arc_angle[1], b=segment_angle[1])
                ap01 = interval_intersect(a=arc_angle[0], b=segment_angle[1])
                ap10 = interval_intersect(a=arc_angle[1], b=segment_angle[0])

                # Proportion of front arc shaded by segment
                front_arc_proportion = (ap00 + ap11 + ap01 + ap10) / deg_arc

                # Compare sub-arcs and sub-segments for overlap - rear
                rap00 = interval_intersect(a=rear_arc_angle[0], b=segment_angle[0])
                rap11 = interval_intersect(a=rear_arc_angle[1], b=segment_angle[1])
                rap01 = interval_intersect(a=rear_arc_angle[0], b=segment_angle[1])
                rap10 = interval_intersect(a=rear_arc_angle[1], b=segment_angle[0])

                # Proportion of rearward arc within segment
                rear_arc_proportion = (rap00 + rap11 + rap01 + rap10) / deg_arc

                # Segment f_sky contribution in forward direction
                if tilt == 0:
                    f_sky_seg_front = f_sky * (deg_seg / 360.0)
                else:
                    f_sky_seg_front = front_arc_proportion * min(0.5, f_sky)

                # For tilted surface, segment f_sky contribution in rear direction
                if 0.0 < tilt < 90.0:
                    f_sky_seg_rear = rear_arc_proportion * max(0.0, (f_sky - 0.5))
                else:
                    f_sky_seg_rear = 0.0

                f_sky_front = f_sky_seg_front
                f_sky_rear = f_sky_seg_rear

                if "shading" in segment.keys():
                    for shade_obj in segment["shading"]:
                        if shade_obj["type"] == ShadingObjectType.OBSTACLE:
                            shading_object_height = max(
                                0.0, shade_obj["height"] - base_height
                            )  # height of shading object relative to element base

                            if f_sky == 1.0:  # Horizontal Element (tilt = 0)
                                alpha_obst = degrees(
                                    atan(shading_object_height / shade_obj["distance"])
                                )  # angle between midpoint of shaded section and obstacle
                                f_sky_front = min(
                                    f_sky_front, f_sky_seg_front * cos(radians(alpha_obst))
                                )

                            elif f_sky > 0.0:
                                if f_sky_seg_front > 0.0:
                                    H_above = max(
                                        0.0, height - shading_object_height
                                    )  # height element is above obstacle (zero if not)
                                    proportion_above_obstacle = (
                                        H_above / height
                                    )  # proportion of element above obstacle
                                    alpha_obst = degrees(
                                        atan(
                                            (
                                                shading_object_height
                                                - (min(height, shading_object_height) / 2.0)
                                            )
                                            / shade_obj["distance"]
                                        )
                                    )  # angle between midpoint of shaded section and obstacle
                                    # Determine if obstacle gives largest reduction to the segment f_sky contribution
                                    f_sky_front = min(
                                        f_sky_front,
                                        max(
                                            0.0,
                                            f_sky_seg_front
                                            - 0.5
                                            * front_arc_proportion
                                            * (1.0 - cos(radians(alpha_obst)))
                                            * (1.0 - proportion_above_obstacle),
                                        ),
                                    )

                                if f_sky_seg_rear > 0.0:
                                    # Determine if potential for shading from obstacles to rear of tilted surface exist
                                    H_eff = height + (
                                        shade_obj["distance"] * tan(radians(tilt))
                                    )  # Projected height of element at obstacle distance
                                    if H_eff < shading_object_height:
                                        alpha_obst = degrees(
                                            atan(shading_object_height / shade_obj["distance"])
                                        )  # angle from element midpoint to top of obstacle
                                        # Determine new rear sky view factor directly from shading angle (alpha_obst) using standard 0.5 x cos(angle) method
                                        # as shadng is now determined by this angle not the tilt angle which is smaller
                                        f_sky_rear = min(
                                            f_sky_rear,
                                            rear_arc_proportion * 0.5 * cos(radians(alpha_obst)),
                                        )

                        elif shade_obj["type"] == ShadingObjectType.OVERHANG:
                            shading_object_height = max(
                                0.0, shade_obj["height"] - base_height
                            )  # base height of overhang object relative to element base

                            if f_sky == 1.0:  # Horizontal Element (tilt = 0)
                                alpha_ovh = degrees(
                                    atan(shading_object_height / shade_obj["distance"])
                                )  # angle between midpoint of shaded section and obstacle
                                f_sky_front = min(
                                    f_sky_front, f_sky_seg_front * (1.0 - cos(radians(alpha_ovh)))
                                )

                            elif f_sky > 0.0:
                                if f_sky_seg_front > 0.0:
                                    H_below = min(
                                        height, shading_object_height
                                    )  # height element is below overhang (zero if not)
                                    proportion_below_overang = (
                                        H_below / height
                                    )  # proportion of element below overhang
                                    alpha_ovh = degrees(
                                        atan(
                                            (
                                                shading_object_height
                                                - (min(height, shading_object_height) / 2.0)
                                            )
                                            / shade_obj["distance"]
                                        )
                                    )  # angle between midpoint of shaded section and overhang
                                    # Determine if overhang gives largest reduction to the segment f_sky contribution
                                    f_sky_front = min(
                                        f_sky_front,
                                        0.5
                                        * front_arc_proportion
                                        * (1.0 - cos(radians(alpha_ovh)))
                                        * proportion_below_overang,
                                    )

                                if f_sky_seg_rear > 0.0:
                                    # Determine if potential for shading from overhangs to rear of tilted surface exist
                                    H_eff = height + (
                                        shade_obj["distance"] * tan(radians(tilt))
                                    )  # Projected height of element at overhang distance
                                    if H_eff < shading_object_height:
                                        alpha_ovh = degrees(
                                            atan(shading_object_height / shade_obj["distance"])
                                        )  # angle from element midpoint to top of obstacle
                                        f_sky_rear = min(
                                            f_sky_rear,
                                            rear_arc_proportion
                                            * 0.5
                                            * (cos(radians(tilt)) - cos(radians(alpha_ovh))),
                                        )

                                    else:
                                        f_sky_rear = 0.0

                        else:
                            raise ValueError(
                                f"Invalid ShadingObjectType for calculating diffuse shading reduction factor: {shade_obj['type']}."
                            )

                f_sky_new += f_sky_front + f_sky_rear

        # Calculate Fdiff (diffuse_factor) for remote obstacles
        # Allow for tilt = 180deg (i.e. f_sky = 0) case
        if f_sky > 0.0:
            F_sh_dif_rem = 1.0 - ((f_sky - f_sky_new) / f_sky)
        else:
            F_sh_dif_rem = 1.0

        # Assumes for remote objects that the reduction in sky view factor is
        # matched by an equivalent increase in ground reflected irradiance.
        if f_sky != 1.0:
            F_sh_ref_rem = (1.0 - f_sky_new) / (1.0 - f_sky)
            remote_obstacles_diffuse_factor = (
                F_sh_dif_rem * (diffuse_irr_sky + diffuse_irr_hor) + F_sh_ref_rem * diffuse_irr_ref
            ) / diffuse_irr_total

        else:
            effective_tilt_angle = degrees(
                acos((2.0 * f_sky_new) - 1.0)
            )  # Effective tilt angle equivalent of shading
            diffuse_irr_ref_new = self.ground_reflection_irradiance(tilt=effective_tilt_angle)
            remote_obstacles_diffuse_factor = (
                F_sh_dif_rem * (diffuse_irr_sky + diffuse_irr_hor) + diffuse_irr_ref_new
            ) / diffuse_irr_total

        # Calculate shading from fins and overhangs (PD CEN ISO/TR 52016-2:2017 Section F.6.3)
        # TODO Alpha is not defined in this standard but is possibly the angular
        #      height of the horizon. This would make some sense as raising the
        #      horizon angle would have essentially the same effect as increasing
        #      the tilt of the building element so it would make sense to add it
        #      to beta when calculating the sky view factor. The overall effect
        #      of changing alpha when there are no fins or overhangs seems to be
        #      to decrease the shading factor (meaning more shading) for diffuse
        #      radiation from sky and horizon, and to increase the shading factor
        #      for radiation reflected from the ground (sometimes to above 1),
        #      which would also seem to make sense as in this case there is less
        #      sky and more ground in view than in the basic assumption of
        #      perfectly flat surroundings.
        # TODO Should angular height of horizon be user input or derived from
        #      calculation of distant shading objects above? Set to zero for now
        angular_height_of_horizon = 0.0
        alpha = radians(angular_height_of_horizon)
        # TODO Beta is not defined in this standard but is used for tilt of the
        #      building element in BS EN ISO 52016-1:2017, so assuming the same.
        #      This seems to give sensible numbers for the sky view factor
        #      F_w_sky when alpha = 0
        beta = radians(tilt)

        if not window_shading:
            diffuse_factors = [1.0]

        else:
            # create lists of diffuse shading factors to keep the largest one
            # in case there are multiple shading objects
            diffuse_factors = []

            # Unpack window shading details
            # L (distance) cannot be zero for overhang and sidefins as this leads to divide-by-zero later on
            overhang_depths_distances = [[0.0, 1.0]]  # [D (depth), L (distance)]
            right_sidefin_depths_distances = [[0.0, 1.0]]  # [D (depth), L (distance)]
            left_sidefin_depths_distances = [[0.0, 1.0]]  # [D (depth), L (distance)]
            obstacle_heights_distances = [
                [0.0, 1.0, 0.0]
            ]  # [H (heightt), L (distance), transparency]

            if window_shading:
                for shade_obj in window_shading:
                    if shade_obj["type"] == WindowShadingType.OVERHANG:
                        overhang_depths_distances.append(
                            [shade_obj["depth"], shade_obj["distance"]]
                        )
                    elif shade_obj["type"] == WindowShadingType.SIDEFINRIGHT:
                        right_sidefin_depths_distances.append(
                            [shade_obj["depth"], shade_obj["distance"]]
                        )
                    elif shade_obj["type"] == WindowShadingType.SIDEFINLEFT:
                        left_sidefin_depths_distances.append(
                            [shade_obj["depth"], shade_obj["distance"]]
                        )
                    elif shade_obj["type"] == ShadingObjectType.OBSTACLE:
                        obstacle_heights_distances.append(
                            [shade_obj["height"], shade_obj["distance"], shade_obj["transparency"]]
                        )
                    else:
                        raise ValueError(f"Invalid window shading: {shade_obj['type']}.")

            # the default values should not be used if shading is specified
            if len(overhang_depths_distances) >= 2:
                overhang_depths_distances.pop(0)
            if len(right_sidefin_depths_distances) >= 2:
                right_sidefin_depths_distances.pop(0)
            if len(left_sidefin_depths_distances) >= 2:
                left_sidefin_depths_distances.pop(0)
            if len(obstacle_heights_distances) >= 2:
                obstacle_heights_distances.pop(0)

            # perform the diff shading calculation for each comination of overhangs, fins and obstacles
            F_sh_dif = 0
            F_sh_ref = 0
            for (
                overhang_depth_distance,
                right_sidefin_depth_distance,
                left_sidefin_depth_distance,
                obstacle_height_distance,
            ) in product(
                overhang_depths_distances,
                right_sidefin_depths_distances,
                left_sidefin_depths_distances,
                obstacle_heights_distances,
            ):
                overhang_depth = overhang_depth_distance[0]
                overhang_distance = overhang_depth_distance[1]
                left_sidefin_depth = left_sidefin_depth_distance[0]
                left_sidefin_distance = left_sidefin_depth_distance[1]
                right_sidefin_depth = right_sidefin_depth_distance[0]
                right_sidefin_distance = right_sidefin_depth_distance[1]
                obstacle_height = obstacle_height_distance[0]
                obstacle_distance = obstacle_height_distance[1]
                obstacle_transparency = obstacle_height_distance[2]
                # Calculate required geometric ratios
                # Note: PD CEN ISO/TR 52016-2:2017 Section F.6.3 refers to ISO 52016-1:2017
                #       Section F.5.5.1.6 for the definition of P1 and P2. However, this
                #       section does not exist. Therefore, these definitions have been
                #       taken from Section F.3.5.1.2 instead, also supported by Table F.6
                #       in PD CEN ISO/TR 52016-2:2017. These sources define P1 and P2
                #       differently for fins and for overhangs so it is assumed that
                #       should also apply here.
                p1_overhang = overhang_depth / height
                p2_overhang = overhang_distance / height
                p1_left_sidefin = left_sidefin_depth / width
                p2_left_sidefin = left_sidefin_distance / width
                p1_right_sidefin = right_sidefin_depth / width
                p2_right_sidefin = right_sidefin_distance / width

                # Calculate view factors (eqns F.15 to F.18) required for eqns F.9 to F.14
                # Note: The equations in the standard refer to P1 and P2, but as per the
                #       comment above, there are different definitions of these for fins
                #       and for overhangs. The decision on which ones to use for each of
                #       the equations below has been made depending on which of the
                #       subsequent equations the resulting variables are used in (e.g.
                #       F_w_s is used to calculate F_sh_dif_fins so we use P1 and P2 for
                #       fins).
                # Note: For F_w_r, we could set P1 equal to P1 for fins and P2 equal to
                #       P1 (not P2) for overhangs, as this appears to be consistent with
                #       example in Table F.6
                # F_w_r = 1 - exp(-0.8632 * (P1_fin + P1_overhang))
                # Note: Formula in standard for view factor to fins seems to assume that
                #       fins are the same on each side. Therefore, here we take the
                #       average of this view factor calculated with the dimensions of
                #       each fin.
                F_w_s = (
                    0.6514
                    * (
                        1
                        - (
                            p2_left_sidefin
                            / sqrt(
                                p1_left_sidefin * p1_left_sidefin
                                + p2_left_sidefin * p2_left_sidefin
                            )
                        )
                    )
                    + 0.6514
                    * (
                        1
                        - (
                            p2_right_sidefin
                            / sqrt(
                                p1_right_sidefin * p1_right_sidefin
                                + p2_right_sidefin * p2_right_sidefin
                            )
                        )
                    )
                ) / 2
                F_w_o = 0.3282 * (
                    1 - (p2_overhang / sqrt(p1_overhang * p1_overhang + p2_overhang * p2_overhang))
                )
                F_w_sky = (1 - sin(alpha + beta - radians(90))) / 2

                # Calculate denominators of eqns F.9 to F.14
                view_factor_sky_no_obstacles = (1 + cos(beta)) / 2
                view_factor_ground_no_obstacles = (1 - cos(beta)) / 2

                # Setback and remote obstacles (eqns F.9 and F.10): Top half of each eqn
                # is view factor to sky (F.9) or ground (F.10) with setback and distant
                # obstacles
                # TODO Uncomment these lines when definitions of P1 and P2 in formula
                #      for F_w_r have been confirmed.
                # if view_factor_sky_no_obstacles == 0:
                #     # Shading makes no difference if sky not visible (avoid divide-by-zero)
                #     F_sh_dif_setback = 1.0
                # else:
                #     F_sh_dif_setback = (1 - F_w_r) * F_w_sky \
                #                      / view_factor_sky_no_obstacles
                # if view_factor_ground_no_obstacles == 0:
                #     # Shading makes no difference if ground not visible (avoid divide-by-zero)
                #     F_sh_ref_setback = 1.0
                # else:
                #     F_sh_ref_setback = (1 - F_w_r) * (1 - F_w_sky) \
                #                      / view_factor_ground_no_obstacles

                # Fins and remote obstacles (eqns F.11 and F.12): Top half of each eqn
                # is view factor to sky (F.11) or ground (F.12) with fins and distant
                # obstacles
                if view_factor_sky_no_obstacles == 0:
                    # Shading makes no difference if sky not visible (avoid divide-by-zero)
                    F_sh_dif_fins = 1.0
                else:
                    F_sh_dif_fins = (1 - F_w_s) * F_w_sky / view_factor_sky_no_obstacles

                if view_factor_ground_no_obstacles == 0:
                    # Shading makes no difference if ground not visible (avoid divide-by-zero)
                    F_sh_ref_fins = 1.0
                else:
                    F_sh_ref_fins = (1 - F_w_s) * (1 - F_w_sky) / view_factor_ground_no_obstacles

                # Overhangs and remote obstacles (eqns F.13 and F.14)
                # Top half of eqn F.13 is view factor to sky with overhangs
                if view_factor_sky_no_obstacles == 0:
                    # Shading makes no difference if sky not visible (avoid divide-by-zero)
                    F_sh_dif_overhangs = 1.0
                else:
                    F_sh_dif_overhangs = (F_w_sky - F_w_o) / view_factor_sky_no_obstacles
                # Top half of eqn F.14 is view factor to ground with distant obstacles,
                # but does not account for overhangs blocking any part of the view of
                # the ground, presumably because this will not happen in the vast
                # majority of cases
                if view_factor_ground_no_obstacles == 0:
                    # Shading makes no difference if ground not visible (avoid divide-by-zero)
                    F_sh_ref_overhangs = 1.0
                else:
                    F_sh_ref_overhangs = (1 - F_w_sky) / view_factor_ground_no_obstacles

                # Obstacles adjacent to surface (e.g. balcony rails, garden walls). Not explicitly
                # covered by 52016-1 or -2, therefore derived from first principles and general
                # method basis.
                net_shade_height = obstacle_height - base_height
                F_sh_dif_obs = 0
                if view_factor_sky_no_obstacles == 0 or net_shade_height <= 0.0:
                    # Shading makes no difference if sky not visible (avoid divide-by-zero)
                    F_sh_dif_obs = 1.0
                else:
                    height_above_obstacle = max(
                        0.0, height - net_shade_height
                    )  # height of element above obstacle
                    prop_above_obstacle = (
                        height_above_obstacle / height
                    )  # proportion of element above obstacle
                    angle_obst = degrees(
                        atan((net_shade_height / 2.0) / obstacle_distance)
                    )  # angle between midpoint of shaded section and top of obstacle
                    F_w_ob = (
                        min(
                            view_factor_sky_no_obstacles,
                            ((1.0 - sin(radians(90.0 - angle_obst))) * 0.5),
                        )
                        * (1.0 - prop_above_obstacle)
                        * (1.0 - obstacle_transparency)
                    )  # Sky view factor reduction
                    F_sh_dif_obs = (
                        view_factor_sky_no_obstacles - F_w_ob
                    ) / view_factor_sky_no_obstacles

                # The impact of obstacles on ground reflected irradiance is difficult to calculate
                # as there is no defined reference ground distance to determine shading impact.
                # A reflected shading reduction factor of 1 is therefore assumed for obstacles
                # on the assumption that any ground reflected irradiance lost will be offset by
                # diffuse reflectance from the obstacle.
                F_sh_ref_obs = 1.0

                # Keep the smallest of the three shading reduction factors as the
                # diffuse or reflected shading factor. Also enforce that these cannot be
                # negative (which may happen with some extreme tilt values)
                # TODO Add setback shading factors to the arguments to min function when
                #      definitions of P1 and P2 in formula for F_w_r have been confirmed.
                # F_sh_dif = max(0.0, min(F_sh_dif_setback, F_sh_dif_fins, F_sh_dif_overhangs))
                # F_sh_ref = max(0.0, min(F_sh_ref_setback, F_sh_ref_fins, F_sh_ref_overhangs))
                F_sh_dif = max(0.0, min(F_sh_dif_fins, F_sh_dif_overhangs, F_sh_dif_obs))
                F_sh_ref = max(0.0, min(F_sh_ref_fins, F_sh_ref_overhangs, F_sh_ref_obs))

            diffuse_factor = (
                F_sh_dif * (diffuse_irr_sky + diffuse_irr_hor) + F_sh_ref * diffuse_irr_ref
            ) / diffuse_irr_total

            diffuse_factors.append(diffuse_factor)

        diffuse_factor = min(diffuse_factors)
        diffuse_factor = min(diffuse_factor, remote_obstacles_diffuse_factor)

        return diffuse_factor

    def shading_reduction_factor_direct_diffuse(
        self,
        base_height: float,
        height: float,
        width: float,
        tilt: float,
        orientation: Orientation360,
        window_shading: list[dict[str, Any]],
    ) -> tuple[float, float]:
        """calculates the direct and diffuse shading factors due to external
        shading objects

        Arguments:
        base_height    -- is the base height of the shaded surface k, in m
        height         -- is the height of the shaded surface (if surface is tilted then
                          this must be the vertical projection of the height), in m
        width          -- is the width of the shaded surface, in m
        tilt           -- is the tilt angle of the inclined surface from horizontal, measured
                          upwards facing, 0 to 180, in degrees;
        orientation    -- is the orientation angle of the inclined surface, expressed as the
                          geographical azimuth angle of the horizontal projection of the
                          inclined surface normal, 0 to 360, in degrees;
        window_shading -- data on overhangs and side fins associated to this building element
                          includes the shading object type, depth, and distance from element
        """
        # first chceck if there is any radiation. This is needed to prevent a potential
        # divide by zero error in the final step, but also, if there is no radiation
        # then shading is irrelevant and we can skip the whole calculation

        direct, diffuse, _, diffuse_breakdown = self.calculated_direct_diffuse_total_irradiance(
            tilt=tilt, orientation=orientation, diffuse_breakdown=True
        )
        if diffuse_breakdown is None:
            raise ValueError(
                "diffuse_breakdown not calculated by self.calculated_direct_diffuse_total_irradiance."
            )

        if direct + diffuse == 0:
            return 0.0, 0.0

        window_shading_expanded = []
        if window_shading:
            for shading_obj in window_shading:
                if shading_obj["type"] == WindowShadingType.REVEAL:
                    window_shading_expanded.append(
                        {
                            "type": WindowShadingType.OVERHANG,
                            "depth": shading_obj["depth"],
                            "distance": shading_obj["distance"],
                        }
                    )
                    window_shading_expanded.append(
                        {
                            "type": WindowShadingType.SIDEFINLEFT,
                            "depth": shading_obj["depth"],
                            "distance": shading_obj["distance"],
                        }
                    )
                    window_shading_expanded.append(
                        {
                            "type": WindowShadingType.SIDEFINRIGHT,
                            "depth": shading_obj["depth"],
                            "distance": shading_obj["distance"],
                        }
                    )
                else:
                    window_shading_expanded.append(shading_obj)

        # first check if the surface is outside the solar beam
        # if so then direct shading is complete and we don't need to
        # calculate shading from objects
        # TODO The outside solar beam condition is based on a vertical projection
        #      of the surface and does not account for the condition where a
        #      surface that is only slightly pitched is exposed to direct solar
        #      radiation when the sun is high (e.g. a surface pitched slightly
        #      to the north will be exposed to direct solar radiation when the
        #      sun is high in the southern sky). As the solar radiation
        #      calculation already accounts for the situation where the sun is
        #      actually behind the surface (accounting for the combination of
        #      orientation and pitch), there is no need to zero it using the
        #      shading factor. For now, we set the shading factor to 1 and ignore
        #      shading from objects on the other side of the building (which if
        #      significantly pitched would have to be relatively tall and/or
        #      very close to cast a shadow on the surface in question anyway),
        #      so that results in the unshaded case will be correct.
        if self.outside_solar_beam(tilt=tilt, orientation=orientation):
            direct_shading_reduction_factor = 1.0
        else:
            direct_shading_reduction_factor = self.direct_shading_reduction_factor(
                base_height=base_height,
                height=height,
                width=width,
                orientation=orientation,
                window_shading=window_shading_expanded,
            )

        f_sky = sky_view_factor(pitch=tilt)
        diffuse_shading_factor = self.diffuse_shading_reduction_factor(
            diffuse_breakdown=diffuse_breakdown,
            tilt=tilt,
            height=height,
            base_height=base_height,
            width=width,
            orientation=orientation,
            window_shading=window_shading_expanded,
            f_sky=f_sky,
        )

        return direct_shading_reduction_factor, diffuse_shading_factor

        # TODO suspected bug identified in ISO 52016 as it conflicts with ISO 52010:
        # ISO 52010 states that (6.4.5.2.1) the total irradiance on the inclined surface is
        # Itotal = Fdir * Idirect + Idiffuse
        # This is how the shading factor is used with the solar gains calculation.
        # However, ISO 52016 takes Fdir and performs the calculation below to give a "final"
        # shading factor. This does not make sense to be applied solely to the direct radiation
        # when calculating solar gains. Therefore we return Fdir here.

        # Fshade = (Fdir * direct + diffuse) / (direct + diffuse)

        # return Fshade

    def surface_irradiance(
        self,
        base_height: float,
        projected_height: float,
        width: float,
        tilt: float,
        orientation: Orientation360,
        window_shading: list[dict[str, Any]],
    ) -> float:
        i_sol_dir, i_sol_dif, _, _ = self.calculated_direct_diffuse_total_irradiance(
            tilt=tilt, orientation=orientation, diffuse_breakdown=False
        )

        direct_shading_factor, diffuse_shading_factor = (
            self.shading_reduction_factor_direct_diffuse(
                base_height=base_height,
                height=projected_height,
                width=width,
                tilt=tilt,
                orientation=orientation,
                window_shading=window_shading,
            )
        )
        return i_sol_dif * diffuse_shading_factor + i_sol_dir * direct_shading_factor

    def sun_above_horizon(self) -> bool:
        solar_angle = self.solar_angle_of_incidence(tilt=0, orientation=Orientation360(180))
        return solar_angle < 90.0


def create_external_conditions(
    external_conditions: dict, simtime: SimulationTime
) -> ExternalConditions:
    # TODO Some inputs are not currently used, so set to None here rather
    #      than requiring them in input file.
    # TODO Read timezone from input file. For now, set timezone to 0 (GMT)
    # Let direct beam conversion input be optional, this will be set if comes from weather file.
    if external_conditions["direct_beam_conversion_needed"]:
        dir_beam_conversion = external_conditions["direct_beam_conversion_needed"]
    else:
        dir_beam_conversion = False

    def convert_shading(shading_segments):
        for element in shading_segments:
            element["start360"] = Orientation360(element["start360"])
            element["end360"] = Orientation360(element["end360"])
        return shading_segments

    return ExternalConditions(
        simulation_time=simtime,
        air_temps=external_conditions["air_temperatures"],
        wind_speeds=external_conditions["wind_speeds"],
        wind_directions=[
            Orientation360(direction) for direction in external_conditions["wind_directions"]
        ],
        diffuse_horizontal_radiation=external_conditions["diffuse_horizontal_radiation"],
        direct_beam_radiation=external_conditions["direct_beam_radiation"],
        solar_reflectivity_of_ground=external_conditions["solar_reflectivity_of_ground"],
        latitude=external_conditions["latitude"],
        longitude=external_conditions["longitude"],
        timezone=0,  # external_conditions['timezone'],
        start_day=0,  # external_conditions['start_day'],
        end_day=365,  # external_conditions['end_day'],
        time_series_step=1,  # external_conditions['time_series_step'],
        january_first=None,  # external_conditions['january_first'],
        daylight_savings=None,  # external_conditions['daylight_savings'],
        leap_day_included=None,  # external_conditions['leap_day_included'],
        direct_beam_conversion_needed=dir_beam_conversion,
        shading_segments=convert_shading(external_conditions["shading_segments"])
        if "shading_segments" in external_conditions
        else None,
    )


def sky_view_factor(pitch: float) -> float:
    """Calculate longwave sky view factor from pitch in degrees"""
    # TODO account for shading
    # TODO check longwave is correct
    pitch_rads = pitch * pi / 180
    return 0.5 * (1 + cos(pitch_rads))
