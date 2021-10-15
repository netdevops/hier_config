# Experimental Features

Experimental features are those features that work, but haven't been thoroughly tested enough to feel confident to use in production.

## Rollback Configuration

Starting in version 2.0.2, a featured called rollback configuraiton was introduced. The rollback configuration is exactly what it sounds like. It renders a rollback configuration in the event that a remediation causes a hiccup when being deployed. The rollback configuration does the inverse on a remediation. Instead of a remediation being renedered based upon the generated config, a rollback remediation is rendered from the generated config based upon the running configuration.

A rollback configuration can be rendered once the running and generated configurations are loaded. Below is an example.

```bash
>>> from hier_config import Host
>>> host = Host(hostname="aggr-example.rtr", os="ios")
>>> host.load_running_config_from_file("./tests/fixtures/running_config.conf")
>>> host.load_generated_config_from_file("./tests/fixtures/generated_config.conf")
>>> rollback = host.rollback_config()
>>> for line in rollback.all_children_sorted():
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