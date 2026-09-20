from hier_config.models import Platform
from hier_config.platforms.cisco_nxos.view import HConfigViewCiscoNXOS
from hier_config.platforms.driver_base import (
    HConfigDriverBase,
    HConfigDriverRules,
    load_platform_rules,
)


class HConfigDriverCiscoNXOS(HConfigDriverBase):
    """Driver for Cisco NX-OS (Nexus Operating System).

    Handles NX-OS quirks such as double-space in snmp-server location,
    boot-image stripping, HSRP group-level idempotency, TCAM region
    assignments, and secondary IP address avoidance in idempotency checks.
    Platform enum: Platform.CISCO_NXOS.
    """

    platform = Platform.CISCO_NXOS
    view_class = HConfigViewCiscoNXOS

    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        """Load the canonical rules the Rust core compiles against."""
        return load_platform_rules(Platform.CISCO_NXOS)
