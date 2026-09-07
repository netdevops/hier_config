from hier_config.models import Platform
from hier_config.platforms.driver_base import HConfigDriverBase


class HConfigDriverVYOS(HConfigDriverBase):
    """Driver for VyOS (and compatible VyOS-based routers).

    Like the JunOS driver, converts hierarchical VyOS configuration into flat
    ``set``/``delete`` command syntax via a preprocessor. Overrides
    ``declaration_prefix`` to ``"set "`` and ``negation_prefix`` to
    ``"delete "``. Platform enum: ``Platform.VYOS``.
    """

    platform = Platform.VYOS

    @property
    def negation_prefix(self) -> str:
        return "delete "

    @property
    def declaration_prefix(self) -> str:
        return "set "
