# Hierarchical Configuration (hier_config)

`hier_config` is a Python library that compares a network device's running configuration against its intended configuration and generates the exact commands needed to bring the device into compliance — without ever connecting to it. Configurations are parsed into hierarchical trees, diffed with full awareness of vendor-specific syntax rules (negation, idempotency, section exiting, command ordering), and rendered back out as minimal, ready-to-apply remediation.

## Quick example

```python
from hier_config import HConfig, Platform, WorkflowRemediation

running_config_text = """
hostname old-name
interface Vlan2
 shutdown
"""

intended_config_text = """
hostname new-name
interface Vlan2
 no shutdown
"""

running = HConfig.from_text(Platform.CISCO_IOS, running_config_text)
intended = HConfig.from_text(Platform.CISCO_IOS, intended_config_text)

workflow = WorkflowRemediation(running, intended)
for line in workflow.remediation_config.all_children_sorted():
    print(line.indented_text())
# no hostname old-name
# hostname new-name
# interface Vlan2
#   no shutdown
```

## Where to go next

### I want to generate remediation → [User Guide](user/getting-started.md)

Install the library, walk through your first diff, and learn the everyday workflows: [loading configurations](user/loading-configs.md) from text, JSON, or XML; [remediation and rollback](user/remediation-workflows.md); [tag-based filtering](user/tags.md); [future-state prediction](user/future-config.md); [multi-device reporting](user/remediation-reporting.md); and [typed config views](user/config-views.md).

### I need to tune platform behavior → [Administrator Guide](admin/platforms.md)

Review the [supported platforms](admin/platforms.md) and their quirks, [customize driver rules](admin/customizing-rules.md) (idempotency, negation, ordering, post-load callbacks), [register custom drivers](admin/custom-drivers.md), or [load rules from YAML files](admin/rules-from-files.md).

### I want to extend hier_config → [Developer Guide](dev/architecture.md)

Understand the [architecture](dev/architecture.md) (tree, driver, and workflow layers), browse the [driver rule reference](dev/rule-reference.md), [create a new platform driver](dev/creating-drivers.md) from scratch, or [contribute](dev/contributing.md) to the project. The full [API reference](dev/api-reference.md) documents every public class and function.

---

Unsure what a term means? Check the [Glossary](glossary.md).
