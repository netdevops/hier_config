"""Tests for Aruba AOS-CX config views."""

from ipaddress import IPv4Address, IPv4Interface

import pytest

from hier_config import HConfig, Platform, get_hconfig_view
from hier_config.platforms.aruba_aoscx.view import ConfigViewInterfaceArubaAOSCX
from hier_config.platforms.models import InterfaceDot1qMode, InterfaceDuplex, Vlan
from hier_config.platforms.view_base import HConfigViewBase


def _view_from_config(config_text: str = "") -> HConfigViewBase:
    return get_hconfig_view(HConfig.from_text(Platform.ARUBA_AOSCX, config_text))


def _interface_view(
    view: HConfigViewBase,
    name: str,
) -> ConfigViewInterfaceArubaAOSCX:
    interface_view = view.interface_view_by_name(name)
    assert isinstance(interface_view, ConfigViewInterfaceArubaAOSCX)
    return interface_view


def test_hostname() -> None:
    view = _view_from_config("hostname CX-LEAF-01\n")

    assert view.hostname == "cx-leaf-01"


def test_interface_properties() -> None:
    view = _view_from_config(
        """
interface 1/1/1
    description Uplink to Core
    no shutdown
    vlan trunk native 10
    vlan trunk allowed 20,21,26
    vrf attach CUSTOMER
"""
    )

    interface_view = _interface_view(view, "1/1/1")
    assert interface_view.description == "Uplink to Core"
    assert interface_view.enabled is True
    assert interface_view.native_vlan == 10
    assert interface_view.tagged_vlans == (20, 21, 26)
    assert interface_view.vrf == "CUSTOMER"
    assert interface_view.dot1q_mode == InterfaceDot1qMode.TAGGED


def test_access_interface_properties() -> None:
    view = _view_from_config(
        """
interface 1/1/2
    shutdown
    vlan access 25
"""
    )

    interface_view = _interface_view(view, "1/1/2")
    assert interface_view.enabled is False
    assert interface_view.native_vlan == 25
    assert interface_view.dot1q_mode == InterfaceDot1qMode.ACCESS


def test_interface_enabled_defaults_to_down() -> None:
    # AOS-CX ports are admin-down by default: with neither `shutdown` nor
    # `no shutdown` present, `enabled` must be False, not True.
    view = _view_from_config(
        """
interface 1/1/3
    description unconfigured
"""
    )

    interface_view = _interface_view(view, "1/1/3")
    assert interface_view.enabled is False


def test_view_tolerates_malformed_trunk_vlan_spec() -> None:
    # A malformed spec the driver leaves collapsed (e.g. 10-12-13) must not
    # surface a bare ValueError from the view; the parseable VLANs still come
    # through and the bad one is skipped.
    view = _view_from_config(
        """
interface 1/1/1
    vlan trunk allowed 10
    vlan trunk allowed 10-12-13
"""
    )

    interface_view = _interface_view(view, "1/1/1")
    assert interface_view.tagged_vlans == (10,)
    assert view.vlan_ids == frozenset({10})


def test_ip_properties() -> None:
    view = _view_from_config(
        """
interface vlan 25
    ip address 10.25.0.1/24
ip route 0.0.0.0/0 10.25.0.254
"""
    )

    interface_view = _interface_view(view, "vlan 25")
    assert interface_view.is_svi is True
    assert list(interface_view.ipv4_interfaces) == [IPv4Interface("10.25.0.1/24")]
    assert view.ipv4_default_gw == IPv4Address("10.25.0.254")


def test_vlan_properties() -> None:
    view = _view_from_config(
        """
vlan 20
    name SERVERS
interface 1/1/1
    vlan trunk allowed 25
interface 1/1/2
    vlan access 30
"""
    )

    assert list(view.vlans) == [
        Vlan(id=20, name="SERVERS"),
        Vlan(id=25, name=None),
        Vlan(id=30, name=None),
    ]


def test_bundle_properties() -> None:
    view = _view_from_config(
        """
interface lag 48
    description UPLINK LAG
interface 1/1/47
    lag 48
interface 1/1/48
    lag 48
"""
    )

    bundle_view = _interface_view(view, "lag 48")
    member_view = _interface_view(view, "1/1/47")
    assert bundle_view.is_bundle is True
    assert bundle_view.bundle_id == "48"
    assert tuple(bundle_view.bundle_member_interfaces) == ("1/1/47", "1/1/48")
    assert member_view.bundle_name == "lag 48"
    assert member_view.parent_name == "lag 48"


def test_bundle_properties_multi_chassis() -> None:
    # Multi-word LAG names ("lag 1 multi-chassis") must still resolve the numeric
    # bundle id, not the trailing "multi-chassis" word.
    view = _view_from_config(
        """
interface lag 1 multi-chassis
    description Test-Server
interface 1/1/1
    lag 1
"""
    )

    bundle_view = _interface_view(view, "lag 1 multi-chassis")
    member_view = _interface_view(view, "1/1/1")
    assert bundle_view.is_bundle is True
    assert bundle_view.bundle_id == "1"
    assert bundle_view.bundle_name == "lag 1"
    assert tuple(bundle_view.bundle_member_interfaces) == ("1/1/1",)
    assert member_view.bundle_id == "1"
    assert member_view.parent_name == "lag 1"


def test_duplex_speed_and_poe_defaults() -> None:
    view = _view_from_config("interface 1/1/1\n")

    interface_view = _interface_view(view, "1/1/1")
    assert interface_view.duplex == InterfaceDuplex.AUTO
    assert interface_view.speed is None
    assert interface_view.poe is True


def test_unsupported_nac_client_limits() -> None:
    view = _view_from_config("interface 1/1/1\n")

    interface_view = _interface_view(view, "1/1/1")
    with pytest.raises(NotImplementedError):
        _ = interface_view.nac_max_dot1x_clients
    with pytest.raises(NotImplementedError):
        _ = interface_view.nac_max_mab_clients
