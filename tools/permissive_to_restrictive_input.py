#!/usr/bin/env python3

from pathlib import Path

import pydantic
import typer

from hem_core.input_output.input import Input as InputRestrictive
from hem_core.input_output.input import StrictBaseModel

PATH_ROOT = Path(__file__).parent.parent


def main(directory: Path):
    """Convert input JSON files to the restrictive Input format, removing any extra fields not in the schema."""
    validation_errors: dict[Path, pydantic.ValidationError] = {}

    _recursive_make_model_permissive(StrictBaseModel)

    for demo_file in directory.glob("*.json"):
        with open(demo_file) as file:
            raw_json = file.read()
        try:
            input_restrictive = InputRestrictive.model_validate_json(raw_json)
        except pydantic.ValidationError as ex:
            validation_errors[demo_file] = ex
            continue
        with open(demo_file, "w") as file:
            file.write(
                input_restrictive.model_dump_json(indent=2, by_alias=True, exclude_unset=True)
            )
    if validation_errors:
        for demo_file, exception in validation_errors.items():
            print(
                f"""
                Errors for demo file: {demo_file}
                {exception}
                """
            )


def _recursive_make_model_permissive(model: type[pydantic.BaseModel]):
    for sub_cls in model.__subclasses__():
        sub_cls.model_config["extra"] = "ignore"
        sub_cls.model_rebuild(force=True)
        _recursive_make_model_permissive(sub_cls)


if __name__ == "__main__":
    typer.run(main)
