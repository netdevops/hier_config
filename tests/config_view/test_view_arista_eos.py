"""Tests for Arista EOS view.py ConfigViewInterfaceAristaEOS and HConfigViewAristaEOS classes."""

import pytest

from hier_config import Platform, get_hconfig, get_hconfig_view


def test_dot1q_mode_from_vlans_not_implemented() -> None:
    """Test dot1q_mode_from_vlans raises NotImplementedError (covers line 154)."""
    config = get_hconfig(Platform.ARISTA_EOS)
    view = get_hconfig_view(config)

    with pytest.raises(NotImplementedError):
        view.dot1q_mode_from_vlans(untagged_vlan=10)


def test_hostname() -> None:
    """Test hostname returns hostname (covers lines 158-160)."""
    config = get_hconfig(Platform.ARISTA_EOS)
    config.add_child("hostname ARISTA-LEAF-01")

    view = get_hconfig_view(config)
    assert view.hostname == "arista-leaf-01"


def test_hostname_none() -> None:
    """Test hostname returns None (covers line 160)."""
    config = get_hconfig(Platform.ARISTA_EOS)

    view = get_hconfig_view(config)
    assert view.hostname is None


def test_interface_names_mentioned_not_implemented() -> None:
    """Test interface_names_mentioned raises NotImplementedError (covers line 165)."""
    config = get_hconfig(Platform.ARISTA_EOS)
    config.add_child("interface Ethernet1")

    view = get_hconfig_view(config)

    with pytest.raises(NotImplementedError):
        _ = view.interface_names_mentioned


def test_interface_views() -> None:
    """Test interface_views yields interface views (covers lines 169-170)."""
    config = get_hconfig(Platform.ARISTA_EOS)
    config.add_child("interface Ethernet1")
    config.add_child("interface Ethernet2")
    config.add_child("interface Management1")

    view = get_hconfig_view(config)
    interface_views = list(view.interface_views)

    assert len(interface_views) == 3


def test_interfaces() -> None:
    """Test interfaces returns interface children (covers line 174)."""
    config = get_hconfig(Platform.ARISTA_EOS)
    config.add_child("interface Ethernet1")
    config.add_child("interface Ethernet2")

    view = get_hconfig_view(config)
    interfaces = list(view.interfaces)

    assert len(interfaces) == 2


def test_ipv4_default_gw_not_implemented() -> None:
    """Test ipv4_default_gw raises NotImplementedError (covers line 178)."""
    config = get_hconfig(Platform.ARISTA_EOS)

    view = get_hconfig_view(config)

    with pytest.raises(NotImplementedError):
        _ = view.ipv4_default_gw


def test_location_not_implemented() -> None:
    """Test location raises NotImplementedError (covers line 182)."""
    config = get_hconfig(Platform.ARISTA_EOS)

    view = get_hconfig_view(config)

    with pytest.raises(NotImplementedError):
        _ = view.location


def test_stack_members_not_implemented() -> None:
    """Test stack_members raises NotImplementedError (covers line 186)."""
    config = get_hconfig(Platform.ARISTA_EOS)

    view = get_hconfig_view(config)

    with pytest.raises(NotImplementedError):
        _ = list(view.stack_members)


def test_vlans_not_implemented() -> None:
    """Test vlans raises NotImplementedError (covers line 190)."""
    config = get_hconfig(Platform.ARISTA_EOS)

    view = get_hconfig_view(config)

    with pytest.raises(NotImplementedError):
        _ = list(view.vlans)
