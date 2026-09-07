"""Tests for HP Comware 5 driver functionality."""

import pytest

from hier_config import WorkflowRemediation, get_hconfig
from hier_config.models import Platform


@pytest.mark.displaced_by("corpus:hp_comware5/negation_prefix")
def test_hp_comware5_negation_prefix() -> None:
    """Test that HP Comware 5 uses 'undo ' as its negation prefix."""
    running = (
        "interface GigabitEthernet1/0/1\n"
        " port link-mode bridge\n"
        " port link-type trunk\n"
        " port trunk permit vlan 10 20\n"
    )
    intended = (
        "interface GigabitEthernet1/0/1\n"
        " port link-mode bridge\n"
        " port link-type trunk\n"
        " port trunk permit vlan 10\n"
    )

    workflow = WorkflowRemediation(
        get_hconfig(Platform.HP_COMWARE5, running),
        get_hconfig(Platform.HP_COMWARE5, intended),
    )
    rem_lines = [
        line.cisco_style_text()
        for line in workflow.remediation_config.all_children_sorted()
    ]

    assert "interface GigabitEthernet1/0/1" in rem_lines
    assert "  undo port trunk permit vlan 10 20" in rem_lines
    assert "  port trunk permit vlan 10" in rem_lines


@pytest.mark.displaced_by("corpus:hp_comware5/remediation_and_rollback_round_trip")
def test_hp_comware5_remediation_and_rollback_round_trip() -> None:
    """Test full remediation and rollback workflow with Comware 5 undo prefix."""
    running = (
        "interface Vlan-interface10\n"
        " ip address 10.10.10.1 255.255.255.0\n"
        " description Management\n"
    )
    intended = (
        "interface Vlan-interface10\n"
        " ip address 10.10.10.254 255.255.255.0\n"
        " description Corporate-Mgmt\n"
    )

    running_config = get_hconfig(Platform.HP_COMWARE5, running)
    intended_config = get_hconfig(Platform.HP_COMWARE5, intended)

    remediation = running_config.config_to_get_to(intended_config)
    rem_text = "\n".join(
        line.cisco_style_text() for line in remediation.all_children_sorted()
    )

    assert "undo ip address 10.10.10.1 255.255.255.0" in rem_text
    assert "ip address 10.10.10.254 255.255.255.0" in rem_text

    # Compute rollback to revert intended to running
    rollback = intended_config.config_to_get_to(running_config)
    rb_text = "\n".join(
        line.cisco_style_text() for line in rollback.all_children_sorted()
    )

    assert "undo ip address 10.10.10.254 255.255.255.0" in rb_text
    assert "ip address 10.10.10.1 255.255.255.0" in rb_text
