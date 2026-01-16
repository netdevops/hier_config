# Unused Object Remediation

## Overview

The unused object remediation feature automatically identifies and generates removal commands for configuration objects that are defined but not referenced anywhere in the configuration. This helps maintain clean, efficient configurations by removing unnecessary ACLs, prefix-lists, route-maps, and other objects.

## Supported Object Types

The system supports detection and removal of the following object types:

### Cisco IOS / IOS-XE / Arista EOS

- **IPv4 ACLs** (`ipv4-acl`): Standard and extended access lists
- **IPv6 ACLs** (`ipv6-acl`): IPv6 access lists
- **Prefix Lists** (`prefix-list`): IPv4 prefix lists
- **IPv6 Prefix Lists** (`ipv6-prefix-list`): IPv6 prefix lists
- **Route Maps** (`route-map`): Routing policy configurations
- **Class Maps** (`class-map`): QoS classification rules
- **Policy Maps** (`policy-map`): QoS policy configurations
- **VRFs** (`vrf`): Virtual routing and forwarding instances
- **IPv6 General Prefixes** (`ipv6-general-prefix`): IPv6 general prefix definitions (EOS)

### Cisco NX-OS

All of the above, plus:

- **Object Groups** (`object-group`): Address and service object groups

### Cisco IOS-XR

- **IPv4 ACLs** (`ipv4-acl`): IPv4 access lists
- **IPv6 ACLs** (`ipv6-acl`): IPv6 access lists
- **Prefix Sets** (`prefix-set`): IPv4/IPv6 prefix sets
- **AS Path Sets** (`as-path-set`): BGP AS path match sets
- **Community Sets** (`community-set`): BGP community match sets
- **Route Policies** (`route-policy`): Routing policy configurations
- **Class Maps** (`class-map`): QoS classification rules
- **Policy Maps** (`policy-map`): QoS policy configurations
- **VRFs** (`vrf`): Virtual routing and forwarding instances

## Usage

### Basic Usage with WorkflowRemediation

The most common way to use this feature is through the `WorkflowRemediation` class:

```python
from hier_config import get_hconfig, WorkflowRemediation
from hier_config.models import Platform

# Load running configuration
running_config = get_hconfig(Platform.CISCO_IOS, running_config_text)

# Load generated/target configuration
generated_config = get_hconfig(Platform.CISCO_IOS, generated_config_text)

# Create workflow
workflow = WorkflowRemediation(running_config, generated_config)

# Generate cleanup configuration for all unused objects
cleanup = workflow.unused_object_remediation()

# Output cleanup commands
for line in cleanup.all_children_sorted():
    print(line.cisco_style_text())
```

### Selective Cleanup

Clean up only specific object types:

```python
# Only remove unused ACLs and prefix-lists
cleanup = workflow.unused_object_remediation(
    object_types=["ipv4-acl", "prefix-list"]
)
```

### Direct Driver Access

Use the driver directly for analysis without remediation:

```python
from hier_config import get_hconfig
from hier_config.models import Platform

config = get_hconfig(Platform.CISCO_IOS, config_text)

# Analyze unused objects
analysis = config.driver.find_unused_objects(config)

# Review results
print(f"Total unused objects: {analysis.total_unused}")
for object_type, objects in analysis.unused_objects.items():
    print(f"\n{object_type}:")
    for obj in objects:
        print(f"  - {obj.name} at {' -> '.join(obj.definition_location)}")
```

### Combining with Standard Remediation

Combine unused object cleanup with standard configuration remediation:

```python
from hier_config import get_hconfig, WorkflowRemediation
from hier_config.models import Platform

running_config = get_hconfig(Platform.CISCO_IOS, running_config_text)
generated_config = get_hconfig(Platform.CISCO_IOS, generated_config_text)

workflow = WorkflowRemediation(running_config, generated_config)

# Get standard remediation (to match generated config)
standard_remediation = workflow.remediation_config

# Get cleanup remediation (to remove unused objects)
cleanup_remediation = workflow.unused_object_remediation()

# Combine both into a single configuration
combined = get_hconfig(Platform.CISCO_IOS, "")
combined.merge(standard_remediation)

# Add cleanup commands that don't conflict
for child in cleanup_remediation.all_children():
    if not combined.children.get(child.text):
        combined.add_shallow_copy_of(child)

# Output combined remediation
for line in combined.all_children_sorted():
    print(line.cisco_style_text())
```

## How It Works

### Detection Process

1. **Find Definitions**: Scans the configuration for object definitions using pattern matching rules
2. **Find References**: Searches for references to those objects throughout the configuration
3. **Identify Unused**: Compares definitions to references to find objects with zero references
4. **Generate Removal Commands**: Creates properly formatted removal commands for unused objects

### Reference Detection

The system looks for object references in multiple contexts:

#### ACL References
- Interface applications (`ip access-group`)
- Line VTY applications (`access-class`)
- Class map matches (`match access-group`)
- Crypto map references (`match address`)
- Route map matches (`match ip address`)
- NAT configurations (`ip nat`)
- VACL applications (NX-OS)

#### Prefix List References
- Route map matches (`match ip address prefix-list`)
- BGP neighbor filters (`neighbor prefix-list`)

#### Route Map References
- BGP neighbor policies (`neighbor route-map`)
- Redistribution policies (`redistribute route-map`)
- Policy-based routing (`ip policy route-map`)
- VRF import/export maps (`import/export map`)

#### Class Map References
- Policy map classes (`class`)
- Control plane policies (`service-policy`)

#### Policy Map References
- Interface service policies (`service-policy`)
- Control plane policies (`service-policy`)
- Hierarchical QoS (policy within policy)

#### VRF References
- Interface VRF membership (`vrf forwarding`, `vrf member`, `vrf`)
- BGP VRF instances (`address-family vrf`)

### Removal Ordering

Objects are removed in a specific order (controlled by `removal_order_weight`) to avoid dependency issues:

1. **Policy Maps** (weight 110) - Removed first
2. **Class Maps** (weight 120)
3. **Route Maps** (weight 130)
4. **Prefix Lists / AS Path Sets / Community Sets** (weight 140)
5. **ACLs / Object Groups** (weight 150)
6. **VRFs** (weight 200) - Removed last (highest impact)

## Case Sensitivity

Different platforms handle case sensitivity differently:

- **Cisco IOS / EOS**: Case-insensitive (ACL "MY_ACL" matches reference "my_acl")
- **Cisco IOS-XR**: Case-sensitive (ACL "MY_ACL" ≠ reference "my_acl")
- **Cisco NX-OS**: Case-insensitive

The system automatically handles case sensitivity based on the platform.

## Examples

### Example 1: Remove Unused ACLs

**Running Configuration:**
```
ip access-list extended UNUSED_ACL
 permit ip any any
ip access-list extended USED_ACL
 deny ip any any
interface GigabitEthernet0/1
 ip access-group USED_ACL in
```

**Output:**
```
no ip access-list extended UNUSED_ACL
```

### Example 2: Remove Multiple Object Types

**Running Configuration:**
```
ip access-list extended UNUSED_ACL
 permit ip any any
ip prefix-list UNUSED_PL seq 5 permit 0.0.0.0/0
route-map UNUSED_RM permit 10
```

**Output:**
```
no ip access-list extended UNUSED_ACL
no ip prefix-list UNUSED_PL
no route-map UNUSED_RM
```

### Example 3: Complex Dependency Scenario

**Running Configuration:**
```
ip access-list extended ACL1
 permit ip any any
ip prefix-list PL1 seq 5 permit 10.0.0.0/8
route-map RM1 permit 10
 match ip address ACL1
 match ip address prefix-list PL1
router bgp 65000
 neighbor 10.0.0.1 route-map RM1 in
```

**Result:** No objects are removed because:
- ACL1 is referenced by RM1
- PL1 is referenced by RM1
- RM1 is referenced by BGP neighbor

### Example 4: Platform-Specific Objects (IOS-XR)

**Running Configuration:**
```
prefix-set UNUSED_PS
  10.0.0.0/8
end-set
as-path-set UNUSED_AS
  ios-regex '_100$'
end-set
route-policy RP1
  if destination in USED_PS then
    pass
  endif
end-policy
```

**Output:**
```
no prefix-set UNUSED_PS
no as-path-set UNUSED_AS
```

## Extending for Custom Objects

To add support for new object types, extend the driver's `unused_object_rules`:

```python
from hier_config.models import UnusedObjectRule, ReferencePattern, MatchRule
from hier_config.platforms.cisco_ios.driver import HConfigDriverCiscoIOS
from hier_config.platforms.driver_base import HConfigDriverRules

class CustomIOSDriver(HConfigDriverCiscoIOS):
    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        base_rules = HConfigDriverCiscoIOS._instantiate_rules()

        # Add custom object rule
        custom_rules = [
            UnusedObjectRule(
                object_type="my-custom-object",
                definition_match=(
                    MatchRule(startswith="my-object "),
                ),
                reference_patterns=(
                    ReferencePattern(
                        match_rules=(
                            MatchRule(startswith="apply my-object "),
                        ),
                        extract_regex=r"apply my-object\s+(\S+)",
                        reference_type="application",
                    ),
                ),
                removal_template="no my-object {name}",
                removal_order_weight=100,
                case_sensitive=False,
            ),
        ]

        # Combine with base rules
        base_rules.unused_object_rules.extend(custom_rules)
        return base_rules
```

## Safety Considerations

### What the System Does

- ✅ Identifies objects with **zero** direct references
- ✅ Follows proper removal ordering to avoid dependency issues
- ✅ Generates syntactically correct removal commands
- ✅ Respects platform-specific case sensitivity

### What the System Does NOT Do

- ❌ Detect runtime-only references (e.g., objects referenced by device features not in config)
- ❌ Validate that removal is operationally safe
- ❌ Consider default/implicit object applications
- ❌ Detect indirect references through variables or automation systems

### Recommendations

1. **Test in lab first**: Always test cleanup commands in a non-production environment
2. **Review before applying**: Manually review all removal commands before execution
3. **Use version control**: Save configurations before and after cleanup
4. **Gradual rollout**: Clean up one object type at a time
5. **Monitor impact**: Watch for any operational issues after cleanup

## API Reference

### WorkflowRemediation.unused_object_remediation()

```python
def unused_object_remediation(
    self,
    object_types: Iterable[str] | None = None,
) -> HConfig:
    """Generates remediation to remove unused objects from running_config.

    Args:
        object_types: Specific object types to clean up (None = all types)

    Returns:
        HConfig with removal commands, sorted by removal order weight
    """
```

### HConfigDriverBase.find_unused_objects()

```python
def find_unused_objects(self, config: HConfig) -> UnusedObjectAnalysis:
    """Finds unused objects in a configuration.

    Args:
        config: The configuration to analyze

    Returns:
        UnusedObjectAnalysis with detailed information about all objects
    """
```

### UnusedObjectRemediator

```python
from hier_config.remediation import UnusedObjectRemediator

remediator = UnusedObjectRemediator(config)
analysis = remediator.analyze()
```

#### UnusedObjectAnalysis Model

```python
class UnusedObjectAnalysis:
    defined_objects: dict[str, tuple[UnusedObjectDefinition, ...]]
    referenced_objects: dict[str, tuple[UnusedObjectReference, ...]]
    unused_objects: dict[str, tuple[UnusedObjectDefinition, ...]]
    total_defined: int
    total_unused: int
    removal_commands: tuple[str, ...]
```

## Troubleshooting

### Object Not Detected as Unused

**Problem**: An object you expect to be unused is not being flagged.

**Possible Causes**:
1. The object has a reference that wasn't detected
2. The reference pattern doesn't match the actual reference syntax
3. Case sensitivity mismatch

**Solution**: Use the analysis API to inspect references:

```python
analysis = config.driver.find_unused_objects(config)
refs = analysis.referenced_objects.get("ipv4-acl", ())
for ref in refs:
    if ref.name == "MY_ACL":
        print(f"Found reference at: {' -> '.join(ref.reference_location)}")
        print(f"Reference type: {ref.reference_type}")
```

### Incorrect Removal Command

**Problem**: The removal command syntax is incorrect for your platform.

**Solution**: The removal template may need adjustment for your platform's specific syntax. Check the driver's `unused_object_rules` and update the `removal_template`.

### Object Detected as Unused But Is Actually Used

**Problem**: An object is flagged as unused but is actually referenced.

**Possible Causes**:
1. Reference is in a location not covered by reference patterns
2. Dynamic/runtime reference not visible in static configuration
3. Reference uses non-standard syntax

**Solution**: Add additional reference patterns to cover the missing location.

## Performance Considerations

The unused object detection performs a full scan of the configuration:

- **Time Complexity**: O(n × m) where n = config lines, m = reference patterns
- **Memory**: Minimal - works with configuration tree structure
- **Caching**: Analysis results are not cached; rerun for updated configs

For large configurations (>10,000 lines), analysis typically completes in under 1 second.
