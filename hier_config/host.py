from functools import lru_cache
from pathlib import Path

from .constructors import get_hconfig, get_hconfig_driver
from .model import Platform
from .platforms.driver_base import HConfigDriverBase
from .root import HConfig


class Host:
    """
    A host object is a convenient way to loading host inventory
    items into a single object.

    The default is to load "hostname", "os", and "options" to the host object,
    however, it can easily be extended for developer needs.

    .. code:: python

        import yaml
        from hier_config.host import Host

        options = yaml.load(open("./tests/fixtures/options_ios.yml"), loader=yaml.SafeLoader())
        host = Host("example.rtr", "ios", options)

        # Example of loading running config and generated configs into a host object
        host.load_running_config_from_file("./tests/files/running_config.conf)
        host.load_generated_config_from_file("./tests/files/generated_config.conf)

        # Example of creating a remediation config without a tag targeting specific config
        host.remediation_config()

        # Example of creating a remediation config with a tag ("safe") targeting a specific config.
        host.remediation_config_filtered_text({"safe"}, set()})
    """

    def __init__(  # pylint: disable=dangerous-default-value
        self,
        platform: Platform,
        driver: HConfigDriverBase | None = None,
    ) -> None:
        self.platform = platform
        self.driver = driver or get_hconfig_driver(self.platform)
        self._running_config: HConfig | None = None
        self._generated_config: HConfig | None = None

    def __repr__(self) -> str:
        return f"Host(hostname={self.platform.name})"

    @property
    def running_config(self) -> HConfig:
        """Running configuration property."""
        if self._running_config is None:
            self._running_config = self._get_running_config()
        return self._running_config

    @property
    def generated_config(self) -> HConfig:
        """Generated configuration property."""
        if self._generated_config is None:
            self._generated_config = self._get_generated_config()
        return self._generated_config

    @lru_cache
    def remediation_config(self) -> HConfig:
        """
        Once self.running_config and self.generated_config have been created,
        create self.remediation_config.
        """
        if self.running_config and self.generated_config:
            remediation = self.running_config.config_to_get_to(self.generated_config)
        else:
            msg = "Missing host.running_config or host.generated_config"
            raise AttributeError(msg)

        return remediation.set_order_weight()

    @lru_cache
    def rollback_config(self) -> HConfig:
        """
        Once a self.running_config and self.generated_config have been created,
        generate a self.rollback_config.
        """
        if self.running_config and self.generated_config:
            rollback = self.generated_config.config_to_get_to(self.running_config)
        else:
            msg = "Missing host.running_config or host.generated_config"
            raise AttributeError(msg)

        return rollback.set_order_weight()

    def load_running_config_from_file(self, file: Path) -> None:
        config_raw = file.read_text(encoding="utf-8")
        self.load_running_config(config_raw)

    def load_running_config(self, config_raw: str) -> None:
        self._running_config = get_hconfig(self.driver, config_raw)

    def load_generated_config_from_file(self, file: Path) -> None:
        config_raw = file.read_text(encoding="utf-8")
        self.load_generated_config(config_raw)

    def load_generated_config(self, config_raw: str) -> None:
        self._generated_config = get_hconfig(self.driver, config_raw)

    def remediation_config_filtered_text(
        self, include_tags: set[str], exclude_tags: set[str]
    ) -> str:
        config = self.remediation_config()
        children = (
            config.all_children_sorted_by_tags(include_tags, exclude_tags)
            if include_tags or exclude_tags
            else config.all_children_sorted()
        )
        return "\n".join(c.cisco_style_text() for c in children)

    @staticmethod
    def _get_running_config() -> HConfig:
        return NotImplemented

    @staticmethod
    def _get_generated_config() -> HConfig:
        return NotImplemented
