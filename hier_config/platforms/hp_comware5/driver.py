from hier_config.platforms.driver_base import HConfigDriverBase, HConfigDriverRules


class HConfigDriverHPComware5(HConfigDriverBase):
    @property
    def negation_prefix(self) -> str:
        return "undo "

    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        return HConfigDriverRules()
