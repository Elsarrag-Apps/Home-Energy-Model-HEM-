#!/usr/bin/env python3

"""
This module contains unit tests for the building_element module
"""

# Standard library imports
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

# Local imports
from hem_core.external_conditions import ExternalConditions
from hem_core.input_output.enums import (
    FloorType,
    MassDistributionClass,
    TerrainClass,
    VentilationShieldClass,
    WindShieldLocation,
    ZoneTemperatureControlBasis,
)
from hem_core.simulation_time import SimulationTime
from hem_core.space_heat_demand.building_element import (
    BuildingElementAdjacentConditionedSpace,
    BuildingElementAdjacentUnconditionedSpace_Simple,
    BuildingElementGround,
    BuildingElementOpaque,
    BuildingElementPartyWall,
    BuildingElementTransparent,
)
from hem_core.space_heat_demand.thermal_bridge import ThermalBridgeLinear, ThermalBridgePoint
from hem_core.space_heat_demand.ventilation import InfiltrationVentilation, Vent, Window
from hem_core.space_heat_demand.zone import Zone
from hem_core.units import Orientation360


class TestZone(unittest.TestCase):
    """Unit tests for Zone class"""

    def setUp(self):
        """Create Zone object to be tested"""
        self.simtime = SimulationTime(start_time=0, end_time=2, step=1)
        air_temp_day_Jan = [
            0.0,
            0.5,
            1.0,
            1.5,
            2.0,
            2.5,
            3.0,
            3.5,
            4.0,
            4.5,
            5.0,
            7.5,
            10.0,
            12.5,
            15.0,
            19.5,
            17.0,
            15.0,
            12.0,
            10.0,
            7.0,
            5.0,
            3.0,
            1.0,
        ]
        air_temp_day_Feb = [x + 1.0 for x in air_temp_day_Jan]
        air_temp_day_Mar = [x + 2.0 for x in air_temp_day_Jan]
        air_temp_day_Apr = [x + 3.0 for x in air_temp_day_Jan]
        air_temp_day_May = [x + 4.0 for x in air_temp_day_Jan]
        air_temp_day_Jun = [x + 5.0 for x in air_temp_day_Jan]
        air_temp_day_Jul = [x + 6.0 for x in air_temp_day_Jan]
        air_temp_day_Aug = [x + 6.0 for x in air_temp_day_Jan]
        air_temp_day_Sep = [x + 5.0 for x in air_temp_day_Jan]
        air_temp_day_Oct = [x + 4.0 for x in air_temp_day_Jan]
        air_temp_day_Nov = [x + 3.0 for x in air_temp_day_Jan]
        air_temp_day_Dec = [x + 2.0 for x in air_temp_day_Jan]

        self.airtemp = []
        self.airtemp.extend(air_temp_day_Jan * 31)
        self.airtemp.extend(air_temp_day_Feb * 28)
        self.airtemp.extend(air_temp_day_Mar * 31)
        self.airtemp.extend(air_temp_day_Apr * 30)
        self.airtemp.extend(air_temp_day_May * 31)
        self.airtemp.extend(air_temp_day_Jun * 30)
        self.airtemp.extend(air_temp_day_Jul * 31)
        self.airtemp.extend(air_temp_day_Aug * 31)
        self.airtemp.extend(air_temp_day_Sep * 30)
        self.airtemp.extend(air_temp_day_Oct * 31)
        self.airtemp.extend(air_temp_day_Nov * 30)
        self.airtemp.extend(air_temp_day_Dec * 31)

        wind_speed_day_Jan = [
            4.7,
            4.8,
            4.9,
            5.0,
            5.1,
            5.2,
            5.3,
            5.4,
            5.7,
            5.4,
            5.6,
            5.3,
            5.1,
            4.8,
            4.7,
            4.6,
            4.5,
            4.2,
            4.9,
            4.3,
            4.4,
            4.5,
            4.3,
            4.6,
        ]
        wind_speed_day_Feb = [x - 0.1 for x in wind_speed_day_Jan]
        wind_speed_day_Mar = [x - 0.2 for x in wind_speed_day_Jan]
        wind_speed_day_Apr = [x - 0.6 for x in wind_speed_day_Jan]
        wind_speed_day_May = [x - 0.8 for x in wind_speed_day_Jan]
        wind_speed_day_Jun = [x - 1.1 for x in wind_speed_day_Jan]
        wind_speed_day_Jul = [x - 1.2 for x in wind_speed_day_Jan]
        wind_speed_day_Aug = [x - 1.2 for x in wind_speed_day_Jan]
        wind_speed_day_Sep = [x - 1.1 for x in wind_speed_day_Jan]
        wind_speed_day_Oct = [x - 0.7 for x in wind_speed_day_Jan]
        wind_speed_day_Nov = [x - 0.5 for x in wind_speed_day_Jan]
        wind_speed_day_Dec = [x - 0.3 for x in wind_speed_day_Jan]

        self.windspeed = []
        self.windspeed.extend(wind_speed_day_Jan * 31)
        self.windspeed.extend(wind_speed_day_Feb * 28)
        self.windspeed.extend(wind_speed_day_Mar * 31)
        self.windspeed.extend(wind_speed_day_Apr * 30)
        self.windspeed.extend(wind_speed_day_May * 31)
        self.windspeed.extend(wind_speed_day_Jun * 30)
        self.windspeed.extend(wind_speed_day_Jul * 31)
        self.windspeed.extend(wind_speed_day_Aug * 31)
        self.windspeed.extend(wind_speed_day_Sep * 30)
        self.windspeed.extend(wind_speed_day_Oct * 31)
        self.windspeed.extend(wind_speed_day_Nov * 30)
        self.windspeed.extend(wind_speed_day_Dec * 31)

        wind_direction_day_Jan = [
            300,
            250,
            220,
            180,
            150,
            120,
            100,
            80,
            60,
            40,
            20,
            10,
            50,
            100,
            140,
            190,
            200,
            320,
            330,
            340,
            350,
            355,
            315,
            5,
        ]
        wind_direction_day_Feb = [x - 1 for x in wind_direction_day_Jan]
        wind_direction_day_Mar = [x - 2 for x in wind_direction_day_Jan]
        wind_direction_day_Apr = [x - 3 for x in wind_direction_day_Jan]
        wind_direction_day_May = [x - 4 for x in wind_direction_day_Jan]
        wind_direction_day_Jun = [x + 1 for x in wind_direction_day_Jan]
        wind_direction_day_Jul = [x + 2 for x in wind_direction_day_Jan]
        wind_direction_day_Aug = [x + 3 for x in wind_direction_day_Jan]
        wind_direction_day_Sep = [x + 4 for x in wind_direction_day_Jan]
        wind_direction_day_Oct = [x - 5 for x in wind_direction_day_Jan]
        wind_direction_day_Nov = [x + 5 for x in wind_direction_day_Jan]
        wind_direction_day_Dec = [x - 0 for x in wind_direction_day_Jan]

        self.wind_direction = []
        self.wind_direction.extend(wind_direction_day_Jan * 31)
        self.wind_direction.extend(wind_direction_day_Feb * 28)
        self.wind_direction.extend(wind_direction_day_Mar * 31)
        self.wind_direction.extend(wind_direction_day_Apr * 30)
        self.wind_direction.extend(wind_direction_day_May * 31)
        self.wind_direction.extend(wind_direction_day_Jun * 30)
        self.wind_direction.extend(wind_direction_day_Jul * 31)
        self.wind_direction.extend(wind_direction_day_Aug * 31)
        self.wind_direction.extend(wind_direction_day_Sep * 30)
        self.wind_direction.extend(wind_direction_day_Oct * 31)
        self.wind_direction.extend(wind_direction_day_Nov * 30)
        self.wind_direction.extend(wind_direction_day_Dec * 31)

        self.diffuse_horizontal_radiation = [333.0, 610.0, 572.0, 420.0, 0.0, 10.0, 90.0, 275.0]
        self.direct_beam_radiation = [420.0, 750.0, 425.0, 500.0, 0.0, 40.0, 0.0, 388.0]
        self.solar_reflectivity_of_ground = [0.2] * 8760
        self.latitude = 51.42
        self.longitude = -0.75
        self.timezone = 0
        self.start_day = 0
        self.end_day = 0
        self.time_series_step = 1
        self.january_first = 1
        self.daylight_savings = "not applicable"
        self.leap_day_included = False
        self.direct_beam_conversion_needed = False
        self.shading_segments = [
            {
                "number": 1,
                "start360": Orientation360.create_from_180(angle180=180),
                "end360": Orientation360.create_from_180(angle180=135),
            },
            {
                "number": 2,
                "start360": Orientation360.create_from_180(angle180=135),
                "end360": Orientation360.create_from_180(angle180=90),
            },
            {
                "number": 3,
                "start360": Orientation360.create_from_180(angle180=90),
                "end360": Orientation360.create_from_180(angle180=45),
            },
            {
                "number": 4,
                "start360": Orientation360.create_from_180(angle180=45),
                "end360": Orientation360.create_from_180(angle180=0),
            },
            {
                "number": 5,
                "start360": Orientation360.create_from_180(angle180=0),
                "end360": Orientation360.create_from_180(angle180=-45),
            },
            {
                "number": 6,
                "start360": Orientation360.create_from_180(angle180=-45),
                "end360": Orientation360.create_from_180(angle180=-90),
            },
            {
                "number": 7,
                "start360": Orientation360.create_from_180(angle180=-90),
                "end360": Orientation360.create_from_180(angle180=-135),
            },
            {
                "number": 8,
                "start360": Orientation360.create_from_180(angle180=-135),
                "end360": Orientation360.create_from_180(angle180=-180),
            },
        ]
        extcond = ExternalConditions(
            simulation_time=self.simtime,
            air_temps=self.airtemp,
            wind_speeds=self.windspeed,
            wind_directions=self.wind_direction,
            diffuse_horizontal_radiation=self.diffuse_horizontal_radiation,
            direct_beam_radiation=self.direct_beam_radiation,
            solar_reflectivity_of_ground=self.solar_reflectivity_of_ground,
            latitude=self.latitude,
            longitude=self.longitude,
            timezone=self.timezone,
            start_day=self.start_day,
            end_day=self.end_day,
            time_series_step=self.time_series_step,
            january_first=self.january_first,
            daylight_savings=self.daylight_savings,
            leap_day_included=self.leap_day_included,
            direct_beam_conversion_needed=self.direct_beam_conversion_needed,
            shading_segments=self.shading_segments,
        )

        window_part_list = [{"mid_height_air_flow_path": 1.5}]
        window_obj = Window(
            free_area_height=1.6,
            midheight=1,
            max_opening_area=3,
            window_part_list=window_part_list,
            orientation=Orientation360.create_from_180(0),
            pitch=0,
            altitude=30,
            on_off_ctrl_obj=None,
            ventilation_zone_base_height=2.5,
        )
        self.window = {"window 0": window_obj}

        vent_obj = Vent(
            midheight=1.5,
            area=100.0,
            delta_p_vent_ref=20.0,
            orientation=Orientation360.create_from_180(180.0),
            pitch=60.0,
            altitude=30.0,
            ventilation_zone_base_height=2.5,
        )
        self.vent = {"vent 1": vent_obj}

        self.leaks = {
            "ventilation_zone_height": 6,
            "test_pressure": 50,
            "test_result": 1.2,
            "env_area": 220,
            "area_facades": 85.0,
            "area_roof": 25.0,
            "altitude": 30,
        }

        self.infilvent = InfiltrationVentilation(
            simulation_time=self.simtime,
            f_cross=True,
            shield_class=VentilationShieldClass.NORMAL,
            terrain_class=TerrainClass.OPEN_FIELD,
            average_roof_pitch=20.0,
            windows=self.window,
            vents=self.vent,
            leaks=self.leaks,
            combustion_appliances={},
            ATDs={},
            mech_vents=[],
            detailed_output_heating_cooling=False,
            altitude=30.0,
            total_volume=250.0,
            ventilation_zone_base_height=2.5,
        )

        # Create objects for the different building elements in the zone
        be_opaque_I = BuildingElementOpaque(
            area=20,
            is_unheated_pitched_roof=False,
            pitch=180,
            solar_absorption_coeff=0.60,
            thermal_resistance_construction=0.25,
            areal_heat_capacity=19000.0,
            mass_distribution_class=MassDistributionClass.I,
            orientation=Orientation360.create_from_180(0),
            base_height=0,
            height=2,
            width=10,
            ext_cond=extcond,
        )
        be_opaque_D = BuildingElementOpaque(
            area=26,
            is_unheated_pitched_roof=True,
            pitch=45,
            solar_absorption_coeff=0.55,
            thermal_resistance_construction=0.33,
            areal_heat_capacity=16000.0,
            mass_distribution_class=MassDistributionClass.D,
            orientation=Orientation360.create_from_180(0),
            base_height=0,
            height=2,
            width=10,
            ext_cond=extcond,
        )
        be_ZTC = BuildingElementAdjacentConditionedSpace(
            area=22.5,
            pitch=135,
            thermal_resistance_construction=0.50,
            areal_heat_capacity=18000.0,
            mass_distribution_class=MassDistributionClass.E,
            ext_cond=extcond,
        )
        be_ground = BuildingElementGround(
            total_area=25.0,
            area=25.0,
            pitch=90,
            u_value=1.33,
            thermal_resistance_floor_construction=0.2,
            areal_heat_capacity=17000.0,
            mass_distribution_class=MassDistributionClass.IE,
            floor_type=FloorType.SUSPENDED_FLOOR,
            edge_insulation=None,
            h_upper=0.5,
            u_f_s=None,
            u_w=0.5,
            area_per_perimeter_vent=0.01,
            shield_fact_location=WindShieldLocation.SHELTERED,
            d_we=0.3,
            r_f_ins=7,
            z_b=None,
            r_w_b=None,
            h_w=None,
            perimeter=20.0,
            psi_wall_floor_junc=0.7,
            ext_cond=extcond,
            simulation_time=self.simtime,
        )
        be_transparent = BuildingElementTransparent(
            pitch=90,
            thermal_resistance_construction=0.4,
            orientation=Orientation360.create_from_180(180),
            g_value=0.75,
            frame_area_fraction=0.25,
            base_height=1,
            height=1.25,
            width=4,
            shading=[],
            treatment=[],
            ext_cond=extcond,
            simtime=self.simtime,
        )
        be_ZTU = BuildingElementAdjacentUnconditionedSpace_Simple(
            area=30,
            pitch=130,
            thermal_resistance_construction=0.50,
            thermal_resistance_unconditioned_space=0.6,
            areal_heat_capacity=18000.0,
            mass_distribution_class=MassDistributionClass.E,
            ext_cond=extcond,
        )

        # Put building element objects in a list that can be iterated over
        self.be_objs = [be_opaque_I, be_opaque_D, be_ZTC, be_ground, be_transparent, be_ZTU]

        # Create objects for thermal bridges
        tb_linear_1 = ThermalBridgeLinear(linear_therm_trans=0.28, length=5.0)
        tb_linear_2 = ThermalBridgeLinear(linear_therm_trans=0.25, length=6.0)
        tb_point = ThermalBridgePoint(heat_transfer_coeff=1.4)

        # Put thermal bridge objects in a list that can be iterated over
        tb_objs = [tb_linear_1, tb_linear_2, tb_point]

        self.temp_ext_air_init = 2.2
        self.temp_setpnt_init = 21.0
        self.temp_setpnt_basis = ZoneTemperatureControlBasis.AIR

        self.zone = Zone(
            area=80.0,
            volume=250.0,
            building_elements=self.be_objs,
            thermal_bridging=tb_objs,
            vent_obj=self.infilvent,
            temp_ext_air_init=self.temp_ext_air_init,
            temp_setpnt_init=self.temp_setpnt_init,
            temp_setpnt_basis=self.temp_setpnt_basis,
            control_obj=None,
            print_heat_balance=True,
        )

    def test_init_single_thermal_bridging_value(self):
        """Test that constructor can take a single value for the thermal bridging"""
        self.zone = Zone(
            area=80.0,
            volume=250.0,
            building_elements=self.be_objs,
            thermal_bridging=4,
            vent_obj=self.infilvent,
            temp_ext_air_init=self.temp_ext_air_init,
            temp_setpnt_init=self.temp_setpnt_init,
            temp_setpnt_basis=self.temp_setpnt_basis,
            control_obj=None,
            print_heat_balance=True,
        )

        self.assertEqual(self.zone._Zone__tb_heat_trans_coeff, 4)  # type: ignore[AttributeAccessIssue]

    def test_setpnt_init(self):
        """Test that setpnt_init returns the correct value"""
        self.assertEqual(self.zone.setpnt_init(), 21.0)

    def test_area(self):
        """Test that area returns the correct value"""
        self.assertEqual(self.zone.area(), 80.0)

    def test_gains_solar(self):
        """Test that gains_solar returns the correct value"""
        self.assertAlmostEqual(self.zone.gains_solar(), -2154.583062153444)

    def test_volume(self):
        """Test that the correct volume is returned when queried"""
        self.assertEqual(self.zone.volume(), 250.0, "incorrect volume returned")

    def test_total_fabric_heat_loss(self):
        """Test that the correct total for fabric heat loss is returned when queried"""
        self.assertAlmostEqual(
            self.zone.total_fabric_heat_loss(),
            181.99557093947166,
            2,
            "incorrect total fabric heat loss returned",
        )

    def test_total_heat_capacity(self):
        """Test that the correct total for heat capacity is returned when queried"""
        self.assertEqual(
            self.zone.total_heat_capacity(), 2166, "incorrect total heat capacity returned"
        )

    def test_total_heat_loss_area(self):
        """Test that total_heat_loss_area returns the correct value"""
        self.assertAlmostEqual(self.zone.total_heat_loss_area(), 106.0)

    def test_total_thermal_bridges(self):
        """Test that the correct total for thermal bridges is returned when queried"""
        self.assertAlmostEqual(
            self.zone.total_thermal_bridges(), 4.3, 2, "incorrect thermal bridge total returned"
        )

    def test_temp_operative(self):
        """Test that temp_operative returns the correct value"""
        self.assertAlmostEqual(self.zone.temp_operative(), 18.92809674634258)

    def test_temp_internal_air(self):
        """Test that temp_internal_air returns the correct value"""
        self.assertAlmostEqual(self.zone.temp_internal_air(), 20.999999999999996)

    def test_fast_solver(self):
        """Test that fast_solver returns the correct values"""
        coeffs = np.empty((28, 28), dtype=np.float64)
        rhs = np.empty((28), dtype=np.float64)
        coeffs[0][1] = 3
        coeffs[2][1] = 3
        coeffs[4][3] = 3

        np.fill_diagonal(coeffs, 2)
        rhs.fill(2000)

        expected = np.linalg.solve(coeffs, rhs)

        result = self.zone._Zone__fast_solver(coeffs=coeffs, rhs=rhs)  # type: ignore[AttributeAccessIssue]

        np.testing.assert_allclose(result, expected)

    def test_update_temperatures(self):
        """Test that update_temperatures returns the correct value and updates temp_prev"""
        delta_t = 1800
        temp_ext_air = 10
        gains_internal = 200
        gains_solar = 220
        gains_heat_cool = 0
        frac_convective = 1
        ach = 0.4
        avg_supply_temp = 10

        heat_balance_dict_expected = {
            "air_node": {
                "solar gains": 22.0,
                "internal gains": 80.0,
                "heating or cooling system gains": 0,
                "energy to change internal temperature": 1617.0201164499708,
                "thermal_bridges": -31.655330373346523,
                "infiltration_ventilation": -247.6853738767846,
                "fabric": -1439.6794121998396,
            },
            "internal_boundary": {
                "fabric_int_air_convective": 1439.679412199842,
                "fabric_int_sol": 198.0,
                "fabric_int_int_gains": 120.0,
                "fabric_int_heat_cool": 0.0,
            },
            "external_boundary": {
                "solar gains": 220,
                "internal gains": 200,
                "heating or cooling system gains": 0,
                "thermal_bridges": -31.655330373346523,
                "infiltration_ventilation": -247.6853738767846,
                "fabric_ext_air_convective": 465.59408303760006,
                "fabric_ext_air_radiative": 355.39880327150297,
                "fabric_ext_sol": -3204.6068977063023,
                "fabric_ext_sky": -1124.4913565980596,
                "opaque_fabric_ext": -2118.880733022755,
                "transparent_fabric_ext": -137.91628674680447,
                "ground_fabric_ext": -816.8733439646372,
                "ZTC_fabric_ext": 0.0,
                "ZTU_fabric_ext": -434.43500426106175,
            },
        }

        temp_prev_expected = np.array(
            [
                11.40867164,
                12.01137488,
                13.21678138,
                14.42218788,
                15.02489113,
                -12.1159808,
                -8.26009178,
                -0.68574761,
                6.55776467,
                9.87697085,
                19.68360344,
                18.98718416,
                17.59434561,
                16.20150706,
                15.50508779,
                -1.09693254,
                4.34888975,
                10.30679644,
                12.52103871,
                13.62815985,
                0.19938929,
                11.23269223,
                9.28858272,
                9.88213728,
                11.0692464,
                12.25635552,
                12.84991008,
                17.36170474,
            ],
            dtype=np.float64,
        )

        heat_balance_dict: dict = self.zone.update_temperatures(
            delta_t=delta_t,
            temp_ext_air=temp_ext_air,
            gains_internal=gains_internal,
            gains_solar=gains_solar,
            gains_heat_cool=gains_heat_cool,
            frac_convective=frac_convective,
            ach=ach,
            avg_supply_temp=avg_supply_temp,
        )

        np.testing.assert_allclose(self.zone._Zone__temp_prev, temp_prev_expected)  # type: ignore[AttributeAccessIssue]

        self.assertEqual(heat_balance_dict.keys(), heat_balance_dict_expected.keys())
        for key1 in heat_balance_dict_expected.keys():
            self.assertEqual(
                heat_balance_dict[key1].keys(), heat_balance_dict_expected[key1].keys()
            )
            for key2 in heat_balance_dict_expected[key1].keys():
                self.assertAlmostEqual(
                    heat_balance_dict[key1][key2], heat_balance_dict_expected[key1][key2]
                )

    def test_ach_req_to_reach_temperature(self):
        """Test that ach_req_to_reach_temperature returns the correct values"""
        ach = self.zone._Zone___ach_req_to_reach_temperature(  # type: ignore[AttributeAccessIssue]
            temp_target=21,
            ach_min=0.08,
            ach_max=48,
            temp_ach_min=9.9,
            temp_ach_max=8.8,
            temp_int_air_min=9.8,
            temp_int_air_max=8.2,
            temp_supply=8.1,
        )
        self.assertAlmostEqual(ach, 0.08)

        ach = self.zone._Zone___ach_req_to_reach_temperature(  # type: ignore[AttributeAccessIssue]
            temp_target=21,
            ach_min=0.08,
            ach_max=48,
            temp_ach_min=9.9,
            temp_ach_max=12,
            temp_int_air_min=9.8,
            temp_int_air_max=8.2,
            temp_supply=8.1,
        )
        self.assertAlmostEqual(ach, 0.08)

        ach = self.zone._Zone___ach_req_to_reach_temperature(  # type: ignore[AttributeAccessIssue]
            temp_target=21,
            ach_min=0.08,
            ach_max=48,
            temp_ach_min=9.9,
            temp_ach_max=8.8,
            temp_int_air_min=12,
            temp_int_air_max=8.2,
            temp_supply=10,
        )
        self.assertAlmostEqual(ach, 21.65371789094187)

        ach = self.zone._Zone___ach_req_to_reach_temperature(  # type: ignore[AttributeAccessIssue]
            temp_target=5,
            ach_min=0.08,
            ach_max=48,
            temp_ach_min=9.9,
            temp_ach_max=8.8,
            temp_int_air_min=12,
            temp_int_air_max=11,
            temp_supply=10,
        )
        self.assertAlmostEqual(ach, 48)

    def test_calc_cooling_potential_from_ventilation(self):
        """Test that calc_cooling_potential_from_ventilation returns the correct values"""
        temp_free, ach_cooling, ach_to_trigger_heating = (
            self.zone._Zone__calc_cooling_potential_from_ventilation(  # type: ignore[AttributeAccessIssue]
                delta_t=1800.0,
                temp_ext_air=17.8,
                gains_internal=6.6,
                gains_solar=0.0,
                gains_heat_cool=0.0,
                frac_conv_gains_heat_cool=0.0,
                temp_setpnt_heat=21.0,
                temp_setpnt_cool=24.0,
                temp_setpnt_cool_vent=22.0,
                temp_free=20.0,
                temp_int_air_free=20.0,
                ach_cooling=None,
                ach_windows_open=0.16,
                ach_target=0.13,
                avg_supply_temp=17.8,
            )
        )

        self.assertAlmostEqual(temp_free, 20.0)
        self.assertAlmostEqual(ach_cooling, 0.13)
        self.assertAlmostEqual(ach_to_trigger_heating, 0.13105245458346534)

        temp_free, ach_cooling, ach_to_trigger_heating = (
            self.zone._Zone__calc_cooling_potential_from_ventilation(  # type: ignore[AttributeAccessIssue]
                delta_t=1800.0,
                temp_ext_air=17.8,
                gains_internal=6.6,
                gains_solar=0.0,
                gains_heat_cool=0.0,
                frac_conv_gains_heat_cool=0.0,
                temp_setpnt_heat=21.0,
                temp_setpnt_cool=24.0,
                temp_setpnt_cool_vent=18.0,
                temp_free=20.0,
                temp_int_air_free=20.0,
                ach_cooling=None,
                ach_windows_open=0.16,
                ach_target=0.13,
                avg_supply_temp=17.8,
            )
        )

        self.assertAlmostEqual(temp_free, 17.52067994302452)
        self.assertAlmostEqual(ach_cooling, 0.13)
        self.assertAlmostEqual(ach_to_trigger_heating, 0.13105245458346534)

        temp_free, ach_cooling, ach_to_trigger_heating = (
            self.zone._Zone__calc_cooling_potential_from_ventilation(  # type: ignore[AttributeAccessIssue]
                delta_t=1800.0,
                temp_ext_air=17.8,
                gains_internal=6.6,
                gains_solar=0.0,
                gains_heat_cool=0.0,
                frac_conv_gains_heat_cool=0.0,
                temp_setpnt_heat=21.0,
                temp_setpnt_cool=15.0,
                temp_setpnt_cool_vent=18.0,
                temp_free=20.0,
                temp_int_air_free=20.0,
                ach_cooling=None,
                ach_windows_open=0.16,
                ach_target=0.13,
                avg_supply_temp=17.8,
            )
        )

        self.assertAlmostEqual(temp_free, 20.0)
        self.assertAlmostEqual(ach_cooling, 0.13)
        self.assertAlmostEqual(ach_to_trigger_heating, 0.13105245458346534)

        self.zone._Zone__temp_setpnt_basis = ZoneTemperatureControlBasis.OPERATIVE  # type: ignore[AttributeAccessIssue]

        temp_free, ach_cooling, ach_to_trigger_heating = (
            self.zone._Zone__calc_cooling_potential_from_ventilation(  # type: ignore[AttributeAccessIssue]
                delta_t=1800.0,
                temp_ext_air=17.8,
                gains_internal=6.6,
                gains_solar=0.0,
                gains_heat_cool=0.0,
                frac_conv_gains_heat_cool=0.0,
                temp_setpnt_heat=21.0,
                temp_setpnt_cool=24.0,
                temp_setpnt_cool_vent=22.0,
                temp_free=19.9,
                temp_int_air_free=20.0,
                ach_cooling=None,
                ach_windows_open=0.16,
                ach_target=0.13,
                avg_supply_temp=17.8,
            )
        )

        self.assertAlmostEqual(temp_free, 19.9)
        self.assertAlmostEqual(ach_cooling, 0.13)
        self.assertAlmostEqual(ach_to_trigger_heating, 0.1306962441148573)

        temp_free, ach_cooling, ach_to_trigger_heating = (
            self.zone._Zone__calc_cooling_potential_from_ventilation(  # type: ignore[AttributeAccessIssue]
                delta_t=1800.0,
                temp_ext_air=17.8,
                gains_internal=6.6,
                gains_solar=0.0,
                gains_heat_cool=0.0,
                frac_conv_gains_heat_cool=0.0,
                temp_setpnt_heat=21.0,
                temp_setpnt_cool=24.0,
                temp_setpnt_cool_vent=18.0,
                temp_free=19.9,
                temp_int_air_free=20.0,
                ach_cooling=None,
                ach_windows_open=0.16,
                ach_target=0.13,
                avg_supply_temp=17.8,
            )
        )

        self.assertAlmostEqual(temp_free, 15.144632024928118)
        self.assertAlmostEqual(ach_cooling, 0.13)
        self.assertAlmostEqual(ach_to_trigger_heating, 0.1306962441148573)

        temp_free, ach_cooling, ach_to_trigger_heating = (
            self.zone._Zone__calc_cooling_potential_from_ventilation(  # type: ignore[AttributeAccessIssue]
                delta_t=1800.0,
                temp_ext_air=17.8,
                gains_internal=6.6,
                gains_solar=0.0,
                gains_heat_cool=0.0,
                frac_conv_gains_heat_cool=0.0,
                temp_setpnt_heat=21.0,
                temp_setpnt_cool=15.0,
                temp_setpnt_cool_vent=18.0,
                temp_free=19.9,
                temp_int_air_free=20.0,
                ach_cooling=None,
                ach_windows_open=0.16,
                ach_target=0.13,
                avg_supply_temp=17.8,
            )
        )

        self.assertAlmostEqual(temp_free, 19.9)
        self.assertAlmostEqual(ach_cooling, 0.13)
        self.assertAlmostEqual(ach_to_trigger_heating, 0.1306962441148573)

    def test_interp_heat_cool_demand(self):
        """Test that interp_heat_cool_demand returns the correct values"""
        self.zone._Zone__temp_setpnt_basis = ZoneTemperatureControlBasis.AIR  # type: ignore[AttributeAccessIssue]
        heat_cool_demand = self.zone._Zone__interp_heat_cool_demand(  # type: ignore[AttributeAccessIssue]
            delta_t_h=0.5, temp_setpnt=20, heat_cool_load_upper=4000, temp_free=18, temp_upper=21.2
        )
        self.assertAlmostEqual(heat_cool_demand, 1.2500000000000002)

        self.zone._Zone__temp_setpnt_basis = ZoneTemperatureControlBasis.OPERATIVE  # type: ignore[AttributeAccessIssue]
        heat_cool_demand = self.zone._Zone__interp_heat_cool_demand(  # type: ignore[AttributeAccessIssue]
            delta_t_h=0.5, temp_setpnt=20, heat_cool_load_upper=4000, temp_free=20, temp_upper=19
        )
        self.assertAlmostEqual(heat_cool_demand, 0)

    def test_interp_heat_cool_demand_invalid(self):
        """Test that interp_heat_cool_demand throws on invalid parameters"""
        with self.assertRaises(ValueError):
            self.zone._Zone__temp_setpnt_basis = ZoneTemperatureControlBasis.OPERATIVE  # type: ignore[AttributeAccessIssue]
            self.zone._Zone__interp_heat_cool_demand(  # type: ignore[AttributeAccessIssue]
                delta_t_h=0.5,
                temp_setpnt=20,
                heat_cool_load_upper=4000,
                temp_free=19,
                temp_upper=19,
            )

        with self.assertRaises(ValueError):
            self.zone._Zone__temp_setpnt_basis = ZoneTemperatureControlBasis.AIR  # type: ignore[AttributeAccessIssue]
            self.zone._Zone__interp_heat_cool_demand(  # type: ignore[AttributeAccessIssue]
                delta_t_h=0.5,
                temp_setpnt=20,
                heat_cool_load_upper=4000,
                temp_free=18,
                temp_upper=18,
            )

    def test_space_heat_cool_demand(self):
        """Test that space_heat_cool_demand returns the correct values"""
        with self.assertRaises(ValueError):
            self.zone.space_heat_cool_demand(
                delta_t_h=0.5,
                temp_ext_air=2.8,
                gains_internal=13.5,
                gains_solar=9.1,
                frac_convective_heat=0.4,
                frac_convective_cool=0.95,
                temp_setpnt_heat=24.0,
                temp_setpnt_cool=21.0,
                avg_air_supply_temp=2.8,
                gains_heat_cool_convective=0.0,
                gains_heat_cool_radiative=0.0,
                ach_windows_open=0.17,
                ach_target=0.14,
                ach_cooling=None,
            )

        space_heat_demand, space_cool_demand, ach_cooling, ach_to_trigger_heating = (
            self.zone.space_heat_cool_demand(
                delta_t_h=0.5,
                temp_ext_air=2.8,
                gains_internal=13.5,
                gains_solar=9.1,
                frac_convective_heat=0.4,
                frac_convective_cool=0.95,
                temp_setpnt_heat=21.0,
                temp_setpnt_cool=24.0,
                avg_air_supply_temp=2.8,
                gains_heat_cool_convective=0.0,
                gains_heat_cool_radiative=0.0,
                ach_windows_open=0.17,
                ach_target=0.14,
                ach_cooling=None,
            )
        )

        self.assertAlmostEqual(space_heat_demand, 2.1541345392835387)
        self.assertAlmostEqual(space_cool_demand, 0)
        self.assertAlmostEqual(ach_cooling, 0.14)
        self.assertAlmostEqual(ach_to_trigger_heating, 0.14)

        self.zone._Zone__control_obj = MagicMock()  # type: ignore[AttributeAccessIssue]
        self.zone._Zone__control_obj.setpnt.return_value = 25  # type: ignore[AttributeAccessIssue]

        space_heat_demand, space_cool_demand, ach_cooling, ach_to_trigger_heating = (
            self.zone.space_heat_cool_demand(
                delta_t_h=0.5,
                temp_ext_air=2.8,
                gains_internal=13.5,
                gains_solar=9.1,
                frac_convective_heat=0.4,
                frac_convective_cool=0.95,
                temp_setpnt_heat=21.0,
                temp_setpnt_cool=24.0,
                avg_air_supply_temp=2.8,
                gains_heat_cool_convective=0.0,
                gains_heat_cool_radiative=0.0,
                ach_windows_open=0.17,
                ach_target=0.14,
                ach_cooling=None,
            )
        )

        self.assertAlmostEqual(space_heat_demand, 2.1541345392835387)
        self.assertAlmostEqual(space_cool_demand, 0)
        self.assertAlmostEqual(ach_cooling, 0.14)
        self.assertAlmostEqual(ach_to_trigger_heating, 0.14)

        with self.assertRaises(ValueError):
            self.zone._Zone__control_obj.setpnt.return_value = 20  # type: ignore[AttributeAccessIssue]
            self.zone.space_heat_cool_demand(
                delta_t_h=0.5,
                temp_ext_air=2.8,
                gains_internal=13.5,
                gains_solar=9.1,
                frac_convective_heat=0.4,
                frac_convective_cool=0.95,
                temp_setpnt_heat=21.0,
                temp_setpnt_cool=24.0,
                avg_air_supply_temp=2.8,
                gains_heat_cool_convective=0.0,
                gains_heat_cool_radiative=0.0,
                ach_windows_open=0.17,
                ach_target=0.14,
                ach_cooling=None,
            )

        self.zone._Zone__control_obj.setpnt.return_value = None  # type: ignore[AttributeAccessIssue]
        space_heat_demand, space_cool_demand, ach_cooling, ach_to_trigger_heating = (
            self.zone.space_heat_cool_demand(
                delta_t_h=0.5,
                temp_ext_air=2.8,
                gains_internal=13.5,
                gains_solar=9.1,
                frac_convective_heat=0.4,
                frac_convective_cool=0.95,
                temp_setpnt_heat=21.0,
                temp_setpnt_cool=24.0,
                avg_air_supply_temp=2.8,
                gains_heat_cool_convective=0.0,
                gains_heat_cool_radiative=0.0,
                ach_windows_open=0.17,
                ach_target=0.14,
                ach_cooling=None,
            )
        )

        self.assertAlmostEqual(space_heat_demand, 2.1541345392835387)
        self.assertAlmostEqual(space_cool_demand, 0)
        self.assertAlmostEqual(ach_cooling, 0.14)
        self.assertAlmostEqual(ach_to_trigger_heating, 0.14)

        with self.assertRaises(ValueError):
            self.zone._Zone__control_obj = None  # type: ignore[AttributeAccessIssue]
            self.zone.space_heat_cool_demand(
                delta_t_h=0.5,
                temp_ext_air=2.8,
                gains_internal=13.5,
                gains_solar=9.1,
                frac_convective_heat=0.4,
                frac_convective_cool=0.95,
                temp_setpnt_heat=2.6e32,
                temp_setpnt_cool=2.7e32,
                avg_air_supply_temp=2.8,
                gains_heat_cool_convective=0.0,
                gains_heat_cool_radiative=0.0,
                ach_windows_open=0.17,
                ach_target=0.14,
                ach_cooling=None,
            )

        space_heat_demand, space_cool_demand, ach_cooling, ach_to_trigger_heating = (
            self.zone.space_heat_cool_demand(
                delta_t_h=0.5,
                temp_ext_air=2.8,
                gains_internal=13.5,
                gains_solar=9.1,
                frac_convective_heat=0.4,
                frac_convective_cool=0.95,
                temp_setpnt_heat=21.0,
                temp_setpnt_cool=24.0,
                avg_air_supply_temp=2.8,
                gains_heat_cool_convective=0.2,
                gains_heat_cool_radiative=0.3,
                ach_windows_open=0.17,
                ach_target=0.14,
                ach_cooling=None,
            )
        )

        self.assertAlmostEqual(space_heat_demand, 2.153884539283528)
        self.assertAlmostEqual(space_cool_demand, 0)
        self.assertAlmostEqual(ach_cooling, 0.14)
        self.assertAlmostEqual(ach_to_trigger_heating, 0.14)

        space_heat_demand, space_cool_demand, ach_cooling, ach_to_trigger_heating = (
            self.zone.space_heat_cool_demand(
                delta_t_h=0.5,
                temp_ext_air=2.8,
                gains_internal=13.5,
                gains_solar=9.1,
                frac_convective_heat=0.4,
                frac_convective_cool=0.95,
                temp_setpnt_heat=21.0,
                temp_setpnt_cool=24.0,
                avg_air_supply_temp=2.8,
                gains_heat_cool_convective=0.0,
                gains_heat_cool_radiative=0.0,
                ach_windows_open=0.17,
                ach_target=0.14,
                ach_cooling=None,
            )
        )

        self.assertAlmostEqual(space_heat_demand, 2.1541345392835387)
        self.assertAlmostEqual(space_cool_demand, 0)
        self.assertAlmostEqual(ach_cooling, 0.14)
        self.assertAlmostEqual(ach_to_trigger_heating, 0.14)

        space_heat_demand, space_cool_demand, ach_cooling, ach_to_trigger_heating = (
            self.zone.space_heat_cool_demand(
                delta_t_h=0.5,
                temp_ext_air=2.8,
                gains_internal=13.5,
                gains_solar=9.1,
                frac_convective_heat=0.4,
                frac_convective_cool=0.95,
                temp_setpnt_heat=16.0,
                temp_setpnt_cool=24.0,
                avg_air_supply_temp=2.8,
                gains_heat_cool_convective=0.0,
                gains_heat_cool_radiative=0.0,
                ach_windows_open=0.17,
                ach_target=0.14,
                ach_cooling=None,
            )
        )

        self.assertAlmostEqual(space_heat_demand, 0)
        self.assertAlmostEqual(space_cool_demand, 0)
        self.assertAlmostEqual(ach_cooling, 0.14)
        self.assertAlmostEqual(ach_to_trigger_heating, 0.17)

        space_heat_demand, space_cool_demand, ach_cooling, ach_to_trigger_heating = (
            self.zone.space_heat_cool_demand(
                delta_t_h=0.5,
                temp_ext_air=2.8,
                gains_internal=13.5,
                gains_solar=9.1,
                frac_convective_heat=0.4,
                frac_convective_cool=0.95,
                temp_setpnt_heat=16.0,
                temp_setpnt_cool=16.0,
                avg_air_supply_temp=2.8,
                gains_heat_cool_convective=0.0,
                gains_heat_cool_radiative=0.0,
                ach_windows_open=0.17,
                ach_target=0.14,
                ach_cooling=None,
            )
        )

        self.assertAlmostEqual(space_heat_demand, 0)
        self.assertAlmostEqual(space_cool_demand, -0.3774681469845284)
        self.assertAlmostEqual(ach_cooling, 0.14)
        self.assertAlmostEqual(ach_to_trigger_heating, 0.17)

        self.zone._Zone__temp_setpnt_basis = ZoneTemperatureControlBasis.OPERATIVE  # type: ignore[AttributeAccessIssue]

        space_heat_demand, space_cool_demand, ach_cooling, ach_to_trigger_heating = (
            self.zone.space_heat_cool_demand(
                delta_t_h=0.5,
                temp_ext_air=2.8,
                gains_internal=13.5,
                gains_solar=9.1,
                frac_convective_heat=0.4,
                frac_convective_cool=0.95,
                temp_setpnt_heat=21.0,
                temp_setpnt_cool=24.0,
                avg_air_supply_temp=2.8,
                gains_heat_cool_convective=0.0,
                gains_heat_cool_radiative=0.0,
                ach_windows_open=0.17,
                ach_target=0.14,
                ach_cooling=None,
            )
        )

        self.assertAlmostEqual(space_heat_demand, 3.147608479695715)
        self.assertAlmostEqual(space_cool_demand, 0)
        self.assertAlmostEqual(ach_cooling, 0.14)
        self.assertAlmostEqual(ach_to_trigger_heating, 0.14)

        space_heat_demand, space_cool_demand, ach_cooling, ach_to_trigger_heating = (
            self.zone.space_heat_cool_demand(
                delta_t_h=0.5,
                temp_ext_air=2.8,
                gains_internal=13.5,
                gains_solar=9.1,
                frac_convective_heat=0.4,
                frac_convective_cool=0.95,
                temp_setpnt_heat=24.0,
                temp_setpnt_cool=24.0,
                avg_air_supply_temp=2.8,
                gains_heat_cool_convective=0.0,
                gains_heat_cool_radiative=0.0,
                ach_windows_open=0.17,
                ach_target=0.14,
                ach_cooling=None,
            )
        )

        self.assertAlmostEqual(space_heat_demand, 4.699947718442156)
        self.assertAlmostEqual(space_cool_demand, 0)
        self.assertAlmostEqual(ach_cooling, 0.14)
        self.assertAlmostEqual(ach_to_trigger_heating, 0.14)

        self.zone._Zone__temp_setpnt_basis = ZoneTemperatureControlBasis.AIR  # type: ignore[AttributeAccessIssue]

        with patch.object(
            self.zone, "_Zone__interp_heat_cool_demand"
        ) as mock_interp_heat_cool_demand:
            mock_interp_heat_cool_demand.return_value = -5
            space_heat_demand, space_cool_demand, _, _ = self.zone.space_heat_cool_demand(
                delta_t_h=0.5,
                temp_ext_air=2.8,
                gains_internal=13.5,
                gains_solar=9.1,
                frac_convective_heat=0.4,
                frac_convective_cool=0.95,
                temp_setpnt_heat=21.0,
                temp_setpnt_cool=24.0,
                avg_air_supply_temp=2.8,
                gains_heat_cool_convective=0.0,
                gains_heat_cool_radiative=0.0,
                ach_windows_open=0.17,
                ach_target=0.14,
                ach_cooling=None,
            )

            self.assertAlmostEqual(space_heat_demand, 0)
            self.assertAlmostEqual(space_cool_demand, -5)

            mock_interp_heat_cool_demand.return_value = 0
            space_heat_demand, space_cool_demand, _, _ = self.zone.space_heat_cool_demand(
                delta_t_h=0.5,
                temp_ext_air=2.8,
                gains_internal=13.5,
                gains_solar=9.1,
                frac_convective_heat=0.4,
                frac_convective_cool=0.95,
                temp_setpnt_heat=21.0,
                temp_setpnt_cool=24.0,
                avg_air_supply_temp=2.8,
                gains_heat_cool_convective=0.0,
                gains_heat_cool_radiative=0.0,
                ach_windows_open=0.17,
                ach_target=0.14,
                ach_cooling=None,
            )

            self.assertAlmostEqual(space_heat_demand, 0)
            self.assertAlmostEqual(space_cool_demand, 0)

    def test_space_heat_cool_demand_fast_solver(self):
        """Test that space_heat_cool_demand uses the fast_solver if set"""
        with patch.object(
            self.zone,
            "_Zone__fast_solver",
            wraps=self.zone._Zone__fast_solver,  # type: ignore[AttributeAccessIssue]
        ) as mock_fast_solver:
            self.zone._Zone__use_fast_solver = False  # type: ignore[AttributeAccessIssue]
            self.zone.space_heat_cool_demand(
                delta_t_h=0.5,
                temp_ext_air=2.8,
                gains_internal=13.5,
                gains_solar=9.1,
                frac_convective_heat=0.4,
                frac_convective_cool=0.95,
                temp_setpnt_heat=21.0,
                temp_setpnt_cool=24.0,
                avg_air_supply_temp=2.8,
                gains_heat_cool_convective=0.0,
                gains_heat_cool_radiative=0.0,
                ach_windows_open=0.17,
                ach_target=0.14,
                ach_cooling=None,
            )
            mock_fast_solver.assert_not_called()

            self.zone._Zone__use_fast_solver = True  # type: ignore[AttributeAccessIssue]
            self.zone.space_heat_cool_demand(
                delta_t_h=0.5,
                temp_ext_air=2.8,
                gains_internal=13.5,
                gains_solar=9.1,
                frac_convective_heat=0.4,
                frac_convective_cool=0.95,
                temp_setpnt_heat=21.0,
                temp_setpnt_cool=24.0,
                avg_air_supply_temp=2.8,
                gains_heat_cool_convective=0.0,
                gains_heat_cool_radiative=0.0,
                ach_windows_open=0.17,
                ach_target=0.14,
                ach_cooling=None,
            )
            mock_fast_solver.assert_called()

    def test_zone_with_party_wall(self):
        """Test that Zone correctly handles BuildingElementPartyWall in heat balance calculations"""
        # Get external conditions from one of the existing building elements
        extcond = self.be_objs[0]._external_conditions

        # Create a party wall building element
        be_party_wall = BuildingElementPartyWall(
            area=15.0,
            pitch=90,
            thermal_resistance_construction=0.45,
            party_wall_cavity_type="unfilled_unsealed",
            party_wall_lining_type="dry_lined",
            thermal_resistance_cavity=None,
            areal_heat_capacity=12000.0,
            mass_distribution_class=MassDistributionClass.D,
            ext_cond=extcond,
        )

        # Create a zone WITHOUT the party wall first to get baseline values
        zone_without_party_wall = Zone(
            area=80.0,
            volume=250.0,
            building_elements=[
                self.be_objs[0],  # be_opaque_I
                self.be_objs[1],  # be_opaque_D
                self.be_objs[2],  # be_ZTC
            ],
            thermal_bridging=4.0,
            vent_obj=self.infilvent,
            temp_ext_air_init=self.temp_ext_air_init,
            temp_setpnt_init=self.temp_setpnt_init,
            temp_setpnt_basis=self.temp_setpnt_basis,
            control_obj=None,
            print_heat_balance=True,
        )

        # Create a zone WITH the party wall
        zone_with_party_wall = Zone(
            area=80.0,
            volume=250.0,
            building_elements=[
                self.be_objs[0],  # be_opaque_I
                self.be_objs[1],  # be_opaque_D
                self.be_objs[2],  # be_ZTC
                be_party_wall,  # Party wall
            ],
            thermal_bridging=4.0,
            vent_obj=self.infilvent,
            temp_ext_air_init=self.temp_ext_air_init,
            temp_setpnt_init=self.temp_setpnt_init,
            temp_setpnt_basis=self.temp_setpnt_basis,
            control_obj=None,
            print_heat_balance=True,
        )

        # Run update_temperatures for both zones with the same conditions
        delta_t = 1800
        temp_ext_air = 10
        gains_internal = 200
        gains_solar = 220
        gains_heat_cool = 0
        frac_convective = 1
        ach = 0.4
        avg_supply_temp = 10

        heat_balance_without = zone_without_party_wall.update_temperatures(
            delta_t=delta_t,
            temp_ext_air=temp_ext_air,
            gains_internal=gains_internal,
            gains_solar=gains_solar,
            gains_heat_cool=gains_heat_cool,
            frac_convective=frac_convective,
            ach=ach,
            avg_supply_temp=avg_supply_temp,
        )

        heat_balance_with = zone_with_party_wall.update_temperatures(
            delta_t=delta_t,
            temp_ext_air=temp_ext_air,
            gains_internal=gains_internal,
            gains_solar=gains_solar,
            gains_heat_cool=gains_heat_cool,
            frac_convective=frac_convective,
            ach=ach,
            avg_supply_temp=avg_supply_temp,
        )

        # Verify that both heat balance dictionaries were created successfully
        self.assertIsNotNone(heat_balance_without, "Heat balance dict should not be None")
        self.assertIsNotNone(heat_balance_with, "Heat balance dict should not be None")
        self.assertIn("external_boundary", heat_balance_with)
        self.assertIn("ZTU_fabric_ext", heat_balance_with["external_boundary"])
        self.assertIn("external_boundary", heat_balance_without)
        self.assertIn("ZTU_fabric_ext", heat_balance_without["external_boundary"])

        # The critical test: verify that the party wall actually contributes to the ZTU fabric heat loss
        # The zone with the party wall should have a higher (more positive) ZTU_fabric_ext value
        # because the party wall adds heat loss to the unconditioned space
        ztu_with_party_wall = heat_balance_with["external_boundary"]["ZTU_fabric_ext"]
        ztu_without_party_wall = heat_balance_without["external_boundary"]["ZTU_fabric_ext"]

        self.assertIsInstance(ztu_with_party_wall, float)
        self.assertIsInstance(ztu_without_party_wall, float)

        # The party wall should cause ZTU_fabric_ext to be non-zero and negative (heat loss)
        # Without party wall, ZTU_fabric_ext should be 0.0 (no unconditioned space elements)
        self.assertEqual(
            ztu_without_party_wall, 0.0, "ZTU_fabric_ext should be 0.0 when no party wall present"
        )

        # With party wall, ZTU_fabric_ext should be negative (heat loss to unconditioned space)
        self.assertLess(
            ztu_with_party_wall,
            0.0,
            "ZTU_fabric_ext should be negative (heat loss) when party wall present",
        )

        # The difference should equal the party wall's contribution
        # (more negative value means more heat loss)
        self.assertLess(
            ztu_with_party_wall,
            ztu_without_party_wall,
            "Party wall should increase heat loss to unconditioned spaces",
        )

        # Verify the actual calculated value is reasonable
        self.assertAlmostEqual(
            ztu_with_party_wall,
            -164.2832446432019,
            msg="Party wall ZTU_fabric_ext should be approximately -141.53",
        )
