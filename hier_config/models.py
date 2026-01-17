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


class ReferencePattern(BaseModel):
    """Defines where an object might be referenced in the configuration.

    Attributes:
        match_rules: Sequence of MatchRules to locate reference contexts.
        extract_regex: Regular expression to extract the object name from the reference.
        capture_group: Which regex capture group contains the object name.
        reference_type: Descriptive type of the reference (e.g., "interface-applied").
        ignore_patterns: Patterns to exclude from consideration as references.

    """

    match_rules: tuple[MatchRule, ...]
    extract_regex: str
    capture_group: PositiveInt = 1
    reference_type: str
    ignore_patterns: tuple[str, ...] = ()


class UnusedObjectRule(BaseModel):
    """Defines how to identify and remove an unused object type.

    This rule is completely user-definable and can be applied to ANY configuration
    object type on ANY platform. Users can create custom rules for their specific
    use cases without code changes.

    Attributes:
        object_type: User-defined identifier for organizing results. Can be any
            descriptive string (e.g., "ipv4-acl", "my-custom-object", "firewall-policy").
            This is purely for categorization and has no functional restrictions.
        definition_match: MatchRules to locate object definitions in the configuration.
            These patterns identify where objects of this type are defined.
        reference_patterns: Patterns describing where objects can be referenced.
            Each pattern includes match rules to find the reference context and a
            regex to extract the referenced object name.
        removal_template: Template string for generating removal commands.
            Use {name} for the object name and any metadata keys from extract_metadata.
            Example: "no ip access-list {acl_type} {name}"
        removal_order_weight: Controls the order in which unused objects are removed.
            Lower weights are removed first. Use this to respect dependencies
            (e.g., remove policy-maps before class-maps they reference).
        allow_in_comment: Whether to consider references in comments as valid usage.
        case_sensitive: Whether object name matching is case-sensitive.
            Set to False for platforms with case-insensitive names (e.g., Cisco IOS).
        require_exact_match: Whether to require exact name matches.

    Example:
        >>> rule = UnusedObjectRule(
        ...     object_type="custom-firewall-policy",
        ...     definition_match=(MatchRule(startswith="firewall policy "),),
        ...     reference_patterns=(
        ...         ReferencePattern(
        ...             match_rules=(MatchRule(startswith="interface "),),
        ...             extract_regex=r"apply-policy\s+(\S+)",
        ...             reference_type="interface-applied",
        ...         ),
        ...     ),
        ...     removal_template="no firewall policy {name}",
        ...     removal_order_weight=100,
        ... )

    """

    object_type: str
    definition_match: tuple[MatchRule, ...]
    reference_patterns: tuple[ReferencePattern, ...]
    removal_template: str
    removal_order_weight: int = 100
    allow_in_comment: bool = False
    case_sensitive: bool = True
    require_exact_match: bool = True


class UnusedObjectDefinition(BaseModel):
    """Represents a discovered object definition in the configuration.

    Note: This model uses model_config to allow arbitrary types for config_section.

    Attributes:
        object_type: Type of the object (e.g., "ipv4-acl").
        name: Name of the object.
        definition_location: Hierarchical path to the definition.
        metadata: Additional information extracted from the definition.

    """

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    object_type: str
    name: str
    definition_location: tuple[str, ...]
    metadata: dict[str, str] = {}


class UnusedObjectReference(BaseModel):
    """Represents a reference to an object in the configuration.

    Attributes:
        object_type: Type of the object being referenced.
        name: Name of the referenced object.
        reference_location: Hierarchical path to the reference.
        reference_type: Type of reference (from ReferencePattern).

    """

    object_type: str
    name: str
    reference_location: tuple[str, ...]
    reference_type: str


class UnusedObjectAnalysis(BaseModel):
    """Results of unused object analysis.

    Attributes:
        defined_objects: Mapping of object types to their definitions.
        referenced_objects: Mapping of object types to their references.
        unused_objects: Mapping of object types to unused definitions.
        total_defined: Total count of defined objects across all types.
        total_unused: Total count of unused objects across all types.
        removal_commands: List of commands to remove unused objects.

    """

    defined_objects: dict[str, tuple[UnusedObjectDefinition, ...]]
    referenced_objects: dict[str, tuple[UnusedObjectReference, ...]]
    unused_objects: dict[str, tuple[UnusedObjectDefinition, ...]]
    total_defined: NonNegativeInt
    total_unused: NonNegativeInt
    removal_commands: tuple[str, ...]
