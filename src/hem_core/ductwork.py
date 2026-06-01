#!/usr/bin/env python3

"""
This module provides object(s) to represent ductwork
"""

# Standard library imports
from math import log, pi

from hem_core.input_output.enums import DuctShape, DuctType

# Set default value for the heat transfer coefficient inside the duct, in W / m^2 K
INTERNAL_HTC = 15.5  # CIBSE Guide C, Table 3.25, air flow rate approx 3 m/s

# Set default values for the heat transfer coefficient at the outer surface, in W / m^2 K
EXTERNAL_REFLECTIVE_HTC = 5.7  # low emissivity reflective surface, CIBSE Guide C, Table 3.25
EXTERNAL_NONREFLECTIVE_HTC = (
    10.0  # high emissivity non-reflective surface, CIBSE Guide C, Table 3.25
)


class Ductwork:
    """An object to represent ductwork for mechanical ventilation with heat recovery
    (MVHR), assuming steady state heat transfer in, 1. A hollow cyclinder (duct)
    with radial heat flow and 2. A rectangular cross-section. ISO 12241:2022"""

    def __init__(
        self,
        cross_section_shape: DuctShape,
        duct_perimeter: float | None,
        internal_diameter: float | None,
        external_diameter: float | None,
        length: float,
        k_insulation: float,
        thickness_insulation: float,
        reflective: bool,
        duct_type: DuctType,
    ):
        """Construct a ductwork object
        Arguments:
        cross_section_shape  -- whether cross-section of duct is circular or rectangular(sqaure)
        duct_perimeter       -- if ductwork is rectangular(sqaure) enter perimeter, in m
        internal_diameter    -- internal diameter of the duct, in m
        external_diameter    -- external diameter of the duct, in m
        length               -- length of duct, in m
        k_insulation         -- thermal conductivity of the insulation, in W / m K
        thickness_insulation -- thickness of the duct insulation, in m
        reflective           -- whether the outer surface of the duct is reflective
        duct_type            -- intake, supply, extract or exhaust
        """
        self.__length = length
        self.__duct_type = duct_type

        """ Select the correct heat transfer coefficient for the outer surface, in W / m^2 K """
        if reflective:
            external_htc = EXTERNAL_REFLECTIVE_HTC
        else:
            external_htc = EXTERNAL_NONREFLECTIVE_HTC

        if cross_section_shape == DuctShape.CIRCULAR:
            """ Calculate the diameter of the duct including the insulation (D_ins), in m"""
            if internal_diameter is None or external_diameter is None:
                raise ValueError(
                    "For circular ducts, both internal and external diameters must be provided."
                )  # pragma: no cover
            self.__D_ins = external_diameter + (2.0 * thickness_insulation)

            """ Calculate the interior linear surface resistance, in K m / W  """
            self.__internal_surface_resistance = 1.0 / (INTERNAL_HTC * pi * internal_diameter)

            """ Calculate the insulation linear thermal resistance, in K m / W  """
            self.__insulation_resistance = log(self.__D_ins / external_diameter) / (
                2.0 * pi * k_insulation
            )

            """ Calculate the exterior linear surface resistance, in K m / W  """
            self.__external_surface_resistance = 1.0 / (external_htc * pi * self.__D_ins)

        elif cross_section_shape == DuctShape.RECTANGULAR:
            """ Calculate the perimeter of the duct including the insulation, in m"""
            # the value 8 is specified in the standard ISO 12241:2022 and not assigned a description
            if duct_perimeter is None:
                raise ValueError(
                    "For rectangular ducts, duct perimeter must be provided."
                )  # pragma: no cover
            duct_perimeter_external = duct_perimeter + (8 * thickness_insulation)

            """ Calculate the interior linear surface resistance, in K m / W  """
            self.__internal_surface_resistance = 1.0 / (INTERNAL_HTC * duct_perimeter)

            """ Calculate the insulation linear thermal resistance, in K m / W  """
            self.__insulation_resistance = (2.0 * thickness_insulation) / (
                k_insulation * (duct_perimeter + duct_perimeter_external)
            )

            """ Calculate the exterior linear surface resistance, in K m / W  """
            self.__external_surface_resistance = 1.0 / (external_htc * duct_perimeter_external)
        else:
            raise ValueError(f"Invalid DuctShape: {cross_section_shape}.")

    def get_duct_type(self) -> DuctType:
        return self.__duct_type

    def duct_heat_loss(self, inside_temp: float, outside_temp: float) -> float:
        """Return the heat loss for air inside the duct for the current timestep
        Arguments:
        inside_temp    -- temperature of air inside the duct, in degrees C
        outside_temp   -- temperature outside the duct, in degrees C
        """
        # Calculate total thermal resistance
        total_resistance = (
            self.__internal_surface_resistance
            + self.__insulation_resistance
            + self.__external_surface_resistance
        )

        # Calculate the heat loss, in W
        duct_heat_loss = (inside_temp - outside_temp) / total_resistance * self.__length

        return duct_heat_loss
