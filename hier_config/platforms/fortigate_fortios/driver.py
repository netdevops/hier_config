from collections.abc import Iterable
from typing import Optional

from hier_config.child import HConfigChild
from hier_config.models import (
    MatchRule,
    ParentAllowsDuplicateChildRule,
    SectionalExitingRule,
)
from hier_config.platforms.driver_base import HConfigDriverBase, HConfigDriverRules


class HConfigDriverFortigateFortiOS(HConfigDriverBase):
    """Driver for FortiGate OS."""

    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        return HConfigDriverRules(
            sectional_exiting=[
                SectionalExitingRule(
                    match_rules=(MatchRule(startswith="config"),), exit_text="end"
                ),
                SectionalExitingRule(
                    match_rules=(
                        MatchRule(startswith="config"),
                        MatchRule(startswith="edit"),
                    ),
                    exit_text="next",
                ),
            ],
            parent_allows_duplicate_child=[
                ParentAllowsDuplicateChildRule(match_rules=()),
            ],
        )

    def negate_with(self, config: HConfigChild) -> Optional[str]:
        """Generate clean 'unset' command (e.g. 'unset description' instead of 'unset set description ...')."""
        if config.text.startswith("set "):
            parts = config.text.split()
            if len(parts) >= 2:
                keyword = parts[1]
                return f"unset {keyword}"
        return super().negate_with(config)

    def idempotent_for(
        self, config: HConfigChild, other_children: Iterable[HConfigChild]
    ) -> Optional[HConfigChild]:
        """Override idempotent_for to only consider a config idempotent
        if the same command exists in the other set.
        """
        for other_child in other_children:
            if (
                config.text.startswith("set ")
                and other_child.text.startswith("set ")
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
