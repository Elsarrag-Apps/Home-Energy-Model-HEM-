import pandas as pd

# Typical week numbers. Note week numbers count from 1 not 0 following the ISO standard.
# You can get the week number from a pandas datetime object with `datetime.dt.isocalendar().week`.
# typical winter week - starts midnight 5th Feb
typical_winter_week = 6
# typical summer week - starts midnight 16th July
typical_summer_week = 29
# typical transition week - starts 9th April
typical_transition_week = 15


def convert_timestep_to_datetime(timestep, start_timestep, step_size, year=2018):
    """
    Converts timestep into a pandas datetime object for easier date manipulation.

    The year is arbitrary - it is set to 2018 to match FHS wrapper assumptions that the year starts on a Monday and is not a leap year.

    You can use this datetime to calculate various date fields, including month, day of the week, whether a day is a weekday or not:
    week_of_the_year = datetime.dt.isocalendar().week
    # day_of_week = datetime.dt.isocalendar().day
    # weekday = datetime.dt.weekday
    # month = datetime.dt.month
    # day_of_the_week = datetime.dt.day_name

    Args:
        timestep: int pandas series: timestep output from the model
        start_timestep: int/float: first timestep as specified in the run dictionary e.g. `project_dict['SimulationTime']['start']`
        step_size: float: size of each timestep in hours as specified in the run dictionary, e.g. project_dict['SimulationTime']['step']
        year: int: year used for the datetime object. Defaults to 2018.

    Returns:
        pandas datetime series for the time at the end of each timestep with the year set to 2018

    """
    # convert timestep into hours from the beginning of the year
    timestep_hours = (start_timestep + timestep) * step_size

    # convert to datetime
    # calculated for the end of the timestep
    # using 2018 as it starts on a Monday and is not a leap year (consistent with FHS wrapper assumptions)
    # e.g. timestep 00:00 - 00:30 1st January would be recorded as 00:30 1/1/2018

    time_delta = pd.to_timedelta(timestep_hours + step_size, unit="hours")
    date_time = pd.to_datetime([f"{year}-01-01"])[0] + time_delta

    return date_time
