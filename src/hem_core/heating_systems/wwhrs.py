#!/usr/bin/env python3

import math

import scipy.interpolate

"""
This module provides objects to model waste water heat recovery systems of different types.
Uses a unified WWHRS class that handles all system types (A, B, C).
"""
# Temperature reduction of water during the shower from temp_target
delta_T_shower = 6.0


class WWHRS_Instantaneous:
    """A unified class to represent instantaneous waste water heat recovery systems

    This class can handle all three system configurations (A, B, C) based on the
    system type specified when calling the calculation methods. Each physical WWHRS
    unit is defined once and can be connected to multiple showers with different
    configurations.
    """

    def __init__(
        self,
        flow_rates,
        system_a_efficiencies,
        cold_water_source,
        system_a_utilisation_factor=None,
        system_b_efficiencies=None,
        system_b_utilisation_factor=None,
        system_c_efficiencies=None,
        system_c_utilisation_factor=None,
        system_b_efficiency_factor=None,
        system_c_efficiency_factor=None,
    ):
        """
        Initialize the WWHRS with efficiency data for all system types.

        Args:
            flow_rates: List of test flow rates (e.g., [5, 7, 9, 11, 13])
            system_a_efficiencies: Measured efficiencies for System A at test flow rates
            cold_water_source: Cold water source object
            system_a_utilisation_factor: Utilisation factor for System A
            system_b_efficiencies: Efficiencies for System B (optional, will use reduction factor if not provided)
            system_b_utilisation_factor: Utilisation factor for System B
            system_c_efficiencies: Efficiencies for System C (optional, will use reduction factor if not provided)
            system_c_utilisation_factor: Utilisation factor for System C
            system_b_efficiency_factor: Reduction factor for System B (default 0.81)
            system_c_efficiency_factor: Reduction factor for System C (default 0.88)
        """
        self.__cold_water_source = cold_water_source
        self.__flow_rates = flow_rates

        # System A data
        self.__system_a_efficiencies = system_a_efficiencies
        self.__system_a_utilisation_factor = system_a_utilisation_factor

        # System B data
        self.__system_b_efficiencies = system_b_efficiencies
        self.__system_b_utilisation_factor = system_b_utilisation_factor
        self.__system_b_efficiency_factor = system_b_efficiency_factor

        # System C data
        self.__system_c_efficiencies = system_c_efficiencies
        self.__system_c_utilisation_factor = system_c_utilisation_factor
        self.__system_c_efficiency_factor = system_c_efficiency_factor

        # Pre-heated water tracking: temperature and available volume
        # Only water that passes through the heat exchanger while waste water
        # is flowing can be pre-heated. This tracks how much is available.
        self.__preheated_temperature = None
        self.__preheated_volume_remaining = 0.0

        # Future expansion - track last use time
        self.__last_used_time = None

    def register_preheated_volume(self, temperature: float, volume: float) -> None:
        """
        Register pre-heated water available from a shower event.

        Called after a shower event processes through the WWHRS. The pre-heated
        water is only available up to the volume of cold water that was drawn
        through the heat exchanger during that shower.

        If called multiple times within a timestep (e.g., multiple showers
        connected to same WWHRS), volumes are accumulated with weighted average
        temperature.

        Args:
            temperature: The pre-heated water temperature (T_cyl_feed)
            volume: Volume of pre-heated water available (litres)

        Raises:
            ValueError: If volume is negative
        """
        if math.isclose(volume, 0.0, abs_tol=1e-10):
            return

        if volume < 0:
            raise ValueError(f"volume cannot be negative, got {volume}")

        if self.__preheated_volume_remaining > 0 and self.__preheated_temperature is not None:
            # Multiple showers in same timestep - weighted average temperature
            total_volume = self.__preheated_volume_remaining + volume
            self.__preheated_temperature = (
                (self.__preheated_temperature * self.__preheated_volume_remaining)
                + (temperature * volume)
            ) / total_volume
            self.__preheated_volume_remaining = total_volume
        else:
            self.__preheated_temperature = temperature
            self.__preheated_volume_remaining = volume

    def timestep_end(self) -> None:
        """
        Reset state at the end of the timestep.

        Pre-heated water is only available while waste water is actively flowing
        through the WWHRS heat exchanger. Any pre-heated volume not consumed
        during the timestep cannot carry over, as there will be no waste water
        flow to maintain the pre-heating.

        This must be called at the end of each timestep to prevent incorrect
        energy recovery calculations in subsequent timesteps.

        Note: While draw_off_water() consumes pre-heated volume, it may not
        fully deplete it if the total cold water demand is less than the
        registered pre-heated volume. This explicit reset ensures correctness
        regardless of draw patterns.
        """
        self.__preheated_temperature = None
        self.__preheated_volume_remaining = 0.0

    def calculate_performance(
        self, system_type, temp_target, flowrate_waste_water, volume_cold_water, temp_hot
    ):
        """
        Calculate WWHRS performance based on system type.

        Args:
            system_type: 'A', 'B', or 'C'
            temp_target: Target shower temperature (T_shower)
            flowrate_waste_water: Flow rate of waste water
            temp_hot: Hot water temperature (required for Systems B and C)
            volume_cold_water: Not used in current implementation

        Returns:
            Dictionary with:
                - T_pre: Pre-heated water temperature
                - T_cyl_feed: Temperature of water feeding the cylinder
                - m_hot: Hot water flow rate (if calculable)
        """
        if system_type.upper() == "A":
            return self._calculate_system_a(
                temp_target, flowrate_waste_water, volume_cold_water, temp_hot
            )
        elif system_type.upper() == "B":
            return self._calculate_system_b(
                temp_target, flowrate_waste_water, volume_cold_water, temp_hot
            )
        elif system_type.upper() == "C":
            return self._calculate_system_c(
                temp_target, flowrate_waste_water, volume_cold_water, temp_hot
            )
        else:
            raise ValueError(f"Invalid system type: {system_type}. Must be 'A', 'B', or 'C'")

    def _calculate_system_a(self, temp_target, flowrate_waste_water, volume_cold_water, temp_hot):
        """Calculate performance for System A configuration."""
        # Validate required parameters
        if self.__system_a_utilisation_factor is None:
            raise ValueError("system_a_utilisation_factor is required for System A calculation")

        list_temp_vol = self.__cold_water_source.get_temp_cold_water(volume_cold_water)
        temp_main = math.fsum(t * v for t, v in list_temp_vol) / math.fsum(
            v for _, v in list_temp_vol
        )

        # Get efficiency for System A
        efficiency = self.get_efficiency_from_flowrate(flowrate_waste_water, "A") / 100.0
        eta_uf = efficiency * self.__system_a_utilisation_factor

        # Calculate drain temperature
        temp_drain = temp_target - delta_T_shower

        # For System A: T_pre_A = T_main + η × U_F × (T_drain - T_main)
        temp_pre = temp_main + eta_uf * (temp_drain - temp_main)

        # For System A: m_hot = flowrate_waste_water * (T_target - T_pre_A) / (temp_hot - T_pre_A)
        if math.isclose(temp_hot, temp_pre, abs_tol=1e-10):
            flowrate_hot = None
        else:
            flowrate_hot = flowrate_waste_water * (temp_target - temp_pre) / (temp_hot - temp_pre)

        # For System A, both shower and cylinder are fed with pre-heated water
        return {
            "T_cyl_feed": temp_pre,
            "flowrate_hot": flowrate_hot,
        }

    def _calculate_system_b(self, temp_target, flowrate_waste_water, volume_cold_water, temp_hot):
        """Calculate performance for System B configuration using algebraic solution."""
        if temp_hot is None:
            raise ValueError("temp_hot must be provided for System B calculation")

        list_temp_vol = self.__cold_water_source.get_temp_cold_water(volume_cold_water)
        temp_main = math.fsum(t * v for t, v in list_temp_vol) / math.fsum(
            v for _, v in list_temp_vol
        )

        # Determine which approach to use based on available data
        if self.__system_b_efficiencies is not None:
            # Approach 1: Pre-corrected System B data
            if self.__system_b_utilisation_factor is None:
                raise ValueError(
                    "system_b_utilisation_factor is required when using system_b_efficiencies"
                )

            efficiency_adjusted = (
                self.get_efficiency_from_flowrate(flowrate_waste_water, "B") / 100.0
            )
            eta_uf = efficiency_adjusted * self.__system_b_utilisation_factor

        else:
            # Approach 2: Convert from System A data
            if (
                self.__system_b_utilisation_factor is None
                or self.__system_b_efficiency_factor is None
            ):
                raise ValueError(
                    "Both system_b_utilisation_factor and system_b_efficiency_factor are required when converting from System A data"
                )

            base_efficiency = self.get_efficiency_from_flowrate(flowrate_waste_water, "A") / 100.0
            efficiency_adjusted = base_efficiency * self.__system_b_efficiency_factor
            eta_uf = efficiency_adjusted * self.__system_b_utilisation_factor

        # Calculate drain temperature
        temp_drain = temp_target - delta_T_shower

        # Implement algebraic solution from Technical Recommendations
        if math.isclose(temp_hot, temp_target, abs_tol=1e-10):
            temp_pre = temp_main
        else:
            temp = eta_uf * (temp_drain - temp_main) / (temp_hot - temp_target)
            temp_pre = (temp_main + temp_hot * temp) / (1 + temp)

        # For System B: m_hot = flowrate_waste_water * (T_target - T_pre_B) / (temp_hot - T_pre_B)
        if math.isclose(temp_hot, temp_pre, abs_tol=1e-10):
            flowrate_hot = None
        else:
            flowrate_hot = flowrate_waste_water * (temp_target - temp_pre) / (temp_hot - temp_pre)

        # For System B, only shower is fed with pre-heated water
        return {
            "T_cyl_feed": temp_main,  # Cylinder still gets mains water
            "flowrate_hot": flowrate_hot,
        }

    def _calculate_system_c(self, temp_target, flowrate_waste_water, volume_cold_water, temp_hot):
        """Calculate performance for System C configuration."""
        if temp_hot is None:
            raise ValueError("temp_hot must be provided for System C calculation")

        list_temp_vol = self.__cold_water_source.get_temp_cold_water(volume_cold_water)
        temp_main = math.fsum(t * v for t, v in list_temp_vol) / math.fsum(
            v for _, v in list_temp_vol
        )

        # Determine which approach to use based on available data
        if self.__system_c_efficiencies is not None:
            # Approach 1: Pre-corrected System C data
            if self.__system_c_utilisation_factor is None:
                raise ValueError(
                    "system_c_utilisation_factor is required when using system_c_efficiencies"
                )

            efficiency_adjusted = (
                self.get_efficiency_from_flowrate(flowrate_waste_water, "C") / 100.0
            )
            eta_uf = efficiency_adjusted * self.__system_c_utilisation_factor

        else:
            # Approach 2: Convert from System A data
            if (
                self.__system_c_utilisation_factor is None
                or self.__system_c_efficiency_factor is None
            ):
                raise ValueError(
                    "Both system_c_utilisation_factor and system_c_efficiency_factor are required when converting from System A data"
                )

            base_efficiency = self.get_efficiency_from_flowrate(flowrate_waste_water, "A") / 100.0
            efficiency_adjusted = base_efficiency * self.__system_c_efficiency_factor
            eta_uf = efficiency_adjusted * self.__system_c_utilisation_factor

        # Calculate drain temperature
        temp_drain = temp_target - delta_T_shower

        # Direct calculation for System C
        if math.isclose(temp_target, temp_main, abs_tol=1e-10):
            temp_pre = temp_main
        else:
            temp_pre = temp_main + eta_uf * (temp_drain - temp_main) * (temp_hot - temp_main) / (
                temp_target - temp_main
            )

        # For System C: m_hot = flowrate_waste_water * (T_target - T_main) / (temp_hot - T_main)
        if math.isclose(temp_hot, temp_main, abs_tol=1e-10):
            flowrate_hot = None
        else:
            flowrate_hot = flowrate_waste_water * (temp_target - temp_main) / (temp_hot - temp_main)

        # For System C, only cylinder is fed with pre-heated water
        return {
            "T_cyl_feed": temp_pre,  # Cylinder gets pre-heated water
            "flowrate_hot": flowrate_hot,
        }

    def get_efficiency_from_flowrate(self, flowrate, system_type="A"):
        """Get the interpolated efficiency from the flowrate for specified system type."""
        if system_type.upper() == "A":
            if self.__system_a_efficiencies is None:
                raise ValueError(
                    "System A efficiencies not available - no system_a_efficiencies provided"
                )
            efficiencies = self.__system_a_efficiencies
        elif system_type.upper() == "B":
            if self.__system_b_efficiencies is None:
                raise ValueError(
                    "System B efficiencies not available - no system_b_efficiencies provided"
                )
            efficiencies = self.__system_b_efficiencies
        elif system_type.upper() == "C":
            if self.__system_c_efficiencies is None:
                raise ValueError(
                    "System C efficiencies not available - no system_c_efficiencies provided"
                )
            efficiencies = self.__system_c_efficiencies
        else:
            raise ValueError(f"Invalid system type: {system_type}")

        if flowrate < self.__flow_rates[0] or math.isclose(flowrate, self.__flow_rates[0]):
            return efficiencies[0]
        elif flowrate > self.__flow_rates[-1] or math.isclose(flowrate, self.__flow_rates[-1]):
            return efficiencies[-1]

        y_interp = scipy.interpolate.interp1d(self.__flow_rates, efficiencies)
        return float(y_interp(flowrate))

    def get_temp_cold_water(self, volume_needed: float) -> list[tuple[float, float]]:
        """
        Get the temperature of cold water, accounting for pre-heated availability.

        Returns pre-heated temperature up to the available volume, then mains
        temperature for any remainder.

        Args:
            volume_needed: Volume of cold water required (litres)

        Returns:
            List of (temperature, volume) tuples.
        """
        result = []

        if self.__preheated_volume_remaining > 0 and self.__preheated_temperature is not None:
            # Provide pre-heated water up to available volume
            preheated_to_provide = min(volume_needed, self.__preheated_volume_remaining)

            if preheated_to_provide > 0:
                result.append((self.__preheated_temperature, preheated_to_provide))

            # Remainder from mains
            remaining = volume_needed - preheated_to_provide
            if remaining > 0:
                result.extend(self.__cold_water_source.get_temp_cold_water(remaining))
        else:
            # No pre-heated water available
            result = self.__cold_water_source.get_temp_cold_water(volume_needed)

        return result

    def draw_off_water(self, volume_needed: float) -> list[tuple[float, float]]:
        """
        Draw water, consuming pre-heated volume if available.

        Unlike get_temp_cold_water(), this method consumes the pre-heated
        volume so subsequent draws receive less (or no) pre-heated water.

        Args:
            volume_needed: Volume of water to draw (litres)

        Returns:
            List of (temperature, volume) tuples for the water drawn.
        """
        result = []

        if self.__preheated_volume_remaining > 0 and self.__preheated_temperature is not None:
            # Consume pre-heated water up to available volume
            preheated_to_use = min(volume_needed, self.__preheated_volume_remaining)

            if preheated_to_use > 0:
                result.append((self.__preheated_temperature, preheated_to_use))
                self.__preheated_volume_remaining -= preheated_to_use

            # Remainder from mains
            remaining = volume_needed - preheated_to_use
            if remaining > 0:
                result.extend(self.__cold_water_source.draw_off_water(remaining))
        else:
            # No pre-heated water available
            result = self.__cold_water_source.draw_off_water(volume_needed)

        return result

    def set_last_used_time(self, time):
        """Set the time when this WWHRS was last used (for future expansion)."""
        self.__last_used_time = time

    def get_last_used_time(self):
        """Get the time when this WWHRS was last used (for future expansion)."""
        return self.__last_used_time
