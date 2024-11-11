from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from typing import Optional

from pydantic import PositiveInt

from hier_config.child import HConfigChild
from hier_config.model import (
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
    Platform,
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
    sectional_exiting_rules: tuple[SectionalExitingRule, ...] = ()
    sectional_overwrite_rules: tuple[SectionalOverwriteRule, ...] = ()
    sectional_overwrite_no_negate_rules: tuple[SectionalOverwriteNoNegateRule, ...] = ()
    ordering_rules: tuple[OrderingRule, ...] = ()
    indent_adjust_rules: tuple[IndentAdjustRule, ...] = ()
    parent_allows_duplicate_child_rules: tuple[ParentAllowsDuplicateChildRule, ...] = ()
    full_text_sub_rules: tuple[FullTextSubRule, ...] = ()
    per_line_sub_rules: tuple[PerLineSubRule, ...] = ()
    idempotent_commands_avoid_rules: tuple[IdempotentCommandsAvoidRule, ...] = ()
    idempotent_commands_rules: tuple[IdempotentCommandsRule, ...] = ()
    negation_default_when_rules: tuple[NegationDefaultWhenRule, ...] = ()
    negation_negate_with_rules: tuple[NegationDefaultWithRule, ...] = ()
    post_load_callbacks: tuple[Callable[[HConfig], None], ...] = ()

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

    @property
    @abstractmethod
    def platform(self) -> Platform:
        pass

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
