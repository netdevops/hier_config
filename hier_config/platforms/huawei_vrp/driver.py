from hier_config.models import Platform
from hier_config.platforms.driver_base import (
    HConfigDriverBase,
    HConfigDriverRules,
    load_platform_rules,
)


class HConfigDriverHuaweiVrp(HConfigDriverBase):
    """Driver for Huawei VRP operating system.

    Platform enum: Platform.HUAWEI_VRP.
    """

    platform = Platform.HUAWEI_VRP

    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        """Load the canonical rules the Rust core compiles against."""
        return load_platform_rules(Platform.HUAWEI_VRP)

    @property
    def negation_prefix(self) -> str:
        return "undo "
