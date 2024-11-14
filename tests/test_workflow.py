import pytest

from hier_config import (
    WorkflowRemediation,
    get_hconfig,
)
from hier_config.models import Platform, TagRule


@pytest.fixture(name="wfr")
def workflow_remediation(
    running_config: str, generated_config: str
) -> WorkflowRemediation:
    return WorkflowRemediation(
        running_config=get_hconfig(Platform.CISCO_IOS, running_config),
        generated_config=get_hconfig(Platform.CISCO_IOS, generated_config),
    )


def test_config_lengths(wfr: WorkflowRemediation) -> None:
    assert wfr.running_config.children
    assert wfr.generated_config.children
    assert wfr.remediation_config.children
    assert wfr.rollback_config.children


def test_apply_tags(
    wfr: WorkflowRemediation, tag_rules_ios: tuple[TagRule, ...]
) -> None:
    wfr.apply_remediation_tag_rules(tag_rules_ios)
    assert len(wfr.remediation_config.tags) > 0


def test_remediation_config_filtered_text(
    wfr: WorkflowRemediation,
    tag_rules_ios: tuple[TagRule, ...],
    remediation_config_with_safe_tags: str,
    remediation_config_without_tags: str,
) -> None:
    wfr.apply_remediation_tag_rules(tag_rules_ios)

    rem1 = wfr.remediation_config_filtered_text(set(), set())
    rem2 = wfr.remediation_config_filtered_text({"safe"}, set())

    assert rem1 != rem2
    assert rem1 == remediation_config_without_tags
    assert rem2 == remediation_config_with_safe_tags


def test_remediation_config_driver_mismatch() -> None:
    # Test to ensure ValueError is raised for mismatched drivers
    running_config = get_hconfig(Platform.CISCO_IOS, "dummy_config")
    generated_config = get_hconfig(Platform.JUNIPER_JUNOS, "dummy_config")

    with pytest.raises(
        ValueError, match="The running and generated configs must use the same driver."
    ):
        WorkflowRemediation(running_config, generated_config)


def test_rollback_config_exists(wfr: WorkflowRemediation) -> None:
    # Check if rollback config is generated and accessible
    rollback_config = wfr.rollback_config
    assert rollback_config is not None
    assert len(rollback_config.children) > 0  # Ensure rollback config has content


def test_rollback_config_reverts_changes(wfr: WorkflowRemediation) -> None:
    # Test if rollback config correctly represents changes needed to revert generated to running
    rollback_config = wfr.rollback_config
    rollback_text = "\n".join(
        line.cisco_style_text() for line in rollback_config.all_children_sorted()
    )
    expected_text = "no vlan 4\nno interface Vlan4\nvlan 3\n  name switch_mgmt_10.0.4.0/24\ninterface Vlan2\n  no mtu 9000\n  no ip access-group TEST in\n  shutdown\ninterface Vlan3\n  description switch_mgmt_10.0.4.0/24\n  ip address 10.0.4.1 255.255.0.0"
    assert rollback_text == expected_text
