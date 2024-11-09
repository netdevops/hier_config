from __future__ import annotations

from hier_config.platforms.driver_base import HConfigDriverBase
from hier_config.platforms.model import Platform


class HConfigDriverHPComware5(HConfigDriverBase):
    negation: str = "undo"

    @property
    def platform(self) -> Platform:
        return Platform.HP_COMWARE5
