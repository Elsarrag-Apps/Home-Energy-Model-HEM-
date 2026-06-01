#!/usr/bin/env python3

"""
This module provides objects to model showers of different types.
"""

import math

import hem_core.units as units
from hem_core.energy_supply.energy_supply import EnergySupplyConnection
from hem_core.heating_systems.wwhrs import WWHRS_Instantaneous
from hem_core.input_output.enums import WWHRSConfiguration
from hem_core.material_properties import WATER
from hem_core.water_heat_demand.cold_water_source import ColdWaterSource
from hem_core.water_heat_demand.misc import (
    CallableGetHotWaterTemperature,
    volume_hot_water_required,
)
from hem_core.water_heat_demand.types import Event


class MixerShower:
    """An object to model mixer showers i.e. those that mix hot and cold water"""

    def __init__(
        self,
        flowrate: float,
        cold_water_source: ColdWaterSource,
        wwhrs: WWHRS_Instantaneous | None = None,
        wwhrs_configuration: WWHRSConfiguration = WWHRSConfiguration.SHOWER_AND_WATER_HEATING_SYSTEM,
    ):
        """Construct a MixerShower object

        Arguments:
        flowrate            -- shower's flow rate, in litres/minute
        cold_water_source   -- reference to ColdWaterSource object representing the
                              cold water feed attached to the shower
        wwhrs              -- reference to WWHRS object (optional)
        wwhrs_configuration -- WWHRS system configuration ('A', 'B', or 'C') for this shower
        """
        self.__flowrate = flowrate
        self.__cold_water_source = cold_water_source
        self.__wwhrs = wwhrs
        self.__wwhrs_configuration = wwhrs_configuration.upper() if wwhrs else None

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
        total_shower_duration = event["duration"]
        temperature_target = event["temperature"]

        # TODO Account for behavioural variation factor fbeh
        volume_warm_water = self.__flowrate * total_shower_duration
        # ^^^ litres = litres/minute * minutes
        volume_hot_water = volume_hot_water_required(
            volume_warm_water=volume_warm_water,
            temperature_target=temperature_target,
            func_temperature_hot_water=func_temp_hot_water,
            func_temperature_cold_water=self.__cold_water_source.get_temp_cold_water,
        )
        # first calculate the volume of hot water needed if heating from cold water source

        if volume_hot_water is None:
            # Unmet demand
            return None, volume_warm_water, total_shower_duration

        volume_cold_water = volume_warm_water - volume_hot_water

        if self.__wwhrs is not None:
            temperature_hot_water = func_temp_hot_water(
                volume_hot_water
            )  # temperature of hot water supply, in Celsius

            # Use the unified WWHRS interface
            wwhrs_result = self.__wwhrs.calculate_performance(
                system_type=self.__wwhrs_configuration,
                temp_target=temperature_target,
                flowrate_waste_water=self.__flowrate,
                volume_cold_water=volume_cold_water,
                temp_hot=temperature_hot_water,
            )
            wwhrs_cyl_feed_temperature = wwhrs_result["T_cyl_feed"]
            volume_hot_water = wwhrs_result["flowrate_hot"] * total_shower_duration

            # Register pre-heated water availability for the hot water system.
            #
            # How WWHRS pre-heating works:
            # - Waste water (volume_warm_water) flows down the drain through the WWHRS
            # - Cold mains water flows through the other side of the heat exchanger
            # - The volume of water that can be pre-heated is limited by the waste water flow
            #
            # For System A: Pre-heated water feeds BOTH the shower's cold inlet AND the
            #   cylinder. The WWHRS calculation above already accounts for the shower
            #   receiving pre-heated water (reflected in the reduced volume_hot_water).
            #   We register the TOTAL volume of waste water as available for pre-heating,
            #   because all of it passes through the heat exchanger. The shower's cold
            #   water draw will consume part of this, leaving the remainder for the
            #   cylinder's draw.
            #
            # For System B: Pre-heated water feeds ONLY the shower's cold inlet, not the
            #   cylinder. No registration needed as cylinder gets mains temperature.
            #
            # For System C: Pre-heated water feeds ONLY the cylinder, not the shower.
            #   The shower draws mains-temperature cold water, so we register the full
            #   waste water volume as available for the cylinder.
            if self.__wwhrs_configuration == "B":
                # System B: only shower benefits, cylinder gets mains water
                # No registration needed - cylinder will draw from cold water source directly
                pass
            elif self.__wwhrs_configuration == "A":
                # System A: both shower and cylinder benefit from pre-heated water
                # Register the full volume of warm water going down the drain, as this
                # is the maximum volume that can be pre-heated while waste water flows.
                # The shower's cold water draw (below) will consume part of this volume,
                # leaving the remainder available for the cylinder.
                self.__wwhrs.register_preheated_volume(
                    temperature=wwhrs_cyl_feed_temperature,
                    volume=volume_warm_water,
                )
            elif self.__wwhrs_configuration == "C":
                # System C: only cylinder benefits, shower gets mains water
                # Register the full volume - shower won't draw from WWHRS (draws from
                # cold_water_source instead), so all pre-heated water is for cylinder.
                self.__wwhrs.register_preheated_volume(
                    temperature=wwhrs_cyl_feed_temperature,
                    volume=volume_warm_water,
                )
            else:
                raise ValueError(
                    f"Invalid WWHRS configuration: {self.__wwhrs_configuration}"
                )  # pragma: nocover

        volume_cold_water = volume_warm_water - volume_hot_water

        # Draw cold water for the shower.
        # For System A: draw from WWHRS (consumes pre-heated volume, remainder for cylinder)
        # For System B: draw from WWHRS (shower gets pre-heated water, but we didn't
        #               register any volume since cylinder doesn't benefit)
        # For System C: draw from cold_water_source (shower gets mains, cylinder gets
        #               pre-heated via the registered volume)
        if self.__wwhrs is not None and self.__wwhrs_configuration != "C":
            # Systems A and B: shower's cold feed comes through WWHRS
            self.__wwhrs.draw_off_water(volume_needed=volume_cold_water)
        else:
            # System C or no WWHRS: shower's cold feed comes from mains
            self.__cold_water_source.draw_off_water(volume_needed=volume_cold_water)

        return volume_hot_water, volume_warm_water, total_shower_duration


class InstantElecShower:
    """An object to model instantaneous electric showers

    i.e. those with an electric heating element that heats cold water to the
    desired temperature on-demand
    """

    def __init__(
        self,
        rated_power: float,
        cold_water_source: ColdWaterSource,
        elec_supply_conn: EnergySupplyConnection,
    ):
        """Construct an InstantElecShower object

        Arguments:
        rated_power      -- shower's rated electrical power, in kW
        cold_water_feed  -- reference to ColdWaterSource object representing
                            the cold water feed attached to the shower
        elec_supply_conn -- reference to EnergySupplyConnection object representing
                            the electricity supply attached to the shower
        """
        self.__pwr = rated_power
        # TODO Does the above account for target temperature? Presumably pwr
        #      stays constant while flow rate changes? Is this how modern
        #      electric showers work, or do they modulate their power output?
        self.__cold_water_source = cold_water_source
        self.__elec_supply_conn = elec_supply_conn

    def get_cold_water_source(self) -> ColdWaterSource:
        return self.__cold_water_source

    def hot_water_demand(
        self, event: Event, func_temp_hot_water: CallableGetHotWaterTemperature | None = None
    ) -> tuple[float, float, float]:
        """Calculate electrical energy required

        (and volume of warm water draining to WWHRS, if applicable)

        Arguments:
        event                   -- dict containing "temperature" and "duration" keys
                                    - temperature: temperature of warm water delivered at shower head, in Celsius
                                    - duration: cumulative running time of this shower during the current timestep, in minutes
        """
        total_shower_duration = event["duration"]
        temperature_target = event["temperature"]

        # TODO Account for behavioural variation factor fbeh
        electricity_demand = self.__pwr * (total_shower_duration / units.minutes_per_hour)
        # ^^^ kWh = kW * hours
        volume_warm_water = total_shower_duration * 6.0
        volume_warm_water_prev = 0.0
        while not math.isclose(volume_warm_water, volume_warm_water_prev, abs_tol=1e-10):
            list_temperature_volume = self.__cold_water_source.get_temp_cold_water(
                volume_needed=volume_warm_water
            )
            temperature_cold = math.fsum(t * v for t, v in list_temperature_volume) / math.fsum(
                v for _, v in list_temperature_volume
            )
            volume_warm_water_prev = volume_warm_water
            volume_warm_water = electricity_demand / WATER.volumetric_energy_content_kWh_per_litre(
                temp_high=temperature_target, temp_base=temperature_cold
            )

        self.__elec_supply_conn.demand_energy(amount_demanded=electricity_demand)

        # Instantaneous electric shower heats its own water, so no demand on
        # the water heating system.
        return 0.0, volume_warm_water, total_shower_duration
        # TODO Should this return hot water demand or send message to HW system?
        #      The latter would allow for different showers to be connected to
        #      different HW systems, but complicates the implementation of the
        #      HW system as it will have to deal with calls from several
        #      different objects and work out when to amalgamate the figures to
        #      do its own calculation, rather than being given a single overall
        #      figure for each timestep.
        # TODO Also send volume_warm_water to connected WWHRS object? Account for
        #      heat loss between shower head and drain?
