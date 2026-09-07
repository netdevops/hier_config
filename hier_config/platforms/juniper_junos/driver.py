from hier_config.models import Platform
from hier_config.platforms.driver_base import HConfigDriverBase


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
