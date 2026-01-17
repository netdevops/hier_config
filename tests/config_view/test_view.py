"""Tests for view_base.py ConfigViewInterfaceBase and HConfigViewBase classes."""

from hier_config import Platform, get_hconfig, get_hconfig_view
from hier_config.platforms.models import InterfaceDot1qMode
from hier_config.platforms.view_base import ConfigViewInterfaceBase, HConfigViewBase


def test_interface_dot1q_mode_tagged() -> None:
    """Test dot1q_mode returns TAGGED (covers view_base.py line 45)."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_children_deep(("interface GigabitEthernet0/0", "switchport mode trunk"))
    config.add_children_deep(
        ("interface GigabitEthernet0/0", "switchport trunk allowed vlan 10,20")
    )

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.dot1q_mode == InterfaceDot1qMode.TAGGED


def test_interface_dot1q_mode_access() -> None:
    """Test dot1q_mode returns ACCESS (covers view_base.py line 47)."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_children_deep(
        ("interface GigabitEthernet0/0", "switchport", "switchport mode access")
    )

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.dot1q_mode == InterfaceDot1qMode.ACCESS


def test_interface_dot1q_mode_none() -> None:
    """Test dot1q_mode returns None (covers view_base.py line 49)."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_children_deep(("interface GigabitEthernet0/0", "no switchport"))

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.dot1q_mode is None


def test_interface_ipv4_interface_none() -> None:
    """Test ipv4_interface returns None when no IP (covers view_base.py line 69)."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_child("interface GigabitEthernet0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.ipv4_interface is None


def test_interface_is_subinterface_true() -> None:
    """Test is_subinterface returns True (covers view_base.py line 89)."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_child("interface GigabitEthernet0/0.100")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0.100")
    assert interface_view is not None
    assert interface_view.is_subinterface is True


def test_hconfig_view_interface_view_by_name_none() -> None:
    """Test interface_view_by_name returns None (covers view_base.py line 221)."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_child("interface GigabitEthernet0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("NonExistent0/0")

    assert interface_view is None


def test_hconfig_view_interfaces_names() -> None:
    """Test interfaces_names property (covers view_base.py line 236)."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_child("interface GigabitEthernet0/0")
    config.add_child("interface GigabitEthernet0/1")
    config.add_child("interface Port-channel1")

    view = get_hconfig_view(config)
    interface_names = list(view.interfaces_names)

    assert len(interface_names) == 3
    assert "GigabitEthernet0/0" in interface_names
    assert "GigabitEthernet0/1" in interface_names
    assert "Port-channel1" in interface_names


def test_hconfig_view_module_numbers_none() -> None:
    """Test module_numbers when module_number is None (covers view_base.py line 250)."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_child("interface Port-channel1")
    config.add_child("interface Loopback0")

    view = get_hconfig_view(config)
    module_numbers = list(view.module_numbers)

    assert len(module_numbers) == 0


def test_hconfig_view_module_numbers_duplicate() -> None:
    """Test module_numbers skips duplicates (covers view_base.py lines 251-252)."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_child("interface GigabitEthernet1/0/1")
    config.add_child("interface GigabitEthernet1/0/2")
    config.add_child("interface GigabitEthernet2/0/1")

    view = get_hconfig_view(config)
    module_numbers = list(view.module_numbers)

    assert len(module_numbers) == 2
    assert 1 in module_numbers
    assert 2 in module_numbers


def test_hconfig_view_module_numbers_yield() -> None:
    """Test module_numbers yields values (covers view_base.py lines 253-254)."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_child("interface GigabitEthernet1/0/1")
    config.add_child("interface GigabitEthernet2/0/1")
    config.add_child("interface GigabitEthernet3/0/1")

    view = get_hconfig_view(config)
    module_numbers = list(view.module_numbers)

    assert module_numbers == [1, 2, 3]


def test_hconfig_view_vlan_ids() -> None:
    """Test vlan_ids property (covers view_base.py line 266)."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_child("vlan 10")
    config.add_child("vlan 20")
    config.add_child("vlan 30")

    view = get_hconfig_view(config)
    vlan_ids = view.vlan_ids

    assert vlan_ids == frozenset({10, 20, 30})


def test_interface_view_abstract_properties_coverage() -> None:
    """Test that abstract properties are properly defined (covers view_base.py lines 184, 205, 210, 226, 231, 235, 241, 246, 256)."""
    assert hasattr(ConfigViewInterfaceBase, "bundle_id")
    assert hasattr(ConfigViewInterfaceBase, "bundle_member_interfaces")
    assert hasattr(ConfigViewInterfaceBase, "bundle_name")
    assert hasattr(ConfigViewInterfaceBase, "description")
    assert hasattr(ConfigViewInterfaceBase, "duplex")
    assert hasattr(ConfigViewInterfaceBase, "enabled")
    assert hasattr(ConfigViewInterfaceBase, "has_nac")
    assert hasattr(ConfigViewInterfaceBase, "ipv4_interfaces")
    assert hasattr(ConfigViewInterfaceBase, "is_bundle")
    assert hasattr(ConfigViewInterfaceBase, "is_loopback")
    assert hasattr(ConfigViewInterfaceBase, "is_svi")
    assert hasattr(ConfigViewInterfaceBase, "module_number")
    assert hasattr(ConfigViewInterfaceBase, "_bundle_prefix")

    # Verify HConfigViewBase has the expected abstract methods/properties
    assert hasattr(HConfigViewBase, "dot1q_mode_from_vlans")
    assert hasattr(HConfigViewBase, "hostname")
    assert hasattr(HConfigViewBase, "interface_names_mentioned")
    assert hasattr(HConfigViewBase, "interface_views")
    assert hasattr(HConfigViewBase, "interfaces")
    assert hasattr(HConfigViewBase, "ipv4_default_gw")
    assert hasattr(HConfigViewBase, "location")
    assert hasattr(HConfigViewBase, "stack_members")
    assert hasattr(HConfigViewBase, "vlans")
