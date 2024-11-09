from __future__ import annotations

from hier_config.child import HConfigChild
from hier_config.platforms.driver_base import HConfigDriverBase
from hier_config.platforms.model import Platform


class HConfigDriverCiscoIOSXR(HConfigDriverBase):  # pylint: disable=too-many-instance-attributes
    negation: str = "delete"
    declaration: str = "set"

    def swap_negation(self, child: HConfigChild) -> HConfigChild:
        """Swap negation of a `self.text`."""
        if child.text.startswith(child._negation_prefix):
            child.text = f"{self.declaration} {child.text_without_negation}"
        elif child.text.startswith(f"{self.declaration} "):
            child.text = (
                f"{child._negation_prefix}{child.text.removeprefix(self.declaration)}"
            )

        return child

    @property
    def platform(self) -> Platform:
        return Platform.JUNIPER_JUNOS
