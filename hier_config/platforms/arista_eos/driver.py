from hier_config.models import (
    IdempotentCommandsRule,
    MatchRule,
    NegationDefaultWhenRule,
    PerLineSubRule,
    ReferencePattern,
    SectionalExitingRule,
    UnusedObjectRule,
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
            unused_object_rules=[
                # IPv4 ACLs (EOS is similar to IOS)
                UnusedObjectRule(
                    object_type="ipv4-acl",
                    definition_match=(MatchRule(startswith="ip access-list "),),
                    reference_patterns=(
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="interface "),
                                MatchRule(re_search=r"ip access-group "),
                            ),
                            extract_regex=r"ip access-group\s+(\S+)",
                            reference_type="interface-applied",
                        ),
                        ReferencePattern(
                            match_rules=(
                                MatchRule(equals="control-plane"),
                                MatchRule(startswith="ip access-group "),
                            ),
                            extract_regex=r"ip access-group\s+(\S+)",
                            reference_type="control-plane",
                        ),
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="class-map "),
                                MatchRule(startswith="match ip access-group "),
                            ),
                            extract_regex=r"match ip access-group\s+(\S+)",
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
                    ),
                    removal_template="no ip access-list {name}",
                    removal_order_weight=150,
                    case_sensitive=False,  # EOS is case-insensitive like IOS
                ),
                # IPv6 ACLs
                UnusedObjectRule(
                    object_type="ipv6-acl",
                    definition_match=(MatchRule(startswith="ipv6 access-list "),),
                    reference_patterns=(
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="interface "),
                                MatchRule(startswith="ipv6 access-group "),
                            ),
                            extract_regex=r"ipv6 access-group\s+(\S+)",
                            reference_type="interface-applied",
                        ),
                    ),
                    removal_template="no ipv6 access-list {name}",
                    removal_order_weight=150,
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
                # IPv6 Prefix lists
                UnusedObjectRule(
                    object_type="ipv6-prefix-list",
                    definition_match=(MatchRule(startswith="ipv6 prefix-list "),),
                    reference_patterns=(
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="route-map "),
                                MatchRule(startswith="match ipv6 address prefix-list "),
                            ),
                            extract_regex=r"match ipv6 address prefix-list\s+(\S+)",
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
                    removal_template="no ipv6 prefix-list {name}",
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
                                MatchRule(startswith="vrf instance "),
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
                # VRFs (vrf instance on EOS)
                UnusedObjectRule(
                    object_type="vrf",
                    definition_match=(MatchRule(startswith="vrf instance "),),
                    reference_patterns=(
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="interface "),
                                MatchRule(startswith="vrf "),
                            ),
                            extract_regex=r"vrf\s+(\S+)",
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
                    removal_template="no vrf instance {name}",
                    removal_order_weight=200,
                    case_sensitive=False,
                ),
                # IPv6 General Prefixes (EOS-specific)
                UnusedObjectRule(
                    object_type="ipv6-general-prefix",
                    definition_match=(MatchRule(startswith="ipv6 general-prefix "),),
                    reference_patterns=(
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="interface "),
                                MatchRule(re_search=r"ipv6 address.*general-prefix"),
                            ),
                            extract_regex=r"ipv6 address\s+\S+\s+(\S+)",
                            reference_type="interface-ipv6",
                        ),
                    ),
                    removal_template="no ipv6 general-prefix {name}",
                    removal_order_weight=150,
                    case_sensitive=False,
                ),
            ],
        )
