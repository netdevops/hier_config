from hier_config.models import Platform
from hier_config.platforms.driver_base import HConfigDriverBase


class HConfigDriverFortinetFortiOS(HConfigDriverBase):
    """Driver for Fortinet FortiOS.

    FortiOS treats two ``set <key> ...`` lines with the same key as idempotent
    regardless of their values. That comparison spans sibling nodes, so it is
    implemented natively in the Rust core rather than as a rule.
    """

    platform = Platform.FORTINET_FORTIOS

    @property
    def negation_prefix(self) -> str:
        return "unset "

    @property
    def declaration_prefix(self) -> str:
        return "set "
