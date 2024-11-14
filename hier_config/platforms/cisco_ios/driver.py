from collections.abc import Callable
from logging import getLogger

from pydantic import Field

from hier_config.models import (
    IdempotentCommandsRule,
    MatchRule,
    NegationDefaultWithRule,
    OrderingRule,
    PerLineSubRule,
    Platform,
    SectionalExitingRule,
)
from hier_config.platforms.driver_base import HConfigDriverBase
from hier_config.root import HConfig

logger = getLogger(__name__)


def _rm_ipv6_acl_sequence_numbers(config: HConfig) -> None:
    """If there are sequence numbers in the IPv6 ACL, remove them."""
    for acl in config.get_children(startswith="ipv6 access-list "):
        for entry in acl.children:
            if entry.text.startswith("sequence"):
                entry.text = " ".join(entry.text.split()[2:])


def _remove_ipv4_acl_remarks(config: HConfig) -> None:
    for acl in config.get_children(startswith="ip access-list "):
        for entry in tuple(acl.children):
            if entry.text.startswith("remark"):
                acl.children.remove(entry)


def _add_acl_sequence_numbers(config: HConfig) -> None:
    """Add ACL sequence numbers."""
    ipv4_acl_sw = "ip access-list"
    acl_line_sw: tuple[str, ...] = ("permit", "deny")
    for child in config.children:
        if child.text.startswith(ipv4_acl_sw):
            sequence_number = 10
            for sub_child in child.children:
                if sub_child.text.startswith(acl_line_sw):
                    sub_child.text = f"{sequence_number} {sub_child.text}"
                    sequence_number += 10


class HConfigDriverCiscoIOS(HConfigDriverBase):
    negation_negate_with_rules: list[NegationDefaultWithRule] = Field(
        default=[
            NegationDefaultWithRule(
                lineage=(MatchRule(startswith="logging console "),),
                use="logging console debugging",
            ),
        ]
    )
    sectional_exiting_rules: list[SectionalExitingRule] = Field(
        default=[
            SectionalExitingRule(
                lineage=(
                    MatchRule(startswith="router bgp"),
                    MatchRule(startswith="template peer-policy"),
                ),
                exit_text="exit-peer-policy",
            ),
            SectionalExitingRule(
                lineage=(
                    MatchRule(startswith="router bgp"),
                    MatchRule(startswith="template peer-session"),
                ),
                exit_text="exit-peer-session",
            ),
            SectionalExitingRule(
                lineage=(
                    MatchRule(startswith="router bgp"),
                    MatchRule(startswith="address-family"),
                ),
                exit_text="exit-address-family",
            ),
        ]
    )
    ordering_rules: list[OrderingRule] = Field(
        default=[
            OrderingRule(
                lineage=(
                    MatchRule(startswith="interface"),
                    MatchRule(startswith="switchport mode "),
                ),
                weight=-10,
            ),
            OrderingRule(
                lineage=(MatchRule(startswith="no vlan filter"),),
                weight=200,
            ),
            OrderingRule(
                lineage=(
                    MatchRule(startswith="interface"),
                    MatchRule(startswith="no shutdown"),
                ),
                weight=200,
            ),
            OrderingRule(
                lineage=(
                    MatchRule(startswith="aaa group server tacacs+ "),
                    MatchRule(startswith="no server "),
                ),
                weight=10,
            ),
            OrderingRule(
                lineage=(MatchRule(startswith="no tacacs-server "),),
                weight=10,
            ),
        ]
    )
    per_line_sub_rules: list[PerLineSubRule] = Field(
        default=[
            PerLineSubRule(search="^Building configuration.*", replace=""),
            PerLineSubRule(search="^Current configuration.*", replace=""),
            PerLineSubRule(search="^! Last configuration change.*", replace=""),
            PerLineSubRule(search="^! NVRAM config last updated.*", replace=""),
            PerLineSubRule(search="^ntp clock-period .*", replace=""),
            PerLineSubRule(search="^version.*", replace=""),
            PerLineSubRule(search="^ logging event link-status$", replace=""),
            PerLineSubRule(search="^ logging event subif-link-status$", replace=""),
            PerLineSubRule(search="^\\s*ipv6 unreachables disable$", replace=""),
            PerLineSubRule(search="^end$", replace=""),
            PerLineSubRule(search="^\\s*[#!].*", replace=""),
            PerLineSubRule(search="^ no ip address", replace=""),
            PerLineSubRule(search="^ exit-peer-policy", replace=""),
            PerLineSubRule(search="^ exit-peer-session", replace=""),
            PerLineSubRule(search="^ exit-address-family", replace=""),
            PerLineSubRule(
                search="^crypto key generate rsa general-keys.*$", replace=""
            ),
        ]
    )
    idempotent_commands_rules: list[IdempotentCommandsRule] = Field(
        default=[
            IdempotentCommandsRule(
                lineage=(
                    MatchRule(startswith="vlan"),
                    MatchRule(startswith="name"),
                ),
            ),
            IdempotentCommandsRule(
                lineage=(
                    MatchRule(startswith="interface "),
                    MatchRule(startswith="description "),
                ),
            ),
            IdempotentCommandsRule(
                lineage=(
                    MatchRule(startswith="interface "),
                    MatchRule(startswith="ip address "),
                ),
            ),
            IdempotentCommandsRule(
                lineage=(
                    MatchRule(startswith="interface "),
                    MatchRule(startswith="switchport mode "),
                ),
            ),
            IdempotentCommandsRule(
                lineage=(
                    MatchRule(startswith="interface "),
                    MatchRule(startswith="authentication host-mode "),
                ),
            ),
            IdempotentCommandsRule(
                lineage=(
                    MatchRule(startswith="interface "),
                    MatchRule(
                        startswith="authentication event server dead action authorize vlan ",
                    ),
                ),
            ),
            IdempotentCommandsRule(
                lineage=(MatchRule(startswith="errdisable recovery interval "),),
            ),
            IdempotentCommandsRule(
                lineage=(MatchRule(re_search=r"^(no )?logging console.*"),),
            ),
        ]
    )
    post_load_callbacks: list[Callable[[HConfig], None]] = Field(
        default=[
            _rm_ipv6_acl_sequence_numbers,
            _remove_ipv4_acl_remarks,
            _add_acl_sequence_numbers,
        ]
    )

    @property
    def platform(self) -> Platform:
        return Platform.CISCO_IOS
