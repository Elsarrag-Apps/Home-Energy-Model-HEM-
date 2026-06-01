#!/usr/bin/env python3

"""
This module contains unit tests for the schedule module
"""

# Standard library imports
import unittest

# Local imports
from hem_core.schedule import expand_events, expand_schedule, validate_schedule_length


class TestSchedule(unittest.TestCase):
    """Unit tests for schedule module"""

    def setUp(self):
        """Define schedules to be used in tests"""

        # Concise boolean schedule input (e.g. for heating time control) to be
        # expanded into full schedule
        self.schedule = {
            "main": [
                {"value": "weekday", "repeat": 5},
                "weekend",
                "weekend",
            ],
            "weekday": [
                {"value": False, "repeat": 7},
                {"value": True, "repeat": 2},
                {"value": False, "repeat": 7},
                {"value": True, "repeat": 7},
                False,
            ],
            "weekend": [
                {"value": False, "repeat": 7},
                {"value": True, "repeat": 16},
                False,
            ],
        }

        # Expanded boolean schedule (one item per hour)
        self.schedule_expanded = [
            # Weekday schedule (Mon)
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            True,
            True,
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            False,
            # Weekday schedule (Tue)
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            True,
            True,
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            False,
            # Weekday schedule (Wed)
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            True,
            True,
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            False,
            # Weekday schedule (Thu)
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            True,
            True,
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            False,
            # Weekday schedule (Fri)
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            True,
            True,
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            False,
            # Weekend schedule (Sat)
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            False,
            # Weekend schedule (Sun)
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            False,
        ]

    def test_expand_schedule(self):
        """Test that schedule is expanded correctly"""
        self.maxDiff = None
        # Run the concise schedule through the expand_schedule function and
        # check it matches the expanded schedule as expected
        self.assertEqual(
            expand_schedule(
                sched_type=bool, sched_dict=self.schedule, sched_main="main", nullable=False
            ),
            self.schedule_expanded,
            "incorrect schedule expansion",
        )

    def test_validate_schedule_length(self):
        """Test that validate_schedule_length raises an error if the schedule length is less than the expected length"""
        with self.assertRaises(ValueError):
            validate_schedule_length(schedule=[0.0, 0.1], expected_length=3)

    def test_expand_schedule_invalid_type(self):
        """Test that expand_schedule throws on an invalid schedule type"""
        with self.assertRaises(ValueError):
            expand_schedule(
                sched_type=dict,  # type: ignore[dict] - used to test error handling
                sched_dict=self.schedule,
                sched_main="main",
                nullable=False,
            )
        with self.assertRaises(ValueError):
            expand_schedule(
                sched_type=str,  # type: ignore[str] - used to test error handling
                sched_dict=self.schedule,
                sched_main="main",
                nullable=False,
            )

    def test_expand_schedule_with_nullable_allowed(self):
        """Test that Nones are allowed if nullable is True"""
        self.schedule["main"] = [{"value": None, "repeat": 2}]
        self.assertEqual(
            expand_schedule(
                sched_type=bool, sched_dict=self.schedule, sched_main="main", nullable=True
            ),
            [None, None],
        )

    def test_expand_schedule_with_nullable_not_allowed(self):
        """Test that Nones are not allowed if nullable is False"""
        self.schedule["main"] = [{"value": None, "repeat": 2}]
        with self.assertRaises(ValueError):
            expand_schedule(
                sched_type=bool, sched_dict=self.schedule, sched_main="main", nullable=False
            )

    def test_expand_events(self):
        """Test that list of events is expanded into schedule correctly"""
        events = [
            {"start": 2, "duration": 6},
            {"start": 2.2, "duration": 6},
            {"start": 3, "duration": 6},
            {"start": 2.1, "duration": 6},
        ]
        simulation_timestep = 0.5
        total_timesteps = 10
        schedule = {
            0: [],
            1: [],
            2: [],
            3: [],
            4: [
                {"start": 2, "duration": 6, "type": "event_type", "name": "name"},
                {"start": 2.1, "duration": 6, "type": "event_type", "name": "name"},
                {"start": 2.2, "duration": 6, "type": "event_type", "name": "name"},
            ],
            5: [],
            6: [{"start": 3, "duration": 6, "type": "event_type", "name": "name"}],
            7: [],
            8: [],
            9: [],
        }
        # Run the list of events through the expand_events function and check it
        # matches the event schedule expected
        schedule_to_test = {t_idx: [] for t_idx in range(total_timesteps)}
        # schedule_to_test = expand_events(events, simulation_timestep, total_timesteps, "name", "event_type", schedule_to_test)
        # print(schedule_to_test)
        self.assertEqual(
            expand_events(
                event_list=events,
                sim_timestep=simulation_timestep,
                tot_timesteps=total_timesteps,
                name="name",
                event_type="event_type",
                schedule=schedule_to_test,
            ),
            schedule,
            "incorrect expansion of event list to schedule",
        )
