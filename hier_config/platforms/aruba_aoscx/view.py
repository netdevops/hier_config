"""Aruba AOS-CX configuration views.

The view implementation lives in the Rust core; these classes are the
platform-specific names the public API has always exposed. ``HConfigViewArubaAOSCX``
is a real subclass, so ``driver.view_class`` construction is unchanged.
``ConfigViewInterfaceArubaAOSCX`` is a marker: the native view is platform-aware, so
``isinstance`` is resolved from the view's ``platform`` attribute.
"""

# Marker and alias classes carry no methods of their own; every property is
# inherited from the native view.
# pylint: disable=too-few-public-methods

from __future__ import annotations

from hier_config.models import Platform
from hier_config.platforms.view_base import (
    ConfigViewInterface,
    HConfigView,
    ViewMarkerMeta,
)

__all__ = ("ConfigViewInterfaceArubaAOSCX", "HConfigViewArubaAOSCX")


class ConfigViewInterfaceArubaAOSCX(ConfigViewInterface, metaclass=ViewMarkerMeta):
    """A single Aruba AOS-CX interface."""

    view_platform = Platform.ARUBA_AOSCX


class HConfigViewArubaAOSCX(HConfigView):
    """A Aruba AOS-CX device configuration."""
