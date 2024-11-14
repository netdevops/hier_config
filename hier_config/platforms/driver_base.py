from abc import ABC
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


class HConfigDriverBase(ABC, BaseModel):  # pylint: disable=too-many-instance-attributes
    """Defines all hier_config options, rules, and rule checking methods.
    Override methods as needed.
    """

    indentation: PositiveInt = 2
    sectional_exiting_rules: list[SectionalExitingRule] = Field(default=[])
    sectional_overwrite_rules: list[SectionalOverwriteRule] = Field(default=[])
    sectional_overwrite_no_negate_rules: list[SectionalOverwriteNoNegateRule] = Field(
        default=[]
    )
    ordering_rules: list[OrderingRule] = Field(default=[])
    indent_adjust_rules: list[IndentAdjustRule] = Field(default=[])
    parent_allows_duplicate_child_rules: list[ParentAllowsDuplicateChildRule] = Field(
        default=[]
    )
    full_text_sub_rules: list[FullTextSubRule] = Field(default=[])
    per_line_sub_rules: list[PerLineSubRule] = Field(default=[])
    idempotent_commands_avoid_rules: list[IdempotentCommandsAvoidRule] = Field(
        default=[]
    )
    idempotent_commands_rules: list[IdempotentCommandsRule] = Field(default=[])
    negation_default_when_rules: list[NegationDefaultWhenRule] = Field(default=[])
    negation_negate_with_rules: list[NegationDefaultWithRule] = Field(default=[])
    post_load_callbacks: list[Callable[[HConfig], None]] = Field(default=[])

    def idempotent_for(
        self,
        config: HConfigChild,
        other_children: Iterable[HConfigChild],
    ) -> Optional[HConfigChild]:
        for rule in self.idempotent_commands_rules:
            if config.lineage_test(rule.lineage):
                for other_child in other_children:
                    if other_child.lineage_test(rule.lineage):
                        return other_child
        return None

    def negation_negate_with_check(self, config: HConfigChild) -> Optional[str]:
        for with_rule in self.negation_negate_with_rules:
            if config.lineage_test(with_rule.lineage):
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
