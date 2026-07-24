from collections.abc import Iterable
from ipaddress import AddressValueError, IPv4Address, IPv4Interface
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
from hier_config.platforms.view_base import (
    ConfigViewInterfaceBase,
    HConfigViewBase,
)


class ConfigViewInterfaceArubaAOSCX(ConfigViewInterfaceBase):  # ruff:ignore[too-many-public-methods]
    """Interface config view for Aruba AOS-CX."""

    @property
    def bundle_id(self) -> str | None:
        if self.is_bundle:
            return self.name.split()[-1]
        if lag := self.config.get_child(startswith="lag "):
            return lag.text.split()[1]
        return None

    @property
    def bundle_member_interfaces(self) -> Iterable[str]:
        if not self.is_bundle or not self.bundle_id:
            return
        lag_text = f"lag {self.bundle_id}"
        for interface in self.config.root.get_children(startswith="interface "):
            if interface.get_child(equals=lag_text):
                yield interface.text.split(maxsplit=1)[1]

    @property
    def bundle_name(self) -> str | None:
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
    def is_bundle(self) -> bool:
        return self.name.lower().startswith(self._bundle_prefix)

    @property
    def is_loopback(self) -> bool:
        return self.name.lower().startswith("loopback")

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
    def port_number(self) -> int:
        return int(self.name.split("/")[-1].split(".")[0])

    @property
    def speed(self) -> tuple[int, ...] | None:
        if speed := self.config.get_child(startswith="speed "):
            if speed.text == "speed auto":
                return None
            return (int(speed.text.split()[1]),)
        return None

    @property
    def subinterface_number(self) -> int | None:
        return int(self.name.split(".")[-1]) if self.is_subinterface else None

    @property
    def tagged_all(self) -> bool:
        return bool(self.config.get_child(equals="vlan trunk allowed all"))

    @property
    def tagged_vlans(self) -> tuple[int, ...]:
        vlans: set[int] = set()
        for child in self.config.get_children(
            re_search=r"^vlan trunk allowed [0-9,-]+$"
        ):
            vlans.update(expand_range(child.text.split()[3]))
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

    def dot1q_mode_from_vlans(  # ruff:ignore[no-self-use]
        self,
        untagged_vlan: int | None = None,
        tagged_vlans: tuple[int, ...] = (),
        *,
        tagged_all: bool = False,
    ) -> InterfaceDot1qMode | None:
        if tagged_all:
            return InterfaceDot1qMode.TAGGED_ALL
        if tagged_vlans:
            return InterfaceDot1qMode.TAGGED
        if untagged_vlan:
            return InterfaceDot1qMode.ACCESS
        return None

    @property
    def hostname(self) -> str | None:
        if child := self.config.get_child(startswith="hostname "):
            return child.text.split()[1].lower()
        return None

    @property
    def interface_names_mentioned(self) -> frozenset[str]:
        return frozenset(model.name for model in self.interface_views)

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
    def location(self) -> str:
        if location := self.config.get_child(startswith="snmp-server location "):
            return location.text.split(maxsplit=2)[2].replace('"', "")
        return ""

    @property
    def stack_members(self) -> Iterable[StackMember]:
        return ()

    @property
    def vlans(self) -> Iterable[Vlan]:
        yielded_vlans: set[int] = set()
        for child in self.config.get_children(re_search=r"^vlan [0-9,-]+$"):
            vlan_name = None
            if name := child.get_child(startswith="name "):
                _, vlan_name = name.text.split(maxsplit=1)
                vlan_name = vlan_name.replace('"', "")
            for vlan_id in expand_range(child.text.split()[1]):
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
