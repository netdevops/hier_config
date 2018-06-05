from hier_config import HConfig


class HierConfig(HConfig):

    """
    HierConfig will be the replacement of HConfig.
    The advantage is being able to load a single Host
    object into HConfig, rather than individual hostname,
    os, and options variables.

    """

    def __init__(self, host):
        self._host = host

        super().__init__(self.host.hostname, self.host.os, self.host.options)

    @property
    def __repr__(self):
        return 'HierConfig({})'.format(self.host)

    @property
    def host(self):
        return self._host
