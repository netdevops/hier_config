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

## load_driver_rules

**Description**:
Loads driver rules from a dictionary or YAML file into a platform driver.

**Arguments**:

    `options (Dict[str, Any] | str)`: A dictionary of rule options, or a file path to a YAML file.
    `platform (Platform)`: The Platform enum for the target platform.

**Returns**:

    `HConfigDriverBase`: A driver instance with the loaded rules.

**Example loading rules from a dictionary**:
```python
from hier_config import Platform
from hier_config.utils import load_driver_rules

options = {
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
driver = load_driver_rules(options, platform)
```

**Example loading rules from a file**:
```python
from hier_config import Platform
from hier_config.utils import load_driver_rules

platform = Platform.CISCO_IOS
driver = load_driver_rules("/path/to/options.yml", platform)
```

## load_tag_rules

**Description**:
Loads tag rules from a list of dictionaries or a YAML file into TagRule objects.

**Arguments**:

    `tags (List[Dict[str, Any]] | str)`: A list of dictionaries representing tag rules, or a file path to a YAML file.

**Returns**:

    `Tuple[TagRule, ...]`: A tuple of TagRule objects.

**Example loading tags from a dictionary**:
```python
from hier_config.utils import load_tag_rules

tags = load_tag_rules([
    {
        "lineage": [{"startswith": ["ip name-server", "ntp"]}],
        "add_tags": "ntp"
    }
])

print(tags)
```

**Example loading tags from a file**:
```python
from hier_config.utils import load_tag_rules

tags = load_tag_rules("path/to/tags.yml")

print(tags)
```