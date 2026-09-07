from hier_config.models import Platform
from hier_config.platforms.driver_base import core_owned, HConfigDriverBase
from hier_config.child import HConfigChild
import re


class HConfigDriverHuaweiVrp(HConfigDriverBase):
    """Driver for Huawei VRP operating system.

    Platform enum: Platform.HUAWEI_VRP.
    """

    platform = Platform.HUAWEI_VRP

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

    @core_owned
    def sectional_exit(self, config: HConfigChild) -> str | None:
        result = super().sectional_exit(config)
        if result == "exit":
            return "quit"
        return result
