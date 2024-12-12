from importlib.metadata import version, PackageNotFoundError

from .child import HConfigChild
from .constructors import (
    get_hconfig,
    get_hconfig_driver,
    get_hconfig_fast_load,
    get_hconfig_from_dump,
    get_hconfig_view,
)
from .models import Platform
from .root import HConfig
from .workflows import WorkflowRemediation

__all__ = (
    "HConfig",
    "HConfigChild",
    "Platform",
    "WorkflowRemediation",
    "get_hconfig",
    "get_hconfig_driver",
    "get_hconfig_fast_load",
    "get_hconfig_from_dump",
    "get_hconfig_view",
)

try:
    __version__ = version("hier_config")
except PackageNotFoundError:
    __version__ = "unknown"
