from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from hier_config.platforms.model import Platform


class Dump(BaseModel):
    driver_platform: Platform
    lines: tuple[DumpLine, ...]


class DumpLine(BaseModel):
    depth: int
    text: str
    tags: frozenset[str]
    comments: frozenset[str]
    new_in_config: bool


@dataclass(frozen=True, slots=True, eq=False)
class MatchRule:
    equals: str | frozenset[str] | None = None
    startswith: str | tuple[str, ...] | None = None
    endswith: str | tuple[str, ...] | None = None
    contains: str | tuple[str, ...] | None = None
    re_search: str | None = None


@dataclass(frozen=True, slots=True, eq=False)
class SectionalExitingRule:
    lineage: tuple[MatchRule, ...]
    exit_text: str


@dataclass(frozen=True, slots=True, eq=False)
class SectionalOverwriteRule:
    lineage: tuple[MatchRule, ...]


@dataclass(frozen=True, slots=True, eq=False)
class SectionalOverwriteNoNegateRule:
    lineage: tuple[MatchRule, ...]


@dataclass(frozen=True, slots=True, eq=False)
class OrderingRule:
    lineage: tuple[MatchRule, ...]
    weight: int


@dataclass(frozen=True, slots=True, eq=False)
class IndentAdjustRule:
    start_expression: str
    end_expression: str


@dataclass(frozen=True, slots=True, eq=False)
class ParentAllowsDuplicateChildRule:
    lineage: tuple[MatchRule, ...]


@dataclass(frozen=True, slots=True, eq=False)
class FullTextSubRule:
    search: str
    replace: str


@dataclass(frozen=True, slots=True, eq=False)
class PerLineSubRule:
    search: str
    replace: str


@dataclass(frozen=True, slots=True, eq=False)
class IdempotentCommandsRule:
    lineage: tuple[MatchRule, ...]


@dataclass(frozen=True, slots=True, eq=False)
class IdempotentCommandsAvoidRule:
    lineage: tuple[MatchRule, ...]


@dataclass(frozen=True, slots=True)
class Instance:
    id: int
    comments: frozenset[str]
    tags: frozenset[str]


@dataclass(frozen=True, slots=True, eq=False)
class NegationDefaultWhenRule:
    lineage: tuple[MatchRule, ...]


@dataclass(frozen=True, slots=True, eq=False)
class NegationDefaultWithRule:
    lineage: tuple[MatchRule, ...]
    use: str


SetLikeOfStr = frozenset[str] | set[str]
