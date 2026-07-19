# Config Views

This page covers config views — a typed, Pythonic layer for extracting structured data (hostnames, interfaces, VLANs, IP addresses) from a parsed configuration without writing regex. Use it when you need to *read* facts out of a config rather than remediate it.

A config view wraps an `HConfig` tree and exposes Python properties in a platform-independent way: the framework combines abstract base classes (`HConfigViewBase`, `ConfigViewInterfaceBase`) with platform-specific implementations (e.g. `HConfigViewCiscoIOS`, `ConfigViewInterfaceCiscoIOS`) so the same code works across vendors.

## Why use config views?

1. **Vendor abstraction:** devices from different vendors have varied configuration formats; views standardize access across platforms.
2. **Simplified interface:** structured properties instead of hand-rolled text parsing.
3. **Extensibility:** support new platforms by implementing platform-specific subclasses.
4. **Error reduction:** parsing logic is encapsulated and tested once.

## Getting a view

Use `get_hconfig_view()`; it instantiates the view class declared by the config's driver:

```python
from hier_config import HConfig, Platform, get_hconfig_view

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

hconfig = HConfig.from_text(Platform.CISCO_IOS, raw_config)
config_view = get_hconfig_view(hconfig)
```

Platforms without a view raise `DriverNotFoundError`. Views are currently provided for Cisco IOS, Arista EOS, Cisco NX-OS, Cisco IOS XR, and HP ProCurve. (You can also import a platform view class directly, e.g. `from hier_config.platforms.cisco_ios.view import HConfigViewCiscoIOS`.)

## The capability mixin model

`ConfigViewInterfaceBase` carries only the core interface properties that every platform supports. Optional capabilities are modeled as mixins that a platform view inherits *only when it genuinely supports them*:

- `InterfaceBundleViewMixin` — bundle / port-channel properties (`bundle_id`, `bundle_name`, `bundle_member_interfaces`, `is_bundle`).
- `InterfaceVlanViewMixin` — 802.1Q VLAN properties (`native_vlan`, `tagged_vlans`, `tagged_all`, `dot1q_mode`).
- `InterfaceNACViewMixin` — NAC properties (`has_nac`, `nac_host_mode`, `nac_mab_first`, ...).
- `InterfacePhysicalViewMixin` — physical-layer properties (`duplex`, `speed`, `poe`, `module_number`).

Check whether an interface view supports a capability with `isinstance()`:

```python
from hier_config import InterfaceVlanViewMixin

for interface_view in config_view.interface_views:
    if isinstance(interface_view, InterfaceVlanViewMixin):
        print(interface_view.name, interface_view.native_vlan)
```

Current platform capabilities: Cisco IOS and HP ProCurve inherit all four mixins; Arista EOS, Cisco NX-OS, and Cisco IOS XR inherit the bundle and VLAN mixins.

## Device-level view properties

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

## Interface view properties

### Core properties (`ConfigViewInterfaceBase` — all platforms)

| **Property** | **Type** | **Description** |
|--------------|----------|-----------------|
| `name` | `str` | The name of the interface (e.g. `GigabitEthernet0/1`). |
| `number` | `str` | The numeric portion of the interface name. |
| `description` | `str` | The configured description of the interface. |
| `enabled` | `bool` | `True` if the interface is not shut down. |
| `ipv4_interface` | `Optional[IPv4Interface]` | The first configured IPv4 address and prefix. |
| `ipv4_interfaces` | `Iterable[IPv4Interface]` | All IPv4 addresses and prefixes configured on the interface. |
| `vrf` | `str` | The VRF associated with the interface. |
| `is_loopback` | `bool` | `True` if the interface is a loopback. |
| `is_subinterface` | `bool` | `True` if the interface is a subinterface (e.g. `Gi0/1.100`). |
| `is_svi` | `bool` | `True` if the interface is a switched virtual interface (SVI / VLAN interface). |
| `parent_name` | `Optional[str]` | The parent interface name of a subinterface. |
| `port_number` | `int` | The port number of the interface. |
| `subinterface_number` | `Optional[int]` | The subinterface number, if applicable. |

### Bundle / port-channel (`InterfaceBundleViewMixin`)

| **Property** | **Type** | **Description** |
|--------------|----------|-----------------|
| `is_bundle` | `bool` | `True` if the interface is a bundle (port-channel / LAG). |
| `bundle_id` | `Optional[str]` | The bundle ID of the interface. |
| `bundle_name` | `Optional[str]` | The name of the bundle to which the interface belongs. |
| `bundle_member_interfaces` | `Iterable[str]` | The member interfaces of a bundle. |

### VLAN and 802.1Q (`InterfaceVlanViewMixin`)

| **Property** | **Type** | **Description** |
|--------------|----------|-----------------|
| `dot1q_mode` | `Optional[InterfaceDot1qMode]` | The 802.1Q mode (`ACCESS`, `TAGGED`, `TAGGED_ALL`, ...) based on VLAN tagging configuration. |
| `native_vlan` | `Optional[int]` | The native VLAN of the interface. |
| `tagged_vlans` | `tuple[int, ...]` | The VLANs that are tagged on the interface. |
| `tagged_all` | `bool` | `True` if all VLANs are tagged on the interface. |

### NAC (`InterfaceNACViewMixin`)

| **Property** | **Type** | **Description** |
|--------------|----------|-----------------|
| `has_nac` | `bool` | `True` if NAC is configured on the interface. |
| `nac_control_direction_in` | `bool` | `True` if NAC is configured with `control direction in`. |
| `nac_host_mode` | `Optional[NACHostMode]` | The NAC host mode (`SINGLE_HOST`, `MULTI_AUTH`, ...). |
| `nac_mab_first` | `bool` | `True` if NAC tries MAB (MAC Authentication Bypass) before 802.1X. |
| `nac_max_dot1x_clients` | `int` | Maximum number of 802.1X clients allowed on the interface. |
| `nac_max_mab_clients` | `int` | Maximum number of MAB clients allowed on the interface. |

### Physical layer (`InterfacePhysicalViewMixin`)

| **Property** | **Type** | **Description** |
|--------------|----------|-----------------|
| `duplex` | `InterfaceDuplex` | The duplex mode of the interface (`FULL`, `HALF`, `AUTO`). |
| `speed` | `Optional[tuple[int, ...]]` | The static speeds (in Mbps) at which the interface can operate. |
| `poe` | `bool` | `True` if Power over Ethernet (PoE) is enabled on the interface. |
| `module_number` | `Optional[int]` | The module number of the interface. |

## Example: device-level access

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

## Example: interface-level access

```python
from hier_config import HConfig, Platform, get_hconfig_view

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

hconfig = HConfig.from_text(Platform.CISCO_IOS, raw_config)
config_view = get_hconfig_view(hconfig)

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

Example output:

```text
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

## Next steps

- [Creating a Platform Driver](../dev/creating-drivers.md#adding-a-config-view) — implement a view for a new platform with the mixin model.
- [API Reference](../dev/api-reference.md) — full view base-class documentation.
