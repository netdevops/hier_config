import unittest
import tempfile
import os
import yaml
import types

from hier_config import HConfig
from hier_config.host import Host


class TestNegateWithUndo(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.os = 'comware5'
        cls.options_file = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            'files',
            'test_options_negate_with_undo.yml',
        )
        cls.running_cfg = 'test_for_undo\nundo test_for_redo\n'
        cls.compiled_cfg = 'undo test_for_undo\ntest_for_redo\n'
        cls.remediation = 'undo test_for_undo\ntest_for_redo\n'

        with open(cls.options_file) as f:
            cls.options = yaml.safe_load(f.read())

        cls.host_a = Host('example1.rtr', cls.os, cls.options)

    def test_merge(self):
        self.host_a.load_config_from(config_type="running", name=self.running_cfg, load_file=False)
        self.host_a.load_config_from(config_type="compiled", name=self.compiled_cfg, load_file=False)
        self.host_a.load_remediation()

        self.assertEqual(self.remediation, self.host_a.facts['remediation_config_raw'])

if __name__ == "__main__":
    unittest.main(failfast=True)
