# Utilities

## read_text_from_file

**Description**:
Reads the contents of a file and loads its contents into memory.

**Arguments**:

    `file_path (str)`: The path to the device configuration file.

**Returns**:

    `str`: The contents of the file as a string.

**Example**:
```python
from hier_config.utils import read_text_from_file

device_config = read_text_from_file("path/to/device_config.txt")
print(device_config)
```

## load_hier_config_tags

**Description**:
Parses a YAML file containing configuration tags and converts them into a format compatible with Hier Config.

**Arguments**:

    `file_path (str)`: The path to the YAML file containing tag rules.

**Returns**:

    `List[Dict[str, Any]]`: A list of dictionaries representing tag rules.

**Example**:
```python
from hier_config.utils import load_hier_config_tags

tag_rules = load_hier_config_tags("path/to/tag_rules.yml")

print(tag_rules)
```

## Hier Config V2 to V3 Migration Utilities

Hier Config version 3 introduces breaking changes compared to version 2. These utilities are designed to help you transition seamlessly by enabling the continued use of version 2 configurations while you update your tooling to support the new version.

### hconfig_v2_os_v3_platform_mapper
**Description**:
Maps a Hier Config v2 OS name to a v3 Platform enumeration.

**Arguments**:

    `os_name (str)`: The name of the OS as defined in Hier Config v2.

**Returns**:

    `Platform`: The corresponding Platform enumeration for Hier Config v3.

**Raises**:

    `ValueError`: If the provided OS name is not supported in v2.

**Example**:
```python
from hier_config.utils import hconfig_v2_os_v3_platform_mapper

platform = hconfig_v2_os_v3_platform_mapper("ios")

print(platform)  # Output: <Platform.CISCO_IOS: '2'>
```

### hconfig_v3_platform_v2_os_mapper
**Description**:
Maps a Hier Config v3 Platform enumeration to a v2 OS name.

**Arguments**:

    `platform (Platform)`: A Platform enumeration from Hier Config v3.

**Returns**:

    `str`: The corresponding OS name for Hier Config v2.

**Raises**:

    `ValueError`: If the provided Platform is not supported in v3.

**Example**:
```python
from hier_config.utils import hconfig_v3_platform_v2_os_mapper

os_name = hconfig_v3_platform_v2_os_mapper(Platform.CISCO_IOS)
print(os_name)  # Output: "ios"
```

### load_hconfig_v2_options
**Description**:
Loads v2-style configuration options into a v3-compatible driver.

**Arguments**:

    `v2_options (Dict[str, Any])`: A dictionary of v2-style options.
    `platform (Platform)`: A Platform enumeration from Hier Config v3.

**Returns**:

    `HConfigDriverBase`: Hier Config Platform Driver.

**Example loading options from a dictionary**:
```python
from hier_config import Platform
from hier_config.utils import load_hconfig_v2_options

v2_options = {
    "negation": "no",
    "ordering": [{"lineage": [{"startswith": "ntp"}], "order": 700}],
    "per_line_sub": [{"search": "^!.*Generated.*$", "replace": ""}],
    "sectional_exiting": [
        {"lineage": [{"startswith": "router bgp"}], "exit_text": "exit"}
    ],
    "idempotent_commands": [{"lineage": [{"startswith": "interface"}]}],
    "negation_negate_with": [
        {
            "lineage": [
                {"startswith": "interface Ethernet"},
                {"startswith": "spanning-tree port type"},
            ],
            "use": "no spanning-tree port type",
        }
    ],
}
platform = Platform.CISCO_IOS
driver = load_hconfig_v2_options(v2_options, platform)

print(driver)
```

*Output*:
```
print(driver.rules)
full_text_sub=[] idempotent_commands=[IdempotentCommandsRule(match_rules=(MatchRule(equals=None, startswith='vlan', endswith=None, contains=None, re_search=None), MatchRule(equals=None, startswith='name', endswith=None, contains=None, re_search=None))), IdempotentCommandsRule(match_rules=(MatchRule(equals=None, startswith='interface ', endswith=None, contains=None, re_search=None), MatchRule(equals=None, startswith='description ', endswith=None, contains=None, re_search=None))), IdempotentCommandsRule(match_rules=(MatchRule(equals=None, startswith='interface ', endswith=None, contains=None, re_search=None), MatchRule(equals=None, startswith='ip address ', endswith=None, contains=None, re_search=None))), IdempotentCommandsRule(match_rules=(MatchRule(equals=None, startswith='interface ', endswith=None, contains=None, re_search=None), MatchRule(equals=None, startswith='switchport mode ', endswith=None, contains=None, re_search=None))), IdempotentCommandsRule(match_rules=(MatchRule(equals=None, startswith='interface ', endswith=None, contains=None, re_search=None), MatchRule(equals=None, startswith='authentication host-mode ', endswith=None, contains=None, re_search=None))), IdempotentCommandsRule(match_rules=(MatchRule(equals=None, startswith='interface ', endswith=None, contains=None, re_search=None), MatchRule(equals=None, startswith='authentication event server dead action authorize vlan ', endswith=None, contains=None, re_search=None))), IdempotentCommandsRule(match_rules=(MatchRule(equals=None, startswith='errdisable recovery interval ', endswith=None, contains=None, re_search=None),)), IdempotentCommandsRule(match_rules=(MatchRule(equals=None, startswith=None, endswith=None, contains=None, re_search='^(no )?logging console.*'),)), IdempotentCommandsRule(match_rules=(MatchRule(equals=None, startswith='interface', endswith=None, contains=None, re_search=None),))] idempotent_commands_avoid=[] indent_adjust=[] indentation=2 negation_default_when=[] negate_with=[NegationDefaultWithRule(match_rules=(MatchRule(equals=None, startswith='logging console ', endswith=None, contains=None, re_search=None),), use='logging console debugging'), NegationDefaultWithRule(match_rules=(MatchRule(equals=None, startswith='', endswith=None, contains=None, re_search=None),), use='no')] ordering=[OrderingRule(match_rules=(MatchRule(equals=None, startswith='interface', endswith=None, contains=None, re_search=None), MatchRule(equals=None, startswith='switchport mode ', endswith=None, contains=None, re_search=None)), weight=-10), OrderingRule(match_rules=(MatchRule(equals=None, startswith='no vlan filter', endswith=None, contains=None, re_search=None),), weight=200), OrderingRule(match_rules=(MatchRule(equals=None, startswith='interface', endswith=None, contains=None, re_search=None), MatchRule(equals=None, startswith='no shutdown', endswith=None, contains=None, re_search=None)), weight=200), OrderingRule(match_rules=(MatchRule(equals=None, startswith='aaa group server tacacs+ ', endswith=None, contains=None, re_search=None), MatchRule(equals=None, startswith='no server ', endswith=None, contains=None, re_search=None)), weight=10), OrderingRule(match_rules=(MatchRule(equals=None, startswith='no tacacs-server ', endswith=None, contains=None, re_search=None),), weight=10), OrderingRule(match_rules=(MatchRule(equals=None, startswith='ntp', endswith=None, contains=None, re_search=None),), weight=700)] parent_allows_duplicate_child=[] per_line_sub=[PerLineSubRule(search='^Building configuration.*', replace=''), PerLineSubRule(search='^Current configuration.*', replace=''), PerLineSubRule(search='^! Last configuration change.*', replace=''), PerLineSubRule(search='^! NVRAM config last updated.*', replace=''), PerLineSubRule(search='^ntp clock-period .*', replace=''), PerLineSubRule(search='^version.*', replace=''), PerLineSubRule(search='^ logging event link-status$', replace=''), PerLineSubRule(search='^ logging event subif-link-status$', replace=''), PerLineSubRule(search='^\\s*ipv6 unreachables disable$', replace=''), PerLineSubRule(search='^end$', replace=''), PerLineSubRule(search='^\\s*[#!].*', replace=''), PerLineSubRule(search='^ no ip address', replace=''), PerLineSubRule(search='^ exit-peer-policy', replace=''), PerLineSubRule(search='^ exit-peer-session', replace=''), PerLineSubRule(search='^ exit-address-family', replace=''), PerLineSubRule(search='^crypto key generate rsa general-keys.*$', replace=''), PerLineSubRule(search='^!.*Generated.*$', replace='')] post_load_callbacks=[<function _rm_ipv6_acl_sequence_numbers at 0x110e24e00>, <function _remove_ipv4_acl_remarks at 0x110e24ea0>, <function _add_acl_sequence_numbers at 0x110e24f40>] sectional_exiting=[SectionalExitingRule(match_rules=(MatchRule(equals=None, startswith='router bgp', endswith=None, contains=None, re_search=None), MatchRule(equals=None, startswith='template peer-policy', endswith=None, contains=None, re_search=None)), exit_text='exit-peer-policy'), SectionalExitingRule(match_rules=(MatchRule(equals=None, startswith='router bgp', endswith=None, contains=None, re_search=None), MatchRule(equals=None, startswith='template peer-session', endswith=None, contains=None, re_search=None)), exit_text='exit-peer-session'), SectionalExitingRule(match_rules=(MatchRule(equals=None, startswith='router bgp', endswith=None, contains=None, re_search=None), MatchRule(equals=None, startswith='address-family', endswith=None, contains=None, re_search=None)), exit_text='exit-address-family'), SectionalExitingRule(match_rules=(MatchRule(equals=None, startswith='router bgp', endswith=None, contains=None, re_search=None),), exit_text='exit')] sectional_overwrite=[] sectional_overwrite_no_negate=[]
```

**Example loading options from a file**:
```python
from hier_config import Platform
from hier_config.utils import load_hconfig_v2_options_from_file

platform = Platform.CISCO_IOS
driver = load_hconfig_v2_options("/path/to/options.yml", platform)
```

### load_hconfig_v2_tags
**Description**:
Converts v2-style tags into a tuple of TagRule Pydantic objects compatible with Hier Config v3.

**Arguments**:

    `v2_tags (List[Dict[str, Any]])`: A list of dictionaries representing v2-style tags.

**Returns**:

    `Tuple[TagRule, ...]`: A tuple of TagRule Pydantic objects.

**Example loading tags from a dictionary**:
```python
from hier_config.utils import load_hconfig_v2_tags

v3_tags = load_hconfig_v2_tags([
    {
        "lineage": [{"startswith": ["ip name-server", "ntp"]}],
        "add_tags": "ntp"
    }
])

print(v3_tags) # Output: (TagRule(match_rules=(MatchRule(equals=None, startswith=('ip name-server', 'ntp'), endswith=None, contains=None, re_search=None),), apply_tags=frozenset({'ntp'})),)
```

**Example loading tags from a file**:
```python
from hier_config.utils import load_hconfig_v2_tags_from_file

v3_tags = load_hconfig_v2_tags("path/to/v2_tags.yml")

print(v3_tags)
```