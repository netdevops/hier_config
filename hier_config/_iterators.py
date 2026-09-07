"""Helpers for handing lazy Python iterators back out of the Rust core."""

from collections.abc import Iterable, Iterator
from typing import TypeVar

_T = TypeVar("_T")

__all__ = ("as_generator",)


def as_generator(items: Iterable[_T]) -> Iterator[_T]:
    """Re-yield ``items`` so callers receive a genuine generator object.

    The core materializes traversals eagerly (it must, to avoid holding a read
    lock on the tree across arbitrary Python code), but the public API is
    documented as returning an iterator. Wrapping preserves that contract.
    """
    yield from items
