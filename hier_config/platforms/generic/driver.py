from hier_config.models import Platform
from hier_config.platforms.driver_base import (
    HConfigDriverBase,
    HConfigDriverRules,
    load_platform_rules,
)


class HConfigDriverGeneric(HConfigDriverBase):
    """Generic driver with no platform-specific rules.

    Useful as a starting point for custom drivers or for configuration text
    that follows basic Cisco-style indentation without any special negation,
    sectional-exiting, or idempotency requirements.
    Platform enum: Platform.GENERIC.
    """

    platform = Platform.GENERIC

    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        """Load the canonical rules the Rust core compiles against."""
        return load_platform_rules(Platform.GENERIC)
