from hier_config.models import Platform
from hier_config.platforms.driver_base import HConfigDriverBase


class HConfigDriverNokiaSRL(HConfigDriverBase):
    """Driver for Nokia SR Linux.

    Converts hierarchical SRL configuration into flat ``set``/``delete``
    command syntax via a preprocessor. Overrides ``declaration_prefix`` to
    ``"set "`` and ``negation_prefix`` to ``"delete "``.
    Platform enum: ``Platform.NOKIA_SRL``.
    """

    platform = Platform.NOKIA_SRL
