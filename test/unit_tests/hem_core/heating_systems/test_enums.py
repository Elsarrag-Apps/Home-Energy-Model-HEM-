import pytest

from hem_core.heating_systems.enums import SourceType


class TestSourceType:
    @pytest.mark.parametrize(
        "source_type, exhaust_air_result, air_source_fluid_result, water_source_fluid_result",
        [
            (SourceType.GROUND, False, False, True),
            (SourceType.OUTSIDE_AIR, False, True, False),
            (SourceType.EXHAUST_AIR_MEV, True, True, False),
            (SourceType.EXHAUST_AIR_MVHR, True, True, False),
            (SourceType.EXHAUST_AIR_MIXED, True, True, False),
            (SourceType.WATER_GROUND, False, False, True),
            (SourceType.WATER_SURFACE, False, False, True),
            (SourceType.HEAT_NETWORK, False, False, True),
            ("Ground", False, False, True),
            ("OutsideAir", False, True, False),
            ("ExhaustAirMEV", True, True, False),
            ("ExhaustAirMVHR", True, True, False),
            ("ExhaustAirMixed", True, True, False),
            ("WaterGround", False, False, True),
            ("WaterSurface", False, False, True),
            ("HeatNetwork", False, False, True),
        ],
    )
    def test_source_type_properties(
        self,
        source_type: SourceType | str,
        exhaust_air_result: bool,
        air_source_fluid_result: bool,
        water_source_fluid_result: bool,
    ):
        """Test that is_exhaust_air, source_fluid_is_air, source_fluid_is_water functions return correct results"""

        source_type_instance = SourceType(source_type)
        assert source_type_instance.is_exhaust_air == exhaust_air_result
        assert source_type_instance.source_fluid_is_air == air_source_fluid_result
        assert source_type_instance.source_fluid_is_water == water_source_fluid_result
