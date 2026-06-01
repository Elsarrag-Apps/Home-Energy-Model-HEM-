import importlib.metadata
import logging
import math
from typing import Annotated, Literal, Self, Union, get_args, get_origin

import annotated_types
import numpy as np
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeFloat,
    RootModel,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic.fields import FieldInfo
from pydantic_core import InitErrorDetails, PydanticCustomError
from typing_extensions import deprecated

# Import all enums from the new enums module
from hem_core.input_output.enums import (
    AirFlowType,
    BatteryLocation,
    BoilerHotWaterTest,
    BuildingElementType,
    ControlCombinationOperation,
    ControlLogicType,
    DuctShape,
    DuctType,
    EcoDesignControllerClass,
    EdgeInsulationDirection,
    EnergySupplyPriorityEntry,
    FloorType,
    FuelType,
    HeatPumpBackupControlType,
    HeatPumpSinkType,
    HeatPumpSourceType,
    HeatSourceLocation,
    HeatSourceWetType,
    HotWaterHeatSourceType,
    HotWaterSourceType,
    InverterType,
    MassDistributionClass,
    MechVentType,
    MVHRLocation,
    PartyWallCavityType,
    PartyWallLiningType,
    PhotovoltaicVentilationStrategy,
    PipeworkContents,
    ShadingObjectType,
    ShowerType,
    SolarCollectorLoopLocation,
    SupplyAirFlowRateControlType,
    SupplyAirTemperatureControlType,
    TerrainClass,
    TestLetter,
    ThermalBridgingType,
    TimeControlType,
    VentilationShieldClass,
    WaterPipeworkLocation,
    WetEmitterType,
    WindowShadingType,
    WindowTreatmentControl,
    WindowTreatmentType,
    WindShieldLocation,
    WWHRSConfiguration,
    ZoneTemperatureControlBasis,
)
from hem_core.units import calculate_thermal_resistance_of_virtual_layer

logger = logging.getLogger(__name__)

# Custom types
FloatBetween0and1 = Annotated[float, annotated_types.Interval(ge=0, le=1)]

FloatGreaterThan0UpTo1 = Annotated[float, annotated_types.Interval(gt=0, le=1)]

RValue = Annotated[float, annotated_types.Gt(0)]

UValue = Annotated[float, annotated_types.Gt(0)]

# From BR 443: The values under "horizontal" apply to heat flow
# directions +/- 30 degrees from horizontal plane.
PITCH_LIMIT_HORIZ_CEILING = 60.0
PITCH_LIMIT_HORIZ_FLOOR = 120.0


def _validator_unique_list(value: list) -> list:
    """Validates that a list contains only unique items"""
    if len(set(value)) != len(value):
        raise ValueError("List must only contain unique items.")
    return value


UniqueStringList = Annotated[
    list[str],
    Field(json_schema_extra={"uniqueItems": True}),
    AfterValidator(_validator_unique_list),
]
"""An ordered list, containing only unique items."""
# We can't just use set[], because that is un-ordered, and some fields require both order and uniqueness.


# Domain errors
class IncompatibleSystemError(ValueError):
    """Raised when two systems are incompatible."""

    pass


class InputFieldReferenceIntegrityError(ValueError):
    """Raised when a cross-reference was not found."""

    pass


# Common type definitions for reuse
ControlReference = Annotated[
    str,
    Field(
        alias="Control",
        description="References a key in $.Control",
        json_schema_extra={"reference_to": ["$.control", "$.smart_appliance_controls"]},
    ),
]

PitchAngle = Annotated[
    float,
    Field(
        description="Tilt angle of the surface from horizontal, between 0 and 180, where 0 means the external surface is facing up, 90 means the external surface is vertical and 180 means the external surface is facing down (unit: ˚)",
        ge=0,
        le=180,
    ),
]

PitchAnglePV = Annotated[
    float,
    Field(
        description="The tilt angle (inclination) of the PV panel from horizontal, measured upwards facing, 0 to 90 (unit: ˚)",
        ge=0,
        le=90,
    ),
]


RotationalAngleDegrees = Annotated[float, annotated_types.Interval(ge=0, le=360)]
"""(unit: °)"""

Orientation360 = Annotated[
    RotationalAngleDegrees,
    Field(
        description="The orientation angle of the inclined surface, expressed as the geographical azimuth angle of the horizontal projection of the inclined surface normal, 0 to 360 (unit: ˚)",
    ),
]

HoursDuration24 = Annotated[
    float,
    Field(gt=0, le=24, description="Duration in hours (must be within 24-hour period)"),
]

DegreesCelsius = Annotated[
    float,
    Field(
        description="Temperature measurement in degrees Celsius (unit: ˚C)",
        ge=-273.15,  # Absolute zero
    ),
]

RunningWaterTemperature = Annotated[
    float,
    Field(
        description="Running water temperature 0-100 (unit: ˚C)",
        ge=0,
        le=100,
    ),
]

EnergySupplyReference = Annotated[
    str,
    Field(
        alias="EnergySupply",
        description="References a key (e.g., 'mains elec', 'mains gas') in $.EnergySupply",
        json_schema_extra={"reference_to": "$.energy_supply"},
    ),
]

ColdWaterSourceReference = Annotated[
    str,
    Field(
        alias="ColdWaterSource",
        description='References a key (e.g., "mains water") in $.ColdWaterSource',
        json_schema_extra={
            "reference_to": [
                "$.cold_water_source",
                "$.pre_heated_water_source",
                "$.waste_water_heat_recovery_systems",
            ]
        },
    ),
]

HotWaterSourceReference = Annotated[
    str,
    Field(
        alias="HotWaterSource",
        description='References a key (e.g., "hw cylinder") in $.HotWaterSource',
        json_schema_extra={"reference_to": "$.hot_water_source"},
    ),
]

HeatSourceWetReference = Annotated[
    str,
    Field(
        alias="HeatSourceWet",
        description="References a key (e.g., 'boiler', 'hp', 'HeatNetwork', 'hb1') in $.HeatSourceWet",
        json_schema_extra={"reference_to": "$.heat_source_wet"},
    ),
]

HeatSourceReference = Annotated[
    str,
    Field(
        alias="HeatSource",
        description="References a key (e.g., 'immersion') in $.HotWaterSource.HeatSource",
    ),
]

ZoneReference = Annotated[
    str,
    Field(
        alias="Zone",
        description="References a key in $.Zone",
        json_schema_extra={"reference_to": "$.zone"},
    ),
]


class StrictBaseModel(BaseModel):
    """Base model class that forbids extra fields by default."""

    model_config = ConfigDict(extra="forbid")


class TimeSeriesBase(StrictBaseModel):
    """Base class containing common fields for all time series data"""

    start_day: Annotated[
        int,
        Field(description="First day of the time series, day of the year, 0 to 365", ge=0, le=365),
    ]
    time_series_step: HoursDuration24


class Metadata(StrictBaseModel):
    model_config = ConfigDict(extra="allow")
    hem_core_version: str | None = None

    @field_validator("hem_core_version", mode="after")
    @classmethod
    def validate_hem_core_version(cls, value: str | None):
        """Validate metadata version against engine version"""
        if not value:
            return value
        engine_version = importlib.metadata.version("hem-core")
        if value != engine_version:
            logger.warning(
                f"Core engine version ({engine_version}) does not match target version ({value}) suggested by metadata section of input file."
            )

        return value


class AirTerminalDevice(StrictBaseModel):
    area_cm2: Annotated[
        float,
        Field(
            description="Equivalent area of the air terminal device (unit: cm2)", gt=0, title="Area"
        ),
    ]
    pressure_difference_ref: Annotated[
        float,
        Field(
            description="Reference pressure difference for an air terminal device (unit: Pa)", gt=0
        ),
    ]


class ApplianceGainsEvent(StrictBaseModel):
    demand_w: Annotated[
        float,
        Field(
            alias="demand_W",
            title="Demand",
            description="Electrical power consumption during the appliance event (unit: W)",
            gt=0,
        ),
    ]
    duration: Annotated[
        float, Field(description="Duration of the appliance event (unit: hours)", gt=0)
    ]
    start: Annotated[
        float,
        Field(
            description="Hours from start of simulation to when the appliance event begins (unit: hours)",
            ge=0,
        ),
    ]


class ApplianceLoadShifting(StrictBaseModel):
    control: Annotated[ControlReference | None, Field(alias="Control")] = None
    demand_limit_weighted: Annotated[
        float,
        Field(
            ge=0,
            description=(
                "Value above which the sum demand multiplied by the "
                "weight should not exceed. If a 7hr tariff were used for "
                "the weight timeseries, then this would be a cost. If this value "
                "is 0, then all events will be shifted to the optimal time "
                "within the window, otherwise they will be shifted to the earliest "
                "time at which the weighted demand goes below the limit. "
                "(if there is no time in the window when the weighted demand is below"
                "the limit, then the optimum is chosen.)"
            ),
        ),
    ]
    max_shift_hrs: Annotated[
        float,
        Field(
            description="Maximum time that an event may be shifted away from when it was originally intended to occur. This may be up to 24 hours. (unit: hours)",
            ge=0,
            le=24,
        ),
    ]
    priority: int | None = None
    weight_timeseries: Annotated[
        list[float],
        Field(
            description=(
                "This may be, for example, the hourly cost per "
                "kWh of a 7hr tariff, but could be any time series. "
                "The sum of the other demand and the demand of the "
                "appliance in question at any given time is multiplied "
                "by the value of this timeseries to obtain a figure "
                "that is used to determine whether to shift an event, "
                "and when would be the most appropriate time to shift "
                "the event to."
            )
        ),
    ]


class ColdWaterSource(TimeSeriesBase):
    temperatures: Annotated[
        list[RunningWaterTemperature],
        Field(description="List of cold water temperatures, one entry per hour (unit: ˚C)"),
    ]


class EdgeInsulationHorizontal(StrictBaseModel):
    type: Literal[EdgeInsulationDirection.HORIZONTAL]
    edge_thermal_resistance: Annotated[
        RValue,
        Field(description="Thermal resistance of floor edge insulation (unit: m²K/W)"),
    ]
    width: Annotated[float, Field(gt=0, description="(unit: m)")]


class EdgeInsulationVertical(StrictBaseModel):
    type: Literal[EdgeInsulationDirection.VERTICAL]
    edge_thermal_resistance: Annotated[
        RValue,
        Field(description="Thermal resistance of floor edge insulation (unit: m²K/W)"),
    ]
    depth: Annotated[float, Field(gt=0, description="(unit: m)")]


EdgeInsulation = Annotated[
    EdgeInsulationHorizontal | EdgeInsulationVertical,
    Field(discriminator="type"),
]


class ElectricBattery(StrictBaseModel):
    battery_age: Annotated[
        float, Field(description="The starting age of the battery (in years)", ge=0)
    ]
    battery_location: Annotated[
        BatteryLocation, Field(description="The location of the battery (inside/outside)")
    ]
    capacity: Annotated[
        float, Field(description="The maximum capacity of the battery (unit: kWh)", gt=0)
    ]
    charge_discharge_efficiency_round_trip: Annotated[
        FloatGreaterThan0UpTo1,
        Field(
            description="Charge/discharge round trip efficiency of battery system (greater than 0, up to 1)",
        ),
    ]
    grid_charging_possible: Annotated[
        bool, Field(description="Is charging from the grid possible?")
    ]
    maximum_charge_rate_one_way_trip: Annotated[
        float,
        Field(
            description="The maximum charge rate one way trip the battery allows (unit: kW)", gt=0
        ),
    ]
    maximum_discharge_rate_one_way_trip: Annotated[
        float,
        Field(
            description="The maximum discharge rate one way trip the battery allows (unit: kW)",
            gt=0,
        ),
    ]
    minimum_charge_rate_one_way_trip: Annotated[
        float,
        Field(
            description="The minimum charge rate one way trip the battery allows (unit: kW)", ge=0
        ),
    ]


class ExternalSensorCorrelation(StrictBaseModel):
    temperature: Annotated[
        DegreesCelsius,
        Field(
            description="External temperature data point for the corresponding maximum charge level (unit: Celsius)"
        ),
    ]
    max_charge: Annotated[
        FloatBetween0and1,
        Field(
            description="Maximum charge level permitted by the control for a given external temperature"
        ),
    ]


class FanSpeedData(StrictBaseModel):
    power_output: Annotated[
        list[NonNegativeFloat],
        Field(description="Heat output for a specific test temperature difference (unit: kW)"),
    ]
    temperature_diff: Annotated[
        float,
        Field(
            gt=0,
            description="Difference in temperature between the hot water supplied to the fan coil and the air in the room (unit: Kelvin)",
        ),
    ]


class FancoilTestData(StrictBaseModel):
    fan_power_w: Annotated[
        list[Annotated[float, Field(gt=0)]],
        Field(
            alias="fan_power_W",
            title="Fan Power",
            description="A list of fan powers for which heat output data is provided (unit: W)",
        ),
    ]
    fan_speed_data: list[FanSpeedData]

    @model_validator(mode="after")
    def validate_lists_length(self):
        # Create a list to hold rows of the new array
        rows = []

        # Add fan speed data rows
        for entry in self.fan_speed_data:
            row = [speed for speed in entry.power_output]
            rows.append(row)

        # Check all the fan speed lists are of the same length
        lists_length = all(len(i) == len(rows[0]) for i in rows)
        if not lists_length:
            raise ValueError("Fan speed lists of fancoil manufacturer data differ in length")

        # Check if the length of fan power matches the number of power outputs
        if len(self.fan_power_w) != len(rows[0]):
            raise ValueError("Fan power data length does not match the length of fan speed data")

        return self


class HeatPumpBufferTank(StrictBaseModel):
    daily_losses: Annotated[
        float,
        Field(description="Standing heat loss (unit: kWh/day)", gt=0),
    ]
    pump_fixed_flow_rate: Annotated[
        float,
        Field(description="Flow rate of the buffer tank - emitters loop (unit: l/min)", gt=0),
    ]
    pump_power_at_flow_rate: Annotated[
        float,
        Field(description="Pump power of the buffer tank - emitters loop (unit: kW)", gt=0),
    ]
    volume: Annotated[
        float,
        Field(description="Volume of the buffer tank (unit: litre)", gt=0),
    ]


class HeatPumpHotWaterOnlyTestDatum(StrictBaseModel):
    cop_dhw: Annotated[
        float,
        Field(description="CoP measured during EN 16147 test", gt=0, title="CoP DHW"),
    ]
    energy_input_measured: Annotated[
        float,
        Field(
            description="Electrical input energy measured in EN 16147 test over 24 hrs (unit: kWh)",
            gt=0,
        ),
    ]
    hw_tapping_prof_daily_total: Annotated[
        float,
        Field(
            description="Daily energy requirement for tapping profile used for test (unit: kWh/day)",
            gt=0,
            title="Hot Water Tapping Profile Daily Total",
        ),
    ]
    hw_vessel_loss_daily: Annotated[
        float,
        Field(
            description="Daily hot water vessel heat loss "
            "for a 45 K temperature difference between vessel "
            "and surroundings, tested in accordance with BS 1566 or "
            "EN 12897 or any equivalent standard. Vessel must be same "
            "as that used during EN 16147 test (unit: kWh/day)",
            gt=0,
            title="Hot Water Vessel Loss Daily",
        ),
    ]
    power_standby: Annotated[
        float,
        Field(description="Standby power measured in EN 16147 test (unit: kW)", gt=0),
    ]


class HeatPumpHotWaterTestData(StrictBaseModel):
    l: Annotated[HeatPumpHotWaterOnlyTestDatum | None, Field(alias="L")] = None  # noqa: E741  # Ambiguous variable name: `l`
    m: Annotated[HeatPumpHotWaterOnlyTestDatum, Field(alias="M")]


class BoilerBase(StrictBaseModel):
    """Base class containing common boiler properties"""

    energy_supply: EnergySupplyReference
    energy_supply_aux: Annotated[
        EnergySupplyReference,
        Field(
            alias="EnergySupply_aux",
            description="References a key in $.EnergySupply for auxiliary electrical power",
        ),
    ]
    boiler_location: Annotated[
        HeatSourceLocation,
        Field(description="Location of the boiler (internal or external to the building)"),
    ]
    efficiency_full_load: Annotated[
        FloatGreaterThan0UpTo1,
        Field(description="Boiler net efficiency at full load (dimensionless, 0-1)"),
    ]
    efficiency_part_load: Annotated[
        float,
        Field(
            description="Boiler net efficiency at part load (dimensionless, 0-1.12). Net efficiencies may exceed 1 in test data.",
            gt=0,
            le=1.12,
        ),
    ]
    electricity_circ_pump: Annotated[
        float,
        Field(description="Electrical power consumption of circulation pump (unit: kW)", ge=0),
    ]
    electricity_full_load: Annotated[
        float, Field(description="Electrical power consumption at full load (unit: kW)", ge=0)
    ]
    electricity_part_load: Annotated[
        float, Field(description="Electrical power consumption at part load (unit: kW)", ge=0)
    ]
    electricity_standby: Annotated[
        float, Field(description="Electrical power consumption in standby mode (unit: kW)", ge=0)
    ]
    modulation_load: Annotated[
        FloatBetween0and1,
        Field(
            alias="modulation_load",
            description="Modulation load ratio (dimensionless, 0-1)",
        ),
    ]
    rated_power: Annotated[
        float, Field(description="Rated power output of the boiler (unit: kW)", gt=0)
    ]


class HeatSourceWetBoiler(BoilerBase):
    """Standalone boiler heat source"""

    type: Literal[HeatSourceWetType.BOILER]


class HeatSourceWetHeatBatteryPCM(StrictBaseModel):
    """PCM (Phase Change Material) Heat Battery"""

    type: Literal[HeatSourceWetType.HEAT_BATTERY]
    battery_type: Literal["pcm"]
    a: Annotated[float, Field(alias="A", description="Heat battery parameter A (dimensionless)")]
    b: Annotated[float, Field(alias="B", description="Heat battery parameter B (dimensionless)")]
    control_charge: Annotated[ControlReference, Field(alias="ControlCharge")]
    energy_supply: EnergySupplyReference
    inlet_diameter_mm: Annotated[
        float,
        Field(
            description="Inlet diameter of capillary tubes (unit: mm)", gt=0, title="Inlet Diameter"
        ),
    ]
    electricity_circ_pump: Annotated[
        float,
        Field(description="Electrical power consumption of circulation pump (unit: kW)", ge=0),
    ]
    electricity_standby: Annotated[
        float, Field(description="Electrical power consumption in standby mode (unit: kW)", gt=0)
    ]
    flow_rate_l_per_min: Annotated[
        float,
        Field(
            description="Flow rate through the heat battery (unit: litre/minute)",
            gt=0,
            title="Flow Rate",
        ),
    ]
    heat_storage_k_j_per_k_above_phase_transition: Annotated[
        float,
        Field(
            alias="heat_storage_kJ_per_K_above_Phase_transition",
            title="Heat Storage kJ Per K Above Phase Transition",
            description="Heat capacity of storage above phase transition (unit: kJ/K)",
            gt=0,
        ),
    ]
    heat_storage_k_j_per_k_below_phase_transition: Annotated[
        float,
        Field(
            alias="heat_storage_kJ_per_K_below_Phase_transition",
            title="Heat Storage kJ Per K Below Phase Transition",
            description="Heat capacity of storage below phase transition (unit: kJ/K)",
            gt=0,
        ),
    ]
    heat_storage_k_j_per_k_during_phase_transition: Annotated[
        float,
        Field(
            alias="heat_storage_kJ_per_K_during_Phase_transition",
            title="Heat Storage kJ Per K During Phase Transition",
            description="Heat capacity of storage during phase transition (unit: kJ/K)",
            gt=0,
        ),
    ]
    max_rated_losses: Annotated[
        float, Field(description="Maximum rated heat losses (unit: kW)", gt=0)
    ]
    max_temperature: Annotated[
        DegreesCelsius, Field(description="Maximum operating temperature (unit: ˚C)")
    ]
    number_of_units: Annotated[
        int, Field(alias="number_of_units", description="Number of heat battery units", ge=1)
    ]
    phase_transition_temperature_upper: Annotated[
        DegreesCelsius, Field(description="Upper temperature limit for phase transition (unit: ˚C)")
    ]
    phase_transition_temperature_lower: Annotated[
        DegreesCelsius, Field(description="Lower temperature limit for phase transition (unit: ˚C)")
    ]
    rated_charge_power: Annotated[float, Field(description="Rated charging power (unit: kW)", gt=0)]
    simultaneous_charging_and_discharging: Annotated[
        bool, Field(description="Whether the heat battery can charge and discharge simultaneously")
    ]
    velocity_in_hex_tube_at_1_l_per_min_m_per_s: Annotated[
        float,
        Field(
            alias="velocity_in_HEX_tube_at_1_l_per_min_m_per_s",
            title="Velocity In Hex Tube At 1 Litre/Minute",
            description="Velocity in heat exchanger tube at 1 litre/minute flow rate (unit: m/s)",
            gt=0,
        ),
    ]
    temp_init: Annotated[
        DegreesCelsius,
        Field(
            description="Initial temperature of the PCM heat battery at the start of simulation (unit: ˚C)"
        ),
    ]


class HeatSourceWetHeatBatteryDryCore(StrictBaseModel):
    """Dry Core Heat Battery"""

    type: Literal["HeatBattery"]
    battery_type: Literal["dry_core"]
    control_charge: Annotated[str, Field(alias="ControlCharge")]
    energy_supply: Annotated[str, Field(alias="EnergySupply")]
    electricity_circ_pump: float
    electricity_standby: float
    pwr_in: Annotated[float, Field(description="Charging power (kW)")]
    state_of_charge_init: Annotated[
        float,
        Field(
            description="State of charge at initialisation of dry core heat storage (ratio)",
            ge=0.0,
            le=1.0,
        ),
    ]
    rated_power_instant: Annotated[
        float, Field(description="Rated instantaneous power output (kW)")
    ]
    heat_storage_capacity: Annotated[float, Field(description="Heat storage capacity (kWh)")]
    number_of_units: Annotated[int, Field(ge=1)]
    dry_core_min_output: Annotated[
        list[Annotated[list[float], Field(max_length=2, min_length=2)]],
        Field(description="Lookup table for minimum output based on charge level"),
    ]
    dry_core_max_output: Annotated[
        list[Annotated[list[float], Field(max_length=2, min_length=2)]],
        Field(description="Lookup table for maximum output based on charge level"),
    ]
    fan_pwr: Annotated[float, Field(description="Fan power (W)")]


# Discriminated union for HeatSourceWetHeatBattery
HeatSourceWetHeatBattery = Annotated[
    HeatSourceWetHeatBatteryPCM | HeatSourceWetHeatBatteryDryCore,
    Field(discriminator="battery_type"),
]


class HeatSourceWetHIU(StrictBaseModel):
    type: Literal[HeatSourceWetType.HIU]
    energy_supply: EnergySupplyReference
    hiu_daily_loss: Annotated[
        float,
        Field(
            alias="HIU_daily_loss",
            title="HIU Daily Loss",
            description="Daily heat losses from the HIU (unit: kWh/day)",
            gt=0,
        ),
    ]
    building_level_distribution_losses: Annotated[
        float,
        Field(description="Heat losses from building-level distribution pipework (unit: W)", ge=0),
    ]
    power_max: Annotated[
        float, Field(description="Maximum power output of the HIU (unit: kW)", gt=0)
    ]
    power_circ_pump: Annotated[
        float | None,
        Field(description="Power consumption of heating circulation pump (unit: kW)", ge=0),
    ] = None
    power_aux: Annotated[
        float | None,
        Field(description="Power consumption of auxiliary electrical usage (unit: kW)", gt=0),
    ] = None


class HotWaterSourceCombiBoiler(StrictBaseModel):
    type: Literal[HotWaterSourceType.COMBI_BOILER]
    cold_water_source: ColdWaterSourceReference
    heat_source_wet: HeatSourceWetReference
    daily_hw_usage: Annotated[
        float,
        Field(
            alias="daily_HW_usage",
            title="Daily Hot Water Usage",
            description="Daily hot water usage for the combi boiler system (unit: litre/day)",
            gt=0,
        ),
    ]
    rejected_energy_1: Annotated[
        float | None,
        Field(
            description="Rejected energy factor 1 for combi boiler efficiency calculations (unit: kWh)",
            ge=0,
        ),
    ] = None
    rejected_factor_3: Annotated[
        float | None,
        Field(
            description="Rejected energy factor 3 for combi boiler efficiency calculations (dimensionless)",
        ),
    ] = None
    separate_dhw_tests: Annotated[
        BoilerHotWaterTest,
        Field(
            alias="separate_DHW_tests",
            description="Type of separate domestic hot water test performed on the combi boiler (M&L, M&S, M_only, or No_additional_tests)",
        ),
    ]
    setpoint_temp: Annotated[
        RunningWaterTemperature,
        Field(description="Temperature setpoint for the combi boiler hot water output (unit: ˚C)"),
    ]
    storage_loss_factor_2: Annotated[
        float | None,
        Field(
            description="Storage loss factor 2 for combi boiler efficiency calculations (unit: kWh/day)",
            ge=0,
        ),
    ] = None
    storage_loss_factor_1: Annotated[
        float | None,
        Field(
            description="Storage loss factor 1 for combi boiler efficiency calculations (unit: kWh/day)",
            ge=0,
        ),
    ] = None

    @model_validator(mode="after")
    def validate_dhw_tests_inputs(self):
        # check test data provided matches the DHW tests carried out
        if self.separate_dhw_tests == "M&L" or self.separate_dhw_tests == "M&S":
            if (
                self.rejected_energy_1 is None
                or self.rejected_factor_3 is None
                or self.storage_loss_factor_2 is None
            ):
                raise ValueError(
                    "Loss factors r1, F2, and F3 are required when a combi boiler is tested to two profiles."
                )
            elif self.storage_loss_factor_1 is not None:
                raise ValueError(
                    "storage_loss_factor_1 invalid input for combis tested to two profiles."
                )

        elif (
            self.separate_dhw_tests == "M_only" or self.separate_dhw_tests == "No_additional_tests"
        ):
            if self.rejected_energy_1 is None or self.storage_loss_factor_1 is None:
                raise ValueError(
                    "Loss factors r1, and F1, are required when a combi boiler is tested to profile M, or not tested."
                )
            elif self.storage_loss_factor_2 is not None:
                raise ValueError(
                    "storage_loss_factor_2 invalid input for combis tested to one profile, or not tested."
                )
            elif self.rejected_factor_3 is not None:
                raise ValueError(
                    "rejected_factor_3 invalid input for combis tested to one profile, or not tested."
                )

        return self


class HotWaterSourceHUI(StrictBaseModel):
    type: Literal[HotWaterSourceType.HIU]
    cold_water_source: ColdWaterSourceReference
    heat_source_wet: HeatSourceWetReference
    setpoint_temp: Annotated[
        RunningWaterTemperature | None,
        Field(description="Temperature setpoint for the HIU hot water output (unit: ˚C)"),
    ] = None


class HotWaterSourcePointOfUse(StrictBaseModel):
    type: Literal[HotWaterSourceType.POINT_OF_USE]
    cold_water_source: ColdWaterSourceReference
    energy_supply: EnergySupplyReference
    efficiency: Annotated[
        FloatGreaterThan0UpTo1 | None,
        Field(
            description="Thermal efficiency of the point-of-use water heater (dimensionless, 0-1)",
        ),
    ]
    setpoint_temp: Annotated[
        RunningWaterTemperature,
        Field(
            description="Temperature setpoint for the point-of-use water heater output (unit: ˚C)"
        ),
    ]


class HotWaterSourceHeatBattery(StrictBaseModel):
    type: Literal[HotWaterSourceType.HEAT_BATTERY]
    cold_water_source: ColdWaterSourceReference
    heat_source_wet: HeatSourceWetReference
    setpoint_temp: Annotated[
        RunningWaterTemperature,
        Field(description="Temperature setpoint for the heat battery hot water output (unit: ˚C)"),
    ]


class MechanicalVentilationDuctwork(StrictBaseModel):
    cross_section_shape: Annotated[
        DuctShape,
        Field(description="Whether the cross-section of duct is circular or rectangular (square)"),
    ]
    duct_perimeter_mm: Annotated[
        float | None,
        Field(
            gt=0,
            description="Cross-sectional perimeter length of rectangular ductwork (unit: mm)",
            title="Duct Perimeter",
        ),
    ] = None
    duct_type: DuctType
    external_diameter_mm: Annotated[
        float | None, Field(gt=0, description="(unit: mm)", title="External Diameter")
    ] = None
    insulation_thermal_conductivity: Annotated[
        UValue, Field(description="Thermal conductivity of the insulation (unit: W / m K)")
    ]
    insulation_thickness_mm: Annotated[
        float, Field(ge=0, description="(unit: mm)", title="Insulation Thickness")
    ]
    internal_diameter_mm: Annotated[
        float | None, Field(gt=0, description="(unit: mm)", title="Internal Diameter")
    ] = None
    length: Annotated[float, Field(gt=0, description="(unit: m)")]
    reflective: bool


class OtherWaterUse(StrictBaseModel):
    cold_water_source: ColdWaterSourceReference
    hot_water_source: Annotated[
        HotWaterSourceReference | None,
        Field(
            alias="HotWaterSource",
            description="Reference to HotWaterSource object that provides hot water to this tapping point. If only one HotWaterSource is defined, then this will be assumed by default",
        ),
    ] = None
    flowrate: Annotated[float, Field(description="Tap/outlet flow rate (unit: litre/minute)", gt=0)]


class ScheduleRepeaterEntryForBoolean(RootModel[bool | None]):
    root: bool | None


class ScheduleRepeaterEntryForDouble(RootModel[float | None]):
    root: float | None


class ScheduleRepeaterValueForBoolean(RootModel[str | ScheduleRepeaterEntryForBoolean]):
    root: str | ScheduleRepeaterEntryForBoolean


class ScheduleRepeaterValueForDouble(RootModel[str | ScheduleRepeaterEntryForDouble]):
    root: str | ScheduleRepeaterEntryForDouble


class ScheduleRepeaterForBoolean(StrictBaseModel):
    """
    Defines a repeating pattern for boolean schedule values.

    Examples:
        # Repeat 'true' 24 times (once per hour)
        {"repeat": 24, "value": true}

        # Reference another schedule, repeat 7 times (once per day)
        {"repeat": 7, "value": "weekday_schedule"}
    """

    repeat: Annotated[int, Field(ge=1, description="Number of times to repeat the value")]
    value: Annotated[
        ScheduleRepeaterValueForBoolean, Field(description="Value to repeat or schedule reference")
    ]


class ScheduleRepeaterForDouble(StrictBaseModel):
    """
    Defines a repeating pattern for double (float) schedule values.

    Examples:
        # Repeat temperature setpoint 21.5°C 24 times (once per hour)
        {"repeat": 24, "value": 21.5}

        # Reference another schedule, repeat 7 times (once per day)
        {"repeat": 7, "value": "weekday_temp_schedule"}

        # Repeat power level 2.5 kW for 8 hours
        {"repeat": 8, "value": 2.5}
    """

    repeat: Annotated[int, Field(ge=1, description="Number of times to repeat the value")]
    value: Annotated[
        ScheduleRepeaterValueForDouble, Field(description="Value to repeat or schedule reference")
    ]


class ShowerMixer(StrictBaseModel):
    type: Literal[ShowerType.MIXER_SHOWER]
    cold_water_source: ColdWaterSourceReference
    hot_water_source: Annotated[
        HotWaterSourceReference | None,
        Field(
            alias="HotWaterSource",
            description="Reference to HotWaterSource object that provides hot water to this shower. If only one HotWaterSource is defined, then this will be assumed by default",
        ),
    ] = None
    waste_water_heat_recovery_system: Annotated[
        str | None,
        Field(
            alias="WWHRS",
            title="WWHRS",
            description="Reference to a key in Input.WWHRS",
        ),
    ] = None
    wwhrs_configuration: Annotated[
        WWHRSConfiguration | None,
        Field(
            alias="WWHRS_configuration",
            title="WWHRS configuration",
            description="WWHRS system configuration for this shower connection",
        ),
    ] = None
    flowrate: Annotated[float, Field(description="Shower flow rate (unit: litre/minute)", gt=0)]

    @model_validator(mode="after")
    def validate_wwhrs_configuration(self) -> Self:
        """Validate that WWHRS_configuration is provided when WWHRS is specified."""
        if self.waste_water_heat_recovery_system is not None and self.wwhrs_configuration is None:
            # Default to System A if not specified (matching the shower.py implementation)
            self.wwhrs_configuration = WWHRSConfiguration.SHOWER_AND_WATER_HEATING_SYSTEM
        if self.waste_water_heat_recovery_system is None and self.wwhrs_configuration is not None:
            raise ValueError(
                "WWHRS_configuration should not be specified when WWHRS is not provided"
            )
        return self


class ShowerInstantElectric(StrictBaseModel):
    type: Literal[ShowerType.INSTANT_ELECTRIC_SHOWER]
    cold_water_source: ColdWaterSourceReference
    energy_supply: EnergySupplyReference
    rated_power: Annotated[
        float, Field(description="Shower's rated electrical power (unit: kW)", gt=0)
    ]


Shower = Annotated[
    ShowerMixer | ShowerInstantElectric,
    Field(discriminator="type"),
]


class SimulationTime(StrictBaseModel):
    start: Annotated[
        float,
        Field(
            description="The start time of the simulation, in hours from the start of the year",
            ge=0,
        ),
    ]
    end: Annotated[
        float,
        Field(
            description="The end time of the simulation, in hours from the start of the year", gt=0
        ),
    ]
    step: Annotated[
        float,
        Field(description="The time increment for each step of the calculation, in hours", gt=0),
    ]


class SmartApplianceBattery(StrictBaseModel):
    battery_state_of_charge: Annotated[
        dict[EnergySupplyReference, Annotated[list[FloatBetween0and1], Field(min_length=1)]],
        Field(
            description="Dictionary of lists containing the battery state of charge for each timestep for each energy supply",
            min_length=1,
        ),
    ]
    energy_into_battery_from_generation: Annotated[
        dict[EnergySupplyReference, Annotated[list[float], Field(min_length=1)]],
        Field(
            description="Dictionary of lists containing energy sent to the battery from generation for each timestep for each energy supply (unit: kWh)",
            min_length=1,
        ),
    ]
    energy_into_battery_from_grid: Annotated[
        dict[EnergySupplyReference, Annotated[list[float], Field(min_length=1)]],
        Field(
            description="Dictionary of lists containing energy sent to the battery from the grid for each timestep for each energy supply (unit: kWh)",
            min_length=1,
        ),
    ]
    energy_out_of_battery: Annotated[
        dict[EnergySupplyReference, Annotated[list[float], Field(min_length=1)]],
        Field(
            description="Dictionary of lists containing energy drawn from the battery for each timestep for each energy supply (unit: kWh)",
            min_length=1,
        ),
    ]


class SmartApplianceControl(StrictBaseModel):
    appliances: Annotated[
        list[str],
        Field(
            alias="Appliances",
            description="List of names of all appliance objects in the simulation",
        ),
    ]
    battery24hr: SmartApplianceBattery
    non_appliance_demand_24hr: Annotated[
        dict[EnergySupplyReference, Annotated[list[float], Field(min_length=1)]],
        Field(
            description="Dictionary of lists containing demand per end user for each timestep for each energy supply (unit: W)"
        ),
    ]
    power_timeseries: Annotated[
        dict[EnergySupplyReference, Annotated[list[float], Field(min_length=1)]],
        Field(
            description="Dictionary of lists containing expected power for appliances for each energy supply, for the entire length of the simulation (unit: W)",
            min_length=1,
        ),
    ]
    time_series_step: Annotated[
        float, Field(description="Timestep of the power time series (unit: hours)")
    ]


class SpaceHeatSystemHeatSource(StrictBaseModel):
    name: str
    temp_flow_limit_upper: Annotated[
        float | None,
        Field(description="Upper operating limit for temperature (unit: deg C)", gt=0),
    ] = None


class ThermalBridgingLinear(StrictBaseModel):
    type: Literal[ThermalBridgingType.LINEAR]
    length: Annotated[
        float,
        Field(
            description="Length of the thermal bridge over which the linear thermal transmittance applies. (Unit: m)",
            gt=0,
        ),
    ]
    linear_thermal_transmittance: Annotated[
        float,
        Field(
            description="Linear thermal transmittance of the thermal bridge. (Unit: W/m.K)",
        ),
        # This can be positive or negative.
    ]


class ThermalBridgingPoint(StrictBaseModel):
    type: Literal[ThermalBridgingType.POINT]
    heat_transfer_coeff: Annotated[
        float,
        Field(description="Heat transfer coefficient of the thermal bridge. (Unit: W/K)"),
        # This can be positive or negative. SAP 2012, Appendix K has negative point thermal bridges.
    ]


ThermalBridging = Annotated[
    ThermalBridgingLinear | ThermalBridgingPoint,
    Field(discriminator="type"),
]


class Vent(StrictBaseModel):
    area_cm2: Annotated[
        float, Field(description="Equivalent area of a vent (unit: cm2)", gt=0, title="Area")
    ]
    mid_height_air_flow_path: Annotated[
        float,
        Field(
            description="Mid height of air flow path relative to ventilation zone (unit: m)", gt=0
        ),
    ]
    orientation360: Orientation360
    pitch: PitchAngle
    pressure_difference_ref: Annotated[
        float,
        Field(description="Reference pressure difference for a vent (unit: Pa)", gt=0),
    ]


class VentilationLeaks(StrictBaseModel):
    env_area: Annotated[
        float, Field(description="Reference area of the envelope airtightness index", gt=0)
    ]
    test_pressure: Annotated[
        float, Field(description="Reference pressure difference (unit: Pa)", gt=0)
    ]
    test_result: Annotated[float, Field(description="Flow rate through (unit: m³/h.m²)", gt=0)]
    ventilation_zone_height: Annotated[
        float, Field(description="Height of ventilation zone (unit: m)", gt=0)
    ]


class WaterHeatingEvent(StrictBaseModel):
    duration: Annotated[
        float | None, Field(description="Duration of the water heating event (unit: minutes)", gt=0)
    ] = None
    start: Annotated[
        float,
        Field(
            description="Hours from start of simulation to when the water heating event begins (unit: hours)",
            ge=0,
        ),
    ]
    temperature: Annotated[
        RunningWaterTemperature,
        Field(description="Target temperature for the water heating event (unit: ˚C)"),
    ]
    volume: Annotated[
        float | None, Field(description="Volume of water for the event (unit: litre)", gt=0)
    ] = None


class WaterHeatingEvents(StrictBaseModel):
    # Restrict top-level keys to only these predefined categories
    shower: Annotated[
        dict[str, list[WaterHeatingEvent]] | None,
        Field(
            alias="Shower",
            description="Dictionary of shower water heating events, where keys are shower names and values are lists of events",
        ),
    ] = None
    bath: Annotated[
        dict[str, list[WaterHeatingEvent]] | None,
        Field(
            alias="Bath",
            description="Dictionary of bath water heating events, where keys are bath names and values are lists of events",
        ),
    ] = None
    other: Annotated[
        dict[str, list[WaterHeatingEvent]] | None,
        Field(
            alias="Other",
            description="Dictionary of other water heating events (e.g., taps, sinks), where keys are event names and values are lists of events",
        ),
    ] = None


class WaterPipework(StrictBaseModel):
    external_diameter_mm: Annotated[
        float, Field(gt=0, description="(unit: mm)", title="External Diameter")
    ]
    insulation_thermal_conductivity: Annotated[
        float, Field(description="Thermal conductivity of the insulation (unit: W / m K)", gt=0)
    ]
    insulation_thickness_mm: Annotated[
        float, Field(ge=0, description="(unit: mm)", title="Insulation Thickness")
    ]
    internal_diameter_mm: Annotated[
        float, Field(gt=0, description="(unit: mm)", title="Internal Diameter")
    ]
    length: Annotated[float, Field(gt=0, description="(unit: m)")]
    location: Annotated[
        WaterPipeworkLocation, Field(description="Location of the pipework (internal or external)")
    ]
    pipe_contents: Annotated[
        PipeworkContents, Field(description="Contents of the pipework (water or glycol25)")
    ]
    surface_reflectivity: bool


class WaterPipeworkSimple(StrictBaseModel):
    # Only the three core fields for the simple pipework class
    internal_diameter_mm: Annotated[
        float, Field(gt=0, description="(unit: mm)", title="Internal Diameter")
    ]
    length: Annotated[float, Field(gt=0, description="(unit: m)")]
    location: WaterPipeworkLocation


class WetEmitterRadiator(StrictBaseModel):
    type: Annotated[Literal[WetEmitterType.RADIATOR], Field(alias="wet_emitter_type")]
    constant: Annotated[
        float | None,
        Field(
            alias="c",
            title="c",
            description="Constant from characteristic equation of emitters (e.g. derived from BS EN 442 tests)",
            gt=0,
        ),
    ] = None
    constant_per_m: Annotated[
        float | None,
        Field(
            alias="c_per_m",
            title="c per m",
            description="Constant from characteristic equation of emitters (e.g. derived from BS EN 442 tests) per the length of the emitter",
            gt=0,
        ),
    ] = None
    thermal_mass: Annotated[
        float | None,
        Field(
            description="Thermal mass of the radiator (unit: kWh/K)",
            gt=0,
        ),
    ] = None
    thermal_mass_per_m: Annotated[
        float | None,
        Field(
            description="Thermal mass per meter length of the radiator (unit: kWh/K/m)",
            gt=0,
        ),
    ] = None
    length: Annotated[
        float | None,
        Field(
            description="The length of the emitter (unit: m)",
            gt=0,
        ),
    ] = None
    frac_convective: Annotated[
        FloatBetween0and1, Field(description="Convective fraction for heating")
    ]
    exponent: Annotated[
        float,
        Field(
            alias="n",
            title="n",
            description="Exponent from characteristic equation of emitters (e.g. derived from BS EN 442 tests)",
            gt=0,
        ),
    ]

    @model_validator(mode="after")
    def validate_required_fields(self):
        # Either c or c_per_m and length should be specified
        if self.constant is None and (self.constant_per_m is None or self.length is None):
            raise ValueError("Must specify either 'c', or 'c_per_m' and 'length'")

        # If thermal_mass_per_m is specified, length must be too
        if self.thermal_mass_per_m is not None and self.length is None:
            raise ValueError("Must specify 'length' when 'thermal_mass_per_m' is provided")

        return self


class WetEmitterUFH(StrictBaseModel):
    type: Annotated[Literal[WetEmitterType.UFH], Field(alias="wet_emitter_type")]
    emitter_floor_area: Annotated[float, Field(gt=0, description="(unit: m²)")]
    equivalent_specific_thermal_mass: Annotated[
        float,
        Field(
            description="Equivalent thermal mass per m² of floor area for under-floor heating systems (unit: kJ/m²K)",
            gt=0,
        ),
    ]
    frac_convective: Annotated[
        FloatBetween0and1, Field(description="Convective fraction for heating")
    ]
    system_performance_factor: Annotated[
        float,
        Field(
            description="Heat output per m² of floor area for under-floor heating systems (unit: W/m²K)",
            gt=0,
        ),
    ]


class WetEmitterFanCoil(StrictBaseModel):
    type: Annotated[Literal[WetEmitterType.FANCOIL], Field(alias="wet_emitter_type")]
    fancoil_test_data: Annotated[
        FancoilTestData, Field(description="Manufacturer's data for fancoil unit")
    ]
    frac_convective: Annotated[
        FloatBetween0and1, Field(description="Convective fraction for heating")
    ]
    n_units: Annotated[
        int | None,
        Field(
            default=1, gt=0, description="Number of units of this specification of fancoil in Zone"
        ),
    ]


WetEmitter = Annotated[
    WetEmitterRadiator | WetEmitterUFH | WetEmitterFanCoil,
    Field(discriminator="type"),
]


class WindowPart(StrictBaseModel):
    mid_height_air_flow_path: Annotated[float, Field(gt=0, description="(unit: m)")]


class WindowShadingObject(StrictBaseModel):
    type: WindowShadingType
    depth: Annotated[float, Field(gt=0, description="(unit: m)")]
    distance: Annotated[float, Field(ge=0, description="(unit: m)")]


class WindowShadingObstacle(StrictBaseModel):
    type: Literal[ShadingObjectType.OBSTACLE]
    height: Annotated[float, Field(gt=0, description="(unit: m)")]
    distance: Annotated[float, Field(ge=0, description="(unit: m)")]
    transparency: FloatBetween0and1


WindowShading = WindowShadingObject | WindowShadingObstacle
# Can't use Field(discriminator="type") because WindowShadingObject.type is an enum.
# Shouldn't need to anyway, the structures are different enough to clearly infer.


class Bath(StrictBaseModel):
    cold_water_source: ColdWaterSourceReference
    hot_water_source: Annotated[
        HotWaterSourceReference | None,
        Field(
            alias="HotWaterSource",
            description="Reference to HotWaterSource object that provides hot water to this bath. If only one HotWaterSource is defined, then this will be assumed by default",
        ),
    ] = None
    flowrate: Annotated[float, Field(description="Tap/outlet flow rate (unit: litre/minute)", gt=0)]
    size: Annotated[float, Field(description="Volume held by bath (unit: litre)", gt=0)]


class BuildingElementCommonBase(StrictBaseModel):
    """Base class for all building elements with minimal common properties"""

    pitch: PitchAngle
    u_value: Annotated[
        UValue | None,
        Field(description="U-value (W/m²·K), must be positive if provided", title="U-Value"),
    ] = None


class BuildingElementCommonBaseNotGround(BuildingElementCommonBase):
    """Base class for non-ground elements that require thermal properties"""

    thermal_resistance_construction: Annotated[
        RValue | None,
        Field(description="Thermal resistance (m².K/W), must be positive if provided"),
    ] = None

    @model_validator(mode="after")
    def validate_thermal_properties(self):
        """At least one of u_value or thermal_resistance_construction must be provided"""
        if self.u_value is None and self.thermal_resistance_construction is None:
            raise ValueError("Must specify either 'thermal_resistance_construction' or 'u_value'")
        return self


class BuildingElementNotTransparent(StrictBaseModel):
    """Mixin for elements that are not transparent (need area and thermal mass)"""

    area: Annotated[
        float,
        Field(gt=0, description="Area of the building element (m²), must be positive"),
    ]
    areal_heat_capacity: Annotated[
        float,
        Field(gt=0, description="Areal heat capacity (J/m².K), must be positive"),
    ]
    mass_distribution_class: MassDistributionClass


class BuildingElementExposedToSolarRadiation(StrictBaseModel):
    """Mixin for elements exposed to solar radiation (need orientation and dimensions)"""

    orientation360: Annotated[
        Orientation360,
        Field(description="Orientation of the building element (degrees from North)"),
    ]
    base_height: Annotated[
        float,
        Field(
            ge=0,
            description="The distance between the ground and the lowest edge of the element (unit: m)",
        ),
    ]
    height: Annotated[
        float,
        Field(gt=0, description="Height of the building element (m), must be positive"),
    ]
    width: Annotated[
        float,
        Field(gt=0, description="Width of the building element (m), must be positive"),
    ]


class WindowTreatment(StrictBaseModel):
    control_closing_irrad: Annotated[
        ControlReference | None,
        Field(
            alias="Control_closing_irrad",
            description="Irradiation level above which the window treatment is assumed to be closed (unit: W/m²). References a key in $.Control.",
        ),
    ] = None
    control_open: Annotated[
        ControlReference | None,
        Field(
            alias="Control_open",
            description="reference to a time control object containing a schedule of booleans describing when a window treatment is open. References a key in $.Control.",
        ),
    ] = None
    control_opening_irrad: Annotated[
        ControlReference | None,
        Field(
            alias="Control_opening_irrad",
            description="Irradiation level below which a window treatment is assumed to be open (unit: W/m²). References a key in $.Control.",
        ),
    ] = None
    controls: WindowTreatmentControl
    delta_r: Annotated[
        float,
        Field(
            description="Additional thermal resistance provided by a window treatment (unit: m²K/W)",
            gt=0,
            title="Delta r",
        ),
    ]
    is_open: Annotated[
        bool | None,
        Field(description="A boolean describing the state of the window treatment"),
    ] = None
    opening_delay_hrs: Annotated[
        float | None,
        Field(
            description="Time delay enforced before a window treatment may be opened after the conditions for its opening are met (unit: hours)",
        ),
    ] = None
    trans_red: Annotated[
        FloatBetween0and1,
        Field(
            description="Dimensionless factor describing the reduction in the amount of transmitted radiation due to a window treatment"
        ),
    ]
    type: WindowTreatmentType


class BuildingElementTransparent(
    BuildingElementCommonBaseNotGround, BuildingElementExposedToSolarRadiation
):
    """Transparent building elements (windows, glazing)"""

    type: Literal[BuildingElementType.TRANSPARENT]
    control_window_openable: Annotated[
        ControlReference | None, Field(alias="Control_WindowOpenable")
    ] = None
    frame_area_fraction: Annotated[
        FloatBetween0and1,
        Field(
            description="The frame area fraction of window, ratio of the projected frame area to the overall projected area of the glazed element of the window"
        ),
    ]
    free_area_height: Annotated[
        float,
        Field(
            ge=0,
            description="Height of the openable area, corrected for obstruction due to the window frame of the openable section (unit: m)",
        ),
    ]
    g_value: Annotated[
        FloatBetween0and1,
        Field(
            description="Total solar energy transmittance of the transparent part of the window",
            title="G-Value",
        ),
    ]
    max_window_open_area: Annotated[
        float,
        Field(
            ge=0,
            description="Openable area of the window ignoring the obstructing effect of the frame of the openable part",
        ),
    ]
    mid_height: Annotated[
        float,
        Field(
            gt=0,
            description="Height of the mid-point of the window, relative to the base of the ventilation zone (unit: m)",
        ),
    ]
    shading: list[WindowShading]
    treatment: list[WindowTreatment] | None = None
    window_part_list: list[WindowPart]

    @model_validator(mode="after")
    def validate_max_window_open_area(self):
        # Area is calculated from height * width for transparent elements
        area = self.height * self.width
        if self.max_window_open_area > area:
            raise ValueError("max_window_open_area must be less than or equal to the area")
        return self


class BuildingElementOpaque(
    BuildingElementCommonBaseNotGround,
    BuildingElementNotTransparent,
    BuildingElementExposedToSolarRadiation,
):
    """Opaque building elements (walls, roofs, etc.)"""

    type: Literal[BuildingElementType.OPAQUE]
    is_unheated_pitched_roof: bool | None = None
    solar_absorption_coeff: Annotated[
        FloatBetween0and1,
        Field(description="Solar absorption coefficient at the external surface (dimensionless)"),
    ]


class BuildingElementAdjacentConditionedSpace(
    BuildingElementCommonBaseNotGround, BuildingElementNotTransparent
):
    """Adjacent conditioned space building elements"""

    type: Literal[BuildingElementType.ADJACENT_CONDITIONED]


class BuildingElementAdjacentUnconditionedSpaceSimple(
    BuildingElementCommonBaseNotGround, BuildingElementNotTransparent
):
    """Adjacent unconditioned space building elements"""

    type: Literal[BuildingElementType.ADJACENT_UNCONDITIONED_SPACE_SIMPLE]
    thermal_resistance_unconditioned_space: Annotated[
        RValue, Field(description="Effective thermal resistance of unheated space (unit: m².K/W)")
    ]


class BuildingElementPartyWall(BuildingElementCommonBaseNotGround, BuildingElementNotTransparent):
    """
    Party wall element for all party wall types, with specific handling for cavity air movement heat loss.

    For cavity party walls, this accounts for non-negligible heat loss due to air movement
    within the cavity, as identified by research. The thermal resistance of the
    unconditioned space (cavity) is derived from the party wall cavity type and lining type.
    Five cavity types are supported:
    solid, unfilled_unsealed, unfilled_sealed, filled_sealed, and defined_resistance.
    Two lining types are supported:
    wet_plaster, and dry_lined
    """

    type: Literal[BuildingElementType.PARTY_WALL]
    pitch: Annotated[
        float,
        Field(
            description="Tilt angle of the surface from horizontal, between 60 and 120 degrees (wall range), where 90 means vertical (unit: °)",
            ge=PITCH_LIMIT_HORIZ_CEILING,
            le=PITCH_LIMIT_HORIZ_FLOOR,
        ),
    ]
    party_wall_cavity_type: Annotated[
        PartyWallCavityType,
        Field(
            description="Type of party wall cavity construction affecting heat loss through air movement"
        ),
    ]
    thermal_resistance_construction: Annotated[
        RValue | None,
        Field(
            description="Thermal resistance of wall construction before the cavity (unit: m².K/W)"
        ),
    ] = None
    thermal_resistance_cavity: Annotated[
        RValue | None,
        Field(
            description="Effective thermal resistance of the party wall cavity (unit: m².K/W). Required only when party_wall_cavity_type is 'defined_resistance'. For other cavity types (solid, unfilled_unsealed, unfilled_sealed, filled_sealed), this is calculated automatically."
        ),
    ] = None
    party_wall_lining_type: Annotated[
        PartyWallLiningType | None,
        Field(
            description="Type of party wall lining. Required only when party_wall_cavity_type is unfilled_unsealed, unfilled_sealed, or filled_sealed"
        ),
    ] = None

    @model_validator(mode="after")
    def validate_thermal_resistance_cavity(self) -> Self:
        """Validate that thermal_resistance_cavity is provided only for defined_resistance type."""
        if self.party_wall_cavity_type == PartyWallCavityType.DEFINED_RESISTANCE:
            if self.thermal_resistance_cavity is None:
                raise ValueError(
                    "thermal_resistance_cavity must be provided when "
                    "party_wall_cavity_type is 'defined_resistance'"
                )
        else:
            if self.thermal_resistance_cavity is not None:
                raise ValueError(
                    "thermal_resistance_cavity should only be provided when "
                    "party_wall_cavity_type is 'defined_resistance'. For other cavity types, "
                    "it is calculated automatically."
                )
        return self

    @model_validator(mode="after")
    def validate_party_wall_lining_type(self) -> Self:
        """Validate that party_wall_lining_type is provided only for unfilled_unsealed, unfilled_sealed, or filled_unsealed types."""
        if (
            self.party_wall_cavity_type == PartyWallCavityType.FILLED_UNSEALED
            or self.party_wall_cavity_type == PartyWallCavityType.UNFILLED_SEALED
            or self.party_wall_cavity_type == PartyWallCavityType.UNFILLED_UNSEALED
        ):
            if self.party_wall_lining_type is None:
                raise ValueError(
                    "party_wall_lining_type must be provided when "
                    "party_wall_cavity_type is unfilled_unsealed, unfilled_sealed, or filled_unsealed."
                )
        else:
            if self.party_wall_lining_type is not None:
                raise ValueError(
                    "party_wall_lining_type should only be provided when "
                    "party_wall_cavity_type is unfilled_unsealed, unfilled_sealed, or filled_unsealed."
                )
        return self


class BuildingElementGroundBase(BuildingElementCommonBase, BuildingElementNotTransparent):
    """Base class for all ground building elements"""

    type: Literal["BuildingElementGround"]

    # Override u_value to make it required for ground elements
    # Using type: ignore comment to suppress pyright warnings about intentional type narrowing
    u_value: Annotated[  # type: ignore[assignment]
        UValue,
        Field(
            description="Steady-state thermal transmittance of floor in accordance with BS EN ISO 13370, including internal surface resistance and the effect of the ground (unit: W/m2.K)",
            title="U-Value",
        ),
    ]

    # Ground-specific thermal properties
    thermal_resistance_floor_construction: Annotated[
        RValue,
        Field(
            description="Total thermal resistance of all layers in the floor construction, excluding surface resistances (unit: m².K/W)",
        ),
    ]

    # Ground-specific geometric properties
    total_area: Annotated[
        float,
        Field(
            description="Total area of the building element across entire dwelling (unit: m²)",
            gt=0,
        ),
    ]
    perimeter: Annotated[
        float,
        Field(
            description="Perimeter of the floor (unit: m)",
            gt=0,
        ),
    ]

    # Junction and wall properties
    psi_wall_floor_junc: Annotated[
        float,
        Field(
            description="Linear thermal transmittance of the junction between the floor and the walls (unit: W/m.K)",
        ),
    ]
    thickness_walls: Annotated[float, Field(description="Thickness of the walls (unit: m)", gt=0)]

    @model_validator(mode="after")
    def validate_u_value_and_thermal_resistance_floor_construction(self):
        """Validate compatibility between u_value and thermal_resistance_floor_construction"""
        calculate_thermal_resistance_of_virtual_layer(
            self.u_value, self.thermal_resistance_floor_construction
        )
        return self


class BuildingElementGroundSlabNoEdgeInsulation(BuildingElementGroundBase):
    """Slab floor with no edge insulation - uses init_slab_on_ground_floor_uninsulated_or_all_insulation()"""

    floor_type: Literal[FloorType.SLAB_NO_EDGE_INSULATION]


class BuildingElementGroundSlabEdgeInsulation(BuildingElementGroundBase):
    """Slab floor with edge insulation - uses init_slab_on_ground_floor_edge_insulated()"""

    floor_type: Literal[FloorType.SLAB_EDGE_INSULATION]

    # Edge insulation is actually used in edge_type() function for this floor type
    edge_insulation: list[EdgeInsulation] | None = None


class BuildingElementGroundSuspendedFloor(BuildingElementGroundBase):
    """Suspended floor - uses init_suspended_floor()"""

    floor_type: Literal[FloorType.SUSPENDED_FLOOR]

    # Fields used specifically in suspended floor calculations
    # Using the actual Pydantic field names from the original schema
    area_per_perimeter_vent: Annotated[
        float,
        Field(description="Area of ventilation openings per perimeter (unit: m²/m)", gt=0),
    ]
    thermal_resist_insul: Annotated[
        RValue,
        Field(
            description="Thermal resistance of insulation on base of underfloor space, excluding surface resistances (unit: m².K/W)",
        ),
    ]
    # thermal_transm_walls and height_upper_surface are used in suspended floor calculations
    thermal_transm_walls: Annotated[
        UValue,
        Field(
            description="Thermal transmittance of walls above ground in accordance with ISO 6946, i.e. including surface resistances (unit: W/m².K)"
        ),
    ]

    height_upper_surface: Annotated[
        float,
        Field(
            description="Height of the floor upper surface (unit: m) - average value is used if h varies",
            gt=0,
        ),
    ]

    shield_fact_location: Annotated[WindShieldLocation, Field(description="Wind shielding factor")]


class BuildingElementGroundHeatedBasement(BuildingElementGroundBase):
    """Heated basement - uses init_heated_basement()"""

    floor_type: Literal[FloorType.HEATED_BASEMENT]

    # Required fields actually used in init_heated_basement()
    # Only z_b (depth_basement_floor) and r_w_b (thermal_resist_walls_base) are used!
    depth_basement_floor: Annotated[
        float, Field(description="Depth of basement floor below ground level (unit: m)", gt=0)
    ]
    thermal_resist_walls_base: Annotated[
        RValue,
        Field(
            description="Thermal resistance of walls of the basement, excluding surface resistances (unit: m².K/W)"
        ),
    ]


class BuildingElementGroundUnheatedBasement(BuildingElementGroundBase):
    """Unheated basement - uses init_unheated_basement()"""

    floor_type: Literal[FloorType.UNHEATED_BASEMENT]

    # Required fields actually used in init_unheated_basement()
    # All basement parameters are used in unheated basement calculations
    depth_basement_floor: Annotated[
        float, Field(description="Depth of basement floor below ground level (unit: m)", gt=0)
    ]
    height_basement_walls: Annotated[
        float,
        Field(description="Height of the basement walls above ground level (unit: m)", gt=0),
    ]
    thermal_resist_walls_base: Annotated[
        RValue,
        Field(
            description="Thermal resistance of walls of the basement, excluding surface resistances (unit: m².K/W)"
        ),
    ]
    thermal_transm_envi_base: Annotated[
        UValue,
        Field(
            description="Thermal transmittance of floor above basement in accordance with ISO 6946, i.e. including surface resistances (unit: W/m².K)"
        ),
    ]
    thermal_transm_walls: Annotated[
        UValue,
        Field(
            description="Thermal transmittance of walls above ground in accordance with ISO 6946, i.e. including surface resistances (unit: W/m².K)"
        ),
    ]


# Discriminated union based on floor_type
BuildingElementGround = Annotated[
    BuildingElementGroundSlabNoEdgeInsulation
    | BuildingElementGroundSlabEdgeInsulation
    | BuildingElementGroundSuspendedFloor
    | BuildingElementGroundHeatedBasement
    | BuildingElementGroundUnheatedBasement,
    Field(discriminator="floor_type"),
]


# Discriminated union based on type
BuildingElement = Annotated[
    BuildingElementOpaque
    | BuildingElementTransparent
    | BuildingElementGround
    | BuildingElementAdjacentConditionedSpace
    | BuildingElementAdjacentUnconditionedSpaceSimple
    | BuildingElementPartyWall,
    Field(discriminator="type"),
]


class ControlCombination(StrictBaseModel):
    controls: Annotated[list[str], Field(min_length=1)]
    operation: ControlCombinationOperation


class ControlCombinations(RootModel[dict[str, ControlCombination]]):
    """
    A dictionary of control combinations where:
    - Keys are user-defined names (e.g., "main", "week", "weekday", "weekend")
    - Values conform to the ControlCombination schema
    - The "main" entry is required
    """

    @model_validator(mode="after")
    def validate_main_exists(self) -> Self:
        if "main" not in self.root:
            raise ValueError("ControlCombinations must contain a 'main' entry")
        return self

    @property
    def main(self) -> ControlCombination:
        return self.root["main"]


class ControlCombinationTime(StrictBaseModel):
    type: Literal[TimeControlType.COMBINATION]
    combination: ControlCombinations


class EcoDesignController(StrictBaseModel):
    ecodesign_control_class: EcoDesignControllerClass
    max_outdoor_temp: Annotated[
        DegreesCelsius | None, Field(description="Maximum outdoor temperature (unit: Celsius)")
    ] = None
    min_flow_temp: Annotated[
        float | None, Field(description="Minimum flow temperature (unit: Celsius)", gt=0)
    ] = None
    min_outdoor_temp: Annotated[
        DegreesCelsius | None, Field(description="Minimum outdoor temperature (unit: Celsius)")
    ] = None


class EnergyDiverter(StrictBaseModel):
    controlmax: Annotated[
        ControlReference,
        Field(
            alias="Controlmax",
            description="Reference to a control schedule of maximum temperature setpoints. References a key in $.Control.",
        ),
    ]
    heat_source: HeatSourceReference


class EnergySupply(StrictBaseModel):
    electric_battery: Annotated[
        ElectricBattery | None,
        Field(alias="ElectricBattery", description="Indicates that an electric battery is present"),
    ] = None
    diverter: Annotated[
        EnergyDiverter | None, Field(description="Indicates that the supply has a diverter")
    ] = None
    fuel: Annotated[FuelType, Field(description="Type of fuel")]
    is_export_capable: Annotated[
        bool,
        Field(description="Denotes that this energy supply can export its surplus supply"),
    ]
    priority: Annotated[
        list[EnergySupplyPriorityEntry] | None,
        Field(description="Priority order of energy surplus"),
    ] = None
    tariff: str | None = None
    threshold_charges: (
        Annotated[
            list[FloatBetween0and1],
            Field(
                max_length=12,
                min_length=12,
                description="Level of battery charge above which grid prohibited from charging battery (monthly values) (0 - 1)",
            ),
        ]
        | None
    ) = None
    threshold_prices: (
        Annotated[
            list[float],
            Field(
                max_length=12,
                min_length=12,
                description="Grid price below which battery is permitted to charge from grid (monthly values) (unit: p/kWh)",
            ),
        ]
        | None
    ) = None


class ExternalSensor(StrictBaseModel):
    correlation: list[ExternalSensorCorrelation]


class HeatPumpTestDatum(StrictBaseModel):
    air_flow_rate: Annotated[
        float | None,
        Field(
            gt=0,
            description="Air flow rate through the heat pump for the test condition (unit: m³/h)",
        ),
    ] = None
    capacity: Annotated[
        float, Field(gt=0, description="Heat output capacity at this test condition (unit: kW)")
    ]
    cop: Annotated[
        float,
        Field(
            gt=0,
            description="Coefficient of performance at this test condition (dimensionless)",
            title="CoP",
        ),
    ]
    design_flow_temp: Annotated[
        float,
        Field(description="Design flow temperature for the heating system (unit: Celsius)", gt=0),
    ]
    eahp_mixed_ext_air_ratio: Annotated[
        FloatBetween0and1 | None,
        Field(
            description="Ratio of external air to recirculated air for exhaust air heat pumps (dimensionless)",
            title="EAHP Mixed External Air Ratio",
        ),
    ] = None
    temp_outlet: Annotated[
        float,
        Field(
            description="Heat pump outlet temperature for the test condition (unit: Celsius)", gt=0
        ),
    ]
    temp_source: Annotated[
        DegreesCelsius,
        Field(description="Heat pump source temperature for the test condition (unit: Celsius)"),
    ]
    temp_test: Annotated[
        DegreesCelsius,
        Field(description="Ambient air temperature for the test condition (unit: Celsius)"),
    ]
    test_letter: TestLetter


class ImmersionHeater(StrictBaseModel):
    type: Literal[HotWaterHeatSourceType.IMMERSION_HEATER]
    controlmax: Annotated[
        ControlReference,
        Field(
            alias="Controlmax",
            description="Reference to a control schedule of maximum temperature setpoints. References a key in $.Control.",
        ),
    ]
    controlmin: Annotated[
        ControlReference,
        Field(
            alias="Controlmin",
            description="Reference to a control schedule of minimum temperature setpoints. References a key in $.Control.",
        ),
    ]
    energy_supply: EnergySupplyReference
    heater_position: Annotated[
        FloatBetween0and1,
        Field(
            description="Vertical position of the heater within the tank, as a fraction of the tank height (0 = bottom, 1 = top). Dimensionless."
        ),
    ]
    power: Annotated[float, Field(description="(unit: kW)", gt=0)]
    thermostat_position: Annotated[
        FloatBetween0and1 | None,
        Field(
            description="Vertical position of the thermostat within the tank, as a fraction of the tank height (0 = bottom, 1 = top). Dimensionless. Required for StorageTank but not for SmartHotWaterTank.",
        ),
    ] = None


class SolarThermalSystem(StrictBaseModel):
    type: Literal[HotWaterHeatSourceType.SOLAR_THERMAL_SYSTEM]
    controlmax: Annotated[
        ControlReference,
        Field(
            alias="Controlmax",
            description="Reference to a control schedule of maximum temperature setpoints. References a key in $.Control.",
        ),
    ]
    energy_supply: EnergySupplyReference
    area_module: Annotated[
        float, Field(description="Collector module reference area (unit: m2)", gt=0)
    ]
    collector_mass_flow_rate: Annotated[
        float, Field(description="Mass flow rate solar loop (unit: kg/s)", gt=0)
    ]
    first_order_hlc: Annotated[
        float, Field(description="First order heat loss coefficient", gt=0, title="First Order HLC")
    ]
    heater_position: Annotated[
        FloatBetween0and1,
        Field(
            description="Vertical position of the heater within the tank, as a fraction of the tank height (0 = bottom, 1 = top). Dimensionless."
        ),
    ]
    incidence_angle_modifier: Annotated[
        FloatGreaterThan0UpTo1, Field(description="Hemispherical incidence angle modifier")
    ]
    modules: Annotated[int, Field(ge=1, description="Number of collector modules installed")]
    orientation360: Orientation360
    peak_collector_efficiency: FloatGreaterThan0UpTo1
    power_pump: Annotated[float, Field(description="Power of collector pump (unit: kW)", ge=0)]
    power_pump_control: Annotated[
        float, Field(description="Power of collector pump controller (unit: kW)", ge=0)
    ]
    second_order_hlc: Annotated[
        float,
        Field(description="Second order heat loss coefficient", ge=0, title="Second Order HLC"),
    ]
    sol_loc: Annotated[
        SolarCollectorLoopLocation,
        Field(description="Location of the main part of the collector loop piping"),
    ]
    solar_loop_piping_hlc: Annotated[
        float,
        Field(
            description="Heat loss coefficient of the collector loop piping (unit: W/K)",
            gt=0,
            title="Solar Loop Piping HLC",
        ),
    ]
    thermostat_position: Annotated[
        FloatBetween0and1 | None,
        Field(
            description="Vertical position of the thermostat within the tank, as a fraction of the tank height (0 = bottom, 1 = top). Dimensionless. Required for StorageTank but not for SmartHotWaterTank.",
        ),
    ] = None
    tilt: Annotated[
        float,
        Field(
            description=(
                "Tilt angle (inclination) of the solar thermal panel from horizontal, "
                "measured upwards facing, 0 to 90, in degrees. "
                "0=horizontal surface, 90=vertical surface. "
                "Needed to calculate solar irradiation at the panel surface."
            ),
            ge=0,
            le=90,
        ),
    ]


class HeatSourceWetServiceWaterRegular(StrictBaseModel):
    type: Literal[HotWaterHeatSourceType.HEAT_SOURCE_WET_SERVICE_WATER_REGULAR]
    controlmax: Annotated[
        ControlReference,
        Field(
            alias="Controlmax",
            description="Reference to a control schedule of maximum temperature setpoints. References a key in $.Control.",
        ),
    ]
    controlmin: Annotated[
        ControlReference,
        Field(
            alias="Controlmin",
            description="Reference to a control schedule of minimum temperature setpoints. References a key in $.Control.",
        ),
    ]
    heater_position: Annotated[
        FloatBetween0and1,
        Field(
            description="Vertical position of the heater within the tank, as a fraction of the tank height (0 = bottom, 1 = top). Dimensionless."
        ),
    ]
    name: Annotated[
        str,
        Field(description="User-defined name for this heat source."),
    ]
    temp_flow_limit_upper: Annotated[
        float | None,
        Field(description="Upper operating limit for flow temperature (unit: °C). Optional.", gt=0),
    ] = None
    thermostat_position: Annotated[
        FloatBetween0and1 | None,
        Field(
            description="Vertical position of the thermostat within the tank, as a fraction of the tank height (0 = bottom, 1 = top). Dimensionless. Required for StorageTank but not for SmartHotWaterTank."
        ),
    ] = None


class HeatPumpHotWaterOnly(StrictBaseModel):
    type: Literal[HotWaterHeatSourceType.HEAT_PUMP_HOT_WATER_ONLY]
    controlmax: Annotated[
        ControlReference,
        Field(
            alias="Controlmax",
            description="Reference to a control schedule of maximum temperature setpoints. References a key in $.Control.",
        ),
    ]
    controlmin: Annotated[
        ControlReference,
        Field(
            alias="Controlmin",
            description="Reference to a control schedule of minimum temperature setpoints. References a key in $.Control.",
        ),
    ]
    energy_supply: EnergySupplyReference
    daily_losses_declared: Annotated[
        float, Field(description="Standing heat loss (unit: kWh/day)", gt=0)
    ]
    heat_exchanger_surface_area_declared: Annotated[
        float | None,
        Field(description="Surface area of heat exchanger stored in the database (unit: m2)", gt=0),
    ]
    heater_position: Annotated[
        FloatBetween0and1,
        Field(
            description="Vertical position of the heater within the tank, as a fraction of the tank height (0 = bottom, 1 = top). Dimensionless."
        ),
    ]
    in_use_factor_mismatch: Annotated[
        float, Field(description="In use factor to be applied to heat pump efficiency", gt=0)
    ]
    power_max: Annotated[float, Field(description="(unit: kW)", gt=0)]
    tank_volume_declared: Annotated[
        float, Field(description="Tank volume stored in the database (unit: litres)", gt=0)
    ]
    test_data: Annotated[
        HeatPumpHotWaterTestData,
        Field(description="Dictionary with keys denoting tapping profile letter (M or L)"),
    ]
    thermostat_position: Annotated[
        FloatBetween0and1 | None,
        Field(
            description="Vertical position of the thermostat within the tank, as a fraction of the tank height (0 = bottom, 1 = top). Dimensionless. Required for StorageTank but not for SmartHotWaterTank.",
        ),
    ] = None
    vol_hw_daily_average: Annotated[
        float,
        Field(
            description="Annual average hot water use for the dwelling (unit: litres/day)",
            gt=0,
            title="Volume Hot Water Daily Average",
        ),
    ]


HotWaterHeatSource = Annotated[
    ImmersionHeater | SolarThermalSystem | HeatSourceWetServiceWaterRegular | HeatPumpHotWaterOnly,
    Field(discriminator="type"),
]


class HotWaterDemand(StrictBaseModel):
    bath: Annotated[dict[str, Bath] | None, Field(alias="Bath")] = None
    distribution: Annotated[
        list[WaterPipeworkSimple] | dict[str, list[WaterPipeworkSimple]] | None,
        Field(alias="Distribution"),
    ] = None
    other: Annotated[dict[str, OtherWaterUse] | None, Field(alias="Other")] = None
    shower: Annotated[dict[str, Shower] | None, Field(alias="Shower")] = None


class HotWaterSourceSmartHotWaterTank(StrictBaseModel):
    type: Literal[HotWaterSourceType.SMART_HOT_WATER_TANK]
    cold_water_source: ColdWaterSourceReference
    energy_supply_pump: Annotated[EnergySupplyReference, Field(alias="EnergySupply_pump")]
    heat_source: Annotated[
        dict[str, HotWaterHeatSource],
        Field(
            alias="HeatSource",
            description="Dictionary of heating systems connected to the smart hot water tank",
        ),
    ]
    daily_losses: Annotated[
        float,
        Field(
            description="Daily standby losses due to tank insulation at standardised conditions (unit: kWh/24h)",
            gt=0,
        ),
    ]
    init_temp: Annotated[
        RunningWaterTemperature,
        Field(
            description="Initial temperature of the smart hot water tank at the start of simulation (unit: ˚C)"
        ),
    ]
    max_flow_rate_pump_l_per_min: Annotated[
        float,
        Field(
            description="Maximum flow rate of the pump (unit: litre/minute)",
            gt=0,
            title="Maximum Flow Rate Pump",
        ),
    ]
    power_pump_k_w: Annotated[
        float,
        Field(
            alias="power_pump_kW",
            title="Power Pump",
            description="Electrical power consumption of the pump (unit: kW)",
            gt=0,
        ),
    ]
    primary_pipework: Annotated[
        list[WaterPipework] | None,
        Field(
            description="List of primary pipework components connected to the smart hot water tank"
        ),
    ] = None
    temp_setpnt_max: Annotated[
        str, Field(description="Reference to a control schedule of maximum state of charge values")
    ]
    temp_usable: Annotated[
        RunningWaterTemperature,
        Field(description="Temperature below which water is considered unusable (unit: ˚C)"),
    ]
    volume: Annotated[
        float,
        Field(
            description="Total volume of tank (unit: litre)",
            gt=0,
        ),
    ]


class MechanicalVentilationPosition(StrictBaseModel):
    """Position data for mechanical ventilation intake/exhaust points"""

    orientation360: Orientation360
    pitch: PitchAngle
    mid_height_air_flow_path: Annotated[
        float,
        Field(
            description="Mid height of air flow path relative to ventilation zone (unit: m)", gt=0
        ),
    ]


class MechanicalVentilation(StrictBaseModel):
    control: Annotated[ControlReference | None, Field(alias="Control")] = None
    energy_supply: EnergySupplyReference
    sfp: Annotated[
        float,
        Field(
            alias="SFP",
            title="SFP",
            description="Specific fan power, assumed inclusive of any in use factors unless SFP_in_use_factor also provided (unit: W/l/s)",
            gt=0,
        ),
    ]
    sfp_in_use_factor: Annotated[
        float,
        Field(
            alias="SFP_in_use_factor",
            title="SFP In Use Factor",
            description="Adjustment factor to be applied to SFP to account for e.g. type of ducting. Typical range 1 - 2.5",
            ge=1,
        ),
    ] = 1
    design_outdoor_air_flow_rate: Annotated[float, Field(description="(unit: m³/hour)", gt=0)]
    ductwork: Annotated[
        list[MechanicalVentilationDuctwork] | None,
        Field(description="List of ductworks installed in this ventilation system"),
    ] = None
    mvhr_eff: Annotated[
        float | None, Field(description="MVHR efficiency", ge=0, le=1, title="MVHR Efficiency")
    ] = None
    mvhr_location: Annotated[
        MVHRLocation | None,
        Field(description="Location of the MVHR unit (inside or outside the thermal envelope)"),
    ] = None
    sup_air_flw_ctrl: Annotated[
        SupplyAirFlowRateControlType, Field(description="Supply air flow rate control")
    ] = SupplyAirFlowRateControlType.ODA
    sup_air_temp_ctrl: Annotated[
        SupplyAirTemperatureControlType, Field(description="Supply air temperature control")
    ] = SupplyAirTemperatureControlType.NO_CTRL
    vent_type: Annotated[MechVentType, Field(description="Ventilation system type")]

    # Position fields for MVHR systems (with both intake and exhaust)
    position_intake: Annotated[
        MechanicalVentilationPosition | None, Field(description="Position data for MVHR intake")
    ] = None
    position_exhaust: Annotated[
        MechanicalVentilationPosition | None,
        Field(description="Position data for MVHR exhaust or MEV extract"),
    ] = None

    # Single position fields for non-MVHR systems
    mid_height_air_flow_path: Annotated[
        float | None,
        Field(
            description="Mid height of air flow path relative to ventilation zone (unit: m). Used for non-MVHR systems.",
            gt=0,
        ),
    ] = None
    orientation360: Annotated[
        Orientation360 | None, Field(description="Orientation for non-MVHR systems")
    ] = None
    pitch: Annotated[PitchAngle | None, Field(description="Pitch angle for non-MVHR systems")] = (
        None
    )

    @model_validator(mode="after")
    def validate_position_fields(self) -> Self:
        """Validate that appropriate position fields are provided based on ventilation type."""
        if self.vent_type == MechVentType.MVHR:
            # MVHR requires both intake and exhaust positions
            if self.position_intake is None or self.position_exhaust is None:
                raise ValueError(
                    "MVHR ventilation systems require both 'position_intake' and 'position_exhaust' fields"
                )
            # MVHR should not use legacy single position fields
            if any(
                v is not None
                for v in [self.orientation360, self.pitch, self.mid_height_air_flow_path]
            ):
                raise ValueError(
                    "MVHR ventilation systems should use 'position_intake' and 'position_exhaust' fields, "
                    "not the legacy single position fields (orientation360, pitch, mid_height_air_flow_path)"
                )
        elif (
            self.vent_type.is_extract_only()
            or self.vent_type == MechVentType.POSITIVE_INPUT_VENTILATION
        ):
            # Extract-only and supply-only systems can use either format
            # Check if using new format
            if self.position_exhaust is not None:
                # Using new format - ensure legacy fields are not used
                if any(
                    v is not None
                    for v in [self.orientation360, self.pitch, self.mid_height_air_flow_path]
                ):
                    raise ValueError(
                        f"{self.vent_type} systems should use either 'position_exhaust' OR the legacy fields, not both"
                    )
                # Ensure position_intake is not used for extract-only systems
                if self.position_intake is not None:
                    raise ValueError(
                        f"{self.vent_type} systems should not have 'position_intake' field"
                    )
            else:
                # Using legacy format - ensure all required fields are present
                if any(
                    v is None
                    for v in [self.orientation360, self.pitch, self.mid_height_air_flow_path]
                ):
                    raise ValueError(
                        f"{self.vent_type} systems require either 'position_exhaust' field OR all legacy position fields "
                        "(orientation360, pitch, mid_height_air_flow_path)"
                    )
        else:
            raise ValueError(f"Unknown ventilation type: {self.vent_type}")  # pragma: nocover

        return self


class PhotovoltaicPanel(StrictBaseModel):
    peak_power: Annotated[
        float,
        Field(
            description=(
                "Peak power; represents the electrical power of a photovoltaic system "
                "with a given area for a solar irradiance of 1 kW/m² on this surface (at 25 degrees) "
                "(unit: kW)"
            ),
            gt=0,
        ),
    ]
    ventilation_strategy: PhotovoltaicVentilationStrategy
    pitch: PitchAnglePV
    orientation360: Orientation360
    base_height: Annotated[
        float,
        Field(
            description="The distance between the ground and the lowest edge of the PV array (unit: m)",
            ge=0,
        ),
    ]
    height: Annotated[float, Field(description="Height of the PV array (unit: m)")]
    width: Annotated[float, Field(description="Width of the PV panel (unit: m)", gt=0)]
    shading: list[WindowShading]


class PhotovoltaicSystem(StrictBaseModel):
    type: Literal["PhotovoltaicSystem"]
    peak_power: Annotated[
        float,
        Field(
            description=(
                "Peak power; represents the electrical power of a photovoltaic system "
                "with a given area for a solar irradiance of 1 kW/m² on this surface (at 25 degrees) "
                "(unit: kW)"
            ),
            gt=0,
        ),
    ]
    energy_supply: EnergySupplyReference
    height: Annotated[float, Field(description="Height of the PV array (unit: m)", gt=0)]
    width: Annotated[float, Field(description="Width of the PV panel (unit: m)", gt=0)]
    shading: list[WindowShading]
    inverter_is_inside: Annotated[
        bool, Field(description="Whether the inverter is considered inside the building")
    ]
    inverter_peak_power_ac: Annotated[
        float,
        Field(
            description="Peak power; represents the peak electrical AC power output from the inverter (unit: kW)",
            gt=0,
            title="Inverter Peak Power AC",
        ),
    ]
    inverter_peak_power_dc: Annotated[
        float,
        Field(
            description="Peak power; represents the peak electrical DC power input to the inverter (unit: kW)",
            gt=0,
            title="Inverter Peak Power DC",
        ),
    ]
    inverter_type: InverterType
    ventilation_strategy: PhotovoltaicVentilationStrategy
    pitch: PitchAnglePV
    orientation360: Orientation360
    base_height: Annotated[
        float,
        Field(
            description="The distance between the ground and the lowest edge of the PV array (unit: m)",
            ge=0,
        ),
    ]


class PhotovoltaicSystemWithPanels(StrictBaseModel):
    type: Literal["PhotovoltaicSystem"]
    energy_supply: Annotated[str, Field(alias="EnergySupply")]
    inverter_is_inside: Annotated[
        bool, Field(description="Whether the inverter is considered inside the building")
    ]
    inverter_peak_power_ac: Annotated[
        float,
        Field(
            description="Peak power; represents the peak electrical AC power output from the inverter (unit: kW)",
            gt=0,
            title="Inverter Peak Power AC",
        ),
    ]
    inverter_peak_power_dc: Annotated[
        float,
        Field(
            description="Peak power; represents the peak electrical DC power input to the inverter (unit: kW)",
            gt=0,
            title="Inverter Peak Power DC",
        ),
    ]
    inverter_type: InverterType
    panels: Annotated[list[PhotovoltaicPanel], Field(min_length=1)]


OnSiteGeneration = (
    PhotovoltaicSystemWithPanels
    | Annotated[
        PhotovoltaicSystem, deprecated("Deprecated: use PhotovoltaicSystemWithPanels instead")
    ]
)


class ScheduleEntryForBoolean(RootModel[bool | ScheduleRepeaterForBoolean | str | None]):
    """
    A schedule entry that can be a direct value, repeating pattern, or reference.

    Examples:
        # Direct boolean value
        true

        # Repeating pattern (heating on for 8 hours, off for 16 hours)
        {"repeat": 24, "value": true}

        # Reference to another schedule
        "weekday_heating_schedule"

        # Complex repeating pattern with reference
        {"repeat": 7, "value": "daily_pattern"}
    """

    root: bool | ScheduleRepeaterForBoolean | str | None


class ScheduleEntryForDouble(RootModel[float | ScheduleRepeaterForDouble | str | None]):
    """
    A schedule entry that can be a direct value, repeating pattern, or reference.

    Examples:
        # Direct float value (temperature setpoint)
        21.5

        # Repeating pattern (21.5°C for 8 hours, 18°C for 16 hours)
        {"repeat": 24, "value": 21.5}

        # Reference to another schedule
        "weekday_temp_schedule"

        # Complex repeating pattern with reference
        {"repeat": 7, "value": "daily_temp_pattern"}

        # Power level schedule
        2.5  # 2.5 kW constant power
    """

    root: float | ScheduleRepeaterForDouble | str | None


# Updated ScheduleForBoolean to support user-defined entries
class ScheduleForBoolean(RootModel[dict[str, list[ScheduleEntryForBoolean]]]):
    """
    A dictionary of schedule entries where:
    - Keys are user-defined names (e.g., "main", "week", "weekday", "weekend")
    - Values are lists of ScheduleEntryForBoolean
    - The "main" entry is required
    """

    @model_validator(mode="after")
    def validate_main_exists(self) -> Self:
        if "main" not in self.root:
            raise ValueError("Schedule must contain a 'main' entry")
        return self

    # Convenience properties for backward compatibility
    @property
    def main(self) -> list[ScheduleEntryForBoolean]:
        return self.root["main"]


# Updated ScheduleForDouble to support user-defined entries
class ScheduleForDouble(RootModel[dict[str, list[ScheduleEntryForDouble]]]):
    """
    A dictionary of schedule entries where:
    - Keys are user-defined names (e.g., "main", "week", "weekday", "weekend")
    - Values are lists of ScheduleEntryForDouble
    - The "main" entry is required
    """

    @model_validator(mode="after")
    def validate_main_exists(self) -> Self:
        if "main" not in self.root:
            raise ValueError("Schedule must contain a 'main' entry")
        return self

    # Convenience properties for backward compatibility
    @property
    def main(self) -> list[ScheduleEntryForDouble]:
        return self.root["main"]


class ScheduleRepeaterEntryForDegreesCelsius(RootModel[DegreesCelsius | None]):
    root: DegreesCelsius | None


class ScheduleRepeaterValueForDegreesCelsius(
    RootModel[str | ScheduleRepeaterEntryForDegreesCelsius]
):
    root: str | ScheduleRepeaterEntryForDegreesCelsius


class ScheduleRepeaterForDegreesCelsius(StrictBaseModel):
    repeat: Annotated[int, Field(ge=1)]
    value: ScheduleRepeaterValueForDegreesCelsius


class ScheduleEntryForDegreesCelsius(
    RootModel[DegreesCelsius | ScheduleRepeaterForDegreesCelsius | str | None]
):
    root: DegreesCelsius | ScheduleRepeaterForDegreesCelsius | str | None


class ScheduleForDegreesCelsius(RootModel[dict[str, list[ScheduleEntryForDegreesCelsius]]]):
    """
    A dictionary of temperature schedule entries where:
    - Keys are user-defined names (e.g., "main", "week", "weekend")
    - Values are lists of ScheduleEntryForDegreesCelsius
    - The "main" entry is required
    """

    @model_validator(mode="after")
    def validate_main_exists(self) -> Self:
        if "main" not in self.root:
            raise ValueError("Schedule must contain a 'main' entry")
        return self

    @property
    def main(self) -> list[ScheduleEntryForDegreesCelsius]:
        return self.root["main"]


class ShadingObject(StrictBaseModel):
    distance: Annotated[
        float,
        Field(description="Distance of the shading object from the building. (Unit: m)", gt=0),
    ]
    height: Annotated[float, Field(description="Height of the shading object. (Unit: m)", gt=0)]
    type: Annotated[ShadingObjectType, Field(description="The type of shading object.")]


class ShadingSegment(StrictBaseModel):
    end360: Annotated[
        RotationalAngleDegrees,
        Field(description="The end angle of the shading segment (clockwise). (unit: °)"),
    ]
    shading: Annotated[
        list[ShadingObject] | None,
        Field(
            description="The shading object of the segment, detailing the distance, height, and type of the shading object."
        ),
    ] = None
    start360: Annotated[
        RotationalAngleDegrees,
        Field(description="Starting angle of the shading segment (clockwise). (unit: °)"),
    ]


class SpaceCoolSystemAirConditioning(StrictBaseModel):
    type: Literal["AirConditioning"]  # Changed from SpaceCoolSystemType to Literal
    control: ControlReference
    energy_supply: EnergySupplyReference
    cooling_capacity: Annotated[
        float, Field(description="Maximum cooling capacity of the system (unit: kW)", gt=0)
    ]
    efficiency: Annotated[
        float,
        Field(
            gt=0,
            description="Efficiency of the air conditioning system. SEER (Seasonal energy efficiency ratio)",
        ),
    ]
    frac_convective: Annotated[
        FloatBetween0and1, Field(description="Convective fraction for cooling")
    ]


SpaceCoolSystem = Annotated[
    SpaceCoolSystemAirConditioning,
    Field(discriminator="type"),
]


class SpaceHeatSystemInstantElectricHeater(StrictBaseModel):
    type: Literal["InstantElecHeater"]
    energy_supply: EnergySupplyReference
    control: ControlReference
    frac_convective: Annotated[
        FloatBetween0and1, Field(description="Convective fraction for heating")
    ]
    rated_power: Annotated[
        float, Field(description="Rated power of the instant electric heater. (Unit: kW)", gt=0)
    ]


class SpaceHeatSystemElectricStorageHeater(StrictBaseModel):
    type: Literal["ElecStorageHeater"]
    control_charger: Annotated[ControlReference, Field(alias="ControlCharger")]
    dry_core_max_output: Annotated[
        list[Annotated[list[NonNegativeFloat], Field(max_length=2, min_length=2)]],
        Field(
            alias="dry_core_max_output",
            description=(
                "Maximum output of the electric storage heater. (Unit: kW) "
                "Data from test showing the output from the storage heater when it is actively "
                "outputting heat, e.g. damper open / fan running."
            ),
        ),
    ]
    dry_core_min_output: Annotated[
        list[Annotated[list[NonNegativeFloat], Field(max_length=2, min_length=2)]],
        Field(
            alias="dry_core_min_output",
            description=(
                "Minimum output of the electric storage heater. (Unit: kW) "
                "Data from test showing the output from the storage heater when not actively "
                "outputting heat, i.e. case losses only"
            ),
        ),
    ]
    energy_supply: EnergySupplyReference
    air_flow_type: AirFlowType
    control: ControlReference
    fan_pwr: Annotated[float, Field(description="Fan power (unit: W)", ge=0)]
    frac_convective: Annotated[
        FloatBetween0and1, Field(description="Convective fraction for heating")
    ]
    n_units: Annotated[int, Field(description="Number of units installed in the zone.", gt=0)]
    pwr_in: Annotated[
        float,
        Field(
            description="The rated power of the heating element which charges the storage medium with heat (unit: kW)",
            gt=0,
        ),
    ]
    state_of_charge_init: Annotated[
        FloatBetween0and1,
        Field(
            description="State of charge at initialisation of dry core heat storage (ratio)",
        ),
    ]
    rated_power_instant: Annotated[
        float,
        Field(
            description="The rated power output of the instantaneous backup heater (unit: kW)", ge=0
        ),
    ]
    storage_capacity: Annotated[
        float,
        Field(description="Storage capacity of the electric storage heater. (Unit: kWh)", gt=0),
    ]
    zone: Annotated[
        ZoneReference,
        Field(
            description="The zone where the unit(s) is/are installed. References a key in $.Zone.",
        ),
    ]

    @field_validator("dry_core_max_output", "dry_core_min_output", mode="after")
    @classmethod
    def validate_dry_core_output(cls, value: list[list[NonNegativeFloat]], ctx):
        """Validate that the dry_core_min_output and dry_core_max_output SOC values:
        - are in increasing order
        - start at 0.0
        - end at 0.0"""
        if not value:
            return value

        # Convert esh_***_output to NumPy arrays without sorting
        soc_array = np.array([pair[0] for pair in value])

        # Validate that both SOC arrays are in strictly increasing order
        if not np.all(soc_array[:-1] <= soc_array[1:]):
            raise ValueError(
                f"{ctx.field_name} SOC values must be in increasing order (from 0.0 to 1.0)."
            )

        # Validate that both SOC arrays start at 0.0 and end at 1.0
        if not np.isclose(soc_array[0], 0.0):
            raise ValueError(
                f"The first SOC value in {ctx.field_name} must be 0.0 (fully discharged)."
            )
        if not np.isclose(soc_array[-1], 1.0):
            raise ValueError(f"The last SOC value in {ctx.field_name} must be 1.0 (fully charged).")

        return value


class SpaceHeatSystemWetDistribution(StrictBaseModel):
    type: Literal["WetDistribution"]
    heat_source: Annotated[SpaceHeatSystemHeatSource, Field(alias="HeatSource")]
    bypass_fraction_recirculated: Annotated[
        float | None, Field(description="Fraction of return back into flow water", ge=0, lt=1)
    ] = None
    design_flow_rate: Annotated[
        float | None,
        Field(
            description="Constant flow rate if the heat source can't modulate flow rate (unit: l/s)",
            gt=0,
        ),
    ] = None
    design_flow_temp: Annotated[
        float, Field(description="Design flow temperature. (Unit: ˚C)", gt=0)
    ]
    emitters: Annotated[
        list[WetEmitter],
        Field(description="Wet emitter details of the heating system.", min_length=1),
    ]
    pipework: list[WaterPipework] | None = None
    ecodesign_controller: EcoDesignController
    max_flow_rate: Annotated[
        float | None, Field(description="Maximum flow rate allowed (unit: litres/min)", gt=0)
    ] = None
    min_flow_rate: Annotated[
        float | None, Field(description="Minimum flow rate allowed (unit: litres/min)", gt=0)
    ] = None
    temp_diff_emit_dsgn: Annotated[
        float,
        Field(
            description="Design temperature difference across the emitters. (Unit: deg C or K)",
            gt=0,
        ),
    ]
    thermal_mass: Annotated[
        float | None,
        Field(
            description="Thermal mass of the emitters, excluding any thermal mass entered under individual radiator/UFH entries and always excluding thermal mass of pipework. (Unit: kWh/K)",
            gt=0,
        ),
    ] = None
    variable_flow: Annotated[
        bool, Field(description="Whether the heat source can modulate flow rate.")
    ]
    control: ControlReference
    energy_supply: Annotated[EnergySupplyReference | None, Field(alias="EnergySupply")] = None
    zone: Annotated[
        ZoneReference,
        Field(description="Zone in which the emitters are located. References a key in $.Zone"),
    ]

    @model_validator(mode="after")
    def validate_flow_rate(self) -> Self:
        if self.variable_flow and (self.min_flow_rate is None or self.max_flow_rate is None):
            raise ValueError(
                "Both min_flow_rate and max_flow_rate are required if variable_flow is True."
            )
        return self

    @model_validator(mode="after")
    def validate_design_flow_rate(self) -> Self:
        if self.variable_flow is False and self.design_flow_rate is None:
            raise ValueError("design_flow_rate is required if variable_flow is False.")
        return self


class SpaceHeatSystemWarmAir(StrictBaseModel):
    type: Literal["WarmAir"]
    heat_source: Annotated[SpaceHeatSystemHeatSource, Field(alias="HeatSource")]
    control: ControlReference
    frac_convective: Annotated[
        FloatBetween0and1, Field(description="Convective fraction for heating")
    ]


SpaceHeatSystem = Annotated[
    SpaceHeatSystemInstantElectricHeater
    | SpaceHeatSystemElectricStorageHeater
    | SpaceHeatSystemWetDistribution
    | SpaceHeatSystemWarmAir,
    Field(discriminator="type"),
]


class WasteWaterHeatRecoverySystem(StrictBaseModel):
    type: Literal["WWHRS_Instantaneous"]
    cold_water_source: ColdWaterSourceReference
    flow_rates: Annotated[
        list[Annotated[float, Field(gt=0)]],
        Field(
            description="Test flow rates in litres per minute (e.g., [5, 7, 9, 11, 13])",
        ),
    ]
    system_a_efficiencies: Annotated[
        list[Annotated[float, Field(gt=0, le=100)]] | None,  # Made optional
        Field(
            description="Measured efficiencies for System A at the test flow rates",
        ),
    ] = None
    system_a_utilisation_factor: Annotated[
        FloatGreaterThan0UpTo1 | None,
        Field(
            description="Utilisation factor for System A",
        ),
    ] = None
    system_b_efficiencies: Annotated[
        list[Annotated[float, Field(gt=0, le=100)]] | None,
        Field(
            description="Measured efficiencies for System B (optional, uses system_b_efficiency_factor if not provided)",
        ),
    ] = None
    system_b_utilisation_factor: Annotated[
        FloatGreaterThan0UpTo1 | None,
        Field(
            description="Utilisation factor for System B. Required when using either system_b_efficiencies (pre-corrected data) or when converting system_a_efficiencies to System B (used with system_b_efficiency_factor).",
        ),
    ] = None
    system_c_efficiencies: Annotated[
        list[Annotated[float, Field(gt=0, le=100)]] | None,
        Field(
            description="Measured efficiencies for System C (optional, uses system_c_efficiency_factor if not provided)",
        ),
    ] = None
    system_c_utilisation_factor: Annotated[
        FloatGreaterThan0UpTo1 | None,
        Field(
            description="Utilisation factor for System C. Required when using either system_c_efficiencies (pre-corrected data) or when converting system_a_efficiencies to System C (used with system_c_efficiency_factor).",
        ),
    ] = None
    system_b_efficiency_factor: Annotated[
        FloatGreaterThan0UpTo1,
        Field(
            description="Reduction factor for converting System A efficiency data to System B (default 0.81). Only used when system_b_efficiencies is not provided.",
        ),
    ] = 0.81
    system_c_efficiency_factor: Annotated[
        FloatGreaterThan0UpTo1,
        Field(
            description="Reduction factor for converting System A efficiency data to System C (default 0.88). Only used when system_c_efficiencies is not provided.",
        ),
    ] = 0.88

    @model_validator(mode="after")
    def validate_at_least_one_efficiency_set(self) -> Self:
        """Ensure at least one efficiency dataset is provided."""
        if (
            self.system_a_efficiencies is None
            and self.system_b_efficiencies is None
            and self.system_c_efficiencies is None
        ):
            raise ValueError(
                "At least one efficiency dataset must be provided: "
                "system_a_efficiencies, system_b_efficiencies, or system_c_efficiencies"
            )
        return self

    @model_validator(mode="after")
    def validate_flow_rates_and_efficiencies_length(self) -> Self:
        # Validate system A if provided.
        if self.system_a_efficiencies is not None and len(self.flow_rates) != len(
            self.system_a_efficiencies
        ):
            raise ValueError("flow_rates and system_a_efficiencies must have the same length")

        # Validate system B if provided
        if self.system_b_efficiencies is not None and len(self.flow_rates) != len(
            self.system_b_efficiencies
        ):
            raise ValueError("flow_rates and system_b_efficiencies must have the same length")

        # Validate system C if provided
        if self.system_c_efficiencies is not None and len(self.flow_rates) != len(
            self.system_c_efficiencies
        ):
            raise ValueError("flow_rates and system_c_efficiencies must have the same length")

        return self


class ApplianceGains(TimeSeriesBase):
    events: Annotated[
        list[ApplianceGainsEvent] | None,
        Field(alias="Events", description="List of appliance usage events"),
    ] = None
    standby: Annotated[
        float | None,
        Field(
            alias="Standby",
            description="Appliance power consumption when not in use (unit: W)",
            ge=0,
        ),
    ] = None
    energy_supply: EnergySupplyReference
    gains_fraction: Annotated[
        FloatBetween0and1,
        Field(
            description="Proportion of appliance demand turned into heat gains (dimensionless, 0-1)"
        ),
    ]
    loadshifting: Annotated[
        ApplianceLoadShifting | None,
        Field(
            description="Load shifting configuration for smart appliance control",
        ),
    ] = None
    priority: Annotated[
        int | None,
        Field(description="Priority level for load shifting (lower numbers = higher priority)"),
    ] = None
    schedule: Annotated[
        ScheduleForDouble | None,
        Field(description="Power consumption schedule (one entry per hour)"),
    ] = None


class BoilerCostScheduleHybrid(StrictBaseModel):
    cost_schedule_boiler: Annotated[
        ScheduleForDouble,
        Field(
            description="Cost data for the fuel used by the hybrid system's boiler (can be any units, typically p/kWh, as long as they are consistent across input fields)"
        ),
    ]
    cost_schedule_hp: Annotated[
        ScheduleForDouble,
        Field(
            description="Cost data for the fuel used by the hybrid system's heat pump (can be any units, typically p/kWh, as long as they are consistent across input fields)"
        ),
    ]
    cost_schedule_start_day: Annotated[
        int,
        Field(ge=0, le=365, description="Day on which the cost data series begins"),
    ]
    cost_schedule_time_series_step: Annotated[
        float,
        Field(description="Time step of the cost data series"),
    ]


class ChargeLevel(RootModel[float | list[float] | ScheduleForDouble]):
    root: float | list[float] | ScheduleForDouble


class ControlOnOffTimer(TimeSeriesBase):
    type: Literal[TimeControlType.ON_OFF_TIME]
    allow_null: bool | None = None
    schedule: Annotated[
        ScheduleForBoolean,
        Field(description="List of boolean values where true means on, one entry per hour"),
    ]


class ControlOnOffCostMinimising(TimeSeriesBase):
    type: Literal[TimeControlType.ON_OFF_COST_MINIMISING]
    schedule: Annotated[
        ScheduleForDouble, Field(description="List of cost values (one entry per time_series_step)")
    ]
    time_on_daily: HoursDuration24


class ControlSetpointTimer(TimeSeriesBase):
    type: Literal[TimeControlType.SETPOINT_TIME]
    advanced_start: Annotated[
        float | None,
        Field(
            description="How long before heating period the system should switch on (unit: hours)",
            ge=0,
        ),
    ] = None
    default_to_max: Annotated[
        bool | None,
        Field(
            description="If both min and max limits are set but setpoint is not, whether to default to min (false) or max (true)"
        ),
    ] = None
    schedule: Annotated[
        ScheduleForDouble,
        Field(description="Setpoint schedule with one entry per timestep"),
    ]
    setpoint_max: Annotated[float | None, Field(description="Maximum setpoint allowed")] = None
    setpoint_min: Annotated[float | None, Field(description="Minimum setpoint allowed")] = None

    @model_validator(mode="after")
    def validate_setpoint_bounds(self) -> Self:
        """Validate that setpoint_max is greater than setpoint_min when both are provided"""
        if self.setpoint_max is not None and self.setpoint_min is not None:
            if self.setpoint_max <= self.setpoint_min:
                raise ValueError("setpoint_max must be greater than setpoint_min")
        return self


class ControlChargeTarget(TimeSeriesBase):
    type: Literal[TimeControlType.CHARGE]
    charge_level: Annotated[
        ChargeLevel | None, Field(description="Proportion of the charge targeted for each day")
    ] = None
    external_sensor: ExternalSensor | None = None
    logic_type: ControlLogicType | None = None
    schedule: Annotated[
        ScheduleForBoolean,
        Field(description="List of boolean values where true means 'on' (one entry per hour)"),
    ]
    temp_charge_cut: Annotated[
        DegreesCelsius | None, Field(description="Temperature at which charging should stop")
    ] = None
    temp_charge_cut_delta: Annotated[
        ScheduleForDegreesCelsius | None,
        Field(description="Temperature delta schedule for charge cut-off adjustment (unit: ˚C)"),
    ] = None
    charge_calc_time: Annotated[
        float,
        Field(
            default=21,
            ge=0,
            lt=24,
            description="Indicates from which hour of the day the system starts to target the charge level for the next day rather than the current day",
        ),
    ]

    @model_validator(mode="after")
    def validate_logic_type(self) -> Self:
        if (
            self.logic_type
            in (ControlLogicType.AUTOMATIC, ControlLogicType.CELECT, ControlLogicType.HHRSH)
            and self.temp_charge_cut is None
        ):
            raise ValueError(f"logic_type ({self.logic_type}) requires temp_charge_cut to be set")
        return self


Control = Annotated[
    ControlOnOffTimer
    | ControlOnOffCostMinimising
    | ControlSetpointTimer
    | ControlChargeTarget
    | ControlCombinationTime,
    Field(
        discriminator="type",
        description="Control schedule configuration for heating and energy systems.",
    ),
]


# Constraints for ExternalConditionsInput list variables
GroundReflectance = Annotated[
    FloatBetween0and1,
    Field(
        description="The fraction of solar radiation incident on the ground that is reflected. Also called the albedo.",
    ),
]


class ExternalConditionsInput(StrictBaseModel):
    air_temperatures: Annotated[
        list[DegreesCelsius] | None,
        Field(
            description="List of external air temperatures, one entry per hour (unit: ˚C)",
        ),
    ] = None
    diffuse_horizontal_radiation: Annotated[
        list[NonNegativeFloat] | None,
        Field(
            description="List of diffuse horizontal radiation values, one entry per hour (unit: W/m²)",
        ),
    ] = None
    direct_beam_conversion_needed: Annotated[
        bool | None,
        Field(
            description="A flag to indicate whether direct beam radiation from climate data needs to be converted from horizontal to normal incidence; if normal direct beam radiation values are provided then no conversion is needed"
        ),
    ] = None
    direct_beam_radiation: Annotated[
        list[NonNegativeFloat] | None,
        Field(
            description="List of direct beam radiation values, one entry per hour (unit: W/m²)",
        ),
    ] = None
    latitude: Annotated[
        float | None,
        Field(
            description="Latitude of weather station, angle from south (unit: ˚)",
            ge=-90,
            le=90,
        ),
    ] = None
    longitude: Annotated[
        float | None,
        Field(
            description="Longitude of weather station, easterly +ve westerly -ve (unit: ˚)",
            ge=-180,
            le=180,
        ),
    ] = None
    shading_segments: Annotated[
        list[ShadingSegment] | None,
        Field(
            description="Data splitting the ground plane into segments (8-36) and giving height and distance to shading objects surrounding the building"
        ),
    ] = None
    solar_reflectivity_of_ground: Annotated[
        list[GroundReflectance] | None,
        Field(
            description="List of ground reflectivity values, 0 to 1, one entry per hour",
        ),
    ] = None
    wind_directions: Annotated[
        list[Orientation360] | None,
        Field(
            description="List of wind directions in degrees where North=0, East=90, South=180, West=270. Values range: 0 to 360. Wind direction is reported by the direction from which it originates, e.g. a southerly (180 degree) wind blows from the south to the north. (unit: ˚)"
        ),
    ] = None
    wind_speeds: Annotated[
        list[NonNegativeFloat] | None,
        Field(
            description="List of wind speeds, one entry per hour (unit: m/s)",
        ),
    ] = None

    def are_all_fields_set(self) -> bool:
        """Assert that all required fields are set and valid, allowing the model to run without a weather file."""
        for field_name, _ in self.__class__.model_fields.items():
            value = getattr(self, field_name)
            if value is None:
                return False
            if (
                field_name
                in [
                    "air_temperatures",
                    "diffuse_horizontal_radiation",
                    "direct_beam_radiation",
                    "solar_reflectivity_of_ground",
                    "wind_speeds",
                    "wind_directions",
                ]
                and len(value) < 8760
            ):
                # Data series must always have 8760 entries as some parts of the calculation rely on annual averages
                raise ValueError(f"ExternalConditions {field_name} should contain 8760 values.")
        return True


class HeatPumpBoiler(BoilerBase):
    """Boiler used as backup for heat pump systems"""

    cost_schedule_hybrid: BoilerCostScheduleHybrid | None = None


class HeatSourceWetHeatPump(StrictBaseModel):
    type: Literal[HeatSourceWetType.HEAT_PUMP]
    buffer_tank: Annotated[
        HeatPumpBufferTank | None,
        Field(
            alias="BufferTank",
            description="Optional buffer tank configuration for the heat pump system",
        ),
    ] = None
    energy_supply: EnergySupplyReference
    energy_supply_heat_network: Annotated[
        EnergySupplyReference | None,
        Field(
            alias="EnergySupply_heat_network",
            description="References a key in $.EnergySupply for heat network energy supply",
        ),
    ] = None
    mechanical_ventilation: Annotated[
        str | None,
        Field(
            alias="MechanicalVentilation",
            description="References a key in $.MechanicalVentilation",
            json_schema_extra={"reference_to": "$.infiltration_ventilation.mechanical_ventilation"},
        ),
    ] = None
    backup_ctrl_type: Annotated[
        HeatPumpBackupControlType,
        Field(description="Type of backup control for the heat pump system"),
    ]
    boiler: Annotated[
        HeatPumpBoiler | None,
        Field(description="Optional boiler configuration used as backup for the heat pump"),
    ] = None
    eahp_mixed_max_temp: Annotated[
        DegreesCelsius | None,
        Field(
            description="Maximum temperature for exhaust air heat pump mixed operation (unit: ˚C)",
            title="EAHP Mixed Max Temperature",
        ),
    ] = None
    eahp_mixed_min_temp: Annotated[
        DegreesCelsius | None,
        Field(
            description="Minimum temperature for exhaust air heat pump mixed operation (unit: ˚C)",
            title="EAHP Mixed Min Temperature",
        ),
    ] = None
    min_modulation_rate_20: Annotated[
        FloatBetween0and1 | None,
        Field(description="Minimum modulation rate at 20°C flow temperature (dimensionless, 0-1)"),
    ] = None
    min_modulation_rate_35: Annotated[
        FloatBetween0and1 | None,
        Field(description="Minimum modulation rate at 35°C flow temperature (dimensionless, 0-1)"),
    ] = None
    min_modulation_rate_55: Annotated[
        FloatBetween0and1 | None,
        Field(description="Minimum modulation rate at 55°C flow temperature (dimensionless, 0-1)"),
    ] = None
    min_temp_diff_flow_return_for_hp_to_operate: Annotated[
        float,
        Field(
            description="Minimum temperature difference between flow and return for heat pump operation (unit: K)",
            ge=0,
            title="Minimum Temperature Difference Flow Return For Heat Pump To Operate",
        ),
    ]
    modulating_control: Annotated[
        bool, Field(description="Whether the heat pump uses modulating control")
    ]
    power_crankcase_heater: Annotated[
        float, Field(description="Power consumption of crankcase heater (unit: kW)", ge=0)
    ]
    power_heating_circ_pump: Annotated[
        float,
        Field(description="Power consumption of heating circuit pump (unit: kW)", ge=0),
    ] = 0.0
    power_heating_warm_air_fan: Annotated[
        float | None, Field(description="Power consumption of warm air fan (unit: kW)", ge=0)
    ] = None
    power_max_backup: Annotated[
        float | None, Field(description="Backup resistive heater maximum power (unit: kW)", gt=0)
    ] = None
    power_off: Annotated[
        float, Field(description="Power consumption when heat pump is off (unit: kW)", ge=0)
    ]
    power_source_circ_pump: Annotated[
        float, Field(description="Power consumption of source circuit pump (unit: kW)", ge=0)
    ]
    power_standby: Annotated[
        float, Field(description="Power consumption in standby mode (unit: kW)", ge=0)
    ]
    sink_type: Annotated[HeatPumpSinkType, Field(description="Type of heat sink for the heat pump")]
    source_type: Annotated[
        HeatPumpSourceType, Field(description="Type of heat source for the heat pump")
    ]
    temp_distribution_heat_network: Annotated[
        float | None,
        Field(description="Distribution temperature for heat network (unit: ˚C)", gt=0),
    ] = None
    temp_lower_operating_limit: Annotated[
        DegreesCelsius,
        Field(description="Lower temperature limit for heat pump operation (unit: ˚C)"),
    ]
    temp_return_feed_max: Annotated[
        float | None, Field(description="Maximum return feed temperature (unit: ˚C)", gt=0)
    ] = None
    test_data_en14825: Annotated[
        list[HeatPumpTestDatum],
        Field(alias="test_data_EN14825", description="EN14825 test data for the heat pump"),
    ]
    time_constant_onoff_operation: Annotated[
        float, Field(description="Time constant for on/off operation (unit: seconds)", gt=0)
    ]
    time_delay_backup: Annotated[
        float | None, Field(description="Time delay before backup operation (unit: hours)", ge=0)
    ] = None
    var_flow_temp_ctrl_during_test: Annotated[
        bool, Field(description="Whether variable flow temperature control was used during testing")
    ]

    @model_validator(mode="after")
    def validate_backup_configuration(self):
        if self.boiler is not None and self.power_max_backup is not None:
            raise ValueError("power_max_backup and boiler can not both be set.")
        if self.backup_ctrl_type is HeatPumpBackupControlType.NONE:
            if self.boiler is not None:
                raise ValueError("boiler can not be set if backup_ctrl_type is 'None'.")
            if self.power_max_backup is not None:
                raise ValueError("power_max_backup can not be set if backup_ctrl_type is 'None'.")
        else:
            if self.time_delay_backup is None:
                raise ValueError("time_delay_backup is required if backup_ctrl_type is set.")
            if self.boiler is None and self.power_max_backup is None:
                raise ValueError(
                    "Either power_max_backup or boiler is required if backup_ctrl_type is set."
                )
        return self  # Valid


HeatSourceWet = Annotated[
    HeatSourceWetHeatPump | HeatSourceWetBoiler | HeatSourceWetHeatBattery | HeatSourceWetHIU,
    Field(discriminator="type"),
]


class InfiltrationVentilation(StrictBaseModel):
    control_vent_adjust_max: Annotated[
        ControlReference | None, Field(alias="Control_VentAdjustMax")
    ] = None
    control_vent_adjust_min: Annotated[
        ControlReference | None, Field(alias="Control_VentAdjustMin")
    ] = None
    control_window_adjust: Annotated[
        ControlReference | None, Field(alias="Control_WindowAdjust")
    ] = None
    leaks: Annotated[
        VentilationLeaks, Field(alias="Leaks", description="List of the required inputs for Leaks")
    ]
    mechanical_ventilation: Annotated[
        dict[str, MechanicalVentilation] | None,
        Field(
            alias="MechanicalVentilation",
            description="Provides details about available mechanical ventilation systems",
        ),
    ] = None
    vents: Annotated[
        dict[str, Vent],
        Field(
            alias="Vents",
            description="Provides details about available non-mechanical ventilation systems",
        ),
    ]
    ach_max_static_calcs: Annotated[
        float | None,
        Field(
            description="Maximum ACH (Air Changes per Hour) limit",
            ge=0,
            title="ACH Maximum Static Calcs",
        ),
    ] = None
    ach_min_static_calcs: Annotated[
        float | None,
        Field(
            description="Minimum ACH (Air Changes per Hour) limit",
            ge=0,
            title="ACH Minimum Static Calcs",
        ),
    ] = None
    altitude: Annotated[float, Field(description="Altitude of dwelling above sea level (unit: m)")]
    cross_vent_possible: bool
    shield_class: Annotated[
        VentilationShieldClass,
        Field(
            description="Indicates the exposure to wind of an air flow path on a facade (can can be open, normal and shielded)"
        ),
    ]
    terrain_class: TerrainClass
    ventilation_zone_base_height: Annotated[
        float,
        Field(description="Base height of the ventilation zone relative to ground (unit: m)"),
    ]
    vent_opening_ratio_init: Annotated[
        FloatBetween0and1 | None,
        Field(
            description="Initial vent position, 0 = vents closed and 1 = vents fully open",
        ),
    ] = None


class StorageTank(StrictBaseModel):
    type: Literal[HotWaterSourceType.STORAGE_TANK]
    cold_water_source: ColdWaterSourceReference
    heat_source: Annotated[
        dict[str, HotWaterHeatSource],
        Field(
            alias="HeatSource",
            description="Dictionary of heating systems connected to the storage tank",
        ),
    ]
    daily_losses: Annotated[
        float,
        Field(
            description="Measured standby losses due to cylinder insulation at standardised conditions (unit: kWh/24h)",
            gt=0,
        ),
    ]
    heat_exchanger_surface_area: Annotated[
        float | None,
        Field(
            description="Surface area of the heat exchanger within the storage tank (unit: m²)",
            gt=0,
        ),
    ] = None
    init_temp: Annotated[
        RunningWaterTemperature,
        Field(
            description="Initial temperature of the storage tank at the start of simulation (unit: ˚C)"
        ),
    ]
    primary_pipework: Annotated[
        list[WaterPipework] | None,
        Field(description="List of primary pipework components connected to the storage tank"),
    ] = None
    volume: Annotated[
        float,
        Field(
            description="Total volume of tank (unit: litre)",
            gt=0,
        ),
    ]


class Zone(StrictBaseModel):
    building_element: Annotated[
        dict[str, BuildingElement],
        Field(
            alias="BuildingElement",
            description="Dictionary of building elements present in the zone (e.g. walls, floors, windows, etc.).",
        ),
    ]
    space_cool_system: Annotated[
        str | UniqueStringList | None,
        Field(
            alias="SpaceCoolSystem",
            description="Cooling system details of the zone. References a key in $.SpaceCoolSystem",
        ),
    ] = None
    space_heat_system: Annotated[
        str | UniqueStringList | None,
        Field(
            alias="SpaceHeatSystem",
            description="Heating system details of the zone. References a key in $.SpaceHeatSystem",
        ),
    ] = None
    thermal_bridging: Annotated[
        float | dict[str, ThermalBridging],
        Field(
            alias="ThermalBridging",
            description="Overall heat transfer coefficient of the thermal bridge (in W/K), or dictionary of linear thermal transmittance details of the thermal bridges in the zone.",
        ),
    ]
    area: Annotated[float, Field(description="Useful floor area of the zone. (Unit: m²)", gt=0)]
    temp_setpnt_basis: Annotated[
        ZoneTemperatureControlBasis | None,
        Field(description="Basis for zone temperature control."),
    ] = None
    temp_setpnt_init: Annotated[
        DegreesCelsius,
        Field(description="Setpoint temperature to use during initialisation (unit: ˚C)"),
    ]
    volume: Annotated[float, Field(description="Total volume of the zone. (Unit: m³)", gt=0)]

    @field_validator("space_heat_system", "space_cool_system", mode="before")
    @classmethod
    def validate_system_list_no_duplicates(cls, value, info):
        """Validate that space heat and cool system lists have no duplicate entries."""
        if value is not None and isinstance(value, list):
            if len(value) != len(set(value)):
                raise ValueError(f"Invalid input: duplicate entry in {info.field_name} list")
        return value


HotWaterSourceDetails = Annotated[
    StorageTank
    | HotWaterSourceCombiBoiler
    | HotWaterSourceHUI
    | HotWaterSourcePointOfUse
    | HotWaterSourceSmartHotWaterTank
    | HotWaterSourceHeatBattery,
    Field(discriminator="type"),
]


class InternalGainsDetails(TimeSeriesBase):
    schedule: ScheduleForDouble


class InternalGains(RootModel[dict[str, InternalGainsDetails]]):
    """
    A dictionary of internal gains entries where:
    - Keys are user-defined names (e.g., "ColdWaterLosses", "EvaporativeLosses", "metabolic gains", etc.)
    - Values conform to the InternalGainsDetails schema
    - No specific entries are required - all entries are optional and user-defined
    - Note: Despite the name, this container includes both gains and losses
    """

    root: dict[str, InternalGainsDetails]

    # Optional convenience properties for backward compatibility with common field names
    @property
    def cold_water_losses(self) -> InternalGainsDetails | None:
        return self.root.get("ColdWaterLosses")

    @property
    def evaporative_losses(self) -> InternalGainsDetails | None:
        return self.root.get("EvaporativeLosses")

    @property
    def metabolic_gains(self) -> InternalGainsDetails | None:
        return self.root.get("metabolic gains")

    @property
    def other(self) -> InternalGainsDetails | None:
        return self.root.get("other")

    @property
    def total_internal_gains_1(self) -> InternalGainsDetails | None:
        return self.root.get("total internal gains") or self.root.get("total_internal_gains")


class Input(StrictBaseModel):
    metadata: Annotated[Metadata | None, Field(description="Metadata for the input file")] = None
    appliance_gains: Annotated[dict[str, ApplianceGains] | None, Field(alias="ApplianceGains")] = (
        None
    )
    cold_water_source: Annotated[dict[str, ColdWaterSource], Field(alias="ColdWaterSource")]
    control: Annotated[dict[str, Control] | None, Field(alias="Control")]
    energy_supply: Annotated[dict[str, EnergySupply], Field(alias="EnergySupply")]
    events: Annotated[WaterHeatingEvents, Field(alias="Events")]
    external_conditions: Annotated[ExternalConditionsInput, Field(alias="ExternalConditions")]
    heat_source_wet: Annotated[
        dict[str, HeatSourceWet] | None,
        Field(
            None,
            alias="HeatSourceWet",
            description="Dictionary of available wet heat sources, keyed by user-defined names (e.g., 'boiler', 'hp', 'HeatNetwork', 'hb1'). Other models reference these keys via their heat_source_wet fields.",
        ),
    ] = None
    hot_water_demand: Annotated[HotWaterDemand, Field(alias="HotWaterDemand")]
    hot_water_source: Annotated[dict[str, HotWaterSourceDetails], Field(alias="HotWaterSource")]
    infiltration_ventilation: Annotated[
        InfiltrationVentilation, Field(alias="InfiltrationVentilation")
    ]
    internal_gains: Annotated[InternalGains, Field(alias="InternalGains")]

    on_site_generation: Annotated[
        dict[str, OnSiteGeneration] | None, Field(alias="OnSiteGeneration")
    ] = None
    pre_heated_water_source: Annotated[
        dict[str, StorageTank] | None, Field(alias="PreHeatedWaterSource")
    ] = None
    simulation_time: Annotated[SimulationTime, Field(alias="SimulationTime")]
    smart_appliance_controls: Annotated[
        dict[str, SmartApplianceControl] | None, Field(alias="SmartApplianceControls")
    ] = None
    space_cool_system: Annotated[
        dict[str, SpaceCoolSystem] | None, Field(alias="SpaceCoolSystem")
    ] = None
    space_heat_system: Annotated[
        dict[str, SpaceHeatSystem] | None, Field(alias="SpaceHeatSystem")
    ] = None
    waste_water_heat_recovery_systems: Annotated[
        dict[str, WasteWaterHeatRecoverySystem] | None, Field(alias="WWHRS", title="WWHRS")
    ] = None
    zone: Annotated[dict[str, Zone], Field(alias="Zone")]
    temp_internal_air_static_calcs: float

    @model_validator(mode="after")
    def validate_cross_references(self) -> Self:
        errors: list[InitErrorDetails] = Input._validate_cross_references_recursively(
            current_input=self, root_input=self
        )
        if errors:
            raise ValidationError.from_exception_data(title="Input", line_errors=errors)
        return self

    @staticmethod
    def _validate_cross_references_recursively(
        current_input: StrictBaseModel, root_input: StrictBaseModel
    ) -> list[InitErrorDetails]:
        """Recursive function to loop through all inputs' fields.
        Check if the field references something in Input and if it does, validates whether the reference exists or not.
        This function will return a list of PydanticCustomError for each rogue reference.
        """
        errors: list[InitErrorDetails] = []
        for attr, field_info in current_input.__class__.model_fields.items():
            # does this field have references to check?
            Input._check_for_references(attr, field_info, current_input, root_input, errors)
            # whether it does or not, keep looping through the fields and subfields
            field = getattr(current_input, attr)
            if type(field) is dict:
                for _, obj in field.items():
                    if isinstance(obj, StrictBaseModel):
                        errors.extend(
                            Input._validate_cross_references_recursively(
                                current_input=obj, root_input=root_input
                            )
                        )
            elif isinstance(field, StrictBaseModel):
                errors.extend(
                    Input._validate_cross_references_recursively(
                        current_input=field, root_input=root_input
                    )
                )
        return errors

    @staticmethod
    def _check_for_references(
        field_name: str,
        field_info: FieldInfo,
        current_input: StrictBaseModel,
        root_input: StrictBaseModel,
        errors: list,
    ):
        references_to = Input._find_reference_to(field_info, field_name, current_input)
        if references_to is not None:
            # since it's a reference field, we know it has to be either str or set
            reference_keys: str | set = getattr(current_input, field_name)
            if reference_keys is not None:
                # some inputs can have a set of references, cast any str into a set to harmonise
                if isinstance(reference_keys, str):
                    reference_keys = {reference_keys}

                for reference_key in reference_keys:
                    try:
                        Input._validate_reference(
                            reference_key=reference_key,
                            references_to=references_to,
                            root_input=root_input,
                        )
                    except ValueError:
                        context_root_input_error = " or ".join(
                            f"Input.{reference_to.replace('$.', '')}"
                            for reference_to in references_to
                        )
                        errors.append(
                            InitErrorDetails(
                                type=PydanticCustomError(
                                    "value_error",
                                    'Provided {input}.{field_name} key ("{reference_key}") does not exist in {root_input_error}',
                                    {
                                        "reference_to": references_to,
                                        "reference_key": reference_key,
                                        "input": type(current_input).__name__,
                                        "field_name": field_name,
                                        "root_input_error": context_root_input_error,
                                    },
                                ),
                                loc=(f"{type(current_input).__name__}.{field_name}",),
                                input=reference_key,
                            )
                        )

    @staticmethod
    def _find_reference_to(
        field_info: FieldInfo, field_name: str, current_input: StrictBaseModel
    ) -> list[str] | None:
        if hasattr(field_info, "json_schema_extra") and field_info.json_schema_extra:
            if (
                isinstance(field_info.json_schema_extra, dict)
                and "reference_to" in field_info.json_schema_extra
            ):
                if isinstance(field_info.json_schema_extra["reference_to"], str):
                    return [str(field_info.json_schema_extra["reference_to"])]
                elif isinstance(field_info.json_schema_extra["reference_to"], list):
                    return [str(x) for x in field_info.json_schema_extra["reference_to"]]
                else:
                    return None  # pragma: nocover
        elif get_origin(field_info) is Annotated:
            for sub_annotation in get_args(field_info):
                if isinstance(sub_annotation, FieldInfo):
                    return Input._find_reference_to(sub_annotation, field_name, current_input)
        elif get_origin(field_info.annotation) is Union:
            for union_arg in get_args(field_info.annotation):
                if get_origin(union_arg) is Annotated:
                    for sub_annotation in get_args(union_arg):
                        if isinstance(sub_annotation, FieldInfo):
                            return Input._find_reference_to(union_arg, field_name, current_input)
        return None

    @staticmethod
    def _validate_reference(
        reference_key: str, references_to: list[str], root_input: StrictBaseModel
    ):
        """Check if the value (e.g. "mains elec") actually exists in Input (e.g. Input.energy_supply)"""
        found: bool = False
        for reference_to in references_to:
            # treat reference_to as a path
            parts = reference_to.split(".")
            references = getattr(root_input, parts[1])  # ignore the $ in the path
            for part in parts[2:]:
                references = getattr(references, part)
            if references is not None and reference_key in references:
                found = True
                break

        if found is not True:
            raise InputFieldReferenceIntegrityError(
                f'"{reference_key}" {references_to} key does not exist in Input.{references_to}'
            )

    @model_validator(mode="after")
    def validate_shower_waste_water_heat_recovery_systems(self) -> Self:
        # Validate that showers point to a valid WWHRS key.
        if self.hot_water_demand.shower:
            for shower_name, shower in self.hot_water_demand.shower.items():
                if (
                    isinstance(shower, ShowerMixer)
                    and shower.waste_water_heat_recovery_system is not None
                    and shower.waste_water_heat_recovery_system
                    not in (self.waste_water_heat_recovery_systems or {})
                ):
                    raise ValueError(
                        f"WWHRS value '{shower.waste_water_heat_recovery_system}' not found in Input.WWHRS (from Input.HotWaterDemand.Shower['{shower_name}'].WWHRS)"
                    )
        return self  # Valid

    @model_validator(mode="after")
    def validate_exhaust_air_heat_pump_ventilation_compatibility(self) -> Self:
        """Validate that exhaust air heat pumps are compatible with ventilation systems."""
        # Early return if no mechanical ventilation or heat pumps
        if (
            self.infiltration_ventilation.mechanical_ventilation is None
            or self.heat_source_wet is None
        ):
            return self

        incompatible_vent_types = {
            MechVentType.INTERMITTENT_MEV,
            MechVentType.DECENTRALISED_CONTINUOUS_MEV,
        }

        exhaust_air_source_types = {
            HeatPumpSourceType.EXHAUST_AIR_MEV,
            HeatPumpSourceType.EXHAUST_AIR_MVHR,
            HeatPumpSourceType.EXHAUST_AIR_MIXED,
        }

        exhaust_air_heat_pumps = [
            (hp_name, hp_data.source_type)
            for hp_name, hp_data in self.heat_source_wet.items()
            if (
                hp_data.type == HeatSourceWetType.HEAT_PUMP
                and hp_data.source_type in exhaust_air_source_types
            )
        ]

        if not exhaust_air_heat_pumps:
            return self

        incompatible_vents = [
            (vent_name, vent_data.vent_type)
            for vent_name, vent_data in self.infiltration_ventilation.mechanical_ventilation.items()
            if vent_data.vent_type in incompatible_vent_types
        ]

        if incompatible_vents and exhaust_air_heat_pumps:
            incompatibilities = [
                f"Exhaust air heat pump '{hp_name}' (source type: {source_type}) "
                f"is incompatible with ventilation system '{vent_name}' "
                f"(vent type: {vent_type})"
                for hp_name, source_type in exhaust_air_heat_pumps
                for vent_name, vent_type in incompatible_vents
            ]
            raise IncompatibleSystemError(
                f"System incompatibilities found: {'; '.join(incompatibilities)}. "
                "Exhaust air heat pumps do not work with Intermittent MEV or "
                "Decentralised continuous MEV."
            )

        return self

    @model_validator(mode="after")
    def validate_time_series(self) -> Self:
        for cold_water_source in self.cold_water_source.values():
            total_steps = math.ceil(
                (self.simulation_time.end - self.simulation_time.start)
                / cold_water_source.time_series_step
            )
            if len(cold_water_source.temperatures) < total_steps:
                raise ValueError(
                    "ColdWaterSource.temperatures does not contain enough values to cover the simulation."
                )

        return self
