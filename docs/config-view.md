# Config View

A Config View is an abstraction layer for network device configurations. It provides a structured, Pythonic way to interact with and extract information from raw configuration data. Config Views are especially useful for standardizing how configuration elements are accessed across different platforms and devices.

The framework uses a combination of abstract base classes (e.g., `ConfigViewInterfaceBase`, `HConfigViewBase`) and platform-specific implementations (e.g., `ConfigViewInterfaceCiscoIOS`, `HConfigViewCiscoIOS`) to provide a unified interface for interacting with configurations while accounting for the unique syntax and semantics of each vendor or platform.

## Why Use Config Views?

1. **Vendor Abstraction:** Network devices from different vendors (Cisco, Arista, Juniper, etc.) have varied configuration formats. Config Views standardize access, making it easier to work across platforms.

2. **Simplified Interface:** Accessing configuration data becomes more intuitive through Python properties and methods rather than manually parsing text.

3. **Extensibility:** Easily extendable to support new platforms or devices by implementing platform-specific subclasses.

4. **Error Reduction:** Encapsulates parsing logic, reducing the risk of errors due to configuration syntax differences.

## Available Config Views

| **Property/Method**         | **Type**                       | **Description**                                                              |
|-----------------------------|--------------------------------|------------------------------------------------------------------------------|
| `bundle_interface_views`    | `Iterable`                    | Yields interfaces configured as bundles.                                    |
| `config`                    | `HConfig`                     | Root configuration object.                                                  |
| `dot1q_mode_from_vlans`     | `Callable`                    | Determines 802.1Q mode based on VLANs and tagging.                          |
| `hostname`                  | `Optional[str]`               | Retrieves the device hostname.                                              |
| `interface_names_mentioned` | `frozenset[str]`              | Set of all interface names mentioned.                                       |
| `interface_view_by_name`    | `Callable`                    | Returns view of a specific interface by name.                               |
| `interface_views`           | `Iterable`                    | Yields all interface views.                                                 |
| `interfaces`                | `Iterable[HConfigChild]`      | Yields raw configuration objects for all interfaces.                        |
| `interfaces_names`          | `Iterable[str]`               | Yields the names of all interfaces.                                         |
| `ipv4_default_gw`           | `Optional[IPv4Address]`       | Retrieves the IPv4 default gateway.                                         |
| `location`                  | `str`                         | Returns the SNMP location.                                                  |
| `module_numbers`            | `Iterable[int]`               | Yields module numbers from interfaces.                                      |
| `stack_members`             | `Iterable[StackMember]`       | Yields stack members configured on the device.                              |
| `vlan_ids`                  | `frozenset[int]`              | Set of VLAN IDs configured.                                                 |
| `vlans`                     | `Iterable[Vlan]`              | Yields VLAN objects, including ID and name.                                 |

## Example: Cisco IOS Config View

### Step 1: Parse Configuration

Assume we have a Cisco IOS configuration file as a string.

```python
from hier_config import Platform, get_hconfig


raw_config = """
hostname router1
interface GigabitEthernet0/1
 description Uplink to Switch
 switchport access vlan 10
 ip address 192.168.1.1 255.255.255.0
 shutdown
!
vlan 10
 name DATA
"""

hconfig = get_hconfig(Platform.CISCO_IOS, raw_config)
```

### Step 2: Create Config View

```python
from hier_config.platforms.cisco_ios.view import HConfigViewCiscoIOS


config_view = HConfigViewCiscoIOS(hconfig)
```

### Step 3: Access Configuration Details

Access properties to interact with the configuration programmatically:

```python
# Get the hostname
print(config_view.hostname)  # Output: router1

# List all interface names
print(list(config_view.interfaces_names))  # Output: ['GigabitEthernet0/1']

# Check if an interface is enabled
for interface_view in config_view.interface_views:
    print(interface_view.name, "Enabled:", interface_view.enabled)

# Get all VLANs
for vlan in config_view.vlans:
    print(f"VLAN {vlan.id}: {vlan.name}")

```