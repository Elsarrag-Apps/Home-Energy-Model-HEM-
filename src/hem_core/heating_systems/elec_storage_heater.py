#!/usr/bin/env python3

"""
This module provides the class for Electric Storage Heaters.
"""

# Third-party imports

# Local imports
from hem_core.controls.time_control import ChargeControl, SetpointTimeControl
from hem_core.energy_supply.energy_supply import EnergySupplyConnection
from hem_core.heating_systems import SpaceHeatSystem
from hem_core.heating_systems.heat_battery_drycore import HeatStorageDryCore, OutputMode
from hem_core.input_output.enums import (
    AirFlowType,
    ControlLogicType,
)
from hem_core.simulation_time import SimulationTime
from hem_core.space_heat_demand.zone import Zone


class ElecStorageHeater(HeatStorageDryCore, SpaceHeatSystem):
    """Class to represent electric storage heaters"""

    def __init__(
        self,
        pwr_in: float,
        rated_power_instant: float,
        storage_capacity: float,
        air_flow_type: AirFlowType,
        frac_convective: float,
        fan_pwr: float,
        n_units: int,
        zone: Zone,
        energy_supply_conn: EnergySupplyConnection,
        simulation_time: SimulationTime,
        control: SetpointTimeControl,
        charge_control: ChargeControl,
        dry_core_min_output: list[list[float]],
        dry_core_max_output: list[list[float]],
        state_of_charge_init: float,
        output_detailed_results=False,
    ):
        """Construct an ElecStorageHeater object

        Arguments:
        pwr_in               -- in kW (Charging)
        rated_power_instant  -- in kW (Instant backup)
        storage_capacity     -- in kWh
        air_flow_type        -- str enum specifying type of Electric Storage Heater:
                                -- AirFlowType.FAN_ASSISTED
                                -- AirFlowType.DAMPER_ONLY
        frac_convective      -- convective fraction for heating (TODO: Check if necessary)
        fan_pwr              -- Fan power [W]
        n_units              -- number of units install in zone
        zone                 -- zone where the unit(s) is/are installed
        energy_supply_conn   -- reference to EnergySupplyConnection object
        simulation_time      -- reference to SimulationTime object
        control              -- reference to a control object which must implement is_on() and setpnt() funcs
        charge_control       -- reference to a ChargeControl object which must implement different logic types
                                for charging the Electric Storage Heaters.
        dry_core_min_output       -- Data from test showing the output from the storage heater when not actively
                                outputting heat, i.e. case losses only (with units kW)
        dry_core_max_output       -- Data from test showing the output from the storage heater when it is actively
                                outputting heat, e.g. damper open / fan running (with units kW)
        output_detailed_results -- flag to create detailed emitter output results
        """
        # Initialize base class
        super().__init__(
            pwr_in=pwr_in,
            storage_capacity=storage_capacity,
            n_units=n_units,
            simulation_time=simulation_time,
            charge_control=charge_control,
            dry_core_min_output=dry_core_min_output,
            dry_core_max_output=dry_core_max_output,
            state_of_charge_init=state_of_charge_init,
        )

        valid_logic_types = {
            ControlLogicType.MANUAL,
            ControlLogicType.AUTOMATIC,
            ControlLogicType.CELECT,
            ControlLogicType.HHRSH,
        }

        if charge_control.logic_type() not in valid_logic_types:
            raise ValueError(
                f"Control logic type '{charge_control.logic_type()}' is not valid for ElecStorageHeater. "
                f"Valid types are: {', '.join(t.value for t in valid_logic_types)}"
            )

        self.__pwr_instant: float = rated_power_instant
        self.__air_flow_type: AirFlowType = air_flow_type
        self.__frac_convective: float = frac_convective
        self.__zone: Zone = zone
        self.__energy_supply_conn: EnergySupplyConnection = energy_supply_conn
        self.__control: SetpointTimeControl = control
        self.__fan_pwr = fan_pwr

        self.__output_detailed_results = output_detailed_results
        self.temp_air: float = self.__zone.temp_internal_air()  # °C Room temperature
        # Power for driving fan
        # TODO: Modify fan energy calculation to SFP
        # self.__sfp: float = 0.0

        # Initialising other variables
        self.__energy_in: float = 0.0

        # Zone initial set point
        self.__zone_setpnt_init = self.__zone.setpnt_init()

        # Create instance variable for emitter detailed output
        if self.__output_detailed_results:
            self.__esh_detailed_results = {}
        else:
            self.__esh_detailed_results = None

    def temp_setpnt(self) -> float | None:
        return self.__control.setpnt()

    def in_required_period(self) -> bool:
        return self.__control.in_required_period()

    def frac_convective(self) -> float:
        return self.__frac_convective

    def _get_temp_for_charge_control(self) -> float | None:
        """Get temperature for charge control calculations."""
        return self.__zone.temp_internal_air()

    def _get_zone_setpoint(self) -> float:
        """Get zone setpoint for HHRSH calculations."""
        return self.__zone_setpnt_init

    def demand_energy(self, energy_demand: float) -> float:
        """
        Determines the amount of energy to release based on energy demand, while also handling the
        energy charging and logging fan energy.

        :param energy_demand: Energy demand in kWh.
        :return: Total net energy delivered (including instant heating and fan energy).
        """
        timestep = self._get_simulation_time().timestep()
        energy_demand = energy_demand / self._get_n_units()
        self.__energy_instant: float = 0.0

        # Initialize time_used_max and energy_charged_max to default values
        time_used_max: float = 0.0
        energy_charged_max: float = 0.0

        # Calculate minimum energy that can be delivered
        q_released_min, __, self.__energy_charged, final_soc = self._energy_output(
            mode=OutputMode.MIN
        )
        q_released_max = None

        if q_released_min > energy_demand:
            # Deliver at least the minimum energy
            self.__energy_delivered = q_released_min
            self._set_demand_met(q_released_min)
            self._set_demand_unmet(0)
        else:
            # Calculate maximum energy that can be delivered
            q_released_max, time_used_max, energy_charged_max, final_soc = self._energy_output_max()

            if q_released_max < energy_demand:
                # Deliver as much as possible up to the maximum energy
                self.__energy_delivered = q_released_max
                self._set_demand_met(q_released_max)
                self._set_demand_unmet(energy_demand - q_released_max)
                self.__energy_charged = energy_charged_max

                # For now, we assume demand not met from storage is topped-up by
                # the direct top-up heater (if applicable). If still some unmet,
                # this is reported as unmet demand.
                if self.__pwr_instant:
                    self.__energy_instant = min(
                        self._get_demand_unmet(), self.__pwr_instant * timestep
                    )  # kWh
                    time_instant = self.__energy_instant / self.__pwr_instant
                    time_used_max += time_instant
                    time_used_max = min(time_used_max, timestep)

            else:
                # IMPROVED ACCURACY: Use exact energy target instead of linear proration
                # Deliver exactly the demanded energy using the differential equation solver
                self.__energy_delivered, time_used_max, self.__energy_charged, final_soc = (
                    self._energy_output(
                        mode=OutputMode.MAX,
                        time_remaining=None,  # Will use default timestep
                        target_energy=energy_demand,
                    )
                )

                # The solver should have delivered exactly what we requested
                # (within numerical tolerances)
                self.__energy_delivered = min(self.__energy_delivered, energy_demand)
                self._set_demand_met(self.__energy_delivered)
                self._set_demand_unmet(max(0, energy_demand - self.__energy_delivered))

        # Ensure energy_delivered does not exceed q_released_max
        self.__energy_delivered = min(
            self.__energy_delivered,
            q_released_max if q_released_max is not None else q_released_min,
        )

        # Update state of charge using the final SOC from the differential equation solver
        # The ODE has already integrated the charging and discharging accurately
        self._set_state_of_charge(soc=final_soc)

        # Calculate fan energy
        self.__energy_for_fan: float = 0.0
        power_for_fan: float = 0.0
        if self.__air_flow_type == AirFlowType.FAN_ASSISTED and "q_released_max" in locals():
            power_for_fan = self.__fan_pwr
            self.__energy_for_fan = self._convert_to_kwh(power=power_for_fan, time=time_used_max)

        # Log the energy charged, fan energy, and total energy delivered
        self.__energy_supply_conn.demand_energy(
            amount_demanded=self._get_n_units()
            * (self.__energy_charged + self.__energy_instant + self.__energy_for_fan)
        )

        # If detailed results flag is set populate dict with values
        if self.__output_detailed_results:
            dr_list = [
                self._get_simulation_time().index(),
                self._get_n_units(),
                energy_demand,
                self.__energy_delivered,
                self.__energy_instant,
                self.__energy_charged,
                self.__energy_for_fan,
                self._get_state_of_charge(),
                final_soc,
                time_used_max,
            ]

            if self.__esh_detailed_results is not None:
                self.__esh_detailed_results[self._get_simulation_time().index()] = dr_list

        # Return total net energy delivered (discharged + instant heat + fan energy)
        return self._get_n_units() * (self.__energy_delivered + self.__energy_instant)

    def output_esh_results(self) -> dict[int, list[float | int]] | None:
        """Return the data dictionary containing detailed emitter results"""
        return self.__esh_detailed_results
