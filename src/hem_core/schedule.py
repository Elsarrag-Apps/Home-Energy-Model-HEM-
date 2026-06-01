"""
This module provides ways to define schedules which can be expressed concisely
and built from sub-schedules (e.g. construct a weekly schedule from daily schedules)
in input files.
"""

from math import floor
from typing import Any, Sequence

ScheduleEntry = bool | float | int | str | dict[str, Any] | None

EventSchedule = dict[int, Any]

Schedule = list[bool | float | int | None]


def expand_schedule(
    sched_type: type[bool | float | int],
    sched_dict: dict[str, list[ScheduleEntry]],
    sched_main: str,
    nullable: bool,
) -> Schedule:
    """Construct a schedule from direct entries or sub-schedules.

    Arguments:
    sched_type -- the type of value contained within the schedule (e.g. bool or
                  float), which cannot be a string or a dict
    sched_dict -- dictionary of schedules (lists) where each schedule element
                  can be either:
                  - a string referencing the name of another schedule in
                    sched_dict
                  - a dict with 'value' and 'repeat' fields, denoting that the
                    value in the 'value' field is repeated the number of times
                    given in the 'repeat field'
                  - a value of the type given in the sched_type argument
    sched_main -- name of main top-level schedule in sched_dict where processing
                  should start
    nullable -- flag denoting whether null values are allowed (True) or not (False)
    """
    if sched_type is dict or sched_type is str:
        # Exit with error if specified value type is dict or string, as these have special meanings
        raise ValueError("Schedule type cannot be dict or string")
        # TODO Exit just the current case instead of whole program entirely?

    def process_schedule_entry(sched_entry: ScheduleEntry) -> Schedule:
        """Process a single schedule entry"""
        if isinstance(sched_entry, str):
            # If entry is a string, look up sub-schedule with name given by the string
            return process_schedule_entries(sched=sched_dict[sched_entry])
        elif isinstance(sched_entry, dict):
            # If entry is a dict, repeat 'value' element number of times given in 'repeat' element
            # Note that the variable val below is a list
            val = process_schedule_entry(sched_entry=sched_entry["value"])
            return val * sched_entry["repeat"]
        elif (
            isinstance(sched_entry, sched_type)
            or (isinstance(sched_entry, int) and sched_type is float)
        ) or (nullable and sched_entry is None):
            # If entry is a value of the expected type (e.g. bool or float), store as-is
            # Note: must return a list here, to be consistent with the other returns from this func
            return [sched_entry]
        else:
            # If entry is of an unexpected type, exit with error message
            raise ValueError(
                f"Invalid type ({type(sched_entry)}) in schedule entry. Expected {sched_type})"
            )

    def process_schedule_entries(sched: list[ScheduleEntry]) -> Schedule:
        """Process all entries in a schedule (list)"""
        sched_expanded = []
        for sched_entry in sched:
            sched_expanded.extend(process_schedule_entry(sched_entry=sched_entry))
        return sched_expanded

    return process_schedule_entries(sched=sched_dict[sched_main])


def expand_events(
    event_list: list[dict[str, Any]],
    sim_timestep: int | float,
    tot_timesteps: int,
    name: str,
    event_type: str,
    schedule: EventSchedule,
) -> EventSchedule:
    """Construct or update a schedule from a list of events, appending the event type to each event and
        ensuring events are ordered by 'start' time within each timestep.

    Arguments:
    event_list        -- list of event dictionaries, where the 'start' element gives
                         the start time of the event, in hours from the start of the simulation
    sim_timestep      -- length of simulation timestep, in hours
    tot_timesteps     -- total number of timesteps in the simulation
    event_type        -- type of the events being processed (e.g., "Shower", "Bath", "Others")
    schedule          -- the existing schedule dictionary to update
    """

    for event in event_list:
        starting_timestep = floor(event["start"] / sim_timestep)

        if 0 <= starting_timestep < tot_timesteps:
            event_with_type_name = event.copy()
            event_with_type_name["type"] = event_type
            event_with_type_name["name"] = name

            existing_events = schedule.get(starting_timestep)

            if not existing_events:
                schedule[starting_timestep] = [event_with_type_name]
            else:
                # Insert the event into the correct position to maintain order by 'start' time
                inserted = False
                for i, existing_event in enumerate(existing_events):
                    if existing_event["start"] > event_with_type_name["start"]:
                        existing_events.insert(i, event_with_type_name)
                        inserted = True
                        break
                if not inserted:
                    existing_events.append(event_with_type_name)

    return schedule


def validate_schedule_length(schedule: Sequence[Any], expected_length: int):
    """Validate a schedule length to avoid running out of values during the simulation"""
    if len(schedule) < expected_length:
        raise ValueError(
            f"Schedule length is less than the expected length ({len(schedule)} / {expected_length})."
        )
