# Creating Custom Workflows

Certain scenarios demand remediation strategies that go beyond the standard negation and idempotency workflows Hier Config is designed to handle. To address these edge cases, Hier Config allows for custom remediation workflows that integrate seamlessly with the existing remediation process.

----

## Building a Remediation Workflow

1. Importing Modules and Loading Configurations

Start by importing the necessary modules and loading the running and intended configurations for comparison.

```python
from hier_config import WorkflowRemediation, get_hconfig, Platform
from hier_config.utils import read_text_from_file
```

Load the configurations from files:

```python
running_config = read_text_from_file("./tests/fixtures/running_config_acl.conf")
generated_config = read_text_from_file("./tests/fixtures/generated_config_acl.conf")
```

These configurations represent the current and desired states of the device.

----

2. Initializing the Workflow Remediation Object:

Initialize the WorkflowRemediation object for a Cisco IOS platform:


```python
wfr = WorkflowRemediation(
        running_config=get_hconfig(Platform.CISCO_IOS, running_config),
        generated_config=get_hconfig(Platform.CISCO_IOS, generated_config)
)
```
This object manages the remediation workflow between the running and generated configurations.

----

## Extracting and Analyzing Remediation Sections

### Example: Access-List Custom Remediation

**Current (Running) Configuration**

```python
print(wfr.running_config.get_child(startswith="ip access-list"))
```

Output:

```
ip access-list extended TEST
  12 permit ip 10.0.0.0 0.0.0.7 any
  exit
```

**Intended (Generated) Configuration**

```python
print(wfr.generated_config.get_child(startswith="ip access-list"))
```

Output:

```
ip access-list extended TEST
  10 permit ip 10.0.1.0 0.0.0.255 any
  20 permit ip 10.0.0.0 0.0.0.7 any
  exit
```

**Default Remediation Configuration**

```python
print(wfr.remediation_config.get_child(startswith="ip access-list"))
```

Output:

```
ip access-list extended TEST
  no 12 permit ip 10.0.0.0 0.0.0.7 any
  10 permit ip 10.0.1.0 0.0.0.255 any
  20 permit ip 10.0.0.0 0.0.0.7 any
  exit
```

#### Issues with the Default Remediation:

1. **Invalid Command:** `no 12 permit ip 10.0.0.0 0.0.0.7 any` is invalid in Cisco IOS. The valid command is `no 12`.
2. **Risk of Lockout:** Removing a line currently matched by traffic could cause a connectivity outage.
3. **Unnecessary Changes:** `permit ip 10.0.0.0 0.0.0.7 any` is a valid line aside from sequence numbers. In large ACLs, this might be unnecessary to delete and re-add.

----

#### Goals for Safe Access-List Remediation

To avoid outages during production changes:

1. **Resequence the ACL:** Adjust sequence numbers using the ip access-list resequence command.
    * For demonstration, resequence to align 12 to 20.
1. **Temporary Allow-All:** Add a temporary rule (1 permit ip any any) to prevent lockouts.
1. **Cleanup:** Remove the temporary rule (no 1) after applying the changes.

----

## Building the Custom Remediation

1. Create a Custom `HConfig` Object

```python
from hier_config import HConfig

custom_remediation = HConfig(wfr.running_config.driver)
```

2. Add Resequencing and Extract ACL Remediation

```python
custom_remediation.add_child("ip access-list resequence TEST 10 10")
custom_remediation.add_child("ip access-list extended TEST")
remediation = wfr.remediation_config.get_child(equals="ip access-list extended TEST")
```

3. Build the Custom ACL Remediation

```python
acl = custom_remediation.get_child(equals="ip access-list extended TEST")
acl.add_child("1 permit ip any any")  # Temporary allow-all

for line in remediation.all_children():
    if line.text.startswith("no "):
        # Adjust invalid sequence negation
        parts = line.text.split()
        rounded_number = round(int(parts[1]), -1)
        acl.add_child(f"{parts[0]} {rounded_number}")
    else:
        acl.add_child(line.text)

acl.add_child("no 1")  # Cleanup temporary rule
```

### Output of Custom Remediation

```python
print(custom_remediation)
```

Output:

```
ip access-list resequence TEST 10 10
ip access-list extended TEST
  1 permit ip any any
  no 10
  10 permit ip 10.0.1.0 0.0.0.255 any
  20 permit ip 10.0.0.0 0.0.0.7 any
  no 1
  exit
```

## Applying the Custom Remediation

### Remove Invalid Remediation

```python
invalid_remediation = wfr.remediation_config.get_child(equals="ip access-list extended TEST")
wfr.remediation_config.delete_child(invalid_remediation)
```

### Add Custom Remediation

```python
wfr.remediation_config.merge(custom_remediation)
```

> **Note:** `merge()` is intentionally strict. If any child already exists under the same parent in the target tree, Hier Config raises `hier_config.exceptions.DuplicateChildError`. This guards against accidentally overwriting commands when combining remediation fragments. When you need to layer one configuration onto another and allow overlapping sections, use [`future()`](future-config.md) instead.

### Output of Updated Remediation

```python
print(wfr.remediation_config)
```

Output:

```text
vlan 3
  name switch_mgmt_10.0.3.0/24
  exit
vlan 4
  name switch_mgmt_10.0.4.0/24
  exit
interface Vlan2
  mtu 9000
  ip access-group TEST in
  no shutdown
  exit
interface Vlan3
  description switch_mgmt_10.0.3.0/24
  ip address 10.0.3.1 255.255.0.0
  exit
interface Vlan4
  mtu 9000
  description switch_mgmt_10.0.4.0/24
  ip address 10.0.4.1 255.255.0.0
  ip access-group TEST in
  no shutdown
  exit
ip access-list resequence TEST 10 10
ip access-list extended TEST
  1 permit ip any any
  no 10
  10 permit ip 10.0.1.0 0.0.0.255 any
  20 permit ip 10.0.0.0 0.0.0.7 any
  no 1
  exit
```
