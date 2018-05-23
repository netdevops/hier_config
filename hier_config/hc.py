import yaml
import os as pyos
import hier_config


class HConfigRunner:
    """
    Helper class to obtain delta between running and expected config. Options and
    tags, should be named "{os}_options.yml" and "{os}_tags.yml" respectively
    """

    def __init__(self, hostname, os, root_dir=None):
        self.hostname = hostname
        self.os = os

        if pyos.environ.get('HC_ROOT_DIR') and not root_dir:
            root_dir = pyos.environ['HC_ROOT_DIR']
        elif not root_dir:
            root_dir = str(pyos.path.dirname(pyos.path.dirname(pyos.path.realpath(__file__)))) + '/tests/files/test_'
        option_pth_str = '{}options_{}.yml'.format(root_dir, self.os)
        tags_pth_str = '{}tags_{}.yml'.format(root_dir, self.os)

        self.options = yaml.load(open(option_pth_str))
        self.tags = yaml.load(open(tags_pth_str))

    def hc_from_file(self, run_config, expected_config, return_type='list'):

        # Build HConfig object for the Running Config

        running_config_hier = hier_config.HConfig(self.hostname, self.os, self.options)
        running_config_hier.load_from_file(run_config)

        # Build Hierarchical Configuration object for the Compiled Config

        expected_config_hier = hier_config.HConfig(self.hostname, self.os, self.options)
        expected_config_hier.load_from_file(expected_config)
        return self._hc_load_and_return(running_config_hier, expected_config_hier, return_type)

    def hc_from_string(self, run_config, expected_config, return_type='list'):

        # Build HConfig object for the Running Config

        running_config_hier = hier_config.HConfig(self.hostname, self.os, self.options)
        running_config_hier.load_from_str(run_config)

        # Build Hierarchical Configuration object for the Compiled Config

        expected_config_hier = hier_config.HConfig(self.hostname, self.os, self.options)
        expected_config_hier.load_from_file(expected_config)
        return self._hc_load_and_return(running_config_hier, expected_config_hier, return_type)

    def _hc_load_and_return(self, running_config_hier, expected_config_hier, return_type):
        # Build Hierarchical Configuration object for the Remediation Config

        remediation_config_hier = running_config_hier.config_to_get_to(expected_config_hier)
        remediation_config_hier.add_sectional_exiting()
        remediation_config_hier.add_tags(self.tags)

        list_of_lines = []
        for line in remediation_config_hier.all_children():
            list_of_lines.append(line.cisco_style_text())
        if return_type == 'string':
            return ''.join(list_of_lines)
        elif return_type == 'list':
            return list_of_lines
        else:
            raise Exception('"return_type" not one of ["string", "list"]')
