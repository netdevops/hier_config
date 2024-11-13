# Advanced Topics

## MatchRules

MatchRules, written in YAML, help users identify either highly specific sections or more generalized lines within a configuration. For instance, if you want to target interface descriptions, you could set up MatchRules as follows:

```yaml
- match_rules:
  - startswith: interface
  - startswith: description
```

This setup directs hier_config to search for configuration lines that begin with `interface` and, under each interface, locate lines that start with `description`​​.

With MatchRules, you can specify the level of detail needed, whether focusing on general configuration lines or diving into specific subsections. For example, to check for the presence or absence of HTTP, SSH, SNMP, and logging commands in a configuration, you could use a single rule as follows:

```yaml
- match_rules:
  - startswith:
    - ip ssh
    - no ip ssh
    - ip http
    - no ip http
    - snmp-server
    - no snmp-server
    - logging
    - no logging
```

This rule will look for configuration lines that start with any of the listed keywords​.

To check whether BGP IPv4 AFIs (Address Family Identifiers) are activated, you can use the following rule:

```yaml
- match_rules:
  - startswith: router bgp
  - startswith: address-family ipv4
  - endswith: activate
```

In this example, the `activate` keyword is used to identify active BGP neighbors. Available keywords for MatchRules include:
- startswith
- endswith
- contains
- equals
- re_search (for regular expressions)

These options allow you to target configuration lines with precision based on the desired pattern​.

You can also combine the previous examples into a single set of MatchRules, like this:

```yaml
- match_rules:
  - startswith: interface
  - startswith: description
- match_rules:
  - startswith:
    - ip ssh
    - no ip ssh
    - ip http
    - no ip http
    - snmp-server
    - no snmp-server
    - logging
    - no logging
- match_rules:
  - startswith: router bgp
  - startswith: address-family ipv4
  - endswith: activate
```

When `hier_config` processes MatchRules, it treats each as a separate rule, evaluating them individually to match the specified configuration patterns​.

## Working with Tags

With a solid understanding of MatchRules, you can unlock more advanced capabilities in `hier_config`, such as tagging specific configuration sections to control remediation output based on tags. This feature is particularly useful during maintenance, allowing you to focus on low-risk changes or isolate high-risk changes for detailed inspection.

Tagging builds on MatchRules by adding the **apply_tags** keyword to target specific configurations.

For example, suppose your running configuration contains an NTP server setup like this:

```text
ntp server 192.0.2.1 prefer version 2
```

But your intended configuration uses publicly available NTP servers:

```text
ip name-server 1.1.1.1
ip name-server 8.8.8.8
ntp server time.nist.gov
```

You can create a MatchRule to tag this specific remediation with "ntp" as follows:

```yaml
- match_rules:
  - startswith:
    - ip name-server
    - no ip name-server
    - ntp
    - no ntp
  apply_tags: [ntp]
```

With the tags loaded, you can create a targeted remediation based on those tags as follows:

```python
#!/usr/bin/env python3

# Import necessary libraries
import yaml
from pydantic import TypeAdapter
from hier_config import WorkflowRemediation, get_hconfig
from hier_config.model import Platform, TagRule

# Load the running and generated configurations from files
with open("./tests/fixtures/running_config.conf") as f:
    running_config = f.read()

with open("./tests/fixtures/generated_config.conf") as f:
    generated_config = f.read()

# Load tag rules from a file
with open("./tests/fixtures/tag_rules_ios.yml") as f:
    tags = yaml.safe_load(f)

# Validate and format tags using the TagRule model
tags = TypeAdapter(tuple[TagRule, ...]).validate_python(tags)

# Initialize a WorkflowRemediation object with the running and intended configurations
wfr = WorkflowRemediation(
    running_config=get_hconfig(Platform.CISCO_IOS, running_config),
    generated_config=get_hconfig(Platform.CISCO_IOS, generated_config)
)

# Apply the tag rules to filter remediation steps by tags
wfr.apply_remediation_tag_rules(tags)

# Generate the remediation steps
wfr.remediation_config

# Display remediation steps filtered to include only the "ntp" tag
print(wfr.remediation_config_filtered_text(include_tags={"ntp"}, exclude_tags={}))
```

The resulting remediation output appears as follows:

```text
no ntp server 192.0.2.1 prefer version 2
ip name-server 1.1.1.1
ip name-server 8.8.8.8
ntp server time.nist.gov
```

## Drivers

## Custom hier_config Workflows

Coming soon...
