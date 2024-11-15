# Hierarchical Configuration

Welcome to the Hierarchical Configuration documentation site. Hierarchical Configuration, also known as `hier_config`, is a Python library designed to take a running configuration from a network device, compare it to its intended configuration, and build the remediation steps necessary to bring a device into compliance with its intended configuration.

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

Hierarchical Configuration can be installed directly from github or with pip:

### Github
1. [Install Poetry](https://python-poetry.org/docs/#installation)
2. Clone the Repository: `git clone git@github.com:netdevops/hier_config.git`
3. Install `hier_config`: `cd hier_config; poetry install`

### Pip
6. Install from PyPi: `pip install hier-config`
