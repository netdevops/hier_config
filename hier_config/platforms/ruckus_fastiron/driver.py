"""Driver for Ruckus/Brocade FastIron (ICX) switches."""

from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING

from hier_config.models import (
    IdempotentCommandsRule,
    MatchRule,
    NegationRule,
    NegationStrategy,
    OrderingRule,
    PerLineSubRule,
    SectionalOverwriteRule,
)
from hier_config.platforms.driver_base import HConfigDriverBase, HConfigDriverRules
from hier_config.platforms.ruckus_fastiron.functions import fastiron_expand_ports

if TYPE_CHECKING:
    from hier_config.root import HConfig

logger = getLogger(__name__)

_MEMBERSHIP_KEYWORDS = ("tagged", "untagged")


def _remove_stack_config(config: HConfig) -> None:
    """Drop stack provisioning from the tree so remediation never touches it.

    ``stack unit``/``stack enable``/``stack mac`` describe physical stack
    membership that is established once at build time.  Re-issuing any of it
    against a live stack can renumber or reload members, so the safe default is
    to treat it as out of scope rather than to diff it.
    """
    for child in tuple(config.get_children(startswith="stack ")):
        child.delete()


def _normalize_vlan_headers(config: HConfig) -> None:
    """Reduce a VLAN header to its id and carry the name as a child line.

    FastIron renders the name inline (`vlan 101 name USERS by port`) and renames
    by re-issuing that whole command, so the header is both the section selector
    and the rename command. Left as-is, a rename changes the header text and
    hier_config treats the section as brand new -- and marking the header
    idempotent instead breaks `future()`, which then keeps only the delta's
    children and drops the unchanged ones.

    Splitting the header into `vlan 101` plus a `vlan 101 name USERS by port`
    child keeps the section identity stable across a rename while leaving the
    rename itself a single remediation line. The child is a global command, so
    it applies correctly from inside the VLAN context where it is emitted.
    """
    for vlan in tuple(config.get_children(re_search=r"^vlan \d+\s+\S")):
        words = vlan.text.split()
        header = f"{words[0]} {words[1]}"

        if existing := config.get_child(equals=header):
            # A config that already selects the VLAN bare somewhere else --
            # a template emitting `vlan 101` and `vlan 101 name USERS by port`
            # as separate blocks, say -- would otherwise leave two sibling
            # sections for one VLAN and diff them against each other.
            existing.add_child(vlan.text, return_if_present=True)
            for child in vlan.children:
                existing.add_deep_copy_of(child, merged=True)
            vlan.delete()
            continue

        name_line = vlan.text
        vlan.text = header
        vlan.add_child(name_line, return_if_present=True)


def _expand_vlan_port_memberships(config: HConfig) -> None:
    """Split collapsed VLAN membership lines into one line per port.

    FastIron renders membership as a single collapsed line::

        vlan 101 name USERS by port
         tagged ethe 1/1/1 to 1/1/48 ethe 1/2/4

    Diffing that as one string means changing a single port rewrites the whole
    line, which momentarily removes every other port from the VLAN.  Expanding
    to one ``tagged ethe 1/1/1`` per port lets the diff engine emit exactly the
    ports that changed, and the expanded form is accepted verbatim by the CLI.

    A specification that does not parse cleanly is left untouched.
    """
    for vlan in config.get_children(startswith="vlan "):
        for membership in tuple(
            vlan.get_children(startswith=_MEMBERSHIP_KEYWORDS),
        ):
            words = membership.text.split()
            try:
                ports = fastiron_expand_ports(words[1:])
            except ValueError:
                logger.debug("leaving unparsable membership line %r", membership.text)
                continue
            if len(ports) == 1 and words[1] == "ethe" and len(words) == 3:
                continue
            for port in ports:
                vlan.add_child(f"{words[0]} ethe {port}", return_if_present=True)
            membership.delete()


def _expand_lag_port_membership(config: HConfig) -> None:
    """Split a collapsed LAG member list into one ``ports ethernet`` line each.

    FastIron accumulates repeated ``ports ethernet ...`` commands and renders
    the result collapsed (``ports ethernet 1/1/12 to 1/1/13``), so expanding at
    load time normalises both sides of the diff and lets a single member change
    show up as a single line instead of rewriting the whole member list.

    Note that the resulting ``no ports ethernet ...`` is only valid for a
    non-primary member and disables the port it removes; see the LAG note in
    the class docstring below.
    """
    for lag in config.get_children(startswith="lag "):
        for membership in tuple(lag.get_children(startswith="ports ")):
            words = membership.text.split()
            try:
                ports = fastiron_expand_ports(words[1:])
            except ValueError:
                logger.debug("leaving unparsable LAG member line %r", membership.text)
                continue
            if len(words) == 3 and words[1] == "ethernet":
                continue
            for port in ports:
                lag.add_child(f"ports ethernet {port}", return_if_present=True)
            membership.delete()


class HConfigDriverRuckusFastIron(HConfigDriverBase):
    """Driver for Ruckus/Brocade FastIron switches (ICX series).

    Developed and verified against FastIron 08.0.30 on ICX 6450 (``S`` switch
    image) and ICX 6650 (``R`` router image).  FastIron 08.0.95 and the 09.x/10.x
    releases moved several command families closer to Cisco IOS syntax and are
    not covered.

    Behaviour specific to this platform:

    * VLAN and LAG membership is normalised at load time to one line per port,
      because FastIron has no interface-level VLAN membership command and
      collapsed range lines cannot be diffed safely.
    * ``stack`` configuration is removed at load time and never remediated.
    * A VLAN header carries its name inline and doubles as the rename command,
      so it is normalised to ``vlan <id>`` with the name as a child. A LAG
      header is negated down to its name; a LAG cannot be renamed in place.
    * ``ip address`` is additive on an interface -- a second address in another
      subnet is added rather than replacing the first -- so addresses are
      diffed one line at a time and are not treated as idempotent.
    * IPv4 ACLs have no sequence numbers on this release, so an ACL whose body
      changed is negated and re-created rather than appended to.
    * A VLAN membership line naming one member of a deployed LAG moves the
      whole LAG, and the device renders the result as the full range. Diffs
      stay consistent, but a single remediation line can move several ports.
    * A deployed LAG refuses to give up or change its primary port, so a
      membership change is a stateful sequence (``no deploy`` -> ``primary-port``
      -> ``no ports`` -> ``enable ethe`` -> ``deploy``) that cannot be
      synthesised from a diff: ``deploy`` is identical on both sides, and the
      disabled state a removed member is left in is not visible in the running
      config. Removing a member is valid only for a non-primary port and
      disables it. LAG changes should be tagged for manual handling.

    Platform enum: ``Platform.RUCKUS_FASTIRON``.
    """

    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        return HConfigDriverRules(
            indentation=1,
            per_line_sub=[
                PerLineSubRule(search=r"^Current configuration:.*", replace=""),
                PerLineSubRule(search=r"^Building configuration.*", replace=""),
                PerLineSubRule(search=r"^\s*!.*", replace=""),
                PerLineSubRule(search=r"^ver \S+\s*$", replace=""),
                PerLineSubRule(search=r"^end\s*$", replace=""),
                # `show run` captured over SSH keeps the prompt echo
                PerLineSubRule(search=r"^\S*#.*", replace=""),
            ],
            negation=[
                NegationRule(
                    strategy=NegationStrategy.REPLACE,
                    match_rules=(
                        MatchRule(startswith="interface "),
                        MatchRule(startswith="port-name "),
                    ),
                    use="no port-name",
                ),
                NegationRule(
                    strategy=NegationStrategy.REGEX_SUB,
                    match_rules=(MatchRule(startswith="lag "),),
                    search=r'^no (lag (?:"[^"]*"|\S+)).*$',
                    replace=r"no \1",
                ),
            ],
            idempotent_commands=[
                # The normalised VLAN header line -- one per VLAN, last one
                # wins. This has to match every `vlan <id> ...` child, not just
                # the named form: an unnamed VLAN normalises to a `vlan 20 by
                # port` child, and naming it would otherwise negate that line.
                # `no vlan 20 by port` is a global command that deletes the
                # VLAN and every port in it.
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="vlan "),
                        MatchRule(re_search=r"^vlan \d+"),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="hostname "),)
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="ip default-gateway "),),
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="console timeout "),),
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="telnet timeout "),),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="errdisable recovery interval "),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="logging buffered "),),
                ),
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="clock timezone "),),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface "),
                        MatchRule(startswith="port-name "),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface "),
                        MatchRule(startswith="speed-duplex "),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface "),
                        MatchRule(startswith="voice-vlan "),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface "),
                        MatchRule(re_search=r"^ip helper-address (\d+) "),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface "),
                        MatchRule(startswith="port security"),
                        MatchRule(startswith="maximum "),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface "),
                        MatchRule(startswith="port security"),
                        MatchRule(startswith="violation "),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="interface "),
                        MatchRule(startswith="port security"),
                        MatchRule(startswith="age "),
                    ),
                ),
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="lag "),
                        MatchRule(startswith="primary-port "),
                    ),
                ),
                # a LAG member description is keyed by the member port
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith="lag "),
                        MatchRule(re_search=r"^port-name .+ (ethernet \S+)$"),
                    ),
                ),
            ],
            sectional_overwrite=[
                # no sequence numbers on 08.0.30: entries can only be appended,
                # so a changed ACL body has to be rebuilt to preserve order
                SectionalOverwriteRule(
                    match_rules=(MatchRule(startswith="ip access-list "),),
                ),
            ],
            ordering=[
                # `no interface ethernet 1/1/1` clears the interface block --
                # port-name, port security, trust, dual-mode -- and the port
                # then vanishes from `show running-config` because FastIron
                # omits default interfaces. VLAN membership is unaffected: it
                # lives in the `vlan` blocks. Run resets first so one cannot
                # clobber interface settings applied earlier in the same push.
                OrderingRule(
                    match_rules=(MatchRule(startswith="no interface ethernet "),),
                    weight=-30,
                ),
                # A deployed LAG rejects membership and primary-port changes,
                # so if an un-deploy/re-deploy pair is present it has to wrap
                # everything else in the section. hier_config cannot invent the
                # pair when `deploy` is unchanged on both sides -- see the LAG
                # note in docs/user/drivers.md.
                OrderingRule(
                    match_rules=(
                        MatchRule(startswith="lag "),
                        MatchRule(equals="no deploy"),
                    ),
                    weight=-50,
                ),
                OrderingRule(
                    match_rules=(
                        MatchRule(startswith="lag "),
                        MatchRule(equals="deploy"),
                    ),
                    weight=50,
                ),
                # Inside a LAG: add members, then move the primary onto one of
                # them, then drop the old members. A primary port cannot be
                # removed, so it has to be demoted first.
                OrderingRule(
                    match_rules=(
                        MatchRule(startswith="lag "),
                        MatchRule(startswith="ports ethernet "),
                    ),
                    weight=-40,
                ),
                OrderingRule(
                    match_rules=(
                        MatchRule(startswith="lag "),
                        MatchRule(startswith="primary-port "),
                    ),
                    weight=-30,
                ),
                OrderingRule(
                    match_rules=(
                        MatchRule(startswith="lag "),
                        MatchRule(startswith="no ports ethernet "),
                    ),
                    weight=-20,
                ),
                # A port must leave its old untagged VLAN before it can join a
                # new one, otherwise the device answers
                # "port ethe 1/1/1 are not member of default vlan".
                OrderingRule(
                    match_rules=(
                        MatchRule(startswith="vlan "),
                        MatchRule(startswith="no untagged "),
                    ),
                    weight=-20,
                ),
                # A `mac filter-group` binding must be removed before the
                # filter it points at: FastIron refuses to delete a filter
                # that is still bound. ACLs sort the other way -- see the
                # trade-off note on the `ip access-list` weights below.
                OrderingRule(
                    match_rules=(
                        MatchRule(startswith="interface "),
                        MatchRule(startswith="no mac filter-group "),
                    ),
                    weight=-20,
                ),
                OrderingRule(
                    match_rules=(
                        MatchRule(startswith="interface "),
                        MatchRule(startswith="no ip access-group "),
                    ),
                    weight=-20,
                ),
                OrderingRule(
                    match_rules=(MatchRule(startswith="no mac filter "),),
                    weight=20,
                ),
                # A filter has to exist before an interface names it:
                # `mac filter-group 32` against an undefined filter is refused
                # outright ("filter 32 is not configured in the global table").
                # Without this rule the order would ride on whichever line the
                # intended config happens to declare first.
                OrderingRule(
                    match_rules=(MatchRule(startswith="mac filter "),),
                    weight=-25,
                ),
                # ACLs go first, ahead of the interfaces that bind them, so a
                # newly created ACL exists before an `ip access-group` points at
                # it. An interface fails open while its ACL is missing, so the
                # alternative would leave the interface unfiltered for the rest
                # of the push. The negation stays ahead of the body so that a
                # rebuild re-creates the ACL instead of deleting it.
                #
                # The trade-off: an ACL that is being deleted is removed before
                # the interface unbinds it, leaving a dangling `ip access-group`
                # for the rest of the push. That is transient and self-resolving
                # -- unlike `mac filter`, FastIron does not refuse the removal --
                # whereas an unfiltered interface is not.
                OrderingRule(
                    match_rules=(MatchRule(startswith="no ip access-list "),),
                    weight=-30,
                ),
                OrderingRule(
                    match_rules=(MatchRule(startswith="ip access-list "),),
                    weight=-25,
                ),
                # Removing a VLAN also removes every port membership in it, so
                # do it after the memberships have been moved elsewhere.
                OrderingRule(
                    match_rules=(MatchRule(re_search=r"^no vlan \d+$"),),
                    weight=10,
                ),
            ],
            post_load_callbacks=[
                _remove_stack_config,
                _normalize_vlan_headers,
                _expand_vlan_port_memberships,
                _expand_lag_port_membership,
            ],
        )
