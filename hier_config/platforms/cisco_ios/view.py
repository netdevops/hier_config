from collections.abc import Iterable
from ipaddress import AddressValueError, IPv4Address, IPv4Interface
from re import sub
from typing import Optional

from hier_config.child import HConfigChild
from hier_config.platforms.functions import expand_range
from hier_config.platforms.models import (
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


class ConfigViewInterfaceCiscoIOS(ConfigViewInterfaceBase):  # noqa: PLR0904
    @property
    def bundle_id(self) -> Optional[str]:
        if channel_group := self.config.get_child(startswith="channel-group"):
            return channel_group.text.split()[1]
        return None

    @property
    def bundle_member_interfaces(self) -> Iterable[str]:
        raise NotImplementedError

    @property
    def bundle_name(self) -> Optional[str]:
        if self.bundle_id:
            return f"{self._bundle_prefix}{self.bundle_id}"
        return None

    @property
    def description(self) -> str:
        if child := self.config.get_child(startswith="description "):
            return child.text.split(maxsplit=1)[1]
        return ""

    @property
    def duplex(self) -> InterfaceDuplex:
        if duplex := self.config.get_child(startswith="duplex "):
            return InterfaceDuplex(duplex.text.split()[1])
        return InterfaceDuplex.AUTO

    @property
    def enabled(self) -> bool:
        return not self.config.get_child(equals="shutdown")

    @property
    def has_nac(self) -> bool:
        return any(
            line in self.config.children
            for line in (
                "authentication port-control auto",
                "mab",
            )
        )

    @property
    def ipv4_interface(self) -> Optional[IPv4Interface]:
        return next(iter(self.ipv4_interfaces), None)

    @property
    def ipv4_interfaces(self) -> Iterable[IPv4Interface]:
        for ipv4_address_obj in self.config.get_children(startswith="ip address "):
            ipv4_address = ipv4_address_obj.text.split()
            try:
                yield IPv4Interface("/".join(ipv4_address[2:4]))
            except AddressValueError:
                continue

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
    def module_number(self) -> Optional[int]:
        words = self.number.split("/", 1)
        if len(words) == 1:
            return None
        return int(words[0])

    @property
    def nac_control_direction_in(self) -> bool:
        """Determine if the interface has NAC control direction in configured."""
        return "authentication control-direction in" in self.config.children

    @property
    def nac_host_mode(self) -> Optional[NACHostMode]:
        """Determine the NAC host mode."""
        mode = self.config.get_child(startswith="authentication host-mode ")
        if mode is None:
            return None

        mode_word = mode.text.split()[2]
        if mode_word == "multi-auth":
            return NACHostMode.MULTI_AUTH
        if mode_word == "multi-domain":
            return NACHostMode.MULTI_DOMAIN
        if mode_word == "multi-host":
            return NACHostMode.MULTI_HOST
        if mode_word == "single-host":
            return NACHostMode.SINGLE_HOST

        message = f"Unhandled NAC host mode: {mode_word}"
        raise ValueError(message)

    @property
    def nac_mab_first(self) -> bool:
        """Determine if the interface has NAC configured for MAB first."""
        return bool(self.config.get_child(equals="authentication order mab dot1x"))

    @property
    def nac_max_dot1x_clients(self) -> int:
        """Determine the max mab clients."""
        raise NotImplementedError

    @property
    def nac_max_mab_clients(self) -> int:
        """Determine the max mab clients."""
        raise NotImplementedError

    @property
    def name(self) -> str:
        return self.config.text.split()[1]

    @property
    def native_vlan(self) -> Optional[int]:
        # It's configured as a sub-interface
        if self.is_subinterface and (
            vlan := self.config.get_child(startswith="encapsulation dot1Q ")
        ):
            return int(vlan.text.split()[2])

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
        return sub("^[a-zA-Z-]+", "", self.name)

    @property
    def parent_name(self) -> Optional[str]:
        if self.is_subinterface:
            return self.name.split(".")[0]
        return None

    @property
    def poe(self) -> bool:
        return not self.config.get_child(equals="power inline never")

    @property
    def port_number(self) -> int:
        return int(self.name.split("/")[-1].split(".")[0])

    @property
    def speed(self) -> Optional[tuple[int, ...]]:
        if speed := self.config.get_child(startswith="speed "):
            if speed.text == "auto":
                return None
            return (int(speed.text.split()[1]),)
        return None

    @property
    def subinterface_number(self) -> Optional[int]:
        return int(self.name.split(".")[0 - 1]) if self.is_subinterface else None

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
        if vrf := self.config.get_child(startswith="ip vrf forwarding "):
            return vrf.text.split()[3]
        return ""

    @property
    def _bundle_prefix(self) -> str:
        return "Port-channel"


class HConfigViewCiscoIOS(HConfigViewBase):
    def dot1q_mode_from_vlans(
        self,
        untagged_vlan: Optional[int] = None,
        tagged_vlans: tuple[int, ...] = (),
        *,
        tagged_all: bool = False,
    ) -> Optional[InterfaceDot1qMode]:
        raise NotImplementedError

    @property
    def hostname(self) -> Optional[str]:
        if child := self.config.get_child(startswith="hostname "):
            return child.text.split()[1].lower()
        return None

    @property
    def interface_names_mentioned(self) -> frozenset[str]:
        """Returns a set with all the interface names mentioned in the config."""
        return frozenset(model.name for model in self.interface_views)

    @property
    def interface_views(self) -> Iterable[ConfigViewInterfaceCiscoIOS]:
        for interface in self.interfaces:
            yield ConfigViewInterfaceCiscoIOS(interface)

    @property
    def interfaces(self) -> Iterable[HConfigChild]:
        return self.config.get_children(startswith="interface ")

    @property
    def ipv4_default_gw(self) -> Optional[IPv4Address]:
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
        """stacking
        member 1 type "JL123" mac-address abc123-abc123
        member 1 priority 255
        member 2 type "JL123" mac-address abc123-abc123
        member 2 priority 254
        ...
        """
        for member in self.config.get_children(re_search="^switch .* provision .*"):
            words = member.text.split()
            member_id = int(words[1])
            yield StackMember(
                id=member_id,
                priority=256 - member_id,
                mac_address=None,
                model=words[3],
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
            if (
                native_vlan := interface_view.native_vlan
            ) and native_vlan not in yielded_vlans:
                yielded_vlans.add(native_vlan)
                yield Vlan(
                    id=native_vlan,
                    name=None,
                )
