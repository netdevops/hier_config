from hier_config.model import Platform
from hier_config.platforms.driver_base import HConfigDriverBase


class HConfigDriverGeneric(HConfigDriverBase):
    @property
    def platform(self) -> Platform:
        return Platform.GENERIC
