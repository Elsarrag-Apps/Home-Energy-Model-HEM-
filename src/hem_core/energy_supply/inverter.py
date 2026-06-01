"""
This module contains objects that represent photovoltaic systems.
"""

# Standard library imports
from __future__ import annotations

import numpy as np

# Local imports
from hem_core.energy_supply.energy_supply import EnergySupplyConnection
from hem_core.input_output.enums import InverterType
from hem_core.simulation_time import SimulationTime


class Inverter:
    """An object to represent an inverter.  Although primarily for PV systems this may have other uses e.g. wind turbine"""

    def __init__(
        self,
        energy_supply_conn: EnergySupplyConnection,
        simulation_time: SimulationTime,
        inverter_peak_power_dc: float,
        inverter_peak_power_ac: float,
        inverter_is_inside: bool,
        inverter_type: InverterType,
    ) -> None:
        """Construct an Inverter object

        Arguments:
        energy_supply_conn     -- reference to EnergySupplyConnection object
        simulation_time        -- reference to SimulationTime object
        inverter_peak_power_dc -- Peak power in kW; represents the peak electrical DC power input to the inverter
        inverter_peak_power_ac -- Peak power in kW; represents the peak electrical AC power output from the inverter
        inverter_is_inside     -- tells us that the inverter is considered inside the building
        inverter_type          -- type of inverter to help with calculation of efficiency of inverter when overshading
        """
        self.__energy_supply_conn = energy_supply_conn
        self.__simulation_time = simulation_time
        self.__inverter_peak_power_dc = inverter_peak_power_dc
        self.__inverter_peak_power_ac = inverter_peak_power_ac
        self.__inverter_is_inside = inverter_is_inside
        self.__inverter_type = inverter_type

    def type(self) -> InverterType:
        """Return the inverter type"""
        return self.__inverter_type

    def is_inside(self) -> bool:
        """Return whether this unit is considered inside the building or not"""
        return self.__inverter_is_inside

    def efficiency_power_ratio(self, power_input: float) -> float:
        """Returns the efficiency of the inverter calculated based on the ratio of input power to the dc capacity of the inverter"""
        # TODO this should be included in the efficiency_lookup method as an inverter type
        # Calculate the input as a ratio of the dc capacity of the inverter
        # input limited to be within the peak power dc capacity
        ratio_of_rated_output = (
            min(power_input, self.__inverter_peak_power_dc) / self.__inverter_peak_power_dc
        )

        # Using Ratio of Rated Power, calculate Inverter DC to AC efficiency
        # equation was estimated based on graph from
        # https://www.researchgate.net/publication/260286647_Performance_of_PV_inverters figure 9
        if ratio_of_rated_output == 0:
            inverter_dc_ac_efficiency = 0
        else:
            """Empirical efficiency curve fit primarily based on SMA Sunny Boy inverters (largest market share 2018)
            assisted with Sungrow and Huawei inverters (largest market share 2019)."""
            # System of 3 equations to fit efficiency curve for Sunny Boy PV2AC Inverters
            inverter_dc_ac_efficiency_1 = 97.2 * (
                1 - (0.18 / (1 + np.e ** (21 * ratio_of_rated_output)))
            )
            inverter_dc_ac_efficiency_2 = 0.5 * np.cos(np.pi * ratio_of_rated_output) + 96.9
            inverter_dc_ac_efficiency_3 = 97.2 * np.tanh(30 * ratio_of_rated_output)
            inverter_dc_ac_efficiency = min(
                inverter_dc_ac_efficiency_1,
                inverter_dc_ac_efficiency_2,
                inverter_dc_ac_efficiency_3,
            )
            inverter_dc_ac_efficiency = inverter_dc_ac_efficiency / 100

        return inverter_dc_ac_efficiency

    def calculate_energy_output(self, power_input: float) -> float:
        """Calculate energy from input power, applying efficiency and returning the energy produced"""
        # TODO this should use the inverter type to determine the efficiency calculation to be used
        # For now hard coded as the SMA sunny boy for consistency with previous PhotoVoltaicSystem
        # Calculate useful power from ac and dc peak capacity and efficiency
        power = min(power_input, self.__inverter_peak_power_dc)
        power *= self.efficiency_power_ratio(power)
        power = min(power, self.__inverter_peak_power_ac)

        # Convert power to energy
        energy_produced = power * self.__simulation_time.timestep()
        return energy_produced

    def produce_energy(self, power_input: float) -> float:
        """Calculate energy from input power, apply efficiency, and supply to energy supply connection"""
        energy_produced = self.calculate_energy_output(power_input)
        self.__energy_supply_conn.supply_energy(amount_produced=energy_produced)
        return energy_produced
