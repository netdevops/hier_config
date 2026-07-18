"""Driver registration system (#226).

Built-in drivers are registered at import time. Users can register drivers for
custom platforms (by string name), override built-in drivers, and restore
built-in defaults by unregistering the override.

The registry is not synchronized; register drivers at application startup,
before configs are parsed concurrently.
"""

from hier_config.exceptions import DriverNotFoundError
from hier_config.models import Platform
from hier_config.platforms.arista_eos.driver import HConfigDriverAristaEOS
from hier_config.platforms.cisco_ios.driver import HConfigDriverCiscoIOS
from hier_config.platforms.cisco_nxos.driver import HConfigDriverCiscoNXOS
from hier_config.platforms.cisco_xr.driver import HConfigDriverCiscoIOSXR
from hier_config.platforms.driver_base import HConfigDriverBase
from hier_config.platforms.fortinet_fortios.driver import HConfigDriverFortinetFortiOS
from hier_config.platforms.generic.driver import HConfigDriverGeneric
from hier_config.platforms.hp_comware5.driver import HConfigDriverHPComware5
from hier_config.platforms.hp_procurve.driver import HConfigDriverHPProcurve
from hier_config.platforms.huawei_vrp.driver import HConfigDriverHuaweiVrp
from hier_config.platforms.juniper_junos.driver import HConfigDriverJuniperJUNOS
from hier_config.platforms.nokia_srl.driver import HConfigDriverNokiaSRL
from hier_config.platforms.vyos.driver import HConfigDriverVYOS

_BUILTIN_DRIVERS: dict[Platform | str, type[HConfigDriverBase]] = {
    Platform.ARISTA_EOS: HConfigDriverAristaEOS,
    Platform.CISCO_IOS: HConfigDriverCiscoIOS,
    Platform.CISCO_NXOS: HConfigDriverCiscoNXOS,
    Platform.CISCO_XR: HConfigDriverCiscoIOSXR,
    Platform.FORTINET_FORTIOS: HConfigDriverFortinetFortiOS,
    Platform.GENERIC: HConfigDriverGeneric,
    Platform.HP_PROCURVE: HConfigDriverHPProcurve,
    Platform.HP_COMWARE5: HConfigDriverHPComware5,
    Platform.HUAWEI_VRP: HConfigDriverHuaweiVrp,
    Platform.JUNIPER_JUNOS: HConfigDriverJuniperJUNOS,
    Platform.NOKIA_SRL: HConfigDriverNokiaSRL,
    Platform.VYOS: HConfigDriverVYOS,
}

_registry: dict[Platform | str, type[HConfigDriverBase]] = dict(_BUILTIN_DRIVERS)


def _normalize(platform: Platform | str) -> Platform | str:
    if isinstance(platform, Platform):
        return platform
    name = platform.upper()
    try:
        return Platform[name]
    except KeyError:
        return name


def register_driver(
    platform: Platform | str,
    driver_class: type[HConfigDriverBase],
) -> None:
    """Register a driver for a platform.

    Passing a string registers a custom platform usable anywhere a `Platform`
    is accepted (names are case-insensitive). Passing an existing `Platform`
    member overrides the built-in driver for that platform.
    """
    _registry[_normalize(platform)] = driver_class


def unregister_driver(platform: Platform | str) -> None:
    """Remove a custom platform, or restore an overridden built-in driver."""
    platform = _normalize(platform)
    if platform not in _registry:
        message = f"Unsupported platform: {platform}"
        raise DriverNotFoundError(message)
    if isinstance(platform, Platform):
        if _registry[platform] is _BUILTIN_DRIVERS[platform]:
            message = f"Built-in platform {platform} is not overridden"
            raise DriverNotFoundError(message)
        _registry[platform] = _BUILTIN_DRIVERS[platform]
    else:
        del _registry[platform]


def get_registered_platforms() -> tuple[Platform | str, ...]:
    """Return all registered platforms, built-in and custom."""
    return tuple(_registry)


def get_hconfig_driver(platform: Platform | str) -> HConfigDriverBase:
    """Instantiate the driver registered for a platform."""
    driver_class = _registry.get(_normalize(platform))
    if driver_class is None:
        message = f"Unsupported platform: {platform}"
        raise DriverNotFoundError(message)
    return driver_class()
