#!/usr/bin/env python3

"""
This module contains unit tests for units module
"""

import pytest

from hem_core.units import (
    Celcius2Kelvin,
    Kelvin2Celcius,
    Orientation360,
    average_monthly_to_annual,
    convert_profile_to_daily,
)


class TestUnits:
    """Unit tests for free functions in units module"""

    def test_temp_conversions(self):
        """Test temperature conversions between Celcius and Kelvin"""
        assert Celcius2Kelvin(temp_C=20.0) == 293.15, "incorrect conversion of C to K"
        assert Kelvin2Celcius(temp_K=5.0) == -268.15, "incorrect conversion of K to C"

    @pytest.mark.parametrize("temp_c", [i for i in range(-10, 80)])
    def test_temp_conversion_round_trip(self, temp_c):
        """Test round-trip conversion for a range of temperatures."""
        converted_k = Celcius2Kelvin(temp_C=float(temp_c))
        assert Kelvin2Celcius(temp_K=converted_k) == temp_c

    def test_temp_conversion_raises_error(self):
        """Test it raises a ValueError if the temperature is below absolute zero."""
        with pytest.raises(ValueError):
            Celcius2Kelvin(temp_C=-300)

        with pytest.raises(ValueError):
            Kelvin2Celcius(temp_K=-1)

    def test_average_monthly_to_annual(self):
        """Test conversion from monthly averages and annual average"""
        list_monthly_averages = [4.3, 4.9, 6.5, 8.9, 11.7, 14.6, 16.6, 16.4, 14.1, 10.6, 7.1, 4.2]
        expected = 10.020547945205479
        assert average_monthly_to_annual(list_monthly_averages) == pytest.approx(expected)

    def test_average_monthly_to_annual_raises_error_for_invalid_list_length(self):
        """Test it raises a ValueError if the list does not have a length of 12."""
        with pytest.raises(ValueError):
            invalid_list = [4.3, 4.9, 6.5, 8.9, 11.7, 14.6, 16.6, 16.4, 14.1]
            average_monthly_to_annual(list_monthly_averages=invalid_list)

    def test_convert_profile_to_daily(self):
        """Test conversion from per-timestep profile to daily profile"""
        list_timestep_totals = [1.0] * 48 + [x / 2 for x in range(0, 48)]
        expected = [48.0, 564.0]
        result = convert_profile_to_daily(original_profile=list_timestep_totals, timestep=0.5)
        assert result == expected


class TestOrientation360:
    """Unit tests for Orientation360 class"""

    def test_orientation360_angle(self):
        """Test that orientation360.angle returns the correct value"""
        orientation360 = Orientation360(180)
        assert orientation360.angle == 180

    def test_orientation360_invalid_angle(self):
        """Test that orientation360.angle raises an exception with an invalid value"""

        with pytest.raises(ValueError, match="angle must be between 0 and 360"):
            Orientation360(-10)
        with pytest.raises(ValueError, match="angle must be between 0 and 360"):
            Orientation360(380)

    def test_orientation360_str(self):
        """Test that orientation360.__str__ returns the correct value"""
        orientation360 = Orientation360(180)
        assert str(orientation360) == "180"

    @pytest.mark.parametrize(
        "value, expected_result",
        [
            (0, 180),
            (90, 90),
            (180, 0),
            (270, -90),
            (360, -180),
        ],
    )
    def test_orientation360_transform_to_180(self, value: int, expected_result: str):
        """Test that orientation360.transform_to_180 returns the correct values"""

        assert Orientation360(value).transform_to_180() == expected_result

    @pytest.mark.parametrize(
        "value, expected_result",
        [
            (-90, 270),
            (90, 90),
            (-180, 360),
            (0, 180),
            (180, 0),
        ],
    )
    def test_orientation360_create_from_180(self, value: int, expected_result: str):
        """Test that orientation360.transform_to_180 returns the correct values"""

        orientation360 = Orientation360.create_from_180(value)
        assert isinstance(orientation360, Orientation360)
        assert orientation360.angle == expected_result

    def test_orientation360_create_from_180_invalid_angle(self):
        """Test that orientation360.transform_to_180 raises an exception with an invalid angle"""

        with pytest.raises(ValueError, match="angle180 must be between -180 and 180"):
            Orientation360.create_from_180(190)
        with pytest.raises(ValueError, match="angle180 must be between -180 and 180"):
            Orientation360.create_from_180(-190)
