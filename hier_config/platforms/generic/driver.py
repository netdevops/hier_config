from __future__ import annotations

from hier_config.platforms.driver_base import HConfigDriverBase
from hier_config.platforms.model import Platform


class HConfigDriverGeneric(HConfigDriverBase):
    @property
    def platform(self) -> Platform:
        return Platform.GENERIC
