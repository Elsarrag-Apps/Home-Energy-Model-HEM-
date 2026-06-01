import importlib.metadata
import json
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any

import pydantic
import pytest
from pydantic import BaseModel, ValidationError

from hem_core.input_output.enums import (
    AirFlowType,
    BatteryLocation,
    BuildingElementType,
    DuctType,
    EcoDesignControllerClass,
    FloorType,
    FuelType,
    HeatPumpBackupControlType,
    HeatPumpSinkType,
    HeatPumpSourceType,
    HeatSourceLocation,
    InverterType,
    MassDistributionClass,
    MechVentType,
    PartyWallCavityType,
    PartyWallLiningType,
    ShadingObjectType,
    ShowerType,
    TerrainClass,
    ThermalBridgingType,
    VentilationShieldClass,
    WaterPipeworkLocation,
    WindShieldLocation,
)
from hem_core.input_output.input import (
    AirTerminalDevice,
    ApplianceGains,
    ApplianceGainsEvent,
    ApplianceLoadShifting,
    Bath,
    BoilerBase,
    BoilerCostScheduleHybrid,
    BuildingElementAdjacentConditionedSpace,
    BuildingElementAdjacentUnconditionedSpaceSimple,
    BuildingElementCommonBase,
    BuildingElementCommonBaseNotGround,
    BuildingElementExposedToSolarRadiation,
    BuildingElementGroundHeatedBasement,
    BuildingElementGroundSuspendedFloor,
    BuildingElementGroundUnheatedBasement,
    BuildingElementNotTransparent,
    BuildingElementOpaque,
    BuildingElementPartyWall,
    BuildingElementTransparent,
    ColdWaterSource,
    ControlChargeTarget,
    ControlCombination,
    ControlCombinations,
    ControlOnOffCostMinimising,
    ControlSetpointTimer,
    EdgeInsulationHorizontal,
    EdgeInsulationVertical,
    ElectricBattery,
    EnergySupply,
    ExternalConditionsInput,
    ExternalSensorCorrelation,
    FancoilTestData,
    FanSpeedData,
    HeatPumpBoiler,
    HeatPumpBufferTank,
    HeatPumpHotWaterOnly,
    HeatPumpHotWaterOnlyTestDatum,
    HeatPumpTestDatum,
    HeatSourceWetHeatBatteryPCM,
    HeatSourceWetHeatPump,
    HeatSourceWetHIU,
    HeatSourceWetServiceWaterRegular,
    HotWaterSourceCombiBoiler,
    HotWaterSourceHUI,
    HotWaterSourcePointOfUse,
    HotWaterSourceSmartHotWaterTank,
    ImmersionHeater,
    InfiltrationVentilation,
    Input,
    InternalGains,
    InternalGainsDetails,
    MechanicalVentilation,
    MechanicalVentilationDuctwork,
    Metadata,
    OtherWaterUse,
    PhotovoltaicPanel,
    PhotovoltaicSystem,
    PhotovoltaicSystemWithPanels,
    ScheduleForBoolean,
    ScheduleForDegreesCelsius,
    ScheduleForDouble,
    ScheduleRepeaterForBoolean,
    ScheduleRepeaterForDegreesCelsius,
    ScheduleRepeaterForDouble,
    ShadingObject,
    ShadingSegment,
    ShowerInstantElectric,
    ShowerMixer,
    SimulationTime,
    SmartApplianceBattery,
    SmartApplianceControl,
    SolarThermalSystem,
    SpaceCoolSystemAirConditioning,
    SpaceHeatSystemElectricStorageHeater,
    SpaceHeatSystemHeatSource,
    SpaceHeatSystemInstantElectricHeater,
    SpaceHeatSystemWarmAir,
    SpaceHeatSystemWetDistribution,
    StorageTank,
    ThermalBridgingLinear,
    TimeSeriesBase,
    UniqueStringList,
    Vent,
    VentilationLeaks,
    WasteWaterHeatRecoverySystem,
    WaterHeatingEvent,
    WaterPipework,
    WaterPipeworkSimple,
    WetEmitterFanCoil,
    WetEmitterRadiator,
    WetEmitterUFH,
    WindowPart,
    WindowShadingObject,
    WindowShadingObstacle,
    WindowTreatment,
    Zone,
)
from hem_core.schema_utils import write_schema_files

PATH_ROOT = Path(__file__).parent.parent.parent.parent.parent
PATH_SCHEMAS = PATH_ROOT / "schemas"

logger = logging.getLogger(__name__)


class TestInput:
    """Test class for core Input validation and schema generation."""

    def test_demo_files_validation(self, demo_file: Path):
        """Test that all demo files in core folder validate against the core Input schema."""
        # Try to read the demo file
        with open(demo_file, "r", encoding="utf-8") as file:
            demo_file_json = file.read()

        validated_input = Input.model_validate_json(demo_file_json)
        assert isinstance(validated_input, Input)

    def test_core_input_schema_generation_is_up_to_date(self, tmp_path: Path):
        """
        Test that ensures the core Input JSON schema file is always up-to-date with the Pydantic models.
        This catches schema drift if the models are modified but schemas aren't regenerated.
        """
        core_schema_filename = Path("core-input.json")
        existing_core_input_schema_path = PATH_SCHEMAS / core_schema_filename
        assert existing_core_input_schema_path.exists()

        write_schema_files(schema_path=tmp_path)
        temp_core_schema_path = tmp_path / core_schema_filename
        assert temp_core_schema_path.exists(), f"Temporary {core_schema_filename} was not written"

        # The schemas should be identical.
        with open(existing_core_input_schema_path) as file:
            existing_core_input_schema_str = file.read()
        with open(temp_core_schema_path) as file:
            temp_core_schema_str = file.read()

        assert temp_core_schema_str == existing_core_input_schema_str

    def test_core_input_schema_structure_validation(self):
        """Test that the core Input schema has the expected structure and required fields."""
        schema = Input.model_json_schema()

        # Basic schema structure validation
        assert isinstance(schema, dict)
        assert "title" in schema
        assert schema["title"] == "Input"
        assert "type" in schema
        assert "properties" in schema
        assert "required" in schema

        # Check that key required fields are present in core Input schema
        # NOTE: Using actual PascalCase field names from the schema (not snake_case)
        required_fields = schema.get("required", [])
        expected_core_fields = [
            "ColdWaterSource",
            "EnergySupply",
            "Events",
            "ExternalConditions",
            "HotWaterDemand",
            "HotWaterSource",
            "InfiltrationVentilation",
            "InternalGains",
            "SimulationTime",
            "Zone",
            "temp_internal_air_static_calcs",
        ]

        for field in expected_core_fields:
            assert field in required_fields, (
                f"Expected required field '{field}' not found in schema required fields: {required_fields}"
            )

        # Verify properties exist for required fields
        properties = schema.get("properties", {})
        for field in expected_core_fields:
            assert field in properties, (
                f"Required field '{field}' should have a property definition"
            )

    def test_core_input_can_generate_valid_schema(self):
        """Test that core Input can generate a valid JSON schema without errors."""
        schema = Input.model_json_schema()

        # Test that schema is valid JSON by serializing and deserializing
        schema_json = json.dumps(schema)
        parsed_schema = json.loads(schema_json)

        # Basic validation that it's a proper JSON Schema
        assert isinstance(parsed_schema, dict)
        assert len(parsed_schema.get("properties", {})) > 0, (
            "Schema should have at least one property"
        )

    def test_core_schema_contains_expected_definitions(self):
        """Test that the core schema contains expected model definitions."""
        schema = Input.model_json_schema()

        # Check for $defs section (Pydantic v2 style) or definitions (older style)
        definitions = schema.get("$defs") or schema.get("definitions", {})

        assert len(definitions) > 0, "Schema should contain model definitions"

        # Check for some expected model definitions in core schema
        expected_models = ["Zone", "EnergySupply", "SimulationTime", "BuildingElement"]
        found_models = []

        for model_name in expected_models:
            if any(model_name in def_name for def_name in definitions.keys()):
                found_models.append(model_name)

        assert len(found_models) > 0, "Schema should contain definitions for some expected models."

    def test_validate_shower_waste_water_heat_recovery_systems_empty(
        self, baseline_demo_file_dict: Path
    ):
        """Test WWHRS validation with empty configuration."""
        modified_input = baseline_demo_file_dict | {"WWHRS": None, "HotWaterDemand": {}}
        validated_input = Input.model_validate(modified_input)
        assert isinstance(validated_input, Input)

    def test_validate_shower_waste_water_heat_recovery_systems_valid_mixer_shower(
        self, baseline_demo_file_dict: dict
    ):
        """Test WWHRS validation with valid mixer shower configuration."""
        modified_input = baseline_demo_file_dict | {
            "WWHRS": {
                "WWHRS1": {
                    "ColdWaterSource": "mains water",
                    "flow_rates": [5, 7, 9, 11, 13],
                    "system_a_efficiencies": [44.8, 39.1, 34.8, 31.4, 28.6],
                    "system_a_utilisation_factor": 0.7,
                    "system_b_efficiency_factor": 0.81,
                    "type": "WWHRS_Instantaneous",
                }
            },
            "HotWaterDemand": {
                "Shower": {
                    "Shower1": {
                        "type": "MixerShower",
                        "ColdWaterSource": "mains water",
                        "flowrate": 15,
                        "WWHRS": "WWHRS1",
                        "WWHRS_configuration": "B",
                    },
                },
            },
        }
        validated_input = Input.model_validate(modified_input)
        assert isinstance(validated_input, Input)

    def test_validate_shower_waste_water_heat_recovery_systems_invalid_reference(
        self, baseline_demo_file_dict: dict
    ):
        """Test WWHRS validation with invalid WWHRS reference."""
        modified_input = baseline_demo_file_dict | {
            "WWHRS": {
                "WWHRS1": {
                    "type": "WWHRS_Instantaneous",
                    "ColdWaterSource": "mains water",
                    "system_a_efficiencies": [1.0],
                    "flow_rates": [1.0],
                    "system_a_utilisation_factor": 1.0,
                }
            },
            "HotWaterDemand": {
                "Shower": {
                    "Shower1": {
                        "type": "MixerShower",
                        "ColdWaterSource": "mains water",
                        "flowrate": 15,
                        "WWHRS": "WWHRS1",
                        "WWHRS_configuration": "A",
                    },
                    "Shower2": {
                        "type": "MixerShower",
                        "ColdWaterSource": "mains water",
                        "flowrate": 15,
                        "WWHRS": "WWHRS2",  # This doesn't exist!
                        "WWHRS_configuration": "B",
                    },
                },
            },
        }
        with pytest.raises(ValidationError, match="WWHRS"):
            Input.model_validate(modified_input)

    def test_validate_exhaust_air_heat_pump_ventilation_compatibility_valid_combinations(
        self, baseline_demo_file_dict: dict
    ):
        """Test that compatible exhaust air heat pump and ventilation combinations pass validation."""
        valid_combinations = [
            ("ExhaustAirMEV", "MVHR"),
            ("ExhaustAirMEV", "Centralised continuous MEV"),
            ("ExhaustAirMVHR", "MVHR"),
            ("ExhaustAirMixed", "MVHR"),
        ]

        for source_type, vent_type in valid_combinations:
            modified_input = self._create_exhaust_air_heat_pump_config(
                baseline_demo_file_dict, source_type, vent_type
            )
            modified_input["Control"]["MVHR_Control"] = self._create_control_config()
            modified_input["Control"]["Centralised_continuous_MEV_Control"] = (
                self._create_control_config()
            )
            # Should not raise any exception
            validated_input = Input.model_validate(modified_input)
            assert isinstance(validated_input, Input)

    def test_validate_exhaust_air_heat_pump_ventilation_compatibility_invalid_combinations(
        self, baseline_demo_file_dict: dict
    ):
        """Test that incompatible exhaust air heat pump and ventilation combinations fail validation."""
        invalid_combinations = [
            ("ExhaustAirMEV", "Intermittent MEV"),
            ("ExhaustAirMEV", "Decentralised continuous MEV"),
            ("ExhaustAirMVHR", "Intermittent MEV"),
            ("ExhaustAirMixed", "Decentralised continuous MEV"),
        ]

        for source_type, vent_type in invalid_combinations:
            modified_input = self._create_exhaust_air_heat_pump_config(
                baseline_demo_file_dict, source_type, vent_type
            )
            modified_input["Control"]["Intermittent_MEV_Control"] = self._create_control_config()
            modified_input["Control"]["Decentralised_continuous_MEV_Control"] = (
                self._create_control_config()
            )
            with pytest.raises(Exception) as excinfo:
                Input.model_validate(modified_input)
            error_message = str(excinfo.value)
            assert "System incompatibilities found" in error_message
            assert source_type in error_message
            assert vent_type in error_message

    def test_validate_exhaust_air_heat_pump_ventilation_compatibility_edge_cases(
        self, baseline_demo_file_dict: dict
    ):
        """Test edge cases where validation should pass regardless of configuration."""
        # Test case 1: No heat pumps
        modified_input = deepcopy(baseline_demo_file_dict)
        modified_input["InfiltrationVentilation"]["MechanicalVentilation"] = {
            "mechvent1": self._create_ventilation_config("Intermittent MEV")
        }
        modified_input["Control"]["Intermittent_MEV_Control"] = self._create_control_config()
        # Should not raise any exception
        validated_input = Input.model_validate(modified_input)
        assert isinstance(validated_input, Input)

        # Test case 2: No mechanical ventilation
        modified_input = deepcopy(baseline_demo_file_dict)
        modified_input["HeatSourceWet"] = self._create_heat_pump_config("ExhaustAirMEV")
        modified_input["InfiltrationVentilation"]["MechanicalVentilation"] = {
            "mechvent1": self._create_ventilation_config("Centralised continuous MEV")
        }
        modified_input["Control"]["Centralised_continuous_MEV_Control"] = (
            self._create_control_config()
        )
        # Should not raise any exception
        validated_input = Input.model_validate(modified_input)
        assert isinstance(validated_input, Input)

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"path": ["ApplianceGains", "lighting", "EnergySupply"]},
                "ApplianceGains.energy_supply",
            ),
            (
                {"path": ["ApplianceGains", "lighting", "loadshifting", "Control"]},
                "ApplianceLoadShifting.control",
            ),
            (
                {"path": ["HotWaterSource", "hw cylinder", "ColdWaterSource"]},
                "HotWaterSourceCombiBoiler.cold_water_source",
            ),
            (
                {"path": ["HotWaterSource", "hw cylinder", "HeatSourceWet"]},
                "HotWaterSourceCombiBoiler.heat_source_wet",
            ),
            (
                {"path": ["SpaceHeatSystem", "main", "Zone"]},
                "SpaceHeatSystemElectricStorageHeater.zone",
            ),
            (
                {"path": ["HeatSourceWet", "boiler", "MechanicalVentilation"]},
                "HeatSourceWetHeatPump.mechanical_ventilation",
            ),
        ],
    )
    def test_validate_cross_references(
        self,
        inputs: dict[str, list[str]],
        expected_message: str,
        baseline_demo_file_dict: dict,
    ):
        # make baseline_demo_file_dict valid first
        modified_input = self._create_valid_input(baseline_demo_file_dict)
        Input.model_validate(modified_input)

        path = inputs["path"]
        temp = modified_input
        for p in path[:-1]:
            temp = temp[p]
        temp[path[-1]] = "incorrect"

        with pytest.raises(ValidationError, match=expected_message):
            Input.model_validate(modified_input)

    def test_validate_multiple_cross_references(
        self,
        baseline_demo_file_dict: dict,
    ):
        """Test invalid cross-reference keys."""
        modified_input = baseline_demo_file_dict

        # Test EnergySupplyReference
        modified_input["ApplianceGains"]["lighting"]["EnergySupply"] = "incorrect"

        # Test ControlReference
        modified_input["ApplianceGains"]["lighting"]["loadshifting"] = (
            self._create_loadshifting_config()
        )
        modified_input["ApplianceGains"]["lighting"]["loadshifting"]["Control"] = "incorrect"

        # Test ColdWaterSourceReference
        # Test HeatSourceWetReference
        modified_input["HotWaterSource"]["hw cylinder"] = self._create_combiboiler_config()
        modified_input["HotWaterSource"]["hw cylinder"]["ColdWaterSource"] = "incorrect"
        modified_input["HotWaterSource"]["hw cylinder"]["HeatSourceWet"] = "incorrect"

        # Test ZoneReference
        modified_input["SpaceHeatSystem"] = {}
        modified_input["SpaceHeatSystem"]["main"] = self._create_elec_storage_heater_config()
        modified_input["SpaceHeatSystem"]["main"]["Zone"] = "incorrect"

        # Test MechanicalVentilation
        modified_input["HeatSourceWet"] = self._create_heat_pump_config("ExhaustAirMEV")
        modified_input["HeatSourceWet"]["hp"]["MechanicalVentilation"] = "incorrect"

        try:
            Input.model_validate(modified_input)
        except ValidationError as e:
            errors = e.errors()
            assert len(errors) == 6
            for error in errors:
                loc = error.get("loc")[0]
                match loc:
                    case "ApplianceGains.energy_supply":
                        assert (
                            error["msg"]
                            == 'Provided ApplianceGains.energy_supply key ("incorrect") does not exist in Input.energy_supply'
                        )
                    case "ApplianceLoadShifting.control":
                        assert (
                            error["msg"]
                            == 'Provided ApplianceLoadShifting.control key ("incorrect") does not exist in Input.control or Input.smart_appliance_controls'
                        )
                    case "HotWaterSourceCombiBoiler.cold_water_source":
                        assert (
                            error["msg"]
                            == 'Provided HotWaterSourceCombiBoiler.cold_water_source key ("incorrect") does not exist in Input.cold_water_source or Input.pre_heated_water_source or Input.waste_water_heat_recovery_systems'
                        )
                    case "HotWaterSourceCombiBoiler.heat_source_wet":
                        assert (
                            error["msg"]
                            == 'Provided HotWaterSourceCombiBoiler.heat_source_wet key ("incorrect") does not exist in Input.heat_source_wet'
                        )
                    case "SpaceHeatSystemElectricStorageHeater.zone":
                        assert (
                            error["msg"]
                            == 'Provided SpaceHeatSystemElectricStorageHeater.zone key ("incorrect") does not exist in Input.zone'
                        )
                    case "HeatSourceWetHeatPump.mechanical_ventilation":
                        assert (
                            error["msg"]
                            == 'Provided HeatSourceWetHeatPump.mechanical_ventilation key ("incorrect") does not exist in Input.infiltration_ventilation.mechanical_ventilation'
                        )
                    case _:  # pragma: no cover
                        pytest.fail("An error occurred: no match found for loc")  # pragma: no cover

    def _create_valid_input(self, baseline_demo_file_dict: dict) -> dict:
        modified_input = baseline_demo_file_dict
        modified_input["ApplianceGains"]["lighting"]["loadshifting"] = (
            self._create_loadshifting_config()
        )
        modified_input["HotWaterSource"]["hw cylinder"] = self._create_combiboiler_config()
        modified_input["SpaceHeatSystem"] = {}
        modified_input["SpaceHeatSystem"]["main"] = self._create_elec_storage_heater_config()
        modified_input["HeatSourceWet"] = self._create_heat_pump_config("ExhaustAirMEV")
        modified_input["Control"]["SmartApplianceControl"] = self._create_control_config()
        modified_input["Control"]["Centralised_continuous_MEV_Control"] = (
            self._create_control_config()
        )
        modified_input["HeatSourceWet"] = self._create_heat_pump_config("ExhaustAirMEV")
        modified_input["HeatSourceWet"]["boiler"] = modified_input["HeatSourceWet"]["hp"]
        del modified_input["HeatSourceWet"]["hp"]
        modified_input["InfiltrationVentilation"]["MechanicalVentilation"] = {}
        modified_input["InfiltrationVentilation"]["MechanicalVentilation"]["mechvent1"] = (
            self._create_ventilation_config("Centralised continuous MEV")
        )
        return modified_input

    def _create_heat_pump_config(self, source_type):
        """Helper method to create heat pump configuration."""
        return {
            "hp": {
                "type": "HeatPump",
                "EnergySupply": "mains elec",
                "source_type": source_type,
                "sink_type": "Water",
                "backup_ctrl_type": "TopUp",
                "time_delay_backup": 1.0,
                "modulating_control": True,
                "min_modulation_rate_35": 0.35,
                "min_modulation_rate_55": 0.4,
                "time_constant_onoff_operation": 140,
                "temp_return_feed_max": 70.0,
                "temp_lower_operating_limit": -5.0,
                "min_temp_diff_flow_return_for_hp_to_operate": 0.0,
                "var_flow_temp_ctrl_during_test": True,
                "power_heating_circ_pump": 0.015,
                "power_source_circ_pump": 0.010,
                "power_standby": 0.015,
                "power_crankcase_heater": 0.01,
                "power_off": 0.015,
                "power_max_backup": 3.0,
                "MechanicalVentilation": "mechvent1",
                "test_data_EN14825": [self._MINIMAL_TEST_DATA],
            }
        }

    @staticmethod
    def _create_ventilation_config(vent_type: str) -> dict[str, Any]:
        """Helper method to create ventilation configuration."""
        # MVHR systems use a different structure
        if vent_type == "MVHR":
            return {
                "sup_air_flw_ctrl": "ODA",
                "sup_air_temp_ctrl": "NO_CTRL",
                "vent_type": vent_type,
                "SFP": 1.5,
                "EnergySupply": "mains elec",
                "design_outdoor_air_flow_rate": 0.5,
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
                "mvhr_eff": 0.80,
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
                        "cross_section_shape": "circular",
                        "internal_diameter_mm": 200,
                        "external_diameter_mm": 300,
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
            }

        # Non-MVHR systems use a single position fields
        return {
            "sup_air_flw_ctrl": "ODA",
            "sup_air_temp_ctrl": "NO_CTRL",
            "vent_type": vent_type,
            "Control": f"{vent_type.replace(' ', '_')}_Control",
            "SFP": 1.5,
            "EnergySupply": "mains elec",
            "design_outdoor_air_flow_rate": 0.5,
            "orientation360": 180,
            "pitch": 90,
            "mid_height_air_flow_path": 2,
        }

    def _create_control_config(self):
        return {
            "type": "SetpointTimeControl",
            "start_day": 0,
            "time_series_step": 0.5,
            "schedule": {"main": [{"repeat": 7, "value": "day"}]},
        }

    def _create_combiboiler_config(self) -> dict:
        return {
            "type": "CombiBoiler",
            "ColdWaterSource": "mains water",
            "HeatSourceWet": "boiler",
            "separate_DHW_tests": "M&L",
            "rejected_energy_1": 0.0004,
            "storage_loss_factor_2": 0.91574,
            "rejected_factor_3": 0,
            "setpoint_temp": 60.0,
            "daily_HW_usage": 120,
        }

    def _create_elec_storage_heater_config(self) -> dict:
        return {
            "type": "ElecStorageHeater",
            "pwr_in": 3.7,
            "rated_power_instant": 2.5,
            "storage_capacity": 20,
            "state_of_charge_init": 0,
            "air_flow_type": "fan-assisted",
            "frac_convective": 0.7,
            "fan_pwr": 11.0,
            "n_units": 1,
            "EnergySupply": "mains elec",
            "Control": "hw timer",
            "ControlCharger": "hw timer",
            "Zone": "zone 1",
            "dry_core_min_output": [
                [0, 0],
                [0.001, 0.0000005],
                [0.002, 0.000002],
                [0.003, 0.0000045],
                [0.005, 0.0000125],
                [0.0075, 0.000028125],
                [0.01, 0.00005],
                [0.015, 0.0001125],
                [0.02, 0.0002],
                [0.03, 0.00045],
                [0.05, 0.00125],
                [0.1, 0.005],
                [0.2, 0.02],
                [0.3, 0.045],
                [0.4, 0.08],
                [0.5, 0.125],
                [0.6, 0.18],
                [0.7, 0.245],
                [0.8, 0.32],
                [0.9, 0.405],
                [1, 0.5],
            ],
            "dry_core_max_output": [
                [0, 0],
                [0.001, 1.40420839159243],
                [0.002, 1.66989461022824],
                [0.003, 1.84804217294461],
                [0.005, 2.09978130694835],
                [0.0075, 2.32379000772445],
                [0.01, 2.49707487017269],
                [0.015, 2.76346761095814],
                [0.02, 2.96953920230386],
                [0.03, 3.286335345031],
                [0.05, 3.73399786373087],
                [0.1, 4.44049682695371],
                [0.2, 5.28067042076036],
                [0.3, 5.84402247855178],
                [0.4, 6.27981083635263],
                [0.5, 6.64009151820193],
                [0.6, 6.94975311172961],
                [0.7, 7.2228080610163],
                [0.8, 7.46799572746174],
                [0.9, 7.69116611513221],
                [1, 7.89644407771495],
            ],
        }

    def _create_loadshifting_config(self) -> dict:
        return {
            "Control": "SmartApplianceControl",
            "demand_limit_weighted": 14,
            "max_shift_hrs": 12,
            "priority": 2,
            "weight_timeseries": [7 * 24],
        }

    def _create_exhaust_air_heat_pump_config(self, base_input, source_type, vent_type):
        """Helper method to create complete exhaust air heat pump configuration."""
        modified_input = base_input
        modified_input.update(
            {
                "HeatSourceWet": self._create_heat_pump_config(source_type),
                "InfiltrationVentilation": {
                    **base_input.get("InfiltrationVentilation", {}),
                    "MechanicalVentilation": {
                        "mechvent1": self._create_ventilation_config(vent_type)
                    },
                },
            }
        )
        return modified_input

    # Minimal test data constant
    _MINIMAL_TEST_DATA = {
        "air_flow_rate": 100.0,
        "test_letter": "A",
        "capacity": 8.4,
        "cop": 4.6,
        "design_flow_temp": 35,
        "temp_outlet": 34,
        "temp_source": 0,
        "temp_test": -7,
    }

    def test_validate_time_series(
        self,
        baseline_demo_file_dict: Path,
    ):
        modified_input = baseline_demo_file_dict
        modified_input["ColdWaterSource"]["mains water"]["temperatures"] = [0.0]

        with pytest.raises(
            ValidationError,
            match="ColdWaterSource.temperatures does not contain enough values to cover the simulation.",
        ):
            Input.model_validate(modified_input)


class TestTimeSeriesBase:
    @pytest.fixture
    def valid_example(self) -> TimeSeriesBase:
        return TimeSeriesBase(
            start_day=12,
            time_series_step=12,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"start_day": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"start_day": 366},
                "Input should be less than or equal to 365",
            ),
            (
                {"time_series_step": 0},
                "Input should be greater than 0",
            ),
            (
                {"time_series_step": 25},
                "Input should be less than or equal to 24",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: TimeSeriesBase,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            TimeSeriesBase(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestMetadata:
    def test_validate_hem_core_version(self, caplog):
        # Test Metadata without hem_core_version
        metadata = Metadata()
        assert metadata.hem_core_version is None
        metadata = Metadata(hem_core_version=None)
        assert metadata.hem_core_version is None

        # Test Metadata with a hem_core_version different from the core engine version
        caplog.set_level(logging.WARNING)
        engine_version = importlib.metadata.version("hem-core")
        Metadata(hem_core_version="0.0")
        assert (
            f"Core engine version ({engine_version}) does not match target version (0.0) suggested by metadata section of input file."
            in caplog.text
        )


class TestApplianceGainsEvent:
    @pytest.fixture
    def valid_example(self) -> ApplianceGainsEvent:
        return ApplianceGainsEvent(duration=7, start=6, demand_W=2000)

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"demand_W": -1},
                "Input should be greater than 0",
            ),
            (
                {"duration": -1},
                "Input should be greater than 0",
            ),
            (
                {"start": -1},
                "Input should be greater than or equal to 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: ApplianceGainsEvent,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            ApplianceGainsEvent(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestApplianceLoadShifting:
    @pytest.fixture
    def valid_example(self) -> ApplianceLoadShifting:
        return ApplianceLoadShifting(
            demand_limit_weighted=14,
            max_shift_hrs=12,
            weight_timeseries=[],
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"demand_limit_weighted": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"max_shift_hrs": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"max_shift_hrs": 25},
                "Input should be less than or equal to 24",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: ApplianceLoadShifting,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            ApplianceLoadShifting(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestColdWaterSource:
    @pytest.fixture
    def valid_example(self) -> ColdWaterSource:
        return ColdWaterSource(start_day=1, time_series_step=1, temperatures=[14])

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"temperatures": [-1]},
                "Input should be greater than or equal to 0",
            ),
            (
                {"temperatures": [101]},
                "Input should be less than or equal to 100",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: ColdWaterSource,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            ColdWaterSource(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestElectricBattery:
    @pytest.fixture
    def valid_example(self) -> ElectricBattery:
        return ElectricBattery(
            battery_age=1,
            battery_location=BatteryLocation.OUTSIDE,
            capacity=1,
            charge_discharge_efficiency_round_trip=0.8,
            grid_charging_possible=True,
            maximum_discharge_rate_one_way_trip=1.25,
            maximum_charge_rate_one_way_trip=1.5,
            minimum_charge_rate_one_way_trip=0.001,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"battery_age": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"capacity": 0},
                "Input should be greater than 0",
            ),
            (
                {"maximum_charge_rate_one_way_trip": 0},
                "Input should be greater than 0",
            ),
            (
                {"maximum_discharge_rate_one_way_trip": 0},
                "Input should be greater than 0",
            ),
            (
                {"minimum_charge_rate_one_way_trip": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"charge_discharge_efficiency_round_trip": -1},
                "Input should be greater than 0",
            ),
            (
                {"charge_discharge_efficiency_round_trip": 2},
                "Input should be less than or equal to 1",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: ElectricBattery,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            ElectricBattery(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestExternalSensorCorrelation:
    @pytest.fixture
    def valid_example(self) -> ExternalSensorCorrelation:
        return ExternalSensorCorrelation(
            temperature=15,
            max_charge=0.4,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"temperature": -274},
                "Input should be greater than or equal to -273.15",
            ),
            (
                {"max_charge": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"max_charge": 2},
                "Input should be less than or equal to 1",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: ExternalSensorCorrelation,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            ExternalSensorCorrelation(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestFanSpeedData:
    @pytest.fixture
    def valid_example(self) -> FanSpeedData:
        return FanSpeedData(
            power_output=[],
            temperature_diff=10,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"power_output": [-1]},
                "Input should be greater than or equal to 0",
            ),
            (
                {"temperature_diff": 0},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: FanSpeedData,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            FanSpeedData(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestBoilerBase:
    @pytest.fixture
    def valid_example(self) -> BoilerBase:
        return BoilerBase(
            EnergySupply="mains elec",
            EnergySupply_aux="mains elec",
            boiler_location="internal",
            efficiency_full_load=1,
            efficiency_part_load=1,
            electricity_circ_pump=10,
            electricity_full_load=1,
            electricity_part_load=1,
            electricity_standby=10,
            modulation_load=1,
            rated_power=10,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"efficiency_full_load": 0},
                "Input should be greater than 0",
            ),
            (
                {"efficiency_full_load": 2},
                "Input should be less than or equal to 1",
            ),
            (
                {"efficiency_part_load": -1},
                "Input should be greater than 0",
            ),
            (
                {"efficiency_part_load": 2},
                "Input should be less than or equal to 1.12",
            ),
            (
                {"modulation_load": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"modulation_load": 2},
                "Input should be less than or equal to 1",
            ),
            (
                {"electricity_circ_pump": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"electricity_full_load": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"electricity_part_load": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"electricity_standby": -0.1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"rated_power": 0},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: BoilerBase,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            BoilerBase(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestHeatSourceWetHeatBattery:
    @pytest.fixture
    def valid_example(self) -> HeatSourceWetHeatBatteryPCM:
        return HeatSourceWetHeatBatteryPCM(
            type="HeatBattery",
            battery_type="pcm",  # Add the discriminator field
            A=3.532,
            B=4.415,
            ControlCharge="control",
            EnergySupply="mains elec",
            inlet_diameter_mm=6.5,
            electricity_circ_pump=0.0600,
            electricity_standby=0.0244,
            flow_rate_l_per_min=10,
            heat_storage_kJ_per_K_above_Phase_transition=381.5,
            heat_storage_kJ_per_K_below_Phase_transition=305.2,
            heat_storage_kJ_per_K_during_Phase_transition=12317,
            max_temperature=25,
            temp_init=25,
            max_rated_losses=0.22,
            number_of_units=1,
            phase_transition_temperature_lower=57,
            phase_transition_temperature_upper=59,
            rated_charge_power=10,
            simultaneous_charging_and_discharging=True,
            velocity_in_HEX_tube_at_1_l_per_min_m_per_s=0.035,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"inlet_diameter_mm": 0},
                "Input should be greater than 0",
            ),
            (
                {"flow_rate_l_per_min": 0},
                "Input should be greater than 0",
            ),
            (
                {"heat_storage_kJ_per_K_above_Phase_transition": 0},
                "Input should be greater than 0",
            ),
            (
                {"heat_storage_kJ_per_K_below_Phase_transition": 0},
                "Input should be greater than 0",
            ),
            (
                {"heat_storage_kJ_per_K_during_Phase_transition": 0},
                "Input should be greater than 0",
            ),
            (
                {"rated_charge_power": 0},
                "Input should be greater than 0",
            ),
            (
                {"velocity_in_HEX_tube_at_1_l_per_min_m_per_s": 0},
                "Input should be greater than 0",
            ),
            (
                {"electricity_circ_pump": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"electricity_standby": 0},
                "Input should be greater than 0",
            ),
            (
                {"max_rated_losses": 0},
                "Input should be greater than 0",
            ),
            (
                {"number_of_units": 0},
                "Input should be greater than or equal to 1",
            ),
            (
                {"max_temperature": -9999},
                "Input should be greater than or equal to -273.15",
            ),
            (
                {"phase_transition_temperature_upper": -9999},
                "Input should be greater than or equal to -273.15",
            ),
            (
                {"phase_transition_temperature_lower": -9999},
                "Input should be greater than or equal to -273.15",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: HeatSourceWetHeatBatteryPCM,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            HeatSourceWetHeatBatteryPCM(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestHeatSourceWetHIU:
    @pytest.fixture
    def valid_example(self) -> HeatSourceWetHIU:
        return HeatSourceWetHIU(
            type="HIU",
            EnergySupply="mains elec",
            HIU_daily_loss=0.8,
            building_level_distribution_losses=62,
            power_max=3.0,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"power_max": 0},
                "Input should be greater than 0",
            ),
            (
                {"HIU_daily_loss": 0},
                "Input should be greater than 0",
            ),
            (
                {"building_level_distribution_losses": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"power_circ_pump": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"power_aux": 0},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: HeatSourceWetHIU,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            HeatSourceWetHIU(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestHotWaterSourceCombiBoiler:
    @pytest.fixture
    def valid_example(self) -> HotWaterSourceCombiBoiler:
        return HotWaterSourceCombiBoiler(
            type="CombiBoiler",
            ColdWaterSource="cold water source",
            HeatSourceWet="heat source wet",
            daily_HW_usage=120,
            separate_DHW_tests="M_only",
            setpoint_temp=10,
            rejected_energy_1=0.0004,
            storage_loss_factor_1=1.35,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"daily_HW_usage": 0},
                "Input should be greater than 0",
            ),
            (
                {"rejected_energy_1": -0.1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"storage_loss_factor_1": -0.1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"storage_loss_factor_2": -0.1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"setpoint_temp": -9999},
                "Input should be greater than or equal to 0",
            ),
            (
                {"setpoint_temp": 101},
                "Input should be less than or equal to 100",
            ),
            (
                {"storage_loss_factor_2": 2.3},
                "storage_loss_factor_2 invalid input for combis tested to one profile, or not tested.",
            ),
            (
                {"rejected_factor_3": 0.0001},
                "rejected_factor_3 invalid input for combis tested to one profile, or not tested.",
            ),
            (
                {"storage_loss_factor_1": None},
                "Loss factors r1, and F1, are required when a combi boiler is tested to profile M, or not tested.",
            ),
            (
                {
                    "separate_DHW_tests": "M&L",
                    "rejected_factor_3": 0.0002,
                    "storage_loss_factor_1": None,
                    "storage_loss_factor_2": -0.1,
                },
                "Input should be greater than or equal to 0",
            ),
            (
                {
                    "separate_DHW_tests": "M&L",
                    "rejected_factor_3": 0.0002,
                    "storage_loss_factor_2": 1.67,
                },
                "storage_loss_factor_1 invalid input for combis tested to two profiles.",
            ),
            (
                {
                    "separate_DHW_tests": "M&L",
                    "rejected_factor_3": 0.0002,
                    "storage_loss_factor_1": None,
                },
                "Loss factors r1, F2, and F3 are required when a combi boiler is tested to two profiles.",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: HotWaterSourceCombiBoiler,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            HotWaterSourceCombiBoiler(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestHotWaterSourceHUI:
    @pytest.fixture
    def valid_example(self) -> HotWaterSourceHUI:
        return HotWaterSourceHUI(
            type="HIU",
            ColdWaterSource="cold water source",
            HeatSourceWet="heat source wet",
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"setpoint_temp": -9999},
                "Input should be greater than or equal to 0",
            ),
            (
                {"setpoint_temp": 101},
                "Input should be less than or equal to 100",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: HotWaterSourceHUI,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            HotWaterSourceHUI(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestHotWaterSourcePointOfUse:
    @pytest.fixture
    def valid_example(self) -> HotWaterSourcePointOfUse:
        return HotWaterSourcePointOfUse(
            type="PointOfUse",
            ColdWaterSource="cold water source",
            EnergySupply="mains elec",
            efficiency=0.7,
            setpoint_temp=25,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"efficiency": 0},
                "Input should be greater than 0",
            ),
            (
                {"efficiency": 2},
                "Input should be less than or equal to 1",
            ),
            (
                {"setpoint_temp": -9999},
                "Input should be greater than or equal to 0",
            ),
            (
                {"setpoint_temp": 101},
                "Input should be less than or equal to 100",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: HotWaterSourcePointOfUse,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            HotWaterSourcePointOfUse(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestMechanicalVentilationDuctwork:
    @pytest.fixture
    def valid_example(self) -> MechanicalVentilationDuctwork:
        return MechanicalVentilationDuctwork(
            cross_section_shape="circular",
            duct_type=DuctType.EXHAUST,
            insulation_thermal_conductivity=0.8,
            insulation_thickness_mm=20,
            length=100,
            reflective=True,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"duct_perimeter_mm": 0},
                "Input should be greater than 0",
            ),
            (
                {"external_diameter_mm": 0},
                "Input should be greater than 0",
            ),
            (
                {"insulation_thermal_conductivity": 0},
                "Input should be greater than 0",
            ),
            (
                {"internal_diameter_mm": 0},
                "Input should be greater than 0",
            ),
            (
                {"length": 0},
                "Input should be greater than 0",
            ),
            (
                {"insulation_thickness_mm": -1},
                "Input should be greater than or equal to 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: MechanicalVentilationDuctwork,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            MechanicalVentilationDuctwork(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestOtherWaterUse:
    @pytest.fixture
    def valid_example(self) -> OtherWaterUse:
        return OtherWaterUse(
            ColdWaterSource="cold water source",
            flowrate=10,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"flowrate": 0},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: OtherWaterUse,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            OtherWaterUse(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestScheduleRepeaterForBoolean:
    @pytest.fixture
    def valid_example(self) -> ScheduleRepeaterForBoolean:
        return ScheduleRepeaterForBoolean(
            repeat=10,
            value=None,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"repeat": -1},
                "Input should be greater than or equal to 1",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: ScheduleRepeaterForBoolean,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            ScheduleRepeaterForBoolean(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestScheduleRepeaterForDouble:
    @pytest.fixture
    def valid_example(self) -> ScheduleRepeaterForDouble:
        return ScheduleRepeaterForDouble(
            repeat=10,
            value=None,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"repeat": -1},
                "Input should be greater than or equal to 1",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: ScheduleRepeaterForDouble,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            ScheduleRepeaterForDouble(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestShowerMixer:
    @pytest.fixture
    def valid_example(self) -> ShowerMixer:
        return ShowerMixer(
            type=ShowerType.MIXER_SHOWER,
            ColdWaterSource="cold water source",
            flowrate=10,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"flowrate": 0},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: ShowerMixer,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            ShowerMixer(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"WWHRS": None, "WWHRS_configuration": "A"},
                "WWHRS_configuration should not be specified when WWHRS is not provided",
            ),
        ],
    )
    def test_validate_wwhrs_configuration(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: ShowerMixer,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            ShowerMixer(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestShowerInstantElectric:
    @pytest.fixture
    def valid_example(self) -> ShowerInstantElectric:
        return ShowerInstantElectric(
            type=ShowerType.INSTANT_ELECTRIC_SHOWER,
            ColdWaterSource="cold water source",
            EnergySupply="mains elec",
            rated_power=5,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"rated_power": 0},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: ShowerInstantElectric,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            ShowerInstantElectric(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestSimulationTime:
    @pytest.fixture
    def valid_example(self) -> SimulationTime:
        return SimulationTime(
            start=0,
            end=12,
            step=1,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"start": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"end": -1},
                "Input should be greater than 0",
            ),
            (
                {"step": -1},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: SimulationTime,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            SimulationTime(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestSmartApplianceBattery:
    @pytest.fixture
    def valid_example(self) -> SmartApplianceBattery:
        return SmartApplianceBattery(
            battery_state_of_charge={"test": [0.1, 0.2, 0.3, 0.4]},
            energy_into_battery_from_generation={"test": [0.1, 0.2, 0.3, 0.4]},
            energy_into_battery_from_grid={"test": [0.1, 0.2, 0.3, 0.4]},
            energy_out_of_battery={"test": [0.1, 0.2, 0.3, 0.4]},
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"battery_state_of_charge": {}},
                "Dictionary should have at least 1 item after validation, not 0",
            ),
            (
                {"battery_state_of_charge": {"_unmet_demand": []}},
                "List should have at least 1 item after validation, not 0",
            ),
            (
                {"battery_state_of_charge": {"_unmet_demand": [0, 1, 2, -1]}},
                "Input should be less than or equal to 1",
            ),
            (
                {"battery_state_of_charge": {"_unmet_demand": [0, 0.1, 0.2, -1]}},
                "Input should be greater than or equal to 0",
            ),
            (
                {"energy_into_battery_from_generation": {}},
                "Dictionary should have at least 1 item after validation, not 0",
            ),
            (
                {"energy_into_battery_from_generation": {"_unmet_demand": []}},
                "List should have at least 1 item after validation, not 0",
            ),
            (
                {"energy_into_battery_from_grid": {}},
                "Dictionary should have at least 1 item after validation, not 0",
            ),
            (
                {"energy_into_battery_from_grid": {"_unmet_demand": []}},
                "List should have at least 1 item after validation, not 0",
            ),
            (
                {"energy_out_of_battery": {}},
                "Dictionary should have at least 1 item after validation, not 0",
            ),
            (
                {"energy_out_of_battery": {"_unmet_demand": []}},
                "List should have at least 1 item after validation, not 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: SmartApplianceBattery,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            SmartApplianceBattery(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestSmartApplianceControl:
    @pytest.fixture
    def valid_example(self) -> SmartApplianceControl:
        return SmartApplianceControl(
            Appliances=[],
            battery24hr=SmartApplianceBattery(
                battery_state_of_charge={"test": [0.1, 0.2, 0.3, 0.4]},
                energy_into_battery_from_generation={"test": [0.1, 0.2, 0.3, 0.4]},
                energy_into_battery_from_grid={"test": [0.1, 0.2, 0.3, 0.4]},
                energy_out_of_battery={"test": [0.1, 0.2, 0.3, 0.4]},
            ),
            non_appliance_demand_24hr={"test": [1, 2, 3, 4]},
            power_timeseries={"test": [1, 2, 3, 4]},
            time_series_step=1,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"non_appliance_demand_24hr": {"_unmet_demand": []}},
                "List should have at least 1 item after validation, not 0",
            ),
            (
                {"power_timeseries": {"_unmet_demand": []}},
                "List should have at least 1 item after validation, not 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: SmartApplianceControl,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            SmartApplianceControl(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestSpaceHeatSystemHeatSource:
    @pytest.fixture
    def valid_example(self) -> SpaceHeatSystemHeatSource:
        return SpaceHeatSystemHeatSource(
            name="test",
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"temp_flow_limit_upper": 0},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: SpaceHeatSystemHeatSource,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            SpaceHeatSystemHeatSource(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestThermalBridgingLinear:
    @pytest.fixture
    def valid_example(self) -> ThermalBridgingLinear:
        return ThermalBridgingLinear(
            type=ThermalBridgingType.LINEAR,
            length=10,
            linear_thermal_transmittance=0.9,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"length": 0},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: ThermalBridgingLinear,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            ThermalBridgingLinear(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestVent:
    @pytest.fixture
    def valid_example(self) -> Vent:
        return Vent(
            area_cm2=120,
            mid_height_air_flow_path=1.3,
            orientation360=123,
            pitch=45,
            pressure_difference_ref=3.4,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"area_cm2": 0},
                "Input should be greater than 0",
            ),
            (
                {"mid_height_air_flow_path": 0},
                "Input should be greater than 0",
            ),
            (
                {"orientation360": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"orientation360": 361},
                "Input should be less than or equal to 360",
            ),
            (
                {"pitch": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"pitch": 181},
                "Input should be less than or equal to 180",
            ),
            (
                {"pressure_difference_ref": 0},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: Vent,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            Vent(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestVentilationLeaks:
    @pytest.fixture
    def valid_example(self) -> VentilationLeaks:
        return VentilationLeaks(
            env_area=220,
            test_pressure=50,
            test_result=1.2,
            ventilation_zone_height=6,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"env_area": 0},
                "Input should be greater than 0",
            ),
            (
                {"test_pressure": 0},
                "Input should be greater than 0",
            ),
            (
                {"test_result": 0},
                "Input should be greater than 0",
            ),
            (
                {"ventilation_zone_height": 0},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: VentilationLeaks,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            VentilationLeaks(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestWaterHeatingEvent:
    @pytest.fixture
    def valid_example(self) -> WaterHeatingEvent:
        return WaterHeatingEvent(
            start=1,
            temperature=12,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"duration": 0},
                "Input should be greater than 0",
            ),
            (
                {"start": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"volume": 0},
                "Input should be greater than 0",
            ),
            (
                {"temperature": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"temperature": 101},
                "Input should be less than or equal to 100",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: WaterHeatingEvent,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            WaterHeatingEvent(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestWaterPipework:
    @pytest.fixture
    def valid_example(self) -> WaterPipework:
        return WaterPipework(
            external_diameter_mm=27,
            insulation_thickness_mm=34,
            internal_diameter_mm=25,
            length=10,
            pipe_contents="water",
            surface_reflectivity=False,
            insulation_thermal_conductivity=1.3,
            location=WaterPipeworkLocation.INTERNAL,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"external_diameter_mm": 0},
                "Input should be greater than 0",
            ),
            (
                {"insulation_thermal_conductivity": 0},
                "Input should be greater than 0",
            ),
            (
                {"internal_diameter_mm": 0},
                "Input should be greater than 0",
            ),
            (
                {"insulation_thickness_mm": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"length": 0},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: WaterPipework,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            WaterPipework(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestWaterPipeworkSimple:
    @pytest.fixture
    def valid_example(self) -> WaterPipeworkSimple:
        return WaterPipeworkSimple(
            internal_diameter_mm=25,
            length=10,
            location=WaterPipeworkLocation.EXTERNAL,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"internal_diameter_mm": 0},
                "Input should be greater than 0",
            ),
            (
                {"length": 0},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: WaterPipeworkSimple,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            WaterPipeworkSimple(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestWetEmitterRadiator:
    @pytest.fixture
    def valid_example(self) -> WetEmitterRadiator:
        return WetEmitterRadiator(
            wet_emitter_type="radiator",
            c=1.2,
            frac_convective=0.9,
            n=1.2,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"c": 0},
                "Input should be greater than 0",
            ),
            (
                {"n": 0},
                "Input should be greater than 0",
            ),
            (
                {"frac_convective": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"frac_convective": 2},
                "Input should be less than or equal to 1",
            ),
            (
                {"length": 0},
                "Input should be greater than 0",
            ),
            (
                {"c_per_m": 0},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: WetEmitterRadiator,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            WetEmitterRadiator(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"c": None, "c_per_m": None},
                "Must specify either 'c', or 'c_per_m' and 'length'",
            ),
            (
                {"c": None, "length": None},
                "Must specify either 'c', or 'c_per_m' and 'length'",
            ),
            (
                {"thermal_mass_per_m": 5, "length": None},
                "Must specify 'length' when 'thermal_mass_per_m' is provided",
            ),
        ],
    )
    def test_validate_required_fields(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: WetEmitterRadiator,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            WetEmitterRadiator(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestWetEmitterUFH:
    @pytest.fixture
    def valid_example(self) -> WetEmitterUFH:
        return WetEmitterUFH(
            wet_emitter_type="ufh",
            frac_convective=0.9,
            emitter_floor_area=40,
            equivalent_specific_thermal_mass=80,
            system_performance_factor=5,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"equivalent_specific_thermal_mass": 0},
                "Input should be greater than 0",
            ),
            (
                {"system_performance_factor": 0},
                "Input should be greater than 0",
            ),
            (
                {"emitter_floor_area": 0},
                "Input should be greater than 0",
            ),
            (
                {"frac_convective": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"frac_convective": 2},
                "Input should be less than or equal to 1",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: WetEmitterUFH,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            WetEmitterUFH(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestWetEmitterFanCoil:
    @pytest.fixture
    def valid_example(self) -> WetEmitterFanCoil:
        return WetEmitterFanCoil(
            wet_emitter_type="fancoil",
            fancoil_test_data={
                "fan_speed_data": [
                    {"temperature_diff": 80.0, "power_output": [2.7, 3.6, 5, 5.3, 6.2, 7.4]},
                    {"temperature_diff": 70.0, "power_output": [2.3, 3.1, 4.2, 4.5, 5.3, 6.3]},
                    {"temperature_diff": 60.0, "power_output": [1.9, 2.6, 3.5, 3.8, 4.4, 5.3]},
                    {"temperature_diff": 50.0, "power_output": [1.5, 2, 2.8, 3, 3.5, 4.2]},
                ],
                "fan_power_W": [15, 19, 25, 33, 43, 56],
            },
            frac_convective=0.8,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"n_units": 0},
                "Input should be greater than 0",
            ),
            (
                {"frac_convective": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"frac_convective": 2},
                "Input should be less than or equal to 1",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: WetEmitterFanCoil,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            WetEmitterFanCoil(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestWindowShadingObstacle:
    @pytest.fixture
    def valid_example(self) -> WindowShadingObstacle:
        return WindowShadingObstacle(
            type="obstacle",
            height=10,
            distance=10,
            transparency=0.6,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"height": 0},
                "Input should be greater than 0",
            ),
            (
                {"distance": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"transparency": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"transparency": 2},
                "Input should be less than or equal to 1",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: WindowShadingObstacle,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            WindowShadingObstacle(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestWindowShadingObject:
    @pytest.fixture
    def valid_example(self) -> WindowShadingObject:
        return WindowShadingObject(
            type="sidefinleft",
            depth=10,
            distance=1.5,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"depth": 0},
                "Input should be greater than 0",
            ),
            (
                {"distance": -1},
                "Input should be greater than or equal to 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: WindowShadingObject,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            WindowShadingObject(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestBath:
    @pytest.fixture
    def valid_example(self) -> Bath:
        return Bath(
            ColdWaterSource="cold water source",
            flowrate=2,
            size=10,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"flowrate": 0},
                "Input should be greater than 0",
            ),
            (
                {"size": 0},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: Bath,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            Bath(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestEnergySupply:
    @pytest.fixture
    def valid_example(self) -> EnergySupply:
        return EnergySupply(
            fuel=FuelType.ENERGY_FROM_ENVIRONMENT,
            is_export_capable=True,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"threshold_charges": [0, 1, 1]},
                "List should have at least 12 items after validation, not 3",
            ),
            (
                {"threshold_charges": [0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]},
                "List should have at most 12 items after validation, not 13",
            ),
            (
                {"threshold_charges": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 2]},
                "Input should be less than or equal to 1",
            ),
            (
                {"threshold_charges": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, -1]},
                "Input should be greater than or equal to 0",
            ),
            (
                {"threshold_prices": [0, 1, 1]},
                "List should have at least 12 items after validation, not 3",
            ),
            (
                {"threshold_prices": [0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]},
                "List should have at most 12 items after validation, not 13",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: EnergySupply,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            EnergySupply(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestImmersionHeater:
    @pytest.fixture
    def valid_example(self) -> ImmersionHeater:
        return ImmersionHeater(
            type="ImmersionHeater",
            Controlmax="control max",
            Controlmin="control min",
            EnergySupply="mains elec",
            heater_position=0.7,
            power=12,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"power": 0},
                "Input should be greater than 0",
            ),
            (
                {"heater_position": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"heater_position": 2},
                "Input should be less than or equal to 1",
            ),
            (
                {"thermostat_position": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"thermostat_position": 2},
                "Input should be less than or equal to 1",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: ImmersionHeater,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            ImmersionHeater(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestSolarThermalSystem:
    @pytest.fixture
    def valid_example(self) -> SolarThermalSystem:
        return SolarThermalSystem(
            type="SolarThermalSystem",
            Controlmax="control max",
            EnergySupply="mains elec",
            area_module=10,
            collector_mass_flow_rate=1,
            first_order_hlc=3.5,
            heater_position=0.8,
            incidence_angle_modifier=0.9,
            modules=1,
            orientation360=234,
            peak_collector_efficiency=0.8,
            power_pump=100,
            power_pump_control=10,
            second_order_hlc=0,
            solar_loop_piping_hlc=0.5,
            sol_loc="OUT",
            tilt=56,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"area_module": 0},
                "Input should be greater than 0",
            ),
            (
                {"collector_mass_flow_rate": 0},
                "Input should be greater than 0",
            ),
            (
                {"first_order_hlc": 0},
                "Input should be greater than 0",
            ),
            (
                {"incidence_angle_modifier": 0},
                "Input should be greater than 0",
            ),
            (
                {"incidence_angle_modifier": 2},
                "Input should be less than or equal to 1",
            ),
            (
                {"peak_collector_efficiency": 0},
                "Input should be greater than 0",
            ),
            (
                {"peak_collector_efficiency": 2},
                "Input should be less than or equal to 1",
            ),
            (
                {"power_pump": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"power_pump_control": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"second_order_hlc": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"solar_loop_piping_hlc": 0},
                "Input should be greater than 0",
            ),
            (
                {"modules": 0},
                "Input should be greater than or equal to 1",
            ),
            (
                {"orientation360": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"orientation360": 361},
                "Input should be less than or equal to 360",
            ),
            (
                {"heater_position": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"heater_position": 2},
                "Input should be less than or equal to 1",
            ),
            (
                {"thermostat_position": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"thermostat_position": 2},
                "Input should be less than or equal to 1",
            ),
            (
                {"tilt": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"tilt": 91},
                "Input should be less than or equal to 90",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: SolarThermalSystem,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            SolarThermalSystem(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestHeatSourceWetServiceWaterRegular:
    @pytest.fixture
    def valid_example(self) -> HeatSourceWetServiceWaterRegular:
        return HeatSourceWetServiceWaterRegular(
            type="HeatSourceWet",
            Controlmax="control max",
            Controlmin="control min",
            heater_position=1,
            name="test",
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"heater_position": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"heater_position": 2},
                "Input should be less than or equal to 1",
            ),
            (
                {"thermostat_position": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"thermostat_position": 2},
                "Input should be less than or equal to 1",
            ),
            (
                {"temp_flow_limit_upper": 0},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: HeatSourceWetServiceWaterRegular,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            HeatSourceWetServiceWaterRegular(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestHeatPumpHotWaterOnly:
    @pytest.fixture
    def valid_example(self) -> HeatPumpHotWaterOnly:
        return HeatPumpHotWaterOnly(
            type="HeatPump_HWOnly",
            Controlmax="control max",
            Controlmin="control min",
            EnergySupply="mains elec",
            heater_position=1,
            daily_losses_declared=2.3,
            heat_exchanger_surface_area_declared=1.3,
            in_use_factor_mismatch=0.4,
            power_max=10,
            tank_volume_declared=10,
            test_data={
                "M": {
                    "cop_dhw": 2.5,
                    "hw_tapping_prof_daily_total": 5.845,
                    "energy_input_measured": 2.338,
                    "power_standby": 0.02,
                    "hw_vessel_loss_daily": 2.0,
                }
            },
            vol_hw_daily_average=10,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"heater_position": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"heater_position": 2},
                "Input should be less than or equal to 1",
            ),
            (
                {"thermostat_position": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"thermostat_position": 2},
                "Input should be less than or equal to 1",
            ),
            (
                {"daily_losses_declared": 0},
                "Input should be greater than 0",
            ),
            (
                {"heat_exchanger_surface_area_declared": 0},
                "Input should be greater than 0",
            ),
            (
                {"in_use_factor_mismatch": 0},
                "Input should be greater than 0",
            ),
            (
                {"power_max": 0},
                "Input should be greater than 0",
            ),
            (
                {"vol_hw_daily_average": 0},
                "Input should be greater than 0",
            ),
            (
                {"tank_volume_declared": 0},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: HeatPumpHotWaterOnly,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            HeatPumpHotWaterOnly(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestHotWaterSourceSmartHotWaterTank:
    @pytest.fixture
    def valid_example(self) -> HotWaterSourceSmartHotWaterTank:
        return HotWaterSourceSmartHotWaterTank(
            type="SmartHotWaterTank",
            ColdWaterSource="cold water source",
            EnergySupply_pump="mains elec",
            HeatSource={},
            daily_losses=2.3,
            init_temp=15,
            max_flow_rate_pump_l_per_min=10,
            power_pump_kW=5,
            temp_setpnt_max="test",
            temp_usable=40,
            volume=10,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"daily_losses": 0},
                "Input should be greater than 0",
            ),
            (
                {"max_flow_rate_pump_l_per_min": 0},
                "Input should be greater than 0",
            ),
            (
                {"power_pump_kW": 0},
                "Input should be greater than 0",
            ),
            (
                {"volume": 0},
                "Input should be greater than 0",
            ),
            (
                {"init_temp": -2},
                "Input should be greater than or equal to 0",
            ),
            (
                {"temp_usable": -2},
                "Input should be greater than or equal to 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: HotWaterSourceSmartHotWaterTank,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            HotWaterSourceSmartHotWaterTank(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestMechanicalVentilation:
    @pytest.fixture
    def valid_example(self) -> MechanicalVentilation:
        return MechanicalVentilation(
            EnergySupply="mains elec",
            SFP=1.2,
            design_outdoor_air_flow_rate=10,
            sup_air_flw_ctrl="ODA",
            sup_air_temp_ctrl="NO_CTRL",
            vent_type=MechVentType.MVHR,
            position_intake={
                "orientation360": 180,
                "pitch": 90,
                "mid_height_air_flow_path": 3.0,
            },
            position_exhaust={
                "orientation360": 0,
                "pitch": 90,
                "mid_height_air_flow_path": 2.0,
            },
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"SFP": -1},
                "Input should be greater than 0",
            ),
            (
                {"design_outdoor_air_flow_rate": -1},
                "Input should be greater than 0",
            ),
            (
                {"mvhr_eff": -1},
                "Input should be greater than or equal to 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: MechanicalVentilation,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            MechanicalVentilation(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"vent_type": MechVentType.MVHR, "position_intake": None},
                "MVHR ventilation systems require both 'position_intake' and 'position_exhaust' fields",
            ),
            (
                {"vent_type": MechVentType.MVHR, "position_exhaust": None},
                "MVHR ventilation systems require both 'position_intake' and 'position_exhaust' fields",
            ),
            (
                {"orientation360": 234},
                r"MVHR ventilation systems should use 'position_intake' and 'position_exhaust' fields, not the legacy single position fields \(orientation360, pitch, mid_height_air_flow_path\)",
            ),
            (
                {"pitch": 12},
                r"MVHR ventilation systems should use 'position_intake' and 'position_exhaust' fields, not the legacy single position fields \(orientation360, pitch, mid_height_air_flow_path\)",
            ),
            (
                {"mid_height_air_flow_path": 4},
                r"MVHR ventilation systems should use 'position_intake' and 'position_exhaust' fields, not the legacy single position fields \(orientation360, pitch, mid_height_air_flow_path\)",
            ),
            (
                {
                    "vent_type": MechVentType.POSITIVE_INPUT_VENTILATION,
                    "position_exhaust": {
                        "orientation360": 0,
                        "pitch": 90,
                        "mid_height_air_flow_path": 2.0,
                    },
                    "orientation360": 345,
                },
                f"{MechVentType.POSITIVE_INPUT_VENTILATION} systems should use either 'position_exhaust' OR the legacy fields, not both",
            ),
            (
                {
                    "vent_type": MechVentType.POSITIVE_INPUT_VENTILATION,
                    "position_exhaust": {
                        "orientation360": 0,
                        "pitch": 90,
                        "mid_height_air_flow_path": 2.0,
                    },
                    "pitch": 34,
                },
                f"{MechVentType.POSITIVE_INPUT_VENTILATION} systems should use either 'position_exhaust' OR the legacy fields, not both",
            ),
            (
                {
                    "vent_type": MechVentType.POSITIVE_INPUT_VENTILATION,
                    "position_exhaust": {
                        "orientation360": 0,
                        "pitch": 90,
                        "mid_height_air_flow_path": 2.0,
                    },
                    "mid_height_air_flow_path": 3,
                },
                f"{MechVentType.POSITIVE_INPUT_VENTILATION} systems should use either 'position_exhaust' OR the legacy fields, not both",
            ),
            (
                {
                    "vent_type": MechVentType.POSITIVE_INPUT_VENTILATION,
                    "position_exhaust": None,
                    "orientation360": None,
                    "pitch": None,
                    "mid_height_air_flow_path": 3,
                },
                rf"{MechVentType.POSITIVE_INPUT_VENTILATION} systems require either 'position_exhaust' field OR all legacy position fields \(orientation360, pitch, mid_height_air_flow_path\)",
            ),
            (
                {
                    "vent_type": MechVentType.POSITIVE_INPUT_VENTILATION,
                    "position_exhaust": None,
                    "orientation360": 234,
                    "pitch": None,
                    "mid_height_air_flow_path": None,
                },
                rf"{MechVentType.POSITIVE_INPUT_VENTILATION} systems require either 'position_exhaust' field OR all legacy position fields \(orientation360, pitch, mid_height_air_flow_path\)",
            ),
            (
                {
                    "vent_type": MechVentType.POSITIVE_INPUT_VENTILATION,
                    "position_exhaust": None,
                    "orientation360": None,
                    "pitch": 23,
                    "mid_height_air_flow_path": None,
                },
                rf"{MechVentType.POSITIVE_INPUT_VENTILATION} systems require either 'position_exhaust' field OR all legacy position fields \(orientation360, pitch, mid_height_air_flow_path\)",
            ),
            (
                {
                    "vent_type": MechVentType.POSITIVE_INPUT_VENTILATION,
                    "position_exhaust": {
                        "orientation360": 0,
                        "pitch": 90,
                        "mid_height_air_flow_path": 2.0,
                    },
                    "position_intake": {
                        "orientation360": 180,
                        "pitch": 90,
                        "mid_height_air_flow_path": 3.0,
                    },
                },
                f"{MechVentType.POSITIVE_INPUT_VENTILATION} systems should not have 'position_intake' field",
            ),
        ],
    )
    def test_validate_position_fields(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: MechanicalVentilation,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            MechanicalVentilation(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestPhotovoltaicSystem:
    @pytest.fixture
    def valid_example(self) -> PhotovoltaicSystem:
        return PhotovoltaicSystem(
            type="PhotovoltaicSystem",
            EnergySupply="mains elec",
            base_height=10,
            height=10,
            inverter_is_inside=True,
            inverter_type=InverterType.STRING_INVERTER,
            inverter_peak_power_ac=1.4,
            inverter_peak_power_dc=3.5,
            orientation360=30,
            peak_power=10,
            pitch=90,
            shading=[],
            ventilation_strategy="unventilated",
            width=10,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"base_height": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"height": 0},
                "Input should be greater than 0",
            ),
            (
                {"inverter_peak_power_ac": 0},
                "Input should be greater than 0",
            ),
            (
                {"inverter_peak_power_dc": 0},
                "Input should be greater than 0",
            ),
            (
                {"peak_power": 0},
                "Input should be greater than 0",
            ),
            (
                {"width": 0},
                "Input should be greater than 0",
            ),
            (
                {"orientation360": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"orientation360": 361},
                "Input should be less than or equal to 360",
            ),
            (
                {"pitch": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"pitch": 91},
                "Input should be less than or equal to 90",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: PhotovoltaicSystem,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            PhotovoltaicSystem(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestPhotovoltaicSystemWithPanels:
    @pytest.fixture
    def valid_example(self) -> PhotovoltaicSystemWithPanels:
        return PhotovoltaicSystemWithPanels(
            type="PhotovoltaicSystem",
            EnergySupply="mains elec",
            inverter_is_inside=True,
            inverter_type=InverterType.STRING_INVERTER,
            inverter_peak_power_ac=1.4,
            inverter_peak_power_dc=3.5,
            panels=[
                {
                    "peak_power": 2.5,
                    "ventilation_strategy": "moderately_ventilated",
                    "pitch": 30,
                    "orientation360": 180,
                    "base_height": 10,
                    "height": 1,
                    "width": 1,
                    "shading": [],
                }
            ],
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"inverter_peak_power_ac": 0},
                "Input should be greater than 0",
            ),
            (
                {"inverter_peak_power_dc": 0},
                "Input should be greater than 0",
            ),
            (
                {"panels": []},
                "List should have at least 1 item after validation, not 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: PhotovoltaicSystemWithPanels,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            PhotovoltaicSystemWithPanels(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestPhotovoltaicPanel:
    @pytest.fixture
    def valid_example(self) -> PhotovoltaicPanel:
        return PhotovoltaicPanel(
            peak_power=1.3,
            ventilation_strategy="unventilated",
            pitch=34,
            orientation360=245,
            base_height=1.2,
            height=2.3,
            width=4.3,
            shading=[],
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"peak_power": 0},
                "Input should be greater than 0",
            ),
            (
                {"base_height": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"width": 0},
                "Input should be greater than 0",
            ),
            (
                {"orientation360": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"orientation360": 361},
                "Input should be less than or equal to 360",
            ),
            (
                {"pitch": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"pitch": 91},
                "Input should be less than or equal to 90",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: PhotovoltaicPanel,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            PhotovoltaicPanel(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestShadingObject:
    @pytest.fixture
    def valid_example(self) -> ShadingObject:
        return ShadingObject(
            distance=10,
            height=10,
            type=ShadingObjectType.OBSTACLE,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"distance": 0},
                "Input should be greater than 0",
            ),
            (
                {"height": 0},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: ShadingObject,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            ShadingObject(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestShadingSegment:
    @pytest.fixture
    def valid_example(self) -> ShadingSegment:
        return ShadingSegment(
            end360=360,
            start360=0,
            shading=None,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"end360": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"end360": 361},
                "Input should be less than or equal to 360",
            ),
            (
                {"start360": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"start360": 361},
                "Input should be less than or equal to 360",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: ShadingSegment,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            ShadingSegment(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestSpaceCoolSystemAirConditioning:
    @pytest.fixture
    def valid_example(self) -> SpaceCoolSystemAirConditioning:
        return SpaceCoolSystemAirConditioning(
            type="AirConditioning",
            Control="control",
            EnergySupply="mains elec",
            cooling_capacity=1.2,
            efficiency=4.3,
            frac_convective=0.2,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"frac_convective": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"frac_convective": 2},
                "Input should be less than or equal to 1",
            ),
            (
                {"efficiency": 0},
                "Input should be greater than 0",
            ),
            (
                {"cooling_capacity": 0},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: SpaceCoolSystemAirConditioning,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            SpaceCoolSystemAirConditioning(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestSpaceHeatSystemInstantElectricHeater:
    @pytest.fixture
    def valid_example(self) -> SpaceHeatSystemInstantElectricHeater:
        return SpaceHeatSystemInstantElectricHeater(
            type="InstantElecHeater",
            Control="control",
            EnergySupply="mains elec",
            frac_convective=0.3,
            rated_power=6.0,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"frac_convective": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"frac_convective": 2},
                "Input should be less than or equal to 1",
            ),
            (
                {"rated_power": 0},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: SpaceHeatSystemInstantElectricHeater,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            SpaceHeatSystemInstantElectricHeater(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestSpaceHeatSystemWetDistribution:
    @pytest.fixture
    def valid_example(self) -> SpaceHeatSystemWetDistribution:
        return SpaceHeatSystemWetDistribution(
            type="WetDistribution",
            HeatSource={"name": "immersion_system_heating"},
            bypass_fraction_recirculated=0.0,
            design_flow_rate=None,
            design_flow_temp=55.0,
            emitters=[
                {"wet_emitter_type": "radiator", "c": 0.08, "n": 1.2, "frac_convective": 0.4}
            ],
            ecodesign_controller={"ecodesign_control_class": EcoDesignControllerClass.CLASS_VI},
            max_flow_rate=18,
            min_flow_rate=3,
            temp_diff_emit_dsgn=10.0,
            thermal_mass=0.14,
            variable_flow=True,
            Control="control_test",
            Zone="zone_test",
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"variable_flow": True, "min_flow_rate": None, "max_flow_rate": None},
                "Both min_flow_rate and max_flow_rate are required if variable_flow is True.",
            ),
            (
                {"variable_flow": True, "min_flow_rate": 4, "max_flow_rate": None},
                "Both min_flow_rate and max_flow_rate are required if variable_flow is True.",
            ),
            (
                {"variable_flow": True, "min_flow_rate": None, "max_flow_rate": 4},
                "Both min_flow_rate and max_flow_rate are required if variable_flow is True.",
            ),
        ],
    )
    def test_validate_flow_rate(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: SpaceHeatSystemWetDistribution,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            SpaceHeatSystemWetDistribution(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"variable_flow": False, "design_flow_rate": None},
                "design_flow_rate is required if variable_flow is False.",
            ),
        ],
    )
    def test_validate_design_flow_rate(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: SpaceHeatSystemWetDistribution,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            SpaceHeatSystemWetDistribution(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"bypass_fraction_recirculated": 1},
                "Input should be less than 1",
            ),
            (
                {"bypass_fraction_recirculated": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"design_flow_rate": 0},
                "Input should be greater than 0",
            ),
            (
                {"max_flow_rate": 0},
                "Input should be greater than 0",
            ),
            (
                {"min_flow_rate": 0},
                "Input should be greater than 0",
            ),
            (
                {"temp_diff_emit_dsgn": 0},
                "Input should be greater than 0",
            ),
            (
                {"thermal_mass": 0},
                "Input should be greater than 0",
            ),
            (
                {"design_flow_temp": 0},
                "Input should be greater than 0",
            ),
            (
                {"emitters": []},
                "List should have at least 1 item after validation, not 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: SpaceHeatSystemWetDistribution,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            SpaceHeatSystemWetDistribution(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestSpaceHeatSystemWarmAir:
    @pytest.fixture
    def valid_example(self) -> SpaceHeatSystemWarmAir:
        return SpaceHeatSystemWarmAir(
            type="WarmAir",
            HeatSource={"name": "immersion_system_heating"},
            Control="control",
            frac_convective=0.8,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"frac_convective": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"frac_convective": 2},
                "Input should be less than or equal to 1",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: SpaceHeatSystemWarmAir,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            SpaceHeatSystemWarmAir(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestControlChargeTarget:
    @pytest.fixture
    def valid_example(self) -> ControlChargeTarget:
        return ControlChargeTarget(
            type="ChargeControl",
            charge_level=None,
            external_sensor=None,
            logic_type=None,
            schedule={"main": []},
            start_day=0,
            temp_charge_cut=None,
            temp_charge_cut_delta=None,
            time_series_step=0.1,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            ({"logic_type": "automatic"}, r"logic_type \(automatic\) requires temp_charge_cut"),
            ({"logic_type": "celect"}, r"logic_type \(celect\) requires temp_charge_cut"),
            ({"logic_type": "hhrsh"}, r"logic_type \(hhrsh\) requires temp_charge_cut"),
        ],
    )
    def test_validate_logic_type(
        self, inputs: dict[str, Any], expected_message: str, valid_example: ControlChargeTarget
    ):
        with pytest.raises(ValidationError, match=expected_message):
            ControlChargeTarget(
                **(valid_example.model_dump() | inputs),
            )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"temp_charge_cut": -274},
                "Input should be greater than or equal to -273.15",
            ),
            (
                {"charge_calc_time": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"charge_calc_time": 24},
                "Input should be less than 24",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: ControlChargeTarget,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            ControlChargeTarget(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestControlSetpointTimerValidation:
    """Test validation for ControlSetpointTimer setpoint bounds."""

    @pytest.fixture
    def base_data(self):
        """Set up common test data."""
        return {
            "type": "SetpointTimeControl",
            "start_day": 0,
            "time_series_step": 1.0,
            "schedule": {"main": [{"value": 21.0, "repeat": 24}]},
        }

    def test_valid_setpoint_bounds(self, base_data):
        """Test that valid setpoint bounds pass validation."""
        data = deepcopy(base_data)
        data.update({"setpoint_min": 18.0, "setpoint_max": 25.0})

        control = ControlSetpointTimer.model_validate(data)
        assert control.setpoint_min == 18.0
        assert control.setpoint_max == 25.0

    def test_invalid_setpoint_bounds(self, base_data):
        """Test that invalid setpoint bounds fail validation."""
        data = deepcopy(base_data)
        data.update(
            {
                "setpoint_min": 18.0,
                "setpoint_max": 18.0,  # Equal to min - should fail
            }
        )

        with pytest.raises(ValueError, match="setpoint_max must be greater than setpoint_min"):
            ControlSetpointTimer.model_validate(data)

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"advanced_start": -1},
                "Input should be greater than or equal to 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self, inputs: dict[str, Any], expected_message: str, base_data
    ):
        data = base_data.copy()
        data.update(inputs)
        with pytest.raises(ValidationError, match=expected_message):
            ControlSetpointTimer.model_validate(data)


class TestWasteWaterHeatRecoverySystem:
    @pytest.fixture
    def valid_example(self) -> WasteWaterHeatRecoverySystem:
        return WasteWaterHeatRecoverySystem(
            type="WWHRS_Instantaneous",
            ColdWaterSource="header tank",
            system_a_efficiencies=[],
            flow_rates=[],
            system_a_utilisation_factor=1,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {
                    "system_a_efficiencies": [1, 2, 3],
                    "system_b_efficiencies": [1, 2, 3, 4],
                    "system_c_efficiencies": [1, 2, 3, 4],
                    "flow_rates": [1, 2, 3, 4],
                },
                "flow_rates and system_a_efficiencies must have the same length",
            ),
            (
                {
                    "system_a_efficiencies": [1, 2, 3, 4],
                    "system_b_efficiencies": [1, 2, 3],
                    "system_c_efficiencies": [1, 2, 3, 4],
                    "flow_rates": [1, 2, 3, 4],
                },
                "flow_rates and system_b_efficiencies must have the same length",
            ),
            (
                {
                    "system_a_efficiencies": [1, 2, 3, 4],
                    "system_b_efficiencies": [1, 2, 3, 4],
                    "system_c_efficiencies": [1, 2, 3],
                    "flow_rates": [1, 2, 3, 4],
                },
                "flow_rates and system_c_efficiencies must have the same length",
            ),
        ],
    )
    def test_validate_flow_rates_and_efficiencies_length(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: WasteWaterHeatRecoverySystem,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            WasteWaterHeatRecoverySystem(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"system_a_efficiencies": [0]},
                "Input should be greater than 0",
            ),
            (
                {"system_a_efficiencies": [101]},
                "Input should be less than or equal to 100",
            ),
            (
                {"flow_rates": [0]},
                "Input should be greater than 0",
            ),
            (
                {"system_a_utilisation_factor": 0},
                "Input should be greater than 0",
            ),
            (
                {"system_a_utilisation_factor": 2},
                "Input should be less than or equal to 1",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: WasteWaterHeatRecoverySystem,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            WasteWaterHeatRecoverySystem(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )

    def test_wwhrs_system_b_and_c_fields_optional(self):
        """Test that system B and C fields are truly optional."""
        cold_water_source = "test_cold_water_source"

        # Test with only required fields (no system B or C)
        wwhrs = WasteWaterHeatRecoverySystem(
            type="WWHRS_Instantaneous",
            flow_rates=[5, 7, 9, 11, 13],
            system_a_efficiencies=[50, 55, 60, 65, 70],
            ColdWaterSource=cold_water_source,
            system_a_utilisation_factor=0.9,
        )

        # Verify that optional fields are None
        assert wwhrs.system_b_efficiencies is None
        assert wwhrs.system_c_efficiencies is None
        assert wwhrs.system_b_utilisation_factor is None
        assert wwhrs.system_c_utilisation_factor is None

    def test_wwhrs_with_all_systems(self):
        """Test WWHRS with all three systems configured."""
        cold_water_source = "test_cold_water_source"

        wwhrs = WasteWaterHeatRecoverySystem(
            type="WWHRS_Instantaneous",
            flow_rates=[5, 7, 9, 11, 13],
            system_a_efficiencies=[50, 55, 60, 65, 70],
            ColdWaterSource=cold_water_source,
            system_a_utilisation_factor=0.9,
            system_b_efficiencies=[40, 44, 48, 52, 56],
            system_b_utilisation_factor=0.85,
            system_c_efficiencies=[45, 49, 53, 57, 61],
            system_c_utilisation_factor=0.88,
            system_b_efficiency_factor=0.81,
            system_c_efficiency_factor=0.88,
        )

        # Test that all values are stored correctly
        assert wwhrs.system_b_efficiencies == [40, 44, 48, 52, 56]
        assert wwhrs.system_c_efficiencies == [45, 49, 53, 57, 61]
        assert wwhrs.system_b_utilisation_factor == 0.85
        assert wwhrs.system_c_utilisation_factor == 0.88

    def test_no_efficiencies_raises_error(self):
        """Test that at least one efficiency dataset must be provided."""
        with pytest.raises(
            ValidationError,
            match="At least one efficiency dataset must be provided",
        ):
            WasteWaterHeatRecoverySystem(
                type="WWHRS_Instantaneous",
                ColdWaterSource="header tank",
                flow_rates=[5, 7, 9, 11, 13],
            )


class TestBuildingElementCommonBase:
    """Test the base building element class with minimal properties."""

    @pytest.fixture
    def valid_example(self) -> BuildingElementCommonBase:
        return BuildingElementCommonBase(
            pitch=45.0,
            u_value=0.3,  # Optional field
        )

    @pytest.fixture
    def minimal_example(self) -> BuildingElementCommonBase:
        return BuildingElementCommonBase(
            pitch=90.0,
            # u_value is optional, can be None
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"pitch": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"pitch": 181},
                "Input should be less than or equal to 180",
            ),
            (
                {"u_value": 0},
                "Input should be greater than 0",
            ),
            (
                {"u_value": -0.5},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: BuildingElementCommonBase,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            BuildingElementCommonBase(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )

    def test_u_value_optional(self, minimal_example: BuildingElementCommonBase):
        """Test that u_value is optional in the base class."""
        assert minimal_example.u_value is None
        assert minimal_example.pitch == 90.0


class TestBuildingElementCommonBaseNotGround:
    """Test building elements that require thermal properties."""

    @pytest.fixture
    def valid_example_with_u_value(self) -> BuildingElementCommonBaseNotGround:
        return BuildingElementCommonBaseNotGround(
            pitch=60.0,
            u_value=0.25,
            # thermal_resistance_construction not provided
        )

    @pytest.fixture
    def valid_example_with_thermal_resistance(self) -> BuildingElementCommonBaseNotGround:
        return BuildingElementCommonBaseNotGround(
            pitch=60.0,
            thermal_resistance_construction=4.0,  # 1/0.25
            # u_value not provided
        )

    @pytest.fixture
    def valid_example_with_both(self) -> BuildingElementCommonBaseNotGround:
        return BuildingElementCommonBaseNotGround(
            pitch=60.0,
            u_value=0.25,
            thermal_resistance_construction=4.0,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"u_value": None, "thermal_resistance_construction": None},
                "Must specify either 'thermal_resistance_construction' or 'u_value'",
            ),
        ],
    )
    def test_validate_thermal_properties(
        self,
        inputs: dict[str, Any],
        expected_message: str,
    ):
        """Test that at least one thermal property must be provided."""
        with pytest.raises(ValidationError, match=expected_message):
            BuildingElementCommonBaseNotGround(
                pitch=60.0,
                **inputs,
            )

    def test_valid_with_u_value_only(self, valid_example_with_u_value):
        """Test valid instance with only u_value provided."""
        assert valid_example_with_u_value.u_value == 0.25
        assert valid_example_with_u_value.thermal_resistance_construction is None

    def test_valid_with_thermal_resistance_only(self, valid_example_with_thermal_resistance):
        """Test valid instance with only thermal_resistance_construction provided."""
        assert valid_example_with_thermal_resistance.u_value is None
        assert valid_example_with_thermal_resistance.thermal_resistance_construction == 4.0

    def test_valid_with_both_properties(self, valid_example_with_both):
        """Test valid instance with both thermal properties provided."""
        assert valid_example_with_both.u_value == 0.25
        assert valid_example_with_both.thermal_resistance_construction == 4.0

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"thermal_resistance_construction": 0},
                "Input should be greater than 0",
            ),
            (
                {"thermal_resistance_construction": -1.0},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_thermal_resistance_range(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example_with_thermal_resistance: BuildingElementCommonBaseNotGround,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            BuildingElementCommonBaseNotGround(
                **(valid_example_with_thermal_resistance.model_dump(by_alias=True) | inputs),
            )


class TestBuildingElementNotTransparent:
    """Test mixin for non-transparent building elements."""

    @pytest.fixture
    def valid_example(self) -> BuildingElementNotTransparent:
        return BuildingElementNotTransparent(
            area=25.0,
            areal_heat_capacity=15000.0,
            mass_distribution_class=MassDistributionClass.I,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"area": 0},
                "Input should be greater than 0",
            ),
            (
                {"area": -5.0},
                "Input should be greater than 0",
            ),
            (
                {"areal_heat_capacity": 0},
                "Input should be greater than 0",
            ),
            (
                {"areal_heat_capacity": -1000},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: BuildingElementNotTransparent,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            BuildingElementNotTransparent(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )

    def test_all_fields_required(self):
        """Test that all fields are required for non-transparent elements."""
        # Missing area
        with pytest.raises(ValidationError, match="Field required"):
            BuildingElementNotTransparent(
                areal_heat_capacity=15000.0,
                mass_distribution_class=MassDistributionClass.I,
            )

        # Missing areal_heat_capacity
        with pytest.raises(ValidationError, match="Field required"):
            BuildingElementNotTransparent(
                area=25.0,
                mass_distribution_class=MassDistributionClass.I,
            )

        # Missing mass_distribution_class
        with pytest.raises(ValidationError, match="Field required"):
            BuildingElementNotTransparent(
                area=25.0,
                areal_heat_capacity=15000.0,
            )

    def test_mass_distribution_class_enum(self, valid_example):
        """Test that mass_distribution_class uses the enum."""
        assert valid_example.mass_distribution_class == MassDistributionClass.I

        # Test other valid enum values
        element_class_m = BuildingElementNotTransparent(
            area=25.0,
            areal_heat_capacity=15000.0,
            mass_distribution_class=MassDistributionClass.M,
        )
        assert element_class_m.mass_distribution_class == MassDistributionClass.M

        element_class_e = BuildingElementNotTransparent(
            area=25.0,
            areal_heat_capacity=15000.0,
            mass_distribution_class=MassDistributionClass.E,
        )
        assert element_class_e.mass_distribution_class == MassDistributionClass.E


class TestBuildingElementExposedToSolarRadiation:
    """Test mixin for elements exposed to solar radiation."""

    @pytest.fixture
    def valid_example(self) -> BuildingElementExposedToSolarRadiation:
        return BuildingElementExposedToSolarRadiation(
            orientation360=180.0,
            base_height=0.5,
            height=3.0,
            width=8.0,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"orientation360": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"orientation360": 361},
                "Input should be less than or equal to 360",
            ),
            (
                {"base_height": -0.5},
                "Input should be greater than or equal to 0",
            ),
            (
                {"height": 0},
                "Input should be greater than 0",
            ),
            (
                {"height": -1.0},
                "Input should be greater than 0",
            ),
            (
                {"width": 0},
                "Input should be greater than 0",
            ),
            (
                {"width": -2.0},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: BuildingElementExposedToSolarRadiation,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            BuildingElementExposedToSolarRadiation(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )

    def test_all_fields_required(self):
        """Test that all solar exposure fields are required."""
        # Missing orientation360
        with pytest.raises(ValidationError, match="Field required"):
            BuildingElementExposedToSolarRadiation(
                base_height=0.5,
                height=3.0,
                width=8.0,
            )

        # Missing base_height
        with pytest.raises(ValidationError, match="Field required"):
            BuildingElementExposedToSolarRadiation(
                orientation360=180.0,
                height=3.0,
                width=8.0,
            )

        # Missing height
        with pytest.raises(ValidationError, match="Field required"):
            BuildingElementExposedToSolarRadiation(
                orientation360=180.0,
                base_height=0.5,
                width=8.0,
            )

        # Missing width
        with pytest.raises(ValidationError, match="Field required"):
            BuildingElementExposedToSolarRadiation(
                orientation360=180.0,
                base_height=0.5,
                height=3.0,
            )

    def test_base_height_can_be_zero(self):
        """Test that base_height can be zero (ground level)."""
        ground_level = BuildingElementExposedToSolarRadiation(
            orientation360=90.0,
            base_height=0.0,  # Element starts at ground
            height=2.5,
            width=4.0,
        )
        assert ground_level.base_height == 0.0  # noqa: float-compare

    def test_orientation_boundary_values(self):
        """Test orientation at boundary values."""
        # North (0 degrees)
        north = BuildingElementExposedToSolarRadiation(
            orientation360=0.0,
            base_height=1.0,
            height=3.0,
            width=5.0,
        )
        assert north.orientation360 == 0.0  # noqa: float-compare

        # Full circle (360 degrees)
        full_circle = BuildingElementExposedToSolarRadiation(
            orientation360=360.0,
            base_height=1.0,
            height=3.0,
            width=5.0,
        )
        assert full_circle.orientation360 == 360.0

        # East (90 degrees)
        east = BuildingElementExposedToSolarRadiation(
            orientation360=90.0,
            base_height=1.0,
            height=3.0,
            width=5.0,
        )
        assert east.orientation360 == 90.0


class TestBuildingElementTransparent:
    @pytest.fixture
    def valid_example(self) -> BuildingElementTransparent:
        return BuildingElementTransparent(
            u_value=None,
            pitch=45,
            max_window_open_area=3,
            orientation360=180.0,
            height=10,
            width=5,
            window_part_list=[],
            mid_height=40,
            shading=[],
            g_value=1,
            free_area_height=1.6,
            frame_area_fraction=0.25,
            base_height=10,
            type=BuildingElementType.TRANSPARENT,
            thermal_resistance_construction=0.74,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"max_window_open_area": 9999, "width": 5, "height": 10},
                "max_window_open_area must be less than or equal to the area",
            ),
        ],
    )
    def test_validate_max_window_open_area(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: BuildingElementTransparent,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            BuildingElementTransparent(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"base_height": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"free_area_height": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"g_value": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"max_window_open_area": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"mid_height": 0},
                "Input should be greater than 0",
            ),
            (
                {"thermal_resistance_construction": 0},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: BuildingElementTransparent,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            BuildingElementTransparent(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestBuildingElementOpaque:
    @pytest.fixture
    def valid_example(self) -> BuildingElementOpaque:
        return BuildingElementOpaque(
            pitch=1.2,
            type=BuildingElementType.OPAQUE,
            orientation360=180.0,
            height=3.0,
            width=8.0,
            area=24.0,
            areal_heat_capacity=15000.0,
            base_height=10,
            solar_absorption_coeff=0.8,
            mass_distribution_class=MassDistributionClass.I,
            u_value=1.2,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"base_height": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"solar_absorption_coeff": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"solar_absorption_coeff": 2},
                "Input should be less than or equal to 1",
            ),
            (
                {"thermal_resistance_construction": 0},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: BuildingElementOpaque,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            BuildingElementOpaque(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestBuildingElementAdjacentConditionedSpace:
    @pytest.fixture
    def valid_example(self) -> BuildingElementAdjacentConditionedSpace:
        return BuildingElementAdjacentConditionedSpace(
            pitch=1.2,
            type=BuildingElementType.ADJACENT_CONDITIONED,
            area=20.0,
            areal_heat_capacity=15000.0,
            mass_distribution_class=MassDistributionClass.I,
            u_value=1.2,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"thermal_resistance_construction": 0},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: BuildingElementAdjacentConditionedSpace,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            BuildingElementAdjacentConditionedSpace(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestBuildingElementAdjacentUnconditionedSpaceSimple:
    @pytest.fixture
    def valid_example(self) -> BuildingElementAdjacentUnconditionedSpaceSimple:
        return BuildingElementAdjacentUnconditionedSpaceSimple(
            pitch=1.2,
            type=BuildingElementType.ADJACENT_UNCONDITIONED_SPACE_SIMPLE,
            area=20.0,
            areal_heat_capacity=15000.0,
            mass_distribution_class=MassDistributionClass.I,
            u_value=0.7,
            thermal_resistance_unconditioned_space=1.3,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"thermal_resistance_construction": 0},
                "Input should be greater than 0",
            ),
            (
                {"thermal_resistance_unconditioned_space": 0},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: BuildingElementAdjacentUnconditionedSpaceSimple,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            BuildingElementAdjacentUnconditionedSpaceSimple(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestBuildingElementPartyWallValidation:
    """Tests for BuildingElementPartyWall thermal_resistance_cavity validation"""

    @pytest.fixture
    def valid_party_wall_base(self) -> dict:
        """Base valid party wall configuration"""
        return {
            "type": "BuildingElementPartyWall",
            "pitch": 90,
            "u_value": 0.3,
            "mass_distribution_class": MassDistributionClass.D,
            "area": 15.0,
            "areal_heat_capacity": 120000,
        }

    def test_invalid_party_wall_lining_type_raises_error(self, valid_party_wall_base: dict):
        """Test that party_wall_lining_type provided only for certain party wall types"""
        invalid_data = valid_party_wall_base | {
            "party_wall_cavity_type": PartyWallCavityType.SOLID,
            "party_wall_lining_type": "wet_plaster",  # should be None
        }

        with pytest.raises(
            ValidationError,
            match="party_wall_lining_type should only be provided when "
            "party_wall_cavity_type is unfilled_unsealed, unfilled_sealed, or filled_unsealed.",
        ):
            BuildingElementPartyWall.model_validate(invalid_data)

    def test_party_wall_lining_type_provided(self, valid_party_wall_base: dict):
        """Test that party_wall_lining_type provided only for certain party wall types"""
        invalid_data = valid_party_wall_base | {
            "party_wall_cavity_type": PartyWallCavityType.UNFILLED_UNSEALED,
            "party_wall_lining_type": None,
        }

        with pytest.raises(
            ValidationError,
            match="party_wall_lining_type must be provided when "
            "party_wall_cavity_type is unfilled_unsealed, unfilled_sealed, or filled_unsealed.",
        ):
            BuildingElementPartyWall.model_validate(invalid_data)

    def test_defined_resistance_without_thermal_resistance_raises_error(
        self, valid_party_wall_base: dict
    ):
        """Test that defined_resistance type requires thermal_resistance_cavity"""
        invalid_data = valid_party_wall_base | {
            "party_wall_cavity_type": PartyWallCavityType.DEFINED_RESISTANCE,
            # Missing thermal_resistance_cavity
        }

        with pytest.raises(
            ValidationError,
            match="thermal_resistance_cavity must be provided when "
            "party_wall_cavity_type is 'defined_resistance'",
        ):
            BuildingElementPartyWall.model_validate(invalid_data)

    def test_defined_resistance_with_thermal_resistance_is_valid(self, valid_party_wall_base: dict):
        """Test that defined_resistance type works correctly with thermal_resistance_cavity"""
        valid_data = valid_party_wall_base | {
            "party_wall_cavity_type": PartyWallCavityType.DEFINED_RESISTANCE,
            "thermal_resistance_cavity": 2.5,
        }

        party_wall = BuildingElementPartyWall.model_validate(valid_data)
        assert party_wall.party_wall_cavity_type == PartyWallCavityType.DEFINED_RESISTANCE
        assert party_wall.thermal_resistance_cavity == 2.5

    @pytest.mark.parametrize(
        "cavity_type",
        [
            PartyWallCavityType.SOLID,
            PartyWallCavityType.UNFILLED_UNSEALED,
            PartyWallCavityType.FILLED_UNSEALED,
            PartyWallCavityType.UNFILLED_SEALED,
            PartyWallCavityType.FILLED_SEALED,
        ],
    )
    def test_automatic_cavity_types_reject_thermal_resistance(
        self, valid_party_wall_base: dict, cavity_type: PartyWallCavityType
    ):
        lining_type = (
            PartyWallLiningType.DRY_LINED
            if (
                cavity_type == PartyWallCavityType.UNFILLED_UNSEALED
                or cavity_type == PartyWallCavityType.FILLED_UNSEALED
                or cavity_type == PartyWallCavityType.UNFILLED_SEALED
            )
            else None
        )

        """Test that all automatic cavity types reject thermal_resistance_cavity"""
        invalid_data = valid_party_wall_base | {
            "party_wall_cavity_type": cavity_type,
            "party_wall_lining_type": lining_type,
            "thermal_resistance_cavity": 2.5,  # Should not be provided
        }

        with pytest.raises(
            ValidationError,
            match="thermal_resistance_cavity should only be provided when "
            "party_wall_cavity_type is 'defined_resistance'",
        ):
            BuildingElementPartyWall.model_validate(invalid_data)

    @pytest.mark.parametrize(
        "cavity_type",
        [
            PartyWallCavityType.SOLID,
            PartyWallCavityType.UNFILLED_UNSEALED,
            PartyWallCavityType.FILLED_UNSEALED,
            PartyWallCavityType.UNFILLED_SEALED,
            PartyWallCavityType.FILLED_SEALED,
        ],
    )
    def test_automatic_cavity_types_valid_without_thermal_resistance(
        self, valid_party_wall_base: dict, cavity_type: PartyWallCavityType
    ):
        """Test that all automatic cavity types work correctly without thermal_resistance_cavity"""

        lining_type = (
            PartyWallLiningType.DRY_LINED
            if (
                cavity_type == PartyWallCavityType.UNFILLED_UNSEALED
                or cavity_type == PartyWallCavityType.FILLED_UNSEALED
                or cavity_type == PartyWallCavityType.UNFILLED_SEALED
            )
            else None
        )

        valid_data = valid_party_wall_base | {
            "party_wall_cavity_type": cavity_type,
            "party_wall_lining_type": lining_type,
            # No thermal_resistance_cavity - should be valid
        }

        party_wall = BuildingElementPartyWall.model_validate(valid_data)
        assert party_wall.party_wall_cavity_type == cavity_type
        assert party_wall.party_wall_lining_type == lining_type
        assert party_wall.thermal_resistance_cavity is None


class TestBuildingElementGroundSuspendedFloor:
    @pytest.fixture
    def valid_example(self) -> BuildingElementGroundSuspendedFloor:
        return BuildingElementGroundSuspendedFloor(
            pitch=1.2,
            type="BuildingElementGround",
            mass_distribution_class=MassDistributionClass.I,
            u_value=0.7,
            area=200,
            total_area=210,
            perimeter=100,
            psi_wall_floor_junc=0.4,
            thickness_walls=20,
            floor_type=FloorType.SUSPENDED_FLOOR,
            areal_heat_capacity=1.2,
            thermal_resistance_floor_construction=0.2,
            height_upper_surface=0.5,
            shield_fact_location=WindShieldLocation.AVERAGE,
            area_per_perimeter_vent=0.0015,
            thermal_resist_insul=0.5,
            thermal_transm_walls=1.5,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"area_per_perimeter_vent": 0},
                "Input should be greater than 0",
            ),
            (
                {"thermal_transm_walls": 0},
                "Input should be greater than 0",
            ),
            (
                {"thermal_resist_insul": 0},
                "Input should be greater than 0",
            ),
            # Common base class field validations (from deleted BuildingElementGroundBase tests)
            ({"area": 0}, "Input should be greater than 0"),
            ({"total_area": 0}, "Input should be greater than 0"),
            ({"perimeter": 0}, "Input should be greater than 0"),
            ({"areal_heat_capacity": 0}, "Input should be greater than 0"),
            ({"thermal_resistance_floor_construction": 0}, "Input should be greater than 0"),
            ({"thickness_walls": 0}, "Input should be greater than 0"),
            ({"pitch": -1}, "Input should be greater than or equal to 0"),
            ({"pitch": 181}, "Input should be less than or equal to 180"),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: BuildingElementGroundSuspendedFloor,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            BuildingElementGroundSuspendedFloor(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )

    def test_base_class_u_value_validation(self, valid_example):
        """Test inherited base class u_value validator."""
        with pytest.raises(ValidationError, match="r_vi should be greater than zero"):
            BuildingElementGroundSuspendedFloor(
                **(
                    valid_example.model_dump(by_alias=True)
                    | {"u_value": 1, "thermal_resistance_floor_construction": 1}
                ),
            )


class TestBuildingElementGroundHeatedBasement:
    @pytest.fixture
    def valid_example(self) -> BuildingElementGroundHeatedBasement:
        return BuildingElementGroundHeatedBasement(
            pitch=1.2,
            type="BuildingElementGround",
            mass_distribution_class=MassDistributionClass.I,
            u_value=0.7,
            area=200,
            total_area=210,
            perimeter=100,
            psi_wall_floor_junc=0.4,
            thickness_walls=20,
            floor_type=FloorType.HEATED_BASEMENT,
            areal_heat_capacity=1.2,
            thermal_resistance_floor_construction=0.2,
            depth_basement_floor=10,
            thermal_resist_walls_base=0.15,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"thermal_resist_walls_base": 0},
                "Input should be greater than 0",
            ),
            (
                {"depth_basement_floor": 0},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: BuildingElementGroundHeatedBasement,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            BuildingElementGroundHeatedBasement(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )

    def test_base_class_u_value_validation(self, valid_example):
        """Test inherited base class u_value validator."""
        with pytest.raises(ValidationError, match="r_vi should be greater than zero"):
            BuildingElementGroundHeatedBasement(
                **(
                    valid_example.model_dump(by_alias=True)
                    | {"u_value": 1, "thermal_resistance_floor_construction": 1}
                ),
            )


class TestBuildingElementGroundUnheatedBasement:
    @pytest.fixture
    def valid_example(self) -> BuildingElementGroundUnheatedBasement:
        return BuildingElementGroundUnheatedBasement(
            pitch=1.2,
            type="BuildingElementGround",
            mass_distribution_class=MassDistributionClass.I,
            u_value=0.7,
            area=200,
            total_area=210,
            perimeter=100,
            psi_wall_floor_junc=0.4,
            thickness_walls=20,
            floor_type=FloorType.UNHEATED_BASEMENT,
            areal_heat_capacity=1.2,
            thermal_resistance_floor_construction=0.2,
            depth_basement_floor=10,
            thermal_transm_walls=0.15,
            thermal_resist_walls_base=0.15,
            height_basement_walls=10,
            thermal_transm_envi_base=1.2,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"thermal_resist_walls_base": 0},
                "Input should be greater than 0",
            ),
            (
                {"thermal_transm_envi_base": 0},
                "Input should be greater than 0",
            ),
            (
                {"thermal_transm_walls": 0},
                "Input should be greater than 0",
            ),
            (
                {"depth_basement_floor": 0},
                "Input should be greater than 0",
            ),
            (
                {"height_basement_walls": 0},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: BuildingElementGroundUnheatedBasement,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            BuildingElementGroundUnheatedBasement(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )

    def test_base_class_u_value_validation(self, valid_example):
        """Test inherited base class u_value validator."""
        with pytest.raises(ValidationError, match="r_vi should be greater than zero"):
            BuildingElementGroundUnheatedBasement(
                **(
                    valid_example.model_dump(by_alias=True)
                    | {"u_value": 1, "thermal_resistance_floor_construction": 1}
                ),
            )


class TestSpaceHeatSystemElectricStorageHeater:
    @pytest.fixture
    def valid_example(self) -> SpaceHeatSystemElectricStorageHeater:
        return SpaceHeatSystemElectricStorageHeater(
            type="ElecStorageHeater",
            ControlCharger="control_charger_test",
            dry_core_max_output=[[0.0, 0.0], [0.5, 1.5], [1.0, 3.0]],
            dry_core_min_output=[[0.0, 0.0], [0.5, 0.02], [1.0, 0.05]],
            EnergySupply="energy_supply_test",
            air_flow_type=AirFlowType.FAN_ASSISTED,
            Control="control_test",
            storage_capacity=20,
            Zone="zone_test",
            rated_power_instant=2.5,
            pwr_in=3.7,
            n_units=1,
            frac_convective=0.2,
            fan_pwr=11.0,
            state_of_charge_init=0,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"dry_core_max_output": [[0.1, 0.0], [0.5, 1.5], [1.0, 3.0]]},
                "The first SOC value in dry_core_max_output must be 0.0 \\(fully discharged\\).",
            ),
            (
                {"dry_core_max_output": [[0.0, 0.0], [0.5, 1.5], [0.9, 3.0]]},
                "The last SOC value in dry_core_max_output must be 1.0 \\(fully charged\\).",
            ),
            (
                {"dry_core_max_output": [[0.0, 0.0], [0.7, 1.5], [0.5, 3.0], [1.0, 3.5]]},
                "dry_core_max_output SOC values must be in increasing order \\(from 0.0 to 1.0\\).",
            ),
            (
                {"dry_core_min_output": [[0.1, 0.0], [0.5, 0.02], [1.0, 0.05]]},
                "The first SOC value in dry_core_min_output must be 0.0 \\(fully discharged\\).",
            ),
            (
                {"dry_core_min_output": [[0.0, 0.0], [0.5, 0.02], [0.9, 0.05]]},
                "The last SOC value in dry_core_min_output must be 1.0 \\(fully charged\\).",
            ),
            (
                {"dry_core_min_output": [[0.0, 0.0], [0.7, 0.02], [0.5, 0.03], [1.0, 0.05]]},
                "dry_core_min_output SOC values must be in increasing order \\(from 0.0 to 1.0\\).",
            ),
        ],
    )
    def test_validate_dry_core_output(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: SpaceHeatSystemElectricStorageHeater,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            SpaceHeatSystemElectricStorageHeater(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"dry_core_max_output": [[]]},
                "List should have at least 2 items after validation, not 0",
            ),
            (
                {"dry_core_max_output": [[-1], [-1]]},
                "Input should be greater than or equal to 0",
            ),
            (
                {"dry_core_min_output": [[]]},
                "List should have at least 2 items after validation, not 0",
            ),
            (
                {"dry_core_min_output": [[-1], [-1]]},
                "Input should be greater than or equal to 0",
            ),
            (
                {"fan_pwr": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"pwr_in": 0},
                "Input should be greater than 0",
            ),
            (
                {"rated_power_instant": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"frac_convective": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"frac_convective": 2},
                "Input should be less than or equal to 1",
            ),
            (
                {"n_units": 0},
                "Input should be greater than 0",
            ),
            (
                {"storage_capacity": 0},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: SpaceHeatSystemElectricStorageHeater,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            SpaceHeatSystemElectricStorageHeater(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )

    def test_validate_dry_core_output_when_no_input(
        self,
        valid_example: SpaceHeatSystemElectricStorageHeater,
    ):
        modified_example = SpaceHeatSystemElectricStorageHeater(
            **(valid_example.model_dump(by_alias=True) | {"dry_core_max_output": []}),
        )
        modified_example = SpaceHeatSystemElectricStorageHeater.model_validate(modified_example)
        assert modified_example.dry_core_max_output == []

        modified_example = SpaceHeatSystemElectricStorageHeater(
            **(valid_example.model_dump(by_alias=True) | {"dry_core_min_output": []}),
        )
        modified_example = SpaceHeatSystemElectricStorageHeater.model_validate(modified_example)
        assert modified_example.dry_core_min_output == []


class TestFancoilTestData:
    @pytest.fixture
    def valid_example(self) -> FancoilTestData:
        return FancoilTestData(
            fan_speed_data=[
                {"temperature_diff": 80.0, "power_output": [2.7, 3.6, 5, 5.3, 6.2, 7.4]},
                {"temperature_diff": 70.0, "power_output": [2.3, 3.1, 4.2, 4.5, 5.3, 6.3]},
                {"temperature_diff": 60.0, "power_output": [1.9, 2.6, 3.5, 3.8, 4.4, 5.3]},
                {"temperature_diff": 50.0, "power_output": [1.5, 2, 2.8, 3, 3.5, 4.2]},
                {"temperature_diff": 40.0, "power_output": [1.1, 1.5, 2.05, 2.25, 2.6, 3.15]},
                {"temperature_diff": 30.0, "power_output": [0.7, 0.97, 1.32, 1.49, 1.7, 2.09]},
                {"temperature_diff": 20.0, "power_output": [0.3, 0.44, 0.59, 0.73, 0.8, 1.03]},
                {"temperature_diff": 10.0, "power_output": [0, 0, 0, 0, 0, 0]},
            ],
            fan_power_W=[15, 19, 25, 33, 43, 56],
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {
                    "fan_speed_data": [
                        {"temperature_diff": 80.0, "power_output": [2, 4, 6, 8, 9, 11]},
                        {"temperature_diff": 70.0, "power_output": [2, 4, 6, 8, 9]},
                    ]
                },
                "Fan speed lists of fancoil manufacturer data differ in length",
            ),
            (
                {
                    "fan_speed_data": [
                        {"temperature_diff": 80.0, "power_output": [2, 4, 6, 8, 9]},
                        {"temperature_diff": 70.0, "power_output": [2, 4, 6, 8, 9]},
                    ],
                    "fan_power_W": [15, 19, 25, 33, 43, 56],
                },
                "Fan power data length does not match the length of fan speed data",
            ),
        ],
    )
    def test_validate_lists_length(
        self, inputs: dict[str, Any], expected_message: str, valid_example: FancoilTestData
    ):
        with pytest.raises(ValidationError, match=expected_message):
            FancoilTestData(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"fan_power_W": [0]},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: FancoilTestData,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            FancoilTestData(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestApplianceGains:
    @pytest.fixture
    def valid_example(self) -> ApplianceGains:
        return ApplianceGains(
            start_day=0,
            time_series_step=1,
            EnergySupply="mains elec",
            gains_fraction=0.8,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"Standby": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"gains_fraction": 2},
                "Input should be less than or equal to 1",
            ),
            (
                {"gains_fraction": -1},
                "Input should be greater than or equal to 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: ApplianceGains,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            ApplianceGains(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestBoilerCostScheduleHybrid:
    @pytest.fixture
    def valid_example(self) -> BoilerCostScheduleHybrid:
        return BoilerCostScheduleHybrid(
            cost_schedule_boiler={"main": []},
            cost_schedule_hp={"main": []},
            cost_schedule_start_day=0,
            cost_schedule_time_series_step=1,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"cost_schedule_start_day": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"cost_schedule_start_day": 366},
                "Input should be less than or equal to 365",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: BoilerCostScheduleHybrid,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            BoilerCostScheduleHybrid(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestControlOnOffCostMinimising:
    @pytest.fixture
    def valid_example(self) -> ControlOnOffCostMinimising:
        return ControlOnOffCostMinimising(
            start_day=0,
            time_series_step=1,
            type="OnOffCostMinimisingTimeControl",
            schedule={"main": []},
            time_on_daily=1,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"time_on_daily": 0},
                "Input should be greater than 0",
            ),
            (
                {"time_on_daily": 25},
                "Input should be less than or equal to 24",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: ControlOnOffCostMinimising,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            ControlOnOffCostMinimising(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestExternalConditionsInput:
    @pytest.fixture
    def valid_example(self) -> ExternalConditionsInput:
        return ExternalConditionsInput()

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"air_temperatures": [-274]},
                "Input should be greater than or equal to -273.15",
            ),
            (
                {"latitude": -91},
                "Input should be greater than or equal to -90",
            ),
            (
                {"latitude": 91},
                "Input should be less than or equal to 90",
            ),
            (
                {"longitude": -181},
                "Input should be greater than or equal to -180",
            ),
            (
                {"longitude": 181},
                "Input should be less than or equal to 180",
            ),
            (
                {"solar_reflectivity_of_ground": [-1]},
                "Input should be greater than or equal to 0",
            ),
            (
                {"solar_reflectivity_of_ground": [2]},
                "Input should be less than or equal to 1",
            ),
            (
                {"wind_speeds": [-1]},
                "Input should be greater than or equal to 0",
            ),
            (
                {"diffuse_horizontal_radiation": [-1]},
                "Input should be greater than or equal to 0",
            ),
            (
                {"direct_beam_radiation": [-1]},
                "Input should be greater than or equal to 0",
            ),
            (
                {"wind_directions": [-1]},
                "Input should be greater than or equal to 0",
            ),
            (
                {"wind_directions": [361]},
                "Input should be less than or equal to 360",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: ExternalConditionsInput,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            ExternalConditionsInput(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )

    def test_are_all_fields_set(self):
        valid_example = ExternalConditionsInput(
            air_temperatures=[0.0] * 8760,
            wind_speeds=[0.0] * 8760,
            wind_directions=[0.0] * 8760,
            diffuse_horizontal_radiation=[0.0] * 8760,
            direct_beam_conversion_needed=False,
            direct_beam_radiation=[0.0] * 8760,
            latitude=13.9,
            longitude=34.2,
            shading_segments=[],
            solar_reflectivity_of_ground=[0.0] * 8760,
        )
        assert valid_example.are_all_fields_set()

        invalid_example = ExternalConditionsInput()
        assert not invalid_example.are_all_fields_set()

    @pytest.mark.parametrize(
        "invalid_field",
        [
            "air_temperatures",
            "wind_speeds",
            "wind_directions",
            "diffuse_horizontal_radiation",
            "direct_beam_radiation",
            "solar_reflectivity_of_ground",
        ],
    )
    def test_are_all_fields_set_invalid_lengths(
        self,
        invalid_field: str,
    ):
        valid_data = {
            "air_temperatures": [0.0] * 8760,
            "wind_speeds": [0.0] * 8760,
            "wind_directions": [0.0] * 8760,
            "diffuse_horizontal_radiation": [0.0] * 8760,
            "direct_beam_conversion_needed": False,
            "direct_beam_radiation": [0.0] * 8760,
            "latitude": 13.9,
            "longitude": 34.2,
            "shading_segments": [],
            "solar_reflectivity_of_ground": [0.0] * 8760,
            invalid_field: [0.0],
        }

        ext_cond = ExternalConditionsInput(**valid_data)
        with pytest.raises(
            ValueError, match=f"ExternalConditions {invalid_field} should contain 8760 values."
        ):
            ext_cond.are_all_fields_set()


class TestHeatSourceWetHeatPump:
    @pytest.fixture
    def valid_heat_pump(self) -> HeatSourceWetHeatPump:
        return HeatSourceWetHeatPump(
            type="HeatPump",
            EnergySupply="mains elec",
            backup_ctrl_type="TopUp",
            min_temp_diff_flow_return_for_hp_to_operate=1,
            modulating_control=True,
            power_crankcase_heater=0.01,
            power_off=0.015,
            power_source_circ_pump=0.010,
            power_heating_circ_pump=0.015,
            power_standby=0.015,
            power_heating_warm_air_fan=0.015,
            power_max_backup=3.0,
            sink_type=HeatPumpSinkType.WATER,
            source_type=HeatPumpSourceType.EXHAUST_AIR_MIXED,
            temp_distribution_heat_network=10,
            temp_return_feed_max=70,
            temp_lower_operating_limit=-5,
            eahp_mixed_max_temp=10,
            eahp_mixed_min_temp=10,
            test_data_EN14825=[],
            time_constant_onoff_operation=140,
            time_delay_backup=0.5,
            var_flow_temp_ctrl_during_test=True,
        )

    @pytest.fixture(scope="class")
    def valid_boiler(self) -> HeatPumpBoiler:
        return HeatPumpBoiler(
            EnergySupply="mains_gas",
            EnergySupply_aux="mains elec",
            boiler_location=HeatSourceLocation.INTERNAL,
            efficiency_full_load=0.9,
            efficiency_part_load=0.7,
            electricity_circ_pump=0.0,
            electricity_full_load=0.2,
            electricity_part_load=0.1,
            electricity_standby=0.01,
            modulation_load=0.0,
            rated_power=6.0,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"eahp_mixed_max_temp": -274},
                "Input should be greater than or equal to -273.15",
            ),
            (
                {"eahp_mixed_min_temp": -274},
                "Input should be greater than or equal to -273.15",
            ),
            (
                {"temp_distribution_heat_network": 0},
                "Input should be greater than 0",
            ),
            (
                {"temp_lower_operating_limit": -274},
                "Input should be greater than or equal to -273.15",
            ),
            (
                {"temp_return_feed_max": 0},
                "Input should be greater than 0",
            ),
            (
                {"min_modulation_rate_20": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"min_modulation_rate_20": 2},
                "Input should be less than or equal to 1",
            ),
            (
                {"min_modulation_rate_35": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"min_modulation_rate_35": 2},
                "Input should be less than or equal to 1",
            ),
            (
                {"min_modulation_rate_55": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"min_modulation_rate_55": 2},
                "Input should be less than or equal to 1",
            ),
            (
                {"power_crankcase_heater": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"power_heating_circ_pump": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"power_heating_warm_air_fan": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"power_max_backup": 0},
                "Input should be greater than 0",
            ),
            (
                {"power_off": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"power_source_circ_pump": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"power_standby": -0.1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"time_constant_onoff_operation": 0},
                "Input should be greater than 0",
            ),
            (
                {"time_delay_backup": -1},
                "Input should be greater than or equal to 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_heat_pump: HeatSourceWetHeatPump,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            HeatSourceWetHeatPump(
                **(valid_heat_pump.model_dump(by_alias=True) | inputs),
            )

    @pytest.mark.parametrize(
        "inputs, valid, exception_match",
        # Valid
        [
            (
                {
                    "boiler": None,
                    "backup_ctrl_type": control_type,
                    "power_max_backup": 3.0,
                    "time_delay_backup": 0.5,
                },
                True,
                None,
            )
            for control_type in [
                HeatPumpBackupControlType.TOP_UP,
                HeatPumpBackupControlType.SUBSTITUTE,
            ]
        ]
        + [
            (
                {
                    "boiler": True,
                    "backup_ctrl_type": control_type,
                    "power_max_backup": None,
                    "time_delay_backup": 0.5,
                },
                True,
                None,
            )
            for control_type in [
                HeatPumpBackupControlType.TOP_UP,
                HeatPumpBackupControlType.SUBSTITUTE,
            ]
        ]
        # Invalid
        + [
            (
                {
                    "boiler": None,
                    "backup_ctrl_type": HeatPumpBackupControlType.NONE,
                    "power_max_backup": 3.0,
                    "time_delay_backup": 0.5,
                },
                False,
                "power_max_backup can not be set if backup_ctrl_type is 'None'.",
            ),
            (
                {
                    "boiler": True,
                    "backup_ctrl_type": HeatPumpBackupControlType.NONE,
                    "power_max_backup": None,
                    "time_delay_backup": 0.5,
                },
                False,
                "boiler can not be set if backup_ctrl_type is 'None'.",
            ),
            (
                {
                    "boiler": None,
                    "backup_ctrl_type": HeatPumpBackupControlType.TOP_UP,
                    "power_max_backup": 3.0,
                    "time_delay_backup": None,
                },
                False,
                "time_delay_backup is required if backup_ctrl_type is set.",
            ),
            (
                {
                    "boiler": True,
                    "backup_ctrl_type": HeatPumpBackupControlType.NONE,
                    "power_max_backup": 3.0,
                    "time_delay_backup": 0.5,
                },
                False,
                "power_max_backup and boiler can not both be set.",
            ),
            (
                {
                    "boiler": None,
                    "backup_ctrl_type": HeatPumpBackupControlType.TOP_UP,
                    "power_max_backup": None,
                    "time_delay_backup": 0.5,
                },
                False,
                "Either power_max_backup or boiler is required if backup_ctrl_type is set.",
            ),
        ],
    )
    def test_validate_backup_configuration(
        self,
        inputs: dict[str, Any],
        valid: bool,
        exception_match: str | None,
        valid_heat_pump: HeatSourceWetHeatPump,
        valid_boiler: HeatPumpBoiler,
    ):
        if inputs.get("boiler", None) is True:
            inputs["boiler"] = valid_boiler
        if valid:
            heat_pump = HeatSourceWetHeatPump(
                **(valid_heat_pump.model_dump(by_alias=True) | inputs)
            )
            assert isinstance(heat_pump, HeatSourceWetHeatPump)
        else:
            with pytest.raises(pydantic.ValidationError, match=exception_match):
                HeatSourceWetHeatPump(**(valid_heat_pump.model_dump(by_alias=True) | inputs))


class TestHeatPumpBufferTank:
    @pytest.fixture
    def valid_example(self) -> HeatPumpBufferTank:
        return HeatPumpBufferTank(
            daily_losses=1.68,
            pump_fixed_flow_rate=15,
            pump_power_at_flow_rate=0.04,
            volume=40,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"daily_losses": 0},
                "Input should be greater than 0",
            ),
            (
                {"pump_fixed_flow_rate": 0},
                "Input should be greater than 0",
            ),
            (
                {"pump_power_at_flow_rate": 0},
                "Input should be greater than 0",
            ),
            (
                {"volume": 0},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: HeatPumpBufferTank,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            HeatPumpBufferTank(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestHeatPumpHotWaterOnlyTestDatum:
    @pytest.fixture
    def valid_example(self) -> HeatPumpHotWaterOnlyTestDatum:
        return HeatPumpHotWaterOnlyTestDatum(
            cop_dhw=2.5,
            energy_input_measured=2.4,
            hw_vessel_loss_daily=2.0,
            hw_tapping_prof_daily_total=5.8,
            power_standby=0.012,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"cop_dhw": 0},
                "Input should be greater than 0",
            ),
            (
                {"energy_input_measured": 0},
                "Input should be greater than 0",
            ),
            (
                {"hw_tapping_prof_daily_total": 0},
                "Input should be greater than 0",
            ),
            (
                {"hw_vessel_loss_daily": 0},
                "Input should be greater than 0",
            ),
            (
                {"power_standby": 0},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: HeatPumpHotWaterOnlyTestDatum,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            HeatPumpHotWaterOnlyTestDatum(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestInfiltrationVentilation:
    @pytest.fixture
    def valid_example(self) -> InfiltrationVentilation:
        return InfiltrationVentilation(
            Leaks={
                "ventilation_zone_height": 6,
                "test_pressure": 50,
                "test_result": 1.2,
                "env_area": 220,
            },
            Vents={},
            altitude=10,
            cross_vent_possible=True,
            shield_class=VentilationShieldClass.SHIELDED,
            terrain_class=TerrainClass.URBAN,
            ventilation_zone_base_height=10,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"ach_max_static_calcs": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"ach_min_static_calcs": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"vent_opening_ratio_init": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"vent_opening_ratio_init": 2},
                "Input should be less than or equal to 1",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: InfiltrationVentilation,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            InfiltrationVentilation(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestStorageTank:
    @pytest.fixture
    def valid_example(self) -> StorageTank:
        return StorageTank(
            type="StorageTank",
            ColdWaterSource="cold water source",
            HeatSource={
                "hp": {
                    "type": "HeatSourceWet",
                    "name": "hp",
                    "temp_flow_limit_upper": 65,
                    "Controlmin": "min_temp",
                    "Controlmax": "setpoint_temp_max",
                    "heater_position": 0.1,
                    "thermostat_position": 0.33,
                }
            },
            daily_losses=10,
            init_temp=10,
            volume=100,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"init_temp": -2},
                "Input should be greater than or equal to 0",
            ),
            (
                {"init_temp": 101},
                "Input should be less than or equal to 100",
            ),
            (
                {"daily_losses": 0},
                "Input should be greater than 0",
            ),
            (
                {"heat_exchanger_surface_area": 0},
                "Input should be greater than 0",
            ),
            (
                {"volume": 0},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: StorageTank,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            StorageTank(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestZone:
    @pytest.fixture
    def valid_example(self) -> Zone:
        return Zone(
            BuildingElement={},
            ThermalBridging=1.9,
            area=200,
            temp_setpnt_init=10,
            volume=100,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"area": 0},
                "Input should be greater than 0",
            ),
            (
                {"volume": 0},
                "Input should be greater than 0",
            ),
            (
                {"temp_setpnt_init": -274},
                "Input should be greater than or equal to -273.15",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: Zone,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            Zone(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"SpaceHeatSystem": ["mains", "mains", "other"]},
                "Invalid input: duplicate entry in space_heat_system list",
            ),
            (
                {"SpaceCoolSystem": ["mains", "mains", "other"]},
                "Invalid input: duplicate entry in space_cool_system list",
            ),
        ],
    )
    def test_validate_system_list_no_duplicates(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: Zone,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            Zone(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestWindowTreatment:
    @pytest.fixture
    def valid_example(self) -> WindowTreatment:
        return WindowTreatment(
            controls="auto_motorised",
            delta_r=10,
            trans_red=0.3,
            type="curtains",
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"trans_red": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"trans_red": 2},
                "Input should be less than or equal to 1",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: WindowTreatment,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            WindowTreatment(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestAirTerminalDevice:
    @pytest.fixture
    def valid_example(self) -> AirTerminalDevice:
        return AirTerminalDevice(
            area_cm2=100,
            pressure_difference_ref=1.2,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"area_cm2": 0},
                "Input should be greater than 0",
            ),
            (
                {"pressure_difference_ref": 0},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: AirTerminalDevice,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            AirTerminalDevice(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestEdgeInsulationHorizontal:
    @pytest.fixture
    def valid_example(self) -> EdgeInsulationHorizontal:
        return EdgeInsulationHorizontal(
            type="horizontal",
            edge_thermal_resistance=1.2,
            width=10,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"edge_thermal_resistance": 0},
                "Input should be greater than 0",
            ),
            (
                {"width": 0},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: EdgeInsulationHorizontal,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            EdgeInsulationHorizontal(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestEdgeInsulationVertical:
    @pytest.fixture
    def valid_example(self) -> EdgeInsulationVertical:
        return EdgeInsulationVertical(
            type="vertical",
            edge_thermal_resistance=1.2,
            depth=10,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"edge_thermal_resistance": 0},
                "Input should be greater than 0",
            ),
            (
                {"depth": 0},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: EdgeInsulationVertical,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            EdgeInsulationVertical(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestWindowPart:
    @pytest.fixture
    def valid_example(self) -> WindowPart:
        return WindowPart(
            mid_height_air_flow_path=1.5,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"mid_height_air_flow_path": 0},
                "Input should be greater than 0",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: WindowPart,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            WindowPart(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestHeatPumpTestDatum:
    @pytest.fixture
    def valid_example(self) -> HeatPumpTestDatum:
        return HeatPumpTestDatum(
            capacity=10,
            cop=1.2,
            design_flow_temp=12,
            temp_test=14,
            temp_outlet=12,
            temp_source=13,
            test_letter="A",
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"air_flow_rate": 0},
                "Input should be greater than 0",
            ),
            (
                {"capacity": 0},
                "Input should be greater than 0",
            ),
            (
                {"cop": 0},
                "Input should be greater than 0",
            ),
            (
                {"eahp_mixed_ext_air_ratio": -1},
                "Input should be greater than or equal to 0",
            ),
            (
                {"eahp_mixed_ext_air_ratio": 2},
                "Input should be less than or equal to 1",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: HeatPumpTestDatum,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            HeatPumpTestDatum(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestScheduleRepeaterForDegreesCelsius:
    @pytest.fixture
    def valid_example(self) -> ScheduleRepeaterForDegreesCelsius:
        return ScheduleRepeaterForDegreesCelsius(
            repeat=1,
            value=None,
        )

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            (
                {"repeat": 0},
                "Input should be greater than or equal to 1",
            ),
        ],
    )
    def test_validate_range_constraints(
        self,
        inputs: dict[str, Any],
        expected_message: str,
        valid_example: ScheduleRepeaterForDegreesCelsius,
    ):
        with pytest.raises(ValidationError, match=expected_message):
            ScheduleRepeaterForDegreesCelsius(
                **(valid_example.model_dump(by_alias=True) | inputs),
            )


class TestControlCombinations:
    def test_main_property(self):
        ctrl_combination = ControlCombinations(
            {"main": {"controls": ["test_ctrl"], "operation": "AND"}}
        )
        main = ctrl_combination.main
        assert isinstance(main, ControlCombination)

    def test_validate_main_exists(self):
        with pytest.raises(
            ValidationError, match="ControlCombinations must contain a 'main' entry"
        ):
            ControlCombinations({})


class TestScheduleForBoolean:
    def test_main_property(self):
        schedule = ScheduleForBoolean({"main": []})
        main = schedule.main
        assert isinstance(main, list)

    def test_validate_main_exists(self):
        with pytest.raises(ValidationError, match="Schedule must contain a 'main' entry"):
            ScheduleForBoolean({})


class TestScheduleForDegreesCelsius:
    def test_main_property(self):
        schedule = ScheduleForDegreesCelsius({"main": []})
        main = schedule.main
        assert isinstance(main, list)

    def test_validate_main_exists(self):
        with pytest.raises(ValidationError, match="Schedule must contain a 'main' entry"):
            ScheduleForDegreesCelsius({})


class TestScheduleForDouble:
    def test_main_property(self):
        schedule = ScheduleForDouble({"main": []})
        main = schedule.main
        assert isinstance(main, list)

    def test_validate_main_exists(self):
        with pytest.raises(ValidationError, match="Schedule must contain a 'main' entry"):
            ScheduleForDouble({})


class TestInternalGains:
    def test_cold_water_losses_property_exists(self):
        internal_gains = InternalGains(
            root={
                "ColdWaterLosses": {"start_day": 1, "time_series_step": 1, "schedule": {"main": []}}
            }
        )
        result = internal_gains.cold_water_losses
        assert isinstance(result, InternalGainsDetails)

    def test_evaporative_losses_property_exists(self):
        internal_gains = InternalGains(
            root={
                "EvaporativeLosses": {
                    "start_day": 1,
                    "time_series_step": 1,
                    "schedule": {"main": []},
                }
            }
        )
        result = internal_gains.evaporative_losses
        assert isinstance(result, InternalGainsDetails)

    def test_metabolic_gains_property_exists(self):
        internal_gains = InternalGains(
            root={
                "metabolic gains": {"start_day": 1, "time_series_step": 1, "schedule": {"main": []}}
            }
        )
        result = internal_gains.metabolic_gains
        assert isinstance(result, InternalGainsDetails)

    def test_other_property_exists(self):
        internal_gains = InternalGains(
            root={"other": {"start_day": 1, "time_series_step": 1, "schedule": {"main": []}}}
        )
        result = internal_gains.other
        assert isinstance(result, InternalGainsDetails)

    def test_total_internal_gains_1_property_exists(self):
        internal_gains = InternalGains(
            root={
                "total internal gains": {
                    "start_day": 1,
                    "time_series_step": 1,
                    "schedule": {"main": []},
                }
            }
        )
        result = internal_gains.total_internal_gains_1
        assert isinstance(result, InternalGainsDetails)

        internal_gains = InternalGains(
            root={
                "total_internal_gains": {
                    "start_day": 1,
                    "time_series_step": 1,
                    "schedule": {"main": []},
                }
            }
        )
        result = internal_gains.total_internal_gains_1
        assert isinstance(result, InternalGainsDetails)


class TestUniqueStringList:
    class ExampleModel(BaseModel):
        a: UniqueStringList

    @pytest.mark.parametrize(
        "value",
        [
            ["a"],
            ["a", "b"],
            ["a", "b", "c"],
        ],
    )
    def test_valid(self, value: list[str]):
        model = TestUniqueStringList.ExampleModel.model_validate({"a": value})
        assert isinstance(model.a, list)
        assert model.a == value

    @pytest.mark.parametrize(
        "value",
        [
            ["a", "a"],
            ["b", "a", "b"],
            ["a", "b", "c", "b"],
        ],
    )
    def test_invalid(self, value: list[str]):
        with pytest.raises(ValidationError, match="List must only contain unique items."):
            TestUniqueStringList.ExampleModel.model_validate({"a": value})
