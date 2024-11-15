# Hierarchical Configuration

Hierarchical Configuration, also known as `hier_config`, is a Python library designed to query and compare network devices configurations. Among other capabilities, it can compare the running config to an intended configuration to determine the commands necessary to bring a device into compliance with its intended configuration.

Hierarchical Configuration has been used extensively on:

- [x] Cisco IOS
- [x] Cisco IOSXR
- [x] Cisco NXOS
- [x] Arista EOS
- [x] HP Procurve (Aruba AOSS)

In addition to the Cisco-style syntax, hier_config offers experimental support for Juniper-style configurations using set and delete commands. This allows users to remediate Junos configurations in native syntax. However, please note that Juniper syntax support is still in an experimental phase and has not been tested extensively. Use with caution in production environments.

- [x] Juniper JunOS
- [x] VyOS

Hier Config is compatible with any NOS that utilizes a structured CLI syntax similar to Cisco IOS or Junos OS.

The code documentation can be found at: https://hier-config.readthedocs.io/en/latest/

Installation
============

### Pip
Install from PyPi: `pip install hier-config`
