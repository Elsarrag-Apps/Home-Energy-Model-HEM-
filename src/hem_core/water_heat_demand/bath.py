#!/usr/bin/env python3

"""
This module provides objects to model showers of different types.
"""

from typing import Any

from hem_core.water_heat_demand.cold_water_source import ColdWaterSource

# Local imports
from hem_core.water_heat_demand.misc import (
    CallableGetHotWaterTemperature,
    volume_hot_water_required,
)


class Bath:
    """An object to model a bath"""

    def __init__(self, size: float, cold_water_source: ColdWaterSource, flowrate: float):
        """Construct a Bath object

        Arguments:
        size            -- bath size in litres - may not be needed but here but retained for flexibility
        cold_water_feed -- reference to ColdWaterSource object representing the
                           cold water feed attached to the shower
        flowrate        -- tap/outlet flow rate, in litres/minute
        """
        self.__bathsize = size  # TODO entire capacity or typical usage?
        self.__cold_water_source = cold_water_source
        self.__flowrate = flowrate

    def get_cold_water_source(self) -> ColdWaterSource:
        return self.__cold_water_source

    def hot_water_demand(
        self, event: dict, func_temp_hot_water: CallableGetHotWaterTemperature
    ) -> tuple[Any | None, float, float]:
        """Calculate volume of hot water required

        (and volume of warm water draining to WWHRS, if applicable)

        Arguments:
        temp_target           -- temperature of warm water delivered at tap, in Celcius
        """
        peak_flowrate = self.__flowrate
        if "volume" in event.keys():
            vol_warm_water = event["volume"]
            bath_duration = event["volume"] / peak_flowrate
            event["duration"] = bath_duration
        elif "duration" in event.keys():
            bath_duration = event["duration"]
            vol_warm_water = bath_duration * peak_flowrate
        else:
            raise ValueError(
                f"Invalid bath event ({event}). Must specify either volume or duration"
            )
        temp_target = event["temperature"]

        vol_warm_water = min(vol_warm_water, self.__bathsize)
        vol_hot_water = volume_hot_water_required(
            volume_warm_water=vol_warm_water,
            temperature_target=temp_target,
            func_temperature_hot_water=func_temp_hot_water,
            func_temperature_cold_water=self.__cold_water_source.get_temp_cold_water,
        )
        if vol_hot_water is not None:
            vol_cold_water = vol_warm_water - vol_hot_water
            self.__cold_water_source.draw_off_water(volume_needed=vol_cold_water)

        return vol_hot_water, vol_warm_water, bath_duration  # litres and minutes
