from math import log, pi

import hem_core.units as units
from hem_core.input_output.enums import PipeworkContents, WaterPipeworkLocation
from hem_core.material_properties import GLYCOL25, WATER, MaterialProperties

# Set default values for heat transfer coefficients inside pipework, in W / m^2 K
INTERNAL_HTC_WATER = 1500.0  # CIBSE Guide C, Table 3.32 #Note, consider changing to 1478.4
INTERNAL_HTC_GLYCOL25 = INTERNAL_HTC_WATER

# TODO In the absence of a specific figure, use same value for water/glycol mix as for water.
#      Given the figure is relatively high (meaning little resistance to heat flow
#      between the fluid and the inside surface of the pipe) this is unlikely to
#      make a significant difference.

# Set default values for the heat transfer coefficient at the outer surface, in W / m^2 K
EXTERNAL_REFLECTIVE_HTC = 5.7  # low emissivity reflective surface, CIBSE Guide C, Table 3.25
EXTERNAL_NONREFLECTIVE_HTC = (
    10.0  # high emissivity non-reflective surface, CIBSE Guide C, Table 3.25
)

C_N_CALCULATION_FACTOR = 0.02761  # CIBSE Guide C empirical factor
C_N_EXPONENT = 0.8254  # CIBSE Guide C empirical exponent
N_CALCULATION_FACTOR = -0.001793  # CIBSE Guide C empirical factor
N_OFFSET = 1.245135  # CIBSE Guide C empirical offset


class PipeworkSimple:
    """An object to represent heat loss from pipework after flow has stopped"""

    def __init__(
        self,
        location: WaterPipeworkLocation,
        internal_diameter: float,
        length: float,
        contents: PipeworkContents,
    ):
        """Construct a PipeworkSimple object

        Args:
            location: Location of pipework
            internal_diameter: Internal diameter of pipe, metres
            length: Length of pipe, metres
            contents: Pipe contains water or glycol(25%)/water(75%)
        """
        self.__location = location
        self.__length = length
        self.__internal_diameter = internal_diameter
        self.__volume = self._calculate_volume()

        contents_mapping = {
            PipeworkContents.WATER: WATER,
            PipeworkContents.GLYCOL25: GLYCOL25,
        }

        if contents not in contents_mapping:
            raise ValueError(
                f"No properties available for specified pipe content: {str(contents)}."
            )

        self.__contents_properties: MaterialProperties = contents_mapping[contents]

    def _calculate_volume(self) -> float:
        """Calculate pipework volume in litres"""
        radius = self.__internal_diameter / 2
        return pi * radius * radius * self.__length * units.litres_per_cubic_metre

    @property
    def location(self) -> WaterPipeworkLocation:
        return self.__location

    @property
    def length(self) -> float:
        return self.__length

    @property
    def volume(self) -> float:
        return self.__volume

    @property
    def contents_properties(self) -> MaterialProperties:
        return self.__contents_properties

    def calculate_cool_down_loss(self, inside_temp: float, outside_temp: float) -> float:
        """Calculates total heat loss from a full pipe from demand temp to ambient temp in kWh

        Args:
            inside_temp: Temperature of water inside the pipe, in degrees C
            outside_temp: Temperature outside the pipe, in degrees C

        Returns:
            Heat loss in kWh
        """
        return (
            self.__contents_properties.volumetric_energy_content_kWh_per_litre(
                temp_high=inside_temp, temp_base=outside_temp
            )
            * self.__volume
        )


class Pipework(PipeworkSimple):
    """An object to represent steady state heat transfer in a hollow cyclinder (pipe)
    with radial heat flow. Method taken from 2021 ASHRAE Handbook, Section 4.4.2
    """

    def __init__(
        self,
        location: WaterPipeworkLocation,
        internal_diameter: float,
        external_diameter: float,
        length: float,
        insulation_thermal_conductivity: float,
        insulation_thickness: float,
        reflective: bool,
        contents: PipeworkContents,
    ):
        """Construct a Pipework object

        Args:
            location: Location of pipework
            internal_diameter: Internal diameter of pipe, metres
            external_diameter: External diameter of pipe, metres
            length: Length of pipe, metres
            insulation_thermal_conductivity: Thermal conductivity of insulation, W/mK
            insulation_thickness: Thickness of pipe insulation, metres
            reflective: Pipe surface is reflective
            contents: Pipe contains water or glycol(25%)/water(75%)
        """
        if external_diameter <= internal_diameter:
            raise ValueError("Pipework: External diameter must be greater than internal diameter.")

        super().__init__(
            location=location, internal_diameter=internal_diameter, length=length, contents=contents
        )

        # Set the heat transfer coefficient (htc) inside and outside the pipe, in W/m^2K (watts per square meter per kelvin)
        internal_htc = self._get_internal_heat_transfer_coefficient(contents=contents)
        external_htc = self._get_external_heat_transfer_coefficient(reflective=reflective)

        self.__external_diameter = external_diameter

        self.__D_insulation = self._calculate_insulated_diameter(
            external_diameter=external_diameter, thickness_insulation=insulation_thickness
        )

        self.__interior_surface_resistance = self._calculate_interior_surface_resistance(
            internal_htc=internal_htc, internal_diameter=internal_diameter
        )

        self.__insulation_resistance = self._calculate_insulation_resistance(
            insulation_thermal_conductivity=insulation_thermal_conductivity,
            external_diameter=external_diameter,
        )

        self.__external_surface_resistance = self._calculate_external_surface_resistance(
            external_htc=external_htc, D_insulation=self.__D_insulation
        )

        self.__total_resistance = (
            self.__interior_surface_resistance
            + self.__insulation_resistance
            + self.__external_surface_resistance
        )

        # Calculate linear thermal transmittance (non embedded), W/mK (watts per metre per kelvin)
        self.__linear_thermal_transmittance = 1 / self.__total_resistance

    def _get_internal_heat_transfer_coefficient(self, contents: PipeworkContents) -> float:
        """Get the internal heat transfer coefficient based on pipe contents.

        Args:
            contents: The contents of the pipe (water or glycol)

        Returns:
            Heat transfer coefficient in W/m²K

        Raises:
            ValueError: If contents is not supported
        """
        if contents == PipeworkContents.WATER:
            return INTERNAL_HTC_WATER
        elif contents == PipeworkContents.GLYCOL25:
            return INTERNAL_HTC_GLYCOL25
        else:
            raise ValueError("Invalid pipe contents.")  # pragma: no cover

    def _get_external_heat_transfer_coefficient(self, reflective: bool) -> float:
        """Get the external heat transfer coefficient based on pipe reflective surface.

        Args:
            reflective: Whether the surface is reflective

        Returns:
            Heat transfer coefficient in W/m^2K
        """
        return EXTERNAL_REFLECTIVE_HTC if reflective else EXTERNAL_NONREFLECTIVE_HTC

    def _calculate_insulated_diameter(
        self, external_diameter: float, thickness_insulation: float
    ) -> float:
        """Calculate the total outer diameter including insulation (D_insulation).

        Args:
            external_diameter: Outer diameter of the bare pipe, in metres
            thickness_insulation: Thickness of insulation layer, in metres

        Returns:
            Total outer diameter including insulation, in metres
        """
        return external_diameter + (2.0 * thickness_insulation)

    def _calculate_interior_surface_resistance(
        self, internal_htc: float, internal_diameter: float
    ) -> float:
        """Calculate the interior surface resistance.

        Args:
            internal_htc: Heat transfer coefficient inside the pipe, in W/m^2K
            internal_diameter: Internal diameter of the pipe, in metres

        Returns:
            Interior surface resistance, in Km/W
        """
        return 1.0 / (internal_htc * pi * internal_diameter)

    def _calculate_insulation_resistance(
        self, insulation_thermal_conductivity: float, external_diameter: float
    ) -> float:
        """Calculate the insulation resistance.

        Args:
            insulation_thermal_conductivity: Thermal conductivity of insulation, in W/mK
            external_diameter: External diameter of the pipe, in metres

        Returns:
            Insulation resistance, in Km/W
        """
        return log(self.__D_insulation / external_diameter) / (
            2.0 * pi * insulation_thermal_conductivity
        )

    def _calculate_external_surface_resistance(
        self, external_htc: float, D_insulation: float
    ) -> float:
        """Calculate the external surface resistance.

        Args:
            external_htc: Heat transfer coefficient outside the pipe, in W/m^2K
            D_insulation: Diameter of the pipe including insulation, in metres

        Returns:
            External surface resistance, in Km/W
        """
        return 1.0 / (external_htc * pi * D_insulation)

    @property
    def interior_surface_resistance(self) -> float:
        return self.__interior_surface_resistance

    @property
    def insulation_resistance(self) -> float:
        return self.__insulation_resistance

    @property
    def external_surface_resistance(self) -> float:
        return self.__external_surface_resistance

    def c_n_equivalence(self) -> tuple[float, float, float]:
        """Return the c and n value equivalent and thermal mass for the pipework as if working like a emitter"""

        # Calculate c and n values needed to give the same heat loss predicted by CIBSE Guide C
        # using equations 3.101, 3.107 and 3.108. The following equations give a good fit through
        # the data over the realistic working range of temperatures and pipework thicknesses used
        # in dwellings derived from the more detailed CIBSE equations,
        # outputting in the c and n format needed here.
        # The derived equation expects pipework diameter in mm (so unit conversion is required)
        # and outputs c and n coefficients which provide output in W (so conversion to kW required)

        dop = self.__external_diameter * units.mm_per_m
        c_Watts = self.length * C_N_CALCULATION_FACTOR * (dop**C_N_EXPONENT)
        c = c_Watts / units.W_per_kW
        n = N_CALCULATION_FACTOR * log(dop) + N_OFFSET

        thermal_mass = self.volume * WATER.specific_heat_capacity() / units.J_per_kWh

        # TODO: Add thermal mass of pipe itself
        return c, n, thermal_mass

    def calculate_steady_state_heat_loss(self, inside_temp: float, outside_temp: float) -> float:
        """Return the heat loss from the pipe for the current timestep

        Args:
            inside_temp    -- temperature of water inside the pipe, in degrees C
            outside_temp   -- temperature outside the pipe, in degrees C

        Returns:
            Heat loss in W
        """
        return (inside_temp - outside_temp) / (self.__total_resistance) * self.length
