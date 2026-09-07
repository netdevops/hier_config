"""Platform-independent views over a parsed configuration.

All view logic lives in the Rust core and is exposed by the
``_hier_config_rust`` extension as :class:`HConfigView` and
:class:`ConfigViewInterface`. This module is the documented Python facade: it
re-exports those native classes under their historical names and defines the
capability marker classes.

Because one native class serves every platform, the capability mixins are
markers whose ``isinstance`` checks are answered from the view's runtime
``capabilities`` set rather than from its position in a class hierarchy. The
observable behaviour is unchanged -- ``isinstance(view, InterfaceVlanViewMixin)``
is still true only for platforms that model 802.1Q on interfaces -- and the
markers still subclass :class:`ConfigViewInterface`, so type checkers narrow to
the full property set.
"""

# Marker and alias classes carry no methods of their own; every property is
# inherited from the native view.
# pylint: disable=too-few-public-methods

from __future__ import annotations

from typing import TYPE_CHECKING

from _hier_config_rust import ConfigViewInterface, HConfigView

if TYPE_CHECKING:
    from hier_config.models import Platform

__all__ = (
    "ConfigViewInterface",
    "ConfigViewInterfaceBase",
    "HConfigView",
    "HConfigViewBase",
    "InterfaceBundleViewMixin",
    "InterfaceNACViewMixin",
    "InterfacePhysicalViewMixin",
    "InterfaceVlanViewMixin",
    "ViewMarkerMeta",
)

#: Historical name for the native per-interface view.
ConfigViewInterfaceBase = ConfigViewInterface

#: Historical name for the native device-level view.
HConfigViewBase = HConfigView


class ViewMarkerMeta(type):
    """Resolve ``isinstance`` for interface-view marker classes.

    A marker sets exactly one of ``view_capability`` or ``view_platform`` in its
    class body; instances are matched against the corresponding runtime
    attribute of the native view rather than against the class hierarchy.
    """

    view_capability: str | None = None
    view_platform: Platform | None = None

    def __instancecheck__(cls, instance: object) -> bool:
        if not isinstance(instance, ConfigViewInterface):
            return False
        if cls.view_platform is not None:
            return instance.platform is cls.view_platform
        return (
            cls.view_capability is not None
            and cls.view_capability in instance.capabilities
        )


class InterfaceBundleViewMixin(ConfigViewInterface, metaclass=ViewMarkerMeta):
    """Marker for interface views that model bundles / port channels."""

    view_capability = "bundle"


class InterfaceVlanViewMixin(ConfigViewInterface, metaclass=ViewMarkerMeta):
    """Marker for interface views that model 802.1Q VLAN membership."""

    view_capability = "vlan"


class InterfaceNACViewMixin(ConfigViewInterface, metaclass=ViewMarkerMeta):
    """Marker for interface views that model NAC (802.1X)."""

    view_capability = "nac"


class InterfacePhysicalViewMixin(ConfigViewInterface, metaclass=ViewMarkerMeta):
    """Marker for interface views that model physical-layer attributes."""

    view_capability = "physical"
