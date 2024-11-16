from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Optional, TypeVar, Union, overload

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from hier_config import HConfigChild

_D = TypeVar("_D")


class Children:
    def __init__(self) -> None:
        self._children: list[HConfigChild] = []
        self._children_dict: dict[str, HConfigChild] = {}

    @overload
    def __getitem__(self, subscript: Union[int, str]) -> HConfigChild: ...

    @overload
    def __getitem__(self, subscript: slice) -> list[HConfigChild]: ...

    def __getitem__(
        self, subscript: Union[slice, int, str]
    ) -> Union[HConfigChild, list[HConfigChild]]:
        if isinstance(subscript, slice):
            return self._children[subscript]
        if isinstance(subscript, int):
            return self._children[subscript]
        return self._children_dict[subscript]

    def __setitem__(self, index: int, child: HConfigChild) -> None:
        self._children[index] = child
        self.rebuild_mapping()

    def __contains__(self, item: str) -> bool:
        return item in self._children_dict

    def __iter__(self) -> Iterator[HConfigChild]:
        return iter(self._children)

    def __len__(self) -> int:
        return len(self._children)

    def append(
        self,
        child: HConfigChild,
        *,
        update_mapping: Literal["normal", "fast", "disabled"] = "normal",
    ) -> None:
        self._children.append(child)
        if update_mapping == "normal":
            self.rebuild_mapping()
        elif update_mapping == "fast":
            self._children_dict[child.text] = child

    def clear(self) -> None:
        """Delete all children."""
        self._children.clear()
        self._children_dict.clear()

    def delete(self, child_or_text: Union[HConfigChild, str]) -> None:
        """Delete a child from self._children and self._children_dict."""
        if isinstance(child_or_text, str):
            if child_or_text in self._children_dict:
                self._children[:] = [
                    c for c in self._children if c.text != child_or_text
                ]
                self.rebuild_mapping()
        else:
            old_len = len(self._children)
            self._children = [c for c in self._children if c is not child_or_text]
            if old_len != len(self._children):
                self.rebuild_mapping()

    def extend(self, children: Iterable[HConfigChild]) -> None:
        """Add child instances of HConfigChild."""
        self._children.extend(children)
        self.rebuild_mapping()

    def get(
        self, key: str, default: Optional[_D] = None
    ) -> Union[HConfigChild, _D, None]:
        return self._children_dict.get(key, default)

    def index(self, child: HConfigChild) -> int:
        return self._children.index(child)

    def rebuild_mapping(self) -> None:
        """Rebuild self._children_dict."""
        self._children_dict.clear()
        for child in self._children:
            self._children_dict.setdefault(child.text, child)
