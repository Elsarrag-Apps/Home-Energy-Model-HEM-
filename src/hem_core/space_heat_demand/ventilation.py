#!/usr/bin/env python3

"""
This module provides objects to represent Infiltration and Ventilation.
The calculations are based on Method 1 of BS EN 16798-7.
"""

import math
import warnings
from math import fsum
from typing import Any, NotRequired, TypedDict, cast

import numpy as np
from scipy.optimize import minimize_scalar, root_scalar

from hem_core.controls.time_control import OnOffTimeControl, SetpointTimeControl
from hem_core.ductwork import Ductwork
from hem_core.energy_supply.energy_supply import EnergySupply, EnergySupplyConnection
from hem_core.input_output.enums import (
    CombustionAirSupplySituation,
    CombustionApplianceType,
    CombustionFuelType,
    DuctShape,
    DuctType,
    FlueGasExhaustSituation,
    MechVentType,
    MVHRLocation,
    SupplyAirFlowRateControlType,
    SupplyAirTemperatureControlType,
    TerrainClass,
    VentilationShieldClass,
)
from hem_core.material_properties import AIR
from hem_core.simulation_time import SimulationTime
from hem_core.space_heat_demand.building_element import BuildingElement, HeatFlowDirection

# Local imports
from hem_core.units import (
    Celcius2Kelvin,
    Orientation360,
    W_per_kW,
    litres_per_cubic_metre,
    mm_per_m,
    seconds_per_hour,
)

# Define constants
p_a_ref = AIR.density_kg_per_m3()
c_a = AIR.specific_heat_capacity_kWh()

# (Default values from BS EN 16798-7, Table 11)
# Coefficient to take into account stack effect in airing calculation in (m/s)/(m*K)
C_stack = 0.0035
# Coefficient to take into account wind speed in airing calculation in 1/(m/s)
C_wnd = 0.001
# Gravitational constant in m/s2
g = 9.81
# Room temperature in degrees K
T_e_ref = 293.15
# Absolute zero in degrees K
T_0_abs = 273.15

# Flow change coefficients for different mechanical ventilation types
# From "Sensitivity of fans to back pressure – generic values for HEM - Technical Note"
FLOW_CHANGE_COEFFICIENTS = {
    MechVentType.MVHR: 0.5,
    MechVentType.CENTRALISED_CONTINUOUS_MEV: 0.5,
    MechVentType.DECENTRALISED_CONTINUOUS_MEV: 0.1,
    MechVentType.INTERMITTENT_MEV: 0.5,
    MechVentType.POSITIVE_INPUT_VENTILATION: 0.1,
}


class PressureCoefficient(TypedDict):
    wind_seg1: float
    wind_seg2: float
    wind_seg3: float
    wind_seg4: float
    wind_seg5: float
    Roof: NotRequired[float]
    Roof10: NotRequired[float]
    Roof10_30: NotRequired[float]
    Roof30: NotRequired[float]


def calculate_pressure_difference_at_an_airflow_path(
    h_path: float, C_p_path: float, u_site: float, T_e: float, T_z: float, p_z_ref: float
) -> float:
    """Calculate pressure difference between the exterior and the interior of the dwelling
    for a flow path (at it's elevavation above the vent zone floor)

    Arguments:
    h_path -- height of air flow path (m)
    C_p_path -- wind pressure coefficient
    u_site -- wind velocity at zone level (m/s)
    T_e -- external air temperature (K)
    T_z -- thermal zone air temperature (K)
    p_z_ref -- internal reference pressure (Pa)
    """
    p_e_path = p_a_ref * T_e_ref / T_e * (0.5 * C_p_path * u_site**2 - h_path * g)  # (5)
    p_z_path = p_z_ref - p_a_ref * h_path * g * T_e_ref / T_z  # (6)

    # TODO: Investigate why, due to differences in internal temperature, these values are different in
    # Windows implementation when compared to Linux
    if math.isclose(p_e_path, p_z_path, abs_tol=1e-12):
        delta_p_path = 0.0  # pragma: no cover
    else:
        delta_p_path = p_e_path - p_z_path  # (4)

    return delta_p_path


def air_change_rate_to_flow_rate(air_change_rate: float, zone_volume: float) -> float:
    """Convert infiltration rate from ach to m^3/s"""
    return air_change_rate * zone_volume / seconds_per_hour


def get_fuel_flow_factor(
    fuel_type: CombustionFuelType, appliance_type: CombustionApplianceType
) -> float:
    """Table B.3 fuel flow factors

    Arguments:
    fuel_type -- options are 'wood', 'gas', 'oil' or 'coal'.
    appliance_type -- options are 'open_fireplace', 'closed_with_fan',
        open_gas_flue_balancer', 'open_gas_kitchen_stove', 'open_gas_fire' or 'closed_fire'
    """
    if fuel_type == CombustionFuelType.WOOD:
        if appliance_type == CombustionApplianceType.OPEN_FIREPLACE:
            f_ff = 2.8
        else:
            raise ValueError(
                "appliance_type: "
                + str(appliance_type)
                + " not applicable for the fuel_type: "
                + str(fuel_type)
                + " selected."
            )
    elif fuel_type == CombustionFuelType.GAS:
        if appliance_type == CombustionApplianceType.CLOSED_WITH_FAN:
            f_ff = 0.38
        elif appliance_type == CombustionApplianceType.OPEN_GAS_FLUE_BALANCER:
            f_ff = 0.78
        elif appliance_type == CombustionApplianceType.OPEN_GAS_KITCHEN_STOVE:
            f_ff = 3.35
        elif appliance_type == CombustionApplianceType.OPEN_GAS_FIRE:
            f_ff = 3.35
        else:
            raise ValueError(
                "appliance_type: "
                + str(appliance_type)
                + " not applicable for the fuel_type: "
                + str(fuel_type)
                + " selected."
            )
    elif fuel_type == CombustionFuelType.OIL:
        if appliance_type == CombustionApplianceType.CLOSED_FIRE:
            f_ff = 0.32
        else:
            raise ValueError(
                "appliance_type: "
                + str(appliance_type)
                + " not applicable for the fuel_type: "
                + str(fuel_type)
                + " selected."
            )
    elif fuel_type == CombustionFuelType.COAL:
        if appliance_type == CombustionApplianceType.CLOSED_FIRE:
            f_ff = 0.52
        else:
            raise ValueError(
                "appliance_type: "
                + str(appliance_type)
                + " not applicable for the fuel_type: "
                + str(fuel_type)
                + " selected."
            )
    else:
        raise ValueError(" fuel_type: " + str(fuel_type) + " not found.")  # pragma: no cover
    return f_ff


def get_appliance_system_factor(
    supply_situation: CombustionAirSupplySituation, exhaust_situation: FlueGasExhaustSituation
) -> int:
    """Interpreted from Table B.2 from BS EN 16798-7, get the appliance system factor
    for a combustion appliance.

    Arguments:
    supply_situation -- Combustion air supply situation: 'room_air' or 'outside'
    exhaust_situation -- flue gas exhaust situation: 'into_room', 'into_separate_duct' or 'into_mech_vent'
    """
    if supply_situation == CombustionAirSupplySituation.OUTSIDE:
        f_as = 0
    elif supply_situation == CombustionAirSupplySituation.ROOM_AIR:
        if exhaust_situation == FlueGasExhaustSituation.INTO_ROOM:
            f_as = 0
        elif exhaust_situation == FlueGasExhaustSituation.INTO_SEPARATE_DUCT:
            f_as = 1
        elif exhaust_situation == FlueGasExhaustSituation.INTO_MECH_VENT:
            raise ValueError(
                "Cannot currently handle 'exhaust_situation': "
                + str(exhaust_situation)
                + " for combustion appliance."
            )
        else:
            raise ValueError(  # pragma: no cover
                "'exhaust_situation': "
                + str(exhaust_situation)
                + " not recognised for combustion appliance"
            )
    else:
        raise ValueError(  # pragma: no cover
            "'supply_situation': "
            + str(supply_situation)
            + " not recognised for combustion appliance"
        )
    return f_as


def adjust_air_density_for_altitude(altitude: float) -> float:
    """Adjust air density for altitude above sea level.

    Arguments:
    altitude -- altitude above sea level (m)
    """
    p_a_alt = p_a_ref * (1 - ((0.00651 * altitude) / 293)) ** 4.255
    return p_a_alt


def air_density_at_temp(temperature: float, air_density_adjusted_for_alt: float) -> float:
    """Recalculate air density based on the current temperature

    Arguments:
    temperature -- temperature to adjust (K)
    air_density_adjusted_for_alt - The air density after adjusting for altitude (Kg/m3)
    """
    return T_e_ref / temperature * air_density_adjusted_for_alt


def convert_to_mass_air_flow_rate(
    qv_in: float, qv_out: float, T_e: float, T_z: float, p_a_alt: float
) -> tuple[float, float]:
    """Converts volume air flow rate (qv) to mass air flow rate (qm).
    (Equations 65 & 66 from BS EN 16798-7)

    Arguments:
    qv_in -- volume flow rate of air entering the dwelling
    qv_out -- volume flow rate of air leaving the dwelling
    T_e -- External air temperature (K)
    T_e -- Thermal zone air temperature (K)
    p_a_alt -- The air density after adjusting for altitude (Kg/m3)
    """
    qm_in = convert_volume_flow_rate_to_mass_flow_rate(qv=qv_in, temperature=T_e, p_a_alt=p_a_alt)
    qm_out = convert_volume_flow_rate_to_mass_flow_rate(qv=qv_out, temperature=T_z, p_a_alt=p_a_alt)
    return qm_in, qm_out


def convert_volume_flow_rate_to_mass_flow_rate(
    qv: float, temperature: float, p_a_alt: float
) -> float:
    """Convert volume flow rate in m3/hr to mass flow rate in kg/hr, at temperature in Kelvin

    Arguments:
    qv -- volume flow rate (m3/h)
    temperature -- air temperature (K)
    p_a_alt -- The air density after adjusting for altitude (Kg/m3)
    """
    return qv * air_density_at_temp(temperature=temperature, air_density_adjusted_for_alt=p_a_alt)


def convert_mass_flow_rate_to_volume_flow_rate(
    qm: float | int | np.float64, temperature: float, p_a_alt: float
) -> float | np.float64:
    """Convert mass flow rate in kg/hr to volume flow rate in m3/hr, at temperature in Kelvin

    Arguments:
    qm -- mass flow rate (Kg/h)
    temperature -- air temperature (K)
    p_a_alt -- The air density after adjusting for altitude (Kg/m3)
    """
    return qm / air_density_at_temp(temperature=temperature, air_density_adjusted_for_alt=p_a_alt)


def terrain_class_to_roughness_coeff(terrain_class: TerrainClass, z: float) -> float:
    """
    Retrieves the roughness parameters and calculates the roughness coefficient (CR)
    based on the terrain type and height of airflow path.

    Args:
        terrain_class (str): The terrain type ('OpenWater', 'OpenField', 'Suburban', 'Urban').
        z (float): Height of airflow path relative to the ground (m).

    Returns:
        float: Calculated roughness coefficient CR.

    Raises:
        ValueError: If an invalid terrain type is provided.
    """
    # Mapping of terrain types to their roughness parameters (KR, z0, zmin)
    terrain_data = {
        TerrainClass.OPEN_WATER: (0.17, 0.01, 2),  # Rough open sea, lake shore
        TerrainClass.OPEN_FIELD: (0.19, 0.05, 4),  # Farm land, small structures
        TerrainClass.SUBURBAN: (0.22, 0.3, 8),  # Suburban or industrial areas
        TerrainClass.URBAN: (0.24, 1.0, 16),  # Urban areas with tall buildings
    }

    if terrain_class not in terrain_data:
        raise ValueError(f"Unknown terrain type: {terrain_class}")  # pragma: no cover

    # Retrieve the terrain parameters
    KR, z0, zmin = terrain_data[terrain_class]

    # Ensure z is at least zmin
    z = max(z, zmin)

    # Calculate the roughness coefficient
    CR = KR * np.log(z / z0)

    return CR


def wind_speed_at_zone_level(
    C_rgh_site: float,
    u_10: float,
    C_top_site: float = 1,
    C_rgh_met: float = 1,
    C_top_met: float = 1,
) -> float:
    """Meteorological wind speed at 10 m corrected to reference wind speed at zone level of the dwelling

    Arguments:
    C_rgh_site -- roughness coefficient at building site
    u_10 -- wind velocity at 10m (m/s)
    C_top_site -- topography coefficient at building site
    C_rgh_met -- roughness coefficient at 10m depending on meteorological station
    C_top_met -- topography coefficient at building height depending on meteorological station
    """
    u_site = ((C_rgh_site * C_top_site) / (C_rgh_met * C_top_met)) * u_10
    return u_site


# Not needed as using internal pressure for windows, not cross ventilation
# def wind_speed_at_10m_height(C_rgh_10_site, u_10, C_top_10_site=1, C_rgh_met=1, C_top_met=1):
#     """The meteorological wind speed at 10 m is corrected as follows to obtain the reference wind speed at
#     site at 10m height:
#     """
#     u_10_site = ((C_rgh_10_site * C_top_10_site) / (C_rgh_met * C_top_met)) * u_10
#     return u_10_site


def get_facade_direction(
    f_cross: bool, orientation: Orientation360, pitch: float, wind_direction: Orientation360
) -> str:
    """Gets direction of the facade from pitch and orientation

    Arguments:
    f_cross -- boolean, dependant on if cross ventilation is possible or not
    orientation -- orientation of the facade (degrees)
    pitch -- pitch of the facade (degrees)
    wind_direction -- direction the wind is blowing (degrees)
    """

    # There are now eight wind angle segments but the pressure coefficients
    # associated to these segments are symmetric around 180 degrees so we can
    # continue to use the same orientation_difference method with five
    # segments as follows:
    #
    # wind_seg1 0 - 22.5 degrees
    # wind_seg2 22.5 - 67.5 degrees
    # wind_seg3 67.5 - 112.5 degrees
    # wind_seg4 112.5 - 157.5 degrees
    # wind_seg5 157.5 - 180 degrees

    # these replace Windward and Leeward from EN 16798-7

    if f_cross:
        if pitch < 10:
            facade_direction = "Roof10"
        elif pitch <= 30:
            facade_direction = "Roof10_30"
        elif pitch < 60:
            facade_direction = "Roof30"
        else:
            orientation_diff = Orientation360.orientation_difference(orientation, wind_direction)
            if orientation_diff <= 22.5:
                facade_direction = "wind_seg1"
            elif orientation_diff <= 67.5:
                facade_direction = "wind_seg2"
            elif orientation_diff <= 112.5:
                facade_direction = "wind_seg3"
            elif orientation_diff <= 157.5:
                facade_direction = "wind_seg4"
            else:
                facade_direction = "wind_seg5"
    else:
        if pitch < 60:
            facade_direction = "Roof"
        else:
            orientation_diff = Orientation360.orientation_difference(
                orientation1=orientation, orientation2=wind_direction
            )
            if orientation_diff <= 22.5:
                facade_direction = "wind_seg1"
            elif orientation_diff <= 67.5:
                facade_direction = "wind_seg2"
            elif orientation_diff <= 112.5:
                facade_direction = "wind_seg3"
            elif orientation_diff <= 157.5:
                facade_direction = "wind_seg4"
            else:
                facade_direction = "wind_seg5"
    return facade_direction


def get_pressure_coefficient_dict(
    z: float, shield_class: VentilationShieldClass
) -> PressureCoefficient:
    if z < 15:
        if shield_class == VentilationShieldClass.OPEN:
            return {
                "wind_seg1": 0.7,
                "wind_seg2": 0.35,
                "wind_seg3": -0.5,
                "wind_seg4": -0.4,
                "wind_seg5": -0.2,
                "Roof10": -0.60,
                "Roof10_30": -0.50,
                "Roof30": -0.38,
            }
        elif shield_class == VentilationShieldClass.NORMAL:
            return {
                "wind_seg1": 0.4,
                "wind_seg2": 0.1,
                "wind_seg3": -0.3,
                "wind_seg4": -0.35,
                "wind_seg5": -0.2,
                "Roof10": -0.50,
                "Roof10_30": -0.45,
                "Roof30": -0.43,
            }
        elif shield_class == VentilationShieldClass.SHIELDED:
            return {
                "wind_seg1": 0.2,
                "wind_seg2": 0.05,
                "wind_seg3": -0.25,
                "wind_seg4": -0.3,
                "wind_seg5": -0.25,
                "Roof10": -0.48,
                "Roof10_30": -0.40,
                "Roof30": -0.30,
            }
    # Above 15m we currently only have a single set of coefficients.
    # We preserve the split by exposure type here, for future update to values.
    # Coefficient data currently has only a single value for (flat) roofs
    # and so that is applied here to all roof pitches for now.
    elif 15 <= z < 50:
        if shield_class == VentilationShieldClass.OPEN:
            return {
                "wind_seg1": 0.49,
                "wind_seg2": 0.24,
                "wind_seg3": -0.61,
                "wind_seg4": -0.47,
                "wind_seg5": -0.34,
                "Roof10": -0.61,
                "Roof10_30": -0.61,
                "Roof30": -0.61,
            }
        elif shield_class == VentilationShieldClass.NORMAL:
            return {
                "wind_seg1": 0.49,
                "wind_seg2": 0.24,
                "wind_seg3": -0.61,
                "wind_seg4": -0.47,
                "wind_seg5": -0.34,
                "Roof10": -0.61,
                "Roof10_30": -0.61,
                "Roof30": -0.61,
            }
        elif shield_class == VentilationShieldClass.SHIELDED:
            return {
                "wind_seg1": 0.49,
                "wind_seg2": 0.24,
                "wind_seg3": -0.61,
                "wind_seg4": -0.47,
                "wind_seg5": -0.34,
                "Roof10": -0.61,
                "Roof10_30": -0.61,
                "Roof30": -0.61,
            }
    elif z >= 50:
        if shield_class == VentilationShieldClass.OPEN:
            return {
                "wind_seg1": 0.49,
                "wind_seg2": 0.24,
                "wind_seg3": -0.61,
                "wind_seg4": -0.47,
                "wind_seg5": -0.34,
                "Roof10": -0.61,
                "Roof10_30": -0.61,
                "Roof30": -0.61,
            }
    raise ValueError(f"No pressure coefficient found for z ({z}) and shield_class {shield_class}")


def get_pressure_coefficient(
    f_cross: bool,
    shield_class: VentilationShieldClass,
    z: float,
    wind_direction: Orientation360,
    orientation: Orientation360 | None = None,
    pitch: float | None = None,
    facade_direction: str | None = None,
) -> float:
    """wind pressure coefficients are based on AIVC Technical Note 44

    Arguments:
    f_cross -- boolean, dependant on if cross ventilation is possible or not
    shield_class -- indicates exposure to wind
    z -- height of air flow path relative to ground (m)
    wind_direction -- direction the wind is blowing (degrees)
    orientation -- orientation of the facade (degrees)
    pitch -- pitch of the facade (degrees)
    facade_direction -- direction of the facade (from get_facade_direction or manual entry)
    """
    if facade_direction is None:
        if orientation is None or pitch is None:
            raise ValueError(
                "You have not entered a pitch or orientation for an opaque building element."
            )
        else:
            facade_direction = get_facade_direction(
                f_cross=f_cross, orientation=orientation, pitch=pitch, wind_direction=wind_direction
            )

    if f_cross:
        pressure_coefficient = get_pressure_coefficient_dict(z=z, shield_class=shield_class)
    else:
        pressure_coefficient = {
            "wind_seg1": 0.05,
            "wind_seg2": 0.05,
            "wind_seg3": -0.05,
            "wind_seg4": -0.05,
            "wind_seg5": -0.05,
            "Roof": 0,
        }
    return pressure_coefficient[facade_direction]


class Window:
    """An object to represent Windows"""

    def __init__(
        self,
        free_area_height: float,
        midheight: float,
        max_opening_area: float,
        window_part_list: list[dict[str, float]],
        orientation: Orientation360,
        pitch: float,
        altitude: float,
        on_off_ctrl_obj: OnOffTimeControl | None,
        ventilation_zone_base_height: float,
    ):
        """Construct a Window object

        Arguments:
            free_area_height -- The free area height of the window
            midheight -- The midheight of the window.
            max_opening_area -- The maximum window opening area.
            window_part_list -- The list of window parts.
            orientation -- The orientation of the window.
            pitch -- The pitch of the window.
            altitude -- altitude of dwelling above sea level (m)
            on_off_ctrl_obj -

        Method
            - Based on Section 6.4.3.5 Airflow due to windows opening section.
        """
        self.__h_w_fa = free_area_height
        self.__h_w_path = midheight
        self.__A_w_max = max_opening_area
        self.__C_D_w = (
            0.67  # Discharge coefficient for windows based on Section B.3.2.1 of BS EN 16798-7:2017
        )
        self.__n_w = 0.5  # Flow exponent of window based on Section B.3.2.2 of BS EN 16798-7:2017
        self.__orientation = orientation
        self.__pitch = pitch
        self.__N_w_div = max(len(window_part_list) - 1, 0)
        self.__on_off_ctrl_obj = on_off_ctrl_obj
        self.__altitude = altitude
        self.__p_a_alt = adjust_air_density_for_altitude(altitude=altitude)
        self.__z = self.__h_w_path + ventilation_zone_base_height

        self.__window_parts = []
        for window_part_number, window_part in enumerate(window_part_list):
            self.__window_parts.append(
                WindowPart(
                    midheight=window_part["mid_height_air_flow_path"],  # h_w_path
                    free_area_height=self.__h_w_fa,
                    number_window_divisions=self.__N_w_div,
                    window_part_number=window_part_number + 1,
                    ventilation_zone_base_height=ventilation_zone_base_height,
                )
            )

    def calculate_window_opening_free_area(self, R_w_arg: float) -> float:
        """The window opening free area A_w for a window
        Equation 40 in BS EN 16798-7.
        Arguments:
        R_w_arg -- ratio of window opening (0-1)
        """
        # Assume windows are shut if the control object is empty
        if self.__on_off_ctrl_obj is None:
            R_w_arg = 0
        if self.__on_off_ctrl_obj is not None and not self.__on_off_ctrl_obj.is_on():
            R_w_arg = 0
        return R_w_arg * self.__A_w_max  # self.__A_w

    def calculate_flow_coeff_for_window(self, R_w_arg: float) -> float:
        """The C_w_path flow coefficient for a window
        Equation 54 from BS EN 16798-7
        Arguments:
        R_w_arg -- ratio of window opening (0-1)
        """
        # Assume windows are shut if the control object is empty
        if self.__on_off_ctrl_obj is None:
            R_w_arg = 0
        if self.__on_off_ctrl_obj is not None and not self.__on_off_ctrl_obj.is_on():
            R_w_arg = 0
        A_w = self.calculate_window_opening_free_area(R_w_arg=R_w_arg)
        return 3600 * self.__C_D_w * A_w * (2 / p_a_ref) ** self.__n_w

    def calculate_flow_from_internal_p(
        self,
        wind_direction: Orientation360,
        u_site: float,
        T_e: float,
        T_z: float,
        p_z_ref: float,
        f_cross: bool,
        shield_class: VentilationShieldClass,
        R_w_arg: float,
    ) -> tuple[float, float]:
        """Calculate the airflow through window opening based on the how open the window is and internal pressure

        Arguments:
        wind_direction -- direction wind is blowing from, in clockwise degrees from North
        u_site -- wind velocity at zone level (m/s)
        T_e -- external air temperature (K)
        T_z -- thermal zone air temperature (K)
        p_z_ref -- internal reference pressure (Pa)
        f_cross -- boolean, dependant on if cross ventilation is possible or not
        shield_class -- indicates exposure to wind
        R_w_arg -- ratio of window opening (0-1)
        """
        # Assume windows are shut if the control object is empty
        if self.__on_off_ctrl_obj is None:
            R_w_arg = 0
        if self.__on_off_ctrl_obj is not None and not self.__on_off_ctrl_obj.is_on():
            R_w_arg = 0

        # Wind pressure coefficient for the window
        pressure_coefficient_path = get_pressure_coefficient(
            f_cross=f_cross,
            shield_class=shield_class,
            z=self.__z,
            wind_direction=wind_direction,
            orientation=self.__orientation,
            pitch=self.__pitch,
        )

        # Airflow coefficient of the window
        C_w_path = self.calculate_flow_coeff_for_window(R_w_arg=R_w_arg)

        # Sum airflow through each window part entering and leaving - based on Equation 56 and 57
        qv_in_through_window_opening = 0
        qv_out_through_window_opening = 0
        for window_part in self.__window_parts:
            air_flow = window_part.calculate_ventilation_through_windows_using_internal_p(
                u_site=u_site,
                T_e=T_e,
                T_z=T_z,
                C_w_path=C_w_path,
                p_z_ref=p_z_ref,
                C_p_path=pressure_coefficient_path,
            )
            if air_flow >= 0:
                qv_in_through_window_opening += air_flow
            else:
                qv_out_through_window_opening += air_flow

        # Convert volume air flow rate to mass air flow rate
        qm_in_through_window_opening, qm_out_through_window_opening = convert_to_mass_air_flow_rate(
            qv_in=qv_in_through_window_opening,
            qv_out=qv_out_through_window_opening,
            T_e=T_e,
            T_z=T_z,
            p_a_alt=self.__p_a_alt,
        )
        return qm_in_through_window_opening, qm_out_through_window_opening


class WindowPart:
    def __init__(
        self,
        midheight: float,
        free_area_height: float,
        number_window_divisions: float,
        window_part_number: int,
        ventilation_zone_base_height: float,
    ):
        """
        Construct a WindowPart object

        Argument:
            midheight -- Mid-height of the window
            free_area_height -- free area height of the window
            number_window_divisions -- number of window divisions
            window_part_number -- The identifying number of the window part
        """
        self.__h_w_path = midheight  # Find from inp file - Midheight of window part
        self.__h_w_fa = free_area_height  # Find from inp file
        self.__N_w_div = number_window_divisions
        self.__h_w_div_path = self.calculate_height_for_delta_p_w_div_path(j=window_part_number)
        self.__n_w = 0.5  # Flow exponent of window
        self.__z = self.__h_w_path + ventilation_zone_base_height

    def calculate_ventilation_through_windows_using_internal_p(
        self,
        u_site: float,
        T_e: float,
        T_z: float,
        C_w_path: float,
        p_z_ref: float,
        C_p_path: float,
    ) -> float:
        """Calculate the airflow through window parts from internal pressure

        Arguments:
        u_site -- wind velocity at zone level (m/s)
        T_e -- external air temperature (K)
        T_z -- thermal zone air temperature (K)
        C_w_path -- wind pressure coefficient at height of the window
        p_z_ref -- internal reference pressure (Pa)
        C_p_path -- wind pressure coefficient at the height of the window part
        """
        delta_p_path = calculate_pressure_difference_at_an_airflow_path(
            h_path=self.__h_w_div_path,
            C_p_path=C_p_path,
            u_site=u_site,
            T_e=T_e,
            T_z=T_z,
            p_z_ref=p_z_ref,
        )
        # Based on Equation 53
        qv_w_div_path = (
            C_w_path
            / (self.__N_w_div + 1)
            * np.sign(delta_p_path)
            * abs(delta_p_path) ** self.__n_w
        )
        return qv_w_div_path

    def calculate_height_for_delta_p_w_div_path(self, j: float) -> float:
        """The height to be considered for delta_p_w_div_path
        Equation 55 from BS EN 16798-7"""
        h_w_div_path = (
            self.__h_w_path
            - self.__h_w_fa / 2
            + self.__h_w_fa / (2 * (self.__N_w_div + 1))
            + (self.__h_w_fa / (self.__N_w_div + 1)) * (j - 1)
        )
        return h_w_div_path


class Vent:
    """An object to represent Vents"""

    def __init__(
        self,
        midheight: float,
        area: float,
        delta_p_vent_ref: float,
        orientation: Orientation360,
        pitch: float,
        altitude: float,
        ventilation_zone_base_height: float,
    ):
        """Construct a Vent object

        Arguments:
            h_path -- mid height of air flow path relative to ventilation zone (m)
            A_vent - Equivalent area of a vent (cm2)
            delta_p_vent_ref -- reference pressure difference for vent (Pa)
            orientation -- The orientation of the vent (degrees)
            pitch -- The pitch of the vent (degrees)
            altitude -- altitude of dwelling above sea level (m)

        Method:
            - Based on Section 6.4.3.6 Airflow through vents from BS EN 16798-7
        """
        self.__h_path = midheight
        self.__A_vent = area
        self.__delta_p_vent_ref = delta_p_vent_ref
        self.__orientation = orientation
        self.__pitch = pitch
        self.__altitude = altitude
        self.__n_vent = 0.5  # Flow exponent for vents based on Section B.3.2.2 from BS EN 16798-7
        self.__C_D_vent = 0.6  # Discharge coefficient of vents based on B.3.2.1 from BS EN 16798-7
        self.__p_a_alt = adjust_air_density_for_altitude(altitude=altitude)
        self.__z = self.__h_path + ventilation_zone_base_height

    def calculate_vent_opening_free_area(self, R_v_arg: float) -> float:
        """The vent opening free area A_vent for a vent
        Arguments:
        R_v_arg -- ratio of vent opening (0-1)
        """
        return R_v_arg * self.__A_vent

    def calculate_flow_coeff_for_vent(self, R_v_arg: float) -> float:
        """The airflow coefficient of the vent calculated from equivalent area A_vent
        according to EN 13141-1 and EN 13141-2.
        Based on Equation 59 from BS EN 16798-7.
        """
        # NOTE: The standard does not define what the below 3600 and 10000 are.
        A_vent = self.calculate_vent_opening_free_area(R_v_arg=R_v_arg)
        C_vent_path = (
            (3600 / 10000)
            * self.__C_D_vent
            * A_vent
            * (2 / p_a_ref) ** 0.5
            * (1 / self.__delta_p_vent_ref) ** (self.__n_vent - 0.5)
        )
        return C_vent_path

    def calculate_ventilation_through_vents_using_internal_p(
        self,
        u_site: float,
        T_e: float,
        T_z: float,
        C_vent_path: float,
        C_p_path: float,
        p_z_ref: float,
    ) -> float:
        """Calculate the airflow through vents from internal pressure

        Arguments:
        u_site -- wind velocity at zone level (m/s)
        T_e -- external air temperature (K)
        T_z -- thermal zone air temperature (K)
        C_vent_path -- wind pressure coefficient at height of the vent
        C_p_path -- wind pressure coefficient at the height of the window part
        p_z_ref -- internal reference pressure (Pa)
        """
        # Pressure_difference at the vent level
        delta_p_path = calculate_pressure_difference_at_an_airflow_path(
            h_path=self.__h_path,
            C_p_path=C_p_path,
            u_site=u_site,
            T_e=T_e,
            T_z=T_z,
            p_z_ref=p_z_ref,
        )

        # Air flow rate for each couple of height and wind pressure coeficient associated with vents.
        # Based on Equation 58
        qv_vent_path = C_vent_path * np.sign(delta_p_path) * abs(delta_p_path) ** self.__n_vent
        return qv_vent_path

    def calculate_flow_from_internal_p(
        self,
        wind_direction: Orientation360,
        u_site: float,
        T_e: float,
        T_z: float,
        p_z_ref: float,
        f_cross: bool,
        shield_class: VentilationShieldClass,
        R_v_arg: float,
    ) -> tuple[float, float]:
        """Calculate the airflow through vents from internal pressure

        Arguments:
        wind_direction -- direction wind is blowing from, in clockwise degrees from North
        u_site -- wind velocity at zone level (m/s)
        T_e -- external air temperature (K)
        T_z -- thermal zone air temperature (K)
        p_z_ref -- internal reference pressure (Pa)
        f_cross -- boolean, dependant on if cross ventilation is possible or not
        shield_class -- indicates exposure to wind
        """

        # Wind pressure coefficient for the air flow path
        pressure_coefficient_path = get_pressure_coefficient(
            f_cross=f_cross,
            shield_class=shield_class,
            z=self.__z,
            wind_direction=wind_direction,
            orientation=self.__orientation,
            pitch=self.__pitch,
        )
        C_vent_path = self.calculate_flow_coeff_for_vent(R_v_arg=R_v_arg)
        # Calculate airflow through each vent
        air_flow = self.calculate_ventilation_through_vents_using_internal_p(
            u_site=u_site,
            T_e=T_e,
            T_z=T_z,
            C_vent_path=C_vent_path,
            C_p_path=pressure_coefficient_path,
            p_z_ref=p_z_ref,
        )

        # Sum airflows entering and leaving - based on Equation 60 and 61
        qv_in_through_vent = 0
        qv_out_through_vent = 0
        if air_flow >= 0:
            qv_in_through_vent += air_flow
        else:
            qv_out_through_vent += air_flow

        # Convert volume air flow rate to mass air flow rate
        qm_in_through_vent, qm_out_through_vent = convert_to_mass_air_flow_rate(
            qv_in=qv_in_through_vent,
            qv_out=qv_out_through_vent,
            T_e=T_e,
            T_z=T_z,
            p_a_alt=self.__p_a_alt,
        )
        return qm_in_through_vent, qm_out_through_vent


class Leaks:
    """An object to represent Leaks"""

    def __init__(
        self,
        midheight: float,
        delta_p_leak_ref: float,
        qv_delta_p_leak_ref: float,
        facade_direction: str,
        area_roof: float,
        area_facades: float,
        area_leak: float,
        altitude: float,
        ventilation_zone_base_height: float,
    ):
        """Construct a Leaks object

        Arguments:
            h_path -- mid height of the air flow path relative to ventilation zone floor level
            delta_p_leak_ref -- Reference pressure difference (From pressure test e.g blower door = 50Pa)
            qv_delta_p_leak_ref -- flow rate through
            facade_direction -- The direction of the facade the leak is on.
            A_roof -- Surface area of the roof of the ventilation zone (m2)
            A_facades -- Surface area of facades (m2)
            A_leak - Reference area of the envelope airtightness index qv_delta_p_leak_ref (depends on national context)
            altitude -- altitude of dwelling above sea level (m)
            ventilation_zone_base_height -- Base height of the ventilation zone relative to ground (m)

        Method:
            - - Based on Section 6.4.3.6 Airflow through leaks from BS EN 16798-7.

        """
        self.__h_path = midheight
        self.__delta_p_leak_ref = delta_p_leak_ref
        self.__A_roof = area_roof
        self.__A_facades = area_facades
        self.__A_leak = area_leak
        self.__qv_delta_p_leak_ref = qv_delta_p_leak_ref
        self.__facade_direction = facade_direction
        self.__altitude = altitude
        self.__n_leak = 0.667  # Flow exponent through leaks based on value in B.3.3.14
        self.__C_leak_path = self.calculate_flow_coeff_for_leak()
        self.__p_a_alt = adjust_air_density_for_altitude(altitude=altitude)
        self.__z = self.__h_path + ventilation_zone_base_height

    def calculate_flow_coeff_for_leak(self) -> float:
        """The airflow coefficient of the leak"""
        # C_leak - Leakage coefficient of ventilation zone
        C_leak = (
            self.__qv_delta_p_leak_ref * self.__A_leak / (self.__delta_p_leak_ref) ** self.__n_leak
        )

        # Leakage coefficient of roof, estimated to be proportional to ratio
        # of surface area of the facades to that of the facades plus the roof.
        if "wind_seg" not in self.__facade_direction:  # leak in roof
            C_leak_roof = C_leak * self.__A_roof / (self.__A_facades + self.__A_roof)
            C_leak_path = C_leak_roof  # Table B.12
        # Leakage coefficient of facades, estimated to be proportional to ratio
        # of surface area of the roof to that of the facades plus the roof.
        else:  # leak in facades
            C_leak_facades = C_leak * self.__A_facades / (self.__A_facades + self.__A_roof)
            C_leak_path = 0.25 * C_leak_facades  # Table B.12
        return C_leak_path

    def calculate_ventilation_through_leaks_using_internal_p(
        self,
        u_site: float,
        T_e: float,
        T_z: float,
        C_p_path: float,
        p_z_ref: float,
    ) -> float:
        """Calculate the airflow through leaks from internal pressure

        Arguments:
        u_site -- wind velocity at zone level (m/s)
        T_e -- external air temperature (K)
        T_z -- thermal zone air temperature (K)
        C_p_path -- wind pressure coefficient at the height of the window part
        p_z_ref -- internal reference pressure (Pa)
        """
        # For each couple of height and wind pressure coeficient associated with vents,
        # the air flow rate.
        delta_p_path = calculate_pressure_difference_at_an_airflow_path(
            h_path=self.__h_path,
            C_p_path=C_p_path,
            u_site=u_site,
            T_e=T_e,
            T_z=T_z,
            p_z_ref=p_z_ref,
        )

        # Airflow through leaks based on Equation 62
        qv_leak_path = (
            self.__C_leak_path * np.sign(delta_p_path) * abs(delta_p_path) ** self.__n_leak
        )

        return qv_leak_path

    def calculate_flow_from_internal_p(
        self,
        wind_direction: Orientation360,
        u_site: float,
        T_e: float,
        T_z: float,
        p_z_ref: float,
        f_cross: bool,
        shield_class: VentilationShieldClass,
    ) -> tuple[float, float]:
        # Wind pressure coefficient for the air flow path
        pressure_coefficient_path = get_pressure_coefficient(
            f_cross=f_cross,
            shield_class=shield_class,
            z=self.__z,
            wind_direction=wind_direction,
            orientation=None,
            pitch=None,
            facade_direction=self.__facade_direction,
        )  # TABLE from annex B
        # Calculate airflow through each leak
        qv_in_through_leak = 0
        qv_out_through_leak = 0
        air_flow = self.calculate_ventilation_through_leaks_using_internal_p(
            u_site=u_site,
            T_e=T_e,
            T_z=T_z,
            C_p_path=pressure_coefficient_path,
            p_z_ref=p_z_ref,
        )

        # Add airflow entering and leaving through leak
        if air_flow >= 0:
            qv_in_through_leak += air_flow
        else:
            qv_out_through_leak += air_flow

        # Convert volume air flow rate to mass air flow rate
        qm_in_through_leak, qm_out_through_leak = convert_to_mass_air_flow_rate(
            qv_in=qv_in_through_leak,
            qv_out=qv_out_through_leak,
            T_e=T_e,
            T_z=T_z,
            p_a_alt=self.__p_a_alt,
        )
        return qm_in_through_leak, qm_out_through_leak


# TODO uncomment when re-implementing ATDs
# class AirTerminalDevices:
#     """An object to represent AirTerminalDevices"""
#
#     def __init__(
#             self,
#             A_ATD,
#             delta_p_ATD_ref,
#             ):
#         """
#         Construct a AirTerminalDevices object
#
#         Arguments:
#             A_ATD -- equivalent area of the air terminal device (m2)
#             delta_p_ATD_ref -- Reference pressure difference for an air terminal device (Pa)
#
#         Method:
#             Based on Section 6.4.3.2.2 from BS EN 16798-7
#         """
#         self.__C_D_ATD = 0.6 # Discharge coefficient for air terminal devices based on B.3.2.1
#         self.__n_ATD = 0.5 # Flow exponent of air terminal devices based on B.3.2.2
#         self.__A_ATD = A_ATD
#         self.__delta_p_ATD_ref = delta_p_ATD_ref
#         self.__C_ATD_path = self.calculate_flow_coeff_for_ATD()
#
#     def calculate_flow_coeff_for_ATD(self):
#         """The airflow coefficient of the ATD is calculated
#         from the equivalent area A_vent value, according to
#         EN 13141-1 and EN 13141-2.
#         Equation 26 from BS EN 16798-7."""
#         #NOTE: The standard does not define what the below 3600 and 10000 are.
#         C_ATD_path = (3600/10000) * self.__C_D_ATD \
#                                   * self.__A_ATD \
#                                   * (2 / p_a_ref)**0.5 \
#                                   * (1 / self.__delta_p_ATD_ref) \
#                                   **(self.__n_ATD - 0.5)
#         return C_ATD_path
#
#     def calculate_pressure_difference_atd(self, qv_pdu):
#         """The pressure loss at internal air terminal devices is calculated from
#         the total air flow rate passing through the device.
#         Equation 25 from BS EN 16798-7.
#         Solving for qv_pdu.
#
#         Arguments:
#         qv_pdu - volume flow rate through passive and hybrid ducts.
#         """
#         delta_p_ATD = -(np.sign(qv_pdu)) \
#                     * (abs(qv_pdu)/self.__C_ATD_path) \
#                     ** (1/self.__n_ATD)
#         return delta_p_ATD


# class Cowls:
#     """An object to represent Cowls"""
#
#     def __init__(
#         self,
#         height,
#     ):
#         """
#         Construct a Cowls object
#
#         Arguments:
#         height - height Between the top of the roof and the roof outlet in m (m)
#         """
#         self.__C_p_cowl_roof = 0  # Default B.3.3.5
#         self.__delta_cowl_height = self.get_delta_cowl_height(height)
#
#     def get_delta_cowl_height(self, height):
#         """Interpreted Table B.9 from BS EN 16798-7
#         Get values for delta_C_cowl_height.
#
#         Arguments:
#         height - height Between the top of the roof and the roof outlet in m (m)
#         """
#         if height < 0.5:
#             delta_p_cowl_height = -0.0
#         elif height >= 0.5 and height <= 1.0:
#             delta_p_cowl_height = -0.1
#         else:
#             delta_p_cowl_height = -0.2
#         return delta_p_cowl_height


class CombustionAppliances:
    """An object to represent CombustionAppliances"""

    def __init__(
        self,
        supply_situation: CombustionAirSupplySituation,
        exhaust_situation: FlueGasExhaustSituation,
        fuel_type: CombustionFuelType,
        appliance_type: CombustionApplianceType,
    ):
        """Construct a CombustionAppliances object

        Arguments:
        f_op_comp -- Operation requirement signal (combustion appliance) (0 =  OFF ; 1 = ON)
        supply_situation - Combustion air supply situation: 'room_air' or 'outside'
        exhaust_situation - flue gas exhaust situation: 'into_room', 'into_separate_duct' or 'into_mech_vent'
        f_ff -- combustion air flow factor
        P_h_fi - Combustion appliance heating fuel input power (kW)
        """
        self.__f_as = get_appliance_system_factor(
            supply_situation, exhaust_situation
        )  # Combustion appliance system factor (0 or 1)
        self.__f_ff = get_fuel_flow_factor(
            fuel_type=fuel_type, appliance_type=appliance_type
        )  # Fuel flow factor (0-5)

    def calculate_air_flow_req_for_comb_appliance(
        self, f_op_comp: int, P_h_fi: float
    ) -> tuple[float, float]:
        """Calculate additional air flow rate required for the operation of
        combustion appliance q_v_comb.

        Arguments:
        f_op_comp --  Operation requirement signal (combustion appliance) (0 =  OFF ; 1 = ON)
        P_h_fi -- Combustion appliance heating fuel input power (kW)

        Returns:
        q_v_in_through_comb, q_v_out_through_comb
        """
        if f_op_comp == 1:
            q_v_comb = 3.6 * f_op_comp * self.__f_as * self.__f_ff * P_h_fi  # (35)
            q_v_in_through_comb = 0  # (37)
            q_v_out_through_comb = -q_v_comb  # (38)
            # temp associated with q_v_out_through_comb is ventilation zone temperature Tz
        else:
            q_v_in_through_comb = 0
            q_v_out_through_comb = 0
            # TODO flue is considered as vertical passive duct, standard formulas in CIBSE guide.
        return q_v_in_through_comb, q_v_out_through_comb


class MechanicalVentilation:
    """An object to represent Mechanical Ventilation"""

    def __init__(
        self,
        sup_air_flw_ctrl: SupplyAirFlowRateControlType,
        sup_air_temp_ctrl: SupplyAirTemperatureControlType,
        Q_H_des: float,
        Q_C_des: float,
        vent_type: MechVentType,
        specific_fan_power: float,
        design_outdoor_air_flow_rate: float,
        simulation_time: SimulationTime,
        energy_supply_conn: EnergySupplyConnection,
        total_volume: float,
        altitude: float,
        orientation_exhaust: Orientation360,  # For MVHR exhaust / MEV extract
        pitch_exhaust: float,
        midheight_exhaust: float,
        ventilation_zone_base_height: float,
        ctrl_intermittent_MEV: SetpointTimeControl | None = None,
        mvhr_eff: float = 0.0,
        theta_ctrl_sys: float | None = None,  # Only required if sup_air_temp_ctrl = LOAD_COM
        orientation_intake: Orientation360 | None = None,  # For MVHR intake
        pitch_intake: float | None = None,
        h_path_intake: float | None = None,
        sfp_in_use_factor: float = 1.0,
        mvhr_location: MVHRLocation | None = None,
        mvhr_ductwork: list[Ductwork] | None = None,
    ):
        """Construct a Mechanical Ventilation object

        Arguments:
            sup_air_flw_ctrl -- supply air flow rate control
            sup_air_temp_ctrl --supply air temperature control
            Q_H_des -- design zone heating need to be covered by the mechanical ventilation system
            Q_C_des -- design zone cooling need to be covered by the mechanical ventilation system
            vent_type -- ventilation system type
            specific_fan_power -- in W / (litre / second), assumed inclusive of any in use factors if sfp_in_use_factor not supplied
            design_outdoor_air_flow_rate -- design outdoor air flow rate in m3/h
            simulation_time -- reference to Simulation time object
            energy_supply_conn -- Energy supply connection
            total_volume  -- Total zone volume (m3)
            altitude -- altitude of dwelling above sea level (m)
            orientation_exhaust -- orientation of the exhaust (degrees) - for MVHR/MEV
            pitch_exhaust -- pitch of the exhaust (degrees) - for MVHR/MEV
            h_path_exhaust -- mid height of exhaust air flow path relative to ventilation zone (m) - for MVHR/MEV
            ventilation_zone_base_height -- Base height of the ventilation zone relative to ground (m)
            ctrl_intermittent_MEV -- reference to Control object with boolean schedule
                                    defining when the MechVent should be on.
            mvhr_eff -- MVHR efficiency
            theta_ctrl_sys -- Temperature variation based on control system (K)
            orientation_intake -- orientation of the intake (degrees) - for MVHR
            pitch_intake -- pitch of the intake (degrees) - for MVHR
            h_path_intake -- mid height of intake air flow path relative to ventilation zone (m) - for MVHR
            sfp_in_use_factor -- in-use factor to be applied to specific_fan_power. default of 1 if not supplied
            mvhr_location -- Location of the MVHR unit, inside or outside the thermal envelope
            mvhr_ductwork -- list of ductwork objects associated with this MVHR system
        """

        # Validate that required positions are provided
        if vent_type == MechVentType.MVHR:
            if any(
                v is None
                for v in [
                    orientation_intake,
                    pitch_intake,
                    h_path_intake,
                ]
            ):
                raise ValueError("MVHR systems require both intake and exhaust positions")

        # Hard coded variables
        self.__f_ctrl = 1  # From table B.4, for residential buildings, default f_ctrl = 1
        self.__f_sys = 1.1  # From table B.5, f_sys = 1.1
        self.__E_v = (
            1  # Section B.3.3.7 defaults E_v = 1 (this is the assumption for perfect mixing)
        )
        self.theta_z_t = 0  # TODO get Thermal zone temperature - used for LOAD
        self.__sup_air_flw_ctrl = (
            SupplyAirFlowRateControlType.ODA
        )  # TODO currently hard coded until load comp implemented
        self.__sup_air_temp_ctrl = (
            SupplyAirTemperatureControlType.NO_CTRL
        )  # TODO currently hard coded until load comp implemented

        # Arguments
        self.__Q_H_des = Q_H_des
        self.__Q_C_des = Q_C_des
        self.__theta_ctrl_sys = theta_ctrl_sys
        self.__vent_type = vent_type
        self.vent_type = vent_type
        self.total_volume = total_volume
        self.__ctrl_intermittent_MEV = ctrl_intermittent_MEV
        self.__sfp = specific_fan_power * sfp_in_use_factor
        self.__simtime = simulation_time
        self.__energy_supply_conn = energy_supply_conn
        self.__altitude = altitude
        self.design_outdoor_air_flow_rate_m3_h = design_outdoor_air_flow_rate  # in m3/h
        self.__mvhr_eff = mvhr_eff
        self.__mvhr_location = mvhr_location
        self.__mvhr_ductwork = mvhr_ductwork if mvhr_ductwork is not None else []

        # Store positions based on system type
        if vent_type == MechVentType.MVHR:
            self.__orientation_intake = orientation_intake
            self.__pitch_intake = pitch_intake
            self.__h_path_intake = h_path_intake
            self.__z_intake = (
                self.__h_path_intake + ventilation_zone_base_height
                if self.__h_path_intake is not None
                else ventilation_zone_base_height
            )

            self.__orientation_exhaust = orientation_exhaust
            self.__pitch_exhaust = pitch_exhaust
            self.__h_path_exhaust = midheight_exhaust  # is required for MVHR type
            self.__z_exhaust = self.__h_path_exhaust + ventilation_zone_base_height
        elif vent_type.is_extract_only():
            self.__orientation_exhaust = orientation_exhaust
            self.__pitch_exhaust = pitch_exhaust
            self.__h_path_exhaust = midheight_exhaust  # is required for extract_only types
            self.__z_exhaust = self.__h_path_exhaust + ventilation_zone_base_height
        else:
            raise ValueError("Mechanical ventilation type not recognised")  # PRAGMA: nocover

        # Calculated variables
        self.__qv_ODA_req_design = self.calculate_required_outdoor_air_flow_rate()
        self.__p_a_alt = adjust_air_density_for_altitude(altitude=altitude)

    def calculate_required_outdoor_air_flow_rate(self) -> float:
        """Calculate required outdoor ventilation air flow rates.
        Equation 9 from BS EN 16798-7."""
        # Required outdoor air flow rate in m3/h
        qv_ODA_req = (
            (self.__f_ctrl * self.__f_sys) / self.__E_v
        ) * self.design_outdoor_air_flow_rate_m3_h
        return qv_ODA_req

    def calc_req_ODA_flow_rates_at_ATDs(self) -> tuple[float, float]:
        """Calculate required outdoor air flow rates at the air terminal devices
        Equations 10-17 from BS EN 16798-7
        Adjusted to be based on ventilation type instead of vent_sys_op.
        """
        if self.__vent_type.is_balanced():
            qv_SUP_req = self.__qv_ODA_req_design
            qv_ETA_req = -self.__qv_ODA_req_design
            # NOTE: Calculation of effective flow rate of external air (in func
            # calc_mech_vent_air_flw_rates_req_to_supply_vent_zone) assumes that
            # supply and extract are perfectly balanced (as defined above), so
            # any future change to this assumption will need to be considered
            # with that in mind
        elif self.__vent_type.is_extract_only():
            qv_SUP_req = 0
            qv_ETA_req = -self.__qv_ODA_req_design
        elif self.__vent_type.is_supply_only():
            qv_SUP_req = self.__qv_ODA_req_design
            qv_ETA_req = 0
        else:
            raise ValueError("Unrecognised ventilation system type")

        return qv_SUP_req, qv_ETA_req

    def __f_op_v(self) -> float:
        """Returns the fraction of the timestep for which the ventilation is running"""
        if self.__vent_type.is_intermittent():
            f_op_V = (
                self.__ctrl_intermittent_MEV.setpnt()
                if self.__ctrl_intermittent_MEV is not None
                else None
            )
            if f_op_V is None or not 0 <= f_op_V <= 1:
                raise ValueError("Error f_op_V is not between 0 and 1.")
        elif self.__vent_type.is_continuous():
            # Assumed to operate continuously
            f_op_V = 1
        else:
            raise ValueError("Unknown mechanical ventilation system type")
        return f_op_V

    def calc_mech_vent_air_flw_rates_req_to_supply_vent_zone(
        self,
        u_site: float,
        wind_direction: Orientation360,
        f_cross: bool,
        shield_class: VentilationShieldClass,
        T_z: float,
        T_e: float,
        p_z_ref: float,
        time_step: float,
    ) -> tuple[float, float, float]:
        """Calculate the air flow rates to and from the ventilation zone required from mechanical ventilation.
        u_site -- wind velocity at zone level (m/s)
        wind_direction -- direction wind is blowing from, in clockwise degrees from North
        f_cross -- boolean, dependent on if cross ventilation is possible or not
        shield_class -- indicates exposure to wind
        T_z -- thermal zone temperature (K)
        T_e -- external air temperature (K)
        p_z_ref -- internal reference pressure (Pa)
        """
        # Required air flow at air terminal devices
        qv_SUP_req, qv_ETA_req = self.calc_req_ODA_flow_rates_at_ATDs()
        delta_p_intake = 0.0
        delta_p_exhaust = 0.0
        # Calculate pressure differences based on system type
        if self.__vent_type.has_supply():
            pressure_coefficient_intake = get_pressure_coefficient(
                f_cross=f_cross,
                shield_class=shield_class,
                z=self.__z_intake,
                wind_direction=wind_direction,
                orientation=self.__orientation_intake,
                pitch=self.__pitch_intake,
            )

            delta_p_intake = calculate_pressure_difference_at_an_airflow_path(
                h_path=cast(float, self.__h_path_intake),
                C_p_path=pressure_coefficient_intake,
                u_site=u_site,
                T_e=T_e,
                T_z=T_z,
                p_z_ref=p_z_ref,
            )

        elif self.__vent_type.has_extract():
            pressure_coefficient_exhaust = get_pressure_coefficient(
                f_cross=f_cross,
                shield_class=shield_class,
                z=self.__z_exhaust,
                wind_direction=wind_direction,
                orientation=self.__orientation_exhaust,
                pitch=self.__pitch_exhaust,
            )

            delta_p_exhaust = calculate_pressure_difference_at_an_airflow_path(
                h_path=cast(
                    float, self.__h_path_exhaust
                ),  # is required for mvhr or extract_only types
                C_p_path=pressure_coefficient_exhaust,
                u_site=u_site,
                T_e=T_e,
                T_z=T_z,
                p_z_ref=p_z_ref,
            )
        else:
            raise ValueError("Unrecognised ventilation system type")

        # Amount of air flow depends on controls
        if self.__sup_air_flw_ctrl == SupplyAirFlowRateControlType.ODA:
            f_op_V = self.__f_op_v()

            # From Sensitivity of fans to back pressure – generic values for HEM - Technical Note
            try:
                flow_change_coefficient = FLOW_CHANGE_COEFFICIENTS[self.__vent_type]
            except KeyError as ex:
                ex.add_note("Unrecognised ventilation system type")
                raise ex

            # Based on Equation 18 and 19
            qv_SUP_dis_req = f_op_V * qv_SUP_req
            if self.__vent_type.has_supply():
                flow_intake_change_due_to_pressure = (
                    flow_change_coefficient
                    * delta_p_intake
                    / litres_per_cubic_metre
                    * seconds_per_hour
                )
                qv_SUP_dis_req = max(0, qv_SUP_dis_req + flow_intake_change_due_to_pressure)
            elif self.__vent_type.is_extract_only():
                pass
            else:
                # Considering the check already implemented on the MechVentilation Init call, this line is unreachable
                raise ValueError("Unrecognised ventilation system type")  # PRAGMA: nocover

            qv_ETA_dis_req = f_op_V * qv_ETA_req
            if self.__vent_type.has_extract():
                flow_exhaust_change_due_to_pressure = (
                    flow_change_coefficient
                    * delta_p_exhaust
                    / litres_per_cubic_metre
                    * seconds_per_hour
                )
                qv_ETA_dis_req = min(0, qv_ETA_dis_req + flow_exhaust_change_due_to_pressure)
            elif self.__vent_type.is_supply_only():  # Note: Supply-only systems (PIV) are not implemented and fail at initialization. Currently unreachable # PRAGMA: nocover
                pass  # PRAGMA: nocover
            else:
                # Considering the check already implemented on the MechVentilation Init call, this line is unreachable
                raise ValueError("Unrecognised ventilation system type")  # PRAGMA: nocover

        ### COMMENTED OUT CODE ###
        # "LOAD" air flow control not fully implemented.
        #        elif self.__sup_air_flw_ctrl == SupplyAirFlowRateControlType.LOAD:
        #            #TODO load not implementented
        #            Q_H_V_req = 10 #TODO get (Q_H_V_req) heat to be supplied to thermal zone by the ventilation system at current timestep.
        #            Q_C_V_req = 10 ##TODO get (Q_C_V_req) heat to be extracted from thermal zone by the ventilation system at current timestep.
        #            p_a = adjust_air_density_for_altitude(self.__altitude)
        #            theta_SUP_dis_out = 10 #TODO get supply air temperature from previous timestep.
        #            Q_H_V_emission_losses = Q_H_V_req * self.theta_ctrl_sys / (self.theta_z_t - self.theta_e_comb)
        #            Q_C_V_emission_losses = Q_C_V_req * self.theta_ctrl_sys / (self.theta_z_t - self.theta_e_comb)
        #            qv_SUP_dis_req = self.f_op_V * max(
        #                (Q_H_V_req + Q_H_V_emission_losses) / (p_a * c_a * (theta_SUP_dis_out - T_z + T_0_abs)),
        #                (Q_C_V_req + Q_C_V_emission_losses) / (p_a * c_a * (T_z - T_0_abs - theta_SUP_dis_out)),
        #                qv_SUP_req
        #                )
        #            qv_SUP_dis_max_des = max (
        #                self.Q_H_des / (p_a * c_a * (theta_SUP_dis_out - T_z + T_0_abs)),
        #                self.Q_C_des / (p_a * c_a * (T_z - T_0_abs - theta_SUP_dis_out)),
        #                self.qv_ODA_req_design
        #                )
        #            qv_SUP_dis_req = min(qv_SUP_dis_req, qv_SUP_dis_max_des)
        #
        #            if self.vent_type == MechVentType.MVHR:
        #                qv_ETA_dis_req = -qv_SUP_dis_req
        #            else:
        #                qv_ETA_dis_req = 0
        else:
            raise ValueError("Unknown sup_air_flw_ctrl type")

        # Calculate effective flow rate of external air
        # NOTE: Technically, the MVHR system supplies air at a higher
        # temperature than the outside air. However, it is simpler to
        # account for the heat recovery effect using an "equivalent" or
        # "effective" flow rate of external air
        qv_effective_heat_recovery_saving = qv_SUP_dis_req * self.__mvhr_eff

        # Convert volume air flow rate to mass air flow rate
        qm_SUP_dis_req, qm_ETA_dis_req = convert_to_mass_air_flow_rate(
            qv_in=qv_SUP_dis_req, qv_out=qv_ETA_dis_req, T_e=T_e, T_z=T_z, p_a_alt=self.__p_a_alt
        )
        qm_in_effective_heat_recovery_saving = convert_volume_flow_rate_to_mass_flow_rate(
            qv=qv_effective_heat_recovery_saving,
            temperature=T_e,
            p_a_alt=self.__p_a_alt,
        )

        return qm_SUP_dis_req, qm_ETA_dis_req, qm_in_effective_heat_recovery_saving

    def fans(
        self, zone_volume: float, total_volume: float, throughput_factor: float = 1.0
    ) -> float:
        """Calculate gains and energy use due to fans
        zone_volume -- volume of the zone (m3)
        total_volume -- volume of the dwelling (m3)
        vent_type -- one of "Intermittent MEV", "Centralised continuous MEV",
            "Decentralised continuous MEV", "MVHR" or "POSITIVE_INPUT_VENTILATION".
        """
        # Calculate energy use by fans
        fan_power_W = (
            self.__sfp * (self.__qv_ODA_req_design / seconds_per_hour) * litres_per_cubic_metre
        ) * (zone_volume / total_volume)
        fan_energy_use_kWh = (fan_power_W / W_per_kW) * self.__simtime.timestep() * self.__f_op_v()
        if self.__vent_type in (
            MechVentType.INTERMITTENT_MEV,
            MechVentType.CENTRALISED_CONTINUOUS_MEV,
            MechVentType.DECENTRALISED_CONTINUOUS_MEV,
        ):
            # Fan energy use = 0
            supply_fan_energy_use_kWh = 0.0
            extract_fan_energy_use_in_kWh = fan_energy_use_kWh
        elif self.__vent_type == MechVentType.MVHR:
            # Balanced, therefore split power between extract and supply fans
            supply_fan_energy_use_kWh = fan_energy_use_kWh / 2
            extract_fan_energy_use_in_kWh = fan_energy_use_kWh / 2
        ### COMMENTED OUT CODE ###
        # PIV not fully implemented
        #        elif self.__vent_type == MechVentType.POSITIVE_INPUT_VENTILATION:
        #            #Positive input, supply fans only
        #            supply_fan_energy_use_kWh = fan_energy_use_kWh
        #            extract_fan_energy_use_in_kWh = 0
        else:
            raise ValueError("Invalid ventilation type input.")  # PRAGMA: nocover

        self.__energy_supply_conn.demand_energy(amount_demanded=supply_fan_energy_use_kWh)
        self.__energy_supply_conn.demand_energy(amount_demanded=extract_fan_energy_use_in_kWh)

        return supply_fan_energy_use_kWh * W_per_kW / self.__simtime.timestep()

    def calc_internal_gains_ductwork(self, temp_intake: float, temp_extract: float) -> float:
        """Calculate the internal gains/losses from MVHR ductwork.

        Accounts for the cascade effect where losses in extract/intake ducts
        affect the temperatures in supply/exhaust ducts after the heat exchanger.

        Arguments:
            temp_intake -- outdoor air temperature entering the system, in degrees C
            temp_extract -- indoor air temperature being extracted, in degrees C

        Returns:
            Internal gains in Watts (positive = heat gained by dwelling,
                                    negative = heat lost from dwelling)
        """
        gains_internal_intake_duct = 0.0
        gains_internal_supply_duct = 0.0
        gains_internal_extract_duct = 0.0
        gains_internal_exhaust_duct = 0.0

        vol_flow_rate_m3_per_hr = self.calculate_required_outdoor_air_flow_rate()
        vol_flow_rate_litres_per_s = (
            vol_flow_rate_m3_per_hr * litres_per_cubic_metre / seconds_per_hour
        )

        # Outside location
        # Air inside the duct loses heat, external environment gains heat
        # Loses energy to outside in extract duct - losses must be X by the efficiency of heat recovery
        # Loses energy to outside in supply duct - lose all because after MVHR unit
        if self.__mvhr_location == MVHRLocation.OUTSIDE:
            # Process extract ductwork (before heat exchanger)
            for duct in self.__mvhr_ductwork:
                if duct.get_duct_type() == DuctType.EXTRACT:
                    # Heat loss from extract ducts is to outside, so subtract from internal gains
                    gains_internal_extract_duct -= (
                        duct.duct_heat_loss(inside_temp=temp_extract, outside_temp=temp_intake)
                        * self.__mvhr_eff
                    )

            # Account for effect of losses from extract duct on temperature in supply duct
            temp_gain_extract_duct = gains_internal_extract_duct / (
                vol_flow_rate_litres_per_s * AIR.volumetric_heat_capacity()
            )
            # The duct heat loss calculation assumes a uniform temperature in the duct equal to the
            # temperature before any heat gains/losses. If the volume flow rate is low enough, this
            # can cause an unrealistically large temperature difference to be calculated, so the
            # temperature difference needs to be limited.
            if temp_gain_extract_duct < 0.0:
                # temp_gain_extract_duct is negative, so must be limited by taking max of value and limit
                temp_gain_extract_duct = max(temp_gain_extract_duct, temp_intake - temp_extract)
            else:
                # temp_gain_extract_duct is positive, so must be limited by taking min of value and limit
                temp_gain_extract_duct = min(temp_gain_extract_duct, temp_intake - temp_extract)
            # Recalculate duct gains to account for limit on temperature change of air flowing through
            gains_internal_extract_duct = (
                temp_gain_extract_duct * vol_flow_rate_litres_per_s * AIR.volumetric_heat_capacity()
            )

            temp_heat_exch_hot_side = temp_extract + temp_gain_extract_duct
            temp_supply_duct = temp_intake + self.__mvhr_eff * (
                temp_heat_exch_hot_side - temp_intake
            )

            # Process supply ductwork (after heat exchanger)
            for duct in self.__mvhr_ductwork:
                if duct.get_duct_type() == DuctType.SUPPLY:
                    # Heat loss from supply ducts is to outside, so subtract from internal gains
                    gains_internal_supply_duct -= duct.duct_heat_loss(
                        inside_temp=temp_supply_duct, outside_temp=temp_intake
                    )

        # Inside location
        # This will be a negative heat loss i.e. air inside the duct gains heat, dwelling loses heat
        # Gains energy from zone in intake duct - benefit of gain must be X by the efficiency of heat recovery
        # Gains energy from zone in exhaust duct
        elif self.__mvhr_location == MVHRLocation.INSIDE:
            # Process intake ductwork (before heat exchanger)
            for duct in self.__mvhr_ductwork:
                if duct.get_duct_type() == DuctType.INTAKE:
                    # Heat loss from intake ducts is to zone, so add to internal gains (may be negative gains)
                    gains_internal_intake_duct += (
                        duct.duct_heat_loss(inside_temp=temp_intake, outside_temp=temp_extract)
                        * self.__mvhr_eff
                    )

            # Account for effect of heat gained by intake duct on temperature in exhaust duct
            temp_gain_intake_duct = -gains_internal_intake_duct / (
                vol_flow_rate_litres_per_s * AIR.volumetric_heat_capacity()
            )
            # The duct heat loss calculation assumes a uniform temperature in the duct equal to the
            # temperature before any heat gains/losses. If the volume flow rate is low enough, this
            # can cause an unrealistically large temperature difference to be calculated, so the
            # temperature difference needs to be limited.
            if temp_gain_intake_duct < 0.0:
                # temp_gain_intake_duct is negative, so must be limited by taking max of value and limit
                temp_gain_intake_duct = max(temp_gain_intake_duct, temp_extract - temp_intake)
            else:
                # temp_gain_intake_duct is positive, so must be limited by taking min of value and limit
                temp_gain_intake_duct = min(temp_gain_intake_duct, temp_extract - temp_intake)
            # Recalculate duct gains to account for limit on temperature change of air flowing through
            gains_internal_intake_duct = (
                -temp_gain_intake_duct * vol_flow_rate_litres_per_s * AIR.volumetric_heat_capacity()
            )

            temp_heat_exch_cld_side = temp_intake + temp_gain_intake_duct
            temp_exhaust_duct = temp_extract - self.__mvhr_eff * (
                temp_extract - temp_heat_exch_cld_side
            )

            # Process exhaust ductwork (after heat exchanger)
            for duct in self.__mvhr_ductwork:
                if duct.get_duct_type() == DuctType.EXHAUST:
                    # Heat loss from exhaust ducts is to zone, so add to internal gains (may be negative gains)
                    gains_internal_exhaust_duct += duct.duct_heat_loss(
                        inside_temp=temp_exhaust_duct, outside_temp=temp_extract
                    )

        else:
            # Not MVHR, so no ductwork losses
            pass

        return (
            gains_internal_intake_duct
            + gains_internal_supply_duct
            + gains_internal_extract_duct
            + gains_internal_exhaust_duct
        )


class InfiltrationVentilation:
    """A class to represent Infiltration and Ventilation object"""

    def __init__(
        self,
        simulation_time: SimulationTime,
        f_cross: bool,
        shield_class: VentilationShieldClass,
        terrain_class: TerrainClass,
        average_roof_pitch: float,
        windows: dict[str, Window],
        vents: dict[str, Vent],
        leaks: dict[str, float],
        combustion_appliances: dict[str, CombustionAppliances],
        ATDs,
        mech_vents: list[MechanicalVentilation],
        detailed_output_heating_cooling: bool,
        altitude: float,
        total_volume: float,
        ventilation_zone_base_height: float,
    ):
        """
        Constructs a InfiltrationVentilation object

        Arguments:
            simulation_time -- reference to SimulationTime object
            f_cross -- cross-ventilation factor
            shield_class -- indicates the exposure to wind of an air flow path on a facade
                (can can be open, normal and shielded)
            ventilation_zone_height -- height of ventilation zone (m)
            windows -- list of windows
            vents -- list of vents
            leaks -- required inputs for leaks
            ATDs -- list of air terminal devices
            mech_vents -- list of mech vents
            altitude -- altitude of dwelling above sea level (m)
            total_volume -- total zone volume
            ventilation_zone_base_height -- base height of the ventilation zone (m)
        """
        self.__simulation_time = simulation_time
        self.__f_cross = f_cross
        self.__shield_class = shield_class
        self.__ventilation_zone_base_height = ventilation_zone_base_height
        self.ventilation_zone_height = leaks["ventilation_zone_height"]
        self.__C_rgh_site = terrain_class_to_roughness_coeff(
            terrain_class=terrain_class,
            z=ventilation_zone_base_height + self.ventilation_zone_height / 2,
        )
        self.__windows = []
        self.__vents = []
        self.__leaks = []
        self.__combustion_appliances = []
        self.__ATDs = []
        self.__mech_vents = mech_vents
        for window in windows.values():
            self.__windows.append(window)
        for vent in vents.values():
            self.__vents.append(vent)
        self.__leaks = self.make_leak_objects(
            leaks=leaks,
            average_roof_pitch=average_roof_pitch,
            ventilation_zone_base_height=ventilation_zone_base_height,
        )
        for combustion_appliance in combustion_appliances.values():
            self.__combustion_appliances.append(combustion_appliance)
        # TODO uncomment when re-implementing ATDs
        #         for ATD in ATDs.values():
        #             self.__ATDs.append(ATD)
        self.__detailed_output_heating_cooling = detailed_output_heating_cooling
        self.__ventilation_detailed_results = []
        self.__p_a_alt = adjust_air_density_for_altitude(altitude=altitude)
        self.total_volume = total_volume

    # def temp_supply(self):
    #     """ Calculate supply temperature of the air flow element """
    #     # NOTE: Technically, the MVHR system supplies air at a higher temperature
    #     # than the outside air, i.e.:
    #     #     temp_supply = self.__efficiency * temp_interior_air \
    #     #                 + (1 - self.__efficiency) * self.__external_conditions.air_temp()
    #     # However, calculating this requires the internal air temperature, which
    #     # has not been calculated yet. Calculating this properly would require
    #     # the equation above to be added to the heat balance solver. Therefore,
    #     # it is simpler to adjust the heat transfer coefficient h_ve to account
    #     # for the heat recovery effect using an "equivalent" flow rate of
    #     # external air, which is done elsewhere
    #     return self.__external_conditions.air_temp()

    def mech_vents(self) -> list[MechanicalVentilation]:
        """Return the list of mechanical ventilations."""
        return self.__mech_vents

    def calculate_total_volume_air_flow_rate_in(
        self, qm_in: float, external_air_density: float
    ) -> float:
        """Calculate total volume air flow rate entering ventilation zone
        Equation 68 from BS EN 16798-7"""
        return qm_in / external_air_density  # from weather file?

    def calculate_total_volume_air_flow_rate_out(
        self, qm_out: float, zone_air_density: float
    ) -> float:
        """Calculate total volume air flow rate leaving ventilation zone
        Equation 69 from BS EN 16798-7"""
        return qm_out / zone_air_density

    def make_leak_objects(
        self,
        leaks: dict[str, float | int],
        average_roof_pitch: float,
        ventilation_zone_base_height: float,
    ) -> list[Leaks]:
        """Distribute leaks around the dwelling according to Table B.12 from BS EN 16798-7.
        Create 5 leak objects:
            At 0.25*Height of the Ventilation Zone in the Windward facade
            At 0.25*Height of the Ventilation Zone in the Leeward facade
            At 0.75*Height of the Ventilation Zone in the Windward facade
            At 0.75*Height of the Ventilation Zone in the Leeward facade
            At the Height of the Ventilation Zone in the roof
        Arguments:
        leak - dict of leaks input data from JSON file
        average_roof_pitch - calculated in project.py, average pitch of all roof elements weighted by area (degrees)
        """
        h_path1_2 = 0.25 * leaks["ventilation_zone_height"]
        h_path3_4 = 0.75 * leaks["ventilation_zone_height"]
        h_path5 = leaks["ventilation_zone_height"]
        h_path_list = [h_path1_2, h_path1_2, h_path3_4, h_path3_4, h_path5]

        if self.__f_cross:
            if average_roof_pitch < 10:
                roof_pitch = "Roof10"
            elif average_roof_pitch <= 30:
                roof_pitch = "Roof10_30"
            elif average_roof_pitch < 60:
                roof_pitch = "Roof30"
            else:
                raise ValueError("Invalid roof pitch")
        else:
            roof_pitch = "Roof"

        # interim approach until implementation of new envelope leakage method
        # assign windward to wind segment 2, Leeward to wind segment 4
        # facade_direction = ["Windward", "Leeward", "Windward", "Leeward", roof_pitch]
        facade_direction = ["wind_seg2", "wind_seg4", "wind_seg2", "wind_seg4", roof_pitch]

        leaklist = []
        for i in range(0, 5):
            leak_obj = Leaks(
                midheight=h_path_list[i],
                delta_p_leak_ref=leaks["test_pressure"],
                qv_delta_p_leak_ref=leaks["test_result"],
                facade_direction=facade_direction[i],
                area_roof=leaks["area_roof"],
                area_facades=leaks["area_facades"],
                area_leak=leaks["env_area"],
                altitude=leaks["altitude"],
                ventilation_zone_base_height=ventilation_zone_base_height,
            )
            leaklist.append(leak_obj)
        return leaklist

    # TODO uncomment when re-implementing ATDs
    #     def calculate_qv_pdu(self, qv_pdu, p_z_ref, T_z, T_e, h_z):
    #         """Implicit solver for qv_pdu"""
    #         return fsolve(self.implicit_formula_for_qv_pdu, qv_pdu, args = (p_z_ref, T_z, T_e, h_z))[0] #returns qv_pdu
    #
    #     def implicit_formula_for_qv_pdu(self, qv_pdu, p_z_ref, T_z, T_e, h_z):
    #         """Implicit formula solving for qv_pdu as unknown.
    #         Equation 30 from BS EN 16798-7
    #         Arguments:
    #         qv_pdu -- volume flow rate from passive and hybrid ducts (m3/h)
    #         p_z_ref -- internal reference pressure (Pa)
    #         T_z -- thermal zone temperature (K)
    #         T_e -- external air temperature (K)
    #         h_z -- height of ventilation zone (m)
    #         """
    #         external_air_density = air_density_at_temp(T_e, self.__p_a_alt)
    #         zone_air_density = air_density_at_temp(T_z, self.__p_a_alt)
    #
    #         #TODO Standard isn't clear if delta_p_ATD can be totalled or not.
    #         delta_p_ATD_list = [atd.calculate_pressure_difference_atd(qv_pdu) for atd in self.__ATDs]
    #         delta_p_ATD = math.fsum(delta_p_ATD_list)
    #
    #         # Stack effect in passive and hybrid duct. As there is no air transfer
    #         # between levels of the ventilation zone Equation B.1 is used.
    #         h_pdu_stack = h_z + 2
    #
    #         #TODO include delta_p_dpu and delta_p_cowl in the return.
    #         return delta_p_ATD - p_z_ref - h_pdu_stack * g * (external_air_density - zone_air_density)

    def calculate_internal_reference_pressure(
        self,
        initial_p_z_ref_guess: float,
        wind_speed: float,
        wind_direction: Orientation360,
        temp_interior_air: float,
        temp_exterior_air: float,
        R_v_arg: float,
        R_w_arg: float | None = None,
    ) -> float:
        """The root scalar function will iterate until it finds a value of p_z_ref
        that satisfies the mass balance equation.
        The root scalar solver allows a range of intervals to be entered.
        The loop begins with a small interval to start with and if no solution is
        found or the boundary is too small for to cause a sign change then a wider
        interval is used until a solution is found.
        """
        interval_expansion_list = [1, 5, 10, 15, 20, 40, 50, 100, 200]
        for interval_expansion in interval_expansion_list:
            try:
                with warnings.catch_warnings():
                    warnings.filterwarnings("error", category=RuntimeWarning)
                    sol = root_scalar(
                        self.implicit_mass_balance_for_internal_reference_pressure,
                        args=(
                            wind_speed,
                            wind_direction,
                            temp_interior_air,
                            temp_exterior_air,
                            R_v_arg,
                            R_w_arg,
                        ),
                        method="brentq",
                        bracket=(
                            initial_p_z_ref_guess - interval_expansion,
                            initial_p_z_ref_guess + interval_expansion,
                        ),
                    )
                p_z_ref = sol.root
                return p_z_ref
            except ValueError as e:
                if str(e) == "f(a) and f(b) must have different signs":
                    continue
                # For other ValueError exceptions, re-raise
                raise
            except RuntimeWarning:
                continue
            except Exception as e:
                raise RuntimeError("Mass balance solver failed: " + str(e)) from e
        raise RuntimeError("Mass balance solver failed")

    def implicit_mass_balance_for_internal_reference_pressure(
        self,
        p_z_ref: float,
        wind_speed: float,
        wind_direction: Orientation360,
        temp_interior_air: float,
        temp_exterior_air: float,
        R_v_arg: float,
        R_w_arg_min_max: float,
        flag: str | None = None,
    ) -> np.float64 | float | int:
        """Used in calculate_internal_reference_pressure function for p_z_ref solve"""
        qm_in, qm_out, _ = self.__implicit_mass_balance_for_internal_reference_pressure_components(
            p_z_ref=p_z_ref,
            wind_speed=wind_speed,
            wind_direction=wind_direction,
            temp_interior_air=temp_interior_air,
            temp_exterior_air=temp_exterior_air,
            R_v_arg=R_v_arg,
            R_w_arg_min_max=R_w_arg_min_max,
            reporting_flag=flag,
        )
        return qm_in + qm_out

    def incoming_air_flow(
        self,
        p_z_ref: float,
        wind_speed: float,
        wind_direction: Orientation360,
        temp_interior_air: float,
        temp_exterior_air: float,
        R_v_arg: float,
        R_w_arg_min_max: float,
        reporting_flag: str | None = None,
        report_effective_flow_rate: bool = False,
    ) -> float | np.float64:
        """Calculate incoming air flow, in m3/hr, at specified conditions"""
        qm_in, _, qm_effective_flow_rate = (
            self.__implicit_mass_balance_for_internal_reference_pressure_components(
                p_z_ref=p_z_ref,
                wind_speed=wind_speed,
                wind_direction=wind_direction,
                temp_interior_air=temp_interior_air,
                temp_exterior_air=temp_exterior_air,
                R_v_arg=R_v_arg,
                R_w_arg_min_max=R_w_arg_min_max,
                reporting_flag=reporting_flag,
            )
        )
        if report_effective_flow_rate:
            qm_in -= qm_effective_flow_rate
        return convert_mass_flow_rate_to_volume_flow_rate(
            qm=qm_in,
            temperature=cast(float, Celcius2Kelvin(temp_exterior_air)),
            p_a_alt=self.__p_a_alt,
        )

    def __implicit_mass_balance_for_internal_reference_pressure_components(
        self,
        p_z_ref: float,
        wind_speed: float,
        wind_direction: Orientation360,
        temp_interior_air: float,
        temp_exterior_air: float,
        R_v_arg: float,
        R_w_arg_min_max: float,
        reporting_flag: str | None = None,
    ) -> tuple[np.float64 | float | int, np.float64 | float | int, np.float64 | float | int]:
        """Implicit mass balance for calculation of the internal reference pressure
        Equation 67 from BS EN 16798-7.

        Arguments:
        p_z_ref -- internal reference pressure (Pa)
        wind_speed -- wind speed, in m/s
        wind_direction -- direction wind is blowing from, in clockwise degrees from North
        temp_interior_air -- temperature of air in the zone (Celsius)
        temp_exterior_air -- temperature of external air (Celsius)
        reporting_flag -- flag used to give more detailed ventilation outputs (None = no additional reporting)

        Key Variables:
        qm_SUP_to_vent_zone - Supply air mass flow rate going to ventilation zone
        qm_ETA_from_vent_zone - Extract air mass flow rate from a ventilation zone
        qm_in_through_comb - Air mass flow rate entering through combustion appliances
        qm_out_through_comb - Air mass flow rate leaving through combustion appliances
        qm_in_through_passive_hybrid_ducts - Air mass flow rate entering through passive or hybrid duct
        qm_out_through_passive_hybrid_ducts - Air mass flow rate leaving through passive or hybrid duct
        qm_in_through_window_opening - Air mass flow rate entering through window opening
        qm_out_through_window_opening - Air mass flow rate leaving through window opening
        qm_in_through_vents - Air mass flow rate entering through vents (openings in the external envelope)
        qm_out_through_vents - Air mass flow rate leaving through vents (openings in the external envelope)
        qm_in_through_leaks - Air mass flow rate entering through envelope leakage
        qm_out_through_leaks - Air mass flow rate leaving through envelope leakage
        """
        u_site = wind_speed_at_zone_level(self.__C_rgh_site, wind_speed)
        T_e = cast(float, Celcius2Kelvin(temp_exterior_air))
        T_z = cast(float, Celcius2Kelvin(temp_interior_air))
        qm_in_through_window_opening = 0
        qm_out_through_window_opening = 0
        qm_in_through_vents = 0
        qm_out_through_vents = 0
        qm_in_through_leaks = 0
        qm_out_through_leaks = 0
        qm_in_through_comb = 0
        qm_out_through_comb = 0
        qm_in_through_passive_hybrid_ducts = 0
        qm_out_through_passive_hybrid_ducts = 0
        qm_SUP_to_vent_zone = 0
        qm_ETA_from_vent_zone = 0
        qm_in_effective_heat_recovery_saving_total = 0.0
        for window in self.__windows:
            qm_in, qm_out = window.calculate_flow_from_internal_p(
                wind_direction=wind_direction,
                u_site=u_site,
                T_e=T_e,
                T_z=T_z,
                p_z_ref=p_z_ref,
                f_cross=self.__f_cross,
                shield_class=self.__shield_class,
                R_w_arg=R_w_arg_min_max,
            )
            qm_in_through_window_opening += qm_in
            qm_out_through_window_opening += qm_out
        for vent in self.__vents:
            qm_in, qm_out = vent.calculate_flow_from_internal_p(
                wind_direction=wind_direction,
                u_site=u_site,
                T_e=T_e,
                T_z=T_z,
                p_z_ref=p_z_ref,
                f_cross=self.__f_cross,
                shield_class=self.__shield_class,
                R_v_arg=R_v_arg,
            )
            qm_in_through_vents += qm_in
            qm_out_through_vents += qm_out
        for leak in self.__leaks:
            qm_in, qm_out = leak.calculate_flow_from_internal_p(
                wind_direction=wind_direction,
                u_site=u_site,
                T_e=T_e,
                T_z=T_z,
                p_z_ref=p_z_ref,
                f_cross=self.__f_cross,
                shield_class=self.__shield_class,
            )
            qm_in_through_leaks += qm_in
            qm_out_through_leaks += qm_out
        # TODO uncomment when re-implementing ATDs
        #         for ATD in self.__ATDs:
        #             qv_pdu_initial = 0 #TODO get from prev timestep
        #             h_z = self.ventilation_zone_height
        #             qv_pdu = self.calculate_qv_pdu(qv_pdu_initial, p_z_ref, T_z, T_e, h_z)
        #             if qv_pdu >= 0:
        #                 qv_pdu_in = qv_pdu
        #                 qv_pdu_out = 0
        #             else:
        #                 qv_pdu_in = 0
        #                 qv_pdu_out = qv_pdu
        #             qm_in_through_phds, qm_out_through_phds = convert_to_mass_air_flow_rate(
        #                 qv_pdu_in,
        #                 qv_pdu_out,
        #                 T_e,
        #                 T_z,
        #                 self.__p_a_alt
        #             )
        #             qm_in_through_passive_hybrid_ducts += qm_in_through_phds
        #             qm_out_through_passive_hybrid_ducts += qm_out_through_phds
        for combustion_appliance in self.__combustion_appliances:
            P_h_fi = 0  # TODO to work out from previous zone temperature? - Combustion appliance heating fuel input power
            f_op_comb = 1  # TODO work out what turns the appliance on or off. Schedule or Logic?
            qv_in, qv_out = combustion_appliance.calculate_air_flow_req_for_comb_appliance(
                f_op_comp=f_op_comb, P_h_fi=P_h_fi
            )
            qm_in_comb, qm_out_comb = convert_to_mass_air_flow_rate(
                qv_in=qv_in, qv_out=qv_out, T_e=T_e, T_z=T_z, p_a_alt=self.__p_a_alt
            )
            qm_in_through_comb += qm_in_comb
            qm_out_through_comb += qm_out_comb
        for mech_vent in self.__mech_vents:
            qm_SUP, qm_ETA, qm_in_effective_heat_recovery_saving = (
                mech_vent.calc_mech_vent_air_flw_rates_req_to_supply_vent_zone(
                    u_site=u_site,
                    wind_direction=wind_direction,
                    f_cross=self.__f_cross,
                    shield_class=self.__shield_class,
                    T_z=T_z,
                    T_e=T_e,
                    p_z_ref=p_z_ref,
                    time_step=self.__simulation_time.index(),
                )
            )
            qm_SUP_to_vent_zone += qm_SUP
            qm_ETA_from_vent_zone += qm_ETA
            qm_in_effective_heat_recovery_saving_total += qm_in_effective_heat_recovery_saving

        # Calculate the total mass airflow rate in and out of the zones
        qm_in = (
            qm_in_through_window_opening
            + qm_in_through_vents
            + qm_in_through_leaks
            + qm_in_through_comb
            + qm_in_through_passive_hybrid_ducts
            + qm_SUP_to_vent_zone
        )
        qm_out = (
            qm_out_through_window_opening
            + qm_out_through_vents
            + qm_out_through_leaks
            + qm_out_through_comb
            + qm_out_through_passive_hybrid_ducts
            + qm_ETA_from_vent_zone
        )

        # Output detailed ventilation file
        if self.__detailed_output_heating_cooling:
            incoming_air_flow = convert_mass_flow_rate_to_volume_flow_rate(
                qm=qm_in,
                temperature=T_e,
                p_a_alt=self.__p_a_alt,
            )
            air_changes_per_hour = incoming_air_flow / self.total_volume

            if reporting_flag is not None:
                self.__ventilation_detailed_results.append(
                    [
                        self.__simulation_time.index(),
                        reporting_flag,
                        R_v_arg,
                        incoming_air_flow,
                        self.total_volume,
                        air_changes_per_hour,
                        temp_interior_air,
                        p_z_ref,
                        qm_in_through_window_opening,
                        qm_out_through_window_opening,
                        qm_in_through_vents,
                        qm_out_through_vents,
                        qm_in_through_leaks,
                        qm_out_through_leaks,
                        qm_in_through_comb,
                        qm_out_through_comb,
                        qm_in_through_passive_hybrid_ducts,
                        qm_out_through_passive_hybrid_ducts,
                        qm_SUP_to_vent_zone,
                        qm_ETA_from_vent_zone,
                        qm_in_effective_heat_recovery_saving_total,
                        qm_in,
                        qm_out,
                    ]
                )

        return qm_in, qm_out, qm_in_effective_heat_recovery_saving_total

    def output_vent_results(self) -> list[Any]:
        """Return the data dictionary containing detailed ventilation results"""
        return self.__ventilation_detailed_results

    def calc_air_changes_per_hour(
        self,
        wind_speed: float,
        wind_direction: Orientation360,
        temp_interior_air: float,
        temp_exterior_air: float,
        R_v_arg: float,
        R_w_arg: float,
        initial_p_z_ref_guess: float,
        reporting_flag: str | None = None,
        report_effective_flow_rate: bool = False,
    ) -> float | np.float64:
        internal_reference_pressure = self.calculate_internal_reference_pressure(
            initial_p_z_ref_guess=initial_p_z_ref_guess,
            wind_speed=wind_speed,
            wind_direction=wind_direction,
            temp_interior_air=temp_interior_air,
            temp_exterior_air=temp_exterior_air,
            R_v_arg=R_v_arg,
            R_w_arg=R_w_arg,
        )

        incoming_air_flow = self.incoming_air_flow(
            p_z_ref=internal_reference_pressure,
            wind_speed=wind_speed,
            wind_direction=wind_direction,
            temp_interior_air=temp_interior_air,
            temp_exterior_air=temp_exterior_air,
            R_v_arg=R_v_arg,
            R_w_arg_min_max=R_w_arg,
            reporting_flag=reporting_flag,
            report_effective_flow_rate=report_effective_flow_rate,
        )
        air_changes_per_hour = incoming_air_flow / self.total_volume
        return air_changes_per_hour

    def calc_diff_ach_target(
        self,
        R_v_arg: float,
        wind_speed: float,
        wind_direction: Orientation360,
        temp_interior_air: float,
        temp_exterior_air: float,
        ach_target: float,
        R_w_arg: float,
        initial_p_z_ref_guess: float,
        reporting_flag: str | None = None,
    ) -> float | np.float64:
        """
        Calculates the difference between the target air changes per hour (ACH) and the current ACH.

        Arguments:
            R_v_arg -- Current vent position, where 0 means vents are fully closed and 1 means vents are fully open.
            wind_speed -- Speed of the wind.
            wind_direction -- Direction of the wind.
            temp_interior_air -- Interior air temperature.
            temp_exterior_air -- Exterior air temperature.
            ach_target -- The desired target ACH value that needs to be achieved.
            R_w_arg -- Parameter related to the wind or building ventilation.
            initial_p_z_ref_guess --Initial guess for reference pressure.
            reporting_flag -- Flag indicating whether to report detailed output

        Returns:
            The adjusted absolute difference between the calculated ACH and the target ACH.
                   The difference is rounded to the 10th decimal place and a small gradient adjustment is applied
                   to help avoid numerical issues and local minima.
        """
        ach = self.calc_air_changes_per_hour(
            wind_speed=wind_speed,
            wind_direction=wind_direction,
            temp_interior_air=temp_interior_air,
            temp_exterior_air=temp_exterior_air,
            R_v_arg=R_v_arg,
            R_w_arg=R_w_arg,
            initial_p_z_ref_guess=initial_p_z_ref_guess,
            reporting_flag=reporting_flag,
        )
        # To avoid the solver finding local minimums & numerically stagnating:
        # 1. The residuals of this function (ach- ach_target) are rounded to the 10th decimal place
        # 2. A very small gradient (1e-10 * R_v_arg) is added to the residuals to slightly 'tilt'
        #    the surface of the function towards higher R_v_arg values. This is because it can be flat
        #    at low R_v_arg values when flow is dominated by other components.
        ach_diff_adjusted = round(abs(ach - ach_target), 10) - (1e-10 * R_v_arg)
        return ach_diff_adjusted

    def find_R_v_arg_within_bounds(
        self,
        ach_min: float | None,
        ach_max: float | None,
        initial_R_v_arg: float,
        wind_speed: float,
        wind_direction: Orientation360,
        temp_interior_air: float,
        temp_exterior_air: float,
        R_w_arg: float,
        initial_p_z_ref_guess: float,
        reporting_flag: str | None = None,
    ) -> float:
        """
        Determines the optimal vent position (R_v_arg) to achieve a desired air
        changes per hour (ACH) within specified bounds.

        Arguments:
            ach_min -- Minimum ACH limit.
            ach_max -- Maximum ACH limit.
            initial_R_v_arg -- Initial vent position, 0 = vents closed and 1 = vents fully open.
            wind_speed -- Speed of the wind.
            wind_direction -- Direction of the wind.
            temp_interior_air -- Interior air temperature.
            temp_exterior_air -- Exterior air temperature.
            R_w_arg -- Parameter related to the wind or building ventilation.
            initial_p_z_ref_guess -- Initial guess for reference pressure.
            reporting_flag -- Flag indicating whether to report detailed output.

        Returns:
            The optimal vent position (R_v_arg) that brings the ACH within the specified bounds.
        """
        # First, check if the vent position from previous timestep gives an ach within bounds
        initial_ach = self.calc_air_changes_per_hour(
            wind_speed=wind_speed,
            wind_direction=wind_direction,
            temp_interior_air=temp_interior_air,
            temp_exterior_air=temp_exterior_air,
            R_v_arg=initial_R_v_arg,
            R_w_arg=R_w_arg,
            initial_p_z_ref_guess=initial_p_z_ref_guess,
            reporting_flag=reporting_flag,
        )

        # Determine if initial_ach is within the bounds
        if ach_min is not None and ach_max is not None:
            if ach_min > ach_max:
                raise ValueError(
                    "ERROR: Max ach limit is below the min ach limit for vent opening."
                )
            if ach_min <= initial_ach <= ach_max:
                return initial_R_v_arg

        ach_target = None
        # Check extremes with fully open or closed vents
        if ach_min is not None and initial_ach < ach_min:
            # If initial ACH is less than ach_min, check ach with vents fully open
            ach_vent_open = self.calc_air_changes_per_hour(
                wind_speed=wind_speed,
                wind_direction=wind_direction,
                temp_interior_air=temp_interior_air,
                temp_exterior_air=temp_exterior_air,
                R_v_arg=1,  # vents fully open
                R_w_arg=R_w_arg,
                initial_p_z_ref_guess=initial_p_z_ref_guess,
                reporting_flag=reporting_flag,
            )
            if ach_vent_open < ach_min:
                # If the maximum achievable ACH with vents fully open is less than ach_min
                return 1.0

            # If current ACH is too low but ACH with vents fully open is higher than the threshold, set ach_target to ach_min
            ach_target = ach_min

        if ach_max is not None and initial_ach > ach_max:
            ach_vent_closed = self.calc_air_changes_per_hour(
                wind_speed=wind_speed,
                wind_direction=wind_direction,
                temp_interior_air=temp_interior_air,
                temp_exterior_air=temp_exterior_air,
                R_v_arg=0,  # vents fully closed
                R_w_arg=R_w_arg,
                initial_p_z_ref_guess=initial_p_z_ref_guess,
                reporting_flag=reporting_flag,
            )
            if ach_vent_closed > ach_max:
                # If the minimum achievable ACH with vents fully closed is less than ach_max
                return 0

            # If current ACH is too high but ACH with vents fully closed is lower than the threshold, set ach_target to ach_max
            ach_target = ach_max

        # If ach_target is still None, no need for further adjustment
        if ach_target is None:
            return initial_R_v_arg

        # With ach_target set to either ach_min or ach_max, run the minimize_scalar solver
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("error", category=RuntimeWarning)
                result = minimize_scalar(
                    self.calc_diff_ach_target,
                    args=(
                        wind_speed,
                        wind_direction,
                        temp_interior_air,
                        temp_exterior_air,
                        ach_target,
                        R_w_arg,
                        initial_p_z_ref_guess,
                        reporting_flag,
                    ),
                    bounds=(0, 1),
                    method="bounded",
                    options={"xatol": 1e-10},
                )
            R_v_arg_solution = max(0.0, min(1.0, float(result.x)))

            return R_v_arg_solution

        except Exception as e:
            raise RuntimeError("Vent opening ratio solver failed:" + str(e)) from None

    def calc_internal_gains_ductwork(
        self, temp_outdoor_air: float, temp_indoor_air: float
    ) -> float:
        """Calculate the losses/gains in the MVHR ductwork, in Watts"""
        return fsum(
            mech_vent.calc_internal_gains_ductwork(temp_outdoor_air, temp_indoor_air)
            for mech_vent in self.__mech_vents
        )


def create_infiltration_ventilation(
    infiltration_ventilation_dict: dict[str, Any],
    zones_dict: dict[str, dict[str, Any]],
    simulation_time: SimulationTime,
    detailed_output_heating_cooling: bool,
    energy_supplies: dict[str, EnergySupply],
    controls: dict[str, SetpointTimeControl | OnOffTimeControl],
) -> InfiltrationVentilation:
    ventilation_zone_base_height = infiltration_ventilation_dict["ventilation_zone_base_height"]

    windows_dict = {}
    for zone in zones_dict.values():
        for building_element_name, building_element in zone["BuildingElement"].items():
            if building_element["type"] == "BuildingElementTransparent":
                # Check control for window open exists
                if building_element.get("Control_WindowOpenable") is None:
                    on_off_ctrl_obj = None
                else:
                    ctrl = controls[building_element["Control_WindowOpenable"]]
                    on_off_ctrl_obj = ctrl if isinstance(ctrl, OnOffTimeControl) else None
                windows_dict[building_element_name] = Window(
                    free_area_height=building_element["free_area_height"],
                    midheight=building_element["mid_height"],
                    max_opening_area=building_element["max_window_open_area"],
                    window_part_list=building_element["window_part_list"],
                    orientation=Orientation360(building_element["orientation360"]),
                    pitch=building_element["pitch"],
                    altitude=infiltration_ventilation_dict["altitude"],
                    on_off_ctrl_obj=on_off_ctrl_obj,
                    ventilation_zone_base_height=ventilation_zone_base_height,
                )

    pitches = []
    areas = []
    for zone in zones_dict.values():
        for _building_element_name, building_element in zone["BuildingElement"].items():
            if building_element["type"] == "BuildingElementOpaque":
                if (
                    BuildingElement.pitch_class(pitch=building_element["pitch"])
                    == HeatFlowDirection.UPWARDS
                ):
                    pitches.append(building_element["pitch"])
                    areas.append(building_element["area"])
    # Work out the average pitch, weighted by area.
    area_tot = math.fsum(areas)
    if len(pitches) > 0:
        weighting = [x / area_tot for x in areas]
        weighted_pitches = list(map(lambda x, y: x * y, weighting, pitches))
        average_pitch = math.fsum(weighted_pitches)
    else:
        # This case doesn't matter as if the area of roof = 0, the leakage coefficient = 0 anyway.
        average_pitch = 0

    surface_area_facades_list = []
    surface_area_roof_list = []
    for zone in zones_dict.values():
        for _building_element_name, building_element in zone["BuildingElement"].items():
            # If wall
            if (
                BuildingElement.pitch_class(pitch=building_element["pitch"])
                == HeatFlowDirection.HORIZONTAL
            ):
                if building_element["type"] == "BuildingElementOpaque":
                    surface_area_facades_list.append(building_element["area"])
                elif building_element["type"] == "BuildingElementTransparent":
                    area = building_element["height"] * building_element["width"]
                    surface_area_facades_list.append(area)
            # If roof:
            if BuildingElement.pitch_class(building_element["pitch"]) == HeatFlowDirection.UPWARDS:
                if building_element["type"] == "BuildingElementOpaque":
                    surface_area_roof_list.append(building_element["area"])
                elif building_element["type"] == "BuildingElementTransparent":
                    area = building_element["height"] * building_element["width"]
                    surface_area_roof_list.append(area)

    surface_area_facades = math.fsum(surface_area_facades_list)
    surface_area_roof = math.fsum(surface_area_roof_list)

    # Loop trough zones to sum up volume to avoid infiltration redundant input.
    total_volume = 0
    for _zones, zone_data in zones_dict.items():
        total_volume += zone_data["volume"]

    vents_dict = {}
    for vent_name, vent_data in infiltration_ventilation_dict["Vents"].items():
        vents_dict[vent_name] = Vent(
            midheight=vent_data["mid_height_air_flow_path"],
            area=vent_data["area_cm2"],
            delta_p_vent_ref=vent_data["pressure_difference_ref"],
            orientation=Orientation360(vent_data["orientation360"]),
            pitch=vent_data["pitch"],
            altitude=infiltration_ventilation_dict["altitude"],
            ventilation_zone_base_height=ventilation_zone_base_height,
        )

    leaks_dict = infiltration_ventilation_dict["Leaks"]
    leaks_dict["area_facades"] = surface_area_facades
    leaks_dict["area_roof"] = surface_area_roof
    leaks_dict["altitude"] = infiltration_ventilation_dict["altitude"]

    combustion_appliances_dict = {}
    # Handle case where CombustionAppliances might be missing or empty
    if infiltration_ventilation_dict.get("CombustionAppliances"):
        for combustion_appliances_name, combustion_appliances_data in infiltration_ventilation_dict[
            "CombustionAppliances"
        ].items():
            combustion_appliances_dict[combustion_appliances_name] = CombustionAppliances(
                supply_situation=CombustionAirSupplySituation(
                    combustion_appliances_data["supply_situation"]
                ),
                exhaust_situation=FlueGasExhaustSituation(
                    combustion_appliances_data["exhaust_situation"]
                ),
                fuel_type=CombustionFuelType(combustion_appliances_data["fuel_type"]),
                appliance_type=CombustionApplianceType(
                    combustion_appliances_data["appliance_type"]
                ),
            )
    # Empty dictionary for air terminal devices until passive ducts work
    atds_dict = {}
    # TODO uncomment when re-implementing ATDs
    #     if infiltration_ventilation.get('AirTerminalDevices') is not None:
    #         for atd_name, atds_data in infiltration_ventilation['AirTerminalDevices'].items():
    #             atds_dict[atd_name] = AirTerminalDevices(
    #             atds_data['area_cm2'],
    #             atds_data['pressure_difference_ref'],
    #             )

    mech_vents_dict = {}
    # Check if Mechanical Ventilation exists
    if infiltration_ventilation_dict.get("MechanicalVentilation") is not None:
        for mech_vents_name, mech_vents_data in infiltration_ventilation_dict[
            "MechanicalVentilation"
        ].items():
            # Assign the appropriate control object
            if mech_vents_data.get("Control") is not None:
                ctrl = controls[mech_vents_data["Control"]]
                ctrl_intermittent_MEV = ctrl if isinstance(ctrl, SetpointTimeControl) else None
            else:
                ctrl_intermittent_MEV = None

            SFP_in_use_factor = mech_vents_data.get("SFP_in_use_factor", 1.0)

            energy_supply = energy_supplies[mech_vents_data["EnergySupply"]]
            # TODO Need to handle error if EnergySupply name is invalid.
            energy_supply_conn = energy_supply.connection(end_user_name=mech_vents_name)

            if mech_vents_data["vent_type"] == MechVentType.MVHR:
                mvhr_ductwork = []
                for ductwork_data in mech_vents_data["ductwork"]:
                    if ductwork_data["cross_section_shape"] == DuctShape.CIRCULAR:
                        duct_perimeter = None
                        internal_diameter = ductwork_data["internal_diameter_mm"] / mm_per_m
                        external_diameter = ductwork_data["external_diameter_mm"] / mm_per_m
                    elif ductwork_data["cross_section_shape"] == DuctShape.RECTANGULAR:
                        duct_perimeter = ductwork_data["duct_perimeter_mm"] / mm_per_m
                        internal_diameter = None
                        external_diameter = None
                    else:
                        raise ValueError("Duct shape not valid")

                    ductwork = Ductwork(
                        cross_section_shape=ductwork_data["cross_section_shape"],
                        duct_perimeter=duct_perimeter,
                        internal_diameter=internal_diameter,
                        external_diameter=external_diameter,
                        length=ductwork_data["length"],
                        k_insulation=ductwork_data["insulation_thermal_conductivity"],
                        thickness_insulation=ductwork_data["insulation_thickness_mm"] / mm_per_m,
                        reflective=ductwork_data["reflective"],
                        duct_type=ductwork_data["duct_type"],
                    )
                    mvhr_ductwork.append(ductwork)

                mech_vents_dict[mech_vents_name] = MechanicalVentilation(
                    sup_air_flw_ctrl=SupplyAirFlowRateControlType(
                        mech_vents_data["sup_air_flw_ctrl"]
                    ),
                    sup_air_temp_ctrl=SupplyAirTemperatureControlType(
                        mech_vents_data["sup_air_temp_ctrl"]
                    ),
                    Q_H_des=0,
                    Q_C_des=0,
                    vent_type=MechVentType(mech_vents_data["vent_type"]),
                    specific_fan_power=mech_vents_data["SFP"],
                    design_outdoor_air_flow_rate=mech_vents_data["design_outdoor_air_flow_rate"],
                    simulation_time=simulation_time,
                    energy_supply_conn=energy_supply_conn,
                    total_volume=total_volume,
                    altitude=infiltration_ventilation_dict["altitude"],
                    orientation_exhaust=Orientation360(
                        mech_vents_data["position_exhaust"]["orientation360"]
                    ),
                    pitch_exhaust=mech_vents_data["position_exhaust"]["pitch"],
                    midheight_exhaust=mech_vents_data["position_exhaust"][
                        "mid_height_air_flow_path"
                    ],
                    ventilation_zone_base_height=ventilation_zone_base_height,
                    ctrl_intermittent_MEV=ctrl_intermittent_MEV,
                    mvhr_eff=mech_vents_data["mvhr_eff"],
                    orientation_intake=Orientation360(
                        mech_vents_data["position_intake"]["orientation360"]
                    ),
                    pitch_intake=mech_vents_data["position_intake"]["pitch"],
                    h_path_intake=mech_vents_data["position_intake"]["mid_height_air_flow_path"],
                    sfp_in_use_factor=SFP_in_use_factor,
                    mvhr_location=mech_vents_data["mvhr_location"],
                    mvhr_ductwork=mvhr_ductwork,
                )
            elif mech_vents_data["vent_type"] in (
                MechVentType.INTERMITTENT_MEV,
                MechVentType.CENTRALISED_CONTINUOUS_MEV,
                MechVentType.DECENTRALISED_CONTINUOUS_MEV,
            ):
                mech_vents_dict[mech_vents_name] = MechanicalVentilation(
                    sup_air_flw_ctrl=SupplyAirFlowRateControlType(
                        mech_vents_data["sup_air_flw_ctrl"]
                    ),
                    sup_air_temp_ctrl=SupplyAirTemperatureControlType(
                        mech_vents_data["sup_air_temp_ctrl"]
                    ),
                    Q_H_des=0,  # mech_vents_data['design_zone_cooling_covered_by_mech_vent'],
                    Q_C_des=0,  # mech_vents_data['design_zone_heating_covered_by_mech_vent'],
                    vent_type=MechVentType(mech_vents_data["vent_type"]),
                    specific_fan_power=mech_vents_data["SFP"],
                    design_outdoor_air_flow_rate=mech_vents_data["design_outdoor_air_flow_rate"],
                    simulation_time=simulation_time,
                    energy_supply_conn=energy_supply_conn,
                    total_volume=total_volume,
                    altitude=infiltration_ventilation_dict["altitude"],
                    orientation_exhaust=Orientation360(mech_vents_data["orientation360"]),
                    pitch_exhaust=mech_vents_data["pitch"],
                    midheight_exhaust=mech_vents_data["mid_height_air_flow_path"],
                    ventilation_zone_base_height=ventilation_zone_base_height,
                    ctrl_intermittent_MEV=ctrl_intermittent_MEV,
                    sfp_in_use_factor=SFP_in_use_factor,
                )
            else:
                raise ValueError("Mechanical ventilation type not recognised")

    return InfiltrationVentilation(
        simulation_time=simulation_time,
        f_cross=infiltration_ventilation_dict["cross_vent_possible"],
        shield_class=infiltration_ventilation_dict["shield_class"],
        terrain_class=infiltration_ventilation_dict["terrain_class"],
        average_roof_pitch=average_pitch,
        windows=windows_dict,
        vents=vents_dict,
        leaks=leaks_dict,
        combustion_appliances=combustion_appliances_dict,
        ATDs=atds_dict,
        mech_vents=list(mech_vents_dict.values()),
        detailed_output_heating_cooling=detailed_output_heating_cooling,
        altitude=infiltration_ventilation_dict["altitude"],
        total_volume=total_volume,
        ventilation_zone_base_height=ventilation_zone_base_height,
    )
