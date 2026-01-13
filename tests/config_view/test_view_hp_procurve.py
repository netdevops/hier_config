"""Tests for HP Procurve view.py ConfigViewInterfaceHPProcurve and HConfigViewHPProcurve classes."""

from ipaddress import IPv4Address, IPv4Interface

import pytest

from hier_config import Platform, get_hconfig, get_hconfig_view
from hier_config.platforms.models import InterfaceDuplex, StackMember


def test_bundle_id_not_implemented() -> None:
    """Test bundle_id raises NotImplementedError (covers line 26)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface Trk1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Trk1")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = interface_view.bundle_id


def test_bundle_member_interfaces() -> None:
    """Test bundle_member_interfaces returns member interfaces (covers lines 31-42)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface Trk1")
    config.add_child("trunk 1/45,2/45 trk1 trunk")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Trk1")
    assert interface_view is not None

    members = list(interface_view.bundle_member_interfaces)
    assert "1/45" in members
    assert "2/45" in members


def test_bundle_member_interfaces_bundle_not_found_error() -> None:
    """Test bundle_member_interfaces raises TypeError when bundle config missing (covers lines 33-36)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface Trk1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Trk1")
    assert interface_view is not None

    with pytest.raises(
        TypeError, match="Interface is a bundle but bundle config was not found"
    ):
        _ = list(interface_view.bundle_member_interfaces)


def test_bundle_member_interfaces_value_error() -> None:
    """Test bundle_member_interfaces raises ValueError for non-bundle (covers lines 38-40)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None

    with pytest.raises(ValueError, match="The bundle config line couldn't be found"):
        _ = list(interface_view.bundle_member_interfaces)


def test_bundle_name() -> None:
    """Test bundle_name returns bundle name (covers lines 46-53)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1")
    config.add_child("trunk 1/1-2 trk1 lacp")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert interface_view.bundle_name == "Trk1"


def test_bundle_name_none() -> None:
    """Test bundle_name returns None when not in bundle (covers line 53)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert interface_view.bundle_name is None


def test_description() -> None:
    """Test description returns interface name (covers lines 57-59)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_children_deep(("interface 1/1", 'name "uplink port"'))

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert interface_view.description == "uplink port"


def test_description_empty() -> None:
    """Test description returns empty string (covers line 59)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert not interface_view.description


def test_duplex_auto() -> None:
    """Test duplex returns auto (covers line 65)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert interface_view.duplex == InterfaceDuplex.AUTO


def test_enabled_true() -> None:
    """Test enabled returns True (covers line 69)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert interface_view.enabled is True


def test_enabled_false() -> None:
    """Test enabled returns False when disabled (covers line 69)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_children_deep(("interface 1/1", "disable"))

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert interface_view.enabled is False


def test_has_nac_authenticator() -> None:
    """Test has_nac with authenticator (covers line 74)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1")
    config.add_child("aaa port-access authenticator 1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert interface_view.has_nac is True


def test_has_nac_mac_based() -> None:
    """Test has_nac with mac-based (covers line 74)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1")
    config.add_child("aaa port-access mac-based 1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert interface_view.has_nac is True


def test_has_nac_false() -> None:
    """Test has_nac returns False (covers line 74)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert interface_view.has_nac is False


def test_ipv4_interface_none() -> None:
    """Test ipv4_interface returns None (covers line 84)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert interface_view.ipv4_interface is None


def test_ipv4_interfaces() -> None:
    """Test ipv4_interfaces returns IP addresses (covers lines 88-93)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_children_deep(("vlan 10", "ip address 10.1.1.1 255.255.255.0"))

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("vlan 10")
    assert interface_view is not None

    ips = list(interface_view.ipv4_interfaces)
    assert len(ips) == 1
    assert ips[0] == IPv4Interface("10.1.1.1/24")


def test_ipv4_interfaces_invalid() -> None:
    """Test ipv4_interfaces skips invalid addresses (covers line 93)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_children_deep(("vlan 10", "ip address dhcp-bootp"))

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("vlan 10")
    assert interface_view is not None

    ips = list(interface_view.ipv4_interfaces)
    assert len(ips) == 0


def test_is_bundle_true() -> None:
    """Test is_bundle returns True (covers line 97)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface Trk1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Trk1")
    assert interface_view is not None
    assert interface_view.is_bundle is True


def test_is_bundle_false() -> None:
    """Test is_bundle returns False (covers line 97)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert interface_view.is_bundle is False


def test_is_loopback_true() -> None:
    """Test is_loopback returns True (covers line 101)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface Loopback0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Loopback0")
    assert interface_view is not None
    assert interface_view.is_loopback is True


def test_is_loopback_false() -> None:
    """Test is_loopback returns False (covers line 101)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert interface_view.is_loopback is False


def test_is_subinterface_true() -> None:
    """Test is_subinterface returns True (covers line 105)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1.100")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1.100")
    assert interface_view is not None
    assert interface_view.is_subinterface is True


def test_is_subinterface_false() -> None:
    """Test is_subinterface returns False (covers line 105)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert interface_view.is_subinterface is False


def test_is_svi_true() -> None:
    """Test is_svi returns True (covers line 109)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    vlan = config.add_child("vlan 10")
    vlan.add_child("ip address 10.1.1.1 255.255.255.0")

    view = get_hconfig_view(config)
    interface_views = list(view.interface_views)
    vlan_view = next((iv for iv in interface_views if iv.is_svi), None)
    assert vlan_view is not None
    assert vlan_view.is_svi is True


def test_is_svi_false() -> None:
    """Test is_svi returns False (covers line 109)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert interface_view.is_svi is False


def test_module_number() -> None:
    """Test module_number returns module (covers lines 113-116)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 2/10")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("2/10")
    assert interface_view is not None
    assert interface_view.module_number == 2


def test_module_number_none() -> None:
    """Test module_number returns None (covers lines 115-116)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface Trk1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Trk1")
    assert interface_view is not None
    assert interface_view.module_number is None


def test_nac_control_direction_in_true() -> None:
    """Test nac_control_direction_in returns True (covers line 121)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1")
    config.add_child("aaa port-access 1/1 controlled-direction in")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert interface_view.nac_control_direction_in is True


def test_nac_control_direction_in_false() -> None:
    """Test nac_control_direction_in returns False (covers line 121)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert interface_view.nac_control_direction_in is False


def test_nac_host_mode() -> None:
    """Test nac_host_mode returns None (covers line 130)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert interface_view.nac_host_mode is None


def test_nac_mab_first_true() -> None:
    """Test nac_mab_first returns True (covers line 135)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1")
    config.add_child("aaa port-access 1/1 auth-order mac-based authenticator")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert interface_view.nac_mab_first is True


def test_nac_mab_first_false() -> None:
    """Test nac_mab_first returns False (covers line 135)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert interface_view.nac_mab_first is False


def test_nac_max_dot1x_clients() -> None:
    """Test nac_max_dot1x_clients returns count (covers lines 144-148)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1")
    config.add_child("aaa port-access authenticator 1/1 client-limit 5")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert interface_view.nac_max_dot1x_clients == 5


def test_nac_max_dot1x_clients_default() -> None:
    """Test nac_max_dot1x_clients returns default (covers line 148)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert interface_view.nac_max_dot1x_clients == 1


def test_nac_max_mab_clients() -> None:
    """Test nac_max_mab_clients returns count (covers lines 153-157)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1")
    config.add_child("aaa port-access mac-based 1/1 addr-limit 10")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert interface_view.nac_max_mab_clients == 10


def test_nac_max_mab_clients_default() -> None:
    """Test nac_max_mab_clients returns default (covers line 157)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert interface_view.nac_max_mab_clients == 1


def test_name_with_interface_prefix() -> None:
    """Test name returns interface name (covers lines 161-163)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert interface_view.name == "1/1"


def test_name_without_interface_prefix() -> None:
    """Test name returns text as-is (covers line 163)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    vlan = config.add_child("vlan 10")
    vlan.add_child("ip address 10.1.1.1 255.255.255.0")

    view = get_hconfig_view(config)
    interface_views = list(view.interface_views)
    vlan_view = next((iv for iv in interface_views if "vlan" in iv.name.lower()), None)
    assert vlan_view is not None
    assert vlan_view.name == "vlan 10"


def test_native_vlan() -> None:
    """Test native_vlan returns VLAN ID (covers lines 167-169)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_children_deep(("interface 1/1", "untagged vlan 100"))

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert interface_view.native_vlan == 100


def test_native_vlan_none() -> None:
    """Test native_vlan returns None (covers line 169)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert interface_view.native_vlan is None


def test_number() -> None:
    """Test number returns interface number (covers line 173)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/10")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/10")
    assert interface_view is not None
    assert interface_view.number == "1/10"


def test_parent_name() -> None:
    """Test parent_name returns parent interface (covers lines 177-179)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1.100")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1.100")
    assert interface_view is not None
    assert interface_view.parent_name == "1/1"


def test_parent_name_none() -> None:
    """Test parent_name returns None (covers line 179)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert interface_view.parent_name is None


def test_poe_true() -> None:
    """Test poe returns True (covers line 183)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert interface_view.poe is True


def test_poe_false() -> None:
    """Test poe returns False (covers line 183)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_children_deep(("interface 1/1", "no power-over-ethernet"))

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert interface_view.poe is False


def test_port_number() -> None:
    """Test port_number returns port number (covers line 187)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 2/15")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("2/15")
    assert interface_view is not None
    assert interface_view.port_number == 15


def test_port_number_with_subinterface() -> None:
    """Test port_number with subinterface (covers line 187)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/5.100")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/5.100")
    assert interface_view is not None
    assert interface_view.port_number == 5


def test_speed_none() -> None:
    """Test speed returns None (covers line 193)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert interface_view.speed is None


def test_subinterface_number() -> None:
    """Test subinterface_number returns number (covers line 197)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1.200")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1.200")
    assert interface_view is not None
    assert interface_view.subinterface_number == 200


def test_subinterface_number_none() -> None:
    """Test subinterface_number returns None (covers line 197)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert interface_view.subinterface_number is None


def test_tagged_all_false() -> None:
    """Test tagged_all always returns False (covers line 201)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert interface_view.tagged_all is False


def test_tagged_vlans() -> None:
    """Test tagged_vlans returns VLAN list (covers line 205)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    interface = config.add_child("interface 1/1")
    interface.add_child("tagged vlan 10")
    interface.add_child("tagged vlan 20")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert interface_view.tagged_vlans == (10, 20)


def test_tagged_vlans_empty() -> None:
    """Test tagged_vlans returns empty tuple (covers line 205)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert interface_view.tagged_vlans == ()


def test_vrf_empty() -> None:
    """Test vrf always returns empty string (covers line 212)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("1/1")
    assert interface_view is not None
    assert not interface_view.vrf


def test_bundle_prefix() -> None:
    """Test _bundle_prefix returns 'trk' (covers line 216)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface Trk1")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Trk1")
    assert interface_view is not None
    assert interface_view.is_bundle


def test_dot1q_mode_from_vlans_not_implemented() -> None:
    """Test dot1q_mode_from_vlans raises NotImplementedError (covers line 243)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    view = get_hconfig_view(config)

    with pytest.raises(NotImplementedError):
        view.dot1q_mode_from_vlans(untagged_vlan=10)


def test_hostname() -> None:
    """Test hostname returns hostname (covers lines 247-249)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child('hostname "SWITCH01"')

    view = get_hconfig_view(config)
    assert view.hostname == "switch01"


def test_hostname_none() -> None:
    """Test hostname returns None (covers line 249)."""
    config = get_hconfig(Platform.HP_PROCURVE)

    view = get_hconfig_view(config)
    assert view.hostname is None


def test_interface_names_mentioned() -> None:
    """Test interface_names_mentioned includes all interfaces (covers lines 253-266)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1")
    config.add_child("interface 2/5")
    config.add_child("aaa port-access authenticator 1/10")
    config.add_child("aaa port-access mac-based 2/15")
    config.add_child("aaa port-access 3/20 controlled-direction in")

    view = get_hconfig_view(config)
    names = view.interface_names_mentioned

    assert "1/1" in names
    assert "2/5" in names
    assert "1/10" in names
    assert "2/15" in names
    assert "3/20" in names


def test_interface_views() -> None:
    """Test interface_views yields interface views (covers lines 270-274)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1")
    config.add_children_deep(("vlan 10", "ip address 10.1.1.1 255.255.255.0"))

    view = get_hconfig_view(config)
    interface_views = list(view.interface_views)

    assert len(interface_views) == 2
    assert any(iv.name == "1/1" for iv in interface_views)
    assert any(iv.name == "vlan 10" for iv in interface_views)


def test_interfaces() -> None:
    """Test interfaces returns interface children (covers line 278)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("interface 1/1")
    config.add_child("interface 2/2")

    view = get_hconfig_view(config)
    interfaces = list(view.interfaces)

    assert len(interfaces) == 2


def test_ipv4_default_gw() -> None:
    """Test ipv4_default_gw returns gateway IP (covers lines 282-284)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("ip default-gateway 192.168.1.1")

    view = get_hconfig_view(config)
    assert view.ipv4_default_gw == IPv4Address("192.168.1.1")


def test_ipv4_default_gw_none() -> None:
    """Test ipv4_default_gw returns None (covers line 284)."""
    config = get_hconfig(Platform.HP_PROCURVE)

    view = get_hconfig_view(config)
    assert view.ipv4_default_gw is None


def test_location() -> None:
    """Test location returns location string (covers lines 288-290)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child('snmp-server location "Building A, Floor 2"')

    view = get_hconfig_view(config)
    assert view.location == "Building A, Floor 2"


def test_location_empty() -> None:
    """Test location returns empty string (covers line 290)."""
    config = get_hconfig(Platform.HP_PROCURVE)

    view = get_hconfig_view(config)
    assert not view.location


def test_stack_members() -> None:
    """Test stack_members yields stack members (covers lines 301-309)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    stacking = config.add_child("stacking")
    stacking.add_child('member 1 type "JL123" mac-address abc123-def456')
    stacking.add_child('member 2 type "JL456" mac-address xyz789-uvw012')

    view = get_hconfig_view(config)
    members = list(view.stack_members)

    assert len(members) == 2
    assert members[0] == StackMember(
        id=1, priority=255, mac_address="abc123-def456", model="JL123"
    )
    assert members[1] == StackMember(
        id=2, priority=254, mac_address="xyz789-uvw012", model="JL456"
    )


def test_stack_members_no_stacking() -> None:
    """Test stack_members returns empty when no stacking (covers line 301)."""
    config = get_hconfig(Platform.HP_PROCURVE)

    view = get_hconfig_view(config)
    members = list(view.stack_members)

    assert len(members) == 0


def test_vlans_explicit() -> None:
    """Test vlans yields explicitly defined VLANs (covers lines 318-346)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_children_deep(("vlan 10", 'name "Data"'))
    config.add_children_deep(("vlan 20", 'name "Voice"'))

    view = get_hconfig_view(config)
    vlans = list(view.vlans)

    assert len(vlans) >= 2
    assert any(v.id == 10 and v.name == "Data" for v in vlans)
    assert any(v.id == 20 and v.name == "Voice" for v in vlans)


def test_vlans_range() -> None:
    """Test vlans expands VLAN ranges (covers lines 318-346)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    config.add_child("vlan 10-12")

    view = get_hconfig_view(config)
    vlans = list(view.vlans)

    assert len(vlans) >= 3
    assert any(v.id == 10 for v in vlans)
    assert any(v.id == 11 for v in vlans)
    assert any(v.id == 12 for v in vlans)


def test_vlans_from_interfaces() -> None:
    """Test vlans includes VLANs from interfaces (covers lines 318-346)."""
    config = get_hconfig(Platform.HP_PROCURVE)
    interface = config.add_child("interface 1/1")
    interface.add_child("tagged vlan 100")
    interface.add_child("untagged vlan 50")

    view = get_hconfig_view(config)
    vlans = list(view.vlans)

    assert any(v.id == 100 for v in vlans)
    assert any(v.id == 50 for v in vlans)
