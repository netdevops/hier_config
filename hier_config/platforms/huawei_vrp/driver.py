import re

from hier_config.child import HConfigChild
from hier_config.models import IndentAdjustRule, PerLineSubRule
from hier_config.platforms.driver_base import HConfigDriverBase, HConfigDriverRules


class HConfigDriverHuaweiVrp(HConfigDriverBase):
    """Driver for Huawei VRP operating system.

    Platform enum: ``Platform.HUAWEI_VRP``.
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

    def sectional_exit(self, config: HConfigChild) -> str | None:
        result = super().sectional_exit(config)
        if result == "exit":
            return "quit"
        return result

    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        return HConfigDriverRules(
            indent_adjust=[
                # Huawei prints public-key blocks with the closing
                # ``peer-public-key end`` line at the same indentation as the
                # opening ``(rsa|dsa|ecc) peer-public-key ...`` line. Nest the
                # whole block under its opener so multiple keys don't collide as
                # duplicate root-level ``peer-public-key end`` children.
                IndentAdjustRule(
                    start_expression="^\\s*(rsa|dsa|ecc) peer-public-key ",
                    end_expression="^\\s*peer-public-key end",
                ),
            ],
            per_line_sub=[
                PerLineSubRule(search="^\\s*[#!].*", replace=""),
            ],
        )
