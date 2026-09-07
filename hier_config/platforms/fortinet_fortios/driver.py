from collections.abc import Iterable

from hier_config.child import HConfigChild
from hier_config.models import Platform
from hier_config.platforms.driver_base import (
    HConfigDriverBase,
    HConfigDriverRules,
    core_owned,
    load_platform_rules,
)


class HConfigDriverFortinetFortiOS(HConfigDriverBase):
    """Driver for Fortinet FortiOS.

    FortiOS treats two ``set <key> ...`` lines with the same key as idempotent
    regardless of their values. That comparison spans sibling nodes, so it is
    implemented natively in the Rust core rather than as a rule.
    """

    platform = Platform.FORTINET_FORTIOS

    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        """Load the canonical rules the Rust core compiles against."""
        return load_platform_rules(Platform.FORTINET_FORTIOS)

    @property
    def negation_prefix(self) -> str:
        return "unset "

    @property
    def declaration_prefix(self) -> str:
        return "set "

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

    @core_owned
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
