# Creating Custom Workflows

In some scenarios, configuration remediations may require handling beyond the standard negation and idempotency workflows that hier_config is designed to support. Hier Config accommodates these edge cases by allowing the creation of custom remediation workflows, enabling you to integrate them seamlessly with the existing remediation process.

## Building a Remediation

1. Import and Configuration Loading

```python
from hier_config import WorkflowRemediation, get_hconfig, Platform
```
Necessary modules are imported, including the `WorkflowRemediation` class for handling remediation

```python
running_config = load_device_config("./tests/fixtures/running_config_acl.conf")
generated_config = load_device_config("./tests/fixtures/generated_config_acl.conf")
```

Here, the current and intended configurations are loaded from files, serving as inputs for comparison and remediation.

2. Initialize `WorkflowRemiation`:
```python
wfr = WorkflowRemediation(
        running_config=get_hconfig(Platform.CISCO_IOS, running_config),
        generated_config=get_hconfig(Platform.CISCO_IOS, generated_config)
)
```
This initializes `WorkflowRemediation` with the configurations for a Cisco IOS platform, setting up the object that will manage the remediation workflow.

## Extracting the Targeted Section of a Remediation

## Building a Custom Remediation

## Merging the Remediations
