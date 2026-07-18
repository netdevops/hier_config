"""Tests for view_base.py ConfigViewInterfaceBase and HConfigViewBase classes."""

from hier_config import HConfig, Platform, get_hconfig_view
from hier_config.platforms.cisco_ios.view import ConfigViewInterfaceCiscoIOS
from hier_config.platforms.models import InterfaceDot1qMode
from hier_config.platforms.view_base import (
    ConfigViewInterfaceBase,
    HConfigViewBase,
    InterfaceBundleViewMixin,
    InterfaceNACViewMixin,
    InterfacePhysicalViewMixin,
    InterfaceVlanViewMixin,
)


def test_interface_dot1q_mode_tagged() -> None:
    """Test dot1q_mode returns TAGGED (covers view_base.py line 45)."""
    config = HConfig.from_text(Platform.CISCO_IOS)
    config.add_children_deep(("interface GigabitEthernet0/0", "switchport mode trunk"))
    config.add_children_deep(
        ("interface GigabitEthernet0/0", "switchport trunk allowed vlan 10,20")
    )

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert isinstance(interface_view, InterfaceVlanViewMixin)
    assert interface_view.dot1q_mode == InterfaceDot1qMode.TAGGED


def test_interface_dot1q_mode_access() -> None:
    """Test dot1q_mode returns ACCESS (covers view_base.py line 47)."""
    config = HConfig.from_text(Platform.CISCO_IOS)
    config.add_children_deep(
        ("interface GigabitEthernet0/0", "switchport", "switchport mode access")
    )

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert isinstance(interface_view, InterfaceVlanViewMixin)
    assert interface_view.dot1q_mode == InterfaceDot1qMode.ACCESS


def test_interface_dot1q_mode_none() -> None:
    """Test dot1q_mode returns None (covers view_base.py line 49)."""
    config = HConfig.from_text(Platform.CISCO_IOS)
    config.add_children_deep(("interface GigabitEthernet0/0", "no switchport"))

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert isinstance(interface_view, InterfaceVlanViewMixin)
    assert interface_view.dot1q_mode is None


def test_interface_ipv4_interface_none() -> None:
    """Test ipv4_interface returns None when no IP (covers view_base.py line 69)."""
    config = HConfig.from_text(Platform.CISCO_IOS)
    config.add_child("interface GigabitEthernet0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface_view is not None
    assert interface_view.ipv4_interface is None


def test_interface_is_subinterface_true() -> None:
    """Test is_subinterface returns True (covers view_base.py line 89)."""
    config = HConfig.from_text(Platform.CISCO_IOS)
    config.add_child("interface GigabitEthernet0/0.100")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("GigabitEthernet0/0.100")
    assert interface_view is not None
    assert interface_view.is_subinterface is True


def test_hconfig_view_interface_view_by_name_none() -> None:
    """Test interface_view_by_name returns None (covers view_base.py line 221)."""
    config = HConfig.from_text(Platform.CISCO_IOS)
    config.add_child("interface GigabitEthernet0/0")

    view = get_hconfig_view(config)
    interface_view = view.interface_view_by_name("NonExistent0/0")

    assert interface_view is None


def test_hconfig_view_interfaces_names() -> None:
    """Test interfaces_names property (covers view_base.py line 236)."""
    config = HConfig.from_text(Platform.CISCO_IOS)
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
    config = HConfig.from_text(Platform.CISCO_IOS)
    config.add_child("interface Port-channel1")
    config.add_child("interface Loopback0")

    view = get_hconfig_view(config)
    module_numbers = list(view.module_numbers)

    assert len(module_numbers) == 0


def test_hconfig_view_module_numbers_duplicate() -> None:
    """Test module_numbers skips duplicates (covers view_base.py lines 251-252)."""
    config = HConfig.from_text(Platform.CISCO_IOS)
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
    config = HConfig.from_text(Platform.CISCO_IOS)
    config.add_child("interface GigabitEthernet1/0/1")
    config.add_child("interface GigabitEthernet2/0/1")
    config.add_child("interface GigabitEthernet3/0/1")

    view = get_hconfig_view(config)
    module_numbers = list(view.module_numbers)

    assert module_numbers == [1, 2, 3]


def test_hconfig_view_vlan_ids() -> None:
    """Test vlan_ids property (covers view_base.py line 266)."""
    config = HConfig.from_text(Platform.CISCO_IOS)
    config.add_child("vlan 10")
    config.add_child("vlan 20")
    config.add_child("vlan 30")

    view = get_hconfig_view(config)
    vlan_ids = view.vlan_ids

    assert vlan_ids == frozenset({10, 20, 30})


def test_interface_view_abstract_properties_coverage() -> None:
    """Test that abstract properties are defined on the base and the mixins."""
    assert hasattr(ConfigViewInterfaceBase, "description")
    assert hasattr(ConfigViewInterfaceBase, "enabled")
    assert hasattr(ConfigViewInterfaceBase, "ipv4_interfaces")
    assert hasattr(ConfigViewInterfaceBase, "is_loopback")
    assert hasattr(ConfigViewInterfaceBase, "is_svi")
    assert hasattr(ConfigViewInterfaceBase, "name")
    assert hasattr(ConfigViewInterfaceBase, "number")
    assert hasattr(ConfigViewInterfaceBase, "port_number")
    assert hasattr(ConfigViewInterfaceBase, "vrf")

    assert hasattr(InterfaceBundleViewMixin, "bundle_id")
    assert hasattr(InterfaceBundleViewMixin, "bundle_member_interfaces")
    assert hasattr(InterfaceBundleViewMixin, "bundle_name")
    assert hasattr(InterfaceBundleViewMixin, "is_bundle")
    assert hasattr(InterfaceBundleViewMixin, "_bundle_prefix")

    assert hasattr(InterfaceVlanViewMixin, "dot1q_mode")
    assert hasattr(InterfaceVlanViewMixin, "native_vlan")
    assert hasattr(InterfaceVlanViewMixin, "tagged_all")
    assert hasattr(InterfaceVlanViewMixin, "tagged_vlans")

    assert hasattr(InterfaceNACViewMixin, "has_nac")
    assert hasattr(InterfaceNACViewMixin, "nac_control_direction_in")
    assert hasattr(InterfaceNACViewMixin, "nac_host_mode")
    assert hasattr(InterfaceNACViewMixin, "nac_mab_first")
    assert hasattr(InterfaceNACViewMixin, "nac_max_dot1x_clients")
    assert hasattr(InterfaceNACViewMixin, "nac_max_mab_clients")

    assert hasattr(InterfacePhysicalViewMixin, "duplex")
    assert hasattr(InterfacePhysicalViewMixin, "module_number")
    assert hasattr(InterfacePhysicalViewMixin, "poe")
    assert hasattr(InterfacePhysicalViewMixin, "speed")

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


def test_dot1q_mode_from_vlans_tagged_all() -> None:
    """tagged_all wins over any other VLAN data (#228)."""
    view = get_hconfig_view(HConfig.from_text(Platform.CISCO_IOS))
    assert (
        view.dot1q_mode_from_vlans(
            untagged_vlan=10, tagged_vlans=(20,), tagged_all=True
        )
        == InterfaceDot1qMode.TAGGED_ALL
    )


def test_dot1q_mode_from_vlans_tagged() -> None:
    """Explicit tagged VLANs mean TAGGED mode (#228)."""
    view = get_hconfig_view(HConfig.from_text(Platform.CISCO_IOS))
    assert (
        view.dot1q_mode_from_vlans(tagged_vlans=(20, 30)) == InterfaceDot1qMode.TAGGED
    )
    assert (
        view.dot1q_mode_from_vlans(untagged_vlan=10, tagged_vlans=(20, 30))
        == InterfaceDot1qMode.TAGGED
    )


def test_dot1q_mode_from_vlans_access() -> None:
    """An untagged VLAN alone means ACCESS mode (#228)."""
    view = get_hconfig_view(HConfig.from_text(Platform.CISCO_IOS))
    assert view.dot1q_mode_from_vlans(untagged_vlan=10) == InterfaceDot1qMode.ACCESS


def test_dot1q_mode_from_vlans_none() -> None:
    """No VLAN data means no 802.1Q mode (#228)."""
    view = get_hconfig_view(HConfig.from_text(Platform.CISCO_IOS))
    assert view.dot1q_mode_from_vlans() is None


def test_dot1q_mode_from_vlans_available_on_all_views() -> None:
    """Every platform view shares the base implementation (#228)."""
    for platform in (
        Platform.ARISTA_EOS,
        Platform.CISCO_IOS,
        Platform.CISCO_NXOS,
        Platform.CISCO_XR,
        Platform.HP_PROCURVE,
    ):
        view = get_hconfig_view(HConfig.from_text(platform))
        assert view.dot1q_mode_from_vlans(untagged_vlan=1) == InterfaceDot1qMode.ACCESS


def test_bundle_mixin_without_membership_prefix_is_inert() -> None:
    """An unset _bundle_membership_prefix must not match arbitrary children (#278).

    get_child(startswith="") matches any first child, so the defaults must
    short-circuit rather than return garbage for a platform that inherits the
    bundle mixin without declaring its membership command prefix.
    """
    config = HConfig.from_text(
        Platform.CISCO_IOS,
        "interface Port-channel10\n description not-a-bundle-command\n",
    )
    interface = config.get_child(startswith="interface ")
    assert interface is not None

    class PrefixlessBundleView(ConfigViewInterfaceCiscoIOS):
        """IOS view with the membership prefix unset."""

        _bundle_membership_prefix = ""

    view = PrefixlessBundleView(interface)
    assert view.bundle_id is None
    assert not tuple(view.bundle_member_interfaces)
