# Type stub for the compiled extension module.
#
# `_hier_config_rust` is a `.so` built by maturin, so type checkers cannot
# introspect it. Without this stub every `from _hier_config_rust import ...`
# in the re-export shims resolves to `Unknown`, which under pyright's strict
# mode cascades into dozens of errors across `hier_config/` and makes the
# package's own source unverifiable.
#
# The authoritative, documented signatures live in the `hier_config/*.pyi`
# stubs beside the shims -- those are what mkdocstrings renders and what
# downstream users see. This file deliberately re-exports from them rather
# than restating them, so there is exactly one copy of each signature and the
# two can never drift.
#
# This stub is repo-local (see `mypy_path` / `stubPath` in pyproject.toml) and
# is not shipped: `_hier_config_rust` is underscore-prefixed precisely because
# callers are meant to reach these types through `hier_config`, which is fully
# typed via `py.typed`.

from ipaddress import IPv4Address, IPv4Interface

from hier_config.base import HConfigBase as HConfigBase
from hier_config.child import HConfigChild as HConfigChild
from hier_config.children import HConfigChildren as HConfigChildren
from hier_config.exceptions import DuplicateChildError as DuplicateChildError
from hier_config.exceptions import HierConfigError as HierConfigError
from hier_config.exceptions import InvalidConfigError as InvalidConfigError
from hier_config.formats import GnmiRemediation as GnmiRemediation
from hier_config.models import Platform as Platform
from hier_config.platforms.models import (
    InterfaceDot1qMode as InterfaceDot1qMode,
)
from hier_config.platforms.models import (
    InterfaceDuplex as InterfaceDuplex,
)
from hier_config.platforms.models import (
    NACHostMode as NACHostMode,
)
from hier_config.platforms.models import (
    StackMember as StackMember,
)
from hier_config.platforms.models import (
    Vlan as Vlan,
)
from hier_config.root import HConfig as HConfig
from hier_config.workflows import WorkflowRemediation as WorkflowRemediation

# Declared here rather than re-exported: this iterator is returned by
# `HConfigChildren.__iter__` but has no stub of its own under `hier_config/`.
class HConfigChildrenIter:
    def __iter__(self) -> HConfigChildrenIter: ...
    def __next__(self) -> HConfigChild: ...

def get_platform_rules_json(platform_str: str) -> str: ...
def driver_swap_negation(platform_str: str, text: str) -> str: ...
def convert_to_set_commands(config_raw: str) -> str: ...
def config_preprocessor(platform_str: str, config_text: str) -> str: ...

# Structured-format conversions. These are implemented entirely in Rust and have
# no `hier_config/*.pyi` counterpart to re-export from, so they are declared
# here; `hier_config/formats.py` is the documented Python-facing wrapper.
def formats_from_json(
    driver_obj: object, data: str, list_keys: list[str] | None = None
) -> HConfig: ...
def formats_to_json(config: HConfig, indent: int | None = 2) -> str: ...
def formats_from_xml(
    driver_obj: object, source: str, list_keys: list[str] | None = None
) -> HConfig: ...
def formats_to_xml(config: HConfig) -> str: ...
def formats_to_netconf_xml(
    remediation: HConfig,
    running: HConfig | None = None,
    list_keys: list[str] | None = None,
) -> str: ...
def formats_to_gnmi_json(
    remediation: HConfig,
    running: HConfig | None = None,
    list_keys: list[str] | None = None,
) -> GnmiRemediation: ...

# Config views. Implemented entirely in Rust; `hier_config.platforms.view_base`
# is the documented Python-facing facade that re-exports these under their
# historical names and adds the capability marker classes. Member names here are
# checked against the extension at lint time by `gen_stubs.py --check`.
class ConfigViewInterface:
    def __init__(self, config: HConfigChild) -> None: ...
    @property
    def bundle_id(self) -> str | None: ...
    @property
    def bundle_member_interfaces(self) -> list[str]: ...
    @property
    def bundle_name(self) -> str | None: ...
    @property
    def capabilities(self) -> frozenset[str]: ...
    @property
    def config(self) -> HConfigChild: ...
    @property
    def description(self) -> str: ...
    @property
    def dot1q_mode(self) -> InterfaceDot1qMode | None: ...
    @property
    def duplex(self) -> InterfaceDuplex | None: ...
    @property
    def enabled(self) -> bool: ...
    @property
    def has_nac(self) -> bool: ...
    @property
    def ipv4_interface(self) -> IPv4Interface | None: ...
    @property
    def ipv4_interfaces(self) -> list[IPv4Interface]: ...
    @property
    def is_bundle(self) -> bool: ...
    @property
    def is_loopback(self) -> bool: ...
    @property
    def is_physical(self) -> bool: ...
    @property
    def is_subinterface(self) -> bool: ...
    @property
    def is_svi(self) -> bool: ...
    @property
    def module_number(self) -> int | None: ...
    @property
    def nac_control_direction_in(self) -> bool: ...
    @property
    def nac_host_mode(self) -> NACHostMode | None: ...
    @property
    def nac_mab_first(self) -> bool: ...
    @property
    def nac_max_dot1x_clients(self) -> int | None: ...
    @property
    def nac_max_mab_clients(self) -> int | None: ...
    @property
    def name(self) -> str: ...
    @property
    def native_vlan(self) -> int | None: ...
    @property
    def number(self) -> str: ...
    @property
    def parent_name(self) -> str | None: ...
    @property
    def platform(self) -> Platform: ...
    @property
    def poe(self) -> bool: ...
    @property
    def port_number(self) -> int | None: ...
    @property
    def speed(self) -> tuple[int, ...] | None: ...
    @property
    def subinterface_number(self) -> int | None: ...
    @property
    def tagged_all(self) -> bool: ...
    @property
    def tagged_vlans(self) -> tuple[int, ...]: ...
    @property
    def vrf(self) -> str: ...

class HConfigView:
    def __init__(self, config: HConfig) -> None: ...
    @property
    def bundle_interface_views(self) -> list[ConfigViewInterface]: ...
    @property
    def config(self) -> HConfig: ...
    @staticmethod
    def dot1q_mode_from_vlans(
        untagged_vlan: int | None = None,
        tagged_vlans: tuple[int, ...] = (),
        *,
        tagged_all: bool = False,
    ) -> InterfaceDot1qMode | None: ...
    @property
    def hostname(self) -> str | None: ...
    @property
    def interface_names_mentioned(self) -> frozenset[str]: ...
    def interface_view_by_name(self, name: str) -> ConfigViewInterface | None: ...
    @property
    def interface_views(self) -> list[ConfigViewInterface]: ...
    @property
    def interfaces(self) -> list[HConfigChild]: ...
    @property
    def interfaces_names(self) -> list[str]: ...
    @property
    def ipv4_default_gw(self) -> IPv4Address | None: ...
    @property
    def location(self) -> str: ...
    @property
    def module_numbers(self) -> list[int]: ...
    @property
    def platform(self) -> Platform: ...
    @property
    def stack_members(self) -> list[StackMember]: ...
    @property
    def vlan_ids(self) -> frozenset[int]: ...
    @property
    def vlans(self) -> list[Vlan]: ...


__all__ = (
    "ConfigViewInterface",
    "DuplicateChildError",
    "GnmiRemediation",
    "HConfig",
    "HConfigBase",
    "HConfigChild",
    "HConfigChildren",
    "HConfigChildrenIter",
    "HConfigView",
    "HierConfigError",
    "InvalidConfigError",
    "WorkflowRemediation",
    "config_preprocessor",
    "convert_to_set_commands",
    "driver_swap_negation",
    "formats_from_json",
    "formats_from_xml",
    "formats_to_gnmi_json",
    "formats_to_json",
    "formats_to_netconf_xml",
    "formats_to_xml",
    "get_platform_rules_json",
)
