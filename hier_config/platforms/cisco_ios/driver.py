from logging import getLogger

from hier_config.models import (
    IdempotentCommandsRule,
    MatchRule,
    NegationDefaultWithRule,
    OrderingRule,
    ParentAllowsDuplicateChildRule,
    PerLineSubRule,
    ReferencePattern,
    SectionalExitingRule,
    UnusedObjectRule,
)
from hier_config.platforms.driver_base import HConfigDriverBase, HConfigDriverRules
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
                entry.delete()


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
    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        return HConfigDriverRules(
            negate_with=[
                NegationDefaultWithRule(
                    match_rules=(MatchRule(startswith="logging console "),),
                    use="logging console debugging",
                ),
            ],
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
            ordering=[
                OrderingRule(
                    match_rules=(
                        MatchRule(startswith="interface"),
                        MatchRule(startswith="switchport mode "),
                    ),
                    weight=-10,
                ),
                OrderingRule(
                    match_rules=(MatchRule(startswith="no vlan filter"),),
                    weight=200,
                ),
                OrderingRule(
                    match_rules=(
                        MatchRule(startswith="interface"),
                        MatchRule(startswith="no shutdown"),
                    ),
                    weight=200,
                ),
                OrderingRule(
                    match_rules=(
                        MatchRule(startswith="aaa group server tacacs+ "),
                        MatchRule(startswith="no server "),
                    ),
                    weight=10,
                ),
                OrderingRule(
                    match_rules=(MatchRule(startswith="no tacacs-server "),),
                    weight=10,
                ),
            ],
            parent_allows_duplicate_child=[
                ParentAllowsDuplicateChildRule(
                    match_rules=(
                        MatchRule(startswith="router"),
                        MatchRule(startswith="address-family"),
                    ),
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
                PerLineSubRule(
                    search="^crypto key generate rsa general-keys.*$", replace=""
                ),
            ],
            idempotent_commands=[
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="vlan"),
                        MatchRule(startswith="name"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface "),
                        MatchRule(startswith="description "),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface "),
                        MatchRule(startswith="ip address "),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface "),
                        MatchRule(startswith="switchport mode "),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface "),
                        MatchRule(startswith="authentication host-mode "),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface "),
                        MatchRule(
                            startswith="authentication event server dead action authorize vlan ",
                        ),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="errdisable recovery interval "),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(re_search=r"^(no )?logging console.*"),),
                ),
            ],
            post_load_callbacks=[
                _rm_ipv6_acl_sequence_numbers,
                _remove_ipv4_acl_remarks,
                _add_acl_sequence_numbers,
            ],
            unused_object_rules=[
                # IPv4 ACLs
                UnusedObjectRule(
                    object_type="ipv4-acl",
                    definition_match=(MatchRule(startswith="ip access-list "),),
                    reference_patterns=(
                        # Interface applications
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="interface "),
                                MatchRule(re_search=r"ip access-group "),
                            ),
                            extract_regex=r"ip access-group\s+(\S+)",
                            reference_type="interface-applied",
                        ),
                        # VTY line applications
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="line "),
                                MatchRule(startswith="access-class "),
                            ),
                            extract_regex=r"access-class\s+(\S+)",
                            reference_type="line-applied",
                        ),
                        # Class map references
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="class-map "),
                                MatchRule(startswith="match access-group "),
                            ),
                            extract_regex=r"match access-group\s+(?:name\s+)?(\S+)",
                            reference_type="class-map-match",
                        ),
                        # Crypto map references
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="crypto map "),
                                MatchRule(startswith="match address "),
                            ),
                            extract_regex=r"match address\s+(\S+)",
                            reference_type="crypto-map",
                        ),
                        # Route-map match references
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="route-map "),
                                MatchRule(startswith="match ip address "),
                            ),
                            extract_regex=r"match ip address\s+(\S+)",
                            reference_type="route-map-match",
                        ),
                        # NAT references
                        ReferencePattern(
                            match_rules=(MatchRule(re_search=r"ip nat "),),
                            extract_regex=r"ip nat \S+.*?(?:access-list|pool)\s+(\S+)",
                            reference_type="nat",
                        ),
                    ),
                    removal_template="no ip access-list {acl_type} {name}",
                    removal_order_weight=150,
                    case_sensitive=False,  # IOS is case-insensitive
                ),
                # IPv6 ACLs
                UnusedObjectRule(
                    object_type="ipv6-acl",
                    definition_match=(MatchRule(startswith="ipv6 access-list "),),
                    reference_patterns=(
                        # Interface applications
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="interface "),
                                MatchRule(startswith="ipv6 traffic-filter "),
                            ),
                            extract_regex=r"ipv6 traffic-filter\s+(\S+)",
                            reference_type="interface-applied",
                        ),
                        # Line applications
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
                # Prefix lists
                UnusedObjectRule(
                    object_type="prefix-list",
                    definition_match=(MatchRule(startswith="ip prefix-list "),),
                    reference_patterns=(
                        # Route-map references
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="route-map "),
                                MatchRule(startswith="match ip address prefix-list "),
                            ),
                            extract_regex=r"match ip address prefix-list\s+(\S+)",
                            reference_type="route-map-match",
                        ),
                        # BGP neighbor filters
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="router bgp "),
                                MatchRule(re_search=r"neighbor\s+\S+\s+prefix-list"),
                            ),
                            extract_regex=r"neighbor\s+\S+\s+prefix-list\s+(\S+)",
                            reference_type="bgp-neighbor-filter",
                        ),
                        # BGP address-family neighbor filters
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="router bgp "),
                                MatchRule(startswith="address-family "),
                                MatchRule(re_search=r"neighbor\s+\S+\s+prefix-list"),
                            ),
                            extract_regex=r"neighbor\s+\S+\s+prefix-list\s+(\S+)",
                            reference_type="bgp-af-neighbor-filter",
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
                        # Route-map references
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="route-map "),
                                MatchRule(startswith="match ipv6 address prefix-list "),
                            ),
                            extract_regex=r"match ipv6 address prefix-list\s+(\S+)",
                            reference_type="route-map-match",
                        ),
                        # BGP neighbor filters
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
                        # BGP neighbor route-maps
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="router bgp "),
                                MatchRule(re_search=r"neighbor\s+\S+\s+route-map"),
                            ),
                            extract_regex=r"neighbor\s+\S+\s+route-map\s+(\S+)",
                            reference_type="bgp-neighbor-policy",
                        ),
                        # BGP address-family neighbor route-maps
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="router bgp "),
                                MatchRule(startswith="address-family "),
                                MatchRule(re_search=r"neighbor\s+\S+\s+route-map"),
                            ),
                            extract_regex=r"neighbor\s+\S+\s+route-map\s+(\S+)",
                            reference_type="bgp-af-neighbor-policy",
                        ),
                        # Redistribution in routing protocols
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="router "),
                                MatchRule(startswith="redistribute "),
                            ),
                            extract_regex=r"redistribute\s+\S+.*?route-map\s+(\S+)",
                            reference_type="redistribution",
                        ),
                        # Interface policy routing
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="interface "),
                                MatchRule(startswith="ip policy route-map "),
                            ),
                            extract_regex=r"ip policy route-map\s+(\S+)",
                            reference_type="pbr",
                        ),
                        # VRF import/export maps
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="vrf definition "),
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
                        # Policy map references
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="policy-map "),
                                MatchRule(startswith="class "),
                            ),
                            extract_regex=r"class\s+(?!class-default)(\S+)",
                            reference_type="policy-map",
                        ),
                        # Control plane policy
                        ReferencePattern(
                            match_rules=(
                                MatchRule(equals="control-plane"),
                                MatchRule(startswith="service-policy "),
                            ),
                            extract_regex=r"service-policy\s+(?:input|output)\s+(\S+)",
                            reference_type="control-plane-policy",
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
                        # Interface service policies
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="interface "),
                                MatchRule(startswith="service-policy "),
                            ),
                            extract_regex=r"service-policy\s+(?:input|output)\s+(\S+)",
                            reference_type="interface-policy",
                        ),
                        # Control plane policy
                        ReferencePattern(
                            match_rules=(
                                MatchRule(equals="control-plane"),
                                MatchRule(startswith="service-policy "),
                            ),
                            extract_regex=r"service-policy\s+(?:input|output)\s+(\S+)",
                            reference_type="control-plane-policy",
                        ),
                        # Hierarchical QoS (policy within policy)
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
                # VRFs
                UnusedObjectRule(
                    object_type="vrf",
                    definition_match=(MatchRule(startswith="vrf definition "),),
                    reference_patterns=(
                        # Interface VRF membership
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="interface "),
                                MatchRule(startswith="vrf forwarding "),
                            ),
                            extract_regex=r"vrf forwarding\s+(\S+)",
                            reference_type="interface-vrf",
                        ),
                        # BGP VRF instance
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="router bgp "),
                                MatchRule(startswith="address-family ipv4 vrf "),
                            ),
                            extract_regex=r"address-family ipv4 vrf\s+(\S+)",
                            reference_type="bgp-vrf",
                        ),
                        # BGP IPv6 VRF instance
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="router bgp "),
                                MatchRule(startswith="address-family ipv6 vrf "),
                            ),
                            extract_regex=r"address-family ipv6 vrf\s+(\S+)",
                            reference_type="bgp-ipv6-vrf",
                        ),
                    ),
                    removal_template="no vrf definition {name}",
                    removal_order_weight=200,  # Remove last (high impact)
                    case_sensitive=False,
                ),
            ],
        )
