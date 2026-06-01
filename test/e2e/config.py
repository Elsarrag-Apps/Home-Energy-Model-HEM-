from pathlib import Path
from typing import Annotated, Self

import pydantic

from hem_core.hem import safe_path

PATH_ROOT = safe_path(Path(__file__).parent.parent.parent)
PATH_TEST = safe_path(PATH_ROOT / "test")
PATH_TEST_E2E = safe_path(PATH_TEST / "e2e")
PATH_DEMO_FILES = safe_path(PATH_TEST_E2E / "demo_files")
PATH_EXPECTED_RESULTS = safe_path(PATH_TEST_E2E / "expected_results")


class Tolerance(pydantic.BaseModel):
    atol: Annotated[float, pydantic.Field(gt=0)] = 1e-9
    rtol: Annotated[float, pydantic.Field(gt=0)] = 1e-6


class DemoFileConfig(pydantic.BaseModel):
    hem_arguments: list[str] = [
        "--CIBSE-weather-file",
        "test/e2e/demo_files/London_weather_CIBSE_format.csv",
        "--tariff-file",
        "test/e2e/demo_files/tariff_data_25-06-2024.csv",
        "--detailed-output-heating-cooling",
        "--heat-balance",
    ]
    tolerance: Tolerance = Tolerance()
    note: str | None = None


class E2EConfig(pydantic.BaseModel):
    """
    Model for demo_files_config.json to load in per-demo-file customisations
    """

    file_patterns: Annotated[
        dict[str, DemoFileConfig],
        pydantic.Field(description="Dict using a file-glob as the key to match demo files"),
    ]
    per_file: dict[Path, DemoFileConfig]

    @pydantic.field_validator("file_patterns", mode="after")
    @classmethod
    def validate_file_patterns(cls, value: dict[str, DemoFileConfig]):
        for pattern in value.keys():
            try:
                matches = PATH_DEMO_FILES.glob(pattern)
                for match in matches:
                    if match.is_dir():
                        raise ValueError("Pattern '{pattern}' matched a directory")
                    if not match.suffix == ".json":
                        raise ValueError(f"Pattern '{pattern}' matched a non-JSON file: {match}")
            except SyntaxError as ex:
                raise ValueError("Invalid file glob pattern") from ex
        return value

    @pydantic.model_validator(mode="after")
    def validate_per_file_paths(self) -> Self:
        for path in self.per_file.keys():
            if path.is_absolute():
                raise ValueError(f"Demo file path should be relative to project root: {path}")
            if not (PATH_ROOT / path).exists():
                raise ValueError(f"Demo file path not found: {path}")
        return self

    def get_config_for_demo_file(self, path: Path) -> DemoFileConfig:
        path = safe_path(path)
        if path.is_absolute():
            if not path.is_relative_to((PATH_ROOT)):
                raise ValueError(f"Path not relative to PATH_ROOT: {path}")
            path_relative = path.relative_to(PATH_ROOT)
        else:
            path_relative = path
        if path_relative in self.per_file:
            return self.per_file[path_relative]
        for pattern, config in self.file_patterns.items():
            if (PATH_ROOT / path_relative) in PATH_ROOT.glob(pattern):
                return config
        raise ValueError(
            "Path does not match either a file pattern or specific file in the config file"
        )


def get_e2e_config() -> E2EConfig:
    with open(PATH_TEST_E2E / "config.json") as file:
        return E2EConfig.model_validate_json(file.read())
