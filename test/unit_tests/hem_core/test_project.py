import pytest

from hem_core.input_output.input import Input
from hem_core.project import Project


def _create_minimal_proj_dict():
    """Create a minimal project dictionary."""
    num_timesteps = 8
    return {
        "temp_internal_air_static_calcs": 20.0,
        "SimulationTime": {
            "start": 0,
            "end": num_timesteps,
            "step": 1,
        },
        "ExternalConditions": {
            "air_temperatures": [10.0] * num_timesteps,
            "wind_speeds": [4.0] * num_timesteps,
            "wind_directions": [180] * num_timesteps,
            "diffuse_horizontal_radiation": [100] * num_timesteps,
            "direct_beam_radiation": [200] * num_timesteps,
            "solar_reflectivity_of_ground": [0.2] * num_timesteps,
            "latitude": 51.5,
            "longitude": -0.1,
            "direct_beam_conversion_needed": False,
            "shading_segments": [
                {"start360": 0, "end360": 360},
            ],
        },
        "InternalGains": {
            "total_internal_gains": {
                "start_day": 0,
                "time_series_step": 1,
                "schedule": {
                    "main": [0.0] * num_timesteps,
                },
            }
        },
        "ApplianceGains": {},
        "Zone": {
            "zone1": {
                "area": 50.0,
                "volume": 100.0,
                "temp_setpnt_init": 21.0,
                "BuildingElement": {
                    "wall1": {
                        "type": "BuildingElementOpaque",
                        "width": 5.0,
                        "height": 2.5,
                        "area": 12.5,
                        "base_height": 0,
                        "orientation360": 0,
                        "pitch": 90,
                        "solar_absorption_coeff": 0.6,
                        "u_value": 0.18,
                        "areal_heat_capacity": 110000,
                        "mass_distribution_class": "IE",
                    }
                },
                "ThermalBridging": {},
            }
        },
        "ColdWaterSource": {
            "mains water": {
                "start_day": 0,
                "time_series_step": 1,
                "temperatures": [10.0] * num_timesteps,
            }
        },
        "EnergySupply": {
            "mains elec": {
                "fuel": "electricity",
                "is_export_capable": False,
            }
        },
        "Control": {
            "min_temp": {
                "type": "SetpointTimeControl",
                "start_day": 0,
                "time_series_step": 1,
                "schedule": {
                    "main": [
                        {
                            "value": 50.0,
                            "repeat": num_timesteps,
                        }
                    ]
                },
            },
            "setpoint_temp_max": {
                "type": "SetpointTimeControl",
                "start_day": 0,
                "time_series_step": 1,
                "schedule": {
                    "main": [
                        {
                            "value": 60.0,
                            "repeat": num_timesteps,
                        }
                    ]
                },
            },
        },
        "Events": {
            "Shower": {},
            "Bath": {},
            "Other": {},
        },
        "InfiltrationVentilation": {
            "cross_vent_possible": False,
            "shield_class": "Normal",
            "terrain_class": "OpenField",
            "ventilation_zone_base_height": 2.5,
            "altitude": 30,
            "Vents": {},
            "Leaks": {
                "ventilation_zone_height": 6,
                "test_pressure": 50,
                "test_result": 1.2,
                "env_area": 220,
            },
        },
        "HotWaterDemand": {
            "Shower": {},
            "Bath": {},
            "Other": {},
            "Distribution": {},
        },
        "HotWaterSource": {},
        "WWHRS": {},
    }


def _create_preheated_water_source_storage_tank(name: str, cold_water_source_name: str) -> dict:
    """Helper to create a PreHeatedWaterSource StorageTank configuration"""
    return {
        "type": "StorageTank",
        "volume": 24.0,
        "daily_losses": 1.55,
        "init_temp": 48.0,
        "ColdWaterSource": cold_water_source_name,
        "HeatSource": {
            f"{name}_immersion": {
                "type": "ImmersionHeater",
                "power": 3.0,
                "EnergySupply": "mains elec",
                "Controlmin": "min_temp",
                "Controlmax": "setpoint_temp_max",
                "heater_position": 0.3,
                "thermostat_position": 0.33,
            }
        },
    }


def test_preheated_water_source_initialization_order_independent():
    """Test that PreHeatedWaterSource objects can be initialized in any order."""
    proj_dict = _create_minimal_proj_dict()

    proj_dict["PreHeatedWaterSource"] = {
        "tank1": _create_preheated_water_source_storage_tank(
            name="tank1", cold_water_source_name="tank2"
        ),
        "tank2": _create_preheated_water_source_storage_tank(
            name="tank2", cold_water_source_name="mains water"
        ),
    }

    project_input = Input.model_validate(proj_dict)

    project = Project(
        proj_dict=proj_dict,
        project_input=project_input,
        print_heat_balance=False,
        detailed_output_heating_cooling=False,
        use_fast_solver=False,
        tariff_data_filename=None,
        display_progress=False,
    )

    pre_heated_sources = project._Project__pre_heated_water_sources  # type: ignore[reportAttributeAccessIssue]
    assert "tank1" in pre_heated_sources
    assert "tank2" in pre_heated_sources


def test_preheated_water_source_circular_reference_detection():
    """
    Test that circular references between PreHeatedWaterSource objects
    are detected and raise an appropriate error.
    """
    proj_dict = _create_minimal_proj_dict()

    proj_dict["PreHeatedWaterSource"] = {
        "tank1": _create_preheated_water_source_storage_tank(
            name="tank1", cold_water_source_name="tank2"
        ),
        "tank2": _create_preheated_water_source_storage_tank(
            name="tank2", cold_water_source_name="tank1"
        ),
    }

    project_input = Input.model_validate(proj_dict)

    with pytest.raises(ValueError, match=r"circular|cycle"):
        Project(
            proj_dict=proj_dict,
            project_input=project_input,
            print_heat_balance=False,
            detailed_output_heating_cooling=False,
            use_fast_solver=False,
            tariff_data_filename=None,
            display_progress=False,
        )


def test_preheated_water_source_chain_of_dependencies():
    """Test that chains of dependencies work regardless of initialization order."""
    proj_dict = _create_minimal_proj_dict()

    proj_dict["PreHeatedWaterSource"] = {
        "tank1": _create_preheated_water_source_storage_tank(
            name="tank1", cold_water_source_name="tank2"
        ),
        "tank2": _create_preheated_water_source_storage_tank(
            name="tank2", cold_water_source_name="tank3"
        ),
        "tank3": _create_preheated_water_source_storage_tank(
            name="tank3", cold_water_source_name="mains water"
        ),
    }

    project_input = Input.model_validate(proj_dict)

    project = Project(
        proj_dict=proj_dict,
        project_input=project_input,
        print_heat_balance=False,
        detailed_output_heating_cooling=False,
        use_fast_solver=False,
        tariff_data_filename=None,
        display_progress=False,
    )

    pre_heated_sources = project._Project__pre_heated_water_sources  # type: ignore[reportAttributeAccessIssue]
    assert "tank1" in pre_heated_sources
    assert "tank2" in pre_heated_sources
    assert "tank3" in pre_heated_sources
