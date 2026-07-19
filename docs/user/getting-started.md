# Getting Started

This page walks you through your first remediation: loading a running and an intended configuration, computing the commands that close the gap, and generating a rollback. It is the best starting point if you are new to hier_config.

hier_config compares a device's current configuration (the *running config*) with its intended configuration (the *generated config*) and produces the minimal set of commands needed to bring the device into compliance. Everything happens offline — no device connection is required.

## Step 1: Import the required classes

You need `HConfig` (the configuration tree), `Platform` (the operating-system selector), and `WorkflowRemediation` (the comparison workflow):

```python
>>> from hier_config import WorkflowRemediation, HConfig, Platform
>>> from hier_config.utils import read_text_from_file
>>>
```

## Step 2: Create HConfig objects for both configurations

Use `HConfig.from_text()` to parse each configuration. The first argument selects the platform driver (`Platform.CISCO_IOS`, `Platform.ARISTA_EOS`, and so on — see [Supported Platforms](../admin/platforms.md)):

```python
# Load running and intended configurations from files
>>> running_config_text = read_text_from_file("./tests/fixtures/running_config.conf")
>>> generated_config_text = read_text_from_file("./tests/fixtures/remediation_config.conf")
>>>

# Create HConfig objects for running and intended configurations
>>> running_config = HConfig.from_text(Platform.CISCO_IOS, running_config_text)
>>> generated_config = HConfig.from_text(Platform.CISCO_IOS, generated_config_text)
>>>
```

`from_text()` also accepts a `pathlib.Path` directly, and there are additional constructors for pre-split lines, JSON, and XML — see [Loading Configurations](loading-configs.md).

## Step 3: Initialize WorkflowRemediation

With both trees built, initialize `WorkflowRemediation` to compute the required changes:

```python
>>> workflow = WorkflowRemediation(running_config, generated_config)
>>>
```

## Generating the remediation configuration

The `remediation_config` property holds the commands that transform the running configuration into the intended one. Use `all_children_sorted()` with `indented_text()` to render it:

```python
>>> print("Remediation configuration:")
Remediation configuration:
>>> for line in workflow.remediation_config.all_children_sorted():
...     print(line.indented_text())
...
vlan 3
  name switch_mgmt_10.0.3.0/24
vlan 4
  name switch_mgmt_10.0.4.0/24
interface Vlan2
  mtu 9000
  ip access-group TEST in
  no shutdown
interface Vlan3
  description switch_mgmt_10.0.3.0/24
  ip address 10.0.3.1 255.255.0.0
interface Vlan4
  mtu 9000
  description switch_mgmt_10.0.4.0/24
  ip address 10.0.4.1 255.255.0.0
  ip access-group TEST in
  no shutdown
>>>
```

## Generating the rollback configuration

The `rollback_config` property generates the inverse change — the commands that revert the device to its original state after the remediation has been applied:

```python
# Generate and display the rollback configuration
>>> print("Rollback configuration:")
Rollback configuration:
>>> for line in workflow.rollback_config.all_children_sorted():
...     print(line.indented_text())
...
no vlan 4
no interface Vlan4
vlan 3
  name switch_mgmt_10.0.4.0/24
interface Vlan2
  no mtu 9000
  no ip access-group TEST in
  shutdown
interface Vlan3
  description switch_mgmt_10.0.4.0/24
  ip address 10.0.4.1 255.255.0.0
>>>
```

## Next steps

- [Loading Configurations](loading-configs.md) — every way to build an `HConfig`, including JSON and XML.
- [Remediation Workflows](remediation-workflows.md) — customize the remediation with transforms and plugins.
- [Working with Tags](tags.md) — deploy only a subset of the remediation.
- [Predicting Future Configs](future-config.md) — preview the post-change configuration.
