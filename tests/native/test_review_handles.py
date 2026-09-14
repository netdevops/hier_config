"""Regression coverage for native handle lifetime and recursive Python metadata."""

from __future__ import annotations

import copy

# A subprocess is required to bound a regression that deadlocks the interpreter.
import subprocess  # ruff: ignore[suspicious-subprocess-import]
import sys
import textwrap
from collections.abc import Iterator

import pytest

from hier_config import HConfig, Platform
from hier_config.models import PerLineSubRule
from hier_config.platforms.generic.driver import HConfigDriverGeneric


@pytest.mark.parametrize(
    "name",
    (
        "text",
        "depth",
        "is_leaf",
        "is_branch",
        "tags",
        "children",
        "indentation",
        "parent",
        "root",
        "driver",
        "text_without_negation",
        "sectional_exit",
        "sectional_exit_text_parent_level",
        "real_indent_level",
        "order_weight",
        "new_in_config",
        "comments",
        "instances",
        "facts",
        "instance",
    ),
)
def test_deleted_handle_properties_raise(name: str) -> None:
    """A deleted node is not an empty, usable node, even after slot reuse."""
    config = HConfig.from_lines(Platform.GENERIC, ("acl", "  permit any"))
    acl = config.children["acl"]
    acl.delete()
    config.add_child("replacement")
    with pytest.raises(ValueError, match="deleted"):
        getattr(acl, name)
    assert config.to_lines() == ("replacement",)


@pytest.mark.parametrize(
    ("method", "args", "kwargs"),
    (
        ("get_children", (), {"startswith": "permit"}),
        ("get_child", (), {"startswith": "permit"}),
        ("get_children_deep", ((),), {}),
        ("get_child_deep", ((),), {}),
        ("path", (), {}),
        ("lineage", (), {}),
        ("all_children", (), {}),
        ("all_children_sorted", (), {}),
        ("all_children_sorted_by_tags", (), {}),
        ("lines", (), {}),
        ("to_lines", (), {}),
        ("dump_simple", (), {}),
        ("add_tags", ("tag",), {}),
        ("remove_tags", ("tag",), {}),
        ("add_child", ("new",), {}),
        ("add_children", ((),), {}),
        ("add_children_deep", ((),), {}),
        ("del_child_by_text", ("missing",), {}),
        ("delete_sectional_exit", (), {}),
        ("use_sectional_overwrite", (), {}),
        ("use_sectional_overwrite_without_negation", (), {}),
        ("negate", (), {}),
        ("_default", (), {}),
        ("delete", (), {}),
        ("is_match", (), {"equals": "acl"}),
        ("is_lineage_match", ((),), {}),
        ("is_idempotent_command", ((),), {}),
        ("line_inclusion_test", ((), ()), {}),
        ("indented_text", (), {}),
        ("__len__", (), {}),
        ("__bool__", (), {}),
        ("__iter__", (), {}),
        ("__contains__", ("permit",), {}),
        ("__repr__", (), {}),
        ("__str__", (), {}),
        ("__hash__", (), {}),
    ),
)
def test_deleted_handle_methods_raise(
    method: str, args: tuple[object, ...], kwargs: dict[str, object]
) -> None:
    """Every handle operation rejects stale IDs without poisoning the tree."""
    config = HConfig.from_lines(Platform.GENERIC, ("acl", "  permit any"))
    acl = config.children["acl"]
    acl.delete()
    with pytest.raises(ValueError, match="deleted"):
        getattr(acl, method)(*args, **kwargs)
    assert config.to_lines() == ()


@pytest.mark.parametrize("method", ("move_child", "del_child", "add_shallow_copy_of"))
def test_stale_source_handle_rejected(method: str) -> None:
    """Mutators validate the supplied handle as well as their receiver."""
    config = HConfig.from_lines(Platform.GENERIC, ("acl", "other"))
    acl = config.children["acl"]
    acl.delete()
    with pytest.raises(ValueError, match="deleted"):
        getattr(config, method)(acl)
    assert config.to_lines() == ("other",)


@pytest.mark.parametrize(
    ("name", "value"),
    (
        ("text", "replacement"),
        ("tags", ("tag",)),
        ("real_indent_level", 2),
        ("order_weight", 10),
        ("new_in_config", True),
        ("comments", {"comment"}),
        ("instances", []),
        ("facts", {}),
    ),
)
def test_deleted_handle_setters_raise(name: str, value: object) -> None:
    """Metadata setters must not silently revive an invalid handle."""
    config = HConfig.from_lines(Platform.GENERIC, ("acl",))
    acl = config.children["acl"]
    acl.delete()
    with pytest.raises(ValueError, match="deleted"):
        setattr(acl, name, value)
    assert config.to_lines() == ()


@pytest.mark.parametrize(
    "method",
    (
        "move_child",
        "del_child",
        "add_shallow_copy_of",
        "add_deep_copy_of",
        "move",
        "use_default_for_negation",
        "unified_diff",
        "__lt__",
        "__eq__",
        "__ne__",
    ),
)
def test_deleted_receiver_with_live_argument_raises(method: str) -> None:
    """Methods taking another node still validate their receiver."""
    config = HConfig.from_lines(Platform.GENERIC, ("acl", "other"))
    acl = config.children["acl"]
    other = config.children["other"]
    acl.delete()
    with pytest.raises(ValueError, match="deleted"):
        getattr(acl, method)(other)
    assert config.to_lines() == ("other",)


@pytest.mark.parametrize(
    ("method", "args"),
    (
        ("clear", ()),
        ("rebuild_mapping", ()),
        ("extend", ((),)),
        ("__len__", ()),
        ("__iter__", ()),
        ("__repr__", ()),
        ("__hash__", ()),
        ("__contains__", ("missing",)),
        ("__getitem__", ("missing",)),
        ("__getitem__", (0,)),
        ("__getitem__", (slice(None),)),
        ("__eq__", (None,)),
        ("__ne__", (None,)),
    ),
)
def test_deleted_children_container_methods_raise(
    method: str, args: tuple[object, ...]
) -> None:
    """Container special methods consistently report an invalid parent."""
    config = HConfig.from_lines(Platform.GENERIC, ("acl",))
    acl = config.children["acl"]
    children = acl.children
    acl.delete()
    with pytest.raises(ValueError, match="deleted"):
        getattr(children, method)(*args)
    assert config.to_lines() == ()


def test_iterator_rejects_deleted_child() -> None:
    """An iterator snapshot cannot return a valid-looking deleted handle."""
    config = HConfig.from_lines(Platform.GENERIC, ("acl",))
    children = iter(config.children)
    config.children["acl"].delete()
    with pytest.raises(ValueError, match="deleted"):
        next(children)
    assert config.to_lines() == ()


@pytest.mark.parametrize("method", ("move_child", "del_child"))
def test_foreign_handle_does_not_mutate_same_slot(method: str) -> None:
    """Equal arena slot numbers in distinct trees never imply node ownership."""
    config = HConfig.from_lines(Platform.GENERIC, ("local",))
    foreign = HConfig.from_lines(Platform.GENERIC, ("foreign",))
    with pytest.raises(ValueError, match="another configuration"):
        getattr(config, method)(foreign.children["foreign"])
    assert config.to_lines() == ("local",)
    assert foreign.to_lines() == ("foreign",)


@pytest.mark.parametrize("method", ("append", "delete", "index", "__setitem__"))
def test_children_container_rejects_deleted_source(method: str) -> None:
    """Collection mutations and lookups reject stale source handles."""
    config = HConfig.from_lines(Platform.GENERIC, ("acl", "other"))
    acl = config.children["acl"]
    acl.delete()
    args = (0, acl) if method == "__setitem__" else (acl,)
    with pytest.raises(ValueError, match="deleted"):
        getattr(config.children, method)(*args)
    assert config.to_lines() == ("other",)


@pytest.mark.parametrize("stale_argument", ("source", "target", "delta"))
def test_overwrite_rejects_deleted_handles(stale_argument: str) -> None:
    """Overwrite checks all participants, including aliased source/delta trees."""
    config = HConfig.from_lines(Platform.GENERIC, ("source", "target", "delta"))
    source, target, delta = tuple(config.children)
    config.children[stale_argument].delete()
    with pytest.raises(ValueError, match="deleted"):
        source.overwrite_with(target, delta)
    assert len(config.to_lines()) == 2


def test_deepcopy_rejects_deleted_child() -> None:
    """A deleted handle cannot be copied into a valid-looking new wrapper."""
    config = HConfig.from_lines(Platform.GENERIC, ("acl",))
    acl = config.children["acl"]
    acl.delete()
    with pytest.raises(ValueError, match="deleted"):
        copy.deepcopy(acl)
    assert config.to_lines() == ()


def test_parent_follows_moves_through_another_handle() -> None:
    """Cached constructor parents cannot hide a subsequent arena-level move."""
    config = HConfig.from_lines(Platform.GENERIC, ("first", "second"))
    first = config.children["first"]
    second = config.children["second"]
    child = first.add_child("child")
    assert child.parent is first
    second.move_child(child)
    assert child.parent is second


@pytest.mark.parametrize("method", ("get", "append", "delete", "index"))
def test_deleted_children_container_rejected(method: str) -> None:
    """Previously fetched containers cannot operate on a deleted parent."""
    config = HConfig.from_lines(Platform.GENERIC, ("acl", "other"))
    acl = config.children["acl"]
    children = acl.children
    other = config.children["other"]
    acl.delete()
    argument = "missing" if method == "get" else other
    with pytest.raises(ValueError, match="deleted"):
        getattr(children, method)(argument)
    assert config.to_lines() == ("other",)


def test_recursive_deepcopy_preserves_memo_and_shared_facts() -> None:
    """Root references and shared metadata must resolve to the copied graph."""
    config = HConfig.from_lines(Platform.GENERIC, ("acl", "other"))
    acl = config.children["acl"]
    facts: dict[str, object] = {"root": config, "values": []}
    acl.facts = facts
    config.children["other"].facts = facts
    copied = copy.deepcopy(config)
    copied_facts = copied.children["acl"].facts
    assert copied_facts["root"] is copied
    assert copied_facts is copied.children["other"].facts
    assert copied_facts is not facts
    assert copied_facts["values"] is not facts["values"]


@pytest.mark.parametrize("copy_child_first", (False, True))
def test_deepcopy_preserves_child_cycles(*, copy_child_first: bool) -> None:
    """Copying either entry point preserves root/child self-references."""
    config = HConfig.from_lines(Platform.GENERIC, ("acl",))
    acl = config.children["acl"]
    acl.facts["self"] = acl
    acl.facts["root"] = config
    memo: dict[int, object] = {}
    if copy_child_first:
        copied_acl = copy.deepcopy(acl, memo)
        copied = copied_acl.root
    else:
        copied = copy.deepcopy(config, memo)
        copied_acl = copied.children["acl"]
    assert copied_acl.facts["self"] is copied_acl
    assert copied_acl.facts["root"] is copied
    assert memo[id(config)] is copied
    assert memo[id(acl)] is copied_acl


def test_deepcopy_metadata_callback_can_read_original_facts() -> None:
    """A subprocess timeout detects locks held across user-defined deepcopy."""
    code = textwrap.dedent(
        """
        import copy
        from hier_config import HConfig, Platform

        config = HConfig.from_lines(Platform.GENERIC, ("acl",))
        acl = config.children["acl"]

        class Fact:
            def __deepcopy__(self, memo):
                assert acl.facts["value"] is self
                return "copied"

        acl.facts["value"] = Fact()
        copied = copy.deepcopy(config)
        assert copied.children["acl"].facts["value"] == "copied"
        """
    )
    # Execute only this literal probe; a timeout prevents a deadlock hanging pytest.
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, result.stderr


def test_query_results_are_iterators() -> None:
    """Query and diff methods retain the next()-compatible v4 contract."""
    config = HConfig.from_lines(Platform.GENERIC, ("acl", "  permit any"))
    acl = config.children["acl"]
    results = (
        config.get_children(startswith="acl"),
        config.get_children_deep(()),
        acl.lineage(),
        acl.path(),
        config.unified_diff(config),
    )
    for result in results:
        assert isinstance(result, Iterator)
        assert iter(result) is result


def test_remove_missing_tag_raises_key_error() -> None:
    """Removing a tag uses set.remove semantics rather than discard."""
    config = HConfig.from_lines(Platform.GENERIC, ("acl",))
    acl = config.children["acl"]
    acl.add_tags("present")
    with pytest.raises(KeyError, match="missing"):
        acl.remove_tags("missing")
    assert acl.tags == frozenset({"present"})


def test_remove_tag_iterable_ignores_absent_tags() -> None:
    """Iterable removal retains set.difference_update semantics."""
    config = HConfig.from_lines(Platform.GENERIC, ("acl",))
    acl = config.children["acl"]
    acl.add_tags("present")
    acl.remove_tags(("present", "missing"))
    assert acl.tags == frozenset()


def test_remove_string_tag_checks_each_leaf() -> None:
    """Branch string removal uses set.remove for each leaf, in tree order."""
    config = HConfig.from_lines(Platform.GENERIC, ("acl", "  first", "  second"))
    acl = config.children["acl"]
    acl.children["first"].add_tags("tag")
    with pytest.raises(KeyError, match="tag"):
        acl.remove_tags("tag")
    assert acl.children["first"].tags == frozenset()


def test_custom_driver_name_does_not_select_builtin_platform() -> None:
    """Only the declared platform selects native operations, not a class name."""
    custom_type = type(
        "HConfigDriverJuniperJUNOS", (HConfigDriverGeneric,), {"platform": None}
    )
    config = HConfig.from_text(custom_type(), "system {\n host-name router;\n}")
    assert config.to_lines() == ("system {", "  host-name router;", "}")


@pytest.mark.parametrize("platform", ("not-a-platform", "", 17, object()))
@pytest.mark.parametrize(
    "constructor", ("new", "from_text", "from_lines", "from_json", "from_xml")
)
def test_invalid_explicit_driver_platform_is_rejected(
    monkeypatch: pytest.MonkeyPatch, platform: object, constructor: str
) -> None:
    """Bad platform metadata must not silently fall back to Generic."""
    monkeypatch.setattr(HConfigDriverGeneric, "platform", platform)
    driver = HConfigDriverGeneric()
    payloads: dict[str, object] = {
        "from_text": "hostname router",
        "from_lines": ("hostname router",),
        "from_json": "{}",
        "from_xml": "<config/>",
    }
    if constructor == "new":
        with pytest.raises(ValueError, match="platform"):
            HConfig(driver)
    else:
        with pytest.raises(ValueError, match="platform"):
            getattr(HConfig, constructor)(driver, payloads[constructor])


def test_valid_explicit_string_platform_selects_native_operations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Recognized string platform selectors remain supported."""
    monkeypatch.setattr(HConfigDriverGeneric, "platform", "juniper_junos")
    config = HConfig.from_text(
        HConfigDriverGeneric(), "system {\n host-name router;\n}"
    )
    assert config.to_lines() == ("set host-name router",)


def test_invalid_driver_regex_rejected_before_tree_construction() -> None:
    """Even an empty native tree validates serialized driver rule data."""
    driver = HConfigDriverGeneric()
    driver.rules.per_line_sub.append(PerLineSubRule(search="[", replace=""))
    with pytest.raises(ValueError, match="per_line_sub"):
        HConfig(driver)


@pytest.mark.parametrize("method", ("negate", "is_idempotent_command"))
def test_invalid_mutated_driver_regex_is_a_python_error(method: str) -> None:
    """Refreshing mutable rule collections cannot panic or poison a handle."""
    driver = HConfigDriverGeneric()
    config = HConfig.from_lines(driver, ("command",))
    child = config.children["command"]
    driver.rules.per_line_sub.append(PerLineSubRule(search="[", replace=""))
    args = ((),) if method == "is_idempotent_command" else ()
    with pytest.raises(ValueError, match="per_line_sub"):
        getattr(child, method)(*args)
    assert config.to_lines() == ("command",)
