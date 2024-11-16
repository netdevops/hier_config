from hier_config.platforms.driver_base import HConfigDriverBase, HConfigDriverRules


class HConfigDriverGeneric(HConfigDriverBase):
    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        return HConfigDriverRules()
