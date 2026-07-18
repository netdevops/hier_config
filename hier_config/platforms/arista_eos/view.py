from collections.abc import Iterable
from ipaddress import IPv4Address, IPv4Interface

from hier_config.child import HConfigChild
from hier_config.platforms.functions import parse_ipv4_interface
from hier_config.platforms.view_base import (
    HConfigViewBase,
    InterfaceBundleViewMixin,
    InterfaceVlanViewMixin,
)


class ConfigViewInterfaceAristaEOS(
    InterfaceBundleViewMixin,
    InterfaceVlanViewMixin,
):
    """Interface config view for Arista EOS."""

    _bundle_membership_prefix = "channel-group "
    _encapsulation_prefix = "encapsulation dot1q vlan "

    @property
    def ipv4_interfaces(self) -> Iterable[IPv4Interface]:
        for ipv4_address_obj in self.config.get_children(startswith="ip address "):
            if interface := parse_ipv4_interface(ipv4_address_obj.text.split()[2:]):
                yield interface

    @property
    def vrf(self) -> str:
        if vrf := self.config.get_child(startswith="vrf "):
            words = vrf.text.split()
            return words[2] if words[1] == "forwarding" else words[1]
        return ""

    @property
    def _bundle_prefix(self) -> str:
        return "Port-Channel"


class HConfigViewAristaEOS(HConfigViewBase):
    """Full-tree config view for Arista EOS."""

    @property
    def hostname(self) -> str | None:
        if child := self.config.get_child(startswith="hostname "):
            return child.text.split()[1].lower()
        return None

    @property
    def interface_views(self) -> Iterable[ConfigViewInterfaceAristaEOS]:
        for interface in self.interfaces:
            yield ConfigViewInterfaceAristaEOS(interface)

    @property
    def interfaces(self) -> Iterable[HConfigChild]:
        return self.config.get_children(startswith="interface ")

    @property
    def ipv4_default_gw(self) -> IPv4Address | None:
        if gateway := self.config.get_child(startswith="ip route 0.0.0.0/0 "):
            return IPv4Address(gateway.text.split()[3])
        return None
