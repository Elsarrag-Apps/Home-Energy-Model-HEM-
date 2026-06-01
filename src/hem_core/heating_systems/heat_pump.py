"""
This module provides objects to represent heat pumps and heat pump test data.
The calculations are based on the DAHPSE method developed for generating PCDB
entries for SAP 2012 and SAP 10. DAHPSE was based on a draft of
BS EN 15316-4-2:2017 and is described in the SAP calculation method CALCM-01.
"""

import logging
import math
from copy import deepcopy
from enum import Enum, auto
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Callable,
    NotRequired,
    Protocol,
    TypedDict,
)

import numpy as np
from numpy.polynomial.polynomial import polyfit
from pydantic import Field

from hem_core.controls.time_control import (
    CombinationTimeControl,
    SetpointTimeControl,
    TimeControl,
)
from hem_core.energy_supply.energy_supply import EnergySupply, EnergySupplyConnection
from hem_core.external_conditions import ExternalConditions
from hem_core.heating_systems._base import SpaceHeatSystem
from hem_core.heating_systems.boiler import (
    Boiler,
    BoilerServiceSpace,
    BoilerServiceWaterCombi,
    BoilerServiceWaterRegular,
)
from hem_core.heating_systems.enums import HeatingServiceType, SourceType
from hem_core.input_output.enums import HeatPumpBackupControlType, HeatPumpSinkType
from hem_core.material_properties import WATER, MaterialProperties
from hem_core.schedule import expand_schedule, validate_schedule_length
from hem_core.simulation_time import SimulationTime
from hem_core.units import (
    Celcius2Kelvin,
    Kelvin2Celcius,
    W_per_kW,
    hours_per_day,
    kJ_per_kWh,
    seconds_per_minute,
)
from hem_core.water_heat_demand.cold_water_source import ColdWaterSource

from ._base import HeatSourceBase

logger = logging.getLogger(__name__)

# Constants
N_EXER = 3.0


class SimulationProject(Protocol):
    def temp_internal_air_prev_timestep(self) -> float: ...


class HeatPumpEmitterType(Enum):
    RADIATORS_UFH = auto()
    FAN_COILS = auto()
    WARM_AIR = auto()


class HeatPumpData(TypedDict):
    """Dictionary of heat pump test data."""

    air_flow_rate: NotRequired[float]
    test_letter: str
    capacity: float
    cop: float
    design_flow_temp: float  # in Celsius
    temp_outlet: float  # in Celsius
    temp_source: float  # in Celsius
    temp_test: float  # in Celsius
    eahp_mixed_ext_air_ratio: NotRequired[float]


class HeatPumpCharacteristics(TypedDict):
    test_data_EN14825: Annotated[
        list[HeatPumpData], Field(description="EN 14825 test data (list of dictionaries)")
    ]
    source_type: Annotated[
        SourceType | str, Field(description="String specifying heat source type")
    ]
    sink_type: Annotated[
        HeatPumpSinkType, Field(description="String specifying heat distribution type")
    ]
    backup_ctrl_type: Annotated[
        HeatPumpBackupControlType,
        Field(description="string specifying control arrangement for backup heater"),
    ]
    time_delay_backup: Annotated[
        float,
        Field(
            description="Time after which the backup heater will activate if demand has not been satisfied."
        ),
    ]
    modulating_control: Annotated[
        bool,
        Field(
            description="Boolean specifying whether or not the heat has controls capable of varying the output (as opposed to just on/off control)"
        ),
    ]
    time_constant_onoff_operation: Annotated[
        float,
        Field(
            description="A characteristic parameter of the heat pump, due to the inertia of the on/off transient"
        ),
    ]
    temp_return_feed_max: Annotated[
        float, Field(description="maximum allowable temperature of the return feed, in Celsius")
    ]
    temp_lower_operating_limit: Annotated[
        float,
        Field(
            description="minimum source temperature at which the heat pump can operate, in Celsius"
        ),
    ]
    min_temp_diff_flow_return_for_hp_to_operate: Annotated[
        float,
        Field(
            description="minimum difference between flow and return temperatures required for the HP to operate, in Celsius or Kelvin"
        ),
    ]
    var_flow_temp_ctrl_during_test: Annotated[
        bool,
        Field(
            description="boolean specifying whether or not variable flow temperature control was enabled during the EN 14825 tests"
        ),
    ]
    power_heating_circ_pump: Annotated[
        float, Field(description="Power (kW) of central heating circulation pump.")
    ]
    power_source_circ_pump: Annotated[
        float,
        Field(
            description="Power (kW) of source circulation pump or fan circulation when not implicit in CoP measurements"
        ),
    ]
    power_standby: Annotated[float, Field(description="Power (kW) consumption in standby mode")]
    power_crankcase_heater: Annotated[
        float, Field(description="Power (kW) consumption in crankcase heater mode")
    ]
    power_off: Annotated[float, Field(description="Power (kW) consumption in off mode.")]
    power_max_backup: Annotated[float, Field(description="Maximum power (kW) of backup heater")]
    temp_distribution_heat_network: Annotated[
        float,
        Field(
            description="distribution temperature of the heat network (for HPs that use heat network as heat source)"
        ),
    ]
    eahp_mixed_max_temp: float  # if source_type = SourceType.EXHAUST_AIR_MIXED
    eahp_mixed_min_temp: float  # if source_type = SourceType.EXHAUST_AIR_MIXED
    min_modulation_rate_20: float
    min_modulation_rate_35: float
    min_modulation_rate_55: float
    BufferTank: NotRequired["BufferTankCharacteristics"]


class BufferTankCharacteristics(TypedDict):
    daily_losses: float
    volume: float
    pump_fixed_flow_rate: float
    pump_power_at_flow_rate: float


class HWHeatPumpData(TypedDict):
    cop_dhw: Annotated[float, Field(description="CoP measured during EN 16147 test")]
    hw_tapping_prof_daily_total: Annotated[
        float,
        Field(description="Daily energy requirement (kWh/day) for tapping profile used for test"),
    ]
    energy_input_measured: Annotated[
        float,
        Field(description="Electrical input energy (kWh) measured in EN 16147 test over 24 hrs"),
    ]
    power_standby: Annotated[
        float, Field(description="Standby power (kW) measured in EN 16147 test")
    ]
    hw_vessel_loss_daily: Annotated[
        float,
        Field(
            description="""
                Daily hot water vessel heat loss
                (kWh/day) for a 45 K temperature difference between vessel
                and surroundings, tested in accordance with BS 1566 or
                EN 12897 or any equivalent standard. Vessel must be same
                as that used during EN 16147 test
            """
        ),
    ]


def carnot_cop(
    temp_source: float, temp_outlet: float, temp_diff_limit_low: float | None = None
) -> float:
    """Calculate Carnot CoP based on source and outlet temperatures (in Kelvin)"""
    temp_diff = temp_outlet - temp_source
    if temp_diff_limit_low is not None:
        temp_diff = max(temp_diff, temp_diff_limit_low)
    return temp_outlet / temp_diff


def interpolate_exhaust_air_heat_pump_test_data(
    throughput_exhaust_air: float,
    hp_test_data: list[HeatPumpData],
    source_type: SourceType,
) -> tuple[float, list[HeatPumpData]]:
    """Interpolate between test data records for different air flow rates

    Arguments:
    throughput_exhaust_air -- throughput (m3/h) of exhaust air
    hp_test_data
        -- list of dictionaries of heat pump test data, each with the following elements:
                - air_flow_rate
                - test_letter
                - capacity
                - cop
                - design_flow_temp (in Celsius)
                - temp_outlet (in Celsius)
                - temp_source (in Celsius)
                - temp_test (in Celsius)
    """
    # Split test records into different lists by air flow rate
    test_data_by_air_flow_rate = {}
    for test_data_record in hp_test_data:
        if "air_flow_rate" not in test_data_record:
            continue  # pragma: no cover
        if test_data_record["air_flow_rate"] not in test_data_by_air_flow_rate.keys():
            # Initialise list for this air flow rate if it does not already exist
            test_data_by_air_flow_rate[test_data_record["air_flow_rate"]] = []
        test_data_by_air_flow_rate[test_data_record["air_flow_rate"]].append(test_data_record)

    # Check that all lists have same combinations of design flow temp and test letter
    fixed_temps_and_test_letters = None
    for test_data_record_list in test_data_by_air_flow_rate.values():
        # Find and save all the combinations of design flow temp and test letter
        # for this air flow rate
        air_flowrate_flow_temps_test_letters = []
        for test_data_record in test_data_record_list:
            air_flowrate_flow_temps_test_letters.append(
                (
                    test_data_record["design_flow_temp"],
                    test_data_record["test_letter"],
                    test_data_record["temp_outlet"],
                    test_data_record["temp_source"],
                    test_data_record["temp_test"],
                )
            )

        if fixed_temps_and_test_letters is None:
            # If we are on the first iteration of the loop, save the list of
            # design flow temps and test letters from this loop for comparison
            # in subsequent loops
            fixed_temps_and_test_letters = air_flowrate_flow_temps_test_letters
        else:
            # If we are not on the first iteration of the loop, check that same
            # design flow temps and test letters are present for this air flow
            # rate and the first one
            if set(fixed_temps_and_test_letters) != set(air_flowrate_flow_temps_test_letters):
                logger.warning(
                    "Different test points have been provided for different air flow rates"
                )

    # Construct test data records interpolated by air flow rate
    air_flow_rates_ordered = sorted(test_data_by_air_flow_rate.keys())
    hp_dict_test_data_interp_by_air_flow_rate = []
    if fixed_temps_and_test_letters is None:
        raise ValueError("fixed_temps_and_test_letters is None.")

    for (
        design_flow_temp,
        test_letter,
        temp_outlet,
        temp_source,
        temp_test,
    ) in fixed_temps_and_test_letters:
        # Create lists of test data values ordered by air flow rate
        capacity_list = []
        cop_list = []
        ext_air_ratio_list = []
        for air_flow_rate in air_flow_rates_ordered:
            for test_record in test_data_by_air_flow_rate[air_flow_rate]:
                if (
                    test_record["design_flow_temp"] == design_flow_temp
                    and test_record["test_letter"] == test_letter
                ):
                    capacity_list.append(test_record["capacity"])
                    cop_list.append(test_record["cop"])
                    if source_type == SourceType.EXHAUST_AIR_MIXED:
                        ext_air_ratio_list.append(test_record["eahp_mixed_ext_air_ratio"])

        # Interpolate test data by air flow rate
        capacity = np.interp(throughput_exhaust_air, air_flow_rates_ordered, capacity_list)
        cop = np.interp(throughput_exhaust_air, air_flow_rates_ordered, cop_list)
        if source_type == SourceType.EXHAUST_AIR_MIXED:
            ext_air_ratio = np.interp(
                throughput_exhaust_air, air_flow_rates_ordered, ext_air_ratio_list
            )
        else:
            ext_air_ratio = None

        # Construct interpolated test data record
        hp_dict_test_data_interp_by_air_flow_rate.append(
            {
                "test_letter": test_letter,
                "capacity": capacity,
                "cop": cop,
                "design_flow_temp": design_flow_temp,
                "temp_outlet": temp_outlet,
                "temp_source": temp_source,
                "temp_test": temp_test,
                "eahp_mixed_ext_air_ratio": ext_air_ratio,
            }
        )

    # Find lowest air flow rate in test data
    lowest_air_flow_rate_in_test_data = min(test_data_by_air_flow_rate.keys())

    return lowest_air_flow_rate_in_test_data, hp_dict_test_data_interp_by_air_flow_rate


class BufferTank:
    """A class for Buffer Tanks objects linked to heat pumps."""

    # part of the thermal losses transmitted to the room
    # Taken from Storage tank module: Method A from BS EN 15316-5:2017
    __f_sto_m = 0.75

    # Reference conditions for buffer tank thermal loss calculations
    __TEMP_SET_REF = 65  # Reference temperature setpnt in °C
    __TEMP_AMB_REF = 20  # Reference ambient temperature in °C

    # Temperature split factor for flow/return calculations
    __TEMP_SPLIT_FACTOR_FLOW = 0.5

    def __init__(
        self,
        daily_losses: float,
        volume: float,
        pump_fixed_flow_rate: float,
        pump_power_at_flow_rate: float,
        number_of_zones: int,
        simulation_time: SimulationTime,
        initial_temp: float,
        contents: MaterialProperties = WATER,
        output_detailed_results: bool = False,
    ):
        """Construct a BufferTank object

        Arguments:
        daily_losses            -- standing loss from the buffer tank under standard test condition in kWh/day
        volume                  -- volume of the buffer tank in litres
        pump_fixed_flow_rate    -- flow rate of the buffer tank - emitters loop in l/min
        pump_power_at_flow_rate -- pump power of the buffer tank - emitters loop in W
        number_of_zones         -- number of zones in the project
        simulation_time         -- reference to SimulationTime object
        initial_temp            -- initial temperature of the buffer tank, in Celsius.  Default is 20C, references INITIAL_EMITTER_CIRCUIT_TEMP from emitters.py
        contents                -- reference to MaterialProperties object
        output_detailed_results -- if true, save detailed results from each timestep
                                   for later reporting
                                   TODO: Detailed reporting has not yet been implemented for Buffer Tanks
        """
        self.__daily_losses = daily_losses
        self.__volume = volume
        self.__pump_fixed_flow_rate = pump_fixed_flow_rate
        self.__pump_power_at_flow_rate = pump_power_at_flow_rate
        self.__number_of_zones = number_of_zones
        self.__simulation_time = simulation_time
        self.__contents = contents
        self.__service_results = []

        self.__buffer_emitter_circ_flow_rate = 0.0
        self.__hp_buffer_circ_flow_rate = 0.0
        self.__print_warning = True  # To avoid multiple warning messages for undersized pump
        # water specific heat in kWh/kg.K
        self.__Cp = contents.specific_heat_capacity_kWh()
        # volumic mass in kg/litre
        self.__rho = contents.density()

        self.__Q_heat_loss_buffer_rbl = 0.0
        self.__track_buffer_loss = 0.0

        # If detailed results are to be output, initialise list
        if output_detailed_results:
            self.__detailed_results = []
        else:
            self.__detailed_results = None

        # Initialisation of buffer tank temperature needed in case No power required by emitters in first step
        self.__temp_average_buffer = initial_temp

    @property
    def volume(self) -> float:
        return self.__volume

    @property
    def detailed_results(self) -> list | None:
        return self.__detailed_results

    def update_buffer_loss(self, buffer_loss: float) -> None:
        self.__track_buffer_loss = deepcopy(buffer_loss)

    def get_buffer_loss(self) -> float:
        return self.__track_buffer_loss

    def thermal_losses(self, temp_average_buffer: float, temp_rm_prev: float) -> float:
        """Thermal losses are calculated with respect to the impact of the temperature set point"""
        H_buffer_ls = (W_per_kW * self.__daily_losses) / (
            hours_per_day * (self.__TEMP_SET_REF - self.__TEMP_AMB_REF)
        )  # Specific loss in W/K
        heat_loss_buffer_W = (
            temp_average_buffer - temp_rm_prev
        ) * H_buffer_ls  # Absolute loss in W
        heat_loss_buffer_kWh = (
            heat_loss_buffer_W
            / W_per_kW
            * self.__simulation_time.timestep()
            / self.__number_of_zones
        )
        # TODO: update when zoning sorted out. Hopefully then there will be no need to divide by the number of zones.

        # recoverable heat losses from buffer - kWh
        self.__Q_heat_loss_buffer_rbl = deepcopy(heat_loss_buffer_kWh * self.__f_sto_m)
        return heat_loss_buffer_kWh

    def internal_gains(self) -> float:
        """Return the recoverable heat losses as internal gain for the current timestep in W"""
        # multiply by number of zones because this is only called once (not per zone like thermal_loss) for internal gains
        return (
            self.__Q_heat_loss_buffer_rbl
            * W_per_kW
            / self.__simulation_time.timestep()
            * self.__number_of_zones
        )

    def calc_buffer_tank(
        self, service_name: str, emitters_data_for_buffer_tank: dict[str, Any]
    ) -> list[dict[str, Any]]:
        temp_rm_prev = emitters_data_for_buffer_tank["temp_rm_prev"]

        if emitters_data_for_buffer_tank["power_req_from_buffer_tank"] > 0.0:
            temp_emitter_req = emitters_data_for_buffer_tank["temp_emitter_req"]
            self.__temp_average_buffer = deepcopy(temp_emitter_req)

            # call to calculate thermal losses
            heat_loss_buffer_kWh = self.thermal_losses(
                temp_average_buffer=temp_emitter_req, temp_rm_prev=temp_rm_prev
            )

            # We are calculating the delta T needed to give the heat output required from the emitters
            # E = m C dT rearranged to make delta T the subject
            deltaT_buffer = (
                emitters_data_for_buffer_tank["power_req_from_buffer_tank"]
                / (self.__pump_fixed_flow_rate / seconds_per_minute)
            ) / (self.__Cp * self.__rho * kJ_per_kWh)

            buffer_flow_temp = temp_emitter_req + self.__TEMP_SPLIT_FACTOR_FLOW * deltaT_buffer
            buffer_return_temp = (
                temp_emitter_req - (1.0 - self.__TEMP_SPLIT_FACTOR_FLOW) * deltaT_buffer
            )
            theoretical_hp_return_temp = buffer_return_temp

            flag = True
            theoretical_hp_flow_temp = None
            if emitters_data_for_buffer_tank["variable_flow"]:
                deltaT_hp_to_buffer = emitters_data_for_buffer_tank["temp_diff_emit_dsgn"]
                theoretical_hp_flow_temp = theoretical_hp_return_temp + deltaT_hp_to_buffer
                hp_flow = (
                    emitters_data_for_buffer_tank["power_req_from_buffer_tank"]
                    + heat_loss_buffer_kWh / self.__simulation_time.timestep()
                ) / (deltaT_hp_to_buffer * self.__Cp * self.__rho * kJ_per_kWh)
                if hp_flow > emitters_data_for_buffer_tank["max_flow_rate"]:
                    hp_flow = emitters_data_for_buffer_tank["max_flow_rate"]
                elif hp_flow < emitters_data_for_buffer_tank["min_flow_rate"]:
                    hp_flow = emitters_data_for_buffer_tank["min_flow_rate"]
                else:
                    flag = False
            else:
                hp_flow = emitters_data_for_buffer_tank["min_flow_rate"]

            if flag:
                theoretical_hp_flow_temp = theoretical_hp_return_temp + (
                    (
                        emitters_data_for_buffer_tank["power_req_from_buffer_tank"]
                        + heat_loss_buffer_kWh / self.__simulation_time.timestep()
                    )
                    / (hp_flow)
                ) / (self.__Cp * self.__rho * kJ_per_kWh)

            # We are currently assuming that, by design, buffer tanks always work with fix pumps on the
            # tank-emitter side with higher flow than the flow in the hp-tank side.
            if hp_flow > self.__pump_fixed_flow_rate / seconds_per_minute:
                raise ValueError(
                    "HP-buffer tank flow > than buffer tank-emitter flow. Calculation aborted"
                )

            flow_temp_increase_due_to_buffer = max(0, theoretical_hp_flow_temp - buffer_flow_temp)
            # TODO Consider circumstances where the flow rate on the hp-buffer loop exceed the flow rate in the
            #      buffer-emitter loop. We think in this circumstances the flow temperature would match rather than
            #      the return temperature, changing the logic of the methodology.
            #      This would happen in situation of very cold weather which exceed the design conditions for the
            #      buffer-emitters loop sizing/flow rate

            # If detailed results are to be output, save the results from the current timestep
            self.__service_results.append(
                {
                    "service_name": f"{service_name}_buffer_tank",
                    "power_req_from_buffer_tank": emitters_data_for_buffer_tank[
                        "power_req_from_buffer_tank"
                    ],
                    "temp_emitter_req": emitters_data_for_buffer_tank["temp_emitter_req"],
                    "buffer_emitter_circ_flow_rate": self.__pump_fixed_flow_rate,
                    "flow_temp_increase_due_to_buffer": flow_temp_increase_due_to_buffer,
                    "pump_power_at_flow_rate": self.__pump_power_at_flow_rate,
                    "heat_loss_buffer_kWh": heat_loss_buffer_kWh,
                }
            )

            if self.__detailed_results is not None:
                self.__detailed_results.append(self.__service_results)
        else:
            # call to calculate cool down losses
            heat_loss_buffer_kWh = self.thermal_losses(
                temp_average_buffer=self.__temp_average_buffer, temp_rm_prev=temp_rm_prev
            )
            heat_capacity_buffer = self.__volume * (self.__rho * self.__Cp * kJ_per_kWh)

            temp_loss = heat_loss_buffer_kWh / (heat_capacity_buffer / kJ_per_kWh)
            new_temp_average_buffer = self.__temp_average_buffer - temp_loss

            self.__temp_average_buffer = deepcopy(new_temp_average_buffer)

            self.__service_results.append(
                {
                    "service_name": f"{service_name}_buffer_tank",
                    "power_req_from_buffer_tank": 0.0,
                    "temp_emitter_req": emitters_data_for_buffer_tank["temp_emitter_req"],
                    "buffer_emitter_circ_flow_rate": self.__pump_fixed_flow_rate,
                    "flow_temp_increase_due_to_buffer": 0.0,
                    "pump_power_at_flow_rate": 0.0,
                    "heat_loss_buffer_kWh": heat_loss_buffer_kWh,
                }
            )
            if self.__detailed_results is not None:
                self.__detailed_results.append(self.__service_results)

        return self.__service_results


class HeatPumpTestData:
    """An object to represent EN 14825 test data for a heat pump.

    This object stores the data and provides functions to look up values from
    the correct data records for the conditions being modelled.
    """

    __test_letters_non_bivalent = ["A", "B", "C", "D"]
    __test_letters_all = ["A", "B", "C", "D", "F"]

    def __init__(self, hp_test_data: list[HeatPumpData]):
        """Construct a HeatPumpTestData object

        Arguments:
        hp_test_data
            -- list of dictionaries of heat pump test data, each with the following elements:
                - test_letter
                - capacity
                - cop
                - design_flow_temp (in Celsius)
                - temp_outlet (in Celsius)
                - temp_source (in Celsius)
                - temp_test (in Celsius)
        """

        def duplicates(a: HeatPumpData, b: HeatPumpData) -> bool:
            """Determine whether records a and b are duplicates"""
            return (
                a["temp_test"] == b["temp_test"] and a["design_flow_temp"] == b["design_flow_temp"]
            )

        # Keys will be design flow temps, values will be lists of dicts containing the test data
        self.__testdata = {}

        # A separate list of design flow temps is required because it can be
        # sorted, whereas the dict above can't be (at least before Python 3.7)
        self.__design_flow_temps = []
        # Dict to count duplicate records for each design flow temp
        dupl = {}

        # Read the test data records
        # Work on a deep copy of the input data structure in case the original
        # is used to init other objects (or the same object multiple times
        # e.g. during testing)
        for hp_testdata_dict in deepcopy(hp_test_data):
            design_flow_temp = hp_testdata_dict["design_flow_temp"]

            # When a new design flow temp is encountered, add it to the lists/dicts
            if design_flow_temp not in self.__design_flow_temps:
                self.__design_flow_temps.append(design_flow_temp)
                self.__testdata[design_flow_temp] = []
                dupl[design_flow_temp] = 0

            # Check for duplicate records
            duplicate = False
            for d in self.__testdata[design_flow_temp]:
                if duplicates(a=hp_testdata_dict, b=d):
                    duplicate = True
                    # Increment count of number of duplicates for this design flow temp
                    # Handle records with same inlet temp
                    # Cannot process a row at the same inlet temperature (div
                    # by zero error during interpolation), so we add a tiny
                    # amount to the temperature (to 10DP) for each duplicate
                    # found.
                    # TODO Why do we need to alter the duplicate record? Can we
                    #      not just eliminate it?
                    hp_testdata_dict["temp_test"] += 0.0000000001
                    hp_testdata_dict["temp_source"] += 0.0000000001
                    # TODO The adjustment to temp_source is in the python
                    #      implementation of DAHPSE but not in the spreadsheet
                    #      implementation. Given that temp_source can be the
                    #      same for all test records anyway, is this adjustment
                    #      needed?
            # This increment has to be after loop to avoid multiple-counting
            # when there are 3 or more duplicates. E.g. if there are already 2
            # records that are the same, then when adding a third that is the
            # same, we only want to increment the counter by 1 (for the record
            # we are adding) and not 2 (the number of existing records the new
            # record duplicates).
            if duplicate:
                dupl[design_flow_temp] += 1

            # Add the test record to the data structure, under the appropriate design flow temp
            self.__testdata[design_flow_temp].append(hp_testdata_dict)

        # Check the number of test records is as expected
        # - Up to 4 design flow temps (EN 14825:2018 defines these as 35, 45, 55, 65)
        # - 4 or 5 distinct records for each flow temp
        # TODO Is there any reason the model couldn't handle more than 5 test
        #      records if data is available? Could/should we relax the
        #      restriction below?
        if len(self.__design_flow_temps) < 1:
            raise ValueError("No test data provided for heat pump performance")
        elif len(self.__design_flow_temps) > 4:
            logger.warning(
                f"Test data for a maximum of 4 design flow temperatures is expected. {len(self.__design_flow_temps)} have been provided."
            )
        for design_flow_temp, data in self.__testdata.items():
            if dupl[design_flow_temp]:
                if (len(data) - dupl[design_flow_temp]) != 4:
                    raise ValueError("Expected 4 distinct records for each design flow temperature")
            elif len(data) != 5:
                raise ValueError("Expected 5 records for each design flow temperature")

        # Check if test letters ABCDF are present as expected
        test_letter_array = []
        for temperature in self.__design_flow_temps:
            for test_data in self.__testdata[temperature]:
                for test_letter in test_data["test_letter"]:
                    test_letter_array.append(test_letter)
                if len(test_letter_array) == 5:
                    for test_letter_check in self.__test_letters_all:
                        if test_letter_check not in test_letter_array:
                            error_output = (
                                "Expected test letter "
                                + test_letter_check
                                + " in "
                                + str(temperature)
                                + " degree temp data"
                            )
                            raise ValueError(error_output)
                    test_letter_array = []

        # Sort the list of design flow temps
        self.__design_flow_temps = sorted(self.__design_flow_temps)

        # Sort the records in order of test temperature from low to high
        for data in self.__testdata.values():
            data.sort(key=lambda sublist: sublist["temp_test"])

        # Calculate derived variables which are not time-dependent

        def average_capacity() -> list[float]:
            # The list average_cap will be in the same order as the
            # corresponding elements in self.__design_flow_temps. This behaviour
            # is relied upon elsewhere.
            average_cap = []
            for design_flow_temp in self.__design_flow_temps:
                average_cap.append(
                    math.fsum(
                        [
                            x["capacity"]
                            for x in self.__testdata[design_flow_temp]
                            if x["test_letter"] in self.__test_letters_non_bivalent
                        ]
                    )
                    / len(self.__test_letters_non_bivalent)
                )
            return average_cap

        self.__average_cap = average_capacity()

        def init_temp_spread_test_conditions() -> list[float]:
            """List temp spread at test conditions for the design flow temps in the test data"""
            dtheta_out_by_flow_temp = {20: 5.0, 35: 5.0, 45: 6.0, 55: 8.0, 65: 10.0}
            dtheta_out = []
            for design_flow_temp in self.__design_flow_temps:
                dtheta_out.append(dtheta_out_by_flow_temp[design_flow_temp])
            return dtheta_out

        self.__temp_spread_test_conditions = init_temp_spread_test_conditions()

        def init_regression_coeffs() -> dict[int, list[float]]:
            """Calculate polynomial regression coefficients for test temperature vs. CoP"""
            regression_coeffs = {}
            for design_flow_temp in self.__design_flow_temps:
                temp_test_list = [x["temp_test"] for x in self.__testdata[design_flow_temp]]
                cop_list = [x["cop"] for x in self.__testdata[design_flow_temp]]
                regression_coeffs[design_flow_temp] = list(polyfit(temp_test_list, cop_list, 2))

            return regression_coeffs

        self.__regression_coeffs = init_regression_coeffs()

        # Calculate derived variables for each data record which are not time-dependent
        for design_flow_temp in self.__design_flow_temps:
            for data in self.__testdata[design_flow_temp]:
                # Get the source and outlet temperatures from the test record
                temp_source = Celcius2Kelvin(temp_C=data["temp_source"])
                temp_outlet = Celcius2Kelvin(temp_C=data["temp_outlet"])

                # Calculate the Carnot CoP and add to the test record
                data["carnot_cop"] = carnot_cop(temp_source=temp_source, temp_outlet=temp_outlet)
                # Calculate the exergetic efficiency and add to the test record
                data["exergetic_eff"] = data["cop"] / data["carnot_cop"]

            temp_source_cld = Celcius2Kelvin(
                temp_C=self.__testdata[design_flow_temp][0]["temp_source"]
            )
            temp_outlet_cld = Celcius2Kelvin(
                temp_C=self.__testdata[design_flow_temp][0]["temp_outlet"]
            )
            carnot_cop_cld = self.__testdata[design_flow_temp][0]["carnot_cop"]

            # Calculate derived variables that require values at coldest test temp as inputs
            for data in self.__testdata[design_flow_temp]:
                # Get the source and outlet temperatures from the test record
                temp_source = Celcius2Kelvin(temp_C=data["temp_source"])
                temp_outlet = Celcius2Kelvin(temp_C=data["temp_outlet"])

                # Calculate the theoretical load ratio and add to the test record
                data["theoretical_load_ratio"] = (data["carnot_cop"] / carnot_cop_cld) * (
                    temp_outlet_cld * temp_source / (temp_source_cld * temp_outlet)
                ) ** N_EXER

    @property
    def design_flow_temperatures(self) -> list[float]:
        return self.__design_flow_temps

    @property
    def regression_coefficients(self) -> dict[int, list[float]]:
        return self.__regression_coeffs

    @property
    def test_data(self):
        return self.__testdata

    def average_capacity(self, design_flow_temp_op_cond: float) -> float:
        """Return average capacity for tests A-D, interpolated between design flow temps"""
        if len(self.__design_flow_temps) == 1:
            # If there is data for only one design flow temp, use that
            return self.__average_cap[0]

        flow_temp = Kelvin2Celcius(temp_K=design_flow_temp_op_cond)
        interpolated_average_capacity = np.interp(
            flow_temp, self.__design_flow_temps, self.__average_cap
        )
        if TYPE_CHECKING:
            assert isinstance(interpolated_average_capacity, float)

        return interpolated_average_capacity

    def temp_spread_test_conditions(self, design_flow_temp_op_cond: float) -> float:
        """Return temperature spread under test conditions, interpolated between design flow temps"""
        if len(self.__design_flow_temps) == 1:
            # If there is data for only one design flow temp, use that
            return self.__temp_spread_test_conditions[0]

        flow_temp = Kelvin2Celcius(temp_K=design_flow_temp_op_cond)
        temperature_spread = np.interp(
            flow_temp, self.__design_flow_temps, self.__temp_spread_test_conditions
        )
        if TYPE_CHECKING:
            assert isinstance(temperature_spread, float)

        return temperature_spread

    def __find_test_record_index(self, test_condition: str, design_flow_temp: float) -> int:
        """Find position of specified test condition in list"""
        if test_condition == "cld":
            # Coldest test condition is first in list
            return 0
        for index, test_record in enumerate(self.__testdata[design_flow_temp]):
            if test_record["test_letter"] == test_condition:
                return index

        # If no index found, return an error.
        raise ValueError("Test record index not found.")

    def __data_at_test_condition(
        self, data_item_name: str, test_condition: str, design_flow_temp_op_cond: float
    ) -> float:
        """Return value at specified test condition, interpolated between design flow temps"""
        # TODO What do we do if flow_temp is outside the range of design flow temps provided?

        if len(self.__design_flow_temps) == 1:
            # If there is data for only one design flow temp, use that
            idx = self.__find_test_record_index(
                test_condition=test_condition, design_flow_temp=self.__design_flow_temps[0]
            )
            return self.__testdata[self.__design_flow_temps[0]][idx][data_item_name]

        # Interpolate between the values at each design flow temp
        data_list = []
        for design_flow_temp in self.__design_flow_temps:
            idx = self.__find_test_record_index(
                test_condition=test_condition, design_flow_temp=design_flow_temp
            )
            data_list.append(self.__testdata[design_flow_temp][idx][data_item_name])

        flow_temp = Kelvin2Celcius(temp_K=design_flow_temp_op_cond)
        interpolated_value = np.interp(flow_temp, self.__design_flow_temps, data_list)
        if TYPE_CHECKING:
            assert isinstance(interpolated_value, float)

        return interpolated_value

    def carnot_cop_at_test_condition(
        self, test_condition: str, design_flow_temp_op_cond: float
    ) -> float:
        """
        Return Carnot CoP at specified test condition (A, B, C, D, F or cld),
        interpolated between design flow temps
        """
        return self.__data_at_test_condition(
            data_item_name="carnot_cop",
            test_condition=test_condition,
            design_flow_temp_op_cond=design_flow_temp_op_cond,
        )

    def outlet_temp_at_test_condition(
        self, test_condition: str, design_flow_temp_op_cond: float
    ) -> float:
        """
        Return outlet temp, in Kelvin, at specified test condition (A, B, C, D,
        F or cld), interpolated between design flow temps.
        """

        outlet_temperature = Celcius2Kelvin(
            temp_C=self.__data_at_test_condition(
                data_item_name="temp_outlet",
                test_condition=test_condition,
                design_flow_temp_op_cond=design_flow_temp_op_cond,
            )
        )

        return outlet_temperature

    def source_temp_at_test_condition(
        self, test_condition: str, design_flow_temp_op_cond: float
    ) -> float:
        """
        Return source temp, in Kelvin, at specified test condition (A, B, C, D,
        F or cld), interpolated between design flow temps.
        """

        source_temperature = Celcius2Kelvin(
            temp_C=self.__data_at_test_condition(
                data_item_name="temp_source",
                test_condition=test_condition,
                design_flow_temp_op_cond=design_flow_temp_op_cond,
            )
        )
        return source_temperature

    def capacity_at_test_condition(
        self, test_condition: str, design_flow_temp_op_cond: float
    ) -> float:
        """
        Return capacity, in kW, at specified test condition (A, B, C, D, F or
        cld), interpolated between design flow temps.
        """
        return self.__data_at_test_condition(
            data_item_name="capacity",
            test_condition=test_condition,
            design_flow_temp_op_cond=design_flow_temp_op_cond,
        )

    def __lr_op_cond(
        self,
        temp_output: float,
        temp_source: float,
        carnot_cop_op_cond: float,
        design_flow_temp: float,
    ) -> float:
        """Return load ratio at operating conditions"""
        design_flow_temp = Celcius2Kelvin(temp_C=design_flow_temp)
        temp_output_cld = self.outlet_temp_at_test_condition(
            test_condition="cld", design_flow_temp_op_cond=design_flow_temp
        )
        temp_source_cld = self.source_temp_at_test_condition(
            test_condition="cld", design_flow_temp_op_cond=design_flow_temp
        )
        carnot_cop_cld = self.carnot_cop_at_test_condition(
            test_condition="cld", design_flow_temp_op_cond=design_flow_temp
        )

        lr_op_cond = (carnot_cop_op_cond / carnot_cop_cld) * (
            temp_output_cld * temp_source / (temp_output * temp_source_cld)
        ) ** N_EXER
        return lr_op_cond

    def __lr_eff_either_side_of_op_cond(
        self, design_flow_temp: float, exergy_lr_op_cond: float
    ) -> tuple[float, float, float, float]:
        """Return test results either side of operating conditions.

        This function returns 4 results:
        - Exergy load ratio below operating conditions
        - Exergy load ratio above operating conditions
        - Exergy efficiency below operating conditions
        - Exergy efficiency above operating conditions

        Arguments:
        flow_temp         -- flow temperature, in Kelvin
        exergy_lr_op_cond -- exergy load ratio at operating conditions
        design_flow_temp_op_cond -- design flow temperature of the heat pump as installed
        """

        # For the design flow temperature, find load ratios in test data
        # either side of load ratio calculated for operating conditions.
        found = False
        design_flow_temp_data = self.__testdata[design_flow_temp]
        # Find the first load ratio in the test data that is greater than
        # or equal to than the load ratio at operating conditions - this
        # and the previous load ratio are the values either side of
        # operating conditions.
        idx = 0
        for idx, test_record in enumerate(design_flow_temp_data):
            # Note: Changed the condition below from ">=" to ">" because
            # otherwise when exergy_lr_op_cond == test_record['theoretical_load_ratio']
            # for the first record, idx == 0 which is not allowed
            if test_record["theoretical_load_ratio"] > exergy_lr_op_cond:
                if idx <= 0:
                    # Use second lowest (list index 1) and lowest
                    idx = 1
                found = True
                # Current value of idx will be used later, so break out of loop
                break

        if not found:
            # Use the highest (list index -1) and second highest
            idx = -1

        # Look up correct load ratio and efficiency based on the idx found above
        lr_below = design_flow_temp_data[idx - 1]["theoretical_load_ratio"]
        lr_above = design_flow_temp_data[idx]["theoretical_load_ratio"]
        eff_below = design_flow_temp_data[idx - 1]["exergetic_eff"]
        eff_above = design_flow_temp_data[idx]["exergetic_eff"]

        return lr_below, lr_above, eff_below, eff_above

    def exer_eff_op_cond(
        self,
        temp_output: float,
        temp_source: float,
        carnot_cop_op_cond: float,
        design_flow_temp_op_cond: float,
    ) -> float:
        exer_eff_op_cond_list = []
        for design_flow_temp in self.__design_flow_temps:
            # Get exergy load ratio at operating conditions
            # Get exergy load ratio and exergy efficiency at test conditions
            # above and below operating conditions
            lr_op_cond = self.__lr_op_cond(
                temp_output=temp_output,
                temp_source=temp_source,
                carnot_cop_op_cond=carnot_cop_op_cond,
                design_flow_temp=design_flow_temp,
            )
            lr_below, lr_above, eff_below, eff_above = self.__lr_eff_either_side_of_op_cond(
                design_flow_temp=design_flow_temp, exergy_lr_op_cond=lr_op_cond
            )

            # CALCM-01 - DAHPSE - V2.0_DRAFT13, section 4.5.4
            # Get exergy efficiency by interpolating between figures above and
            # below operating conditions
            if lr_below == lr_above:
                exer_eff_op_cond = eff_below
            else:
                exer_eff_op_cond = eff_below + (eff_below - eff_above) * (lr_op_cond - lr_below) / (
                    lr_below - lr_above
                )
            exer_eff_op_cond_list.append(exer_eff_op_cond)
        flow_temp = Kelvin2Celcius(temp_K=design_flow_temp_op_cond)
        interpolated_exergy_efficiency = np.interp(
            flow_temp, self.__design_flow_temps, exer_eff_op_cond_list
        )
        if TYPE_CHECKING:
            assert isinstance(interpolated_exergy_efficiency, float)

        return interpolated_exergy_efficiency

    def cop_op_cond_if_not_air_source(
        self,
        temp_diff_limit_low: float,
        temp_ext_C: float,
        temp_source: float,
        temp_output: float,
        design_flow_temp_op_cond: float,
    ) -> float:
        """Calculate CoP at operating conditions when heat pump is not air-source

        Arguments:
        temp_diff_limit_low -- minimum temperature difference between source and sink
        temp_ext_C          -- external temperature, in Celsius.
            Need to use Celsius for temp_ext_C because regression coeffs were calculated
            using temperature in Celsius.
        temp_source         -- source temperature, in Kelvin
        temp_output         -- output temperature, in Kelvin
        design_flow_temp_op_cond -- design flow temperature of the heat pump as installed
        """

        # For each design flow temperature, calculate CoP at operating conditions
        # Note: Loop over sorted list of design flow temps and then index into
        #       self.__testdata, rather than looping over self.__testdata,
        #       which is unsorted and therefore may populate the lists in the
        #       wrong order.
        cop_op_cond = []
        for design_flow_temp in self.__design_flow_temps:
            design_flow_temp_data = self.__testdata[design_flow_temp]
            # Get the source and outlet temperatures from the coldest test record
            temp_outlet_cld = Celcius2Kelvin(temp_C=design_flow_temp_data[0]["temp_outlet"])
            temp_source_cld = Celcius2Kelvin(temp_C=design_flow_temp_data[0]["temp_source"])

            cop_operating_conditions = (
                (
                    self.__regression_coeffs[design_flow_temp][0]
                    + self.__regression_coeffs[design_flow_temp][1] * temp_ext_C
                    + self.__regression_coeffs[design_flow_temp][2] * temp_ext_C**2
                )
                * temp_output
                * (temp_outlet_cld - temp_source_cld)
                / (temp_outlet_cld * max((temp_output - temp_source), temp_diff_limit_low))
            )
            cop_op_cond.append(cop_operating_conditions)

        if len(self.__design_flow_temps) == 1:
            # If there is data for only one design flow temp, use that
            return cop_op_cond[0]

        # Interpolate between the values found for the different design flow temperatures
        flow_temp = Kelvin2Celcius(temp_K=design_flow_temp_op_cond)
        interpolated_cop = np.interp(flow_temp, self.__design_flow_temps, cop_op_cond)
        if TYPE_CHECKING:
            assert isinstance(interpolated_cop, float)

        return interpolated_cop

    def capacity_op_cond_var_flow_or_source_temp(
        self,
        temp_output: float,
        temp_source: float,
        mod_ctrl: bool,
        design_flow_temp_op_cond: float,
    ) -> float:
        """Calculate thermal capacity at operating conditions when flow temp
        during test was variable or source temp was variable

        Arguments:
        temp_source -- source temperature, in Kelvin
        temp_output -- output temperature, in Kelvin
        mod_ctrl    -- boolean specifying whether or not the heat has controls
                    capable of varying the output (as opposed to just on/off
                    control)
        design_flow_temp_op_cond -- design flow temperature of the heat pump as installed
        """
        # In eqns below, method uses condition A rather than coldest. From
        # CALCM-01 - DAHPSE - V2.0_DRAFT13, section 4.4:
        # The Temperature Operation Limit (TOL) is defined in EN14825 as
        # "the lowest outdoor temperature at which the unit can still
        # deliver heating capacity and is declared by the manufacturer.
        # Below this temperature the heat pump will not be able to
        # deliver any heating capacity."
        # The weather data used within this calculation method does not
        # feature a source temperature at or below the "TOL" test
        # temperature (which is -7C to -10C). Therefore, test data at
        # the TOL test condition is not used (Test condition "A" at -7C
        # is sufficient).
        # TODO The above implies that the TOL test temperature data may
        #      be needed if we change the weather data from that used in
        #      DAHPSE for SAP 2012/10.2
        therm_cap_op_cond = []

        if mod_ctrl:
            # For each design flow temperature, calculate capacity at operating conditions
            # Note: Loop over sorted list of design flow temps and then index into
            #       self.__testdata, rather than looping over self.__testdata,
            #       which is unsorted and therefore may populate the lists in the
            #       wrong order.
            for design_flow_temp in self.__design_flow_temps:
                design_flow_temp_data = self.__testdata[design_flow_temp]
                # Get the source and outlet temperatures from the coldest test record
                temp_outlet_cld = Celcius2Kelvin(temp_C=design_flow_temp_data[0]["temp_outlet"])
                temp_source_cld = Celcius2Kelvin(temp_C=design_flow_temp_data[0]["temp_source"])
                # Get the thermal capacity from the coldest test record
                thermal_capacity_cld = design_flow_temp_data[0]["capacity"]

                thermal_capacity_op_cond = (
                    thermal_capacity_cld
                    * ((temp_outlet_cld * temp_source) / (temp_output * temp_source_cld)) ** N_EXER
                )
                therm_cap_op_cond.append(thermal_capacity_op_cond)
        else:
            # For each design flow temperature, calculate capacity at operating conditions
            # Note: Loop over sorted list of design flow temps and then index into
            #       self.__testdata, rather than looping over self.__testdata,
            #       which is unsorted and therefore may populate the lists in the
            #       wrong order.
            for design_flow_temp in self.__design_flow_temps:
                design_flow_temp_data = self.__testdata[design_flow_temp]
                # Get the source and outlet temperatures from the coldest test record
                temp_outlet_cld = Celcius2Kelvin(temp_C=design_flow_temp_data[0]["temp_outlet"])
                temp_source_cld = Celcius2Kelvin(temp_C=design_flow_temp_data[0]["temp_source"])
                # Get the thermal capacity from the coldest test record
                thermal_capacity_cld = design_flow_temp_data[0]["capacity"]

                D_idx = self.__find_test_record_index(
                    test_condition="D", design_flow_temp=design_flow_temp
                )
                # Get the source and outlet temperatures for test condition D
                temp_outlet_D = Celcius2Kelvin(temp_C=design_flow_temp_data[D_idx]["temp_outlet"])
                temp_source_D = Celcius2Kelvin(temp_C=design_flow_temp_data[D_idx]["temp_source"])
                # Get the thermal capacity for test condition D
                thermal_capacity_D = design_flow_temp_data[D_idx]["capacity"]

                temp_diff_cld = temp_outlet_cld - temp_source_cld
                temp_diff_D = temp_outlet_D - temp_source_D
                temp_diff_op_cond = temp_output - temp_source

                thermal_capacity_op_cond = thermal_capacity_cld + (
                    thermal_capacity_D - thermal_capacity_cld
                ) * ((temp_diff_cld - temp_diff_op_cond) / (temp_diff_cld - temp_diff_D))
                therm_cap_op_cond.append(thermal_capacity_op_cond)

        # Interpolate between the values found for the different design flow temperatures
        flow_temp = Kelvin2Celcius(temp_K=design_flow_temp_op_cond)
        interpolated_thermal_capacity = np.interp(
            flow_temp, self.__design_flow_temps, therm_cap_op_cond
        )
        if TYPE_CHECKING:
            assert isinstance(interpolated_thermal_capacity, float)

        return interpolated_thermal_capacity

    def temp_spread_correction(
        self,
        temp_source: float,
        temp_output: float,
        temp_diff_evaporator: float,
        temp_diff_condenser: float,
        temp_spread_emitter: float,
        design_flow_temp_op_cond: float,
    ) -> float:
        """Calculate temperature spread correction factor

        Arguments:
        temp_source -- source temperature, in Kelvin
        temp_output -- output temperature, in Kelvin
        temp_diff_evaporator
            -- average temperature difference between heat transfer medium and
               refrigerant in evaporator, in deg C or Kelvin
        temp_diff_condenser
            -- average temperature difference between heat transfer medium and
               refrigerant in condenser, in deg C or Kelvin
        temp_spread_emitter
            -- temperature spread on condenser side in operation due to design
               of heat emission system
        design_flow_temp_op_cond -- design flow temperature of the heat pump as installed
        """
        temp_spread_correction_list = []
        for i in range(len(self.__design_flow_temps)):
            temp_spread_test_cond = self.__temp_spread_test_conditions[i]
            temp_spread_correction = 1.0 - ((temp_spread_test_cond - temp_spread_emitter) / 2.0) / (
                temp_output
                - temp_spread_test_cond / 2.0
                + temp_diff_condenser
                - temp_source
                + temp_diff_evaporator
            )
            temp_spread_correction_list.append(temp_spread_correction)

        # Interpolate between the values found for the different design flow temperatures
        flow_temp = Kelvin2Celcius(temp_K=design_flow_temp_op_cond)
        interpolated_correction_factor = np.interp(
            flow_temp, self.__design_flow_temps, temp_spread_correction_list
        )
        if TYPE_CHECKING:
            assert isinstance(interpolated_correction_factor, float)

        return interpolated_correction_factor


class HeatPumpService:
    """A base class for objects representing services (e.g. water heating) provided by a heat pump.

    This object encapsulates the name of the service, meaning that the system
    consuming the energy does not have to specify this on every call, and
    helping to enforce that each service has a unique name.

    Derived objects provide a place to handle parts of the calculation (e.g.
    distribution flow temperature) that may differ for different services.

    Separate subclasses need to be implemented for different types of service
    (e.g. HW and space heating). These should implement the following functions:
    - demand_energy(self, energy_demand)
    """

    def __init__(
        self,
        heat_pump: "HeatPump",
        service_name: str,
        control: TimeControl | None = None,
    ):
        """Construct a HeatPumpService object

        Arguments:
        heat_pump    -- reference to the HeatPump object providing the service
        service_name -- name of the service demanding energy from the heat pump
        control -- reference to a control object which must implement is_on() func
        """
        self.__hp = heat_pump
        self.__service_name = service_name
        self.__control = control

    @property
    def heat_pump(self) -> "HeatPump":
        return self.__hp

    @property
    def service_name(self) -> str:
        return self.__service_name

    @property
    def control(self) -> TimeControl | None:
        return self.__control

    def is_on(self) -> bool:
        if self.__control is not None:
            service_on = self.__control.is_on()
        else:
            service_on = True
        return service_on


class HeatPumpServiceWater(HeatPumpService):
    """An object to represent a water heating service provided by a heat pump to e.g. a cylinder.

    This object contains the parts of the heat pump calculation that are
    specific to providing hot water.
    """

    # Values for time constant from BS EN 15316-4-2:2017 Table 13
    __TIME_CONSTANT_WATER = 1560
    __SERVICE_TYPE = HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR

    def __init__(
        self,
        heat_pump,
        service_name: str,
        temp_limit_upper: float,
        cold_feed: ColdWaterSource,
        controlmin: TimeControl,
        controlmax: TimeControl,
        boiler_service_water_regular: BoilerServiceWaterRegular | None = None,
    ):
        """Construct a BoilerServiceWater object

        Arguments:
        heat_pump           -- reference to the HeatPump object providing the service
        service_name        -- name of the service demanding energy from the heat pump
        temp_limit_upper    -- upper operating limit for temperature, in deg C
        cold_feed           -- reference to ColdWaterSource object
        controlmin          -- reference to a control object which must select current
                               the minimum timestep temperature
        controlmax          -- reference to a control object which must select current
                               the maximum timestep temperature
        boiler_service_water_regular -- reference to the BoilerServiceWaterRegular
            object that is backing up or supplementing the heat pump service
        """
        super().__init__(heat_pump=heat_pump, service_name=service_name, control=controlmin)

        self.__controlmin = controlmin
        self.__controlmax = controlmax
        self.__temp_limit_upper = Celcius2Kelvin(temp_C=temp_limit_upper)
        self.__cold_feed = cold_feed
        self.__hybrid_boiler_service = boiler_service_water_regular

    @property
    def controlmin(self) -> TimeControl:
        return self.__controlmin

    @property
    def controlmax(self) -> TimeControl:
        return self.__controlmax

    def setpnt(self) -> tuple[float | None, float | None]:
        """Return water heating setpnt (not necessarily temperature)"""
        if not isinstance(self.controlmin, SetpointTimeControl | CombinationTimeControl):
            raise TypeError(f"controlmin ({type(self.controlmin)}) does not have a set point.")
        if not isinstance(self.controlmax, SetpointTimeControl | CombinationTimeControl):
            raise TypeError(f"controlmax ({type(self.controlmax)}) does not have a set point.")
        return self.controlmin.setpnt(), self.controlmax.setpnt()

    def energy_output_max(
        self, temp_flow: float, temp_return: float | None
    ) -> tuple[float, dict[str, Any]] | float:
        """Calculate the maximum energy output of the HP, accounting for time
        spent on higher-priority services
        """

        if not self.is_on() or temp_return is None:
            return 0.0
        else:
            temp_return_K = Celcius2Kelvin(temp_C=temp_return)
            temp_flow_K = Celcius2Kelvin(temp_C=temp_flow)
            design_flow_temp_op_cond = temp_flow_K

            return self.heat_pump._HeatPump__energy_output_max(  # type: ignore[AttributeAccessIssue]
                temp_output=temp_flow_K,
                temp_return_feed=temp_return_K,
                design_flow_temp_op_cond=design_flow_temp_op_cond,
                hybrid_boiler_service=self.__hybrid_boiler_service,
                service_type=self.__SERVICE_TYPE,
                service_name=self.service_name,
            )

    def demand_energy(
        self, energy_demand: float, temp_flow: float | None, temp_return: float | None
    ) -> float:
        """Demand energy (in kWh) from the heat pump"""
        service_on = self.is_on()
        if not service_on or temp_return is None:
            energy_demand = 0.0

        temp_return_K = None
        temp_flow_K = None
        if temp_return is None and not math.isclose(energy_demand, 0.0, abs_tol=1e-10):
            raise ValueError("temp_return is None and energy_demand is not 0.0")  # PRAGMA: nocover
        elif temp_return is not None:
            temp_return_K = Celcius2Kelvin(temp_C=temp_return)

        if temp_flow is None and not math.isclose(energy_demand, 0.0, abs_tol=1e-10):
            raise ValueError("temp_flow is None and energy_demand is not 0.0")
        elif temp_flow is not None:
            temp_flow_K = Celcius2Kelvin(temp_C=temp_flow)
        design_flow_temp_op_cond = temp_flow_K

        # TODO Arbitrary volume used here for reference cold water temperature
        list_temp_vol = self.__cold_feed.get_temp_cold_water(volume_needed=1.0)
        temp_cold_water = Celcius2Kelvin(
            temp_C=math.fsum(t * v for t, v in list_temp_vol)
            / math.fsum(v for _, v in list_temp_vol)
        )

        return self.heat_pump._HeatPump__demand_energy(  # type: ignore[AttributeAccessIssue]
            service_name=self.service_name,
            service_type=self.__SERVICE_TYPE,
            energy_output_required=energy_demand,
            temp_output=temp_flow_K,
            temp_return_feed=temp_return_K,
            temp_limit_upper=self.__temp_limit_upper,
            design_flow_temp_op_cond=design_flow_temp_op_cond,
            time_constant_for_service=self.__TIME_CONSTANT_WATER,
            service_on=service_on,
            temp_used_for_scaling=temp_cold_water,
            hybrid_boiler_service=self.__hybrid_boiler_service,
        )


class HeatPumpServiceSpace(HeatPumpService):
    """An object to represent a space heating service provided by a heat pump to e.g. radiators.

    This object contains the parts of the heat pump calculation that are
    specific to providing space heating.
    """

    # Values for time constant from BS EN 15316-4-2:2017 Table 13
    __TIME_CONSTANT_SPACE = {
        HeatPumpEmitterType.RADIATORS_UFH: 1370,
        HeatPumpEmitterType.FAN_COILS: 360,
        HeatPumpEmitterType.WARM_AIR: 120,
    }
    __SERVICE_TYPE = HeatingServiceType.SPACE

    def __init__(
        self,
        heat_pump: "HeatPump",
        service_name: str,
        emitter_type: HeatPumpEmitterType,
        temp_limit_upper: float,
        temp_diff_emit_design: float,
        design_flow_temp_op_cond: float,
        control: TimeControl | None,
        volume_heated: float,  # unused variable
        boiler_service_space=None,
    ):
        """Construct a BoilerServiceSpace object

        Arguments:
        heat_pump           -- reference to the HeatPump object providing the service
        emitter_type        -- type of emitters that this space heating service is serving
        service_name        -- name of the service demanding energy from the heat pump
        temp_limit_upper    -- upper operating limit for temperature, in deg C
        temp_diff_emit_design -- design temperature difference across the emitters, in deg C or K
        design_flow_temp_op_cond -- design flow temperature of the heat pump as installed
        control             -- reference to a control object which must implement is_on() and setpnt() funcs
        volume_heated       -- volume of zones heated (required for exhaust air HPs only), in m3
        boiler_service_space -- reference to the BoilerServiceWaterSpace
            object that is backing up or supplementing the heat pump service
        """
        if control is not None and not isinstance(
            control, SetpointTimeControl | CombinationTimeControl
        ):
            raise TypeError(
                f"control ({type(control)}) must be an instance of either: SetpointTimeControl, CombinationTimeControl"
            )
        super().__init__(heat_pump=heat_pump, service_name=service_name, control=control)
        self.__emitter_type = emitter_type
        self.__temp_limit_upper = Celcius2Kelvin(temp_C=temp_limit_upper)
        self.__temp_diff_emit_design = temp_diff_emit_design
        self.__design_flow_temp_op_cond = Celcius2Kelvin(temp_C=design_flow_temp_op_cond)
        self.__hybrid_boiler_service = boiler_service_space
        self.__volume_heated = volume_heated

    def temp_setpnt(self) -> float | None:
        if self.control is None:
            return None
        if TYPE_CHECKING:
            assert isinstance(self.control, SetpointTimeControl | CombinationTimeControl)
        return self.control.setpnt()

    def in_required_period(self) -> bool | None:
        if self.control is None:
            return None
        if TYPE_CHECKING:
            assert isinstance(self.control, SetpointTimeControl | CombinationTimeControl)
        return self.control.in_required_period()

    def energy_output_max(
        self,
        temp_output: float,
        temp_return_feed: float,
        time_start: float = 0.0,
        emitters_data_for_buffer_tank: dict | None = None,
    ) -> tuple[float, dict[str, Any]] | float:
        """Calculate the maximum energy output of the HP, accounting for time
        spent on higher-priority services
        """
        if not self.is_on():
            return 0.0

        temp_output_K = Celcius2Kelvin(temp_C=temp_output)
        return self._HeatPumpService__hp._HeatPump__energy_output_max(  # type: ignore[AttributeAccessIssue]
            temp_output=temp_output_K,
            temp_return_feed=temp_return_feed,
            design_flow_temp_op_cond=self.__design_flow_temp_op_cond,
            hybrid_boiler_service=self.__hybrid_boiler_service,
            service_type=self.__SERVICE_TYPE,
            temp_spread_correction=self.temp_spread_correction,
            time_start=time_start,
            emitters_data_for_buffer_tank=emitters_data_for_buffer_tank,
            service_name=self.service_name,
        )

    def demand_energy(
        self,
        energy_demand: float,
        temp_flow: float,
        temp_return: float,
        time_start: float = 0.0,
        emitters_data_for_buffer_tank: dict | None = None,
        update_heat_source_state: bool = True,
    ) -> float:
        """Demand energy (in kWh) from the heat pump

        Arguments:
        energy_demand   -- space heating energy demand, in kWh
        temp_flow       -- flow temperature for emitters, in deg C
        temp_return     -- return temperature for emitters, in deg C
        time_start      --
        emitters_data_for_buffer_tank --
        update_heat_source_state -- if false the heat pump state does not change
        """
        service_on = self.is_on()
        if not service_on:
            energy_demand = 0.0

        return self._HeatPumpService__hp._HeatPump__demand_energy(  # type: ignore[AttributeAccessIssue]
            service_name=self.service_name,
            service_type=self.__SERVICE_TYPE,
            energy_output_required=energy_demand,
            temp_output=Celcius2Kelvin(temp_C=temp_flow),
            temp_return_feed=Celcius2Kelvin(temp_C=temp_return),
            temp_limit_upper=self.__temp_limit_upper,
            design_flow_temp_op_cond=self.__design_flow_temp_op_cond,
            time_constant_for_service=self.__TIME_CONSTANT_SPACE[self.__emitter_type],
            service_on=service_on,
            temp_spread_correction=self.temp_spread_correction,
            time_start=time_start,
            hybrid_boiler_service=self.__hybrid_boiler_service,
            emitters_data_for_buffer_tank=emitters_data_for_buffer_tank,
            update_heat_source_state=update_heat_source_state,
        )

    def running_time_throughput_factor(
        self,
        space_heat_running_time_cumulative: float,
        energy_demand: float,
        temp_flow: float,
        temp_return: float,
        time_start: float = 0.0,
    ) -> tuple[float, float]:
        """Return the cumulative running time and throughput factor (exhaust air HPs only)"""
        service_on = self.is_on()
        if not service_on:
            energy_demand = 0.0

        return self._HeatPumpService__hp._HeatPump__running_time_throughput_factor(  # type: ignore[AttributeAccessIssue]
            space_heat_running_time_cumulative=space_heat_running_time_cumulative,
            service_name=self.service_name,
            service_type=HeatingServiceType.SPACE,
            energy_output_required=energy_demand,
            temp_output=Celcius2Kelvin(temp_C=temp_flow),
            temp_return_feed=Celcius2Kelvin(temp_C=temp_return),
            temp_limit_upper=self.__temp_limit_upper,
            design_flow_temp_op_cond=self.__design_flow_temp_op_cond,
            time_constant_for_service=self.__TIME_CONSTANT_SPACE[self.__emitter_type],
            service_on=service_on,
            volume_heated_by_service=self.__volume_heated,
            temp_spread_correction=self.temp_spread_correction,
            time_start=time_start,
        )

    def temp_spread_correction(
        self, temp_output: float, temp_source: float, design_flow_temp_op_cond: float
    ) -> float:
        """Calculate temperature spread correction"""
        # Average temperature difference between heat transfer medium and
        # refrigerant in condenser
        temp_diff_condenser = 5.0

        # Average temperature difference between heat transfer medium and
        # refrigerant in evaporator
        # TODO Figures in BS EN ISO 15316-4-2:2017 are -15 and -10, but figures
        #      in BS EN ISO 15316-4-2:2008 were positive (although some were
        #      different numbers) and signs in temp_spread_correction equation
        #      have not changed, so need to check which is correct.
        #      Note: using negative numbers leads to divide-by-zero errors in
        #      the calculation which do not occur when using positive numbers.
        #      Given that the equation that uses these figures already has a
        #      minus sign in front of this variable (as written in the standard)
        #      this would seem to suggest that using positive numbers is correct
        if self._HeatPumpService__hp._HeatPump__source_type.source_fluid_is_air:  # type: ignore[AttributeAccessIssue]
            temp_diff_evaporator = 15.0
        elif self._HeatPumpService__hp._HeatPump__source_type.source_fluid_is_water:  # type: ignore[AttributeAccessIssue]
            temp_diff_evaporator = 10.0
        else:
            raise ValueError("SourceType not recognised.")

        # TODO The temp_spread_emitter input below (self.__temp_diff_emit_design)
        #      is for no weather comp. Add weather comp case as well
        return self.heat_pump._HeatPump__test_data.temp_spread_correction(  # type: ignore[AttributeAccessIssue]
            temp_source=temp_source,
            temp_output=temp_output,
            temp_diff_evaporator=temp_diff_evaporator,
            temp_diff_condenser=temp_diff_condenser,
            temp_spread_emitter=self.__temp_diff_emit_design,
            design_flow_temp_op_cond=design_flow_temp_op_cond,
        )


class HeatPumpWarmAir(SpaceHeatSystem):
    """An object to represent a warm air space heating system, provided by a heat pump.

    This object contains the parts of the heat pump calculation that are
    specific to providing space heating via warm air.
    """

    def __init__(
        self,
        heat_pump: "HeatPump",
        service_name: str,
        temp_diff_emit_design: float,
        design_flow_temp_op_cond: float,
        control: TimeControl | None,
        temp_flow: float,
        frac_convective: float,
        volume_heated: float,
    ):
        """Construct a HeatPumpWarmAir object

        Arguments:
        heat_pump -- reference to the HeatPump object providing the service
        service_name -- name of the service demanding energy from the heat pump
        temp_diff_emit_design -- design temperature difference across the emitters, in deg C or K
        design_flow_temp_op_cond -- design flow temperature of the heat pump as installed
        control -- reference to a control object which must implement is_on() and setpnt() funcs
        temp_flow -- flow temperature, in deg C
        frac_convective -- convective fraction for heating
        volume_heated -- volume of zones heated (required for exhaust air HPs only), in m3
        """
        self.__frac_convective = frac_convective
        self.__temp_flow = temp_flow
        # Return temp won't be used in the relevant code paths anyway, so this is arbitrary
        self.__temp_return = temp_flow

        # Upper operating limit for temperature, in deg C
        temp_limit_upper = temp_flow

        self.__heat_pump_service = HeatPumpServiceSpace(
            heat_pump=heat_pump,
            service_name=service_name,
            emitter_type=HeatPumpEmitterType.WARM_AIR,
            temp_limit_upper=temp_limit_upper,
            temp_diff_emit_design=temp_diff_emit_design,
            design_flow_temp_op_cond=design_flow_temp_op_cond,
            control=control,
            volume_heated=volume_heated,
        )

    def temp_setpnt(self) -> float | None:
        return self.__heat_pump_service.temp_setpnt()

    def in_required_period(self) -> bool | None:
        return self.__heat_pump_service.in_required_period()

    def frac_convective(self) -> float:
        return self.__frac_convective

    def energy_output_min(self) -> float:
        return 0.0

    def demand_energy(self, energy_demand: float) -> float:
        """Demand energy (in kWh) from the heat pump

        Arguments:
        energy_demand -- space heating energy demand, in kWh
        """
        return self.__heat_pump_service.demand_energy(
            energy_demand=energy_demand,
            temp_flow=self.__temp_flow,
            temp_return=self.__temp_return,
        )


class HeatPump:
    """An object to represent an electric heat pump"""

    # From CALCM-01 - DAHPSE - V2.0_DRAFT13, section 4.5.3:
    # A minimum temperature difference of 6K between the source and sink
    # temperature is applied to prevent very high Carnot COPs entering the
    # calculation. This only arises when the temperature difference and heating
    # load is small and is unlikely to affect the calculated SPF.
    __temp_diff_limit_low = 6.0  # Kelvin

    # Fraction of the energy input dedicated to auxiliaries when on
    # TODO This is always zero for electric heat pumps, but if we want to deal
    #      with non-electric heat pumps then this will need to be altered.
    __f_aux = 0.0

    def __init__(
        self,
        hp_dict: HeatPumpCharacteristics,
        energy_supply: EnergySupply,
        energy_supply_conn_name_auxiliary: str,
        simulation_time: SimulationTime,
        external_conditions: ExternalConditions,
        number_of_zones: int,
        throughput_exhaust_air: float | None = None,
        energy_supply_heat_source: EnergySupply | None = None,
        output_detailed_results: bool = False,
        boiler: Boiler | None = None,
        cost_schedule_hybrid_hp: dict | None = None,
        project: SimulationProject | None = None,
    ):
        """Construct a HeatPump object

        Arguments:
        hp_dict -- dictionary of heat pump characteristics
        energy_supply -- reference to EnergySupply object
        energy_supply_conn_name_auxiliary
            -- name to be used for EnergySupplyConnection object for auxiliary energy
        simulation_time -- reference to SimulationTime object
        external_conditions -- reference to ExternalConditions object
        number_of_zones  -- number of zones in the project
        throughput_exhaust_air -- throughput (m3/h) of exhaust air
        energy_supply_heat_source -- reference to EnergySupply object representing heat network
                        (for HPs that use heat network as heat source) / other heat source
        output_detailed_results -- if true, save detailed results from each timestep
                                   for later reporting
        boiler -- reference to Boiler object representing boiler
                  (for hybrid heat pumps)
        cost_schedule_hybrid_hp -- dict of cost schedule for heat pump and boiler

        Other variables:
        energy_supply_connections
            -- dictionary with service name strings as keys and corresponding
               EnergySupplyConnection objects as values
        energy_supply_connection_aux -- EnergySupplyConnection object for auxiliary energy
        test_data -- HeatPumpTestData object
        """
        self.__energy_supply = energy_supply
        self.__simulation_time = simulation_time
        self.__external_conditions = external_conditions
        self.__throughput_exhaust_air = throughput_exhaust_air

        self.__energy_supply_connections = {}
        self.__energy_supply_heat_source_connections = {}
        self.__energy_supply_connection_aux = self.__energy_supply.connection(
            end_user_name=energy_supply_conn_name_auxiliary
        )

        self.__service_results = []
        self.__total_time_running_current_timestep_full_load = 0.0
        self.__time_running_continuous = 0.0

        # Assign hp_dict elements to member variables of this class
        self.__source_type = SourceType(hp_dict["source_type"])
        self.__sink_type = HeatPumpSinkType(hp_dict["sink_type"])
        self.__backup_ctrl = HeatPumpBackupControlType(hp_dict["backup_ctrl_type"])
        if self.__backup_ctrl != HeatPumpBackupControlType.NONE:
            self.__time_delay_backup = float(hp_dict["time_delay_backup"])
            if boiler is None:
                self.__power_max_backup = hp_dict["power_max_backup"]
            else:
                self.__power_max_backup = 0
        else:
            self.__power_max_backup = 0
        self.__modulating_ctrl = bool(hp_dict["modulating_control"])
        self.__time_constant_onoff_operation = float(hp_dict["time_constant_onoff_operation"])
        if self.__sink_type != HeatPumpSinkType.AIR:
            self.__temp_return_feed_max = Celcius2Kelvin(
                temp_C=float(hp_dict["temp_return_feed_max"])
            )
        self.__temp_lower_op_limit = Celcius2Kelvin(
            temp_C=float(hp_dict["temp_lower_operating_limit"])
        )
        self.__temp_diff_flow_return_min = float(
            hp_dict["min_temp_diff_flow_return_for_hp_to_operate"]
        )
        self.__var_flow_temp_ctrl_during_test = bool(hp_dict["var_flow_temp_ctrl_during_test"])
        self.__power_heating_circ_pump = (
            0.0 if "power_heating_circ_pump" not in hp_dict else hp_dict["power_heating_circ_pump"]
        )
        self.__power_heating_warm_air_fan = (
            0.0
            if "power_heating_warm_air_fan" not in hp_dict
            else hp_dict["power_heating_warm_air_fan"]
        )

        self.__power_source_circ_pump = hp_dict["power_source_circ_pump"]
        self.__power_standby = hp_dict["power_standby"]
        self.__power_crankcase_heater_mode = hp_dict["power_crankcase_heater"]
        self.__power_off_mode = hp_dict["power_off"]
        self.__boiler = boiler
        self.__cost_schedule_hybrid_hp = cost_schedule_hybrid_hp
        if cost_schedule_hybrid_hp is not None:
            self.__cost_schedule_hp = expand_schedule(
                sched_type=float,
                sched_dict=cost_schedule_hybrid_hp["cost_schedule_hp"],
                sched_main="main",
                nullable=False,
            )
            self.__cost_schedule_boiler = expand_schedule(
                sched_type=float,
                sched_dict=cost_schedule_hybrid_hp["cost_schedule_boiler"],
                sched_main="main",
                nullable=False,
            )
            self.__cost_schedule_start_day = cost_schedule_hybrid_hp["cost_schedule_start_day"]
            self.__cost_schedule_time_series_step = cost_schedule_hybrid_hp[
                "cost_schedule_time_series_step"
            ]
            validate_schedule_length(
                schedule=self.__cost_schedule_boiler,
                expected_length=simulation_time.total_steps_based_on_step(
                    start_day=self.__cost_schedule_start_day,
                    step=self.__cost_schedule_time_series_step,
                ),
            )
            validate_schedule_length(
                schedule=self.__cost_schedule_hp,
                expected_length=simulation_time.total_steps_based_on_step(
                    start_day=self.__cost_schedule_start_day,
                    step=self.__cost_schedule_time_series_step,
                ),
            )
        self.__project = project

        # HPs that use heat network as heat source require different/additional
        # initialisation, which is implemented here
        if self.__source_type == SourceType.HEAT_NETWORK:
            if energy_supply_heat_source is None:
                raise ValueError(
                    "If HP uses heat network as source, then heat network must be specified"
                )
            self.__temp_distribution_heat_network = hp_dict["temp_distribution_heat_network"]
        self.__energy_supply_heat_source = energy_supply_heat_source

        # Exhaust air HP requires different/additional initialisation, which is implemented here
        if self.__source_type.is_exhaust_air and throughput_exhaust_air:
            lowest_air_flow_rate_in_test_data, hp_dict["test_data_EN14825"] = (
                interpolate_exhaust_air_heat_pump_test_data(
                    throughput_exhaust_air=throughput_exhaust_air,
                    hp_test_data=hp_dict["test_data_EN14825"],
                    source_type=self.__source_type,
                )
            )
            self.__overvent_ratio = max(
                1.0,
                lowest_air_flow_rate_in_test_data / throughput_exhaust_air,
            )
            self.__volume_heated_all_services = 0.0
        else:
            self.__overvent_ratio = 1.0
        # TODO For now, disable exhaust air heat pump when conditions are out of
        #      range of test data. Decision to be made on whether to allow this
        #      and if so how to handle it in the calculation
        if self.__overvent_ratio > 1.0:
            raise ValueError(
                "Exhaust air heat pump: Flow rate for associated ventilation "
                "system is lower than flow rate in any of the test data provided."
            )

        # Check there is no remaining test data specific to an air flow rate
        # For exhaust air HPs, this should have been eliminated in the
        # interpolation above and for other HPs, it should not be present in the
        # first place.
        for test_data_record in hp_dict["test_data_EN14825"]:
            if "air_flow_rate" in test_data_record:
                raise ValueError("Unexpected test data specific to an air flow rate")

        # Parse and initialise heat pump test data
        self.__test_data = HeatPumpTestData(hp_test_data=hp_dict["test_data_EN14825"])

        # Mixed exhaust air heat pumps
        if self.__source_type == SourceType.EXHAUST_AIR_MIXED:
            self.__eahp_mixed_max_temp = hp_dict["eahp_mixed_max_temp"]
            self.__eahp_mixed_min_temp = hp_dict["eahp_mixed_min_temp"]
            ext_air_ratio_list = [
                test_data["eahp_mixed_ext_air_ratio"]
                for test_data in hp_dict["test_data_EN14825"]
                if "eahp_mixed_ext_air_ratio" in test_data
            ]
            same_ext_air_ratio = len(set(ext_air_ratio_list))
            if same_ext_air_ratio > 1:
                raise ValueError("Error: More than one unique external air ratio entered.")
            self.__ext_air_ratio = math.fsum(ext_air_ratio_list) / len(ext_air_ratio_list)

        if self.__modulating_ctrl:
            if self.__sink_type == HeatPumpSinkType.AIR:
                self.__temp_min_modulation_rate_low = Celcius2Kelvin(temp_C=20.0)
                self.__min_modulation_rate_low = float(hp_dict["min_modulation_rate_20"])
            elif self.__sink_type in (HeatPumpSinkType.WATER, HeatPumpSinkType.GLYCOL25):
                self.__temp_min_modulation_rate_low = Celcius2Kelvin(temp_C=35.0)
                self.__min_modulation_rate_low = float(hp_dict["min_modulation_rate_35"])
            else:
                raise ValueError("Sink type not recognised")  # PRAGMA: nocover

            if 55.0 in self.__test_data.design_flow_temperatures:
                self.__temp_min_modulation_rate_high = Celcius2Kelvin(temp_C=55.0)
                self.__min_modulation_rate_55 = float(hp_dict["min_modulation_rate_55"])

        # If detailed results are to be output, initialise list
        if output_detailed_results:
            self.__detailed_results = []
        else:
            self.__detailed_results = None

        # Add Buffer Tank object to Heat Pump if defined in input file
        if "BufferTank" in hp_dict and self.__project is not None:
            self.__buffer_tank = BufferTank(
                daily_losses=hp_dict["BufferTank"]["daily_losses"],
                volume=hp_dict["BufferTank"]["volume"],
                pump_fixed_flow_rate=hp_dict["BufferTank"]["pump_fixed_flow_rate"],
                pump_power_at_flow_rate=hp_dict["BufferTank"]["pump_power_at_flow_rate"],
                number_of_zones=number_of_zones,
                simulation_time=self.__simulation_time,
                initial_temp=self.__project.temp_internal_air_prev_timestep(),
                contents=WATER,
                output_detailed_results=output_detailed_results,
            )
        else:
            self.__buffer_tank = None

    @property
    def backup_heater_max_power(self) -> float:
        return self.__power_max_backup

    @property
    def buffer_tank(self) -> BufferTank | None:
        return self.__buffer_tank

    @property
    def energy_supply_connections(self) -> dict[str, EnergySupplyConnection]:
        return self.__energy_supply_connections

    @property
    def boiler(self) -> Boiler | None:
        return self.__boiler

    @property
    def volume_heated_all_services(self) -> float:
        return self.__volume_heated_all_services

    @property
    def service_results(self) -> list[dict[str, Any]]:
        return self.__service_results

    @property
    def total_time_running_current_timestep_full_load(self) -> float:
        return self.__total_time_running_current_timestep_full_load

    @property
    def energy_supply_heat_source_connections(self) -> dict:
        return self.__energy_supply_heat_source_connections

    @property
    def source_type(self) -> SourceType:
        return self.__source_type

    def source_is_exhaust_air(self) -> bool:
        return self.source_type.is_exhaust_air

    def buffer_int_gains(self) -> float:
        if self.__buffer_tank:
            return self.__buffer_tank.internal_gains()
        else:
            return 0.0

    def __create_service_connection(self, service_name: str) -> None:
        # Check that service_name is not already registered
        if service_name in self.__energy_supply_connections.keys():
            raise ValueError("Error: Service name already used: " + service_name)

        # Set up EnergySupplyConnection for this service
        self.__energy_supply_connections[service_name] = self.__energy_supply.connection(
            end_user_name=service_name
        )

        if self.__energy_supply_heat_source:
            self.__energy_supply_heat_source_connections[service_name] = (
                self.__energy_supply_heat_source.connection(end_user_name=service_name)
            )

    def create_service_hot_water_combi(
        self,
        boiler_data: dict,
        service_name: str,
        temp_hot_water: float,
        cold_feed: ColdWaterSource,
    ) -> BoilerServiceWaterCombi:
        if not self.__boiler:
            raise ValueError(
                "Error: Missing Boiler object for hybrid heat pump. "
                "Non-hybrid heat pumps cannot be used as an "
                "instantaneous hot water system"
            )

        return self.__boiler.create_service_hot_water_combi(
            boiler_data=boiler_data,
            service_name=service_name,
            temp_hot_water=temp_hot_water,
            cold_feed=cold_feed,
        )

    def create_service_hot_water(
        self,
        service_name: str,
        temp_limit_upper: float,
        cold_feed: ColdWaterSource,
        controlmin: SetpointTimeControl | CombinationTimeControl,
        controlmax: SetpointTimeControl | CombinationTimeControl,
    ) -> HeatPumpServiceWater:
        """Return a HeatPumpServiceWater object and create an EnergySupplyConnection for it

        Arguments:
        service_name -- name of the service demanding energy from the boiler
        temp_limit_upper -- upper operating limit for temperature, in deg C
        cold_feed -- reference to ColdWaterSource object
        controlmin            -- reference to a control object which must select current
                                the minimum timestep temperature
        controlmax            -- reference to a control object which must select current
                                the maximum timestep temperature
        """
        self.__create_service_connection(service_name=service_name)

        if self.__boiler is not None:
            boiler_service = self.__boiler.create_service_hot_water_regular(
                service_name=service_name,
                cold_feed=cold_feed,
                controlmin=controlmin,
                controlmax=controlmax,
            )
        else:
            boiler_service = None

        return HeatPumpServiceWater(
            self,
            service_name=service_name,
            temp_limit_upper=temp_limit_upper,
            cold_feed=cold_feed,
            controlmin=controlmin,
            controlmax=controlmax,
            boiler_service_water_regular=boiler_service,
        )

    def create_service_space_heating(
        self,
        service_name: str,
        emitter_type: HeatPumpEmitterType,
        temp_limit_upper: float,
        temp_diff_emit_design: float,
        design_flow_temp_op_cond: float,
        control: SetpointTimeControl | CombinationTimeControl | None,
        volume_heated: float,
    ) -> HeatPumpServiceSpace:
        """Return a HeatPumpServiceSpace object and create an EnergySupplyConnection for it

        Arguments:
        service_name -- name of the service demanding energy from the heat pump
        emitter_type -- type of emitters that this space heating service is serving
        temp_limit_upper -- upper operating limit for temperature, in deg C
        temp_diff_emit_design -- design temperature difference across the emitters, in deg C or K
        design_flow_temp_op_cond -- design flow temperature of the heat pump as installed
        control -- reference to a control object which must implement is_on() func
        volume_heated -- volume of zones heated (required for exhaust air HPs only), in m3
        """
        if self.__boiler is not None:
            boiler_service = self.__boiler.create_service_space_heating(
                service_name=service_name, control=control
            )
        else:
            boiler_service = None
        if self.source_type.is_exhaust_air:
            self.__volume_heated_all_services += volume_heated
        self.__create_service_connection(service_name=service_name)
        return HeatPumpServiceSpace(
            heat_pump=self,
            service_name=service_name,
            emitter_type=emitter_type,
            temp_limit_upper=temp_limit_upper,
            temp_diff_emit_design=temp_diff_emit_design,
            design_flow_temp_op_cond=design_flow_temp_op_cond,
            control=control,
            volume_heated=volume_heated,
            boiler_service_space=boiler_service,
        )

    def create_service_space_heating_warm_air(
        self,
        service_name: str,
        control: SetpointTimeControl | CombinationTimeControl | None,
        frac_convective: float,
        volume_heated: float,
    ) -> HeatPumpWarmAir:
        """Return a HeatPumpWarmAir object and create an EnergySupplyConnection for it

        Arguments:
        service_name    -- name of the service demanding energy from the heat pump
        control         -- reference to a control object which must implement is_on() func
        frac_convective -- convective fraction for heating
        volume_heated   -- volume of zones heated (required for exhaust air HPs only), in m3
        """
        if self.__sink_type != HeatPumpSinkType.AIR:
            raise ValueError("Warm air space heating service requires heat pump with sink type Air")

        if self.__boiler is not None:
            # TODO More evidence is required before warm air space heating systems can work with hybrid heat pumps
            raise ValueError(
                "Cannot handle hybrid warm air heat pumps - calculation not implemented"
            )
        if self.source_type.is_exhaust_air:
            self.__volume_heated_all_services += volume_heated

        # Use low temperature test data for space heating - set flow temp such
        # that it matches the one used in the test
        temp_flow = self.__test_data.design_flow_temperatures[0]
        design_flow_temp_op_cond = temp_flow

        # Design temperature difference across the emitters, in deg C or K
        temp_diff_emit_design = max(
            temp_flow / 7.0,
            self.__test_data.temp_spread_test_conditions(
                design_flow_temp_op_cond=design_flow_temp_op_cond
            ),
        )

        self.__create_service_connection(service_name=service_name)
        return HeatPumpWarmAir(
            heat_pump=self,
            service_name=service_name,
            temp_diff_emit_design=temp_diff_emit_design,
            design_flow_temp_op_cond=design_flow_temp_op_cond,
            control=control,
            temp_flow=temp_flow,
            frac_convective=frac_convective,
            volume_heated=volume_heated,
        )

    def __get_temp_source(self) -> float:
        """Get source temp according to rules in CALCM-01 - DAHPSE - V2.0_DRAFT13, 3.1.1"""
        if self.source_type == SourceType.GROUND:
            # Subject to max source temp of 8 degC and min of 0 degC
            temp_ext = self.__external_conditions.air_temp()
            temp_source = max(0, min(8, temp_ext * 0.25806 + 2.8387))
        elif self.source_type == SourceType.OUTSIDE_AIR:
            temp_source = self.__external_conditions.air_temp()
        elif self.source_type == SourceType.EXHAUST_AIR_MEV and self.__project is not None:
            temp_source = self.__project.temp_internal_air_prev_timestep()
        elif self.source_type == SourceType.EXHAUST_AIR_MVHR and self.__project is not None:
            temp_source = self.__project.temp_internal_air_prev_timestep()
        elif self.source_type == SourceType.EXHAUST_AIR_MIXED and self.__project is not None:
            # Mixed exhaust air heat pumps use proportion of airflow from outside
            # combined with the internal air. However, when the external temperature
            # is above a maximum temperature threshold only the internal air is used
            # and when the mixed air temperature is below a minimum temperature threshold.
            temp_ext = self.__external_conditions.air_temp()
            temp_int = self.__project.temp_internal_air_prev_timestep()
            temp_mixed = self.__ext_air_ratio * temp_ext + (1 - self.__ext_air_ratio) * temp_int
            if temp_ext > self.__eahp_mixed_max_temp or temp_mixed < self.__eahp_mixed_min_temp:
                temp_source = temp_int
            else:
                temp_source = temp_mixed

        elif self.__source_type == SourceType.WATER_GROUND:
            # Where water is extracted from the ground and re-injected into the
            # ground or discharged at the surface, the surface temperature is assumed
            # to be constant and equal to the annual average air temperature.
            temp_source = self.__external_conditions.air_temp_annual()
        elif self.__source_type == SourceType.WATER_SURFACE:
            # Where water is extracted from surface water, such as rivers and lakes,
            # it is assumed that this extraction does not substantively effect the
            # average temperature of the water volume, thus it must have a sufficient
            # thermal capacity. The source temperature is taken as the monthly air
            # temperature.
            temp_source = self.__external_conditions.air_temp_monthly()
        elif self.__source_type == SourceType.HEAT_NETWORK:
            temp_source = self.__temp_distribution_heat_network
        else:
            # If we reach here, then earlier input validation has failed, or a
            # SourceType option is missing above.
            raise ValueError("SourceType not valid.")  # PRAGMA: nocover

        return Celcius2Kelvin(temp_C=temp_source)

    def __thermal_capacity_op_cond(
        self, temp_output: float, temp_source: float, design_flow_temp_op_cond: float
    ) -> float:
        """Calculate the thermal capacity of the heat pump at operating conditions

        Based on CALCM-01 - DAHPSE - V2.0_DRAFT13, section 4.4
        """
        if (
            not self.__source_type == SourceType.OUTSIDE_AIR
            and not self.__var_flow_temp_ctrl_during_test
        ):
            thermal_capacity_op_cond = self.__test_data.average_capacity(
                design_flow_temp_op_cond=design_flow_temp_op_cond
            )
        else:
            thermal_capacity_op_cond = self.__test_data.capacity_op_cond_var_flow_or_source_temp(
                temp_output=temp_output,
                temp_source=temp_source,
                mod_ctrl=self.__modulating_ctrl,
                design_flow_temp_op_cond=design_flow_temp_op_cond,
            )

        return thermal_capacity_op_cond

    def __backup_energy_output_max(
        self,
        temp_output: float,
        temp_return_feed: float,
        time_available: float,
        time_start: float,
        hybrid_boiler_service: BoilerServiceWaterRegular | BoilerServiceSpace | None = None,
    ) -> float:
        if self.__backup_ctrl == HeatPumpBackupControlType.TOP_UP:
            # For top up mode, the time passed to the functions
            # should be set to None, as the time available is independant.
            time_elapsed_hp = None
        elif self.__backup_ctrl in (
            HeatPumpBackupControlType.SUBSTITUTE,
            HeatPumpBackupControlType.NONE,
        ):
            time_elapsed_hp = self.__total_time_running_current_timestep_full_load
        else:
            raise ValueError("Invalid HeatPumpBackupControlType")

        if hybrid_boiler_service is not None:
            if isinstance(hybrid_boiler_service, BoilerServiceWaterRegular):
                energy_output_max = hybrid_boiler_service.energy_output_max(
                    temp_flow=Kelvin2Celcius(temp_K=temp_output),
                    temp_return=Kelvin2Celcius(temp_K=temp_return_feed),
                    time_elapsed_hp=time_elapsed_hp,
                )
            elif isinstance(hybrid_boiler_service, BoilerServiceSpace):
                energy_output_max = hybrid_boiler_service.energy_output_max(
                    temp_output=Kelvin2Celcius(temp_K=temp_output),
                    temp_return_feed=Kelvin2Celcius(temp_K=temp_return_feed),
                    time_start=time_start,
                    time_elapsed_hp=time_elapsed_hp,
                )

        else:
            energy_output_max = self.__power_max_backup * time_available

        return energy_output_max

    def __energy_output_max(
        self,
        temp_output: float,
        temp_return_feed: float,
        design_flow_temp_op_cond: float,
        hybrid_boiler_service: BoilerServiceWaterRegular | BoilerServiceSpace | None,
        service_name: str,
        service_type: HeatingServiceType | None = None,
        temp_spread_correction: float = 1.0,
        time_start: float = 0.0,
        emitters_data_for_buffer_tank: dict | None = None,
    ) -> tuple[float, dict[str, Any]] | float:
        """Calculate the maximum energy output of the HP, accounting for time
            spent on higher-priority services

        Note: Call via a HeatPumpService object, not directly.
        """
        timestep = self.__simulation_time.timestep()
        time_available = self.__time_available(time_start=time_start, timestep=timestep)
        temp_source = self.__get_temp_source()

        # If there is buffer tank, energy output max will be affected by the temperature lift required
        # by the tank
        heat_loss_buffer_kWh = 0.0
        if self.__buffer_tank is not None and emitters_data_for_buffer_tank is not None:
            buffer_tank_results = self.__buffer_tank.calc_buffer_tank(
                service_name=service_name,
                emitters_data_for_buffer_tank=emitters_data_for_buffer_tank,
            )

            if "flow_temp_increase_due_to_buffer" in buffer_tank_results[-1]:
                flow_temp_increase_due_to_buffer = buffer_tank_results[-1][
                    "flow_temp_increase_due_to_buffer"
                ]
                temp_output += flow_temp_increase_due_to_buffer
            if "heat_loss_buffer_kWh" in buffer_tank_results[-1]:
                heat_loss_buffer_kWh = (
                    self.__buffer_tank.get_buffer_loss()
                    + buffer_tank_results[-1]["heat_loss_buffer_kWh"]
                )

            emitters_data_for_buffer_tank["results"] = buffer_tank_results[-1]

        if self.__cost_schedule_hybrid_hp is not None and self.__boiler is not None:
            cop_op_cond = self.__cop_op_cond(
                service_type=service_type,
                temp_output=temp_output,
                temp_source=temp_source,
                temp_spread_correction=temp_spread_correction,
                design_flow_temp_op_cond=design_flow_temp_op_cond,
            )
            energy_output_max_boiler = self.__backup_energy_output_max(
                temp_output=temp_output,
                temp_return_feed=temp_return_feed,
                time_available=time_available,
                time_start=time_start,
                hybrid_boiler_service=hybrid_boiler_service,
            )

            boiler_eff = self.__boiler.calc_boiler_eff(
                service_type=service_type,
                temp_return_feed=Kelvin2Celcius(temp_K=temp_return_feed),
                energy_output_required=energy_output_max_boiler,
                time_start=time_start,
                time_elapsed_hp=timestep,
            )
            hp_cost_effective = self.__is_heat_pump_cost_effective(
                cop_op_cond=cop_op_cond, boiler_eff=boiler_eff
            )
        else:
            hp_cost_effective = True

        energy_max = 0
        if not hp_cost_effective:
            energy_max = self.__backup_energy_output_max(
                temp_output=temp_output,
                temp_return_feed=temp_return_feed,
                time_available=time_available,
                time_start=time_start,
                hybrid_boiler_service=hybrid_boiler_service,
            )
        else:
            outside_operating_limits = self.__outside_operating_limits(
                temp_return_feed=temp_return_feed
            )
            power_max_HP = 0.0
            if outside_operating_limits:
                power_max_HP = 0.0
            else:
                power_max_HP = self.__thermal_capacity_op_cond(
                    temp_output=temp_output,
                    temp_source=temp_source,
                    design_flow_temp_op_cond=design_flow_temp_op_cond,
                )

            if (
                self.__backup_ctrl == HeatPumpBackupControlType.NONE
                or not self.__backup_heater_delay_time_elapsed()
                and not outside_operating_limits
            ):
                energy_max = power_max_HP * time_available
            elif self.__backup_ctrl == HeatPumpBackupControlType.TOP_UP:
                energy_max_backup = self.__backup_energy_output_max(
                    temp_output=temp_output,
                    temp_return_feed=temp_return_feed,
                    time_available=time_available,
                    time_start=time_start,
                    hybrid_boiler_service=hybrid_boiler_service,
                )
                energy_max = (power_max_HP * time_available) + energy_max_backup
            elif self.__backup_ctrl == HeatPumpBackupControlType.SUBSTITUTE:
                energy_max_backup = self.__backup_energy_output_max(
                    temp_output=temp_output,
                    temp_return_feed=temp_return_feed,
                    time_available=time_available,
                    time_start=time_start,
                    hybrid_boiler_service=hybrid_boiler_service,
                )
                energy_max = max(power_max_HP * time_available, energy_max_backup)

        if self.__buffer_tank is not None and emitters_data_for_buffer_tank is not None:
            return max(energy_max - heat_loss_buffer_kWh, 0.0), emitters_data_for_buffer_tank
        else:
            return max(energy_max - heat_loss_buffer_kWh, 0.0)

    def __cop_op_cond(
        self,
        service_type: HeatingServiceType | None,
        temp_output: float,  # Kelvin
        temp_source: float,  # Kelvin
        temp_spread_correction: Callable | float,
        design_flow_temp_op_cond: float,
    ) -> float:
        """Calculate CoP at operating conditions"""
        if callable(temp_spread_correction):
            temp_spread_correction_factor = temp_spread_correction(
                temp_output=temp_output,
                temp_source=temp_source,
                design_flow_temp_op_cond=design_flow_temp_op_cond,
            )
        else:
            temp_spread_correction_factor = temp_spread_correction

        # TODO Make if/elif/else chain exhaustive?
        if (
            not self.__source_type == SourceType.OUTSIDE_AIR
            and not self.__var_flow_temp_ctrl_during_test
        ):
            cop_op_cond = (
                temp_spread_correction_factor
                * self.__test_data.cop_op_cond_if_not_air_source(
                    temp_diff_limit_low=self.__temp_diff_limit_low,
                    temp_ext_C=self.__external_conditions.air_temp(),
                    temp_source=temp_source,
                    temp_output=temp_output,
                    design_flow_temp_op_cond=design_flow_temp_op_cond,
                )
            )
        else:
            carnot_cop_op_cond = carnot_cop(
                temp_source=temp_source,
                temp_outlet=temp_output,
                temp_diff_limit_low=self.__temp_diff_limit_low,
            )
            exer_eff_op_cond = self.__test_data.exer_eff_op_cond(
                temp_output=temp_output,
                temp_source=temp_source,
                carnot_cop_op_cond=carnot_cop_op_cond,
                design_flow_temp_op_cond=design_flow_temp_op_cond,
            )

            # CALCM-01 - DAHPSE - V2.0_DRAFT13, section 4.5.5
            # Note: DAHPSE method document section 4.5.5 doesn't have
            # temp_spread_correction_factor in formula below. However, section 4.5.7
            # states that the correction factor is to be applied to the CoP.
            cop_op_cond = max(
                1.0,
                exer_eff_op_cond * carnot_cop_op_cond * temp_spread_correction_factor,
            )

        return cop_op_cond

    def __energy_output_limited(
        self,
        energy_output_required: float,
        temp_output: float | None,
        temp_used_for_scaling: float,
        temp_limit_upper: float,
    ) -> float:
        """Calculate energy output limited by upper temperature"""
        if temp_output is not None and temp_output > temp_limit_upper:
            # If required output temp is above upper limit
            if temp_output == temp_used_for_scaling:
                # If flow and return temps are equal
                return energy_output_required
            else:
                # If flow and return temps are not equal
                flow_temp = temp_limit_upper - temp_used_for_scaling
                if flow_temp > self.__temp_diff_flow_return_min or math.isclose(
                    flow_temp, self.__temp_diff_flow_return_min
                ):
                    # If max. achievable temp diff is at least the min required
                    # for the HP to operate.
                    return (
                        energy_output_required
                        * (temp_limit_upper - temp_used_for_scaling)
                        / (temp_output - temp_used_for_scaling)
                    )
                else:
                    # If max. achievable temp diff is less than the min required
                    # for the HP to operate.
                    return 0.0
        else:
            # If required output temp is below upper limit
            return energy_output_required

    def __backup_heater_delay_time_elapsed(self) -> bool:
        """Check if backup heater is available or still in delay period"""
        return self.__time_running_continuous >= self.__time_delay_backup

    def __outside_operating_limits(self, temp_return_feed: float) -> bool:
        """Check if heat pump is outside operating limits"""
        temp_source = self.__get_temp_source()
        below_min_ext_temp = temp_source < self.__temp_lower_op_limit or math.isclose(
            temp_source, self.__temp_lower_op_limit, abs_tol=1e-10
        )

        if (
            self.__sink_type == HeatPumpSinkType.WATER
            or self.__sink_type == HeatPumpSinkType.GLYCOL25
        ):
            above_temp_return_feed_max = temp_return_feed > self.__temp_return_feed_max
        elif self.__sink_type == HeatPumpSinkType.AIR:
            above_temp_return_feed_max = False
        else:
            raise ValueError("Return feed temp check not defined for sink type")

        return below_min_ext_temp or above_temp_return_feed_max

    def __inadequate_capacity(
        self,
        energy_output_required: float,
        thermal_capacity_op_cond: float,
        temp_output: float,
        time_available: float,
        time_start: float,
        temp_return_feed: float,
        hybrid_boiler_service: BoilerServiceWaterRegular | BoilerServiceSpace | None,
    ) -> bool:
        """Check if heat pump has adequate capacity to meet demand"""
        timestep = self.__simulation_time.timestep()

        # For top-up backup heater, use backup if delay time has elapsed.
        # For substitute backup heater, use backup if delay time has elapsed and
        # backup heater can provide more energy than heat pump. This assumption
        # is required to make the maximum energy output of the system
        # predictable before the demand is known.
        energy_max_backup = self.__backup_energy_output_max(
            temp_output=temp_output,
            temp_return_feed=temp_return_feed,
            time_available=time_available,
            time_start=time_start,
            hybrid_boiler_service=hybrid_boiler_service,
        )

        if (
            self.__backup_ctrl == HeatPumpBackupControlType.TOP_UP
            and self.__backup_heater_delay_time_elapsed()
        ) or (
            self.__backup_ctrl == HeatPumpBackupControlType.SUBSTITUTE
            and self.__backup_heater_delay_time_elapsed()
            and energy_max_backup > thermal_capacity_op_cond * time_available
        ):
            inadequate_capacity = energy_output_required > thermal_capacity_op_cond * timestep
        else:
            inadequate_capacity = False

        return inadequate_capacity

    def __is_heat_pump_cost_effective(
        self,
        cop_op_cond: float,
        boiler_eff: float,
    ) -> bool:
        cost_hp = self.__cost_schedule_hp[
            self.__simulation_time.time_series_idx(
                start_day=self.__cost_schedule_start_day,
                time_series_step=self.__cost_schedule_time_series_step,
            )
        ]
        cost_boiler = self.__cost_schedule_boiler[
            self.__simulation_time.time_series_idx(
                start_day=self.__cost_schedule_start_day,
                time_series_step=self.__cost_schedule_time_series_step,
            )
        ]
        if TYPE_CHECKING:
            # Type check that these are not None, although they should not return None
            # because nullable=False is expand_schedule()
            assert cost_hp is not None
            assert cost_boiler is not None

        cost_hp_cop_op_cond = cost_hp / cop_op_cond
        cost_boiler_eff = cost_boiler / boiler_eff
        if cost_hp_cop_op_cond < cost_boiler_eff or math.isclose(
            cost_hp_cop_op_cond, cost_boiler_eff, abs_tol=1e-10
        ):
            hp_cost_effective = True
        else:
            hp_cost_effective = False
        return hp_cost_effective

    def __use_backup_heater_only(
        self,
        cop_op_cond: float,
        energy_output_required: float,
        thermal_capacity_op_cond: float,
        temp_output: float,
        time_available: float,
        time_start: float,
        temp_return_feed: float,
        hybrid_boiler_service: BoilerServiceWaterRegular | BoilerServiceSpace | None = None,
        boiler_eff: float | None = None,
    ) -> bool:
        """Evaluate boolean conditions that may trigger backup heater"""
        outside_operating_limits = self.__outside_operating_limits(
            temp_return_feed=temp_return_feed
        )
        inadequate_capacity = self.__inadequate_capacity(
            energy_output_required=energy_output_required,
            thermal_capacity_op_cond=thermal_capacity_op_cond,
            temp_output=temp_output,
            time_available=time_available,
            time_start=time_start,
            temp_return_feed=temp_return_feed,
            hybrid_boiler_service=hybrid_boiler_service,
        )

        hp_not_cost_effective = False
        if self.__cost_schedule_hybrid_hp is not None and boiler_eff is not None:
            hp_not_cost_effective = not self.__is_heat_pump_cost_effective(
                cop_op_cond=cop_op_cond,
                boiler_eff=boiler_eff,
            )

        return self.__backup_ctrl != HeatPumpBackupControlType.NONE and (
            outside_operating_limits
            or (inadequate_capacity and self.__backup_ctrl == HeatPumpBackupControlType.SUBSTITUTE)
            or hp_not_cost_effective
        )

    def __time_available(
        self, time_start: float, timestep: float, additional_time_unavailable: float = 0.0
    ) -> float:
        """Calculate time available for the current service"""
        # Assumes that time spent on other services is evenly spread throughout
        # the timestep so the adjustment for start time below is a proportional
        # reduction of the overall time available, not simply a subtraction
        time_available = (
            timestep
            - self.__total_time_running_current_timestep_full_load
            - additional_time_unavailable
        ) * (1.0 - time_start / timestep)
        return time_available

    def __run_demand_energy_calc(
        self,
        service_name: str,
        service_type: HeatingServiceType,
        energy_output_required: float,
        temp_output: float | None,  # Kelvin
        temp_return_feed: float,  # Kelvin
        temp_limit_upper: float,  # Kelvin
        design_flow_temp_op_cond: float,  # Kelvin
        time_constant_for_service: float,
        service_on: bool,  # bool - is service allowed to run?
        temp_spread_correction: float = 1.0,
        temp_used_for_scaling: float | None = None,
        hybrid_boiler_service=None,
        boiler_eff: float | None = None,
        additional_time_unavailable: float = 0.0,
        time_start: float = 0.0,
        emitters_data_for_buffer_tank: dict | None = None,
    ) -> dict[str, Any]:
        """Calculate energy required by heat pump to satisfy demand for the service indicated.

        Note: Call via the __demand_energy func, not directly.
              This function should not save any results to member variables of
              this class, because it may need to be run more than once (e.g. for
              exhaust air heat pumps). Results should be returned to the
              __demand_energy function which calls this one and will save results
              when appropriate.
        Note: The optional variable additional_time_unavailable is used for
              calculating running time without needing to update any state - the
              variable contains the time already committed to other services
              where the running time has not been added to
              self.__total_time_running_current_timestep_full_load
        Note: The optional variable time_start is used to account for situations
              where the service cannot start at the beginning of the timestep
              (e.g. due to emitters having to cool down before the service can
              run). This is then used to decrease the time available proportionally,
              which assumes that the timing of other services is randomly
              distributed, neither coinciding perfectly with the time that the
              current service is running or the time it is not running. This
              variable is relative to the beginning of the timestep
        """
        flow_temp_increase_due_to_buffer = 0.0
        power_buffer_tank_pump = 0.0
        heat_loss_buffer_kWh = 0.0
        if self.__buffer_tank is not None and emitters_data_for_buffer_tank is not None:
            buffer_tank_results = emitters_data_for_buffer_tank["results"]
            if "flow_temp_increase_due_to_buffer" in buffer_tank_results:
                flow_temp_increase_due_to_buffer = buffer_tank_results[
                    "flow_temp_increase_due_to_buffer"
                ]
            if "pump_power_at_flow_rate" in buffer_tank_results:
                power_buffer_tank_pump = buffer_tank_results["pump_power_at_flow_rate"]
            if "heat_loss_buffer_kWh" in buffer_tank_results:
                heat_loss_buffer_kWh = (
                    self.__buffer_tank.get_buffer_loss()
                    + buffer_tank_results["heat_loss_buffer_kWh"]
                )
            # If the service is not working, all the buffer loss is accumulated for the next time step
            if not service_on:
                self.__buffer_tank.update_buffer_loss(buffer_loss=heat_loss_buffer_kWh)
                heat_loss_buffer_kWh = 0.0

        # Adding buffer tank losses to the energy required to be delivered by the HP
        energy_output_required += heat_loss_buffer_kWh

        if temp_output is not None:
            temp_output += flow_temp_increase_due_to_buffer

        if temp_used_for_scaling is None:
            temp_used_for_scaling = temp_return_feed

        timestep = self.__simulation_time.timestep()

        energy_output_limited = self.__energy_output_limited(
            energy_output_required=energy_output_required,
            temp_output=temp_output,
            temp_used_for_scaling=temp_used_for_scaling,
            temp_limit_upper=temp_limit_upper,
        )

        temp_source = self.__get_temp_source()  # Kelvin
        # From here onwards, output temp to be used is subject to the upper limit
        if temp_output is not None:
            temp_output = min(temp_output, temp_limit_upper)  # Kelvin

            # Get thermal capacity and CoP at operating conditions
            thermal_capacity_op_cond = self.__thermal_capacity_op_cond(
                temp_output=temp_output,
                temp_source=temp_source,
                design_flow_temp_op_cond=design_flow_temp_op_cond,
            )
            cop_op_cond = self.__cop_op_cond(
                service_type=service_type,
                temp_output=temp_output,
                temp_source=temp_source,
                temp_spread_correction=temp_spread_correction,
                design_flow_temp_op_cond=design_flow_temp_op_cond,
            )
        else:
            thermal_capacity_op_cond = None
            cop_op_cond = None

        # Calculate time available to run service
        # Note that different values are calculated here for calculations
        # related to capacity and calculations related to load ratio and
        # cycling.
        # For calculations related to capacity, we account for the time
        # required for emitters to cool to the maximum flow temperature at the
        # start of the timestep to account for the effect of needing to allow
        # the emitters to cool down on the heat pump's usable capacity. If
        # there is a requirement to allow emitters to cool down, then the heat
        # pump capacity will be limited by this requirement.
        # However, in reality the maximum flow temperature may be adjusted more
        # frequently than just once per modelling timestep, so the real effect
        # is likely to look more like an overall reduction in demand (and
        # therefore load ratio) across the whole timestep, and so when
        # calculating the load ratio we do not want to adjust the time
        # available as if there were a cool-down period only at the start of
        # the timestep, but instead consider the load ratio over the whole
        # timestep.
        time_available_for_capacity_calc = self.__time_available(
            time_start=time_start,
            timestep=timestep,
            additional_time_unavailable=additional_time_unavailable,
        )
        time_available_for_load_ratio_calc = self.__time_available(
            time_start=0.0,
            timestep=timestep,
            additional_time_unavailable=additional_time_unavailable,
        )

        if thermal_capacity_op_cond is None:
            time_required = 0.0
        else:
            time_required = energy_output_limited / thermal_capacity_op_cond

        # TODO Consider moving some of these checks earlier or to HeatPumpService
        #      classes. May be able to skip a lot of the calculation.
        if hybrid_boiler_service is not None and self.__boiler is not None:
            boiler_eff = self.__boiler.calc_boiler_eff(
                service_type=service_type,
                temp_return_feed=Kelvin2Celcius(temp_K=temp_return_feed),
                energy_output_required=energy_output_required,
                time_start=time_start,
                time_elapsed_hp=timestep,
            )

        if temp_output and cop_op_cond and thermal_capacity_op_cond:
            use_backup_heater_only = self.__use_backup_heater_only(
                cop_op_cond=cop_op_cond,
                energy_output_required=energy_output_required,
                thermal_capacity_op_cond=thermal_capacity_op_cond,
                temp_output=temp_output,
                time_available=time_available_for_capacity_calc,
                time_start=time_start,
                temp_return_feed=temp_return_feed,
                hybrid_boiler_service=hybrid_boiler_service,
                boiler_eff=boiler_eff,
            )
        else:
            use_backup_heater_only = False

        # Calculate energy delivered by HP
        energy_delivered_HP = 0.0
        time_running_current_service_full_load = 0.0
        if not self.__compressor_is_running(
            service_on=service_on, use_backup_heater_only=use_backup_heater_only
        ):
            energy_delivered_HP = 0.0
            # If using back heater only then heat pump does not run
            # therefore set time running to zero.
            time_running_current_service_full_load = 0.0
        elif thermal_capacity_op_cond is not None:
            # Backup heater not providing entire energy requirement
            time_running_current_service_full_load = min(
                time_required, time_available_for_capacity_calc
            )
            energy_delivered_HP = thermal_capacity_op_cond * time_running_current_service_full_load

        # Calculate energy delivered by backup heater
        if (
            self.__backup_ctrl == HeatPumpBackupControlType.NONE
            or not self.__backup_heater_delay_time_elapsed()
            and not use_backup_heater_only
            or not service_on
        ):
            energy_delivered_backup = 0.0
        elif (
            self.__backup_ctrl
            in (
                HeatPumpBackupControlType.TOP_UP,
                HeatPumpBackupControlType.SUBSTITUTE,
            )
            and temp_output is not None
        ):
            energy_max_backup = self.__backup_energy_output_max(
                temp_output=temp_output,
                temp_return_feed=temp_return_feed,
                time_available=time_available_for_capacity_calc,
                time_start=time_start,
                hybrid_boiler_service=hybrid_boiler_service,
            )
            energy_delivered_backup = max(
                min(
                    energy_max_backup,
                    energy_output_required - energy_delivered_HP,
                ),
                0.0,
            )

            # If all energy provided by backup heater, calculate running time consumed
            if use_backup_heater_only and self.__power_max_backup > 0.0:
                time_running_current_service_full_load = min(
                    energy_delivered_backup / self.__power_max_backup,
                    time_available_for_capacity_calc,
                )
        else:
            raise ValueError("Invalid HeatPumpBackupControlType")  # PRAGMA: nocover

        # Calculate energy input to backup heater
        # TODO Account for backup heater efficiency, or call another heating
        #      system object. For now, assume 100% efficiency
        energy_input_backup = energy_delivered_backup

        if hybrid_boiler_service is not None:
            energy_output_required_boiler = energy_delivered_backup
            energy_delivered_backup = 0.0
            energy_input_backup = 0.0
        else:
            energy_output_required_boiler = 0.0

        # Energy used by pumps
        if use_backup_heater_only:
            energy_source_circ_pump = 0.0
        else:
            energy_source_circ_pump = (
                time_running_current_service_full_load * self.__power_source_circ_pump
            )
        if service_type == HeatingServiceType.SPACE and self.__sink_type == HeatPumpSinkType.AIR:
            # If warm air distribution add electricity for warm air fan
            energy_heating_warm_air_fan = (
                time_running_current_service_full_load * self.__power_heating_warm_air_fan
            )
            energy_heating_circ_pump = 0
        else:
            # if wet distribution add electricity for wet distribution.
            energy_heating_warm_air_fan = 0
            energy_heating_circ_pump = time_running_current_service_full_load * (
                self.__power_heating_circ_pump + power_buffer_tank_pump
            )

        # Calculate total energy delivered and input
        energy_delivered_total = energy_delivered_HP + energy_delivered_backup

        if self.__buffer_tank is not None:
            if energy_delivered_total > heat_loss_buffer_kWh or math.isclose(
                energy_delivered_total, heat_loss_buffer_kWh, abs_tol=1e-10
            ):
                energy_delivered_total -= heat_loss_buffer_kWh
                self.__buffer_tank.update_buffer_loss(buffer_loss=0.0)
            else:
                hp_covered_buffer_losses = energy_delivered_total
                energy_delivered_total = 0.0
                self.__buffer_tank.update_buffer_loss(
                    buffer_loss=heat_loss_buffer_kWh - hp_covered_buffer_losses
                )

        return {
            "service_name": service_name,
            "service_type": service_type,
            "service_on": service_on,
            "energy_output_required": energy_output_required,
            "time_constant_for_service": time_constant_for_service,
            "temp_output": temp_output,
            "temp_source": temp_source,
            "cop_op_cond": cop_op_cond,
            "thermal_capacity_op_cond": thermal_capacity_op_cond,
            "time_running_full_load": time_running_current_service_full_load,
            "time_available_for_capacity_calc": time_available_for_capacity_calc,
            "time_available_for_load_ratio_calc": time_available_for_load_ratio_calc,
            "use_backup_heater_only": use_backup_heater_only,
            "energy_delivered_HP": energy_delivered_HP,
            "energy_input_backup": energy_input_backup,
            "energy_delivered_backup": energy_delivered_backup,
            "energy_delivered_total": energy_delivered_total,
            "energy_heating_circ_pump": energy_heating_circ_pump,
            "energy_source_circ_pump": energy_source_circ_pump,
            "energy_output_required_boiler": energy_output_required_boiler,
            "energy_heating_warm_air_fan": energy_heating_warm_air_fan,
        }

    def __load_ratio_and_mode(
        self,
        time_running_current_service: float,
        time_available_for_current_service: float,
        temp_output: float,
    ) -> tuple[float, float, bool]:
        # Calculate load ratio
        if math.isclose(time_available_for_current_service, 0.0, abs_tol=1e-10):
            if not math.isclose(time_running_current_service, 0.0, abs_tol=1e-10):
                raise ValueError(
                    "Calculated time running is not zero despite no time being available"
                )
            load_ratio = 0.0
        else:
            load_ratio = time_running_current_service / time_available_for_current_service

        if self.__modulating_ctrl:
            if 55.0 in self.__test_data.design_flow_temperatures:
                load_ratio_continuous_min = np.interp(
                    temp_output,
                    [self.__temp_min_modulation_rate_low, self.__temp_min_modulation_rate_high],
                    [self.__min_modulation_rate_low, self.__min_modulation_rate_55],
                )
                if TYPE_CHECKING:
                    assert isinstance(load_ratio_continuous_min, float)
            else:
                load_ratio_continuous_min = self.__min_modulation_rate_low
        else:
            # On/off heat pump cannot modulate below maximum power
            load_ratio_continuous_min = 1.0

        # Determine whether or not HP is operating in on/off mode
        hp_operating_in_onoff_mode = (
            load_ratio > 0
            and not math.isclose(load_ratio, 0.0, abs_tol=1e-10)
            and load_ratio < load_ratio_continuous_min
        )

        return load_ratio, load_ratio_continuous_min, hp_operating_in_onoff_mode

    def __compressor_is_running(self, service_on: bool, use_backup_heater_only: bool) -> bool:
        return service_on and not use_backup_heater_only

    def __energy_input_compressor(
        self,
        service_on: bool,
        use_backup_heater_only: bool,
        hp_operating_in_onoff_mode: bool,
        energy_delivered_HP: float,
        energy_delivered_HP_aggregated: float,
        thermal_capacity_op_cond: float | None,
        cop_op_cond: float,
        time_available_for_current_service: float,
        load_ratio: float,
        load_ratio_continuous_min: float,
        time_constant_for_service: float,
        service_type: HeatingServiceType | None,
    ) -> tuple[float, float]:
        if thermal_capacity_op_cond is None:
            return 0.0, 0.0

        compressor_power_full_load = thermal_capacity_op_cond / cop_op_cond

        # CALCM-01 - DAHPSE - V2.0_DRAFT13, section 4.5.10, step 1:
        compressor_power_min_load = compressor_power_full_load * load_ratio_continuous_min

        if not self.__compressor_is_running(
            service_on=service_on, use_backup_heater_only=use_backup_heater_only
        ):
            energy_input_HP = 0.0
        else:
            if hp_operating_in_onoff_mode:
                # BS EN 15316-4-2:2017 equation 28
                power_used_due_to_inertia_effects = (
                    compressor_power_min_load
                    * self.__time_constant_onoff_operation
                    * load_ratio
                    * (1.0 - load_ratio)
                    / time_constant_for_service
                )

                # Based on BS EN 15316-4-2:2017 equations 25 and 26, with
                # addition of weighting factor to handle existence of more than
                # one space heating service
                compressor_power_part_load_average = compressor_power_full_load * load_ratio

                # Based on BS EN 15316-4-2:2017 equation 29
                # Note: The variable t_H in equation 29 of EN 15316-4-2:2017 is
                # implied to be the running time required at full load, but
                # this is not consistent with the use of part-load compressor
                # power (P_gen,comp,LR) and leads to very low cycling energy
                # when multiplied by the cycling power (P_gen,comp,ONOF,LR) for
                # oversized heat pumps because the running time required at
                # full load for oversized heat pumps is relatively low.
                # Using the part-load running time (i.e. the time the heat pump
                # would run at the relevant load ratio) also does not make
                # sense given that both P_(gen,comp,LR) (from equations 25 and
                # 26)  and P_(gen,comp,ONOF,LR) (from equation 28) already
                # account for load ratio based on the time available after
                # water heating. In other words, both power variables are
                # already averaged over the time available rather than being
                # the power output only during the “on” part of the on-off
                # cycle.
                # Therefore, the approach used here is to use the time
                # available after running higher-priority services in equation
                # 29.
                energy_input_HP = (
                    compressor_power_part_load_average * (1.0 + self.__f_aux)
                    + power_used_due_to_inertia_effects
                ) * time_available_for_current_service

                # As the time available for space heating applies to all space
                # heating services combined, we need to avoid double-counting
                # by apportioning it between the space heating services in
                # proportion to the energy delivered for each space heating
                # service
                weighting_factor = energy_delivered_HP / energy_delivered_HP_aggregated
                energy_input_HP *= weighting_factor

            else:
                # If not operating in on/off mode
                energy_input_HP = energy_delivered_HP / cop_op_cond

        return energy_input_HP, compressor_power_min_load

    def __demand_energy(
        self,
        service_name: str,
        service_type: HeatingServiceType,
        energy_output_required: float,
        temp_output: float,  # Kelvin
        temp_return_feed: float,  # Kelvin
        temp_limit_upper: float,  # Kelvin
        design_flow_temp_op_cond: float,  # Kelvin
        time_constant_for_service: float,
        service_on: bool,  # bool - is service allowed to run?
        temp_spread_correction: float = 1.0,
        temp_used_for_scaling: float | None = None,
        time_start: float = 0.0,
        hybrid_boiler_service: BoilerServiceWaterRegular | BoilerServiceSpace | None = None,
        emitters_data_for_buffer_tank: dict | None = None,
        update_heat_source_state: bool = True,
    ) -> float:
        """Calculate energy required by heat pump to satisfy demand for the service indicated.

        Note: Call via a HeatPumpService object, not directly.
        """
        service_results = self.__run_demand_energy_calc(
            service_name=service_name,
            service_type=service_type,
            energy_output_required=energy_output_required,
            temp_output=temp_output,
            temp_return_feed=temp_return_feed,
            temp_limit_upper=temp_limit_upper,
            design_flow_temp_op_cond=design_flow_temp_op_cond,
            time_constant_for_service=time_constant_for_service,
            service_on=service_on,
            temp_spread_correction=temp_spread_correction,
            temp_used_for_scaling=temp_used_for_scaling,
            hybrid_boiler_service=hybrid_boiler_service,
            time_start=time_start,
            emitters_data_for_buffer_tank=emitters_data_for_buffer_tank,
        )

        if hybrid_boiler_service is not None:
            # Call demand function for boiler and
            # return the boiler running time so that it can be added to the total running time
            is_hybrid_service = True

            if self.__backup_ctrl == HeatPumpBackupControlType.TOP_UP:
                # For top up mode, the time passed to the functions
                # should be set to None, as the time available is independant.
                time_elapsed_hp = None
            elif self.__backup_ctrl in (
                HeatPumpBackupControlType.SUBSTITUTE,
                HeatPumpBackupControlType.NONE,
            ):
                time_elapsed_hp = self.__total_time_running_current_timestep_full_load
            else:
                raise ValueError("Invalid HeatPumpBackupControlType")  # PRAGMA: nocover

            if isinstance(hybrid_boiler_service, BoilerServiceWaterRegular):
                service_results["energy_output_delivered_boiler"], time_running_boiler = (
                    hybrid_boiler_service.demand_energy(
                        energy_demand=service_results["energy_output_required_boiler"],
                        temp_flow=Kelvin2Celcius(temp_K=temp_output),
                        temp_return=Kelvin2Celcius(temp_K=temp_return_feed),
                        hybrid_service=is_hybrid_service,
                        time_elapsed_hp=time_elapsed_hp,
                        update_heat_source_state=update_heat_source_state,
                    )
                )
            elif isinstance(hybrid_boiler_service, BoilerServiceSpace):
                service_results["energy_output_delivered_boiler"], time_running_boiler = (
                    hybrid_boiler_service.demand_energy(
                        energy_demand=service_results["energy_output_required_boiler"],
                        temp_flow=Kelvin2Celcius(temp_K=temp_output),
                        temp_return=Kelvin2Celcius(temp_K=temp_return_feed),
                        time_start=time_start,
                        hybrid_service=is_hybrid_service,
                        time_elapsed_hp=time_elapsed_hp,
                        update_heat_source_state=update_heat_source_state,
                    )
                )
            if (
                self.__backup_ctrl == HeatPumpBackupControlType.SUBSTITUTE
                and update_heat_source_state
            ):
                self.__total_time_running_current_timestep_full_load += time_running_boiler
        else:
            service_results["energy_output_delivered_boiler"] = 0.0

        # Save results that are needed later (in the timestep_end function)
        if update_heat_source_state:
            self.__service_results.append(service_results)
            self.__total_time_running_current_timestep_full_load += service_results[
                "time_running_full_load"
            ]

        return (
            service_results["energy_delivered_total"]
            + service_results["energy_output_delivered_boiler"]
        )

    def __running_time_throughput_factor(
        self,
        space_heat_running_time_cumulative: float,
        service_name: str,
        service_type: HeatingServiceType,
        energy_output_required: float,
        temp_output: float,
        temp_return_feed: float,
        temp_limit_upper: float,
        design_flow_temp_op_cond: float,
        time_constant_for_service: float,
        service_on: bool,
        volume_heated_by_service: float,
        temp_spread_correction: float,
        time_start: float = 0.0,
    ) -> tuple[float, float]:
        """Return the cumulative running time and throughput factor (exhaust air HPs only)"""

        # TODO Run HP calculation to get total running time incl space heating,
        #      but do not save space heating running time
        service_results = self.__run_demand_energy_calc(
            service_name=service_name,
            service_type=service_type,
            energy_output_required=energy_output_required,
            temp_output=temp_output,
            temp_return_feed=temp_return_feed,
            temp_limit_upper=temp_limit_upper,
            design_flow_temp_op_cond=design_flow_temp_op_cond,
            time_constant_for_service=time_constant_for_service,
            service_on=service_on,
            temp_spread_correction=temp_spread_correction,
            additional_time_unavailable=space_heat_running_time_cumulative,
            time_start=time_start,
        )

        throughput_factor = self.__calc_throughput_factor(
            time_running=service_results["time_running_full_load"]
        )

        # Adjust throughput factor to match simplifying assumption that all
        # extra ventilation required due to space heating demand in the current
        # zone is assigned to current zone
        throughput_factor_zone = (
            throughput_factor - 1.0
        ) * self.__volume_heated_all_services / volume_heated_by_service + 1.0

        return service_results["time_running_full_load"], throughput_factor_zone

    def __calc_throughput_factor(self, time_running: float) -> float:
        timestep = self.__simulation_time.timestep()

        # Apply overventilation ratio to part of timestep where HP is running
        # to calculate throughput_factor.
        throughput_factor = (
            (timestep - time_running) + self.__overvent_ratio * time_running
        ) / timestep
        return throughput_factor

    def throughput_factor(self) -> float:
        return self.__calc_throughput_factor(
            time_running=self.__total_time_running_current_timestep_full_load
        )

    def __calc_energy_input(self) -> None:
        for service_data in self.__service_results:
            temp_output = service_data["temp_output"]
            energy_input_backup = service_data["energy_input_backup"]
            energy_heating_circ_pump = service_data["energy_heating_circ_pump"]
            energy_source_circ_pump = service_data["energy_source_circ_pump"]
            energy_heating_warm_air_fan = service_data["energy_heating_warm_air_fan"]
            use_backup_heater_only = service_data["use_backup_heater_only"]

            if service_data["service_type"] == HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR:
                # The definition of load ratio in equation 15 from EN 15316-4-2
                # (along with the definition of hot water running time in
                # equation 11) implies that water heating always runs at full-load.
                # This is likely to be true in practice as the goal will be to
                # heat the water as quickly as possible and then return to
                # space heating operation
                # This calculation follows Path B from the standard, and the
                # definition of load ratio in equation 35 from EN 15316-4-2
                # implies that the combined load ratio for both water and space
                # heating should be used in the calculations. However, this
                # does not account for any variation in heat pump output
                # between the two services (e.g. running at full load for water
                # heating and then in on-off mode to meet low space heating
                # demand). It also causes problems with equation 28, which
                # requires the time constant of the particular service under
                # consideration.
                load_ratio = 1.0
                load_ratio_continuous_min = 1.0
                hp_operating_in_onoff_mode = False
                time_available_for_current_service = service_data[
                    "time_available_for_load_ratio_calc"
                ]
                energy_delivered_HP_aggregated = service_data["energy_delivered_HP"]

            elif service_data["service_type"] == HeatingServiceType.SPACE:
                # Aggregate space heating services
                # TODO This is only necessary because the model cannot handle an
                #      emitter circuit that serves more than one zone. If/when this
                #      capability is added, there will no longer be separate space
                #      heating services for each zone and this aggregation can be
                #      removed as it will not be necessary. At that point, the other
                #      contents of this function could also be moved back to their
                #      original locations
                time_running_for_load_ratio = math.fsum(
                    x["time_running_full_load"]
                    for x in self.__service_results
                    if x["service_type"] == HeatingServiceType.SPACE
                )
                time_available_for_current_service = max(
                    x["time_available_for_load_ratio_calc"]
                    for x in self.__service_results
                    if x["service_type"] == HeatingServiceType.SPACE
                )
                energy_delivered_HP_aggregated = math.fsum(
                    x["energy_delivered_HP"]
                    for x in self.__service_results
                    if x["service_type"] == HeatingServiceType.SPACE
                )
                # TODO Check that certain parameters are the same across all space heating services

                load_ratio, load_ratio_continuous_min, hp_operating_in_onoff_mode = (
                    self.__load_ratio_and_mode(
                        time_running_current_service=time_running_for_load_ratio,
                        time_available_for_current_service=time_available_for_current_service,
                        temp_output=temp_output,
                    )
                )
            else:
                raise ValueError(
                    f"Service type ({service_data['service_type']}) should either be DOMESTIC_HOT_WATER_REGULAR or SPACE."
                )

            if use_backup_heater_only:
                service_data["time_running_part_load"] = service_data["time_running_full_load"]
            else:
                service_data["time_running_part_load"] = service_data[
                    "time_running_full_load"
                ] / max(load_ratio, load_ratio_continuous_min)

            energy_input_HP, compressor_power_min_load = self.__energy_input_compressor(
                service_on=service_data["service_on"],
                use_backup_heater_only=use_backup_heater_only,
                hp_operating_in_onoff_mode=hp_operating_in_onoff_mode,
                energy_delivered_HP=service_data["energy_delivered_HP"],
                energy_delivered_HP_aggregated=energy_delivered_HP_aggregated,
                thermal_capacity_op_cond=service_data["thermal_capacity_op_cond"],
                cop_op_cond=service_data["cop_op_cond"],
                time_available_for_current_service=time_available_for_current_service,
                load_ratio=load_ratio,
                load_ratio_continuous_min=load_ratio_continuous_min,
                time_constant_for_service=service_data["time_constant_for_service"],
                service_type=service_data["service_type"],
            )
            energy_input_total = (
                energy_input_HP
                + energy_input_backup
                + energy_heating_circ_pump
                + energy_source_circ_pump
                + energy_heating_warm_air_fan
            )

            service_data["compressor_power_min_load"] = compressor_power_min_load
            service_data["load_ratio_continuous_min"] = load_ratio_continuous_min
            service_data["load_ratio"] = load_ratio
            service_data["hp_operating_in_onoff_mode"] = hp_operating_in_onoff_mode
            service_data["energy_input_HP"] = energy_input_HP
            service_data["energy_input_total"] = energy_input_total

            # Feed/return results to other modules
            self.__energy_supply_connections[service_data["service_name"]].demand_energy(
                amount_demanded=energy_input_total,
            )

    def __calc_auxiliary_energy(
        self, timestep: float, time_remaining_current_timestep_part_load: float
    ) -> tuple[float, float, float]:
        """Calculate auxiliary energy according to CALCM-01 - DAHPSE - V2.0_DRAFT13, section 4.7"""

        # Retrieve control settings for this timestep
        heating_profile_on = False
        water_profile_on = False
        for service_data in self.__service_results:
            if service_data["service_type"] == HeatingServiceType.SPACE:
                heating_profile_on = service_data["service_on"]
            elif service_data["service_type"] == HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR:
                water_profile_on = service_data["service_on"]
            else:
                raise ValueError("HeatingServiceType not recognised")

        # Energy used in standby and crankcase heater mode
        # TODO Crankcase heater mode appears to be relevant only when HP is
        #      available to provide space heating. Therefore, it could be added
        #      to space heating energy consumption instead of auxiliary
        # TODO Standby power is only relevant when at least one service is
        #      available. Therefore, it could be split between the available
        #      services rather than treated as auxiliary
        energy_off_mode = 0.0
        energy_standby = 0.0
        energy_crankcase_heater_mode = 0.0
        if heating_profile_on:
            energy_standby = time_remaining_current_timestep_part_load * self.__power_standby
            energy_crankcase_heater_mode = (
                time_remaining_current_timestep_part_load * self.__power_crankcase_heater_mode
            )
        elif not heating_profile_on and water_profile_on:
            energy_standby = time_remaining_current_timestep_part_load * self.__power_standby
        # Energy used in off mode
        elif not heating_profile_on and not water_profile_on:
            energy_off_mode = timestep * self.__power_off_mode
        else:
            raise RuntimeError()  # Should never get here. #PRAGMA: nocover

        energy_aux = energy_standby + energy_crankcase_heater_mode + energy_off_mode
        self.__energy_supply_connection_aux.demand_energy(amount_demanded=energy_aux)
        return energy_standby, energy_crankcase_heater_mode, energy_off_mode

    def __extract_energy_from_source(self) -> None:
        """Calculate energy extracted from heat source (heat network or environment such as ground)"""
        for service_data in self.__service_results:
            service_name = service_data["service_name"]
            energy_delivered_HP = service_data["energy_delivered_HP"]
            energy_input_HP = service_data["energy_input_HP"]

            # When heat pump is operating at very low load ratio, the energy consumption due to
            # inertia effects may cause the energy input to exceed the energy output. The extra
            # energy would most likely be lost through the casing, but such losses are not part of
            # the energy extracted from the heat source so the energy extracted must not be allowed
            # to become negative.
            energy_extracted_HP = max(0.0, energy_delivered_HP - energy_input_HP)

            self.__energy_supply_heat_source_connections[service_name].demand_energy(
                amount_demanded=energy_extracted_HP
            )

    def timestep_end(self) -> None:
        """Calculations to be done at the end of each timestep"""
        self.__calc_energy_input()

        timestep = self.__simulation_time.timestep()
        time_remaining_current_timestep_full_load = (
            timestep - self.__total_time_running_current_timestep_full_load
        )
        time_remaining_current_timestep_part_load = timestep - math.fsum(
            x["time_running_part_load"] for x in self.__service_results
        )

        if math.isclose(time_remaining_current_timestep_full_load, 0.0, abs_tol=1e-10):
            self.__time_running_continuous += self.__total_time_running_current_timestep_full_load
        else:
            self.__time_running_continuous = 0.0

        energy_standby, energy_crankcase_heater_mode, energy_off_mode = (
            self.__calc_auxiliary_energy(
                timestep=timestep,
                time_remaining_current_timestep_part_load=time_remaining_current_timestep_part_load,
            )
        )

        if self.__energy_supply_heat_source:
            self.__extract_energy_from_source()

        # If detailed results are to be output, save the results from the current timestep
        if self.__detailed_results is not None:
            self.__service_results.append(
                {
                    "energy_standby": energy_standby,
                    "energy_crankcase_heater_mode": energy_crankcase_heater_mode,
                    "energy_off_mode": energy_off_mode,
                }
            )
            self.__detailed_results.append(self.__service_results)

        # Variables below need to be reset at the end of each timestep.
        self.__total_time_running_current_timestep_full_load = 0.0
        self.__service_results = []

    def output_detailed_results(
        self,
        hot_water_energy_output: dict[str, list[float]],
        hotwatersource_name_for_heatpump_service: dict[str, str],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Output detailed results of heat pump calculation"""

        # Define parameters to output
        # Second element of each tuple controls whether item is summed for annual total
        output_parameters = [
            ("service_name", None, False),
            ("service_type", None, False),
            ("service_on", None, False),
            ("energy_output_required", "kWh", True),
            ("temp_output", "K", False),
            ("temp_source", "K", False),
            ("thermal_capacity_op_cond", "kW", False),
            ("cop_op_cond", None, False),
            ("time_running_full_load", "hours", True),
            ("time_running_part_load", "hours", True),
            ("load_ratio", None, False),
            ("hp_operating_in_onoff_mode", None, False),
            ("energy_delivered_HP", "kWh", True),
            ("energy_delivered_backup", "kWh", True),
            ("energy_delivered_total", "kWh", True),
            ("energy_input_HP", "kWh", True),
            ("energy_input_backup", "kWh", True),
            ("energy_heating_circ_pump", "kWh", True),
            ("energy_source_circ_pump", "kWh", True),
            ("energy_heating_warm_air_fan", "kWh", True),
            ("energy_input_total", "kWh", True),
            ("energy_output_delivered_boiler", "kWh", True),
        ]
        aux_parameters = [
            ("energy_standby", "kWh", True),
            ("energy_crankcase_heater_mode", "kWh", True),
            ("energy_off_mode", "kWh", True),
        ]

        results_per_timestep = {"auxiliary": {}}
        # Report auxiliary parameters (not specific to a service)
        for parameter, param_unit, _ in aux_parameters:
            results_per_timestep["auxiliary"][(parameter, param_unit)] = []
            if self.__detailed_results:
                for service_results in self.__detailed_results:
                    result = service_results[-1][parameter]
                    results_per_timestep["auxiliary"][(parameter, param_unit)].append(result)
        # For each service, report required output parameters
        for service_idx, service_name in enumerate(self.__energy_supply_connections.keys()):
            results_per_timestep[service_name] = {}
            # Look up each required parameter
            for parameter, param_unit, _ in output_parameters:
                results_per_timestep[service_name][(parameter, param_unit)] = []
                # Look up value of required parameter in each timestep
                if self.__detailed_results:
                    for service_results in self.__detailed_results:
                        result = service_results[service_idx][parameter]
                        results_per_timestep[service_name][(parameter, param_unit)].append(result)
            # For water heating service, record hot water energy delivered from tank
            if (
                self.__detailed_results
                and self.__detailed_results[0][service_idx]["service_type"]
                == HeatingServiceType.DOMESTIC_HOT_WATER_REGULAR
            ):
                # For DHW, need to include storage and primary circuit losses.
                # Can do this by replacing H5 numerator with total energy
                # draw-off from hot water cylinder.
                hws_name = hotwatersource_name_for_heatpump_service[service_name]
                results_per_timestep[service_name][("energy_delivered_H5", "kWh")] = (
                    [None]
                    * len(results_per_timestep[service_name][("energy_delivered_total", "kWh")])
                    if hws_name not in hot_water_energy_output.keys()
                    else hot_water_energy_output[hws_name]
                )
            else:
                # TODO Note that the below assumes there is no buffer tank for
                #      space heating, which is not currently included in the
                #      model. If this is included in future, this code will need
                #      to be revised.
                results_per_timestep[service_name][("energy_delivered_H5", "kWh")] = (
                    results_per_timestep[service_name][("energy_delivered_total", "kWh")]
                )

        results_annual = {
            "Overall": {
                (parameter, param_units): 0.0
                for parameter, param_units, incl_in_annual in output_parameters
                if incl_in_annual
            },
            "auxiliary": {},
        }
        results_annual["Overall"][("energy_delivered_H5", "kWh")] = 0.0
        # Report auxiliary parameters (not specific to a service)
        for parameter, param_unit, incl_in_annual in aux_parameters:
            if incl_in_annual:
                results_annual["auxiliary"][(parameter, param_unit)] = math.fsum(
                    results_per_timestep["auxiliary"][(parameter, param_unit)]
                )
        # For each service, report required output parameters
        for service_name in self.__energy_supply_connections.keys():
            results_annual[service_name] = {}
            for parameter, param_unit, incl_in_annual in output_parameters:
                if incl_in_annual:
                    parameter_annual_total = math.fsum(
                        results_per_timestep[service_name][(parameter, param_unit)]
                    )
                    results_annual[service_name][(parameter, param_unit)] = parameter_annual_total
                    results_annual["Overall"][(parameter, param_unit)] += parameter_annual_total

            if None in results_per_timestep[service_name][("energy_delivered_H5", "kWh")]:
                results_annual[service_name][("energy_delivered_H5", "kWh")] = None
                results_annual["Overall"][("energy_delivered_H5", "kWh")] = None
            else:
                results_annual[service_name][("energy_delivered_H5", "kWh")] = math.fsum(
                    results_per_timestep[service_name][("energy_delivered_H5", "kWh")]
                )
                if results_annual["Overall"][("energy_delivered_H5", "kWh")] is not None:
                    results_annual["Overall"][("energy_delivered_H5", "kWh")] += results_annual[
                        service_name
                    ][("energy_delivered_H5", "kWh")]

            # For each service, calculate CoP at different system boundaries
            self.__calc_service_cop(results_totals=results_annual[service_name])

        # Calculate overall CoP for all services combined
        self.__calc_service_cop(
            results_totals=results_annual["Overall"], results_auxiliary=results_annual["auxiliary"]
        )

        return results_per_timestep, results_annual

    def __calc_service_cop(
        self,
        results_totals: dict[tuple[str, str | None], Any],
        results_auxiliary: dict | None = None,
    ) -> dict[tuple[str, str | None], float | None]:
        """Calculate CoP for whole simulation period for the given service (or overall)"""
        # Add auxiliary energy to overall CoP
        if results_auxiliary is not None:
            energy_auxiliary = math.fsum(result for result in results_auxiliary.values())
        else:
            energy_auxiliary = 0.0

        # Calculate CoP at different system boundaries
        cop_h1_numerator = results_totals[("energy_delivered_HP", "kWh")]
        cop_h1_denominator = results_totals[("energy_input_HP", "kWh")] + energy_auxiliary
        cop_h2_numerator = cop_h1_numerator
        cop_h2_denominator = cop_h1_denominator + results_totals[("energy_source_circ_pump", "kWh")]
        cop_h3_numerator = cop_h2_numerator + results_totals[("energy_delivered_backup", "kWh")]
        cop_h3_denominator = cop_h2_denominator + results_totals[("energy_input_backup", "kWh")]
        cop_h4_numerator = cop_h3_numerator
        cop_h4_denominator = (
            cop_h3_denominator
            + results_totals[("energy_heating_circ_pump", "kWh")]
            + results_totals[("energy_heating_warm_air_fan", "kWh")]
        )
        cop_h5_numerator = results_totals[("energy_delivered_H5", "kWh")]
        cop_h5_denominator = cop_h4_denominator

        if math.isclose(cop_h1_denominator, 0.0, abs_tol=1e-10):
            results_totals[("CoP (H1)", None)] = 0.0
        else:
            results_totals[("CoP (H1)", None)] = cop_h1_numerator / cop_h1_denominator

        if math.isclose(cop_h2_denominator, 0.0, abs_tol=1e-10):
            results_totals[("CoP (H2)", None)] = 0.0
        else:
            results_totals[("CoP (H2)", None)] = cop_h2_numerator / cop_h2_denominator

        if math.isclose(cop_h3_denominator, 0.0, abs_tol=1e-10):
            results_totals[("CoP (H3)", None)] = 0.0
        else:
            results_totals[("CoP (H3)", None)] = cop_h3_numerator / cop_h3_denominator

        if math.isclose(cop_h4_denominator, 0.0, abs_tol=1e-10):
            results_totals[("CoP (H4)", None)] = 0.0
        else:
            results_totals[("CoP (H4)", None)] = cop_h4_numerator / cop_h4_denominator

        if math.isclose(cop_h5_denominator, 0.0, abs_tol=1e-10):
            results_totals[("CoP (H5)", None)] = 0.0
        elif cop_h5_numerator is None:
            cop_h5_note = "Note: Cannot calculate CoP (H5) when HP is heating a pre-heat tank"
            results_totals[("CoP (H5)", cop_h5_note)] = None
        else:
            cop_h5_note = "Note: For water heating services, only valid when HP is only heat source"
            results_totals[("CoP (H5)", cop_h5_note)] = cop_h5_numerator / cop_h5_denominator

        return results_totals


class HeatPump_HWOnly(HeatSourceBase):
    """An object to represent an electric hot-water-only heat pump, tested to EN 16147"""

    def __init__(
        self,
        power_max: float,
        test_data: dict[str, HWHeatPumpData],
        vol_daily_average: float,
        tank_volume: float,
        daily_losses: float,
        heat_exchanger_surface_area: float,
        in_use_factor_mismatch: float,
        tank_volume_declared: float,
        heat_exchanger_surface_area_declared: float | None,
        daily_losses_declared: float,
        energy_supply_conn: EnergySupplyConnection,
        simulation_time: SimulationTime,
        controlmin: TimeControl,
        controlmax: TimeControl,
    ):
        """Construct a HeatPump_HWOnly object

        Arguments:
        power_max           -- in kW
        test_data           -- dictionary with keys denoting tapping profile letter (M or L)
                               and values being HWHeatPumpData dictionary
        vol_daily_average   -- annual average hot water use for the dwelling, in litres / day
        tank_volume         -- volume of tank in litres
        daily_losses        -- daily losses in kWh/day
        heat_exchanger_surface_area -- surface area of heat exchanger in m2
        in_use_factor_mismatch      -- in use factor to be applied to heat pump efficiency
        tank_volume_declared        -- tank volume stored in the database in litres
        heat_exchanger_surface_area_declared
            -- surface area of heat exchanger stored in the database in m2
        daily_losses_declared       -- standing heat loss in kWh/day
        energy_supply_conn          -- reference to EnergySupplyConnection object
        simulation_time     -- reference to SimulationTime object
        controlmin          -- reference to a control object which must select current
                               the minimum timestep temperature
        controlmax          -- reference to a control object which must select current
                               the maximum timestep temperature
        """

        self.__pwr = power_max
        self.__energy_supply_conn = energy_supply_conn
        self.__simulation_time = simulation_time
        self.__tank_volume = tank_volume
        self.__daily_losses = daily_losses
        self.__heat_exchanger_surface_area = heat_exchanger_surface_area
        self.__in_use_factor_mismatch = in_use_factor_mismatch
        self.__tank_volume_declared = tank_volume_declared
        self.__heat_exchanger_surface_area_declared = heat_exchanger_surface_area_declared
        self.__daily_losses_declared = daily_losses_declared
        self.__vol_daily_average = vol_daily_average
        self.__controlmin = controlmin
        self.__controlmax = controlmax

        def init_efficiency_tapping_profile(
            cop_dhw: float,
            hw_tapping_prof_daily_total: float,
            energy_input_measured: float,
            power_standby: float,
            hw_vessel_loss_daily: float,
        ) -> float:
            """Calculate efficiency for given test condition (tapping profile)"""
            # CALCM-01 - DAHPSE - V2.0_DRAFT13, section 4.2
            temp_factor = 0.6 * 0.9
            energy_input_hw_vessel_loss = hw_vessel_loss_daily / cop_dhw * temp_factor
            energy_input_standby = power_standby * hours_per_day * temp_factor
            energy_input_test = (
                energy_input_measured - energy_input_standby + energy_input_hw_vessel_loss
            )
            energy_demand_test = hw_tapping_prof_daily_total + hw_vessel_loss_daily * temp_factor
            return energy_demand_test / energy_input_test

        # Calculate efficiency for each tapping profile
        # TODO Check that expected tapping profiles have been provided
        efficiencies = {}
        for profile_name, profile_data in test_data.items():
            efficiencies[profile_name] = init_efficiency_tapping_profile(
                cop_dhw=profile_data["cop_dhw"],
                hw_tapping_prof_daily_total=profile_data["hw_tapping_prof_daily_total"],
                energy_input_measured=profile_data["energy_input_measured"],
                power_standby=profile_data["power_standby"],
                hw_vessel_loss_daily=profile_data["hw_vessel_loss_daily"],
            )

        def init_efficiency() -> float:
            """Calculate initial efficiency based on SAP 10.2 section N3.7 b) and c)"""
            if len(efficiencies) == 1 and "M" in efficiencies.keys():
                # If efficiency for tapping profile M only has been provided, use it
                eff = efficiencies["M"]
            elif (
                len(efficiencies) == 2 and "M" in efficiencies.keys() and "L" in efficiencies.keys()
            ):
                # If efficiencies for tapping profiles M and L have been provided, interpolate
                vol_daily_limit_lower = 100.2
                vol_daily_limit_upper = 199.8
                if self.__vol_daily_average < vol_daily_limit_lower or math.isclose(
                    self.__vol_daily_average, vol_daily_limit_lower
                ):
                    eff = efficiencies["M"]
                elif self.__vol_daily_average > vol_daily_limit_upper or math.isclose(
                    self.__vol_daily_average, vol_daily_limit_upper
                ):
                    eff = efficiencies["L"]
                else:
                    eff_M = efficiencies["M"]
                    eff_L = efficiencies["L"]
                    eff = eff_M + (eff_L - eff_M) / (
                        vol_daily_limit_upper - vol_daily_limit_lower
                    ) * (vol_daily_average - vol_daily_limit_lower)
            else:
                raise ValueError("Unrecognised combination of tapping profiles in test data")
            return eff

        self.__initial_efficiency = init_efficiency()

    @property
    def controlmin(self) -> TimeControl:
        return self.__controlmin

    @property
    def controlmax(self) -> TimeControl:
        return self.__controlmax

    @property
    def initial_efficiency(self) -> float:
        return self.__initial_efficiency

    def calc_efficiency(self) -> float:
        """
        Calculate efficiency after applying in use factor if entered tank characteristics
        do not meet criteria of data in database.
        """
        if (
            self.__tank_volume < self.__tank_volume_declared
            or self.__heat_exchanger_surface_area_declared is None
            or self.__heat_exchanger_surface_area < self.__heat_exchanger_surface_area_declared
            or self.__daily_losses > self.__daily_losses_declared
        ):
            # heat pump does not meet criteria then in use factor applied
            in_use_factor_mismatch = self.__in_use_factor_mismatch
        else:
            # no in use factor is applied
            in_use_factor_mismatch = 1.0

        return self.__initial_efficiency * in_use_factor_mismatch

    def setpnt(self) -> tuple[float | None, float | None]:
        """Return water heating setpoint (not necessarily temperature)"""
        if not isinstance(self.controlmin, SetpointTimeControl | CombinationTimeControl):
            raise TypeError(f"controlmin ({type(self.controlmin)}) does not have a set point.")
        if not isinstance(self.controlmax, SetpointTimeControl | CombinationTimeControl):
            raise TypeError(f"controlmax ({type(self.controlmax)}) does not have a set point.")
        return self.controlmin.setpnt(), self.controlmax.setpnt()

    def demand_energy(self, energy_demand: float, temp_flow: float, temp_return: float) -> float:
        """Demand energy (in kWh) from the heat pump"""
        # Account for time control where present. If no control present, assume
        # system is always active (except for basic thermostatic control, which
        # is implicit in demand calculation).
        if self.controlmin is None or self.controlmin.is_on():
            # Energy that heater is able to supply is limited by power rating
            energy_supplied = min(energy_demand, self.__pwr * self.__simulation_time.timestep())
        else:
            energy_supplied = 0.0

        energy_required = energy_supplied / self.calc_efficiency()
        self.__energy_supply_conn.demand_energy(amount_demanded=energy_required)
        return energy_supplied

    def energy_output_max(self, temp_flow: float, temp_return: float) -> float:
        """Calculate the maximum energy output (in kWh) from the heater"""

        # Account for time control where present. If no control present, assume
        # system is always active (except for basic thermostatic control, which
        # is implicit in demand calculation).
        if self.controlmin is None or self.controlmin.is_on():
            # Energy that heater is able to supply is limited by power rating
            energy_max = self.__pwr * self.__simulation_time.timestep()
        else:
            energy_max = 0.0

        return energy_max
