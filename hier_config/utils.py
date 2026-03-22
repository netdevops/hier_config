from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import yaml
from pydantic import TypeAdapter

from hier_config import Platform, get_hconfig_driver
from hier_config.models import (
    FullTextSubRule,
    IdempotentCommandsAvoidRule,
    IdempotentCommandsRule,
    IndentAdjustRule,
    MatchRule,
    NegationDefaultWhenRule,
    NegationDefaultWithRule,
    NegationSubRule,
    OrderingRule,
    ParentAllowsDuplicateChildRule,
    PerLineSubRule,
    ReferenceLocation,
    SectionalExitingRule,
    SectionalOverwriteNoNegateRule,
    SectionalOverwriteRule,
    TagRule,
    UnusedObjectRule,
)
from hier_config.platforms.driver_base import HConfigDriverBase


def _set_match_rule(lineage: dict[str, Any]) -> MatchRule | None:
    if startswith := lineage.get("startswith"):
        return MatchRule(startswith=startswith)
    if endswith := lineage.get("endswith"):
        return MatchRule(endswith=endswith)
    if contains := lineage.get("contains"):
        return MatchRule(contains=contains)
    if equals := lineage.get("equals"):
        return MatchRule(equals=equals)
    if re_search := lineage.get("re_search"):
        return MatchRule(re_search=re_search)

    return None


def _collect_match_rules(
    lineages: Iterable[dict[str, Any]],
) -> tuple[MatchRule, ...]:
    collected: list[MatchRule] = []
    for lineage in lineages:
        match_rule = _set_match_rule(lineage)
        if match_rule is not None:
            collected.append(match_rule)
    return tuple(collected)


def read_text_from_file(file_path: str) -> str:
    """Function that loads the contents of a file into memory.

    Args:
        file_path (str): The path to the configuration file.

    Returns:
        str: The configuration file contents as a string.

    """
    return Path(file_path).read_text(encoding="utf-8")


def load_hier_config_tags(tags_file: str) -> tuple[TagRule, ...]:
    """Loads and validates Hier Config tags from a YAML file.

    Args:
        tags_file (str): Path to the YAML file containing the tags.

    Returns:
        Tuple[TagRule, ...]: A tuple of validated TagRule objects.

    """
    tags_data = yaml.safe_load(read_text_from_file(file_path=tags_file))
    return TypeAdapter(tuple[TagRule, ...]).validate_python(tags_data)


def _process_simple_rules(
    options: dict[str, Any],
    key: str,
    rule_class: type[Any],
    append_to: Callable[[Any], None],
) -> None:
    """Process rules that only need match_rules."""
    for rule in options.get(key, ()):
        match_rules = _collect_match_rules(rule.get("lineage", []))
        append_to(rule_class(match_rules=match_rules))


def _process_custom_rules(options: dict[str, Any], driver: HConfigDriverBase) -> None:
    """Process rules that require custom handling."""
    for rule in options.get("ordering", ()):
        match_rules = _collect_match_rules(rule.get("lineage", []))
        weight = rule.get("order", 500) - 500
        driver.rules.ordering.append(
            OrderingRule(match_rules=match_rules, weight=weight),
        )

    for rule in options.get("indent_adjust", ()):
        driver.rules.indent_adjust.append(
            IndentAdjustRule(
                start_expression=rule.get("start_expression"),
                end_expression=rule.get("end_expression"),
            )
        )

    for rule in options.get("sectional_exiting", ()):
        match_rules = _collect_match_rules(rule.get("lineage", []))
        driver.rules.sectional_exiting.append(
            SectionalExitingRule(
                match_rules=match_rules, exit_text=rule.get("exit_text", "")
            ),
        )

    for rule in options.get("full_text_sub", ()):
        driver.rules.full_text_sub.append(
            FullTextSubRule(
                search=rule.get("search", ""), replace=rule.get("replace", "")
            )
        )

    for rule in options.get("per_line_sub", ()):
        driver.rules.per_line_sub.append(
            PerLineSubRule(
                search=rule.get("search", ""), replace=rule.get("replace", "")
            )
        )

    for rule in options.get("negation_negate_with", ()):
        match_rules = _collect_match_rules(rule.get("lineage", []))
        driver.rules.negate_with.append(
            NegationDefaultWithRule(match_rules=match_rules, use=rule.get("use", "")),
        )

    for rule in options.get("negation_sub", ()):
        match_rules = _collect_match_rules(rule.get("lineage", []))
        driver.rules.negation_sub.append(
            NegationSubRule(
                match_rules=match_rules,
                search=rule.get("search", ""),
                replace=rule.get("replace", ""),
            ),
        )

    for rule in options.get("unused_objects", ()):
        match_rules = _collect_match_rules(rule.get("lineage", []))
        ref_locations = tuple(
            ReferenceLocation(
                match_rules=_collect_match_rules(ref.get("lineage", [])),
                reference_re=ref.get("reference_re", ""),
            )
            for ref in rule.get("reference_locations", [])
        )
        driver.rules.unused_objects.append(
            UnusedObjectRule(
                match_rules=match_rules,
                name_re=rule.get("name_re", ""),
                reference_locations=ref_locations,
            ),
        )


def load_driver_rules(
    options: dict[str, Any] | str, platform: Platform
) -> HConfigDriverBase:
    """Load driver rules from a dictionary or YAML file.

    Args:
        options: Either a dictionary containing driver rule options or
            a file path to a YAML file containing the options.
        platform: The Platform enum for the target platform.

    Returns:
        HConfigDriverBase: A driver instance with the loaded rules.

    """
    if isinstance(options, str):
        options = yaml.safe_load(read_text_from_file(file_path=options))

    if not isinstance(options, dict):
        msg = "options must be a dictionary or a valid file path."
        raise TypeError(msg)

    driver = get_hconfig_driver(platform)

    # Process simple rules that only need match_rules
    simple_rules: tuple[tuple[str, type[Any], Callable[[Any], None]], ...] = (
        (
            "sectional_overwrite",
            SectionalOverwriteRule,
            driver.rules.sectional_overwrite.append,
        ),
        (
            "sectional_overwrite_no_negate",
            SectionalOverwriteNoNegateRule,
            driver.rules.sectional_overwrite_no_negate.append,
        ),
        (
            "parent_allows_duplicate_child",
            ParentAllowsDuplicateChildRule,
            driver.rules.parent_allows_duplicate_child.append,
        ),
        (
            "idempotent_commands_blacklist",
            IdempotentCommandsAvoidRule,
            driver.rules.idempotent_commands_avoid.append,
        ),
        (
            "idempotent_commands",
            IdempotentCommandsRule,
            driver.rules.idempotent_commands.append,
        ),
        (
            "negation_default_when",
            NegationDefaultWhenRule,
            driver.rules.negation_default_when.append,
        ),
    )
    for key, rule_class, append_to in simple_rules:
        _process_simple_rules(options, key, rule_class, append_to)

    # Process rules that require custom handling
    _process_custom_rules(options, driver)

    return driver


def load_tag_rules(
    tags: list[dict[str, Any]] | str,
) -> tuple[TagRule, ...]:
    """Load tag rules from a list of dictionaries or a YAML file.

    Args:
        tags: Either a list of dictionaries or a file path to a YAML file.
            Each dictionary should contain:
              - `lineage`: A list of dictionaries with rules (e.g., `startswith`, `endswith`).
              - `add_tags`: A string representing the tag to add.

    Returns:
        A tuple of TagRule objects.

    """
    if isinstance(tags, str):
        tags = yaml.safe_load(read_text_from_file(file_path=tags))

    if not isinstance(tags, list):
        msg = "tags must be a list of dictionaries or a valid file path."
        raise TypeError(msg)

    result: list[TagRule] = []

    for tag in tags:
        if "lineage" in tag and "add_tags" in tag:
            lineage_rules = tag["lineage"]
            tag_name = tag["add_tags"]

            match_rules = _collect_match_rules(lineage_rules)

            result.append(
                TagRule(match_rules=match_rules, apply_tags=frozenset([tag_name]))
            )

    return tuple(result)
