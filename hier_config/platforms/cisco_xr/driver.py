from collections.abc import Iterable

from hier_config.child import HConfigChild
from hier_config.model import (
    IdempotentCommandsRule,
    IndentAdjustRule,
    MatchRule,
    OrderingRule,
    ParentAllowsDuplicateChildRule,
    PerLineSubRule,
    Platform,
    SectionalExitingRule,
    SectionalOverwriteNoNegateRule,
    SectionalOverwriteRule,
)
from hier_config.platforms.driver_base import HConfigDriverBase


class HConfigDriverCiscoIOSXR(HConfigDriverBase):  # pylint: disable=too-many-instance-attributes
    sectional_exiting_rules: tuple[SectionalExitingRule, ...] = (
        SectionalExitingRule(
            lineage=(MatchRule(startswith="route-policy"),),
            exit_text="end-policy",
        ),
        SectionalExitingRule(
            lineage=(MatchRule(startswith="prefix-set"),),
            exit_text="end-set",
        ),
        SectionalExitingRule(
            lineage=(MatchRule(startswith="policy-map"),),
            exit_text="end-policy-map",
        ),
        SectionalExitingRule(
            lineage=(MatchRule(startswith="class-map"),),
            exit_text="end-class-map",
        ),
        SectionalExitingRule(
            lineage=(MatchRule(startswith="community-set"),),
            exit_text="end-set",
        ),
        SectionalExitingRule(
            lineage=(MatchRule(startswith="extcommunity-set"),),
            exit_text="end-set",
        ),
        SectionalExitingRule(
            lineage=(MatchRule(startswith="template"),),
            exit_text="end-template",
        ),
        SectionalExitingRule(
            lineage=(MatchRule(startswith="interface"),),
            exit_text="root",
        ),
        SectionalExitingRule(
            lineage=(MatchRule(startswith="router bgp"),),
            exit_text="root",
        ),
    )
    sectional_overwrite_rules: tuple[SectionalOverwriteRule, ...] = (
        SectionalOverwriteRule(lineage=(MatchRule(startswith="template"),)),
    )
    sectional_overwrite_no_negate_rules: tuple[SectionalOverwriteNoNegateRule, ...] = (
        SectionalOverwriteNoNegateRule(lineage=(MatchRule(startswith="as-path-set"),)),
        SectionalOverwriteNoNegateRule(lineage=(MatchRule(startswith="prefix-set"),)),
        SectionalOverwriteNoNegateRule(lineage=(MatchRule(startswith="route-policy"),)),
        SectionalOverwriteNoNegateRule(
            lineage=(MatchRule(startswith="extcommunity-set"),)
        ),
        SectionalOverwriteNoNegateRule(
            lineage=(MatchRule(startswith="community-set"),)
        ),
    )
    ordering_rules: tuple[OrderingRule, ...] = (
        OrderingRule(
            lineage=(MatchRule(startswith="vrf "),),
            weight=-200,
        ),
        OrderingRule(
            lineage=(MatchRule(startswith="no vrf "),),
            weight=200,
        ),
    )

    indent_adjust_rules: tuple[IndentAdjustRule, ...] = (
        IndentAdjustRule(
            start_expression="^\\s*template", end_expression="^\\s*end-template"
        ),
    )
    parent_allows_duplicate_child_rules: tuple[ParentAllowsDuplicateChildRule, ...] = (
        ParentAllowsDuplicateChildRule(lineage=(MatchRule(startswith="route-policy"),)),
    )
    per_line_sub_rules: tuple[PerLineSubRule, ...] = (
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
    )
    idempotent_commands_rules: tuple[IdempotentCommandsRule, ...] = (
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="router bgp"),
                MatchRule(startswith="vrf"),
                MatchRule(startswith="address-family"),
                MatchRule(startswith="additional-paths selection route-policy"),
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
                MatchRule(startswith="router bgp"),
                MatchRule(startswith="neighbor-group"),
                MatchRule(startswith="address-family"),
                MatchRule(startswith="soft-reconfiguration inbound"),
            ),
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="router bgp"),
                MatchRule(startswith="vrf"),
                MatchRule(startswith="neighbor"),
                MatchRule(startswith="address-family"),
                MatchRule(startswith="soft-reconfiguration inbound"),
            ),
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="router bgp"),
                MatchRule(startswith="vrf"),
                MatchRule(startswith="neighbor"),
                MatchRule(startswith="address-family"),
                MatchRule(startswith="maximum-prefix"),
            ),
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="router bgp"),
                MatchRule(startswith="vrf"),
                MatchRule(startswith="neighbor"),
                MatchRule(startswith="password"),
            ),
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="router bgp"),
                MatchRule(startswith="vrf"),
                MatchRule(startswith="neighbor"),
                MatchRule(startswith="description"),
            ),
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="router bgp"),
                MatchRule(startswith="neighbor"),
                MatchRule(startswith="description"),
            ),
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="router bgp"),
                MatchRule(startswith="neighbor"),
                MatchRule(startswith="password"),
            ),
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="router ospf"),
                MatchRule(startswith="area"),
                MatchRule(startswith="interface"),
                MatchRule(startswith="cost"),
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
                MatchRule(startswith="area"),
                MatchRule(startswith="message-digest-key"),
            ),
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="router ospf"),
                MatchRule(startswith="max-metric router-lsa"),
            ),
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(equals="l2vpn"),
                MatchRule(startswith="router-id"),
            ),
        ),
        IdempotentCommandsRule(
            lineage=(MatchRule(re_search="logging \\d+.\\d+.\\d+.\\d+ vrf MGMT"),),
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(equals="line default"),
                MatchRule(startswith="access-class ingress"),
            ),
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(equals="line default"),
                MatchRule(startswith="transport input"),
            ),
        ),
        IdempotentCommandsRule(
            lineage=(MatchRule(startswith="hostname"),),
        ),
        IdempotentCommandsRule(
            lineage=(MatchRule(startswith="logging source-interface"),)
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="interface"),
                MatchRule(startswith="ipv4 address"),
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
                MatchRule(equals="line console"),
                MatchRule(startswith="exec-timeout"),
            ),
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(equals="mpls ldp"),
                MatchRule(startswith="session protection duration"),
            ),
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(equals="mpls ldp"),
                MatchRule(startswith="igp sync delay"),
            ),
        ),
        IdempotentCommandsRule(
            lineage=(
                MatchRule(startswith="interface"),
                MatchRule(startswith="mtu"),
            ),
        ),
        IdempotentCommandsRule(
            lineage=(MatchRule(startswith="banner"),),
        ),
    )

    @staticmethod
    def idempotent_acl_check(
        config: HConfigChild, other_children: Iterable[HConfigChild]
    ) -> bool:
        if isinstance(config.parent, HConfigChild):
            acl = ("ipv4 access-list ", "ipv6 access-list ")
            if config.parent.text.startswith(acl):
                self_sn = config.text.split(" ", 1)[0]
                for other_child in other_children:
                    other_sn = other_child.text.split(" ", 1)[0]
                    if self_sn == other_sn:
                        return True
        return False

    @property
    def platform(self) -> Platform:
        return Platform.CISCO_XR
