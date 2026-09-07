from hier_config import HConfig, Platform, WorkflowRemediation, get_hconfig_fast_load
from hier_config.child import HConfigChild


def _remediation(running: str, intended: str) -> tuple[str, ...]:
    workflow = WorkflowRemediation(
        get_hconfig_fast_load(Platform.FORTINET_FORTIOS, running),
        get_hconfig_fast_load(Platform.FORTINET_FORTIOS, intended),
    )
    return workflow.remediation_config.dump_simple()


def test_negation_swaps_set_and_unset() -> None:
    """FortiOS toggles between `set` and `unset` when negating."""
    config = HConfig.from_text(Platform.FORTINET_FORTIOS)

    assert HConfigChild(config, "unset description").negate().text == "set description"


def test_negation_drops_parameters_intentionally() -> None:
    """FortiOS negation resets an attribute to its default via `unset <attribute>`.

    The value is never part of the unset command, so parameters after the
    attribute name must be dropped (#225).
    """
    config = HConfig.from_text(Platform.FORTINET_FORTIOS)
    child = HConfigChild(config, 'set description "Port 1"')

    assert child.negate().text == "unset description"


def test_negation_of_bare_set_is_unchanged() -> None:
    """A bare `set` command has no attribute to negate (#225)."""
    config = HConfig.from_text(Platform.FORTINET_FORTIOS)

    assert HConfigChild(config, "set").negate().text == "set"


def test_same_attribute_is_replaced_not_negated() -> None:
    """Two `set` commands for the same attribute are idempotent (#225)."""
    assert _remediation(
        "config system dns\n    set primary 192.0.2.1\nend",
        "config system dns\n    set primary 192.0.2.3\nend",
    ) == ("config system dns", "  set primary 192.0.2.3")


def test_different_attribute_is_negated_then_set() -> None:
    """`set` commands for different attributes are not idempotent (#225)."""
    assert _remediation(
        "config system dns\n    set primary 192.0.2.1\nend",
        "config system dns\n    set secondary 192.0.2.3\nend",
    ) == ("config system dns", "  unset primary", "  set secondary 192.0.2.3")
