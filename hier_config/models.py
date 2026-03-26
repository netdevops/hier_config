from enum import Enum, auto
from typing import Literal

from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict, NonNegativeInt, PositiveInt

TextStyle = Literal["without_comments", "merged", "with_comments"]


class BaseModel(PydanticBaseModel):
    """Pydantic.BaseModel with a safe config applied."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class DumpLine(BaseModel):
    """A single line from a serialised HConfig tree (see :class:`Dump`)."""

    depth: NonNegativeInt
    text: str
    tags: frozenset[str]
    comments: frozenset[str]
    new_in_config: bool


class MatchRule(BaseModel):
    """Flexible predicate for matching an ``HConfigChild.text`` value.

    All fields are optional; when multiple are set every criterion must match.
    Used inside all rule types (ordering, idempotency, negation, etc.).
    """

    equals: str | frozenset[str] | None = None
    startswith: str | tuple[str, ...] | None = None
    endswith: str | tuple[str, ...] | None = None
    contains: str | tuple[str, ...] | None = None
    re_search: str | None = None


class TagRule(BaseModel):
    """Rule that applies a set of tags to children matching ``match_rules``."""

    match_rules: tuple[MatchRule, ...]
    apply_tags: frozenset[str]


class SectionalExitingRule(BaseModel):
    """Rule defining the exit command for a hierarchical configuration section."""

    match_rules: tuple[MatchRule, ...]
    exit_text: str
    exit_text_parent_level: bool = False


class SectionalOverwriteRule(BaseModel):
    """Rule marking a section for full negation + re-creation during remediation."""

    match_rules: tuple[MatchRule, ...]


class SectionalOverwriteNoNegateRule(BaseModel):
    """Rule marking a section for re-creation *without* prior negation."""

    match_rules: tuple[MatchRule, ...]


class OrderingRule(BaseModel):
    """Rule assigning an integer weight to commands to control apply order."""

    match_rules: tuple[MatchRule, ...]
    weight: int


class IndentAdjustRule(BaseModel):
    """Rule defining start/end expressions that shift the indentation level."""

    start_expression: str
    end_expression: str


class ParentAllowsDuplicateChildRule(BaseModel):
    """Rule permitting multiple children with identical text under a parent."""

    match_rules: tuple[MatchRule, ...]


class FullTextSubRule(BaseModel):
    """Regex substitution applied to the entire configuration text block."""

    search: str
    replace: str


class PerLineSubRule(BaseModel):
    """Regex substitution applied to each line of configuration text."""

    search: str
    replace: str


class IdempotentCommandsRule(BaseModel):
    r"""Rule declaring that a command family is idempotent (last value wins).

    Use regex capture groups in ``MatchRule.re_search`` to parameterize
    idempotency keys — e.g. ``r"^client (\S+) server-key"`` makes each
    client IP independently idempotent.

    Prefer separate rules for unrelated command families rather than
    combining them via a tuple ``startswith`` in a single ``MatchRule``.
    """

    match_rules: tuple[MatchRule, ...]


class IdempotentCommandsAvoidRule(BaseModel):
    """Rule preventing specific commands from being treated as idempotent."""

    match_rules: tuple[MatchRule, ...]


class Instance(BaseModel):
    """Metadata snapshot for a single HConfig instance used in merged views."""

    id: PositiveInt
    comments: frozenset[str]
    tags: frozenset[str]


class NegationDefaultWhenRule(BaseModel):
    """Rule specifying when negation should use the ``default`` form."""

    match_rules: tuple[MatchRule, ...]


class NegationDefaultWithRule(BaseModel):
    """Rule replacing negation with a fixed custom command string."""

    match_rules: tuple[MatchRule, ...]
    use: str


class NegationSubRule(BaseModel):
    r"""Regex substitution applied to a command during negation.

    When a negated command matches ``match_rules``, ``re.sub(search, replace, text)``
    is applied to transform the negation line.  Useful when a platform requires
    truncated or reformatted negation commands — e.g. NX-OS SNMP user removal
    must drop everything after the username.

    The regex is applied to the **already-negated** text (with ``no `` prepended).
    ``replace`` supports back-references such as ``\1``.
    """

    match_rules: tuple[MatchRule, ...]
    search: str
    replace: str


class ReferenceLocation(BaseModel):
    """A location in the config tree where object name references are searched.

    ``match_rules`` defines a lineage prefix that narrows the search scope.
    ``reference_re`` is a regex pattern containing ``{name}`` which is
    interpolated with the extracted object name before matching.
    """

    match_rules: tuple[MatchRule, ...]
    reference_re: str


class UnusedObjectRule(BaseModel):
    r"""Rule for detecting unused named objects in a configuration.

    Identifies object definitions via ``match_rules``, extracts the object
    name using ``name_re`` (a regex with a ``(?P<name>...)`` capture group),
    and searches for references across all ``reference_locations``.
    """

    match_rules: tuple[MatchRule, ...]
    name_re: str
    reference_locations: tuple[ReferenceLocation, ...]


SetLikeOfStr = frozenset[str] | set[str]


class Platform(str, Enum):
    """Enumeration of supported network operating system platforms."""

    ARISTA_EOS = auto()
    CISCO_IOS = auto()
    CISCO_NXOS = auto()
    CISCO_XR = auto()
    FORTINET_FORTIOS = auto()
    GENERIC = auto()  # used in cases where the specific platform is unimportant/unknown
    HP_COMWARE5 = auto()
    HP_PROCURVE = auto()
    HUAWEI_VRP = auto()
    JUNIPER_JUNOS = auto()
    VYOS = auto()


class Dump(BaseModel):
    """Serialised representation of an entire HConfig tree."""

    lines: tuple[DumpLine, ...]


class ChangeDetail(BaseModel):
    """Detail record for a single remediation change line, optionally nested."""

    line: str
    full_path: tuple[str, ...]
    device_count: NonNegativeInt
    device_ids: frozenset[PositiveInt]
    tags: frozenset[str]
    comments: frozenset[str]
    instances: tuple[Instance, ...]
    children: tuple["ChangeDetail", ...] = ()


class ReportSummary(BaseModel):
    """High-level statistics produced by :class:`RemediationReporter`."""

    total_devices: NonNegativeInt
    total_unique_changes: NonNegativeInt
    most_common_changes: tuple[tuple[str, NonNegativeInt], ...]
    changes_by_tag: dict[str, NonNegativeInt]
