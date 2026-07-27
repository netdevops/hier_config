from hier_config.models import (
    IdempotentCommandsRule,
    MatchRule,
    OrderingRule,
    PerLineSubRule,
    SectionalExitingRule,
)
from hier_config.platforms.driver_base import HConfigDriverBase, HConfigDriverRules
from hier_config.platforms.functions import expand_range
from hier_config.platforms.utils import split_vlan_id_lists
from hier_config.root import HConfig


def _split_interface_vlan_trunk_allowed(config: HConfig) -> None:
    """Split AOS-CX additive trunk VLAN lists into one VLAN per line.

    ``vlan trunk allowed`` is additive on AOS-CX rather than declarative, so
    modelling one VLAN per line lets standard remediation add missing VLANs with
    ``vlan trunk allowed <id>`` and remove extra ones with
    ``no vlan trunk allowed <id>`` -- matching how the device actually behaves.
    A spec that does not parse to at least one VLAN id is left untouched so the
    line is never deleted without a replacement.
    """
    for interface in config.get_children(startswith="interface "):
        for allowed in tuple(interface.get_children(startswith="vlan trunk allowed ")):
            words = allowed.text.split(maxsplit=3)
            if len(words) != 4:
                continue
            spec = words[3]
            if spec in {"all", "none"} or not any(
                separator in spec for separator in (",", "-")
            ):
                continue
            try:
                vlan_ids = expand_range(spec)
            except ValueError:
                continue
            if not vlan_ids:
                continue
            for vlan_id in vlan_ids:
                interface.add_child(
                    f"vlan trunk allowed {vlan_id}",
                    return_if_present=True,
                )
            allowed.delete()


class HConfigDriverArubaAOSCX(HConfigDriverBase):
    """Driver for Aruba AOS-CX switches.

    AOS-CX uses a Cisco IOS/EOS-like hierarchical CLI with ``no`` negation, so it
    reuses the standard tree model and remediation. The one platform-specific
    behaviour is that ``vlan trunk allowed`` is additive rather than declarative:
    the driver splits comma/range VLAN lists into one VLAN per line (both on load
    and in the intended config, via ``post_load_callbacks``) so remediation adds
    only the missing VLANs and negates only the removed ones. Unnamed collapsed
    VLAN headers like ``vlan 1,10`` are split into separate VLAN sections the same
    way. Platform enum: ``Platform.ARUBA_AOSCX``.
    """

    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        return HConfigDriverRules(
            sectional_exiting=[
                SectionalExitingRule(
                    match_rules=(
                        MatchRule(startswith="router bgp"),
                        MatchRule(startswith="address-family"),
                    ),
                    exit_text="exit-address-family",
                ),
            ],
            ordering=[
                # Create/modify top-level VLANs before the interfaces that
                # reference them: AOS-CX rejects `vlan trunk allowed <id>` for a
                # VLAN that does not yet exist.
                OrderingRule(
                    match_rules=(MatchRule(startswith="vlan "),),
                    weight=-10,
                ),
            ],
            per_line_sub=[
                PerLineSubRule(search=r"^\S+(?:\([^)]+\))?#.*", replace=""),
                PerLineSubRule(search=r"^Current configuration.*", replace=""),
                PerLineSubRule(search=r"^!.*", replace=""),
                PerLineSubRule(search=r"^#.*", replace=""),
                PerLineSubRule(search=r"^end$", replace=""),
                PerLineSubRule(search=r"^\s*exit$", replace=""),
                PerLineSubRule(search=r"^\s*exit-address-family$", replace=""),
            ],
            idempotent_commands=[
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="hostname "),),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="vlan "),
                        MatchRule(startswith="name "),
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
                        MatchRule(startswith="vlan access "),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface "),
                        MatchRule(startswith="vlan trunk native "),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface "),
                        MatchRule(startswith="vrf attach "),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface "),
                        MatchRule(startswith="mtu "),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface "),
                        MatchRule(startswith="speed "),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface "),
                        MatchRule(startswith="flow-control "),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="router bgp "),
                        MatchRule(startswith="bgp router-id "),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="router bgp "),
                        MatchRule(re_search=r"neighbor \S+ description "),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="router ospf "),
                        MatchRule(startswith="router-id "),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="snmp-server location "),),
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="snmp-server contact "),),
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="logging "),),
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="ntp vrf "),),
                ),
            ],
            post_load_callbacks=[
                split_vlan_id_lists,
                _split_interface_vlan_trunk_allowed,
            ],
        )
