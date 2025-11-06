# Hierarchical Configuration

Hierarchical Configuration, also known as `hier_config`, is a Python library designed to query and compare network devices configurations. Among other capabilities, it can compare the running config to an intended configuration to determine the commands necessary to bring a device into compliance with its intended configuration.

Hierarchical Configuration has been used extensively on:

- [x] Cisco IOS
- [x] Cisco IOSXR
- [x] Cisco NXOS
- [x] Arista EOS
- [x] Fortinet FortiOS
- [x] HP Procurve (Aruba AOSS)

In addition to the Cisco-style syntax, hier_config offers experimental support for Juniper-style configurations using set and delete commands. This allows users to remediate Junos configurations in native syntax. However, please note that Juniper syntax support is still in an experimental phase and has not been tested extensively. Use with caution in production environments.

- [x] Juniper JunOS
- [x] VyOS

Hier Config is compatible with any NOS that utilizes a structured CLI syntax similar to Cisco IOS or Junos OS.

The code documentation can be found at: [Hier Config documentation](https://hier-config.readthedocs.io/en/latest/).

## Highlights

- Predict the device state before deploying (`future()`) and generate accurate rollbacks that now preserve distinct structural commands—BGP neighbor descriptions, for example, no longer collapse when multiple peers share a common prefix.
- Build remediation workflows with deterministic diffs across Cisco-style and Junos-style configuration syntaxes.

## Installation

### PIP

Install from PyPi:

```shell
pip install hier-config
```

## Quick Start

### Step 1: Import Required Classes

```python
from hier_config import WorkflowRemediation, get_hconfig, Platform
from hier_config.utils import read_text_from_file
```

### Step 2: Load Configurations

Load the running and intended configurations as strings:

```python
running_config_text = read_text_from_file("./tests/fixtures/running_config.conf")
generated_config_text = read_text_from_file("./tests/fixtures/generated_config.conf")
```

### Step 3: Create HConfig Objects

Specify the device platform (e.g., `Platform.CISCO_IOS`):

```python
running_config = get_hconfig(Platform.CISCO_IOS, running_config_text)
generated_config = get_hconfig(Platform.CISCO_IOS, generated_config_text)
```

### Step 4: Initialize WorkflowRemediation

Compare configurations and generate remediation steps:

```python
workflow = WorkflowRemediation(running_config, generated_config)

print("Remediation Configuration:")
print(workflow.remediation_config)
```

This guide gets you started with Hier Config in minutes! For more details, visit [Hier Config Documentation Site](https://hier-config.readthedocs.io/en/latest/).
