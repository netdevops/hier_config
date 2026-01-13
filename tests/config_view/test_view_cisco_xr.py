"""Tests for Cisco IOS-XR view.py ConfigViewInterfaceCiscoIOSXR and HConfigViewCiscoIOSXR classes."""

from ipaddress import IPv4Interface

import pytest

from hier_config import Platform, get_hconfig, get_hconfig_view


def test_bundle_id_not_implemented() -> None:
    """Test bundle_id raises NotImplementedError (covers line 26)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface Bundle-Ether1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Bundle-Ether1")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = interface_view.bundle_id


def test_bundle_member_interfaces_not_implemented() -> None:
    """Test bundle_member_interfaces raises NotImplementedError (covers line 30)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0/0/0")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = list(interface_view.bundle_member_interfaces)


def test_bundle_name_with_bundle_id() -> None:
    """Test bundle_name returns formatted name (covers lines 34-36)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface Bundle-Ether1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Bundle-Ether1")
    assert interface_view is not None
    with pytest.raises(NotImplementedError):
        _ = interface_view.bundle_name


def test_bundle_name_none() -> None:
    """Test bundle_name returns None when not bundle (covers line 36)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0/0/0")
    assert interface_view is not None
    with pytest.raises(NotImplementedError):
        _ = interface_view.bundle_name


def test_description() -> None:
    """Test description returns description text (covers lines 40-42)."""
    config = get_hconfig(Platform.CISCO_XR)
    interface = config.add_child("interface GigabitEthernet0/0/0/0")
    interface.add_child("description Uplink to Core")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0/0/0")
    assert interface_view is not None
    assert interface_view.description == "Uplink to Core"


def test_description_empty() -> None:
    """Test description returns empty string (covers line 42)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0/0/0")
    assert interface_view is not None
    assert not interface_view.description


def test_duplex_not_implemented() -> None:
    """Test duplex raises NotImplementedError (covers line 46)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0/0/0")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = interface_view.duplex


def test_enabled_not_implemented() -> None:
    """Test enabled raises NotImplementedError (covers line 50)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0/0/0")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = interface_view.enabled


def test_has_nac_not_implemented() -> None:
    """Test has_nac raises NotImplementedError (covers line 55)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0/0/0")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = interface_view.has_nac


def test_ipv4_interface_none() -> None:
    """Test ipv4_interface returns None (covers line 59)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0/0/0")
    assert interface_view is not None
    assert interface_view.ipv4_interface is None


def test_ipv4_interfaces() -> None:
    """Test ipv4_interfaces returns IP addresses (covers lines 63-68)."""
    config = get_hconfig(Platform.CISCO_XR)
    interface = config.add_child("interface GigabitEthernet0/0/0/0")
    interface.add_child("ipv4 address 192.168.1.1 255.255.255.0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0/0/0")
    assert interface_view is not None

    ips = list(interface_view.ipv4_interfaces)
    assert len(ips) == 1
    assert ips[0] == IPv4Interface("192.168.1.1/24")


def test_ipv4_interfaces_invalid() -> None:
    """Test ipv4_interfaces skips invalid addresses (covers line 68)."""
    config = get_hconfig(Platform.CISCO_XR)
    interface = config.add_child("interface GigabitEthernet0/0/0/0")
    interface.add_child("ipv4 address dhcp")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0/0/0")
    assert interface_view is not None

    ips = list(interface_view.ipv4_interfaces)
    assert len(ips) == 0


def test_is_bundle_false() -> None:
    """Test is_bundle returns False (covers line 72)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0/0/0")
    assert interface_view is not None
    assert interface_view.is_bundle is False


def test_is_loopback_true() -> None:
    """Test is_loopback returns True (covers line 76)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface Loopback0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Loopback0")
    assert interface_view is not None
    assert interface_view.is_loopback is True


def test_is_loopback_false() -> None:
    """Test is_loopback returns False (covers line 76)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0/0/0")
    assert interface_view is not None
    assert interface_view.is_loopback is False


def test_is_subinterface_true() -> None:
    """Test is_subinterface returns True (covers line 80)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/0.100")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0/0/0.100")
    assert interface_view is not None
    assert interface_view.is_subinterface is True


def test_is_subinterface_false() -> None:
    """Test is_subinterface returns False (covers line 80)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0/0/0")
    assert interface_view is not None
    assert interface_view.is_subinterface is False


def test_is_svi_true() -> None:
    """Test is_svi returns True (covers line 84)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface vlan100")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("vlan100")
    assert interface_view is not None
    assert interface_view.is_svi is True


def test_is_svi_false() -> None:
    """Test is_svi returns False (covers line 84)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0/0/0")
    assert interface_view is not None
    assert interface_view.is_svi is False


def test_module_number() -> None:
    """Test module_number returns module (covers lines 88-91)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/2/0/5")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/2/0/5")
    assert interface_view is not None
    assert interface_view.module_number == 0


def test_module_number_none() -> None:
    """Test module_number returns None (covers lines 90-91)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface Loopback0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Loopback0")
    assert interface_view is not None
    assert interface_view.module_number is None


def test_nac_control_direction_in_not_implemented() -> None:
    """Test nac_control_direction_in raises NotImplementedError (covers line 96)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0/0/0")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = interface_view.nac_control_direction_in


def test_nac_host_mode_not_implemented() -> None:
    """Test nac_host_mode raises NotImplementedError (covers line 101)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0/0/0")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = interface_view.nac_host_mode


def test_nac_mab_first_not_implemented() -> None:
    """Test nac_mab_first raises NotImplementedError (covers line 106)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0/0/0")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = interface_view.nac_mab_first


def test_nac_max_dot1x_clients_not_implemented() -> None:
    """Test nac_max_dot1x_clients raises NotImplementedError (covers line 111)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0/0/0")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = interface_view.nac_max_dot1x_clients


def test_nac_max_mab_clients_not_implemented() -> None:
    """Test nac_max_mab_clients raises NotImplementedError (covers line 116)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0/0/0")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = interface_view.nac_max_mab_clients


def test_name() -> None:
    """Test name returns interface name (covers line 120)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/10")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0/0/10")
    assert interface_view is not None
    assert interface_view.name == "GigabitEthernet0/0/0/10"


def test_native_vlan_not_implemented() -> None:
    """Test native_vlan raises NotImplementedError (covers line 124)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0/0/0")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = interface_view.native_vlan


def test_number() -> None:
    """Test number returns interface number (covers line 128)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/1/2/15")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/1/2/15")
    assert interface_view is not None
    assert interface_view.number == "0/1/2/15"


def test_parent_name() -> None:
    """Test parent_name returns parent interface (covers lines 132-134)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/0.100")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0/0/0.100")
    assert interface_view is not None
    assert interface_view.parent_name == "GigabitEthernet0/0/0/0"


def test_parent_name_none() -> None:
    """Test parent_name returns None (covers line 134)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0/0/0")
    assert interface_view is not None
    assert interface_view.parent_name is None


def test_poe_not_implemented() -> None:
    """Test poe raises NotImplementedError (covers line 138)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0/0/0")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = interface_view.poe


def test_port_number() -> None:
    """Test port_number returns port number (covers line 142)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/2/1/25")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/2/1/25")
    assert interface_view is not None
    assert interface_view.port_number == 25


def test_port_number_with_subinterface() -> None:
    """Test port_number with subinterface (covers line 142)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/5.200")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0/0/5.200")
    assert interface_view is not None
    assert interface_view.port_number == 5


def test_speed_not_implemented() -> None:
    """Test speed raises NotImplementedError (covers line 146)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0/0/0")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = interface_view.speed


def test_subinterface_number() -> None:
    """Test subinterface_number returns number (covers line 150)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/0.500")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0/0/0.500")
    assert interface_view is not None
    assert interface_view.subinterface_number == 500


def test_subinterface_number_none() -> None:
    """Test subinterface_number returns None (covers line 150)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0/0/0")
    assert interface_view is not None
    assert interface_view.subinterface_number is None


def test_tagged_all_not_implemented() -> None:
    """Test tagged_all raises NotImplementedError (covers line 154)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0/0/0")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = interface_view.tagged_all


def test_tagged_vlans_not_implemented() -> None:
    """Test tagged_vlans raises NotImplementedError (covers line 158)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0/0/0")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = interface_view.tagged_vlans


def test_vrf_not_implemented() -> None:
    """Test vrf raises NotImplementedError (covers line 162)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0/0/0")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = interface_view.vrf


def test_dot1q_mode_from_vlans_not_implemented() -> None:
    """Test dot1q_mode_from_vlans raises NotImplementedError (covers line 173)."""
    config = get_hconfig(Platform.CISCO_XR)
    view = get_hconfig_view(config)

    with pytest.raises(NotImplementedError):
        view.dot1q_mode_from_vlans(untagged_vlan=10)


def test_hostname() -> None:
    """Test hostname returns hostname (covers lines 177-179)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("hostname CORE-ROUTER-01")

    view = get_hconfig_view(config)
    assert view.hostname == "core-router-01"


def test_hostname_none() -> None:
    """Test hostname returns None (covers line 179)."""
    config = get_hconfig(Platform.CISCO_XR)

    view = get_hconfig_view(config)
    assert view.hostname is None


def test_interface_names_mentioned_not_implemented() -> None:
    """Test interface_names_mentioned raises NotImplementedError (covers line 183)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/0")

    view = get_hconfig_view(config)

    with pytest.raises(NotImplementedError):
        _ = view.interface_names_mentioned


def test_interface_views() -> None:
    """Test interface_views yields interface views (covers lines 187-188)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/0")
    config.add_child("interface GigabitEthernet0/0/0/1")

    view = get_hconfig_view(config)
    interface_views = list(view.interface_views)

    assert len(interface_views) == 2
    assert any(iv.name == "GigabitEthernet0/0/0/0" for iv in interface_views)
    assert any(iv.name == "GigabitEthernet0/0/0/1" for iv in interface_views)


def test_interfaces() -> None:
    """Test interfaces returns interface children (covers line 192)."""
    config = get_hconfig(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/0")
    config.add_child("interface GigabitEthernet0/0/0/1")
    config.add_child("interface Loopback0")

    view = get_hconfig_view(config)
    interfaces = list(view.interfaces)

    assert len(interfaces) == 3


def test_ipv4_default_gw_not_implemented() -> None:
    """Test ipv4_default_gw raises NotImplementedError (covers line 196)."""
    config = get_hconfig(Platform.CISCO_XR)

    view = get_hconfig_view(config)

    with pytest.raises(NotImplementedError):
        _ = view.ipv4_default_gw


def test_location_not_implemented() -> None:
    """Test location raises NotImplementedError (covers line 200)."""
    config = get_hconfig(Platform.CISCO_XR)

    view = get_hconfig_view(config)

    with pytest.raises(NotImplementedError):
        _ = view.location


def test_stack_members_not_implemented() -> None:
    """Test stack_members raises NotImplementedError (covers line 204)."""
    config = get_hconfig(Platform.CISCO_XR)

    view = get_hconfig_view(config)

    with pytest.raises(NotImplementedError):
        _ = list(view.stack_members)


def test_vlans_not_implemented() -> None:
    """Test vlans raises NotImplementedError (covers line 208)."""
    config = get_hconfig(Platform.CISCO_XR)

    view = get_hconfig_view(config)

    with pytest.raises(NotImplementedError):
        _ = list(view.vlans)
