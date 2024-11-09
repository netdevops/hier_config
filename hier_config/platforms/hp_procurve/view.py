from __future__ import annotations

import re
from collections.abc import Iterable
from ipaddress import AddressValueError, IPv4Address, IPv4Interface

from hier_config.child import HConfigChild
from hier_config.platforms.functions import expand_range
from hier_config.platforms.hp_procurve.functions import hp_procurve_expand_range
from hier_config.platforms.model import (
    InterfaceDot1qMode,
    InterfaceDuplex,
    NACHostMode,
    StackMember,
    Vlan,
)
from hier_config.platforms.view_base import (
    ConfigViewInterfaceBase,
    HConfigViewBase,
)


class HConfigViewHPProcurve(HConfigViewBase):
    def dot1q_mode_from_vlans(
        self,
        untagged_vlan: int | None = None,
        tagged_vlans: tuple[int, ...] = (),
        *,
        tagged_all: bool = False,
    ) -> InterfaceDot1qMode | None:
        raise NotImplementedError

    @property
    def hostname(self) -> str | None:
        if child := self.config.get_child(startswith="hostname "):
            return child.text.split()[1].lower().replace('"', "")
        return None

    @property
    def interface_names_mentioned(self) -> frozenset[str]:
        interfaces = {model.name for model in self.interface_views}

        for child in self.config.children:
            text = child.text_without_negation
            words = text.split()
            if text.startswith("aaa port-access "):
                found = (
                    words[3] if words[2] in {"authenticator", "mac-based"} else words[2]
                )

                if re.search(r"^(\d+|\d+/\d+)$", found):
                    interfaces.add(found)

        return frozenset(interfaces)

    @property
    def interface_views(self) -> Iterable[ConfigViewInterfaceHPProcurve]:
        for interface in self.interfaces:
            yield ConfigViewInterfaceHPProcurve(interface)
        for vlan in self.config.get_children(startswith="vlan "):
            if vlan.get_child(startswith="ip address "):
                yield ConfigViewInterfaceHPProcurve(vlan)

    @property
    def interfaces(self) -> Iterable[HConfigChild]:
        return self.config.get_children(startswith="interface ")

    @property
    def ipv4_default_gw(self) -> IPv4Address | None:
        if gateway := self.config.get_child(startswith="ip default-gateway "):
            return IPv4Address(gateway.text.split()[2])
        return None

    @property
    def location(self) -> str:
        if location := self.config.get_child(startswith="snmp-server location "):
            return location.text.split(maxsplit=2)[2].replace('"', "")
        return ""

    @property
    def stack_members(self) -> Iterable[StackMember]:
        """
        stacking
           member 1 type "JL123" mac-address abc123-abc123
           member 1 priority 255
           member 2 type "JL123" mac-address abc123-abc123
           member 2 priority 254
           ...
        """
        stacking = self.config.get_child(equals="stacking")
        if not stacking:
            return

        for member in stacking.get_children(startswith="member"):
            words = member.text.split()
            if words[2] == "type":
                member_id = int(words[1])
                yield StackMember(
                    member_id, 256 - member_id, words[5], words[3].replace('"', "")
                )

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
            for vlan_id in interface_view.tagged_vlans:
                if vlan_id not in yielded_vlans:
                    yielded_vlans.add(vlan_id)
                    yield Vlan(
                        id=vlan_id,
                        name=None,
                    )
            if (
                native_vlan := interface_view.native_vlan
            ) and native_vlan not in yielded_vlans:
                yielded_vlans.add(native_vlan)
                yield Vlan(
                    id=native_vlan,
                    name=None,
                )


class ConfigViewInterfaceHPProcurve(  # noqa: PLR0904 pylint: disable=abstract-method
    ConfigViewInterfaceBase
):
    @property
    def bundle_id(self) -> str | None:
        raise NotImplementedError

    @property
    def bundle_member_interfaces(self) -> Iterable[str]:
        # trunk 1/45,2/45 trk1 trunk
        bundle = self.config.parent.get_child(
            re_search=rf"^trunk .* {self.name.lower()} (trunk|lacp)$"
        )
        if self.is_bundle and bundle is None:
            message = (
                f"Interface is a bundle but bundle config was not found: {self.name}"
            )
            raise TypeError(message)
        if bundle is None:
            message = f"The bundle config line couldn't be found: {self.name}"
            raise ValueError(message)
        return hp_procurve_expand_range(bundle.text.split()[1])

    @property
    def bundle_name(self) -> str | None:
        for bundle_def in self.config.parent.get_children(startswith="trunk "):
            interface_range = bundle_def.text.split()[1]
            interfaces = hp_procurve_expand_range(interface_range)
            if self.name in interfaces:
                # Capitalizing the interface name is consistent with 1/A1 interface naming
                # and is consistent with references under `vlan 10/n  tagged Trk1`
                return bundle_def.text.split()[2].capitalize()
        return None

    @property
    def description(self) -> str:
        if child := self.config.get_child(startswith="name "):
            return child.text.split(maxsplit=1)[1].replace('"', "")
        return ""

    @property
    def duplex(self) -> InterfaceDuplex:
        if duplex := self.config.get_child(startswith="speed-duplex "):
            return _duplex_from_speed_duplex(duplex.text)
        return InterfaceDuplex.AUTO

    @property
    def enabled(self) -> bool:
        return not self.config.get_child(equals="disable")

    @property
    def has_nac(self) -> bool:
        """Determine if the interface has NAC configured."""
        return any(
            line in self.config.parent.children_dict
            for line in (
                f"aaa port-access authenticator {self.name}",
                f"aaa port-access mac-based {self.name}",
            )
        )

    @property
    def ipv4_interface(self) -> IPv4Interface | None:
        return next(iter(self.ipv4_interfaces), None)

    @property
    def ipv4_interfaces(self) -> Iterable[IPv4Interface]:
        for ipv4_address_obj in self.config.get_children(startswith="ip address "):
            ipv4_address = ipv4_address_obj.text.split()
            try:
                yield IPv4Interface("/".join(ipv4_address[2:4]))
            except AddressValueError:
                continue
                # message = f"{self.name} does not a have a valid IPv4 Address: {ipv4_address_obj.text}"
                # raise

    @property
    def is_bundle(self) -> bool:
        return self.name.lower().startswith(self._bundle_prefix)

    @property
    def is_loopback(self) -> bool:
        return self.name.lower().startswith("loopback")

    @property
    def is_subinterface(self) -> bool:
        return "." in self.name

    @property
    def is_svi(self) -> bool:
        return self.name.lower().startswith("vlan")

    @property
    def module_number(self) -> int | None:
        words = self.number.split("/", 1)
        if len(words) == 1:
            return None
        return int(words[0])

    @property
    def nac_control_direction_in(self) -> bool:
        """Determine if the interface has NAC control direction in configured."""
        return (
            f"aaa port-access {self.name} controlled-direction in"
            in self.config.parent.children_dict
        )

    @property
    def nac_host_mode(self) -> NACHostMode | None:
        """Determine the NAC host mode."""
        # hp_procurve does not support host mode
        return None

    @property
    def nac_mab_first(self) -> bool:
        """Determine if the interface has NAC configured for MAB first."""
        return bool(
            self.config.parent.get_child(
                equals=f"aaa port-access {self.name} auth-order mac-based authenticator",
            )
        )

    @property
    def nac_max_dot1x_clients(self) -> int:
        """Determine the max dot1x clients."""
        if child := self.config.parent.get_child(
            startswith=f"aaa port-access authenticator {self.name} client-limit "
        ):
            return int(child.text.split()[5])
        return 1

    @property
    def nac_max_mab_clients(self) -> int:
        """Determine the max mab clients."""
        if child := self.config.parent.get_child(
            startswith=f"aaa port-access mac-based {self.name} addr-limit "
        ):
            return int(child.text.split()[5])
        return 1

    @property
    def name(self) -> str:
        if self.config.text.startswith("interface "):
            return self.config.text.split()[1]
        return self.config.text

    @property
    def native_vlan(self) -> int | None:
        if vlan := self.config.get_child(startswith="untagged vlan "):
            return int(vlan.text.split()[2])
        return None

    @property
    def number(self) -> str:
        return re.sub("^[a-zA-Z-]+", "", self.name)

    @property
    def parent_name(self) -> str | None:
        if self.is_subinterface:
            return self.name.split(".")[0]
        return None

    @property
    def poe(self) -> bool:
        return not self.config.get_child(equals="no power-over-ethernet")

    @property
    def port_number(self) -> int:
        return int(self.name.split("/")[-1].split(".")[0])

    @property
    def speed(self) -> tuple[int, ...] | None:
        if speed := self.config.get_child(startswith="speed-duplex "):
            return _speed_from_speed_duplex(speed.text)
        return None

    @property
    def subinterface_number(self) -> int | None:
        return int(self.name.split(".")[0 - 1]) if self.is_subinterface else None

    @property
    def tagged_all(self) -> bool:
        return False

    @property
    def tagged_vlans(self) -> tuple[int, ...]:
        return tuple(
            int(c.text.split()[2])
            for c in self.config.get_children(startswith="tagged vlan ")
        )

    @property
    def vrf(self) -> str:
        return ""

    @property
    def _bundle_prefix(self) -> str:
        return "trk"


def _speed_from_speed_duplex(speed_duplex: str) -> tuple[int, ...] | None:
    if speed_duplex.startswith("10"):
        return (int(speed_duplex.split("-")[0]),)
    if speed_duplex.startswith("auto-"):
        return tuple(int(s) for s in speed_duplex.replace("auto-", "").split("-"))
    return None


def _duplex_from_speed_duplex(speed_duplex: str) -> InterfaceDuplex:
    if speed_duplex.startswith("auto"):
        return InterfaceDuplex(speed_duplex[:4])
    if speed_duplex.endswith("half") | speed_duplex.endswith("full"):
        return InterfaceDuplex(speed_duplex[-4:])
    return InterfaceDuplex(speed_duplex)
