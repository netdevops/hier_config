"""Reporting types for the tree algorithms implemented in the Rust core.

The algorithms themselves (`future`, `remediation`, tag filtering, pruning)
live in `hier_config_core`; only the report they hand back is modelled here,
because it is a plain data carrier over nodes of the returned tree.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .child import HConfigChild


@dataclass(frozen=True, slots=True)
class FutureReport:
    """How `HConfig.future_with_report()` resolved a change's negations (#285).

    The nodes reference the returned future config tree, so `path()` and
    `lineage()` give the surrounding context.
    """

    unresolved_negations: tuple[HConfigChild, ...]
    """Kept negation lines whose positive form matched nothing in the source
    config -- the change did not apply cleanly."""

    idempotency_replacements: tuple[HConfigChild, ...]
    """Negation lines that persisted by replacing an idempotency-tracked
    counterpart (e.g. IOS `no logging console`)."""


__all__ = ("FutureReport",)
