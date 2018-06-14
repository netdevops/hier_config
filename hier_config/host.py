from hier_config import HConfig
import hier_config.helpers as H


class Host:
    """
    A host object is a convenient way to loading host inventory
    items into a single object.

    The default is to load "hostname", "os", and "options" to the host object,
    however, it can easily be extended for developer needs.

    .. code:: python

        import yaml
        from hier_config.host import Host

        options = yaml.load(open('./tests/files/test_options_ios.yml'))
        host = Host('example.rtr', 'ios', options)

        # Example of easily extending the host object
        host.facts['chassis_model'] = 'WS-C4948E'

        # Example of loading running config and compiled configs into a host object
        host.load_config_from(config_type="running", name="./tests/files/running_config.conf")
        host.load_config_from(config_type="compiled", name="./tests/files/compiled_config.conf")

        # Example of loading hier-config tags into a host object
        host.load_tags("./tests/files/test_tags_ios.yml")

        # Example of creating a remediation config without a tag targeting specific config
        host.load_remediation()

        # Example of creating a remediation config with a tag ('safe') targeting a specific config.
        host.filter_remediation(include_tags=['safe'])

    :param hostname: type str
    :param os: type str
    :param hconfig_options: type dict

    :return: Host Object

    """

    def __init__(self, hostname, os, hconfig_options):
        self.hostname = str(hostname)
        self.os = str(os)
        self.hconfig_options = dict(hconfig_options)
        self._hconfig_tags = list()
        self._running_config = None
        self._compiled_config = None
        self._remediation_config = None
        self.facts = dict()

    def __repr__(self):
        return 'Host(hostname={})'.format(self.hostname)

    @property
    def running_config(self):
        """
        running configuration property

        :return: self._running_config -> type HConfig Object or None
        """
        if self._running_config is None:
            self._running_config = self._get_running_config()
        return self._running_config

    @property
    def compiled_config(self):
        """
        compiled configuration property

        :return: self._compiled_config -> type HConfig Object or None
        """
        if self._compiled_config is None:
            self._compiled_config = self._get_compiled_config()
        return self._compiled_config

    @property
    def remediation_config(self):
        """
        remediation configuration property

        :return: self._remediation_config -> type HConfig Object or None
        """
        if self._remediation_config is None:
            self._remediation_config = self._get_remediation_config()
        return self._remediation_config

    @property
    def hconfig_tags(self):
        """
        hier-config tags property

        :return: self._hconfig_tags -> type list of dicts
        """
        return self._hconfig_tags

    def load_config_from(self, config_type, name, load_file=True):
        """
        1. Loads a running config or a compiled config into a Host object
        2. Sets host.facts['running_config_raw'] or host.facts['compiled_config_raw']
        3. Loads the config into HConfig
        4. Sets the loaded hier-config in host.facts['running_config'] or host.facts['compiled_config']

        :param config_type: 'running' or 'compiled' -> type str
        :param name: file name or config text string to load -> type str
        :param load_file: default, True -> type bool
        :return: self.running_config or self.compiled_config
        """
        hier = HConfig(host=self)

        if load_file:
            config_text = self._load_from_file(name)
        else:
            config_text = name

        hier.load_from_string(config_text)

        if config_type == "running":
            self.facts["running_config_raw"] = config_text
            self._running_config = hier

            return self.running_config
        elif config_type == "compiled":
            self.facts["compiled_config_raw"] = config_text
            self._compiled_config = hier

            return self.compiled_config
        else:
            raise SyntaxError("Unknown config_type. Expected 'running' or 'compiled'")

    def load_remediation(self):
        """
        Once self.running_config and self.compled_config have been created,
        create self.remediation_config

        :return: self.remediation_config
        """
        if self.running_config and self.compiled_config:
            self._remediation_config = self.running_config.config_to_get_to(
                self.compiled_config
            )
        else:
            raise AttributeError("Missing host.running_config or host.compiled_config")

        self.remediation_config.add_sectional_exiting()
        self.remediation_config.set_order_weight()
        self.remediation_config.add_tags(self.hconfig_tags)
        self.filter_remediation()

        return self.remediation_config

    def filter_remediation(self, include_tags=None, exclude_tags=None):
        """
        Run filter jobs, based on tags on self.remediation_config

        :param include_tags: type list
        :param exclude_tags: type list
        :return: self.facts['remediation_conig_raw'] -> type str
        """
        remediation_text = str()

        if include_tags or exclude_tags is not None:
            include_tags = H.to_list(include_tags)
            exclude_tags = H.to_list(exclude_tags)

            for line in self.remediation_config.all_children_sorted_by_tags(include_tags, exclude_tags):
                remediation_text += line.cisco_style_text()
                remediation_text += '\n'
        else:
            for line in self.remediation_config.all_children():
                remediation_text += line.cisco_style_text()
                remediation_text += '\n'

        self.facts["remediation_config_raw"] = remediation_text

        return self.facts["remediation_config_raw"]

    def load_tags(self, name, load_file=True):
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
    def _load_from_file(name, parse_yaml=False):
        """
        Opens a config file and loads it as a string.

        :param name: type str
        :param parse_yaml: type boolean
        :return: content -> type str or type dict
        """
        with open(name) as f:
            content = f.read()

        if parse_yaml:
            import yaml
            content = yaml.safe_load(content)

        return content

    def _get_running_config(self):
        return NotImplemented

    def _get_compiled_config(self):
        return NotImplemented

    def _get_remediation_config(self):
        return NotImplemented
