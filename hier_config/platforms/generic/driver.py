from hier_config.models import Platform
from hier_config.platforms.driver_base import HConfigDriverBase


class HConfigDriverGeneric(HConfigDriverBase):
    """Generic driver with no platform-specific rules.

    Useful as a starting point for custom drivers or for configuration text
    that follows basic Cisco-style indentation without any special negation,
    sectional-exiting, or idempotency requirements.
    Platform enum: Platform.GENERIC.
    """

    platform = Platform.GENERIC
