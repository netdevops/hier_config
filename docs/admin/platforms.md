# Supported Platforms

This page describes each built-in platform driver: its behaviors, quirks, and any platform-specific handling that affects remediation. Read it to understand what hier_config does for your platform out of the box — and what you may want to [customize](customizing-rules.md).

## What is a driver?

A driver encodes all operating-system-specific behavior for one network platform. It acts as a framework that encapsulates the rules, transformations, and behaviors required to process and normalize device configurations:

1. **[Negation handling](../glossary.md#negation-rule)**: ensures commands are properly negated or reset according to the operating system's syntax and behavior.
2. **[Sectional exiting rules](../glossary.md#sectional-exiting)**: defines how to navigate in and out of hierarchical configuration sections so remediation output keeps its structural integrity.
3. **Command ordering**: establishes the sequence in which commands should be applied based on dependencies, preventing conflicts during deployment.
4. **Line substitutions**: cleans up unnecessary or temporary data in configurations, such as metadata, system-generated comments, or timestamp banners.
5. **[Idempotency management](../glossary.md#idempotent-command)**: identifies last-value-wins commands so remediation overwrites rather than negate-and-re-add.
6. **Post-processing callbacks**: performs additional adjustments after parsing, such as refining access control lists or splitting collapsed VLAN lists.

By defining these rules in a reusable way, a driver lets hier_config adapt to different operating systems while keeping a consistent interface. Drivers are selected implicitly when you pass a `Platform` to `HConfig.from_text()`, or explicitly:

```python
from hier_config import get_hconfig_driver, Platform

driver = get_hconfig_driver(Platform.CISCO_IOS)
```

## Built-in platforms

| Platform | `Platform` enum | Status |
|----------|-----------------|--------|
| Cisco IOS | `Platform.CISCO_IOS` | Fully supported |
| Arista EOS | `Platform.ARISTA_EOS` | Fully supported |
| Cisco IOS XR | `Platform.CISCO_XR` | Fully supported |
| Cisco NX-OS | `Platform.CISCO_NXOS` | Fully supported |
| Fortinet FortiOS | `Platform.FORTINET_FORTIOS` | Fully supported |
| HP ProCurve (Aruba AOSS) | `Platform.HP_PROCURVE` | Fully supported |
| HP Comware5 / H3C | `Platform.HP_COMWARE5` | Fully supported |
| Huawei VRP | `Platform.HUAWEI_VRP` | Fully supported |
| Aruba AOS-CX | `Platform.ARUBA_AOSCX` | Experimental |
| Juniper JunOS | `Platform.JUNIPER_JUNOS` | Experimental |
| Nokia SRL | `Platform.NOKIA_SRL` | Experimental |
| Ruckus/Brocade FastIron (ICX) | `Platform.RUCKUS_FASTIRON` | Experimental |
| VyOS | `Platform.VYOS` | Experimental |
| Generic | `Platform.GENERIC` | Base for custom drivers |

Every platform is used the same way — parse both configs with `HConfig.from_text(Platform.X, text)` and feed them to `WorkflowRemediation` (see [Getting Started](../user/getting-started.md)). The sections below describe what each driver does differently.

---

### Cisco IOS

Cisco IOS is hier_config's primary reference platform and the most thoroughly tested driver. The `CISCO_IOS` driver ships with a comprehensive set of rules covering common IOS configuration patterns:

- **[Idempotent commands](../glossary.md#idempotent-command)**: `hostname`, `ip address`, `ip access-group`, `description`, `banner`, and many others are treated as last-write-wins — applying the same command twice leaves only the final value in place.
- **Negation**: standard `no ` [negation prefix](../glossary.md#negation-prefix). Several commands (such as `logging console`) use REPLACE-strategy [`NegationRule`](../glossary.md#negation-rule) overrides to emit a specific reset form.
- **[Sectional exiting](../glossary.md#sectional-exiting)**: BGP `peer-policy` and `peer-session` blocks require `exit-peer-policy` and `exit-peer-session` closure tokens.
- **Per-line substitutions**: strips `Building configuration…` banners and timestamp headers.
- **ACL normalization callbacks**: post-load callbacks remove IPv6 ACL sequence numbers, strip IPv4 ACL remarks, and add IPv4 ACL sequence numbers so entries diff cleanly. (See [Customizing Driver Rules](customizing-rules.md#customizing-post-load-callbacks) if you need to keep ACL remarks.)
- **VLAN id list splitting**: IOS can render unnamed VLANs collapsed onto a single comma/range line (e.g. `vlan 69,381`, `vlan 10-12`), depending on how the VLANs were created — named VLANs always get their own block, and the grouping shifts as VLANs are named or unnamed. When such a collapsed line is present, a post-load callback splits it into one `vlan <id>` block each so the VLANs diff block-to-block against an intended config that lists them separately — avoiding a destructive `no vlan 69,381`.

---

### Arista EOS

Arista EOS uses a Cisco IOS-like hierarchical CLI, so the `ARISTA_EOS` driver closely mirrors `CISCO_IOS`:

- BGP peer-policy and peer-session blocks require `exit-peer-policy` and `exit-peer-session` closure tokens (same as IOS).
- Broad idempotency rules cover the most common EOS configuration patterns.
- [Negation prefix](../glossary.md#negation-prefix): `no ` (default).

---

### Cisco IOS XR

Cisco IOS XR uses a commit-based configuration model with several syntax differences from classic IOS:

- **[Sectional overwrite no-negate](../glossary.md#sectional-overwrite-no-negate)**: `prefix-set`, `route-policy`, and similar blocks are replaced wholesale rather than line-by-line, because IOS XR does not support partial modification of these objects.
- **[Indent adjust](../glossary.md#indent-adjust)**: `template` blocks use a different indentation depth; the driver adjusts the tree depth between `template` and `end-template` markers.
- **[Sectional exiting](../glossary.md#sectional-exiting)**: route-policy blocks close with `end-policy`; prefix-set and community-set blocks close with `end-set`; template blocks close with `end-template`; group blocks close with `end-group`. All `end-*` exit text is rendered at the parent indentation level (`exit_text_parent_level=True`).
- ACL sequence numbers are preserved for correct ordered access-list handling.

---

### Cisco NX-OS

Cisco NX-OS is similar to IOS in CLI structure but has NX-OS-specific idempotency requirements:

- **TCAM region idempotency**: `hardware access-list tcam region` commands are treated as last-write-wins.
- Some BGP commands use different negation forms; the driver includes REPLACE-strategy `NegationRule` entries for affected commands.
- [Negation prefix](../glossary.md#negation-prefix): `no ` (default).

---

### Fortinet FortiOS

Fortinet firewalls model their CLI around `config` and `edit` blocks that are terminated with `next` and `end`. The `FORTINET_FORTIOS` driver captures those patterns and makes sure remediation output keeps the indentation and closure FortiOS expects. Highlights include:

- Preserves the `set`/`unset` pairing by swapping declarations and negations automatically when hier_config determines a change is required.
- Treats sibling `config` blocks as duplicates when appropriate so that multiple objects such as policies or firewall addresses can be compared in a stable order.
- Normalizes bare `next` and `end` tokens into indented versions to match the format FortiOS emits on the device.
- Overrides idempotency matching to require that the same object name exists on both sides before a command is considered already present.

---

### HP ProCurve (Aruba AOSS)

HP ProCurve switches (sold as Aruba switches after the HP/Aruba merger) use a Cisco-style hierarchical CLI with `no` as the negation prefix. The `HP_PROCURVE` driver adds several post-load normalization callbacks that simplify diffing:

- **VLAN membership** — moves `untagged`/`tagged` directives out of `vlan <id>` blocks and into per-interface blocks, matching the mental model that operators typically use when writing intended configs.
- **Port-access range expansion** — expands compact port ranges like `aaa port-access authenticator 1/15-1/20,1/26-1/40` into individual interface lines so that hier_config can apply idempotency rules per port.
- **Device-profile tagged-VLAN splitting** — splits comma-separated VLAN lists in `device-profile` blocks into one command per VLAN.

The driver also extends idempotency and negation-replacement logic to handle ProCurve-specific command patterns such as `aaa port-access`, `radius-server`, and `tacacs-server` with variable-length key fields.

---

### HP Comware5 / H3C

HP Comware5 (and the compatible H3C platform) uses `undo` as the negation prefix rather than `no`. The `HP_COMWARE5` driver overrides `negation_prefix` accordingly. No additional platform-specific rules are configured by default; extend the driver if your environment requires them (see [Customizing Driver Rules](customizing-rules.md)).

---

### Huawei VRP

Huawei VRP (Versatile Routing Platform) uses `undo` as the negation prefix rather than `no`. The `HUAWEI_VRP` driver customizes negation handling for several command families:

- **[Negation prefix](../glossary.md#negation-prefix)**: `undo ` (replaces `no `).
- **Smart negation**: `description` and `alias` commands are negated without their argument; `remark` commands strip the remark text; `snmp-agent community` commands truncate to the community name.
- **Sectional exiting**: section exit text `exit` is translated to `quit` as VRP requires.
- **Per-line substitutions**: strips `#` and `!` comment lines during parsing.

---

### Aruba AOS-CX

Aruba AOS-CX uses a Cisco IOS/EOS-like hierarchical CLI with `no ` as the [negation prefix](../glossary.md#negation-prefix), so the `ARUBA_AOSCX` driver reuses the standard IOS/EOS tree model and remediation. The one platform-specific behavior is how trunk VLAN membership is modeled:

- `vlan trunk allowed` is *additive* on AOS-CX rather than declarative. The driver splits comma/range VLAN lists into one command per VLAN (on load and in the intended config), so remediation adds a missing VLAN with `vlan trunk allowed <id>` and removes an extra one with `no vlan trunk allowed <id>`, rather than rewriting the whole list.
- Unnamed collapsed VLAN headers such as `vlan 1,10` or `vlan 100-102` are likewise split into individual `vlan <id>` sections.
- Structured sections such as `evpn` and `interface vxlan` are remediated like any other section: individual members (for example an EVPN `vlan`) are added or negated, while unchanged siblings such as `arp-suppression` are left untouched. As with Arista/Cisco, the intended config should list the members that must remain.
- Common one-value commands such as interface `description`, `ip address`, `vlan access`, `vlan trunk native`, and `vrf attach` are treated as idempotent replacements.
- BGP address-family blocks close with `exit-address-family`.
- Per-line substitutions strip comment lines and rendered `exit`/`end` markers during parsing.

**Known limitation**: because trunk VLAN lists are modeled one VLAN per line, a very wide range (for example `vlan trunk allowed 1-4094`) expands to one command per VLAN internally, so remediation that creates such a trunk from scratch renders many lines instead of the single range the operator wrote. Only the *delta* is emitted for an existing trunk, so day-to-day changes stay minimal; the expansion only shows up when adding a wide range wholesale.

---

### Juniper JunOS

Juniper JunOS uses `set` and `delete` command syntax for its hierarchical configuration.

> **Experimental:** JunOS support has not been tested extensively in production environments. Use with caution.

- **[Declaration prefix](../glossary.md#declaration-prefix)**: `set ` (prepended to each positive command).
- **[Negation prefix](../glossary.md#negation-prefix)**: `delete ` (replaces `no `).
- **Config preprocessor**: native curly-brace configuration is flattened to `set` commands before parsing.

For a worked example see [Set-Style Platforms](../user/set-style-platforms.md).

---

### Nokia SRL (Service Router Linux)

Nokia SR Linux uses `set` and `delete` command syntax, similar to VyOS and JunOS. The driver converts hierarchical SRL configuration (from `info` output) into flat `set`/`delete` commands via a preprocessor.

> **Experimental:** Nokia SRL support has not been tested extensively in production environments. Use with caution.

- **[Declaration prefix](../glossary.md#declaration-prefix)**: `set ` (prepended to each positive command).
- **[Negation prefix](../glossary.md#negation-prefix)**: `delete ` (replaces `no `).

---

### Ruckus/Brocade FastIron (ICX)

> **Experimental:** developed against FastIron **08.0.30** on ICX 6450 (`S`
> switch image) and ICX 6650 (`R` router image). FastIron 08.0.95 and the
> 09.x/10.x releases moved several command families closer to Cisco IOS syntax
> and are not covered by this driver.

```python
from hier_config import HConfig, Platform

running = HConfig.from_text(Platform.RUCKUS_FASTIRON, running_text)
intended = HConfig.from_text(Platform.RUCKUS_FASTIRON, intended_text)
remediation = running.remediation(intended)
```

Platform-specific behaviour:

- **VLAN membership is expanded per port at load time.** FastIron renders
  membership as one collapsed line under the VLAN
  (`tagged ethe 1/1/1 to 1/1/48 ethe 1/2/4`). Diffing that as a single string
  means changing one port rewrites the whole line, momentarily removing every
  other port from the VLAN. The driver rewrites it to one
  `tagged ethe 1/1/1` per port, which the CLI accepts verbatim. Unlike the HP
  ProCurve driver, membership stays under the VLAN rather than moving to the
  interface, because FastIron has no interface-level VLAN membership command.
- **`stack` configuration is removed at load time** and never remediated.
  Stack membership is established once at build time and re-issuing it against
  a live stack can renumber or reload members.
- **VLAN headers are normalised at load time.** FastIron renders the name
  inline (`vlan 101 name USERS by port`) and renames by re-issuing that whole
  command, so the header is both the section selector and the rename command.
  The driver reduces the header to `vlan 101` and carries the name as a child,
  which keeps the section identity stable across a rename and makes the rename
  itself a single remediation line. The child is a global command, so it
  applies correctly from inside the VLAN context where it is emitted.

    Marking the header idempotent instead would look equivalent but breaks
    `future()`: an idempotent match makes it keep only the delta's children and
    drop the unchanged ones, which corrupts rollback generation.

    An unnamed VLAN renders as `vlan 20 by port` and normalises the same way,
    so the name child is matched idempotently on `vlan <id>` rather than on the
    named form. Both forms are global commands, and negating either one deletes
    the VLAN along with every port in it.
- **A LAG section is negated down to its name** (`no lag "CORE_UPLINK"`), and a
  LAG cannot be renamed in place -- a name change is a delete and re-create.
- **`ip address` is additive, not idempotent.** A second address in another
  subnet is added to the interface rather than replacing the first, verified on
  an ICX 6650. Addresses are therefore diffed one line at a time, so removing
  one emits `no ip address ...` for exactly that address.
- **IPv4 ACLs are rebuilt when their body changes**, because entries have no
  sequence numbers on this release and can only be appended, so an entry that
  belongs in the middle cannot be inserted in place.

    The rebuild is emitted as `no ip access-list ...` followed by the full new
    body. An interface binding (`ip access-group ...`) survives the gap and
    re-arms automatically once the ACL is re-created with the same name, and
    traffic is **not** dropped in between -- the interface fails open. Treat an
    ACL rebuild as traffic-affecting from a security standpoint and schedule it
    accordingly, e.g. by tagging it for manual review:

    ```python
    TagRule(
        match_rules=(MatchRule(startswith=("ip access-list ", "no ip access-list ")),),
        apply_tags=frozenset({"manual"}),
    )
    ```

    Note that any change to an ACL body triggers the rebuild, including an
    append that would have been safe on its own. If the push is interrupted
    between the negation and the re-created body, the ACL stays deleted -- the
    open window is short but it is not self-healing.
- **`no interface ethernet ...` is a reset, not a deletion.** FastIron accepts
  it, clears the interface block (`port-name`, `port security`, `trust`,
  `dual-mode`, ...) and the port then disappears from `show running-config`,
  because FastIron omits interfaces that are entirely at their defaults. VLAN
  membership is *not* affected -- it lives in the `vlan` blocks -- so a port
  that was dual-mode in VLAN 101 stays in VLAN 101 as a plain tagged member.
  The driver emits the reset normally but orders it ahead of everything else so
  it cannot clobber interface settings applied earlier in the same push.
- **An interface absent from the running config is at its defaults**, not
  missing. Intended configs that spell out every port will diff against a
  running config that lists only the non-default ones; this is expected and the
  resulting remediation is correct.
- **A LAG member carries the whole LAG into a VLAN.** Issuing
  `untagged ethe 1/1/11` for a port that belongs to a deployed LAG moves every
  member of that LAG, and the device renders the result as the full range.
  Membership stays consistent across diffs because both sides see the same
  rendering, but a one-line remediation can move more ports than it names.
- **LAG sections need human review.** A deployed LAG refuses to give up its
  primary port or to change it, so a membership change is a stateful sequence
  (`no deploy` -> `primary-port` -> `no ports` -> `enable ethe` -> `deploy`)
  that hier_config cannot synthesise: `deploy` is identical on both sides, so
  it never appears in the delta for the driver to order around. Removing a
  member also disables that port automatically, and the disabled state is not
  visible in `show running-config`, so a follow-up `enable ethe ...` can never
  be derived from a diff either. The driver orders an un-deploy/re-deploy pair
  correctly when one is present, but LAG changes should be tagged for manual
  handling:

    ```python
    TagRule(
        match_rules=(MatchRule(startswith=("lag ", "no lag ")),),
        apply_tags=frozenset({"manual"}),
    )
    ```

    Member lists are expanded per port at load time, the same way VLAN
    membership is: FastIron accumulates repeated `ports ethernet ...` commands
    and renders them collapsed, so expanding normalises both sides and a single
    member change stays a single line. Adding a member to a deployed LAG is
    accepted; removing one is accepted only for a non-primary member, and it
    disables the removed port.

    LAG member descriptions (`port-name ... ethernet ...`) are keyed on the
    member port and are safe to apply on a deployed LAG.
- **Ordering rules** reflect device-enforced dependencies: a port leaves its
  old untagged VLAN before joining a new one; `no vlan` is deferred because it
  also drops every membership in that VLAN; and a `mac filter-group` binding is
  removed from the interface before the filter itself, and a newly created
  `mac filter` sorts ahead of the interfaces that bind it. FastIron guards a
  `mac filter` from both sides: binding one that does not exist is refused
  (*filter 32 is not configured in the global table*) and deleting one that is
  still bound is refused too. ACLs are guarded in neither direction, which is
  why the two are ordered differently.

    ACLs are ordered the other way, ahead of the interfaces that bind them, so
    a newly created ACL exists before an `ip access-group` names it. The
    negation stays ahead of the body so a rebuild re-creates the ACL rather
    than deleting it.

    The trade-off is that an ACL being *deleted* is removed before the
    interface unbinds it, leaving a dangling `ip access-group` for the rest of
    the push. FastIron permits that -- unlike `mac filter`, it does not refuse
    the removal -- and both lines are in the same remediation, so the end state
    is identical either way. An interface left unfiltered because its ACL does
    not exist yet is not recoverable in the same way, so it wins.

---

### VyOS

VyOS uses `set` and `delete` command syntax rather than the `no`-prefix convention.

> **Experimental:** VyOS support has not been tested extensively in production environments. Use with caution.

- **[Declaration prefix](../glossary.md#declaration-prefix)**: `set ` (prepended to each positive command).
- **[Negation prefix](../glossary.md#negation-prefix)**: `delete ` (replaces `no `).
- **Config preprocessor**: native curly-brace configuration is flattened to `set` commands before parsing.

---

### Generic

The `GENERIC` driver contains no platform-specific rules. It is useful as a starting point for custom drivers or for platforms that follow standard Cisco-style syntax with few special cases.

See [Custom Drivers and Registration](custom-drivers.md) for how to build on top of the generic driver.

## Next steps

- [Customizing Driver Rules](customizing-rules.md) — extend or adjust the rules of any built-in driver.
- [Custom Drivers and Registration](custom-drivers.md) — add a platform hier_config does not ship with.
- [Driver Rule Reference](../dev/rule-reference.md) — the full catalog of rule types and their fields.
