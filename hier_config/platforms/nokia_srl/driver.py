from hier_config.models import Platform
from hier_config.platforms.driver_base import HConfigDriverBase
from hier_config.child import HConfigChild


class HConfigDriverNokiaSRL(HConfigDriverBase):
    """Driver for Nokia SR Linux.

    Converts hierarchical SRL configuration into flat ``set``/``delete``
    command syntax via a preprocessor. Overrides ``declaration_prefix`` to
    ``"set "`` and ``negation_prefix`` to ``"delete "``.
    Platform enum: ``Platform.NOKIA_SRL``.
    """

    platform = Platform.NOKIA_SRL

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

        return child
