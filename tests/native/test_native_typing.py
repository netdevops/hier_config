"""The packaged native module owns both runtime classes and their type contract."""

import ast
import importlib
import inspect
import pickle  # ruff: ignore[suspicious-pickle-import] # Trusted legacy class-reference fixture only.
from pathlib import Path

import pytest

import hier_config


@pytest.mark.parametrize(
    "name", ("HConfigBase", "HConfig", "HConfigChild", "HConfigChildren")
)
def test_native_tree_classes_have_runtime_documentation(name: str) -> None:
    native = importlib.import_module("_hier_config_rust")
    assert inspect.getdoc(getattr(native, name))


def test_packaged_native_module_and_public_api_share_types() -> None:
    native = importlib.import_module("hier_config._hier_config_rust")
    assert native.HConfig is hier_config.HConfig
    assert native.HConfigChild is hier_config.HConfigChild
    assert native.HConfig.__module__ == "hier_config._hier_config_rust"


def test_native_stub_declares_exported_classes_in_the_package() -> None:
    path = Path(hier_config.__file__).parent / "_hier_config_rust.pyi"
    declarations = ast.parse(path.read_text(encoding="utf-8"))
    classes = {
        node.name for node in declarations.body if isinstance(node, ast.ClassDef)
    }
    assert {
        "HConfigBase",
        "HConfig",
        "HConfigChild",
        "HConfigChildren",
        "WorkflowRemediation",
        "HConfigView",
        "ConfigViewInterface",
    } <= classes


def test_native_stub_does_not_fall_back_to_unknown_annotations() -> None:
    path = Path(hier_config.__file__).parent / "_hier_config_rust.pyi"
    declarations = ast.parse(path.read_text(encoding="utf-8"))
    unknown = {"Any", "Incomplete"}
    assert not [
        ast.unparse(node)
        for node in ast.walk(declarations)
        if (isinstance(node, ast.Name) and node.id in unknown)
        or (isinstance(node, ast.Attribute) and node.attr in unknown)
    ]


def test_native_stub_preserves_deepcopy_memo_and_index_overloads() -> None:
    path = Path(hier_config.__file__).parent / "_hier_config_rust.pyi"
    declarations = ast.parse(path.read_text(encoding="utf-8"))
    classes = {
        node.name: node for node in declarations.body if isinstance(node, ast.ClassDef)
    }
    deepcopy = next(
        node
        for node in classes["HConfigChild"].body
        if isinstance(node, ast.FunctionDef) and node.name == "__deepcopy__"
    )
    memo = next(
        arg
        for arg in deepcopy.args.posonlyargs + deepcopy.args.args
        if arg.arg == "memo"
    )
    assert memo.annotation is not None
    annotation = ast.unparse(memo.annotation).replace("builtins.", "")
    assert annotation == "dict[int, object]"
    assert deepcopy.returns is not None
    assert ast.unparse(deepcopy.returns).rsplit(".", 1)[-1] == "HConfigChild"
    overloads = [
        node
        for node in classes["HConfigChildren"].body
        if isinstance(node, ast.FunctionDef) and node.name == "__getitem__"
    ]
    assert len(overloads) >= 2
    assert all(node.returns is not None for node in overloads)


def test_native_stub_declares_base_classes_before_their_subclasses() -> None:
    # Astroid resolves a base only against names declared earlier in the file;
    # a subclass rendered above its base silently loses its inherited members
    # and Pylint stops reporting invalid attribute access on it.
    path = Path(hier_config.__file__).parent / "_hier_config_rust.pyi"
    declarations = ast.parse(path.read_text(encoding="utf-8"))
    classes = [node for node in declarations.body if isinstance(node, ast.ClassDef)]
    declared: set[str] = set()
    local = {node.name for node in classes}
    for node in classes:
        bases = {ast.unparse(base) for base in node.bases} & local
        assert bases <= declared, f"{node.name} precedes {sorted(bases - declared)}"
        declared.add(node.name)


def test_historical_native_module_pickle_resolves_public_type() -> None:
    # Protocol 0 GLOBAL records stored the original extension module name.
    legacy = b"c_hier_config_rust\nHConfig\n."
    restored = pickle.loads(legacy)  # ruff: ignore[suspicious-pickle-usage] # Trusted literal, not external data.
    assert restored is hier_config.HConfig
