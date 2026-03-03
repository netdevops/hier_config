from hier_config.platforms.driver_base import HConfigDriverBase, HConfigDriverRules


class HConfigDriverHPComware5(HConfigDriverBase):
    """Driver for HP/H3C Comware 5 operating system.

    Overrides the negation prefix to ``"undo "`` to match Comware / H3C CLI
    conventions (e.g. ``undo ip address``).  No additional platform-specific
    rules are configured by default.  Platform enum: ``Platform.HP_COMWARE5``.
    """

    @property
    def negation_prefix(self) -> str:
        return "undo "

    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        return HConfigDriverRules()
