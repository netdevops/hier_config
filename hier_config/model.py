from enum import Enum, auto

from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict, PositiveInt


class BaseModel(PydanticBaseModel):
    """Pydantic.BaseModel with a safe config applied."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class DumpLine(BaseModel):
    depth: PositiveInt
    text: str
    tags: frozenset[str]
    comments: frozenset[str]
    new_in_config: bool


class MatchRule(BaseModel):
    equals: str | frozenset[str] | None = None
    startswith: str | tuple[str, ...] | None = None
    endswith: str | tuple[str, ...] | None = None
    contains: str | tuple[str, ...] | None = None
    re_search: str | None = None


class TagRule(BaseModel):
    match_rules: tuple[MatchRule, ...]
    apply_tags: frozenset[str]


class SectionalExitingRule(BaseModel):
    lineage: tuple[MatchRule, ...]
    exit_text: str


class SectionalOverwriteRule(BaseModel):
    lineage: tuple[MatchRule, ...]


class SectionalOverwriteNoNegateRule(BaseModel):
    lineage: tuple[MatchRule, ...]


class OrderingRule(BaseModel):
    lineage: tuple[MatchRule, ...]
    weight: int


class IndentAdjustRule(BaseModel):
    start_expression: str
    end_expression: str


class ParentAllowsDuplicateChildRule(BaseModel):
    lineage: tuple[MatchRule, ...]


class FullTextSubRule(BaseModel):
    search: str
    replace: str


class PerLineSubRule(BaseModel):
    search: str
    replace: str


class IdempotentCommandsRule(BaseModel):
    lineage: tuple[MatchRule, ...]


class IdempotentCommandsAvoidRule(BaseModel):
    lineage: tuple[MatchRule, ...]


class Instance(BaseModel):
    id: PositiveInt
    comments: frozenset[str]
    tags: frozenset[str]


class NegationDefaultWhenRule(BaseModel):
    lineage: tuple[MatchRule, ...]


class NegationDefaultWithRule(BaseModel):
    lineage: tuple[MatchRule, ...]
    use: str


SetLikeOfStr = frozenset[str] | set[str]


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


class Dump(BaseModel):
    driver_platform: Platform
    lines: tuple[DumpLine, ...]
