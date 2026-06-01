#!/usr/bin/env python3

"""
This module contains common unit conversions for use by other modules.
"""

import math

J_per_kWh = 3600000
kJ_per_kWh = 3600
J_per_kJ = 1000
W_per_kW = 1000
litres_per_cubic_metre = 1000
m3_per_s_to_l_per_min = 60000
minutes_per_hour = 60
seconds_per_minute = 60
seconds_per_hour = 3600
hours_per_day = 24
days_per_year = 365
days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
knots_per_m_per_sec = 1 / (1852 / 3600)
mm_per_m = 1000


def average_monthly_to_annual(list_monthly_averages: list[float]) -> float:
    if len(list_monthly_averages) != 12:
        raise ValueError("list_monthly_averages should have a length of 12")
    return math.fsum(
        [
            month_ave * days_in_month[month_idx]
            for month_idx, month_ave in enumerate(list_monthly_averages)
        ]
    ) / sum(days_in_month)


def Celcius2Kelvin(temp_C: float) -> float:
    if temp_C < -273.15:
        raise ValueError(
            "temp_C should be greater than or equal to -273.15 (absolute zero on the Celsius scale)"
        )
    return temp_C + 273.15


def Kelvin2Celcius(temp_K: float) -> float:
    if temp_K < 0:
        raise ValueError(
            "temp_K should be greater than or equal to 0 (absolute zero on the Kelvin scale)"
        )
    return temp_K - 273.15


def convert_profile_to_daily(original_profile: list[float], timestep: float):
    """Convert profile from per-timestep figures to daily figures"""
    total_steps = len(original_profile)
    steps_per_day = int(hours_per_day / timestep)
    daily_profile = [
        math.fsum(original_profile[i : i + steps_per_day])
        for i in range(0, total_steps, steps_per_day)
    ]
    return daily_profile


def calculate_thermal_resistance_of_virtual_layer(
    u_value: float, thermal_resistance_floor_construction: float
) -> float:
    # Thermal properties of ground from BS EN ISO 13370:2017 Table 7
    # Use values for clay or silt (same as BR 443 and SAP 10)
    thermal_conductivity = 1.5  # in W/(m.K)

    # Calculate thermal resistance and heat capacity of fixed ground layer
    # using BS EN ISO 13370:2017
    thickness_ground_layer = 0.5  # in m. Specified in BS EN ISO 52016-1:2017 section 6.5.8.2

    # thermal resistance in (m2.K)/W
    r_gr = thickness_ground_layer / thermal_conductivity

    # Calculate thermal resistance of virtual layer using BS EN ISO 13370:2017 Equation (F1)
    r_si = 0.17  # ISO 6946 - internal surface resistance
    r_vi = (1.0 / u_value) - r_si - thermal_resistance_floor_construction - r_gr  # in m2.K/W
    # BS EN ISO 13370:2017 Table 2 validty interval r_vi > 0

    if r_vi <= 0:
        raise ValueError(
            "r_vi should be greater than zero. check u-value and thermal_resistance_floor_construction inputs for floors"
        )

    return r_vi


class Orientation360:
    def __init__(self, angle: float):
        if angle > 360 or angle < 0:
            raise ValueError("angle must be between 0 and 360")
        self.__angle = angle

    @property
    def angle(self) -> float:
        return self.__angle

    def transform_to_180(self) -> float:
        return 180 - self.__angle

    @staticmethod
    def create_from_180(angle180: float):
        if angle180 > 180 or angle180 < -180:
            raise ValueError("angle180 must be between -180 and 180")
        return Orientation360(180 - angle180)

    def __str__(self):
        return str(self.__angle)

    @staticmethod
    def orientation_difference(
        orientation1: "Orientation360", orientation2: "Orientation360"
    ) -> float:
        """Determine difference between two bearings, taking shortest route around circle"""
        op_rel_orientation = abs(orientation1.angle - orientation2.angle)
        if op_rel_orientation > 180:
            op_rel_orientation = 360 - op_rel_orientation
        return op_rel_orientation
