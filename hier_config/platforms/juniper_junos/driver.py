from hier_config.child import HConfigChild
from hier_config.models import Platform
from hier_config.platforms.driver_base import (
    HConfigDriverBase,
    HConfigDriverRules,
    load_platform_rules,
)
from hier_config.platforms.functions import convert_to_set_commands


class HConfigDriverJuniperJUNOS(HConfigDriverBase):
    """Driver for Juniper JunOS (experimental).

    Converts hierarchical JunOS configuration into flat ``set``/``delete``
    command syntax via a preprocessor. Overrides ``declaration_prefix`` to
    ``"set "`` and ``negation_prefix`` to ``"delete "`` so that
    ``swap_negation`` correctly toggles between the two forms.

    .. warning::
        JunOS support is experimental and has not been extensively tested in
        production environments.  Use with caution.

    Platform enum: ``Platform.JUNIPER_JUNOS``.
    """

    platform = Platform.JUNIPER_JUNOS

    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        """Load the canonical rules the Rust core compiles against."""
        return load_platform_rules(Platform.JUNIPER_JUNOS)

    @property
    def negation_prefix(self) -> str:
        return "delete "

    @property
    def declaration_prefix(self) -> str:
        return "set "

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

    @staticmethod
    def config_preprocessor(config_text: str) -> str:
        return convert_to_set_commands(config_text)
