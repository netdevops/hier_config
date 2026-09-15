from __future__ import annotations

from collections.abc import Callable
from typing import TypeAlias

from hier_config._hier_config_rust import WorkflowRemediation
from hier_config.root import HConfig

RemediationTransform: TypeAlias = Callable[[HConfig], None]

__all__ = ("RemediationTransform", "WorkflowRemediation")
