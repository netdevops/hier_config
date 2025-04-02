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
    """Configuration rules used by a driver to control parsing, matching,
    ordering, rendering, and normalization of device configurations.

    Attributes:
        full_text_sub: Substitutions applied across full config blocks.
        idempotent_commands: Commands safe to appear multiple times.
        idempotent_commands_avoid: Commands that should not be repeated.
        indent_adjust: Manual indentation overrides for specific lines.
        indentation: Number of spaces used for indentation.
        negation_default_when: When to apply 'no' for default/removed lines.
        negate_with: Custom negation rules for specific commands.
        ordering: Defines sort order of config sections and lines.
        parent_allows_duplicate_child: Allows child repetition under a parent.
        per_line_sub: Line-based text substitutions.
        post_load_callbacks: Functions run after config is loaded.
        sectional_exiting: Rules for determining end of a config block.
        sectional_overwrite: Replace full blocks instead of diffing lines.
        sectional_overwrite_no_negate: Overwrite blocks without using 'no'.

    """

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
        """Initialize the base driver."""
        self.rules: HConfigDriverRules = self._instantiate_rules()

    def idempotent_for(
        self,
        config: HConfigChild,
        other_children: Iterable[HConfigChild],
    ) -> Optional[HConfigChild]:
        """Determine if the `config` is an idempotent change.

        Args:
            config (HConfigChild): The child config object to check.
            other_children (Iterable[HConfigChild]): Other children to check.

        Returns:
            Optional[HConfigChild]: The other child that is an idempotent
                change. None if not found.

        """
        for rule in self.rules.idempotent_commands:
            if config.is_lineage_match(rules=rule.match_rules):
                for other_child in other_children:
                    if other_child.is_lineage_match(rules=rule.match_rules):
                        return other_child
        return None

    def negate_with(self, config: HConfigChild) -> Optional[str]:
        """Determine if the `config` should be negated.

        Args:
            config (HConfigChild): The child config object to check.

        Returns:
            Optional[str]: _description_

        """
        for with_rule in self.rules.negate_with:
            if config.is_lineage_match(rules=with_rule.match_rules):
                return with_rule.use
        return None

    def swap_negation(self, child: HConfigChild) -> HConfigChild:
        """Swap negation of a `child.text`.

        Args:
            child (HConfigChild): The child config object to check.

        Returns:
            HConfigChild: The child config object with negation swapped.

        """
        if child.text.startswith(self.negation_prefix):
            child.text = child.text_without_negation
        else:
            child.text = f"{self.negation_prefix}{child.text}"

        return child

    @property
    def declaration_prefix(self) -> str:
        """Returns the prefix used for command declarations (e.g., 'no', 'delete').

        Default is an empty string; meant to be overridden by platform-specific drivers.
        """
        return ""

    @property
    def negation_prefix(self) -> str:
        """Returns the default prefix used to negate configuration commands.

        Default is 'no ', commonly used in IOS-style configurations.
        """
        return "no "

    @staticmethod
    def config_preprocessor(config_text: str) -> str:
        """Preprocesses raw configuration text before parsing.

        By default, returns the input unchanged. Subclasses can override
        this to normalize, clean, or transform config text as needed.

        Args:
            config_text: The raw configuration string.

        Returns:
            str: The (optionally modified) configuration string.

        """
        return config_text

    @staticmethod
    @abstractmethod
    def _instantiate_rules() -> HConfigDriverRules:
        """Creates and returns a set of HConfigDriverRules for the driver.

        This must be implemented by each driver subclass to define the platform-specific
        parsing, rendering, and normalization behavior.

        Returns:
            HConfigDriverRules: A complete ruleset for the configuration driver.

        """
