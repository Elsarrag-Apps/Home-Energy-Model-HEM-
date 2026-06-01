#!/usr/bin/env python3

"""
This module contains the hot water demand calculations.
"""

import math
from enum import StrEnum
from functools import partial
from typing import Any, Protocol

import hem_core.units as units
import hem_core.water_heat_demand.misc as misc
from hem_core.energy_supply.energy_supply import EnergySupply
from hem_core.heating_systems.point_of_use import PointOfUse
from hem_core.heating_systems.wwhrs import WWHRS_Instantaneous
from hem_core.input_output.enums import PipeworkContents, ShowerType, WaterPipeworkLocation
from hem_core.pipework import PipeworkSimple
from hem_core.water_heat_demand.bath import Bath
from hem_core.water_heat_demand.cold_water_source import ColdWaterSource
from hem_core.water_heat_demand.misc import FRAC_DHW_ENERGY_INTERNAL_GAINS, WaterEventResult
from hem_core.water_heat_demand.other_hot_water_uses import OtherHotWater
from hem_core.water_heat_demand.shower import InstantElecShower, MixerShower
from hem_core.water_heat_demand.types import Event

ELECTRIC_SHOWERS_HWS_NAME = "_electric_showers"


class HotWaterSource(Protocol):
    def get_temp_hot_water(
        self, volume_req: float, volume_req_already: float = 0.0
    ) -> list[tuple[float, float]]: ...
    def get_losses_from_primary_pipework_and_storage(self) -> tuple[float, float]: ...
    def internal_gains(self) -> float: ...
    def get_cold_water_source(self) -> ColdWaterSource: ...
    def demand_hot_water(self, usage_events: list[WaterEventResult]) -> float: ...


class PreHeatWaterSource(Protocol):
    def demand_hot_water(self, usage_events: list[WaterEventResult] | None) -> float: ...


class OutletType(StrEnum):
    SHOWER = "Shower"
    BATH = "Bath"
    OTHER = "Other"


class DHWDemand:
    # TODO    Enhance analysis for overlapping events
    # Part of draft code for future overlapping analysis of events
    # For pipework losses count only none overlapping events
    # Time of finalisation of the previous hot water event
    # __time_end_previous_event = 0.0

    def __init__(
        self,
        showers_dict: dict[str, dict[str, Any]],
        baths_dict: dict[str, dict[str, Any]],
        other_hw_users_dict: dict[str, dict[str, Any]],
        hw_pipework_inputs: list[dict[str, Any]] | dict[str, list[dict[str, Any]]],
        cold_water_sources: dict[str, ColdWaterSource],
        wwhrs: dict[str, WWHRS_Instantaneous],
        energy_supplies: dict[str, EnergySupply],
        event_schedules: dict[int, Any],
        hot_water_sources: dict[str, HotWaterSource],
        pre_heated_water_sources: dict[str, PreHeatWaterSource] | None = None,
    ):
        """Construct a DHWDemand object"""
        self.__cold_water_sources = cold_water_sources
        self.__wwhrs = wwhrs
        self.__energy_supplies = energy_supplies
        self.__event_schedules = event_schedules
        self.__showers = {}
        self.__no_of_showers = 0
        self.__baths = {}
        self.__other_hw_users = {}
        self.__total_no_of_hot_water_tapping_points = None
        self.__pre_heated_water_sources = (
            {} if pre_heated_water_sources is None else pre_heated_water_sources
        )
        self.__hot_water_sources = hot_water_sources
        self.__hw_distribution_pipework = {
            hws_name: [] for hws_name in self.__hot_water_sources.keys()
        }

        for name, data in showers_dict.items():
            try:
                self.__showers[name] = self._create_shower(name=name, data=data)
                if data["type"] != ShowerType.INSTANT_ELECTRIC_SHOWER:
                    self.__no_of_showers += 1
            except Exception as err:
                raise ValueError(f"Failed to create shower '{name}': {err}") from err

        for name, data in baths_dict.items():
            try:
                self.__baths[name] = self._create_bath(name=name, data=data)
            except Exception as err:
                raise ValueError(f"Failed to create bath '{name}': {err}") from err

        for name, data in other_hw_users_dict.items():
            try:
                self.__other_hw_users[name] = self._create_other_water_use(name=name, data=data)
            except Exception as err:
                raise ValueError(f"Failed to create other water use '{name}': {err}") from err

        if isinstance(hw_pipework_inputs, list):
            if len(self.__hot_water_sources) == 1:
                hw_pipework_inputs = {list(self.__hot_water_sources.keys())[0]: hw_pipework_inputs}
            else:
                raise ValueError(
                    "If more than one HotWaterSource is defined, then distribution pipework must be defined for each one"
                )

        pw_without_hws = [
            name
            for name in hw_pipework_inputs.keys()
            if name not in self.__hot_water_sources.keys()
        ]
        if pw_without_hws:
            raise ValueError(
                f"Distribution pipework defined for non-existent HotWaterSource(s): {pw_without_hws}"
            )
        hws_without_pw = [
            name
            for name in self.__hot_water_sources.keys()
            if name not in hw_pipework_inputs.keys()
        ]
        for hws_name in hws_without_pw:
            if isinstance(self.__hot_water_sources[hws_name], PointOfUse):
                hw_pipework_inputs[hws_name] = []
            else:
                raise ValueError(
                    f"Distribution pipework not specified for HotWaterSource: {hws_name}"
                )

        for hws_name, hws in self.__hot_water_sources.items():
            if not isinstance(hws, PointOfUse):
                for data in hw_pipework_inputs[hws_name]:
                    try:
                        pipework = self._create_water_distribution_pipework(data=data)
                        self.__hw_distribution_pipework[hws_name].append(pipework)
                    except Exception as err:
                        raise ValueError(
                            f"Failed to create water distribution pipework for HotWaterSource {hws_name}: {err}"
                        ) from err

        # Set up unmet demand connection for each hot water source
        self.__energy_supply_conn_unmet_demand = {}
        for name in self.__hot_water_sources.keys():
            try:
                self.__energy_supply_conn_unmet_demand[name] = self.__energy_supplies[
                    "_unmet_demand"
                ].connection(end_user_name=name)
            except Exception as err:
                raise ValueError(
                    f"Failed to create unmet demand connection for water heating {name}: {err}"
                ) from err

        self.__source_supplying_outlet = self.__init_outlet_to_source_mapping(
            showers_dict=showers_dict,
            baths_dict=baths_dict,
            other_hw_users_dict=other_hw_users_dict,
        )

    def __init_outlet_to_source_mapping(
        self,
        showers_dict: dict[str, dict[str, Any]],
        baths_dict: dict[str, dict[str, Any]],
        other_hw_users_dict: dict[str, dict[str, Any]],
    ) -> dict[tuple[OutletType, str], str]:
        mapping = {}
        for outlet_type, outlets_dict in [
            (OutletType.SHOWER, showers_dict),
            (OutletType.BATH, baths_dict),
            (OutletType.OTHER, other_hw_users_dict),
        ]:
            for outlet_name, outlet_data in outlets_dict.items():
                if (
                    outlet_type == OutletType.SHOWER
                    and outlet_data["type"] == ShowerType.INSTANT_ELECTRIC_SHOWER
                ):
                    mapping[(outlet_type, outlet_name)] = ELECTRIC_SHOWERS_HWS_NAME
                    continue

                if "HotWaterSource" in outlet_data:
                    if outlet_data["HotWaterSource"] not in self.__hot_water_sources.keys():
                        raise ValueError(
                            f"Invalid HotWaterSource specified for tapping point {outlet_name} of type {outlet_type}"
                        )
                    mapping[(outlet_type, outlet_name)] = outlet_data["HotWaterSource"]
                elif len(self.__hot_water_sources) == 1:
                    mapping[(outlet_type, outlet_name)] = list(self.__hot_water_sources.keys())[0]
                else:
                    raise ValueError(
                        f"HotWaterSource not specified for tapping point {outlet_name} of type {outlet_type}"
                    )
        return mapping

    def __temp_hot_water(
        self,
        hot_water_source: HotWaterSource,
        volume_required_already: float,
        volume_required: float,
    ) -> float:
        list_temperature_for_required_volume = hot_water_source.get_temp_hot_water(
            volume_req=volume_required, volume_req_already=volume_required_already
        )

        # Return average hot water temperature for the required volume
        return math.fsum(t * v for t, v in list_temperature_for_required_volume) / math.fsum(
            v for _, v in list_temperature_for_required_volume
        )

    def _get_tapping_point_for_event(
        self, event: Event
    ) -> tuple[InstantElecShower | MixerShower | Bath | OtherHotWater, OutletType, str]:
        event_type = event["type"]
        event_name = event["name"]

        if event_type == "Shower":
            lookup = self.__showers
            tapping_point_type = OutletType.SHOWER
        elif event_type == "Bath":
            lookup = self.__baths
            tapping_point_type = OutletType.BATH
        elif event_type == "Other":
            lookup = self.__other_hw_users
            tapping_point_type = OutletType.OTHER
        else:
            raise ValueError(f"Event type not recognised: {event_type}")

        if event_name in lookup.keys():
            return lookup[event_name], tapping_point_type, event_name
        else:
            raise ValueError(f"Tapping point not found for event: {event_name}")

    def hot_water_demand(
        self, t_idx: int
    ) -> tuple[
        dict[str, float],
        dict[str, float],
        dict[str, int],
        dict[str, float],
        dict[str, list[WaterEventResult]],
    ]:
        """Calculate the hot water demand for the current timestep

        Arguments:
        t_idx -- timestep index/count
        """
        hw_demand_volume = {hws_name: 0.0 for hws_name in self.__hot_water_sources.keys()}
        hw_energy_demand = {hws_name: 0.0 for hws_name in self.__hot_water_sources.keys()}
        hw_duration = {hws_name: 0.0 for hws_name in self.__hot_water_sources.keys()}
        all_events = {hws_name: 0 for hws_name in self.__hot_water_sources.keys()}

        hw_demand_volume[ELECTRIC_SHOWERS_HWS_NAME] = 0.0
        hw_energy_demand[ELECTRIC_SHOWERS_HWS_NAME] = 0.0
        hw_duration[ELECTRIC_SHOWERS_HWS_NAME] = 0.0
        all_events[ELECTRIC_SHOWERS_HWS_NAME] = 0

        # none_overlapping_events = 0.0

        volume_hot_water_left_in_pipework = {}
        for hws_name in self.__hot_water_sources.keys():
            volume_hot_water_left_in_pipework[hws_name] = 0.0
            for pipework in self.__hw_distribution_pipework[hws_name]:
                volume_hot_water_left_in_pipework[hws_name] += pipework.volume

        """
        Events have been organised now so that they are structured by timple step t_idx and 
        sorted for each time step from start to end. 
        """
        # TODO No overlapping is currently considered in terms of interaction with hot water
        #      source (tank). The first event that starts is Served before the second event
        #      is considered even if this starts before the previous event has finished.

        usage_events = self.__event_schedules[t_idx]
        usage_events_with_flushes = {hws_name: [] for hws_name in self.__hot_water_sources.keys()}
        usage_events_with_flushes[ELECTRIC_SHOWERS_HWS_NAME] = []

        if usage_events is not None:
            for event in usage_events:
                energy_supply_conn_unmet_demand = None
                hot_water_source = None
                tapping_point, tapping_point_type, tapping_point_name = (
                    self._get_tapping_point_for_event(event=event)
                )

                if isinstance(tapping_point, InstantElecShower):
                    hot_water_source_name = ELECTRIC_SHOWERS_HWS_NAME
                    hw_demand_i, hw_demand_target_i, event_duration_i = (
                        tapping_point.hot_water_demand(event=event)
                    )
                else:
                    hot_water_source_name = self.__source_supplying_outlet[
                        (tapping_point_type, tapping_point_name)
                    ]
                    hot_water_source = self.__hot_water_sources[hot_water_source_name]
                    energy_supply_conn_unmet_demand = self.__energy_supply_conn_unmet_demand[
                        hot_water_source_name
                    ]
                    func_temperature_hot_water = partial(
                        self.__temp_hot_water,
                        hot_water_source,
                        hw_demand_volume[hot_water_source_name],
                    )
                    hw_demand_i, hw_demand_target_i, event_duration_i = (
                        tapping_point.hot_water_demand(
                            event=event, func_temp_hot_water=func_temperature_hot_water
                        )
                    )

                cold_water_temperature = tapping_point.get_cold_water_source()

                temperature_event = event["temperature"]

                if hw_demand_i is not None:
                    hw_demand_volume[hot_water_source_name] += hw_demand_i
                    list_temperature_volume = cold_water_temperature.get_temp_cold_water(
                        volume_needed=hw_demand_target_i - hw_demand_i
                    )
                    cold_water_temperature = math.fsum(
                        t * v for t, v in list_temperature_volume
                    ) / math.fsum(v for _, v in list_temperature_volume)
                else:
                    list_temperature_volume = cold_water_temperature.get_temp_cold_water(
                        volume_needed=hw_demand_target_i
                    )
                    cold_water_temperature = math.fsum(
                        t * v for t, v in list_temperature_volume
                    ) / math.fsum(v for _, v in list_temperature_volume)

                hw_energy_demand_i = misc.water_demand_to_kWh(
                    litres_demand=hw_demand_target_i,
                    demand_temperature=temperature_event,
                    cold_temperature=cold_water_temperature,
                )
                hw_energy_demand[hot_water_source_name] += hw_energy_demand_i
                hw_duration[hot_water_source_name] += event["duration"]
                all_events[hot_water_source_name] += 1
                if hw_demand_i is None and energy_supply_conn_unmet_demand is not None:
                    energy_supply_conn_unmet_demand.demand_energy(
                        amount_demanded=hw_energy_demand_i
                    )

                # If event demand cannot be met, skip to the next one
                if hw_demand_i is None:
                    continue

                event_result = WaterEventResult(
                    type=event["type"],
                    temperature_warm=temperature_event,
                    volume_warm=hw_demand_target_i,
                    volume_hot=hw_demand_i,
                    event_duration=event_duration_i,
                )

                usage_events_with_flushes[hot_water_source_name].append(event_result)
                # Add pipework flushes after every event (except for IES)
                if (
                    not math.isclose(event_result.volume_hot, 0.0, abs_tol=1e-10)
                    and volume_hot_water_left_in_pipework[hot_water_source_name] > 0.0
                    and hot_water_source is not None
                ):
                    temperature_pipe_flush = self.__temp_hot_water(
                        hot_water_source=hot_water_source,
                        volume_required_already=hw_demand_volume[hot_water_source_name],
                        volume_required=volume_hot_water_left_in_pipework[hot_water_source_name],
                    )
                    usage_events_with_flushes[hot_water_source_name].append(
                        WaterEventResult(
                            type="PipeFlush",
                            temperature_warm=temperature_pipe_flush,
                            volume_warm=volume_hot_water_left_in_pipework[hot_water_source_name],
                            volume_hot=volume_hot_water_left_in_pipework[hot_water_source_name],
                            event_duration=0.0,
                        )
                    )
                    hw_demand_volume[hot_water_source_name] += volume_hot_water_left_in_pipework[
                        hot_water_source_name
                    ]

                # TODO    Enhance analysis for overlapping events
                # Part of draft code for future overlapping analysis of events
                # For pipework losses count only none overlapping events
                # if not is_IES:
                #    time_start_current_event = event['start']
                #    if time_start_current_event > self.__time_end_previous_event:
                #        none_overlapping_events += 1
                #    # 0.0 can be modified for additional minutes when pipework could be considered still warm/hot
                #    self.__time_end_previous_event = deepcopy(time_start_current_event + (event['duration'] + 0.0) / 60.0)

        # TODO     Refine pipework losses by considering overlapping of events
        #          and shared pipework between serving tap points
        #          none_overlapping_events calculated above is a lower bound(ish)
        #          approximation for this

        # Return:
        # - litres hot water per timestep (demand on hw system)
        # - minutes demand per timestep,
        # - number of events in timestep
        # - hot water energy demand (kWh)
        # - usage_events updated to reflect pipework volumes and bath durations
        return (
            hw_demand_volume,
            hw_duration,
            all_events,
            hw_energy_demand,
            usage_events_with_flushes,
        )

    def calc_water_heating(
        self,
        t_idx: int,
        timestep: int | float,
        internal_air_temperature: float,
        external_air_temperature: float,
    ) -> tuple[
        dict[str, float],
        dict[str, float],
        dict[str, int],
        dict[str, float],
        dict[str, float],
        dict[str, float],
        dict[str, float],
        dict[str, float],
        dict[str, float],
        dict[str, float],
    ]:
        (
            hw_demand_vol,
            hw_duration,
            no_events,
            hw_energy_demand_at_tapping_points,
            usage_events,
        ) = self.hot_water_demand(t_idx=t_idx)

        # Running heat sources of pre-heated tanks and updating thermal losses, etc.
        for storage_tank in self.__pre_heated_water_sources.values():
            storage_tank.demand_hot_water(usage_events=None)

        hw_energy_demand_at_hot_water_source = {}
        hw_energy_output = {}
        pw_losses_internal = {}
        pw_losses_external = {}
        pw_losses_total = {}
        gains_internal_dhw_use = {}
        gains_internal_dhw = {}
        primary_pw_losses = {}
        storage_losses = {}

        for hws_name in list(self.__hot_water_sources.keys()) + [ELECTRIC_SHOWERS_HWS_NAME]:
            (
                pw_losses_internal[hws_name],
                pw_losses_external[hws_name],
                gains_internal_dhw_use[hws_name],
            ) = self.pipework_losses_and_internal_gains_from_hot_water_events(
                hot_water_source_name=hws_name,
                usage_events=usage_events[hws_name],
                internal_air_temperature=internal_air_temperature,
                external_air_temperature=external_air_temperature,
            )
            pw_losses_total[hws_name] = pw_losses_internal[hws_name] + pw_losses_external[hws_name]
            gains_internal_dhw[hws_name] = (
                (pw_losses_internal[hws_name] + gains_internal_dhw_use[hws_name])
                * units.W_per_kW
                / timestep
            )

        for hws_name, hws in self.__hot_water_sources.items():
            # Filtering out IES events that don't get added a 'hot_volume' when processing
            # the dhw_demand calculation
            # Note: Cast to list because we may need to loop over this more
            #       than once, which cannot be done with iterator object
            filtered_events = list(
                filter(
                    lambda e: e.volume_hot is not None
                    and not math.isclose(e.volume_hot, 0.0, abs_tol=1e-10),
                    usage_events[hws_name],
                )
            )

            hw_energy_output[hws_name] = hws.demand_hot_water(usage_events=filtered_events)

            # Convert from litres to kWh
            # Find underlying cold water source, ignoring pre-heat tanks
            cold_water_source: Any = hws.get_cold_water_source()
            cold_water_source_found = False
            while not cold_water_source_found:
                if hasattr(cold_water_source, "get_cold_water_source") and callable(
                    cold_water_source.get_cold_water_source
                ):
                    cold_water_source = cold_water_source.get_cold_water_source()
                else:
                    cold_water_source_found = True
            hw_energy_demand_at_hot_water_source[hws_name] = 0.0
            for event in filtered_events:
                list_temperature_volume = cold_water_source.get_temp_cold_water(
                    volume_needed=event.volume_hot
                )
                cold_water_temperature = math.fsum(
                    t * v for t, v in list_temperature_volume
                ) / math.fsum(v for _, v in list_temperature_volume)
                hw_energy_demand_at_hot_water_source[hws_name] += misc.water_demand_to_kWh(
                    litres_demand=event.volume_warm,
                    demand_temperature=event.temperature_warm,
                    cold_temperature=cold_water_temperature,
                )

            if hasattr(hws, "internal_gains") and callable(hws.internal_gains):
                gains_internal_dhw[hws_name] += hws.internal_gains()

            if hasattr(hws, "get_losses_from_primary_pipework_and_storage") and callable(
                hws.get_losses_from_primary_pipework_and_storage
            ):
                primary_pw_losses[hws_name], storage_losses[hws_name] = (
                    hws.get_losses_from_primary_pipework_and_storage()
                )
            else:
                primary_pw_losses[hws_name] = 0.0
                storage_losses[hws_name] = 0.0

        return (
            hw_demand_vol,
            hw_duration,
            no_events,
            hw_energy_demand_at_tapping_points,
            hw_energy_demand_at_hot_water_source,
            hw_energy_output,
            pw_losses_total,
            primary_pw_losses,
            storage_losses,
            gains_internal_dhw,
        )

    def calc_pipework_losses(
        self,
        hot_water_source_name: str,
        no_of_hot_water_events: int,
        demand_water_temperature: float,
        internal_air_temperature: float,
        external_air_temperature: float,
    ) -> tuple[float, float]:
        if not self.__hw_distribution_pipework[hot_water_source_name]:
            # Return heat loss in kWh for the timestep
            return 0.0, 0.0

        cool_down_loss_internal = 0
        cool_down_loss_external = 0

        for pipework in self.__hw_distribution_pipework[hot_water_source_name]:
            if pipework.location == WaterPipeworkLocation.INTERNAL:
                cool_down_loss_internal += pipework.calculate_cool_down_loss(
                    inside_temp=demand_water_temperature, outside_temp=internal_air_temperature
                )
            elif pipework.location == WaterPipeworkLocation.EXTERNAL:
                cool_down_loss_external += pipework.calculate_cool_down_loss(
                    inside_temp=demand_water_temperature, outside_temp=external_air_temperature
                )
            else:
                # fallback else block with a failed exception
                raise ValueError(f"Unexpected location value: {pipework.location()}")

        pipework_heat_loss_internal = no_of_hot_water_events * cool_down_loss_internal

        pipework_heat_loss_external = no_of_hot_water_events * cool_down_loss_external

        # Return heat loss in kWh for the timestep
        return pipework_heat_loss_internal, pipework_heat_loss_external

    def _create_shower(self, name: str, data: dict[str, Any]) -> MixerShower | InstantElecShower:
        """Create a shower object from a dictionary of data."""
        cold_water_source_name = data["ColdWaterSource"]
        if cold_water_source_name not in self.__cold_water_sources:
            raise ValueError(
                f"Invalid cold water source name for shower {name}: {cold_water_source_name}"
            )

        cold_water_source = self.__cold_water_sources[cold_water_source_name]
        shower_type = data["type"]

        if shower_type == ShowerType.MIXER_SHOWER:
            return self._create_mixer_shower(
                name=name, data=data, cold_water_source=cold_water_source
            )
        elif shower_type == ShowerType.INSTANT_ELECTRIC_SHOWER:
            return self._create_instant_elec_shower(
                name=name, data=data, cold_water_source=cold_water_source
            )
        else:
            raise ValueError(f"Shower '{name}': Invalid shower type '{shower_type}'")

    def _create_mixer_shower(
        self, name: str, data: dict[str, Any], cold_water_source: ColdWaterSource
    ) -> MixerShower:
        """Create a MixerShower object."""
        wwhrs_instance = None
        if "WWHRS" in data:
            wwhrs_name = data["WWHRS"]
            if wwhrs_name not in self.__wwhrs:
                raise ValueError(f"Shower '{name}': WWHRS '{wwhrs_name}' not found")
            wwhrs_instance = self.__wwhrs[wwhrs_name]
        # Get WWHRS configuration if specified, otherwise default to 'A'
        wwhrs_configuration = data.get("WWHRS_configuration", "A")

        return MixerShower(
            flowrate=data["flowrate"],
            cold_water_source=cold_water_source,
            wwhrs=wwhrs_instance,
            wwhrs_configuration=wwhrs_configuration,
        )

    def _create_instant_elec_shower(
        self, name: str, data: dict[str, Any], cold_water_source: ColdWaterSource
    ) -> InstantElecShower:
        """Create an InstantElecShower object."""
        energy_supply_name = data["EnergySupply"]
        if energy_supply_name not in self.__energy_supplies:
            raise ValueError(f"Shower '{name}': Energy supply '{energy_supply_name}' not found")
        energy_supply = self.__energy_supplies[energy_supply_name]
        energy_supply_conn = energy_supply.connection(end_user_name=name)

        return InstantElecShower(
            rated_power=data["rated_power"],
            cold_water_source=cold_water_source,
            elec_supply_conn=energy_supply_conn,
        )

    def _create_bath(self, name: str, data: dict[str, Any]) -> Bath:
        """Create a bath object from configuration data."""
        cold_water_source_name = data["ColdWaterSource"]
        if cold_water_source_name not in self.__cold_water_sources:
            raise ValueError(
                f"Bath '{name}': Cold water source '{cold_water_source_name}' not found"
            )

        cold_water_source = self.__cold_water_sources[cold_water_source_name]
        return Bath(
            size=data["size"], cold_water_source=cold_water_source, flowrate=data["flowrate"]
        )

    def _create_other_water_use(self, name: str, data: dict[str, Any]) -> OtherHotWater:
        """Create an OtherHotWater object from configuration data."""
        cold_water_source_name = data["ColdWaterSource"]
        if cold_water_source_name not in self.__cold_water_sources:
            raise ValueError(
                f"Other water use '{name}': Cold water source '{cold_water_source_name}' not found"
            )

        cold_water_source = self.__cold_water_sources[cold_water_source_name]
        return OtherHotWater(flowrate=data["flowrate"], cold_water_source=cold_water_source)

    def _create_water_distribution_pipework(self, data: dict[str, Any]) -> PipeworkSimple:
        """Create a Pipework_Simple object for water distribution."""
        location = WaterPipeworkLocation(data["location"])

        # Validate total_no_of_hot_water_tapping_points is not zero
        total_points = self.total_no_of_hot_water_tapping_points
        if total_points <= 0:
            raise ValueError("Cannot create pipework: no hot water tapping points defined")

        # Calculate average length of pipework between HW system and tapping point
        length_average = data["length"] / total_points

        return PipeworkSimple(
            location=location,
            internal_diameter=data["internal_diameter_mm"] / units.mm_per_m,
            length=length_average,
            contents=PipeworkContents.WATER,
        )

    @property
    def total_no_of_hot_water_tapping_points(self) -> int:
        """Calculate the total number of hot water tapping points.

        This includes non-electric showers, baths, and other water uses.
        The result is cached after first computation.
        """
        if self.__total_no_of_hot_water_tapping_points is None:
            self.__total_no_of_hot_water_tapping_points = (
                self.__no_of_showers + len(self.__baths) + len(self.__other_hw_users)
            )

        return self.__total_no_of_hot_water_tapping_points

    def pipework_losses_and_internal_gains_from_hot_water_events(
        self,
        hot_water_source_name: str,
        usage_events: list[WaterEventResult],
        internal_air_temperature: float,
        external_air_temperature: float,
    ) -> tuple[float, float, float]:
        pw_losses_internal = 0.0
        pw_losses_external = 0.0
        gains_internal_dhw_use = 0.0
        for event in usage_events:
            if event.type == "PipeFlush":
                pw_losses_internal_i, pw_losses_external_i = self.calc_pipework_losses(
                    hot_water_source_name=hot_water_source_name,
                    no_of_hot_water_events=1,  # no_of_hw_events,
                    demand_water_temperature=event.temperature_warm,
                    internal_air_temperature=internal_air_temperature,
                    external_air_temperature=external_air_temperature,
                )
                pw_losses_internal += pw_losses_internal_i
                pw_losses_external += pw_losses_external_i
            else:
                gains_internal_dhw_use += FRAC_DHW_ENERGY_INTERNAL_GAINS * misc.water_demand_to_kWh(
                    litres_demand=event.volume_warm,
                    demand_temperature=event.temperature_warm,
                    cold_temperature=internal_air_temperature,
                )
        return pw_losses_internal, pw_losses_external, gains_internal_dhw_use
