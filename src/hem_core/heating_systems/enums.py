from enum import StrEnum


class HeatingServiceType(StrEnum):
    DOMESTIC_HOT_WATER_COMBI = "domestic_hot_water_combi"
    DOMESTIC_HOT_WATER_REGULAR = "domestic_hot_water_regular"
    SPACE = "space"
    DOMESTIC_HOT_WATER_DIRECT = "domestic_hot_water_direct"


class SourceType(StrEnum):
    GROUND = "Ground"
    OUTSIDE_AIR = "OutsideAir"
    EXHAUST_AIR_MEV = "ExhaustAirMEV"
    EXHAUST_AIR_MVHR = "ExhaustAirMVHR"
    EXHAUST_AIR_MIXED = "ExhaustAirMixed"
    WATER_GROUND = "WaterGround"
    WATER_SURFACE = "WaterSurface"
    HEAT_NETWORK = "HeatNetwork"

    @property
    def is_exhaust_air(self) -> bool:
        return self in (
            SourceType.EXHAUST_AIR_MEV,
            SourceType.EXHAUST_AIR_MVHR,
            SourceType.EXHAUST_AIR_MIXED,
        )

    @property
    def source_fluid_is_air(self) -> bool:
        return self in (
            SourceType.OUTSIDE_AIR,
            SourceType.EXHAUST_AIR_MEV,
            SourceType.EXHAUST_AIR_MVHR,
            SourceType.EXHAUST_AIR_MIXED,
        )

    @property
    def source_fluid_is_water(self) -> bool:
        return self in (
            SourceType.GROUND,
            SourceType.WATER_GROUND,
            SourceType.WATER_SURFACE,
            SourceType.HEAT_NETWORK,
        )
