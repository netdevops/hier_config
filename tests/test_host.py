from hier_config.host import Host

import unittest
import os
import yaml


class TestHost(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.running_file = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            'files',
            'running_config.conf'
        )
        cls.compiled_file = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            'files',
            'compiled_config.conf'
        )
        cls.options_file = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            'files',
            'test_options_ios.yml'
        )
        cls.tags_file = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            'files',
            'test_tags_ios.yml'
        )
        cls.hconfig_tags = yaml.load(open(cls.tags_file))
        cls.hconfig_options = yaml.load(open(cls.options_file))
        cls.host = Host('example.rtr', 'ios', cls.hconfig_options)

        with open(cls.compiled_file) as f:
            cls.compiled_string = f.read()

    def test_load_config_from(self):
        self.host.load_config_from(config_type="running", name=self.running_file)
        self.host.load_config_from(config_type="compiled", name=self.compiled_string, file=False)

        self.assertTrue(len(self.host.compiled_config) > 0)
        self.assertTrue(len(self.host.running_config) > 0)

    def test_load_remediation(self):
        self.host.load_remediation()
        self.assertTrue(len(self.host.remediation_config) > 0)

    def test_load_tags(self):
        self.host.load_tags(self.tags_file)
        self.assertTrue(len(self.host.hconfig_tags) > 0)

        self.host.load_tags(self.hconfig_tags, file=False)
        self.assertTrue(len(self.host.hconfig_tags) > 0)

    def test_tagged_remediation(self):
        self.host.load_config_from(config_type="running", name=self.running_file)
        self.host.load_config_from(config_type="compiled", name=self.compiled_file)
        self.host.load_remediation()

        rem1 = self.host.facts['remediation_config_raw']

        self.host.load_tags(self.hconfig_tags, file=False)
        self.host.load_remediation(include_tags='safe')

        rem2 = self.host.facts['remediation_config_raw']

        self.assertNotEqual(rem1, rem2)


if __name__ == "__main__":
    unittest.main(failfast=True)
