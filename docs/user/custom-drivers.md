# Customizing and Creating Drivers

Every driver is built from a common set of rule types. This guide explains those rule types, how to customize the built-in drivers, and how to create a custom driver for a platform that hier_config does not support out of the box.

For an overview of drivers and a reference of the built-in platforms, see [Drivers](drivers.md).

## Driver Rule Types

In Hier Config, the rules within a driver are organized into sections, each targeting a specific aspect of device configuration processing. These sections use Pydantic models to define the behavior and ensure consistency. Here's a breakdown of each section and its associated models:

---

### 1. Negation Rules

**Purpose**: Define how to negate commands or reset them to a default state.

- **Models**:
  - **`NegationDefaultWithRule`**:
    - `match_rules`: A tuple of `MatchRule` objects defining the conditions under which the rule applies.
    - `use`: The text to use as the negation command.

  - **`NegationDefaultWhenRule`**:
    - `match_rules`: A tuple of `MatchRule` objects for matching conditions where negation is default.

---

### 2. Sectional Exiting

**Purpose**: Manage hierarchical configuration sections by defining commands for properly exiting each section.

- **Models**:
  - **`SectionalExitingRule`**:
    - `match_rules`: A tuple of `MatchRule` objects defining the section's boundaries.
    - `exit_text`: The command used to exit the section.
    - `exit_text_parent_level`: A boolean (default `False`). When `True`, the exit text is rendered at the parent's indentation level rather than the section's own level (e.g., IOS XR `end-policy` appears unindented).

---

### 3. Ordering

**Purpose**: Assign weights to commands to control the order of operations during configuration application.

- **Models**:
  - **`OrderingRule`**:
    - `match_rules`: A tuple of `MatchRule` objects defining the commands to be ordered.
    - `weight`: An integer determining the order (lower weights are processed earlier).

---

### 4. Per-Line Substitutions

**Purpose**: Modify or clean up specific lines in the configuration.

- **Models**:
  - **`PerLineSubRule`**:
    - `search`: A string or regex to search for.
    - `replace`: The replacement text.

  - **`FullTextSubRule`**:
    - Similar to `PerLineSubRule`, but applies to the entire text rather than individual lines.

---

### 5. Idempotent Commands

**Purpose**: Ensure commands are not repeated unnecessarily in the configuration.

- **Models**:
  - **`IdempotentCommandsRule`**:
    - `match_rules`: A tuple of `MatchRule` objects defining idempotent commands.

  - **`IdempotentCommandsAvoidRule`**:
    - `match_rules`: Specifies commands that should be avoided during idempotency checks.

---

### 6. Post-Processing Callbacks

**Purpose**: Apply additional transformations after initial configuration processing.

- **Implementation**:
  - A list of functions or methods called after the driver rules are applied, enabling custom logic specific to the platform.

---

### 7. Tagging and Overwriting

**Purpose**: Apply tags to configuration lines or define overwriting behavior for specific sections.

- **Models**:
  - **`TagRule`**:
    - `match_rules`: A tuple of `MatchRule` objects defining the lines to tag.
    - `apply_tags`: A frozenset of tags to apply.

  - **`SectionalOverwriteRule`**:
    - `match_rules`: Defines sections that can be overwritten.

  - **`SectionalOverwriteNoNegateRule`**:
    - Similar to `SectionalOverwriteRule`, but prevents negation.

---

### 8. Indentation Adjustments

**Purpose**: Define start and end points for adjusting indentation within configurations.

- **Models**:
  - **`IndentAdjustRule`**:
    - `start_expression`: Regex or text marking the start of an adjustment.
    - `end_expression`: Regex or text marking the end of an adjustment.

---

### 9. Match Rules

**Purpose**: Provide a flexible way to define conditions for matching configuration lines.

`MatchRule` is the building block that every other rule type uses to target configuration lines by their lineage (`equals`, `startswith`, `endswith`, `contains`, `re_search`; multiple fields on one rule combine with AND logic). See [MatchRules](tags.md#matchrules) for the full reference and examples.

---

### 10. Instance Metadata

**Purpose**: Manage metadata for configuration instances, such as tags and comments.

- **Models**:
  - **`Instance`**:
    - `id`: A unique positive integer identifier.
    - `comments`: A frozenset of comments.
    - `tags`: A frozenset of tags.

---

### 11. Dumping Configuration

**Purpose**: Represent and handle the output of processed configuration lines.

- **Models**:
  - **`DumpLine`**:
    - `depth`: Indicates the hierarchy level of the line.
    - `text`: The configuration text.
    - `tags`: A frozenset of tags associated with the line.
    - `comments`: A frozenset of comments associated with the line.
    - `new_in_config`: A boolean indicating if the line is new.

  - **`Dump`**:
    - `lines`: A tuple of `DumpLine` objects representing the processed configuration.

---

### General Rule-Building Patterns

1. **Define Matching Conditions**:
   - Use `MatchRule` to specify conditions for each rule, ensuring flexible and precise control over which configuration lines a rule applies to.

2. **Apply Context-Specific Logic**:
   - Use specialized models like `SectionalExitingRule` or `IdempotentCommandsRule` to tailor behavior to hierarchical or idempotency-related scenarios.

3. **Maintain Immutability**:
   - All models use Pydantic’s immutability and validation to enforce the integrity of rules and configurations.

This structure ensures that drivers are modular, extensible, and capable of handling diverse configuration scenarios across different platforms.

## Customizing Existing Drivers

This guide provides two examples of how to extend the rules for a Cisco IOS driver in Hier Config. The first example involves subclassing the driver to customize and add rules. The second example demonstrates extending the driver rules dynamically after the driver has already been instantiated.

---

### Example 1: Subclassing the Driver to Extend Rules

In this approach, you create a new class that subclasses the base Cisco IOS driver and overrides its `_instantiate_rules` method to customize the rules.

```python
from hier_config.models import (
    MatchRule,
    NegationDefaultWithRule,
    SectionalExitingRule,
    OrderingRule,
    PerLineSubRule,
    IdempotentCommandsRule,
)
from hier_config.platforms.cisco_ios.driver import HConfigDriverCiscoIOS


class ExtendedHConfigDriverCiscoIOS(HConfigDriverCiscoIOS):
    @staticmethod
    def _instantiate_rules():
        # Start with the base rules
        base_rules = HConfigDriverCiscoIOS._instantiate_rules()

        # Extend negation rules
        base_rules.negate_with.append(
            NegationDefaultWithRule(
                match_rules=(MatchRule(startswith="ip route "),),
                use="no ip route"
            )
        )

        # Extend sectional exiting rules
        base_rules.sectional_exiting.append(
            SectionalExitingRule(
                match_rules=(
                    MatchRule(startswith="policy-map"),
                    MatchRule(startswith="class"),
                ),
                exit_text="exit",
            )
        )

        # Add additional ordering rules
        base_rules.ordering.append(
            OrderingRule(
                match_rules=(
                    MatchRule(startswith="access-list"),
                    MatchRule(startswith="permit "),
                ),
                weight=50,
            )
        )

        # Add new per-line substitutions
        base_rules.per_line_sub.append(
            PerLineSubRule(
                search="^!.*Generated by system.*$", replace=""
            )
        )

        # Add new idempotent commands
        base_rules.idempotent_commands.append(
            IdempotentCommandsRule(
                match_rules=(
                    MatchRule(startswith="interface "),
                    MatchRule(startswith="speed "),
                )
            )
        )

        return base_rules
```

#### Using the Subclassed Driver

```python
from hier_config import Platform

# Example function to activate the extended driver
def get_extended_hconfig_driver(platform: Platform):
    if platform == Platform.CISCO_IOS:
        return ExtendedHConfigDriverCiscoIOS()
    raise ValueError(f"Unsupported platform: {platform}")

# Activate the extended driver
driver = get_extended_hconfig_driver(Platform.CISCO_IOS)
```

### Example 2: Dynamically Extending Rules for an Instantiated Driver

If you already have the driver instantiated, you can modify its rules dynamically by directly appending to the appropriate sections.

```python
from hier_config import get_hconfig_driver, Platform
from hier_config.models import (
    MatchRule,
    NegationDefaultWithRule,
    SectionalExitingRule,
    OrderingRule,
    PerLineSubRule,
    IdempotentCommandsRule,
)

# Instantiate the driver
driver = get_hconfig_driver(Platform.CISCO_IOS)

# Dynamically extend negation rules
driver.rules.negate_with.append(
    NegationDefaultWithRule(
        match_rules=(MatchRule(startswith="ip route "),),
        use="no ip route"
    )
)

# Dynamically extend sectional exiting rules
driver.rules.sectional_exiting.append(
    SectionalExitingRule(
        match_rules=(
            MatchRule(startswith="policy-map"),
            MatchRule(startswith="class"),
        ),
        exit_text="exit",
    )
)

# Add additional ordering rules dynamically
driver.rules.ordering.append(
    OrderingRule(
        match_rules=(
            MatchRule(startswith="access-list"),
            MatchRule(startswith="permit "),
        ),
        weight=50,
    )
)

# Add new per-line substitutions dynamically
driver.rules.per_line_sub.append(
    PerLineSubRule(
        search="^!.*Generated by system.*$", replace=""
    )
)

# Add new idempotent commands dynamically
driver.rules.idempotent_commands.append(
    IdempotentCommandsRule(
        match_rules=(
            MatchRule(startswith="interface "),
            MatchRule(startswith="speed "),
        )
    )
)
```

#### Explanation

- **Dynamic Rule Extension:** You directly modify the driver.rules attributes to append new rules dynamically.
- **Flexibility:** This approach is useful when the driver is instantiated by external code, and subclassing is not feasible.

Both approaches allow you to extend the functionality of the Cisco IOS driver:

1. **Subclassing:** Recommended for reusable, modular extensions where the driver logic can be encapsulated in a new class.
2. **Dynamic Modification:** Useful when the driver is instantiated dynamically, and you need to modify the rules at runtime.

### Example 3: Adding Unused Object Detection

Unused object detection is not enabled in any driver by default — it must be explicitly configured. This ensures no unintended side-effects for users who are not expecting it.

You can add unused object rules dynamically or via `load_hconfig_v2_options`:

#### Dynamic Extension

```python
from hier_config import get_hconfig, get_hconfig_driver, Platform
from hier_config.models import MatchRule, ReferenceLocation, UnusedObjectRule

driver = get_hconfig_driver(Platform.CISCO_XR)

# Detect unused IPv4 ACLs
driver.rules.unused_objects.append(
    UnusedObjectRule(
        match_rules=(MatchRule(startswith="ipv4 access-list "),),
        name_re=r"^ipv4 access-list (?P<name>\S+)",
        reference_locations=(
            ReferenceLocation(
                match_rules=(MatchRule(startswith="interface "),),
                reference_re=r"\bipv4 access-group {name}\b",
            ),
        ),
    )
)

config = get_hconfig(driver, running_config_text)
for unused in config.unused_objects():
    print(f"Unused: {unused.text}")
```

#### Via `load_hconfig_v2_options`

```python
from hier_config import get_hconfig, Platform
from hier_config.utils import load_hconfig_v2_options

options = {
    "unused_objects": [
        {
            "lineage": [{"startswith": "ipv4 access-list "}],
            "name_re": r"^ipv4 access-list (?P<name>\S+)",
            "reference_locations": [
                {
                    "lineage": [{"startswith": "interface "}],
                    "reference_re": r"\bipv4 access-group {name}\b",
                },
            ],
        },
    ],
}
driver = load_hconfig_v2_options(options, Platform.CISCO_XR)
config = get_hconfig(driver, running_config_text)

for unused in config.unused_objects():
    print(f"Unused: {unused.text}")
```

Each `UnusedObjectRule` requires:

- `match_rules` — locates the object definition (e.g., `startswith="ipv4 access-list "`)
- `name_re` — regex with a `(?P<name>...)` capture group to extract the object name
- `reference_locations` — a tuple of `ReferenceLocation` entries, each specifying where to search and what regex pattern (with `{name}` placeholder) to match

### Example 4: Adding Negation Substitution

Some platforms require negation commands to be truncated or transformed. Use `NegationSubRule` for regex-based negation transformations:

```python
from hier_config import get_hconfig_driver, Platform
from hier_config.models import MatchRule, NegationSubRule

driver = get_hconfig_driver(Platform.CISCO_NXOS)

# Truncate SNMP user negation after the username
driver.rules.negation_sub.append(
    NegationSubRule(
        match_rules=(MatchRule(startswith="snmp-server user "),),
        search=r"(no snmp-server user \S+).*",
        replace=r"\1",
    )
)
```

## Creating a Custom Driver

This guide walks you through the process of creating a custom driver using the `HConfigDriverBase` class from the `hier_config.platforms.driver_base` module. Custom drivers allow you to define operating system-specific rules and behaviors for managing device configurations.

---

### Overview of `HConfigDriverBase`

The `HConfigDriverBase` class provides a foundation for defining driver-specific rules and behaviors. It encapsulates configuration rules and methods for handling idempotency, negation, and more. You will extend this class to create a new driver.

Key Components:

1. **`HConfigDriverRules`**: A collection of rules for handling configuration logic.
1. **Methods to Override**: Define custom behavior by overriding the `_instantiate_rules` method.
1. **Properties**: Adjust behavior for negation and declaration prefixes.

---

### Steps to Create a Custom Driver

#### Step 1: Subclass `HConfigDriverBase`

Begin by subclassing `HConfigDriverBase` to define a new driver.

```python
from hier_config.platforms.driver_base import HConfigDriverBase, HConfigDriverRules
from hier_config.models import (
    MatchRule,
    NegationDefaultWithRule,
    SectionalExitingRule,
    OrderingRule,
    PerLineSubRule,
    IdempotentCommandsRule,
)


class CustomHConfigDriver(HConfigDriverBase):
    """Custom driver for a specific operating system."""

    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        """Define the rules for this custom driver."""
        return HConfigDriverRules(
            negate_with=[
                NegationDefaultWithRule(
                    match_rules=(MatchRule(startswith="ip route "),),
                    use="no ip route"
                )
            ],
            sectional_exiting=[
                SectionalExitingRule(
                    match_rules=(
                        MatchRule(startswith="policy-map"),
                        MatchRule(startswith="class"),
                    ),
                    exit_text="exit"
                )
            ],
            ordering=[
                OrderingRule(
                    match_rules=(MatchRule(startswith="interface"),),
                    weight=10
                )
            ],
            per_line_sub=[
                PerLineSubRule(
                    search="^!.*Generated by system.*$",
                    replace=""
                )
            ],
            idempotent_commands=[
                IdempotentCommandsRule(
                    match_rules=(MatchRule(startswith="interface"),)
                )
            ],
        )
```

#### Step 2: Customize Negation or Declaration Prefixes (Optional)

Override the `negation_prefix` or `declaration_prefix` properties to customize their behavior.

```python
    @property
    def negation_prefix(self) -> str:
        """Customize the negation prefix."""
        return "disable "

    @property
    def declaration_prefix(self) -> str:
        """Customize the declaration prefix."""
        return "enable "
```

#### Step 3: Use the Custom Driver

This section describes how to use the custom driver by extending the `get_hconfig_driver` function and adding a new platform to the `Platform` model. It also covers how to load the driver into Hier Config and utilize it for remediation workflows.

---

##### 1. Extend `get_hconfig_driver` to Include the Custom Driver

First, modify the `get_hconfig_driver` function to include the new custom driver:

```python
from hier_config.platforms.driver_base import HConfigDriverBase
from hier_config import get_hconfig_driver
from .custom_driver import CustomHConfigDriver  # Import your custom driver
from hier_config.models import Platform

def get_custom_hconfig_driver(platform: Union[CustomPlatform,Platform]) -> HConfigDriverBase:
    """Create base options on an OS level."""
    if platform == CustomPlatform.CUSTOM_DRIVER:
        return CustomHConfigDriver()
    return get_hconfig_driver(platform)
```

##### 2. Create a custom `Platform` to Include the Custom Driver

```python
from enum import Enum, auto

class CustomPlatform(str, Enum):
    CUSTOM_PLATFORM = auto()
```

##### 3. Load the Driver into `HConfig`

```python
from .custom_platform import CustomPlatform
from hier_config import get_hconfig
from hier_config.utils import read_text_from_file

# Load running and intended configurations from files
running_config_text = read_text_from_file("./tests/fixtures/running_config.conf")
generated_config_text = read_text_from_file("./tests/fixtures/remediation_config.conf")

# Create HConfig objects for running and intended configurations
running_config = get_hconfig(CustomPlatform.CUSTOM_DRIVER, running_config_text)
generated_config = get_hconfig(CustomPlatform.CUSTOM_DRIVER, generated_config_text)
```

##### 4. Instantiate a `WorkflowRemediation`

```python
from hier_config import WorkflowRemediation

# Instantiate the remediation workflow
workflow = WorkflowRemediation(running_config, generated_config)
```


### Key Methods in HConfigDriverBase

1. `idempotent_for`:
    - Matches configurations against idempotent rules to prevent duplication.

```python
def idempotent_for(
    self,
    config: HConfigChild,
    other_children: Iterable[HConfigChild],
) -> Optional[HConfigChild]:
    ...
```

1. `negate_with`:
    - Provides a negation command based on rules.

```python
def negate_with(self, config: HConfigChild) -> Optional[str]:
    ...
```

1. `swap_negation`:
    - Toggles the negation of a command.

```python
def swap_negation(self, child: HConfigChild) -> HConfigChild:
    ...
```

1. Properties:
    - `negation_prefix`: Default is `"no "`.
    - `declaration_prefix`: Default is `""`.

### Example Rule Definitions

#### Negation Rules

Define commands that require specific negation handling:

```python
negate_with=[
    NegationDefaultWithRule(
        match_rules=(MatchRule(startswith="ip route "),),
        use="no ip route"
    )
]
```

#### Sectional Exiting

Define how to exit specific configuration sections:

```python
sectional_exiting=[
    SectionalExitingRule(
        match_rules=(
            MatchRule(startswith="policy-map"),
            MatchRule(startswith="class"),
        ),
        exit_text="exit",
    ),
    SectionalExitingRule(
        match_rules=(MatchRule(startswith="route-policy"),),
        exit_text="end-policy",
        exit_text_parent_level=True,  # render at parent indentation
    ),
]
```

#### Command Ordering

Set the execution order of specific commands:

```python
ordering=[
    OrderingRule(
        match_rules=(MatchRule(startswith="interface"),),
        weight=10
    )
]
```

#### Per-Line Substitution

Clean up unwanted lines in the configuration:

```python
per_line_sub=[
    PerLineSubRule(
        search="^!.*Generated by system.*$",
        replace=""
    )
]
```
