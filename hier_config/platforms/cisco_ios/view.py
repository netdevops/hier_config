from collections.abc import Iterable
from ipaddress import IPv4Address, IPv4Interface

from hier_config.child import HConfigChild
from hier_config.platforms.functions import parse_ipv4_interface
from hier_config.platforms.models import (
    InterfaceDuplex,
    NACHostMode,
    StackMember,
)
from hier_config.platforms.view_base import (
    HConfigViewBase,
    InterfaceBundleViewMixin,
    InterfaceNACViewMixin,
    InterfacePhysicalViewMixin,
    InterfaceVlanViewMixin,
)


class ConfigViewInterfaceCiscoIOS(
    InterfaceBundleViewMixin,
    InterfaceNACViewMixin,
    InterfacePhysicalViewMixin,
    InterfaceVlanViewMixin,
):
    """Interface config view for Cisco IOS / IOS-XE."""

    _bundle_membership_prefix = "channel-group "
    _encapsulation_prefix = "encapsulation dot1Q "

    @property
    def duplex(self) -> InterfaceDuplex:
        if duplex := self.config.get_child(startswith="duplex "):
            return InterfaceDuplex(duplex.text.split()[1])
        return InterfaceDuplex.AUTO

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
    def ipv4_interfaces(self) -> Iterable[IPv4Interface]:
        for ipv4_address_obj in self.config.get_children(startswith="ip address "):
            if interface := parse_ipv4_interface(ipv4_address_obj.text.split()[2:]):
                yield interface

    @property
    def nac_control_direction_in(self) -> bool:
        """Determine if the interface has NAC control direction in configured."""
        return "authentication control-direction in" in self.config.children

    @property
    def nac_host_mode(self) -> NACHostMode | None:
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
    def poe(self) -> bool:
        return not self.config.get_child(equals="power inline never")

    @property
    def speed(self) -> tuple[int, ...] | None:
        if speed := self.config.get_child(startswith="speed "):
            if speed.text == "auto":
                return None
            return (int(speed.text.split()[1]),)
        return None

    @property
    def vrf(self) -> str:
        if vrf := self.config.get_child(startswith="ip vrf forwarding "):
            return vrf.text.split()[3]
        return ""

    @property
    def _bundle_prefix(self) -> str:
        return "Port-channel"


class HConfigViewCiscoIOS(HConfigViewBase):
    """Full-tree config view for Cisco IOS / IOS-XE."""

    @property
    def hostname(self) -> str | None:
        if child := self.config.get_child(startswith="hostname "):
            return child.text.split()[1].lower()
        return None

    @property
    def interface_views(self) -> Iterable[ConfigViewInterfaceCiscoIOS]:
        for interface in self.interfaces:
            yield ConfigViewInterfaceCiscoIOS(interface)

    @property
    def interfaces(self) -> Iterable[HConfigChild]:
        return self.config.get_children(startswith="interface ")

    @property
    def ipv4_default_gw(self) -> IPv4Address | None:
        if gateway := self.config.get_child(startswith="ip default-gateway "):
            return IPv4Address(gateway.text.split()[2])
        return None

    @property
    def stack_members(self) -> Iterable[StackMember]:
        """Stacking
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
