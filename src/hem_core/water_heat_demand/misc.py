#!/usr/bin/env python3

"""
This module contains miscellaneous free functions related to water heat demand.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass

import hem_core.material_properties as material_properties

# Fraction of domestic hot water energy that becomes internal gains
# This applies to both hot water usage and combi boiler losses
FRAC_DHW_ENERGY_INTERNAL_GAINS = 0.25


CallableGetHotWaterTemperature = Callable[[float], float]


@dataclass(frozen=True)
class WaterEventResult:
    """Result of processing a single water use event."""

    # Type of event
    type: str  # TODO Convert to enum: Shower, Bath, Other, PipeFlush

    # Temperature of water at outlet (Celsius)
    temperature_warm: float

    # Volume of water at outlet (litres)
    volume_warm: float

    # Hot water demand volume (litres)
    volume_hot: float

    # Duration of hot water event (minutes)
    event_duration: float

    def format_event(self) -> str:
        # Map event types to abbreviations
        abbreviations = {"Shower": "S", "Bath": "B", "Other": "O", "PipeFlush": "P"}

        hot_volume = self.volume_hot
        warm_volume = self.volume_warm
        temperature = self.temperature_warm
        abbrev = abbreviations.get(self.type, "?")
        # TODO Consolidate rounding to 10 significant figures below with rounding of other values
        #      in hem.py CsvWriter class. Requires wider refactoring to avoid circular imports.
        return f"{abbrev}: {hot_volume:.10g} ({warm_volume:.10g} @ {temperature:.10g})"


def summarise_events(events: list[WaterEventResult]) -> str:
    if events is None:
        return ""  # pragma: no cover

    # Generate the summary in the desired format
    condensed = " | ".join([e.format_event() for e in events])

    return condensed


def calc_fraction_hot_water(
    temperature_target: float, temperature_hot: float, temperature_cold: float
) -> float:
    """Calculate the fraction of hot water required when mixing hot and cold
    water to achieve a target temperature

    Arguments:
    temperature_target -- temperature to be achieved, in any units
    temperature_hot    -- temperature of hot water to be mixed, in same units as temp_target
    temperature_cold   -- temperature of cold water to be mixed, in same units as temp_target
    """
    fraction = (temperature_target - temperature_cold) / (temperature_hot - temperature_cold)
    if (fraction < 0.0 and not math.isclose(fraction, 0.0, abs_tol=1e-10)) or (
        fraction > 1.0 and not math.isclose(fraction, 1.0, abs_tol=1e-10)
    ):
        raise ValueError(
            f"Cannot achieve temperature {temperature_target} by mixing "
            f"water at {temperature_cold} and {temperature_hot}"
        )
    return fraction


def water_demand_to_kWh(
    litres_demand: float, demand_temperature: float, cold_temperature: float
) -> float:
    """
    Calculates the kWh energy content of the hot water demand.

    Arguments:
    litres_demand       -- hot water demand in litres
    demand_temperature  -- temperature of hot water inside the pipe, in degrees C
    cold_temperature    -- temperature outside the pipe, in degrees C
    """
    kWh_demand = (
        material_properties.WATER.volumetric_energy_content_kWh_per_litre(
            temp_high=demand_temperature, temp_base=cold_temperature
        )
        * litres_demand
    )

    return kWh_demand


def volume_hot_water_required(
    volume_warm_water: float,
    temperature_target: float,
    func_temperature_hot_water: Callable[[float], float],
    func_temperature_cold_water: Callable[[float], list[tuple[float, float]]],
) -> float | None:
    temperature_hot_water = func_temperature_hot_water(volume_warm_water * 0.5)
    list_temperature_volume = func_temperature_cold_water(volume_warm_water * 0.5)
    temperature_cold_water = math.fsum(t * v for t, v in list_temperature_volume) / math.fsum(
        v for _, v in list_temperature_volume
    )
    temperature_warm_water = temperature_hot_water
    volume_hot_water = None
    while not math.isclose(temperature_warm_water, temperature_target, abs_tol=1e-10):
        # Calculate the volume of hot/cold water needed if heating from cold water source
        if temperature_target > temperature_hot_water:
            return None
        volume_hot_water = volume_warm_water * calc_fraction_hot_water(
            temperature_target=temperature_target,
            temperature_hot=temperature_hot_water,
            temperature_cold=temperature_cold_water,
        )
        volume_cold_water = volume_warm_water - volume_hot_water
        # Calculate the temperature of hot and warm (mixed) water given the volumes calculated
        temperature_hot_water = func_temperature_hot_water(volume_hot_water)
        list_temperature_volume = func_temperature_cold_water(volume_cold_water)
        temperature_cold_water = math.fsum(t * v for t, v in list_temperature_volume) / math.fsum(
            v for _, v in list_temperature_volume
        )
        temperature_warm_water = (
            volume_hot_water * temperature_hot_water + volume_cold_water * temperature_cold_water
        ) / volume_warm_water
    return volume_hot_water


def calculate_volume_weighted_average_temperature(
    temp_volume_pairs: list[tuple[float, float]],
    expected_volume: float | None = None,
    tolerance: float = 1e-10,
) -> float:
    """Calculate volume-weighted average temperature from list of (temperature, volume) pairs.

    Args:
        temp_volume_pairs: List of (temperature, volume) tuples
        expected_volume: Expected total volume. If provided, validates that actual total matches.
        tolerance: Tolerance for volume validation (absolute tolerance)

    Returns:
        Volume-weighted average temperature

    Raises:
        ValueError: If temp_volume_pairs is empty, total volume is zero, or
                   actual volume doesn't match expected volume
    """
    if not temp_volume_pairs:
        raise ValueError("Cannot calculate weighted average: temp_volume_pairs is empty")

    temp_volume_products = []
    volumes = []

    for temp, volume in temp_volume_pairs:
        temp_volume_products.append(temp * volume)
        volumes.append(volume)

    weighted_temp_sum = math.fsum(temp_volume_products)
    total_volume = math.fsum(volumes)

    if math.isclose(total_volume, 0.0, abs_tol=1e-10):
        raise ValueError("Cannot calculate weighted average: total volume is zero")

    # Validate expected volume if provided
    if expected_volume is not None:
        if not math.isclose(total_volume, expected_volume, abs_tol=tolerance):
            raise ValueError(
                f"Volume mismatch: expected {expected_volume}, got {total_volume}. "
                f"This indicates an error in the cold water source implementation."
            )

    return weighted_temp_sum / total_volume
