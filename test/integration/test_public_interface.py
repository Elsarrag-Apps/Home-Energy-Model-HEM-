"""
The hem_core module exposes several classes and functions intended to be called publicly.

The interface to these should remain compatible within major versions.

If you have only added parameters, or added additional type options to existing parameters,
then you may update the expected public interface configuration for these tests by running:

    pytest test/integration/test_hem_core_public_interface.py -n0 --update-expected-public-interface

"""

import inspect
import re
import types
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Literal

import pydantic
import pytest
from pydantic import BaseModel

import hem_core

__PUBLIC_MODULE_NAMES = [
    "enums",
    "external_conditions",
    "input",
    "output",
    "read_weather_file",
    "schedule",
    "simulation_time",
    "units",
    "water_heat_demand_utilities",
]

__PUBLIC_CLASS_NAMES = [
    "BuildingElement",
    "ColdWaterSource",
    "DHWDemand",
    "EnergySupply",
    "EnergySupplyConnection",
    "HeatFlowDirection",
    "Project",
    "WWHRSInstantaneous",
    "WindowTreatmentControl",
]

__PUBLIC_FUNCTION_NAMES = [
    "load_weather_data_from_file",
    "run_project",
    "write_project_outputs",
]
T_SIGNATURE = dict[str, list[str] | str]


class EnumInterface(pydantic.BaseModel):
    type: Literal["Enum"] = "Enum"
    members: dict[str, str | int]


class ClassPublicInterface(pydantic.BaseModel):
    init: T_SIGNATURE
    methods: dict[str, T_SIGNATURE]


T_CLASS_INTERFACES = ClassPublicInterface | EnumInterface | None


class ModulePublicInterface(pydantic.BaseModel):
    classes: dict[str, T_CLASS_INTERFACES] = {}
    functions: dict[str, T_SIGNATURE] = {}


class ExpectedInterfaces(pydantic.BaseModel):
    modules: dict[str, ModulePublicInterface] = {}
    classes: dict[str, T_CLASS_INTERFACES] = {}
    functions: dict[str, T_SIGNATURE] = {}


@pytest.fixture(scope="session")
def path_public_interface(path_expected: Path) -> Path:
    return path_expected / "public_interface.json"


@pytest.fixture(autouse=True, scope="session")
def __update_expected_interface(request: pytest.FixtureRequest, path_public_interface: Path):
    """
    An auto-use fixture (which runs before the tests) to update the saved JSON expectations for the public interface.
    """
    if not request.config.getoption(name="--update-expected-public-interface", default=False):
        return
    data = ExpectedInterfaces()
    for module_name in __PUBLIC_MODULE_NAMES:
        data.modules[module_name] = _get_module_interface(getattr(hem_core, module_name))

    for class_name in __PUBLIC_CLASS_NAMES:
        data.classes[class_name] = _get_class_interface(getattr(hem_core, class_name))
    for function_name in __PUBLIC_FUNCTION_NAMES:
        data.functions[function_name] = _signature_list(getattr(hem_core, function_name))
    with open(path_public_interface, mode="w+", encoding="utf-8") as file:
        file.write(data.model_dump_json(indent=2))


@pytest.fixture(scope="session")
def expected_interfaces(path_public_interface: Path) -> ExpectedInterfaces:
    with open(path_public_interface, mode="r", encoding="utf-8") as file:
        return ExpectedInterfaces.model_validate_json(file.read())


@pytest.fixture(params=__PUBLIC_MODULE_NAMES)
def module_name(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture(params=__PUBLIC_CLASS_NAMES)
def class_name(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture(params=__PUBLIC_FUNCTION_NAMES)
def function_name(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture
def expected_module_interface(
    module_name: str, expected_interfaces: ExpectedInterfaces
) -> ModulePublicInterface:
    return expected_interfaces.modules[module_name]


@pytest.fixture()
def expected_class_interface(
    class_name: str, expected_interfaces: ExpectedInterfaces
) -> T_CLASS_INTERFACES:
    return expected_interfaces.classes[class_name]


@pytest.fixture()
def expected_function_signature(
    function_name: str, expected_interfaces: ExpectedInterfaces
) -> T_SIGNATURE:
    return expected_interfaces.functions[function_name]


def test_public_modules(module_name: str, expected_module_interface: ModulePublicInterface):
    assert hasattr(hem_core, module_name)
    module = getattr(hem_core, module_name)
    assert inspect.ismodule(module)
    assert _get_module_interface(module) == expected_module_interface


def test_public_classes(class_name: str, expected_class_interface: T_CLASS_INTERFACES):
    assert hasattr(hem_core, class_name)
    cls = getattr(hem_core, class_name)
    assert inspect.isclass(cls)
    class_interface = _get_class_interface(cls)
    if expected_class_interface is None:
        assert class_interface is None
    else:
        assert class_interface is not None
        assert class_interface == expected_class_interface


def test_public_functions(function_name: str, expected_function_signature: inspect.Signature):
    assert function_name[0] != "_", "Only public functions should be present in the hem_core module"
    assert hasattr(hem_core, function_name)
    func = getattr(hem_core, function_name)
    assert inspect.isfunction(func)
    assert _signature_list(func) == expected_function_signature


def test_unexpected_classes():
    """Test that there are no extra classes in the hem_core module no in the expected list."""
    classes = {name for name, _ in inspect.getmembers(hem_core, predicate=inspect.isclass)}
    assert classes == set(__PUBLIC_CLASS_NAMES)


def test_unexpected_functions():
    """Test that there are no extra functions in the hem_core module not in the expected list."""
    functions = {name for name, _ in inspect.getmembers(hem_core, predicate=inspect.isfunction)}
    assert functions == set(__PUBLIC_FUNCTION_NAMES)


def _get_class_interface(
    target_class: type,
) -> T_CLASS_INTERFACES:
    if issubclass(target_class, Enum):
        return EnumInterface(
            members=dict(target_class.__members__.items()),  # type: ignore[ArgumentType]
            # Enum.__members__ is typed as dict[str, Enum] but maps to str or int literals.
        )
    try:
        class_module = inspect.getmodule(target_class)
        return ClassPublicInterface(
            init=_signature_list(target_class, True),
            methods={
                function_name: _signature_list(function)
                for function_name, function in inspect.getmembers(
                    target_class, predicate=inspect.isfunction
                )
                if function_name[0] != "_" and inspect.getmodule(function) == class_module
            },
        )
    except ValueError as ex:
        if "no signature found for builtin type" in str(ex):
            return None
        raise


def _signature_string(obj: Callable[..., Any]) -> str:
    signature = inspect.signature(obj)
    signature_str = str(signature)
    return _clean_up_signature(signature_str)


def _clean_up_signature(value: str) -> str:
    # Objects and functions get stringified with unique identifiers.
    # Strip that out.
    substitutions = {
        r"\<([\w.]+) object at 0x\w+\>": r"<object \1>",
        r"\<function ([\w.]+) at 0x\w+\>": r"<function \1>",
    }
    for pattern, substitute in substitutions.items():
        value = re.sub(pattern, substitute, value)
    return value


def _signature_list(obj: Callable[..., Any], is_constructor: bool = False) -> T_SIGNATURE:
    data: T_SIGNATURE = {}
    signature = inspect.signature(obj)
    is_pydantic_model = isinstance(obj, type) and issubclass(obj, BaseModel)

    data["parameters"] = [
        _clean_up_signature(str(param)) for param in signature.parameters.values()
    ]
    if is_pydantic_model and is_constructor:
        data["parameters"].insert(0, "*")
    ret = signature.return_annotation
    if ret is inspect.Signature.empty:
        ret_str = "None"
    elif isinstance(ret, type):
        if ret.__module__ == "builtins":
            ret_str = ret.__name__
        else:
            ret_str = f"{ret.__module__}.{ret.__name__}"
    else:
        ret_str = str(ret)
    data["return"] = ret_str

    return data


def _get_module_interface(module: types.ModuleType) -> ModulePublicInterface:
    return ModulePublicInterface(
        classes={
            class_name: _get_class_interface(getattr(module, class_name))
            for class_name, class_obj in inspect.getmembers(module, predicate=inspect.isclass)
            if class_name[0] != "_" and inspect.getmodule(class_obj) == module
        },
        functions={
            function_name: _signature_list(getattr(module, function_name))
            for function_name, function in inspect.getmembers(module, predicate=inspect.isfunction)
            if function_name[0] != "_" and inspect.getmodule(function) == module
        },
    )
