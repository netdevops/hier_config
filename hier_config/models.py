from enum import Enum, auto

from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict, NonNegativeInt, PositiveInt


class BaseModel(PydanticBaseModel):
    """Pydantic.BaseModel with a safe config applied."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class DumpLine(BaseModel):
    depth: NonNegativeInt
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
    match_rules: tuple[MatchRule, ...]
    exit_text: str
    exit_text_parent_level: bool = False


class SectionalOverwriteRule(BaseModel):
    match_rules: tuple[MatchRule, ...]


class SectionalOverwriteNoNegateRule(BaseModel):
    match_rules: tuple[MatchRule, ...]


class OrderingRule(BaseModel):
    match_rules: tuple[MatchRule, ...]
    weight: int


class IndentAdjustRule(BaseModel):
    start_expression: str
    end_expression: str


class ParentAllowsDuplicateChildRule(BaseModel):
    match_rules: tuple[MatchRule, ...]


class FullTextSubRule(BaseModel):
    search: str
    replace: str


class PerLineSubRule(BaseModel):
    search: str
    replace: str


class IdempotentCommandsRule(BaseModel):
    match_rules: tuple[MatchRule, ...]


class IdempotentCommandsAvoidRule(BaseModel):
    match_rules: tuple[MatchRule, ...]


class Instance(BaseModel):
    id: PositiveInt
    comments: frozenset[str]
    tags: frozenset[str]


class NegationDefaultWhenRule(BaseModel):
    match_rules: tuple[MatchRule, ...]


class NegationDefaultWithRule(BaseModel):
    match_rules: tuple[MatchRule, ...]
    use: str


SetLikeOfStr = frozenset[str] | set[str]


class Platform(str, Enum):
    ARISTA_EOS = auto()
    CISCO_IOS = auto()
    CISCO_NXOS = auto()
    CISCO_XR = auto()
    FORTINET_FORTIOS = auto()
    GENERIC = auto()  # used in cases where the specific platform is unimportant/unknown
    HP_COMWARE5 = auto()
    HP_PROCURVE = auto()
    JUNIPER_JUNOS = auto()
    VYOS = auto()


class Dump(BaseModel):
    lines: tuple[DumpLine, ...]
