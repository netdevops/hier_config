from enum import Enum, auto
from typing import Optional, Union

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
    """A rule for matching configuration lines.

    Attrs:
        equals: A string or set of strings to match exactly.
        startswith: A string or tuple of strings to match lines that start with.
        endswith: A string or tuple of strings to match lines that end with.
        contains: A string or tuple of strings to match lines that contain.
        re_search: A regex pattern to match lines that match the pattern.
    """

    equals: Union[str, frozenset[str], None] = None
    startswith: Union[str, tuple[str, ...], None] = None
    endswith: Union[str, tuple[str, ...], None] = None
    contains: Union[str, tuple[str, ...], None] = None
    re_search: Optional[str] = None


class TagRule(BaseModel):
    match_rules: tuple[MatchRule, ...]
    apply_tags: frozenset[str]


class SectionalExitingRule(BaseModel):
    """A rule for exiting a section.

    Attrs:
        match_rules: A tuple of rules that must match to exit the section.
        exit_text: The text returned when exiting the section.
    """

    match_rules: tuple[MatchRule, ...]
    exit_text: str


class SectionalOverwriteRule(BaseModel):
    """Represents a rule for overwriting configuration lines.

    Attrs:
        match_rules: A tuple of rules that must match to overwrite the section.
    """

    match_rules: tuple[MatchRule, ...]


class SectionalOverwriteNoNegateRule(BaseModel):
    """Represents a rule for overwriting configuration lines.

    Attrs:
        match_rules: A tuple of rules that must match to overwrite the section.
    """

    match_rules: tuple[MatchRule, ...]


class OrderingRule(BaseModel):
    """Represents a rule for ordering configuration lines.

    Attrs:
        match_rules: A tuple of rules that must match to be ordered.
        weight: An integer determining the order (lower weights are processed earlier).
    """

    match_rules: tuple[MatchRule, ...]
    weight: int


class IndentAdjustRule(BaseModel):
    """Represents a rule for adjusting indentation.

    Attrs:
        start_expression: Regex or text marking the start of an adjustment.
        end_expression: Regex or text marking the end of an adjustment.
    """

    start_expression: str
    end_expression: str


class ParentAllowsDuplicateChildRule(BaseModel):
    """Represents a rule for allowing duplicate child configurations.

    Attrs:
        match_rules: A tuple of rules that must match to allow duplicate children.
    """

    match_rules: tuple[MatchRule, ...]


class FullTextSubRule(BaseModel):
    """Represents a full-text substitution rule.

    Attrs:
        search: The text to search for.
        replace: The text to replace the search text with.
    """

    search: str
    replace: str


class PerLineSubRule(BaseModel):
    """Represents a per-line substitution rule.

    Attrs:
        search: The text to search for.
        replace: The text to replace the search text with.
    """

    search: str
    replace: str


class IdempotentCommandsRule(BaseModel):
    """Represents a rule for idempotent commands.

    Attrs:
        match_rules: A tuple of rules that must match to be idempotent.
    """

    match_rules: tuple[MatchRule, ...]


class IdempotentCommandsAvoidRule(BaseModel):
    """Represents a rule for avoiding idempotent commands.

    Attrs:
        match_rules: A tuple of rules that must match to avoid idempotent commands.
    """

    match_rules: tuple[MatchRule, ...]


class Instance(BaseModel):
    """Represents a single configuration entity within a HConfig model.

    Attrs:
        id: A unique identifier for the instance.
        comments: A set of comments associated with the instance.
        tags: A set of tags associated with the instance.
    """

    id: PositiveInt
    comments: frozenset[str]
    tags: frozenset[str]


class NegationDefaultWhenRule(BaseModel):
    """Represents a rule for matching configuration lines.

    Attrs:
        match_rules: A tuple of rules that must match to negate the default behavior.
    """

    match_rules: tuple[MatchRule, ...]


class NegationDefaultWithRule(BaseModel):
    """Represents a rule for matching and negating configuration lines.

    Attrs:
        match_rules: A tuple of rules that must match to negate the default behavior.
        use: The default behavior to negate.
    """

    match_rules: tuple[MatchRule, ...]
    use: str


SetLikeOfStr = Union[frozenset[str], set[str]]


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
    lines: tuple[DumpLine, ...]
