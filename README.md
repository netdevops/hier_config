[![Build Status](https://travis-ci.org/netdevops/hier_config.svg?branch=master)](https://travis-ci.org/netdevops/hier_config)

# Hierarchical Configuration

Hierarchical Configuration is a python library that is able to take a running configuration of a network device, compare it to its intended configuration, and build the remediation steps necessary bring a device into spec with its intended configuration.

Hierarchical Configuraiton has been used extensively on:

- [x] Cisco IOS
- [x] Cisco IOSXR
- [x] Cisco NXOS
- [x] Arista EOS

However, any NOS that utilizes a CLI syntax that is structured in a similar fasion to IOS should work mostly out of the box.

The code documentation can be found at: https://netdevops.io/hier_config/

Installation
============

Hierarchical Configuration can be installed directly from github or with pip:

- Github
```
git clone git@github.com:netdevops/hier_config.git
cd hier_config; ./setup.py
```
- Pip
```
pip install hier-config
```
