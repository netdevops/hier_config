# Introduction

Welcome to the Hierarchical Configuration documentation site. Hierarchical Configuration, also known as `hier_config`, is a Python library designed to take a running configuration from a network device, compare it to its intended configuration, and build the remediation steps necessary to bring a device into compliance with its intended configuration.

Hierarchical Configuration has been used extensively on:

- [x] Cisco IOS
- [x] Cisco IOSXR
- [x] Cisco NXOS
- [x] Arista EOS
- [x] Fortinet FortiOS
- [x] HP Procurve (Aruba AOSS)

In addition to the Cisco-style syntax, hier_config offers experimental support for Juniper-style configurations using set and delete commands. This allows users to remediate Junos configurations in native syntax. However, please note that Juniper syntax support is still in an experimental phase and has not been tested extensively. Use with caution in production environments.

Hier Config is compatible with any NOS that utilizes a structured CLI syntax similar to Cisco IOS or Junos OS.
