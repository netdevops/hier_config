"""Tests for Cisco NX-OS view.py ConfigViewInterfaceCiscoNXOS and HConfigViewCiscoNXOS classes."""

from ipaddress import IPv4Address, IPv4Interface

from hier_config import (
    HConfig,
    InterfaceBundleViewMixin,
    InterfaceNACViewMixin,
    InterfacePhysicalViewMixin,
    InterfaceVlanViewMixin,
    Platform,
    get_hconfig_view,
)
from hier_config.platforms.cisco_nxos.view import ConfigViewInterfaceCiscoNXOS
from hier_config.platforms.models import InterfaceDot1qMode, Vlan


def _interface_view(
    config: HConfig, name: str = "Ethernet1/1"
) -> ConfigViewInterfaceCiscoNXOS:
    interface_view = get_hconfig_view(config).interface_view_by_name(name)
    assert isinstance(interface_view, ConfigViewInterfaceCiscoNXOS)
    return interface_view


def test_capabilities() -> None:
    """NX-OS interface views support bundles and VLANs but not NAC or physical."""
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")

    interface_view = _interface_view(config)
    assert isinstance(interface_view, InterfaceBundleViewMixin)
    assert isinstance(interface_view, InterfaceVlanViewMixin)
    assert not isinstance(interface_view, InterfaceNACViewMixin)
    assert not isinstance(interface_view, InterfacePhysicalViewMixin)


def test_bundle_id() -> None:
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_children_deep(("interface Ethernet1/1", "channel-group 10 mode active"))

    assert _interface_view(config).bundle_id == "10"


def test_bundle_id_none() -> None:
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")

    assert _interface_view(config).bundle_id is None


def test_bundle_name() -> None:
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_children_deep(("interface Ethernet1/1", "channel-group 10 mode active"))

    assert _interface_view(config).bundle_name == "port-channel10"


def test_bundle_member_interfaces() -> None:
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_child("interface port-channel10")
    config.add_children_deep(("interface Ethernet1/1", "channel-group 10 mode active"))
    config.add_children_deep(("interface Ethernet1/2", "channel-group 10 mode active"))
    config.add_children_deep(("interface Ethernet1/3", "channel-group 20 mode active"))

    interface_view = _interface_view(config, "port-channel10")
    assert list(interface_view.bundle_member_interfaces) == [
        "Ethernet1/1",
        "Ethernet1/2",
    ]


def test_bundle_member_interfaces_not_a_bundle() -> None:
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")

    assert not list(_interface_view(config).bundle_member_interfaces)


def test_description() -> None:
    """Test description returns description text."""
    config = HConfig.from_text(Platform.CISCO_NXOS)
    interface = config.add_child("interface Ethernet1/1")
    interface.add_child("description Uplink to Core")

    assert _interface_view(config).description == "Uplink to Core"


def test_description_empty() -> None:
    """Test description returns empty string."""
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")

    assert not _interface_view(config).description


def test_enabled() -> None:
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")
    config.add_children_deep(("interface Ethernet1/2", "shutdown"))

    assert _interface_view(config).enabled is True
    assert _interface_view(config, "Ethernet1/2").enabled is False


def test_ipv4_interface_none() -> None:
    """Test ipv4_interface returns None."""
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")

    assert _interface_view(config).ipv4_interface is None


def test_ipv4_interfaces() -> None:
    """Test ipv4_interfaces returns IP addresses."""
    config = HConfig.from_text(Platform.CISCO_NXOS)
    interface = config.add_child("interface Ethernet1/1")
    interface.add_child("ip address 10.1.1.1 255.255.255.0")

    assert list(_interface_view(config).ipv4_interfaces) == [
        IPv4Interface("10.1.1.1/24")
    ]


def test_ipv4_interfaces_cidr() -> None:
    """Test ipv4_interfaces supports NX-OS address/prefix syntax."""
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_children_deep(("interface Ethernet1/1", "ip address 10.1.1.1/24"))

    assert _interface_view(config).ipv4_interface == IPv4Interface("10.1.1.1/24")


def test_ipv4_interfaces_invalid() -> None:
    """Test ipv4_interfaces skips invalid addresses."""
    config = HConfig.from_text(Platform.CISCO_NXOS)
    interface = config.add_child("interface Ethernet1/1")
    interface.add_child("ip address dhcp")

    assert not list(_interface_view(config).ipv4_interfaces)


def test_is_bundle_true() -> None:
    """Test is_bundle returns True."""
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_child("interface port-channel10")

    assert _interface_view(config, "port-channel10").is_bundle is True


def test_is_bundle_false() -> None:
    """Test is_bundle returns False."""
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")

    assert _interface_view(config).is_bundle is False


def test_is_loopback() -> None:
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_child("interface loopback0")
    config.add_child("interface Ethernet1/1")

    assert _interface_view(config, "loopback0").is_loopback is True
    assert _interface_view(config).is_loopback is False


def test_is_subinterface() -> None:
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1.100")
    config.add_child("interface Ethernet1/1")

    assert _interface_view(config, "Ethernet1/1.100").is_subinterface is True
    assert _interface_view(config).is_subinterface is False


def test_is_svi() -> None:
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_child("interface vlan100")
    config.add_child("interface Ethernet1/1")

    assert _interface_view(config, "vlan100").is_svi is True
    assert _interface_view(config).is_svi is False


def test_name() -> None:
    """Test name returns interface name."""
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/10")

    assert _interface_view(config, "Ethernet1/10").name == "Ethernet1/10"


def test_native_vlan_subinterface() -> None:
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_children_deep(("interface Ethernet1/1.100", "encapsulation dot1q 100"))

    assert _interface_view(config, "Ethernet1/1.100").native_vlan == 100


def test_native_vlan_routed_port() -> None:
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_children_deep(("interface Ethernet1/1", "no switchport"))

    assert _interface_view(config).native_vlan is None


def test_native_vlan_trunk() -> None:
    config = HConfig.from_text(Platform.CISCO_NXOS)
    interface = config.add_child("interface Ethernet1/1")
    interface.add_child("switchport mode trunk")
    interface.add_child("switchport trunk native vlan 999")

    assert _interface_view(config).native_vlan == 999


def test_native_vlan_trunk_default() -> None:
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_children_deep(("interface Ethernet1/1", "switchport mode trunk"))

    assert _interface_view(config).native_vlan is None


def test_native_vlan_access() -> None:
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_children_deep(("interface Ethernet1/1", "switchport access vlan 50"))

    interface_view = _interface_view(config)
    assert interface_view.native_vlan == 50
    assert interface_view.dot1q_mode == InterfaceDot1qMode.ACCESS


def test_native_vlan_default() -> None:
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")

    assert _interface_view(config).native_vlan == 1


def test_number() -> None:
    """Test number returns interface number."""
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet3/25")

    assert _interface_view(config, "Ethernet3/25").number == "3/25"


def test_parent_name() -> None:
    """Test parent_name returns parent interface."""
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1.200")

    assert _interface_view(config, "Ethernet1/1.200").parent_name == "Ethernet1/1"


def test_parent_name_none() -> None:
    """Test parent_name returns None."""
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")

    assert _interface_view(config).parent_name is None


def test_port_number() -> None:
    """Test port_number returns port number."""
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet2/48")

    assert _interface_view(config, "Ethernet2/48").port_number == 48


def test_port_number_with_subinterface() -> None:
    """Test port_number with subinterface."""
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/5.300")

    assert _interface_view(config, "Ethernet1/5.300").port_number == 5


def test_subinterface_number() -> None:
    """Test subinterface_number returns number."""
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1.999")

    assert _interface_view(config, "Ethernet1/1.999").subinterface_number == 999


def test_subinterface_number_none() -> None:
    """Test subinterface_number returns None."""
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")

    assert _interface_view(config).subinterface_number is None


def test_tagged_all() -> None:
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_children_deep(("interface Ethernet1/1", "switchport mode trunk"))

    interface_view = _interface_view(config)
    assert interface_view.tagged_all is True
    assert interface_view.dot1q_mode == InterfaceDot1qMode.TAGGED_ALL


def test_tagged_vlans() -> None:
    config = HConfig.from_text(Platform.CISCO_NXOS)
    interface = config.add_child("interface Ethernet1/1")
    interface.add_child("switchport mode trunk")
    interface.add_child("switchport trunk allowed vlan 10,20,30-32")

    interface_view = _interface_view(config)
    assert interface_view.tagged_vlans == (10, 20, 30, 31, 32)
    assert interface_view.tagged_all is False
    assert interface_view.dot1q_mode == InterfaceDot1qMode.TAGGED


def test_tagged_vlans_empty() -> None:
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")

    assert _interface_view(config).tagged_vlans == ()


def test_vrf() -> None:
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_children_deep(("interface Ethernet1/1", "vrf member RED"))
    config.add_child("interface Ethernet1/2")

    assert _interface_view(config).vrf == "RED"
    assert not _interface_view(config, "Ethernet1/2").vrf


def test_hostname() -> None:
    """Test hostname returns hostname."""
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_child("hostname NEXUS-CORE-01")

    view = get_hconfig_view(config)
    assert view.hostname == "nexus-core-01"


def test_hostname_none() -> None:
    """Test hostname returns None."""
    config = HConfig.from_text(Platform.CISCO_NXOS)

    view = get_hconfig_view(config)
    assert view.hostname is None


def test_interface_names_mentioned() -> None:
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")
    config.add_child("interface Ethernet1/2")

    view = get_hconfig_view(config)
    assert view.interface_names_mentioned == frozenset({"Ethernet1/1", "Ethernet1/2"})


def test_interface_views() -> None:
    """Test interface_views yields interface views."""
    config = HConfig.from_text(Platform.CISCO_NXOS)
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
    """Test interfaces returns interface children."""
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_child("interface Ethernet1/1")
    config.add_child("interface Ethernet1/2")
    config.add_child("interface port-channel1")

    view = get_hconfig_view(config)
    interfaces = list(view.interfaces)

    assert len(interfaces) == 3


def test_ipv4_default_gw() -> None:
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_child("ip route 0.0.0.0/0 192.0.2.254")

    view = get_hconfig_view(config)
    assert view.ipv4_default_gw == IPv4Address("192.0.2.254")


def test_ipv4_default_gw_none() -> None:
    config = HConfig.from_text(Platform.CISCO_NXOS)

    view = get_hconfig_view(config)
    assert view.ipv4_default_gw is None


def test_location() -> None:
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_child('snmp-server location "Data Center 1"')

    view = get_hconfig_view(config)
    assert view.location == "Data Center 1"


def test_location_empty() -> None:
    config = HConfig.from_text(Platform.CISCO_NXOS)

    view = get_hconfig_view(config)
    assert not view.location


def test_stack_members() -> None:
    """NX-OS has no stacking, so stack_members is always empty."""
    config = HConfig.from_text(Platform.CISCO_NXOS)

    view = get_hconfig_view(config)
    assert not list(view.stack_members)


def test_vlans() -> None:
    config = HConfig.from_text(Platform.CISCO_NXOS)
    config.add_children_deep(("vlan 10", "name PROD"))
    config.add_child("vlan 20")
    config.add_children_deep(("interface Ethernet1/1", "switchport access vlan 30"))

    view = get_hconfig_view(config)
    assert list(view.vlans) == [
        Vlan(id=10, name="PROD"),
        Vlan(id=20, name=None),
        Vlan(id=30, name=None),
    ]
    assert view.vlan_ids == frozenset({10, 20, 30})
