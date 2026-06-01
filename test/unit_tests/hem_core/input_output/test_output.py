import json
from pathlib import Path
from typing import Any

import pytest
from pydantic.fields import FieldInfo

from hem_core.input_output.output import Output, OutputHotWaterSystems, OutputSummary
from hem_core.schema_utils import write_schema_files

PATH_ROOT = Path(__file__).parent.parent.parent.parent.parent
PATH_SCHEMAS = PATH_ROOT / "schemas"


class TestOutputHotWaterSystems:
    @pytest.mark.parametrize(
        "field_name, field_info",
        [
            (field_name, field_info)
            for field_name, field_info in OutputHotWaterSystems.model_fields.items()
        ],
    )
    def test_all_fields_define_an_alias(self, field_name: str, field_info: FieldInfo):
        assert field_info.alias is not None, (
            f"All OutputHotWaterSystems field {field_name} must define an alias as the column heading for the output file"
        )


class TestOutputSummary:
    @pytest.mark.parametrize(
        "values, computed_field, expected",
        [
            (
                {
                    "total_floor_area": 100.0,
                    "space_heat_demand_total": 12_000.0,
                },
                "space_heat_demand_by_floor_area",
                120.0,
            ),
            (
                {
                    "total_floor_area": 50.0,
                    "space_heat_demand_total": 12_000.0,
                },
                "space_heat_demand_by_floor_area",
                240.0,
            ),
            (
                {
                    "total_floor_area": 85.0,
                    "space_heat_demand_total": 12_000.0,
                },
                "space_heat_demand_by_floor_area",
                pytest.approx(141.1764705882),
            ),
            (
                {
                    "total_floor_area": 100.0,
                    "space_cool_demand_total": 6_000.0,
                },
                "space_cool_demand_by_floor_area",
                60.0,
            ),
            (
                {
                    "total_floor_area": 50.0,
                    "space_cool_demand_total": 6_000.0,
                },
                "space_cool_demand_by_floor_area",
                120.0,
            ),
            (
                {
                    "total_floor_area": 85.0,
                    "space_cool_demand_total": 2_000.0,
                },
                "space_cool_demand_by_floor_area",
                pytest.approx(23.529411764705),
            ),
            (
                {
                    "total_floor_area": 100.0,
                    "delivered_energy": {
                        "total": {
                            "total": 20_000.0,
                            "_unmet_demand": 0.0,
                            "cooking": 3_000.0,
                            "lighting": 500.0,
                        },
                        "mains elec": {
                            "total": 20_000.0,
                            "_unmet_demand": 0.0,
                            "cooking": 1_000.0,
                            "lighting": 500.0,
                        },
                    },
                },
                "delivered_energy_by_floor_area",
                {
                    "total": {
                        "total": 200.0,
                        "_unmet_demand": 0.0,
                        "cooking": 30.0,
                        "lighting": 5.0,
                    },
                    "mains elec": {
                        "total": 200.0,
                        "_unmet_demand": 0.0,
                        "cooking": 10.0,
                        "lighting": 5.0,
                    },
                },
            ),
        ],
    )
    def test_computed_fields(self, values: dict[str, Any], computed_field: str, expected: float):
        output = OutputSummary.model_construct(
            **values
            # Use model-construct to avoid validation and defining all the unrelated fields for each test case.
        )
        assert getattr(output, computed_field) == expected, (
            f"OutputSummary computed field '{computed_field}' not as expected"
        )


class TestOutput:
    def test_schema_generation_is_up_to_date(self, tmp_path: Path):
        """
        Test that ensures the core Output JSON schema file is always up-to-date with the Pydantic models.
        This catches schema drift if the models are modified but schemas aren't regenerated.
        """
        core_schema_filename = Path("core-output.json")
        existing_schema_path = PATH_SCHEMAS / core_schema_filename
        assert existing_schema_path.exists()

        write_schema_files(schema_path=tmp_path)
        temp_core_schema_path = tmp_path / core_schema_filename
        assert temp_core_schema_path.exists(), f"Temporary {core_schema_filename} was not written"

        # The schemas should be identical.
        with open(existing_schema_path) as file:
            existing_schema_str = file.read()
        with open(temp_core_schema_path) as file:
            temp_schema_str = file.read()

        assert temp_schema_str == existing_schema_str

    def test_generates_a_valid_schema(self):
        """Test that Output can generate a valid JSON schema without errors."""
        schema = Output.model_json_schema()

        # Test that schema is valid JSON by serializing and deserializing
        schema_json = json.dumps(schema)
        parsed_schema = json.loads(schema_json)

        # Basic validation that it's a proper JSON Schema
        assert isinstance(parsed_schema, dict)
        assert len(parsed_schema.get("properties", {})) > 0, (
            "Schema should have at least one property"
        )
