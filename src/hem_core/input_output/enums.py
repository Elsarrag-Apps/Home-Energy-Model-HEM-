"""
Enums used across the input schema and potentially other modules.
Extracted from input.py for better code organization.
"""

from enum import IntEnum, StrEnum


class BatteryLocation(StrEnum):
    INSIDE = "inside"
    OUTSIDE = "outside"


class BoilerHotWaterTest(StrEnum):
    M_L = "M&L"
    M_S = "M&S"
    M_ONLY = "M_only"
    NO_ADDITIONAL_TESTS = "No_additional_tests"


class BuildingElementType(StrEnum):
    OPAQUE = "BuildingElementOpaque"
    TRANSPARENT = "BuildingElementTransparent"
    GROUND = "BuildingElementGround"
    ADJACENT_CONDITIONED = "BuildingElementAdjacentConditionedSpace"
    ADJACENT_UNCONDITIONED_SPACE_SIMPLE = "BuildingElementAdjacentUnconditionedSpace_Simple"
    PARTY_WALL = "BuildingElementPartyWall"


class ControlCombinationOperation(StrEnum):
    AND_ = "AND"
    OR_ = "OR"
    XOR = "XOR"
    NOT_ = "NOT"
    MAX = "MAX"
    MIN = "MIN"
    MEAN = "MEAN"


class ControlLogicType(StrEnum):
    CELECT = "celect"
    HEAT_BATTERY = "heat_battery"
    HHRSH = "hhrsh"
    AUTOMATIC = "automatic"
    MANUAL = "manual"


class DaylightSavingsConfig(StrEnum):
    APPLICABLE_AND_TAKEN_INTO_ACCOUNT = "applicable and taken into account"
    APPLICABLE_BUT_NOT_TAKEN_INTO_ACCOUNT = "applicable but not taken into account"
    NOT_APPLICABLE = "not applicable"


class DiverterHeatSourceType(StrEnum):
    IMMERSION = "immersion"


class DuctShape(StrEnum):
    CIRCULAR = "circular"
    RECTANGULAR = "rectangular"


class DuctType(StrEnum):
    INTAKE = "intake"
    SUPPLY = "supply"
    EXTRACT = "extract"
    EXHAUST = "exhaust"


class EcoDesignControllerClass(IntEnum):
    CLASS_I = 1
    "On/off room thermostat"
    CLASS_II = 2
    "Weather compensator with modulating heaters"
    CLASS_III = 3
    "Weather compensator with on/off heaters"
    CLASS_IV = 4
    "TPI room thermostat with on/off heaters"
    CLASS_V = 5
    "Modulating room thermostat with modulating heaters"
    CLASS_VI = 6
    "Weather compensator with room sensor for modulating heaters"
    CLASS_VII = 7
    "Weather compensator with room sensor for on/off heaters"
    CLASS_VIII = 8
    "Multi room temperature control with modulating heaters"


class FloorType(StrEnum):
    SLAB_NO_EDGE_INSULATION = "Slab_no_edge_insulation"
    SLAB_EDGE_INSULATION = "Slab_edge_insulation"
    SUSPENDED_FLOOR = "Suspended_floor"
    HEATED_BASEMENT = "Heated_basement"
    UNHEATED_BASEMENT = "Unheated_basement"


class FuelType(StrEnum):
    LPG_BOTTLED = "LPG_bottled"
    LPG_BULK = "LPG_bulk"
    LPG_CONDITION_11_F = "LPG_condition_11F"
    CUSTOM = "custom"
    ELECTRICITY = "electricity"
    ENERGY_FROM_ENVIRONMENT = "energy_from_environment"
    MAINS_GAS = "mains_gas"
    UNMET_DEMAND = "unmet_demand"


class HeatPumpBackupControlType(StrEnum):
    NONE = "None"
    TOP_UP = "TopUp"
    SUBSTITUTE = "Substitute"


class HeatPumpSinkType(StrEnum):
    WATER = "Water"
    AIR = "Air"
    GLYCOL25 = "Glycol25"


class HeatPumpSourceType(StrEnum):
    GROUND = "Ground"
    OUTSIDE_AIR = "OutsideAir"
    EXHAUST_AIR_MEV = "ExhaustAirMEV"
    EXHAUST_AIR_MVHR = "ExhaustAirMVHR"
    EXHAUST_AIR_MIXED = "ExhaustAirMixed"
    WATER_GROUND = "WaterGround"
    WATER_SURFACE = "WaterSurface"
    HEAT_NETWORK = "HeatNetwork"


class HeatSourceLocation(StrEnum):
    INTERNAL = "internal"
    EXTERNAL = "external"


class HeatSourceWetType(StrEnum):
    """Enum for wet heat source types used in the heating system.

    These values are used as discriminators in the HeatSourceWet union type to identify
    different types of wet heat sources that can be configured in the system.
    """

    HEAT_PUMP = "HeatPump"
    BOILER = "Boiler"
    HEAT_BATTERY = "HeatBattery"
    HIU = "HIU"


class HotWaterHeatSourceType(StrEnum):
    """Enum for hot water heat source types used in the hot water system.

    These values are used as discriminators in the HotWaterHeatSource union type to identify
    different types of hot water heat sources that can be configured in the system.
    """

    IMMERSION_HEATER = "ImmersionHeater"
    SOLAR_THERMAL_SYSTEM = "SolarThermalSystem"
    HEAT_SOURCE_WET_SERVICE_WATER_REGULAR = "HeatSourceWet"
    HEAT_PUMP_HOT_WATER_ONLY = "HeatPump_HWOnly"


class HotWaterSourceType(StrEnum):
    """Enum for hot water source types used in the hot water system.

    These values are used as discriminators in the HotWaterSourceDetails union type to identify
    different types of hot water sources that can be configured in the system.

    Note: Some values (HIU, HEAT_BATTERY) overlap with HeatSourceWetType but serve different
    purposes - these are for hot water sources rather than general wet heat sources.
    """

    STORAGE_TANK = "StorageTank"
    COMBI_BOILER = "CombiBoiler"
    HIU = "HIU"
    POINT_OF_USE = "PointOfUse"
    SMART_HOT_WATER_TANK = "SmartHotWaterTank"
    HEAT_BATTERY = "HeatBattery"


class InverterType(StrEnum):
    OPTIMISED_INVERTER = "optimised_inverter"
    STRING_INVERTER = "string_inverter"


class MVHRLocation(StrEnum):
    INSIDE = "inside"
    OUTSIDE = "outside"


class MassDistributionClass(StrEnum):
    D = "D"
    E = "E"
    I = "I"  # noqa: E741  # Ambiguous variable name: `I`
    IE = "IE"
    M = "M"


class PartyWallCavityType(StrEnum):
    """Types of party wall cavity configurations"""

    SOLID = "solid"  # Solid wall or structurally insulated panel
    UNFILLED_UNSEALED = "unfilled_unsealed"  # Unfilled cavity with no effective edge sealing
    UNFILLED_SEALED = "unfilled_sealed"  # Unfilled cavity with effective sealing
    FILLED_SEALED = "filled_sealed"  # Fully filled cavity with effective sealing
    FILLED_UNSEALED = "filled_unsealed"  # Fully filled cavity with no effective edge sealing
    DEFINED_RESISTANCE = "defined_resistance"  # User-defined thermal resistance


class PartyWallLiningType(StrEnum):
    """Types of party wall lining"""

    WET_PLASTER = "wet_plaster"
    DRY_LINED = "dry_lined"


class PhotovoltaicVentilationStrategy(StrEnum):
    UNVENTILATED = "unventilated"
    MODERATELY_VENTILATED = "moderately_ventilated"
    STRONGLY_OR_FORCED_VENTILATED = "strongly_or_forced_ventilated"
    REAR_SURFACE_FREE = "rear_surface_free"


class EnergySupplyPriorityEntry(StrEnum):
    ELECTRIC_BATTERY = "ElectricBattery"
    DIVERTER = "diverter"


class ShadingObjectType(StrEnum):
    OBSTACLE = "obstacle"
    OVERHANG = "overhang"


class SolarCollectorLoopLocation(StrEnum):
    """Location of the main part of the solar thermal collector loop piping.

    This affects the ambient temperature used for heat loss calculations
    in the collector loop piping.
    """

    OUT = "OUT"
    "Outside - collector loop piping is located outdoors, uses external air temperature"

    HS = "HS"
    "Heated Space - collector loop piping is in heated space, uses internal air temperature"

    NHS = "NHS"
    "Non-Heated Space - collector loop piping is in unheated space, uses average of internal and external temperatures"


class SpaceCoolSystemType(StrEnum):
    AIR_CONDITIONING = "AirConditioning"


class AirFlowType(StrEnum):
    FAN_ASSISTED = "fan-assisted"
    DAMPER_ONLY = "damper-only"


class SupplyAirFlowRateControlType(StrEnum):
    ODA = "ODA"
    # LOAD = "LOAD"


class SupplyAirTemperatureControlType(StrEnum):
    # CONST = "CONST"
    NO_CTRL = "NO_CTRL"
    # LOAD_COM = "LOAD_COM"


class TerrainClass(StrEnum):
    OPEN_WATER = "OpenWater"
    OPEN_FIELD = "OpenField"
    SUBURBAN = "Suburban"
    URBAN = "Urban"


class TestLetter(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


class TimeControlType(StrEnum):
    ON_OFF_TIME = "OnOffTimeControl"
    SETPOINT_TIME = "SetpointTimeControl"
    CHARGE = "ChargeControl"
    ON_OFF_COST_MINIMISING = "OnOffCostMinimisingTimeControl"
    COMBINATION = "CombinationTimeControl"


class ThermalBridgingType(StrEnum):
    LINEAR = "ThermalBridgeLinear"
    POINT = "ThermalBridgePoint"


class MechVentType(StrEnum):
    INTERMITTENT_MEV = "Intermittent MEV"
    CENTRALISED_CONTINUOUS_MEV = "Centralised continuous MEV"
    DECENTRALISED_CONTINUOUS_MEV = "Decentralised continuous MEV"
    MVHR = "MVHR"
    POSITIVE_INPUT_VENTILATION = "Positive input ventilation"

    def is_balanced(self) -> bool:
        """
        Check if this ventilation type is a balanced system (both supply and extract).

        Returns:
            True if balanced system, False otherwise
        """
        return self == MechVentType.MVHR

    def is_extract_only(self) -> bool:
        """
        Check if this ventilation type is an extract-only system.

        Returns:
            True if extract-only system, False otherwise
        """
        return self in (
            MechVentType.INTERMITTENT_MEV,
            MechVentType.CENTRALISED_CONTINUOUS_MEV,
            MechVentType.DECENTRALISED_CONTINUOUS_MEV,
        )

    def is_supply_only(self) -> bool:
        """
        Check if this ventilation type is a supply-only system.

        Returns:
            True if supply-only system, False otherwise
        """
        return self == MechVentType.POSITIVE_INPUT_VENTILATION

    def has_supply(self) -> bool:
        """
        Check if this ventilation type includes supply air.

        Returns:
            True if system has supply component, False otherwise
        """
        return self.is_balanced() or self.is_supply_only()

    def has_extract(self) -> bool:
        """
        Check if this ventilation type includes extract air.

        Returns:
            True if system has extract component, False otherwise
        """
        return self.is_balanced() or self.is_extract_only()

    def is_continuous(self) -> bool:
        """
        Check if this ventilation type operates continuously.

        Returns:
            True if continuous operation, False otherwise
        """
        return self in (
            MechVentType.CENTRALISED_CONTINUOUS_MEV,
            MechVentType.DECENTRALISED_CONTINUOUS_MEV,
            MechVentType.MVHR,
        )

    def is_intermittent(self) -> bool:
        """
        Check if this ventilation type operates intermittently.

        Returns:
            True if intermittent operation, False otherwise
        """
        return self == MechVentType.INTERMITTENT_MEV


class VentilationShieldClass(StrEnum):
    OPEN = "Open"
    NORMAL = "Normal"
    SHIELDED = "Shielded"


class PipeworkContents(StrEnum):
    WATER = "water"
    GLYCOL25 = "glycol25"


class WaterPipeworkLocation(StrEnum):
    INTERNAL = "internal"
    EXTERNAL = "external"


class WindShieldLocation(StrEnum):
    SHELTERED = "Sheltered"
    AVERAGE = "Average"
    EXPOSED = "Exposed"


class WindowShadingType(StrEnum):
    OVERHANG = "overhang"
    SIDEFINRIGHT = "sidefinright"
    SIDEFINLEFT = "sidefinleft"
    REVEAL = "reveal"


class WindowTreatmentControl(StrEnum):
    AUTO_MOTORISED = "auto_motorised"
    COMBINED_LIGHT_BLIND_HVAC = "combined_light_blind_HVAC"
    MANUAL = "manual"
    MANUAL_MOTORISED = "manual_motorised"

    @property
    def is_manual(self) -> bool:
        return self.value in (
            WindowTreatmentControl.MANUAL,
            WindowTreatmentControl.MANUAL_MOTORISED,
        )

    @property
    def is_automatic(self) -> bool:
        return self.value in (
            WindowTreatmentControl.AUTO_MOTORISED,
            WindowTreatmentControl.COMBINED_LIGHT_BLIND_HVAC,
        )


class WindowTreatmentType(StrEnum):
    BLINDS = "blinds"
    CURTAINS = "curtains"


class WasteWaterHeatRecoverySystemType(StrEnum):
    INSTANTANEOUS_SYSTEM_A = "WWHRS_InstantaneousSystemA"
    INSTANTANEOUS_SYSTEM_B = "WWHRS_InstantaneousSystemB"
    INSTANTANEOUS_SYSTEM_C = "WWHRS_InstantaneousSystemC"


class ZoneTemperatureControlBasis(StrEnum):
    AIR = "air"
    OPERATIVE = "operative"


class ShowerType(StrEnum):
    MIXER_SHOWER = "MixerShower"
    INSTANT_ELECTRIC_SHOWER = "InstantElecShower"


class WetEmitterType(StrEnum):
    RADIATOR = "radiator"
    UFH = "ufh"
    FANCOIL = "fancoil"


class HeatFlowDirection(StrEnum):
    # Set up heat flow directions as enums
    HORIZONTAL = "HORIZONTAL"
    UPWARDS = "UPWARDS"
    DOWNWARDS = "DOWNWARDS"


class EdgeInsulationDirection(StrEnum):
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


class WWHRSConfiguration(StrEnum):
    """
    WWHRS system configuration

    A - Both shower and water heating system get pre-heated water
    B - Only shower gets pre-heated water
    C - Only water heating system gets pre-heated water
    """

    SHOWER_AND_WATER_HEATING_SYSTEM = "A"
    SHOWER = "B"
    WATER_HEATING_SYSTEM = "C"


# FHS-specific enums
class EnergySupplyType(StrEnum):
    MAINS_ELECTRIC = "mains elec"
    MAINS_GAS = "mains gas"


class HeatingControlType(StrEnum):
    SEPARATE_TIME_AND_TEMP_CONTROL = "SeparateTimeAndTempControl"
    SEPARATE_TEMP_CONTROL = "SeparateTempControl"


class SpaceHeatControlType(StrEnum):
    LIVINGROOM = "livingroom"
    RESTOFDWELLING = "restofdwelling"


class BuildType(StrEnum):
    HOUSE = "house"
    FLAT = "flat"


class CombustionAirSupplySituation(StrEnum):
    ROOM_AIR = "room_air"
    OUTSIDE = "outside"


class CombustionApplianceType(StrEnum):
    OPEN_FIREPLACE = "open_fireplace"
    CLOSED_WITH_FAN = "closed_with_fan"
    OPEN_GAS_FLUE_BALANCER = "open_gas_flue_balancer"
    OPEN_GAS_KITCHEN_STOVE = "open_gas_kitchen_stove"
    OPEN_GAS_FIRE = "open_gas_fire"
    CLOSED_FIRE = "closed_fire"


class CombustionFuelType(StrEnum):
    WOOD = "wood"
    GAS = "gas"
    OIL = "oil"
    COAL = "coal"


class FlueGasExhaustSituation(StrEnum):
    INTO_ROOM = "into_room"
    INTO_SEPARATE_DUCT = "into_separate_duct"
    INTO_MECH_VENT = "into_mech_vent"


class WaterHeatingSchedule(StrEnum):
    ALL_DAY = "AllDay"
    HEATING_HOURS = "HeatingHours"
