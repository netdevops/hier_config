from hier_config.models import (
    IdempotentCommandsRule,
    MatchRule,
    NegationDefaultWhenRule,
    PerLineSubRule,
    SectionalExitingRule,
)
from hier_config.platforms.driver_base import HConfigDriverBase, HConfigDriverRules


class HConfigDriverAristaEOS(HConfigDriverBase):
    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        return HConfigDriverRules(
            sectional_exiting=[
                SectionalExitingRule(
                    match_rules=(
                        MatchRule(startswith="router bgp"),
                        MatchRule(startswith="template peer-policy"),
                    ),
                    exit_text="exit-peer-policy",
                ),
                SectionalExitingRule(
                    match_rules=(
                        MatchRule(startswith="router bgp"),
                        MatchRule(startswith="template peer-session"),
                    ),
                    exit_text="exit-peer-session",
                ),
                SectionalExitingRule(
                    match_rules=(
                        MatchRule(startswith="router bgp"),
                        MatchRule(startswith="address-family"),
                    ),
                    exit_text="exit-address-family",
                ),
            ],
            per_line_sub=[
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
            ],
            idempotent_commands=[
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="hostname"),),
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="logging source-interface"),),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface"),
                        MatchRule(startswith="ip address"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="line vty"),
                        MatchRule(
                            startswith="transport input",
                        ),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="line vty"),
                        MatchRule(
                            startswith="access-class",
                        ),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="line vty"),
                        MatchRule(
                            startswith="ipv6 access-class",
                        ),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface"),
                        MatchRule(
                            re_search="standby \\d+ (priority|authentication md5)",
                        ),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="router bgp"),
                        MatchRule(startswith="bgp router-id"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="router ospf"),
                        MatchRule(startswith="router-id"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="router ospf"),
                        MatchRule(startswith="max-lsa"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="router ospf"),
                        MatchRule(startswith="maximum-paths"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="ipv6 router ospf"),
                        MatchRule(startswith="router-id"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="router ospf"),
                        MatchRule(startswith="log-adjacency-changes"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="ipv6 router ospf"),
                        MatchRule(startswith="log-adjacency-changes"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="router bgp"),
                        MatchRule(re_search="neighbor \\S+ description"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="snmp-server community"),),
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="snmp-server location"),),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(equals="line con 0"),
                        MatchRule(startswith="exec-timeout"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface"),
                        MatchRule(startswith="ip ospf message-digest-key"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="logging buffered"),),
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="tacacs-server key"),),
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="logging facility"),),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="vlan internal allocation policy"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="username admin"),),
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="snmp-server user"),),
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="banner"),),
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="ntp source"),),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="management"),
                        MatchRule(startswith="idle-timeout"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(
                            startswith="aaa authentication enable default group tacacs+"
                        ),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(equals="control-plane"),
                        MatchRule(equals="ip access-group CPP in"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface"),
                        MatchRule(startswith="mtu"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="snmp-server source-interface"),),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="ip tftp client source-interface"),
                    ),
                ),
            ],
            negation_default_when=[
                NegationDefaultWhenRule(
                    match_rules=(
                        MatchRule(startswith="interface"),
                        MatchRule(equals="logging event link-status"),
                    ),
                ),
            ],
        )
