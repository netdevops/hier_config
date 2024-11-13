# Getting Started with hier_config

Hier Config is a Python library that assists with remediating network configurations by comparing a device's current configuration (running config) with its intended configuration (generated config). Hier Config v3 processes configuration data without connecting to devices, enabling configuration analysis and remediation.

## Step 1: Import Required Classes

To use `WorkflowRemediation`, you’ll import it along with `get_hconfig` (for generating configuration objects) and `Platform` (for specifying the operating system driver).

```python
>>> from hier_config import WorkflowRemediation, get_hconfig
>>> from hier_config.model import Platform
>>>
```

With the Host class imported, it can be utilized to create host objects.

## Step 2: Creating HConfig Objects for Configurations

Use `get_hconfig` to create HConfig objects for both the running and intended configurations. Specify the platform with `Platform.CISCO_IOS`, `Platform.CISCO_NXOS`, etc., based on the device type.

```python
# Define running and intended configurations as strings
>>> running_config_text = open("./tests/fixtures/running_config.conf").read()
>>> generated_config_text = open("./tests/fixtures/generated_config.conf").read()
>>>

# Create HConfig objects for running and intended configurations
>>> running_config = get_hconfig(Platform.CISCO_IOS, running_config_text)
>>> generated_config = get_hconfig(Platform.CISCO_IOS, generated_config_text)
>>>
```

## Step 3: Initializing WorkflowRemediation and Generating Remediation

With the HConfig objects created, initialize `WorkflowRemediation` to calculate the required remediation steps.

```python
# Initialize WorkflowRemediation with the running and intended configurations
>>> workflow = WorkflowRemediation(running_config, generated_config)
>>>
```

## Generating the Remediation Configuration

The `remediation_config` attribute generates the configuration needed to apply the intended changes to the device. Use `all_children_sorted()` to display the configuration in a readable format:

```python
>>> print("Remediation configuration:")
Remediation configuration:
>>> for line in workflow.remediation_config.all_children_sorted():
...     print(line.cisco_style_text())
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

## Generating the Rollback Configuration

Similarly, the `rollback_config` attribute generates a configuration that can revert the changes, restoring the device to its original state.

```python
# Generate and display the rollback configuration
>>> print("Rollback configuration:")
Rollback configuration:
>>> for line in workflow.rollback_config.all_children_sorted():
...     print(line.cisco_style_text())
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