# Utilities for writing JSON Schema files.
import json
from pathlib import Path

import pydantic

from hem_core.input_output.input import Input
from hem_core.input_output.output import Output

SCHEMA_MAPPING: dict[pydantic.BaseModel, Path] = {
    Input: Path("core-input.json"),
    Output: Path("core-output.json"),
}


def write_schema_files(schema_path: Path):
    """
    Generate and write all JSON schema files.
    """
    for model, filename in SCHEMA_MAPPING.items():
        with open(schema_path / filename, "w") as file:
            json.dump(
                _format_json_schema(model.model_json_schema()),
                file,
                indent=2,
            )


def _format_json_schema(schema: dict) -> dict:
    # Format pydantic's JSON schema into a slightly more standard layout
    schema |= {
        "$schema": "https://json-schema.org/draft/2020-12/schema#",
        # TODO we can use the description to note the version and time of generation.
        # "description": f"Version {version_number}; generated {datetime.date.today()}"
    }
    key_order = [
        "$schema",
        "title",
        "description",
        "type",
        "required",
        "additionalProperties",
        "properties",
        "$defs",
    ]
    return {key: schema[key] for key in key_order if key in schema} | schema
