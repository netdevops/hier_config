def _load_hier_options():
    import hier_config.helpers as H
    import os

    """
    Loads the HierarchicalConfiguration options.
    """
    hier_options = dict()

    for netos in ['ios', 'nxos', 'iosxr', 'eos']:
        filename = os.path.join(
            CONF_DIR,
            'hierarchical_configuration_options_{}.yml'.format(netos))

        if os.path.isfile(filename):
            hier_options[netos] = H.read_yaml_file(filename)
        else:
            open(filename, 'w').close()

    return hier_options


def _load_conf_dir():
    import os

    """
    Creates and Loads the HierarchicalConfiguraiton configuration directory.
    """

    if os.environ.get('HIER_CONF_DIR', None):
        return os.getenv('HIER_CONF_DIR')
    else:
        if os.path.isdir(os.path.expanduser('~/.hier_config')):
            return os.path.expanduser('~/.hier_config')
        else:
            os.makedirs(os.path.expanduser('~/.hier_config'))
            return os.path.expanduser('~/.hier_config')

CONF_DIR = _load_conf_dir()
HIER_OPTIONS = _load_hier_options()
