"""Back-compatibility guarantees for the public import surface.

The tree types moved into the Rust extension in v3.7, leaving
``hier_config.base``/``child``/``children``/``root`` as thin re-export shims.
Nothing inside the package imports some of those modules any more, so without
these tests a shim could be deleted or renamed without a single failure --
silently breaking downstream code that imports from the documented path.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

import hier_config
from hier_config.exceptions import DuplicateChildError, HierConfigError

_hier_config_rust = importlib.import_module("_hier_config_rust")

SHIM_MODULES = (
    ("hier_config.base", "HConfigBase"),
    ("hier_config.child", "HConfigChild"),
    ("hier_config.children", "HConfigChildren"),
    ("hier_config.root", "HConfig"),
)

# Every ``from <module> import <name>`` an external consumer is documented to
# be able to write. Sampled from a real downstream integration so that moving
# a symbol between modules fails here rather than in someone else's build.
CONSUMER_IMPORTS = (
    ("hier_config", "HConfig"),
    ("hier_config", "HConfigChild"),
    ("hier_config", "Platform"),
    ("hier_config", "get_hconfig"),
    ("hier_config", "get_hconfig_fast_load"),
    ("hier_config", "get_hconfig_view"),
    ("hier_config.constructors", "get_hconfig_fast_generic_load"),
    ("hier_config.constructors", "get_hconfig_from_dump"),
    ("hier_config.models", "Dump"),
    ("hier_config.models", "IdempotentCommandsRule"),
    ("hier_config.models", "MatchRule"),
    ("hier_config.models", "NegationDefaultWithRule"),
    ("hier_config.models", "OrderingRule"),
    ("hier_config.platforms.arista_eos.driver", "HConfigDriverAristaEOS"),
    ("hier_config.platforms.cisco_ios.driver", "HConfigDriverCiscoIOS"),
    ("hier_config.platforms.cisco_nxos.driver", "HConfigDriverCiscoNXOS"),
    ("hier_config.platforms.cisco_xr.driver", "HConfigDriverCiscoIOSXR"),
    ("hier_config.platforms.driver_base", "HConfigDriverBase"),
    ("hier_config.platforms.functions", "expand_range"),
    ("hier_config.platforms.generic.driver", "HConfigDriverGeneric"),
    ("hier_config.platforms.hp_procurve.driver", "HConfigDriverHPProcurve"),
    ("hier_config.platforms.juniper_junos.driver", "HConfigDriverJuniperJUNOS"),
    ("hier_config.platforms.models", "InterfaceDot1qMode"),
    ("hier_config.platforms.models", "InterfaceDuplex"),
    ("hier_config.platforms.models", "NACHostMode"),
    ("hier_config.platforms.models", "StackMember"),
    ("hier_config.platforms.view_base", "ConfigViewInterfaceBase"),
    ("hier_config.platforms.view_base", "HConfigViewBase"),
)


@pytest.mark.parametrize(("module_name", "attribute"), SHIM_MODULES)
def test_shim_module_exports_public_name(module_name: str, attribute: str) -> None:
    """Each shim module still exposes its documented public name."""
    module = importlib.import_module(module_name)

    assert hasattr(module, attribute)
    assert attribute in module.__all__


@pytest.mark.parametrize(("module_name", "attribute"), SHIM_MODULES)
def test_shim_module_reexports_native_type(module_name: str, attribute: str) -> None:
    """The re-exported object is the native type, not a divergent Python copy."""
    module = importlib.import_module(module_name)
    exported = getattr(module, attribute)
    native = getattr(_hier_config_rust, attribute)

    # ``HConfig`` is a thin subclass of the native type; the rest are aliases.
    assert exported is native or issubclass(exported, native)


def test_top_level_package_exports_are_importable() -> None:
    """Everything advertised in ``hier_config.__all__`` actually resolves."""
    for name in hier_config.__all__:
        assert hasattr(hier_config, name), name


@pytest.mark.parametrize(("module_name", "attribute"), CONSUMER_IMPORTS)
def test_documented_consumer_import_path_resolves(
    module_name: str, attribute: str
) -> None:
    """Each documented import path still yields a usable object."""
    module = importlib.import_module(module_name)

    assert getattr(module, attribute, None) is not None, (
        f"{module_name}.{attribute} no longer resolves"
    )


def test_native_classes_report_their_real_module() -> None:
    """``__module__`` must name the extension, not ``builtins``.

    ``pickle`` resolves a class by importing ``__module__`` and looking up
    ``__qualname__``; a class claiming to live in ``builtins`` cannot be
    pickled, and every introspection tool mislabels it.
    """
    for name in ("HConfig", "HConfigBase", "HConfigChild", "HConfigChildren"):
        cls = getattr(_hier_config_rust, name)
        assert cls.__module__ == "_hier_config_rust", name


def test_children_is_a_discoverable_property() -> None:
    """``children`` must be a real descriptor, not a ``__getattr__`` fallback.

    A dynamic fallback is invisible to ``dir()``, IDEs, and type checkers even
    though ``.children`` is the most-used attribute on the tree.
    """
    assert "children" in vars(_hier_config_rust.HConfigBase)
    assert "children" in dir(_hier_config_rust.HConfigChild)


def test_duplicate_child_error_derives_from_the_public_base() -> None:
    """``HierConfigError`` is exported as a base class, so it must behave as one."""
    assert issubclass(DuplicateChildError, HierConfigError)
    assert issubclass(HierConfigError, Exception)


def test_type_stubs_ship_alongside_the_shims() -> None:
    """The ``.pyi`` files are the only typed view of the compiled classes.

    Without them ``py.typed`` is a false promise: mypy sees every tree type as
    ``Any``, and mkdocstrings cannot resolve the re-export aliases at all.
    """
    package = Path(hier_config.__file__).parent
    for module in ("base", "child", "children", "root", "exceptions"):
        assert (package / f"{module}.pyi").is_file(), module


def test_native_extension_stub_packaged_for_maturin() -> None:
    """The root `_hier_config_rust.pyi` exists and matches `stubs/` for maturin wheel packaging."""
    repo_root = Path(__file__).resolve().parents[2]
    root_stub = repo_root / "_hier_config_rust.pyi"
    native_stub = repo_root / "stubs" / "_hier_config_rust.pyi"
    assert root_stub.is_file(), (
        "_hier_config_rust.pyi must exist at repo root for maturin wheel packaging"
    )
    assert root_stub.read_text() == native_stub.read_text(), (
        "_hier_config_rust.pyi at repo root must match stubs/_hier_config_rust.pyi"
    )
