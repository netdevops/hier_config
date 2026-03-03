from enum import Enum, auto

from pydantic import NonNegativeInt, PositiveInt

from hier_config.models import BaseModel


class NACHostMode(str, Enum):
    """802.1X / NAC host-mode options ordered from most to least secure."""

    # Ordered from the most to the least secure
    SINGLE_HOST = "single-host"
    MULTI_DOMAIN = "multi-domain"
    MULTI_AUTH = "multi-auth"
    MULTI_HOST = "multi-host"


class InterfaceDot1qMode(str, Enum):
    """802.1Q encapsulation mode of a switchport interface."""

    ACCESS = auto()
    TAGGED = auto()
    TAGGED_ALL = auto()


class StackMember(BaseModel):
    """Identity and priority record for a single switch-stack member."""

    id: NonNegativeInt
    priority: NonNegativeInt
    mac_address: str | None  # not defined in cisco_ios stacks
    model: str


class InterfaceDuplex(str, Enum):
    """Physical duplex setting of an Ethernet interface."""

    AUTO = auto()
    FULL = auto()
    HALF = auto()


class Vlan(BaseModel):
    """Identifier and optional name for a single VLAN."""

    id: PositiveInt
    name: str | None
