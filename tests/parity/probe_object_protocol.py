"""Probe script for verifying parity with the legacy object protocol."""

from __future__ import annotations

import copy
import pickle  # ruff: ignore[suspicious-pickle-import] - round-trip only objects constructed here
import sys
from typing import TYPE_CHECKING, cast

from hier_config import HConfigChild, get_hconfig
from hier_config.base import HConfigBase
from hier_config.models import Platform

if TYPE_CHECKING:
    from collections.abc import Callable

    from hier_config import HConfig

_CUSTOM_ATTRIBUTE = "custom_attr"


def _attempt(operation: Callable[[], str]) -> str:
    """Capture backend-specific failures as parity data rather than aborting."""
    try:
        return operation()
    # Every exception is recorded, including unexpected backend failures.
    except Exception as exc:  # ruff: ignore[blind-except]  # pylint: disable=broad-exception-caught
        return f"{type(exc).__name__}: {exc}"


def _set_attribute(child: HConfigChild) -> str:
    try:
        setattr(child, _CUSTOM_ATTRIBUTE, "hello_probe")
    except AttributeError:
        return "AttributeError (has __slots__)"
    return str(getattr(child, _CUSTOM_ATTRIBUTE))


def _unpickle(config: HConfig) -> HConfig:
    # The payload is produced locally immediately before loading, never input.
    return cast("HConfig", pickle.loads(pickle.dumps(config)))  # ruff: ignore[suspicious-pickle-usage]


def _subclass() -> str:
    # A single method is sufficient to prove that native nodes are subclassable.
    class CustomChild(HConfigChild):  # pylint: disable=too-few-public-methods
        """Subclass probe."""

        def custom_method(self) -> str:
            return f"custom: {self.text}"

    return f"OK {CustomChild.__name__}"


def _representation(value: object) -> str:
    try:
        return repr(value)
    # Preserve backend-specific repr failures as baseline data.
    except Exception as exc:  # ruff: ignore[blind-except]  # pylint: disable=broad-exception-caught
        return type(exc).__name__


def _is_base(value: object) -> bool:
    return isinstance(value, HConfigBase)


def probe() -> str:
    hc = get_hconfig(Platform.CISCO_IOS)
    c = hc.add_child("interface GigabitEthernet0/1")
    c.add_child("ip address 10.0.0.1 255.255.255.0")

    results: list[str] = []

    # 1. Object identity
    first_get = hc.children[0]
    second_get = hc.children[0]
    results.extend(
        (
            f"identity: {first_get is second_get}",
            f"setattr: {_attempt(lambda: _set_attribute(c))}",
        )
    )

    # 3. facts dict
    c.facts["custom_key"] = "hello_facts"
    results.extend(
        (
            f"facts: {c.facts.get('custom_key')}",
            "deepcopy: "
            + _attempt(lambda: f"OK len={len(list(copy.deepcopy(hc).all_children()))}"),
            "pickle: "
            + _attempt(lambda: f"OK len={len(list(_unpickle(hc).all_children()))}"),
            f"subclass: {_attempt(_subclass)}",
        )
    )

    # 7. tags (frozenset & tags_add)
    c.tags_add("tag_x")
    results.extend(
        (f"tags_type: {type(c.tags).__name__}", f"tags_contain: {'tag_x' in c.tags}")
    )

    # 8. live comments mutation
    c.comments.add("comment_x")
    results.extend(
        (
            f"comments_mutation: {'comment_x' in c.comments}",
            f"children_type: {type(c.children).__name__}",
            f"has_dict: {hasattr(c, '__dict__')}",
            f"hc_is_child: {isinstance(hc, HConfigChild)}",
            f"hc_is_base: {_is_base(hc)}",
            f"child_is_base: {_is_base(c)}",
            f"child_repr: {_representation(c)}",
            f"hc_repr: {_representation(hc)}",
        )
    )
    return "\n".join(results)


if __name__ == "__main__":
    sys.stdout.write(f"{probe()}\n")
