"""
This module provides objects to represent the source(s) of cold water.
"""

from hem_core.heating_systems import WaterSupplyBase
from hem_core.simulation_time import SimulationTime


class ColdWaterSource(WaterSupplyBase):
    """An object to represent a source of cold water"""

    def __init__(
        self,
        cold_water_temps: list[float],
        simulation_time: SimulationTime,
        start_day: int,
        time_series_step: float,
    ):
        """Construct a ColdWaterSource object
        Args:
            cold_water_temps: list of cold water temperatures, in deg C (one entry per hour)
            simulation_time: reference to SimulationTime object
            start_day: first day of the time series, day of the year, 0 to 365 (single value)
            time_series_step: timestep of the time series data, in hours
        """
        self.__cold_water_temps = cold_water_temps
        self.__simulation_time = simulation_time
        self.__start_day = start_day
        self.__time_series_step = time_series_step

    def get_temp_cold_water(self, volume_needed: float) -> list[tuple[float, float]]:
        """Return the cold water temperature and volume for the current timestep"""
        # volume_needed -- added for compatibility with other pre-heated sources such as storage tanks
        temperature = self.__cold_water_temps[
            self.__simulation_time.time_series_idx(
                start_day=self.__start_day, time_series_step=self.__time_series_step
            )
        ]
        return [(temperature, volume_needed)]

    def draw_off_water(self, volume_needed: float) -> list[tuple[float, float]]:
        return self.get_temp_cold_water(volume_needed=volume_needed)
