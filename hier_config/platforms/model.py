from enum import Enum, auto

from pydantic import PositiveInt

from hier_config.model import BaseModel


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


class StackMember(BaseModel):
    id: PositiveInt
    priority: PositiveInt
    mac_address: str | None  # not defined in cisco_ios stacks
    model: str


class InterfaceDuplex(str, Enum):
    AUTO = auto()
    FULL = auto()
    HALF = auto()


class Vlan(BaseModel):
    id: PositiveInt
    name: str | None
