from logging import getLogger

from hier_config.models import (
    IdempotentCommandsRule,
    MatchRule,
    NegationRule,
    NegationStrategy,
    OrderingRule,
    ParentAllowsDuplicateChildRule,
    PerLineSubRule,
    SectionalExitingRule,
)
from hier_config.platforms.cisco_ios.view import HConfigViewCiscoIOS
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


def _expand_vlan_id_list(spec: str) -> list[int]:
    """Expand a VLAN id spec like ``69,381`` or ``10-12,20`` into a list of ints."""
    ids: list[int] = []
    for part in spec.split(","):
        if "-" in part:
            low, high = part.split("-")
            ids.extend(range(int(low), int(high) + 1))
        else:
            ids.append(int(part))
    return ids


def _split_vlan_id_lists(config: HConfig) -> None:
    """Split ``vlan 69,381`` / ``vlan 10-12`` into a separate ``vlan <id>`` block per VLAN.

    IOS can render unnamed VLANs collapsed onto a single comma/range line
    (depending on how they were created; named VLANs always get their own block).
    Splitting such a line at load time lets the diff engine match VLANs
    block-to-block against an intended config that lists them separately,
    avoiding a destructive ``no vlan 69,381``.
    """
    for vlan in tuple(config.get_children(re_search=r"^vlan \d[\d,\-]*$")):
        spec = vlan.text.split(maxsplit=1)[1]
        if not any(separator in spec for separator in (",", "-")):
            continue
        for vlan_id in _expand_vlan_id_list(spec):
            config.add_child(f"vlan {vlan_id}")
        vlan.delete()


class HConfigDriverCiscoIOS(HConfigDriverBase):
    """Driver for Cisco IOS and IOS-XE.

    Includes post-load callbacks that normalise IPv4/IPv6 ACL sequence numbers,
    remove IPv4 ACL remarks, and split collapsed comma/range VLAN id lists into
    one block per VLAN, ensuring stable diffs across device snapshots.  Also
    handles BGP template peer-policy/peer-session sectional exiting and
    ``logging console`` negation-with replacement.  Platform enum:
    ``Platform.CISCO_IOS``.
    """

    view_class = HConfigViewCiscoIOS

    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        return HConfigDriverRules(
            negation=[
                NegationRule(
                    strategy=NegationStrategy.REPLACE,
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
                _split_vlan_id_lists,
            ],
        )
