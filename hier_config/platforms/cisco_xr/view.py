from collections.abc import Iterable
from ipaddress import IPv4Address, IPv4Interface

from hier_config.child import HConfigChild
from hier_config.platforms.functions import parse_ipv4_interface
from hier_config.platforms.view_base import (
    HConfigViewBase,
    InterfaceBundleViewMixin,
    InterfaceVlanViewMixin,
)


class ConfigViewInterfaceCiscoIOSXR(
    InterfaceBundleViewMixin,
    InterfaceVlanViewMixin,
):
    """Interface config view for Cisco IOS XR.

    IOS XR has no switchports, so the VLAN view only reports sub-interface
    dot1q encapsulations; ``tagged_all`` is always False and ``tagged_vlans``
    is always empty.
    """

    _bundle_membership_prefix = "bundle id "

    @property
    def ipv4_interfaces(self) -> Iterable[IPv4Interface]:
        for ipv4_address_obj in self.config.get_children(startswith="ipv4 address "):
            if interface := parse_ipv4_interface(ipv4_address_obj.text.split()[2:]):
                yield interface

    @property
    def native_vlan(self) -> int | None:
        # VLANs only exist on sub-interfaces (e.g. `encapsulation dot1q 100`)
        if self.is_subinterface and (
            vlan := self.config.get_child(startswith="encapsulation dot1q ")
        ):
            return int(vlan.text.split()[2])
        return None

    @property
    def vrf(self) -> str:
        if vrf := self.config.get_child(startswith="vrf "):
            return vrf.text.split()[1]
        return ""

    @property
    def _bundle_prefix(self) -> str:
        return "Bundle-Ether"


class HConfigViewCiscoIOSXR(HConfigViewBase):
    """Full-tree config view for Cisco IOS XR.

    VLANs are derived from sub-interface encapsulations; IOS XR does not
    support stacking.
    """

    @property
    def hostname(self) -> str | None:
        if child := self.config.get_child(startswith="hostname "):
            return child.text.split()[1].lower()
        return None

    @property
    def interface_views(self) -> Iterable[ConfigViewInterfaceCiscoIOSXR]:
        for interface in self.interfaces:
            yield ConfigViewInterfaceCiscoIOSXR(interface)

    @property
    def interfaces(self) -> Iterable[HConfigChild]:
        return self.config.get_children(startswith="interface ")

    @property
    def ipv4_default_gw(self) -> IPv4Address | None:
        if (
            (router_static := self.config.get_child(equals="router static"))
            and (
                address_family := router_static.get_child(
                    equals="address-family ipv4 unicast",
                )
            )
            and (route := address_family.get_child(startswith="0.0.0.0/0 "))
        ):
            return IPv4Address(route.text.split()[1])
        return None
