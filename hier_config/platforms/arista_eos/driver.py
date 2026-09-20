from hier_config.models import Platform
from hier_config.platforms.arista_eos.view import HConfigViewAristaEOS
from hier_config.platforms.driver_base import (
    HConfigDriverBase,
    HConfigDriverRules,
    load_platform_rules,
)


class HConfigDriverAristaEOS(HConfigDriverBase):
    """Driver for Arista EOS (Extensible Operating System).

    Handles EOS-specific conventions including BGP address-family sectional
    exiting, per-line substitutions that strip timestamps and banner markers,
    and a comprehensive set of idempotency rules for interface, BGP, and OSPF
    commands.  Platform enum: Platform.ARISTA_EOS.
    """

    platform = Platform.ARISTA_EOS
    view_class = HConfigViewAristaEOS

    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        """Load the canonical rules the Rust core compiles against."""
        return load_platform_rules(Platform.ARISTA_EOS)
