from hier_config import WorkflowRemediation, get_hconfig, get_hconfig_fast_load
from hier_config.model import Platform


def test_junos_basic_remediation() -> None:
    platform = Platform.JUNIPER_JUNOS
    running_config_str = "set vlans switch_mgmt_10.0.2.0/24 vlan-id 2"
    generated_config_str = "set vlans switch_mgmt_10.0.3.0/24 vlan-id 3"
    remediation_str = "delete vlans switch_mgmt_10.0.2.0/24 vlan-id 2\nset vlans switch_mgmt_10.0.3.0/24 vlan-id 3"

    workflow_remediation = WorkflowRemediation(
        get_hconfig_fast_load(platform, running_config_str),
        get_hconfig_fast_load(platform, generated_config_str),
    )

    assert workflow_remediation.remediation_config_filtered_text() == remediation_str


def test_junos_convert_to_set(
    running_config_junos: str,
    generated_config_junos: str,
    remediation_config_flat_junos: str,
) -> None:
    platform = Platform.JUNIPER_JUNOS
    workflow_remediation = WorkflowRemediation(
        get_hconfig(platform, running_config_junos),
        get_hconfig(platform, generated_config_junos),
    )

    assert (
        workflow_remediation.remediation_config_filtered_text()
        == remediation_config_flat_junos
    )


def test_flat_junos_remediation(
    running_config_flat_junos: str,
    generated_config_flat_junos: str,
    remediation_config_flat_junos: str,
) -> None:
    platform = Platform.JUNIPER_JUNOS
    workflow_remediation = WorkflowRemediation(
        get_hconfig_fast_load(platform, running_config_flat_junos),
        get_hconfig_fast_load(platform, generated_config_flat_junos),
    )

    remediation_list = remediation_config_flat_junos.splitlines()
    for line in str(workflow_remediation.remediation_config).splitlines():
        assert line in remediation_list
