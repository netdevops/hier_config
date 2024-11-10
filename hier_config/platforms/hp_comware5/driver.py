from hier_config.model import Platform
from hier_config.platforms.driver_base import HConfigDriverBase


class HConfigDriverHPComware5(HConfigDriverBase):
    @property
    def negation_prefix(self) -> str:
        return "undo "

    @property
    def platform(self) -> Platform:
        return Platform.HP_COMWARE5
