from hier_config.models import Platform
from hier_config.platforms.driver_base import (
    HConfigDriverBase,
    HConfigDriverRules,
    load_platform_rules,
)


class HConfigDriverHPComware5(HConfigDriverBase):
    """Driver for HP/H3C Comware 5 operating system.

    Uses negation prefix "undo " to match Comware / H3C CLI
    conventions (e.g. undo ip address). No additional platform-specific
    rules are configured by default. Platform enum: Platform.HP_COMWARE5.
    """

    platform = Platform.HP_COMWARE5

    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        """Load the canonical rules the Rust core compiles against."""
        return load_platform_rules(Platform.HP_COMWARE5)

    @property
    def negation_prefix(self) -> str:
        return "undo "
