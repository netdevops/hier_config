from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class Platform(str, Enum):
    ARISTA_EOS = auto()
    CISCO_IOS = auto()
    CISCO_NXOS = auto()
    CISCO_XR = auto()
    GENERIC = auto()  # used in cases where the specific platform is unimportant/unknown
    HP_COMWARE5 = auto()
    HP_PROCURVE = auto()
    JUNIPER_JUNOS = auto()
    VYOS = auto()


class NACHostMode(str, Enum):
    # Ordered from the most to the least secure
    SINGLE_HOST = "single-host"
    MULTI_DOMAIN = "multi-domain"
    MULTI_AUTH = "multi-auth"
    # We don't use multi-host
    MULTI_HOST = "multi-host"


class InterfaceDot1qMode(str, Enum):
    ACCESS = auto()
    TAGGED = auto()
    TAGGED_ALL = auto()


@dataclass
class StackMember:
    id: int
    priority: int
    mac_address: str | None  # not defined in cisco_ios stacks
    model: str


class InterfaceDuplex(str, Enum):
    AUTO = auto()
    FULL = auto()
    HALF = auto()


@dataclass(frozen=True, slots=True)
class Vlan:
    id: int
    name: str | None
