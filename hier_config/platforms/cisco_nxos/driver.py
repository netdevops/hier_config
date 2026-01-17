from hier_config.models import (
    IdempotentCommandsAvoidRule,
    IdempotentCommandsRule,
    MatchRule,
    NegationDefaultWhenRule,
    NegationDefaultWithRule,
    PerLineSubRule,
    ReferencePattern,
    UnusedObjectRule,
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
            unused_object_rules=[
                # IPv4 ACLs (similar to IOS)
                UnusedObjectRule(
                    object_type="ipv4-acl",
                    definition_match=(MatchRule(startswith="ip access-list "),),
                    reference_patterns=(
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="interface "),
                                MatchRule(
                                    re_search=r"ip (access-group|port access-group)"
                                ),
                            ),
                            extract_regex=r"ip (?:access-group|port access-group)\s+(\S+)",
                            reference_type="interface-applied",
                        ),
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="line "),
                                MatchRule(startswith="access-class "),
                            ),
                            extract_regex=r"access-class\s+(\S+)",
                            reference_type="line-applied",
                        ),
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="class-map "),
                                MatchRule(startswith="match access-group "),
                            ),
                            extract_regex=r"match access-group\s+(?:name\s+)?(\S+)",
                            reference_type="class-map-match",
                        ),
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="route-map "),
                                MatchRule(startswith="match ip address "),
                            ),
                            extract_regex=r"match ip address\s+(\S+)",
                            reference_type="route-map-match",
                        ),
                        # VLAN access-map (VACL)
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="vlan access-map "),
                                MatchRule(startswith="match ip address "),
                            ),
                            extract_regex=r"match ip address\s+(\S+)",
                            reference_type="vacl",
                        ),
                    ),
                    removal_template="no ip access-list {name}",
                    removal_order_weight=150,
                    case_sensitive=False,
                ),
                # IPv6 ACLs
                UnusedObjectRule(
                    object_type="ipv6-acl",
                    definition_match=(MatchRule(startswith="ipv6 access-list "),),
                    reference_patterns=(
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="interface "),
                                MatchRule(startswith="ipv6 traffic-filter "),
                            ),
                            extract_regex=r"ipv6 traffic-filter\s+(\S+)",
                            reference_type="interface-applied",
                        ),
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="line "),
                                MatchRule(startswith="ipv6 access-class "),
                            ),
                            extract_regex=r"ipv6 access-class\s+(\S+)",
                            reference_type="line-applied",
                        ),
                    ),
                    removal_template="no ipv6 access-list {name}",
                    removal_order_weight=150,
                    case_sensitive=False,
                ),
                # Object-groups (NX-OS specific)
                UnusedObjectRule(
                    object_type="object-group",
                    definition_match=(MatchRule(startswith="object-group "),),
                    reference_patterns=(
                        # ACL references
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="ip access-list "),
                                MatchRule(re_search=r"(permit|deny).*addrgroup"),
                            ),
                            extract_regex=r"addrgroup\s+(\S+)",
                            reference_type="acl-match",
                        ),
                    ),
                    removal_template="no object-group {group_type} {name}",
                    removal_order_weight=140,
                    case_sensitive=False,
                ),
                # Prefix lists
                UnusedObjectRule(
                    object_type="prefix-list",
                    definition_match=(MatchRule(startswith="ip prefix-list "),),
                    reference_patterns=(
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="route-map "),
                                MatchRule(startswith="match ip address prefix-list "),
                            ),
                            extract_regex=r"match ip address prefix-list\s+(\S+)",
                            reference_type="route-map-match",
                        ),
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="router bgp "),
                                MatchRule(re_search=r"neighbor\s+\S+\s+prefix-list"),
                            ),
                            extract_regex=r"neighbor\s+\S+\s+prefix-list\s+(\S+)",
                            reference_type="bgp-neighbor-filter",
                        ),
                    ),
                    removal_template="no ip prefix-list {name}",
                    removal_order_weight=140,
                    case_sensitive=False,
                ),
                # Route maps
                UnusedObjectRule(
                    object_type="route-map",
                    definition_match=(MatchRule(startswith="route-map "),),
                    reference_patterns=(
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="router bgp "),
                                MatchRule(re_search=r"neighbor\s+\S+\s+route-map"),
                            ),
                            extract_regex=r"neighbor\s+\S+\s+route-map\s+(\S+)",
                            reference_type="bgp-neighbor-policy",
                        ),
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="router "),
                                MatchRule(startswith="redistribute "),
                            ),
                            extract_regex=r"redistribute\s+\S+.*?route-map\s+(\S+)",
                            reference_type="redistribution",
                        ),
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="interface "),
                                MatchRule(startswith="ip policy route-map "),
                            ),
                            extract_regex=r"ip policy route-map\s+(\S+)",
                            reference_type="pbr",
                        ),
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="vrf context "),
                                MatchRule(re_search=r"(import|export).*map"),
                            ),
                            extract_regex=r"(?:import|export)\s+(?:ipv4|ipv6)?\s*(?:unicast)?\s*map\s+(\S+)",
                            reference_type="vrf-policy",
                        ),
                    ),
                    removal_template="no route-map {name}",
                    removal_order_weight=130,
                    case_sensitive=False,
                ),
                # Class maps
                UnusedObjectRule(
                    object_type="class-map",
                    definition_match=(MatchRule(startswith="class-map "),),
                    reference_patterns=(
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="policy-map "),
                                MatchRule(startswith="class "),
                            ),
                            extract_regex=r"class\s+(?!class-default)(\S+)",
                            reference_type="policy-map",
                        ),
                    ),
                    removal_template="no class-map {match_type} {name}",
                    removal_order_weight=120,
                    case_sensitive=False,
                ),
                # Policy maps
                UnusedObjectRule(
                    object_type="policy-map",
                    definition_match=(MatchRule(startswith="policy-map "),),
                    reference_patterns=(
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="interface "),
                                MatchRule(startswith="service-policy "),
                            ),
                            extract_regex=r"service-policy\s+(?:input|output)\s+(\S+)",
                            reference_type="interface-policy",
                        ),
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="policy-map "),
                                MatchRule(startswith="class "),
                                MatchRule(startswith="service-policy "),
                            ),
                            extract_regex=r"service-policy\s+(\S+)",
                            reference_type="hierarchical-policy",
                        ),
                    ),
                    removal_template="no policy-map {name}",
                    removal_order_weight=110,
                    case_sensitive=False,
                ),
                # VRFs (vrf context on NX-OS)
                UnusedObjectRule(
                    object_type="vrf",
                    definition_match=(MatchRule(startswith="vrf context "),),
                    reference_patterns=(
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="interface "),
                                MatchRule(startswith="vrf member "),
                            ),
                            extract_regex=r"vrf member\s+(\S+)",
                            reference_type="interface-vrf",
                        ),
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="router bgp "),
                                MatchRule(startswith="vrf "),
                            ),
                            extract_regex=r"vrf\s+(\S+)",
                            reference_type="bgp-vrf",
                        ),
                    ),
                    removal_template="no vrf context {name}",
                    removal_order_weight=200,
                    case_sensitive=False,
                ),
            ],
        )
