from __future__ import annotations

from dataclasses import dataclass

from hier_config.platforms.driver_base import HConfigDriverBase
from hier_config.platforms.model import Platform


@dataclass(frozen=True)
class HConfigDriverGeneric(HConfigDriverBase):
    @property
    def platform(self) -> Platform:
        return Platform.GENERIC
