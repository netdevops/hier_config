"""Regression coverage for the PyO3 binding findings raised on PR #302.

Each test pins one reviewer finding that was verified present at the head of
the Rust-rewrite branch and is fixed in `crates/hier_config_py/`. The test
names map one-to-one onto the finding identifiers used in the review.
"""

from __future__ import annotations

import functools
import gc
import pickle  # ruff: ignore[suspicious-pickle-import] # Round-trips locally built configs only.
import subprocess  # ruff: ignore[suspicious-subprocess-import] # Runs this interpreter on literal test code.
import sys
import textwrap
import weakref
from unittest.mock import MagicMock

import pytest

from hier_config import (
    HConfig,
    HConfigChild,
    HConfigDriverBase,
    MatchRule,
    Platform,
    WorkflowRemediation,
    get_hconfig,
    get_hconfig_driver,
)
from hier_config.models import Instance, OrderingRule, SectionalExitingRule

RUNNING = (
    "interface Vlan2",
    "  ip address 10.0.0.1 255.255.255.0",
    "  no shutdown",
)
GENERATED = (
    "interface Vlan2",
    "  ip address 10.0.0.2 255.255.255.0",
    "  no shutdown",
)


def _driver() -> HConfigDriverBase:
    """A fresh generic driver; `get_hconfig_driver` never returns a shared one."""
    return get_hconfig_driver(Platform.GENERIC)


_POST_LOAD_CALLS: list[int] = []


def _recording_post_load_callback(config: HConfig) -> None:
    """A picklable post-load callback that records each invocation.

    It has to be defined at module scope: pickling a config pickles its driver,
    which pickles the driver's callbacks, and a local lambda is not picklable.
    """
    del config
    _POST_LOAD_CALLS.append(1)


def _run_isolated(code: str, *, timeout: float = 30.0) -> None:
    """Run `code` in a fresh interpreter, failing instead of hanging.

    The deadlock and leak checks need a clean heap and must not be able to
    wedge the suite, so they run out of process under a timeout.
    """
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [sys.executable, "-c", textwrap.dedent(code)],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    assert result.returncode == 0, result.stdout + result.stderr


# --------------------------------------------------------------------------
# MF-1 - the tree held a strong reference back to the config, so none was freed
# --------------------------------------------------------------------------


def test_mf1_parsed_config_is_collected() -> None:
    """A parsed config is freed once the last Python reference goes away."""
    config = HConfig.from_lines(Platform.GENERIC, RUNNING)
    ref = weakref.ref(config)
    assert ref() is not None

    del config
    gc.collect()

    assert ref() is None


def test_mf1_derived_trees_are_collected() -> None:
    """Trees produced by the diff and copy paths are freed like parsed ones."""
    running = HConfig.from_lines(Platform.GENERIC, RUNNING)
    generated = HConfig.from_lines(Platform.GENERIC, GENERATED)

    derived = {
        "deep_copy": running.deep_copy(),
        "config_to_get_to": running.config_to_get_to(generated),
        "future": running.future(generated),
        "difference": running.difference(generated),
    }
    refs = {name: weakref.ref(value) for name, value in derived.items()}

    derived.clear()
    gc.collect()

    assert [name for name, ref in refs.items() if ref() is not None] == []


def test_mf1_remediation_tree_is_collected() -> None:
    """The remediation config a workflow builds is not immortal either."""
    workflow = WorkflowRemediation(
        HConfig.from_lines(Platform.GENERIC, RUNNING),
        HConfig.from_lines(Platform.GENERIC, GENERATED),
    )
    ref = weakref.ref(workflow.remediation_config)

    del workflow
    gc.collect()

    assert ref() is None


def test_mf1_repeated_parses_do_not_accumulate() -> None:
    """Repeated parse and remediate cycles must not retain every tree."""
    _run_isolated(
        """
        import gc
        import weakref

        from hier_config import HConfig, Platform, WorkflowRemediation

        running = ("interface Vlan2", "  ip address 10.0.0.1 255.255.255.0")
        generated = ("interface Vlan2", "  ip address 10.0.0.2 255.255.255.0")

        refs = []
        for _ in range(50):
            workflow = WorkflowRemediation(
                HConfig.from_lines(Platform.GENERIC, running),
                HConfig.from_lines(Platform.GENERIC, generated),
            )
            refs.append(weakref.ref(workflow.remediation_config))
            del workflow

        gc.collect()

        alive = [ref for ref in refs if ref() is not None]
        assert not alive, f"{len(alive)} of {len(refs)} remediation trees leaked"
        """
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Known limitation: cycles closing through `HConfigChild.facts` are not "
        "collectable. `PyHConfig.__traverse__` cannot safely report the fact "
        "objects, because they live behind the shared tree's `RwLock` and "
        "`__traverse__` must never block while the GC is running."
    ),
)
def test_mf1_config_in_python_cycle_is_collectable() -> None:
    """A config caught in a Python-level cycle is still reclaimed by the GC.

    This is what `__traverse__`/`__clear__` buy: the reference from `facts`
    back to the config is only visible to CPython if the class participates
    in garbage collection.
    """
    _run_isolated(
        """
        import gc
        import weakref

        from hier_config import HConfig, Platform

        config = HConfig.from_lines(Platform.GENERIC, ("acl", "  permit any"))
        config.children["acl"].facts["cycle"] = {"config": config}

        ref = weakref.ref(config)
        del config
        gc.collect()

        assert ref() is None, "cycle through the config was not collected"
        """
    )


# --------------------------------------------------------------------------
# SF-1 - a callback without __name__ broke every tree creation
# --------------------------------------------------------------------------


def _marker_callback(config: HConfig, marker: str) -> None:
    config.add_child(marker)


def test_sf1_partial_post_load_callback_is_accepted() -> None:
    """`functools.partial` has no `__name__`; it must be skipped, not fatal."""
    driver = _driver()
    driver.rules.post_load_callbacks.append(
        functools.partial(_marker_callback, marker="from-partial")
    )

    # Construction is the operation that used to raise AttributeError.
    config = HConfig(driver)

    assert config.to_lines() == ()


def test_sf1_partial_post_load_callback_via_get_hconfig() -> None:
    """The full-parse constructor tolerates a `partial` callback too."""
    driver = _driver()
    driver.rules.post_load_callbacks.append(
        functools.partial(_marker_callback, marker="from-partial")
    )

    config = get_hconfig(driver, "hostname sw1\n")

    assert config.dump_simple() == ("hostname sw1", "from-partial")


def test_sf1_callable_object_post_load_callback_is_accepted() -> None:
    """A callable instance also lacks `__name__` and must not raise."""

    class Callback:  # pylint: disable=too-few-public-methods
        """A callable object whose `__name__` lookup raises `AttributeError`."""

        def __call__(self, config: HConfig) -> None:
            config.add_child("from-callable")

    driver = _driver()
    driver.rules.post_load_callbacks.append(Callback())

    assert HConfig(driver).to_lines() == ()


def test_sf1_lambda_post_load_callback_is_accepted() -> None:
    """A lambda's `__name__` is not a real rule name; it must be tolerated."""
    driver = _driver()
    driver.rules.post_load_callbacks.append(lambda _config: None)

    assert HConfig(driver).to_lines() == ()


# --------------------------------------------------------------------------
# SF-2 - rule changes made after the parse were silently ignored
# --------------------------------------------------------------------------


def test_sf2_ordering_rule_applied_after_parse() -> None:
    """A new `OrderingRule` reorders the output once re-applied.

    Ordering weights are stored on each child, and `set_order_weight()` is the
    only thing that walks the driver's ordering rules and assigns them; nothing
    recomputes them at dump time. So a rule added post-parse takes effect once
    `set_order_weight()` re-applies it, matching v3 semantics.
    """
    config = HConfig.from_lines(Platform.GENERIC, ("aaa", "zzz"))
    driver = config.driver

    driver.rules = driver.rules.model_copy(
        update={
            "ordering": [
                *driver.rules.ordering,
                OrderingRule(match_rules=(MatchRule(equals="zzz"),), weight=-500),
            ]
        }
    )
    config.set_order_weight()

    assert config.to_lines() == ("zzz", "aaa")


def test_sf2_sectional_exiting_rule_applied_after_parse() -> None:
    """A new `SectionalExitingRule` changes the exit line post-parse."""
    config = HConfig.from_lines(Platform.GENERIC, ("acl", "  permit any"))
    driver = config.driver

    driver.rules = driver.rules.model_copy(
        update={
            "sectional_exiting": [
                *driver.rules.sectional_exiting,
                SectionalExitingRule(
                    match_rules=(MatchRule(equals="acl"),), exit_text="exit-foo"
                ),
            ]
        }
    )

    assert config.children["acl"].sectional_exit == "exit-foo"


def test_sf2_dump_simple_reflects_new_sectional_rule() -> None:
    """`dump_simple` re-reads the driver's rules rather than a stale copy."""
    config = HConfig.from_lines(Platform.GENERIC, ("acl", "  permit any"))
    driver = config.driver

    driver.rules = driver.rules.model_copy(
        update={
            "sectional_exiting": [
                *driver.rules.sectional_exiting,
                SectionalExitingRule(
                    match_rules=(MatchRule(equals="acl"),), exit_text="exit-foo"
                ),
            ]
        }
    )

    assert any(
        "exit-foo" in line for line in config.dump_simple(sectional_exiting=True)
    )


# --------------------------------------------------------------------------
# SF-8 - quadratic rendering, and Python running under the tree write lock
# --------------------------------------------------------------------------


def test_sf8_instances_property_reading_tree_does_not_deadlock() -> None:
    """Rendering must not hold the tree lock while calling into Python."""
    _run_isolated(
        """
        from hier_config import HConfig, Platform

        config = HConfig.from_lines(Platform.GENERIC, ("acl", "  permit any"))
        child = config.children["acl"]


        class Reentrant:
            def __init__(self, node):
                self._node = node

            @property
            def id(self):
                # Reads back through the tree while rendering is in progress.
                return len(self._node.children) or 1

            @property
            def comments(self):
                return {self._node.text}

            @property
            def tags(self):
                return set(self._node.tags)


        child.instances = [Reentrant(child)]

        # Would never return while the write lock was held across `getattr`.
        assert config.to_lines()
        assert child.cisco_style_text()
        """
    )


def test_sf8_rendering_scales_with_the_rendered_node() -> None:
    """Rendering one line must not walk the whole tree's Python metadata."""
    _run_isolated(
        """
        import time

        from hier_config import HConfig, Platform

        lines = []
        for index in range(400):
            lines.append(f"interface Ethernet{index}")
            lines.append(f"  description port-{index}")

        config = HConfig.from_lines(Platform.GENERIC, lines)
        # Give every node Python-side metadata so the old whole-map walk
        # would have had to visit all of it on every single render.
        for child in config.children:
            child.facts["seen"] = True

        start = time.perf_counter()
        for child in config.children:
            child.cisco_style_text()
        elapsed = time.perf_counter() - start

        assert elapsed < 10.0, f"per-line rendering took {elapsed:.2f}s"
        """,
        timeout=60.0,
    )


# --------------------------------------------------------------------------
# SF-9 - comments lived in a Python shadow store as well as the native one
# --------------------------------------------------------------------------


def test_sf9_comments_survive_deep_copy() -> None:
    """A comment added through the Python view is in the native tree."""
    config = HConfig.from_lines(Platform.GENERIC, ("acl", "  permit any"))
    config.children["acl"].comments.add("note")

    copied = config.deep_copy()

    assert set(copied.children["acl"].comments) == {"note"}


def test_sf9_add_is_reflected_in_dump() -> None:
    """A comment added through the view reaches `dump()`."""
    config = HConfig.from_lines(Platform.GENERIC, ("acl", "  permit any"))
    config.children["acl"].comments.add("note")

    acl_line = next(line for line in config.dump().lines if line.text == "acl")

    assert acl_line.comments == frozenset({"note"})


def test_sf9_discard_is_reflected_in_dump() -> None:
    """`discard` removes the comment from the single source of truth."""
    config = HConfig.from_lines(Platform.GENERIC, ("acl", "  permit any"))
    child = config.children["acl"]
    child.comments.add("note")
    child.comments.discard("note")

    acl_line = next(line for line in config.dump().lines if line.text == "acl")

    assert acl_line.comments == frozenset()
    assert set(child.comments) == set()


def test_sf9_comments_survive_future() -> None:
    """`future()` carries comments, as the v3 baseline did."""
    running = HConfig.from_lines(Platform.GENERIC, RUNNING)
    generated = HConfig.from_lines(Platform.GENERIC, GENERATED)
    running.children["interface Vlan2"].comments.add("note")

    future = running.future(generated)

    assert "note" in set(future.children["interface Vlan2"].comments)


def test_sf9_deep_copy_does_not_alias_the_source() -> None:
    """The copy owns its comments; mutating one must not move the other."""
    running = HConfig.from_lines(Platform.GENERIC, RUNNING)
    running.children["interface Vlan2"].comments.add("note")

    copied = running.deep_copy()
    copied.children["interface Vlan2"].comments.add("copy-only")

    assert set(running.children["interface Vlan2"].comments) == {"note"}
    assert set(copied.children["interface Vlan2"].comments) == {"note", "copy-only"}


def test_sf9_comments_view_is_live() -> None:
    """The view and the node are one store, not two that periodically resync."""
    config = HConfig.from_lines(Platform.GENERIC, ("acl", "  permit any"))
    child = config.children["acl"]

    view = child.comments
    view.add("first")
    assert "first" in set(child.comments)

    child.comments = {"second"}
    assert set(view) == {"second"}


def test_sf9_comments_set_operations() -> None:
    """The view keeps the mutable-set API v3 exposed."""
    config = HConfig.from_lines(Platform.GENERIC, ("acl", "  permit any"))
    comments = config.children["acl"].comments

    comments.update({"a", "b"})
    assert set(comments) == {"a", "b"}

    comments -= {"a"}
    assert set(comments) == {"b"}

    comments |= {"c"}
    assert set(comments) == {"b", "c"}

    comments.discard("missing")
    comments.remove("b")
    assert set(comments) == {"c"}

    comments.clear()
    assert not comments
    assert len(comments) == 0


# --------------------------------------------------------------------------
# SF-10 - dump() tags, and __pydantic_fields_set__
# --------------------------------------------------------------------------


def test_sf10_dump_tags_are_the_recursive_union() -> None:
    """A parent dumps the union of its children's tags, as v3 did."""
    config = HConfig.from_lines(Platform.GENERIC, ("interface Vlan2", "  no shutdown"))
    config.children["interface Vlan2"].children["no shutdown"].add_tags("t")

    parent = next(
        line for line in config.dump().lines if line.text == "interface Vlan2"
    )

    assert parent.tags == frozenset({"t"})


def test_sf10_dump_line_supports_model_copy_update() -> None:
    """`__pydantic_fields_set__` must be mutable for `model_copy(update=...)`."""
    config = HConfig.from_lines(Platform.GENERIC, ("acl",))
    line = config.dump().lines[0]

    updated = line.model_copy(update={"text": "changed"})

    assert updated.text == "changed"
    assert line.text == "acl"


def test_sf10_dump_lines_do_not_share_fields_set() -> None:
    """Each line gets its own set, so one copy cannot corrupt another."""
    config = HConfig.from_lines(Platform.GENERIC, ("a", "b"))
    first, second = config.dump().lines

    first.model_copy(update={"text": "changed"})

    assert second.text == "b"
    assert first.__pydantic_fields_set__ is not second.__pydantic_fields_set__


# --------------------------------------------------------------------------
# SF-11 - pickling lost data, and two classes could not pickle at all
# --------------------------------------------------------------------------


def test_sf11_hconfig_pickle_preserves_node_state() -> None:
    """`facts`, `order_weight` and comments survive a pickle round-trip."""
    config = HConfig.from_lines(Platform.GENERIC, ("acl", "  permit any"))
    child = config.children["acl"]
    child.facts["role"] = "edge"
    child.order_weight = 321
    child.comments.add("note")

    restored = pickle.loads(pickle.dumps(config))  # ruff: ignore[suspicious-pickle-usage]
    restored_child = restored.children["acl"]

    assert restored.to_lines() == config.to_lines()
    assert restored_child.facts == {"role": "edge"}
    assert restored_child.order_weight == 321
    assert set(restored_child.comments) == {"note"}


def test_sf11_hconfig_pickle_preserves_instances() -> None:
    """`instances` is carried across the pickle boundary, not dropped."""
    config = HConfig.from_lines(Platform.GENERIC, ("acl", "  permit any"))
    config.children["acl"].instances = [
        Instance(id=7, comments=frozenset(), tags=frozenset({"t"}))
    ]

    restored = pickle.loads(pickle.dumps(config))  # ruff: ignore[suspicious-pickle-usage]
    restored_instances = list(restored.children["acl"].instances)

    assert [instance.id for instance in restored_instances] == [7]
    assert restored_instances[0].tags == frozenset({"t"})


def test_sf11_hconfig_child_is_picklable() -> None:
    """`HConfigChild` pickles through its root, as v3 allowed."""
    config = HConfig.from_lines(Platform.GENERIC, ("acl", "  permit any"))
    child = config.children["acl"].children["permit any"]
    child.facts["role"] = "leaf"
    child.order_weight = 77

    restored = pickle.loads(pickle.dumps(child))  # ruff: ignore[suspicious-pickle-usage]

    assert restored.text == "permit any"
    assert restored.facts == {"role": "leaf"}
    assert restored.order_weight == 77
    assert restored.parent.text == "acl"


def test_sf11_workflow_remediation_is_picklable() -> None:
    """`WorkflowRemediation` pickles through its constructor arguments."""
    workflow = WorkflowRemediation(
        HConfig.from_lines(Platform.GENERIC, RUNNING),
        HConfig.from_lines(Platform.GENERIC, GENERATED),
    )
    expected = workflow.remediation_config.to_lines()

    restored = pickle.loads(pickle.dumps(workflow))  # ruff: ignore[suspicious-pickle-usage]

    assert restored.running_config.to_lines() == tuple(RUNNING)
    assert restored.generated_config.to_lines() == tuple(GENERATED)
    assert restored.remediation_config.to_lines() == expected


def test_sf11_pickle_does_not_depend_on_callbacks_rerunning() -> None:
    """Unpickling restores state rather than replaying post-load callbacks."""
    driver = _driver()
    _POST_LOAD_CALLS.clear()
    driver.rules.post_load_callbacks.append(_recording_post_load_callback)

    config = HConfig(driver)
    config.add_children_deep(("acl", "permit any"))
    config.children["acl"].facts["role"] = "edge"
    before = len(_POST_LOAD_CALLS)

    restored = pickle.loads(pickle.dumps(config))  # ruff: ignore[suspicious-pickle-usage]

    assert restored.to_lines() == config.to_lines()
    assert restored.children["acl"].facts == {"role": "edge"}
    assert len(_POST_LOAD_CALLS) == before


# --------------------------------------------------------------------------
# SF-12 - HConfigChild(parent, text) appended a duplicate
# --------------------------------------------------------------------------


def test_sf12_duplicate_child_construction_reuses_existing() -> None:
    """Constructing an existing line returns it instead of duplicating it."""
    config = HConfig.from_lines(Platform.GENERIC, ("no hostname r1",))
    HConfigChild(config, "no hostname r1")

    assert len(config.children) == 1
    assert config.to_lines() == ("no hostname r1",)


def test_sf12_distinct_child_construction_still_appends() -> None:
    """A genuinely new line is still added."""
    config = HConfig.from_lines(Platform.GENERIC, ("no hostname r1",))
    HConfigChild(config, "hostname r2")

    assert len(config.children) == 2


# --------------------------------------------------------------------------
# CF-8 - subclasses with a different __init__ signature failed
# --------------------------------------------------------------------------


def test_cf8_hconfig_subclass_with_extra_init_arguments() -> None:
    """A subclass may take extra positional and keyword arguments."""

    class LabelledConfig(HConfig):
        """An `HConfig` subclass whose `__init__` takes an extra argument."""

        def __init__(  # pyright: ignore[reportInconsistentConstructor] # The native `__new__` absorbs extra subclass arguments.
            self, driver: HConfigDriverBase, label: str
        ) -> None:
            super().__init__(driver)
            self.label = label

    config = LabelledConfig(_driver(), "site-a")

    assert config.label == "site-a"
    assert config.to_lines() == ()


def test_cf8_workflow_subclass_with_extra_init_arguments() -> None:
    """The workflow's `__new__` tolerates a subclass's extra parameters."""

    class LabelledWorkflow(WorkflowRemediation):
        """A `WorkflowRemediation` subclass with an extra `__init__` argument."""

        def __init__(  # pyright: ignore[reportInconsistentConstructor] # The native `__new__` absorbs extra subclass arguments.
            self,
            running_config: HConfig,
            generated_config: HConfig,
            label: str,
        ) -> None:
            super().__init__(running_config, generated_config)
            self.label = label

    workflow = LabelledWorkflow(
        HConfig.from_lines(Platform.GENERIC, RUNNING),
        HConfig.from_lines(Platform.GENERIC, GENERATED),
        "site-a",  # pyright: ignore[reportArgumentType] # Consumed by the subclass's `label`, not by `plugins`.
    )

    assert workflow.label == "site-a"
    assert workflow.remediation_config.to_lines()


def test_cf8_genuine_plugins_misuse_still_errors() -> None:
    """Tolerating extra arguments must not hide a bad `plugins` value."""
    with pytest.raises(TypeError):
        WorkflowRemediation(
            HConfig.from_lines(Platform.GENERIC, RUNNING),
            HConfig.from_lines(Platform.GENERIC, GENERATED),
            plugins=42,  # type: ignore[arg-type] # pyright: ignore[reportArgumentType] # Deliberately invalid.
        )


# --------------------------------------------------------------------------
# CF-9 - HConfigChildren diverged from the v3 API
# --------------------------------------------------------------------------


@pytest.mark.parametrize("operand", (1, None, 2.5, object()))
def test_cf9_contains_non_string_returns_false(operand: object) -> None:
    """A non-`str` operand is simply absent, not a `TypeError`."""
    config = HConfig.from_lines(Platform.GENERIC, ("acl",))

    assert (operand in config.children) is False


def test_cf9_contains_string_still_works() -> None:
    """The `str` path is unchanged."""
    config = HConfig.from_lines(Platform.GENERIC, ("acl",))

    assert "acl" in config.children
    assert "missing" not in config.children


def test_cf9_append_accepts_update_mapping_keyword() -> None:
    """`append(child, update_mapping=False)` is accepted, as in v3."""
    source = HConfig.from_lines(Platform.GENERIC, ("acl",))
    target = HConfig(_driver())

    target.children.append(source.children["acl"], update_mapping=False)

    assert target.to_lines() == ("acl",)


def test_cf9_append_default_update_mapping() -> None:
    """The default remains the mapping-updating behaviour."""
    source = HConfig.from_lines(Platform.GENERIC, ("acl",))
    target = HConfig(_driver())

    target.children.append(source.children["acl"])

    assert "acl" in target.children


# --------------------------------------------------------------------------
# N-4 - MagicMock(spec=HConfigDriverBase) failed at construction
#
# The thread is on `sync_rules` (crates/hier_config_py/src/tree.rs): a mocked
# driver's rule attributes are not real strings, which used to raise. They now
# fall back to the platform defaults.
#
# `platform` is deliberately *not* given the same tolerance. A spec'd MagicMock
# returns a child mock for `.platform`, which is indistinguishable from any
# other non-string object, so accepting it would also accept `17` and
# `object()` - regressing `test_invalid_explicit_driver_platform_is_rejected`,
# which pins that bad platform metadata must not silently become Generic. A
# driver that has no platform declares `platform = None`, exactly as
# `HConfigDriverBase` itself does.
# --------------------------------------------------------------------------


def _mock_driver() -> MagicMock:
    """A mocked driver using the supported no-platform declaration."""
    driver = MagicMock(spec=HConfigDriverBase)
    driver.platform = None
    return driver


def test_n4_magicmock_driver_constructs() -> None:
    """A mocked driver must not raise; it falls back to platform defaults."""
    config = HConfig(_mock_driver())

    assert config.to_lines() == ()


def test_n4_magicmock_driver_supports_parsing() -> None:
    """The mocked-driver config is usable, not merely constructible."""
    config = HConfig(_mock_driver())
    config.add_children_deep(("acl", "permit any"))

    assert config.to_lines() == ("acl", "  permit any")


def test_n4_magicmock_driver_platform_is_still_validated() -> None:
    """Tolerating mocked rules must not tolerate bad platform metadata."""
    with pytest.raises(ValueError, match="platform"):
        HConfig(MagicMock(spec=HConfigDriverBase))


# --------------------------------------------------------------------------
# MaxDepthExceeded - the v3 RecursionError behaviour is restored
# --------------------------------------------------------------------------


def _descend(node: HConfig | HConfigChild, depth: int) -> None:
    """Append `depth` nested children, one per level, below `node`."""
    for index in range(depth):
        node = node.add_child(f"level-{index}")


def test_max_depth_raises_recursion_error() -> None:
    """An absurdly deep config raises `RecursionError`, not a panic or abort."""
    config = HConfig(_driver())

    with pytest.raises(RecursionError):
        _descend(config, 1_500)
