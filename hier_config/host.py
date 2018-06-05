class Host:

    """
    A host object is a convenient way to loading host inventory
    items into a single object.

    The default is to load "hostname", "os", and "options" to the host object,
    however, it can easily be extended for developer needs.

    :param hostname: type str
    :param os: type str
    :param options: type dict

    :return: Host Object

    .. code:: python
        import yaml
        from hier_config.host import Host

        options = yaml.load(open('./tests/files/test_options_ios.yml'))
        host = Host('example.rtr', 'ios', options)

        # Example of easily extending the host object
        host.facts['chassis_model'] = 'WS-C4948E'

    """

    def __init__(self, hostname, os, hconfig_options):
        self.hostname = hostname
        self.os = os
        self.hconfig_options = hconfig_options
        self.facts = dict()

    def __repr__(self):
        return 'Host(hostname={})'.format(self.hostname)
