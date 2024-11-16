from abc import ABC, abstractmethod
from collections.abc import Iterable
from ipaddress import IPv4Address, IPv4Interface
from typing import Optional

from hier_config.child import HConfigChild
from hier_config.platforms.models import (
    InterfaceDot1qMode,
    InterfaceDuplex,
    NACHostMode,
    StackMember,
    Vlan,
)
from hier_config.root import HConfig


class ConfigViewInterfaceBase:  # noqa: PLR0904
    def __init__(self, config: HConfigChild) -> None:
        self.config = config

    @property
    @abstractmethod
    def bundle_id(self) -> Optional[str]:
        """Determine the bundle ID."""

    @property
    @abstractmethod
    def bundle_member_interfaces(self) -> Iterable[str]:
        """Determine the member interfaces of a bundle."""

    @property
    @abstractmethod
    def bundle_name(self) -> Optional[str]:
        """Determine the bundle name of a bundle member."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Determine the interface's description."""

    @property
    def dot1q_mode(self) -> Optional[InterfaceDot1qMode]:
        """Derive the configured 802.1Q mode."""
        if self.tagged_all:
            return InterfaceDot1qMode.TAGGED_ALL
        if self.tagged_vlans:
            return InterfaceDot1qMode.TAGGED
        if self.native_vlan and not self.is_svi:
            return InterfaceDot1qMode.ACCESS
        return None

    @property
    @abstractmethod
    def duplex(self) -> InterfaceDuplex:
        """Determine the configured Duplex of the interface."""

    @property
    @abstractmethod
    def enabled(self) -> bool:
        """Determines if the interface is enabled."""

    @property
    @abstractmethod
    def has_nac(self) -> bool:
        """Determine if the interface has NAC configured."""

    @property
    def ipv4_interface(self) -> Optional[IPv4Interface]:
        """Determine the first configured IPv4Interface, address/prefix, object."""
        return next(iter(self.ipv4_interfaces), None)

    @property
    @abstractmethod
    def ipv4_interfaces(self) -> Iterable[IPv4Interface]:
        """Determine the configured IPv4Interface, address/prefix, objects."""

    @property
    @abstractmethod
    def is_bundle(self) -> bool:
        """Determine if the interface is a bundle."""

    @property
    @abstractmethod
    def is_loopback(self) -> bool:
        """Determine if the interface is a loopback."""

    @property
    def is_subinterface(self) -> bool:
        """Determine if the interface is a subinterface."""
        return "." in self.name

    @property
    @abstractmethod
    def is_svi(self) -> bool:
        """Determine if the interface is an SVI."""

    @property
    @abstractmethod
    def module_number(self) -> Optional[int]:
        """Determine the module number of the interface."""

    @property
    @abstractmethod
    def nac_control_direction_in(self) -> bool:
        """Determine if the interface has NAC 'control direction in' configured."""

    @property
    @abstractmethod
    def nac_host_mode(self) -> Optional[NACHostMode]:
        """Determine the NAC host mode."""

    @property
    @abstractmethod
    def nac_mab_first(self) -> bool:
        """Determine if the interface has NAC configured for MAB first."""

    @property
    @abstractmethod
    def nac_max_dot1x_clients(self) -> int:
        """Determine the max dot1x clients."""

    @property
    @abstractmethod
    def nac_max_mab_clients(self) -> int:
        """Determine the max mab clients."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Determine the name of the interface."""

    @property
    @abstractmethod
    def native_vlan(self) -> Optional[int]:
        """Determine the native VLAN."""

    @property
    @abstractmethod
    def number(self) -> str:
        """Remove letters from the interface name, leaving just numbers and symbols."""

    @property
    @abstractmethod
    def parent_name(self) -> Optional[str]:
        """Determine the parent bundle interface name."""

    @property
    @abstractmethod
    def poe(self) -> bool:
        """Determine if PoE is enabled."""

    @property
    @abstractmethod
    def port_number(self) -> int:
        """Determine the interface port number."""

    @property
    @abstractmethod
    def speed(self) -> Optional[tuple[int, ...]]:
        """Determine the statically allowed speeds the interface can operate at. In Mbps."""

    @property
    @abstractmethod
    def subinterface_number(self) -> Optional[int]:
        """Determine the sub-interface number."""

    @property
    @abstractmethod
    def tagged_all(self) -> bool:
        """Determine if all the VLANs are tagged."""

    @property
    @abstractmethod
    def tagged_vlans(self) -> tuple[int, ...]:
        """Determine the tagged VLANs."""

    @property
    @abstractmethod
    def vrf(self) -> str:
        """Determine the VRF."""

    @property
    @abstractmethod
    def _bundle_prefix(self) -> str:
        pass


class HConfigViewBase(ABC):
    def __init__(self, config: HConfig) -> None:
        self.config = config

    @property
    def bundle_interface_views(self) -> Iterable[ConfigViewInterfaceBase]:
        for interface_view in self.interface_views:
            if interface_view.is_bundle:
                yield interface_view

    @abstractmethod
    def dot1q_mode_from_vlans(
        self,
        untagged_vlan: Optional[int] = None,
        tagged_vlans: tuple[int, ...] = (),
        *,
        tagged_all: bool = False,
    ) -> Optional[InterfaceDot1qMode]:
        pass

    @property
    @abstractmethod
    def hostname(self) -> Optional[str]:
        pass

    @property
    @abstractmethod
    def interface_names_mentioned(self) -> frozenset[str]:
        """Returns a set with all the interface names mentioned in the config."""

    def interface_view_by_name(self, name: str) -> Optional[ConfigViewInterfaceBase]:
        for interface_view in self.interface_views:
            if interface_view.name == name:
                return interface_view
        return None

    @property
    @abstractmethod
    def interface_views(self) -> Iterable[ConfigViewInterfaceBase]:
        pass

    @property
    @abstractmethod
    def interfaces(self) -> Iterable[HConfigChild]:
        pass

    @property
    def interfaces_names(self) -> Iterable[str]:
        for interface_view in self.interface_views:
            yield interface_view.name

    @property
    @abstractmethod
    def ipv4_default_gw(self) -> Optional[IPv4Address]:
        pass

    @property
    @abstractmethod
    def location(self) -> str:
        pass

    @property
    def module_numbers(self) -> Iterable[int]:
        seen: set[int] = set()
        for interface_view in self.interface_views:
            if module_number := interface_view.module_number:
                if module_number in seen:
                    continue
                seen.add(module_number)
                yield module_number

    @property
    @abstractmethod
    def stack_members(self) -> Iterable[StackMember]:
        """Determine the configured stack members."""

    @property
    def vlan_ids(self) -> frozenset[int]:
        """Determine the VLAN IDs."""
        return frozenset(vlan.id for vlan in self.vlans)

    @property
    @abstractmethod
    def vlans(self) -> Iterable[Vlan]:
        """Determine the configured VLANs."""
