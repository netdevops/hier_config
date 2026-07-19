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

---

## Core Classes

::: hier_config.HConfig

::: hier_config.HConfigChild

::: hier_config.children.HConfigChildren

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

---

## Config Views

::: hier_config.HConfigViewBase

::: hier_config.ConfigViewInterfaceBase

::: hier_config.InterfaceBundleViewMixin

::: hier_config.InterfaceVlanViewMixin

::: hier_config.InterfaceNACViewMixin

::: hier_config.InterfacePhysicalViewMixin

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
