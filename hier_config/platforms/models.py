from enum import Enum, auto
from typing import Optional

from pydantic import NonNegativeInt, PositiveInt

from hier_config.models import BaseModel


class NACHostMode(str, Enum):
    # Ordered from the most to the least secure
    SINGLE_HOST = "single-host"
    MULTI_DOMAIN = "multi-domain"
    MULTI_AUTH = "multi-auth"
    MULTI_HOST = "multi-host"


class InterfaceDot1qMode(str, Enum):
    ACCESS = auto()
    TAGGED = auto()
    TAGGED_ALL = auto()


class StackMember(BaseModel):
    id: NonNegativeInt
    priority: NonNegativeInt
    mac_address: Optional[str]  # not defined in cisco_ios stacks
    model: str


class InterfaceDuplex(str, Enum):
    AUTO = auto()
    FULL = auto()
    HALF = auto()


class Vlan(BaseModel):
    id: PositiveInt
    name: Optional[str]
