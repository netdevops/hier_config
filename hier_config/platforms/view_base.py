from abc import ABC, abstractmethod
from collections.abc import Iterable
from ipaddress import IPv4Address, IPv4Interface
from re import sub

from hier_config.child import HConfigChild
from hier_config.platforms.functions import expand_range
from hier_config.platforms.models import (
    InterfaceDot1qMode,
    InterfaceDuplex,
    NACHostMode,
    StackMember,
    Vlan,
)
from hier_config.root import HConfig


class ConfigViewInterfaceBase(ABC):
    """Abstract base providing a typed view over a single interface config node.

    Subclasses parse the child tree of one ``interface ...`` block and expose
    structured properties (IP address, description, enabled state, etc.) in a
    platform-independent way.

    Optional capabilities (bundles, VLANs, NAC, physical-layer settings) are
    modeled as mixins (:class:`InterfaceBundleViewMixin`,
    :class:`InterfaceVlanViewMixin`, :class:`InterfaceNACViewMixin`,
    :class:`InterfacePhysicalViewMixin`). Platform views inherit the mixins
    they genuinely support, and users check capability with ``isinstance()``.
    """

    def __init__(self, config: HConfigChild) -> None:
        self.config = config

    @property
    def description(self) -> str:
        """Determine the interface's description."""
        if child := self.config.get_child(startswith="description "):
            return child.text.split(maxsplit=1)[1]
        return ""

    @property
    def enabled(self) -> bool:
        """Determines if the interface is enabled."""
        return not self.config.get_child(equals="shutdown")

    @property
    def ipv4_interface(self) -> IPv4Interface | None:
        """Determine the first configured IPv4Interface, address/prefix, object."""
        return next(iter(self.ipv4_interfaces), None)

    @property
    @abstractmethod
    def ipv4_interfaces(self) -> Iterable[IPv4Interface]:
        """Determine the configured IPv4Interface, address/prefix, objects."""

    @property
    def is_loopback(self) -> bool:
        """Determine if the interface is a loopback."""
        return self.name.lower().startswith("loopback")

    @property
    def is_subinterface(self) -> bool:
        """Determine if the interface is a subinterface."""
        return "." in self.name

    @property
    def is_svi(self) -> bool:
        """Determine if the interface is an SVI."""
        return self.name.lower().startswith("vlan")

    @property
    def name(self) -> str:
        """Determine the name of the interface."""
        return self.config.text.split()[1]

    @property
    def number(self) -> str:
        """Remove letters from the interface name, leaving just numbers and symbols."""
        return sub(r"^[a-zA-Z-]+", "", self.name)

    @property
    def parent_name(self) -> str | None:
        """Determine the parent interface name of a subinterface."""
        if self.is_subinterface:
            return self.name.split(".")[0]
        return None

    @property
    def port_number(self) -> int:
        """Determine the interface port number."""
        return int(self.number.split("/")[-1].split(".")[0])

    @property
    def subinterface_number(self) -> int | None:
        """Determine the sub-interface number."""
        return int(self.name.split(".")[-1]) if self.is_subinterface else None

    @property
    @abstractmethod
    def vrf(self) -> str:
        """Determine the VRF."""


class InterfaceBundleViewMixin(ConfigViewInterfaceBase, ABC):
    """Mixin for platforms that support bundle (LAG/port-channel) interfaces.

    ``_bundle_membership_prefix`` is the child command prefix that assigns an
    interface to a bundle, e.g. ``"channel-group "`` / ``"bundle id "``. It is
    required by the default ``bundle_id``/``bundle_member_interfaces``
    implementations; the bundle id is the word at index
    ``len(_bundle_membership_prefix.split())`` of the matching child.
    """

    _bundle_membership_prefix: str = ""

    @property
    def bundle_id(self) -> str | None:
        """Determine the bundle ID."""
        if membership := self.config.get_child(
            startswith=self._bundle_membership_prefix,
        ):
            return membership.text.split()[len(self._bundle_membership_prefix.split())]
        return None

    @property
    def bundle_member_interfaces(self) -> Iterable[str]:
        """Determine the member interfaces of a bundle."""
        if not self.is_bundle:
            return
        id_index = len(self._bundle_membership_prefix.split())
        number = self.number
        for interface in self.config.parent.get_children(startswith="interface "):
            if (
                membership := interface.get_child(
                    startswith=self._bundle_membership_prefix,
                )
            ) and membership.text.split()[id_index] == number:
                yield interface.text.split()[1]

    @property
    def bundle_name(self) -> str | None:
        """Determine the bundle name of a bundle member."""
        if self.bundle_id:
            return f"{self._bundle_prefix}{self.bundle_id}"
        return None

    @property
    def is_bundle(self) -> bool:
        """Determine if the interface is a bundle."""
        return self.name.lower().startswith(self._bundle_prefix.lower())

    @property
    @abstractmethod
    def _bundle_prefix(self) -> str:
        """Determine the platform's bundle interface name prefix."""


class InterfaceVlanViewMixin(ConfigViewInterfaceBase, ABC):
    """Mixin for platforms that support 802.1Q VLAN interface configuration.

    ``_encapsulation_prefix`` is the subinterface dot1q encapsulation command
    prefix used by the default ``native_vlan`` implementation; the VLAN id is
    the word at index ``len(_encapsulation_prefix.split())`` of the matching
    child.
    """

    _encapsulation_prefix: str = "encapsulation dot1q "

    @property
    def dot1q_mode(self) -> InterfaceDot1qMode | None:
        """Derive the configured 802.1Q mode."""
        if self.tagged_all:
            return InterfaceDot1qMode.TAGGED_ALL
        if self.tagged_vlans:
            return InterfaceDot1qMode.TAGGED
        if self.native_vlan and not self.is_svi:
            return InterfaceDot1qMode.ACCESS
        return None

    @property
    def native_vlan(self) -> int | None:
        """Determine the native VLAN."""
        # It's configured as a sub-interface
        if self.is_subinterface and (
            vlan := self.config.get_child(startswith=self._encapsulation_prefix)
        ):
            return int(vlan.text.split()[len(self._encapsulation_prefix.split())])

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
    def tagged_all(self) -> bool:
        """Determine if all the VLANs are tagged."""
        return bool(
            self.config.get_child(equals="switchport mode trunk")
            and not self.tagged_vlans,
        )

    @property
    def tagged_vlans(self) -> tuple[int, ...]:
        """Determine the tagged VLANs."""
        if child := self.config.get_child(
            re_search="^switchport trunk allowed vlan [0-9,-]+$",
        ):
            return expand_range(child.text.split()[4])
        return ()


class InterfaceNACViewMixin(ConfigViewInterfaceBase, ABC):
    """Mixin for platforms that support NAC (802.1X/MAB) interface configuration."""

    @property
    @abstractmethod
    def has_nac(self) -> bool:
        """Determine if the interface has NAC configured."""

    @property
    @abstractmethod
    def nac_control_direction_in(self) -> bool:
        """Determine if the interface has NAC 'control direction in' configured."""

    @property
    @abstractmethod
    def nac_host_mode(self) -> NACHostMode | None:
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


class InterfacePhysicalViewMixin(ConfigViewInterfaceBase, ABC):
    """Mixin for platforms that expose physical-layer interface settings."""

    @property
    @abstractmethod
    def duplex(self) -> InterfaceDuplex:
        """Determine the configured Duplex of the interface."""

    @property
    def module_number(self) -> int | None:
        """Determine the module number of the interface."""
        words = self.number.split("/", 1)
        if len(words) == 1:
            return None
        return int(words[0])

    @property
    @abstractmethod
    def poe(self) -> bool:
        """Determine if PoE is enabled."""

    @property
    @abstractmethod
    def speed(self) -> tuple[int, ...] | None:
        """Determine the statically allowed speeds the interface can operate at. In Mbps."""


class HConfigViewBase(ABC):
    """Abstract base providing a structured view over a full HConfig tree.

    Platform-specific subclasses (e.g. ``HConfigViewCiscoIOS``) implement
    ``interface_views`` to yield :class:`ConfigViewInterfaceBase` objects.
    """

    def __init__(self, config: HConfig) -> None:
        self.config = config

    @property
    def bundle_interface_views(self) -> Iterable[InterfaceBundleViewMixin]:
        for interface_view in self.interface_views:
            if (
                isinstance(interface_view, InterfaceBundleViewMixin)
                and interface_view.is_bundle
            ):
                yield interface_view

    @staticmethod
    def dot1q_mode_from_vlans(
        untagged_vlan: int | None = None,
        tagged_vlans: tuple[int, ...] = (),
        *,
        tagged_all: bool = False,
    ) -> InterfaceDot1qMode | None:
        """Derive the 802.1Q mode implied by the given VLAN membership data."""
        if tagged_all:
            return InterfaceDot1qMode.TAGGED_ALL
        if tagged_vlans:
            return InterfaceDot1qMode.TAGGED
        if untagged_vlan is not None:
            return InterfaceDot1qMode.ACCESS
        return None

    @property
    @abstractmethod
    def hostname(self) -> str | None:
        pass

    @property
    def interface_names_mentioned(self) -> frozenset[str]:
        """Determine all the interface names mentioned in the config."""
        return frozenset(model.name for model in self.interface_views)

    def interface_view_by_name(self, name: str) -> ConfigViewInterfaceBase | None:
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
    def ipv4_default_gw(self) -> IPv4Address | None:
        pass

    @property
    def location(self) -> str:
        """Determine the SNMP location."""
        if location := self.config.get_child(startswith="snmp-server location "):
            return location.text.split(maxsplit=2)[2].replace('"', "")
        return ""

    @property
    def module_numbers(self) -> Iterable[int]:
        seen: set[int] = set()
        for interface_view in self.interface_views:
            if not isinstance(interface_view, InterfacePhysicalViewMixin):
                continue
            if module_number := interface_view.module_number:
                if module_number in seen:
                    continue
                seen.add(module_number)
                yield module_number

    @property
    def stack_members(self) -> Iterable[StackMember]:
        """Determine the configured stack members.

        Defaults to an empty tuple for platforms without stacking support.
        """
        return ()

    @property
    def vlan_ids(self) -> frozenset[int]:
        """Determine the VLAN IDs."""
        return frozenset(vlan.id for vlan in self.vlans)

    @property
    def vlans(self) -> Iterable[Vlan]:
        """Determine the configured VLANs.

        Yields explicitly defined VLAN blocks first, then any remaining
        unnamed VLANs mentioned on interfaces (e.g. subinterface
        encapsulations or switchport membership).
        """
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
            if not isinstance(interface_view, InterfaceVlanViewMixin):
                continue
            if (
                native_vlan := interface_view.native_vlan
            ) and native_vlan not in yielded_vlans:
                yielded_vlans.add(native_vlan)
                yield Vlan(
                    id=native_vlan,
                    name=None,
                )
