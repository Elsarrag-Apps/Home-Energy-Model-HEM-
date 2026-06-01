#!/usr/bin/env python3

"""
This module contains objects that represent photovoltaic systems.
"""

from __future__ import annotations

import math
from typing import Any

import hem_core.units as units
from hem_core.energy_supply.inverter import Inverter
from hem_core.energy_supply.on_site_generation_base import OnSiteGenerationBase
from hem_core.external_conditions import ExternalConditions
from hem_core.input_output.enums import InverterType
from hem_core.simulation_time import SimulationTime
from hem_core.space_heat_demand.building_element import projected_height


class PhotovoltaicPanel:
    """system performance factor lookup
    informative values from table C.4 Annex C BS EN 15316-4-3:2017
    note from 6.2.4.7.2 rear surface free - is if PV system is not integrated.
    Assume this means NOT integrated (BIPV)  or attached (BAPV)
    Increased by 0.85/0.8 based on median quoted performance ratio from
    "Performance of Distributed PV in the UK: A Statistical Analysis of
    Over 7000 systems" conference paper from 31st European Photovoltaic
    Solar Energy Conference and Exhibition, September 2015, assuming this
    applies to moderately ventilated case.
    """

    # Note: BS EN 15316-4-3:2017 section 6.2.4.7.2 states that the performance
    #       factor for "rear surface free" should be 1.0. However, this would
    #       seem to imply that there are no inverter or other system losses,
    #       despite the fact that section 6.2.4.7.5 states that this factor
    #       accounts for these losses. Also, no factor for "rear surface free"
    #       has been given in Table C.4. Therefore, it was decided to use the
    #       same factor for "rear surface free" as for "strongly or forced
    #       ventilated".
    __f_perf_lookup = {
        "unventilated": 0.81,
        "moderately_ventilated": 0.85,
        "strongly_or_forced_ventilated": 0.87,
        "rear_surface_free": 0.87,
    }

    def __init__(
        self,
        peak_power: float,
        ventilation_strategy: str,
        pitch: float,
        orientation: units.Orientation360,
        base_height: float,
        height: float,
        width: float,
        shading: list[dict[str, Any]],
    ) -> None:
        """Construct a PhotovoltaicPanel object

        Arguments:
        peak_power           -- Peak power in kW; represents the electrical power of a photovoltaic
                                system with a given area and a for a solar irradiance of 1 kW/m2
                                on this surface (at 25 degrees)
                                TODO - Could add other options at a later stage.
                                Standard has alternative method when peak power is not available
                                (input type of PV module and Area instead when peak power unknown)
        ventilation_strategy -- ventilation strategy of the PV system.
                                This will be used to determine the system performance factor
                                based on a lookup table
        pitch                -- is the tilt angle (inclination) of the PV panel from horizontal,
                                measured upwards facing, 0 to 90, in degrees.
                                0=horizontal surface, 90=vertical surface.
                                Needed to calculate solar irradiation at the panel surface.
        orientation          -- is the orientation angle of the inclined surface, expressed as the
                                geographical azimuth angle of the horizontal projection of the inclined
                                surface normal, 0 to 360, in degrees;
                                Needed to calculate solar irradiation at the panel surface.
        base_height          -- is the distance between the ground and the lowest edge of the PV panel, in m
        height               -- is the height of the PV panel, in m
        width                -- is the width of the PV panel, in m
        shading              -- TODO could add at a later date.
        """

        self.peak_power = peak_power
        self.f_perf = self.__f_perf_lookup[ventilation_strategy]
        self.pitch = pitch
        self.orientation = orientation
        self.base_height = base_height
        self.projected_height = projected_height(pitch, height)
        self.width = width
        self.shading = shading

    def shading_factors_direct(self, external_conditions: ExternalConditions) -> float:
        """return calculated shading factor"""
        return external_conditions.shading_reduction_factor_direct_diffuse(
            self.base_height,
            self.projected_height,
            self.width,
            self.pitch,
            self.orientation,
            self.shading,
        )[0]

    def shading_factors_diffuse(self, external_conditions: ExternalConditions) -> float:
        """return calculated shading factor"""
        return external_conditions.shading_reduction_factor_direct_diffuse(
            base_height=self.base_height,
            height=self.projected_height,
            width=self.width,
            tilt=self.pitch,
            orientation=self.orientation,
            window_shading=self.shading,
        )[1]

    def produce_energy(
        self,
        photovoltaicSystem: PhotovoltaicSystem,
        external_conditions: ExternalConditions,
        simulation_time: SimulationTime,
        f_sh_dir: float,
    ) -> float:
        # solar_irradiance in W/m2
        i_sol_dir, i_sol_dif, _, _ = external_conditions.calculated_direct_diffuse_total_irradiance(
            tilt=self.pitch, orientation=self.orientation
        )

        # diffuse shading factor
        f_sh_dif = self.shading_factors_diffuse(external_conditions=external_conditions)

        # Calculate the impact of direct shading on the panel/inverters ability to output energy,
        # i.e. where the shadow of an obstacle falls on the PV panel.
        # There is a lower impact if module level electronics ('optimised inverter') selected.
        # This factor is then applied in the energy_produced calculation later.
        if f_sh_dir < 1:
            inv_shad_inefficiency = photovoltaicSystem.inverter_efficiency_lookup(f_sh_dir=f_sh_dir)
        else:
            inv_shad_inefficiency = 1

        # solar_irradiation in kWh/m2
        solar_irradiation = (
            (i_sol_dir * f_sh_dir + i_sol_dif * f_sh_dif)
            * simulation_time.timestep()
            / units.W_per_kW
        )

        # reference_solar_irradiance kW/m2
        ref_solar_irradiance = 1

        # CALCULATION
        # E.el.pv.out.h = E.sol.pv.h * P.pk * f.perf / I.ref
        # energy_produced = solar_irradiation * peak_power * system_performance_factor
        #                    / reference_solar_irradiance
        # energy input in kWh; now need to calculate total energy produce taking into account inverter efficiency
        energy_input = (
            solar_irradiation
            * self.peak_power
            * self.f_perf
            * inv_shad_inefficiency
            / 0.972
            / ref_solar_irradiance
        )
        # f_perf is divided by 0.92 to avoid double-applying the inverter efficiency,
        # which is applied separately below via 'inverter_dc_ac_efficiency', since
        # inverter efficiency was inherently included in the factors taken from
        # from BS EN 15316-4-3:2017.

        return energy_input


class PhotovoltaicSystem(OnSiteGenerationBase):
    """An object to represent a photovoltaic system"""

    """
    Inverter efficiency reduction as a function of shaded proportion and type of inverter is based on data from
    'Partial Shade Evaluation of Distributed Power Electronics for Photovoltaic Systems', Chris Deline et al,
    figure 7, accessed at: https://www.nrel.gov/docs/fy12osti/54039.pdf.    
    
    The equations given in figure 7 were used to calculate the normalised power output for a range of different
    levels of panel covering, from 0 to 100% for the two inverter types represented (string and micro [aka optimised]). 
    
    The measured 37% transmission rate of the covering material was applied to determine the reduction in incident
    radiation at each level of coverage:
        % reduction in radiation reaching panel = percent of panel covered * (1 - 0.37)
    (where 1 = all radiation blocked, 0 = no reduction)      
    
    The level of shading was converted to a shading factor of the form used in HEM 
    (where 1 = no shading, 0 = complete shading):
        f_sh_dir = (1 - % reduction in radiation reaching panel)
        
    It was assumed that efficiency reduction being calculated is only related to the shading of *direct* radiation
    (not diffuse) on the basis that the impact is caused by part of the panel being shaded, while the rest is not. 
    Diffuse shading would affect the whole panel approximately equally, so should not affect inverter efficiency 
    in the same way. (Note that the reduction in output associated with the overall level of radiation - including 
    direct and diffuse shading - is separately accounted for).
    
    To set a reference point, it was assumed that, in the absence of a reduction due inverter efficiency, output would 
    be proportional to the incident solar radiation and therefore that the normalised output would be equal to the 
    shading factor - e.g. if 75% of the radiation was transmitted we would get 75% of the power output.
    
    The difference between this reference output and the output predicted by the equations representing the actual data
    was assumed to be due to the efficiency reduction of the inverter induced by overshading. The ratio of the 'expected'
    output and the 'actual' output was calculated. This step disaggregates the reduction due to inverter efficiency from 
    the reduction simply due to lower incident radiation, to avoid this being double counted. This is tehrefore the 
    correction factor needed in HEM to take into consideration the reduced efficiency of inverters when PV panels are 
    partially overshaded. 
    
    2nd order polynomial curves were fitted through the resulting inverter efficiency factors (as a function of the direct
    factor f_sh_dir, resulting in the equations used below). A two stage polynomial is needed for each inverter type
    because of the step change in behaviour when the 'lower limit' referred to in the source is reached.       
    """

    def inverter_efficiency_lookup(self, f_sh_dir: float) -> float:
        # Calculate inverter efficiency based on direct shading factor and inverter type
        x = f_sh_dir
        inverter_type = self.__inverter.type()

        if inverter_type == InverterType.STRING_INVERTER:
            thresh = 0.7
            a = 2.7666
            b = -4.3397
            c = 2.2201
            d = -1.9012
            e = 4.8821
            f = -1.9926
            if x < thresh:
                return min(1, a * x**2 + b * x + c)
            else:
                return min(1, d * x**2 + e * x + f)

        elif inverter_type == InverterType.OPTIMISED_INVERTER:  # aka micro inverter
            thresh = 0.42
            a = 2.7666
            b = -4.3397
            c = 2.2201
            d = -0.2024
            e = 0.4284
            f = 0.7721
            if x < thresh:
                return min(1, a * x**2 + b * x + c)
            else:
                return min(1, d * x**2 + e * x + f)
        else:
            raise ValueError(
                f"Invalid inverter type: {inverter_type}. Valid options are: {[inverter_type.value for inverter_type in InverterType]}"
            )

    def __init__(
        self,
        ext_cond: ExternalConditions,
        simulation_time: SimulationTime,
        panels: list[PhotovoltaicPanel],
        inverter: Inverter,
    ) -> None:
        """Construct a PhotovoltaicSystem object
        Arguments:
        ext_cond               -- reference to ExternalConditions object
        simulation_time        -- reference to SimulationTime object
        panels                 -- a list of PhotovoltaicSystem objects
        inverter               -- reference to Inverter object
        """
        self.__external_conditions = ext_cond
        self.__simulation_time = simulation_time
        self.__panels = panels
        self.__inverter = inverter

    def inverter_is_inside(self) -> bool:
        """Return whether this unit is considered inside the building or not"""
        return self.__inverter.is_inside()

    def produce_energy(self) -> tuple[float, float]:
        """Produce electrical energy (in kWh) from the PV system
        according to BS EN 15316-4-3:2017"""

        # Calculate a weighted f_sh_dir from the weighted average of the
        # direct shading factor and unshaded output of each panel
        total_unshaded_energy_produced = 0
        weighted_f_sh_dir = 0
        for panel in self.__panels:
            energy_produced = panel.produce_energy(
                self, self.__external_conditions, self.__simulation_time, f_sh_dir=1.0
            )
            total_unshaded_energy_produced += energy_produced
            weighted_f_sh_dir += (
                panel.shading_factors_direct(self.__external_conditions) * energy_produced
            )

        if total_unshaded_energy_produced < 0 or math.isclose(
            total_unshaded_energy_produced, 0.0, abs_tol=1e-10
        ):
            weighted_f_sh_dir = 1
        else:
            weighted_f_sh_dir /= total_unshaded_energy_produced

        total_energy_produced = 0
        for panel in self.__panels:
            energy_produced = panel.produce_energy(
                self, self.__external_conditions, self.__simulation_time, weighted_f_sh_dir
            )
            total_energy_produced += energy_produced

        # Add energy produced to the applicable energy supply connection via inverter (this will reduce demand)
        # calculate total power going to inverter
        power_input_inverter = total_energy_produced / self.__simulation_time.timestep()
        # Inverter will calculate the efficiency and apply ac/dc limits and return energy delivered to the supply connection
        total_energy_delivered = self.__inverter.produce_energy(power_input_inverter)
        total_energy_lost = total_energy_produced - total_energy_delivered

        return total_energy_delivered, total_energy_lost
