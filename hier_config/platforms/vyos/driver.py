from hier_config.models import Platform
from hier_config.platforms.driver_base import (
    HConfigDriverBase,
    HConfigDriverRules,
    load_platform_rules,
)
from hier_config.platforms.functions import convert_to_set_commands


class HConfigDriverVYOS(HConfigDriverBase):
    """Driver for VyOS (and compatible VyOS-based routers).

    Like the JunOS driver, converts hierarchical VyOS configuration into flat
    ``set``/``delete`` command syntax via a preprocessor. Overrides
    ``declaration_prefix`` to ``"set "`` and ``negation_prefix`` to
    ``"delete "``. Platform enum: ``Platform.VYOS``.
    """

    platform = Platform.VYOS

    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        """Load the canonical rules the Rust core compiles against."""
        return load_platform_rules(Platform.VYOS)

    @property
    def negation_prefix(self) -> str:
        return "delete "

    @property
    def declaration_prefix(self) -> str:
        return "set "

    @staticmethod
    def config_preprocessor(config_text: str) -> str:
        return convert_to_set_commands(config_text)
