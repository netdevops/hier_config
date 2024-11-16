from hier_config.models import (
    IdempotentCommandsAvoidRule,
    IdempotentCommandsRule,
    MatchRule,
    NegationDefaultWhenRule,
    NegationDefaultWithRule,
    PerLineSubRule,
)
from hier_config.platforms.driver_base import HConfigDriverBase, HConfigDriverRules


class HConfigDriverCiscoNXOS(HConfigDriverBase):
    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        return HConfigDriverRules(
            per_line_sub=[
                PerLineSubRule(search="^Building configuration.*", replace=""),
                PerLineSubRule(search="^Current configuration.*", replace=""),
                PerLineSubRule(search="^ntp clock-period .*", replace=""),
                PerLineSubRule(
                    search="^snmp-server location  ",
                    replace="snmp-server location ",
                ),
                PerLineSubRule(search="^version.*", replace=""),
                PerLineSubRule(search="^boot (system|kickstart) .*", replace=""),
                PerLineSubRule(search="!.*", replace=""),
            ],
            idempotent_commands_avoid=[
                IdempotentCommandsAvoidRule(
                    match_rules=(
                        MatchRule(startswith="interface"),
                        MatchRule(re_search="ip address.*secondary"),
                    ),
                ),
            ],
            idempotent_commands=[
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="power redundancy-mode"),),
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="cli alias name wr "),)
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="aaa authentication login console"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="port-channel load-balance"),),
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="hostname "),)
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="ip tftp source-interface"),),
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="ip telnet source-interface"),),
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="ip tacacs source-interface"),),
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="logging source-interface"),),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="hardware access-list tcam region ifacl"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="hardware access-list tcam region vacl"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="hardware access-list tcam region qos"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="hardware access-list tcam region racl"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(
                            startswith="hardware access-list tcam region ipv6-racl"
                        ),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(
                            startswith="hardware access-list tcam region e-ipv6-racl"
                        ),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="hardware access-list tcam region l3qos"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="router ospf"),
                        MatchRule(startswith="vrf"),
                        MatchRule(startswith="maximum-paths"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="router ospf"),
                        MatchRule(startswith="vrf"),
                        MatchRule(startswith="log-adjacency-changes"),
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
                        MatchRule(startswith="router ospf"),
                        MatchRule(startswith="log-adjacency-changes"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="router bgp"),
                        MatchRule(startswith="vrf"),
                        MatchRule(startswith="address-family"),
                        MatchRule(startswith="maximum-paths"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="router bgp"),
                        MatchRule(startswith="address-family"),
                        MatchRule(startswith="maximum-paths"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="router bgp"),
                        MatchRule(startswith="template"),
                        MatchRule(startswith="address-family"),
                        MatchRule(startswith="send-community"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface"),
                        MatchRule(re_search="^hsrp \\d+"),
                        MatchRule(startswith="ip"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface"),
                        MatchRule(re_search="^hsrp \\d+"),
                        MatchRule(startswith="priority"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface"),
                        MatchRule(re_search="^hsrp \\d+"),
                        MatchRule(startswith="authentication md5 key-string"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface"),
                        MatchRule(startswith="ip address"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface"),
                        MatchRule(startswith="duplex"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface"),
                        MatchRule(startswith="speed"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface"),
                        MatchRule(startswith="switchport mode"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface"),
                        MatchRule(startswith="switchport access vlan"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface"),
                        MatchRule(startswith="switchport trunk native vlan"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface"),
                        MatchRule(startswith="switchport trunk allowed vlan"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface"),
                        MatchRule(startswith="udld port"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface"),
                        MatchRule(startswith="ip ospf cost"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface"),
                        MatchRule(startswith="ipv6 link-local"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface"),
                        MatchRule(startswith="ospfv3 cost"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface"),
                        MatchRule(startswith="mtu"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(equals="line console"),
                        MatchRule(startswith="exec-timeout"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="line vty"),
                        MatchRule(startswith="transport input"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="line vty"),
                        MatchRule(startswith="ipv6 access-class"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="line vty"),
                        MatchRule(startswith="access-class"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="router bgp"),
                        MatchRule(
                            startswith="bgp router-id",
                        ),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="router bgp"),
                        MatchRule(
                            re_search="neighbor \\S+ description",
                        ),
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
                        MatchRule(startswith="log-adjacency-changes"),
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
                        MatchRule(startswith="ipv6 router ospf"),
                        MatchRule(startswith="log-adjacency-changes"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="mac address-table aging-time"),),
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="snmp-server community"),),
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="snmp-server location"),)
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="vpc domain"),
                        MatchRule(startswith="role priority"),
                    ),
                ),
                IdempotentCommandsRule(match_rules=(MatchRule(startswith="banner"),)),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="username admin password 5"),),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(
                            equals="policy-map type control-plane copp-system-policy"
                        ),
                        MatchRule(startswith="class"),
                        MatchRule(startswith="police"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="router bgp"),
                        MatchRule(startswith="vrf"),
                        MatchRule(startswith="neighbor"),
                        MatchRule(startswith="address-family"),
                        MatchRule(startswith="soft-reconfiguration inbound"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="router bgp"),
                        MatchRule(startswith="vrf"),
                        MatchRule(startswith="neighbor"),
                        MatchRule(startswith="password"),
                    ),
                ),
            ],
            negation_default_when=[
                NegationDefaultWhenRule(
                    match_rules=(
                        MatchRule(startswith="interface"),
                        MatchRule(
                            startswith="ip ospf bfd",
                            re_search="standby \\d+ authentication md5 key-string",
                        ),
                    ),
                ),
                NegationDefaultWhenRule(
                    match_rules=(
                        MatchRule(startswith="router bgp"),
                        MatchRule(startswith="neighbor"),
                        MatchRule(startswith="address-family"),
                        MatchRule(equals="send-community"),
                    ),
                ),
                NegationDefaultWhenRule(
                    match_rules=(
                        MatchRule(startswith="interface"),
                        MatchRule(contains="ip ospf passive-interface"),
                    ),
                ),
                NegationDefaultWhenRule(
                    match_rules=(
                        MatchRule(startswith="interface"),
                        MatchRule(contains="ospfv3 passive-interface"),
                    ),
                ),
            ],
            negate_with=[
                NegationDefaultWithRule(
                    match_rules=(
                        MatchRule(startswith="router bgp"),
                        MatchRule(startswith="address-family"),
                        MatchRule(startswith="maximum-paths ibgp"),
                    ),
                    use="default maximum-paths ibgp",
                ),
                NegationDefaultWithRule(
                    match_rules=(
                        MatchRule(startswith="router bgp"),
                        MatchRule(startswith="vrf"),
                        MatchRule(startswith="address-family"),
                        MatchRule(startswith="maximum-paths ibgp"),
                    ),
                    use="default maximum-paths ibgp",
                ),
                NegationDefaultWithRule(
                    match_rules=(
                        MatchRule(equals="line vty"),
                        MatchRule(startswith="session-limit"),
                    ),
                    use="session-limit 32",
                ),
            ],
        )
