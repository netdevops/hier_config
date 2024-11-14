from collections.abc import Iterable
from ipaddress import AddressValueError, IPv4Address, IPv4Interface
from re import sub
from typing import Optional

from hier_config.child import HConfigChild
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


class ConfigViewInterfaceCiscoIOSXR(ConfigViewInterfaceBase):  # noqa: PLR0904
    @property
    def _bundle_prefix(self) -> str:
        return "Bundle-Ether"

    @property
    def bundle_id(self) -> Optional[str]:
        raise NotImplementedError

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
        raise NotImplementedError

    @property
    def enabled(self) -> bool:
        raise NotImplementedError

    @property
    def has_nac(self) -> bool:
        """Determine if the interface has NAC configured."""
        raise NotImplementedError

    @property
    def ipv4_interface(self) -> Optional[IPv4Interface]:
        return next(iter(self.ipv4_interfaces), None)

    @property
    def ipv4_interfaces(self) -> Iterable[IPv4Interface]:
        for ipv4_address_obj in self.config.get_children(startswith="ipv4 address "):
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
        raise NotImplementedError

    @property
    def nac_host_mode(self) -> Optional[NACHostMode]:
        """Determine the NAC host mode."""
        raise NotImplementedError

    @property
    def nac_mab_first(self) -> bool:
        """Determine if the interface has NAC configured for MAB first."""
        raise NotImplementedError

    @property
    def nac_max_dot1x_clients(self) -> int:
        """Determine the max dot1x clients."""
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
        raise NotImplementedError

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
        raise NotImplementedError

    @property
    def port_number(self) -> int:
        return int(self.name.split("/")[-1].split(".")[0])

    @property
    def speed(self) -> Optional[tuple[int, ...]]:
        raise NotImplementedError

    @property
    def subinterface_number(self) -> Optional[int]:
        return int(self.name.split(".")[0 - 1]) if self.is_subinterface else None

    @property
    def tagged_all(self) -> bool:
        raise NotImplementedError

    @property
    def tagged_vlans(self) -> tuple[int, ...]:
        raise NotImplementedError

    @property
    def vrf(self) -> str:
        raise NotImplementedError


class HConfigViewCiscoIOSXR(HConfigViewBase):
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
        raise NotImplementedError

    @property
    def interface_views(self) -> Iterable[ConfigViewInterfaceCiscoIOSXR]:
        for interface in self.interfaces:
            yield ConfigViewInterfaceCiscoIOSXR(interface)

    @property
    def interfaces(self) -> Iterable[HConfigChild]:
        return self.config.get_children(startswith="interface ")

    @property
    def ipv4_default_gw(self) -> Optional[IPv4Address]:
        raise NotImplementedError

    @property
    def location(self) -> str:
        raise NotImplementedError

    @property
    def stack_members(self) -> Iterable[StackMember]:
        raise NotImplementedError

    @property
    def vlans(self) -> Iterable[Vlan]:
        raise NotImplementedError
