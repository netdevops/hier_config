"""Tests for hier_config/models.py."""

import pytest
from pydantic import ValidationError

from hier_config.models import MatchRule, NegationRule, NegationStrategy


def test_negation_rule_replace_requires_use() -> None:
    """A REPLACE-strategy rule without `use` is a misconfiguration (#278 review)."""
    with pytest.raises(ValidationError, match="REPLACE strategy requires `use`"):
        NegationRule(
            match_rules=(MatchRule(startswith="logging console"),),
            strategy=NegationStrategy.REPLACE,
        )


def test_negation_rule_regex_sub_requires_search() -> None:
    """A REGEX_SUB-strategy rule without `search` is a misconfiguration (#278 review)."""
    with pytest.raises(ValidationError, match="REGEX_SUB strategy requires `search`"):
        NegationRule(
            match_rules=(MatchRule(startswith="snmp-server user"),),
            strategy=NegationStrategy.REGEX_SUB,
        )


def test_negation_rule_regex_sub_allows_empty_replace() -> None:
    """REGEX_SUB with an empty `replace` is valid (deletion-style substitution)."""
    rule = NegationRule(
        match_rules=(MatchRule(startswith="snmp-server user"),),
        strategy=NegationStrategy.REGEX_SUB,
        search=r"(no snmp-server user \S+).*",
    )
    assert not rule.replace


def test_negation_rule_default_requires_no_extra_fields() -> None:
    """A DEFAULT-strategy rule is valid with only match_rules."""
    rule = NegationRule(
        match_rules=(MatchRule(startswith="interface"),),
        strategy=NegationStrategy.DEFAULT,
    )
    assert not rule.use
    assert not rule.search
