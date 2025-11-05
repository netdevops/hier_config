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
    """Abstract base class for extracting structured interface data from an HConfigChild node."""

    def __init__(self, config: HConfigChild) -> None:
        """Initialize the interface view.

        Args:
            config (HConfigChild): The child config object to view.

        """
        self.config: HConfigChild = config

    @property
    @abstractmethod
    def bundle_id(self) -> Optional[str]:
        """Determine the bundle (or LAG) ID.

        Returns:
            Optional[str]: The bundle (or LAG) ID.

        """

    @property
    @abstractmethod
    def bundle_member_interfaces(self) -> Iterable[str]:
        """Determine the member interfaces of a bundle.

        Returns:
            Iterable[str]: The member interfaces of a bundle.

        """

    @property
    @abstractmethod
    def bundle_name(self) -> Optional[str]:
        """Determine the bundle name of a bundle member.

        Returns:
            Optional[str]: The bundle name of a bundle member or None.

        """

    @property
    @abstractmethod
    def description(self) -> str:
        """Determine the interface's description.

        Returns:
            str: The interface's description.

        """

    @property
    def dot1q_mode(self) -> Optional[InterfaceDot1qMode]:
        """Derive the configured 802.1Q mode.

        Returns:
            Optional[InterfaceDot1qMode]: The configured 802.1Q mode.

        """
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
        """Determine the configured Duplex of the interface.

        Returns:
            InterfaceDuplex: The configured duplex mode.

        """

    @property
    @abstractmethod
    def enabled(self) -> bool:
        """Determines if the interface is enabled.

        Returns:
            bool: True if the interface is enabled, else False.

        """

    @property
    @abstractmethod
    def has_nac(self) -> bool:
        """Determine if the interface has NAC (Network Access Control) configured.

        Returns:
            bool: True if the interface has NAC configured, else False.

        """

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
        """Determine if the interface is a bundle.

        Returns:
            bool: True if the interface is a bundle, else False.

        """

    @property
    @abstractmethod
    def is_loopback(self) -> bool:
        """Determine if the interface is a loopback.

        Returns:
            bool: True if the interface is a loopback, else False.

        """

    @property
    def is_subinterface(self) -> bool:
        """Determine if the interface is a subinterface.

        Returns:
            bool: True if the interface is a subinterface, else False.

        """
        return "." in self.name

    @property
    @abstractmethod
    def is_svi(self) -> bool:
        """Determine if the interface is an SVI.

        Returns:
            bool: True if the interface is an SVI, else False.

        """

    @property
    @abstractmethod
    def module_number(self) -> Optional[int]:
        """Determine the module number of the interface.

        Returns:
            Optional[int]: The module number of the interface or None.

        """

    @property
    @abstractmethod
    def nac_control_direction_in(self) -> bool:
        """Determine if the interface has NAC 'control direction in' configured.

        Returns:
            bool: True if 'control direction in' is configured, else False.

        """

    @property
    @abstractmethod
    def nac_host_mode(self) -> Optional[NACHostMode]:
        """Determine the NAC host mode.

        Returns:
            Optional[NACHostMode]: The NAC host mode or None.

        """

    @property
    @abstractmethod
    def nac_mab_first(self) -> bool:
        """Determine if the interface has NAC configured for MAB first.

        Returns:
            bool: True is MAB authentication is configured first, else False.

        """

    @property
    @abstractmethod
    def nac_max_dot1x_clients(self) -> int:
        """Determine the max dot1x clients.

        Returns:
            int: The max amount of dot1x clients.

        """

    @property
    @abstractmethod
    def nac_max_mab_clients(self) -> int:
        """Determine the max mab clients.

        Returns:
            int: The max number of clients that can be authenticated using MAB.

        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Determine the name of the interface.

        Returns:
            str: The interface name.

        """

    @property
    @abstractmethod
    def native_vlan(self) -> Optional[int]:
        """Determine the native VLAN.

        Returns:
            Optional[int]: Native VLAN ID or None if not set.

        """

    @property
    @abstractmethod
    def number(self) -> str:
        """Remove letters from the interface name, leaving just numbers and symbols.

        Returns:
            str: The interface number.

        """

    @property
    @abstractmethod
    def parent_name(self) -> Optional[str]:
        """Determine the parent bundle interface name.

        Returns:
            Optional[str]: The logical parent bundle interface name or None.

        """

    @property
    @abstractmethod
    def poe(self) -> bool:
        """Determine if PoE is enabled.

        Returns:
            bool: True if PoE is enabled, else False.

        """

    @property
    @abstractmethod
    def port_number(self) -> int:
        """Determine the interface port number.

        Returns:
            int: The interface port number.

        """

    @property
    @abstractmethod
    def speed(self) -> Optional[tuple[int, ...]]:
        """Determine the statically allowed speeds the interface can operate at. In Mbps.

        Returns:
            Optional[tuple[int, ...]]: The allowed speeds or None.

        """

    @property
    @abstractmethod
    def subinterface_number(self) -> Optional[int]:
        """Determine the sub-interface number.

        Returns:
            Optional[int]: The sub-interface number or None.

        """

    @property
    @abstractmethod
    def tagged_all(self) -> bool:
        """Determine if all the VLANs are tagged.

        Returns:
            bool: True if all the VLANs are tagged, else False.

        """

    @property
    @abstractmethod
    def tagged_vlans(self) -> tuple[int, ...]:
        """Determine the tagged VLANs.

        Returns:
            tuple[int, ...]: Tuple of tagged VLAN IDs.

        """

    @property
    @abstractmethod
    def vrf(self) -> str:
        """Determine the VRF.

        Returns:
            str: The VRF name.

        """

    @property
    @abstractmethod
    def _bundle_prefix(self) -> str:
        """Determine the bundle prefix name.

        Returns:
            str: The bundle prefix name.

        """


class HConfigViewBase(ABC):
    """Abstract class to view HConfig config tree objects."""

    def __init__(self, config: HConfig) -> None:
        """Initialize the HConfig view base class.

        Args:
            config (HConfig): The HConfig object to view.

        """
        self.config: HConfig = config

    @property
    def bundle_interface_views(self) -> Iterable[ConfigViewInterfaceBase]:
        """Determine the bundle interface views.

        Yields:
            Iterable[ConfigViewInterfaceBase]: Iterable of bundle interface views.

        """
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
        """Determine the 802.1Q mode from VLANs.

        Args:
            untagged_vlan (Optional[int], optional): Untagged VLAN. Defaults to None.
            tagged_vlans (tuple[int, ...], optional): Tagged VLANs. Defaults to ().
            tagged_all (bool, optional): Tagged all VLANs. Defaults to False.

        Returns:
            Optional[InterfaceDot1qMode]: The 802.1Q mode or None if not set.

        """

    @property
    @abstractmethod
    def hostname(self) -> Optional[str]:
        """Determine the hostname.

        Returns:
            Optional[str]: The hostname or None.

        """

    @property
    @abstractmethod
    def interface_names_mentioned(self) -> frozenset[str]:
        """Returns a set with all the interface names mentioned in the config.

        Returns:
            frozenset[str]: All the interface names mentioned in the config.

        """

    def interface_view_by_name(self, name: str) -> Optional[ConfigViewInterfaceBase]:
        """Determine the interface view by name.

        Args:
            name (str): The interface name.

        Returns:
            Optional[ConfigViewInterfaceBase]: The interface view or None.

        """
        for interface_view in self.interface_views:
            if interface_view.name == name:
                return interface_view
        return None

    @property
    @abstractmethod
    def interface_views(self) -> Iterable[ConfigViewInterfaceBase]:
        """Determine the configured interfaces.

        Returns:
            Iterable[ConfigViewInterfaceBase]: The configured interfaces.

        """

    @property
    @abstractmethod
    def interfaces(self) -> Iterable[HConfigChild]:
        """Determine the configured interfaces.

        Returns:
            Iterable[HConfigChild]: An iterbale of the configured interfaces'
                HConfig objects.

        """

    @property
    def interfaces_names(self) -> Iterable[str]:
        """Determine the configured interface names.

        Yields:
            Iterator[Iterable[str]]: The configured interface names.

        """
        for interface_view in self.interface_views:
            yield interface_view.name

    @property
    @abstractmethod
    def ipv4_default_gw(self) -> Optional[IPv4Address]:
        """Determine the IPv4 default gateway IPv4Address.

        Returns:
            Optional[IPv4Address]: The IPv4 default gateway object or None.

        """

    @property
    @abstractmethod
    def location(self) -> str:
        """Determine the location of the device.

        Returns:
            str: Location name of the device.

        """

    @property
    def module_numbers(self) -> Iterable[int]:
        """Determine the configured module numbers.

        Yields:
            Iterator[Iterable[int]]: Yields unique module numbers.

        """
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
        """Determine the configured stack members.

        Returns:
            Iterable[StackMember]: The configured stack members.

        """

    @property
    def vlan_ids(self) -> frozenset[int]:
        """Determine the VLAN IDs.

        Returns:
            frozenset[int]: The VLAN IDs.

        """
        return frozenset(vlan.id for vlan in self.vlans)

    @property
    @abstractmethod
    def vlans(self) -> Iterable[Vlan]:
        """Determine the configured VLANs.

        Returns:
            Iterable[Vlan]: The configured VLANs.

        """
