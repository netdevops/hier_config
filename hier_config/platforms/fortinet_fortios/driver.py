from collections.abc import Iterable
from typing import Optional

from hier_config.child import HConfigChild
from hier_config.models import (
    MatchRule,
    ParentAllowsDuplicateChildRule,
    SectionalExitingRule,
)
from hier_config.platforms.driver_base import HConfigDriverBase, HConfigDriverRules


class HConfigDriverFortinetFortiOS(HConfigDriverBase):
    """Driver for Fortinet FortiOS."""

    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        return HConfigDriverRules(
            sectional_exiting=[
                SectionalExitingRule(
                    match_rules=(MatchRule(startswith="config "),), exit_text="end"
                ),
                SectionalExitingRule(
                    match_rules=(
                        MatchRule(startswith="config "),
                        MatchRule(startswith="edit "),
                    ),
                    exit_text="next",
                ),
            ],
            parent_allows_duplicate_child=[
                ParentAllowsDuplicateChildRule(
                    match_rules=(MatchRule(startswith="end"),)
                ),
            ],
        )

    def swap_negation(self, child: HConfigChild) -> HConfigChild:
        """Swap negation of a `self.text`."""
        if child.text.startswith(self.negation_prefix):
            child.text = f"{self.declaration_prefix}{child.text_without_negation}"
        elif child.text.startswith(self.declaration_prefix):
            child.text = f"{self.negation_prefix}{child.text.removeprefix(self.declaration_prefix).split()[0]}"

        return child

    def idempotent_for(
        self, config: HConfigChild, other_children: Iterable[HConfigChild]
    ) -> Optional[HConfigChild]:
        """Override idempotent_for to only consider a config idempotent
        if the same command exists in the other set.
        """
        for other_child in other_children:
            if (
                config.text.startswith(self.declaration_prefix)
                and other_child.text.startswith(self.declaration_prefix)
                and config.text.split()[1] == other_child.text.split()[1]
            ):
                return other_child
        return super().idempotent_for(config, other_children)

    @property
    def negation_prefix(self) -> str:
        return "unset "

    @property
    def declaration_prefix(self) -> str:
        return "set "
