from __future__ import annotations

from hier_config.model import (
    IdempotentCommandsRule,
    MatchRule,
    NegationDefaultWhenRule,
    PerLineSubRule,
    SectionalExitingRule,
)
from hier_config.platforms.driver_base import HConfigDriverBase
from hier_config.platforms.model import Platform


class HConfigDriverAristaEOS(HConfigDriverBase):
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
    )
    idempotent_commands_rules: tuple[IdempotentCommandsRule, ...] = (
        IdempotentCommandsRule(
            lineage=(MatchRule(startswith="hostname"),),
        ),
        IdempotentCommandsRule(
            lineage=(MatchRule(startswith="logging source-interface"),),
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="interface"),
                MatchRule(startswith="ip address"),
            ),
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="line vty"),
                MatchRule(
                    startswith="transport input",
                ),
            ),
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="line vty"),
                MatchRule(
                    startswith="access-class",
                ),
            ),
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="line vty"),
                MatchRule(
                    startswith="ipv6 access-class",
                ),
            ),
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="interface"),
                MatchRule(
                    re_search="standby \\d+ (priority|authentication md5)",
                ),
            ),
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="router bgp"),
                MatchRule(startswith="bgp router-id"),
            ),
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="router ospf"),
                MatchRule(startswith="router-id"),
            ),
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="router ospf"),
                MatchRule(startswith="max-lsa"),
            ),
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="router ospf"),
                MatchRule(startswith="maximum-paths"),
            ),
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="ipv6 router ospf"),
                MatchRule(startswith="router-id"),
            ),
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="router ospf"),
                MatchRule(startswith="log-adjacency-changes"),
            ),
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="ipv6 router ospf"),
                MatchRule(startswith="log-adjacency-changes"),
            ),
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="router bgp"),
                MatchRule(re_search="neighbor \\S+ description"),
            ),
        ),
        IdempotentCommandsRule(
            lineage=(MatchRule(startswith="snmp-server community"),),
        ),
        IdempotentCommandsRule(
            lineage=(MatchRule(startswith="snmp-server location"),),
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(equals="line con 0"),
                MatchRule(startswith="exec-timeout"),
            ),
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="interface"),
                MatchRule(startswith="ip ospf message-digest-key"),
            ),
        ),
        IdempotentCommandsRule(
            lineage=(MatchRule(startswith="logging buffered"),),
        ),
        IdempotentCommandsRule(
            lineage=(MatchRule(startswith="tacacs-server key"),),
        ),
        IdempotentCommandsRule(
            lineage=(MatchRule(startswith="logging facility"),),
        ),
        IdempotentCommandsRule(
            lineage=(MatchRule(startswith="vlan internal allocation policy"),),
        ),
        IdempotentCommandsRule(
            lineage=(MatchRule(startswith="username admin"),),
        ),
        IdempotentCommandsRule(
            lineage=(MatchRule(startswith="snmp-server user"),),
        ),
        IdempotentCommandsRule(
            lineage=(MatchRule(startswith="banner"),),
        ),
        IdempotentCommandsRule(
            lineage=(MatchRule(startswith="ntp source"),),
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="management"),
                MatchRule(startswith="idle-timeout"),
            ),
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="aaa authentication enable default group tacacs+"),
            ),
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(equals="control-plane"),
                MatchRule(equals="ip access-group CPP in"),
            ),
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="interface"),
                MatchRule(startswith="mtu"),
            ),
        ),
        IdempotentCommandsRule(
            lineage=(MatchRule(startswith="snmp-server source-interface"),),
        ),
        IdempotentCommandsRule(
            lineage=(MatchRule(startswith="ip tftp client source-interface"),),
        ),
    )
    negation_default_when_rules: tuple[NegationDefaultWhenRule, ...] = (
        NegationDefaultWhenRule(
            lineage=(
                MatchRule(startswith="interface"),
                MatchRule(equals="logging event link-status"),
            )
        ),
    )

    @property
    def platform(self) -> Platform:
        return Platform.ARISTA_EOS
