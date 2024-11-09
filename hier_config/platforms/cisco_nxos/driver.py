from hier_config.model import (
    IdempotentCommandsAvoidRule,
    IdempotentCommandsRule,
    MatchRule,
    NegationDefaultWhenRule,
    NegationDefaultWithRule,
    PerLineSubRule,
    Platform,
)
from hier_config.platforms.driver_base import HConfigDriverBase


class HConfigDriverCiscoNXOS(HConfigDriverBase):
    per_line_sub_rules: tuple[PerLineSubRule, ...] = (
        PerLineSubRule(search="^Building configuration.*", replace=""),
        PerLineSubRule(search="^Current configuration.*", replace=""),
        PerLineSubRule(search="^ntp clock-period .*", replace=""),
        PerLineSubRule(
            search="^snmp-server location  ", replace="snmp-server location "
        ),
        PerLineSubRule(search="^version.*", replace=""),
        PerLineSubRule(search="^boot (system|kickstart) .*", replace=""),
        PerLineSubRule(search="!.*", replace=""),
    )

    idempotent_commands_avoid_rules: tuple[IdempotentCommandsAvoidRule, ...] = (
        IdempotentCommandsAvoidRule(
            lineage=(
                MatchRule(startswith="interface"),
                MatchRule(re_search="ip address.*secondary"),
            )
        ),
    )

    idempotent_commands_rules: tuple[IdempotentCommandsRule, ...] = (
        IdempotentCommandsRule(
            lineage=(MatchRule(startswith="power redundancy-mode"),)
        ),
        IdempotentCommandsRule(lineage=(MatchRule(startswith="cli alias name wr "),)),
        IdempotentCommandsRule(
            lineage=(MatchRule(startswith="aaa authentication login console"),)
        ),
        IdempotentCommandsRule(
            lineage=(MatchRule(startswith="port-channel load-balance"),)
        ),
        IdempotentCommandsRule(lineage=(MatchRule(startswith="hostname "),)),
        IdempotentCommandsRule(
            lineage=(MatchRule(startswith="ip tftp source-interface"),)
        ),
        IdempotentCommandsRule(
            lineage=(MatchRule(startswith="ip telnet source-interface"),)
        ),
        IdempotentCommandsRule(
            lineage=(MatchRule(startswith="ip tacacs source-interface"),)
        ),
        IdempotentCommandsRule(
            lineage=(MatchRule(startswith="logging source-interface"),)
        ),
        IdempotentCommandsRule(
            lineage=(MatchRule(startswith="hardware access-list tcam region ifacl"),)
        ),
        IdempotentCommandsRule(
            lineage=(MatchRule(startswith="hardware access-list tcam region vacl"),)
        ),
        IdempotentCommandsRule(
            lineage=(MatchRule(startswith="hardware access-list tcam region qos"),)
        ),
        IdempotentCommandsRule(
            lineage=(MatchRule(startswith="hardware access-list tcam region racl"),)
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="hardware access-list tcam region ipv6-racl"),
            )
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="hardware access-list tcam region e-ipv6-racl"),
            )
        ),
        IdempotentCommandsRule(
            lineage=(MatchRule(startswith="hardware access-list tcam region l3qos"),)
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="router ospf"),
                MatchRule(startswith="vrf"),
                MatchRule(startswith="maximum-paths"),
            )
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="router ospf"),
                MatchRule(startswith="vrf"),
                MatchRule(startswith="log-adjacency-changes"),
            )
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="router ospf"),
                MatchRule(startswith="maximum-paths"),
            )
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="router ospf"),
                MatchRule(startswith="log-adjacency-changes"),
            )
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="router bgp"),
                MatchRule(startswith="vrf"),
                MatchRule(startswith="address-family"),
                MatchRule(startswith="maximum-paths"),
            )
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="router bgp"),
                MatchRule(startswith="address-family"),
                MatchRule(startswith="maximum-paths"),
            )
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="router bgp"),
                MatchRule(startswith="template"),
                MatchRule(startswith="address-family"),
                MatchRule(startswith="send-community"),
            )
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="interface"),
                MatchRule(re_search="^hsrp \\d+"),
                MatchRule(startswith="ip"),
            )
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="interface"),
                MatchRule(re_search="^hsrp \\d+"),
                MatchRule(startswith="priority"),
            )
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="interface"),
                MatchRule(re_search="^hsrp \\d+"),
                MatchRule(startswith="authentication md5 key-string"),
            )
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="interface"),
                MatchRule(startswith="ip address"),
            )
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="interface"),
                MatchRule(startswith="duplex"),
            )
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="interface"),
                MatchRule(startswith="speed"),
            )
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="interface"),
                MatchRule(startswith="switchport mode"),
            )
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="interface"),
                MatchRule(startswith="switchport access vlan"),
            )
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="interface"),
                MatchRule(startswith="switchport trunk native vlan"),
            )
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="interface"),
                MatchRule(startswith="switchport trunk allowed vlan"),
            )
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="interface"),
                MatchRule(startswith="udld port"),
            )
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="interface"),
                MatchRule(startswith="ip ospf cost"),
            )
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="interface"),
                MatchRule(startswith="ipv6 link-local"),
            )
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="interface"),
                MatchRule(startswith="ospfv3 cost"),
            )
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="interface"),
                MatchRule(startswith="mtu"),
            )
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(equals="line console"),
                MatchRule(startswith="exec-timeout"),
            )
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="line vty"),
                MatchRule(startswith="transport input"),
            )
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="line vty"),
                MatchRule(startswith="ipv6 access-class"),
            )
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="line vty"),
                MatchRule(startswith="access-class"),
            )
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="router bgp"),
                MatchRule(
                    startswith="bgp router-id",
                ),
            )
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="router bgp"),
                MatchRule(
                    re_search="neighbor \\S+ description",
                ),
            )
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="router ospf"),
                MatchRule(startswith="router-id"),
            )
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="router ospf"),
                MatchRule(startswith="log-adjacency-changes"),
            )
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="ipv6 router ospf"),
                MatchRule(startswith="router-id"),
            )
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="ipv6 router ospf"),
                MatchRule(startswith="log-adjacency-changes"),
            )
        ),
        IdempotentCommandsRule(
            lineage=(MatchRule(startswith="mac address-table aging-time"),)
        ),
        IdempotentCommandsRule(
            lineage=(MatchRule(startswith="snmp-server community"),)
        ),
        IdempotentCommandsRule(lineage=(MatchRule(startswith="snmp-server location"),)),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="vpc domain"),
                MatchRule(startswith="role priority"),
            )
        ),
        IdempotentCommandsRule(lineage=(MatchRule(startswith="banner"),)),
        IdempotentCommandsRule(
            lineage=(MatchRule(startswith="username admin password 5"),)
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(equals="policy-map type control-plane copp-system-policy"),
                MatchRule(startswith="class"),
                MatchRule(startswith="police"),
            )
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="router bgp"),
                MatchRule(startswith="vrf"),
                MatchRule(startswith="neighbor"),
                MatchRule(startswith="address-family"),
                MatchRule(startswith="soft-reconfiguration inbound"),
            )
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="router bgp"),
                MatchRule(startswith="vrf"),
                MatchRule(startswith="neighbor"),
                MatchRule(startswith="password"),
            )
        ),
    )
    negation_default_when_rules: tuple[NegationDefaultWhenRule, ...] = (
        NegationDefaultWhenRule(
            lineage=(
                MatchRule(startswith="interface"),
                MatchRule(
                    startswith="ip ospf bfd",
                    re_search="standby \\d+ authentication md5 key-string",
                ),
            )
        ),
        NegationDefaultWhenRule(
            lineage=(
                MatchRule(startswith="router bgp"),
                MatchRule(startswith="neighbor"),
                MatchRule(startswith="address-family"),
                MatchRule(equals="send-community"),
            )
        ),
        NegationDefaultWhenRule(
            lineage=(
                MatchRule(startswith="interface"),
                MatchRule(contains="ip ospf passive-interface"),
            )
        ),
        NegationDefaultWhenRule(
            lineage=(
                MatchRule(startswith="interface"),
                MatchRule(contains="ospfv3 passive-interface"),
            )
        ),
    )
    negation_negate_with_rules: tuple[NegationDefaultWithRule, ...] = (
        NegationDefaultWithRule(
            lineage=(
                MatchRule(startswith="router bgp"),
                MatchRule(startswith="address-family"),
                MatchRule(startswith="maximum-paths ibgp"),
            ),
            use="default maximum-paths ibgp",
        ),
        NegationDefaultWithRule(
            lineage=(
                MatchRule(startswith="router bgp"),
                MatchRule(startswith="vrf"),
                MatchRule(startswith="address-family"),
                MatchRule(startswith="maximum-paths ibgp"),
            ),
            use="default maximum-paths ibgp",
        ),
        NegationDefaultWithRule(
            lineage=(
                MatchRule(equals="line vty"),
                MatchRule(startswith="session-limit"),
            ),
            use="session-limit 32",
        ),
    )

    @property
    def platform(self) -> Platform:
        return Platform.CISCO_NXOS
