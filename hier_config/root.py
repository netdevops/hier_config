from __future__ import annotations

from typing import TYPE_CHECKING

from _hier_config_rust import HConfig as _RustHConfig

if TYPE_CHECKING:
    from hier_config.platforms.driver_base import HConfigDriverBase


class HConfig(_RustHConfig):  # pylint: disable=too-few-public-methods
    """HConfig root tree instance."""

    def __init__(self, driver: HConfigDriverBase) -> None:  # pylint: disable=useless-parent-delegation
        super().__init__(driver)


__all__ = ("HConfig",)
