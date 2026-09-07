"""Behavioral coverage for the two documented extension surfaces.

hier_config exposes exactly two ways for a consumer to extend driver
behavior without forking the library:

1. **Post-load callbacks** -- ``HConfigDriverRules.post_load_callbacks``, the
   only callback collection. Stock/project-defined callbacks run natively in
   Rust, so anything registered here is purely *additive*.
2. **Code-injected rules** -- the fifteen rule collections on
   ``HConfigDriverRules`` plus the scalar ``indentation``.

Both surfaces are exercised here end to end: a rule or callback is injected
from Python and the resulting parse/remediation output is asserted, proving
the value crosses the FFI boundary and reaches the Rust engine.
"""

from typing import TYPE_CHECKING

import pytest

from hier_config import (
    HConfig,
    Platform,
    get_hconfig,
    get_hconfig_driver,
    get_hconfig_fast_load,
)
from hier_config.constructors import get_hconfig_from_dump
from hier_config.models import (
    Dump,
    DumpLine,
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
    SectionalExitingRule,
    SectionalOverwriteNoNegateRule,
    SectionalOverwriteRule,
)
from hier_config.platforms.cisco_ios.driver import HConfigDriverCiscoIOS
from hier_config.platforms.driver_base import (
    HConfigDriverBase,
    HConfigDriverRules,
    load_platform_rules,
)
from hier_config.platforms.hp_procurve.driver import HConfigDriverHPProcurve

if TYPE_CHECKING:
    from collections.abc import Callable


def _driver() -> HConfigDriverBase:
    """Return a throwaway driver whose rule lists are safe to mutate.

    ``get_hconfig_driver`` builds a new driver on every call and
    ``load_platform_rules`` shallow-copies each rule list, so mutations made by
    one test can never leak into another.
    """
    return get_hconfig_driver(Platform.GENERIC)


# ---------------------------------------------------------------------------
# Callback surface: post_load_callbacks
# ---------------------------------------------------------------------------


def test_extension_surface_is_fully_enumerated() -> None:
    """Pin the extension surface so a new rules field forces a doc update.

    ``post_load_callbacks`` is the only callback collection; everything else on
    ``HConfigDriverRules`` is a code-injectable rule list, apart from the
    scalar ``indentation``.
    """
    injectable_rule_fields = {
        "full_text_sub",
        "idempotent_commands",
        "idempotent_commands_avoid",
        "indent_adjust",
        "negate_with",
        "negation_default_when",
        "negation_sub",
        "ordering",
        "parent_allows_duplicate_child",
        "per_line_sub",
        "sectional_exiting",
        "sectional_overwrite",
        "sectional_overwrite_no_negate",
        "unused_objects",
    }
    callback_fields = {"post_load_callbacks"}
    scalar_fields = {"indentation"}

    assert set(HConfigDriverRules.model_fields) == (
        injectable_rule_fields | callback_fields | scalar_fields
    )
    assert len(injectable_rule_fields) == 14

    rules = load_platform_rules(Platform.GENERIC)
    for field in injectable_rule_fields | callback_fields:
        assert isinstance(getattr(rules, field), list), field
    # Callbacks are additive only: no stock callbacks are exposed to Python.
    assert rules.post_load_callbacks == []


def test_custom_callback_runs_via_get_hconfig() -> None:
    """A callback appended in Python runs on the full-parse constructor."""
    driver = _driver()
    seen: list[int] = []

    def _callback(config: HConfig) -> None:
        seen.append(len(tuple(config.all_children())))
        config.add_child("from-callback")

    driver.rules.post_load_callbacks.append(_callback)
    config = get_hconfig(driver, "hostname sw1\n")

    assert seen == [1]
    assert config.dump_simple() == ("hostname sw1", "from-callback")


def test_custom_callback_runs_via_get_hconfig_fast_load() -> None:
    """The fast-load constructor honors user callbacks too."""
    driver = _driver()

    def _callback(config: HConfig) -> None:
        config.add_child("from-callback")

    driver.rules.post_load_callbacks.append(_callback)
    config = get_hconfig_fast_load(driver, ["hostname sw1"])

    assert config.dump_simple() == ("hostname sw1", "from-callback")


def test_custom_callbacks_run_in_registration_order() -> None:
    """Multiple callbacks fire in list order, so later ones see earlier edits."""
    driver = _driver()
    order: list[str] = []

    def _first(config: HConfig) -> None:
        order.append("first")
        config.add_child("first")

    def _second(config: HConfig) -> None:
        order.append("second")
        assert config.get_child(equals="first") is not None
        config.add_child("second")

    driver.rules.post_load_callbacks.extend((_first, _second))
    config = get_hconfig(driver, "hostname sw1\n")

    assert order == ["first", "second"]
    assert config.dump_simple() == ("hostname sw1", "first", "second")


def test_custom_callbacks_are_additive_to_stock_behavior() -> None:
    """Registering a callback does not disable the native stock callbacks.

    Cisco IOS strips sequence numbers from IPv6 ACL entries in a stock
    callback that now lives in Rust. A user callback must not suppress it.
    """
    driver = get_hconfig_driver(Platform.CISCO_IOS)

    def _callback(config: HConfig) -> None:
        config.add_child("user-callback-marker")

    driver.rules.post_load_callbacks.append(_callback)
    config = get_hconfig(
        driver,
        "ipv6 access-list ACL1\n sequence 10 permit ipv6 any any\n",
    )

    assert config.dump_simple() == (
        "ipv6 access-list ACL1",
        "  permit ipv6 any any",
        "user-callback-marker",
    )


def test_callbacks_registered_through_load_platform_rules() -> None:
    """``load_platform_rules(post_load_callbacks=...)`` is a supported entry."""

    def _callback(config: HConfig) -> None:
        config.add_child("from-loader")

    rules = load_platform_rules(Platform.GENERIC, post_load_callbacks=[_callback])
    driver = _driver()
    driver.rules = rules
    config = get_hconfig(driver, "hostname sw1\n")

    assert config.dump_simple() == ("hostname sw1", "from-loader")
    # The loader must not have mutated the shared cached rules.
    assert not load_platform_rules(Platform.GENERIC).post_load_callbacks


def test_callbacks_registered_through_instantiate_rules_override() -> None:
    """A custom driver subclass can ship callbacks via ``_instantiate_rules``."""

    def _callback(config: HConfig) -> None:
        config.add_child("from-subclass")

    class _CustomDriver(HConfigDriverBase):
        platform = Platform.GENERIC

        @classmethod
        def _instantiate_rules(cls) -> HConfigDriverRules:
            return load_platform_rules(
                Platform.GENERIC, post_load_callbacks=[_callback]
            )

    config = get_hconfig(_CustomDriver(), "hostname sw1\n")

    assert config.dump_simple() == ("hostname sw1", "from-subclass")


def test_callbacks_run_on_the_empty_config_for_get_hconfig_from_dump() -> None:
    """``get_hconfig_from_dump`` runs callbacks before the dump lines load.

    The constructor builds an empty ``HConfig`` (which triggers callbacks) and
    then appends the dumped lines, so callbacks observe an empty tree. This is
    asserted to pin the behavior rather than to endorse it.
    """
    driver = _driver()
    observed: list[tuple[str, ...]] = []

    def _callback(config: HConfig) -> None:
        observed.append(config.dump_simple())

    driver.rules.post_load_callbacks.append(_callback)
    dump = Dump(
        lines=(
            DumpLine(
                depth=1,
                text="hostname sw1",
                tags=frozenset(),
                comments=frozenset(),
                new_in_config=False,
            ),
        )
    )
    config = get_hconfig_from_dump(driver, dump)

    assert observed == [()]
    assert config.dump_simple() == ("hostname sw1",)


def test_custom_callback_can_delete_children() -> None:
    """Callbacks may prune the tree, not just append to it.

    A realistic consumer callback drops interfaces that carry no configuration,
    which requires iterating over a snapshot while mutating the live tree.
    """
    driver = HConfigDriverCiscoIOS()

    def _drop_empty_interfaces(config: HConfig) -> None:
        for interface in tuple(config.get_children(startswith="interface ")):
            if not interface.children:
                interface.delete()

    driver.rules.post_load_callbacks.append(_drop_empty_interfaces)
    config = get_hconfig(
        driver,
        "hostname sw1\n"
        "interface GigabitEthernet1/0/1\n"
        " shutdown\n"
        "interface GigabitEthernet1/0/2\n"
        "interface TenGigabitEthernet1/0/49\n",
    )

    assert config.dump_simple() == (
        "hostname sw1",
        "interface GigabitEthernet1/0/1",
        "  shutdown",
    )


def test_custom_callback_can_rewrite_child_text() -> None:
    """Assigning to ``child.text`` from a callback rewrites the parsed line.

    Multi-line banners arrive with escape sequences intact, so consumers
    normalize them in place rather than re-parsing the config.
    """
    driver = HConfigDriverHPProcurve()

    def _flatten_banner(config: HConfig) -> None:
        for banner in config.get_children(startswith="banner motd "):
            banner.text = banner.text.replace("\\n", " ").replace("\\'", "'")

    driver.rules.post_load_callbacks.append(_flatten_banner)
    config = get_hconfig(
        driver,
        'banner motd "Property of ACME\\nNo access. Don\\\'t try."\n!\n',
    )

    assert config.dump_simple() == (
        'banner motd "Property of ACME No access. Don\'t try."',
    )


# ---------------------------------------------------------------------------
# Code-injected rules: parse-time
# ---------------------------------------------------------------------------


def test_inject_full_text_sub_rule() -> None:
    """``full_text_sub`` rewrites the config before it is parsed."""
    driver = _driver()
    driver.rules.full_text_sub.append(
        FullTextSubRule(search="SECRET", replace="REDACTED")
    )

    assert get_hconfig(driver, "hostname SECRET\n").dump_simple() == (
        "hostname REDACTED",
    )


def test_inject_per_line_sub_rule() -> None:
    """``per_line_sub`` applies on both the full and fast parse paths."""
    driver = _driver()
    driver.rules.per_line_sub.append(PerLineSubRule(search=r"^\s*#.*$", replace=""))
    lines = ["# a banner comment", "hostname sw1"]

    assert get_hconfig_fast_load(driver, lines).dump_simple() == ("hostname sw1",)
    assert get_hconfig(driver, "\n".join(lines)).dump_simple() == ("hostname sw1",)


def test_inject_indent_adjust_rule() -> None:
    """``indent_adjust`` folds a delimited block into a single line."""
    driver = _driver()
    driver.rules.indent_adjust.append(
        IndentAdjustRule(start_expression=r"^\s*banner", end_expression=r"^\s*EOF")
    )
    config = get_hconfig(driver, "banner motd\nline one\nEOF\nhostname sw1\n")

    assert config.dump_simple() == ("banner motd\nline one\nEOF", "hostname sw1")


def test_inject_parent_allows_duplicate_child_rule() -> None:
    """``parent_allows_duplicate_child`` suppresses ``DuplicateChildError``."""
    raw = "route-map RM permit 10\n match ip address 1\n match ip address 1\n"
    driver = _driver()
    driver.rules.parent_allows_duplicate_child.append(
        ParentAllowsDuplicateChildRule(match_rules=(MatchRule(startswith="route-map"),))
    )
    config = get_hconfig(driver, raw)

    assert config.dump_simple() == (
        "route-map RM permit 10",
        "  match ip address 1",
        "  match ip address 1",
    )


def test_inject_indentation_via_instantiate_rules() -> None:
    """``indentation`` is a frozen scalar, so it is set at construction time."""
    driver = _driver()
    setter: Callable[[str, int], None] = driver.rules.__setattr__
    with pytest.raises(ValueError, match="frozen"):
        setter("indentation", 4)

    driver.rules = load_platform_rules(Platform.GENERIC).model_copy(
        update={"indentation": 4}
    )
    config = get_hconfig(driver, "interface Ethernet1\n    description uplink\n")

    assert driver.rules.indentation == 4
    assert config.dump_simple() == ("interface Ethernet1", "    description uplink")


# ---------------------------------------------------------------------------
# Code-injected rules: remediation-time
# ---------------------------------------------------------------------------


def _remediate(
    driver: HConfigDriverBase, running: str, intended: str
) -> tuple[str, ...]:
    """Build both configs with ``driver`` and return the remediation lines."""
    running_config = get_hconfig(driver, running)
    intended_config = get_hconfig(driver, intended)
    return running_config.config_to_get_to(intended_config).dump_simple()


def test_inject_idempotent_commands_rule() -> None:
    """``idempotent_commands`` collapses a replace into a single set command."""
    driver = _driver()
    driver.rules.idempotent_commands.append(
        IdempotentCommandsRule(match_rules=(MatchRule(startswith="hostname"),))
    )

    assert _remediate(driver, "hostname old\n", "hostname new\n") == ("hostname new",)


def test_inject_idempotent_commands_avoid_rule() -> None:
    """``idempotent_commands_avoid`` wins over a matching idempotency rule."""
    driver = _driver()
    driver.rules.idempotent_commands.append(
        IdempotentCommandsRule(match_rules=(MatchRule(startswith="hostname"),))
    )
    driver.rules.idempotent_commands_avoid.append(
        IdempotentCommandsAvoidRule(match_rules=(MatchRule(startswith="hostname"),))
    )

    assert _remediate(driver, "hostname old\n", "hostname new\n") == (
        "no hostname old",
        "hostname new",
    )


def test_inject_negation_default_when_rule() -> None:
    """``negation_default_when`` switches ``no`` to ``default``."""
    driver = _driver()
    driver.rules.negation_default_when.append(
        NegationDefaultWhenRule(match_rules=(MatchRule(startswith="logging"),))
    )

    assert _remediate(driver, "logging console\n", "") == ("default logging console",)


def test_inject_negate_with_rule() -> None:
    """``negate_with`` replaces the negation line outright."""
    driver = _driver()
    driver.rules.negate_with.append(
        NegationDefaultWithRule(
            match_rules=(MatchRule(startswith="spanning-tree"),),
            use="default spanning-tree",
        )
    )

    assert _remediate(driver, "spanning-tree mode rapid-pvst\n", "") == (
        "default spanning-tree",
    )


def test_inject_negation_sub_rule() -> None:
    """``negation_sub`` regex-rewrites the already-negated line."""
    driver = _driver()
    driver.rules.negation_sub.append(
        NegationSubRule(
            match_rules=(MatchRule(startswith="snmp-server user"),),
            search=r"^(no snmp-server user \S+).*$",
            replace=r"\1",
        )
    )
    running = "snmp-server user bob group1 auth md5 secret\n"

    assert _remediate(driver, running, "") == ("no snmp-server user bob",)


def test_inject_sectional_overwrite_rule() -> None:
    """``sectional_overwrite`` negates then re-declares the whole section."""
    driver = _driver()
    driver.rules.sectional_overwrite.append(
        SectionalOverwriteRule(match_rules=(MatchRule(startswith="template"),))
    )

    assert _remediate(driver, "template T1\n a 1\n", "template T1\n b 2\n") == (
        "no template T1",
        "template T1",
        "  b 2",
    )


def test_inject_sectional_overwrite_no_negate_rule() -> None:
    """``sectional_overwrite_no_negate`` re-declares without the negation."""
    driver = _driver()
    driver.rules.sectional_overwrite_no_negate.append(
        SectionalOverwriteNoNegateRule(match_rules=(MatchRule(startswith="template"),))
    )

    assert _remediate(driver, "template T1\n a 1\n", "template T1\n b 2\n") == (
        "template T1",
        "  b 2",
    )


def test_inject_sectional_exiting_rule() -> None:
    """``sectional_exiting`` appends the exit line to rendered remediation."""
    driver = _driver()
    driver.rules.sectional_exiting.append(
        SectionalExitingRule(
            match_rules=(MatchRule(startswith="router bgp"),), exit_text="exit"
        )
    )
    running = get_hconfig(driver, "")
    intended = get_hconfig(driver, "router bgp 65000\n neighbor 1.1.1.1 remote-as 1\n")
    remediation = running.config_to_get_to(intended)

    assert remediation.dump_simple(sectional_exiting=True) == (
        "router bgp 65000",
        "  neighbor 1.1.1.1 remote-as 1",
        "  exit",
    )


def test_inject_ordering_rule() -> None:
    """``ordering`` weights reorder ``all_children_sorted`` output."""
    driver = _driver()
    driver.rules.ordering.append(
        OrderingRule(match_rules=(MatchRule(startswith="zzz"),), weight=-500)
    )
    running = get_hconfig(driver, "")
    intended = get_hconfig(driver, "aaa command\nzzz command\n")
    remediation = running.config_to_get_to(intended)
    remediation.set_order_weight()

    assert tuple(child.text for child in remediation.all_children_sorted()) == (
        "zzz command",
        "aaa command",
    )


# ---------------------------------------------------------------------------
# Driver hook overrides: which subclass overrides still take effect
#
# Remediation, negation and section-exit resolution all run inside the Rust
# core, which reads the *rules* synced across the FFI boundary rather than
# calling back into Python. A subclass that overrides the corresponding
# ``HConfigDriverBase`` method could therefore never run. Rather than let
# that fail silently, defining one of those hooks raises ``TypeError`` at class
# creation. These tests pin that boundary so the regression cannot drift
# unnoticed, and demonstrate the supported rule-based equivalent.
# ---------------------------------------------------------------------------


def test_negation_prefix_override_is_honored() -> None:
    """``negation_prefix`` is synced to Rust, so a subclass override applies."""

    class Driver(HConfigDriverCiscoIOS):
        """Driver overriding the negation prefix."""

        @property
        def negation_prefix(self) -> str:
            return "undo "

    driver = Driver()
    assert _remediate(driver, "vlan 5\n", "") == ("undo vlan 5",)


def test_config_preprocessor_override_is_not_honored() -> None:
    """``config_preprocessor`` is resolved natively; the override never runs."""
    calls: list[str] = []

    class Driver(HConfigDriverCiscoIOS):
        """Driver overriding the config preprocessor."""

        @classmethod
        def config_preprocessor(cls, config_text: str) -> str:
            calls.append(config_text)
            return config_text.replace("SECRET", "REDACTED")

    config = get_hconfig(Driver(), "hostname SECRET\n")

    assert config.dump_simple() == ("hostname SECRET",)
    assert not calls


def _unreachable_hook(*_args: object, **_kwargs: object) -> None:
    """Stand-in body for a hook the v4 engine can never call."""
    raise NotImplementedError


@pytest.mark.parametrize(
    ("base", "hook"),
    (
        (HConfigDriverHPProcurve, "idempotent_for"),
        (HConfigDriverCiscoIOS, "negate_with"),
        (HConfigDriverCiscoIOS, "sectional_exit"),
    ),
)
def test_removed_driver_hook_override_raises(
    base: type[HConfigDriverBase], hook: str
) -> None:
    """Defining a removed hook fails loudly rather than being ignored."""
    with pytest.raises(TypeError, match=rf"{hook}\(\)"):
        type("Driver", (base,), {hook: _unreachable_hook})


def _procurve_tacacs_key_driver() -> HConfigDriverHPProcurve:
    """ProCurve driver carrying the rule that replaces the removed override.

    The capture group spans exactly the four words the old
    ``_idempotent_for_helper(..., stop_index=4)`` call kept, so the rule keys
    idempotency per ``host``/``encrypted-key`` pair.
    """
    driver = HConfigDriverHPProcurve()
    driver.rules.idempotent_commands.append(
        IdempotentCommandsRule(
            match_rules=(
                MatchRule(re_search=r"^(tacacs-server host \S+ encrypted-key) \S+$"),
            )
        )
    )
    return driver


@pytest.mark.parametrize(
    ("running", "intended", "expected"),
    (
        # A key rotation on the same host is idempotent: overwrite in place,
        # with no preceding negation. This is the case the override existed
        # for.
        (
            "tacacs-server host 10.0.0.1 encrypted-key OLDKEY\n",
            "tacacs-server host 10.0.0.1 encrypted-key NEWKEY\n",
            ("tacacs-server host 10.0.0.1 encrypted-key NEWKEY",),
        ),
        # A different host is a different key, so the rule must NOT collapse
        # the two lines into an overwrite.
        (
            "tacacs-server host 10.0.0.1 encrypted-key AAA\n",
            "tacacs-server host 10.0.0.2 encrypted-key BBB\n",
            (
                "no tacacs-server host 10.0.0.1",
                "tacacs-server host 10.0.0.2 encrypted-key BBB",
            ),
        ),
        # Depth guard: the override was gated on ``config.parent is
        # config.root``. A single-element ``match_rules`` reproduces that,
        # because lineage matching is an exact-length comparison, so a nested
        # line must not be treated as idempotent.
        (
            "interface 1\n  tacacs-server host 10.0.0.1 encrypted-key OLD\n",
            "interface 1\n  tacacs-server host 10.0.0.1 encrypted-key NEW\n",
            (
                "interface 1",
                "  no tacacs-server host 10.0.0.1 encrypted-key OLD",
                "  tacacs-server host 10.0.0.1 encrypted-key NEW",
            ),
        ),
    ),
)
def test_idempotent_commands_rule_replaces_idempotent_for_override(
    running: str, intended: str, expected: tuple[str, ...]
) -> None:
    """A capture-group rule is the supported equivalent of the override."""
    assert _remediate(_procurve_tacacs_key_driver(), running, intended) == expected


def test_idempotent_commands_rule_keys_independently_per_capture() -> None:
    """Unrelated hosts stay untouched because the capture group keys them."""
    remediation = _remediate(
        _procurve_tacacs_key_driver(),
        "tacacs-server host 1.1.1.1 encrypted-key OLD\n"
        "tacacs-server host 2.2.2.2 encrypted-key SAME\n",
        "tacacs-server host 1.1.1.1 encrypted-key NEW\n"
        "tacacs-server host 2.2.2.2 encrypted-key SAME\n",
    )

    assert remediation == ("tacacs-server host 1.1.1.1 encrypted-key NEW",)


def test_negate_with_rule_supports_capture_group_templates() -> None:
    """``use`` backreferences are the supported equivalent of the override."""
    driver = HConfigDriverCiscoIOS()
    driver.rules.negate_with.insert(
        0,
        NegationDefaultWithRule(
            match_rules=(MatchRule(re_search=r"^(radius-server timeout) \d+$"),),
            use=r"\1 5",
        ),
    )

    assert _remediate(driver, "radius-server timeout 30\n", "") == (
        "radius-server timeout 5",
    )
