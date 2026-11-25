"""Regression coverage for PR #302's native rule compatibility review."""

import pytest

from hier_config import HConfig
from hier_config.models import (
    FullTextSubRule,
    MatchRule,
    NegationDefaultWithRule,
    NegationRule,
    NegationStrategy,
    PerLineSubRule,
)
from hier_config.platforms.generic.driver import HConfigDriverGeneric


@pytest.mark.parametrize("fast", (False, True))
def test_per_line_sub_uses_python_replacement_templates(*, fast: bool) -> None:
    driver = HConfigDriverGeneric()
    driver.rules.per_line_sub.append(
        PerLineSubRule(
            search=r"^(?P<name>port) (\d+)$",
            replace=r"\g<name> \2_suffix $\1 \\1",
        )
    )
    config = (
        HConfig.from_lines(driver, ("port 42",))
        if fast
        else HConfig.from_text(driver, "port 42")
    )
    assert config.to_lines() == (r"port 42_suffix $port \1",)


def test_full_text_sub_uses_python_replacement_templates() -> None:
    driver = HConfigDriverGeneric()
    driver.rules.full_text_sub.append(
        FullTextSubRule(
            search=r"(?m)^(?P<name>port) (\d+)$",
            replace=r"\g<name> \2_suffix $\1",
        )
    )
    assert HConfig.from_text(driver, "port 42").to_lines() == ("port 42_suffix $port",)


@pytest.mark.parametrize("pattern", ("(", r"foo(?=bar)"))
def test_unsupported_substitution_regex_is_an_explicit_error(pattern: str) -> None:
    driver = HConfigDriverGeneric()
    driver.rules.per_line_sub.append(PerLineSubRule(search=pattern, replace="changed"))
    with pytest.raises(ValueError, match="regex"):
        HConfig.from_lines(driver, ("foobar",))


def test_python_end_of_string_anchor_is_supported() -> None:
    r"""Python's `\Z` anchor is translated to the Rust `\z` equivalent."""
    driver = HConfigDriverGeneric()
    driver.rules.per_line_sub.append(
        PerLineSubRule(search=r"bar\Z", replace="baz"),
    )
    assert HConfig.from_lines(driver, ("foobar",)).to_lines() == ("foobaz",)


def test_escaped_literal_capital_z_is_not_an_anchor() -> None:
    r"""A literal `\\Z` stays a literal backslash followed by `Z`."""
    driver = HConfigDriverGeneric()
    driver.rules.per_line_sub.append(
        PerLineSubRule(search=r"foo\\Z", replace="changed"),
    )
    assert HConfig.from_lines(driver, ("foo\\Z",)).to_lines() == ("changed",)


def test_unified_replace_overrides_legacy_rule_and_round_trips() -> None:
    driver = HConfigDriverGeneric()
    driver.rules.negate_with.append(
        NegationDefaultWithRule(
            match_rules=(MatchRule(equals="shutdown"),),
            use="legacy override",
        )
    )
    driver.rules.negation.insert(
        0,
        NegationRule(
            strategy=NegationStrategy.REPLACE,
            match_rules=(MatchRule(equals="shutdown"),),
            use="user override",
        ),
    )
    running = HConfig.from_lines(driver, ("shutdown",))
    intended = HConfig.from_lines(driver, ())
    remediation = running.remediation(intended)
    assert remediation.to_lines() == ("user override",)
    future = running.future(remediation)
    assert future.to_lines() == ()
    rollback = future.remediation(running)
    assert rollback.to_lines() == ("shutdown",)
    assert not tuple(future.future(rollback).unified_diff(running))
