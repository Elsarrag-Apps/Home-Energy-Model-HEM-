#!/usr/bin/env python3

"""
This module provides objects to model other hot water uses (any draw from the tap)
"""

from hem_core.water_heat_demand.cold_water_source import ColdWaterSource

# Local imports
from hem_core.water_heat_demand.misc import (
    CallableGetHotWaterTemperature,
    volume_hot_water_required,
)
from hem_core.water_heat_demand.types import Event


class OtherHotWater:
    """An object to model all other hot water use"""

    def __init__(self, flowrate: float, cold_water_source: ColdWaterSource):
        """Construct a OtherHotWater object

        Arguments:
        flowrate            -- tap/outlet flow rate, in litres/minute
        cold_water_source   -- reference to ColdWaterSource object representing the
                               cold water feed attached to the shower
        """
        self.__flowrate = flowrate
        self.__cold_water_source = cold_water_source

    def get_cold_water_source(self) -> ColdWaterSource:
        return self.__cold_water_source

    def hot_water_demand(
        self, event: Event, func_temp_hot_water: CallableGetHotWaterTemperature
    ) -> tuple[float | None, float, float]:
        """Calculate volume of hot water required

        (and volume of warm water draining to WWHRS, if applicable)

        Arguments:
        event                   -- dict containing "temperature" and "duration" keys
                                    - temperature: temperature of warm water delivered at shower head, in Celsius
                                    - duration: cumulative running time of this shower during the current timestep, in minutes
        func_temp_hot_water     -- callable
        """
        total_demand_duration = event["duration"]
        temperature_target = event["temperature"]

        # TODO Account for behavioural variation factor fbeh
        volume_warm_water = self.__flowrate * total_demand_duration
        # ^^^ litres = litres/minute * minutes
        volume_hot_water = volume_hot_water_required(
            volume_warm_water=volume_warm_water,
            temperature_target=temperature_target,
            func_temperature_hot_water=func_temp_hot_water,
            func_temperature_cold_water=self.__cold_water_source.get_temp_cold_water,
        )
        if volume_hot_water is not None:
            volume_cold_water = volume_warm_water - volume_hot_water
            self.__cold_water_source.draw_off_water(volume_needed=volume_cold_water)

        return volume_hot_water, volume_warm_water, total_demand_duration
