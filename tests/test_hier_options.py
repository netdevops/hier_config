import pytest

from hier_config.options import HConfigOptions


class TestHConfigOptions:
    @pytest.fixture(autouse=True)
    def setup(self, options_ios):
        self.options = options_ios

    def test_options(self):
        options = HConfigOptions("ios").options
        assert options == self.options
