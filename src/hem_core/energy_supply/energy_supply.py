#!/usr/bin/env python3

"""
This module contains objects that represent energy supplies such as mains gas,
mains electricity or other fuels (e.g. LPG, wood pellets).
"""

import math
from pathlib import Path

# Standard library inputs
import numpy as np

from hem_core.energy_supply.elec_battery import ElectricBattery

# Local library inputs
from hem_core.energy_supply.tariff_data import TariffData
from hem_core.heating_systems.storage_tank import PVDiverter
from hem_core.input_output.enums import FuelType
from hem_core.simulation_time import SimulationTime


class EnergySupplyConnection:
    """An object to represent the connection of a system that consumes energy to the energy supply

    This object encapsulates the name of the connection, meaning that the
    system consuming the energy does not have to specify these on every call,
    and helping to enforce that each connection to a single supply has a unique
    name.
    """

    def __init__(self, energy_supply: "EnergySupply", end_user_name: str):
        """Construct an EnergySupplyConnection object

        Arguments:
        energy_supply -- reference to the EnergySupply object that the connection is to
        end_user_name -- name of the system (and end use, where applicable)
                         consuming energy from this connection
        """
        self.__energy_supply = energy_supply
        self.__end_user_name = end_user_name

    def energy_out(self, amount_demanded: float):
        """Forwards the amount of energy out (in kWh) to the relevant EnergySupply object"""
        self.__energy_supply._energy_out(
            end_user_name=self.__end_user_name, amount_demanded=amount_demanded
        )

    def demand_energy(self, amount_demanded: float):
        """Forwards the amount of energy demanded (in kWh) to the relevant EnergySupply object"""
        self.__energy_supply._demand_energy(
            end_user_name=self.__end_user_name, amount_demanded=amount_demanded
        )

    def supply_energy(self, amount_produced: float):
        """Forwards the amount of energy produced (in kWh) to the relevant EnergySupply object"""
        self.__energy_supply._supply_energy(
            end_user_name=self.__end_user_name, amount_produced=amount_produced
        )

    def fuel_type(self) -> FuelType:
        return self.__energy_supply.fuel_type()


class EnergySupply:
    """An object to represent an energy supply, and to report energy consumption"""

    # TODO Do we need a subclass for electricity supply specifically, to
    #      account for generators? Or do we just handle it in this object and
    #      have an empty list of generators when not electricity?

    def __init__(
        self,
        fuel_type: FuelType,
        simulation_time: SimulationTime,
        tariff_path: Path | None = None,
        tariff: str | None = None,
        threshold_charges: list[float] | None = None,
        threshold_prices: list[float] | None = None,
        electric_battery: ElectricBattery | None = None,
        priority: list[str] | None = None,
        is_export_capable: bool = True,
    ):
        """Construct an EnergySupply object

        Arguments:
        fuel_type          -- FuelType object
        simulation_time    -- reference to SimulationTime object
        tariff             -- energy tariff
        threshold_charges  -- level of battery charge above which grid prohibited from charging battery (0 - 1)
        threshold_prices   -- grid price below which battery is permitted to charge from grid (p/kWh)
        electric_battery   -- reference to an ElectricBattery object
        is_export_capable  -- denotes that this Energy Supply can export its surplus supply

        Other variables:
        demand_total       -- list to hold total demand on this energy supply at each timestep
        demand_by_end_user -- dictionary of lists to hold demand from each end user on this
                              energy supply at each timestep
        """
        self.__fuel_type = fuel_type
        self.__simulation_time = simulation_time
        self.__tariff = tariff
        self.__threshold_charges = threshold_charges
        self.__threshold_prices = threshold_prices
        self.__elec_battery = electric_battery
        self.__diverter = None
        self.__priority = priority
        self.__is_export_capable = is_export_capable

        self.__demand_total = self.__init_demand_list()
        self.__demand_by_end_user = {}
        self.__energy_out_by_end_user = {}
        self.__beta_factor = (
            self.__init_demand_list()
        )  # this would be multiple columns if multiple beta factors
        self.__supply_surplus = self.__init_demand_list()
        self.__demand_not_met = self.__init_demand_list()
        self.__grid_to_consumption = self.__init_demand_list()
        self.__energy_into_battery_from_generation = self.__init_demand_list()
        self.__energy_battery_to_consumption = self.__init_demand_list()
        self.__energy_into_battery_from_grid = self.__init_demand_list()
        self.__battery_state_of_charge = self.__init_demand_list()
        self.__energy_diverted = self.__init_demand_list()
        self.__energy_generated_consumed = self.__init_demand_list()

        # Create supply connection of Electric Battery to Energy Supply to account for energy imported
        if self.__elec_battery is not None:
            if self.__elec_battery.is_grid_charging_possible():
                # Import electricity tariff data for grid import options
                if tariff_path is not None:
                    self.__tariff_data = TariffData(relative_path=tariff_path)
                else:
                    raise ValueError(
                        "Tariff data file not provided in command line arguments using --tariff-file option"
                    )

    def __init_demand_list(self) -> list[float]:
        """Initialise zeroed list of demand figures (one list entry for each timestep)"""
        # TODO Consider moving this function to SimulationTime object if it
        #      turns out to be more generally useful.
        return [0] * self.__simulation_time.total_steps()

    def connection(self, end_user_name: str) -> EnergySupplyConnection:
        """Return an EnergySupplyConnection object and initialise list for the end user demand"""
        # Check that end_user_name is not already registered/connected
        if end_user_name in self.__demand_by_end_user.keys():
            raise ValueError("Error: End user name already used: " + end_user_name)
            # TODO Exit just the current case instead of whole program entirely?

        self.__demand_by_end_user[end_user_name] = self.__init_demand_list()
        self.__energy_out_by_end_user[end_user_name] = self.__init_demand_list()
        return EnergySupplyConnection(energy_supply=self, end_user_name=end_user_name)

    def _energy_out(self, end_user_name: str, amount_demanded: float):
        # Check that end_user_name is already connected/registered
        if end_user_name not in self.__demand_by_end_user.keys():
            raise RuntimeError(
                "Error: End user name ("
                + end_user_name
                + ") not already registered by calling connection function."
            )
            # TODO Exit just the current case instead of whole program entirely?

        t_idx = self.__simulation_time.index()
        self.__energy_out_by_end_user[end_user_name][t_idx] = (
            self.__energy_out_by_end_user[end_user_name][t_idx] + amount_demanded
        )

    def connect_diverter(self, diverter: PVDiverter):
        if self.__diverter is not None:
            raise RuntimeError("Diverter already connected.")
        self.__diverter = diverter

    def _demand_energy(self, end_user_name: str, amount_demanded: float):
        """Record energy demand (in kWh) for the end user specified.

        Note: Call via an EnergySupplyConnection object, not directly.
        """
        # Check that end_user_name is already connected/registered
        if end_user_name not in self.__demand_by_end_user.keys():
            raise RuntimeError(
                "Error: End user name ("
                + end_user_name
                + ") not already registered by calling connection function."
            )
            # TODO Exit just the current case instead of whole program entirely?

        t_idx = self.__simulation_time.index()
        self.__demand_total[t_idx] = self.__demand_total[t_idx] + amount_demanded
        self.__demand_by_end_user[end_user_name][t_idx] = (
            self.__demand_by_end_user[end_user_name][t_idx] + amount_demanded
        )

    def _supply_energy(self, end_user_name: str, amount_produced: float):
        """Record energy produced (in kWh) for the end user specified.

        Note: this is energy generated so it is subtracted from demand.
        Treat as negative
        """
        # energy produced in kWh as 'negative demand'
        amount_produced = amount_produced * -1
        self._demand_energy(end_user_name=end_user_name, amount_demanded=amount_produced)

    def results_total(self) -> list[float]:
        """Return list of the total demand on this energy source for each timestep"""
        return self.__demand_total

    def results_by_end_user(self) -> dict[str, list[float]]:
        """Return the demand from each end user on this energy source for each timestep.

        Returns dictionary of lists, where dictionary keys are names of end users.
        """
        # If the keys do not match then we will just return the demand by end users
        if self.__demand_by_end_user.keys() != self.__energy_out_by_end_user.keys():
            return self.__demand_by_end_user

        all_results_by_end_user = {}
        for demand, energy_out in zip(
            self.__demand_by_end_user.items(), self.__energy_out_by_end_user.items(), strict=False
        ):
            if demand[0] == energy_out[0]:
                user_name = demand[
                    0
                ]  # Can use either demand[0] or energy_out[0] to retrieve end user name
                all_results_by_end_user[user_name] = np.array(demand[1]) + np.array(energy_out[1])

        return all_results_by_end_user

    def results_by_end_user_single_step(self, t_idx: int) -> dict[str, float]:
        """
        Return the demand from each end user on this energy source for this timestep.
        Returns dictionary of floats, where dictionary keys are names of end users.
        """

        all_results_by_end_user = {}
        for user_name in self.__demand_by_end_user.keys():
            if user_name in self.__energy_out_by_end_user.keys():
                all_results_by_end_user[user_name] = (
                    self.__demand_by_end_user[user_name][t_idx]
                    + self.__energy_out_by_end_user[user_name][t_idx]
                )
            else:
                all_results_by_end_user[user_name] = self.__demand_by_end_user[user_name][t_idx]

        return all_results_by_end_user

    def get_energy_import(self) -> list[float]:
        return self.__demand_not_met

    def get_energy_export(self) -> list[float]:
        return self.__supply_surplus

    def get_energy_export_from_generation(self) -> list[float]:
        return self.__supply_surplus

    def get_energy_generated_consumed(self) -> list[float]:
        """Return the amount of generated energy consumed in the building for all timesteps"""
        return self.__energy_generated_consumed

    def get_grid_to_consumption(self) -> list[float]:
        return self.__grid_to_consumption

    def get_energy_to_from_battery(
        self,
    ) -> tuple[list[float], list[float], list[float], list[float]]:
        """Return the amount of generated energy sent to battery and drawn from battery"""
        return (
            self.__energy_into_battery_from_generation,
            self.__energy_battery_to_consumption,
            self.__energy_into_battery_from_grid,
            self.__battery_state_of_charge,
        )

    def get_energy_diverted(self) -> list[float]:
        """Return the amount of generated energy diverted to minimise export"""
        return self.__energy_diverted

    def get_beta_factor(self) -> list[float]:
        return self.__beta_factor

    def is_charging_from_grid(self) -> tuple[bool, float, bool] | tuple[bool, float | None, bool]:
        """
        Check whether the Electric Battery is in a state where we allow charging from the grid
        This function is called at two different stages in the calculation:
        1. When considering discharging from the battery (electric demand from house)
        2. When considering charging from the grid
        """
        # TODO: Additional logic for grid charging decision
        #       Negative prices - Priority over PV? That would mean calling the function twice
        #                         Once before PV and again after but flagging if charging was
        #                         done in the first call.
        #       PV generation   - Currently set as priority for battery charging
        #       Seasonal threshold - Improve approach for charge threshold to cut grid charging when more PV available
        t_idx = self.__simulation_time.index()
        month = self.__simulation_time.current_month()
        threshold_charge = self.__threshold_charges[month] if self.__threshold_charges else None
        threshold_price = self.__threshold_prices[month] if self.__threshold_prices else None
        # For tariff selected look up price, etc, and decide whether to charge
        elec_price = (
            self.__tariff_data.get_price(tariff_name=self.__tariff, t_idx=t_idx)
            if self.__tariff is not None
            else None
        )
        current_charge = self.__elec_battery.get_state_of_charge() if self.__elec_battery else None
        charge_discharge_efficiency = (
            self.__elec_battery.get_charge_discharge_efficiency() if self.__elec_battery else None
        )

        if (
            elec_price is not None
            and charge_discharge_efficiency is not None
            and threshold_price is not None
            and elec_price / charge_discharge_efficiency < threshold_price
        ):
            if (
                threshold_charge is not None
                and current_charge is not None
                and current_charge < threshold_charge
            ):
                # return parameters are:
                # charging_condition      -- charging condition combining the price and charge thresholds criteria
                # threshold_charge        -- threshold charge for current timestep
                # can_charge_if_not_full  -- just the price threshold criteria for charging
                return True, threshold_charge, True
            else:
                return False, threshold_charge, True
        else:
            return False, threshold_charge, False

    def calc_energy_import_from_grid_to_battery(self):
        if self.__elec_battery is not None:
            t_idx = self.__simulation_time.index()
            if self.__elec_battery.is_grid_charging_possible():
                # Current conditions of the battery
                current_charge = self.__elec_battery.get_state_of_charge()
                max_capacity = self.__elec_battery.get_max_capacity()

                charging_condition, threshold_charge, __ = self.is_charging_from_grid()
                if charging_condition and threshold_charge is not None:
                    # Create max elec_demand from grid to complete battery charging if battery conditions allow
                    elec_demand = (
                        -max_capacity
                        * (threshold_charge - current_charge)
                        / self.__elec_battery.get_charge_efficiency()
                    )
                    # Attempt charging battery and retrieving energy_accepted
                    energy_accepted = -self.__elec_battery.charge_discharge_battery(
                        energy_flow=elec_demand
                    )
                    self.__energy_into_battery_from_grid[t_idx] = energy_accepted

                    # Informing EnergyImport of imported electricity
                    self.__demand_not_met[t_idx] += energy_accepted

            self.__battery_state_of_charge[t_idx] = self.__elec_battery.get_state_of_charge()

    def calc_energy_import_export_betafactor(self):
        """
        calculate how much of that supply can be offset against demand.
        And then calculate what demand and supply is left after offsetting, which are the amount exported imported
        """

        supplies = []
        demands = []
        t_idx = self.__simulation_time.index()
        for user in self.__demand_by_end_user.keys():
            demand = self.__demand_by_end_user[user][t_idx]
            if demand < 0.0:
                # if energy is negative that means its actually a supply, we
                # need to separate the two for beta factor calc. If we had
                # multiple different supplies they would have to be separated
                # here
                supplies.append(demand)
            else:
                demands.append(demand)

        self.__beta_factor[t_idx] = self.beta_factor_function(
            supply=-math.fsum(supplies), demand=math.fsum(demands), beta_factor_function="PV"
        )

        # PV elec consumed within dwelling in absence of battery storage or diverter (kWh)
        # if there were multiple sources they would each have their own beta factors
        supply_consumed = math.fsum(supplies) * self.__beta_factor[t_idx]
        # Surplus PV elec generation (kWh) - ie amount to be exported to the grid or batteries
        supply_surplus = math.fsum(supplies) * (1 - self.__beta_factor[t_idx])
        # Elec demand not met by PV (kWh) - ie amount to be imported from the grid or batteries
        demand_not_met = math.fsum(demands) + supply_consumed

        # See if there is a net supply/demand for the timestep
        if self.__priority is None and self.__elec_battery is not None:
            # See if the battery can deal with excess supply/demand for this timestep
            # supply_surplus is -ve by convention and demand_not_met is +ve
            # TODO: assumption made here that supply is done before demand, could
            # revise in future if more evidence becomes available.
            if self.__elec_battery.is_grid_charging_possible():
                charging_condition, __, can_charge_if_not_full = self.is_charging_from_grid()
            else:
                charging_condition = False
                can_charge_if_not_full = False
            if supply_surplus < 0:
                energy_out_of_battery = self.__elec_battery.charge_discharge_battery(
                    energy_flow=supply_surplus, charging_from_grid=charging_condition
                )
                supply_surplus -= energy_out_of_battery
                self.__energy_into_battery_from_generation[t_idx] = -energy_out_of_battery
            if demand_not_met > 0:
                # Calling is_charging_from_grid threshold level to avoid
                # discharging from the electric battery and
                # triggering lots of small grid recharge events
                # when the level of charge is close to the threshold
                if not can_charge_if_not_full:
                    energy_out_of_battery = self.__elec_battery.charge_discharge_battery(
                        energy_flow=demand_not_met
                    )
                    demand_not_met -= energy_out_of_battery
                    self.__energy_battery_to_consumption[t_idx] = -energy_out_of_battery

        if self.__priority is None and self.__diverter is not None:
            # Divert as much surplus energy as possible, and calculate remaining surplus
            self.__energy_diverted[t_idx] = self.__diverter.divert_surplus(
                supply_surplus=supply_surplus
            )
            supply_surplus += self.__energy_diverted[t_idx]

        # If the priority order of energy surplus is specified,calculate the same according to the order
        if self.__priority is not None:
            for item in self.__priority:
                if item == "ElectricBattery" and self.__elec_battery:
                    if self.__elec_battery.is_grid_charging_possible():
                        charging_condition, __, can_charge_if_not_full = (
                            self.is_charging_from_grid()
                        )
                    else:
                        charging_condition = False
                        can_charge_if_not_full = False
                    energy_out_of_battery = self.__elec_battery.charge_discharge_battery(
                        energy_flow=supply_surplus, charging_from_grid=charging_condition
                    )
                    supply_surplus -= energy_out_of_battery
                    self.__energy_into_battery_from_generation[t_idx] = -energy_out_of_battery
                    energy_out_of_battery = self.__elec_battery.charge_discharge_battery(
                        energy_flow=demand_not_met, charging_from_grid=can_charge_if_not_full
                    )
                    demand_not_met -= energy_out_of_battery
                    self.__energy_battery_to_consumption[t_idx] = -energy_out_of_battery
                if item == "diverter" and self.__diverter is not None:
                    self.__energy_diverted[t_idx] = self.__diverter.divert_surplus(
                        supply_surplus=supply_surplus
                    )
                    supply_surplus += self.__energy_diverted[t_idx]

        if self.__is_export_capable:
            self.__supply_surplus[t_idx] += supply_surplus
        self.__demand_not_met[t_idx] += demand_not_met
        self.__grid_to_consumption[t_idx] += demand_not_met
        # Report energy generated and consumed as positive number, so subtract negative number
        self.__energy_generated_consumed[t_idx] -= supply_consumed

    def beta_factor_function(
        self, supply: float, demand: float, beta_factor_function: str
    ) -> float:
        """
        wrapper that applies relevant function to obtain
        beta factor from energy supply+demand at a given timestep
        """

        if math.isclose(supply, 0.0, abs_tol=1e-10):
            beta_factor = 1.0
            return beta_factor

        if math.isclose(demand, 0.0, abs_tol=1e-10):
            beta_factor = 0.0
            return beta_factor

        demand_ratio = float(supply) / float(demand)
        if beta_factor_function == "PV":
            # Equation for beta factor below is based on hourly data from four
            # dwellings, which gives a similar monthly beta factor to that
            # calculated from the beta factor equation in SAP 10.2, which was
            # based on monthly data from 15 dwellings.
            # TODO: come up with better fit curve for PV
            beta_factor = min(0.6748 * pow(demand_ratio, -0.703), 1.0)
        # TODO
        # elif function=='wind':
        #     beta_factor=1.0
        else:
            raise ValueError("Invalid value for beta_factor_function")

        """
        predicted beta should not be greater than 1/demand_ratio, otherwise
        we might predict demand fulfilled by PV/generation to be greater than
        total demand.
        """

        beta_factor = min(beta_factor, 1 / demand_ratio)

        return beta_factor

    def timestep_end(self) -> None:
        if self.__elec_battery is not None:
            self.__elec_battery.timestep_end()

    def fuel_type(self) -> FuelType:
        return self.__fuel_type

    def has_battery(self) -> bool:
        if self.__elec_battery is not None:
            return True
        return False

    def get_battery_max_capacity(self) -> float | None:
        if self.__elec_battery is not None:
            return self.__elec_battery.get_max_capacity()
        return None

    def get_battery_charge_efficiency(self) -> float | None:
        if self.__elec_battery is not None:
            return self.__elec_battery.get_charge_efficiency()
        return None

    def get_battery_discharge_efficiency(self) -> float | None:
        if self.__elec_battery is not None:
            return self.__elec_battery.get_discharge_efficiency()
        return None

    def get_battery_max_discharge(self, charge: float) -> float | None:
        if self.__elec_battery is not None:
            return self.__elec_battery.calculate_max_discharge(state_of_charge=charge)
        return None

    def get_battery_available_charge(self) -> float | None:
        if self.__elec_battery is not None:
            return (
                self.__elec_battery.get_state_of_charge() * self.__elec_battery.get_max_capacity()
            )
        return None
