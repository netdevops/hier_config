# Drivers in Hier Config

Drivers represent a modern approach to handling operating system-specific options within Hier Config. Prior to version 3, Hier Config utilized `options` or `hconfig_options`, which were defined as dictionaries, to specify OS-specific parameters. Starting with version 3, these options have been replaced by drivers, which are implemented as Pydantic models and loaded as Python classes, offering improved structure and validation.

> **Note:** Many of the options available in the Hier Config version 3 driver format are similar to those in the version 2 options format. However, some options have been removed because they are no longer used in version 3, or their names have been updated for consistency or clarity.

## What is a Driver?

A driver in Hier Config defines a structured and systematic approach to managing operating system-specific configurations for network devices. It acts as a framework that encapsulates the rules, transformations, and behaviors required to process and normalize device configurations.

Drivers provide a consistent way to handle configurations by applying a set of specialized logic, including:

1. **[Negation Handling](glossary.md#negation-prefix)**: Ensures commands are properly negated or reset according to the operating system's syntax and behavior, maintaining consistency in enabling or disabling features.

2. **[Sectional Exiting Rules](glossary.md#sectional-exiting)**: Defines how to navigate in and out of hierarchical configuration sections, ensuring commands are logically grouped and the configuration maintains its structural integrity.

3. **Command Ordering**: Establishes the sequence in which commands should be applied based on dependencies or importance, preventing conflicts or misconfigurations during deployment.

4. **Line Substitutions**: Cleans up unnecessary or temporary data in configurations, such as metadata, system-generated comments, or obsolete commands, resulting in a streamlined and standardized output.

5. **[Idempotency Management](glossary.md#idempotent-command)**: Identifies and enforces commands that should not be duplicated, ensuring repeated application of the configuration does not lead to redundant or conflicting entries.

6. **Post-Processing Callbacks**: Performs additional adjustments or enhancements after the initial configuration is processed, such as refining access control lists or applying custom transformations specific to the device's operating system.

By defining these rules and behaviors in a reusable way, a driver enables Hier Config to adapt seamlessly to different operating systems while maintaining a consistent interface for configuration management. This abstraction allows users to work with configurations in a predictable and efficient manner, regardless of the underlying system-specific requirements.

---

## Built-In Drivers in Hier Config

The following drivers are included in Hier Config:

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
| VyOS | `Platform.VYOS` | Experimental |
| Generic | `Platform.GENERIC` | Base for custom drivers |

To activate a driver, use the `get_hconfig_driver` utility provided by Hier Config:

```python
from hier_config import get_hconfig_driver, Platform

# Example: Activating the CISCO_IOS driver
driver = get_hconfig_driver(Platform.CISCO_IOS)
```

### Cisco IOS Driver

Cisco IOS is hier_config's primary reference platform and the most thoroughly tested driver. The `CISCO_IOS` driver ships with a comprehensive set of rules covering common IOS configuration patterns:

- **[Idempotent commands](glossary.md#idempotent-command)**: `hostname`, `ip address`, `ip access-group`, `description`, `banner`, and many others are treated as last-write-wins — applying the same command twice leaves only the final value in place.
- **Negation**: standard `no ` [negation prefix](glossary.md#negation-prefix). Several commands (such as `logging console`) use [`NegationDefaultWithRule`](glossary.md#negation-negate-with) overrides to emit a specific reset form.
- **[Sectional exiting](glossary.md#sectional-exiting)**: BGP `peer-policy` and `peer-session` blocks require `exit-peer-policy` and `exit-peer-session` closure tokens.
- **Per-line substitutions**: strips `Building configuration…` banners and timestamp headers.
- **VLAN id list splitting**: IOS can render unnamed VLANs collapsed onto a single comma/range line (e.g. `vlan 69,381`, `vlan 10-12`), depending on how the VLANs were created — named VLANs always get their own block, and the grouping shifts as VLANs are named or unnamed. When such a collapsed line is present, a post-load callback splits it into one `vlan <id>` block each so the VLANs diff block-to-block against an intended config that lists them separately — avoiding a destructive `no vlan 69,381`.

Platform enum: `Platform.CISCO_IOS`

```python
from hier_config import Platform, get_hconfig_driver

driver = get_hconfig_driver(Platform.CISCO_IOS)
```

---

### Arista EOS Driver

Arista EOS uses a Cisco IOS-like hierarchical CLI, so the `ARISTA_EOS` driver closely mirrors `CISCO_IOS`:

- BGP peer-policy and peer-session blocks require `exit-peer-policy` and `exit-peer-session` closure tokens (same as IOS).
- Broad idempotency rules cover the most common EOS configuration patterns.
- [Negation prefix](glossary.md#negation-prefix): `no ` (default).

Platform enum: `Platform.ARISTA_EOS`

```python
from hier_config import Platform, get_hconfig_driver

driver = get_hconfig_driver(Platform.ARISTA_EOS)
```

---

### Aruba AOS-CX Driver

Aruba AOS-CX uses a Cisco IOS/EOS-like hierarchical CLI with `no ` as the [negation prefix](glossary.md#negation-prefix), so the `ARUBA_AOSCX` driver reuses the standard IOS/EOS tree model and remediation. The one platform-specific behavior is how trunk VLAN membership is modeled:

- `vlan trunk allowed` is *additive* on AOS-CX rather than declarative. The driver splits comma/range VLAN lists into one command per VLAN (on load and in the intended config), so remediation adds a missing VLAN with `vlan trunk allowed <id>` and removes an extra one with `no vlan trunk allowed <id>`, rather than rewriting the whole list.
- Unnamed collapsed VLAN headers such as `vlan 1,10` or `vlan 100-102` are likewise split into individual `vlan <id>` sections.
- Structured sections such as `evpn` and `interface vxlan` are remediated like any other section: individual members (for example an EVPN `vlan`) are added or negated, while unchanged siblings such as `arp-suppression` are left untouched. As with Arista/Cisco, the intended config should list the members that must remain.
- Common one-value commands such as interface `description`, `ip address`, `vlan access`, `vlan trunk native`, and `vrf attach` are treated as idempotent replacements.
- BGP address-family blocks close with `exit-address-family`.
- Per-line substitutions strip comment lines and rendered `exit`/`end` markers during parsing.

**Known limitation**: because trunk VLAN lists are modeled one VLAN per line, a very wide range (for example `vlan trunk allowed 1-4094`) expands to one command per VLAN internally, so remediation that creates such a trunk from scratch renders many lines instead of the single range the operator wrote. Only the *delta* is emitted for an existing trunk, so day-to-day changes stay minimal; the expansion only shows up when adding a wide range wholesale.

Platform enum: `Platform.ARUBA_AOSCX`

```python
from hier_config import Platform, get_hconfig_driver

driver = get_hconfig_driver(Platform.ARUBA_AOSCX)
```

---

### Cisco IOS XR Driver

Cisco IOS XR uses a commit-based configuration model with several syntax differences from classic IOS:

- **[Sectional overwrite no-negate](glossary.md#sectional-overwrite-no-negate)**: `prefix-set`, `route-policy`, and similar blocks are replaced wholesale rather than line-by-line, because IOS XR does not support partial modification of these objects.
- **[Indent adjust](glossary.md#indent-adjust)**: `template` blocks use a different indentation depth; the driver adjusts the tree depth between `template` and `end-template` markers.
- **[Sectional exiting](glossary.md#sectional-exiting)**: route-policy blocks close with `end-policy`; prefix-set and community-set blocks close with `end-set`; template blocks close with `end-template`; group blocks close with `end-group`. All `end-*` exit text is rendered at the parent indentation level (`exit_text_parent_level=True`).
- ACL sequence numbers are preserved for correct ordered access-list handling.

Platform enum: `Platform.CISCO_XR`

```python
from hier_config import Platform, get_hconfig_driver

driver = get_hconfig_driver(Platform.CISCO_XR)
```

---

### Cisco NX-OS Driver

Cisco NX-OS is similar to IOS in CLI structure but has NX-OS-specific idempotency requirements:

- **TCAM region idempotency**: `hardware access-list tcam region` commands are treated as last-write-wins.
- Some BGP commands use different negation forms; the driver includes `NegationDefaultWithRule` entries for affected commands.
- [Negation prefix](glossary.md#negation-prefix): `no ` (default).

Platform enum: `Platform.CISCO_NXOS`

```python
from hier_config import Platform, get_hconfig_driver

driver = get_hconfig_driver(Platform.CISCO_NXOS)
```

---

### VyOS Driver

VyOS uses `set` and `delete` command syntax rather than the `no`-prefix convention.

> **Experimental:** VyOS support has not been tested extensively in production environments. Use with caution.

- **[Declaration prefix](glossary.md#declaration-prefix)**: `set ` (prepended to each positive command).
- **[Negation prefix](glossary.md#negation-prefix)**: `delete ` (replaces `no `).

Platform enum: `Platform.VYOS`

```python
from hier_config import Platform, get_hconfig_driver

driver = get_hconfig_driver(Platform.VYOS)
```

---

### Nokia SRL (Service Router Linux) Driver

Nokia SR Linux uses `set` and `delete` command syntax, similar to VyOS and JunOS. The driver converts hierarchical SRL configuration (from `info` output) into flat `set`/`delete` commands via a preprocessor.

> **Experimental:** Nokia SRL support has not been tested extensively in production environments. Use with caution.

- **[Declaration prefix](glossary.md#declaration-prefix)**: `set ` (prepended to each positive command).
- **[Negation prefix](glossary.md#negation-prefix)**: `delete ` (replaces `no `).

Platform enum: `Platform.NOKIA_SRL`

```python
from hier_config import Platform, get_hconfig_driver

driver = get_hconfig_driver(Platform.NOKIA_SRL)
```

**Remediation example:**

```python
from hier_config import WorkflowRemediation, get_hconfig, Platform

running = get_hconfig(Platform.NOKIA_SRL, running_text)
intended = get_hconfig(Platform.NOKIA_SRL, intended_text)
workflow = WorkflowRemediation(running, intended)

for line in workflow.remediation_config.all_children_sorted():
    print(line.cisco_style_text())
```

---

### Generic Driver

The `GENERIC` driver contains no platform-specific rules. It is useful as a starting point for custom drivers or for platforms that follow standard Cisco-style syntax with few special cases.

Platform enum: `Platform.GENERIC`

```python
from hier_config import Platform, get_hconfig_driver

driver = get_hconfig_driver(Platform.GENERIC)
```

See [Creating a Custom Driver](custom-drivers.md#creating-a-custom-driver) for how to build on top of the generic driver.

---

### Juniper JunOS Driver

Juniper JunOS uses `set` and `delete` command syntax for its hierarchical configuration.

> **Experimental:** JunOS support has not been tested extensively in production environments. Use with caution.

- **[Declaration prefix](glossary.md#declaration-prefix)**: `set ` (prepended to each positive command).
- **[Negation prefix](glossary.md#negation-prefix)**: `delete ` (replaces `no `).

For a worked example see [JunOS Style Syntax Remediation](junos-style-syntax-remediation.md).

Platform enum: `Platform.JUNIPER_JUNOS`

```python
from hier_config import Platform, get_hconfig_driver

driver = get_hconfig_driver(Platform.JUNIPER_JUNOS)
```

---

### HP ProCurve (Aruba AOSS) Driver

HP ProCurve switches (sold as Aruba switches after the HP/Aruba merger) use a Cisco-style hierarchical CLI with `no` as the negation prefix.  The `HP_PROCURVE` driver adds several post-load normalisation callbacks that simplify diffing:

- **VLAN membership** — moves `untagged`/`tagged` directives out of `vlan <id>` blocks and into per-interface blocks, matching the mental model that operators typically use when writing intended configs.
- **Port-access range expansion** — expands compact port ranges like `aaa port-access authenticator 1/15-1/20,1/26-1/40` into individual interface lines so that hier_config can apply idempotency rules per port.
- **Device-profile tagged-VLAN splitting** — splits comma-separated VLAN lists in `device-profile` blocks into one command per VLAN.

The driver also extends idempotency and negation-with logic to handle ProCurve-specific command patterns such as `aaa port-access`, `radius-server`, and `tacacs-server` with variable-length key fields.

Platform enum: `Platform.HP_PROCURVE`

Activate the driver:

```python
from hier_config import Platform, get_hconfig_driver

driver = get_hconfig_driver(Platform.HP_PROCURVE)
```

**Remediation example:**

```python
from hier_config import WorkflowRemediation, get_hconfig, Platform

running = get_hconfig(Platform.HP_PROCURVE, running_text)
intended = get_hconfig(Platform.HP_PROCURVE, intended_text)
workflow = WorkflowRemediation(running, intended)

for line in workflow.remediation_config.all_children_sorted():
    print(line.cisco_style_text())
```

---

### HP Comware5 Driver

HP Comware5 (and the compatible H3C platform) uses `undo` as the negation prefix rather than `no`.  The `HP_COMWARE5` driver overrides `negation_prefix` accordingly.  No additional platform-specific rules are configured by default; extend the driver if your environment requires them (see [Customising Existing Drivers](custom-drivers.md#customizing-existing-drivers)).

Platform enum: `Platform.HP_COMWARE5`

Activate the driver:

```python
from hier_config import Platform, get_hconfig_driver

driver = get_hconfig_driver(Platform.HP_COMWARE5)
```

**Remediation example:**

```python
from hier_config import WorkflowRemediation, get_hconfig, Platform

running = get_hconfig(Platform.HP_COMWARE5, running_text)
intended = get_hconfig(Platform.HP_COMWARE5, intended_text)
workflow = WorkflowRemediation(running, intended)

for line in workflow.remediation_config.all_children_sorted():
    print(line.cisco_style_text())
```

---

### Huawei VRP Driver

Huawei VRP (Versatile Routing Platform) uses `undo` as the negation prefix rather than `no`. The `HUAWEI_VRP` driver customises negation handling for several command families:

- **[Negation prefix](glossary.md#negation-prefix)**: `undo ` (replaces `no `).
- **Smart negation**: `description` and `alias` commands are negated without their argument; `remark` commands strip the remark text; `snmp-agent community` commands truncate to the community name.
- **Sectional exiting**: section exit text `exit` is translated to `quit` as VRP requires.
- **Per-line substitutions**: strips `#` and `!` comment lines during parsing.

Platform enum: `Platform.HUAWEI_VRP`

```python
from hier_config import Platform, get_hconfig_driver

driver = get_hconfig_driver(Platform.HUAWEI_VRP)
```

**Remediation example:**

```python
from hier_config import WorkflowRemediation, get_hconfig, Platform

running = get_hconfig(Platform.HUAWEI_VRP, running_text)
intended = get_hconfig(Platform.HUAWEI_VRP, intended_text)
workflow = WorkflowRemediation(running, intended)

for line in workflow.remediation_config.all_children_sorted():
    print(line.cisco_style_text())
```

---

### Fortinet FortiOS Driver

Fortinet firewalls model their CLI around `config` and `edit` blocks that are
terminated with `next` and `end`. The `FORTINET_FORTIOS` driver captures those
patterns and makes sure remediation output keeps the indentation and closure
FortiOS expects. Highlights include:

- Preserves the `set`/`unset` pairing by swapping declarations and negations
    automatically when hier_config determines a change is required.
- Treats sibling `config` blocks as duplicates when appropriate so that
    multiple objects such as policies or firewall addresses can be compared in
    a stable order.
- Normalizes bare `next` and `end` tokens into indented versions to match the
    format FortiOS emits on the device.
- Overrides idempotency matching to require that the same object name exists on
    both sides before a command is considered already present.

Activate the driver with the standard helper:

```python
from hier_config import Platform, get_hconfig_driver

driver = get_hconfig_driver(Platform.FORTINET_FORTIOS)
```


---

To learn how these drivers are built, how to customize them, or how to create your own, see [Customizing and Creating Drivers](custom-drivers.md).
