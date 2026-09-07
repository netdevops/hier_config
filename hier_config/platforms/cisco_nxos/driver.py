from hier_config.models import Platform
from hier_config.platforms.driver_base import HConfigDriverBase
from hier_config.platforms.cisco_nxos.view import HConfigViewCiscoNXOS


class HConfigDriverCiscoNXOS(HConfigDriverBase):
    """Driver for Cisco NX-OS (Nexus Operating System).

    Handles NX-OS quirks such as double-space in snmp-server location,
    boot-image stripping, HSRP group-level idempotency, TCAM region
    assignments, and secondary IP address avoidance in idempotency checks.
    Platform enum: Platform.CISCO_NXOS.
    """

    platform = Platform.CISCO_NXOS
    view_class = HConfigViewCiscoNXOS
