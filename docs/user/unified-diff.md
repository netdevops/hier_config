# Unified Diffs

This page covers `HConfig.unified_diff()`, which produces `difflib`-style diff output with awareness of out-of-order lines and parent-child relationships. Use it to compare two configurations for reporting or validation — without generating remediation commands.

This is particularly useful when comparing configurations from two network devices, such as redundant pairs, or when validating differences between running and intended configurations.

> **Note:** The algorithm does not account for duplicate child entries (e.g., multiple `endif` statements in an IOS XR route-policy) or enforce command order in sections where it may be critical, such as access control lists (ACLs). For accurate ordering in ACLs, use sequence numbers.

```python
>>> from hier_config import HConfig, Platform
>>> from hier_config.utils import read_text_from_file
>>> from pprint import pprint
>>>
>>> running_config_text = read_text_from_file("./tests/fixtures/running_config.conf")
>>> generated_config_text = read_text_from_file("./tests/fixtures/generated_config.conf")
>>>
>>> running_config = HConfig.from_text(Platform.CISCO_IOS, running_config_text)
>>> generated_config = HConfig.from_text(Platform.CISCO_IOS, generated_config_text)
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

Lines prefixed with `+` are present in `generated_config` but not in `running_config`; lines prefixed with `-` are present in `running_config` but not in `generated_config`. Parent lines without a prefix are shown as context only.

## Next steps

- [Remediation Workflows](remediation-workflows.md) — turn differences into deployable commands.
- [Predicting Future Configs](future-config.md) — simulate the post-change configuration instead of diffing.
