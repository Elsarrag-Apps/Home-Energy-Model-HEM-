import unittest
from unittest.mock import MagicMock, patch

from hem_core.controls.time_control import SetpointTimeControl
from hem_core.energy_supply.energy_supply import EnergySupply
from hem_core.external_conditions import ExternalConditions
from hem_core.heating_systems import WaterSupplyBase
from hem_core.heating_systems.heat_pump import HeatPump_HWOnly, HWHeatPumpData
from hem_core.heating_systems.storage_tank import (
    ImmersionHeater,
    PipeworkData,
    PVDiverter,
    SmartHotWaterTank,
    SolarThermalSystem,
    StorageTank,
)
from hem_core.input_output import enums
from hem_core.input_output.enums import (
    FuelType,
    PipeworkContents,
    SolarCollectorLoopLocation,
    WaterPipeworkLocation,
)
from hem_core.pipework import Pipework
from hem_core.simulation_time import SimulationTime
from hem_core.units import Orientation360
from hem_core.water_heat_demand.cold_water_source import ColdWaterSource
from hem_core.water_heat_demand.dhw_demand import WaterEventResult


def get_event_data_solthermal() -> list[list[WaterEventResult] | None]:
    return [
        None,
        [
            WaterEventResult(
                type="Shower",
                temperature_warm=41.0,
                volume_warm=48.0,
                volume_hot=30.5956261482843,
                event_duration=0.0,
            )
        ],
        None,
        [
            WaterEventResult(
                type="Shower",
                temperature_warm=45.0,
                volume_warm=48.0,
                volume_hot=36.4281898110265,
                event_duration=0.0,
            ),
        ],
        None,
        [
            WaterEventResult(
                type="Shower",
                temperature_warm=41.0,
                volume_warm=52.0,
                volume_hot=34.4038433055010,
                event_duration=0.0,
            ),
        ],
        None,
        None,
        None,
        [
            WaterEventResult(
                type="Shower",
                temperature_warm=41.0,
                volume_warm=48.0,
                volume_hot=33.3416695316938,
                event_duration=0.0,
            ),
        ],
        None,
        [],
        None,
        [
            WaterEventResult(
                type="Shower",
                temperature_warm=41.0,
                volume_warm=52.0,
                volume_hot=40.521971319747124,
                event_duration=0.0,
            ),
        ],
        None,
        None,
        None,
        [
            WaterEventResult(
                type="Shower",
                temperature_warm=41.0,
                volume_warm=48.0,
                volume_hot=30.5956261482843,
                event_duration=0.0,
            ),
        ],
        None,
        [
            WaterEventResult(
                type="Shower",
                temperature_warm=45.0,
                volume_warm=48.0,
                volume_hot=36.42818981102645,
                event_duration=0.0,
            ),
        ],
        None,
        [
            WaterEventResult(
                type="Shower",
                temperature_warm=41.0,
                volume_warm=52.0,
                volume_hot=34.40384330550096,
                event_duration=0.0,
            ),
        ],
        None,
        None,
    ]


def get_event_data_immersion() -> list[list[WaterEventResult] | None]:
    return [
        [
            WaterEventResult(
                type="Shower",
                temperature_warm=41.0,
                volume_warm=48.0,
                volume_hot=33.0666666666667,
                event_duration=0.0,
            ),
            WaterEventResult(
                type="Bath",
                temperature_warm=43.0,
                volume_warm=100.0,
                volume_hot=73.3333333333333,
                event_duration=0.0,
            ),
            WaterEventResult(
                type="Other",
                temperature_warm=40.0,
                volume_warm=8.0,
                volume_hot=5.3333333333333,
                event_duration=0.0,
            ),
        ],
        [
            WaterEventResult(
                type="Shower",
                temperature_warm=41.0,
                volume_warm=48.0,
                volume_hot=33.0334075723831,
                event_duration=0.0,
            ),
        ],
        None,
        [
            WaterEventResult(
                type="Shower",
                temperature_warm=45.0,
                volume_warm=48.0,
                volume_hot=37.8988082756996,
                event_duration=0.0,
            ),
        ],
        None,
        [
            WaterEventResult(
                type="Shower",
                temperature_warm=41.0,
                volume_warm=52.0,
                volume_hot=35.4545454545455,
                event_duration=0.0,
            ),
        ],
        None,
        None,
    ]


def get_usage_event() -> list[WaterEventResult] | None:
    return get_event_data_immersion()[0]


class DummyProject:
    def __init__(self, temp_internal_air: float):
        self.__temp_internal_air = temp_internal_air

    def temp_internal_air_prev_timestep(self) -> float:
        return self.__temp_internal_air


class Test_StorageTank(unittest.TestCase):
    """Unit tests for StorageTank class"""

    def setUp(self):
        """Create StorageTank object to be tested"""
        self.coldwatertemps = [10.0, 10.1, 10.2, 10.5, 10.6, 11.0, 11.5, 12.1]
        self.simtime = SimulationTime(start_time=0, end_time=8, step=1)
        self.coldfeed = ColdWaterSource(
            cold_water_temps=self.coldwatertemps,
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )
        self.controlmin = SetpointTimeControl(
            schedule=[52.0, None, None, None, 52.0, 52.0, 52.0, 52.0],
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )
        self.controlmax = SetpointTimeControl(
            schedule=[55.0, 55.0, 55.0, 55.0, 55.0, 55.0, 55.0, 55.0],
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )
        self.controlmax2 = SetpointTimeControl(
            schedule=[60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0],
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )
        self.energysupply = EnergySupply(
            fuel_type=FuelType.ELECTRICITY, simulation_time=self.simtime
        )
        self.energysupplyconn = self.energysupply.connection("immersion")
        self.imheater = ImmersionHeater(
            rated_power=50.0,
            energy_supply_conn=self.energysupplyconn,
            simulation_time=self.simtime,
            controlmin=self.controlmin,
            controlmax=self.controlmax,
        )
        self.heat_source_dict = {self.imheater: (0.1, 0.33)}
        self.windspeed = [3.7, 3.8, 3.9, 4.0, 4.1, 4.2, 4.3, 4.4]
        self.wind_direction = [Orientation360.create_from_180(0.0)] * 8
        self.energy_supply_conn_name_auxiliary = "Boiler_auxiliary"
        self.airtemp = [0.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 20.0]
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
            {"number": 1, "start": 180, "end": 135},
            {"number": 2, "start": 135, "end": 90},
            {"number": 3, "start": 90, "end": 45},
            {"number": 4, "start": 45, "end": 0},
            {"number": 5, "start": 0, "end": -45},
            {"number": 6, "start": -45, "end": -90},
            {"number": 7, "start": -90, "end": -135},
            {"number": 8, "start": -135, "end": -180},
        ]
        self.extcond = ExternalConditions(
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
        self.storagetank = StorageTank(
            volume=150.0,
            losses=1.68,
            init_temp=55.0,
            cold_feed=self.coldfeed,
            simulation_time=self.simtime,
            heat_source_dict=self.heat_source_dict,
            project=DummyProject(temp_internal_air=20.0),
            external_conditions=self.extcond,
            detailed_output=True,
        )

        # Also test case where heater does not heat all layers, to ensure this is handled correctly
        self.energysupplyconn2 = self.energysupply.connection("immersion2")
        self.imheater2 = ImmersionHeater(
            rated_power=5.0,
            energy_supply_conn=self.energysupplyconn2,
            simulation_time=self.simtime,
            controlmin=self.controlmin,
            controlmax=self.controlmax2,
        )
        self.heat_source_dict2 = {self.imheater2: (0.6, 0.6)}
        self.storagetank2 = StorageTank(
            volume=210.0,
            losses=1.61,
            init_temp=60.0,
            cold_feed=self.coldfeed,
            simulation_time=self.simtime,
            heat_source_dict=self.heat_source_dict2,
            project=DummyProject(temp_internal_air=20.0),
            external_conditions=self.extcond,
        )

        # Also test case where the cold feed is a pre-heated source
        energysupplyconn3 = self.energysupply.connection("immersion3")
        imheater3 = ImmersionHeater(
            rated_power=5.0,
            energy_supply_conn=energysupplyconn3,
            simulation_time=self.simtime,
            controlmin=self.controlmin,
            controlmax=self.controlmax,
        )
        heat_source_dict3 = {imheater3: (0.6, 0.6)}
        preheatfeed = StorageTank(
            volume=80.0,
            losses=1.61,
            init_temp=30.0,
            cold_feed=self.coldfeed,
            simulation_time=self.simtime,
            heat_source_dict=None,
            project=DummyProject(temp_internal_air=20.0),
            external_conditions=self.extcond,
        )
        self.storagetank3 = StorageTank(
            volume=210.0,
            losses=1.61,
            init_temp=52.0,
            cold_feed=preheatfeed,
            simulation_time=self.simtime,
            heat_source_dict=heat_source_dict3,
            project=DummyProject(temp_internal_air=20.0),
            external_conditions=self.extcond,
        )

        # Also test case where the heater is a SolarThermalSystem
        coldwatertemps = [
            17.0,
            17.1,
            17.2,
            17.3,
            17.4,
            17.5,
            17.6,
            17.7,
            17.0,
            17.1,
            17.2,
            17.3,
            17.4,
            17.5,
            17.6,
            17.7,
            17.0,
            17.1,
            17.2,
            17.3,
            17.4,
            17.5,
            17.6,
            17.7,
        ]
        self.simtime_solthermal = SimulationTime(start_time=5088, end_time=5112, step=1)
        coldfeed = ColdWaterSource(
            cold_water_temps=coldwatertemps,
            simulation_time=self.simtime_solthermal,
            start_day=212,
            time_series_step=1,
        )
        self.controlmax_solthermal = SetpointTimeControl(
            schedule=[
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
            ],
            simulation_time=self.simtime_solthermal,
            start_day=212,
            time_series_step=1,
        )
        self.energysupply_solthermal = EnergySupply(
            fuel_type=FuelType.ELECTRICITY, simulation_time=self.simtime_solthermal
        )
        energy_supply_from_environment = EnergySupply(
            fuel_type=enums.FuelType.ENERGY_FROM_ENVIRONMENT,
            simulation_time=self.simtime_solthermal,
        )

        self.energysupplyconnst_solthermal = self.energysupply_solthermal.connection("solthermal")
        self.energy_supply_from_environment_conn = energy_supply_from_environment.connection(
            "SolarThermalSystem"
        )
        proj_dict = {
            "ExternalConditions": {
                "air_temperatures": [
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                ],
                "wind_speeds": [
                    3.9,
                    3.8,
                    3.9,
                    4.1,
                    3.8,
                    4.2,
                    4.3,
                    4.1,
                    3.9,
                    3.8,
                    3.9,
                    4.1,
                    3.8,
                    4.2,
                    4.3,
                    4.1,
                    3.9,
                    3.8,
                    3.9,
                    4.1,
                    3.8,
                    4.2,
                    4.3,
                    4.1,
                ],
                "wind_directions": [
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
                ],
                "diffuse_horizontal_radiation": [
                    0,
                    0,
                    0,
                    0,
                    35,
                    73,
                    139,
                    244,
                    320,
                    361,
                    369,
                    348,
                    318,
                    249,
                    225,
                    198,
                    121,
                    68,
                    19,
                    0,
                    0,
                    0,
                    0,
                    0,
                ],
                "direct_beam_radiation": [
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    7,
                    53,
                    63,
                    164,
                    339,
                    242,
                    315,
                    577,
                    385,
                    285,
                    332,
                    126,
                    7,
                    0,
                    0,
                    0,
                    0,
                    0,
                ],
                "solar_reflectivity_of_ground": [
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                ],
                "latitude": 51.383,
                "longitude": -0.783,
                "timezone": 0,
                "start_day": 212,
                "end_day": 212,
                "time_series_step": 1,
                "january_first": 1,
                "daylight_savings": "not applicable",
                "leap_day_included": False,
                "direct_beam_conversion_needed": False,
                "shading_segments": [
                    {"number": 1, "start": 180, "end": 135},
                    {"number": 2, "start": 135, "end": 90},
                    {"number": 3, "start": 90, "end": 45},
                    {
                        "number": 4,
                        "start": 45,
                        "end": 0,
                        "shading": [{"type": "obstacle", "height": 10.5, "distance": 12}],
                    },
                    {"number": 5, "start": 0, "end": -45},
                    {"number": 6, "start": -45, "end": -90},
                    {"number": 7, "start": -90, "end": -135},
                    {"number": 8, "start": -135, "end": -180},
                ],
            }
        }
        self.__external_conditions_solthermal = ExternalConditions(
            self.simtime_solthermal,
            proj_dict["ExternalConditions"]["air_temperatures"],
            proj_dict["ExternalConditions"]["wind_speeds"],
            proj_dict["ExternalConditions"]["wind_directions"],
            proj_dict["ExternalConditions"]["diffuse_horizontal_radiation"],
            proj_dict["ExternalConditions"]["direct_beam_radiation"],
            proj_dict["ExternalConditions"]["solar_reflectivity_of_ground"],
            proj_dict["ExternalConditions"]["latitude"],
            proj_dict["ExternalConditions"]["longitude"],
            proj_dict["ExternalConditions"]["timezone"],
            proj_dict["ExternalConditions"]["start_day"],
            proj_dict["ExternalConditions"]["end_day"],
            proj_dict["ExternalConditions"]["time_series_step"],
            proj_dict["ExternalConditions"]["january_first"],
            proj_dict["ExternalConditions"]["daylight_savings"],
            proj_dict["ExternalConditions"]["leap_day_included"],
            proj_dict["ExternalConditions"]["direct_beam_conversion_needed"],
            proj_dict["ExternalConditions"]["shading_segments"],
        )
        self.solthermal = SolarThermalSystem(
            sol_loc=SolarCollectorLoopLocation.OUT,
            area_module=3,
            modules=1,
            peak_collector_efficiency=0.8,
            incidence_angle_modifier=0.9,
            first_order_hlc=3.5,
            second_order_hlc=0,
            collector_mass_flow_rate=1,
            power_pump=100,
            power_pump_control=10,
            energy_supply_conn=self.energysupplyconnst_solthermal,
            tilt=30,
            orientation=Orientation360.create_from_180(0),
            solar_loop_piping_hlc=0.5,
            ext_cond=self.__external_conditions_solthermal,
            simulation_time=self.simtime_solthermal,
            project=DummyProject(20),
            controlmax=self.controlmax_solthermal,
            energy_supply_from_environment_conn=self.energy_supply_from_environment_conn,
        )

        heat_source_dict = {self.solthermal: (0.1, 0.33)}

        self.storagetank_solthermal = StorageTank(
            volume=150.0,
            losses=1.68,
            init_temp=55.0,
            cold_feed=coldfeed,
            simulation_time=self.simtime_solthermal,
            heat_source_dict=heat_source_dict,
            project=DummyProject(temp_internal_air=20.0),
            external_conditions=self.__external_conditions_solthermal,
        )

        self.heat_dict: dict[str, HWHeatPumpData] = {
            "M": {
                "cop_dhw": 2.7,
                "hw_tapping_prof_daily_total": 5.845,
                "energy_input_measured": 2.15,
                "power_standby": 0.02,
                "hw_vessel_loss_daily": 1.18,
            },
            "L": {
                "cop_dhw": 2.5,
                "hw_tapping_prof_daily_total": 11.655,
                "energy_input_measured": 4.6,
                "power_standby": 0.03,
                "hw_vessel_loss_daily": 1.6,
            },
        }
        self.energysupplyconnection_heat_pump = self.energysupply.connection("end_user_name")

        self.power_max = 3.0
        self.vol_daily_average = 150.0
        self.tank_volume = 200.0
        self.daily_losses = 1.5
        self.heat_exchanger_surface_area = 1.2
        self.in_use_factor_mismatch = 0.6
        self.tank_volume_declared = 180.0
        self.heat_exchanger_surface_area_declared = 1.0
        self.daily_losses_declared = 1.2

        self.heat_pump = HeatPump_HWOnly(
            power_max=self.power_max,
            test_data=self.heat_dict,
            vol_daily_average=self.vol_daily_average,
            tank_volume=self.tank_volume,
            daily_losses=self.daily_losses,
            heat_exchanger_surface_area=self.heat_exchanger_surface_area,
            in_use_factor_mismatch=self.in_use_factor_mismatch,
            tank_volume_declared=self.tank_volume_declared,
            heat_exchanger_surface_area_declared=self.heat_exchanger_surface_area_declared,
            daily_losses_declared=self.daily_losses_declared,
            energy_supply_conn=self.energysupplyconnection_heat_pump,
            simulation_time=self.simtime,
            controlmin=self.controlmin,
            controlmax=self.controlmax,
        )

        self.heat_source_dict_heat_pump = {self.heat_pump: (0.1, 0.33)}

        self.storagetank_heat_pump = StorageTank(
            volume=150.0,
            losses=self.daily_losses,
            init_temp=55.0,
            cold_feed=self.coldfeed,
            simulation_time=self.simtime,
            heat_source_dict=self.heat_source_dict_heat_pump,
            project=DummyProject(temp_internal_air=20.0),
            external_conditions=self.extcond,
        )

        self.heat_source_dict_heat_pump = {self.heat_pump: (0.1, 0.33)}

    def test_demand_hot_water(self):
        # Expected results for the unit test
        event_data = get_event_data_immersion()
        expected_temperatures_1 = [
            [55.0, 55.0, 55.0, 55.0],
            [15.448000000000006, 54.595555555555556, 54.595555555555556, 54.595555555555556],
            [15.448000000000006, 54.19530534979424, 54.19530534979424, 54.19530534979424],
            [10.5, 15.39537857738237, 53.39140601130916, 53.79920588690748],
            [55.0, 55.0, 55.0, 55.0],
            [13.400000000000002, 54.595555555555556, 54.595555555555556, 54.595555555555556],
            [13.400000000000002, 54.19530534979424, 54.19530534979424, 54.19530534979424],
            [13.400000000000002, 53.79920588690749, 53.79920588690749, 53.79920588690749],
        ]

        expected_temperatures_2 = [
            [10.0, 24.55607367670878, 60.0, 60.0],
            [10.056616089321501, 16.312757933665832, 39.76314001211786, 59.687654320987654],
            [10.056616089321501, 16.31053773845771, 39.59445105524171, 59.37752591068435],
            [10.342751590114434, 12.274601927758184, 24.50747434931655, 46.393323819752034],
            [10.342751590114434, 12.274601927758184, 60.0, 60.0],
            [10.741316223514428, 11.103100848370719, 60.0, 60.0],
            [10.741316223514428, 11.103100848370719, 59.687654320987654, 59.687654320987654],
            [10.741316223514428, 11.103100848370719, 59.37752591068435, 59.37752591068435],
        ]

        # Loop through the timesteps and the associated data pairs using `subTest`
        for t_idx, _, _ in self.simtime:  # Assuming simtime generates correct time indices
            usage_events = event_data[t_idx]

            # Convert usage events based on HW temp of 55 to equivalent 60:
            usage_events2 = []
            temp_hot = 60.0 if t_idx == 0 else expected_temperatures_2[t_idx - 1][-1]
            if usage_events is not None:
                for event in usage_events:
                    volume_hot = (
                        event.volume_warm
                        * (event.temperature_warm - self.coldwatertemps[t_idx])
                        / (temp_hot - self.coldwatertemps[t_idx])
                    )
                    usage_events2.append(
                        WaterEventResult(
                            type=event.type,
                            temperature_warm=event.temperature_warm,
                            volume_warm=event.volume_warm,
                            volume_hot=volume_hot,
                            event_duration=0.0,
                        )
                    )

            with self.subTest(timestep=t_idx):
                self.storagetank.demand_hot_water(usage_events=usage_events)

                # Verify the temperatures against expected results
                for i in range(len(self.storagetank._temp_n)):
                    self.assertAlmostEqual(
                        first=self.storagetank._temp_n[i],
                        second=expected_temperatures_1[t_idx][i],
                        msg="incorrect temperatures returned",
                    )

                self.assertAlmostEqual(
                    first=self.energysupply.results_by_end_user()["immersion"][t_idx],
                    second=[5.9141614815, 0.0, 0.0, 0.0, 3.8585103966, 0.0, 0.0, 0.0][t_idx],
                    msg="incorrect energy supplied returned",
                )

                self.storagetank2.demand_hot_water(usage_events=usage_events2)

                # Verify the temperatures against expected results
                for i in range(len(self.storagetank._temp_n)):
                    self.assertAlmostEqual(
                        first=self.storagetank2._temp_n[i],
                        second=expected_temperatures_2[t_idx][i],
                        msg="incorrect temperatures returned in case where heater does not heat all layers",
                    )

                self.assertAlmostEqual(
                    first=self.energysupply.results_by_end_user()["immersion2"][t_idx],
                    second=[
                        0.6719988461,
                        0.0,
                        0.0,
                        0.0,
                        3.0339862161,
                        1.8040212455,
                        0.0,
                        0.0,
                    ][t_idx],
                    msg="incorrect energy supplied returned in case where heater does not heat all layers",
                )
                self.assertTrue(
                    self.storagetank.output_results(),
                    msg="List have to contain some entries",
                )

    def test_demand_hot_water_solthermal(self):
        event_data = get_event_data_solthermal()
        for t_idx, _, _ in self.simtime_solthermal:
            usage_events = event_data[t_idx]
            with self.subTest(timestep=t_idx):
                self.storagetank_solthermal.demand_hot_water(usage_events=usage_events)
                self.assertAlmostEqual(
                    self.storagetank_solthermal.test_energy_demand(),
                    [
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                        0.39440131536356493,
                        0.8431945125549533,
                        1.3874298880308749,
                        1.092014226211686,
                        1.1503560996860809,
                        1.484510483919223,
                        0.9003607869563452,
                        0.4981024012117776,
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                    ][t_idx],
                    msg="incorrect energy demand from tank",
                )

    def test_temp_surrounding_primary_pipework(self):
        # External Pipe
        self.pipework = Pipework(
            location=WaterPipeworkLocation.EXTERNAL,
            internal_diameter=0.025,
            external_diameter=0.027,
            length=1.0,
            insulation_thermal_conductivity=0.035,
            insulation_thickness=0.038,
            reflective=False,
            contents=PipeworkContents.WATER,
        )
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    first=self.storagetank.get_temperature_surrounding_primary_pipework(
                        pipework_data=self.pipework
                    ),
                    second=[0.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 20.0][t_idx],
                )

        # Internal Pipe
        self.pipework = Pipework(
            location=WaterPipeworkLocation.INTERNAL,
            internal_diameter=0.025,
            external_diameter=0.027,
            length=1.0,
            insulation_thermal_conductivity=0.035,
            insulation_thickness=0.038,
            reflective=False,
            contents=PipeworkContents.WATER,
        )
        self.simtime.reset()
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    first=self.storagetank.get_temperature_surrounding_primary_pipework(
                        pipework_data=self.pipework
                    ),
                    second=[20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0][t_idx],
                )

        # Invalid pipe location
        with self.assertRaises(ValueError):
            self.pipework = Pipework(
                location="Invalid location",  # type: ignore
                internal_diameter=0.025,
                external_diameter=0.027,
                length=1.0,
                insulation_thermal_conductivity=0.035,
                insulation_thickness=0.038,
                reflective=False,
                contents=PipeworkContents.WATER,
            )
            self.storagetank.get_temperature_surrounding_primary_pipework(
                pipework_data=self.pipework
            )

    def test_get_cold_water_source(self):
        self.assertTrue(isinstance(self.storagetank.get_cold_water_source(), WaterSupplyBase))

    def test_get_temp_hot_water(self):
        self.assertEqual(
            self.storagetank.get_temp_hot_water(100.0), [(55.0, 37.5), (55.0, 37.5), (55.0, 25.0)]
        )
        self.assertEqual(
            first=self.storagetank.get_temp_hot_water(volume_req=90.0, volume_req_already=10.0),
            second=[(55.0, 27.5), (55.0, 37.5), (55.0, 25.0)],
        )

    def test_stand_by_losses_coefficient(self):
        self.assertAlmostEqual(
            first=self.storagetank.stand_by_losses_coefficient(), second=1.5555555555555556
        )

    def test_potential_energy_input(self):
        # Immersionheater as heat_source
        temp_s3_n = [55.0, 55.0, 55.0, 55.0, 55.0, 55.0, 55.0, 55.0]
        self.assertEqual(
            self.storagetank.potential_energy_input(
                temp_s3_n=temp_s3_n, heat_source=self.imheater, heater_layer=0, thermostat_layer=7
            ),
            [0.0, 0, 0, 0],
        )

        # SolarThermal as Heat source
        temp_s3_n = [
            25.0,
            15.0,
            35.0,
            45.0,
            55.0,
            50.0,
            30.0,
            20.0,
            25.0,
            15.0,
            35.0,
            45.0,
            55.0,
            50.0,
            30.0,
            20.0,
            25.0,
            15.0,
            35.0,
            45.0,
            55.0,
            50.0,
            30.0,
            20.0,
            25.0,
            15.0,
            35.0,
            45.0,
            55.0,
            50.0,
            30.0,
            20.0,
        ]

        for t_idx, _, _ in self.simtime:
            with self.subTest(timestep=t_idx):
                actual_result = self.storagetank_solthermal.potential_energy_input(
                    temp_s3_n=temp_s3_n,
                    heat_source=self.solthermal,
                    heater_layer=0,
                    thermostat_layer=7,
                )

                expected_result = [
                    [0, 0, 0, 0],
                    [0, 0, 0, 0],
                    [0, 0, 0, 0],
                    [0, 0, 0, 0],
                    [0, 0, 0, 0],
                    [0, 0, 0, 0],
                    [0, 0, 0, 0],
                    [0, 0, 0, 0],
                    [0.47214338269526945, 0, 0, 0],
                    [0.794165996101526, 0, 0, 0],
                    [1.2488375719961642, 0, 0, 0],
                    [1.0218936489635675, 0, 0, 0],
                    [1.1483985152150102, 0, 0, 0],
                    [1.5175839864027383, 0, 0, 0],
                    [0.9602170463493307, 0, 0, 0],
                    [0.5981490998786696, 0, 0, 0],
                    [0.3454397002046902, 0, 0, 0],
                    [0, 0, 0, 0],
                    [0, 0, 0, 0],
                    [0, 0, 0, 0],
                    [0, 0, 0, 0],
                    [0, 0, 0, 0],
                    [0, 0, 0, 0],
                    [0, 0, 0, 0],
                ][t_idx]

                # Compare each element using assertAlmostEqual
                for expected_value, actual_value in zip(
                    expected_result, actual_result, strict=False
                ):
                    self.assertAlmostEqual(first=expected_value, second=actual_value, places=13)

        # With heat pump as a heat source
        self.setUp()
        temp_s3_n = [55.0, 55.0, 55.0, 55.0, 55.0, 55.0, 55.0, 30.0]
        self.assertEqual(
            first=self.storagetank_heat_pump.potential_energy_input(
                temp_s3_n=temp_s3_n, heat_source=self.heat_pump, heater_layer=0, thermostat_layer=7
            ),
            second=[3.0, 0, 0, 0],
        )

    def test_storage_tank_potential_effect(self):
        energy_proposed = 0
        temp_s3_n = [25.0, 15.0, 35.0, 45.0, 55.0, 50.0, 30.0, 20.0]
        self.assertEqual(
            first=self.storagetank.storage_tank_potential_effect(
                energy_proposed=energy_proposed, temp_s3_n=temp_s3_n
            ),
            second=(20.0, 45.0),
        )

    def test_energy_input(self):
        temp_s3_n = [25.0, 15.0, 35.0, 45.0, 55.0, 50.0, 30.0, 20.0]
        Q_x_in_n = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
        self.assertEqual(
            first=self.storagetank.calc_temps_with_energy_input(
                temp_s3_n=temp_s3_n, Q_x_in_n=Q_x_in_n
            ),
            second=(5.83, [25.0, 17.294455066921607, 39.588910133843214, 51.883365200764814]),
        )

    def test_rearrange_temperatures(self):
        temp_s6_n = [2.5, 3.7, 10.36, 17.43, 32.95, 35.91, 35.91, 42.2]
        self.assertEqual(
            first=self.storagetank.rearrange_temperatures(temp_s6_n=temp_s6_n),
            second=(
                [0.10895833333333334, 0.16125833333333334, 0.45152333333333333, 0.7596575],
                [2.5, 3.7, 10.36, 17.43, 32.95, 35.91, 35.91, 42.2],
            ),
        )

    def test_thermal_losses(self):
        temp_s7_n = [12.0, 18.0, 25.0, 32.0, 37.0, 45.0, 49.0, 58.0]
        Q_x_in_n = [0, 1, 2.0, 3, 4, 5, 6, 7, 8]
        Q_h_sto_s7 = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
        heater_layer = 2
        Q_ls_n_prev_heat_source = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        setpntmax = 55.0
        self.assertEqual(
            first=self.storagetank.calc_temps_after_thermal_losses(
                temp_s7_n=temp_s7_n,
                Q_x_in_n=Q_x_in_n,
                Q_h_sto_s7=Q_h_sto_s7,
                heater_layer=heater_layer,
                Q_ls_n_prev_heat_source=Q_ls_n_prev_heat_source,
                temp_setpntmax=setpntmax,
            ),
            second=(
                36.0,
                0.012203333333333333,
                [12.0, 17.97925925925926, 24.906666666666666, 31.834074074074074],
                [0.0, 0.0009039506172839507, 0.004067777777777778, 0.007231604938271605],
            ),
        )

    def test_run_heat_sources(self):
        temp_s3_n = [5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0]
        heat_source = self.imheater
        heater_layer = 2
        thermostat_layer = 7
        Q_ls_prev_heat_source = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self.assertEqual(
            first=self.storagetank.run_heat_sources(
                temp_s3_n=temp_s3_n,
                heat_source=heat_source,
                heater_layer=heater_layer,
                thermostat_layer=thermostat_layer,
                Q_ls_prev_heat_source=Q_ls_prev_heat_source,
            ),
            second=(
                [5.0, 10.0, 55.0, 55.0],
                [0, 0, 50.0, 0],
                52.17916666666666,
                [5.0, 10.0, 1162.227533460803, 20.0],
                [5.0, 10.0, 591.1137667304015, 591.1137667304015],
                3.3040040740740793,
                0.03525407407407408,
                [0.0, 0.0, 0.01762703703703704, 0.01762703703703704],
            ),
        )

    def test_calculate_temperatures(self):
        temp_s3_n = [10.0, 15.0, 20.0, 25.0, 25.0, 30.0, 35.0, 50.0]
        heat_source = self.imheater
        Q_x_in_n = [0, 1, 2.0, 3, 4, 5, 6, 7, 8]
        heater_layer = 2
        Q_ls_n_prev_heat_source = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

        self.assertEqual(
            first=self.storagetank.calc_final_temps(
                temp_s3_n=temp_s3_n,
                heat_source=heat_source,
                Q_x_in_n=Q_x_in_n,
                heater_layer=heater_layer,
                Q_ls_n_prev_heat_source=Q_ls_n_prev_heat_source,
            ),
            second=(
                [10.0, 37.71697755116492, 55.0, 55.0],
                [0, 1, 2.0, 3, 4, 5, 6, 7, 8],
                9.050833333333333,
                [10.0, 37.944550669216056, 65.88910133843211, 93.83365200764818],
                [10.0, 37.944550669216056, 65.88910133843211, 93.83365200764818],
                33.86817074074074,
                0.04517246913580247,
                [0.0, 0.009918395061728393, 0.01762703703703704, 0.01762703703703704],
            ),
        )

        # Check edge cases for controlmax and controlmin
        with (
            patch.object(heat_source, "_ImmersionHeater__controlmax") as mock_controlmax,
            patch.object(heat_source, "_ImmersionHeater__controlmin") as mock_controlmin,
        ):
            mock_controlmax.setpnt.return_value = None
            mock_controlmin.setpnt.return_value = 50
            with self.assertRaises(ValueError):
                self.storagetank.calc_final_temps(
                    temp_s3_n=temp_s3_n,
                    heat_source=heat_source,
                    Q_x_in_n=Q_x_in_n,
                    heater_layer=heater_layer,
                    Q_ls_n_prev_heat_source=Q_ls_n_prev_heat_source,
                )
            mock_controlmax.setpnt.return_value = 30
            mock_controlmin.setpnt.return_value = 50
            with self.assertRaises(ValueError):
                self.storagetank.calc_final_temps(
                    temp_s3_n=temp_s3_n,
                    heat_source=heat_source,
                    Q_x_in_n=Q_x_in_n,
                    heater_layer=heater_layer,
                    Q_ls_n_prev_heat_source=Q_ls_n_prev_heat_source,
                )
            mock_controlmax.setpnt.return_value = None
            mock_controlmin.setpnt.return_value = None
            self.assertEqual(
                first=self.storagetank.calc_final_temps(
                    temp_s3_n=temp_s3_n,
                    heat_source=heat_source,
                    Q_x_in_n=Q_x_in_n,
                    heater_layer=heater_layer,
                    Q_ls_n_prev_heat_source=Q_ls_n_prev_heat_source,
                ),
                second=(
                    [10.0, 37.71697755116492, 65.37173288010763, 93.02648820905036],
                    [0, 1, 2.0, 3, 4, 5, 6, 7, 8],
                    9.050833333333333,
                    [10.0, 37.944550669216056, 65.88910133843211, 93.83365200764818],
                    [10.0, 37.944550669216056, 65.88910133843211, 93.83365200764818],
                    36.0,
                    0.06764592592592593,
                    [0.0, 0.009918395061728393, 0.02254864197530864, 0.03517888888888889],
                ),
            )

    def test_extract_hot_water(self):
        self.storagetank._temp_average_drawoff_volweighted = 0.0
        self.storagetank._total_volume_drawoff = 0.0

        event = WaterEventResult(
            temperature_warm=41.0,
            type="Other",
            volume_warm=8.0,
            volume_hot=5.511111111111113,
            event_duration=0.0,
        )

        # TODO improve withdrawl logic
        # Current behaviour: Volume is drawn off second layer rather
        # than top layer despite available volume in the top layer. This occurs
        # because pipework withdrawl happens in the next iteration following the event draw off.
        # Future improvement: Update logic to priortise withdrawing from the
        # current layer if sufficient volume is available.
        self.assertEqual(
            first=self.storagetank.extract_hot_water(event=event),
            second=(5.51111111111112, 0.2882311111111112, [37.5, 37.5, 37.5, 31.988888888888887]),
        )

    def test_extract_hot_water_skips_empty_layer(self):
        self.storagetank._temp_average_drawoff_volweighted = 0.0
        self.storagetank._total_volume_drawoff = 0.0

        # Test with a layer that has no volume
        event = WaterEventResult(
            temperature_warm=41.0,
            type="Other",
            volume_warm=8.0,
            volume_hot=5.511111111111113,
            event_duration=0.0,
        )
        self.storagetank._Vol_n = [37.5, 37.5, 37.5, 0.0]
        self.assertEqual(
            first=self.storagetank.extract_hot_water(event=event),
            second=(43.01111111111112, 0.2882311111111112, [37.5, 37.5, 31.988888888888887, 0.0]),
        )

    def test_calc_temps_ater_extraction(self):
        remaining_vol = [0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4]
        self.assertEqual(
            first=self.storagetank.calc_temps_after_extraction(remaining_vols=remaining_vol),
            second=([10.0, 10.0, 10.0, 16.0], False),
        )

        remaining_vol = [40.0, 40.0, 40.0, 40.0]
        self.assertEqual(
            first=self.storagetank.calc_temps_after_extraction(remaining_vols=remaining_vol),
            second=([55.0, 55.0, 55.0, 55.0], False),
        )

    def test_additional_energy_input(self):
        heat_source = self.imheater
        energy_input = 5.0
        setpnt_diverter = SetpointTimeControl(
            schedule=[60] * 8,
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )

        self.storagetank._Q_ls_n_prev_heat_source = [0.0, 0.1, 0.2, 0.3]
        self.assertEqual(
            first=self.storagetank.additional_energy_input(
                heat_source=heat_source,
                energy_input=energy_input,
                controlmax_diverter=setpnt_diverter,
            ),
            second=0.8915535802469137,
        )

        # Test with no energy input
        heat_source = self.imheater2
        energy_input = 0.0
        self.storagetank._Q_ls_n_prev_heat_source = [0.0, 0.1, 0.2, 0.3]
        self.assertEqual(
            first=self.storagetank.additional_energy_input(
                heat_source=heat_source,
                energy_input=energy_input,
                controlmax_diverter=setpnt_diverter,
            ),
            second=0.0,
        )

        # Test it raises an error if heat_source is not in heat_source_dict
        with self.assertRaises(ValueError):
            self.storagetank.additional_energy_input(
                heat_source=self.imheater2, energy_input=5.0, controlmax_diverter=setpnt_diverter
            )

    def test_internal_gains(self):
        self.storagetank._Q_sto_h_ls_rbl = 0.05
        self.assertEqual(first=self.storagetank.internal_gains(), second=50.0)

    def test_primary_pipework_losses(self):
        input_energy_adj = 0.0
        setpnt_max = 55.0
        nb_vol = 4
        primary_pipework_lst: list[PipeworkData] = [
            {
                "location": "internal",
                "internal_diameter_mm": 24,
                "external_diameter_mm": 27,
                "length": 2.0,
                "insulation_thermal_conductivity": 0.035,
                "insulation_thickness_mm": 40,
                "surface_reflectivity": False,
                "pipe_contents": PipeworkContents.WATER,
                "internal_diameter": 0.024,
                "external_diameter": 0.027,
                "insulation_thickness": 0.04,
            },
            {
                "location": "external",
                "internal_diameter_mm": 25,
                "external_diameter_mm": 27,
                "length": 0.0,
                "insulation_thermal_conductivity": 0.035,
                "insulation_thickness_mm": 38,
                "surface_reflectivity": False,
                "pipe_contents": PipeworkContents.WATER,
                "internal_diameter": 0.025,
                "external_diameter": 0.027,
                "insulation_thickness": 0.038,
            },
        ]

        self.storagetank_with_pipework = StorageTank(
            volume=150.0,
            losses=1.68,
            init_temp=55.0,
            cold_feed=self.coldfeed,
            simulation_time=self.simtime,
            heat_source_dict=self.heat_source_dict,
            project=DummyProject(temp_internal_air=20.0),
            external_conditions=self.extcond,
            detailed_output=False,
            nb_vol=nb_vol,
            primary_pipework_lst=primary_pipework_lst,
        )
        for t_idx, _, _ in self.simtime:
            with self.subTest(timestep=t_idx):
                self.assertEqual(
                    first=self.storagetank_with_pipework._calculate_primary_pipework_losses(
                        input_energy_adj=input_energy_adj, temp_flow=setpnt_max
                    ),
                    second=[
                        (0.0, 0.0),
                        (0.0, 0.0),
                        (0.0, 0.0),
                        (0.0, 0.0),
                        (0.0, 0.0),
                        (0.0, 0.0),
                        (0.0, 0.0),
                        (0.0, 0.0),
                    ][t_idx],
                )

        # With value for input_energy_adj
        input_energy_adj = 3.0

        self.simtime.reset()
        for t_idx, _, _ in self.simtime:
            with self.subTest(timestep=t_idx):
                self.assertEqual(
                    first=self.storagetank_with_pipework._calculate_primary_pipework_losses(
                        input_energy_adj=input_energy_adj, temp_flow=setpnt_max
                    ),
                    second=(0.04746228058715814, 10.657894331822993),
                )

    def test_primary_pipework_losses_end_of_heating(self):
        """Test the end of heating event scenario in __primary_pipework_losses method"""
        # Set up storage tank with pipework
        setpnt_max = 55.0
        nb_vol = 4
        primary_pipework_lst: list[PipeworkData] = [
            {
                "location": "internal",
                "internal_diameter_mm": 24,
                "external_diameter_mm": 27,
                "length": 2.0,
                "insulation_thermal_conductivity": 0.035,
                "insulation_thickness_mm": 40,
                "surface_reflectivity": False,
                "pipe_contents": PipeworkContents.WATER,
                "internal_diameter": 0.024,
                "external_diameter": 0.027,
                "insulation_thickness": 0.04,
            },
            {
                "location": "external",
                "internal_diameter_mm": 25,
                "external_diameter_mm": 27,
                "length": 0.0,
                "insulation_thermal_conductivity": 0.035,
                "insulation_thickness_mm": 38,
                "surface_reflectivity": False,
                "pipe_contents": PipeworkContents.WATER,
                "internal_diameter": 0.025,
                "external_diameter": 0.027,
                "insulation_thickness": 0.038,
            },
        ]

        storage_tank = StorageTank(
            volume=150.0,
            losses=1.68,
            init_temp=55.0,
            cold_feed=self.coldfeed,
            simulation_time=self.simtime,
            heat_source_dict=self.heat_source_dict,
            project=DummyProject(temp_internal_air=20.0),
            external_conditions=self.extcond,
            detailed_output=False,
            nb_vol=nb_vol,
            primary_pipework_lst=primary_pipework_lst,
        )

        storage_tank._input_energy_adj_prev_timestep = 3.0

        input_energy_adj = 0.0
        original_cool_down_loss = Pipework.calculate_cool_down_loss

        try:
            cool_down_loss_result = 0.05  # kWh

            def mock_cool_down_loss(self, inside_temp, outside_temp):
                # Only return the mocked value for internal pipework
                if self.location == WaterPipeworkLocation.INTERNAL:
                    return cool_down_loss_result
                return 0.0  # pragma: no cover

            Pipework.calculate_cool_down_loss = mock_cool_down_loss

            losses, gains = storage_tank._calculate_primary_pipework_losses(
                input_energy_adj=input_energy_adj, temp_flow=setpnt_max
            )

            expected_gains = (
                cool_down_loss_result * 1000 / storage_tank._simulation_time.timestep()
            )  # W
            self.assertEqual(gains, expected_gains)

            # No losses should be recorded for the end of heating event
            self.assertEqual(losses, 0.0)

        finally:
            # Restore the original method
            Pipework.calculate_cool_down_loss = original_cool_down_loss

    def test_get_losses_from_primary_pipework_and_storage(self):
        usage_event = get_usage_event()
        self.storagetank.demand_hot_water(usage_events=usage_event)
        self.assertEqual(
            first=self.storagetank.get_losses_from_primary_pipework_and_storage(),
            second=(0, 0.07050814814814815),
        )

    def test_energy_demand(self):
        usage_event = get_usage_event()
        self.storagetank.demand_hot_water(usage_events=usage_event)
        self.assertAlmostEqual(first=self.storagetank.test_energy_demand(), second=5.9141614814815)

    def test_temperature_and_draw_off_hot_water(self):
        """Test the temperature method of the StorageTank class."""
        coldwatertemps = [60.0, 10.1, 10.2, 10.5, 10.6, 11.0, 11.5, 12.1]
        self.storagetank._cold_feed = ColdWaterSource(
            cold_water_temps=coldwatertemps,
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )
        self.assertEqual(
            first=self.storagetank.draw_off_hot_water(volume=240), second=(56.875, 240.0)
        )

        # Setup to reset cold feed
        self.setUp()

        self.assertEqual(first=self.storagetank.draw_off_hot_water(volume=0), second=(None, 0.0))
        self.assertEqual(
            first=self.storagetank.draw_off_water(volume_needed=0), second=[(55.0, 0.0)]
        )
        self.assertEqual(
            first=self.storagetank.draw_off_water(volume_needed=22.3), second=[(55.0, 22.3)]
        )
        self.assertEqual(
            first=self.storagetank.draw_off_water(volume_needed=165),
            second=[(55.0, 37.5), (55.0, 37.5), (55.0, 37.5), (28.24, 37.5), (10.0, 15.0)],
        )

    def test_heat_source_output(self):
        self.assertEqual(
            self.storagetank.heat_source_output(
                heat_source=self.imheater, input_energy_adj=43.2, heater_layer=0
            ),
            43.2,
        )
        self.assertEqual(
            self.storagetank.heat_source_output(
                heat_source=self.solthermal, input_energy_adj=43.2, heater_layer=0
            ),
            0,
        )
        self.assertEqual(
            self.storagetank.heat_source_output(
                heat_source=self.heat_pump, input_energy_adj=43.2, heater_layer=0
            ),
            3,
        )

    def test_extract_hot_water_demand_exceeds_tank_capacity(self):
        """Test that when hot water demand exceeds tank capacity,
        remaining volume is drawn from cold feed (e.g. pre-heat tank)."""
        # Reset draw-off tracking variables
        self.storagetank._temp_average_drawoff_volweighted = 0.0
        self.storagetank._total_volume_drawoff = 0.0

        # Create an event that demands more hot water than the tank can provide
        # Tank volume is 150 litres (4 layers of 37.5 litres each at 55°C)
        # Request 200 litres of hot water - this exceeds tank capacity
        event = WaterEventResult(
            type="Bath",
            temperature_warm=41.0,
            volume_warm=200.0,
            volume_hot=200.0,  # Demand exceeds tank capacity of 150 litres
            event_duration=0.0,
        )

        # Mock the cold feed's draw_off_water method to verify it's called correctly
        with patch.object(self.storagetank._cold_feed, "draw_off_water") as mock_draw_off:
            # Configure mock to return realistic values (cold water at source temp)
            mock_draw_off.return_value = [(10.0, 50.0)]  # 50 litres at 10°C

            volume_used, energy_withdrawn, remaining_vols = self.storagetank.extract_hot_water(
                event=event
            )

            # Verify cold feed's draw_off_water was called once with 50 litres
            # (200 litres demanded - 150 litres from tank = 50 litres from cold feed)
            mock_draw_off.assert_called_once_with(volume_needed=50.0)

        # Volume used from tank should be entire tank capacity
        self.assertAlmostEqual(
            first=volume_used,
            second=150.0,
            msg="Volume used from tank should equal total tank capacity",
        )

        # All tank layers should be depleted
        for i, vol in enumerate(remaining_vols):
            self.assertAlmostEqual(
                first=vol,
                second=0.0,
                msg=f"Layer {i} should be fully depleted",
            )

        # Total draw-off should include both tank water and cold feed water
        # 150 litres from tank + 50 litres from cold feed = 200 litres total
        self.assertAlmostEqual(
            first=self.storagetank._total_volume_drawoff,
            second=200.0,
            msg="Total volume draw-off should include water from cold feed",
        )

        # Energy withdrawn should be positive (hot water from tank + any pre-heated water)
        self.assertAlmostEqual(
            energy_withdrawn,
            7.845,
            msg="Energy withdrawn should be positive",
        )

    def test_extract_hot_water_demand_exceeds_capacity_with_preheat_tank(self):
        """Test that when demand exceeds tank capacity, water is properly drawn
        from a pre-heat tank configured as the cold feed."""
        # Use storagetank3 which has a pre-heated storage tank as its cold feed
        # storagetank3: 210 litres, init_temp=52°C
        # preheatfeed: 80 litres, init_temp=30°C
        self.storagetank3._temp_average_drawoff_volweighted = 0.0
        self.storagetank3._total_volume_drawoff = 0.0

        # Create an event that demands more than storagetank3 capacity (210 litres)
        # but less than storagetank3 + preheatfeed combined (290 litres)
        event = WaterEventResult(
            type="Bath",
            temperature_warm=41.0,
            volume_warm=250.0,
            volume_hot=250.0,  # Exceeds 210 litre tank, needs 40 litres from pre-heat
            event_duration=0.0,
        )

        volume_used, energy_withdrawn, remaining_vols = self.storagetank3.extract_hot_water(
            event=event
        )

        # Volume used from main tank should be entire tank capacity
        self.assertAlmostEqual(
            first=volume_used,
            second=210.0,
            msg="Volume used from main tank should equal its total capacity",
        )

        # Total draw-off should include water from pre-heat tank
        # 210 litres from main tank + 40 litres from pre-heat tank = 250 litres
        self.assertAlmostEqual(
            first=self.storagetank3._total_volume_drawoff,
            second=250.0,
            msg="Total volume draw-off should include water drawn from pre-heat tank",
        )

        # Verify energy calculation accounts for pre-heated water
        # Energy should be greater than zero since we're drawing hot/warm water
        self.assertGreater(
            energy_withdrawn,
            0.0,
            msg="Energy withdrawn should account for both tank and pre-heat water",
        )

    def test_primary_pipework_losses_between_events(self):
        """Test primary pipework losses between heating events when room temperature changes"""
        setpnt_max = 55.0
        nb_vol = 4
        primary_pipework_lst: list[PipeworkData] = [
            {
                "location": "internal",
                "internal_diameter_mm": 24,
                "external_diameter_mm": 27,
                "length": 2.0,
                "insulation_thermal_conductivity": 0.035,
                "insulation_thickness_mm": 40,
                "surface_reflectivity": False,
                "pipe_contents": PipeworkContents.WATER,
                "internal_diameter": 0.024,
                "external_diameter": 0.027,
                "insulation_thickness": 0.04,
            },
        ]

        storage_tank = StorageTank(
            volume=150.0,
            losses=1.68,
            init_temp=55.0,
            cold_feed=self.coldfeed,
            simulation_time=self.simtime,
            heat_source_dict=self.heat_source_dict,
            project=DummyProject(temp_internal_air=20.0),
            external_conditions=self.extcond,
            detailed_output=False,
            nb_vol=nb_vol,
            primary_pipework_lst=primary_pipework_lst,
        )

        # First heating event - should NOT calculate between_events_loss
        storage_tank._input_energy_adj_prev_timestep = 0.0
        input_energy_adj_first = 3.0

        # Save original method to restore after test
        original_cool_down_loss = Pipework.calculate_cool_down_loss
        cool_down_call_count = 0

        try:

            def mock_cool_down_loss_first(self, inside_temp, outside_temp):
                nonlocal cool_down_call_count
                cool_down_call_count += 1
                return 0.05  # kWh

            Pipework.calculate_cool_down_loss = mock_cool_down_loss_first

            losses_first, _ = storage_tank._calculate_primary_pipework_losses(
                input_energy_adj=input_energy_adj_first, temp_flow=setpnt_max
            )

            # Should only call cool_down_loss once (for the start of heating event)
            self.assertEqual(cool_down_call_count, 1)

            # Now simulate end of first heating event
            storage_tank._input_energy_adj_prev_timestep = input_energy_adj_first
            losses_end_first, _ = storage_tank._calculate_primary_pipework_losses(
                input_energy_adj=0.0, temp_flow=setpnt_max
            )

            # Reset for second heating event
            cool_down_call_count = 0
            storage_tank._input_energy_adj_prev_timestep = 0.0
            input_energy_adj_second = 2.5

            losses_second, _ = storage_tank._calculate_primary_pipework_losses(
                input_energy_adj=input_energy_adj_second, temp_flow=setpnt_max
            )

            # Should call cool_down_loss twice now:
            # once for start of heating event, once for between events loss
            self.assertEqual(cool_down_call_count, 2)

            # Second event should have more losses than first due to between_events_loss
            self.assertAlmostEqual(losses_first, 0.060657894331823)
            self.assertAlmostEqual(losses_second, 0.11065789433182299)

        finally:
            # Restore original method to avoid affecting other tests
            Pipework.calculate_cool_down_loss = original_cool_down_loss


class Test_ImmersionHeater(unittest.TestCase):
    """Unit tests for ImmersionHeater class"""

    def setUp(self):
        """Create ImmersionHeater object to be tested"""
        self.simtime = SimulationTime(start_time=0, end_time=4, step=1)
        self.energysupply = EnergySupply(fuel_type=FuelType.MAINS_GAS, simulation_time=self.simtime)
        energysupplyconn = self.energysupply.connection("shower")
        controlmin = SetpointTimeControl(
            schedule=[52, 52, None, 52],
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )
        controlmax = SetpointTimeControl(
            schedule=[60, 60, 60, 60], simulation_time=self.simtime, start_day=0, time_series_step=1
        )
        self.immersionheater = ImmersionHeater(
            rated_power=50,
            energy_supply_conn=energysupplyconn,
            simulation_time=self.simtime,
            controlmin=controlmin,
            controlmax=controlmax,
        )

    def test_demand_energy(self):
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    first=self.immersionheater.demand_energy(
                        energy_demand=[40.0, 100.0, 30.0, 20.0][t_idx]
                    ),
                    second=[40.0, 50.0, 0.0, 20.0][t_idx],
                    msg="incorrect energy supplied returned",
                )

        with self.assertRaises(ValueError):
            self.immersionheater.demand_energy(energy_demand=-1)

    def test_energy_output_max(self):
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    first=self.immersionheater.energy_output_max(ignore_standard_ctrl=True),
                    second=[50.0, 50.0, 50.0, 50.0][t_idx],
                )

        self.simtime.reset()
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertEqual(
                    first=self.immersionheater.energy_output_max(ignore_standard_ctrl=False),
                    second=[50.0, 50.0, 0.0, 50.0][t_idx],
                )


class TestPVDiverter(unittest.TestCase):
    """Unit tests for TestPVDiverter class"""

    def setUp(self):
        """Create PVDiverter object to be tested"""
        self.simtime = SimulationTime(start_time=0, end_time=4, step=1)
        self.coldwatertemps = [10.6, 11.0, 11.5, 12.1]
        self.coldfeed = ColdWaterSource(
            cold_water_temps=self.coldwatertemps,
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )
        self.energysupply = EnergySupply(fuel_type=FuelType.MAINS_GAS, simulation_time=self.simtime)
        energysupplyconn = self.energysupply.connection("shower")
        controlmin = SetpointTimeControl(
            schedule=[52, 52, None, 52],
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )
        controlmax = SetpointTimeControl(
            schedule=[60, 60, 60, 60], simulation_time=self.simtime, start_day=0, time_series_step=1
        )
        setpnt_diverter_control = SetpointTimeControl(
            schedule=[60, 60, 60, 60], simulation_time=self.simtime, start_day=0, time_series_step=1
        )
        self.immersionheater = ImmersionHeater(
            rated_power=50,
            energy_supply_conn=energysupplyconn,
            simulation_time=self.simtime,
            controlmin=controlmin,
            controlmax=controlmax,
        )
        self.heat_source_dict = {self.immersionheater: (0.1, 0.33)}
        self.windspeed = [3.7, 3.8, 3.9, 4.0, 4.1, 4.2, 4.3, 4.4]
        self.wind_direction = [Orientation360.create_from_180(0.0)] * 8
        self.energy_supply_conn_name_auxiliary = "Boiler_auxiliary"
        self.airtemp = [0.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 20.0]
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
            {"number": 1, "start": 180, "end": 135},
            {"number": 2, "start": 135, "end": 90},
            {"number": 3, "start": 90, "end": 45},
            {"number": 4, "start": 45, "end": 0},
            {"number": 5, "start": 0, "end": -45},
            {"number": 6, "start": -45, "end": -90},
            {"number": 7, "start": -90, "end": -135},
            {"number": 8, "start": -135, "end": -180},
        ]
        self.extcond = ExternalConditions(
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
        self.storagetank = StorageTank(
            volume=150.0,
            losses=1.68,
            init_temp=55.0,
            cold_feed=self.coldfeed,
            simulation_time=self.simtime,
            heat_source_dict=self.heat_source_dict,
            project=DummyProject(temp_internal_air=20.0),
            external_conditions=self.extcond,
        )
        self.pvdiverter = PVDiverter(
            storage_tank=self.storagetank,
            immersion_heater=self.immersionheater,
            controlmax=setpnt_diverter_control,
        )

    def test_capacity_used(self):
        capacity_used = 2.3
        self.pvdiverter.increment_capacity_used(energy_supplied=capacity_used)
        self.assertEqual(first=self.pvdiverter.capacity_used, second=capacity_used)

    def test_timestep_end(self):
        self.pvdiverter.increment_capacity_used(energy_supplied=2.3)
        self.pvdiverter.timestep_end()
        self.assertEqual(first=self.pvdiverter.capacity_used, second=0)

    def test_divert_surplus(self):
        # _StorageTank__Q_ls_n_prev_heat_source is needed for the functions to
        # run the test but have no bearing in the results
        self.storagetank._Q_ls_n_prev_heat_source = [0.0, 0.1, 0.2, 0.3]

        self.assertAlmostEqual(
            first=self.pvdiverter.divert_surplus(supply_surplus=-1.0), second=0.891553580246915
        )
        self.assertAlmostEqual(first=self.pvdiverter.divert_surplus(supply_surplus=0.0), second=0.0)
        self.assertAlmostEqual(first=self.pvdiverter.divert_surplus(supply_surplus=1.0), second=0.0)


class TestSolarThermalSystem(unittest.TestCase):
    """Unit tests for SolarThermalSystem class"""

    def setUp(self):
        """Create SolarThermalSystem object to be tested"""
        coldwatertemps = [
            17.0,
            17.1,
            17.2,
            17.3,
            17.4,
            17.5,
            17.6,
            17.7,
            17.0,
            17.1,
            17.2,
            17.3,
            17.4,
            17.5,
            17.6,
            17.7,
            17.0,
            17.1,
            17.2,
            17.3,
            17.4,
            17.5,
            17.6,
            17.7,
        ]
        self.simtime = SimulationTime(start_time=5088, end_time=5112, step=1)
        coldfeed = ColdWaterSource(
            cold_water_temps=coldwatertemps,
            simulation_time=self.simtime,
            start_day=212,
            time_series_step=1,
        )
        self.controlmax = SetpointTimeControl(
            schedule=[
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
                55.0,
            ],
            simulation_time=self.simtime,
            start_day=212,
            time_series_step=1,
        )
        self.energysupply = EnergySupply(
            fuel_type=FuelType.ELECTRICITY, simulation_time=self.simtime
        )
        self.energysupplyconnst = self.energysupply.connection("solarthermal")

        # Adding solarthermal to the test
        proj_dict = {
            "ExternalConditions": {
                "air_temperatures": [
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                    19.0,
                ],
                "wind_speeds": [
                    3.9,
                    3.8,
                    3.9,
                    4.1,
                    3.8,
                    4.2,
                    4.3,
                    4.1,
                    3.9,
                    3.8,
                    3.9,
                    4.1,
                    3.8,
                    4.2,
                    4.3,
                    4.1,
                    3.9,
                    3.8,
                    3.9,
                    4.1,
                    3.8,
                    4.2,
                    4.3,
                    4.1,
                ],
                "wind_directions": [
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
                ],
                "diffuse_horizontal_radiation": [
                    0,
                    0,
                    0,
                    0,
                    35,
                    73,
                    139,
                    244,
                    320,
                    361,
                    369,
                    348,
                    318,
                    249,
                    225,
                    198,
                    121,
                    68,
                    19,
                    0,
                    0,
                    0,
                    0,
                    0,
                ],
                "direct_beam_radiation": [
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    7,
                    53,
                    63,
                    164,
                    339,
                    242,
                    315,
                    577,
                    385,
                    285,
                    332,
                    126,
                    7,
                    0,
                    0,
                    0,
                    0,
                    0,
                ],
                "solar_reflectivity_of_ground": [
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                    0.2,
                ],
                "latitude": 51.383,
                "longitude": -0.783,
                "timezone": 0,
                "start_day": 212,
                "end_day": 212,
                "time_series_step": 1,
                "january_first": 1,
                "daylight_savings": "not applicable",
                "leap_day_included": False,
                "direct_beam_conversion_needed": False,
                "shading_segments": [
                    {"number": 1, "start": 180, "end": 135},
                    {"number": 2, "start": 135, "end": 90},
                    {"number": 3, "start": 90, "end": 45},
                    {
                        "number": 4,
                        "start": 45,
                        "end": 0,
                        "shading": [{"type": "obstacle", "height": 10.5, "distance": 12}],
                    },
                    {"number": 5, "start": 0, "end": -45},
                    {"number": 6, "start": -45, "end": -90},
                    {"number": 7, "start": -90, "end": -135},
                    {"number": 8, "start": -135, "end": -180},
                ],
            }
        }
        self.__external_conditions = ExternalConditions(
            self.simtime,
            proj_dict["ExternalConditions"]["air_temperatures"],
            proj_dict["ExternalConditions"]["wind_speeds"],
            proj_dict["ExternalConditions"]["wind_directions"],
            proj_dict["ExternalConditions"]["diffuse_horizontal_radiation"],
            proj_dict["ExternalConditions"]["direct_beam_radiation"],
            proj_dict["ExternalConditions"]["solar_reflectivity_of_ground"],
            proj_dict["ExternalConditions"]["latitude"],
            proj_dict["ExternalConditions"]["longitude"],
            proj_dict["ExternalConditions"]["timezone"],
            proj_dict["ExternalConditions"]["start_day"],
            proj_dict["ExternalConditions"]["end_day"],
            proj_dict["ExternalConditions"]["time_series_step"],
            proj_dict["ExternalConditions"]["january_first"],
            proj_dict["ExternalConditions"]["daylight_savings"],
            proj_dict["ExternalConditions"]["leap_day_included"],
            proj_dict["ExternalConditions"]["direct_beam_conversion_needed"],
            proj_dict["ExternalConditions"]["shading_segments"],
        )
        self.solthermal = SolarThermalSystem(
            sol_loc=SolarCollectorLoopLocation.OUT,
            area_module=3,
            modules=1,
            peak_collector_efficiency=0.8,
            incidence_angle_modifier=0.9,
            first_order_hlc=3.5,
            second_order_hlc=0,
            collector_mass_flow_rate=1,
            power_pump=100,
            power_pump_control=10,
            energy_supply_conn=self.energysupplyconnst,
            tilt=30,
            orientation=Orientation360.create_from_180(0),
            solar_loop_piping_hlc=0.5,
            ext_cond=self.__external_conditions,
            simulation_time=self.simtime,
            project=DummyProject(temp_internal_air=20.0),
            controlmax=self.controlmax,
        )

        heat_source_dict = {self.solthermal: (0.1, 0.33)}

        self.storagetank = StorageTank(
            volume=150.0,
            losses=1.68,
            init_temp=55.0,
            cold_feed=coldfeed,
            simulation_time=self.simtime,
            heat_source_dict=heat_source_dict,
            project=DummyProject(temp_internal_air=20.0),
            external_conditions=self.__external_conditions,
        )

    def test_energy_output_max(self):
        self.temp_storage_tank_s3_n = [
            17.2,
            17.2,
            17.2,
            17.2,
            17.43,
            32.95,
            35.91,
            35.91,
            35.91,
            42.25,
            43.46,
            43.46,
            43.46,
            43.46,
            43.46,
            43.46,
            43.46,
            43.46,
            43.46,
            43.46,
            43.46,
            43.46,
            43.46,
            43.46,
        ]

        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertAlmostEqual(
                    first=self.solthermal.energy_output_max(
                        storage_tank=self.storagetank,
                        temp_storage_tank_s3_n=self.temp_storage_tank_s3_n,
                    ),
                    second=[
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0.5441009409757523,
                        0.7375096332994749,
                        1.043768276267769,
                        1.4751675743361337,
                        1.2419712751344847,
                        1.3717388178387737,
                        1.7256641787433769,
                        1.1745201463530213,
                        0.8403815010507395,
                        0.6056200608960752,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                    ][t_idx],
                )

        self.sol_loc = SolarCollectorLoopLocation.NHS
        self.solar_thermal_system_NHS = SolarThermalSystem(
            sol_loc=self.sol_loc,
            area_module=3,
            modules=1,
            peak_collector_efficiency=0.8,
            incidence_angle_modifier=0.9,
            first_order_hlc=3.5,
            second_order_hlc=0,
            collector_mass_flow_rate=1,
            power_pump=100,
            power_pump_control=10,
            energy_supply_conn=self.energysupplyconnst,
            tilt=30,
            orientation=Orientation360.create_from_180(0),
            solar_loop_piping_hlc=0.5,
            ext_cond=self.__external_conditions,
            simulation_time=self.simtime,
            project=DummyProject(temp_internal_air=20.0),
            controlmax=self.controlmax,
        )

        self.simtime.reset()
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertAlmostEqual(
                    self.solar_thermal_system_NHS.energy_output_max(
                        storage_tank=self.storagetank,
                        temp_storage_tank_s3_n=self.temp_storage_tank_s3_n,
                    ),
                    second=[
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0.5443432944582923,
                        0.7377445749305638,
                        1.044003444574131,
                        1.4754027357101285,
                        1.2422064367204904,
                        1.371973979418296,
                        1.7258993403230973,
                        1.1747553079327355,
                        0.8406166626304539,
                        0.6058552224757895,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                    ][t_idx],
                )

        self.sol_loc = SolarCollectorLoopLocation.HS
        self.solar_thermal_system_HS = SolarThermalSystem(
            sol_loc=self.sol_loc,
            area_module=3,
            modules=1,
            peak_collector_efficiency=0.8,
            incidence_angle_modifier=0.9,
            first_order_hlc=3.5,
            second_order_hlc=0,
            collector_mass_flow_rate=1,
            power_pump=100,
            power_pump_control=10,
            energy_supply_conn=self.energysupplyconnst,
            tilt=30,
            orientation=Orientation360.create_from_180(0),
            solar_loop_piping_hlc=0.5,
            ext_cond=self.__external_conditions,
            simulation_time=self.simtime,
            project=DummyProject(temp_internal_air=20.0),
            controlmax=self.controlmax,
        )
        self.simtime.reset()
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertAlmostEqual(
                    first=self.solar_thermal_system_HS.energy_output_max(
                        storage_tank=self.storagetank,
                        temp_storage_tank_s3_n=self.temp_storage_tank_s3_n,
                    ),
                    second=[
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0.5445856479408322,
                        0.7379795165616525,
                        1.044238612880493,
                        1.475637897084123,
                        1.2424415983064963,
                        1.372209140997818,
                        1.7261345019028178,
                        1.1749904695124498,
                        0.8408518242101682,
                        0.6060903840555039,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                    ][t_idx],
                )

    def test_demand_energy(self):
        self.temp_storage_tank_s3_n = [
            17.2,
            17.2,
            17.2,
            17.2,
            17.43,
            32.95,
            35.91,
            35.91,
            35.91,
            42.25,
            43.46,
            43.46,
            43.46,
            43.46,
            43.46,
            43.46,
            43.46,
            43.46,
            43.46,
            43.46,
            43.46,
            43.46,
            43.46,
            43.46,
        ]

        self.solthermal.energy_output_max(
            storage_tank=self.storagetank, temp_storage_tank_s3_n=self.temp_storage_tank_s3_n
        )
        for t_idx, _, _ in self.simtime:
            with self.subTest(i=t_idx):
                self.assertAlmostEqual(
                    first=self.solthermal.demand_energy(energy_demand=100),
                    second=[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0][
                        t_idx
                    ],
                )

    def test_energy_potential(self):
        self.assertEqual(self.solthermal.energy_potential, 0)

    def test_energy_supply(self):
        self.assertEqual(self.solthermal.energy_supplied, 0)


class TestSmartHotWaterTank(unittest.TestCase):
    """Unit tests for SmartHotWaterTank class"""

    def setUp(self):
        """Create SmartHotWaterTank object to be tested"""
        self.coldwatertemps = [10.0, 10.1, 10.2, 10.5, 10.6, 11.0, 11.5, 12.1]
        self.simtime = SimulationTime(start_time=0, end_time=8, step=1)
        self.coldfeed = ColdWaterSource(
            cold_water_temps=self.coldwatertemps,
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )
        self.controlmin = SetpointTimeControl(
            schedule=[0.5, None, None, None, 0.5, 0.5, 0.5, 0.5],
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )
        self.controlmax = SetpointTimeControl(
            schedule=[1.0, 1.0, 0.9, 0.8, 0.7, 1.0, 0.9, 0.8],
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )
        self.controlmax2 = SetpointTimeControl(
            schedule=[1.0, 1.0, 0.9, 0.8, 0.7, 1.0, 0.9, 0.8],
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )
        self.windspeed = [3.7, 3.8, 3.9, 4.0, 4.1, 4.2, 4.3, 4.4]
        self.wind_direction = [Orientation360.create_from_180(0.0)] * 8
        self.energy_supply_conn_name_auxiliary = "Boiler_auxiliary"
        self.airtemp = [0.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 20.0]
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
            {"number": 1, "start": 180, "end": 135},
            {"number": 2, "start": 135, "end": 90},
            {"number": 3, "start": 90, "end": 45},
            {"number": 4, "start": 45, "end": 0},
            {"number": 5, "start": 0, "end": -45},
            {"number": 6, "start": -45, "end": -90},
            {"number": 7, "start": -90, "end": -135},
            {"number": 8, "start": -135, "end": -180},
        ]
        self.extcond = ExternalConditions(
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

        self.temp_setpnt_max = SetpointTimeControl(
            schedule=[50.0, 40.0, 30.0, 20.0, 50.0, 50.0, 50.0, 50.0],
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )
        self.energysupply = EnergySupply(FuelType.ELECTRICITY, self.simtime)
        energysupplyconn = self.energysupply.connection("immersion")
        self.imheater = ImmersionHeater(
            rated_power=5.0,
            energy_supply_conn=energysupplyconn,
            simulation_time=self.simtime,
            controlmin=self.controlmin,
            controlmax=self.controlmax,
        )
        self.heat_source_dict = {self.imheater: (0.6, None)}
        self.__max_flow_rate_pump_l_per_min = 1000
        self.__temp_usable = 40
        self.energy_supply_conn_pump = MagicMock()
        self.smarthotwatertank = SmartHotWaterTank(
            volume=300.0,
            losses=1.68,
            init_temp=50.0,
            power_pump_kW=5.0,
            max_flow_rate_pump_l_per_min=self.__max_flow_rate_pump_l_per_min,
            temp_usable=self.__temp_usable,
            temp_setpnt_max=self.temp_setpnt_max,
            cold_feed=self.coldfeed,
            simulation_time=self.simtime,
            heat_source_dict=self.heat_source_dict,
            project=DummyProject(temp_internal_air=20.0),
            external_conditions=self.extcond,
            energy_supply_conn_pump=self.energy_supply_conn_pump,
            nb_vol=4,
        )

        # Also test case where heater does not heat all layers, to ensure this is handled correctly
        self.energysupplyconn2 = self.energysupply.connection("immersion2")
        imheater2 = ImmersionHeater(
            rated_power=5.0,
            energy_supply_conn=self.energysupplyconn2,
            simulation_time=self.simtime,
            controlmin=self.controlmin,
            controlmax=self.controlmax2,
        )
        self.heat_source_dict2 = {imheater2: (0.6, None)}
        self.smarthotwatertank2 = SmartHotWaterTank(
            volume=210.0,
            losses=1.61,
            init_temp=60.0,
            power_pump_kW=5.0,
            max_flow_rate_pump_l_per_min=self.__max_flow_rate_pump_l_per_min,
            temp_usable=self.__temp_usable,
            temp_setpnt_max=self.temp_setpnt_max,
            cold_feed=self.coldfeed,
            simulation_time=self.simtime,
            heat_source_dict=self.heat_source_dict2,
            project=DummyProject(temp_internal_air=20.0),
            external_conditions=self.extcond,
            energy_supply_conn_pump=self.energy_supply_conn_pump,
            nb_vol=4,
            detailed_output=True,
        )

    def test_calc_state_of_charge(self):
        T_h = [
            43.984858220267675,
            43.984858220267675,
            43.984858220267675,
            43.984858220267725,
            43.984858220267725,
            43.98485822026773,
            43.984858220267775,
            43.984858220267775,
        ]
        soc = self.smarthotwatertank.calc_state_of_charge(T_h=T_h)
        self.assertAlmostEqual(first=soc, second=0.850, places=2)

    def test_calc_state_of_charge_low_high(self):
        T_h_low = [10.0, 20.0, 25.0, 30.0, 35.0, 35.0, 35.0, 35.0]
        T_h_high = [50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0]
        soc_low = self.smarthotwatertank.calc_state_of_charge(T_h=T_h_low)
        soc_high = self.smarthotwatertank.calc_state_of_charge(T_h=T_h_high)
        self.assertEqual(first=soc_low, second=0.0)
        self.assertEqual(first=soc_high, second=1.0)

    def test_calc_state_of_charge_varied(self):
        T_h_high = [50.0, 40.0, 30.0, 20.0, 50.0, 50.0, 50.0, 50.0]
        soc_high = self.smarthotwatertank.calc_state_of_charge(T_h=T_h_high)
        self.assertEqual(first=soc_high, second=0.71875)

    def test_bottom_to_top_pump_volume_no_pumping(self):
        temp_s6_n = [10.0, 20.0, 25.0, 30.0, 35.0, 35.0, 35.0, 35.0]
        Qin = 0
        heater_layer = 7
        volumes = [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0]
        volume_pumped = self.smarthotwatertank.bottom_to_top_pump_volume(
            temp_s7_n=temp_s6_n, Qin=Qin, heater_layer=heater_layer, volumes=volumes
        )
        self.assertEqual(first=volume_pumped, second=0.0)

    def test_soc_over_time(self):
        expected_soc = [
            0.5625,
            0.75042,
            1.13005,
            2.33553,
            0.56155,
            0.5609,
            0.56006,
            0.55904,
        ]
        T_h_high = [50.0, 40.0, 30.0, 20.0, 30.0, 40.0, 50.0, 50.0]
        for t_idx, _, _ in self.simtime:
            with self.subTest(timestep=t_idx):
                soc = self.smarthotwatertank.calc_state_of_charge(T_h=T_h_high)
                # Verify the temperatures against expected results
                self.assertAlmostEqual(
                    first=soc,
                    second=expected_soc[t_idx],
                    places=5,
                    msg="incorrect state of charge returned",
                )

    def test_demand_hot_water(self):
        # Expected results for the unit test
        event_data = get_event_data_immersion()
        expected_temperatures_1 = [
            [42.06412979639594, 50.0, 50.0, 50.0],
            [26.168457194735883, 45.942228008024884, 49.87555555555556, 49.87555555555556],
            [26.115731861133547, 45.86963541543229, 49.802962962962965, 49.802962962962965],
            [17.336010881790145, 34.751355008536194, 47.57251929648306, 49.782222222222224],
            [31.875588805820787, 50.0, 50.0, 50.0],
            [20.717353598198578, 40.20747289529573, 49.82370370370371, 49.82370370370371],
            [20.69289324620792, 40.08195266546827, 49.64832153635117, 49.64832153635117],
            [20.668559725672026, 39.95708328127696, 49.47384875801453, 49.47384875801453],
        ]

        expected_temperatures_2 = [
            [10.0, 24.55607367670878, 50.03631427851564, 59.092295619623506],
            [10.057665043481068, 16.16115527929868, 35.205810167360966, 53.69978967126601],
            [10.057665043481068, 16.160011275772792, 35.10642745131158, 53.60040695521663],
            [10.381386078348926, 11.69403406025759, 21.212174941529444, 40.037268379332176],
            [11.520424219588156, 48.63806146445693, 48.63806146445693, 48.63806146445693],
            [50.0, 50.0, 50.0, 50.0],
            [49.75864197530864, 49.75864197530864, 49.75864197530864, 49.75864197530864],
            [49.518997294619716, 49.518997294619716, 49.518997294619716, 49.518997294619716],
        ]

        # Loop through the timesteps and the associated data pairs using `subTest`
        for t_idx, _, _ in self.simtime:  # Assuming simtime generates correct time indices
            usage_events = event_data[t_idx]

            # Convert usage events based on HW temp of 55 to equivalent 50:
            usage_events1 = []
            temp_hot = 50.0 if t_idx == 0 else expected_temperatures_1[t_idx - 1][-1]
            if usage_events is not None:
                for event in usage_events:
                    volume_hot = (
                        event.volume_warm
                        * (event.temperature_warm - self.coldwatertemps[t_idx])
                        / (temp_hot - self.coldwatertemps[t_idx])
                    )
                    usage_events1.append(
                        WaterEventResult(
                            type=event.type,
                            temperature_warm=event.temperature_warm,
                            volume_warm=event.volume_warm,
                            volume_hot=volume_hot,
                            event_duration=0.0,
                        )
                    )

            # Convert usage events based on HW temp of 55 to equivalent 60:
            usage_events2 = []
            temp_hot = 60.0 if t_idx == 0 else expected_temperatures_2[t_idx - 1][-1]
            if usage_events is not None:
                for event in usage_events:
                    volume_hot = (
                        event.volume_warm
                        * (event.temperature_warm - self.coldwatertemps[t_idx])
                        / (temp_hot - self.coldwatertemps[t_idx])
                    )
                    usage_events2.append(
                        WaterEventResult(
                            type=event.type,
                            temperature_warm=event.temperature_warm,
                            volume_warm=event.volume_warm,
                            volume_hot=volume_hot,
                            event_duration=0.0,
                        )
                    )

            with self.subTest(timestep=t_idx):
                self.smarthotwatertank.demand_hot_water(usage_events=usage_events1)

                # Verify the temperatures against expected results
                for i in range(len(self.smarthotwatertank._temp_n)):
                    self.assertAlmostEqual(
                        first=self.smarthotwatertank._temp_n[i],
                        second=expected_temperatures_1[t_idx][i],
                        msg="incorrect temperatures returned",
                    )

                self.assertAlmostEqual(
                    first=self.energysupply.results_by_end_user()["immersion"][t_idx],
                    second=[2.2101151057, 0.0, 0.0, 0.0, 2.0951108105, 0.0, 0.0, 0.0][t_idx],
                    msg="incorrect energy supplied returned",
                )

                self.smarthotwatertank2.demand_hot_water(usage_events=usage_events2)

                # Verify the temperatures against expected results
                for i in range(len(self.smarthotwatertank2._temp_n)):
                    self.assertAlmostEqual(
                        first=self.smarthotwatertank2._temp_n[i],
                        second=expected_temperatures_2[t_idx][i],
                        msg="incorrect temperatures returned in case where heater does not heat all layers",
                    )

                self.assertAlmostEqual(
                    self.energysupply.results_by_end_user()["immersion2"][t_idx],
                    [
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                        4.5043354264,
                        0.1956556236,
                        0.0,
                        0.0,
                    ][t_idx],
                    msg="incorrect energy supplied returned in case where heater does not heat all layers",
                )
                self.assertTrue(self.smarthotwatertank2._detailed_results)

    def test_demand_hot_water_edge_cases(self):
        usage_event = get_usage_event()
        with (
            patch.object(
                self.smarthotwatertank._heat_source_data[0][0],
                "_ImmersionHeater__controlmax",
            ) as mock_controlmax,
            patch.object(
                self.smarthotwatertank._heat_source_data[0][0],
                "_ImmersionHeater__controlmin",
            ) as mock_controlmin,
        ):
            mock_controlmin.setpnt.return_value = 3
            mock_controlmax.setpnt.return_value = 3
            with self.assertRaises(ValueError):
                self.smarthotwatertank.demand_hot_water(usage_event)
            mock_controlmin.setpnt.return_value = 1
            with self.assertRaises(ValueError):
                self.smarthotwatertank.demand_hot_water(usage_event)

    def test_calc_temps_after_extraction(self):
        expected_temps = [10.0, 10.0, 10.0, 12.666666666666666]
        remaining_vol = [0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4]

        temps_after_extraction, flag_rearrange_layers = (
            self.smarthotwatertank.calc_temps_after_extraction(remaining_vol)
        )

        for i, temp in enumerate(temps_after_extraction):
            self.assertAlmostEqual(temp, expected_temps[i])
        self.assertEqual(flag_rearrange_layers, False)

    def test_calc_final_temps(self):
        temp_s3_n = [10.0, 15.0, 20.0, 25.0, 25.0, 30.0, 35.0, 50.0]

        Q_x_in_n = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        heater_layer = 2
        Q_ls_n_prev_heat_source = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        final_temps = self.smarthotwatertank.calc_final_temps(
            temp_s3_n=temp_s3_n,
            heat_source=self.imheater,
            Q_x_in_n=Q_x_in_n,
            heater_layer=heater_layer,
            Q_ls_n_prev_heat_source=Q_ls_n_prev_heat_source,
            controlmax_diverter=self.controlmax,
        )

        self.assertEqual(
            final_temps,
            (
                [50.0, 50.0, 50.0, 50.0],
                [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],
                42.10166666666667,
                [10.0, 15.0, 433.00191204588907, 25.0],
                [229.00095602294454, 229.00095602294454, 229.00095602294454, 229.00095602294454],
                4.824900987654324,
                0.061468641975308644,
                [
                    0.015367160493827161,
                    0.015367160493827161,
                    0.015367160493827161,
                    0.015367160493827161,
                ],
            ),
        )

        self.smarthotwatertank._temp_usable = 100
        self.controlmax = SetpointTimeControl(
            schedule=[0.0, 1.0, 0.9, 0.8, 0.7, 1.0, 0.9, 0.8],
            simulation_time=self.simtime,
            start_day=0,
            time_series_step=1,
        )
        self.assertEqual(
            first=self.smarthotwatertank.calc_final_temps(
                temp_s3_n=temp_s3_n,
                heat_source=self.imheater,
                Q_x_in_n=Q_x_in_n,
                heater_layer=heater_layer,
                Q_ls_n_prev_heat_source=Q_ls_n_prev_heat_source,
                controlmax_diverter=self.controlmax,
            ),
            second=(
                [50.0, 50.0, 50.0, 50.0],
                [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],
                42.10166666666667,
                [10.0, 15.0, 433.00191204588907, 25.0],
                [229.00095602294454, 229.00095602294454, 229.00095602294454, 229.00095602294454],
                4.824900987654324,
                0.061468641975308644,
                [
                    0.015367160493827161,
                    0.015367160493827161,
                    0.015367160493827161,
                    0.015367160493827161,
                ],
            ),
        )

    def test_temps_after_pumping(self):
        volumes = [120.0, 37.5, 37.5, 37.5]
        temps_after_pumping = self.smarthotwatertank.temps_after_pumping(
            volume_pumped=10.0,
            remaining_vols=volumes,
            tank_layer_temperatures=self.smarthotwatertank._temp_n,
        )
        self.assertEqual(first=temps_after_pumping, second=[50.0, 50.0, 50.0, 50.0])

    def test_bottom_to_top_pump_volume(self):
        temp_s7_n = [60.0, 20.0, 25.0, 30.0, 35.0, 35.0, 35.0, 55.0]
        Qin = 1
        heater_layer = 7
        volumes = [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0]
        volume_pumped = self.smarthotwatertank.bottom_to_top_pump_volume(
            temp_s7_n=temp_s7_n, Qin=Qin, heater_layer=heater_layer, volumes=volumes
        )
        self.assertAlmostEqual(first=volume_pumped, second=14.853944719917525)

    def test_bottom_to_top_pump_volume_none_setpoint(self):
        """Test bottom_to_top_pump_volume when temp_setpnt_max.setpnt() returns None"""
        mock_setpoint = MagicMock()
        mock_setpoint.setpnt.return_value = None

        tank_with_none_setpoint = SmartHotWaterTank(
            volume=80.0,
            losses=1.0,
            init_temp=10.0,
            power_pump_kW=0.1,
            max_flow_rate_pump_l_per_min=10.0,
            temp_usable=40.0,
            temp_setpnt_max=mock_setpoint,
            cold_feed=self.coldfeed,
            simulation_time=self.simtime,
            heat_source_dict=self.heat_source_dict,
            project=DummyProject(temp_internal_air=20.0),
            external_conditions=self.extcond,
            detailed_output=False,
            nb_vol=8,
        )

        temp_s7_n = [60.0, 20.0, 25.0, 30.0, 35.0, 35.0, 35.0, 55.0]
        Qin = 1
        heater_layer = 7
        volumes = [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0]

        # This should use temp_usable (40.0) instead of the None setpoint
        volume_pumped = tank_with_none_setpoint.bottom_to_top_pump_volume(
            temp_s7_n=temp_s7_n, Qin=Qin, heater_layer=heater_layer, volumes=volumes
        )

        mock_setpoint.setpnt.assert_called_once()
        self.assertGreaterEqual(volume_pumped, 0.0)
