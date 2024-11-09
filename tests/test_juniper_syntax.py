import pytest

from hier_config import Host
from hier_config.model import Platform


class TestJuniperSyntax:
    @pytest.fixture(autouse=True)
    def setUpClass(
        self,
        running_config_junos: str,
        running_config_flat_junos: str,
        generated_config_junos: str,
        generated_config_flat_junos: str,
        remediation_config_flat_junos: str,
    ) -> None:
        self.os = "junos"
        self.host = Host(Platform.JUNIPER_JUNOS)
        self.running_config_str = "set vlans switch_mgmt_10.0.2.0/24 vlan-id 2"
        self.generated_config_str = "set vlans switch_mgmt_10.0.3.0/24 vlan-id 3"
        self.remediation_str = "delete vlans switch_mgmt_10.0.2.0/24 vlan-id 2\nset vlans switch_mgmt_10.0.3.0/24 vlan-id 3"
        self.running_config_junos = running_config_junos
        self.running_config_flat_junos = running_config_flat_junos
        self.generated_config_junos = generated_config_junos
        self.generated_config_flat_junos = generated_config_flat_junos
        self.remediation_config_flat_junos = remediation_config_flat_junos

    def test_junos_basic_remediation(self) -> None:
        self.host.load_running_config(self.running_config_str)
        self.host.load_generated_config(self.generated_config_str)
        self.host.remediation_config()
        assert self.remediation_str == str(self.host.remediation_config())

    def test_junos_convert_to_set(self) -> None:
        self.host.load_running_config(self.running_config_junos)
        self.host.load_generated_config(self.generated_config_junos)
        assert self.remediation_config_flat_junos == str(self.host.remediation_config())

    def test_flat_junos_remediation(self) -> None:
        self.host.load_running_config(self.running_config_flat_junos)
        self.host.load_generated_config(self.generated_config_flat_junos)
        remediation_list = self.remediation_config_flat_junos.splitlines()
        for line in str(self.host.remediation_config()).splitlines():
            assert line in remediation_list
