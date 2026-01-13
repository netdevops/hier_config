"""Tests for Cisco IOS view.py ConfigViewInterfaceCiscoIOS and HConfigViewCiscoIOS classes."""

from ipaddress import IPv4Address

import pytest

from hier_config import Platform, get_hconfig, get_hconfig_view
from hier_config.platforms.models import InterfaceDuplex, NACHostMode, StackMember


def test_bundle_id() -> None:
    """Test bundle_id returns channel-group ID (covers lines 25, 29)."""
    config = get_hconfig(Platform.CISCO_IOS)
    interface = config.add_child("interface GigabitEthernet0/0")
    interface.add_child("channel-group 10 mode active")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.bundle_id == "10"


def test_bundle_id_none() -> None:
    """Test bundle_id returns None (covers line 25)."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_child("interface GigabitEthernet0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.bundle_id is None


def test_bundle_member_interfaces_not_implemented() -> None:
    """Test bundle_member_interfaces raises NotImplementedError (covers line 29)."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_child("interface GigabitEthernet0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = list(interface_view.bundle_member_interfaces)


def test_bundle_name() -> None:
    """Test bundle_name returns formatted name (covers lines 35, 39-41)."""
    config = get_hconfig(Platform.CISCO_IOS)
    interface = config.add_child("interface GigabitEthernet0/0")
    interface.add_child("channel-group 5 mode active")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.bundle_name == "Port-channel5"


def test_bundle_name_none() -> None:
    """Test bundle_name returns None (covers line 35)."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_child("interface GigabitEthernet0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.bundle_name is None


def test_description() -> None:
    """Test description returns description text (covers lines 45-47)."""
    config = get_hconfig(Platform.CISCO_IOS)
    interface = config.add_child("interface GigabitEthernet0/0")
    interface.add_child("description Uplink to Core")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.description == "Uplink to Core"


def test_description_empty() -> None:
    """Test description returns empty string (covers line 47)."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_child("interface GigabitEthernet0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert not interface_view.description


def test_duplex_auto() -> None:
    """Test duplex returns auto (covers line 51)."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_child("interface GigabitEthernet0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.duplex == InterfaceDuplex.AUTO


def test_enabled_true() -> None:
    """Test enabled returns True (covers line 55)."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_child("interface GigabitEthernet0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.enabled is True


def test_enabled_false() -> None:
    """Test enabled returns False when shutdown (covers line 55)."""
    config = get_hconfig(Platform.CISCO_IOS)
    interface = config.add_child("interface GigabitEthernet0/0")
    interface.add_child("shutdown")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.enabled is False


def test_has_nac_port_control() -> None:
    """Test has_nac with port-control (covers line 70)."""
    config = get_hconfig(Platform.CISCO_IOS)
    interface = config.add_child("interface GigabitEthernet0/0")
    interface.add_child("authentication port-control auto")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.has_nac is True


def test_has_nac_mab() -> None:
    """Test has_nac with mab (covers line 70)."""
    config = get_hconfig(Platform.CISCO_IOS)
    interface = config.add_child("interface GigabitEthernet0/0")
    interface.add_child("mab")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.has_nac is True


def test_has_nac_false() -> None:
    """Test has_nac returns False (covers lines 70-74)."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_child("interface GigabitEthernet0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.has_nac is False


def test_ipv4_interface_none() -> None:
    """Test ipv4_interface returns None (covers line 78)."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_child("interface GigabitEthernet0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.ipv4_interface is None


def test_nac_control_direction_in_true() -> None:
    """Test nac_control_direction_in returns True (covers line 102)."""
    config = get_hconfig(Platform.CISCO_IOS)
    interface = config.add_child("interface GigabitEthernet0/0")
    interface.add_child("authentication control-direction in")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.nac_control_direction_in is True


def test_nac_control_direction_in_false() -> None:
    """Test nac_control_direction_in returns False (covers line 102)."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_child("interface GigabitEthernet0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.nac_control_direction_in is False


def test_nac_host_mode_multi_auth() -> None:
    """Test nac_host_mode returns MULTI_AUTH (covers lines 107-122)."""
    config = get_hconfig(Platform.CISCO_IOS)
    interface = config.add_child("interface GigabitEthernet0/0")
    interface.add_child("authentication host-mode multi-auth")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.nac_host_mode == NACHostMode.MULTI_AUTH


def test_nac_host_mode_multi_domain() -> None:
    """Test nac_host_mode returns MULTI_DOMAIN (covers lines 107-122)."""
    config = get_hconfig(Platform.CISCO_IOS)
    interface = config.add_child("interface GigabitEthernet0/0")
    interface.add_child("authentication host-mode multi-domain")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.nac_host_mode == NACHostMode.MULTI_DOMAIN


def test_nac_host_mode_multi_host() -> None:
    """Test nac_host_mode returns MULTI_HOST (covers lines 107-122)."""
    config = get_hconfig(Platform.CISCO_IOS)
    interface = config.add_child("interface GigabitEthernet0/0")
    interface.add_child("authentication host-mode multi-host")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.nac_host_mode == NACHostMode.MULTI_HOST


def test_nac_host_mode_single_host() -> None:
    """Test nac_host_mode returns SINGLE_HOST (covers lines 107-122)."""
    config = get_hconfig(Platform.CISCO_IOS)
    interface = config.add_child("interface GigabitEthernet0/0")
    interface.add_child("authentication host-mode single-host")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.nac_host_mode == NACHostMode.SINGLE_HOST


def test_nac_host_mode_none() -> None:
    """Test nac_host_mode returns None (covers lines 107-122)."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_child("interface GigabitEthernet0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.nac_host_mode is None


def test_nac_mab_first_true() -> None:
    """Test nac_mab_first returns True (covers line 127)."""
    config = get_hconfig(Platform.CISCO_IOS)
    interface = config.add_child("interface GigabitEthernet0/0")
    interface.add_child("authentication order mab dot1x")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.nac_mab_first is True


def test_nac_mab_first_false() -> None:
    """Test nac_mab_first returns False (covers line 127)."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_child("interface GigabitEthernet0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.nac_mab_first is False


def test_nac_max_dot1x_clients_not_implemented() -> None:
    """Test nac_max_dot1x_clients raises NotImplementedError (covers line 132)."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_child("interface GigabitEthernet0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = interface_view.nac_max_dot1x_clients


def test_nac_max_mab_clients_not_implemented() -> None:
    """Test nac_max_mab_clients raises NotImplementedError (covers line 137)."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_child("interface GigabitEthernet0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None

    with pytest.raises(NotImplementedError):
        _ = interface_view.nac_max_mab_clients


def test_native_vlan_subinterface() -> None:
    """Test native_vlan from subinterface encapsulation (covers lines 149, 162-167)."""
    config = get_hconfig(Platform.CISCO_IOS)
    interface = config.add_child("interface GigabitEthernet0/0.100")
    interface.add_child("encapsulation dot1Q 50")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0.100")
    assert interface_view is not None
    assert interface_view.native_vlan == 50


def test_native_vlan_no_switchport() -> None:
    """Test native_vlan returns None for routed port (covers lines 149, 162-167)."""
    config = get_hconfig(Platform.CISCO_IOS)
    interface = config.add_child("interface GigabitEthernet0/0")
    interface.add_child("no switchport")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.native_vlan is None


def test_native_vlan_trunk() -> None:
    """Test native_vlan on trunk port (covers lines 171, 182-184)."""
    config = get_hconfig(Platform.CISCO_IOS)
    interface = config.add_child("interface GigabitEthernet0/0")
    interface.add_child("switchport mode trunk")
    interface.add_child("switchport trunk native vlan 999")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.native_vlan == 999


def test_native_vlan_trunk_default() -> None:
    """Test native_vlan on trunk without explicit native (covers lines 171, 182-184)."""
    config = get_hconfig(Platform.CISCO_IOS)
    interface = config.add_child("interface GigabitEthernet0/0")
    interface.add_child("switchport mode trunk")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.native_vlan is None


def test_native_vlan_access() -> None:
    """Test native_vlan on access port (covers line 188)."""
    config = get_hconfig(Platform.CISCO_IOS)
    interface = config.add_child("interface GigabitEthernet0/0")
    interface.add_child("switchport access vlan 50")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.native_vlan == 50


def test_native_vlan_default() -> None:
    """Test native_vlan defaults to 1 (covers line 192)."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_child("interface GigabitEthernet0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.native_vlan == 1


def test_poe_true() -> None:
    """Test poe returns True (covers line 196)."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_child("interface GigabitEthernet0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.poe is True


def test_poe_false() -> None:
    """Test poe returns False (covers lines 196-200)."""
    config = get_hconfig(Platform.CISCO_IOS)
    interface = config.add_child("interface GigabitEthernet0/0")
    interface.add_child("power inline never")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.poe is False


def test_speed() -> None:
    """Test speed returns speed value (covers line 204)."""
    config = get_hconfig(Platform.CISCO_IOS)
    interface = config.add_child("interface GigabitEthernet0/0")
    interface.add_child("speed 1000")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.speed == (1000,)


def test_tagged_all_true() -> None:
    """Test tagged_all returns True (covers line 223)."""
    config = get_hconfig(Platform.CISCO_IOS)
    interface = config.add_child("interface GigabitEthernet0/0")
    interface.add_child("switchport mode trunk")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.tagged_all is True


def test_tagged_all_false() -> None:
    """Test tagged_all returns False (covers lines 223-225)."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_child("interface GigabitEthernet0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.tagged_all is False


def test_tagged_vlans() -> None:
    """Test tagged_vlans returns VLAN list (covers line 240)."""
    config = get_hconfig(Platform.CISCO_IOS)
    interface = config.add_child("interface GigabitEthernet0/0")
    interface.add_child("switchport trunk allowed vlan 10,20,30-35")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.tagged_vlans == (10, 20, 30, 31, 32, 33, 34, 35)


def test_tagged_vlans_empty() -> None:
    """Test tagged_vlans returns empty tuple (covers lines 240, 244-246)."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_child("interface GigabitEthernet0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.tagged_vlans == ()


def test_vrf() -> None:
    """Test vrf returns VRF name (covers line 251)."""
    config = get_hconfig(Platform.CISCO_IOS)
    interface = config.add_child("interface GigabitEthernet0/0")
    interface.add_child("ip vrf forwarding MGMT")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.vrf == "MGMT"


def test_vrf_empty() -> None:
    """Test vrf returns empty string (covers line 251)."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_child("interface GigabitEthernet0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert not interface_view.vrf


def test_dot1q_mode_from_vlans_not_implemented() -> None:
    """Test dot1q_mode_from_vlans raises NotImplementedError (covers line 264)."""
    config = get_hconfig(Platform.CISCO_IOS)
    view = get_hconfig_view(config)

    with pytest.raises(NotImplementedError):
        view.dot1q_mode_from_vlans(untagged_vlan=10)


def test_hostname() -> None:
    """Test hostname returns hostname (covers lines 270-272)."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_child("hostname ROUTER-01")

    view = get_hconfig_view(config)
    assert view.hostname == "router-01"


def test_hostname_none() -> None:
    """Test hostname returns None (covers line 272)."""
    config = get_hconfig(Platform.CISCO_IOS)

    view = get_hconfig_view(config)
    assert view.hostname is None


def test_interface_names_mentioned() -> None:
    """Test interface_names_mentioned returns interface names (covers line 283)."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_child("interface GigabitEthernet0/0")
    config.add_child("interface GigabitEthernet0/1")

    view = get_hconfig_view(config)
    names = view.interface_names_mentioned

    assert "GigabitEthernet0/0" in names
    assert "GigabitEthernet0/1" in names


def test_ipv4_default_gw() -> None:
    """Test ipv4_default_gw returns gateway IP (covers lines 283-286)."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_child("ip default-gateway 192.168.1.1")

    view = get_hconfig_view(config)
    assert view.ipv4_default_gw == IPv4Address("192.168.1.1")


def test_ipv4_default_gw_none() -> None:
    """Test ipv4_default_gw returns None (covers line 286)."""
    config = get_hconfig(Platform.CISCO_IOS)

    view = get_hconfig_view(config)
    assert view.ipv4_default_gw is None


def test_location() -> None:
    """Test location returns location string (covers lines 301-302)."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_child('snmp-server location "Building A, Floor 2"')

    view = get_hconfig_view(config)
    assert view.location == "Building A, Floor 2"


def test_location_empty() -> None:
    """Test location returns empty string (covers line 302)."""
    config = get_hconfig(Platform.CISCO_IOS)

    view = get_hconfig_view(config)
    assert not view.location


def test_stack_members() -> None:
    """Test stack_members yields stack members (covers lines 312-316)."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_child("switch 1 provision ws-c3850-24p")
    config.add_child("switch 2 provision ws-c3850-24p")

    view = get_hconfig_view(config)
    members = list(view.stack_members)

    assert len(members) == 2
    assert members[0] == StackMember(
        id=1, priority=255, mac_address=None, model="ws-c3850-24p"
    )
    assert members[1] == StackMember(
        id=2, priority=254, mac_address=None, model="ws-c3850-24p"
    )


def test_vlans_explicit() -> None:
    """Test vlans yields explicitly defined VLANs (covers lines 264-266)."""
    config = get_hconfig(Platform.CISCO_IOS)
    vlan10 = config.add_child("vlan 10")
    vlan10.add_child("name Data")
    vlan20 = config.add_child("vlan 20")
    vlan20.add_child("name Voice")

    view = get_hconfig_view(config)
    vlans = list(view.vlans)

    assert len(vlans) >= 2
    assert any(v.id == 10 and v.name == "Data" for v in vlans)
    assert any(v.id == 20 and v.name == "Voice" for v in vlans)


def test_vlans_from_interfaces() -> None:
    """Test vlans includes VLANs from interfaces (covers lines 264-266)."""
    config = get_hconfig(Platform.CISCO_IOS)
    interface = config.add_child("interface GigabitEthernet0/0")
    interface.add_child("switchport access vlan 100")

    view = get_hconfig_view(config)
    vlans = list(view.vlans)

    assert any(v.id == 100 for v in vlans)
