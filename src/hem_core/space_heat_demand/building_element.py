#!/usr/bin/env python3

"""
This module provides objects to represent building elements such as walls,
floors and windows. Each of these building elements has 2 or more nodes and is
associated with a thermal zone.

Note that the temperatures at each node for each timestep of the calculation
are calculated and stored in the zone module, not here. This is based on the
method described in BS EN ISO 52016-1:2017, section 6.5.6.
"""

# Standard library imports
from abc import ABC, abstractmethod
from math import exp, log, radians, sin
from typing import Any

# Local imports
import hem_core.units as units
from hem_core.external_conditions import ExternalConditions, sky_view_factor
from hem_core.input_output.enums import (
    EdgeInsulationDirection,
    FloorType,
    HeatFlowDirection,
    MassDistributionClass,
    PartyWallCavityType,
    PartyWallLiningType,
    WindowTreatmentControl,
    WindowTreatmentType,
    WindShieldLocation,
)
from hem_core.input_output.input import PITCH_LIMIT_HORIZ_CEILING, PITCH_LIMIT_HORIZ_FLOOR
from hem_core.simulation_time import SimulationTime

# Difference between external air temperature and sky temperature
# (default value for intermediate climatic region from BS EN ISO 52016-1:2017, Table B.19)
temp_diff_sky = 11.0  # Kelvin


def projected_height(tilt: float, height: float) -> float:
    """calc the vertically projected height of a surface from
    the actual height and tilt of the surface"""
    ph = height * sin(radians(tilt))
    """ BS EN ISO 52010-1 Table 7 geometric input data; shading. Footnote d
    validity interval H1;ic > 0
    if horizontal (height = 0): choose small value e.g. H1 = 0.01 m"""
    if ph < 0.01:
        ph = 0.01

    return ph


def calculate_area(height: float, width: float) -> float:
    """calculate area from height and width"""
    area = height * width
    return area


def calculate_cavity_resistance(
    party_wall_cavity_type: str,
    party_wall_lining_type: str | None,
    thermal_resistance_cavity: float | None,
) -> float:
    """Calculate the effective thermal resistance of the party wall cavity

    For defined_resistance type, uses the provided value directly.
    For other types, derives the cavity resistance from equivalent U-values
    which are based on research into heat loss via air movement in party wall cavities.

    The derivation assumes typical party wall constructions and calculates
    what cavity resistance (R_cavity) is needed to achieve the equivalent
    U-values (initially based on SAP guidance):
    - Unsealed cavity, dry lined: U = 0.6 W/m².K → R_cavity ≈ 1.2 m².K/W
    - Unsealed cavity, wet plaster: U = 0.2 W/m².K → R_cavity ≈ 4.5 m².K/W
    - Edge-sealed cavity: U = 0.2 W/m².K → R_cavity ≈ 4.5 m².K/W
    - Unsealed filled cavity: U = 0.2 W/m².K → R_cavity ≈ 4.5 m².K/W
    - Solid or filled and edge-sealed: U = 0.0 W/m².K → R_cavity = 999999 m².K/W (effectively adiabatic)

    Arguments:
    party_wall_cavity_type -- type of party wall cavity construction
    party_wall_lining_type -- type of party wall lining material
    thermal_resistance_cavity -- user-defined cavity resistance (only for 'defined_resistance' type)

    Returns:
    r_cavity -- effective thermal resistance of the cavity, in m2.K / W
    """

    cavity_type = PartyWallCavityType(party_wall_cavity_type)

    if cavity_type == PartyWallCavityType.DEFINED_RESISTANCE:
        assert thermal_resistance_cavity is not None, (
            "thermal_resistance_cavity is validated by schema to be not None "
            "for DEFINED_RESISTANCE type"
        )
        return thermal_resistance_cavity

    # Thermal resistance equivalents for deriving cavity resistance
    if party_wall_lining_type is None:
        PARTY_WALL_CAVITY_THERMAL_RESISTANCE = {
            PartyWallCavityType.SOLID: 999999,
            PartyWallCavityType.FILLED_SEALED: 999999,
            PartyWallCavityType.UNFILLED_UNSEALED: None,
            PartyWallCavityType.FILLED_UNSEALED: None,
            PartyWallCavityType.UNFILLED_SEALED: None,
        }

    elif party_wall_lining_type == PartyWallLiningType.DRY_LINED:
        PARTY_WALL_CAVITY_THERMAL_RESISTANCE = {
            PartyWallCavityType.SOLID: None,
            PartyWallCavityType.UNFILLED_UNSEALED: 1.2,
            PartyWallCavityType.FILLED_UNSEALED: 4.5,
            PartyWallCavityType.UNFILLED_SEALED: 4.5,
            PartyWallCavityType.FILLED_SEALED: None,
        }
    elif party_wall_lining_type == PartyWallLiningType.WET_PLASTER:
        PARTY_WALL_CAVITY_THERMAL_RESISTANCE = {
            PartyWallCavityType.SOLID: None,
            PartyWallCavityType.UNFILLED_UNSEALED: 4.5,
            PartyWallCavityType.FILLED_UNSEALED: 4.5,
            PartyWallCavityType.UNFILLED_SEALED: 4.5,
            PartyWallCavityType.FILLED_SEALED: None,
        }
    else:
        raise ValueError("party_wall_lining_type not recognised")

    thermal_resistance = PARTY_WALL_CAVITY_THERMAL_RESISTANCE[cavity_type]

    if thermal_resistance is None:
        raise ValueError("invalid combination of party wall cavity type and party wall lining type")

    return thermal_resistance


"""

The different variations for each of these are:
- Heat transfer with internal environment:
    - Common
- Heat transfer through and storage within the element:
    - 2 nodes
    - 5 nodes
    - 3+2 nodes
- Heat transfer with environment on other side of element:
    - Ground
    - Conditioned space
    - Unconditioned space
    - Outside
- Interaction with solar radiation:
    - Absorbed
    - Transmitted
    - Not exposed
    
The different building element types are composed of the following combinations:
- BuildingElementOpaque: Common, 5 nodes, Outside, Absorbed
- BuildingElementTransparent: Common, 2 nodes, Outside, Transmitted
- BuildingElementAdjacentConditionedSpace: Common, 5 nodes, Conditioned space, Not exposed
- BuildingElementAdjacentUnconditionedSpace_Simple: Common, 5 nodes, Unconditioned space, Not exposed
- BuildingElementPartyWall: Common, 5 nodes, Unconditioned space, Not exposed
- BuildingElementGround: Common, 3+2 nodes, Ground, Not exposed

BuildingElementTransparent also has the functions projected_height, mid_height and orientation, which I think are now 
unused. If this is confirmed to be the case, then these can be deleted.

BuildingElementGround has several alternative sets of inputs, depending on the floor_type input. The current class
requires all of these inputs and ignores the ones that are not relevant. This class could arguably be split into 5
different classes (one for each floor_type option) to avoid this. The alternative sets of inputs are for calculating
self.__h_pi and self.__h_pe, which are ultimately used in the temp_ext function. Therefore, one way to handle this would
be to have 5 different classes, calculate h_pi and h_pe, then feed these into the constructor of the "Ground" object
under the category "Heat transfer with environment on other side of element".

The relevant functions for each set of characteristics are:
- Heat transfer with internal environment:
    - heat_flow_direction
    - r_si
    - h_ci
    - h_ri
    - pitch_class
- Heat transfer through and storage within the element:
    - no_of_nodes
    - no_of_inside_nodes
    - init_h_pli
    - init_k_pli
- Heat transfer with environment on other side of element:
    - r_se
    - h_ce
    - h_re
    - temp_ext
- Interaction with solar radiation:
    - i_sol_dir_dif
    - solar_gains
    - shading_factors_direct_diffuse

"""

# Values from BS EN ISO 13789:2017, Table 8: Conventional surface heat transfer coefficients
H_CI_UPWARDS = 5.0
H_CI_HORIZONTAL = 2.5
H_CI_DOWNWARDS = 0.7
H_CE = 20.0
H_RI = 5.13
H_RE = 4.14

# Surface resistances of building elements, in m2 K / W
R_SI_HORIZONTAL = 1.0 / (H_RI + H_CI_HORIZONTAL)
R_SI_UPWARDS = 1.0 / (H_RI + H_CI_UPWARDS)
R_SI_DOWNWARDS = 1.0 / (H_RI + H_CI_DOWNWARDS)
R_SE = 1.0 / (H_CE + H_RE)


class BuildingElementBase(ABC):
    _pitch: float
    k_pli: list[float]
    area: float
    _g_value: float
    _h_pli: list[float]
    _external_conditions: ExternalConditions
    _simulation_time: SimulationTime
    _frame_area_fraction: float

    @abstractmethod
    def r_se(self) -> float: ...

    @abstractmethod
    def r_si(self) -> float: ...


class HeatTransferInternal(BuildingElementBase):
    def heat_flow_direction(
        self, temp_int_air: float, temp_int_surface: float
    ) -> HeatFlowDirection:
        """Determine direction of heat flow for a surface"""
        if self._pitch >= PITCH_LIMIT_HORIZ_CEILING and self._pitch <= PITCH_LIMIT_HORIZ_FLOOR:
            return HeatFlowDirection.HORIZONTAL
        else:
            inwards_heat_flow = temp_int_air < temp_int_surface
            is_floor = self._pitch > PITCH_LIMIT_HORIZ_FLOOR
            is_ceiling = self._pitch < PITCH_LIMIT_HORIZ_CEILING
            upwards_heat_flow = (is_floor and inwards_heat_flow) or (
                is_ceiling and not inwards_heat_flow
            )
            if upwards_heat_flow:
                return HeatFlowDirection.UPWARDS
            else:
                return HeatFlowDirection.DOWNWARDS

    @classmethod
    def __r_si(cls, pitch: float) -> float:
        """Return internal surface resistance, in m2 K / W"""
        # TODO use is floor and is ceiling functions so determine R SI values
        if pitch >= PITCH_LIMIT_HORIZ_CEILING and pitch <= PITCH_LIMIT_HORIZ_FLOOR:
            return R_SI_HORIZONTAL
        elif pitch < PITCH_LIMIT_HORIZ_CEILING:
            return R_SI_UPWARDS
        elif pitch > PITCH_LIMIT_HORIZ_FLOOR:
            return R_SI_DOWNWARDS
        else:
            raise ValueError("Pitch class not recognised")

    def r_si(self) -> float:
        """Return internal surface resistance, in m2 K / W"""
        return self.__r_si(pitch=self._pitch)

    def h_ci(self, temp_int_air: float, temp_int_surface: float) -> float:
        """Return internal convective heat transfer coefficient, in W / (m2.K)"""
        if (
            self.heat_flow_direction(temp_int_air=temp_int_air, temp_int_surface=temp_int_surface)
            == HeatFlowDirection.HORIZONTAL
        ):
            return H_CI_HORIZONTAL
        elif (
            self.heat_flow_direction(temp_int_air=temp_int_air, temp_int_surface=temp_int_surface)
            == HeatFlowDirection.UPWARDS
        ):
            return H_CI_UPWARDS
        else:
            return H_CI_DOWNWARDS

    def h_ri(self) -> float:
        """Return internal radiative heat transfer coefficient, in W / (m2.K)"""
        return H_RI

    @classmethod
    def convert_uvalue_to_resistance(cls, u_value: float, pitch: float) -> float:
        """Convert U-value from input data to thermal resistance of construction only
        (not incl. surface resistances)
        """
        return (1.0 / u_value) - cls.__r_si(pitch=pitch) - R_SE

    @classmethod
    def pitch_class(cls, pitch: float) -> HeatFlowDirection:
        """Return whether element is horizontal upwards/downwards or vertical"""
        # TODO use is floor and is ceiling functions so determine R SI values
        if pitch >= PITCH_LIMIT_HORIZ_CEILING and pitch <= PITCH_LIMIT_HORIZ_FLOOR:
            return HeatFlowDirection.HORIZONTAL
        elif pitch < PITCH_LIMIT_HORIZ_CEILING:
            return HeatFlowDirection.UPWARDS
        elif pitch > PITCH_LIMIT_HORIZ_FLOOR:
            return HeatFlowDirection.DOWNWARDS
        else:
            raise ValueError("Pitch class not recognised")


class HeatTransferInternalCommon(HeatTransferInternal):
    pass


class HeatTransferThrough(BuildingElementBase):
    def __init__(
        self, thermal_resistance_construction: float | None, areal_heat_capacity: float
    ) -> None:
        self._r_c = thermal_resistance_construction
        self._k_m = areal_heat_capacity

    def no_of_nodes(self) -> int:
        """Return number of nodes including external and internal layers"""
        return len(self.k_pli)

    def no_of_inside_nodes(self) -> int:
        """Return number of nodes excluding external and internal layers"""
        return self.no_of_nodes() - 2

    def fabric_heat_loss(self) -> float:
        """Return the fabric heat loss for the building element"""
        if self._r_c is None:
            raise ValueError("_r_c is None")  # PRAGMA: nocover
        U_value = 1.0 / (self._r_c + self.r_se() + self.r_si())
        return self.area * U_value

    def heat_capacity(self) -> float:
        """Return the fabric heat capacity for the building element"""
        return self.area * (self._k_m / units.J_per_kJ)

    def h_pli(self, idx) -> float:
        return self._h_pli[idx]


class HeatTransferThrough2Nodes(HeatTransferThrough):
    def __init__(self, thermal_resistance_construction: float) -> None:
        super().__init__(
            thermal_resistance_construction=thermal_resistance_construction, areal_heat_capacity=0
        )
        # Calculate node conductances (h_pli) and node heat capacities (k_pli)
        # according to BS EN ISO 52016-1:2017, section 6.5.7.4
        self.init_h_pli(thermal_resistance_construction=thermal_resistance_construction)
        self.init_k_pli()

    def init_h_pli(self, thermal_resistance_construction: float) -> None:
        self._h_pli = [1.0 / thermal_resistance_construction]

    def init_k_pli(self) -> None:
        self.k_pli = [0.0, 0.0]


class HeatTransferThrough5Nodes(HeatTransferThrough):
    def __init__(
        self,
        thermal_resistance_construction: float,
        mass_distribution_class: MassDistributionClass,
        areal_heat_capacity: float,
    ) -> None:
        super().__init__(
            thermal_resistance_construction=thermal_resistance_construction,
            areal_heat_capacity=areal_heat_capacity,
        )
        self.init_h_pli(thermal_resistance_construction=thermal_resistance_construction)
        self.init_k_pli(
            mass_distribution_class=mass_distribution_class, areal_heat_capacity=areal_heat_capacity
        )

    def init_h_pli(self, thermal_resistance_construction: float) -> None:
        h_outer = 6.0 / thermal_resistance_construction
        h_inner = 3.0 / thermal_resistance_construction
        self._h_pli = [h_outer, h_inner, h_inner, h_outer]

    def init_k_pli(
        self, mass_distribution_class: MassDistributionClass, areal_heat_capacity: float
    ) -> None:
        if mass_distribution_class == MassDistributionClass.I:
            self.k_pli = [0.0, 0.0, 0.0, 0.0, areal_heat_capacity]
        elif mass_distribution_class == MassDistributionClass.E:
            self.k_pli = [areal_heat_capacity, 0.0, 0.0, 0.0, 0.0]
        elif mass_distribution_class == MassDistributionClass.IE:
            k_ie = areal_heat_capacity / 2.0
            self.k_pli = [k_ie, 0.0, 0.0, 0.0, k_ie]
        elif mass_distribution_class == MassDistributionClass.D:
            k_inner = areal_heat_capacity / 4.0
            k_outer = areal_heat_capacity / 8.0
            self.k_pli = [k_outer, k_inner, k_inner, k_inner, k_outer]
        elif mass_distribution_class == MassDistributionClass.M:
            self.k_pli = [0.0, 0.0, areal_heat_capacity, 0.0, 0.0]
        else:
            raise ValueError(f"Mass distribution class ({mass_distribution_class}) not valid")
            # TODO Exit just the current case instead of whole program entirely?


class HeatTransferThrough3Plus2Nodes(HeatTransferThrough):
    def __init__(
        self,
        thermal_resistance_floor_construction: float,
        r_gr: float,
        mass_distribution_class: MassDistributionClass,
        k_gr: float,
        areal_heat_capacity: float,
    ) -> None:
        super().__init__(None, areal_heat_capacity)
        # Calculate node conductances (h_pli) and node heat capacities (k_pli)
        # according to BS EN ISO 52016-1:2017, section 6.5.7.4
        self.init_h_pli(
            thermal_resistance_floor_construction=thermal_resistance_floor_construction, r_gr=r_gr
        )
        self.init_k_pli(
            mass_distribution_class=mass_distribution_class,
            k_gr=k_gr,
            areal_heat_capacity=areal_heat_capacity,
        )

    def init_h_pli(self, thermal_resistance_floor_construction: float, r_gr: float) -> None:
        """BS EN ISO 52016:2017 states that the thermal_resistance_construction (resistance including the
        effect of the ground) should be used in the equations below. However,
        this leads to double-counting of r_si, r_gr and r_vi as these are already
        accounted for separately, so we have used thermal_resistance_floor_construction (resistance of the floor
        construction only) here instead
        """
        h_4 = 4.0 / thermal_resistance_floor_construction
        h_3 = 2.0 / thermal_resistance_floor_construction
        h_2 = 1.0 / (thermal_resistance_floor_construction / 4 + r_gr / 2)
        h_1 = 2.0 / r_gr
        self._h_pli = [h_1, h_2, h_3, h_4]

    def init_k_pli(self, mass_distribution_class: MassDistributionClass, k_gr, areal_heat_capacity):
        if mass_distribution_class == MassDistributionClass.I:
            self.k_pli = [0.0, k_gr, 0.0, 0.0, areal_heat_capacity]
        elif mass_distribution_class == MassDistributionClass.E:
            self.k_pli = [0.0, k_gr, areal_heat_capacity, 0.0, 0.0]
        elif mass_distribution_class == MassDistributionClass.IE:
            k_ie = areal_heat_capacity / 2.0
            self.k_pli = [0.0, k_gr, k_ie, 0.0, k_ie]
        elif mass_distribution_class == MassDistributionClass.D:
            k_inner = areal_heat_capacity / 2.0
            k_outer = areal_heat_capacity / 4.0
            self.k_pli = [0.0, k_gr, k_outer, k_inner, k_outer]
        elif mass_distribution_class == MassDistributionClass.M:
            self.k_pli = [0.0, k_gr, 0.0, areal_heat_capacity, 0.0]
        else:
            raise ValueError(f"Mass distribution class ({mass_distribution_class}) not valid")
            # TODO Exit just the current case instead of whole program entirely?


class HeatTransferOtherSide(BuildingElementBase):
    def __init__(self, f_sky: float = 0) -> None:
        """
        f_sky -- view factor to the sky (see BS EN ISO 52016-1:2017, section 6.5.13.3)
        """
        self.f_sky = f_sky
        self.therm_rad_to_sky = f_sky * self.h_re() * temp_diff_sky

    def r_se(self) -> float:
        """Return external surface resistance, in m2 K / W"""
        return R_SE

    def h_ce(self) -> float:
        """Return external convective heat transfer coefficient, in W / (m2.K)"""
        return H_CE

    def h_re(self) -> float:
        """Return external radiative heat transfer coefficient, in W / (m2.K)"""
        return H_RE

    def temp_ext(self) -> float:
        """Return the temperature of the air on the other side of the building element"""
        return self._external_conditions.air_temp()
        # TODO For now, this only handles building elements to the outdoor
        #      environment, not e.g. elements to adjacent zones.

    def fabric_heat_loss(self) -> float:
        raise RuntimeError("fabric_heat_loss can't be called")


class HeatTransferOtherSideGround(HeatTransferOtherSide):
    # Assume values for temp_int_annual and temp_int_monthly
    # These are based on SAP 10 notional building runs for 5 archetypes used
    # for inter-model comparison/validation. The average of the monthly mean
    # internal temperatures from each run was taken.
    __TEMP_INT_MONTHLY = [
        19.46399546,
        19.66940204,
        19.90785898,
        20.19719837,
        20.37461865,
        20.45679018,
        20.46767703,
        20.46860812,
        20.43505593,
        20.22266322,
        19.82726777,
        19.45430847,
    ]

    def __init__(
        self,
        r_vi: float,
        d_we: float,
        thermal_conductivity: float,
        r_si: float,
        thermal_resistance_floor_construction: float,
        floor_type: FloorType,
        periodic_penetration_depth: float,
        total_area: float,
        perimeter: float,
        u_value: float,
        psi_wall_floor_junc: float,
        h_upper: float,
        z_b: float | None,
        h_w: float | None,
        u_w: float,
        u_f_s: float | None,
        area_per_perimeter_vent: float,
        r_f_ins: float,
        shield_fact_location: WindShieldLocation | None,
        edge_insulation: list[dict[str, Any]],
        r_w_b: float | None,
    ) -> None:
        super().__init__()

        self.__temp_int_annual = units.average_monthly_to_annual(
            list_monthly_averages=self.__TEMP_INT_MONTHLY
        )

        def total_equiv_thickness() -> float:
            equi_thick_ground = d_we + thermal_conductivity * (
                r_si + thermal_resistance_floor_construction + self.r_se()
            )
            return equi_thick_ground

        def init_periodic_heat_transfer() -> tuple[float, float]:
            """
            Return the periodic heat transfer coefficient for the building element
            h_pi     -- Internal periodic heat transfer coefficient, in W / K
                        BS EN ISO 13370:2017 Annex H
            h_pe     -- external periodic heat transfer coefficient, in W / K
                        BS EN ISO 13370:2017 Annex H
            """
            if floor_type == FloorType.SLAB_NO_EDGE_INSULATION:
                h_pi, h_pe = init_slab_on_ground_floor_uninsulated_or_all_insulation()
                return h_pi, h_pe

            elif floor_type == FloorType.SLAB_EDGE_INSULATION:
                h_pi, h_pe = init_slab_on_ground_floor_edge_insulated()
                return h_pi, h_pe

            elif floor_type == FloorType.SUSPENDED_FLOOR:
                h_pi, h_pe = init_suspended_floor()
                return h_pi, h_pe

            elif floor_type == FloorType.HEATED_BASEMENT:
                h_pi, h_pe = init_heated_basement()
                return h_pi, h_pe

            elif floor_type == FloorType.UNHEATED_BASEMENT:
                h_pi, h_pe = init_unheated_basement()
                return h_pi, h_pe

            else:
                raise ValueError(f"Type of Floor ({floor_type}) is not valid")

        def internal_temp_variation() -> float:
            # H.4.1., H.5.1. Internal temperature variation
            h_pi = (
                total_area
                * (thermal_conductivity / self.__d_eq)
                * (2 / ((1 + periodic_penetration_depth / self.__d_eq) ** 2 + 1)) ** 0.5
            )
            return h_pi

        def init_slab_on_ground_floor_uninsulated_or_all_insulation() -> tuple[float, float]:
            """
            Slab-on-ground floor uninsulated or with all-over insulated
            """

            # H.4.1. Internal temperature variation
            h_pi = internal_temp_variation()

            # H.4.2. External temperature variation
            # 0.37 is constant in the standard but not labelled
            h_pe = (
                0.37
                * perimeter
                * thermal_conductivity
                * log(periodic_penetration_depth / self.__d_eq + 1)
            )
            return h_pi, h_pe

        def init_slab_on_ground_floor_edge_insulated() -> tuple[float, float]:
            """Slab-on-ground-with-edge-insulation"""

            # H.5.1. Internal temperature variation
            h_pi = internal_temp_variation()

            # edge insulation (vertically or horizontally)
            h_pe = edge_type()

            return h_pi, h_pe

        def h_pe_h(D_h: float, r_n: float) -> float:
            # horizontal edge insulation
            # 0.37 is constant in the standard but not labelled
            eq_thick_additional = add_eq_thickness(d_n=D_h, r_n=r_n)
            h_pe = (
                0.37
                * perimeter
                * thermal_conductivity
                * (
                    (1 - exp((-D_h / periodic_penetration_depth)))
                    * log(periodic_penetration_depth / (self.__d_eq + eq_thick_additional) + 1)
                    + exp(-D_h / periodic_penetration_depth)
                    * log(periodic_penetration_depth / self.__d_eq + 1)
                )
            )
            return h_pe

        def h_pe_v(D_v: float, r_n: float) -> float:
            # vertical edge insulation
            # 0.37 is constant in the standard but not labelled
            eq_thick_additional = add_eq_thickness(d_n=D_v, r_n=r_n)
            h_pe = (
                0.37
                * perimeter
                * thermal_conductivity
                * (
                    (1 - exp((-2 * D_v / periodic_penetration_depth)))
                    * log(periodic_penetration_depth / (self.__d_eq + eq_thick_additional) + 1)
                    + exp(-2 * D_v / periodic_penetration_depth)
                    * log(periodic_penetration_depth / self.__d_eq + 1)
                )
            )
            return h_pe

        def add_eq_thickness(d_n: float, r_n: float) -> float:
            """Additional equivalent thickness"""
            #  m2·K/W, thermal resistance
            r_add_eq = r_n - d_n / thermal_conductivity
            # m, thickness_edge-insulation or foundation
            d_add_eq = r_add_eq * thermal_conductivity
            return d_add_eq

        def edge_type() -> float:
            """edge insulation vertically or horizontally"""
            # Initialise edge width and depth
            h_pe_list = []
            for edge in edge_insulation:
                if edge["type"] == EdgeInsulationDirection.HORIZONTAL:
                    h_pe_list.append(h_pe_h(edge["width"], edge["edge_thermal_resistance"]))
                elif edge["type"] == EdgeInsulationDirection.VERTICAL:
                    h_pe_list.append(h_pe_v(edge["depth"], edge["edge_thermal_resistance"]))
                else:
                    raise ValueError(f"Type edge_insulation ({edge_insulation}) is not valid")
            h_pe = min(h_pe_list)
            return h_pe

        def init_suspended_floor() -> tuple[float, float]:
            """Suspended floor periodic coefficients"""

            # H.6.1.
            # thermal transmittance of suspended part of floor, in W/(m2·K)
            u_f = thermal_transmittance_sus_floor()

            # equivalent thermal transmittance, in W/(m2·K)
            u_x = equiv_therma_trans()

            # equivalent thickness, in m
            d_g = total_equiv_thickness_sus()

            # H.6.2. Internal temperature variation
            h_pi = total_area * (
                1 / u_f + 1 / (thermal_conductivity / periodic_penetration_depth + u_x)
            )

            # H.6.3. External temperature variation
            # 0.37 is constant in the standard but not labelled
            h_pe = u_f * (
                (
                    0.37
                    * perimeter
                    * thermal_conductivity
                    * log(periodic_penetration_depth / d_g + 1)
                    + u_x * total_area
                )
                / (thermal_conductivity / (periodic_penetration_depth + u_x + u_f))
            )
            return h_pi, h_pe

        def thermal_transmittance_sus_floor() -> float:
            """thermal transmittance of suspended part of floor"""
            return 1 / (thermal_resistance_floor_construction + 2 * r_si)

        def equiv_therma_trans() -> float:
            """equivalent thermal transmittance between the underfloor space and the outside"""

            # Characteristic dimension of floor
            char_dimen = charac_dimen_floor()

            # 1450 is constant in the standard but not labelled
            eq_therm_tran = (
                2 * (self.__h_upper * self.__u_w / char_dimen)
                + 1450
                * (self.__area_per_perimeter_vent * wind_speed() * wind_shield_fact())
                / char_dimen
            )
            return eq_therm_tran

        def total_equiv_thickness_sus() -> float:
            """Equivalent thickness for the ground"""
            equi_thick_ground = d_we + thermal_conductivity * (r_si + self.__r_f_ins + self.r_se())
            return equi_thick_ground

        def charac_dimen_floor() -> float:
            """Characteristic dimension of floor"""
            return total_area / (0.5 * perimeter)  # in m

        def wind_speed() -> float:
            """average wind speed at 10 m height"""
            return self._external_conditions.wind_speed_annual()  # in  m/s

        def wind_shield_fact() -> float:
            """wind shielding factor"""
            # Values from BS EN ISO 13370:2017 Table 8
            if self.__shield_fact_location == WindShieldLocation.SHELTERED:
                wind_s_factor = 0.02

            elif self.__shield_fact_location == WindShieldLocation.AVERAGE:
                wind_s_factor = 0.05

            elif self.__shield_fact_location == WindShieldLocation.EXPOSED:
                wind_s_factor = 0.10

            else:
                raise ValueError(
                    f"Type of wind shield location ({self.__shield_fact_location}) is not valid"
                )
            return wind_s_factor

        def init_heated_basement() -> tuple[float, float]:
            """Heated basement periodic coefficients"""

            if self.__z_b is None:
                raise ValueError("HEATED_BASEMENT requires z_b")  # pragma: no cover

            # total equivalent thickness
            d_w_b = equiv_thick_base_wall()

            # H.7.1. Internal temperature variation
            h_pi = (
                total_area
                * (
                    (thermal_conductivity / self.__d_eq)
                    * (2 / (1 + periodic_penetration_depth / self.__d_eq) ** 2 + 1) ** 0.5
                )
                + self.__z_b
                * perimeter
                * (thermal_conductivity / d_w_b)
                * (2 / ((1 + periodic_penetration_depth / d_w_b) ** 2 + 1)) ** 0.5
            )

            # H.7.2. External temperature variation
            # 0.37 is constant in the standard but not labelled
            h_pe = (
                0.37
                * perimeter
                * thermal_conductivity
                * (
                    exp(-self.__z_b / periodic_penetration_depth)
                    * log(periodic_penetration_depth / self.__d_eq + 1)
                    + 2
                    * (1 - exp(-self.__z_b / periodic_penetration_depth))
                    * log(periodic_penetration_depth / d_w_b + 1)
                )
            )
            return h_pi, h_pe

        def equiv_thick_base_wall() -> float:
            """Equivalent thickness for the basement walls"""

            if r_w_b is None:
                raise ValueError(
                    "HEATED_BASEMENT and UNHEATED_BASEMENT require r_w_b"
                )  # pragma: no cover

            # r_w_b is the thermal resistance of the walls
            equiv_base_wall = thermal_conductivity * (r_si + r_w_b + self.r_se())
            return equiv_base_wall

        def init_unheated_basement() -> tuple[float, float]:
            """Unheated basement"""

            if h_w is None or self.__z_b is None or self.__u_f_s is None:
                raise ValueError(
                    "UNHEATED_BASEMENT requires h_w, z_b and __u_f_s"
                )  # pragma: no cover

            thermal_capacity_air = 0.33  # Wh/(m3·K)
            air_vol_base = total_area * (h_w + self.__z_b)

            # air changes per hour
            # From BS EN ISO 13370:2017 section 7.4
            vent_rate_base = 0.3

            # H.8.1. Internal temperature variation
            h_pi = (
                1 / (total_area * self.__u_f_s)
                + 1
                / (
                    (total_area + self.__z_b * perimeter)
                    * thermal_conductivity
                    / periodic_penetration_depth
                    + h_w * perimeter * self.__u_w
                    + thermal_capacity_air * vent_rate_base * air_vol_base
                )
            ) ** -1

            # H.8.2. External temperature variation
            # 0.37 is constant in the standard but not labelled
            h_pe = (
                total_area
                * self.__u_f_s
                * (
                    0.37
                    * perimeter
                    * thermal_conductivity
                    * (2 - exp(-self.__z_b / periodic_penetration_depth))
                    * log(periodic_penetration_depth / self.__d_eq + 1)
                    + h_w * perimeter * self.__u_w
                    + thermal_capacity_air * vent_rate_base * air_vol_base
                )
                / (
                    (total_area + self.__z_b * perimeter)
                    * thermal_conductivity
                    / periodic_penetration_depth
                    + h_w * perimeter * self.__u_w
                    + thermal_capacity_air * vent_rate_base * air_vol_base
                    + total_area * self.__u_f_s
                )
            )
            return h_pi, h_pe

        self.__total_area = total_area
        self.__perimeter = perimeter
        self.__u_value = u_value
        self.__psi_wall_floor_junc = psi_wall_floor_junc
        self.__h_upper = h_upper
        self.__z_b = z_b
        self.__u_w = u_w
        self.__u_f_s = u_f_s
        self.__area_per_perimeter_vent = area_per_perimeter_vent
        self.__r_f_ins = r_f_ins
        self.__shield_fact_location = shield_fact_location

        # Set external surface heat transfer coeffs as per BS EN ISO 52016-1:2017 eqn 49
        # Must be set before initialisation of base class, as these are referenced there
        # BS EN ISO 52016-1:2017 Table 14 validity interval h_ce 0 to 50
        self.__h_ce = 1.0 / r_vi  # in W/(m2.K)
        self.__d_eq = total_equiv_thickness()
        self.__h_pi, self.__h_pe = init_periodic_heat_transfer()

    def h_ce(self) -> float:
        """Return external convective heat transfer coefficient, in W / (m2.K)"""
        return self.__h_ce

    def h_re(self) -> float:
        """Return external radiative heat transfer coefficient, in W / (m2.K)"""
        return 0.0

    def temp_ext(self) -> float:
        """Return the temperature on the other side of the building element"""
        temp_ext_annual = self._external_conditions.air_temp_annual()
        temp_ext_month = self._external_conditions.air_temp_monthly()

        current_month = self._simulation_time.current_month()
        temp_int_month = self.__TEMP_INT_MONTHLY[current_month]

        # BS EN ISO 13370:2017 Eqn C.4
        heat_flow_month = (
            self.__u_value * self.__total_area * (self.__temp_int_annual - temp_ext_annual)
            + self.__perimeter * self.__psi_wall_floor_junc * (temp_int_month - temp_ext_month)
            - self.__h_pi * (self.__temp_int_annual - temp_int_month)
            + self.__h_pe * (temp_ext_annual - temp_ext_month)
        )

        # BS EN ISO 13370:2017 Eqn F.2
        temp_ground_virtual = temp_int_month - (
            heat_flow_month
            - (
                self.__perimeter
                * self.__psi_wall_floor_junc
                * (self.__temp_int_annual - temp_ext_annual)
            )
        ) / (self.__total_area * self.__u_value)

        return temp_ground_virtual


class HeatTransferOtherSideConditionedSpace(HeatTransferOtherSide):
    def h_ce(self) -> float:
        """Return external convective heat transfer coefficient, in W / (m2.K)"""
        # Element is adjacent to another building / thermally conditioned zone
        # therefore according to BS EN ISO 52016-1:2017, section 6.5.6.3.6,
        # external heat transfer coefficients are zero
        return 0.0

    def h_re(self) -> float:
        """Return external radiative heat transfer coefficient, in W / (m2.K)"""
        # Element is adjacent to another building / thermally conditioned zone
        # therefore according to BS EN ISO 52016-1:2017, section 6.5.6.3.6,
        # external heat transfer coefficients are zero
        return 0.0


class HeatTransferOtherSideUnconditionedSpace(HeatTransferOtherSide):
    def __init__(self, thermal_resistance_unconditioned_space: float) -> None:
        super().__init__()

        self.__r_u = thermal_resistance_unconditioned_space

    def h_ce(self) -> float:
        """Return external convective heat transfer coefficient, in W / (m2.K)"""
        # Add an additional thermal resistance to the outside of the wall and
        # incorporate this in the values for the external surface heat transfer
        # coefficient.
        # As this is an adjusted figure in this class, and the split between
        # h_ce and h_re does not affect the calculation results, assign entire
        # effective surface heat transfer to h_ce and set h_re to zero.
        h_ce = super().h_ce()
        h_re = super().h_re()
        h_se = h_ce + h_re
        r_se = 1.0 / h_se
        r_se_effective = r_se + self.__r_u
        return 1.0 / r_se_effective

    def h_re(self) -> float:
        """Return external radiative heat transfer coefficient, in W / (m2.K)"""
        # As this is an adjusted figure in this class, and the split between
        # h_ce and h_re does not affect the calculation results, assign entire
        # effective surface heat transfer to h_ce and set h_re to zero.
        return 0.0


class HeatTransferOtherSideOutside(HeatTransferOtherSide):
    def __init__(self, pitch: float) -> None:
        # This is the f_sky value for an unshaded surface
        f_sky = sky_view_factor(pitch=pitch)

        super().__init__(f_sky=f_sky)


class SolarRadiationInteraction(BuildingElementBase):
    def __init__(
        self,
        pitch: float,
        orientation: units.Orientation360 | None,
        shading: list[dict[str, Any]] | None,
        base_height: float,
        projected_height: float,
        width: float,
        solar_absorption_coeff: float,
    ):
        """
        solar_absorption_coeff -- solar absorption coefficient at the external surface (dimensionless)
                 according to BS EN ISO 52016-1:2017, section 6.5.7.3
        """
        self._external_pitch = pitch
        self._orientation = orientation
        self._shading = shading
        self._base_height = base_height
        self._projected_height = projected_height
        self._width = width
        self.solar_absorption_coeff = solar_absorption_coeff

    def i_sol_dir_dif(self) -> tuple[float, float]:
        """Return default of zero for i_sol_dir and i_sol_dif"""
        return 0.0, 0.0

    def solar_gains(self) -> float:
        """Return default of zero for solar gains"""
        return 0

    def shading_factors_direct_diffuse(self) -> tuple[float, float]:
        """Return default of one for shading factor (no shading)"""
        return 1.0, 1.0


class SolarRadiationInteractionAbsorbed(SolarRadiationInteraction):
    def i_sol_dir_dif(self) -> tuple[float, float]:
        """Return calculated i_sol_dir and i_sol_dif using pitch and orientation of element"""
        if self._orientation is None:
            raise ValueError(
                "Cannot compute direct and diffuse irradiance because orientation is None."
            )

        i_sol_dir, i_sol_dif, _, _ = (
            self._external_conditions.calculated_direct_diffuse_total_irradiance(
                tilt=self._external_pitch, orientation=self._orientation
            )
        )
        return i_sol_dir, i_sol_dif

    def shading_factors_direct_diffuse(self) -> tuple[float, float]:
        """Return calculated shading factor"""
        if self._orientation is None:
            raise ValueError(
                "Cannot compute direct and diffuse shading factors because orientation is None."
            )

        return self._external_conditions.shading_reduction_factor_direct_diffuse(
            base_height=self._base_height,
            height=self._projected_height,
            width=self._width,
            tilt=self._external_pitch,
            orientation=self._orientation,
            window_shading=[],
        )


class SolarRadiationInteractionTransmitted(SolarRadiationInteraction):
    def __init__(
        self,
        simtime: SimulationTime,
        pitch: float,
        orientation: units.Orientation360 | None,
        shading: list[dict[str, Any]],
        base_height: float,
        projected_height: float,
        width: float,
        solar_absorption_coeff: float,
    ) -> None:
        self._simtime = simtime
        super().__init__(
            pitch=pitch,
            orientation=orientation,
            shading=shading,
            base_height=base_height,
            projected_height=projected_height,
            width=width,
            solar_absorption_coeff=solar_absorption_coeff,
        )

    def convert_g_value(self) -> float:
        """return g_value corrected for angle of solar radiation"""

        # TODO for windows with scattering glazing or solar shading provisions
        # there is a different, more complex method for conversion that depends on
        # timestep (via solar altitude).
        # suggest this is implemented at the same time as window shading (devices
        # rather than fixed features) as will also need to link to shading schedule.
        # see ISO 52016 App E. Page 177
        # How do we know whether a window has "scattering glazing"?

        # g_value = agl * g_alt + (1 - agl) * g_dif

        Fw = 0.90
        # default from ISO 52016 App B Table B.22
        g_value = Fw * self._g_value

        return g_value

    def solar_gains(self) -> float:  # TODO: Can't be added to a super class as it handles to much
        """Return calculated solar gains using pitch and orientation of element"""

        g_value = self.convert_g_value()

        if self._orientation is None:
            raise ValueError("Cannot compute surface irradiance because orientation is None.")
        if self._shading is None:
            raise ValueError("Cannot compute surface irradiance because window shading is None.")

        surf_irrad = self._external_conditions.surface_irradiance(
            base_height=self._base_height,
            projected_height=self._projected_height,
            width=self._width,
            tilt=self._pitch,
            orientation=self._orientation,
            window_shading=self._shading,
        )
        solar_gains = g_value * surf_irrad * self.area * (1 - self._frame_area_fraction)

        return solar_gains

    def shading_factors_direct_diffuse(self) -> tuple[float, float]:
        """return calculated shading factor"""

        if self._orientation is None:
            raise ValueError("Cannot compute shading factor because orientation is None.")
        if self._shading is None:
            raise ValueError("Cannot compute shading factor because window shading is None.")

        return self._external_conditions.shading_reduction_factor_direct_diffuse(
            base_height=self._base_height,
            height=self._projected_height,
            width=self._width,
            tilt=self._pitch,
            orientation=self._orientation,
            window_shading=self._shading,
        )


class SolarRadiationInteractionNotExposed(SolarRadiationInteraction):
    pass


class BuildingElement:
    """A base class with common functionality for building elements

    Classes for particular types of building element should inherit from this
    one and add/override functionality as required. It is not intended for
    objects of this class to be used directly.

    Subclasses should calculate/implement (at least) the following:
    self.h_pli(idx) -- function to return element at position idx from
                       list (len = number of nodes - 1) of thermal conductances,
                       in W / (m2.K) . Element 0 will be conductance between nodes
                       0 and 1. Calculate according to BS EN ISO 52016-1:2017,
                       section 6.5.7
    self.k_pli      -- list of areal heat capacities for each node, in J / (m2.K)
                       Calculate according to BS EN ISO 52016-1:2017, section 6.5.7
    self.temp_ext() -- function to return the temperature of the external
                       environment, in deg C
    """

    def __init__(self, ext_cond: ExternalConditions, area: float, pitch: float) -> None:
        """Initialisation common to all building element types

        Arguments (names based on those in BS EN ISO 52016-1:2017):
        ext_cond -- reference to ExternalConditions object
        area  -- area (in m2) of this building element
        pitch -- tilt angle of the surface from horizontal, in degrees between 0 and 180,
                 where 0 means the external surface is facing up, 90 means the external
                 surface is vertical and 180 means the external surface is facing down

        Other variables:
        i_sol_dif -- diffuse part (EXCLUDING circumsolar, as specified in ISO 52010)
                     of the solar irradiance on the element, in W / m2
        i_sol_dir -- direct part (INCLUDING circumsolar, as specified in ISO 52010)
                     of the solar irradiance on the element, in W / m2
        shading_factor -- shading reduction_factor for shading objects for the element
        therm_rad_to_sky -- thermal radiation to the sky, in W / m2, calculated
                            according to BS EN ISO 52016-1:2017, section 6.5.13.3
        """
        self._external_conditions = ext_cond
        self.area = area
        self._pitch = pitch

    @classmethod
    def convert_uvalue_to_resistance(cls, u_value: float, pitch: float) -> float:
        # Breaks the OO inheritance model!
        return HeatTransferInternal.convert_uvalue_to_resistance(u_value=u_value, pitch=pitch)

    @classmethod
    def pitch_class(cls, pitch: float) -> HeatFlowDirection:
        # Breaks the OO inheritance model!
        return HeatTransferInternal.pitch_class(pitch=pitch)


class BuildingElementOpaque(
    BuildingElement,
    HeatTransferInternalCommon,
    HeatTransferThrough5Nodes,
    HeatTransferOtherSideOutside,
    SolarRadiationInteractionAbsorbed,
):  # Common, 5 nodes, Outside, Absorbed
    """A class to represent opaque building elements (walls, roofs, etc.)"""

    def __init__(
        self,
        area: float,
        is_unheated_pitched_roof: bool,
        pitch: float,
        solar_absorption_coeff: float,
        thermal_resistance_construction: float,
        areal_heat_capacity: float,
        mass_distribution_class: MassDistributionClass,
        orientation: units.Orientation360 | None,
        base_height: float,
        height: float,
        width: float,
        ext_cond: ExternalConditions,
    ) -> None:
        """Construct a BuildingElementOpaque object

        Arguments (names based on those in BS EN ISO 52016-1:2017):
        area -- net area of the opaque building element (i.e. minus any windows / doors / etc.)
        pitch -- tilt angle of the surface from horizontal, in degrees between 0 and 180,
                 where 0 means the external surface is facing up, 90 means the external
                 surface is vertical and 180 means the external surface is facing down
        solar_absorption_coeff    -- solar absorption coefficient at the external surface (dimensionless)
        thermal_resistance_construction      -- thermal resistance, in m2.K / W
        areal_heat_capacity      -- areal heat capacity, in J / (m2.K)
        orientation -- is the orientation angle of the inclined surface, expressed as the
                       geographical azimuth angle of the horizontal projection of the inclined
                       surface normal, 0 to 360, in degrees
        base_height -- is the distance between the ground and the lowest edge of the element, in m
        height      -- is the height of the building element, in m
        width       -- is the width of the building element, in m
        ext_cond -- reference to ExternalConditions object
        mass_distribution_class
                 -- distribution of mass in building element, one of:
                    - 'I':  mass concentrated on internal side
                    - 'E':  mass concentrated on external side
                    - 'IE': mass divided over internal and external side
                    - 'D':  mass equally distributed
                    - 'M':  mass concentrated inside

        Other variables:
        f_sky -- view factor to the sky (see BS EN ISO 52016-1:2017, section 6.5.13.3)
        """
        # To determine if element is a unheated pitched roof

        if is_unheated_pitched_roof:
            internal_pitch = 0
        else:
            internal_pitch = pitch

        # Initialise the base BuildingElement class
        super().__init__(ext_cond=ext_cond, area=area, pitch=internal_pitch)
        HeatTransferThrough5Nodes.__init__(
            self,
            thermal_resistance_construction=thermal_resistance_construction,
            mass_distribution_class=mass_distribution_class,
            areal_heat_capacity=areal_heat_capacity,
        )
        HeatTransferOtherSideOutside.__init__(self, pitch=pitch)
        # shading is None because the model ignores nearby shading on opaque elements
        SolarRadiationInteractionAbsorbed.__init__(
            self,
            pitch=pitch,
            orientation=orientation,
            shading=None,
            base_height=base_height,
            projected_height=projected_height(pitch, height),
            width=width,
            solar_absorption_coeff=solar_absorption_coeff,
        )


class BuildingElementPartyWall(
    BuildingElement,
    HeatTransferInternalCommon,
    HeatTransferThrough5Nodes,
    HeatTransferOtherSideUnconditionedSpace,
    SolarRadiationInteractionNotExposed,
):  # Common, 5 nodes, Unconditioned space, Not exposed
    """A class to represent all party wall building elements

    This class handles all party wall types, with specific provisions for cavity walls
    where heat loss via air movement occurs. Research has shown this heat loss to be
    significant in cavity party walls, contrary to historical assumptions of negligible
    heat transfer.

    For cavity party walls, heat loss is modelled by treating the cavity as an
    unconditioned space with an effective thermal resistance that depends on the
    cavity type. The thermal resistance values (R_cavity) are derived from equivalent
    U-values which are based on research into air movement patterns within party wall cavities:
    - Solid walls and filled-sealed cavities: R_cavity = 0 (no heat loss via cavity)
    - Unfilled unsealed cavities: R_cavity ≈ 1.5 m².K/W
    - Unfilled sealed cavities: R_cavity ≈ 4.5 m².K/W

    Note: This approach does not explicitly model losses via air movement in party
    ceilings/floors, though these may be implicitly included in the cavity resistance
    values derived from the original research.
    """

    def __init__(
        self,
        area: float,
        pitch: float,
        thermal_resistance_construction: float,
        party_wall_cavity_type: str,
        party_wall_lining_type: str | None,
        thermal_resistance_cavity: float | None,
        areal_heat_capacity: float,
        mass_distribution_class: MassDistributionClass,
        ext_cond: ExternalConditions,
    ) -> None:
        """Construct a BuildingElementPartyWall object

        Arguments (names based on those in BS EN ISO 52016-1:2017):
        area     -- area (in m2) of this building element
        pitch -- tilt angle of the surface from horizontal, in degrees between 0 and 180,
                 where 0 means the external surface is facing up, 90 means the external
                 surface is vertical and 180 means the external surface is facing down
        thermal_resistance_construction -- thermal resistance of wall layers before the cavity, in m2.K / W
        party_wall_cavity_type -- type of party wall cavity (solid, unfilled_unsealed,
                                  unfilled_sealed, filled_sealed, or defined_resistance)
        party_wall_lining_type -- type of party wall lining (wet_plaster, or dry_lined)
        thermal_resistance_cavity -- effective thermal resistance of the cavity, in m2.K / W;
                    required only for 'defined_resistance' type, otherwise calculated automatically
        areal_heat_capacity      -- areal heat capacity, in J / (m2.K)
        mass_distribution_class
                 -- distribution of mass in building element, one of:
                    - 'I':  mass concentrated on internal side
                    - 'E':  mass concentrated on external side
                    - 'IE': mass divided over internal and external side
                    - 'D':  mass equally distributed
                    - 'M':  mass concentrated inside
        ext_cond -- reference to ExternalConditions object

        Other variables:
        f_sky -- view factor to the sky (see BS EN ISO 52016-1:2017, section 6.5.13.3)
        h_ce     -- external convective heat transfer coefficient, in W / (m2.K)
        h_re     -- external radiative heat transfer coefficient, in W / (m2.K)
        solar_absorption_coeff    -- solar absorption coefficient at the external surface (dimensionless)
        """
        self._party_wall_cavity_type = party_wall_cavity_type
        self._party_wall_lining_type = party_wall_lining_type
        # Calculate the effective thermal resistance of the unconditioned space (cavity)
        # based on the party wall cavity type and party wall lining type
        r_unconditioned = calculate_cavity_resistance(
            party_wall_cavity_type=party_wall_cavity_type,
            party_wall_lining_type=party_wall_lining_type,
            thermal_resistance_cavity=thermal_resistance_cavity,
        )

        # Initialise the base BuildingElement class
        super().__init__(ext_cond, area, pitch)
        HeatTransferThrough5Nodes.__init__(
            self,
            thermal_resistance_construction=thermal_resistance_construction,
            mass_distribution_class=mass_distribution_class,
            areal_heat_capacity=areal_heat_capacity,
        )
        HeatTransferOtherSideUnconditionedSpace.__init__(
            self, thermal_resistance_unconditioned_space=r_unconditioned
        )
        # Solar absorption coefficient at the external surface is zero
        # (party walls are not exposed to solar radiation)
        SolarRadiationInteractionNotExposed.__init__(
            self,
            pitch=pitch,
            orientation=None,
            shading=None,
            base_height=0,
            projected_height=0,
            width=0,
            solar_absorption_coeff=0,
        )

    def h_ce(self) -> float:
        """Return external convective heat transfer coefficient, in W / (m2.K)"""
        # For party walls with solid or filled_sealed cavity types, return zero
        # to represent adiabatic boundary condition (no heat loss)
        if self._party_wall_cavity_type in (
            PartyWallCavityType.SOLID,
            PartyWallCavityType.FILLED_SEALED,
        ):
            return 0.0

        # Otherwise use the parent class behaviour
        return super().h_ce()

    def fabric_heat_loss(self) -> float:
        """Return the fabric heat loss for the building element

        For party walls with solid or filled_sealed cavity types, return zero
        as these represent adiabatic boundaries with no heat loss to account for
        in the building's heat loss calculation.

        For cavity party walls, the fabric heat loss calculation must include
        the effective thermal resistance of the cavity (R_cavity) in addition to
        the construction resistance.
        """
        # For solid and filled_sealed types, there is no heat loss
        if self._party_wall_cavity_type in (
            PartyWallCavityType.SOLID,
            PartyWallCavityType.FILLED_SEALED,
        ):
            return 0.0

        # For cavity party walls, calculate U-value including cavity resistance
        # The parent class h_ce() already incorporates the cavity resistance,
        # so we need to calculate the effective R_se from h_ce and h_re
        h_ce = self.h_ce()
        h_re = self.h_re()
        h_se_effective = h_ce + h_re

        r_se_effective = 1.0 / h_se_effective

        # Calculate U-value with effective external surface resistance
        if self._r_c is None:
            raise ValueError("_r_c is None")  # PRAGMA: nocover

        U_value = 1.0 / (self._r_c + r_se_effective + self.r_si())
        return self.area * U_value


class BuildingElementAdjacentConditionedSpace(
    BuildingElement,
    HeatTransferInternalCommon,
    HeatTransferThrough5Nodes,
    HeatTransferOtherSideConditionedSpace,
    SolarRadiationInteractionNotExposed,
):  # Common, 5 nodes, Conditioned space, Not exposed
    """A class to represent building elements adjacent to a thermally conditioned zone (ZTC)"""

    def __init__(
        self,
        area: float,
        pitch: float,
        thermal_resistance_construction: float,
        areal_heat_capacity: float,
        mass_distribution_class: MassDistributionClass,
        ext_cond: ExternalConditions,
    ) -> None:
        """Construct a BuildingElementAdjacentConditionedSpace object

        Arguments (names based on those in BS EN ISO 52016-1:2017):
        area     -- area (in m2) of this building element
        pitch -- tilt angle of the surface from horizontal, in degrees between 0 and 180,
                 where 0 means the external surface is facing up, 90 means the external
                 surface is vertical and 180 means the external surface is facing down
        thermal_resistance_construction      -- thermal resistance, in m2.K / W
        areal_heat_capacity      -- areal heat capacity, in J / (m2.K)
        ext_cond -- reference to ExternalConditions object
        mass_distribution_class
                 -- distribution of mass in building element, one of:
                    - 'I':  mass concentrated on internal side
                    - 'E':  mass concentrated on external side
                    - 'IE': mass divided over internal and external side
                    - 'D':  mass equally distributed
                    - 'M':  mass concentrated inside

        Other variables:
        f_sky -- view factor to the sky (see BS EN ISO 52016-1:2017, section 6.5.13.3)
        h_ce     -- external convective heat transfer coefficient, in W / (m2.K)
        h_re     -- external radiative heat transfer coefficient, in W / (m2.K)
        solar_absorption_coeff    -- solar absorption coefficient at the external surface (dimensionless)
        """

        # Initialise the base BuildingElement class
        super().__init__(ext_cond, area, pitch)
        HeatTransferThrough5Nodes.__init__(
            self,
            thermal_resistance_construction=thermal_resistance_construction,
            mass_distribution_class=mass_distribution_class,
            areal_heat_capacity=areal_heat_capacity,
        )
        HeatTransferOtherSideConditionedSpace.__init__(self)
        # Solar absorption coefficient at the external surface is zero
        SolarRadiationInteractionNotExposed.__init__(
            self,
            pitch=pitch,
            orientation=None,
            shading=None,
            base_height=0,
            projected_height=0,
            width=0,
            solar_absorption_coeff=0,
        )

    def fabric_heat_loss(self) -> float:
        """Return the fabric heat loss for the building element"""
        return 0.0  # no heat loss to thermally conditioned zones


class BuildingElementAdjacentUnconditionedSpace_Simple(
    BuildingElement,
    HeatTransferInternalCommon,
    HeatTransferThrough5Nodes,
    HeatTransferOtherSideUnconditionedSpace,
    SolarRadiationInteractionNotExposed,
):  # Common, 5 nodes, Unconditioned space, Not exposed
    """A class to represent building elements adjacent to a thermally unconditioned zone (ZTU)

    This class uses a simple calculation by adding an additional thermal
    resistance to the outside of the wall and incorporating this in the values
    for the external surface heat transfer coefficients. This differs from both
    of the approaches (internal and external) in BS EN ISO 52016-1:2017 which
    require detailed inputs for the unconditioned zone.
    """

    def __init__(
        self,
        area: float,
        pitch: float,
        thermal_resistance_construction: float,
        thermal_resistance_unconditioned_space: float,
        areal_heat_capacity: float,
        mass_distribution_class: MassDistributionClass,
        ext_cond: ExternalConditions,
    ) -> None:
        """Construct a BuildingElementAdjacentUnconditionedSpace_Simple object

        Arguments (names based on those in BS EN ISO 52016-1:2017):
        area     -- area (in m2) of this building element
        pitch -- tilt angle of the surface from horizontal, in degrees between 0 and 180,
                 where 0 means the external surface is facing up, 90 means the external
                 surface is vertical and 180 means the external surface is facing down
        thermal_resistance_construction      -- thermal resistance, in m2.K / W
        thermal_resistance_unconditioned_space      -- effective thermal resistance of unheated space, in m2.K / W;
                    see SAP 10.2 section 3.3 for suggested values
        areal_heat_capacity      -- areal heat capacity, in J / (m2.K)
        ext_cond -- reference to ExternalConditions object
        mass_distribution_class
                 -- distribution of mass in building element, one of:
                    - 'I':  mass concentrated on internal side
                    - 'E':  mass concentrated on external side
                    - 'IE': mass divided over internal and external side
                    - 'D':  mass equally distributed
                    - 'M':  mass concentrated inside

        Other variables:
        f_sky -- view factor to the sky (see BS EN ISO 52016-1:2017, section 6.5.13.3)
        h_ce     -- external convective heat transfer coefficient, in W / (m2.K)
        h_re     -- external radiative heat transfer coefficient, in W / (m2.K)
        solar_absorption_coeff    -- solar absorption coefficient at the external surface (dimensionless)
        """

        # Initialise the base BuildingElement class
        super().__init__(ext_cond, area, pitch)
        HeatTransferThrough5Nodes.__init__(
            self,
            thermal_resistance_construction=thermal_resistance_construction,
            mass_distribution_class=mass_distribution_class,
            areal_heat_capacity=areal_heat_capacity,
        )
        HeatTransferOtherSideUnconditionedSpace.__init__(
            self, thermal_resistance_unconditioned_space=thermal_resistance_unconditioned_space
        )
        # Solar absorption coefficient at the external surface is zero
        SolarRadiationInteractionNotExposed.__init__(
            self,
            pitch=pitch,
            orientation=None,
            shading=None,
            base_height=0,
            projected_height=0,
            width=0,
            solar_absorption_coeff=0,
        )


class BuildingElementGround(
    BuildingElement,
    HeatTransferInternalCommon,
    HeatTransferThrough3Plus2Nodes,
    HeatTransferOtherSideGround,
    SolarRadiationInteractionNotExposed,
):  # Common, 3+2 nodes, Ground, Not exposed
    """A class to represent ground building elements"""

    def __init__(
        self,
        total_area: float,
        area: float,
        pitch: float,
        u_value: float,
        thermal_resistance_floor_construction: float,
        areal_heat_capacity: float,
        mass_distribution_class: MassDistributionClass,
        floor_type: FloorType,
        edge_insulation,
        h_upper: float,
        u_f_s: float | None,
        u_w: float,
        area_per_perimeter_vent: float,
        shield_fact_location: WindShieldLocation | None,
        d_we: float,
        r_f_ins: float,
        z_b: float | None,
        r_w_b: float | None,
        h_w: float | None,
        perimeter: float,
        psi_wall_floor_junc: float,
        ext_cond: ExternalConditions,
        simulation_time: SimulationTime,
    ) -> None:
        """Construct a BuildingElementGround object

        Arguments (names based on those in BS EN ISO 52016-1:2017):
        total_area -- total area (in m2) of the building element across entire dwelling.
                      If the Floor is devided among several zones,
                      this is the total area across all zones.
        area -- area (in m2) of this building element within the zone.
        pitch -- tilt angle of the surface from horizontal, in degrees between 0 and 180,
                 where 0 means the external surface is facing up, 90 means the external
                 surface is vertical and 180 means the external surface is facing down
        u_value -- steady-state thermal transmittance of floor, including the
                   effect of the ground, in W / (m2.K)
                   Calculated for the entire ground floor,
                   even if it is distributed among several zones.
        thermal_resistance_floor_construction -- total thermal resistance of all layers in the floor construction, in (m2.K) / W
        areal_heat_capacity -- areal heat capacity of the ground floor element, in J / (m2.K)
        perimeter -- perimeter of the floor, in metres. Calculated for the entire ground floor,
                     even if it is distributed among several zones.
        psi_wall_floor_junc -- linear thermal transmittance of the junction
                               between the floor and the walls, in W / (m.K)
        ext_cond -- reference to ExternalConditions object
        simulation_time -- reference to SimulationTime object
        mass_distribution_class
                 -- distribution of mass in building element, one of:
                    - 'I':  mass concentrated on internal side
                    - 'E':  mass concentrated on external side
                    - 'IE': mass divided over internal and external side
                    - 'D':  mass equally distributed
                    - 'M':  mass concentrated inside
        floor_type
                - Slab_no_edge_insulation
                - Slab_edge_insulation
                - Suspended_floor
                - Heated_basement
                - Unheated_basement
        edge_insulation
                - horizontal edge insulation
                - vertical or external edge insulation
        h_upper - height of the floor upper surface, in m
                - average value is used if h varies
        u_w - thermal transmittance of walls above ground, in W/(m2·K)
            - in accordance with ISO 6946
        u_f_s - thermal transmittance of floor above basement), in W/(m2·K)
              - in accordance with ISO 6946
        area_per_perimeter_vent - area of ventilation openings per perimeter, in m2/m
        shield_fact_location - wind shielding factor
                - Sheltered
                - Average
                - Exposed
        d_we - thickness of the walls, in m
        r_f_ins - thermal resistance of insulation on base of underfloor space, in m2·K/W
        z_b - depth of basement floor below ground level, in m
        r_w_b - thermal resistance of walls of the basement, in m2·K/W
        h_w - height of the basement walls above ground level, in m

        Other variables:
        f_sky -- view factor to the sky (see BS EN ISO 52016-1:2017, section 6.5.6.3.6)
        h_ce  -- external convective heat transfer coefficient, in W / (m2.K)
        h_re  -- external radiative heat transfer coefficient, in W / (m2.K)
        thermal_resistance_construction -- thermal resistance of the ground floor element including the
                    effect of the ground, in m2.K / W
        r_gr     -- thermal resistance of the fixed ground layer, in m2.K / W
        k_gr     -- areal heat capacity of the fixed ground layer, in J / (m2.K)
        """
        self.__u_value = u_value
        self._simulation_time = simulation_time

        # Thermal properties of ground from BS EN ISO 13370:2017 Table 7
        # Use values for clay or silt (same as BR 443 and SAP 10)
        thermal_conductivity = 1.5  # in W/(m.K)
        heat_capacity_per_vol = 3000000  # in J/(m3.K)

        # Periodic penetration depth of ground from BS EN ISO 13370:2017 Table H.1
        # Use values for clay or silt (same as BR 443 and SAP 10)
        periodic_penetration_depth = 2.2  # in m

        # Calculate thermal resistance and heat capacity of fixed ground layer
        # using BS EN ISO 13370:2017
        thickness_ground_layer = 0.5  # in m. Specified in BS EN ISO 52016-1:2017 section 6.5.8.2

        # thermal resistance in (m2.K)/W
        r_gr = thickness_ground_layer / thermal_conductivity
        # areal heat capacity in J/(m2.K)
        k_gr = thickness_ground_layer * heat_capacity_per_vol

        # Calculate thermal resistance of virtual layer using BS EN ISO 13370:2017 Equation (F1)
        r_si = 0.17  # ISO 6946 - internal surface resistance
        r_vi = units.calculate_thermal_resistance_of_virtual_layer(
            u_value=u_value,
            thermal_resistance_floor_construction=thermal_resistance_floor_construction,
        )

        # Initialise the base BuildingElement class
        super().__init__(ext_cond, area, pitch)
        HeatTransferThrough3Plus2Nodes.__init__(
            self,
            thermal_resistance_floor_construction=thermal_resistance_floor_construction,
            r_gr=r_gr,
            mass_distribution_class=mass_distribution_class,
            k_gr=k_gr,
            areal_heat_capacity=areal_heat_capacity,
        )
        HeatTransferOtherSideGround.__init__(
            self,
            r_vi=r_vi,
            d_we=d_we,
            thermal_conductivity=thermal_conductivity,
            r_si=r_si,
            thermal_resistance_floor_construction=thermal_resistance_floor_construction,
            floor_type=floor_type,
            periodic_penetration_depth=periodic_penetration_depth,
            total_area=total_area,
            perimeter=perimeter,
            u_value=u_value,
            psi_wall_floor_junc=psi_wall_floor_junc,
            h_upper=h_upper,
            z_b=z_b,
            h_w=h_w,
            u_w=u_w,
            u_f_s=u_f_s,
            area_per_perimeter_vent=area_per_perimeter_vent,
            r_f_ins=r_f_ins,
            shield_fact_location=shield_fact_location,
            edge_insulation=edge_insulation,
            r_w_b=r_w_b,
        )
        SolarRadiationInteractionNotExposed.__init__(
            self,
            pitch=pitch,
            orientation=None,
            shading=None,
            base_height=0,
            projected_height=0,
            width=0,
            solar_absorption_coeff=0,
        )

    def fabric_heat_loss(self) -> float:
        """Return the fabric heat loss for the building element"""
        fabric_heat_loss = self.area * self.__u_value
        return fabric_heat_loss


class BuildingElementTransparent(
    BuildingElement,
    HeatTransferInternalCommon,
    HeatTransferThrough2Nodes,
    HeatTransferOtherSideOutside,
    SolarRadiationInteractionTransmitted,
):  # Common, 2 nodes, Outside, Transmitted
    """A class to represent transparent building elements (windows etc.)"""

    def __init__(
        self,
        pitch: float,
        thermal_resistance_construction: float,
        orientation: units.Orientation360 | None,
        g_value: float,
        frame_area_fraction: float,
        base_height: float,
        height: float,
        width: float,
        shading: list[dict[str, Any]],
        treatment: list[dict[str, Any]],
        ext_cond: ExternalConditions,
        simtime: SimulationTime,
    ) -> None:
        """Construct a BuildingElementTransparent object

        Arguments (names based on those in BS EN ISO 52016-1:2017):
        pitch -- tilt angle of the surface from horizontal, in degrees between 0 and 180,
                 where 0 means the external surface is facing up, 90 means the external
                 surface is vertical and 180 means the external surface is facing down
        thermal_resistance_construction -- thermal resistance, in m2.K / W
        orientation -- is the orientation angle of the inclined surface, expressed
                       as the geographical azimuth angle of the horizontal projection
                       of the inclined surface normal, -180 to 180, in degrees
        base_height -- is the distance between the ground and the lowest edge of the element, in m
        height      -- is the height of the building element, in m
        width       -- is the width of the building element, in m
        g_value -- total solar energy transmittance of the transparent part of the window
        frame_area_fraction -- is the frame area fraction of window wi, ratio of the
                               projected frame area to the overall projected area of
                               the glazed element of the window
        treatment -- is additional window elements such as curtain or blinds
        ext_cond -- reference to ExternalConditions object

        Other variables:
        f_sky -- view factor to the sky (see BS EN ISO 52016-1:2017, section 6.5.13.3)
        """
        self.__mid_height = base_height + height / 2.0
        self._g_value = g_value
        # TODO ISO 52016 offers an input option; either the frame factor directly,
        # or the glazed area of the window and then the frame factor is calculated.
        # assuming for now that frame factor is provided (default 0.25 from App B)
        # need to implement ISO 52016 E.2.1 here if other option given.
        self._frame_area_fraction = frame_area_fraction

        # calculate area from height & width for transparent elements
        area = calculate_area(height=height, width=width)

        # Initialise the base BuildingElement class
        super().__init__(ext_cond=ext_cond, area=area, pitch=pitch)

        if treatment is not None:
            for t in treatment:
                t["time_last_adjusted"] = simtime.current_hour()
                t["type"] = WindowTreatmentType(t["type"])
                t["controls"] = WindowTreatmentControl(t["controls"])
        self._treatment = treatment

        HeatTransferThrough2Nodes.__init__(
            self, thermal_resistance_construction=thermal_resistance_construction
        )
        HeatTransferOtherSideOutside.__init__(self, pitch=pitch)
        SolarRadiationInteractionTransmitted.__init__(
            self,
            simtime=simtime,
            pitch=pitch,
            orientation=orientation,
            shading=shading,
            base_height=base_height,
            projected_height=projected_height(pitch, height),
            width=width,
            solar_absorption_coeff=0,
        )

    def _adjust_treatment(self) -> None:
        def open_treatment(t: dict[str, Any]) -> None:
            if t["is_open"] is False:
                t["is_open"] = True
                t["time_last_adjusted"] = time_current

        def close_treatment(t: dict[str, Any]) -> None:
            if t["is_open"] is True:
                t["is_open"] = False
                t["time_last_adjusted"] = time_current

        # Operation and control logic for window treatments (windows, blinds, etc.)
        # as per Annex G and Tables B.23 and B.24 in BS EN ISO 52016-1:2017.
        # 'Manual' modes for curtains/shutters also requires occupancy driver, however
        # only time and solar based controls for now.
        # 'trans_red' specific to selected treatment as per BS EN 13125:2001.
        if self._treatment is not None:
            if self._orientation is None:
                raise ValueError("Cannot compute surface irradiance because orientation is None.")
            if self._shading is None:
                raise ValueError(
                    "Cannot compute surface irradiance because window shading is None."
                )

            surf_irrad = self._external_conditions.surface_irradiance(
                base_height=self._base_height,
                projected_height=self._projected_height,
                width=self._width,
                tilt=self._pitch,
                orientation=self._orientation,
                window_shading=self._shading,
            )
            time_current = self._simtime.current()
            for treatment in self._treatment:
                if treatment["Control_open"] is not None:
                    ctrl_open = treatment["Control_open"].is_on()
                else:
                    ctrl_open = None
                if treatment["Control_closing_irrad"] is not None:
                    closing_irrad_threshold = treatment["Control_closing_irrad"].setpnt()
                else:
                    closing_irrad_threshold = None
                if treatment["Control_opening_irrad"] is not None:
                    opening_irrad_threshold = treatment["Control_opening_irrad"].setpnt()
                else:
                    opening_irrad_threshold = None

                if ctrl_open is True:
                    open_treatment(t=treatment)
                elif ctrl_open is False:
                    close_treatment(t=treatment)
                elif ctrl_open is None:
                    controls = WindowTreatmentControl(treatment["controls"])
                    if closing_irrad_threshold is not None and surf_irrad > closing_irrad_threshold:
                        close_treatment(t=treatment)
                    elif (
                        opening_irrad_threshold is not None
                        and surf_irrad < opening_irrad_threshold
                        and (
                            controls.is_manual
                            or (
                                controls.is_automatic
                                and time_current - treatment["time_last_adjusted"]
                                >= treatment["opening_delay_hrs"]
                            )
                        )
                    ):
                        open_treatment(t=treatment)
                else:
                    raise ValueError("Invalid value for ctrl_open")

    def solar_gains(self) -> float:
        solar_gains = super().solar_gains()
        if self._treatment is not None:
            self._adjust_treatment()
            for treatment in self._treatment:
                if not treatment["is_open"]:
                    solar_gains -= solar_gains * treatment["trans_red"]
        return solar_gains

    def fabric_heat_loss(self) -> float:
        """Return the fabric heat loss for the building element"""
        # Effective window U-value includes assumed use of curtains/blinds, see
        # SAP10.2 spec, paragraph 3.2
        # TODO Confirm this is still the desired approach for SAP 11
        r_curtains_blinds = 0.04
        # Add standard surface resistances to resistance of construction when calculating U-value
        if self._r_c is None:
            raise ValueError("_r_c is None")  # PRAGMA: nocover
        U_value = 1.0 / ((self._r_c + self.r_se() + self.r_si()) + r_curtains_blinds)
        return self.area * U_value

    def h_pli(self, idx: int) -> float:
        # Account for resistance of window treatment in heat transfer coefficient
        # TODO Check that idx refers to inside surface?
        thermal_resistance_construction = 1.0 / self._h_pli[idx]
        if self._treatment is not None:
            for t in self._treatment:
                self._adjust_treatment()
                if not t["is_open"]:
                    # delta_r for window treatment (curtains, blinds, etc.) as per
                    # BS EN 13125:2001
                    thermal_resistance_construction += t["delta_r"]
        return 1.0 / thermal_resistance_construction

    def projected_height(self) -> float:
        return self._projected_height

    def mid_height(self) -> float:
        return self.__mid_height

    def orientation(self) -> units.Orientation360 | None:
        return self._orientation
