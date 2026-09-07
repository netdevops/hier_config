"""Tests for the thin Python facades that wrap the native Rust config views.

The parsing semantics live in Rust and are covered by the per-platform test
modules. These tests exercise the Python-only glue: the ``_bundle_prefix``
class constants, the lazy ``_get_native`` resolution path used when a facade is
constructed directly from an ``HConfigChild``, and the defensive fallbacks that
keep the facades usable on objects that never went through the native view.
"""

import pytest

from hier_config import Platform, get_hconfig, get_hconfig_view
from hier_config.platforms.arista_eos.view import ConfigViewInterfaceAristaEOS
from hier_config.platforms.aruba_aoscx.view import ConfigViewInterfaceArubaAOSCX
from hier_config.platforms.cisco_ios.view import (
    ConfigViewInterfaceCiscoIOS,
    HConfigViewCiscoIOS,
)
from hier_config.platforms.cisco_nxos.view import ConfigViewInterfaceCiscoNXOS
from hier_config.platforms.cisco_xr.view import ConfigViewInterfaceCiscoIOSXR
from hier_config.platforms.hp_procurve.view import ConfigViewInterfaceHPProcurve
from hier_config.platforms.view_base import (
    ConfigViewInterfaceBase,
    _native_interface_view_attr,  # pyright: ignore[reportPrivateUsage]
)

_BUNDLE_PREFIXES: tuple[tuple[type[ConfigViewInterfaceBase], str], ...] = (
    (ConfigViewInterfaceArubaAOSCX, "lag "),
    (ConfigViewInterfaceCiscoIOS, "Port-channel"),
    (ConfigViewInterfaceCiscoNXOS, "port-channel"),
    (ConfigViewInterfaceCiscoIOSXR, "Bundle-Ether"),
    (ConfigViewInterfaceHPProcurve, "trk"),
)


@pytest.mark.parametrize(("view_cls", "expected"), _BUNDLE_PREFIXES)
def test_bundle_prefix_per_platform(
    view_cls: type[ConfigViewInterfaceBase], expected: str
) -> None:
    """Each platform facade exposes its own link-aggregation prefix."""
    config = get_hconfig(Platform.GENERIC)
    child = config.add_child("interface Ethernet1")
    view = view_cls(child)
    assert view._bundle_prefix == expected  # pyright: ignore[reportPrivateUsage] # ruff: ignore[private-member-access]


def test_bundle_prefix_arista_eos_raises() -> None:
    """Arista EOS has no single bundle prefix, so the property refuses to guess."""
    config = get_hconfig(Platform.GENERIC)
    child = config.add_child("interface Ethernet1")
    view = ConfigViewInterfaceAristaEOS(child)
    with pytest.raises(NotImplementedError):
        _ = view._bundle_prefix  # pyright: ignore[reportPrivateUsage] # ruff: ignore[private-member-access]


def test_get_native_resolves_lazily_from_child() -> None:
    """A facade built straight from a child resolves its native view on demand."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_children_deep(
        ("interface GigabitEthernet0/1", "description uplink"),
    )
    child = config.get_child(equals="interface GigabitEthernet0/1")
    assert child is not None

    view = ConfigViewInterfaceCiscoIOS(child)
    assert view.name == "GigabitEthernet0/1"
    # The native view is cached, so a second property read reuses it.
    assert view.description == "uplink"


def test_get_native_raises_for_unresolvable_child() -> None:
    """A node the native tree view does not consider an interface is an error."""
    config = get_hconfig(Platform.CISCO_IOS)
    child = config.add_child("hostname router1")

    view = ConfigViewInterfaceCiscoIOS(child)
    with pytest.raises(ValueError, match="Could not create native interface view"):
        _ = view.name


def test_native_interface_view_attr_returns_none_when_absent() -> None:
    """The cached-native-view lookup tolerates children without the attribute."""
    config = get_hconfig(Platform.CISCO_IOS)
    child = config.add_child("hostname router1")
    assert _native_interface_view_attr(child) is None


def test_dot1q_mode_from_vlans_without_native_returns_none() -> None:
    """The tree facade degrades gracefully if ``_native`` was never assigned."""
    view = HConfigViewCiscoIOS.__new__(HConfigViewCiscoIOS)
    assert view.dot1q_mode_from_vlans(untagged_vlan=10) is None


def test_interface_view_config_is_interned_child() -> None:
    """``interface_view.config`` returns the same handle as a tree traversal.

    Downstream code identifies which interface a child belongs to by comparing
    ``interface_view.config is child`` against children obtained from a separate
    traversal. That only works if the view participates in the handle intern
    cache rather than minting a fresh wrapper for the same node.
    """
    config = get_hconfig(
        Platform.CISCO_IOS,
        "interface Ethernet1\n  description one\ninterface Ethernet2\n",
    )
    view = get_hconfig_view(config)
    traversed = tuple(config.get_children(startswith="interface "))

    for interface_view, child in zip(view.interface_views, traversed, strict=True):
        assert interface_view.config is child


def test_interface_view_by_name_config_is_interned_child() -> None:
    """The single-interface lookup path interns its child handle too."""
    config = get_hconfig(Platform.CISCO_IOS, "interface Ethernet1\n  description one\n")
    view = get_hconfig_view(config)
    child = config.children.get("interface Ethernet1")

    interface_view = view.interface_view_by_name("Ethernet1")
    assert interface_view is not None
    assert interface_view.config is child


def test_view_resolves_from_a_child_root() -> None:
    """``child.root`` round-trips back to the platform-specific view class."""
    config = get_hconfig(
        Platform.CISCO_IOS,
        "interface Ethernet1\n  description one\ninterface Ethernet2\n",
    )
    child = next(iter(config.get_children(startswith="interface ")))

    assert isinstance(get_hconfig_view(child.root), HConfigViewCiscoIOS)
    assert len(list(get_hconfig_view(config).interface_views)) == 2
