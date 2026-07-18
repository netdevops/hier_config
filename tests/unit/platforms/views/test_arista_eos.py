"""Tests for Arista EOS view.py ConfigViewInterfaceAristaEOS and HConfigViewAristaEOS classes."""

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
from hier_config.platforms.arista_eos.view import ConfigViewInterfaceAristaEOS
from hier_config.platforms.models import InterfaceDot1qMode, Vlan


def _interface_view(
    config: HConfig, name: str = "Ethernet1"
) -> ConfigViewInterfaceAristaEOS:
    interface_view = get_hconfig_view(config).interface_view_by_name(name)
    assert isinstance(interface_view, ConfigViewInterfaceAristaEOS)
    return interface_view


def test_capabilities() -> None:
    """EOS interface views support bundles and VLANs but not NAC or physical."""
    config = HConfig.from_text(Platform.ARISTA_EOS)
    config.add_child("interface Ethernet1")

    interface_view = _interface_view(config)
    assert isinstance(interface_view, InterfaceBundleViewMixin)
    assert isinstance(interface_view, InterfaceVlanViewMixin)
    assert not isinstance(interface_view, InterfaceNACViewMixin)
    assert not isinstance(interface_view, InterfacePhysicalViewMixin)


def test_bundle_id() -> None:
    config = HConfig.from_text(Platform.ARISTA_EOS)
    config.add_children_deep(("interface Ethernet1", "channel-group 5 mode active"))

    assert _interface_view(config).bundle_id == "5"


def test_bundle_id_none() -> None:
    config = HConfig.from_text(Platform.ARISTA_EOS)
    config.add_child("interface Ethernet1")

    assert _interface_view(config).bundle_id is None


def test_bundle_name() -> None:
    config = HConfig.from_text(Platform.ARISTA_EOS)
    config.add_children_deep(("interface Ethernet1", "channel-group 5 mode active"))

    assert _interface_view(config).bundle_name == "Port-Channel5"


def test_bundle_member_interfaces() -> None:
    config = HConfig.from_text(Platform.ARISTA_EOS)
    config.add_child("interface Port-Channel5")
    config.add_children_deep(("interface Ethernet1", "channel-group 5 mode active"))
    config.add_children_deep(("interface Ethernet2", "channel-group 5 mode active"))
    config.add_children_deep(("interface Ethernet3", "channel-group 6 mode active"))

    interface_view = _interface_view(config, "Port-Channel5")
    assert list(interface_view.bundle_member_interfaces) == ["Ethernet1", "Ethernet2"]


def test_bundle_member_interfaces_not_a_bundle() -> None:
    config = HConfig.from_text(Platform.ARISTA_EOS)
    config.add_child("interface Ethernet1")

    assert not list(_interface_view(config).bundle_member_interfaces)


def test_is_bundle() -> None:
    config = HConfig.from_text(Platform.ARISTA_EOS)
    config.add_child("interface Port-Channel5")
    config.add_child("interface Ethernet1")

    assert _interface_view(config, "Port-Channel5").is_bundle is True
    assert _interface_view(config).is_bundle is False

    view = get_hconfig_view(config)
    assert [iv.name for iv in view.bundle_interface_views] == ["Port-Channel5"]


def test_description() -> None:
    config = HConfig.from_text(Platform.ARISTA_EOS)
    config.add_children_deep(("interface Ethernet1", "description Uplink to Spine"))

    assert _interface_view(config).description == "Uplink to Spine"


def test_description_empty() -> None:
    config = HConfig.from_text(Platform.ARISTA_EOS)
    config.add_child("interface Ethernet1")

    assert not _interface_view(config).description


def test_enabled() -> None:
    config = HConfig.from_text(Platform.ARISTA_EOS)
    config.add_child("interface Ethernet1")
    config.add_children_deep(("interface Ethernet2", "shutdown"))

    assert _interface_view(config).enabled is True
    assert _interface_view(config, "Ethernet2").enabled is False


def test_ipv4_interfaces_cidr() -> None:
    config = HConfig.from_text(Platform.ARISTA_EOS)
    config.add_children_deep(("interface Ethernet1", "ip address 10.1.1.1/24"))

    assert list(_interface_view(config).ipv4_interfaces) == [
        IPv4Interface("10.1.1.1/24")
    ]


def test_ipv4_interfaces_netmask() -> None:
    config = HConfig.from_text(Platform.ARISTA_EOS)
    config.add_children_deep(
        ("interface Ethernet1", "ip address 10.1.1.1 255.255.255.0")
    )

    assert _interface_view(config).ipv4_interface == IPv4Interface("10.1.1.1/24")


def test_ipv4_interfaces_invalid() -> None:
    config = HConfig.from_text(Platform.ARISTA_EOS)
    config.add_children_deep(("interface Ethernet1", "ip address dhcp"))

    assert not list(_interface_view(config).ipv4_interfaces)


def test_is_loopback() -> None:
    config = HConfig.from_text(Platform.ARISTA_EOS)
    config.add_child("interface Loopback0")
    config.add_child("interface Ethernet1")

    assert _interface_view(config, "Loopback0").is_loopback is True
    assert _interface_view(config).is_loopback is False


def test_is_svi() -> None:
    config = HConfig.from_text(Platform.ARISTA_EOS)
    config.add_child("interface Vlan100")
    config.add_child("interface Ethernet1")

    assert _interface_view(config, "Vlan100").is_svi is True
    assert _interface_view(config).is_svi is False


def test_name_and_number() -> None:
    config = HConfig.from_text(Platform.ARISTA_EOS)
    config.add_child("interface Ethernet3/25")

    interface_view = _interface_view(config, "Ethernet3/25")
    assert interface_view.name == "Ethernet3/25"
    assert interface_view.number == "3/25"
    assert interface_view.port_number == 25


def test_subinterface() -> None:
    config = HConfig.from_text(Platform.ARISTA_EOS)
    config.add_child("interface Ethernet1.100")

    interface_view = _interface_view(config, "Ethernet1.100")
    assert interface_view.is_subinterface is True
    assert interface_view.parent_name == "Ethernet1"
    assert interface_view.subinterface_number == 100


def test_native_vlan_subinterface() -> None:
    config = HConfig.from_text(Platform.ARISTA_EOS)
    config.add_children_deep(
        ("interface Ethernet1.100", "encapsulation dot1q vlan 100")
    )

    assert _interface_view(config, "Ethernet1.100").native_vlan == 100


def test_native_vlan_routed_port() -> None:
    config = HConfig.from_text(Platform.ARISTA_EOS)
    config.add_children_deep(("interface Ethernet1", "no switchport"))

    assert _interface_view(config).native_vlan is None


def test_native_vlan_trunk() -> None:
    config = HConfig.from_text(Platform.ARISTA_EOS)
    interface = config.add_child("interface Ethernet1")
    interface.add_child("switchport mode trunk")
    interface.add_child("switchport trunk native vlan 999")

    assert _interface_view(config).native_vlan == 999


def test_native_vlan_trunk_default() -> None:
    config = HConfig.from_text(Platform.ARISTA_EOS)
    config.add_children_deep(("interface Ethernet1", "switchport mode trunk"))

    assert _interface_view(config).native_vlan is None


def test_native_vlan_access() -> None:
    config = HConfig.from_text(Platform.ARISTA_EOS)
    config.add_children_deep(("interface Ethernet1", "switchport access vlan 50"))

    interface_view = _interface_view(config)
    assert interface_view.native_vlan == 50
    assert interface_view.dot1q_mode == InterfaceDot1qMode.ACCESS


def test_native_vlan_default() -> None:
    config = HConfig.from_text(Platform.ARISTA_EOS)
    config.add_child("interface Ethernet1")

    assert _interface_view(config).native_vlan == 1


def test_tagged_all() -> None:
    config = HConfig.from_text(Platform.ARISTA_EOS)
    config.add_children_deep(("interface Ethernet1", "switchport mode trunk"))

    interface_view = _interface_view(config)
    assert interface_view.tagged_all is True
    assert interface_view.dot1q_mode == InterfaceDot1qMode.TAGGED_ALL


def test_tagged_vlans() -> None:
    config = HConfig.from_text(Platform.ARISTA_EOS)
    interface = config.add_child("interface Ethernet1")
    interface.add_child("switchport mode trunk")
    interface.add_child("switchport trunk allowed vlan 10,20,30-32")

    interface_view = _interface_view(config)
    assert interface_view.tagged_vlans == (10, 20, 30, 31, 32)
    assert interface_view.tagged_all is False
    assert interface_view.dot1q_mode == InterfaceDot1qMode.TAGGED


def test_tagged_vlans_empty() -> None:
    config = HConfig.from_text(Platform.ARISTA_EOS)
    config.add_child("interface Ethernet1")

    assert _interface_view(config).tagged_vlans == ()


def test_vrf() -> None:
    config = HConfig.from_text(Platform.ARISTA_EOS)
    config.add_children_deep(("interface Ethernet1", "vrf RED"))
    config.add_children_deep(("interface Ethernet2", "vrf forwarding BLUE"))
    config.add_child("interface Ethernet3")

    assert _interface_view(config).vrf == "RED"
    assert _interface_view(config, "Ethernet2").vrf == "BLUE"
    assert not _interface_view(config, "Ethernet3").vrf


def test_hostname() -> None:
    """Test hostname returns hostname."""
    config = HConfig.from_text(Platform.ARISTA_EOS)
    config.add_child("hostname ARISTA-LEAF-01")

    view = get_hconfig_view(config)
    assert view.hostname == "arista-leaf-01"


def test_hostname_none() -> None:
    """Test hostname returns None."""
    config = HConfig.from_text(Platform.ARISTA_EOS)

    view = get_hconfig_view(config)
    assert view.hostname is None


def test_interface_names_mentioned() -> None:
    config = HConfig.from_text(Platform.ARISTA_EOS)
    config.add_child("interface Ethernet1")
    config.add_child("interface Ethernet2")

    view = get_hconfig_view(config)
    assert view.interface_names_mentioned == frozenset({"Ethernet1", "Ethernet2"})


def test_interface_views() -> None:
    """Test interface_views yields interface views."""
    config = HConfig.from_text(Platform.ARISTA_EOS)
    config.add_child("interface Ethernet1")
    config.add_child("interface Ethernet2")
    config.add_child("interface Management1")

    view = get_hconfig_view(config)
    interface_views = list(view.interface_views)

    assert len(interface_views) == 3


def test_interfaces() -> None:
    """Test interfaces returns interface children."""
    config = HConfig.from_text(Platform.ARISTA_EOS)
    config.add_child("interface Ethernet1")
    config.add_child("interface Ethernet2")

    view = get_hconfig_view(config)
    interfaces = list(view.interfaces)

    assert len(interfaces) == 2


def test_ipv4_default_gw() -> None:
    config = HConfig.from_text(Platform.ARISTA_EOS)
    config.add_child("ip route 0.0.0.0/0 192.0.2.254")

    view = get_hconfig_view(config)
    assert view.ipv4_default_gw == IPv4Address("192.0.2.254")


def test_ipv4_default_gw_none() -> None:
    config = HConfig.from_text(Platform.ARISTA_EOS)

    view = get_hconfig_view(config)
    assert view.ipv4_default_gw is None


def test_location() -> None:
    config = HConfig.from_text(Platform.ARISTA_EOS)
    config.add_child('snmp-server location "Data Center 1"')

    view = get_hconfig_view(config)
    assert view.location == "Data Center 1"


def test_location_empty() -> None:
    config = HConfig.from_text(Platform.ARISTA_EOS)

    view = get_hconfig_view(config)
    assert not view.location


def test_stack_members() -> None:
    """EOS has no stacking, so stack_members is always empty."""
    config = HConfig.from_text(Platform.ARISTA_EOS)

    view = get_hconfig_view(config)
    assert not list(view.stack_members)


def test_vlans() -> None:
    config = HConfig.from_text(Platform.ARISTA_EOS)
    config.add_children_deep(("vlan 10", "name PROD"))
    config.add_child("vlan 20")
    config.add_children_deep(("interface Ethernet1", "switchport access vlan 30"))

    view = get_hconfig_view(config)
    assert list(view.vlans) == [
        Vlan(id=10, name="PROD"),
        Vlan(id=20, name=None),
        Vlan(id=30, name=None),
    ]
    assert view.vlan_ids == frozenset({10, 20, 30})


def test_port_number_on_bundle_interface() -> None:
    """port_number must not crash on slash-less names like Port-Channel10 (#278 review)."""
    config = HConfig.from_text(Platform.ARISTA_EOS, "interface Port-Channel10\n")
    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("Port-Channel10")
    assert interface_view is not None
    assert interface_view.port_number == 10
