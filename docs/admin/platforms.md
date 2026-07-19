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
| Juniper JunOS | `Platform.JUNIPER_JUNOS` | Experimental |
| Nokia SRL | `Platform.NOKIA_SRL` | Experimental |
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
