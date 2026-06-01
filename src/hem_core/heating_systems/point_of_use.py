#!/usr/bin/env python3

"""
This module provides object(s) to model the behaviour of point of use heaters
"""

import math

import hem_core.water_heat_demand.misc as misc
from hem_core.energy_supply.energy_supply import EnergySupplyConnection
from hem_core.simulation_time import SimulationTime
from hem_core.water_heat_demand.cold_water_source import ColdWaterSource
from hem_core.water_heat_demand.misc import WaterEventResult


class PointOfUse:
    """Class to represent point of use water heaters"""

    def __init__(
        self,
        efficiency: float,
        energy_supply_conn: EnergySupplyConnection,
        simulation_time: SimulationTime,
        cold_feed: ColdWaterSource,
        temp_hot_water: float,
    ):
        """Construct an InstantElecHeater object

        Arguments:
        efficiency         -- efficiency of the heater, between 0 and 1
        energy_supply_conn -- reference to EnergySupplyConnection object
        simulation_time    -- reference to SimulationTime object
        cold_feed            -- reference to ColdWaterSource object
        """
        self.__efficiency = efficiency
        self.__energy_supply_conn = energy_supply_conn
        self.__simulation_time = simulation_time
        self.__cold_feed = cold_feed
        self.__temp_hot_water = temp_hot_water

    def get_cold_water_source(self) -> ColdWaterSource:
        return self.__cold_feed

    def get_temp_hot_water(
        self, volume_req: float, volume_req_already: float = 0.0
    ) -> list[tuple[float, float]]:
        # Always supplies the whole volume at the same temperature, so list has a single element
        return [(self.__temp_hot_water, volume_req)]

    def demand_hot_water(self, usage_events: list[WaterEventResult]) -> float:
        water_energy_demand = 0.0
        for event in usage_events:
            if math.isclose(event.volume_hot, 0.0, abs_tol=1e-10):
                continue
            list_temp_volume = self.__cold_feed.draw_off_water(volume_needed=event.volume_hot)
            temp_cold_water = math.fsum(t * v for t, v in list_temp_volume) / math.fsum(
                v for _, v in list_temp_volume
            )

            water_energy_demand += misc.water_demand_to_kWh(
                litres_demand=event.volume_hot,
                demand_temperature=self.__temp_hot_water,
                cold_temperature=temp_cold_water,
            )

        energy_used = self.demand_energy(energy_demand=water_energy_demand)

        # Assumption is that system specified has sufficient capacity to meet any realistic demand
        return energy_used

    def demand_energy(self, energy_demand: float) -> float:
        """Demand energy (in kWh) from the heater"""
        # Energy that heater is able to supply is limited by power rating
        fuel_demand = energy_demand * (1 / self.__efficiency)

        self.__energy_supply_conn.demand_energy(amount_demanded=fuel_demand)
        return fuel_demand
