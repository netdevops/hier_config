# Remediation Workflows

This page covers `WorkflowRemediation` in depth: remediation and rollback generation, hand-crafting custom remediation for tricky sections, extending the pipeline with transform callbacks and plugins, and rendering NETCONF payloads. Read it once you are comfortable with the basics from [Getting Started](getting-started.md).

## WorkflowRemediation

`WorkflowRemediation` compares a running and a generated (intended) configuration:

```python
from hier_config import WorkflowRemediation, HConfig, Platform
from hier_config.utils import read_text_from_file

running_config = read_text_from_file("./tests/fixtures/running_config_acl.conf")
generated_config = read_text_from_file("./tests/fixtures/generated_config_acl.conf")

wfr = WorkflowRemediation(
    running_config=HConfig.from_text(Platform.CISCO_IOS, running_config),
    generated_config=HConfig.from_text(Platform.CISCO_IOS, generated_config),
)
```

It exposes two cached properties:

- `wfr.remediation_config` — the commands that bring the device to the intended state.
- `wfr.rollback_config` — the commands that revert the device to its original state.

Both configurations must be built with the same driver class; otherwise the constructor raises `hier_config.exceptions.IncompatibleDriverError`. This guards against accidentally diffing, say, an IOS tree against an NX-OS tree.

## Custom remediation for special sections

Certain scenarios demand remediation strategies beyond the standard [negation](../glossary.md#negation-prefix) and [idempotency](../glossary.md#idempotent-command) handling. hier_config lets you extract, replace, and merge remediation sections to handle these edge cases.

### Example: access-list remediation

**Current (running) configuration:**

```python
print(wfr.running_config.get_child(startswith="ip access-list"))
```

```text
ip access-list extended TEST
  12 permit ip 10.0.0.0 0.0.0.7 any
  exit
```

**Intended (generated) configuration:**

```python
print(wfr.generated_config.get_child(startswith="ip access-list"))
```

```text
ip access-list extended TEST
  10 permit ip 10.0.1.0 0.0.0.255 any
  20 permit ip 10.0.0.0 0.0.0.7 any
  exit
```

**Default remediation:**

```python
print(wfr.remediation_config.get_child(startswith="ip access-list"))
```

```text
ip access-list extended TEST
  no 12 permit ip 10.0.0.0 0.0.0.7 any
  10 permit ip 10.0.1.0 0.0.0.255 any
  20 permit ip 10.0.0.0 0.0.0.7 any
  exit
```

The default remediation has three issues:

1. **Invalid command:** `no 12 permit ip 10.0.0.0 0.0.0.7 any` is invalid in Cisco IOS; the valid form is `no 12`.
2. **Risk of lockout:** removing a line currently matched by traffic could cause an outage.
3. **Unnecessary churn:** the entry only differs by sequence number; in large ACLs re-adding it is wasteful.

### Building a safer remediation

The plan: resequence the ACL, add a temporary allow-all entry to prevent lockout, apply the changes, and clean up the temporary entry.

**1. Create a custom `HConfig` object** (reuse the running config's driver):

```python
from hier_config import HConfig

custom_remediation = HConfig(wfr.running_config.driver)
```

**2. Add resequencing and extract the ACL remediation:**

```python
custom_remediation.add_child("ip access-list resequence TEST 10 10")
custom_remediation.add_child("ip access-list extended TEST")
remediation = wfr.remediation_config.get_child(equals="ip access-list extended TEST")
```

**3. Build the custom ACL remediation:**

```python
acl = custom_remediation.get_child(equals="ip access-list extended TEST")
acl.add_child("1 permit ip any any")  # Temporary allow-all

for line in remediation.all_children():
    if line.text.startswith("no "):
        # Adjust invalid sequence negation
        parts = line.text.split()
        rounded_number = round(int(parts[1]), -1)
        acl.add_child(f"{parts[0]} {rounded_number}")
    else:
        acl.add_child(line.text)

acl.add_child("no 1")  # Cleanup temporary rule
```

```python
print(custom_remediation)
```

```text
ip access-list resequence TEST 10 10
ip access-list extended TEST
  1 permit ip any any
  no 10
  10 permit ip 10.0.1.0 0.0.0.255 any
  20 permit ip 10.0.0.0 0.0.0.7 any
  no 1
  exit
```

**4. Swap it into the workflow's remediation:**

```python
invalid_remediation = wfr.remediation_config.get_child(equals="ip access-list extended TEST")
wfr.remediation_config.delete_child(invalid_remediation)
wfr.remediation_config.merge(custom_remediation)
```

> **Note:** `merge()` is intentionally strict. If any child already exists under the same parent in the target tree, hier_config raises `hier_config.exceptions.DuplicateChildError`. This guards against accidentally overwriting commands when combining remediation fragments. When you need to layer one configuration onto another and allow overlapping sections, use [`future()`](future-config.md) instead.

## The remediation transform pipeline

When `remediation_config` is first computed, hier_config runs two ordered sets of transforms over the result, each receiving the remediation `HConfig` and mutating it in place:

1. **Driver-level transforms** — `driver.rules.remediation_transform_callbacks`, populated by platform drivers (or your customized driver) for platform-wide fixups.
2. **User plugins** — the `plugins` argument of `WorkflowRemediation`, for organization policies and per-workflow behavior.

### Plain-callable plugins

Any `Callable[[HConfig], None]` works as a plugin:

```python
from hier_config import WorkflowRemediation, HConfig

def add_change_banner(remediation: HConfig) -> None:
    if remediation.children:
        first = next(iter(remediation.children))
        first.comments.add("change window CHG0012345")

wfr = WorkflowRemediation(running, generated, plugins=[add_change_banner])
```

### `RemediationPlugin` classes

For reusable, named transforms, subclass `RemediationPlugin`. Instances are callable, so they work anywhere a plain callable does:

```python
from hier_config import HConfig, RemediationPlugin, WorkflowRemediation


class ForbidShutdownPlugin(RemediationPlugin):
    """Drop bare `shutdown` commands from remediations."""

    @property
    def name(self) -> str:
        return "forbid-shutdown"

    @property
    def description(self) -> str:
        return "Removes interface shutdown commands to avoid accidental outages."

    def transform(self, remediation: HConfig) -> None:
        for child in tuple(remediation.all_children()):
            if child.text == "shutdown":
                child.delete()


wfr = WorkflowRemediation(running, generated, plugins=[ForbidShutdownPlugin()])
```

Driver authors should prefer `remediation_transform_callbacks` on `HConfigDriverRules` for platform-level transforms (see [Customizing Driver Rules](../admin/customizing-rules.md)); plugins are for user- and workflow-level policy.

## NETCONF remediation payloads

When both configurations were built with [`HConfig.from_xml()`](loading-configs.md#structured-formats-json-and-xml), the remediation can be rendered as a NETCONF `edit-config` payload:

```python
payload = wfr.remediation_netconf_xml()
```

Deletions become elements with `nc:operation="delete"`; additions use the NETCONF default merge operation. Keyed list-entry deletions are expressed by their key leaf, resolved against the running config — pass `list_keys=` if your data does not use the default `name`/`id` keys. Attribute-level changes cannot be expressed as NETCONF operations and raise `InvalidConfigError`.

## Next steps

- [Working with Tags](tags.md) — filter the remediation for phased deployment.
- [Remediation Reporting](remediation-reporting.md) — aggregate remediations across a fleet.
- [Customizing Driver Rules](../admin/customizing-rules.md) — fix incorrect remediation at the driver level instead of patching it per-workflow.
