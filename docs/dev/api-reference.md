# API Reference

Auto-generated reference documentation for the `hier_config` public API. Signatures and docstrings are pulled directly from the source, so this page always reflects the installed version.

---

## Constructors

::: hier_config.HConfig.from_text

::: hier_config.HConfig.from_lines

::: hier_config.HConfig.from_dump

::: hier_config.HConfig.from_json

::: hier_config.HConfig.from_xml

::: hier_config.get_hconfig_driver

::: hier_config.get_hconfig_view

---

## Driver Registry

::: hier_config.register_driver

::: hier_config.unregister_driver

::: hier_config.get_registered_platforms

::: hier_config.registry.resolve_driver

---

## Core Classes

::: hier_config.HConfig

::: hier_config.HConfigChild

::: hier_config.children.HConfigChildren

---

## Future Config

::: hier_config.HConfig.future

::: hier_config.HConfig.future_with_report

::: hier_config.FutureReport

---

## Structured Formats

JSON/XML ingestion and rendering, NETCONF `edit-config` payloads, and gNMI-style JSON remediation. The module docstring below documents the tree↔structure mapping and its caveats.

::: hier_config.formats

---

## Workflow

::: hier_config.WorkflowRemediation

::: hier_config.RemediationPlugin

---

## Reporting

::: hier_config.RemediationReporter

::: hier_config.ReportSummary

::: hier_config.ChangeDetail

---

## Driver System

::: hier_config.platforms.driver_base.HConfigDriverBase

::: hier_config.platforms.driver_base.HConfigDriverRules

### Built-in post-load callbacks

Public functions shipped by the built-in drivers (removable by identity — see [Customizing Driver Rules](../admin/customizing-rules.md#customizing-post-load-callbacks)):

::: hier_config.platforms.cisco_ios.driver.remove_ipv6_acl_sequence_numbers

::: hier_config.platforms.cisco_ios.driver.remove_ipv4_acl_remarks

::: hier_config.platforms.cisco_ios.driver.add_acl_sequence_numbers

::: hier_config.platforms.utils.split_vlan_id_lists

::: hier_config.platforms.cisco_xr.driver.fixup_xr_comments

::: hier_config.platforms.hp_procurve.driver.fixup_hp_procurve_aaa_port_access

::: hier_config.platforms.hp_procurve.driver.fixup_hp_procurve_device_profile

::: hier_config.platforms.hp_procurve.driver.fixup_hp_procurve_vlan

::: hier_config.platforms.aruba_aoscx.driver.split_interface_vlan_trunk_allowed

---

## Config Views

::: hier_config.HConfigViewBase

::: hier_config.ConfigViewInterfaceBase

::: hier_config.InterfaceBundleViewMixin

::: hier_config.InterfaceVlanViewMixin

::: hier_config.InterfaceNACViewMixin

::: hier_config.InterfacePhysicalViewMixin

### Typed view data models

The value types returned by view properties:

::: hier_config.platforms.models.Vlan

::: hier_config.platforms.models.StackMember

::: hier_config.platforms.models.InterfaceDot1qMode

::: hier_config.platforms.models.InterfaceDuplex

::: hier_config.platforms.models.NACHostMode

---

## Models

::: hier_config.models.Platform

::: hier_config.models.TextStyle

::: hier_config.models.MatchRule

::: hier_config.models.TagRule

::: hier_config.models.IdempotentCommandsRule

::: hier_config.models.IdempotentCommandsAvoidRule

::: hier_config.models.NegationRule

::: hier_config.models.NegationStrategy

::: hier_config.models.SectionalExitingRule

::: hier_config.models.SectionalOverwriteRule

::: hier_config.models.SectionalOverwriteNoNegateRule

::: hier_config.models.OrderingRule

::: hier_config.models.PerLineSubRule

::: hier_config.models.FullTextSubRule

::: hier_config.models.IndentAdjustRule

::: hier_config.models.ParentAllowsDuplicateChildRule

::: hier_config.models.UnusedObjectRule

::: hier_config.models.ReferenceLocation

::: hier_config.models.Instance

::: hier_config.models.Dump

::: hier_config.models.DumpLine

---

## Exceptions

::: hier_config.HierConfigError

::: hier_config.DriverNotFoundError

::: hier_config.DuplicateChildError

::: hier_config.IncompatibleDriverError

::: hier_config.InvalidConfigError

---

## Utilities

::: hier_config.utils
