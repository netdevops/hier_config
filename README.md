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

In the below example, we create two hierarchical configuraiton objects, load one with a running configuratoin from a
device, and the other with the intended configuration of the device, then we compare the two objects to derive the
commands necessary to bring the device into spec.

```
>>> from hier_config import HConfig
>>> import yaml
>>>
>>> hostname = 'example.rtr'
>>> os = 'ios'
>>> options = yaml.load(open('./tests/files/test_options_ios.yml'))
>>> tags = yaml.load(open('./tests/files/test_tags_ios.yml'))
>>>
>>> # Build HConfig object for the Running Config
...
>>> running_config_hier = HConfig(hostname, os, options)
>>> running_config_hier.load_from_file('./tests/files/running_config.conf')
>>>
>>> # Build Hierarchical Configuration object for the Compiled Config
...
>>> compiled_config_hier = HConfig(hostname, os, options)
>>> compiled_config_hier.load_from_file('./tests/files/compiled_config.conf')
>>>
>>> # Build Hierarchical Configuration object for the Remediation Config
...
>>> remediation_config_hier = running_config_hier.config_to_get_to(compiled_config_hier)
>>> remediation_config_hier.add_tags(tags)
<HConfig object at 0x103aa1358>
>>> remediation_config_hier.add_sectional_exiting()
>>>
>>> for line in remediation_config_hier.all_children():
...     print(line.cisco_style_text())
...
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

The files in the example can be seen in the `tests/files` folder.