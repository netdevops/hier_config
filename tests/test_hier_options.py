import pytest

from hier_config.options import options_for


class TestHConfigOptions:
    @pytest.fixture(autouse=True)
    def setup(self, options_ios):
        self.ios_options = options_ios

    def test_options(self):
        assert self.ios_options == options_for("ios")
