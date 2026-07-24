from hier_config.child import HConfigChild
from hier_config.models import (
    IdempotentCommandsRule,
    MatchRule,
    PerLineSubRule,
    SectionalExitingRule,
)
from hier_config.platforms.driver_base import HConfigDriverBase, HConfigDriverRules
from hier_config.root import HConfig


def _vlan_id_list(vlan_ids: list[int]) -> str:
    """Collapse VLAN IDs into a compact comma/range string."""
    if not vlan_ids:
        return ""

    ranges: list[str] = []
    start = previous = vlan_ids[0]
    for vlan_id in vlan_ids[1:]:
        if vlan_id == previous + 1:
            previous = vlan_id
            continue
        ranges.append(str(start) if start == previous else f"{start}-{previous}")
        start = previous = vlan_id
    ranges.append(str(start) if start == previous else f"{start}-{previous}")
    return ",".join(ranges)


def _expand_vlan_id_list(spec: str) -> list[str]:
    """Expand a VLAN id spec like ``10,20`` or ``10-12,20``."""
    vlan_ids: list[str] = []
    for raw_part in spec.split(","):
        part = raw_part.strip()
        if not part:
            continue
        if "-" not in part:
            vlan_ids.append(part)
            continue
        low, high = part.split("-", maxsplit=1)
        if not low.isdecimal() or not high.isdecimal():
            vlan_ids.append(part)
            continue
        vlan_ids.extend(str(vlan_id) for vlan_id in range(int(low), int(high) + 1))
    return vlan_ids


def _split_vlan_id_lists(config: HConfig) -> None:
    """Split Aruba collapsed unnamed VLAN headers into one section per VLAN."""
    for vlan in tuple(config.get_children(re_search=r"^vlan \d[\d,\-]*$")):
        spec = vlan.text.split(maxsplit=1)[1]
        if not any(separator in spec for separator in (",", "-")):
            continue
        expanded = _expand_vlan_id_list(spec)
        if not all(vlan_id.isdecimal() for vlan_id in expanded):
            continue
        for vlan_id in expanded:
            config.add_child(f"vlan {vlan_id}", return_if_present=True)
        vlan.delete()


def _split_interface_vlan_trunk_allowed(config: HConfig) -> None:
    """Split AOS-CX additive trunk VLAN lists so remediation adds only missing VLANs."""
    for interface in config.get_children(startswith="interface "):
        for allowed in tuple(interface.get_children(startswith="vlan trunk allowed ")):
            words = allowed.text.split(maxsplit=3)
            if len(words) != 4:
                continue
            spec = words[3]
            if spec in {"all", "none"}:
                continue
            expanded = _expand_vlan_id_list(spec)
            if expanded == [spec]:
                continue
            for vlan_id in expanded:
                interface.add_child(
                    f"vlan trunk allowed {vlan_id}",
                    return_if_present=True,
                )
            allowed.delete()


def _explicit_target_no_child(
    target_parent: HConfig | HConfigChild | None,
    child_text: str,
) -> bool:
    """Return True when a target partial section explicitly asks for a no command."""
    return bool(target_parent and target_parent.get_child(equals=child_text))


def _explicit_source_no_counterpart(
    source_parent: HConfig | HConfigChild | None,
    child_text: str,
) -> bool:
    """Return True when rollback should restore an explicitly negated child."""
    return bool(source_parent and source_parent.get_child(equals=f"no {child_text}"))


def _source_has_rollback_counterpart(
    source_parent: HConfig | HConfigChild | None,
    child_text: str,
) -> bool:
    """Return True when rollback should negate a child added by the source."""
    if source_parent is None:
        return False
    if child_text.startswith("no "):
        return bool(source_parent.get_child(equals=child_text[3:]))
    return _explicit_source_no_counterpart(source_parent, child_text)


def _prune_partial_section_child(
    child: HConfigChild,
    source_section: HConfig | HConfigChild | None,
    target_section: HConfig | HConfigChild | None,
    *,
    workflow: str,
) -> None:
    """Delete a partial-section child the workflow should not emit."""
    if workflow == "remediation":
        remove = (
            child.text.startswith("no ") or child.text == "shutdown"
        ) and not _explicit_target_no_child(target_section, child.text)
        if remove:
            child.delete()
        return
    if not _source_has_rollback_counterpart(source_section, child.text):
        child.delete()


def _prune_partial_section_workflow(
    config: HConfig,
    source_config: HConfig,
    target_config: HConfig,
    *,
    workflow: str,
) -> None:
    """Treat AOS-CX EVPN/VXLAN as partial intended sections in workflows."""
    section_selectors = (
        {"equals": "evpn"},
        {"startswith": "interface vxlan "},
    )
    for selector in section_selectors:
        for section in tuple(config.get_children(**selector)):
            source_section = source_config.get_child(equals=section.text)
            target_section = target_config.get_child(equals=section.text)
            for child in tuple(section.children):
                _prune_partial_section_child(
                    child,
                    source_section,
                    target_section,
                    workflow=workflow,
                )
            if not section.children:
                section.delete()


class HConfigDriverArubaAOSCX(HConfigDriverBase):
    """Driver for Aruba AOS-CX switches.

    AOS-CX uses a Cisco/EOS-like hierarchical CLI with ``no`` negation. Trunk
    allowed VLAN commands are additive, so they are normalized into one VLAN per
    line and treated as an additive command family. Unnamed collapsed VLAN
    section headers like ``vlan 1,10`` are split into separate VLAN sections.
    Platform enum: ``Platform.ARUBA_AOSCX``.
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
                _split_vlan_id_lists,
                _split_interface_vlan_trunk_allowed,
            ],
        )

    def workflow_config_post_process(  # ruff:ignore[no-self-use]
        self,
        config: HConfig,
        source_config: HConfig,
        target_config: HConfig,
        workflow: str = "remediation",
    ) -> HConfig:
        """Collapse additive trunk VLAN workflow lines using target VLAN lists."""
        _prune_partial_section_workflow(
            config,
            source_config,
            target_config,
            workflow=workflow,
        )

        for interface in config.get_children(startswith="interface "):
            allowed_children = tuple(
                interface.get_children(
                    re_search=r"^vlan trunk allowed \d+$",
                ),
            )
            if not allowed_children:
                continue

            target_interface = target_config.get_child(equals=interface.text)
            target_allowed_children = (
                ()
                if target_interface is None
                else tuple(
                    target_interface.get_children(
                        re_search=r"^vlan trunk allowed \d+$",
                    ),
                )
            )
            children_to_collapse = target_allowed_children or allowed_children
            vlan_ids = sorted(
                int(child.text.split()[3]) for child in children_to_collapse
            )
            comments: set[str] = set()
            tags: set[str] = set()
            new_in_config = False
            for child in allowed_children:
                comments.update(child.comments)
                tags.update(child.tags)
                new_in_config = new_in_config or child.new_in_config
                child.delete()

            collapsed = interface.add_child(
                f"vlan trunk allowed {_vlan_id_list(vlan_ids)}"
            )
            collapsed.comments.update(comments)
            collapsed.tags = frozenset(tags)
            collapsed.new_in_config = new_in_config

        return config

    def future_config_post_process(  # ruff:ignore[no-self-use]
        self, config: HConfig
    ) -> HConfig:
        """Normalize simulated future configs back to the internal AOS-CX model."""
        _split_vlan_id_lists(config)
        _split_interface_vlan_trunk_allowed(config)
        return config
