# Set-Style Platforms

This page covers remediation for platforms whose CLI uses `set` / `delete` command syntax — Juniper JunOS, VyOS, and Nokia SR Linux — rather than the Cisco-style `no` prefix. Read it if you work with any of these platforms.

> **Experimental:** set-style platform support has not been tested extensively in production environments. Use with caution.

## How set-style platforms work

All three drivers share the same model:

- **[Declaration prefix](../glossary.md#declaration-prefix)** `set ` — prepended to each positive command.
- **[Negation prefix](../glossary.md#negation-prefix)** `delete ` — replaces the Cisco-style `no `.
- **A config preprocessor** — each driver's `config_preprocessor` converts the platform's hierarchical native rendering into flat `set` commands before parsing:
    - JunOS: curly-brace configuration (`show configuration` output) is flattened.
    - VyOS: curly-brace configuration is flattened.
    - Nokia SRL: hierarchical `info` output is flattened.

You can therefore feed either flat `set`-style text or the hierarchical native format into `HConfig.from_text()` — both parse to the same tree, and remediation is always emitted as `set` / `delete` commands.

| Platform | `Platform` enum | Native hierarchical input |
|----------|-----------------|---------------------------|
| Juniper JunOS | `Platform.JUNIPER_JUNOS` | curly-brace config |
| VyOS | `Platform.VYOS` | curly-brace config |
| Nokia SR Linux | `Platform.NOKIA_SRL` | `info` output |

## Example: JunOS remediation from flat set-style config

```bash
$ cat ./tests/fixtures/running_config_flat_junos.conf
set system host-name aggr-example.rtr

set firewall family inet filter TEST term 1 from source-address 10.0.0.0/29
set firewall family inet filter TEST term 1 then accept

set vlans switch_mgmt_10.0.2.0/24 vlan-id 2
set vlans switch_mgmt_10.0.2.0/24 l3-interface irb.2

set vlans switch_mgmt_10.0.4.0/24 vlan-id 3
set vlans switch_mgmt_10.0.4.0/24 l3-interface irb.3

set interfaces irb unit 2 family inet address 10.0.2.1/24
set interfaces irb unit 2 family inet description "switch_10.0.2.0/24"
set interfaces irb unit 2 family inet disable

set interfaces irb unit 3 family inet address 10.0.4.1/16
set interfaces irb unit 3 family inet filter input TEST
set interfaces irb unit 3 family inet mtu 9000
set interfaces irb unit 3 family inet description "switch_mgmt_10.0.4.0/24"
```

```python
>>> from hier_config import WorkflowRemediation, HConfig, Platform
>>> from hier_config.utils import read_text_from_file
>>>
>>> running_config_text = read_text_from_file("./tests/fixtures/running_config_flat_junos.conf")
>>> generated_config_text = read_text_from_file("./tests/fixtures/generated_config_flat_junos.conf")
>>>
>>> running_config = HConfig.from_text(Platform.JUNIPER_JUNOS, running_config_text)
>>> generated_config = HConfig.from_text(Platform.JUNIPER_JUNOS, generated_config_text)
>>>
>>> workflow = WorkflowRemediation(running_config, generated_config)
>>>
>>> print(str(workflow.remediation_config))
delete vlans switch_mgmt_10.0.4.0/24 vlan-id 3
delete vlans switch_mgmt_10.0.4.0/24 l3-interface irb.3
delete interfaces irb unit 2 family inet disable
delete interfaces irb unit 3 family inet address 10.0.4.1/16
delete interfaces irb unit 3 family inet description "switch_mgmt_10.0.4.0/24"
set vlans switch_mgmt_10.0.3.0/24 vlan-id 3
set vlans switch_mgmt_10.0.3.0/24 l3-interface irb.3
set vlans switch_mgmt_10.0.4.0/24 vlan-id 4
set vlans switch_mgmt_10.0.4.0/24 l3-interface irb.4
set interfaces irb unit 2 family inet filter input TEST
set interfaces irb unit 2 family inet mtu 9000
set interfaces irb unit 3 family inet address 10.0.3.1/16
set interfaces irb unit 3 family inet description "switch_mgmt_10.0.3.0/24"
set interfaces irb unit 4 family inet address 10.0.4.1/16
set interfaces irb unit 4 family inet filter input TEST
set interfaces irb unit 4 family inet mtu 9000
set interfaces irb unit 4 family inet description "switch_mgmt_10.0.4.0/24"
>>>
```

## Example: JunOS remediation from hierarchical config

The same workflow accepts native curly-brace configuration — the preprocessor flattens it to `set` commands automatically:

```bash
$ cat ./tests/fixtures/running_config_junos.conf
system {
    host-name aggr-example.rtr;
}

firewall {
    family inet {
        filter TEST {
            term 1 {
                from {
                    source-address 10.0.0.0/29;
                }
                then {
                    accept;
                }
            }
        }
    }
}

vlans {
    switch_mgmt_10.0.2.0/24 {
        vlan-id 2;
        l3-interface irb.2;
    }
    switch_mgmt_10.0.4.0/24 {
        vlan-id 3;
        l3-interface irb.3;
    }
}

interfaces {
    irb {
        unit 2 {
            family inet {
                address 10.0.2.1/24;
                description "switch_10.0.2.0/24";
                disable;
            }
        }
        unit 3 {
            family inet {
                address 10.0.4.1/16;
                filter {
                    input TEST;
                }
                mtu 9000;
                description "switch_mgmt_10.0.4.0/24";
            }
        }
    }
}
```

```python
>>> running_config = HConfig.from_text(Platform.JUNIPER_JUNOS, read_text_from_file("./tests/fixtures/running_config_junos.conf"))
>>> generated_config = HConfig.from_text(Platform.JUNIPER_JUNOS, read_text_from_file("./tests/fixtures/generated_config_junos.conf"))
>>> workflow = WorkflowRemediation(running_config, generated_config)
>>> print(str(workflow.remediation_config))
delete vlans switch_mgmt_10.0.4.0/24 vlan-id 3
delete vlans switch_mgmt_10.0.4.0/24 l3-interface irb.3
delete interfaces irb unit 2 family inet description "switch_10.0.2.0/24"
delete interfaces irb unit 2 family inet disable
delete interfaces irb unit 3 family inet address 10.0.4.1/16
delete interfaces irb unit 3 family inet description "switch_mgmt_10.0.4.0/24"
set vlans switch_mgmt_10.0.3.0/24 vlan-id 3
set vlans switch_mgmt_10.0.3.0/24 l3-interface irb.3
set vlans switch_mgmt_10.0.4.0/24 vlan-id 4
set vlans switch_mgmt_10.0.4.0/24 l3-interface irb.4
set interfaces irb unit 2 family inet filter input TEST
set interfaces irb unit 2 family inet mtu 9000
set interfaces irb unit 2 family inet description "switch_mgmt_10.0.2.0/24"
set interfaces irb unit 3 family inet address 10.0.3.1/16
set interfaces irb unit 3 family inet description "switch_mgmt_10.0.3.0/24"
set interfaces irb unit 4 family inet address 10.0.4.1/16
set interfaces irb unit 4 family inet filter input TEST
set interfaces irb unit 4 family inet mtu 9000
set interfaces irb unit 4 family inet description "switch_mgmt_10.0.4.0/24"
>>>
```

## VyOS and Nokia SRL

VyOS (`Platform.VYOS`) and Nokia SR Linux (`Platform.NOKIA_SRL`) work identically — build both configs with `HConfig.from_text()` and pass them to `WorkflowRemediation`. Remediation output uses `set` / `delete` syntax for all three platforms.

```python
from hier_config import WorkflowRemediation, HConfig, Platform

running = HConfig.from_text(Platform.NOKIA_SRL, running_text)
intended = HConfig.from_text(Platform.NOKIA_SRL, intended_text)
workflow = WorkflowRemediation(running, intended)

for line in workflow.remediation_config.all_children_sorted():
    print(line.indented_text())
```

## Next steps

- [Supported Platforms](../admin/platforms.md) — details and quirks for every built-in platform.
- [Creating a Platform Driver](../dev/creating-drivers.md) — how `config_preprocessor` and prefixes are implemented, if you need to support another set-style OS.
