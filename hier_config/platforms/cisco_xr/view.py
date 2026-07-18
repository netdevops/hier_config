from collections.abc import Iterable
from ipaddress import IPv4Address, IPv4Interface
from re import sub

from hier_config.child import HConfigChild
from hier_config.platforms.models import StackMember, Vlan
from hier_config.platforms.view_base import (
    HConfigViewBase,
    InterfaceBundleViewMixin,
    InterfaceVlanViewMixin,
)


class ConfigViewInterfaceCiscoIOSXR(
    InterfaceBundleViewMixin,
    InterfaceVlanViewMixin,
):
    """Interface config view for Cisco IOS XR."""

    @property
    def bundle_id(self) -> str | None:
        if bundle := self.config.get_child(startswith="bundle id "):
            return bundle.text.split()[2]
        return None

    @property
    def bundle_member_interfaces(self) -> Iterable[str]:
        if not self.is_bundle:
            return
        for interface in self.config.parent.get_children(startswith="interface "):
            if (
                bundle := interface.get_child(startswith="bundle id ")
            ) and bundle.text.split()[2] == self.number:
                yield interface.text.split()[1]

    @property
    def description(self) -> str:
        if child := self.config.get_child(startswith="description "):
            return child.text.split(maxsplit=1)[1]
        return ""

    @property
    def enabled(self) -> bool:
        return not self.config.get_child(equals="shutdown")

    @property
    def ipv4_interfaces(self) -> Iterable[IPv4Interface]:
        for ipv4_address_obj in self.config.get_children(startswith="ipv4 address "):
            words = ipv4_address_obj.text.split()[2:]
            if len(words) == 1:
                # ipv4 address x.x.x.x/nn
                address = words[0]
            elif words[1].startswith("/"):
                # ipv4 address x.x.x.x /nn
                address = f"{words[0]}{words[1]}"
            else:
                # ipv4 address x.x.x.x y.y.y.y
                address = f"{words[0]}/{words[1]}"
            try:
                yield IPv4Interface(address)
            except ValueError:
                continue

    @property
    def is_loopback(self) -> bool:
        return self.name.lower().startswith("loopback")

    @property
    def is_svi(self) -> bool:
        return self.name.lower().startswith("vlan")

    @property
    def name(self) -> str:
        return self.config.text.split()[1]

    @property
    def native_vlan(self) -> int | None:
        # VLANs only exist on sub-interfaces (e.g. `encapsulation dot1q 100`)
        if self.is_subinterface and (
            vlan := self.config.get_child(startswith="encapsulation dot1q ")
        ):
            return int(vlan.text.split()[2])
        return None

    @property
    def number(self) -> str:
        return sub(r"^[a-zA-Z-]+", "", self.name)

    @property
    def port_number(self) -> int:
        return int(self.name.split("/")[-1].split(".")[0])

    @property
    def tagged_all(self) -> bool:
        """Cisco IOS XR has no switchports; interfaces never tag all VLANs."""
        return False

    @property
    def tagged_vlans(self) -> tuple[int, ...]:
        """Cisco IOS XR has no switchports; interfaces carry no tagged VLANs."""
        return ()

    @property
    def vrf(self) -> str:
        if vrf := self.config.get_child(startswith="vrf "):
            return vrf.text.split()[1]
        return ""

    @property
    def _bundle_prefix(self) -> str:
        return "Bundle-Ether"


class HConfigViewCiscoIOSXR(HConfigViewBase):
    """Full-tree config view for Cisco IOS XR."""

    @property
    def hostname(self) -> str | None:
        if child := self.config.get_child(startswith="hostname "):
            return child.text.split()[1].lower()
        return None

    @property
    def interface_names_mentioned(self) -> frozenset[str]:
        """Returns a set with all the interface names mentioned in the config."""
        return frozenset(model.name for model in self.interface_views)

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

    @property
    def location(self) -> str:
        if location := self.config.get_child(startswith="snmp-server location "):
            return location.text.split(maxsplit=2)[2].replace('"', "")
        return ""

    @property
    def stack_members(self) -> Iterable[StackMember]:
        """Cisco IOS XR does not support stacking."""
        return ()

    @property
    def vlans(self) -> Iterable[Vlan]:
        """Yield the VLANs encapsulated on sub-interfaces."""
        yielded_vlans: set[int] = set()
        for interface_view in self.interface_views:
            if (
                native_vlan := interface_view.native_vlan
            ) and native_vlan not in yielded_vlans:
                yielded_vlans.add(native_vlan)
                yield Vlan(
                    id=native_vlan,
                    name=None,
                )
