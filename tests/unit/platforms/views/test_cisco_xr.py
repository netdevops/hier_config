"""Tests for Cisco IOS-XR view.py ConfigViewInterfaceCiscoIOSXR and HConfigViewCiscoIOSXR classes."""

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
from hier_config.platforms.cisco_xr.view import ConfigViewInterfaceCiscoIOSXR
from hier_config.platforms.models import Vlan


def _interface_view(
    config: HConfig, name: str = "GigabitEthernet0/0/0/1"
) -> ConfigViewInterfaceCiscoIOSXR:
    interface_view = get_hconfig_view(config).interface_view_by_name(name)
    assert isinstance(interface_view, ConfigViewInterfaceCiscoIOSXR)
    return interface_view


def test_capabilities() -> None:
    """IOS XR interface views support bundles and VLANs but not NAC or physical."""
    config = HConfig.from_text(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/1")

    interface_view = _interface_view(config)
    assert isinstance(interface_view, InterfaceBundleViewMixin)
    assert isinstance(interface_view, InterfaceVlanViewMixin)
    assert not isinstance(interface_view, InterfaceNACViewMixin)
    assert not isinstance(interface_view, InterfacePhysicalViewMixin)


def test_bundle_id() -> None:
    config = HConfig.from_text(Platform.CISCO_XR)
    config.add_children_deep(
        ("interface GigabitEthernet0/0/0/1", "bundle id 42 mode active")
    )

    assert _interface_view(config).bundle_id == "42"


def test_bundle_id_none() -> None:
    config = HConfig.from_text(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/1")

    assert _interface_view(config).bundle_id is None


def test_bundle_name() -> None:
    config = HConfig.from_text(Platform.CISCO_XR)
    config.add_children_deep(
        ("interface GigabitEthernet0/0/0/1", "bundle id 42 mode active")
    )

    assert _interface_view(config).bundle_name == "Bundle-Ether42"


def test_bundle_name_none() -> None:
    config = HConfig.from_text(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/1")

    assert _interface_view(config).bundle_name is None


def test_bundle_member_interfaces() -> None:
    config = HConfig.from_text(Platform.CISCO_XR)
    config.add_child("interface Bundle-Ether42")
    config.add_children_deep(
        ("interface GigabitEthernet0/0/0/1", "bundle id 42 mode active")
    )
    config.add_children_deep(
        ("interface GigabitEthernet0/0/0/2", "bundle id 42 mode active")
    )
    config.add_children_deep(
        ("interface GigabitEthernet0/0/0/3", "bundle id 43 mode active")
    )

    interface_view = _interface_view(config, "Bundle-Ether42")
    assert list(interface_view.bundle_member_interfaces) == [
        "GigabitEthernet0/0/0/1",
        "GigabitEthernet0/0/0/2",
    ]


def test_bundle_member_interfaces_not_a_bundle() -> None:
    config = HConfig.from_text(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/1")

    assert not list(_interface_view(config).bundle_member_interfaces)


def test_is_bundle() -> None:
    config = HConfig.from_text(Platform.CISCO_XR)
    config.add_child("interface Bundle-Ether42")
    config.add_child("interface GigabitEthernet0/0/0/1")

    assert _interface_view(config, "Bundle-Ether42").is_bundle is True
    assert _interface_view(config).is_bundle is False

    view = get_hconfig_view(config)
    assert [iv.name for iv in view.bundle_interface_views] == ["Bundle-Ether42"]


def test_description() -> None:
    """Test description returns description text."""
    config = HConfig.from_text(Platform.CISCO_XR)
    config.add_children_deep(("interface GigabitEthernet0/0/0/1", "description Uplink"))

    assert _interface_view(config).description == "Uplink"


def test_description_empty() -> None:
    """Test description returns empty string."""
    config = HConfig.from_text(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/1")

    assert not _interface_view(config).description


def test_enabled() -> None:
    config = HConfig.from_text(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/1")
    config.add_children_deep(("interface GigabitEthernet0/0/0/2", "shutdown"))

    assert _interface_view(config).enabled is True
    assert _interface_view(config, "GigabitEthernet0/0/0/2").enabled is False


def test_ipv4_interfaces_netmask() -> None:
    config = HConfig.from_text(Platform.CISCO_XR)
    config.add_children_deep(
        ("interface GigabitEthernet0/0/0/1", "ipv4 address 10.1.1.1 255.255.255.0")
    )

    assert list(_interface_view(config).ipv4_interfaces) == [
        IPv4Interface("10.1.1.1/24")
    ]


def test_ipv4_interfaces_cidr() -> None:
    config = HConfig.from_text(Platform.CISCO_XR)
    config.add_children_deep(
        ("interface GigabitEthernet0/0/0/1", "ipv4 address 10.1.1.1/24")
    )

    assert _interface_view(config).ipv4_interface == IPv4Interface("10.1.1.1/24")


def test_ipv4_interfaces_cidr_with_space() -> None:
    config = HConfig.from_text(Platform.CISCO_XR)
    config.add_children_deep(
        ("interface GigabitEthernet0/0/0/1", "ipv4 address 10.1.1.1 /24")
    )

    assert _interface_view(config).ipv4_interface == IPv4Interface("10.1.1.1/24")


def test_ipv4_interfaces_invalid() -> None:
    config = HConfig.from_text(Platform.CISCO_XR)
    config.add_children_deep(("interface GigabitEthernet0/0/0/1", "ipv4 address dhcp"))

    assert not list(_interface_view(config).ipv4_interfaces)


def test_is_loopback() -> None:
    config = HConfig.from_text(Platform.CISCO_XR)
    config.add_child("interface Loopback0")
    config.add_child("interface GigabitEthernet0/0/0/1")

    assert _interface_view(config, "Loopback0").is_loopback is True
    assert _interface_view(config).is_loopback is False


def test_is_svi() -> None:
    config = HConfig.from_text(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/1")

    assert _interface_view(config).is_svi is False


def test_name_and_number() -> None:
    config = HConfig.from_text(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/1/2/3")

    interface_view = _interface_view(config, "GigabitEthernet0/1/2/3")
    assert interface_view.name == "GigabitEthernet0/1/2/3"
    assert interface_view.number == "0/1/2/3"
    assert interface_view.port_number == 3


def test_subinterface() -> None:
    config = HConfig.from_text(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/1.100")
    config.add_child("interface GigabitEthernet0/0/0/1")

    subinterface_view = _interface_view(config, "GigabitEthernet0/0/0/1.100")
    assert subinterface_view.is_subinterface is True
    assert subinterface_view.parent_name == "GigabitEthernet0/0/0/1"
    assert subinterface_view.subinterface_number == 100

    interface_view = _interface_view(config)
    assert interface_view.is_subinterface is False
    assert interface_view.parent_name is None
    assert interface_view.subinterface_number is None


def test_native_vlan_subinterface() -> None:
    config = HConfig.from_text(Platform.CISCO_XR)
    config.add_children_deep(
        ("interface GigabitEthernet0/0/0/1.100", "encapsulation dot1q 100")
    )

    assert _interface_view(config, "GigabitEthernet0/0/0/1.100").native_vlan == 100


def test_native_vlan_none() -> None:
    config = HConfig.from_text(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/1")

    assert _interface_view(config).native_vlan is None


def test_tagged_all_and_tagged_vlans() -> None:
    """IOS XR interfaces never carry switchport-style tagged VLANs."""
    config = HConfig.from_text(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/1")

    interface_view = _interface_view(config)
    assert interface_view.tagged_all is False
    assert interface_view.tagged_vlans == ()
    assert interface_view.dot1q_mode is None


def test_vrf() -> None:
    config = HConfig.from_text(Platform.CISCO_XR)
    config.add_children_deep(("interface GigabitEthernet0/0/0/1", "vrf RED"))
    config.add_child("interface GigabitEthernet0/0/0/2")

    assert _interface_view(config).vrf == "RED"
    assert not _interface_view(config, "GigabitEthernet0/0/0/2").vrf


def test_hostname() -> None:
    """Test hostname returns hostname."""
    config = HConfig.from_text(Platform.CISCO_XR)
    config.add_child("hostname XR-PE-01")

    view = get_hconfig_view(config)
    assert view.hostname == "xr-pe-01"


def test_hostname_none() -> None:
    """Test hostname returns None."""
    config = HConfig.from_text(Platform.CISCO_XR)

    view = get_hconfig_view(config)
    assert view.hostname is None


def test_interface_names_mentioned() -> None:
    config = HConfig.from_text(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/1")
    config.add_child("interface Bundle-Ether42")

    view = get_hconfig_view(config)
    assert view.interface_names_mentioned == frozenset(
        {"GigabitEthernet0/0/0/1", "Bundle-Ether42"}
    )


def test_interface_views() -> None:
    """Test interface_views yields interface views."""
    config = HConfig.from_text(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/1")
    config.add_child("interface GigabitEthernet0/0/0/2")
    config.add_child("interface Loopback0")

    view = get_hconfig_view(config)
    interface_views = list(view.interface_views)

    assert len(interface_views) == 3


def test_interfaces() -> None:
    """Test interfaces returns interface children."""
    config = HConfig.from_text(Platform.CISCO_XR)
    config.add_child("interface GigabitEthernet0/0/0/1")
    config.add_child("interface GigabitEthernet0/0/0/2")

    view = get_hconfig_view(config)
    interfaces = list(view.interfaces)

    assert len(interfaces) == 2


def test_ipv4_default_gw() -> None:
    config = HConfig.from_text(Platform.CISCO_XR)
    config.add_children_deep(
        (
            "router static",
            "address-family ipv4 unicast",
            "0.0.0.0/0 192.0.2.254",
        )
    )

    view = get_hconfig_view(config)
    assert view.ipv4_default_gw == IPv4Address("192.0.2.254")


def test_ipv4_default_gw_none() -> None:
    config = HConfig.from_text(Platform.CISCO_XR)

    view = get_hconfig_view(config)
    assert view.ipv4_default_gw is None


def test_ipv4_default_gw_none_without_default_route() -> None:
    config = HConfig.from_text(Platform.CISCO_XR)
    config.add_children_deep(
        (
            "router static",
            "address-family ipv4 unicast",
            "10.0.0.0/8 192.0.2.1",
        )
    )

    view = get_hconfig_view(config)
    assert view.ipv4_default_gw is None


def test_location() -> None:
    config = HConfig.from_text(Platform.CISCO_XR)
    config.add_child('snmp-server location "Data Center 1"')

    view = get_hconfig_view(config)
    assert view.location == "Data Center 1"


def test_location_empty() -> None:
    config = HConfig.from_text(Platform.CISCO_XR)

    view = get_hconfig_view(config)
    assert not view.location


def test_stack_members() -> None:
    """IOS XR has no stacking, so stack_members is always empty."""
    config = HConfig.from_text(Platform.CISCO_XR)

    view = get_hconfig_view(config)
    assert not list(view.stack_members)


def test_vlans() -> None:
    """VLANs are derived from sub-interface encapsulations."""
    config = HConfig.from_text(Platform.CISCO_XR)
    config.add_children_deep(
        ("interface GigabitEthernet0/0/0/1.100", "encapsulation dot1q 100")
    )
    config.add_children_deep(
        ("interface GigabitEthernet0/0/0/1.200", "encapsulation dot1q 200")
    )
    config.add_children_deep(
        ("interface GigabitEthernet0/0/0/2.100", "encapsulation dot1q 100")
    )

    view = get_hconfig_view(config)
    assert list(view.vlans) == [
        Vlan(id=100, name=None),
        Vlan(id=200, name=None),
    ]
    assert view.vlan_ids == frozenset({100, 200})
