# Type stubs for the Rust-backed implementation in `_hier_config_rust`.
#
# griffe (mkdocstrings) and mypy cannot introspect a compiled extension,
# so this stub is the documented, typed view of the native class. It is
# generated from the live extension surface plus the v3.7.0 docstrings;
# see docs/dev/architecture.md.

from collections.abc import Iterable, Iterator
from typing import TypeVar, overload

from hier_config.child import HConfigChild

_D = TypeVar("_D")

class HConfigChildren:
    """Ordered collection of `HConfigChild` objects with fast text-keyed look-up.

    Internally maintains both a `list` (for ordered iteration) and a `dict`
    (for O(1) membership and retrieval by `child.text`).  When duplicate child
    text is allowed by the driver, the mapping always points to the *first*
    occurrence while the list preserves all entries in insertion order.
    """

    def __contains__(self, item: str) -> bool:
        """Return bool(key in self)."""

    def __delitem__(self, key: str, /) -> None:
        """Delete self[key]."""

    def __eq__(self, other: object) -> bool:
        """Return self==value."""

    @overload
    def __getitem__(self, subscript: int | str) -> HConfigChild:
        """Return self[key]."""

    @overload
    def __getitem__(self, subscript: slice) -> list[HConfigChild]:
        """Return self[key]."""

    def __hash__(self) -> int:
        """Return hash(self)."""

    def __iter__(self) -> Iterator[HConfigChild]:
        """Implement iter(self)."""

    def __len__(self) -> int:
        """Return len(self)."""

    def __setitem__(self, index: int, child: HConfigChild) -> None:
        """Set self[key] to value."""

    def append(
        self, child: HConfigChild, *, update_mapping: bool = True
    ) -> HConfigChild: ...
    def clear(self) -> None:
        """Delete all children."""

    def delete(self, child_or_text: HConfigChild | str) -> None:
        """Delete a child from self._data and self._mapping."""

    def extend(self, children: Iterable[HConfigChild]) -> None:
        """Add child instances of HConfigChild."""

    def get(self, key: str, default: _D | None = None) -> HConfigChild | _D | None: ...
    def index(self, child: HConfigChild) -> int: ...
    def rebuild_mapping(self) -> None:
        """Rebuild self._mapping."""
