from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from typing import Optional

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


class HConfigDriverRules(BaseModel):  # pylint: disable=too-many-instance-attributes
    full_text_sub: list[FullTextSubRule] = Field(default_factory=list)
    idempotent_commands: list[IdempotentCommandsRule] = Field(default_factory=list)
    idempotent_commands_avoid: list[IdempotentCommandsAvoidRule] = Field(
        default_factory=list
    )
    indent_adjust: list[IndentAdjustRule] = Field(default_factory=list)
    indentation: PositiveInt = 2
    negation_default_when: list[NegationDefaultWhenRule] = Field(default_factory=list)
    negate_with: list[NegationDefaultWithRule] = Field(default_factory=list)
    ordering: list[OrderingRule] = Field(default_factory=list)
    parent_allows_duplicate_child: list[ParentAllowsDuplicateChildRule] = Field(
        default_factory=list
    )
    per_line_sub: list[PerLineSubRule] = Field(default_factory=list)
    post_load_callbacks: list[Callable[[HConfig], None]] = Field(default_factory=list)
    sectional_exiting: list[SectionalExitingRule] = Field(default_factory=list)
    sectional_overwrite: list[SectionalOverwriteRule] = Field(default_factory=list)
    sectional_overwrite_no_negate: list[SectionalOverwriteNoNegateRule] = Field(
        default_factory=list
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
    ) -> Optional[HConfigChild]:
        for rule in self.rules.idempotent_commands:
            if config.is_lineage_match(rule.match_rules):
                for other_child in other_children:
                    if other_child.is_lineage_match(rule.match_rules):
                        return other_child
        return None

    def negate_with(self, config: HConfigChild) -> Optional[str]:
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
    @abstractmethod
    def _instantiate_rules() -> HConfigDriverRules:
        pass
