from collections.abc import Iterable

from hier_config.child import HConfigChild
from hier_config.models import (
    MatchRule,
    ParentAllowsDuplicateChildRule,
    PerLineSubRule,
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
                    match_rules=(MatchRule(startswith="config"),)
                ),
            ],
            per_line_sub=[
                PerLineSubRule(search="^end$", replace=" end"),
                PerLineSubRule(search="^next$", replace="  next"),
            ],
        )

    def swap_negation(self, child: HConfigChild) -> HConfigChild:
        """Swap negation of a `self.text`.

        FortiOS resets an attribute to its default with ``unset <attribute>``;
        the value is never part of the command, so parameters after the
        attribute name are intentionally dropped when negating.
        """
        if child.text.startswith(self.negation_prefix):
            child.text = f"{self.declaration_prefix}{child.text_without_negation}"
        elif child.text.startswith(self.declaration_prefix) and (
            tokens := child.text.removeprefix(self.declaration_prefix).split()
        ):
            child.text = f"{self.negation_prefix}{tokens[0]}"

        return child

    def idempotent_for(
        self, config: HConfigChild, other_children: Iterable[HConfigChild]
    ) -> HConfigChild | None:
        """Override idempotent_for to only consider a config idempotent
        if a `set` command for the same attribute exists in the other set.
        """
        config_tokens = config.text.split()
        if config.text.startswith(self.declaration_prefix) and len(config_tokens) > 1:
            for other_child in other_children:
                other_tokens = other_child.text.split()
                if (
                    other_child.text.startswith(self.declaration_prefix)
                    and len(other_tokens) > 1
                    and config_tokens[1] == other_tokens[1]
                ):
                    return other_child
        return super().idempotent_for(config, other_children)

    @property
    def negation_prefix(self) -> str:
        return "unset "

    @property
    def declaration_prefix(self) -> str:
        return "set "
