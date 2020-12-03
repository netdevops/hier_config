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
cd hier_config; ./setup.py install
```
- Pip
```
pip install hier-config
```

Basic Usage Example
===================

In the below example, we create a hier_config host object, load a running config and a generated config into the host object, load the remediation, and print out the remediation lines to bring a device into spec.

```
```
>>> from hier_config import Host
>>> import yaml
>>>
>>> options = yaml.load(open('./tests/fixtures/options_ios.yml'), Loader=yaml.SafeLoader)
>>> host = Host('example.rtr', 'ios', options)
>>>
>>> # Build Hierarchical Configuration object for the Running Config
>>> host.load_running_config_from_file("./tests/fixtures/running_config.conf")
HConfig(host=Host(hostname=example.rtr))
>>>
>>> # Build Hierarchical Configuration object for the Generated Config
>>> host.load_generated_config_from_file("./tests/fixtures/generated_config.conf")
HConfig(host=Host(hostname=example.rtr))
>>>
>>> # Build and Print the all lines of the remediation config
>>>
>>> print(host.remediation_config_filtered_text()):
vlan 3
  name switch_mgmt_10.0.3.0/24
vlan 4
  name switch_mgmt_10.0.4.0/24
interface Vlan2
  no shutdown
  mtu 9000
  ip access-group TEST in
interface Vlan3
  description switch_mgmt_10.0.3.0/24
  ip address 10.0.3.1 255.255.0.0
interface Vlan4
  mtu 9000
  description switch_mgmt_10.0.4.0/24
  ip address 10.0.4.1 255.255.0.0
  ip access-group TEST in
  no shutdown
```

The files in the example can be seen in the `tests/fixtures` folder.
