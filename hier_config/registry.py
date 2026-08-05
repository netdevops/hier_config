"""Driver registration system (#226).

Built-in drivers are registered at import time. Users can register drivers for
custom platforms (by string name), override built-in drivers, and restore
built-in defaults by unregistering the override.

Entries are keyed on canonical uppercase platform names (#284): `Platform`
members are converted via their names at the boundary, and string names are
uppercased, so a member and its name address the same entry.

The registry is not synchronized; register drivers at application startup,
before configs are parsed concurrently.
"""

from hier_config.exceptions import DriverNotFoundError
from hier_config.models import Platform
from hier_config.platforms.arista_eos.driver import HConfigDriverAristaEOS
from hier_config.platforms.aruba_aoscx.driver import HConfigDriverArubaAOSCX
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

_BUILTIN_DRIVERS: dict[str, type[HConfigDriverBase]] = {
    Platform.ARISTA_EOS.name: HConfigDriverAristaEOS,
    Platform.ARUBA_AOSCX.name: HConfigDriverArubaAOSCX,
    Platform.CISCO_IOS.name: HConfigDriverCiscoIOS,
    Platform.CISCO_NXOS.name: HConfigDriverCiscoNXOS,
    Platform.CISCO_XR.name: HConfigDriverCiscoIOSXR,
    Platform.FORTINET_FORTIOS.name: HConfigDriverFortinetFortiOS,
    Platform.GENERIC.name: HConfigDriverGeneric,
    Platform.HP_PROCURVE.name: HConfigDriverHPProcurve,
    Platform.HP_COMWARE5.name: HConfigDriverHPComware5,
    Platform.HUAWEI_VRP.name: HConfigDriverHuaweiVrp,
    Platform.JUNIPER_JUNOS.name: HConfigDriverJuniperJUNOS,
    Platform.NOKIA_SRL.name: HConfigDriverNokiaSRL,
    Platform.VYOS.name: HConfigDriverVYOS,
}

_registry: dict[str, type[HConfigDriverBase]] = dict(_BUILTIN_DRIVERS)


def _normalize(platform: Platform | str) -> str:
    # Platform must be checked first: it subclasses str, and its str content
    # is the enum value, not the platform name.
    if isinstance(platform, Platform):
        return platform.name
    return platform.upper()


def register_driver(
    platform: Platform | str,
    driver_class: type[HConfigDriverBase],
) -> None:
    """Register a driver for a platform.

    Passing a string registers a custom platform usable anywhere a `Platform`
    is accepted; names are canonicalized to uppercase, so registration and
    lookup are case-insensitive. Passing an existing `Platform` member (or its
    name — the two are interchangeable) overrides the built-in driver for
    that platform.
    """
    _registry[_normalize(platform)] = driver_class


def unregister_driver(platform: Platform | str) -> None:
    """Remove a custom platform, or restore an overridden built-in driver."""
    name = _normalize(platform)
    if name not in _registry:
        message = f"Unsupported platform: {platform}"
        raise DriverNotFoundError(message)
    builtin = _BUILTIN_DRIVERS.get(name)
    if builtin is None:
        del _registry[name]
    elif _registry[name] is builtin:
        # Format the canonical name: pre-3.11 f-strings render a str-Enum
        # member as its meaningless value string.
        message = f"Built-in platform {name} is not overridden"
        raise DriverNotFoundError(message)
    else:
        _registry[name] = builtin


def get_registered_platforms() -> tuple[Platform | str, ...]:
    """Return all registered platforms, built-in and custom.

    Names matching a `Platform` member are returned as members; custom names
    are returned as canonical uppercase strings.
    """
    return tuple(Platform.__members__.get(name, name) for name in _registry)


def resolve_driver(
    platform_or_driver: Platform | str | HConfigDriverBase,
) -> HConfigDriverBase:
    """Return the driver for a platform, platform name, or driver instance."""
    if isinstance(platform_or_driver, HConfigDriverBase):
        return platform_or_driver
    return get_hconfig_driver(platform_or_driver)


def get_hconfig_driver(platform: Platform | str) -> HConfigDriverBase:
    """Instantiate the driver registered for a platform."""
    driver_class = _registry.get(_normalize(platform))
    if driver_class is None:
        message = f"Unsupported platform: {platform}"
        raise DriverNotFoundError(message)
    return driver_class()
