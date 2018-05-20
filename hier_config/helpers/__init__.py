"""
Place any reusable functions for parsing HConfig object here
"""


def get_interfaces_for_vrf(config, vrf):
    """

    :param config: HierarchicalConfigurationRoot instance
    :param vrf: str name of VRF
    :yields: interface
    """
    tests = [
        # IOS-XR
        'vrf {}',
        # NXOS
        'vrf member {}',
        # IOS IPv4
        'ip vrf forwarding {}',
        # EOS and IOS IPv6
        'vrf forwarding {}'
    ]
    for interface in config.get_children('startswith', 'interface'):
        if any([t.format(vrf) in interface for t in tests]):
            yield interface


def get_hostname(config):
    hier_hostname = config.get_child('startswith', 'hostname ')
    if hier_hostname:
        return hier_hostname.text.split()[1]
    # There are cases where there is not a hostname defined in RC on N7ks,
    # defined instead under VDC
    else:
        return config.host.hostname


def to_list(obj):
    if isinstance(obj, list):
        return obj
    else:
        return [obj]
