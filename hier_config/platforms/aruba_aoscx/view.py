from collections.abc import Iterable
from ipaddress import AddressValueError, IPv4Address, IPv4Interface
from re import sub

from hier_config.child import HConfigChild
from hier_config.platforms.functions import expand_range
from hier_config.platforms.models import (
    InterfaceDuplex,
    NACHostMode,
    Vlan,
)
from hier_config.platforms.view_base import (
    HConfigViewBase,
    InterfaceBundleViewMixin,
    InterfaceNACViewMixin,
    InterfacePhysicalViewMixin,
    InterfaceVlanViewMixin,
)


def _safe_expand_range(spec: str) -> tuple[int, ...]:
    """Expand a VLAN range spec, skipping a malformed one instead of raising.

    The driver's post-load callbacks deliberately leave an unparseable spec
    (e.g. ``10-12-13``) collapsed, so the view must tolerate the same input
    rather than surface a bare ``ValueError`` from deep inside ``expand_range``.
    """
    try:
        return expand_range(spec)
    except ValueError:
        return ()


class ConfigViewInterfaceArubaAOSCX(
    InterfaceBundleViewMixin,
    InterfaceNACViewMixin,
    InterfacePhysicalViewMixin,
    InterfaceVlanViewMixin,
):
    """Interface config view for Aruba AOS-CX."""

    _bundle_membership_prefix = "lag "

    @property
    def bundle_id(self) -> str | None:
        if self.is_bundle:
            # Names look like "lag 1" or "lag 1 multi-chassis"; the id is the
            # token after the "lag " prefix, not the last word.
            return self.name.split()[1]
        return super().bundle_id

    @property
    def bundle_member_interfaces(self) -> Iterable[str]:
        if not self.is_bundle or not self.bundle_id:
            return
        lag_text = f"lag {self.bundle_id}"
        for interface in self.config.parent.get_children(startswith="interface "):
            if interface.get_child(equals=lag_text):
                yield interface.text.split(maxsplit=1)[1]

    @property
    def duplex(self) -> InterfaceDuplex:
        if duplex := self.config.get_child(startswith="duplex "):
            return InterfaceDuplex(duplex.text.split()[1])
        return InterfaceDuplex.AUTO

    @property
    def enabled(self) -> bool:
        # AOS-CX ports are admin-down by default and express the up state as an
        # explicit `no shutdown`, so absence of `shutdown` does not mean enabled.
        return bool(self.config.get_child(equals="no shutdown"))

    @property
    def has_nac(self) -> bool:
        return bool(self.config.get_child(startswith="aaa authentication port-access"))

    @property
    def ipv4_interfaces(self) -> Iterable[IPv4Interface]:
        for ipv4_address_obj in self.config.get_children(startswith="ip address "):
            words = ipv4_address_obj.text.split()
            if len(words) < 3 or words[2] == "dhcp":
                continue
            try:
                yield IPv4Interface(words[2])
            except AddressValueError:
                continue

    @property
    def nac_control_direction_in(self) -> bool:
        return False

    @property
    def nac_host_mode(self) -> NACHostMode | None:
        return None

    @property
    def nac_mab_first(self) -> bool:
        return False

    @property
    def nac_max_dot1x_clients(self) -> int:
        raise NotImplementedError

    @property
    def nac_max_mab_clients(self) -> int:
        raise NotImplementedError

    @property
    def name(self) -> str:
        return self.config.text.split(maxsplit=1)[1]

    @property
    def native_vlan(self) -> int | None:
        if self.is_loopback or self.is_svi:
            return None
        if vlan := self.config.get_child(startswith="vlan trunk native "):
            return int(vlan.text.split()[3])
        if vlan := self.config.get_child(startswith="vlan access "):
            return int(vlan.text.split()[2])
        return None

    @property
    def number(self) -> str:
        return sub(r"^[a-zA-Z-]+\s?", "", self.name)

    @property
    def parent_name(self) -> str | None:
        if self.is_subinterface:
            return self.name.split(".")[0]
        return self.bundle_name if self.bundle_id and not self.is_bundle else None

    @property
    def poe(self) -> bool:
        return not self.config.get_child(equals="no power-over-ethernet")

    @property
    def speed(self) -> tuple[int, ...] | None:
        if speed := self.config.get_child(startswith="speed "):
            if speed.text == "speed auto":
                return None
            return (int(speed.text.split()[1]),)
        return None

    @property
    def tagged_all(self) -> bool:
        return bool(self.config.get_child(equals="vlan trunk allowed all"))

    @property
    def tagged_vlans(self) -> tuple[int, ...]:
        vlans: set[int] = set()
        for child in self.config.get_children(
            re_search=r"^vlan trunk allowed [0-9,-]+$"
        ):
            vlans.update(_safe_expand_range(child.text.split()[3]))
        return tuple(sorted(vlans))

    @property
    def vrf(self) -> str:
        if vrf := self.config.get_child(startswith="vrf attach "):
            return vrf.text.split()[2]
        return ""

    @property
    def _bundle_prefix(self) -> str:
        return "lag "


class HConfigViewArubaAOSCX(HConfigViewBase):
    """Full-tree config view for Aruba AOS-CX."""

    @property
    def hostname(self) -> str | None:
        if child := self.config.get_child(startswith="hostname "):
            return child.text.split()[1].lower()
        return None

    @property
    def interface_views(self) -> Iterable[ConfigViewInterfaceArubaAOSCX]:
        for interface in self.interfaces:
            yield ConfigViewInterfaceArubaAOSCX(interface)

    @property
    def interfaces(self) -> Iterable[HConfigChild]:
        return self.config.get_children(startswith="interface ")

    @property
    def ipv4_default_gw(self) -> IPv4Address | None:
        if gateway := self.config.get_child(startswith="ip route 0.0.0.0/0 "):
            return IPv4Address(gateway.text.split()[3])
        return None

    @property
    def vlans(self) -> Iterable[Vlan]:
        """Determine the configured VLANs.

        Uses tolerant range expansion (a malformed collapsed header is skipped,
        matching the driver's post-load behaviour) and also yields unnamed
        VLANs that only appear as tagged members on interfaces.
        """
        yielded_vlans: set[int] = set()
        for child in self.config.get_children(re_search=r"^vlan [0-9,-]+$"):
            vlan_name = None
            if name := child.get_child(startswith="name "):
                _, vlan_name = name.text.split(maxsplit=1)
                vlan_name = vlan_name.replace('"', "")
            for vlan_id in _safe_expand_range(child.text.split()[1]):
                yielded_vlans.add(vlan_id)
                yield Vlan(id=vlan_id, name=vlan_name or None)

        for interface_view in self.interface_views:
            for vlan_id in interface_view.tagged_vlans:
                if vlan_id not in yielded_vlans:
                    yielded_vlans.add(vlan_id)
                    yield Vlan(id=vlan_id, name=None)
            if (
                native_vlan := interface_view.native_vlan
            ) and native_vlan not in yielded_vlans:
                yielded_vlans.add(native_vlan)
                yield Vlan(id=native_vlan, name=None)
