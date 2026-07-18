from collections.abc import Iterable
from ipaddress import IPv4Address, IPv4Interface
from re import sub

from hier_config.child import HConfigChild
from hier_config.platforms.functions import expand_range
from hier_config.platforms.models import StackMember, Vlan
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

    @property
    def bundle_id(self) -> str | None:
        if channel_group := self.config.get_child(startswith="channel-group "):
            return channel_group.text.split()[1]
        return None

    @property
    def bundle_member_interfaces(self) -> Iterable[str]:
        if not self.is_bundle:
            return
        for interface in self.config.parent.get_children(startswith="interface "):
            if (
                channel_group := interface.get_child(startswith="channel-group ")
            ) and channel_group.text.split()[1] == self.number:
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
        for ipv4_address_obj in self.config.get_children(startswith="ip address "):
            words = ipv4_address_obj.text.split()
            address = words[2] if "/" in words[2] else "/".join(words[2:4])
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
        # It's configured as a sub-interface
        if self.is_subinterface and (
            vlan := self.config.get_child(startswith="encapsulation dot1q vlan ")
        ):
            return int(vlan.text.split()[3])

        # It's not a switchport
        if (
            self.config.get_child(equals="no switchport")
            or self.config.get_child(startswith="ip address ")
            or self.is_loopback
            or self.is_svi
        ):
            return None

        # It's configured as a trunk
        if self.config.get_child(equals="switchport mode trunk"):
            if vlan := self.config.get_child(
                startswith="switchport trunk native vlan ",
            ):
                return int(vlan.text.split()[4])

            return None

        # It's either dynamic or configured as an access port
        if vlan := self.config.get_child(startswith="switchport access vlan "):
            return int(vlan.text.split()[3])

        # Default VLAN
        return 1

    @property
    def number(self) -> str:
        return sub(r"^[a-zA-Z-]+", "", self.name)

    @property
    def port_number(self) -> int:
        return int(self.name.split("/")[-1].split(".")[0])

    @property
    def tagged_all(self) -> bool:
        return bool(
            self.config.get_child(equals="switchport mode trunk")
            and not self.tagged_vlans,
        )

    @property
    def tagged_vlans(self) -> tuple[int, ...]:
        if child := self.config.get_child(
            re_search="^switchport trunk allowed vlan [0-9,-]+$",
        ):
            return expand_range(child.text.split()[4])
        return ()

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
    def interface_names_mentioned(self) -> frozenset[str]:
        """Returns a set with all the interface names mentioned in the config."""
        return frozenset(model.name for model in self.interface_views)

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

    @property
    def location(self) -> str:
        if location := self.config.get_child(startswith="snmp-server location "):
            return location.text.split(maxsplit=2)[2].replace('"', "")
        return ""

    @property
    def stack_members(self) -> Iterable[StackMember]:
        """Arista EOS does not support stacking."""
        return ()

    @property
    def vlans(self) -> Iterable[Vlan]:
        yielded_vlans: set[int] = set()

        # Yield explicitly defined VLANs
        for child in self.config.get_children(re_search="^vlan [0-9,-]+$"):
            vlan_name = None
            if name := child.get_child(startswith="name "):
                _, vlan_name = name.text.split(maxsplit=1)
                vlan_name = vlan_name.replace('"', "")
            for vlan_id in expand_range(child.text.split()[1]):
                yielded_vlans.add(vlan_id)
                yield Vlan(
                    id=vlan_id,
                    name=vlan_name or None,
                )

        # Yield any remaining unnamed VLANs mentioned on interfaces
        for interface_view in self.interface_views:
            if (
                native_vlan := interface_view.native_vlan
            ) and native_vlan not in yielded_vlans:
                yielded_vlans.add(native_vlan)
                yield Vlan(
                    id=native_vlan,
                    name=None,
                )
