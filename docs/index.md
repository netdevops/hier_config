# Hierarchical Configuration (hier_config)

`hier_config` is a Python library that compares a network device's running configuration against its intended configuration and generates the exact remediation commands needed to bring it into compliance — without connecting to any device.

**New to hier_config?** → [Get started in 5 minutes](getting-started.md)

---

## What can hier_config do?

- **Compute remediation** — diff running vs intended config and produce the minimum set of commands to close the gap. See [Getting Started](getting-started.md).
- **Generate rollbacks** — automatically produce the inverse change so you can revert safely. See [Getting Started → Rollback](getting-started.md#generating-the-rollback-configuration).
- **Preview future state** — simulate what the running config will look like after a change set is applied. See [Future Config](future-config.md).
- **Tag-based filtering** — annotate remediation lines with tags and deploy only a subset of changes (e.g., interfaces only, or BGP only). See [Working with Tags](tags.md).
- **Structured config access** — query interface properties, VLANs, hostnames, and more through a typed Python API without writing regex. See [Config View](config-view.md).
- **Multi-device reporting** — aggregate remediation stats across a fleet and export to JSON or CSV. See [Remediation Reporting](remediation-reporting.md).

---

## Supported Platforms

| Platform | `Platform` enum | Status |
|----------|-----------------|--------|
| Cisco IOS | `Platform.CISCO_IOS` | Fully supported |
| Arista EOS | `Platform.ARISTA_EOS` | Fully supported |
| Cisco IOS XR | `Platform.CISCO_XR` | Fully supported |
| Cisco NX-OS | `Platform.CISCO_NXOS` | Fully supported |
| Fortinet FortiOS | `Platform.FORTINET_FORTIOS` | Fully supported |
| HP ProCurve (Aruba AOSS) | `Platform.HP_PROCURVE` | Fully supported |
| HP Comware5 / H3C | `Platform.HP_COMWARE5` | Fully supported |
| Juniper JunOS | `Platform.JUNIPER_JUNOS` | Experimental |
| VyOS | `Platform.VYOS` | Experimental |
| Generic | `Platform.GENERIC` | Base for custom drivers |

---

## Quick Example

```python
from hier_config import WorkflowRemediation, get_hconfig, Platform

running = get_hconfig(Platform.CISCO_IOS, running_config_text)
intended = get_hconfig(Platform.CISCO_IOS, intended_config_text)
workflow = WorkflowRemediation(running, intended)

for line in workflow.remediation_config.all_children_sorted():
    print(line.cisco_style_text())
```

---

## Where to go next

| Goal | Page |
|------|------|
| Install the library | [Install](install.md) |
| Walk through a first diff | [Getting Started](getting-started.md) |
| Learn about platform drivers | [Drivers](drivers.md) |
| Understand the architecture | [Architecture](architecture.md) |
| Browse the full API | [API Reference](api-reference.md) |
| Look up terminology | [Glossary](glossary.md) |
