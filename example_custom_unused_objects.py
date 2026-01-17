#!/usr/bin/env python3
"""Example demonstrating extensible unused object detection.

This example shows how to use the new extensible unused object system
to detect custom configuration objects on any platform.
"""

from hier_config import (
    UnusedObjectRuleBuilder,
    create_simple_rule,
    get_hconfig,
)
from hier_config.models import Platform

# Example configuration for a hypothetical custom platform
CONFIG = """
# Custom ACL definitions
access-list WEB_TRAFFIC
  permit tcp any any eq 80
  permit tcp any any eq 443

access-list UNUSED_ACL
  permit ip any any

# NAT pool definitions
nat-pool PUBLIC_POOL
  range 203.0.113.10 203.0.113.20

nat-pool UNUSED_POOL
  range 203.0.113.30 203.0.113.40

# Interface configuration
interface eth0
  description Uplink interface
  apply-acl WEB_TRAFFIC inbound

# NAT configuration
nat source interface eth0 pool PUBLIC_POOL
"""


def main() -> None:
    """Demonstrate custom unused object detection."""
    print("=" * 70)
    print("Extensible Unused Object Detection Example")
    print("=" * 70)

    # Create config using generic platform (works with ANY platform!)
    config = get_hconfig(Platform.GENERIC, CONFIG)

    print("\n1. Using UnusedObjectRuleBuilder (fluent API):")
    print("-" * 70)

    # Define rule for access-lists using the builder
    acl_rule = (
        UnusedObjectRuleBuilder("custom-access-list")
        .define_with(startswith="access-list ")
        .referenced_in(
            context_match=[
                {"startswith": "interface "},
                {"startswith": "apply-acl "},
            ],
            extract_regex=r"apply-acl\s+(\S+)",
            reference_type="interface-applied",
        )
        .remove_with("no access-list {name}")
        .with_weight(150)
        .build()
    )

    print(f"Created rule: {acl_rule.object_type}")
    print("  - Definition pattern: startswith='access-list '")
    print("  - Reference extraction: apply-acl\\s+(\\S+)")
    print(f"  - Removal template: {acl_rule.removal_template}")

    print("\n2. Using create_simple_rule (simplified API):")
    print("-" * 70)

    # Define rule for NAT pools using the simple helper
    nat_pool_rule = create_simple_rule(
        object_type="custom-nat-pool",
        definition_pattern="nat-pool ",
        reference_pattern=r"pool\s+(\S+)",
        reference_context="nat source ",
        removal_template="no nat-pool {name}",
        removal_weight=140,
    )

    print(f"Created rule: {nat_pool_rule.object_type}")
    print("  - Definition pattern: startswith='nat-pool '")
    print("  - Reference extraction: pool\\s+(\\S+)")
    print(f"  - Removal template: {nat_pool_rule.removal_template}")

    print("\n3. Adding rules to driver:")
    print("-" * 70)

    # Add both custom rules to the driver
    config.driver.add_unused_object_rules([acl_rule, nat_pool_rule])
    print(f"Added {len(config.driver.get_unused_object_rules())} rules to driver")

    print("\n4. Analyzing configuration:")
    print("-" * 70)

    # Analyze and generate cleanup
    analysis = config.driver.find_unused_objects(config)

    print(f"Total defined objects: {analysis.total_defined}")
    print(f"Total unused objects: {analysis.total_unused}")

    print("\n5. Results by object type:")
    print("-" * 70)

    for object_type, definitions in analysis.defined_objects.items():
        unused = analysis.unused_objects.get(object_type, ())
        print(f"\n{object_type}:")
        print(f"  Defined: {len(definitions)}")
        print(f"  Unused:  {len(unused)}")

        if unused:
            print("  Unused objects:")
            for obj in unused:
                print(f"    - {obj.name}")

    print("\n6. Removal commands:")
    print("-" * 70)

    if analysis.removal_commands:
        for cmd in analysis.removal_commands:
            print(f"  {cmd}")
    else:
        print("  (no unused objects to remove)")

    print(f"\n{'=' * 70}")
    print("Example completed successfully!")
    print("=" * 70)


if __name__ == "__main__":
    main()
