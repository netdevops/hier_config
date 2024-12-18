from hier_config.child import HConfigChild
from hier_config.platforms.driver_base import HConfigDriverBase, HConfigDriverRules
from hier_config.platforms.functions import convert_to_set_commands


class HConfigDriverJuniperJUNOS(HConfigDriverBase):  # pylint: disable=too-many-instance-attributes
    def swap_negation(self, child: HConfigChild) -> HConfigChild:
        """Swap negation of a `self.text`."""
        if child.text.startswith(self.negation_prefix):
            child.text = f"{self.declaration_prefix}{child.text_without_negation}"
        elif child.text.startswith(self.declaration_prefix):
            child.text = f"{self.negation_prefix}{child.text.removeprefix(self.declaration_prefix)}"
        else:
            message = f"{child.text=} did not start with {self.negation_prefix} or {self.declaration_prefix}."
            raise ValueError(message)

        return child

    @property
    def declaration_prefix(self) -> str:
        return "set "

    @property
    def negation_prefix(self) -> str:
        return "delete "

    @staticmethod
    def config_preprocessor(config_text: str) -> str:
        return convert_to_set_commands(config_text)

    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        return HConfigDriverRules()
