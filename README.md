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

## Why hier_config?

Network devices continuously drift from their intended state — VLANs appear, ACL entries change, BGP timers shift.  hier_config solves this by parsing configuration text into a hierarchical tree and performing deterministic, line-level diffs that respect the vendor's own syntax rules.  Rather than string-matching raw text, it understands the structure of commands so that remediation output is minimal, ordered, and safe to apply.

## Highlights

- Predict the device state before deploying with [`future()`](https://hier-config.readthedocs.io/en/latest/future-config/) and generate accurate rollbacks that preserve distinct structural commands — BGP neighbor descriptions, for example, no longer collapse when multiple peers share a common prefix.
- Build remediation workflows with deterministic diffs across [Cisco-style and Junos-style](https://hier-config.readthedocs.io/en/latest/drivers/) configuration syntaxes.
- Tag remediation lines and filter output with [tag-based rules](https://hier-config.readthedocs.io/en/latest/tags/) for phased or conditional deployment.
- Aggregate and analyse changes across a fleet with [RemediationReporter](https://hier-config.readthedocs.io/en/latest/remediation-reporting/).
- Render structured, typed interface data with the [Config View](https://hier-config.readthedocs.io/en/latest/config-view/) abstraction.

See the [Architecture Overview](https://hier-config.readthedocs.io/en/latest/architecture/) for how the tree, driver, and workflow layers fit together.

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
