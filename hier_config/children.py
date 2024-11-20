from __future__ import annotations

from typing import TYPE_CHECKING, Optional, TypeVar, Union, overload

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from hier_config import HConfigChild

_D = TypeVar("_D")


class HConfigChildren:
    def __init__(self) -> None:
        self.data: list[HConfigChild] = []
        self.mapping: dict[str, HConfigChild] = {}

    @overload
    def __getitem__(self, subscript: Union[int, str]) -> HConfigChild: ...

    @overload
    def __getitem__(self, subscript: slice) -> list[HConfigChild]: ...

    def __getitem__(
        self, subscript: Union[slice, int, str]
    ) -> Union[HConfigChild, list[HConfigChild]]:
        if isinstance(subscript, slice):
            return self.data[subscript]
        if isinstance(subscript, int):
            return self.data[subscript]
        return self.mapping[subscript]

    def __setitem__(self, index: int, child: HConfigChild) -> None:
        self.data[index] = child
        self.rebuild_mapping()

    def __contains__(self, item: str) -> bool:
        return item in self.mapping

    def __iter__(self) -> Iterator[HConfigChild]:
        return iter(self.data)

    def __len__(self) -> int:
        return len(self.data)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, HConfigChildren):
            return NotImplemented

        self_len = len(self.data)
        other_len = len(other.data)
        # Superfast succeed method for no children
        if self_len == other_len == 0:
            return True

        # Superfast fail method
        if self_len != other_len:
            return False

        # Fast fail method
        if self.mapping.keys() != other.mapping.keys():
            return False

        # Slower full comparison
        return all(
            self_child == other_child
            for self_child, other_child in zip(
                sorted(self.data),
                sorted(other.data),
            )
        )

    def __hash__(self) -> int:
        return hash(
            (*self.data,),
        )

    def append(
        self,
        child: HConfigChild,
        *,
        update_mapping: bool = True,
    ) -> HConfigChild:
        self.data.append(child)
        if update_mapping:
            self.mapping.setdefault(child.text, child)

        return child

    def clear(self) -> None:
        """Delete all children."""
        self.data.clear()
        self.mapping.clear()

    def delete(self, child_or_text: Union[HConfigChild, str]) -> None:
        """Delete a child from self.data and self.mapping."""
        if isinstance(child_or_text, str):
            if child_or_text in self.mapping:
                self.data[:] = [c for c in self.data if c.text != child_or_text]
                self.rebuild_mapping()
        else:
            old_len = len(self.data)
            self.data = [c for c in self.data if c is not child_or_text]
            if old_len != len(self.data):
                self.rebuild_mapping()

    def extend(self, children: Iterable[HConfigChild]) -> None:
        """Add child instances of HConfigChild."""
        self.data.extend(children)
        for child in children:
            self.mapping.setdefault(child.text, child)

    def get(
        self, key: str, default: Optional[_D] = None
    ) -> Union[HConfigChild, _D, None]:
        return self.mapping.get(key, default)

    def index(self, child: HConfigChild) -> int:
        return self.data.index(child)

    def rebuild_mapping(self) -> None:
        """Rebuild self.mapping."""
        self.mapping.clear()
        for child in self.data:
            self.mapping.setdefault(child.text, child)
