from collections.abc import Iterable

from hier_config.child import HConfigChild
from hier_config.models import (
    IdempotentCommandsRule,
    IndentAdjustRule,
    MatchRule,
    OrderingRule,
    ParentAllowsDuplicateChildRule,
    PerLineSubRule,
    ReferencePattern,
    SectionalExitingRule,
    SectionalOverwriteNoNegateRule,
    SectionalOverwriteRule,
    UnusedObjectRule,
)
from hier_config.platforms.driver_base import HConfigDriverBase, HConfigDriverRules


class HConfigDriverCiscoIOSXR(HConfigDriverBase):  # pylint: disable=too-many-instance-attributes
    def idempotent_for(
        self,
        config: HConfigChild,
        other_children: Iterable[HConfigChild],
    ) -> HConfigChild | None:
        if isinstance(config.parent, HConfigChild):
            acl = ("ipv4 access-list ", "ipv6 access-list ")
            if config.parent.text.startswith(acl):
                self_sn = config.text.split(" ", 1)[0]
                for other_child in other_children:
                    other_sn = other_child.text.split(" ", 1)[0]
                    if self_sn == other_sn:
                        return other_child

        return super().idempotent_for(config, other_children)

    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        return HConfigDriverRules(
            sectional_exiting=[
                SectionalExitingRule(
                    match_rules=(MatchRule(startswith="route-policy"),),
                    exit_text="end-policy",
                ),
                SectionalExitingRule(
                    match_rules=(MatchRule(startswith="prefix-set"),),
                    exit_text="end-set",
                ),
                SectionalExitingRule(
                    match_rules=(MatchRule(startswith="policy-map"),),
                    exit_text="end-policy-map",
                ),
                SectionalExitingRule(
                    match_rules=(MatchRule(startswith="class-map"),),
                    exit_text="end-class-map",
                ),
                SectionalExitingRule(
                    match_rules=(MatchRule(startswith="community-set"),),
                    exit_text="end-set",
                ),
                SectionalExitingRule(
                    match_rules=(MatchRule(startswith="extcommunity-set"),),
                    exit_text="end-set",
                ),
                SectionalExitingRule(
                    match_rules=(MatchRule(startswith="template"),),
                    exit_text="end-template",
                ),
                SectionalExitingRule(
                    match_rules=(MatchRule(startswith="interface"),),
                    exit_text="root",
                ),
                SectionalExitingRule(
                    match_rules=(MatchRule(startswith="router bgp"),),
                    exit_text="root",
                ),
            ],
            sectional_overwrite=[
                SectionalOverwriteRule(match_rules=(MatchRule(startswith="template"),)),
            ],
            sectional_overwrite_no_negate=[
                SectionalOverwriteNoNegateRule(
                    match_rules=(MatchRule(startswith="as-path-set"),)
                ),
                SectionalOverwriteNoNegateRule(
                    match_rules=(MatchRule(startswith="prefix-set"),)
                ),
                SectionalOverwriteNoNegateRule(
                    match_rules=(MatchRule(startswith="route-policy"),)
                ),
                SectionalOverwriteNoNegateRule(
                    match_rules=(MatchRule(startswith="extcommunity-set"),),
                ),
                SectionalOverwriteNoNegateRule(
                    match_rules=(MatchRule(startswith="community-set"),),
                ),
            ],
            ordering=[
                OrderingRule(
                    match_rules=(MatchRule(startswith="vrf "),),
                    weight=-200,
                ),
                OrderingRule(
                    match_rules=(MatchRule(startswith="no vrf "),),
                    weight=200,
                ),
            ],
            indent_adjust=[
                IndentAdjustRule(
                    start_expression="^\\s*template",
                    end_expression="^\\s*end-template",
                ),
            ],
            parent_allows_duplicate_child=[
                ParentAllowsDuplicateChildRule(
                    match_rules=(MatchRule(startswith="route-policy"),)
                ),
            ],
            per_line_sub=[
                PerLineSubRule(search="^Building configuration.*", replace=""),
                PerLineSubRule(search="^Current configuration.*", replace=""),
                PerLineSubRule(search="^ntp clock-period .*", replace=""),
                PerLineSubRule(search=".*speed.*", replace=""),
                PerLineSubRule(search=".*duplex.*", replace=""),
                PerLineSubRule(search=".*negotiation auto.*", replace=""),
                PerLineSubRule(search=".*parity none.*", replace=""),
                PerLineSubRule(search="^end-policy$", replace=" end-policy"),
                PerLineSubRule(search="^end-set$", replace=" end-set"),
                PerLineSubRule(search="^end$", replace=""),
                PerLineSubRule(search="^\\s*[#!].*", replace=""),
            ],
            idempotent_commands=[
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="router bgp"),
                        MatchRule(startswith="vrf"),
                        MatchRule(startswith="address-family"),
                        MatchRule(startswith="additional-paths selection route-policy"),
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
                        MatchRule(startswith="router bgp"),
                        MatchRule(startswith="neighbor-group"),
                        MatchRule(startswith="address-family"),
                        MatchRule(startswith="soft-reconfiguration inbound"),
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
                        MatchRule(startswith="address-family"),
                        MatchRule(startswith="maximum-prefix"),
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
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="router bgp"),
                        MatchRule(startswith="vrf"),
                        MatchRule(startswith="neighbor"),
                        MatchRule(startswith="description"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="router bgp"),
                        MatchRule(startswith="neighbor"),
                        MatchRule(startswith="description"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="router bgp"),
                        MatchRule(startswith="neighbor"),
                        MatchRule(startswith="password"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="router ospf"),
                        MatchRule(startswith="area"),
                        MatchRule(startswith="interface"),
                        MatchRule(startswith="cost"),
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
                        MatchRule(startswith="area"),
                        MatchRule(startswith="message-digest-key"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="router ospf"),
                        MatchRule(startswith="max-metric router-lsa"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(equals="l2vpn"),
                        MatchRule(startswith="router-id"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(re_search="logging \\d+.\\d+.\\d+.\\d+ vrf MGMT"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(equals="line default"),
                        MatchRule(startswith="access-class ingress"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(equals="line default"),
                        MatchRule(startswith="transport input"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="hostname"),),
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="logging source-interface"),),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface"),
                        MatchRule(startswith="ipv4 address"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="snmp-server location"),),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(equals="line console"),
                        MatchRule(startswith="exec-timeout"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(equals="mpls ldp"),
                        MatchRule(startswith="session protection duration"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(equals="mpls ldp"),
                        MatchRule(startswith="igp sync delay"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface"),
                        MatchRule(startswith="mtu"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="banner"),),
                ),
            ],
            unused_object_rules=[
                # IPv4 ACLs
                UnusedObjectRule(
                    object_type="ipv4-acl",
                    definition_match=(MatchRule(startswith="ipv4 access-list "),),
                    reference_patterns=(
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="interface "),
                                MatchRule(startswith="ipv4 access-group "),
                            ),
                            extract_regex=r"ipv4 access-group\s+(\S+)",
                            reference_type="interface-applied",
                        ),
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="line "),
                                MatchRule(startswith="access-class ipv4 "),
                            ),
                            extract_regex=r"access-class ipv4\s+(\S+)",
                            reference_type="line-applied",
                        ),
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="class-map "),
                                MatchRule(startswith="match access-group ipv4 "),
                            ),
                            extract_regex=r"match access-group ipv4\s+(\S+)",
                            reference_type="class-map-match",
                        ),
                    ),
                    removal_template="no ipv4 access-list {name}",
                    removal_order_weight=150,
                    case_sensitive=True,  # IOS-XR is case-sensitive
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
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="line "),
                                MatchRule(startswith="access-class ipv6 "),
                            ),
                            extract_regex=r"access-class ipv6\s+(\S+)",
                            reference_type="line-applied",
                        ),
                    ),
                    removal_template="no ipv6 access-list {name}",
                    removal_order_weight=150,
                    case_sensitive=True,
                ),
                # Prefix sets (IOS-XR specific)
                UnusedObjectRule(
                    object_type="prefix-set",
                    definition_match=(MatchRule(startswith="prefix-set "),),
                    reference_patterns=(
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="route-policy "),
                                MatchRule(re_search=r"destination in"),
                            ),
                            extract_regex=r"destination in\s+(\S+)",
                            reference_type="route-policy",
                        ),
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="route-policy "),
                                MatchRule(re_search=r"source in"),
                            ),
                            extract_regex=r"source in\s+(\S+)",
                            reference_type="route-policy",
                        ),
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="router bgp "),
                                MatchRule(re_search=r"neighbor"),
                                MatchRule(re_search=r"address-family"),
                                MatchRule(re_search=r"prefix-set"),
                            ),
                            extract_regex=r"prefix-set\s+(\S+)",
                            reference_type="bgp-neighbor-filter",
                        ),
                    ),
                    removal_template="no prefix-set {name}",
                    removal_order_weight=140,
                    case_sensitive=True,
                ),
                # AS Path Sets (IOS-XR specific)
                UnusedObjectRule(
                    object_type="as-path-set",
                    definition_match=(MatchRule(startswith="as-path-set "),),
                    reference_patterns=(
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="route-policy "),
                                MatchRule(re_search=r"as-path in"),
                            ),
                            extract_regex=r"as-path in\s+(\S+)",
                            reference_type="route-policy",
                        ),
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="router bgp "),
                                MatchRule(re_search=r"as-path-set"),
                            ),
                            extract_regex=r"as-path-set\s+(\S+)",
                            reference_type="bgp-filter",
                        ),
                    ),
                    removal_template="no as-path-set {name}",
                    removal_order_weight=140,
                    case_sensitive=True,
                ),
                # Community Sets (IOS-XR specific)
                UnusedObjectRule(
                    object_type="community-set",
                    definition_match=(MatchRule(startswith="community-set "),),
                    reference_patterns=(
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="route-policy "),
                                MatchRule(re_search=r"community matches-any"),
                            ),
                            extract_regex=r"community matches-any\s+(\S+)",
                            reference_type="route-policy",
                        ),
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="route-policy "),
                                MatchRule(re_search=r"community matches-every"),
                            ),
                            extract_regex=r"community matches-every\s+(\S+)",
                            reference_type="route-policy",
                        ),
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="route-policy "),
                                MatchRule(re_search=r"set community"),
                            ),
                            extract_regex=r"set community\s+(\S+)",
                            reference_type="route-policy-set",
                        ),
                    ),
                    removal_template="no community-set {name}",
                    removal_order_weight=140,
                    case_sensitive=True,
                ),
                # Route policies (IOS-XR uses route-policy instead of route-map)
                UnusedObjectRule(
                    object_type="route-policy",
                    definition_match=(MatchRule(startswith="route-policy "),),
                    reference_patterns=(
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="router bgp "),
                                MatchRule(re_search=r"neighbor"),
                                MatchRule(re_search=r"route-policy"),
                            ),
                            extract_regex=r"route-policy\s+(\S+)",
                            reference_type="bgp-neighbor-policy",
                        ),
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="router bgp "),
                                MatchRule(re_search=r"redistribute"),
                            ),
                            extract_regex=r"redistribute\s+\S+.*?route-policy\s+(\S+)",
                            reference_type="redistribution",
                        ),
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="router "),
                                MatchRule(startswith="redistribute "),
                            ),
                            extract_regex=r"redistribute\s+\S+.*?route-policy\s+(\S+)",
                            reference_type="redistribution",
                        ),
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="vrf "),
                                MatchRule(re_search=r"(import|export).*route-policy"),
                            ),
                            extract_regex=r"(?:import|export)\s+route-policy\s+(\S+)",
                            reference_type="vrf-policy",
                        ),
                    ),
                    removal_template="no route-policy {name}",
                    removal_order_weight=130,
                    case_sensitive=True,
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
                    case_sensitive=True,
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
                    case_sensitive=True,
                ),
                # VRFs
                UnusedObjectRule(
                    object_type="vrf",
                    definition_match=(MatchRule(startswith="vrf "),),
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
                    removal_template="no vrf {name}",
                    removal_order_weight=200,
                    case_sensitive=True,
                ),
            ],
        )
