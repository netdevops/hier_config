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

## Available Config Interface Views

| **Property/Method**           | **Type**                       | **Description**                                                                                   |
|-------------------------------|--------------------------------|---------------------------------------------------------------------------------------------------|
| `bundle_id`                   | `Optional[str]`               | Retrieves the bundle ID of the interface.                                                        |
| `bundle_member_interfaces`    | `Iterable[str]`               | Lists the member interfaces of a bundle.                                                         |
| `bundle_name`                 | `Optional[str]`               | Retrieves the name of the bundle to which the interface belongs.                                  |
| `description`                 | `str`                         | Returns the description of the interface.                                                        |
| `dot1q_mode`                  | `Optional[InterfaceDot1qMode]`| Determines the 802.1Q mode based on VLAN tagging configuration.                                   |
| `duplex`                      | `InterfaceDuplex`             | Determines the duplex mode of the interface.                                                     |
| `enabled`                     | `bool`                        | Checks if the interface is enabled.                                                              |
| `has_nac`                     | `bool`                        | Determines if NAC (Network Admission Control) is configured on the interface.                    |
| `ipv4_interface`              | `Optional[IPv4Interface]`     | Retrieves the first configured IPv4 address and prefix.                                          |
| `ipv4_interfaces`             | `Iterable[IPv4Interface]`     | Lists all IPv4 addresses and prefixes configured on the interface.                               |
| `is_bundle`                   | `bool`                        | Indicates whether the interface is part of a bundle.                                             |
| `is_loopback`                 | `bool`                        | Checks if the interface is a loopback.                                                           |
| `is_subinterface`             | `bool`                        | Indicates if the interface is a subinterface.                                                    |
| `is_svi`                      | `bool`                        | Checks if the interface is a switched virtual interface (SVI).                                   |
| `module_number`               | `Optional[int]`               | Retrieves the module number of the interface.                                                    |
| `nac_control_direction_in`    | `bool`                        | Determines if NAC is configured with "control direction in".                                      |
| `nac_host_mode`               | `Optional[NACHostMode]`       | Retrieves the NAC host mode configuration.                                                       |
| `nac_mab_first`               | `bool`                        | Checks if NAC is configured for MAB (MAC Authentication Bypass) first.                           |
| `nac_max_dot1x_clients`       | `int`                         | Retrieves the maximum number of Dot1x clients allowed on the interface.                          |
| `nac_max_mab_clients`         | `int`                         | Retrieves the maximum number of MAB clients allowed on the interface.                            |
| `name`                        | `str`                         | Returns the name of the interface.                                                               |
| `native_vlan`                 | `Optional[int]`               | Retrieves the native VLAN of the interface.                                                      |
| `number`                      | `str`                         | Extracts the numeric portion of the interface name.                                              |
| `parent_name`                 | `Optional[str]`               | Retrieves the name of the parent bundle interface.                                               |
| `poe`                         | `bool`                        | Indicates if Power over Ethernet (PoE) is enabled on the interface.                              |
| `port_number`                 | `int`                         | Retrieves the port number of the interface.                                                      |
| `speed`                       | `Optional[tuple[int, ...]]`   | Lists the static speeds at which the interface can operate, in Mbps.                             |
| `subinterface_number`         | `Optional[int]`               | Retrieves the subinterface number.                                                               |
| `tagged_all`                  | `bool`                        | Checks if all VLANs are tagged on the interface.                                                 |
| `tagged_vlans`                | `tuple[int, ...]`             | Lists the VLANs that are tagged on the interface.                                                |
| `vrf`                         | `str`                         | Retrieves the VRF (Virtual Routing and Forwarding) associated with the interface.                |

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

## Example: Cisco IOS Config Interface View

### Step 1: Parse Configuration

Assume we have a Cisco IOS configuration file as a string.

```python
from hier_config import Platform, get_hconfig


raw_config = """
interface GigabitEthernet0/1
 description Uplink to Switch
 switchport access vlan 10
 switchport mode access
 ip address 192.168.1.1 255.255.255.0
 shutdown
!
interface GigabitEthernet0/2
 switchport trunk allowed vlan 20,30,40
 switchport mode trunk
!
"""

hconfig = get_hconfig(Platform.CISCO_IOS, raw_config)
```

### Step 2: Create Config View and Access Interface Views

```python
from hier_config.platforms.cisco_ios.view import HConfigViewCiscoIOS

config_view = HConfigViewCiscoIOS(hconfig)
```

### Step 3: Access Interface Details

Access properties and methods to interact with individual interface configurations programmatically:

**Retrieve Interface Properties**

#### Loop through all interface views and display their properties

```python
for interface_view in config_view.interface_views:
    print(f"Interface Name: {interface_view.name}")
    print(f"Description: {interface_view.description}")
    print(f"Enabled: {interface_view.enabled}")
    print(f"Dot1Q Mode: {interface_view.dot1q_mode}")
    print(f"Native VLAN: {interface_view.native_vlan}")
    print(f"Tagged VLANs: {interface_view.tagged_vlans}")
    print(f"IP Address: {interface_view.ipv4_interface}")
    print(f"Is Subinterface: {interface_view.is_subinterface}")
    print("-" * 40)
```

**Example Output:**

```
Interface Name: GigabitEthernet0/1
Description: Uplink to Switch
Enabled: False
Dot1Q Mode: InterfaceDot1qMode.ACCESS
Native VLAN: 10
Tagged VLANs: ()
IP Address: 192.168.1.1/24
Is Subinterface: False
----------------------------------------
Interface Name: GigabitEthernet0/2
Description: None
Enabled: True
Dot1Q Mode: InterfaceDot1qMode.TAGGED
Native VLAN: None
Tagged VLANs: (20, 30, 40)
IP Address: None
Is Subinterface: False
----------------------------------------
```
