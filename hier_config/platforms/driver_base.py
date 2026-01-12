from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from re import Match, search

from pydantic import Field, PositiveInt

from hier_config.child import HConfigChild
from hier_config.models import (
    BaseModel,
    FullTextSubRule,
    IdempotentCommandsAvoidRule,
    IdempotentCommandsRule,
    IndentAdjustRule,
    MatchRule,
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
            if not config.is_lineage_match(rule.match_rules):
                continue

            config_key = self._idempotency_key(config, rule.match_rules)

            for other_child in other_children:
                if not other_child.is_lineage_match(rule.match_rules):
                    continue

                if self._idempotency_key(other_child, rule.match_rules) == config_key:
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

    def _idempotency_key(
        self,
        config: HConfigChild,
        match_rules: tuple[MatchRule, ...],
    ) -> tuple[str, ...]:
        """Build a structural identity for `config` that respects driver rules.

        Args:
            config: The child being evaluated for idempotency.
            match_rules: The match rules describing the lineage signature.

        Returns:
            A tuple of string fragments representing the idempotency key.

        """
        lineage = tuple(config.lineage())
        if len(lineage) != len(match_rules):
            return ()

        components: list[str] = []
        for child, rule in zip(lineage, match_rules, strict=False):
            components.append(self._idempotency_component_key(child, rule))
        return tuple(components)

    def _idempotency_component_key(
        self,
        child: HConfigChild,
        rule: MatchRule,
    ) -> str:
        """Derive the structural key for a single lineage component.

        Args:
            child: The lineage child contributing to the key.
            rule: The rule governing how to match the child.

        Returns:
            A string fragment representing the component key.

        """
        text = child.text
        normalized_text = text.removeprefix(self.negation_prefix)

        parts: list[str] = []
        parts.extend(self._key_from_equals(rule.equals, text))
        parts.extend(self._key_from_prefix(rule.startswith, normalized_text))
        parts.extend(self._key_from_suffix(rule.endswith, normalized_text))
        parts.extend(self._key_from_contains(rule.contains, normalized_text))
        parts.extend(self._key_from_regex(rule.re_search, normalized_text, text))

        if not parts:
            parts.append(f"text|{normalized_text}")

        return ";".join(parts)

    @staticmethod
    def _key_from_equals(equals: str | frozenset[str] | None, text: str) -> list[str]:
        """Return key fragments constrained by `equals` match rules.

        Args:
            equals: The equals constraint specified by the rule.
            text: The original command text to fall back on for sets.

        Returns:
            A list containing zero or one key fragments.

        """
        if equals is None:
            return []
        if isinstance(equals, str):
            return [f"equals|{equals}"]
        return [f"equals|{text}"]

    def _key_from_prefix(
        self,
        prefix: str | tuple[str, ...] | None,
        normalized_text: str,
    ) -> list[str]:
        """Return key fragments for `startswith` match rules.

        Args:
            prefix: The `startswith` constraint(s) to evaluate.
            normalized_text: The command text without the negation prefix.

        Returns:
            A list containing zero or one key fragments.

        """
        if prefix is None:
            return []
        matched = self._match_prefix(normalized_text, prefix)
        if matched is None:
            return []
        return [f"startswith|{matched}"]

    def _key_from_suffix(
        self,
        suffix: str | tuple[str, ...] | None,
        normalized_text: str,
    ) -> list[str]:
        """Return key fragments for `endswith` match rules.

        Args:
            suffix: The `endswith` constraint(s) to evaluate.
            normalized_text: The command text without the negation prefix.

        Returns:
            A list containing zero or one key fragments.

        """
        if suffix is None:
            return []
        matched = self._match_suffix(normalized_text, suffix)
        if matched is None:
            return []
        return [f"endswith|{matched}"]

    def _key_from_contains(
        self,
        contains: str | tuple[str, ...] | None,
        normalized_text: str,
    ) -> list[str]:
        """Return key fragments for `contains` match rules.

        Args:
            contains: The `contains` constraint(s) to evaluate.
            normalized_text: The command text without the negation prefix.

        Returns:
            A list containing zero or one key fragments.

        """
        if contains is None:
            return []
        matched = self._match_contains(normalized_text, contains)
        if matched is None:
            return []
        return [f"contains|{matched}"]

    def _key_from_regex(
        self,
        pattern: str | None,
        normalized_text: str,
        original_text: str,
    ) -> list[str]:
        """Return key fragments derived from regex match rules.

        Args:
            pattern: The regex pattern to match.
            normalized_text: The command text without the negation prefix.
            original_text: The command text including any negation.

        Returns:
            A list containing zero or one key fragments.

        """
        if pattern is None:
            return []

        match = search(pattern, normalized_text)
        match_source = normalized_text
        if match is None:
            match = search(pattern, original_text)
            match_source = original_text

        if match is None:
            return []

        regex_key = self._normalize_regex_key(pattern, match_source, match)
        return [f"re|{regex_key}"]

    @staticmethod
    def _match_prefix(value: str, prefix: str | tuple[str, ...]) -> str | None:
        if isinstance(prefix, tuple):
            matches = [candidate for candidate in prefix if value.startswith(candidate)]
            if matches:
                return max(matches, key=len)
            return None

        if value.startswith(prefix):
            return prefix

        return None

    @staticmethod
    def _match_suffix(value: str, suffix: str | tuple[str, ...]) -> str | None:
        if isinstance(suffix, tuple):
            matches = [candidate for candidate in suffix if value.endswith(candidate)]
            if matches:
                return max(matches, key=len)
            return None

        if value.endswith(suffix):
            return suffix

        return None

    @staticmethod
    def _match_contains(value: str, contains: str | tuple[str, ...]) -> str | None:
        if isinstance(contains, tuple):
            matches = [candidate for candidate in contains if candidate in value]
            if matches:
                return max(matches, key=len)
            return None

        if contains in value:
            return contains

        return None

    @staticmethod
    def _normalize_regex_key(pattern: str, value: str, match: Match[str]) -> str:
        """Normalize regex matches so equivalent commands hash the same."""
        result = match.group(0)

        if match.re.groups:
            groups = tuple(g or "" for g in match.groups())
            if any(groups):
                normalized_groups = tuple(group.strip() for group in groups)
                if any(normalized_groups):
                    return "|".join(normalized_groups)

        trimmed_pattern = pattern.rstrip("$")
        for suffix in (".*", ".+"):
            if trimmed_pattern.endswith(suffix):
                candidate_pattern = trimmed_pattern[: -len(suffix)]
                if not candidate_pattern:
                    break
                trimmed_match = search(candidate_pattern, value)
                if trimmed_match is not None:
                    candidate = trimmed_match.group(0).strip()
                    if candidate:
                        return candidate
                break

        return result.strip()

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
