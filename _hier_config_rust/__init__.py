"""Compatibility imports for pickles and callers using the former native module.

All objects are aliases of the packaged extension, never separate native types.
"""

# This compatibility package intentionally forwards the internal native module.
from hier_config._hier_config_rust import (  # ruff: ignore[import-private-name]
    ConfigViewInterface,
    DuplicateChildError,
    HConfig,
    HConfigBase,
    HConfigChild,
    HConfigChildren,
    HConfigChildrenIter,
    HConfigView,
    HierConfigError,
    InvalidConfigError,
    WorkflowRemediation,
    __version__,
    config_preprocessor,
    convert_to_set_commands,
    driver_swap_negation,
    formats_from_json,
    formats_from_xml,
    formats_to_gnmi_json,
    formats_to_json,
    formats_to_netconf_xml,
    formats_to_xml,
    get_platform_rules_json,
)

__all__ = (
    "ConfigViewInterface",
    "DuplicateChildError",
    "HConfig",
    "HConfigBase",
    "HConfigChild",
    "HConfigChildren",
    "HConfigChildrenIter",
    "HConfigView",
    "HierConfigError",
    "InvalidConfigError",
    "WorkflowRemediation",
    "__version__",
    "config_preprocessor",
    "convert_to_set_commands",
    "driver_swap_negation",
    "formats_from_json",
    "formats_from_xml",
    "formats_to_gnmi_json",
    "formats_to_json",
    "formats_to_netconf_xml",
    "formats_to_xml",
    "get_platform_rules_json",
)
