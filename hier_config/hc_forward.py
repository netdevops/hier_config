from hier_config import HConfig


class HierConfig(HConfig):

    """
    HierConfig will be the replacement of HConfig.
    The advantage is being able to load a single Host
    object into HConfig, rather than individual hostname,
    os, and options variables.

    ..code:: python

        from hier_config.host import Host
        from hier_config.hc_forward import HierConfig

        import yaml

        options = yaml.load(open('./tests/files/test_options_ios.yml'))
        host = Host('example.rtr', 'ios', options)
        hier = HierConfig(host)

    """

    def __init__(self, host):
        self.host = host

        super().__init__(self.host.hostname, self.host.os, self.host.options)

    def __repr__(self):
        return 'HierConfig({})'.format(self.host)
