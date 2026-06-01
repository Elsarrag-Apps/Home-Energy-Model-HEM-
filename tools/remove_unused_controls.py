#!/usr/bin/env python3

from pathlib import Path

import typer
from pydantic import BaseModel

from hem_core.input_output.input import Input

PATH_ROOT = Path(__file__).parent.parent


def main(directory: Path):
    """
    A simple script to remove unused control definitions from Input JSON files.
    """
    for demo_file in directory.glob("*.json"):
        with open(demo_file) as file:
            input = Input.model_validate_json(file.read())
        changed = False
        if input.control:
            # Copy control names to a list, so that we can alter the dict in the loop below.
            control_names = list(input.control.keys())
            for name in control_names:
                if not _is_control_present(name, input):
                    del input.control[name]
                    changed = True
            if changed:
                with open(demo_file, "w") as file:
                    file.write(input.model_dump_json(indent=2, by_alias=True, exclude_unset=True))


def _is_control_present(control_name: str, model_instance: BaseModel) -> bool:
    for field_name in model_instance.__class__.model_fields.keys():
        field_value = getattr(model_instance, field_name)
        if field_value == control_name:
            return True  # Naive but a lot simpler than checking field types.
        elif isinstance(field_value, BaseModel):
            if _is_control_present(control_name, field_value):
                return True
        elif isinstance(field_value, dict):
            for dict_item in field_value.values():
                if dict_item == control_name:
                    return True
                elif isinstance(dict_item, BaseModel):
                    if _is_control_present(control_name, dict_item):
                        return True
        elif isinstance(field_value, list):
            for list_item in field_value:
                if list_item == control_name:
                    return True
                elif isinstance(list_item, BaseModel):
                    if _is_control_present(control_name, list_item):
                        return True
    return False


if __name__ == "__main__":
    typer.run(main)
