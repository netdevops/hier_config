from typing import List, Set, Union, Optional

import yaml

from hier_config import HConfig


class Host:
    """
    A host object is a convenient way to loading host inventory
    items into a single object.

    The default is to load "hostname", "os", and "options" to the host object,
    however, it can easily be extended for developer needs.

    .. code:: python

        import yaml
        from hier_config.host import Host

        options = yaml.load(open('./tests/fixtures/options_ios.yml'), loader=yaml.SafeLoader())
        host = Host('example.rtr', 'ios', options)

        # Example of easily extending the host object
        host.facts['chassis_model'] = 'WS-C4948E'

        # Example of loading running config and generated configs into a host object
        host.load_config_from(config_type="running", name="./tests/fixtures/running_config.conf")
        host.load_config_from(config_type="generated", name="./tests/fixtures/generated_config.conf")

        # Example of loading hier-config tags into a host object
        host.load_tags("./tests/fixtures/tags_ios.yml")

        # Example of creating a remediation config without a tag targeting specific config
        host.load_remediation()

        # Example of creating a remediation config with a tag ('safe') targeting a specific config.
        host.filter_remediation(include_tags=['safe'])
    """

    def __init__(self, hostname: str, os: str, hconfig_options: dict):
        self.hostname = hostname
        self.os = os
        self.hconfig_options = hconfig_options
        self._hconfig_tags: List[dict] = list()
        self._running_config: Optional[HConfig] = None
        self._generated_config = None
        self._remediation_config = None
        self.facts: dict = dict()

    def __repr__(self):
        return "Host(hostname={})".format(self.hostname)

    @property
    def running_config(self) -> Optional[HConfig]:
        """running configuration property"""
        if self._running_config is None:
            self._running_config = self._get_running_config()
        return self._running_config

    @property
    def generated_config(self) -> Optional[HConfig]:
        """generated configuration property"""
        if self._generated_config is None:
            self._generated_config = self._get_generated_config()
        return self._generated_config

    @property
    def remediation_config(self) -> Optional[HConfig]:
        """remediation configuration property"""
        if self._remediation_config is None:
            self._remediation_config = self._get_remediation_config()
        return self._remediation_config

    @property
    def hconfig_tags(self) -> List[dict]:
        """hier-config tags property"""
        return self._hconfig_tags

    def load_config_from_file(self, config_type: str, name: str):
        return self.load_config(config_type, self._load_from_file(name))

    def load_config(self, config_type: str, config_text: str) -> HConfig:
        """
        1. Loads a running config or a generated config into a Host object
        2. Sets host.facts['running_config_raw'] or host.facts['generated_config_raw']
        3. Loads the config into HConfig
        4. Sets the loaded hier-config in host.facts['running_config']
             or host.facts['generated_config']

        :param config_type: 'running' or 'generated' -> type str
        :param config_text: config text string to load -> type str
        :return: self.running_config or self.generated_config
        """
        hier = HConfig(host=self)
        hier.load_from_string(config_text)

        if config_type == "running":
            self.facts["running_config_raw"] = config_text
            self._running_config = hier
            return self.running_config
        if config_type == "generated":
            self.facts["generated_config_raw"] = config_text
            self._generated_config = hier
            return self.generated_config
        raise SyntaxError("Unknown config_type. Expected 'running' or 'generated'")

    def load_remediation(self) -> HConfig:
        """
        Once self.running_config and self.generated_config have been created,
        create self.remediation_config
        """
        if self.running_config and self.generated_config:
            self._remediation_config = self.running_config.config_to_get_to(
                self.generated_config
            )
        else:
            raise AttributeError("Missing host.running_config or host.generated_config")

        self.remediation_config.add_sectional_exiting()
        self.remediation_config.set_order_weight()
        self.remediation_config.add_tags(self.hconfig_tags)
        self.filter_remediation(set(), set())

        return self.remediation_config

    def filter_remediation(
        self,
        include_tags: Set[str],
        exclude_tags: Set[str],
    ) -> str:
        """ Run filter jobs, based on tags on self.remediation_config """
        remediation_text = str()

        if include_tags or exclude_tags:
            for line in self.remediation_config.all_children_sorted_by_tags(
                include_tags, exclude_tags
            ):
                remediation_text += line.cisco_style_text()
                remediation_text += "\n"
        else:
            for line in self.remediation_config.all_children():
                remediation_text += line.cisco_style_text()
                remediation_text += "\n"

        self.facts["remediation_config_raw"] = remediation_text

        return self.facts["remediation_config_raw"]

    def load_tags(self, name: str, load_file: bool = True) -> List[dict]:
        """
        Loads lineage rules into host.facts["hconfig_tags"]

        Example:
            Specify to load lineage rules from a file.

        .. code:: python

            host.load_tags('tags_ios.yml')

        Example:
            Specify to load lineage rules from a dictionary.

        .. code:: python

            tags = [{"lineage": [{"startswith": "interface"}], "add_tags": "interfaces"}]
            host.load_tags(tags, file=False)

        :param name: tags from a file or dictionary
        :param load_file: default, True -> type bool
        :return: self.hconfig_tags
        """
        if load_file:
            self._hconfig_tags = self._load_from_file(name, parse_yaml=True)
        else:
            self._hconfig_tags = name

        return self.hconfig_tags

    @staticmethod
    def _load_from_file(name, parse_yaml: bool = False) -> Union[list, dict, str]:
        """Opens a config file and loads it as a string."""
        with open(name) as file:
            content = file.read()

        if parse_yaml:
            content = yaml.safe_load(content)

        return content

    def _get_running_config(self) -> HConfig:
        return NotImplemented

    def _get_generated_config(self) -> HConfig:
        return NotImplemented

    def _get_remediation_config(self) -> HConfig:
        return NotImplemented
