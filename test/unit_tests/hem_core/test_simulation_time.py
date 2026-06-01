#!/usr/bin/env python3

"""
This module contains unit tests for the simulation_time module
"""

# Standard library imports
import unittest

# Local imports
from hem_core.simulation_time import SimulationTime, create_simulation_time


class TestSimulationTime(unittest.TestCase):
    """Unit tests for SimulationTime class"""

    def setUp(self):
        """Create SimulationTime object to be tested"""
        self.timestep = 0.5
        self.simtime = SimulationTime(start_time=742, end_time=746, step=self.timestep)

    def test_timestep(self):
        """Test that SimulationTime object returns correct timestep"""
        self.assertEqual(self.simtime.timestep(), self.timestep, "incorrect timestep returned")

    def test_time_series_idx(self):
        """Test that time_series_idx() raises an error if the index is negative"""
        with self.assertRaises(ValueError):
            self.simtime.time_series_idx(750, 1)

    def test_total_steps(self):
        """Test that total steps has been calculated correctly"""
        self.assertEqual(self.simtime.total_steps(), 8, "incorrect total steps")

    def test_total_steps_based_on_step(self):
        """Test that total_steps_based_on_step returns the correct value"""
        simtime = SimulationTime(start_time=720, end_time=724, step=self.timestep)
        self.assertEqual(simtime.total_steps_based_on_step(start_day=30, step=1), 4)
        self.assertEqual(simtime.total_steps_based_on_step(start_day=30), 8)

    def test_total_steps_based_on_step_invalid_start_day(self):
        """Test that total_steps_based_on_step raises an error if start_day is after the simulation start"""
        with self.assertRaises(ValueError):
            self.simtime.total_steps_based_on_step(start_day=31, step=1)

    def test_iteration(self):
        """Test that SimulationTime object works as an iterator"""
        # Call to iter() should return reference to same object
        simtime_iter = iter(self.simtime)
        self.assertIs(simtime_iter, self.simtime)

        # Check figures returned in each iteration
        for i in range(0, 8):
            with self.subTest(i=i):
                # Check that call to next() returns correct index and current time
                self.assertEqual(
                    next(simtime_iter),
                    (i, i * self.timestep + 742, self.timestep),
                    "incorrect loop vars returned",
                )

                # Check that individual functions also return correct index and current time
                self.assertEqual(
                    self.simtime.current(),
                    742 + i * self.simtime.timestep(),
                    "incorrect current time returned",
                )
                self.assertEqual(self.simtime.index(), i, "incorrect ordinal index returned")
                self.assertEqual(
                    self.simtime.current_hour(),
                    [742, 742, 743, 743, 744, 744, 745, 745][i],
                    "incorrect current hour returned",
                )
                self.assertEqual(
                    self.simtime.hour_of_day(),
                    [22, 22, 23, 23, 0, 0, 1, 1][i],
                    "incorrect hour of day returned",
                )
                self.assertEqual(
                    self.simtime.current_day(),
                    [30, 30, 30, 30, 31, 31, 31, 31][i],
                    "incorrect current day returned",
                )
                self.assertEqual(
                    self.simtime.time_series_idx(start_day=0, time_series_step=1),
                    [742, 742, 743, 743, 744, 744, 745, 745][i],
                    "incorrect time series index returned",
                )
                self.assertEqual(
                    self.simtime.current_month(),
                    [0, 0, 0, 0, 1, 1, 1, 1][i],
                    "incorrect current month returned",
                )
                self.assertEqual(
                    self.simtime.current_month_start_end_hour(),
                    [
                        (0, 744),
                        (0, 744),
                        (0, 744),
                        (0, 744),
                        (744, 1416),
                        (744, 1416),
                        (744, 1416),
                        (744, 1416),
                    ][i],
                    "incorrect start and end hours for current month returned",
                )

        # Once all timesteps have been iterated over, next increment should raise exception
        with self.assertRaises(StopIteration):
            next(simtime_iter)

    def test_time_series_idx_days(self):
        """Test that time_series_idx_days returns the correct day and switches at 9PM"""
        simtime = SimulationTime(start_time=24, end_time=48, step=0.5)

        for i in range(24 * 2):
            with self.subTest(i=i):
                next(simtime)
                self.assertEqual(simtime.time_series_idx_days(start_day=0), 1 if i < 21 * 2 else 2)

    def test_create_simulation_time(self):
        """Test that a simulation time object is created correctly from a dict"""
        simtime = create_simulation_time({"start": 10, "end": 20, "step": 5})

        self.assertEqual(simtime._SimulationTime__start_time, 10)  # type: ignore[AttributeAccessIssue]
        self.assertEqual(simtime._SimulationTime__end_time, 20)  # type: ignore[AttributeAccessIssue]
        self.assertEqual(simtime._SimulationTime__step, 5)  # type: ignore[AttributeAccessIssue]
