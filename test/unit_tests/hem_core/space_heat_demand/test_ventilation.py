# Standard library imports
import unittest
from copy import deepcopy
from typing import cast
from unittest.mock import MagicMock, call, patch

# Local imports
from hem_core.controls.time_control import OnOffTimeControl, SetpointTimeControl
from hem_core.ductwork import Ductwork
from hem_core.energy_supply.energy_supply import EnergySupply, EnergySupplyConnection
from hem_core.input_output.enums import (
    CombustionAirSupplySituation,
    CombustionApplianceType,
    CombustionFuelType,
    DuctShape,
    DuctType,
    FlueGasExhaustSituation,
    FuelType,
    MechVentType,
    MVHRLocation,
    SupplyAirFlowRateControlType,
    SupplyAirTemperatureControlType,
    TerrainClass,
    VentilationShieldClass,
)
from hem_core.material_properties import AIR
from hem_core.schedule import expand_schedule
from hem_core.simulation_time import SimulationTime
from hem_core.space_heat_demand.ventilation import (
    CombustionAppliances,
    InfiltrationVentilation,
    Leaks,
    MechanicalVentilation,
    Vent,
    Window,
    WindowPart,
    adjust_air_density_for_altitude,
    air_change_rate_to_flow_rate,
    air_density_at_temp,
    calculate_pressure_difference_at_an_airflow_path,
    convert_mass_flow_rate_to_volume_flow_rate,
    convert_to_mass_air_flow_rate,
    convert_volume_flow_rate_to_mass_flow_rate,
    create_infiltration_ventilation,
    get_appliance_system_factor,
    get_facade_direction,
    get_fuel_flow_factor,
    get_pressure_coefficient,
    get_pressure_coefficient_dict,
    terrain_class_to_roughness_coeff,
    wind_speed_at_zone_level,
)
from hem_core.units import Celcius2Kelvin, Orientation360

# Define constants
p_a_ref = AIR.density_kg_per_m3()
c_a = AIR.specific_heat_capacity_kWh()

# (Default values from BS EN 16798-7, Table 11)
# Coefficient to take into account stack effect in airing calculation in (m/s)/(m*K)
C_stack = 0.0035
# Coefficient to take into account wind speed in airing calculation in 1/(m/s)
C_wnd = 0.001
# Gravitational constant in m/s2
g = 9.81
# Room temperature in degrees K
T_e_ref = 293.15
# Absolute zero in degrees K
T_0_abs = 273.15


class TestFunctions(unittest.TestCase):
    def test_calculate_pressure_difference_at_an_airflow_path(self):
        h_path = 0.4
        C_p_path = 0.45
        u_site = 1
        T_e = 294.95
        T_z = 299.15
        p_z_ref = 2.5
        result = calculate_pressure_difference_at_an_airflow_path(
            h_path=h_path, C_p_path=C_p_path, u_site=u_site, T_e=T_e, T_z=T_z, p_z_ref=p_z_ref
        )
        self.assertAlmostEqual(result, -2.2966793114)  # Use spreadsheet to find answer.

    def test_air_change_rate_to_flow_rate(self):
        """Test that air_change_rate_to_flow_rate returns the correct values"""
        self.assertAlmostEqual(
            air_change_rate_to_flow_rate(air_change_rate=3600, zone_volume=1), 1.0
        )
        self.assertAlmostEqual(
            air_change_rate_to_flow_rate(air_change_rate=120, zone_volume=20), 0.6666666666666666
        )

    def test_wind_speed_at_zone_level(self):
        C_rgh_site = 0.8
        u_10 = 10
        result = wind_speed_at_zone_level(C_rgh_site=C_rgh_site, u_10=u_10)
        self.assertAlmostEqual(result, 8)

    def test_get_fuel_flow_factor(self):
        self.assertEqual(
            get_fuel_flow_factor(
                fuel_type=CombustionFuelType.WOOD,
                appliance_type=CombustionApplianceType.OPEN_FIREPLACE,
            ),
            2.8,
        )
        self.assertEqual(
            get_fuel_flow_factor(
                fuel_type=CombustionFuelType.GAS,
                appliance_type=CombustionApplianceType.CLOSED_WITH_FAN,
            ),
            0.38,
        )
        self.assertEqual(
            get_fuel_flow_factor(
                fuel_type=CombustionFuelType.GAS,
                appliance_type=CombustionApplianceType.OPEN_GAS_FLUE_BALANCER,
            ),
            0.78,
        )
        self.assertEqual(
            get_fuel_flow_factor(
                fuel_type=CombustionFuelType.GAS,
                appliance_type=CombustionApplianceType.OPEN_GAS_KITCHEN_STOVE,
            ),
            3.35,
        )
        self.assertEqual(
            get_fuel_flow_factor(
                fuel_type=CombustionFuelType.GAS,
                appliance_type=CombustionApplianceType.OPEN_GAS_FIRE,
            ),
            3.35,
        )
        self.assertEqual(
            get_fuel_flow_factor(
                fuel_type=CombustionFuelType.OIL, appliance_type=CombustionApplianceType.CLOSED_FIRE
            ),
            0.32,
        )
        self.assertEqual(
            get_fuel_flow_factor(
                fuel_type=CombustionFuelType.COAL,
                appliance_type=CombustionApplianceType.CLOSED_FIRE,
            ),
            0.52,
        )

        with self.assertRaises(ValueError):
            get_fuel_flow_factor(CombustionFuelType.WOOD, CombustionApplianceType.OPEN_GAS_FIRE)

        with self.assertRaises(ValueError):
            get_fuel_flow_factor(CombustionFuelType.OIL, CombustionApplianceType.OPEN_GAS_FIRE)

        with self.assertRaises(ValueError):
            get_fuel_flow_factor(CombustionFuelType.COAL, CombustionApplianceType.OPEN_GAS_FIRE)

        with self.assertRaises(ValueError):
            get_fuel_flow_factor(CombustionFuelType.GAS, CombustionApplianceType.CLOSED_FIRE)

    def test_get_appliance_system_factor(self):
        self.assertEqual(
            get_appliance_system_factor(
                supply_situation=CombustionAirSupplySituation.OUTSIDE,
                exhaust_situation=FlueGasExhaustSituation.INTO_ROOM,
            ),
            0,
        )
        self.assertEqual(
            get_appliance_system_factor(
                supply_situation=CombustionAirSupplySituation.ROOM_AIR,
                exhaust_situation=FlueGasExhaustSituation.INTO_ROOM,
            ),
            0,
        )
        self.assertEqual(
            get_appliance_system_factor(
                supply_situation=CombustionAirSupplySituation.ROOM_AIR,
                exhaust_situation=FlueGasExhaustSituation.INTO_SEPARATE_DUCT,
            ),
            1,
        )

        with self.assertRaises(ValueError):
            get_appliance_system_factor(
                supply_situation=CombustionAirSupplySituation.ROOM_AIR,
                exhaust_situation=FlueGasExhaustSituation.INTO_MECH_VENT,
            )

    def test_adjust_air_density_for_altitude(self):
        h_alt = 10  # meters
        expected = 1.2028621569154314  # Pa
        result = adjust_air_density_for_altitude(altitude=h_alt)
        self.assertAlmostEqual(result, expected)

    def test_air_density_at_temp(self):
        temperature = 300  # K
        air_density_adjusted_for_alt = 1.2  # kg/m^3
        expected = 1.1725999999999999  # kg/m^3
        result = air_density_at_temp(
            temperature=temperature, air_density_adjusted_for_alt=air_density_adjusted_for_alt
        )
        self.assertAlmostEqual(result, expected)

    def test_convert_volume_flow_rate_to_mass_flow_rate(self):
        qv = 1000  # m^3/h
        temperature = 300  # K
        p_a_alt = p_a_ref
        expected = 1176.5086666666666  # kg/h
        result = convert_volume_flow_rate_to_mass_flow_rate(
            qv=qv, temperature=temperature, p_a_alt=p_a_alt
        )
        self.assertAlmostEqual(result, expected)

    def test_convert_mass_flow_rate_to_volume_flow_rate(self):
        qm = 1200  # kg/h
        temperature = 300  # K
        p_a_alt = p_a_ref
        expected = 1019.9669870685186  # m^3/h
        result = convert_mass_flow_rate_to_volume_flow_rate(
            qm=qm, temperature=temperature, p_a_alt=p_a_alt
        )
        self.assertAlmostEqual(result, expected)

    def test_convert_to_mass_air_flow_rate(self):
        qv_in = 30  # m^3/h
        qv_out = 40  # m^3/h
        T_e = 300  # K
        T_z = 295  # K
        p_a_alt = p_a_ref
        expected_qm_in = 35.29526  # kg/h
        expected_qm_out = 47.85797966101694  # kg/h
        qm_in, qm_out = convert_to_mass_air_flow_rate(
            qv_in=qv_in, qv_out=qv_out, T_e=T_e, T_z=T_z, p_a_alt=p_a_alt
        )
        self.assertAlmostEqual(qm_in, expected_qm_in)
        self.assertAlmostEqual(qm_out, expected_qm_out)

    def test_ter_class_to_roughness_coeff(self):
        """Test converting terrain class to roughness coefficient."""
        z = 2.5

        self.assertAlmostEqual(
            terrain_class_to_roughness_coeff(terrain_class=TerrainClass.OPEN_WATER, z=z),
            0.9386483560365819,
        )
        self.assertAlmostEqual(
            terrain_class_to_roughness_coeff(terrain_class=TerrainClass.OPEN_FIELD, z=z),
            0.8325850605880374,
        )
        self.assertAlmostEqual(
            terrain_class_to_roughness_coeff(terrain_class=TerrainClass.SUBURBAN, z=z),
            0.7223511561212699,
        )
        self.assertAlmostEqual(
            terrain_class_to_roughness_coeff(terrain_class=TerrainClass.URBAN, z=z),
            0.6654212933375474,
        )

    def test_orientation_difference(self):
        # Test simple cases
        self.assertEqual(
            Orientation360.orientation_difference(
                orientation1=Orientation360(0), orientation2=Orientation360(90)
            ),
            90,
        )
        self.assertEqual(
            Orientation360.orientation_difference(
                orientation1=Orientation360(100), orientation2=Orientation360(90)
            ),
            10,
        )
        # Test cases where shortest angle crosses North
        self.assertEqual(
            Orientation360.orientation_difference(
                orientation1=Orientation360(0), orientation2=Orientation360(310)
            ),
            50,
        )
        self.assertEqual(
            Orientation360.orientation_difference(
                orientation1=Orientation360(300), orientation2=Orientation360(10)
            ),
            70,
        )

    def test_get_facade_direction(self):
        self.assertEqual(
            get_facade_direction(
                f_cross=True,
                orientation=Orientation360(0),
                pitch=5,
                wind_direction=Orientation360(0),
            ),
            "Roof10",
        )
        self.assertEqual(
            get_facade_direction(
                f_cross=True,
                orientation=Orientation360(0),
                pitch=20,
                wind_direction=Orientation360(0),
            ),
            "Roof10_30",
        )
        self.assertEqual(
            get_facade_direction(
                f_cross=True,
                orientation=Orientation360(0),
                pitch=45,
                wind_direction=Orientation360(0),
            ),
            "Roof30",
        )
        self.assertEqual(
            get_facade_direction(
                f_cross=True,
                orientation=Orientation360(0),
                pitch=70,
                wind_direction=Orientation360(0),
            ),
            "wind_seg1",
        )
        self.assertEqual(
            get_facade_direction(
                f_cross=True,
                orientation=Orientation360(60),
                pitch=70,
                wind_direction=Orientation360(0),
            ),
            "wind_seg2",
        )
        self.assertEqual(
            get_facade_direction(
                f_cross=True,
                orientation=Orientation360(90),
                pitch=70,
                wind_direction=Orientation360(0),
            ),
            "wind_seg3",
        )
        self.assertEqual(
            get_facade_direction(
                f_cross=True,
                orientation=Orientation360(140),
                pitch=70,
                wind_direction=Orientation360(0),
            ),
            "wind_seg4",
        )
        self.assertEqual(
            get_facade_direction(
                f_cross=True,
                orientation=Orientation360(160),
                pitch=70,
                wind_direction=Orientation360(0),
            ),
            "wind_seg5",
        )
        self.assertEqual(
            get_facade_direction(
                f_cross=True,
                orientation=Orientation360(0),
                pitch=70,
                wind_direction=Orientation360(0),
            ),
            "wind_seg1",
        )
        self.assertEqual(
            get_facade_direction(
                f_cross=True,
                orientation=Orientation360(60),
                pitch=70,
                wind_direction=Orientation360(0),
            ),
            "wind_seg2",
        )
        self.assertEqual(
            get_facade_direction(
                f_cross=True,
                orientation=Orientation360(90),
                pitch=70,
                wind_direction=Orientation360(0),
            ),
            "wind_seg3",
        )
        self.assertEqual(
            get_facade_direction(
                f_cross=True,
                orientation=Orientation360(140),
                pitch=70,
                wind_direction=Orientation360(0),
            ),
            "wind_seg4",
        )
        self.assertEqual(
            get_facade_direction(
                f_cross=True,
                orientation=Orientation360(160),
                pitch=70,
                wind_direction=Orientation360(0),
            ),
            "wind_seg5",
        )
        self.assertEqual(
            get_facade_direction(
                f_cross=False,
                orientation=Orientation360(0),
                pitch=45,
                wind_direction=Orientation360(0),
            ),
            "Roof",
        )
        self.assertEqual(
            get_facade_direction(
                f_cross=False,
                orientation=Orientation360(0),
                pitch=70,
                wind_direction=Orientation360(0),
            ),
            "wind_seg1",
        )
        self.assertEqual(
            get_facade_direction(
                f_cross=False,
                orientation=Orientation360(60),
                pitch=70,
                wind_direction=Orientation360(0),
            ),
            "wind_seg2",
        )
        self.assertEqual(
            get_facade_direction(
                f_cross=False,
                orientation=Orientation360(90),
                pitch=70,
                wind_direction=Orientation360(0),
            ),
            "wind_seg3",
        )
        self.assertEqual(
            get_facade_direction(
                f_cross=False,
                orientation=Orientation360(140),
                pitch=70,
                wind_direction=Orientation360(0),
            ),
            "wind_seg4",
        )
        self.assertEqual(
            get_facade_direction(
                f_cross=False,
                orientation=Orientation360(160),
                pitch=70,
                wind_direction=Orientation360(0),
            ),
            "wind_seg5",
        )

    def test_get_pressure_coefficient(self):
        """Test that get_pressure_coefficient returns the correct value or raise a ValueError based on different combinations of arguments"""
        self.assertAlmostEqual(
            get_pressure_coefficient(
                f_cross=True,
                shield_class=VentilationShieldClass.OPEN,
                z=10,
                wind_direction=Orientation360(0),
                orientation=Orientation360(0),
                pitch=70,
            ),
            0.70,
        )
        self.assertAlmostEqual(
            get_pressure_coefficient(
                f_cross=True,
                shield_class=VentilationShieldClass.NORMAL,
                z=10,
                wind_direction=Orientation360(0),
                orientation=Orientation360(45),
                pitch=70,
            ),
            0.1,
        )
        self.assertAlmostEqual(
            get_pressure_coefficient(
                f_cross=True,
                shield_class=VentilationShieldClass.SHIELDED,
                z=10,
                wind_direction=Orientation360(0),
                orientation=Orientation360(90),
                pitch=70,
            ),
            -0.25,
        )
        self.assertAlmostEqual(
            get_pressure_coefficient(
                f_cross=True,
                shield_class=VentilationShieldClass.OPEN,
                z=30,
                wind_direction=Orientation360(0),
                orientation=Orientation360(135),
                pitch=70,
            ),
            -0.47,
        )
        self.assertAlmostEqual(
            get_pressure_coefficient(
                f_cross=True,
                shield_class=VentilationShieldClass.NORMAL,
                z=30,
                wind_direction=Orientation360(0),
                orientation=Orientation360(180),
                pitch=70,
            ),
            -0.34,
        )
        self.assertAlmostEqual(
            get_pressure_coefficient(
                f_cross=True,
                shield_class=VentilationShieldClass.SHIELDED,
                z=30,
                wind_direction=Orientation360(0),
                orientation=Orientation360(0),
                pitch=70,
            ),
            0.49,
        )
        self.assertAlmostEqual(
            get_pressure_coefficient(
                f_cross=True,
                shield_class=VentilationShieldClass.OPEN,
                z=60,
                wind_direction=Orientation360(0),
                orientation=Orientation360(0),
                pitch=70,
            ),
            0.49,
        )
        self.assertAlmostEqual(
            get_pressure_coefficient(
                f_cross=True,
                shield_class=VentilationShieldClass.NORMAL,
                z=30,
                wind_direction=Orientation360(90),
                orientation=Orientation360(0),
                pitch=70,
            ),
            -0.61,
        )
        self.assertAlmostEqual(
            get_pressure_coefficient(
                f_cross=False,
                shield_class=VentilationShieldClass.NORMAL,
                z=10,
                wind_direction=Orientation360(0),
                orientation=Orientation360(0),
                pitch=70,
            ),
            0.05,
        )
        self.assertAlmostEqual(
            get_pressure_coefficient(
                f_cross=False,
                shield_class=VentilationShieldClass.NORMAL,
                z=10,
                wind_direction=Orientation360(0),
                orientation=Orientation360(0),
                pitch=45,
            ),
            0.00,
        )
        self.assertAlmostEqual(
            get_pressure_coefficient(
                f_cross=False,
                shield_class=VentilationShieldClass.NORMAL,
                z=15,
                wind_direction=Orientation360(270),
                orientation=Orientation360(10),
                pitch=90,
            ),
            -0.05,
        )

        with self.assertRaises(ValueError):
            get_pressure_coefficient(
                f_cross=True,
                shield_class=VentilationShieldClass.NORMAL,
                z=10,
                wind_direction=Orientation360(0),
            )

        with self.assertRaises(ValueError):
            get_pressure_coefficient(
                f_cross=True,
                shield_class=VentilationShieldClass.NORMAL,
                z=51,
                wind_direction=Orientation360(0),
            )

    def test_get_pressure_coefficient_dict(self):
        """Test that get_pressure_coefficient raises a ValueError if z is over 50 for any VentilationShieldClass other than OPEN"""
        with self.assertRaises(ValueError):
            get_pressure_coefficient_dict(z=51, shield_class=VentilationShieldClass.SHIELDED)

    def test_create_infiltration_ventilation(self):
        """Test that create_infiltration_ventilation creates an InfiltrationVentilation object"""
        simtime = SimulationTime(start_time=0, end_time=4, step=1)
        infiltration_ventilation_dict = {
            "cross_vent_possible": True,
            "shield_class": "Normal",
            "terrain_class": "OpenField",
            "ventilation_zone_base_height": 2.5,
            "altitude": 30,
            "Vents": {
                "vent1": {
                    "mid_height_air_flow_path": 1.5,
                    "area_cm2": 100,
                    "pressure_difference_ref": 20,
                    "orientation360": 180,
                    "pitch": 60,
                }
            },
            "Leaks": {
                "ventilation_zone_height": 6,
                "test_pressure": 50,
                "test_result": 1.2,
                "env_area": 220,
            },
            "CombustionAppliances": {
                "Fireplace": {
                    "supply_situation": "room_air",
                    "exhaust_situation": "into_separate_duct",
                    "fuel_type": "wood",
                    "appliance_type": "open_fireplace",
                }
            },
            "MechanicalVentilation": {
                "mechvent1": {
                    "sup_air_flw_ctrl": "ODA",
                    "sup_air_temp_ctrl": "NO_CTRL",
                    "vent_type": "Centralised continuous MEV",
                    "SFP": 1.5,
                    "EnergySupply": "mains elec",
                    "design_outdoor_air_flow_rate": 80,
                    "orientation360": 180,
                    "pitch": 90,
                    "mid_height_air_flow_path": 2,
                    "Control": "min_temp",
                },
                "mechvent2": {
                    "sup_air_flw_ctrl": "ODA",
                    "sup_air_temp_ctrl": "NO_CTRL",
                    "vent_type": "MVHR",
                    "mvhr_eff": 0.80,
                    "SFP": 1.5,
                    "EnergySupply": "mains elec",
                    "design_outdoor_air_flow_rate": 80,
                    "position_intake": {
                        "orientation360": 180,
                        "pitch": 90,
                        "mid_height_air_flow_path": 3.0,
                    },
                    "position_exhaust": {
                        "orientation360": 0,
                        "pitch": 90,
                        "mid_height_air_flow_path": 2.0,
                    },
                    "mvhr_location": "outside",
                    "ductwork": [
                        {
                            "cross_section_shape": "circular",
                            "internal_diameter_mm": 200,
                            "external_diameter_mm": 300,
                            "length": 10.0,
                            "insulation_thermal_conductivity": 0.023,
                            "insulation_thickness_mm": 100,
                            "reflective": False,
                            "duct_type": "supply",
                        },
                        {
                            "cross_section_shape": "rectangular",
                            "duct_perimeter_mm": 300,
                            "length": 10.0,
                            "insulation_thermal_conductivity": 0.023,
                            "insulation_thickness_mm": 100,
                            "reflective": False,
                            "duct_type": "extract",
                        },
                        {
                            "cross_section_shape": "circular",
                            "internal_diameter_mm": 200,
                            "external_diameter_mm": 300,
                            "length": 10.0,
                            "insulation_thermal_conductivity": 0.023,
                            "insulation_thickness_mm": 100,
                            "reflective": False,
                            "duct_type": "intake",
                        },
                        {
                            "cross_section_shape": "circular",
                            "internal_diameter_mm": 200,
                            "external_diameter_mm": 300,
                            "length": 10.0,
                            "insulation_thermal_conductivity": 0.023,
                            "insulation_thickness_mm": 100,
                            "reflective": False,
                            "duct_type": "exhaust",
                        },
                    ],
                },
            },
        }
        zones_dict = {
            "zone 1": {
                "SpaceHeatSystem": "zone 1 radiators",
                "area": 80.0,
                "volume": 250.0,
                "temp_setpnt_init": 21.0,
                "BuildingElement": {
                    "wall 0": {
                        "type": "BuildingElementOpaque",
                        "solar_absorption_coeff": 0.6,
                        "thermal_resistance_construction": 0.7,
                        "areal_heat_capacity": 19000,
                        "mass_distribution_class": "IE",
                        "pitch": 90,
                        "orientation360": 90,
                        "base_height": 0,
                        "height": 2.5,
                        "width": 10,
                        "area": 20.0,
                    },
                    "wall 1": {
                        "type": "BuildingElementOpaque",
                        "solar_absorption_coeff": 0.62,
                        "thermal_resistance_construction": 0.72,
                        "areal_heat_capacity": 19200,
                        "mass_distribution_class": "E",
                        "pitch": 50,
                        "orientation360": 0,
                        "base_height": 0,
                        "height": 2.5,
                        "width": 8,
                        "area": 20.0,
                    },
                    "wall 2": {
                        "type": "BuildingElementOpaque",
                        "solar_absorption_coeff": 0.62,
                        "thermal_resistance_construction": 0.72,
                        "areal_heat_capacity": 19200,
                        "mass_distribution_class": "E",
                        "pitch": 40,
                        "orientation360": 0,
                        "base_height": 0,
                        "height": 2.5,
                        "width": 8,
                        "area": 20.0,
                    },
                    "window 0": {
                        "type": "BuildingElementTransparent",
                        "Control_WindowOpenable": "_window_opening_closedsleeping",
                        "thermal_resistance_construction": 0.4,
                        "pitch": 90,
                        "orientation360": 90,
                        "g_value": 0.75,
                        "frame_area_fraction": 0.25,
                        "base_height": 1,
                        "height": 1.25,
                        "width": 4,
                        "free_area_height": 1.6,
                        "mid_height": 1.5,
                        "max_window_open_area": 3,
                        "window_part_list": [{"mid_height_air_flow_path": 1.5}],
                        "shading": [
                            {"type": "overhang", "depth": 0.5, "distance": 0.5},
                            {"type": "sidefinleft", "depth": 0.25, "distance": 0.1},
                            {"type": "sidefinright", "depth": 0.25, "distance": 0.1},
                        ],
                    },
                    "Window 1": {
                        "type": "BuildingElementTransparent",
                        "Control_WindowOpenable": "_window_opening_closedsleeping",
                        "thermal_resistance_construction": 0.4,
                        "pitch": 50,
                        "orientation360": 90,
                        "g_value": 0.75,
                        "frame_area_fraction": 0.25,
                        "base_height": 1,
                        "height": 1.25,
                        "width": 4,
                        "free_area_height": 1.6,
                        "mid_height": 1.5,
                        "max_window_open_area": 3,
                        "window_part_list": [],
                    },
                },
            }
        }
        detailed_output_heating_cooling = True
        energy_supplies = {
            "mains elec": EnergySupply(fuel_type=FuelType.ELECTRICITY, simulation_time=simtime)
        }
        control1 = MagicMock(spec=SetpointTimeControl)
        control2 = MagicMock(spec=OnOffTimeControl)
        controls: dict[str, SetpointTimeControl | OnOffTimeControl] = {
            "min_temp": control1,
            "_window_opening_closedsleeping": control2,
        }
        infiltration_ventilation = create_infiltration_ventilation(
            infiltration_ventilation_dict=infiltration_ventilation_dict,
            zones_dict=zones_dict,
            simulation_time=simtime,
            detailed_output_heating_cooling=detailed_output_heating_cooling,
            energy_supplies=energy_supplies,
            controls=controls,
        )

        self.assertEqual(
            infiltration_ventilation._InfiltrationVentilation__simulation_time,  # type: ignore[AttributeAccessIssue]
            simtime,
        )
        self.assertEqual(infiltration_ventilation._InfiltrationVentilation__f_cross, True)  # type: ignore[AttributeAccessIssue]
        self.assertEqual(infiltration_ventilation._InfiltrationVentilation__shield_class, "Normal")  # type: ignore[AttributeAccessIssue]
        self.assertEqual(
            infiltration_ventilation._InfiltrationVentilation__ventilation_zone_base_height,  # type: ignore[AttributeAccessIssue]
            2.5,
        )
        self.assertEqual(infiltration_ventilation.ventilation_zone_height, 6)
        self.assertAlmostEqual(
            infiltration_ventilation._InfiltrationVentilation__C_rgh_site,  # type: ignore[AttributeAccessIssue]
            0.8930912695005592,
        )
        self.assertEqual(infiltration_ventilation._InfiltrationVentilation__ATDs, [])  # type: ignore[AttributeAccessIssue]
        self.assertEqual(
            infiltration_ventilation._InfiltrationVentilation__detailed_output_heating_cooling,  # type: ignore[AttributeAccessIssue]
            True,
        )
        self.assertEqual(
            infiltration_ventilation._InfiltrationVentilation__ventilation_detailed_results,  # type: ignore[AttributeAccessIssue]
            [],
        )
        self.assertAlmostEqual(
            infiltration_ventilation._InfiltrationVentilation__p_a_alt,  # type: ignore[AttributeAccessIssue]
            1.200588938687906,
        )
        self.assertEqual(infiltration_ventilation.total_volume, 250.0)
        self.assertEqual(
            len(infiltration_ventilation._InfiltrationVentilation__combustion_appliances),  # type: ignore[AttributeAccessIssue]
            1,
        )
        self.assertEqual(len(infiltration_ventilation._InfiltrationVentilation__windows), 2)  # type: ignore[AttributeAccessIssue]
        self.assertEqual(len(infiltration_ventilation._InfiltrationVentilation__vents), 1)  # type: ignore[AttributeAccessIssue]
        self.assertEqual(len(infiltration_ventilation._InfiltrationVentilation__leaks), 5)  # type: ignore[AttributeAccessIssue]
        self.assertEqual(len(infiltration_ventilation._InfiltrationVentilation__mech_vents), 2)  # type: ignore[AttributeAccessIssue]

        self.assertEqual(
            [
                leak._Leaks__A_roof
                for leak in infiltration_ventilation._InfiltrationVentilation__leaks  # type: ignore[AttributeAccessIssue]
            ],
            [45.0, 45.0, 45.0, 45.0, 45.0],
        )
        self.assertEqual(
            [
                leak._Leaks__A_facades
                for leak in infiltration_ventilation._InfiltrationVentilation__leaks  # type: ignore[AttributeAccessIssue]
            ],
            [25.0, 25.0, 25.0, 25.0, 25.0],
        )

        self.assertEqual(
            [
                vent._MechanicalVentilation__ctrl_intermittent_MEV
                for vent in infiltration_ventilation._InfiltrationVentilation__mech_vents  # type: ignore[AttributeAccessIssue]
            ],
            [control1, None],
        )

        # Test removing window controls
        self.assertNotEqual(
            infiltration_ventilation._InfiltrationVentilation__windows[0]._Window__on_off_ctrl_obj,  # type: ignore[AttributeAccessIssue]
            None,
        )

        zones_dict_copy = deepcopy(zones_dict)
        del zones_dict_copy["zone 1"]["BuildingElement"]["window 0"]["Control_WindowOpenable"]

        energy_supplies = {
            "mains elec": EnergySupply(fuel_type=FuelType.ELECTRICITY, simulation_time=simtime)
        }
        infiltration_ventilation = create_infiltration_ventilation(
            infiltration_ventilation_dict=infiltration_ventilation_dict,
            zones_dict=zones_dict_copy,
            simulation_time=simtime,
            detailed_output_heating_cooling=detailed_output_heating_cooling,
            energy_supplies=energy_supplies,
            controls=controls,
        )

        self.assertEqual(
            infiltration_ventilation._InfiltrationVentilation__windows[0]._Window__on_off_ctrl_obj,  # type: ignore[AttributeAccessIssue]
            None,
        )

        # Test without walls
        self.assertEqual(
            infiltration_ventilation._InfiltrationVentilation__leaks[4]._Leaks__facade_direction,  # type: ignore[AttributeAccessIssue]
            "Roof30",
        )

        zones_dict_copy = deepcopy(zones_dict)
        del zones_dict_copy["zone 1"]["BuildingElement"]["wall 1"]
        del zones_dict_copy["zone 1"]["BuildingElement"]["wall 2"]

        energy_supplies = {
            "mains elec": EnergySupply(fuel_type=FuelType.ELECTRICITY, simulation_time=simtime)
        }
        infiltration_ventilation = create_infiltration_ventilation(
            infiltration_ventilation_dict=infiltration_ventilation_dict,
            zones_dict=zones_dict_copy,
            simulation_time=simtime,
            detailed_output_heating_cooling=detailed_output_heating_cooling,
            energy_supplies=energy_supplies,
            controls=controls,
        )

        self.assertEqual(
            infiltration_ventilation._InfiltrationVentilation__leaks[4]._Leaks__facade_direction,  # type: ignore[AttributeAccessIssue]
            "Roof10",
        )

        # Test without combustion appliances
        infiltration_ventilation_dict_copy = deepcopy(infiltration_ventilation_dict)
        del infiltration_ventilation_dict_copy["CombustionAppliances"]

        energy_supplies = {
            "mains elec": EnergySupply(fuel_type=FuelType.ELECTRICITY, simulation_time=simtime)
        }
        infiltration_ventilation = create_infiltration_ventilation(
            infiltration_ventilation_dict=infiltration_ventilation_dict_copy,
            zones_dict=zones_dict,
            simulation_time=simtime,
            detailed_output_heating_cooling=detailed_output_heating_cooling,
            energy_supplies=energy_supplies,
            controls=controls,
        )

        self.assertEqual(
            len(infiltration_ventilation._InfiltrationVentilation__combustion_appliances),  # type: ignore[AttributeAccessIssue]
            0,
        )

        # Test invalid mechanical ventilation
        infiltration_ventilation_dict_copy = deepcopy(infiltration_ventilation_dict)
        infiltration_ventilation_dict_copy["MechanicalVentilation"]["mechvent2"]["vent_type"] = (
            "invalid"
        )
        energy_supplies = {
            "mains elec": EnergySupply(fuel_type=FuelType.ELECTRICITY, simulation_time=simtime)
        }
        with self.assertRaises(ValueError):
            create_infiltration_ventilation(
                infiltration_ventilation_dict=infiltration_ventilation_dict_copy,
                zones_dict=zones_dict,
                simulation_time=simtime,
                detailed_output_heating_cooling=detailed_output_heating_cooling,
                energy_supplies=energy_supplies,
                controls=controls,
            )

        # Test with invalid duct shape
        infiltration_ventilation_dict_copy = deepcopy(infiltration_ventilation_dict)
        infiltration_ventilation_dict_copy["MechanicalVentilation"]["mechvent2"]["ductwork"][0][
            "cross_section_shape"
        ] = "invalid"
        energy_supplies = {
            "mains elec": EnergySupply(fuel_type=FuelType.ELECTRICITY, simulation_time=simtime)
        }
        with self.assertRaises(ValueError):
            create_infiltration_ventilation(
                infiltration_ventilation_dict=infiltration_ventilation_dict_copy,
                zones_dict=zones_dict,
                simulation_time=simtime,
                detailed_output_heating_cooling=detailed_output_heating_cooling,
                energy_supplies=energy_supplies,
                controls=controls,
            )


# TODO Re-implement ATDs
# class TestAirTerminalDevices(unittest.TestCase):
#     def test_calculate_flow_coeff_for_ATD(self):
#         """ Test that calculate_flow_coeff_for_ATD returns the correct values """
#         self.assertAlmostEqual(AirTerminalDevices(0.5, 10).calculate_flow_coeff_for_ATD(),
#             0.13919560080114612)
#         self.assertAlmostEqual(AirTerminalDevices(0.9, 5).calculate_flow_coeff_for_ATD(),
#             0.250552081442063)
#
#     def test_calculate_pressure_difference_atd(self):
#         """ Test that calculate_pressure_difference_atd returns the correct values """
#         self.assertAlmostEqual(AirTerminalDevices(0.5, 10).calculate_pressure_difference_atd(10),
#             -5161.179698216733)
#         self.assertAlmostEqual(AirTerminalDevices(0.9, 5).calculate_pressure_difference_atd(20),
#             -6371.826787921896)


class TestWindow(unittest.TestCase):
    def setUp(self):
        self.simtime = SimulationTime(start_time=0, end_time=2, step=1)
        self.windspeed = [3.7, 3.8, 3.9, 4.0, 4.1, 4.2, 4.3, 4.4]
        self.wind_direction = [200, 220, 230, 240, 250, 260, 260, 270]
        self.airtemp = [0.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 20.0]
        self.diffuse_horizontal_radiation = [333, 610, 572, 420, 0, 10, 90, 275]
        self.direct_beam_radiation = [420, 750, 425, 500, 0, 40, 0, 388]
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
            {"number": 1, "start": 180, "end": 135},
            {"number": 2, "start": 135, "end": 90},
            {"number": 3, "start": 90, "end": 45},
            {"number": 4, "start": 45, "end": 0},
            {"number": 5, "start": 0, "end": -45},
            {"number": 6, "start": -45, "end": -90},
            {"number": 7, "start": -90, "end": -135},
            {"number": 8, "start": -135, "end": -180},
        ]

        sched = expand_schedule(
            sched_type=bool,
            sched_dict={"main": [{"repeat": 8760, "value": True}]},
            sched_main="main",
            nullable=False,
        )
        sched = [cast(bool, v) for v in sched]
        OnOffTimeControl(
            schedule=sched, simulation_time=self.simtime, start_day=0, time_series_step=1
        )

        window_part_list = [{"mid_height_air_flow_path": 1.5}]
        self.__window = Window(
            free_area_height=1.6,
            midheight=1.5,
            max_opening_area=3,
            window_part_list=window_part_list,
            orientation=Orientation360(0),
            pitch=90,
            altitude=0,
            on_off_ctrl_obj=None,
            ventilation_zone_base_height=0,
        )

    def test_calculate_window_opening_free_area_no_ctrl(self):
        """Test that calculate_window_opening_free_area returns 0 with no control"""
        self.__window._Window__on_off_ctrl_obj = None  # type: ignore[AttributeAccessIssue]
        self.assertEqual(self.__window.calculate_window_opening_free_area(R_w_arg=0.5), 0)

    def test_calculate_window_opening_free_area_ctrl_off(self):
        mock_ctrl = MagicMock()
        mock_ctrl.is_on.return_value = False
        self.__window._Window__on_off_ctrl_obj = mock_ctrl  # type: ignore[AttributeAccessIssue]
        self.assertEqual(self.__window.calculate_window_opening_free_area(R_w_arg=0.5), 0)

    def test_calculate_window_opening_free_area_ctrl_on(self):
        mock_ctrl = MagicMock()
        mock_ctrl.is_on.return_value = True
        self.__window._Window__on_off_ctrl_obj = mock_ctrl  # type: ignore[AttributeAccessIssue]
        self.assertEqual(self.__window.calculate_window_opening_free_area(R_w_arg=0.5), 1.5)

    def test_calculate_flow_coeff_for_window_ctrl_no_ctrl(self):
        """Test that calculate_flow_coeff_for_window returns 0 with no control"""
        self.__window._Window__on_off_ctrl_obj = None  # type: ignore[AttributeAccessIssue]
        self.assertAlmostEqual(self.__window.calculate_flow_coeff_for_window(R_w_arg=0.5), 0)

    def test_calculate_flow_coeff_for_window_ctrl_off(self):
        mock_ctrl = MagicMock()
        mock_ctrl.is_on.return_value = False
        self.__window._Window__on_off_ctrl_obj = mock_ctrl  # type: ignore[AttributeAccessIssue]
        self.assertAlmostEqual(self.__window.calculate_flow_coeff_for_window(R_w_arg=0.5), 0)

    def test_calculate_flow_coeff_for_window_ctrl_on(self):
        mock_ctrl = MagicMock()
        mock_ctrl.is_on.return_value = True
        self.__window._Window__on_off_ctrl_obj = mock_ctrl  # type: ignore[AttributeAccessIssue]
        expected_A_w = 1.5
        expected_flow_coeff = (
            3600
            * self.__window._Window__C_D_w  # type: ignore[AttributeAccessIssue]
            * expected_A_w
            * (2 / p_a_ref) ** self.__window._Window__n_w  # type: ignore[AttributeAccessIssue]
        )
        self.assertAlmostEqual(
            self.__window.calculate_flow_coeff_for_window(R_w_arg=0.5), expected_flow_coeff
        )

    def test_calculate_flow_from_internal_p(self):
        u_site = 5.0
        T_z = 293.15
        p_z_ref = 1
        f_cross = True
        shield_class = VentilationShieldClass.OPEN
        R_w_arg = 0.5
        mock_ctrl = MagicMock()
        mock_ctrl.is_on.return_value = True
        self.__window._Window__on_off_ctrl_obj = mock_ctrl  # type: ignore[AttributeAccessIssue]

        qm_in, qm_out = self.__window.calculate_flow_from_internal_p(
            wind_direction=Orientation360(self.wind_direction[0]),
            u_site=u_site,
            T_e=cast(float, Celcius2Kelvin(self.airtemp[0])),
            T_z=T_z,
            p_z_ref=p_z_ref,
            f_cross=f_cross,
            shield_class=shield_class,
            R_w_arg=R_w_arg,
        )

        """ qm_in returns 0.0 and qm_out returns -13199.752632683054"""
        self.assertAlmostEqual(qm_in, 0)
        self.assertAlmostEqual(qm_out, -13199.752632683054)

    def test_calculate_flow_from_internal_p_no_ctrl(self):
        """Test that calculate_flow_from_internal_p returns 0 with no control"""
        self.__window._Window__on_off_ctrl_obj = None  # type: ignore[AttributeAccessIssue]
        qm_in, qm_out = self.__window.calculate_flow_from_internal_p(
            wind_direction=Orientation360(10),
            u_site=10,
            T_e=290,
            T_z=300,
            p_z_ref=1,
            f_cross=True,
            shield_class=VentilationShieldClass.OPEN,
            R_w_arg=1,
        )
        self.assertAlmostEqual(qm_in, 0)
        self.assertAlmostEqual(qm_out, 0)

    def test_calculate_flow_from_internal_p_ctrl_off(self):
        """Test that calculate_flow_from_internal_p returns 0 if the control is off"""
        mock_ctrl = MagicMock()
        mock_ctrl.is_on.return_value = False
        self.__window._Window__on_off_ctrl_obj = mock_ctrl  # type: ignore[AttributeAccessIssue]
        qm_in, qm_out = self.__window.calculate_flow_from_internal_p(
            wind_direction=Orientation360(10),
            u_site=10,
            T_e=290,
            T_z=300,
            p_z_ref=1,
            f_cross=True,
            shield_class=VentilationShieldClass.OPEN,
            R_w_arg=1,
        )
        self.assertAlmostEqual(qm_in, 0)
        self.assertAlmostEqual(qm_out, 0)


class TestWindowPart(unittest.TestCase):
    def setUp(self):
        # Initialize your WindowPart object here or mock if needed
        self.window_part = WindowPart(
            midheight=1,
            free_area_height=1.6,
            number_window_divisions=0,
            window_part_number=1,
            ventilation_zone_base_height=0,
        )

    def test_calculate_ventilation_through_windows_using_internal_p(self):
        """Function call returns -13235.33116157"""
        u_site = 3.7
        T_e = 273.15
        T_z = 293.15
        C_w_path = 4663.05
        C_p_path = -0.7
        p_z_ref = 1
        expected_output = -13235.33116157
        self.assertAlmostEqual(
            self.window_part.calculate_ventilation_through_windows_using_internal_p(
                u_site=u_site,
                T_e=T_e,
                T_z=T_z,
                C_w_path=C_w_path,
                p_z_ref=p_z_ref,
                C_p_path=C_p_path,
            ),
            expected_output,
        )

    def test_calculate_height_for_delta_p_w_div_path(self):
        """Function returns 1"""
        window_part_number = 1
        expected_output = 1
        self.assertAlmostEqual(
            self.window_part.calculate_height_for_delta_p_w_div_path(j=window_part_number),
            expected_output,
        )


class TestVent(unittest.TestCase):
    def setUp(self):
        # Initialize your Vent object here or mock if needed
        self.simtime = SimulationTime(start_time=0, end_time=2, step=1)
        self.windspeed = [3.7, 3.8, 3.9, 4.0, 4.1, 4.2, 4.3, 4.4]
        self.wind_direction = [200, 220, 230, 240, 250, 260, 260, 270]
        self.airtemp = [0.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 20.0]
        self.diffuse_horizontal_radiation = [333, 610, 572, 420, 0, 10, 90, 275]
        self.direct_beam_radiation = [420, 750, 425, 500, 0, 40, 0, 388]
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
            {"number": 1, "start": 180, "end": 135},
            {"number": 2, "start": 135, "end": 90},
            {"number": 3, "start": 90, "end": 45},
            {"number": 4, "start": 45, "end": 0},
            {"number": 5, "start": 0, "end": -45},
            {"number": 6, "start": -45, "end": -90},
            {"number": 7, "start": -90, "end": -135},
            {"number": 8, "start": -135, "end": -180},
        ]

        self.__vent = Vent(
            midheight=1,
            area=100.0,
            delta_p_vent_ref=20.0,
            orientation=Orientation360(0),
            pitch=90.0,
            altitude=0,
            ventilation_zone_base_height=0,
        )

    def test_calculate_vent_opening_free_area(self):
        """Returns output"""
        R_v_arg = 0.5
        expected_output = 50
        self.assertAlmostEqual(
            self.__vent.calculate_vent_opening_free_area(R_v_arg=R_v_arg), expected_output
        )

    def test_calculate_flow_coeff_for_vent(self):
        """Returns output 27.8391201602292"""
        R_v_arg = 1
        expected_output = 27.8391201602292
        self.assertAlmostEqual(
            self.__vent.calculate_flow_coeff_for_vent(R_v_arg=R_v_arg), expected_output
        )

    def test_calculate_ventilation_through_vents_using_internal_p(self):
        """Returns  -79.01694696980"""

        u_site = 3.7
        T_e = 273.15
        T_z = 293.15
        C_vent_path = 27.8391201602292
        C_p_path = -0.7
        p_z_ref = 1
        expected_output = -79.01694696980

        self.assertAlmostEqual(
            self.__vent.calculate_ventilation_through_vents_using_internal_p(
                u_site=u_site,
                T_e=T_e,
                T_z=T_z,
                C_vent_path=C_vent_path,
                C_p_path=C_p_path,
                p_z_ref=p_z_ref,
            ),
            expected_output,
        )

    def test_calculate_flow_from_internal_p(self):
        u_site = 3.7
        T_z = 293.15
        p_z_ref = 1
        f_cross = True
        shield_class = VentilationShieldClass.OPEN
        R_v_arg = 1

        qm_in_through_vent, qm_out_through_vent = self.__vent.calculate_flow_from_internal_p(
            wind_direction=Orientation360(self.wind_direction[0]),
            u_site=u_site,
            T_e=cast(float, Celcius2Kelvin(self.airtemp[0])),
            T_z=T_z,
            p_z_ref=p_z_ref,
            f_cross=f_cross,
            shield_class=shield_class,
            R_v_arg=R_v_arg,
        )

        """ qm_in_through_vent returns 0.0 and qm_out_through_vent returns  -63.894177841661275"""
        self.assertAlmostEqual(qm_in_through_vent, 0.0)
        self.assertAlmostEqual(qm_out_through_vent, -63.894177841661275)


class TestLeaks(unittest.TestCase):
    def setUp(self):
        self.simtime = SimulationTime(start_time=0, end_time=2, step=1)
        self.windspeed = [3.7, 3.8, 3.9, 4.0, 4.1, 4.2, 4.3, 4.4]
        self.wind_direction = [200, 220, 230, 240, 250, 260, 260, 270]
        self.airtemp = [0.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 20.0]
        self.diffuse_horizontal_radiation = [333, 610, 572, 420, 0, 10, 90, 275]
        self.direct_beam_radiation = [420, 750, 425, 500, 0, 40, 0, 388]
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
            {"number": 1, "start": 180, "end": 135},
            {"number": 2, "start": 135, "end": 90},
            {"number": 3, "start": 90, "end": 45},
            {"number": 4, "start": 45, "end": 0},
            {"number": 5, "start": 0, "end": -45},
            {"number": 6, "start": -45, "end": -90},
            {"number": 7, "start": -90, "end": -135},
            {"number": 8, "start": -135, "end": -180},
        ]

        self.__leaks = Leaks(
            midheight=1,
            delta_p_leak_ref=50.0,
            qv_delta_p_leak_ref=1.2,
            facade_direction="wind_seg4",
            area_roof=100.0,
            area_facades=120.0,
            area_leak=220.0,
            altitude=0,
            ventilation_zone_base_height=0,
        )

    def test_calculate_flow_coeff_for_leak(self):
        """function returns value 2.6490460494125543"""
        expected_result = 2.6490460494125543
        self.assertAlmostEqual(self.__leaks.calculate_flow_coeff_for_leak(), expected_result)

    def test_calculate_ventilation_through_leaks_using_internal_p(self):
        """Returns -10.653145805095907"""
        u_site = 3.7
        T_e = 273.15
        T_z = 293.15
        C_p_path = -0.7
        p_z_ref = 1
        expected_output = -10.653145805095907

        self.assertAlmostEqual(
            self.__leaks.calculate_ventilation_through_leaks_using_internal_p(
                u_site=u_site, T_e=T_e, T_z=T_z, C_p_path=C_p_path, p_z_ref=p_z_ref
            ),
            expected_output,
        )

    def test_calculate_flow_from_internal_p(self):
        """Returns 0.0 for in and -9.825840128169913 for out"""

        u_site = 3.7
        T_z = 293.15
        p_z_ref = 1
        f_cross = True
        shield_class = VentilationShieldClass.OPEN

        qm_in_through_leaks, qm_out_through_leaks = self.__leaks.calculate_flow_from_internal_p(
            wind_direction=Orientation360(self.wind_direction[0]),
            u_site=u_site,
            T_e=cast(float, Celcius2Kelvin(self.airtemp[0])),
            T_z=T_z,
            p_z_ref=p_z_ref,
            f_cross=f_cross,
            shield_class=shield_class,
        )

        self.assertAlmostEqual(qm_in_through_leaks, 0)
        self.assertAlmostEqual(qm_out_through_leaks, -9.825840128169913)


class TestCombustionApplicances(unittest.TestCase):
    def setUp(self):
        self.__combustion_appliances = CombustionAppliances(
            supply_situation=CombustionAirSupplySituation.ROOM_AIR,
            exhaust_situation=FlueGasExhaustSituation.INTO_SEPARATE_DUCT,
            fuel_type=CombustionFuelType.WOOD,
            appliance_type=CombustionApplianceType.OPEN_FIREPLACE,
        )

    def test_calculate_air_flow_req_for_comb_appliance(self):
        """Returns 0.0 for in and -10.08 for out"""
        f_op_comp = 1
        P_h_fi = 1
        q_in_comb, q_out_comb = (
            self.__combustion_appliances.calculate_air_flow_req_for_comb_appliance(
                f_op_comp=f_op_comp, P_h_fi=P_h_fi
            )
        )

        self.assertAlmostEqual(q_in_comb, 0)
        self.assertAlmostEqual(q_out_comb, -10.08)

    def test_calculate_air_flow_req_for_comb_appliance_no_op_comp(self):
        """Test that calculate_air_flow_req_for_comb_appliance returns 0 with no op_comp"""
        f_op_comp = 0
        P_h_fi = 1
        q_in_comb, q_out_comb = (
            self.__combustion_appliances.calculate_air_flow_req_for_comb_appliance(
                f_op_comp=f_op_comp, P_h_fi=P_h_fi
            )
        )

        self.assertAlmostEqual(q_in_comb, 0)
        self.assertAlmostEqual(q_out_comb, 0)


class TestMechanicalVentilation(unittest.TestCase):
    def setUp(self):
        self.simtime = SimulationTime(start_time=0, end_time=2, step=1)
        self.windspeed = [3.7, 3.8, 3.9, 4.0, 4.1, 4.2, 4.3, 4.4]
        self.wind_direction = [200, 220, 230, 240, 250, 260, 260, 270]
        self.airtemp = [0.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 20.0]
        self.diffuse_horizontal_radiation = [333, 610, 572, 420, 0, 10, 90, 275]
        self.direct_beam_radiation = [420, 750, 425, 500, 0, 40, 0, 388]
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
        self.ctrl_intermittent_MEV = MagicMock()
        self.energy_supply_conn = MagicMock()
        self.shading_segments = [
            {"number": 1, "start": 180, "end": 135},
            {"number": 2, "start": 135, "end": 90},
            {"number": 3, "start": 90, "end": 45},
            {"number": 4, "start": 45, "end": 0},
            {"number": 5, "start": 0, "end": -45},
            {"number": 6, "start": -45, "end": -90},
            {"number": 7, "start": -90, "end": -135},
            {"number": 8, "start": -135, "end": -180},
        ]

        duct_perimeter = 0.9
        internal_diameter = 0.25
        external_diameter = 0.27
        length = 0.4
        k_insulation = 0.02
        thickness_insulation = 0.022
        reflective = False
        mvhr_ductwork = [
            Ductwork(
                cross_section_shape=DuctShape.CIRCULAR,
                duct_perimeter=duct_perimeter,
                internal_diameter=internal_diameter,
                external_diameter=external_diameter,
                length=length,
                k_insulation=k_insulation,
                thickness_insulation=thickness_insulation,
                reflective=reflective,
                duct_type=DuctType.EXHAUST,
            ),
            Ductwork(
                cross_section_shape=DuctShape.CIRCULAR,
                duct_perimeter=duct_perimeter,
                internal_diameter=internal_diameter,
                external_diameter=external_diameter,
                length=length,
                k_insulation=k_insulation,
                thickness_insulation=thickness_insulation,
                reflective=reflective,
                duct_type=DuctType.INTAKE,
            ),
            Ductwork(
                cross_section_shape=DuctShape.CIRCULAR,
                duct_perimeter=duct_perimeter,
                internal_diameter=internal_diameter,
                external_diameter=external_diameter,
                length=length,
                k_insulation=k_insulation,
                thickness_insulation=thickness_insulation,
                reflective=reflective,
                duct_type=DuctType.SUPPLY,
            ),
            Ductwork(
                cross_section_shape=DuctShape.CIRCULAR,
                duct_perimeter=duct_perimeter,
                internal_diameter=internal_diameter,
                external_diameter=external_diameter,
                length=length,
                k_insulation=k_insulation,
                thickness_insulation=thickness_insulation,
                reflective=reflective,
                duct_type=DuctType.EXTRACT,
            ),
            Ductwork(
                cross_section_shape=DuctShape.RECTANGULAR,
                duct_perimeter=duct_perimeter,
                internal_diameter=internal_diameter,
                external_diameter=external_diameter,
                length=length,
                k_insulation=k_insulation,
                thickness_insulation=thickness_insulation,
                reflective=reflective,
                duct_type=DuctType.EXHAUST,
            ),
            Ductwork(
                cross_section_shape=DuctShape.RECTANGULAR,
                duct_perimeter=duct_perimeter,
                internal_diameter=internal_diameter,
                external_diameter=external_diameter,
                length=length,
                k_insulation=k_insulation,
                thickness_insulation=thickness_insulation,
                reflective=reflective,
                duct_type=DuctType.INTAKE,
            ),
            Ductwork(
                cross_section_shape=DuctShape.RECTANGULAR,
                duct_perimeter=duct_perimeter,
                internal_diameter=internal_diameter,
                external_diameter=external_diameter,
                length=length,
                k_insulation=k_insulation,
                thickness_insulation=thickness_insulation,
                reflective=reflective,
                duct_type=DuctType.SUPPLY,
            ),
            Ductwork(
                cross_section_shape=DuctShape.RECTANGULAR,
                duct_perimeter=duct_perimeter,
                internal_diameter=internal_diameter,
                external_diameter=external_diameter,
                length=length,
                k_insulation=k_insulation,
                thickness_insulation=thickness_insulation,
                reflective=reflective,
                duct_type=DuctType.EXTRACT,
            ),
        ]

        # Test MVHR with separate intake/exhaust positions
        self.__mechvent = MechanicalVentilation(
            sup_air_flw_ctrl=SupplyAirFlowRateControlType.ODA,
            sup_air_temp_ctrl=SupplyAirTemperatureControlType.NO_CTRL,
            Q_H_des=1.0,
            Q_C_des=3.4,
            vent_type=MechVentType.MVHR,
            specific_fan_power=1.5,
            design_outdoor_air_flow_rate=0.5,
            simulation_time=self.simtime,
            energy_supply_conn=self.energy_supply_conn,
            total_volume=250.0,
            altitude=0,
            orientation_exhaust=Orientation360(0),
            pitch_exhaust=90,
            midheight_exhaust=2,
            ventilation_zone_base_height=3,
            ctrl_intermittent_MEV=self.ctrl_intermittent_MEV,
            mvhr_eff=0.8,
            theta_ctrl_sys=1.1,
            orientation_intake=Orientation360(180),
            pitch_intake=90,
            h_path_intake=3,
            mvhr_location=MVHRLocation.INSIDE,
            mvhr_ductwork=mvhr_ductwork,
        )

    def test_mvhr_positions(self):
        """Test that MVHR correctly stores intake and exhaust positions"""
        self.assertEqual(self.__mechvent._MechanicalVentilation__orientation_intake.angle, 180)  # type: ignore[AttributeAccessIssue]
        self.assertEqual(self.__mechvent._MechanicalVentilation__pitch_intake, 90)  # type: ignore[AttributeAccessIssue]
        self.assertEqual(self.__mechvent._MechanicalVentilation__h_path_intake, 3)  # type: ignore[AttributeAccessIssue]
        self.assertEqual(
            self.__mechvent._MechanicalVentilation__z_intake,  # type: ignore[AttributeAccessIssue]
            6,
        )  # 3 + 3

        self.assertEqual(self.__mechvent._MechanicalVentilation__orientation_exhaust.angle, 0)  # type: ignore[AttributeAccessIssue]
        self.assertEqual(self.__mechvent._MechanicalVentilation__pitch_exhaust, 90)  # type: ignore[AttributeAccessIssue]
        self.assertEqual(self.__mechvent._MechanicalVentilation__h_path_exhaust, 2)  # type: ignore[AttributeAccessIssue]
        self.assertEqual(
            self.__mechvent._MechanicalVentilation__z_exhaust,  # type: ignore[AttributeAccessIssue]
            5,
        )  # 2 + 3

    def test_mev_position(self):
        """Test that MEV systems only use exhaust position"""
        mechvent_mev = MechanicalVentilation(
            sup_air_flw_ctrl=SupplyAirFlowRateControlType.ODA,
            sup_air_temp_ctrl=SupplyAirTemperatureControlType.NO_CTRL,
            Q_H_des=1.0,
            Q_C_des=3.4,
            vent_type=MechVentType.CENTRALISED_CONTINUOUS_MEV,
            specific_fan_power=1.5,
            design_outdoor_air_flow_rate=0.5,
            simulation_time=self.simtime,
            energy_supply_conn=self.energy_supply_conn,
            total_volume=250.0,
            altitude=0,
            orientation_exhaust=Orientation360(90),
            pitch_exhaust=90,
            midheight_exhaust=2.5,
            ventilation_zone_base_height=3,
            ctrl_intermittent_MEV=self.ctrl_intermittent_MEV,
        )

        self.assertEqual(mechvent_mev._MechanicalVentilation__orientation_exhaust.angle, 90)  # type: ignore[AttributeAccessIssue]
        self.assertEqual(mechvent_mev._MechanicalVentilation__pitch_exhaust, 90)  # type: ignore[AttributeAccessIssue]
        self.assertEqual(mechvent_mev._MechanicalVentilation__h_path_exhaust, 2.5)  # type: ignore[AttributeAccessIssue]

        # MEV shouldn't have intake attributes
        with self.assertRaises(AttributeError):
            _ = mechvent_mev._MechanicalVentilation__orientation_intake  # type: ignore[AttributeAccessIssue]

    def test_missing_positions_error(self):
        """Test that missing required positions raise errors"""
        # MVHR without intake position should fail
        with self.assertRaises(ValueError) as context:
            MechanicalVentilation(
                sup_air_flw_ctrl=SupplyAirFlowRateControlType.ODA,
                sup_air_temp_ctrl=SupplyAirTemperatureControlType.NO_CTRL,
                Q_H_des=1.0,
                Q_C_des=3.4,
                vent_type=MechVentType.MVHR,
                specific_fan_power=1.5,
                design_outdoor_air_flow_rate=0.5,
                simulation_time=self.simtime,
                energy_supply_conn=self.energy_supply_conn,
                total_volume=250.0,
                altitude=0,
                orientation_exhaust=Orientation360(0),
                pitch_exhaust=90,
                midheight_exhaust=2,
                ventilation_zone_base_height=3,
                ctrl_intermittent_MEV=self.ctrl_intermittent_MEV,
                mvhr_eff=0.0,
            )
        self.assertIn(
            "MVHR systems require both intake and exhaust positions", str(context.exception)
        )

    def test_calculate_required_outdoor_air_flow_rate(self):
        """Returns 0.55"""
        expected_result = 0.55
        self.assertAlmostEqual(
            self.__mechvent.calculate_required_outdoor_air_flow_rate(), expected_result
        )

    def test_calc_req_ODA_flow_rates_at_ATDs(self):
        """Test that calc_req_ODA_flow_rates_at_ATDs returns the correct values for different vent types"""
        qv_SUP_req, qv_ETA_req = self.__mechvent.calc_req_ODA_flow_rates_at_ATDs()
        self.assertAlmostEqual(qv_SUP_req, 0.55)
        self.assertAlmostEqual(qv_ETA_req, -0.55)

        self.__mechvent._MechanicalVentilation__vent_type = MechVentType.INTERMITTENT_MEV  # type: ignore[AttributeAccessIssue]
        qv_SUP_req, qv_ETA_req = self.__mechvent.calc_req_ODA_flow_rates_at_ATDs()
        self.assertAlmostEqual(qv_SUP_req, 0.0)
        self.assertAlmostEqual(qv_ETA_req, -0.55)

        self.__mechvent._MechanicalVentilation__vent_type = MechVentType.POSITIVE_INPUT_VENTILATION  # type: ignore[AttributeAccessIssue]
        qv_SUP_req, qv_ETA_req = self.__mechvent.calc_req_ODA_flow_rates_at_ATDs()
        self.assertAlmostEqual(qv_SUP_req, 0.55)
        self.assertAlmostEqual(qv_ETA_req, 0.0)

        # Since MechVentType is an enum, it's impossible to have an invalid value in practice
        # self.__mechvent._MechanicalVentilation__vent_type = 'Invalid'
        # with self.assertRaises(ValueError):
        #    self.__mechvent.calc_req_ODA_flow_rates_at_ATDs()

    def test_calc_mech_vent_air_flw_rates_req_to_supply_vent_zone(self):
        """0.7106861797547136 -0.6622 0.0"""
        qm_SUP_dis_req, qm_ETA_dis_req, qm_in_effective_heat_recovery_saving = (
            self.__mechvent.calc_mech_vent_air_flw_rates_req_to_supply_vent_zone(
                u_site=4.135012577787589,
                wind_direction=Orientation360(140),
                f_cross=True,
                shield_class=VentilationShieldClass.NORMAL,
                T_z=293.15,
                T_e=cast(float, Celcius2Kelvin(self.airtemp[0])),
                p_z_ref=1.7775065710163496,
                time_step=1,
            )
        )
        self.assertAlmostEqual(qm_SUP_dis_req, 0)
        self.assertAlmostEqual(qm_ETA_dis_req, -0.6622)
        self.assertAlmostEqual(qm_in_effective_heat_recovery_saving, 0)

        # Should throw with invalid sup_air_flw_ctrl_type
        self.__mechvent._MechanicalVentilation__sup_air_flw_ctrl = "Invalid"  # type: ignore[AttributeAccessIssue]
        with self.assertRaises(ValueError):
            self.__mechvent.calc_mech_vent_air_flw_rates_req_to_supply_vent_zone(
                u_site=4.135012577787589,
                wind_direction=Orientation360(140),
                f_cross=True,
                shield_class=VentilationShieldClass.NORMAL,
                T_z=290,
                T_e=300,
                p_z_ref=1.7777,
                time_step=1,
            )

    def test_f_op_v(self):
        """Test that __f_op_v returns the correct values"""
        self.assertEqual(self.__mechvent._MechanicalVentilation__f_op_v(), 1)  # type: ignore[AttributeAccessIssue]

        self.__mechvent._MechanicalVentilation__ctrl_intermittent_MEV.setpnt.return_value = 0.5  # type: ignore[AttributeAccessIssue]
        self.__mechvent._MechanicalVentilation__vent_type = MechVentType.INTERMITTENT_MEV  # type: ignore[AttributeAccessIssue]
        self.assertEqual(self.__mechvent._MechanicalVentilation__f_op_v(), 0.5)  # type: ignore[AttributeAccessIssue]

        self.__mechvent._MechanicalVentilation__ctrl_intermittent_MEV.setpnt.return_value = 1.5  # type: ignore[AttributeAccessIssue]
        with self.assertRaises(ValueError):
            self.__mechvent._MechanicalVentilation__f_op_v()  # type: ignore[AttributeAccessIssue]

        # Since MechVentType is an enum, it's impossible to have an invalid value in practice
        # self.__mechvent._MechanicalVentilation__ctrl_intermittent_MEV.setpnt.return_value = 0.5
        # self.__mechvent._MechanicalVentilation__vent_type = 'Invalid'
        # with self.assertRaises(ValueError):
        #    self.__mechvent._MechanicalVentilation__f_op_v()

    def test_fans(self):
        self.__mechvent = MechanicalVentilation(
            sup_air_flw_ctrl=SupplyAirFlowRateControlType.ODA,
            sup_air_temp_ctrl=SupplyAirTemperatureControlType.NO_CTRL,
            Q_H_des=1.0,
            Q_C_des=3.4,
            vent_type=MechVentType.MVHR,
            specific_fan_power=1.5,
            design_outdoor_air_flow_rate=50,
            simulation_time=self.simtime,
            energy_supply_conn=self.energy_supply_conn,
            total_volume=250.0,
            altitude=0,
            orientation_exhaust=Orientation360(180),
            pitch_exhaust=90,
            midheight_exhaust=2,
            ventilation_zone_base_height=3,
            ctrl_intermittent_MEV=self.ctrl_intermittent_MEV,
            mvhr_eff=0.0,
            theta_ctrl_sys=1.1,
            orientation_intake=Orientation360(180),
            pitch_intake=90,
            h_path_intake=2,
        )

        self.__mechvent._MechanicalVentilation__vent_type = MechVentType.CENTRALISED_CONTINUOUS_MEV  # type: ignore[AttributeAccessIssue]
        self.assertAlmostEqual(self.__mechvent.fans(zone_volume=200, total_volume=2000), 0.0)
        self.energy_supply_conn.demand_energy.assert_has_calls(
            [call(amount_demanded=0.0), call(amount_demanded=0.002291666666666667)]
        )

        self.energy_supply_conn.reset_mock()

        self.__mechvent._MechanicalVentilation__vent_type = MechVentType.MVHR  # type: ignore[AttributeAccessIssue]
        self.assertAlmostEqual(
            self.__mechvent.fans(zone_volume=200, total_volume=2000), 1.1458333333333335
        )
        self.energy_supply_conn.demand_energy.assert_has_calls(
            [
                call(amount_demanded=0.0011458333333333336),
                call(amount_demanded=0.0011458333333333336),
            ]
        )

        # Since MechVentType is an enum, it's impossible to have an invalid value in practice
        # self.__mechvent._MechanicalVentilation__vent_type = 'Invalid'
        # with self.assertRaises(ValueError):
        #    self.__mechvent.fans(200, 2000)

    def test_calc_mech_vent_air_flw_rates_req_to_supply_vent_zone_extract_only(self):
        """Test calc_mech_vent_air_flw_rates_req_to_supply_vent_zone for extract-only systems"""
        # Create a mechanical ventilation with extract-only type
        self.__mechvent = MechanicalVentilation(
            sup_air_flw_ctrl=SupplyAirFlowRateControlType.ODA,
            sup_air_temp_ctrl=SupplyAirTemperatureControlType.NO_CTRL,
            Q_H_des=1.0,
            Q_C_des=3.4,
            vent_type=MechVentType.CENTRALISED_CONTINUOUS_MEV,  # This is extract-only
            specific_fan_power=1.5,
            design_outdoor_air_flow_rate=50,
            simulation_time=self.simtime,
            energy_supply_conn=self.energy_supply_conn,
            total_volume=250.0,
            altitude=0,
            orientation_exhaust=Orientation360(180),
            pitch_exhaust=90,
            midheight_exhaust=2,
            ventilation_zone_base_height=3,
            ctrl_intermittent_MEV=None,
            mvhr_eff=0.0,
        )

        # Test with positive delta_p_mech_vent (back pressure)
        qm_SUP_dis_req, qm_ETA_dis_req, qm_in_effective_heat_recovery_saving = (
            self.__mechvent.calc_mech_vent_air_flw_rates_req_to_supply_vent_zone(
                u_site=4.135012577787589,
                wind_direction=Orientation360(140),
                f_cross=True,
                shield_class=VentilationShieldClass.NORMAL,
                T_z=293.15,
                T_e=cast(float, Celcius2Kelvin(10)),
                p_z_ref=2.0,  # Higher pressure to create positive delta_p
                time_step=1,
            )
        )

        # For extract-only systems, supply should be 0
        self.assertEqual(qm_SUP_dis_req, 0.0)
        # Extract should be negative (air leaving)
        self.assertLess(qm_ETA_dis_req, 0)
        self.assertEqual(qm_in_effective_heat_recovery_saving, 0.0)

    def test_calc_mech_vent_air_flw_rates_req_to_supply_vent_zone_supply_only(self):
        """Test that supply-only systems raise appropriate error since they're not implemented"""
        # Since supply-only systems (like PIV) aren't implemented yet,
        # we should test that the appropriate error is raised

        # First, let's test with a valid extract-only system to ensure it works
        self.__mechvent = MechanicalVentilation(
            sup_air_flw_ctrl=SupplyAirFlowRateControlType.ODA,
            sup_air_temp_ctrl=SupplyAirTemperatureControlType.NO_CTRL,
            Q_H_des=1.0,
            Q_C_des=3.4,
            vent_type=MechVentType.CENTRALISED_CONTINUOUS_MEV,  # Extract-only system
            specific_fan_power=1.5,
            design_outdoor_air_flow_rate=50,
            simulation_time=self.simtime,
            energy_supply_conn=self.energy_supply_conn,
            total_volume=250.0,
            altitude=0,
            orientation_exhaust=Orientation360(180),
            pitch_exhaust=90,
            midheight_exhaust=2,
            ventilation_zone_base_height=3,
            ctrl_intermittent_MEV=None,
        )

        # This should work without raising an error
        qm_SUP_dis_req, qm_ETA_dis_req, qm_in_effective_heat_recovery_saving = (
            self.__mechvent.calc_mech_vent_air_flw_rates_req_to_supply_vent_zone(
                u_site=4.135012577787589,
                wind_direction=Orientation360(140),
                f_cross=True,
                shield_class=VentilationShieldClass.NORMAL,
                T_z=293.15,
                T_e=cast(float, Celcius2Kelvin(10)),
                p_z_ref=-1.0,
                time_step=1,
            )
        )

        # Verify extract-only behavior
        self.assertAlmostEqual(qm_SUP_dis_req, 0.0)  # No supply for extract-only
        self.assertLess(qm_ETA_dis_req, 0)  # Negative for extraction
        self.assertAlmostEqual(qm_in_effective_heat_recovery_saving, 0.0)  # No heat recovery

        # TODO: When PIV (Positive Input Ventilation) is implemented, add test coverage here

    def test_calc_mech_vent_air_flw_rates_error_cases_with_flow_change(self):
        """Test the ValueError cases in calc_mech_vent_air_flw_rates_req_to_supply_vent_zone with flow changes"""
        # Create a mechanical ventilation
        self.__mechvent = MechanicalVentilation(
            sup_air_flw_ctrl=SupplyAirFlowRateControlType.ODA,
            sup_air_temp_ctrl=SupplyAirTemperatureControlType.NO_CTRL,
            Q_H_des=1.0,
            Q_C_des=3.4,
            vent_type=MechVentType.MVHR,
            specific_fan_power=1.5,
            design_outdoor_air_flow_rate=50,
            simulation_time=self.simtime,
            energy_supply_conn=self.energy_supply_conn,
            total_volume=250.0,
            altitude=0,
            orientation_exhaust=Orientation360(180),
            pitch_exhaust=90,
            midheight_exhaust=2,
            ventilation_zone_base_height=3,
            ctrl_intermittent_MEV=None,
            mvhr_eff=0.0,
            orientation_intake=Orientation360(180),
            pitch_intake=90,
            h_path_intake=2,
        )

        # Test ValueError for unrecognized ventilation type in supply flow adjustment
        with patch.object(self.__mechvent, "_MechanicalVentilation__vent_type") as mock_vent_type:
            mock_vent_type.has_supply.return_value = False
            mock_vent_type.is_extract_only.return_value = False
            mock_vent_type.is_continuous.return_value = True
            mock_vent_type.is_intermittent.return_value = False

            with patch.object(
                self.__mechvent, "calc_req_ODA_flow_rates_at_ATDs", return_value=(55.0, -55.0)
            ):
                with self.assertRaises(KeyError) as context:
                    self.__mechvent.calc_mech_vent_air_flw_rates_req_to_supply_vent_zone(
                        u_site=4.135012577787589,
                        wind_direction=Orientation360(140),
                        f_cross=True,
                        shield_class=VentilationShieldClass.NORMAL,
                        T_z=293.15,
                        T_e=cast(float, Celcius2Kelvin(10)),
                        p_z_ref=1.0,
                        time_step=1,
                    )
                self.assertIn("Unrecognised ventilation system type", context.exception.__notes__)

        # Test ValueError for unrecognized ventilation type in extract flow adjustment
        with patch.object(self.__mechvent, "_MechanicalVentilation__vent_type") as mock_vent_type:
            mock_vent_type.has_supply.return_value = True
            mock_vent_type.is_extract_only.return_value = False
            mock_vent_type.has_extract.return_value = False
            mock_vent_type.is_supply_only.return_value = False
            mock_vent_type.is_continuous.return_value = True
            mock_vent_type.is_intermittent.return_value = False

            with patch.object(
                self.__mechvent, "calc_req_ODA_flow_rates_at_ATDs", return_value=(55.0, -55.0)
            ):
                with self.assertRaises(KeyError) as context:
                    self.__mechvent.calc_mech_vent_air_flw_rates_req_to_supply_vent_zone(
                        u_site=4.135012577787589,
                        wind_direction=Orientation360(140),
                        f_cross=True,
                        shield_class=VentilationShieldClass.NORMAL,
                        T_z=293.15,
                        T_e=cast(float, Celcius2Kelvin(10)),
                        p_z_ref=1.0,
                        time_step=1,
                    )
                self.assertIn("Unrecognised ventilation system type", context.exception.__notes__)

    def test_calc_req_ODA_flow_rates_at_ATDs_PIV(self):
        """Test calc_req_ODA_flow_rates_at_ATDs for Positive Input Ventilation (uncovered line 1066)"""
        # Create a mechanical ventilation with PIV type
        self.__mechvent = MechanicalVentilation(
            sup_air_flw_ctrl=SupplyAirFlowRateControlType.ODA,
            sup_air_temp_ctrl=SupplyAirTemperatureControlType.NO_CTRL,
            Q_H_des=1.0,
            Q_C_des=3.4,
            vent_type=MechVentType.MVHR,  # We'll mock this to PIV
            specific_fan_power=1.5,
            design_outdoor_air_flow_rate=50,
            simulation_time=self.simtime,
            energy_supply_conn=self.energy_supply_conn,
            total_volume=250.0,
            altitude=0,
            orientation_exhaust=Orientation360(180),
            pitch_exhaust=90,
            midheight_exhaust=2,
            ventilation_zone_base_height=3,
            ctrl_intermittent_MEV=None,
            mvhr_eff=0.0,
            orientation_intake=Orientation360(180),
            pitch_intake=90,
            h_path_intake=2,
        )

        # Mock the vent type to simulate PIV
        with patch.object(self.__mechvent, "_MechanicalVentilation__vent_type") as mock_vent_type:
            # Configure mock to return False for is_balanced() and is_extract_only()
            # but not be is_supply_only() to reach the else clause
            mock_vent_type.is_balanced.return_value = False
            mock_vent_type.is_extract_only.return_value = False
            mock_vent_type.is_supply_only.return_value = False

            with self.assertRaises(ValueError) as context:
                self.__mechvent.calc_req_ODA_flow_rates_at_ATDs()
            self.assertEqual(str(context.exception), "Unrecognised ventilation system type")

    def test_f_op_v_unknown_mech_vent_type(self):
        """Test __f_op_v with unknown mechanical ventilation type (uncovered line 1080)"""
        # Create a mechanical ventilation
        self.__mechvent = MechanicalVentilation(
            sup_air_flw_ctrl=SupplyAirFlowRateControlType.ODA,
            sup_air_temp_ctrl=SupplyAirTemperatureControlType.NO_CTRL,
            Q_H_des=1.0,
            Q_C_des=3.4,
            vent_type=MechVentType.MVHR,
            specific_fan_power=1.5,
            design_outdoor_air_flow_rate=50,
            simulation_time=self.simtime,
            energy_supply_conn=self.energy_supply_conn,
            total_volume=250.0,
            altitude=0,
            orientation_exhaust=Orientation360(180),
            pitch_exhaust=90,
            midheight_exhaust=2,
            ventilation_zone_base_height=3,
            ctrl_intermittent_MEV=None,
            mvhr_eff=0.0,
            orientation_intake=Orientation360(180),
            pitch_intake=90,
            h_path_intake=3,
        )

        # Mock the vent type to not be intermittent or continuous
        with patch.object(self.__mechvent, "_MechanicalVentilation__vent_type") as mock_vent_type:
            mock_vent_type.is_intermittent.return_value = False
            mock_vent_type.is_continuous.return_value = False

            with self.assertRaises(ValueError) as context:
                self.__mechvent._MechanicalVentilation__f_op_v()  # type: ignore[AttributeAccessIssue]
            self.assertEqual(str(context.exception), "Unknown mechanical ventilation system type")

    def test_calc_mech_vent_air_flw_rates_req_to_supply_vent_zone_invalid_sup_air_flw_ctrl(self):
        """Test calc_mech_vent_air_flw_rates_req_to_supply_vent_zone with invalid supply air flow control"""
        # Create a mechanical ventilation
        self.__mechvent = MechanicalVentilation(
            sup_air_flw_ctrl=SupplyAirFlowRateControlType.ODA,
            sup_air_temp_ctrl=SupplyAirTemperatureControlType.NO_CTRL,
            Q_H_des=1.0,
            Q_C_des=3.4,
            vent_type=MechVentType.MVHR,
            specific_fan_power=1.5,
            design_outdoor_air_flow_rate=50,
            simulation_time=self.simtime,
            energy_supply_conn=self.energy_supply_conn,
            total_volume=250.0,
            altitude=0,
            orientation_exhaust=Orientation360(180),
            pitch_exhaust=90,
            midheight_exhaust=2,
            ventilation_zone_base_height=3,
            ctrl_intermittent_MEV=None,
            mvhr_eff=0.0,
            orientation_intake=Orientation360(180),
            pitch_intake=90,
            h_path_intake=3,
        )

        # Set invalid sup_air_flw_ctrl
        self.__mechvent._MechanicalVentilation__sup_air_flw_ctrl = "INVALID"  # type: ignore[AttributeAccessIssue]

        with self.assertRaises(ValueError) as context:
            self.__mechvent.calc_mech_vent_air_flw_rates_req_to_supply_vent_zone(
                u_site=4.135012577787589,
                wind_direction=Orientation360(140),
                f_cross=True,
                shield_class=VentilationShieldClass.NORMAL,
                T_z=293.15,
                T_e=cast(float, Celcius2Kelvin(10)),
                p_z_ref=1.0,
                time_step=1,
            )
        self.assertEqual(str(context.exception), "Unknown sup_air_flw_ctrl type")

    def test_calc_req_ODA_flow_rates_unrecognized_type(self):
        """Test calc_req_ODA_flow_rates_at_ATDs with unrecognized ventilation type"""
        # Create a mechanical ventilation with MVHR
        self.__mechvent = MechanicalVentilation(
            sup_air_flw_ctrl=SupplyAirFlowRateControlType.ODA,
            sup_air_temp_ctrl=SupplyAirTemperatureControlType.NO_CTRL,
            Q_H_des=1.0,
            Q_C_des=3.4,
            vent_type=MechVentType.MVHR,
            specific_fan_power=1.5,
            design_outdoor_air_flow_rate=50,
            simulation_time=self.simtime,
            energy_supply_conn=self.energy_supply_conn,
            total_volume=250.0,
            altitude=0,
            orientation_exhaust=Orientation360(180),
            pitch_exhaust=90,
            midheight_exhaust=2,
            ventilation_zone_base_height=3,
            ctrl_intermittent_MEV=None,
            mvhr_eff=0.0,
            orientation_intake=Orientation360(180),
            pitch_intake=90,
            h_path_intake=2,
        )

        # Mock the vent type to be neither balanced nor extract-only nor supply-only
        with patch.object(self.__mechvent, "_MechanicalVentilation__vent_type") as mock_vent_type:
            mock_vent_type.is_balanced.return_value = False
            mock_vent_type.is_extract_only.return_value = False
            mock_vent_type.is_supply_only.return_value = False

            with self.assertRaises(ValueError) as context:
                self.__mechvent.calc_req_ODA_flow_rates_at_ATDs()
            self.assertEqual(str(context.exception), "Unrecognised ventilation system type")

        # Test ValueError for unrecognized ventilation type in extract flow adjustment
        with patch.object(self.__mechvent, "_MechanicalVentilation__vent_type") as mock_vent_type:
            mock_vent_type.has_supply.return_value = True
            mock_vent_type.is_extract_only.return_value = False
            mock_vent_type.has_extract.return_value = False
            mock_vent_type.is_supply_only.return_value = False
            mock_vent_type.is_continuous.return_value = True
            mock_vent_type.is_intermittent.return_value = False

            with patch.object(
                self.__mechvent, "calc_req_ODA_flow_rates_at_ATDs", return_value=(55.0, -55.0)
            ):
                with self.assertRaises(KeyError) as context:
                    self.__mechvent.calc_mech_vent_air_flw_rates_req_to_supply_vent_zone(
                        u_site=4.135012577787589,
                        wind_direction=Orientation360(140),
                        f_cross=True,
                        shield_class=VentilationShieldClass.NORMAL,
                        T_z=293.15,
                        T_e=cast(float, Celcius2Kelvin(10)),
                        p_z_ref=1.0,
                        time_step=1,
                    )
                self.assertIn("Unrecognised ventilation system type", context.exception.__notes__)

        # Test ValueError for unrecognized ventilation type in extract flow adjustment
        with patch.object(self.__mechvent, "_MechanicalVentilation__vent_type") as mock_vent_type:
            mock_vent_type.has_supply.return_value = False
            mock_vent_type.has_extract.return_value = False

            with patch.object(
                self.__mechvent, "calc_req_ODA_flow_rates_at_ATDs", return_value=(55.0, -55.0)
            ):
                with self.assertRaises(ValueError) as context:
                    self.__mechvent.calc_mech_vent_air_flw_rates_req_to_supply_vent_zone(
                        u_site=4.135012577787589,
                        wind_direction=Orientation360(140),
                        f_cross=True,
                        shield_class=VentilationShieldClass.NORMAL,
                        T_z=293.15,
                        T_e=cast(float, Celcius2Kelvin(10)),
                        p_z_ref=1.0,
                        time_step=1,
                    )
                self.assertEqual(str(context.exception), "Unrecognised ventilation system type")

    def test_mechanical_ventilation_init_piv_error(self):
        """Test that PIV (Positive Input Ventilation) raises error during initialization (line 1023)"""
        # PIV is in the enum but not properly handled in __init__, should raise error
        with self.assertRaises(ValueError) as context:
            MechanicalVentilation(
                sup_air_flw_ctrl=SupplyAirFlowRateControlType.ODA,
                sup_air_temp_ctrl=SupplyAirTemperatureControlType.NO_CTRL,
                Q_H_des=1.0,
                Q_C_des=3.4,
                vent_type=MechVentType.POSITIVE_INPUT_VENTILATION,  # PIV
                specific_fan_power=1.5,
                design_outdoor_air_flow_rate=50,
                simulation_time=self.simtime,
                energy_supply_conn=self.energy_supply_conn,
                total_volume=250.0,
                altitude=0,
                orientation_exhaust=Orientation360(180),
                pitch_exhaust=90,
                midheight_exhaust=2,
                ventilation_zone_base_height=3,
                ctrl_intermittent_MEV=None,
            )
        self.assertEqual(str(context.exception), "Mechanical ventilation type not recognised")

    def test_calc_internal_gains_ductwork_mvhr_inside(self):
        """Test that correct total duct heat loss is returned when queried"""
        outside_temp = [20.0, 5.0]
        inside_temp = [19.0, 19.5]
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertAlmostEqual(
                    self.__mechvent.calc_internal_gains_ductwork(
                        outside_temp[t_idx], inside_temp[t_idx]
                    ),
                    [
                        0.18504811111111114,
                        -2.6831976111111118,
                    ][t_idx],
                    msg="incorrect total duct heat loss returned",
                )

    def test_calc_internal_gains_ductwork_mvhr_inside_equal_temps(self):
        """Test that correct total duct heat loss is returned when queried"""
        outside_temp = [20.0, -5.0]
        inside_temp = [20.0, -5.0]
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertAlmostEqual(
                    self.__mechvent.calc_internal_gains_ductwork(
                        outside_temp[t_idx], inside_temp[t_idx]
                    ),
                    [
                        0.0,
                        0.0,
                    ][t_idx],
                    msg="incorrect total duct heat loss returned",
                )

    def test_calc_internal_gains_ductwork_mvhr_outside(self):
        """Test that correct total duct heat loss is returned when queried"""
        self.__mechvent._MechanicalVentilation__mvhr_location = MVHRLocation.OUTSIDE  # type: ignore[AttributeAccessIssue]

        outside_temp = [20.0, 5.0]
        inside_temp = [19.0, 19.5]
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertAlmostEqual(
                    self.__mechvent.calc_internal_gains_ductwork(
                        outside_temp[t_idx], inside_temp[t_idx]
                    ),
                    [
                        0.18504811111111114,
                        -2.6831976111111118,
                    ][t_idx],
                    msg="incorrect total duct heat loss returned",
                )

    def test_calc_internal_gains_ductwork_mvhr_outside_equal_temps(self):
        """Test that correct total duct heat loss is returned when queried"""
        self.__mechvent._MechanicalVentilation__mvhr_location = MVHRLocation.OUTSIDE  # type: ignore[AttributeAccessIssue]

        outside_temp = [19.0, -4.0]
        inside_temp = [19.0, -4.0]
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertAlmostEqual(
                    self.__mechvent.calc_internal_gains_ductwork(
                        outside_temp[t_idx], inside_temp[t_idx]
                    ),
                    [
                        0.0,
                        0.0,
                    ][t_idx],
                    msg="incorrect total duct heat loss returned",
                )

    def test_calc_internal_gains_ductwork_not_mvhr(self):
        """Test that correct total duct heat loss is returned when queried"""
        mechvent_mev = MechanicalVentilation(
            sup_air_flw_ctrl=SupplyAirFlowRateControlType.ODA,
            sup_air_temp_ctrl=SupplyAirTemperatureControlType.NO_CTRL,
            Q_H_des=1.0,
            Q_C_des=3.4,
            vent_type=MechVentType.CENTRALISED_CONTINUOUS_MEV,
            specific_fan_power=1.5,
            design_outdoor_air_flow_rate=0.5,
            simulation_time=self.simtime,
            energy_supply_conn=self.energy_supply_conn,
            total_volume=250.0,
            altitude=0,
            orientation_exhaust=Orientation360(90),
            pitch_exhaust=90,
            midheight_exhaust=2.5,
            ventilation_zone_base_height=3,
            ctrl_intermittent_MEV=self.ctrl_intermittent_MEV,
        )

        outside_temp = [20.0, 5.0]
        inside_temp = [19.0, 19.5]
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertAlmostEqual(
                    mechvent_mev.calc_internal_gains_ductwork(
                        outside_temp[t_idx], inside_temp[t_idx]
                    ),
                    [
                        0.0,
                        0.0,
                    ][t_idx],
                    msg="incorrect total duct heat loss returned",
                )


class TestInfiltrationVentilation(unittest.TestCase):
    def setUp(self):
        self.simtime = SimulationTime(start_time=0, end_time=2, step=1)
        self.windspeed = [3.7, 3.8, 3.9, 4.0, 4.1, 4.2, 4.3, 4.4]
        self.wind_direction = [200, 220, 230, 240, 250, 260, 260, 270]
        self.airtemp = [0.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 20.0]
        self.diffuse_horizontal_radiation = [333, 610, 572, 420, 0, 10, 90, 275]
        self.direct_beam_radiation = [420, 750, 425, 500, 0, 40, 0, 388]
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
            {"number": 1, "start": 180, "end": 135},
            {"number": 2, "start": 135, "end": 90},
            {"number": 3, "start": 90, "end": 45},
            {"number": 4, "start": 45, "end": 0},
            {"number": 5, "start": 0, "end": -45},
            {"number": 6, "start": -45, "end": -90},
            {"number": 7, "start": -90, "end": -135},
            {"number": 8, "start": -135, "end": -180},
        ]

        sched = expand_schedule(
            sched_type=bool,
            sched_dict={"main": [{"repeat": 8760, "value": True}]},
            sched_main="main",
            nullable=False,
        )
        sched = [cast(bool, v) for v in sched]
        ctrl = OnOffTimeControl(
            schedule=sched, simulation_time=self.simtime, start_day=0, time_series_step=1
        )
        window_part_list = [{"mid_height_air_flow_path": 1.5}]
        self.window = Window(
            free_area_height=1.6,
            midheight=1,
            max_opening_area=3,
            window_part_list=window_part_list,
            orientation=Orientation360(0),
            pitch=90,
            altitude=30,
            on_off_ctrl_obj=ctrl,
            ventilation_zone_base_height=2.5,
        )

        self.window_dict = {"window 0": self.window}

        self.vent = Vent(
            midheight=1.5,
            area=100.0,
            delta_p_vent_ref=20.0,
            orientation=Orientation360(0.0),
            pitch=90.0,
            altitude=30.0,
            ventilation_zone_base_height=2.5,
        )
        self.vent_dict = {"vent 1": self.vent}
        self.leaks_dict = {
            "ventilation_zone_height": 6,
            "test_pressure": 50,
            "test_result": 1.2,
            "env_area": 220,
            "area_facades": 85.0,
            "area_roof": 25.0,
            "altitude": 30.0,
        }

        duct_perimeter = 0.9
        internal_diameter = 0.25
        external_diameter = 0.27
        length = 0.4
        k_insulation = 0.02
        thickness_insulation = 0.022
        reflective = False
        mvhr_ductwork = [
            Ductwork(
                cross_section_shape=DuctShape.CIRCULAR,
                duct_perimeter=duct_perimeter,
                internal_diameter=internal_diameter,
                external_diameter=external_diameter,
                length=length,
                k_insulation=k_insulation,
                thickness_insulation=thickness_insulation,
                reflective=reflective,
                duct_type=DuctType.EXHAUST,
            ),
            Ductwork(
                cross_section_shape=DuctShape.CIRCULAR,
                duct_perimeter=duct_perimeter,
                internal_diameter=internal_diameter,
                external_diameter=external_diameter,
                length=length,
                k_insulation=k_insulation,
                thickness_insulation=thickness_insulation,
                reflective=reflective,
                duct_type=DuctType.INTAKE,
            ),
        ]

        self.mechvent = MechanicalVentilation(
            sup_air_flw_ctrl=SupplyAirFlowRateControlType.ODA,
            sup_air_temp_ctrl=SupplyAirTemperatureControlType.NO_CTRL,
            Q_H_des=1.0,
            Q_C_des=3.4,
            vent_type=MechVentType.MVHR,
            specific_fan_power=1.5,
            design_outdoor_air_flow_rate=0.5,
            simulation_time=self.simtime,
            energy_supply_conn=EnergySupplyConnection(
                energy_supply=EnergySupply(
                    fuel_type=FuelType.ELECTRICITY, simulation_time=self.simtime
                ),
                end_user_name="mech_vent_fans",
            ),
            total_volume=250.0,
            altitude=0,
            orientation_exhaust=Orientation360(180),
            pitch_exhaust=90,
            midheight_exhaust=2,
            ventilation_zone_base_height=3,
            ctrl_intermittent_MEV=None,
            mvhr_eff=0.75,
            orientation_intake=Orientation360(180),
            pitch_intake=90,
            h_path_intake=2,
            mvhr_location=MVHRLocation.INSIDE,
            mvhr_ductwork=mvhr_ductwork,
        )
        self.mech_vents = [self.mechvent]

        self.combustion_appliances = CombustionAppliances(
            supply_situation=CombustionAirSupplySituation.ROOM_AIR,
            exhaust_situation=FlueGasExhaustSituation.INTO_SEPARATE_DUCT,
            fuel_type=CombustionFuelType.WOOD,
            appliance_type=CombustionApplianceType.OPEN_FIREPLACE,
        )
        self.combustion_appliances_dict = {"Fireplace": self.combustion_appliances}

        self.infil_vent = InfiltrationVentilation(
            simulation_time=self.simtime,
            f_cross=True,
            shield_class=VentilationShieldClass.OPEN,
            terrain_class=TerrainClass.OPEN_FIELD,
            average_roof_pitch=20.0,
            windows=self.window_dict,
            vents=self.vent_dict,
            leaks=self.leaks_dict,
            combustion_appliances=self.combustion_appliances_dict,
            ATDs={},
            mech_vents=self.mech_vents,
            detailed_output_heating_cooling=False,
            altitude=0,
            total_volume=250.0,
            ventilation_zone_base_height=2.5,
        )

    # def test_temp_supply(self):
    #     ''' Returns 0.0'''
    #     air_temp = self.infil_vent.temp_supply()
    #     self.assertAlmostEqual(air_temp, 0.0)

    def test_mech_vents(self):
        """Test that mech_vents returns the correct values"""
        self.assertEqual(self.infil_vent.mech_vents(), self.mech_vents)

    def test_calculate_total_volume_air_flow_rate_in(self):
        qm_in = 0.5
        external_air_density = 1
        self.assertAlmostEqual(
            self.infil_vent.calculate_total_volume_air_flow_rate_in(
                qm_in=qm_in, external_air_density=external_air_density
            ),
            0.5,
        )

    def test_calculate_total_volume_air_flow_rate_out(self):
        qm_out = 0.5
        zone_air_density = 1
        self.assertAlmostEqual(
            self.infil_vent.calculate_total_volume_air_flow_rate_out(
                qm_out=qm_out, zone_air_density=zone_air_density
            ),
            0.5,
        )

    def test_make_leak_objects(self):
        """returns leak object"""
        leaklist = self.infil_vent.make_leak_objects(
            self.leaks_dict, average_roof_pitch=40.0, ventilation_zone_base_height=2.5
        )
        for leak in leaklist:
            self.assertEqual(isinstance(leak, Leaks), True)

    def test_make_leak_objects_roof_pitch(self):
        """Test that make_leak_objects returns the correct roof pitches"""
        self.infil_vent._InfiltrationVentilation__f_cross = True  # type: ignore[AttributeAccessIssue]
        leaklist = self.infil_vent.make_leak_objects(
            leaks=self.leaks_dict, average_roof_pitch=5, ventilation_zone_base_height=2.5
        )
        self.assertEqual(
            [leaks._Leaks__facade_direction for leaks in leaklist],  # type: ignore[AttributeAccessIssue]
            ["wind_seg2", "wind_seg4", "wind_seg2", "wind_seg4", "Roof10"],
        )

        self.infil_vent._InfiltrationVentilation__f_cross = True  # type: ignore[AttributeAccessIssue]
        leaklist = self.infil_vent.make_leak_objects(
            leaks=self.leaks_dict, average_roof_pitch=15, ventilation_zone_base_height=2.5
        )
        self.assertEqual(
            [leaks._Leaks__facade_direction for leaks in leaklist],  # type: ignore[AttributeAccessIssue]
            ["wind_seg2", "wind_seg4", "wind_seg2", "wind_seg4", "Roof10_30"],
        )

        leaklist = self.infil_vent.make_leak_objects(
            leaks=self.leaks_dict, average_roof_pitch=40, ventilation_zone_base_height=2.5
        )
        self.assertEqual(
            [leaks._Leaks__facade_direction for leaks in leaklist],  # type: ignore[AttributeAccessIssue]
            ["wind_seg2", "wind_seg4", "wind_seg2", "wind_seg4", "Roof30"],
        )

        self.infil_vent._InfiltrationVentilation__f_cross = False  # type: ignore[AttributeAccessIssue]
        leaklist = self.infil_vent.make_leak_objects(
            leaks=self.leaks_dict, average_roof_pitch=40, ventilation_zone_base_height=2.5
        )
        self.assertEqual(
            [leaks._Leaks__facade_direction for leaks in leaklist],  # type: ignore[AttributeAccessIssue]
            ["wind_seg2", "wind_seg4", "wind_seg2", "wind_seg4", "Roof"],
        )

        self.infil_vent._InfiltrationVentilation__f_cross = True  # type: ignore[AttributeAccessIssue]
        with self.assertRaises(ValueError):
            self.infil_vent.make_leak_objects(
                leaks=self.leaks_dict, average_roof_pitch=90, ventilation_zone_base_height=2.5
            )

    # TODO uncomment when re-implementing ATDs
    #     def test_calculate_qv_pdu(self):
    #         """ Test that calculate_qv_pdu returns the correct value """
    #
    #         self.infil_vent = InfiltrationVentilation(self.simtime,
    #                                                   f_cross = True,
    #                                                   shield_class = 'Open',
    #                                                   terrain_class = 'OpenField',
    #                                                   average_roof_pitch = 20.0,
    #                                                   windows = self.window_dict,
    #                                                   vents = self.vent_dict,
    #                                                   leaks = self.leaks_dict,
    #                                                   combustion_appliances = self.combustion_appliances_dict,
    #                                                   ATDs = {1: AirTerminalDevices(0.5, 20)},
    #                                                   mech_vents = self.mech_vents,
    #                                                   detailed_output_heating_cooling = False,
    #                                                   altitude = 0,
    #                                                   total_volume = 250.0,
    #                                                   ventilation_zone_base_height = 2.5
    #                                                   )
    #
    #         T_z = 299.15
    #         p_z_ref = 0.5
    #         qv_pdu = 1
    #         h_z = 100
    #         T_e = 290
    #         self.assertAlmostEqual(self.infil_vent.calculate_qv_pdu(qv_pdu, p_z_ref, T_z, T_e, h_z), -0.8552256542480364)
    #
    #     def test_implicit_formula_for_qv_pdu(self):
    #         """ Test that implicit_formula_for_qv_pdu returns the correct value """
    #         T_z = 299.15
    #         p_z_ref = 0.5
    #         qv_pdu = 1
    #         h_z = 100
    #         T_e = 290
    #         self.assertAlmostEqual(self.infil_vent.implicit_formula_for_qv_pdu(qv_pdu, p_z_ref, T_z, T_e, h_z), -37.74943189726997)

    def test_calculate_internal_reference_pressure(self):
        """Returns -2.7081717145999975"""
        initial_p_z_ref_guess = 0
        temp_int_air = 20
        R_v_arg = 1
        R_w_arg = 0.5
        self.assertAlmostEqual(
            self.infil_vent.calculate_internal_reference_pressure(
                initial_p_z_ref_guess=initial_p_z_ref_guess,
                wind_speed=self.windspeed[0],
                wind_direction=Orientation360(self.wind_direction[0]),
                temp_interior_air=temp_int_air,
                temp_exterior_air=self.airtemp[0],
                R_v_arg=R_v_arg,
                R_w_arg=R_w_arg,
            ),
            -2.7081717145999975,
        )

    def test_calculate_internal_reference_pressure_warning(self):
        """Test that calculate_internal_reference_pressure skips RuntimeWarnings from root_scalar"""
        with patch(
            "hem_core.space_heat_demand.ventilation.root_scalar", side_effect=RuntimeWarning
        ):
            with self.assertRaises(RuntimeError):
                self.infil_vent.calculate_internal_reference_pressure(
                    initial_p_z_ref_guess=0,
                    wind_speed=10,
                    wind_direction=Orientation360(20),
                    temp_interior_air=20,
                    temp_exterior_air=20,
                    R_v_arg=1,
                    R_w_arg=0.5,
                )

    def test_calculate_internal_reference_pressure_exception(self):
        """Test that calculate_internal_reference_pressure throws on ValueError and Exception"""
        with patch(
            "hem_core.space_heat_demand.ventilation.root_scalar",
            side_effect=ValueError("Some root scalar exception"),
        ):
            with self.assertRaises(ValueError) as context:
                self.infil_vent.calculate_internal_reference_pressure(
                    initial_p_z_ref_guess=0,
                    wind_speed=10,
                    wind_direction=Orientation360(20),
                    temp_interior_air=20,
                    temp_exterior_air=20,
                    R_v_arg=1,
                    R_w_arg=0.5,
                )
            self.assertIn("Some root scalar exception", str(context.exception))

        with patch("hem_core.space_heat_demand.ventilation.root_scalar", side_effect=Exception):
            with self.assertRaises(RuntimeError):
                self.infil_vent.calculate_internal_reference_pressure(
                    initial_p_z_ref_guess=0,
                    wind_speed=10,
                    wind_direction=Orientation360(20),
                    temp_interior_air=20,
                    temp_exterior_air=20,
                    R_v_arg=1,
                    R_w_arg=0.5,
                )

    def test_implicit_mass_balance_for_internal_reference_pressure_components(self):
        """Test that implicit_mass_balance_for_internal_reference_pressure_components returns the correct values"""
        self.infil_vent = InfiltrationVentilation(
            simulation_time=self.simtime,
            f_cross=True,
            shield_class=VentilationShieldClass.OPEN,
            terrain_class=TerrainClass.OPEN_FIELD,
            average_roof_pitch=20.0,
            windows=self.window_dict,
            vents=self.vent_dict,
            leaks=self.leaks_dict,
            combustion_appliances=self.combustion_appliances_dict,
            # TODO uncomment when re-implementing ATDs
            # ATDs = {1: AirTerminalDevices(0.5, 20)},
            ATDs={},
            mech_vents=self.mech_vents,
            detailed_output_heating_cooling=True,
            altitude=0,
            total_volume=250.0,
            ventilation_zone_base_height=2.5,
        )

        # Check results for positive qv_pdu
        qm_in, qm_out, qm_in_effective_heat_recovery_saving_total = (
            self.infil_vent._InfiltrationVentilation__implicit_mass_balance_for_internal_reference_pressure_components(  # type: ignore[AttributeAccessIssue]
                p_z_ref=5,
                wind_speed=10,
                wind_direction=Orientation360(10),
                temp_interior_air=10,
                temp_exterior_air=20,
                R_v_arg=0.1,
                R_w_arg_min_max=0.1,
                reporting_flag=True,
            )
        )
        self.assertAlmostEqual(qm_in, 6122.336725163513)
        self.assertAlmostEqual(qm_out, -124.95154408329704)
        self.assertAlmostEqual(qm_in_effective_heat_recovery_saving_total, 0.0)

        # Check results for negative qv_pdu
        qm_in, qm_out, qm_in_effective_heat_recovery_saving_total = (
            self.infil_vent._InfiltrationVentilation__implicit_mass_balance_for_internal_reference_pressure_components(  # type: ignore[AttributeAccessIssue]
                p_z_ref=5,
                wind_speed=10,
                wind_direction=Orientation360(10),
                temp_interior_air=10,
                temp_exterior_air=30,
                R_v_arg=0.1,
                R_w_arg_min_max=0.1,
                reporting_flag=True,
            )
        )
        self.assertAlmostEqual(qm_in, 5868.964503688903)
        self.assertAlmostEqual(qm_out, -117.00132730163227)
        self.assertAlmostEqual(qm_in_effective_heat_recovery_saving_total, 0.0)

        results = self.infil_vent.output_vent_results()

        expected_results = [
            [
                0,
                True,
                0.1,
                5084.99728003614,
                250.0,
                20.339989120144562,
                10,
                5,
                6054.2676951076,
                0.0,
                18.072440880918208,
                0.0,
                49.99658917499436,
                -124.26595718589283,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                -0.6855868974042028,
                0.0,
                6122.336725163513,
                -124.95154408329704,
            ],
            [
                0,
                True,
                0.1,
                5040.837181234225,
                250.0,
                20.1633487249369,
                10,
                5,
                5801.823062932729,
                0.0,
                17.318874814724566,
                0.0,
                49.822565941449234,
                -116.31574040422807,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                -0.6855868974042028,
                0.0,
                5868.964503688903,
                -117.00132730163227,
            ],
        ]

        # Check detailed results
        self.assertEqual(len(results), 2)
        self.assertEqual(len(results[0]), 23)
        self.assertEqual(len(results[1]), 23)
        for i in range(23):
            self.assertAlmostEqual(results[0][i], expected_results[0][i])
            self.assertAlmostEqual(results[1][i], expected_results[1][i])

    def test_implicit_mass_balance_for_internal_reference_pressure(self):
        """returns -21682.238264921532"""
        p_z_ref = 1
        temp_int_air = 20
        R_v_arg = 1
        R_w_arg_min_max = 1
        self.assertAlmostEqual(
            cast(
                float,
                self.infil_vent.implicit_mass_balance_for_internal_reference_pressure(
                    p_z_ref=p_z_ref,
                    wind_speed=self.windspeed[0],
                    wind_direction=Orientation360(self.wind_direction[0]),
                    temp_interior_air=temp_int_air,
                    temp_exterior_air=self.airtemp[0],
                    R_v_arg=R_v_arg,
                    R_w_arg_min_max=R_w_arg_min_max,
                ),
            ),
            -21682.238264921532,
        )

    def test_incoming_air_flow(self):
        """Returns 5.682004429268872"""
        p_z_ref = 1
        temp_int_air = 20
        R_v_arg = 1
        R_w_arg_min_max = 1

        self.assertAlmostEqual(
            self.infil_vent.incoming_air_flow(
                p_z_ref=p_z_ref,
                wind_speed=self.windspeed[0],
                wind_direction=Orientation360(self.wind_direction[0]),
                temp_interior_air=temp_int_air,
                temp_exterior_air=self.airtemp[0],
                R_v_arg=R_v_arg,
                R_w_arg_min_max=R_w_arg_min_max,
                reporting_flag="min",
                report_effective_flow_rate=False,
            ),
            5.682004429268872,
        )
        self.assertAlmostEqual(
            self.infil_vent.incoming_air_flow(
                p_z_ref=p_z_ref,
                wind_speed=self.windspeed[0],
                wind_direction=Orientation360(self.wind_direction[0]),
                temp_interior_air=temp_int_air,
                temp_exterior_air=self.airtemp[0],
                R_v_arg=R_v_arg,
                R_w_arg_min_max=R_w_arg_min_max,
                reporting_flag="min",
                report_effective_flow_rate=True,
            ),
            2.2877920084276107,
        )

    def test_find_R_v_arg_within_bounds(self):
        # Checking for ach_target = ach_max
        ach_min = 0.3
        ach_max = 1
        temp_int_air = 20
        initial_R_v_arg = 1
        expected_output = 0.0
        self.assertAlmostEqual(
            self.infil_vent.find_R_v_arg_within_bounds(
                ach_min=ach_min,
                ach_max=ach_max,
                initial_R_v_arg=initial_R_v_arg,
                wind_speed=20,
                wind_direction=Orientation360(self.wind_direction[0]),
                temp_interior_air=temp_int_air,
                temp_exterior_air=self.airtemp[0],
                R_w_arg=0,
                initial_p_z_ref_guess=0,
                reporting_flag=None,
            ),
            expected_output,
        )

        # Checking for ach_target = ach_min
        ach_min = 1.0
        ach_max = 1.4
        temp_int_air = 20
        initial_R_v_arg = 0.6
        expected_output = 0.5452009507146588
        self.assertAlmostEqual(
            self.infil_vent.find_R_v_arg_within_bounds(
                ach_min=ach_min,
                ach_max=ach_max,
                initial_R_v_arg=initial_R_v_arg,
                wind_speed=20,
                wind_direction=Orientation360(self.wind_direction[0]),
                temp_interior_air=temp_int_air,
                temp_exterior_air=self.airtemp[0],
                R_w_arg=0,
                initial_p_z_ref_guess=0,
                reporting_flag=None,
            ),
            expected_output,
        )

    def test_find_R_v_arg_within_bounds_min_over_max(self):
        """Test that find_R_v_arg_within_bounds throws if ach_min is over ach_max"""
        ach_min = 1.4
        ach_max = 1.0
        with self.assertRaises(ValueError):
            self.infil_vent.find_R_v_arg_within_bounds(
                ach_min=ach_min,
                ach_max=ach_max,
                initial_R_v_arg=0.4,
                wind_speed=20,
                wind_direction=Orientation360(self.wind_direction[0]),
                temp_interior_air=20,
                temp_exterior_air=self.airtemp[0],
                R_w_arg=0,
                initial_p_z_ref_guess=0,
                reporting_flag=None,
            )

    def test_find_R_v_arg_within_bounds_below_min_vents(self):
        """Test that find_R_v_arg_within_bounds returns the correct value if ach is below ach_min and ach_vent_open is above"""
        ach_min = 1.5
        ach_max = 20
        self.assertEqual(
            self.infil_vent.find_R_v_arg_within_bounds(
                ach_min=ach_min,
                ach_max=ach_max,
                initial_R_v_arg=0.6,
                wind_speed=20,
                wind_direction=Orientation360(self.wind_direction[0]),
                temp_interior_air=20,
                temp_exterior_air=self.airtemp[0],
                R_w_arg=0,
                initial_p_z_ref_guess=0,
                reporting_flag=None,
            ),
            0.810203913567427,
        )

    def test_find_R_v_arg_within_bounds_below_min(self):
        """Test that find_R_v_arg_within_bounds returns 1 if ach is below ach_min"""
        ach_min = 10
        ach_max = 20
        self.assertEqual(
            self.infil_vent.find_R_v_arg_within_bounds(
                ach_min=ach_min,
                ach_max=ach_max,
                initial_R_v_arg=0.6,
                wind_speed=20,
                wind_direction=Orientation360(self.wind_direction[0]),
                temp_interior_air=20,
                temp_exterior_air=self.airtemp[0],
                R_w_arg=0,
                initial_p_z_ref_guess=0,
                reporting_flag=None,
            ),
            1.0,
        )

    def test_find_R_v_arg_within_bounds_above_max(self):
        """Test that find_R_v_arg_within_bounds returns 0 if ach is above ach_max"""
        ach_min = 0.1
        ach_max = 0.2
        self.assertEqual(
            self.infil_vent.find_R_v_arg_within_bounds(
                ach_min=ach_min,
                ach_max=ach_max,
                initial_R_v_arg=0.4,
                wind_speed=20,
                wind_direction=Orientation360(self.wind_direction[0]),
                temp_interior_air=20,
                temp_exterior_air=self.airtemp[0],
                R_w_arg=0,
                initial_p_z_ref_guess=0,
                reporting_flag=None,
            ),
            0.0,
        )

    def test_find_R_v_arg_within_bounds_warn_on_exception(self):
        """Test that find_R_v_arg_within_bounds throws a RuntimeError if there is an exception in minimize_scalar"""
        with patch("hem_core.space_heat_demand.ventilation.minimize_scalar", side_effect=Exception):
            with self.assertRaises(RuntimeError):
                self.infil_vent.find_R_v_arg_within_bounds(
                    ach_min=1,
                    ach_max=1.6,
                    initial_R_v_arg=1.4,
                    wind_speed=20,
                    wind_direction=Orientation360(self.wind_direction[0]),
                    temp_interior_air=20,
                    temp_exterior_air=self.airtemp[0],
                    R_w_arg=0,
                    initial_p_z_ref_guess=0,
                    reporting_flag=None,
                )

    @patch.object(InfiltrationVentilation, "calc_air_changes_per_hour")
    def test_ach_within_bounds(self, mock_calc_ach):
        # Set up the mock to return a value within bounds
        mock_calc_ach.return_value = 2.0

        result = self.infil_vent.find_R_v_arg_within_bounds(
            ach_min=1.5,
            ach_max=2.5,
            initial_R_v_arg=0.5,
            wind_speed=5.0,
            wind_direction=Orientation360(90.0),
            temp_interior_air=20.0,
            temp_exterior_air=10.0,
            R_w_arg=1.0,
            initial_p_z_ref_guess=0.5,
            reporting_flag=None,
        )
        self.assertEqual(result, 0.5)

    @patch.object(InfiltrationVentilation, "calc_air_changes_per_hour")
    def test_no_ach_target(self, mock_calc_ach):
        # Set up the mock to return an initial value
        mock_calc_ach.return_value = 2.0

        result = self.infil_vent.find_R_v_arg_within_bounds(
            ach_min=None,
            ach_max=None,
            initial_R_v_arg=0.5,
            wind_speed=5.0,
            wind_direction=Orientation360(90.0),
            temp_interior_air=20.0,
            temp_exterior_air=10.0,
            R_w_arg=1.0,
            initial_p_z_ref_guess=0.5,
            reporting_flag=None,
        )
        self.assertEqual(result, 0.5)

    def test_calc_internal_gains_ductwork(self):
        outside_temp = [21.0, 15.0]
        inside_temp = [19.75, 19.25]

        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertAlmostEqual(
                    self.infil_vent.calc_internal_gains_ductwork(
                        outside_temp[t_idx], inside_temp[t_idx]
                    ),
                    [
                        0.23131013888888893,
                        -0.7864544722222223,
                    ][t_idx],
                    msg="incorrect total duct heat loss returned",
                )
