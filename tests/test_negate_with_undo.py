import pytest

from hier_config.host import Host


class TestNegateWithUndo:
    @pytest.fixture(autouse=True)
    def setUpClass(self, options_negate_with_undo):
        self.os = "comware5"
        self.running_cfg = "test_for_undo\nundo test_for_redo\n"
        self.generated_cfg = "undo test_for_undo\ntest_for_redo\n"
        self.remediation = "undo test_for_undo\ntest_for_redo\n"
        self.host_a = Host("example1.rtr", self.os, options_negate_with_undo)

    def test_merge(self):
        self.host_a.load_config("running", self.running_cfg)
        self.host_a.load_config("generated", self.generated_cfg)
        self.host_a.load_remediation()
        assert self.remediation == self.host_a.facts["remediation_config_raw"]
