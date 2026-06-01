#!/usr/bin/env python3

"""
This module contains data on the properties of materials, and classes to
organise this data.
"""

# Local imports
import hem_core.units as units


class MaterialProperties:
    """An object to hold properties of materials, both specified and derived"""

    # TODO Consider splitting this into different kinds of materials (e.g. heat
    #      transfer fluid, heat conductor etc.) so that not everything has to
    #      be defined (or made optional, adding complexity to the code)

    def __init__(self, density: float, specific_heat_capacity: float) -> None:
        """Construct a MaterialProperties object

        Arguments:
        density                  -- in kg / litre
        specific_heat_capacity   -- in J / (kg.K)

        Derived values:
        volumetric_heat_capacity -- in J / (litre.K)
        """
        self.__density = density
        self.__specific_heat_capacity = specific_heat_capacity
        self.__volumetric_heat_capacity = specific_heat_capacity * density

    def density(self) -> float:
        """Return density of the material, in kg / litre"""
        return self.__density

    def density_kg_per_m3(self) -> float:
        return self.__density * units.litres_per_cubic_metre

    def specific_heat_capacity(self) -> float:
        """Return specific heat capacity, in J / (kg.K)"""
        return self.__specific_heat_capacity

    def specific_heat_capacity_kWh(self) -> float:
        """Return specific heat capacity, in kWh / (kg.K)"""
        return self.__specific_heat_capacity / units.J_per_kWh

    def volumetric_heat_capacity(self) -> float:
        """Return volumetric heat capacity, in J / (litre.K)"""
        return self.__volumetric_heat_capacity

    def volumetric_energy_content_J_per_litre(self, temp_high: float, temp_base: float) -> float:
        """Return energy content of material, in J / litre

        Arguments:
        temp_high -- temperature for which energy content should be calculated, in deg C or K
        temp_base -- temperature which defines "zero energy", in same units as temp_high
        """
        return (temp_high - temp_base) * self.__volumetric_heat_capacity

    def volumetric_energy_content_kWh_per_litre(self, temp_high: float, temp_base: float) -> float:
        """Return energy content of material, in kWh / litre

        Arguments:
        temp_high -- temperature for which energy content should be calculated, in deg C or K
        temp_base -- temperature which defines "zero energy", in same units as temp_high
        """
        return self.volumetric_energy_content_J_per_litre(temp_high, temp_base) / units.J_per_kWh


# Define materials
WATER: MaterialProperties = MaterialProperties(density=1.0, specific_heat_capacity=4184)
# TODO Check the figures above. Use more precise ones?

# Density of a fluid mixture between 25% glycol (volume) and 75% water (volume) at 20C and
# specific heat capacity in J / (kg * K). The following report suggests (on pages 14-15)
# that this mix would be likely to give antifreeze protection to -10 Celsius for either
# ethylene glycol or propylene glycol:
# https://assets.publishing.service.gov.uk/media/5a8204a3e5274a2e8ab57110/DECC_RHPP_160404_Note_on_bias_errors_v9.pdf
GLYCOL25: MaterialProperties = MaterialProperties(density=1.0, specific_heat_capacity=3757)

AIR: MaterialProperties = MaterialProperties(density=0.001204, specific_heat_capacity=1006.0)
