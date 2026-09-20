from hier_config.models import Platform
from hier_config.platforms.cisco_ios.view import HConfigViewCiscoIOS
from hier_config.platforms.driver_base import (
    HConfigDriverBase,
    HConfigDriverRules,
    core_owned,
    load_platform_rules,
)
from hier_config.platforms.utils import split_vlan_id_lists
from hier_config.root import HConfig


@core_owned
def remove_ipv6_acl_sequence_numbers(config: HConfig) -> None:
    """If there are sequence numbers in the IPv6 ACL, remove them."""
    for acl in config.get_children(startswith="ipv6 access-list "):
        for entry in acl.children:
            if entry.text.startswith("sequence"):
                entry.text = " ".join(entry.text.split()[2:])


@core_owned
def remove_ipv4_acl_remarks(config: HConfig) -> None:
    """Remove remark lines from IPv4 ACLs so they do not participate in diffs."""
    for acl in config.get_children(startswith="ip access-list "):
        for entry in tuple(acl.children):
            if entry.text.startswith("remark"):
                entry.delete()


@core_owned
def add_acl_sequence_numbers(config: HConfig) -> None:
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
    """Driver for Cisco IOS and IOS XE.

    Includes post-load callbacks that normalise IPv4/IPv6 ACL sequence numbers,
    remove IPv4 ACL remarks, and split collapsed comma/range VLAN id lists into
    one block per VLAN, ensuring stable diffs across device snapshots.  Also
    handles BGP template peer-policy/peer-session sectional exiting and
    logging console negation-with replacement.  Platform enum:
    Platform.CISCO_IOS.
    """

    platform = Platform.CISCO_IOS
    view_class = HConfigViewCiscoIOS

    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        """Load the canonical rules and attach this platform's post-load callbacks.

        The callbacks are declared here so custom drivers can discover and
        reuse them (#286); the Rust core applies them during parsing, so
        `hier_config.constructors` skips the redundant Python pass.
        """
        return load_platform_rules(
            Platform.CISCO_IOS,
            post_load_callbacks=[
                remove_ipv6_acl_sequence_numbers,
                remove_ipv4_acl_remarks,
                add_acl_sequence_numbers,
                split_vlan_id_lists,
            ],
        )
