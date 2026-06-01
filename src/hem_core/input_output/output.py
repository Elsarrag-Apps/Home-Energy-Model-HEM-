from functools import cached_property
from types import NoneType
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, computed_field

from hem_core.input_output.input import DegreesCelsius, FloatBetween0and1

EnergySupplyKey = Annotated[str, Field(description="Energy supply key")]
EndUseKey = Annotated[str, Field(description="Energy end use key")]
FuelKey = Annotated[str, Field(description="Fuel key")]
# NB: Output fuel key strings are different from the input FuelType...
HeatSourceWetKey = Annotated[str, Field(description="Heat source wet key")]
HotWaterSourceKey = Annotated[str, Field(description="Hot water source key")]
SpaceHeatingSystemKey = Annotated[str, Field(description="Space heating system key")]
ZoneKey = Annotated[str, Field(description="Zone key")]


class StrictBaseModel(BaseModel):
    """Base model class that forbids extra fields by default."""

    model_config = ConfigDict(extra="forbid")


class OutputStatic(StrictBaseModel):
    heat_transfer_coefficient: Annotated[
        float, Field(description="Heat transfer coefficient (unit: W/K)")
    ]
    heat_loss_param: Annotated[float, Field(description="Heat loss parameter (unit: W/m².K)")]
    heat_capacity_param: Annotated[
        float,
        Field(description="Heat capacity parameter (unit: kJ/m².K)"),
    ]
    heat_loss_form_factor: Annotated[float, Field(description="Heat loss form factor")]
    temperature_air_internal: Annotated[
        DegreesCelsius,
        Field(description="Internal air temperature (unit: ˚C)"),
    ]
    temperature_air_external: Annotated[
        float, Field(description="External air temperature (unit: ˚C)")
    ]


class OutputZoneData(StrictBaseModel):
    """
    Zone output data. Each field is keyed by zone name.
    These fields names are used in the core output file (substituting " " for "_")
    """

    # NB: Field order is important as it affects the output files.
    internal_gains: Annotated[
        dict[ZoneKey, list[float]], Field(description="Internal gains (unit: W)")
    ]
    solar_gains: Annotated[dict[ZoneKey, list[float]], Field(description="Solar gains (unit: W)")]
    operative_temp: Annotated[
        dict[ZoneKey, list[float]], Field(description="Operative temperature (unit: ˚C)")
    ]
    internal_air_temp: Annotated[
        dict[ZoneKey, list[float]], Field(description="Internal air temperature (unit: ˚C)")
    ]
    space_heat_demand: Annotated[
        dict[ZoneKey, list[float]], Field(description="Space heat demand (unit: kWh)")
    ]
    space_cool_demand: Annotated[
        dict[ZoneKey, list[float]], Field(description="Space cool demand (unit: kWh)")
    ]


class OutputHeatingCoolingSystem(StrictBaseModel):
    """
    Contains the output timeseries for the heating and cooling systems, respectively.
    """

    heating_system_output: Annotated[
        dict[str | None, list[float]],
        Field(description="Heating system output, for each heating system (unit: kWh)"),
    ]
    cooling_system_output: Annotated[
        dict[str | None, list[float]],
        Field(description="Cooling system output, keyed by cooling system name (unit: kWh)"),
    ]


class OutputHotWaterSystems(StrictBaseModel):
    """
    Hot water systems data for every time step.
    """

    model_config = ConfigDict(
        validate_by_name=True,
        serialize_by_alias=False,  # Prevent serialising JSON with the verbose aliases. These are for the CSV headers.
    )

    # NB: Field order is important as it affects the output files.
    # Each field's alias is the heading to use in the core output CSV.
    demand: Annotated[
        dict[str, list[float]],
        Field(
            description="Hot water volume required from hot water source, for each hot water source (unit: litres)",
            alias="hot water volume required from hot water source",
        ),
    ]
    energy_demand_at_hot_water_source: Annotated[
        dict[str, list[float]],
        Field(
            description="Hot water energy demand at hot water source, for each hot water source (unit: kWh)",
            alias="hot water energy demand at hot water source",
        ),
    ]
    energy_demand_at_tapping_points: Annotated[
        dict[str, list[float]],
        Field(
            description="Hot water energy demand at connected tapping points, for each hot water source (unit: kWh)",
            alias="hot water energy demand at connected tapping points",
        ),
    ]
    duration: Annotated[
        dict[str, list[float]],
        Field(
            description="Total hot water event duration, for each hot water source (unit: minutes)",
            alias="total event duration",
        ),
    ]
    events_count: Annotated[
        dict[str, list[int]],
        Field(
            description="Number of hot water events, for each hot water source (unit: count)",
            alias="number of events",
        ),
    ]
    losses_pipework: Annotated[
        dict[str, list[float]],
        Field(
            description="Pipework losses, for each hot water source (unit: kWh)",
            alias="distribution pipework losses",
        ),
    ]
    losses_primary_pipework: Annotated[
        dict[str, list[float]],
        Field(
            description="Primary pipework losses, for each hot water source (unit: kWh)",
            alias="primary pipework losses",
        ),
    ]
    losses_storage: Annotated[
        dict[str, list[float]],
        Field(
            description="Storage losses, for each hot water source (unit: kWh)",
            alias="storage losses",
        ),
    ]


class OutputCOP(StrictBaseModel):
    """
    Coefficients of performance for space heating & cooling, and hot water systems.
    Null-values are used when a divide-by-zero occurs in the results. These are output as "DIV/0" in the CSVs.
    """

    space_heating_system: Annotated[
        dict[str, float | None],
        Field(description="Overall coefficient of performance for each heating system (unitless)"),
    ]
    space_cooling_system: Annotated[
        dict[str, float | None],
        Field(description="Overall coefficient of performance for each heating system (unitless)"),
    ]
    hot_water_system: Annotated[
        dict[str, float | None],
        Field(description="Overall coefficient of performance for each heating system (unitless)"),
    ]


class OutputEmitters(StrictBaseModel):
    """
    Emitters data for every time step.
    """

    simulation_time_idx: Annotated[int, Field(description="Current time step", ge=0)]
    energy_demand: Annotated[float, Field(description="Energy demand (unit: kWh)", ge=0)]
    temp_emitter_required: Annotated[
        float,
        Field(
            description="Required emitter temperature to satisfy zone setpoint (unit: Celsius)",
            ge=0,
        ),
    ]
    time_heating_start: Annotated[
        float, Field(description="Time at which the emitter begins operating", ge=0)
    ]
    energy_provided_by_heat_source: Annotated[
        float, Field(description="Energy provided by heat source (unit: kWh)", ge=0)
    ]
    temp_emitter: Annotated[
        float | str, Field(description="Temperature of the emitter (unit: Celsius)")
    ]
    temp_emitter_max: Annotated[
        float,
        Field(description="Maximum temperature the emitter can safely reach (unit: Celsius)", ge=0),
    ]
    energy_released_from_emitters: Annotated[
        float, Field(description="Energy released from emitters (unit: kWh)")
    ]
    temp_flow_target: Annotated[
        float, Field(description="Desired supply temperature to the emitter (unit: Celsius)", ge=0)
    ]
    temp_return_target: Annotated[
        float,
        Field(description="Desired return temperature from the emitter (unit: Celsius)", ge=0),
    ]
    temp_emitter_max_is_final_temp: Annotated[
        bool,
        Field(
            description="Whether the maximum emitter temperature is used as the final supply temperature"
        ),
    ]
    energy_required_from_heat_source: Annotated[
        float, Field(description="Energy required from the heat source (unit: kWh)", ge=0)
    ]
    fan_energy_kWh: Annotated[
        float, Field(description="Fan electricity consumption (unit: kWh)", ge=0)
    ]


class OutputCore(StrictBaseModel):
    """
    The raw HEM Core outputs, from Project.run()

    For the _unmet_demand energy supply object, end-uses are:
        - space heating or cooling per zone, where the naming convention is _unmet_demand: [zone name from input]
        - water heating unmet demand, where the naming convention is _unmet_demand: [hot water source names from input]

    For all other energy supplies, end-use names refer to specific systems or appliances specified in the input file.
    """

    timestep_array: Annotated[
        list[float],
        Field(
            description="The list of timesteps, serves as an index for the other outputs (unit: Hours)"
        ),
    ]
    results_totals: Annotated[
        dict[EnergySupplyKey, list[float]], Field(description="Total energy (unit: kWh)")
    ]
    results_end_user: Annotated[
        dict[EnergySupplyKey, dict[EndUseKey, list[float]]],
        Field(description="Energy per supply, per end use (unit: kWh)"),
    ]
    energy_import: Annotated[
        dict[EnergySupplyKey, list[float]],
        Field(
            description="Total energy imported from the grid, including both direct consumption and battery charging (unit: kWh)"
        ),
    ]
    energy_export: Annotated[
        dict[EnergySupplyKey, list[float]],
        Field(description="Total energy exported to the grid (unit: kWh)"),
    ]
    grid_to_consumption: Annotated[
        dict[EnergySupplyKey, list[float]],
        Field(
            description="Energy imported from the grid directly to consumption. Does not include grid to battery charging (unit: kWh)"
        ),
    ]
    generation_to_grid: Annotated[
        dict[EnergySupplyKey, list[float]],
        Field(description="On-site generation immediately exported to the grid (unit: kWh)"),
    ]
    energy_generated_consumed: Annotated[
        dict[EnergySupplyKey, list[float]],
        Field(
            description="On-site generation immediately consumed within the dwelling. Does not include energy via storage or PV diverter (unit: kWh)"
        ),
    ]
    energy_to_storage: Annotated[
        dict[EnergySupplyKey, list[float]],
        Field(
            description="Energy from on-site generation to storage. Does not include energy from the grid to storage (unit: kWh)"
        ),
    ]
    energy_from_storage: Annotated[
        dict[EnergySupplyKey, list[float]],
        Field(description="Energy discharged from storage to consumption (unit: kWh)"),
    ]
    storage_from_grid: Annotated[
        dict[EnergySupplyKey, list[float]],
        Field(
            description="Energy imported from the grid to storage. Does not include energy from on-site generation to storage (unit: kWh)"
        ),
    ]
    battery_state_of_charge: Annotated[
        dict[EnergySupplyKey, list[FloatBetween0and1]],
        Field(description="Battery charge level (unit: ratio 0 to 1)"),
    ]
    energy_diverted: Annotated[
        dict[EnergySupplyKey, list[float]],
        Field(
            description="Surplus on-site generation diverted to PV diverter, e.g. immersion heater (unit: kWh)"
        ),
    ]
    beta_factor: Annotated[
        dict[EnergySupplyKey, list[float]],
        Field(
            description="Fraction of on-site generation immediately consumed within the dwelling. Does not include energy to storage or diverters (unit: ratio 0 to 1)"
        ),
    ]
    zone_list: Annotated[
        list[ZoneKey], Field(description="List of the unique zone names in the zone data")
    ]
    zone_data: OutputZoneData
    heating_cooling_system: OutputHeatingCoolingSystem
    cop: OutputCOP
    ductwork_gains: Annotated[
        list[float], Field(description="Ventilation ductwork gains (unit: W)")
    ]
    heat_balance_all: Annotated[
        dict[str, dict[ZoneKey, dict[str, list[float]]]],
        Field(description="Heat balance data for each zone."),
    ]
    heat_source_wet_results: Annotated[
        dict[HeatSourceWetKey, dict[str, list[float] | dict]],
        Field(description="Heat source wet detailed results."),
    ]
    heat_source_wet_results_annual: Annotated[
        dict[HeatSourceWetKey, dict[str, float | dict]],
        Field(description="Annual heat source wet detailed results."),
        # TODO Define an Output class and return from:
        #      HeatPump.output_detailed_results
        #      HeatBattery.output_detailed_results
    ]
    hot_water_source_results: Annotated[
        dict[HotWaterSourceKey, list[list[str | float | NoneType]]],
        Field(
            description="""
                Hot water source results.
                Currently unstructured, see CSV for column-order.
                """
        ),
        # TODO Define an Output class and return from StorageTank.output_results
    ]
    emitters: Annotated[
        dict[SpaceHeatingSystemKey, dict[int, OutputEmitters]],
        Field(
            description="""
            Heating system emitters detailed outputs.
            Currently unstructured, see CSV for column-order.
            """
        ),
        # TODO Define an Output class and return from Emitters.output_emitter_results
    ]
    electric_storage_heaters: Annotated[
        dict[SpaceHeatingSystemKey, dict[int, list[float]]],
        Field(
            description="""
            Electric storage heaters detailed outputs.
            Currently unstructured, see CSV for column-order.
            """
        ),
        # TODO Define an Output class and return from ElecStorageHeater.output_esh_results
    ]
    ventilation: Annotated[
        list[list[float | str]],
        Field(
            description="""
            Ventilation detailed outputs.
            Currently unstructured, see CSV for column-order.
            """
        ),
        # TODO Define an Output class and return from InfiltrationVentilation.output_vent_results
    ]
    hot_water_systems: OutputHotWaterSystems


class OutputSummaryPeakElectricityConsumption(StrictBaseModel):
    """
    Details of the time-step with the peak electricity consumption within the simulation.
    """

    peak: Annotated[
        float,
        Field(description="The maximum electricity consumption (unit: kWh)"),
    ]
    index: Annotated[int, Field(description="The time step the peak occurred at")]
    month: Annotated[
        int,
        Field(
            ge=1,
            le=12,
            description="The month the peak occurred in, where 1 = January",
        ),
    ]
    day: Annotated[
        int,
        Field(
            ge=1,
            le=31,
            description="The day of the month the peak occurred on (values start from 1)",
        ),
    ]
    hour: Annotated[
        float,
        Field(
            ge=0,
            lt=24,
            description="The hour of the day the peak occurred on (values start from 0). Decimal-time is used if the simulation step is less than 1 hour.",
        ),
    ]


class OutputSummaryEnergySupply(StrictBaseModel):
    generation: Annotated[
        float,
        Field(description="All energy generated on site (unit: kWh)"),
    ]
    consumption: Annotated[
        float,
        Field(
            description="All energy consumed for space and water heating, appliances and cooking (unit: kWh)"
        ),
    ]
    generation_to_consumption: Annotated[
        float,
        Field(
            description="Total on-site generation immediately consumed within the dwelling. Does not include energy via storage or PV diverter (unit: kWh)"
        ),
    ]
    generation_to_grid: Annotated[
        float,
        Field(description="Total on-site generation immediately exported to the grid (unit: kWh)"),
    ]
    generation_to_diverter: Annotated[
        float,
        Field(
            description="Total surplus on-site generation diverted to PV diverter, e.g. immersion heater (unit: kWh)"
        ),
    ]
    grid_to_consumption: Annotated[
        float,
        Field(
            description="Total energy imported from the grid directly to consumption. Does not include grid to battery charging (unit: kWh)"
        ),
    ]
    grid_to_storage: Annotated[
        float,
        Field(
            description="Total energy imported from the grid to storage. Does not include on-site generation to storage (unit: kWh)"
        ),
    ]
    generation_to_storage: Annotated[
        float,
        Field(
            description="Total on-site generation put into storage. Does not include energy from the grid to storage (unit: kWh)"
        ),
    ]
    storage_to_consumption: Annotated[
        float,
        Field(description="Total energy discharged from storage to consumption (unit: kWh)"),
    ]
    storage_efficiency: Annotated[
        float | None,
        Field(
            description="Storage round-trip efficiency: total energy discharged from storage divided by total energy put into storage from both grid and on-site generation (unit: ratio)"
        ),
    ]
    net_import: Annotated[
        float,
        Field(description="Net import: total gross import minus total gross export (unit: kWh)"),
    ]
    total_gross_import: Annotated[
        float,
        Field(
            description="Total energy imported from the grid, including both direct consumption and battery charging (unit: kWh)"
        ),
    ]
    total_gross_export: Annotated[
        float,
        Field(description="Total energy exported to the grid (unit: kWh)"),
    ]


class OutputSummary(StrictBaseModel):
    """
    Summary outputs from HEM Core.
    """

    total_floor_area: Annotated[
        float, Field(description="Total floor-area of all zones (unit: m²", gt=0)
    ]
    space_heat_demand_total: Annotated[
        float,
        Field(description="Space heating demand total (unit: kWh)"),
    ]
    space_cool_demand_total: Annotated[
        float,
        Field(description="Space cooling demand total (unit: kWh)"),
    ]
    electricity_peak_consumption: OutputSummaryPeakElectricityConsumption
    energy_supply: dict[EnergySupplyKey, OutputSummaryEnergySupply]
    delivered_energy: Annotated[
        dict[FuelKey, dict[EndUseKey, float]],
        Field(
            description="Delivered energy summary, total energy per fuel and end-use (unit: kWh)"
        ),
    ]
    hot_water_demand_daily_75th_percentile: Annotated[
        dict[HotWaterSourceKey, float],
        Field(
            description="75th percentile of hot water demand summed over each 24 hour segment of the simulation."
        ),
    ]

    @computed_field(description="Space heating demand total per floor-area (unit: kWh/m²)")
    @property
    def space_heat_demand_by_floor_area(self) -> float:
        return self.space_heat_demand_total / self.total_floor_area

    @computed_field(description="Space cooling demand total per floor-area (unit: kWh/m²)")
    @property
    def space_cool_demand_by_floor_area(self) -> float:
        return self.space_cool_demand_total / self.total_floor_area

    @computed_field(description="Delivered energy summary by floor-area (unit: kWh/m²)")
    @cached_property
    def delivered_energy_by_floor_area(self) -> dict[FuelKey, dict[EndUseKey, float]]:
        return {
            fuel: {
                end_use: energy / self.total_floor_area for end_use, energy in end_use_dict.items()
            }
            for fuel, end_use_dict in self.delivered_energy.items()
        }


class OutputMetadata(StrictBaseModel):
    hem_core_version: str


class Output(StrictBaseModel):
    static: OutputStatic
    core: OutputCore
    summary: OutputSummary
    metadata: OutputMetadata
