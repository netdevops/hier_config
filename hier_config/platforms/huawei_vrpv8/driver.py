import re
from typing_extensions import override

from hier_config.child import HConfigChild
from hier_config.models import PerLineSubRule
from hier_config.platforms.driver_base import HConfigDriverBase, HConfigDriverRules


class HConfigDriverHuaweiVrpv8(HConfigDriverBase):
    """Driver for Huawei VRPv8 operating system.

    Platform enum: ``Platform.HUAWEI_VRPV8``.
    """

    @property
    def negation_prefix(self) -> str:
        return "undo "

    def swap_negation(self, child: HConfigChild) -> HConfigChild:
        if child.text.startswith(self.negation_prefix):
            child.text = child.text.removeprefix(self.negation_prefix)
            return child

        text = child.text
        if text.startswith("description "):
            text = "description"
        elif text.startswith("alias "):
            text = "alias"
        elif " remark " in text or text.startswith("remark "):
            text = re.sub(r"^(.*?remark) .*", r"\1", text)
        elif text.startswith("snmp-agent community "):
            text = re.sub(
                r"^(snmp-agent community (?:read |write )?(?:cipher )?\S+).*",
                r"\1",
                text,
            )

        child.text = f"{self.negation_prefix}{text}"
        return child

    @override
    def sectional_exit(self, config: HConfigChild) -> str | None:
        if config.children:
            return "quit"
        return None

    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        return HConfigDriverRules(
            per_line_sub=[
                PerLineSubRule(search="^\\s*[#!].*", replace=""),
            ],
        )
