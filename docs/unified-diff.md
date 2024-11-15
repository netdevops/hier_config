# Unified diff

The Unified Diff feature, introduced in version 2.1.0, provides output similar to `difflib.unified_diff()` but with added awareness of out-of-order lines and parent-child relationships in the Hier Config model of configurations being compared.

This feature is particularly useful when comparing configurations from two network devices, such as redundant pairs, or when validating differences between running and intended configurations.

Currently, the algorithm does not account for duplicate child entries (e.g., multiple `endif` statements in an IOS-XR route-policy) or enforce command order in sections where it may be critical, such as Access Control Lists (ACLs). For accurate ordering in ACLs, sequence numbers should be used if command order is important.

```bash
>>> from hier_config import get_hconfig, Platform
>>> from pprint import pprint
>>>
>>> running_config_text = load_device_config("./tests/fixtures/running_config.conf")
>>> generated_config_text = load_device_config("./tests/fixtures/generated_config.conf")
>>>
>>> running_config = get_hconfig(Platform.CISCO_IOS, running_config_text)
>>> generated_config = get_hconfig(Platform.CISCO_IOS, generated_config_text)
>>>
>>> pprint(list(running_config.unified_diff(generated_config)))
['vlan 3',
 '  - name switch_mgmt_10.0.4.0/24',
 '  + name switch_mgmt_10.0.3.0/24',
 'interface Vlan2',
 '  - shutdown',
 '  + mtu 9000',
 '  + ip access-group TEST in',
 '  + no shutdown',
 'interface Vlan3',
 '  - description switch_mgmt_10.0.4.0/24',
 '  - ip address 10.0.4.1 255.255.0.0',
 '  + description switch_mgmt_10.0.3.0/24',
 '  + ip address 10.0.3.1 255.255.0.0',
 '+ vlan 4',
 '  + name switch_mgmt_10.0.4.0/24',
 '+ interface Vlan4',
 '  + mtu 9000',
 '  + description switch_mgmt_10.0.4.0/24',
 '  + ip address 10.0.4.1 255.255.0.0',
 '  + ip access-group TEST in',
 '  + no shutdown']
>>>
```