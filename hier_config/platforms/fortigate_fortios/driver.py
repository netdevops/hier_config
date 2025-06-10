from collections.abc import Iterable
from typing import Optional

from hier_config.child import HConfigChild
from hier_config.models import (
    IdempotentCommandsRule,
    MatchRule,
    OrderingRule,
    ParentAllowsDuplicateChildRule,
    PerLineSubRule,
    SectionalExitingRule,
)
from hier_config.platforms.driver_base import HConfigDriverBase, HConfigDriverRules


class HConfigDriverFortigateFortiOS(HConfigDriverBase):
    """Driver for FortiGate OS."""

    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        return HConfigDriverRules(
            negate_with=[],  # We override negate_with() directly
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
                # Allow multiple edit statements under config system interface
                # because each 'edit' block is keyed by its name
                ParentAllowsDuplicateChildRule(
                    match_rules=(MatchRule(startswith="config system"),)
                )
            ],
            ordering=[
                OrderingRule(match_rules=(MatchRule(startswith="edit "),), weight=10)
            ],
            per_line_sub=[
                PerLineSubRule(
                    search=r"^#.*$",  # Strip comments
                    replace="",
                )
            ],
            idempotent_commands=[
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="config"),
                        MatchRule(startswith="edit"),
                        MatchRule(startswith="set"),
                    )
                ),
            ],
        )

    def negate_with(self, config: HConfigChild) -> Optional[str]:
        """Generate clean 'unset' command (e.g. 'unset description' instead of 'unset set description ...').
        """
        if config.text.startswith("set "):
            parts = config.text.split()
            if len(parts) >= 2:
                keyword = parts[1]
                return f"unset {keyword}"
        return None

    def idempotent_for(
        self, config: HConfigChild, other_children: Iterable[HConfigChild]
    ) -> Optional[HConfigChild]:
        """Override idempotent_for to only consider a config idempotent
        if the same command exists in the other set.
        """
        for other in other_children:
            if (
                config.text.startswith("set ")
                and other.text.startswith("set ")
                and config.text.split()[1] == other.text.split()[1]
            ):
                return other  # it's an idempotent value change

        return None  # if the line is missing, we need to `unset` it

    @property
    def negation_prefix(self) -> str:
        return "unset "

    @property
    def declaration_prefix(self) -> str:
        return "set "
