"""User-extensible remediation plugin system (#181).

Plugins let users package custom remediation transforms — organization
policies, safety sequences, provisioning workflows — outside the hier_config
codebase and apply them via ``WorkflowRemediation(plugins=...)``. Driver
authors should prefer ``remediation_transform_callbacks`` on
``HConfigDriverRules`` (#180) for platform-level transforms.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .root import HConfig


class RemediationPlugin(ABC):
    """Base class for user-defined remediation plugins.

    Subclasses implement ``transform()``, which receives the computed
    remediation config and may mutate it in place (add safety commands,
    reorder sections, drop disallowed changes, etc.). Instances are
    callable, so anywhere a plain ``Callable[[HConfig], None]`` transform
    is accepted, a plugin works too.
    """

    def __call__(self, remediation: HConfig) -> None:
        """Apply this plugin's transform."""
        self.transform(remediation)

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this plugin."""

    @property
    def description(self) -> str:
        """Human-readable description of what this plugin does."""
        return ""

    @abstractmethod
    def transform(self, remediation: HConfig) -> None:
        """Transform the remediation config in place."""
