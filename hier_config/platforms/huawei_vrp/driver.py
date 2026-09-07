from hier_config.models import Platform
from hier_config.platforms.driver_base import HConfigDriverBase


class HConfigDriverHuaweiVrp(HConfigDriverBase):
    """Driver for Huawei VRP operating system.

    Platform enum: Platform.HUAWEI_VRP.
    """

    platform = Platform.HUAWEI_VRP

    @property
    def negation_prefix(self) -> str:
        return "undo "
