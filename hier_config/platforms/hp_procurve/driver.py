import re
from collections.abc import Iterable
from typing import Optional

from hier_config.child import HConfigChild
from hier_config.models import (
    IdempotentCommandsRule,
    MatchRule,
    NegationDefaultWithRule,
    OrderingRule,
    PerLineSubRule,
)
from hier_config.platforms.driver_base import HConfigDriverBase, HConfigDriverRules
from hier_config.platforms.hp_procurve.functions import hp_procurve_expand_range
from hier_config.root import HConfig


def _fixup_hp_procurve_aaa_port_access_fixup(config: HConfig) -> None:
    """Expands the interface ranges present in aaa port-access commands.

    aaa port-access authenticator 1/15-1/20,1/26-1/40,2/14-2/20,2/25-2/28,2/30-2/44,3/8-3/44,4/1-4/2,4/8-4/44,5/1-5/2,5/8-5/15,5/17-5/28,5/30-5/44
    aaa port-access mac-based 1/15-1/20,1/26-1/40,2/14-2/20,2/25-2/28,2/30-2/44,3/8-3/44,4/1-4/2,4/8-4/44,5/1-5/2,5/8-5/28,5/30-5/44.

    to
    aaa port-access authenticator 1/15
    aaa port-access authenticator 1/16
    ...
    """
    for aaa_port_access in tuple(
        config.get_children(
            re_search=r"^aaa port-access (authenticator|mac-based) [0-9,/\-Ttrk]+$",
        ),
    ):
        words = aaa_port_access.text.split()
        if not any(c in words[3] for c in ("-", ",")):
            continue
        for interface_name in hp_procurve_expand_range(words[3]):
            config.add_child(f"aaa port-access {words[2]} {interface_name}")
        aaa_port_access.delete()


def _fixup_hp_procurve_vlan(config: HConfig) -> None:
    """Move native/tagged vlan config to the interface config for easier modeling and remediation.

    vlan 1
       no untagged 1/2-1/22,1/26-1/44,2/2-2/21,2/26-2/44
    vlan 80
       untagged 2/43-2/44,3/43-3/44,4/43-4/44,5/29,5/43-5/44
       tagged 1/23,2/23,Trk1.

    to

    interface 2/43
       untagged vlan 80
    interface 1/23
       tagged vlan 80
       tagged vlan 90
       untagged vlan 10
    ...

    Also, this effectively creates TrkX interfaces in the running config
    """
    for vlan in tuple(config.get_children(startswith="vlan ")):
        vlan_id = vlan.text.split()[1]
        if untagged_interfaces := vlan.get_child(startswith="untagged "):
            untagged_interface_names = hp_procurve_expand_range(
                untagged_interfaces.text.split()[1],
            )
            for untagged_interface_name in sorted(untagged_interface_names):
                config.add_children_deep(
                    (
                        f"interface {untagged_interface_name}",
                        f"untagged vlan {vlan_id}",
                    ),
                )
            untagged_interfaces.delete()

        if tagged_interfaces := vlan.get_child(startswith="tagged "):
            tagged_interface_names = hp_procurve_expand_range(
                tagged_interfaces.text.split()[1],
            )
            for tagged_interface_name in sorted(tagged_interface_names):
                config.add_children_deep(
                    (f"interface {tagged_interface_name}", f"tagged vlan {vlan_id}"),
                )
            tagged_interfaces.delete()

        if no_untagged_interfaces := vlan.get_child(startswith="no untagged "):
            no_untagged_interfaces.delete()


def _fixup_hp_procurve_device_profile(config: HConfig) -> None:
    """Separates the device-profile tagged-vlans onto individual lines.

    device-profile name "phone"
      tagged-vlan 10,20

    to

    device-profile name "phone"
      tagged-vlan 10
      tagged-vlan 20
    """
    for device_profile in config.get_children(startswith="device-profile name "):
        if tagged_vlan := device_profile.get_child(startswith="tagged-vlan "):
            words = tagged_vlan.text.split()
            if not any(c in words[1] for c in ("-", ",")):
                continue
            for vlan in sorted(hp_procurve_expand_range(words[1])):
                device_profile.add_child(f"tagged-vlan {vlan}")
            tagged_vlan.delete()


class HConfigDriverHPProcurve(HConfigDriverBase):
    def idempotent_for(
        self,
        config: HConfigChild,
        other_children: Iterable[HConfigChild],
    ) -> Optional[HConfigChild]:
        if result := super().idempotent_for(config, other_children):
            return result

        if config.parent is config.root:
            rules = (
                (
                    r"^aaa port-access authenticator \S+ (tx-period|supplicant-timeout) \d+$",
                    5,
                ),
                (r"^aaa port-access \S+ auth-(priority|order) ", 4),
                (r"^aaa port-access authenticator \S+ client-limit \d+$", 5),
                (r"^aaa port-access mac-based \S+ (addr-limit|logoff-period) \d+$", 5),
                (r"^aaa port-access \S+ critical-auth user-role ", 5),
                (r"^radius-server host \S+ encrypted-key \S+$", 4),
            )
            for expression, stop_index in rules:
                if result := self._idempotent_for_helper(
                    expression,
                    stop_index,
                    config,
                    other_children,
                ):
                    return result

        return None

    @staticmethod
    def _idempotent_for_helper(
        expression: str,
        end_index: int,
        config: HConfigChild,
        other_children: Iterable[HConfigChild],
    ) -> Optional[HConfigChild]:
        if re.search(expression, config.text):
            words = config.text.split()
            startswith = " ".join(words[:end_index])
            for other_child in other_children:
                if other_child.text.startswith(startswith):
                    return other_child
        return None

    def negate_with(self, config: HConfigChild) -> Optional[str]:
        result = super().negate_with(config)
        if isinstance(result, str):
            return result

        if config.parent is not config.root:
            return None

        rules = (
            (
                r"^aaa port-access authenticator \S+ (tx-period|supplicant-timeout) \d+$",
                5,
                "",
                "30",
            ),
            (r"^aaa port-access authenticator \S+ client-limit \d+$", 5, "no", ""),
            (r"^aaa port-access mac-based \S+ addr-limit \d+$", 5, "", "1"),
            (r"^aaa port-access mac-based \S+ logoff-period \d+$", 5, "", "300"),
            (r"^aaa port-access \S+ critical-auth user-role ", 5, "no", ""),
            (r"^tacacs-server host \S+ ", 3, "no", ""),
            (r"^radius-server host \S+ time-window \d+$", 4, "", "300"),
            (
                r"^radius-server host \S+ time-window plus-or-minus-time-window$",
                4,
                "",
                "positive-time-window",
            ),
            (r"^radius-server host \S+ encrypted-key \S+$", 3, "no", ""),
        )
        for expression, end_index, prepend, append in rules:
            if result := self._negation_negate_with_helper(
                expression,
                end_index,
                prepend,
                append,
                config,
            ):
                return result
        return None

    @staticmethod
    def _negation_negate_with_helper(
        expression: str,
        end_index: int,
        prepend: str,
        append: str,
        config: HConfigChild,
    ) -> Optional[str]:
        if re.search(expression, config.text):
            words = config.text.split()
            return " ".join([prepend] + words[:end_index] + [append]).strip()
        return None

    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        return HConfigDriverRules(
            negate_with=[
                NegationDefaultWithRule(
                    match_rules=(
                        MatchRule(startswith="interface "),
                        MatchRule(equals="disable"),
                    ),
                    use="enable",
                ),
                NegationDefaultWithRule(
                    match_rules=(
                        MatchRule(startswith="interface "),
                        MatchRule(startswith="name "),
                    ),
                    use="no name",
                ),
            ],
            per_line_sub=[
                PerLineSubRule(search=r"^\s*[#!].*", replace=""),
                PerLineSubRule(search=r"^; .*", replace=""),
                PerLineSubRule(search=r"^Running configuration:*", replace=""),
            ],
            idempotent_commands=[
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(
                            startswith="aaa authentication port-access eap-radius"
                        ),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="aaa accounting update periodic "),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface "),
                        MatchRule(startswith="untagged vlan "),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface "),
                        MatchRule(startswith="name "),
                    ),
                ),
            ],
            ordering=[
                # no aaa port-access {{ interface_name }} auth-priority  -- needs to happen before auth-order
                OrderingRule(
                    match_rules=(
                        MatchRule(re_search=r"^no aaa port-access \S+ auth-priority"),
                    ),
                    weight=-10,
                ),
                # `no aaa port-access authenticator 5/43` needs to come before other similar commands
                # e.g. `no aaa port-access authenticator 5/43 client-limit`
                OrderingRule(
                    match_rules=(
                        MatchRule(re_search=r"^no aaa port-access authenticator \S+$"),
                    ),
                    weight=-10,
                ),
                # `aaa server-group radius "ise" host 172.16.1.1` should be defined after reference
                OrderingRule(
                    match_rules=(
                        MatchRule(re_search=r"^aaa server-group radius \S+ host "),
                    ),
                    weight=10,
                ),
                # Need to add vlans before removing to prevent accidentally adding untagged vlan 1
                OrderingRule(
                    match_rules=(
                        MatchRule(startswith="interface "),
                        MatchRule(startswith=("no tagged vlan ", "no untagged vlan ")),
                    ),
                    weight=10,
                ),
                OrderingRule(
                    match_rules=(MatchRule(startswith="no tacacs-server "),),
                    weight=10,
                ),
                # In case a server is a member of a group, `no radius-server host 172.16.1.1 dyn-authorization` cannot
                # be used before adding another server to that group
                OrderingRule(
                    match_rules=(
                        MatchRule(
                            re_search=r"^no radius-server host \S+ dyn-authorization$"
                        ),
                    ),
                    weight=15,
                ),
                # Cannot use `no aaa server-group radius "ise" host 172.16.1.1` after removing that host
                OrderingRule(
                    match_rules=(
                        MatchRule(re_search=r"^no aaa server-group radius \S+ host "),
                    ),
                    weight=20,
                ),
                # `no radius-server host 172.16.1.1` should be called last (cannot leave a server group empty)
                OrderingRule(
                    match_rules=(MatchRule(re_search=r"^no radius-server host \S+$"),),
                    weight=30,
                ),
            ],
            post_load_callbacks=[
                _fixup_hp_procurve_aaa_port_access_fixup,
                _fixup_hp_procurve_device_profile,
                _fixup_hp_procurve_vlan,
            ],
        )
