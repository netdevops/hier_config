def _load_hier_options():
    """
    Loads the HierarchicalConfiguration options.
    """
    hier_options = dict()

    for netos in ['ios', 'nxos', 'iosxr', 'eos']:
        filename = os.path.join(
            CONF_DIR,
            'hierarchical_configuration_options_{}.yml'.format(netos))

        hier_options[netos] = H.read_yaml_file(filename)

    return hier_options


CONF_DIR = '/home/jame4848/hier_config/conf'
HIER_OPTIONS = _load_hier_options()
