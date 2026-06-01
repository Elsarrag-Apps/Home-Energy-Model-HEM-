#!/usr/bin/env python3

"""
This module contains object(s) to track and control information on the
simulation timestep.
"""

# Standard library imports
import datetime
import math

# Local imports
import hem_core.units as units


class SimulationTime:
    """An iterator object to track properties relating to the simulation timestep

    This object is a "single source of truth" for information on timesteps, and it controls
    incrementing the timestep. It can be queried by other objects that have references to it.
    """

    # TODO Re-write this class in terms of datetime and timedelta objects
    # TODO Add options to return timestep (timedelta) in particular units
    #      (e.g. seconds, minutes or hours)
    # TODO Account for GMT/BST switchover

    def __init__(self, start_time: float, end_time: float, step: float):
        """Construct a SimulationTime object

        Arguments:
        start_time -- The start time of the simulation, in hours from the start of the year
        end_time   -- The end time of the simulation, in hours from the start of the year
        step      -- The time increment for each step of the calculation, in hours

        Other variables:
        current             -- The current simulation time, in hours from the same
                            arbitrary zero point as start_time
        total_steps         -- Number of timesteps in simulation
        index               -- Number of timesteps already run (i.e. zero-based ordinal
                            enumeration of current timestep)
        first_iteration     -- True if there have been no iterations yet, False otherwise
        """

        self.__step = step
        self.__end_time = end_time
        self.__current = start_time
        self.__start_time = start_time

        self.__total_steps = math.ceil((end_time - start_time) / step)
        self.__index = 0

        self.__first_iteration = True

    def __iter__(self):
        """Return a reference to this object when an iterator is required"""
        return self

    def __next__(self):
        """Increment simulation timestep"""
        if self.__first_iteration:
            # If we are on the first iteration, don't increment counters, but
            # set flag to False for next iteration
            self.__first_iteration = False
        else:
            # Increment counters
            self.__index = self.__index + 1
            self.__current = self.__current + self.__step

        if self.__current >= self.__end_time:
            # If we have reached the end of the simulation, stop iteration
            raise StopIteration

        return self.__index, self.__current, self.timestep()

    def reset(self):
        """Reset the simulation time to the start time"""
        self.__current = self.__start_time
        self.__index = 0
        self.__first_iteration = True

    def current(self) -> float:
        """Return current simulation time"""
        return self.__current

    def index(self) -> int:
        """Return ordinal enumeration of current timestep"""
        return self.__index

    def current_hour(self) -> int:
        """Return current hour"""
        # Round down to remove fractions of hour
        return int(math.floor(self.__current))

    def hour_of_day(self) -> int:
        """Return hour of day (00:00-01:00 is hour zero)"""
        # TODO Assumes that self.__current == 0 is midnight - make this more flexible
        # Remainder from division by hours in day gives time relative to start of day
        time_of_day = self.__current % units.hours_per_day
        # Round down to remove fractions of hour
        return int(math.floor(time_of_day))

    def current_day(self) -> int:
        """Return current day (day 0 is 1st Jan)"""
        # Divide current time in hours by hours in day and round down to get current day
        # TODO Assumes that day 0 is 0 <= self.__current < 24 - make this more flexible
        return int(math.floor(self.__current / units.hours_per_day))

    def time_series_idx(self, start_day: int, time_series_step: float) -> int:
        """Calculate array lookup index"""
        # Index in array of time-series data is current hour (relative to start
        # of year) adjusted for the time-series step (in hours) and for the start day
        # (relative to start of year) of time-series data
        idx = math.floor((self.current() - start_day * units.hours_per_day) / time_series_step)
        if idx < 0:
            raise ValueError("Time series cannot start after the simulation.")
        return idx

    def time_series_idx_days(self, start_day: int, charge_calc_time: float = 21) -> int:
        """Calculate array lookup index

        charge_calc_time -- Indicates from which hour of the day the formula starts using the next day
                            instead of the current one
        """
        # Index in array of time-series data is current day (relative to start
        # of year) adjusted for the time-series step (in days) and for the start day
        # (relative to start of year) of time-series data

        if self.hour_of_day() >= charge_calc_time:
            return math.floor(self.current_day() + 1 - start_day)
        else:
            return math.floor(self.current_day() - start_day)

    def total_steps(self) -> int:
        """Return the total number of timesteps in simulation"""
        return self.__total_steps

    def total_steps_based_on_step(self, start_day: int, step: float | None = None) -> int:
        """Return the total number of timesteps in simulation based on custom step"""
        if start_day > self.current_day():
            raise ValueError("Time series cannot start after the simulation.")
        if step is None:
            step = self.__step
        return math.ceil((self.__end_time - start_day * units.hours_per_day) / step)

    def timestep(self) -> float:
        """Return the length of the current timestep, in hours"""
        return self.__step

    def current_month(self) -> int:
        """Return current month (0 for January, 11 for December)"""
        start_time = datetime.datetime(2023, 1, 1)  # Assuming a non-leap year (2023)
        time_delta = datetime.timedelta(hours=self.current_hour())
        result_time = start_time + time_delta
        return result_time.month - 1

    def current_month_start_end_hour(self) -> tuple[int, int]:
        """Return the hours upon which the current month starts and ends"""
        month = self.current_month()
        # Calculate the start hour
        start_hour = sum(units.days_in_month[:month]) * units.hours_per_day
        # Calculate the end hour
        end_hour = start_hour + units.days_in_month[month] * units.hours_per_day
        return start_hour, end_hour


def create_simulation_time(simulation_time_dict: dict):
    return SimulationTime(
        start_time=simulation_time_dict["start"],
        end_time=simulation_time_dict["end"],
        step=simulation_time_dict["step"],
    )
