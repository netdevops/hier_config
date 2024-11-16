from collections.abc import Iterable
from typing import Optional

from hier_config.child import HConfigChild
from hier_config.models import (
    IdempotentCommandsRule,
    IndentAdjustRule,
    MatchRule,
    OrderingRule,
    ParentAllowsDuplicateChildRule,
    PerLineSubRule,
    SectionalExitingRule,
    SectionalOverwriteNoNegateRule,
    SectionalOverwriteRule,
)
from hier_config.platforms.driver_base import HConfigDriverBase, HConfigDriverRules


class HConfigDriverCiscoIOSXR(HConfigDriverBase):  # pylint: disable=too-many-instance-attributes
    def idempotent_for(
        self,
        config: HConfigChild,
        other_children: Iterable[HConfigChild],
    ) -> Optional[HConfigChild]:
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
                    match_rules=(MatchRule(startswith="snmp-server community"),),
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
        )
