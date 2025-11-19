from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable

from pydantic import Field, PositiveInt

from hier_config.child import HConfigChild
from hier_config.models import (
    BaseModel,
    FullTextSubRule,
    IdempotentCommandsAvoidRule,
    IdempotentCommandsRule,
    IndentAdjustRule,
    NegationDefaultWhenRule,
    NegationDefaultWithRule,
    OrderingRule,
    ParentAllowsDuplicateChildRule,
    PerLineSubRule,
    SectionalExitingRule,
    SectionalOverwriteNoNegateRule,
    SectionalOverwriteRule,
)
from hier_config.root import HConfig


def _full_text_sub_rules_default() -> list[FullTextSubRule]:
    return []


def _idempotent_commands_rules_default() -> list[IdempotentCommandsRule]:
    return []


def _idempotent_commands_avoid_rules_default() -> list[IdempotentCommandsAvoidRule]:
    return []


def _indent_adjust_rules_default() -> list[IndentAdjustRule]:
    return []


def _negation_default_when_rules_default() -> list[NegationDefaultWhenRule]:
    return []


def _negate_with_rules_default() -> list[NegationDefaultWithRule]:
    return []


def _ordering_rules_default() -> list[OrderingRule]:
    return []


def _parent_allows_duplicate_child_rules_default() -> list[
    ParentAllowsDuplicateChildRule
]:
    return []


def _per_line_sub_rules_default() -> list[PerLineSubRule]:
    return []


def _post_load_callbacks_default() -> list[Callable[[HConfig], None]]:
    return []


def _sectional_exiting_rules_default() -> list[SectionalExitingRule]:
    return []


def _sectional_overwrite_rules_default() -> list[SectionalOverwriteRule]:
    return []


def _sectional_overwrite_no_negate_rules_default() -> list[
    SectionalOverwriteNoNegateRule
]:
    return []


class HConfigDriverRules(BaseModel):  # pylint: disable=too-many-instance-attributes
    full_text_sub: list[FullTextSubRule] = Field(
        default_factory=_full_text_sub_rules_default
    )
    idempotent_commands: list[IdempotentCommandsRule] = Field(
        default_factory=_idempotent_commands_rules_default
    )
    idempotent_commands_avoid: list[IdempotentCommandsAvoidRule] = Field(
        default_factory=_idempotent_commands_avoid_rules_default
    )
    indent_adjust: list[IndentAdjustRule] = Field(
        default_factory=_indent_adjust_rules_default
    )
    indentation: PositiveInt = 2
    negation_default_when: list[NegationDefaultWhenRule] = Field(
        default_factory=_negation_default_when_rules_default
    )
    negate_with: list[NegationDefaultWithRule] = Field(
        default_factory=_negate_with_rules_default
    )
    ordering: list[OrderingRule] = Field(default_factory=_ordering_rules_default)
    parent_allows_duplicate_child: list[ParentAllowsDuplicateChildRule] = Field(
        default_factory=_parent_allows_duplicate_child_rules_default
    )
    per_line_sub: list[PerLineSubRule] = Field(
        default_factory=_per_line_sub_rules_default
    )
    post_load_callbacks: list[Callable[[HConfig], None]] = Field(
        default_factory=_post_load_callbacks_default
    )
    sectional_exiting: list[SectionalExitingRule] = Field(
        default_factory=_sectional_exiting_rules_default
    )
    sectional_overwrite: list[SectionalOverwriteRule] = Field(
        default_factory=_sectional_overwrite_rules_default
    )
    sectional_overwrite_no_negate: list[SectionalOverwriteNoNegateRule] = Field(
        default_factory=_sectional_overwrite_no_negate_rules_default
    )


class HConfigDriverBase(ABC):
    """Defines all hier_config options, rules, and rule checking methods.
    Override methods as needed.
    """

    def __init__(self) -> None:
        self.rules = self._instantiate_rules()

    def idempotent_for(
        self,
        config: HConfigChild,
        other_children: Iterable[HConfigChild],
    ) -> HConfigChild | None:
        for rule in self.rules.idempotent_commands:
            if config.is_lineage_match(rule.match_rules):
                for other_child in other_children:
                    if other_child.is_lineage_match(rule.match_rules):
                        return other_child
        return None

    def negate_with(self, config: HConfigChild) -> str | None:
        for with_rule in self.rules.negate_with:
            if config.is_lineage_match(with_rule.match_rules):
                return with_rule.use
        return None

    def swap_negation(self, child: HConfigChild) -> HConfigChild:
        """Swap negation of a `child.text`."""
        if child.text.startswith(self.negation_prefix):
            child.text = child.text_without_negation
        else:
            child.text = f"{self.negation_prefix}{child.text}"

        return child

    @property
    def declaration_prefix(self) -> str:
        return ""

    @property
    def negation_prefix(self) -> str:
        return "no "

    @staticmethod
    def config_preprocessor(config_text: str) -> str:
        return config_text

    @staticmethod
    @abstractmethod
    def _instantiate_rules() -> HConfigDriverRules:
        pass
