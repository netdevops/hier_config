"""Tests for Cisco NX-OS view.py ConfigViewInterfaceCiscoNXOS and HConfigViewCiscoNXOS classes."""

from ipaddress import IPv4Interface

import pytest

from hier_config import Platform, get_hconfig, get_hconfig_view


def test_bundle_id_not_implemented() -> None:
    """Test bundle_id raises NotImplementedError (covers line 22)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface port-channel1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("port-channel1")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = interface_view.bundle_id


def test_bundle_member_interfaces_not_implemented() -> None:
    """Test bundle_member_interfaces raises NotImplementedError (covers line 26)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Ethernet1/1")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = list(interface_view.bundle_member_interfaces)


def test_bundle_name_not_implemented() -> None:
    """Test bundle_name raises NotImplementedError (covers line 30)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Ethernet1/1")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = interface_view.bundle_name


def test_description() -> None:
    """Test description returns description text (covers lines 34-36)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    interface = config.add_child("interface Ethernet1/1")
    interface.add_child("description Uplink to Core")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Ethernet1/1")
    assert interface_view is not None
    assert interface_view.description == "Uplink to Core"


def test_description_empty() -> None:
    """Test description returns empty string (covers line 36)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Ethernet1/1")
    assert interface_view is not None
    assert not interface_view.description


def test_duplex_not_implemented() -> None:
    """Test duplex raises NotImplementedError (covers line 40)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Ethernet1/1")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = interface_view.duplex


def test_enabled_not_implemented() -> None:
    """Test enabled raises NotImplementedError (covers line 44)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Ethernet1/1")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = interface_view.enabled


def test_has_nac_not_implemented() -> None:
    """Test has_nac raises NotImplementedError (covers line 49)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Ethernet1/1")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = interface_view.has_nac


def test_ipv4_interface_none() -> None:
    """Test ipv4_interface returns None (covers line 53)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Ethernet1/1")
    assert interface_view is not None
    assert interface_view.ipv4_interface is None


def test_ipv4_interfaces() -> None:
    """Test ipv4_interfaces returns IP addresses (covers lines 57-62)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    interface = config.add_child("interface Ethernet1/1")
    interface.add_child("ip address 10.1.1.1 255.255.255.0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Ethernet1/1")
    assert interface_view is not None

    ips = list(interface_view.ipv4_interfaces)
    assert len(ips) == 1
    assert ips[0] == IPv4Interface("10.1.1.1/24")


def test_ipv4_interfaces_invalid() -> None:
    """Test ipv4_interfaces skips invalid addresses (covers line 62)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    interface = config.add_child("interface Ethernet1/1")
    interface.add_child("ip address dhcp")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Ethernet1/1")
    assert interface_view is not None

    ips = list(interface_view.ipv4_interfaces)
    assert len(ips) == 0


def test_is_bundle_true() -> None:
    """Test is_bundle returns True (covers line 66)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface port-channel10")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("port-channel10")
    assert interface_view is not None
    assert interface_view.is_bundle is True


def test_is_bundle_false() -> None:
    """Test is_bundle returns False (covers line 66)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Ethernet1/1")
    assert interface_view is not None
    assert interface_view.is_bundle is False


def test_is_loopback_true() -> None:
    """Test is_loopback returns True (covers line 70)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface loopback0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("loopback0")
    assert interface_view is not None
    assert interface_view.is_loopback is True


def test_is_loopback_false() -> None:
    """Test is_loopback returns False (covers line 70)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Ethernet1/1")
    assert interface_view is not None
    assert interface_view.is_loopback is False


def test_is_subinterface_true() -> None:
    """Test is_subinterface returns True (covers line 74)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1.100")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Ethernet1/1.100")
    assert interface_view is not None
    assert interface_view.is_subinterface is True


def test_is_subinterface_false() -> None:
    """Test is_subinterface returns False (covers line 74)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Ethernet1/1")
    assert interface_view is not None
    assert interface_view.is_subinterface is False


def test_is_svi_true() -> None:
    """Test is_svi returns True (covers line 78)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface vlan100")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("vlan100")
    assert interface_view is not None
    assert interface_view.is_svi is True


def test_is_svi_false() -> None:
    """Test is_svi returns False (covers line 78)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Ethernet1/1")
    assert interface_view is not None
    assert interface_view.is_svi is False


def test_module_number() -> None:
    """Test module_number returns module (covers lines 82-85)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet2/15")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Ethernet2/15")
    assert interface_view is not None
    assert interface_view.module_number == 2


def test_module_number_none() -> None:
    """Test module_number returns None (covers lines 84-85)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface loopback0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("loopback0")
    assert interface_view is not None
    assert interface_view.module_number is None


def test_nac_control_direction_in_not_implemented() -> None:
    """Test nac_control_direction_in raises NotImplementedError (covers line 90)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Ethernet1/1")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = interface_view.nac_control_direction_in


def test_nac_host_mode_not_implemented() -> None:
    """Test nac_host_mode raises NotImplementedError (covers line 95)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Ethernet1/1")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = interface_view.nac_host_mode


def test_nac_mab_first_not_implemented() -> None:
    """Test nac_mab_first raises NotImplementedError (covers line 100)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Ethernet1/1")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = interface_view.nac_mab_first


def test_nac_max_dot1x_clients_not_implemented() -> None:
    """Test nac_max_dot1x_clients raises NotImplementedError (covers line 105)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Ethernet1/1")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = interface_view.nac_max_dot1x_clients


def test_nac_max_mab_clients_not_implemented() -> None:
    """Test nac_max_mab_clients raises NotImplementedError (covers line 110)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Ethernet1/1")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = interface_view.nac_max_mab_clients


def test_name() -> None:
    """Test name returns interface name (covers line 114)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/10")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Ethernet1/10")
    assert interface_view is not None
    assert interface_view.name == "Ethernet1/10"


def test_native_vlan_not_implemented() -> None:
    """Test native_vlan raises NotImplementedError (covers line 118)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Ethernet1/1")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = interface_view.native_vlan


def test_number() -> None:
    """Test number returns interface number (covers line 122)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet3/25")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Ethernet3/25")
    assert interface_view is not None
    assert interface_view.number == "3/25"


def test_parent_name() -> None:
    """Test parent_name returns parent interface (covers lines 126-128)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1.200")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Ethernet1/1.200")
    assert interface_view is not None
    assert interface_view.parent_name == "Ethernet1/1"


def test_parent_name_none() -> None:
    """Test parent_name returns None (covers line 128)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Ethernet1/1")
    assert interface_view is not None
    assert interface_view.parent_name is None


def test_poe_not_implemented() -> None:
    """Test poe raises NotImplementedError (covers line 132)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Ethernet1/1")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = interface_view.poe


def test_port_number() -> None:
    """Test port_number returns port number (covers line 136)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet2/48")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Ethernet2/48")
    assert interface_view is not None
    assert interface_view.port_number == 48


def test_port_number_with_subinterface() -> None:
    """Test port_number with subinterface (covers line 136)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/5.300")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Ethernet1/5.300")
    assert interface_view is not None
    assert interface_view.port_number == 5


def test_speed_not_implemented() -> None:
    """Test speed raises NotImplementedError (covers line 140)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Ethernet1/1")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = interface_view.speed


def test_subinterface_number() -> None:
    """Test subinterface_number returns number (covers line 144)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1.999")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Ethernet1/1.999")
    assert interface_view is not None
    assert interface_view.subinterface_number == 999


def test_subinterface_number_none() -> None:
    """Test subinterface_number returns None (covers line 144)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Ethernet1/1")
    assert interface_view is not None
    assert interface_view.subinterface_number is None


def test_tagged_all_not_implemented() -> None:
    """Test tagged_all raises NotImplementedError (covers line 148)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Ethernet1/1")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = interface_view.tagged_all


def test_tagged_vlans_not_implemented() -> None:
    """Test tagged_vlans raises NotImplementedError (covers line 152)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Ethernet1/1")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = interface_view.tagged_vlans


def test_vrf_not_implemented() -> None:
    """Test vrf raises NotImplementedError (covers line 156)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Ethernet1/1")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = interface_view.vrf


def test_bundle_prefix() -> None:
    """Test _bundle_prefix returns 'port-channel' (covers line 160)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface port-channel1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("port-channel1")
    assert interface_view is not None
    assert interface_view.is_bundle


def test_dot1q_mode_from_vlans_not_implemented() -> None:
    """Test dot1q_mode_from_vlans raises NotImplementedError (covers line 171)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    view = get_hconfig_view(config)

    with pytest.raises(NotImplementedError):
        view.dot1q_mode_from_vlans(untagged_vlan=10)


def test_hostname() -> None:
    """Test hostname returns hostname (covers lines 175-177)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("hostname NEXUS-CORE-01")

    view = get_hconfig_view(config)
    assert view.hostname == "nexus-core-01"


def test_hostname_none() -> None:
    """Test hostname returns None (covers line 177)."""
    config = get_hconfig(Platform.CISCO_NXOS)

    view = get_hconfig_view(config)
    assert view.hostname is None


def test_interface_names_mentioned_not_implemented() -> None:
    """Test interface_names_mentioned raises NotImplementedError (covers line 182)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")

    view = get_hconfig_view(config)

    with pytest.raises(NotImplementedError):
        _ = view.interface_names_mentioned


def test_interface_views() -> None:
    """Test interface_views yields interface views (covers lines 186-187)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")
    config.add_child("interface Ethernet1/2")
    config.add_child("interface loopback0")

    view = get_hconfig_view(config)
    interface_views = list(view.interface_views)

    assert len(interface_views) == 3
    assert any(iv.name == "Ethernet1/1" for iv in interface_views)
    assert any(iv.name == "Ethernet1/2" for iv in interface_views)
    assert any(iv.name == "loopback0" for iv in interface_views)


def test_interfaces() -> None:
    """Test interfaces returns interface children (covers line 191)."""
    config = get_hconfig(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")
    config.add_child("interface Ethernet1/2")
    config.add_child("interface port-channel1")

    view = get_hconfig_view(config)
    interfaces = list(view.interfaces)

    assert len(interfaces) == 3


def test_ipv4_default_gw_not_implemented() -> None:
    """Test ipv4_default_gw raises NotImplementedError (covers line 195)."""
    config = get_hconfig(Platform.CISCO_NXOS)

    view = get_hconfig_view(config)

    with pytest.raises(NotImplementedError):
        _ = view.ipv4_default_gw


def test_location_not_implemented() -> None:
    """Test location raises NotImplementedError (covers line 199)."""
    config = get_hconfig(Platform.CISCO_NXOS)

    view = get_hconfig_view(config)

    with pytest.raises(NotImplementedError):
        _ = view.location


def test_stack_members_not_implemented() -> None:
    """Test stack_members raises NotImplementedError (covers line 203)."""
    config = get_hconfig(Platform.CISCO_NXOS)

    view = get_hconfig_view(config)

    with pytest.raises(NotImplementedError):
        _ = list(view.stack_members)


def test_vlans_not_implemented() -> None:
    """Test vlans raises NotImplementedError (covers line 207)."""
    config = get_hconfig(Platform.CISCO_NXOS)

    view = get_hconfig_view(config)

    with pytest.raises(NotImplementedError):
        _ = list(view.vlans)
