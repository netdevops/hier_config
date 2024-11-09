from __future__ import annotations

from dataclasses import dataclass

from hier_config.platforms.driver_base import HConfigDriverBase
from hier_config.platforms.model import Platform


@dataclass(frozen=True)
class HConfigDriverHPComware5(HConfigDriverBase):
    negation = "undo"

    @property
    def platform(self) -> Platform:
        return Platform.HP_COMWARE5
