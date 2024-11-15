# JunOS-style Syntax Remediation
Operating systems that use "set"-based syntax can now be remediated experimentally. Below is an example of a JunOS-style remediation.

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


$ python3
>>> from hier_config import WorkflowRemediation, get_hconfig, Platform
>>> from hier_config.utils import load_device_config
>>>
>>> running_config_text = load_device_config("./tests/fixtures/running_config_flat_junos.conf")
>>> generated_config_text = load_device_config("./tests/fixtures/generated_config_flat_junos.conf")
# Create HConfig objects for the running and generated configurations using JunOS syntax
>>> running_config = get_hconfig(Platform.JUNIPER_JUNOS, running_config_text)
>>> generated_config = get_hconfig(Platform.JUNIPER_JUNOS, generated_config_text)
>>>
# Initialize WorkflowRemediation with the running and generated configurations
>>> workflow = WorkflowRemediation(running_config, generated_config)
>>>
# Generate and display the remediation configuration
>>> print("Remediation configuration:")
Remediation configuration:
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

Configurations loaded into Hier Config with Juniper-style syntax are converted to a flat, `set`-based format. Remediation steps are then generated using this `set` syntax.

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

$ python3
>>> from hier_config import WorkflowRemediation, get_hconfig, Platform
>>> from hier_config.utils import load_device_config
>>>
>>> running_config_text = load_device_config("./tests/fixtures/running_config_junos.conf")
>>> generated_config_text = load_device_config("./tests/fixtures/generated_config_junos.conf")
# Create HConfig objects for the running and generated configurations using JunOS syntax
>>> running_config = get_hconfig(Platform.JUNIPER_JUNOS, running_config_text)
>>> generated_config = get_hconfig(Platform.JUNIPER_JUNOS, generated_config_text)
>>>
# Initialize WorkflowRemediation with the running and generated configurations
>>> workflow = WorkflowRemediation(running_config, generated_config)
>>>
# Generate and display the remediation configuration
>>> print("Remediation configuration:")
Remediation configuration:
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