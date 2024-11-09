from __future__ import annotations

from collections.abc import Callable
from logging import getLogger

from hier_config.model import (
    IdempotentCommandsRule,
    MatchRule,
    NegationDefaultWithRule,
    OrderingRule,
    PerLineSubRule,
    SectionalExitingRule,
)
from hier_config.platforms.driver_base import HConfigDriverBase
from hier_config.platforms.model import Platform
from hier_config.root import HConfig

logger = getLogger(__name__)


def _rm_10g_interfaces(config: HConfig) -> None:
    """
    Remove dummy 10g interfaces.

    On 3850s with 4x1g modules, TenGigabitEthernet interfaces appear in the config alongside
    GigabitEthernet with the same numbering.
    """
    for interface in tuple(
        config.get_children(re_search=r"^interface (?:Ten)?GigabitEthernet\d/1/[1-4]$")
    ):
        match len(interface.children):
            # An interface with no children is a dummy interface and can be removed
            case 0:
                logger.debug("deleting dummy interface %s", interface.text.split()[1])
                interface.delete()
            # A TenGigabit interface that matches a Gigabit interface number (e.g. 1/1/2) and
            # has 1 or fewer children (e.g. shutdown) is a dummy interface and can be removed.
            case 1 if "TenGigabitEthernet" in interface.text:
                if (
                    other := config.children_dict.get(
                        interface.text.replace("TenGigabitEthernet", "GigabitEthernet")
                    )
                ) and other.children:
                    logger.debug(
                        "deleting dummy interface %s", interface.text.split()[1]
                    )
                    interface.delete()
            case _:
                pass

    # Sometime 10g interfaces show up in the 0 Slot on ports greater than 48 even
    # though they are on a module. These can be removed if they have no children.
    for interface in tuple(
        config.get_children(re_search=r"^interface TenGigabitEthernet\d/0/(49|5[0-6])$")
    ):
        if not interface.children:
            logger.debug("deleting dummy interface %s", interface.text.split()[1])
            interface.delete()


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
    negation_negate_with_rules: tuple[NegationDefaultWithRule, ...] = (
        NegationDefaultWithRule(
            lineage=(MatchRule(startswith="logging console "),),
            use="logging console debugging",
        ),
    )
    sectional_exiting_rules: tuple[SectionalExitingRule, ...] = (
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
    )
    ordering_rules: tuple[OrderingRule, ...] = (
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
    )
    per_line_sub_rules: tuple[PerLineSubRule, ...] = (
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
        PerLineSubRule(search="^crypto key generate rsa general-keys.*$", replace=""),
    )
    idempotent_commands_rules: tuple[IdempotentCommandsRule, ...] = (
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
            )
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="interface "),
                MatchRule(
                    startswith="authentication event server dead action authorize vlan "
                ),
            )
        ),
        IdempotentCommandsRule(
            lineage=(MatchRule(startswith="errdisable recovery interval "),),
        ),
        IdempotentCommandsRule(
            lineage=(MatchRule(re_search=r"^(no )?logging console.*"),),
        ),
    )
    post_load_callbacks: tuple[Callable[[HConfig], None], ...] = (
        _rm_ipv6_acl_sequence_numbers,
        _remove_ipv4_acl_remarks,
        _add_acl_sequence_numbers,
        _rm_10g_interfaces,
    )

    @property
    def platform(self) -> Platform:
        return Platform.CISCO_IOS
