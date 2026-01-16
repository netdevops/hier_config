"""End-to-end tests for WorkflowRemediation with unused object remediation."""

from hier_config import get_hconfig
from hier_config.models import Platform
from hier_config.workflows import WorkflowRemediation


def test_workflow_unused_object_remediation_basic() -> None:
    """Test basic unused object remediation through WorkflowRemediation."""
    running_config_text = """
hostname TestRouter
!
ip access-list extended UNUSED_ACL
 permit ip any any
!
ip access-list extended USED_ACL
 deny ip any any
!
interface GigabitEthernet0/1
 ip address 10.0.0.1 255.255.255.0
 ip access-group USED_ACL in
!
"""
    generated_config_text = """
hostname TestRouter
!
interface GigabitEthernet0/1
 ip address 10.0.0.1 255.255.255.0
!
"""

    running_config = get_hconfig(Platform.CISCO_IOS, running_config_text.strip())
    generated_config = get_hconfig(Platform.CISCO_IOS, generated_config_text.strip())

    workflow = WorkflowRemediation(running_config, generated_config)
    cleanup_config = workflow.unused_object_remediation()

    cleanup_text = "\n".join(
        c.cisco_style_text() for c in cleanup_config.all_children_sorted()
    )

    # Should remove UNUSED_ACL but not USED_ACL
    assert "no ip access-list extended UNUSED_ACL" in cleanup_text
    assert "no ip access-list extended USED_ACL" not in cleanup_text


def test_workflow_unused_object_remediation_selective() -> None:
    """Test selective unused object remediation by object type."""
    running_config_text = """
hostname TestRouter
!
ip access-list extended UNUSED_ACL
 permit ip any any
!
ip prefix-list UNUSED_PL seq 5 permit 0.0.0.0/0
!
route-map UNUSED_RM permit 10
!
"""
    generated_config_text = """
hostname TestRouter
!
"""

    running_config = get_hconfig(Platform.CISCO_IOS, running_config_text.strip())
    generated_config = get_hconfig(Platform.CISCO_IOS, generated_config_text.strip())

    workflow = WorkflowRemediation(running_config, generated_config)

    # Only clean up ACLs
    acl_cleanup = workflow.unused_object_remediation(object_types=["ipv4-acl"])
    acl_cleanup_text = "\n".join(
        c.cisco_style_text() for c in acl_cleanup.all_children_sorted()
    )

    assert "no ip access-list extended UNUSED_ACL" in acl_cleanup_text
    assert "prefix-list" not in acl_cleanup_text
    assert "route-map" not in acl_cleanup_text


def test_workflow_combined_remediation() -> None:
    """Test combining standard remediation with cleanup remediation."""
    running_config_text = """
hostname TestRouter
!
ip access-list extended UNUSED_ACL
 permit ip any any
!
interface GigabitEthernet0/1
 ip address 10.0.0.1 255.255.255.0
!
"""
    generated_config_text = """
hostname TestRouter
!
interface GigabitEthernet0/1
 ip address 10.0.0.2 255.255.255.0
!
"""

    running_config = get_hconfig(Platform.CISCO_IOS, running_config_text.strip())
    generated_config = get_hconfig(Platform.CISCO_IOS, generated_config_text.strip())

    workflow = WorkflowRemediation(running_config, generated_config)

    # Get standard remediation
    standard_remediation = workflow.remediation_config

    # Get cleanup remediation
    cleanup_remediation = workflow.unused_object_remediation()

    # Combine both - merge each one separately
    combined = get_hconfig(Platform.CISCO_IOS, "")
    combined.merge(standard_remediation)
    # For cleanup, manually add children that don't already exist
    for child in cleanup_remediation.all_children():
        if not combined.children.get(child.text):
            combined.add_shallow_copy_of(child)

    combined_text = "\n".join(
        c.cisco_style_text() for c in combined.all_children_sorted()
    )

    # Should have both IP address change and ACL cleanup
    assert "interface GigabitEthernet0/1" in combined_text
    assert "ip address 10.0.0.2 255.255.255.0" in combined_text
    assert "no ip access-list extended UNUSED_ACL" in combined_text


def test_workflow_no_unused_objects() -> None:
    """Test workflow when there are no unused objects."""
    running_config_text = """
hostname TestRouter
!
ip access-list extended USED_ACL
 permit ip any any
!
interface GigabitEthernet0/1
 ip address 10.0.0.1 255.255.255.0
 ip access-group USED_ACL in
!
"""
    generated_config_text = """
hostname TestRouter
!
interface GigabitEthernet0/1
 ip address 10.0.0.1 255.255.255.0
!
"""

    running_config = get_hconfig(Platform.CISCO_IOS, running_config_text.strip())
    generated_config = get_hconfig(Platform.CISCO_IOS, generated_config_text.strip())

    workflow = WorkflowRemediation(running_config, generated_config)
    cleanup_config = workflow.unused_object_remediation()

    cleanup_text = "\n".join(
        c.cisco_style_text() for c in cleanup_config.all_children_sorted()
    )

    # Should be empty or minimal
    assert len(cleanup_text) == 0


def test_workflow_multiple_object_types() -> None:
    """Test cleanup of multiple object types."""
    running_config_text = """
hostname TestRouter
!
ip access-list extended UNUSED_ACL
 permit ip any any
!
ip prefix-list UNUSED_PL seq 5 permit 0.0.0.0/0
!
route-map UNUSED_RM permit 10
!
class-map match-any UNUSED_CM
 match access-group name ACL1
!
"""
    generated_config_text = """
hostname TestRouter
!
"""

    running_config = get_hconfig(Platform.CISCO_IOS, running_config_text.strip())
    generated_config = get_hconfig(Platform.CISCO_IOS, generated_config_text.strip())

    workflow = WorkflowRemediation(running_config, generated_config)
    cleanup_config = workflow.unused_object_remediation()

    cleanup_text = "\n".join(
        c.cisco_style_text() for c in cleanup_config.all_children_sorted()
    )

    # Should remove all unused objects
    assert "no ip access-list extended UNUSED_ACL" in cleanup_text
    assert "no ip prefix-list UNUSED_PL" in cleanup_text
    assert "no route-map UNUSED_RM" in cleanup_text
    assert "no class-map match-any UNUSED_CM" in cleanup_text


def test_workflow_with_nxos() -> None:
    """Test unused object remediation with NX-OS."""
    running_config_text = """
hostname NX-OS-Switch
!
ip access-list UNUSED_ACL
 permit ip any any
!
ip access-list USED_ACL
 deny ip any any
!
interface Ethernet1/1
 ip port access-group USED_ACL in
!
"""
    generated_config_text = """
hostname NX-OS-Switch
!
interface Ethernet1/1
 ip address 10.0.0.1/24
!
"""

    running_config = get_hconfig(Platform.CISCO_NXOS, running_config_text.strip())
    generated_config = get_hconfig(Platform.CISCO_NXOS, generated_config_text.strip())

    workflow = WorkflowRemediation(running_config, generated_config)
    cleanup_config = workflow.unused_object_remediation()

    cleanup_text = "\n".join(
        c.cisco_style_text() for c in cleanup_config.all_children_sorted()
    )

    # Should remove UNUSED_ACL
    assert "no ip access-list UNUSED_ACL" in cleanup_text


def test_workflow_removal_ordering() -> None:
    """Test that removal commands are properly ordered by weight."""
    running_config_text = """
hostname TestRouter
!
vrf definition UNUSED_VRF
 rd 65000:100
!
ip prefix-list UNUSED_PL seq 5 permit 0.0.0.0/0
!
route-map UNUSED_RM permit 10
!
class-map match-any UNUSED_CM
 match access-group name ACL1
!
policy-map UNUSED_PM
 class UNUSED_CM
  bandwidth 1000
!
"""
    generated_config_text = """
hostname TestRouter
!
"""

    running_config = get_hconfig(Platform.CISCO_IOS, running_config_text.strip())
    generated_config = get_hconfig(Platform.CISCO_IOS, generated_config_text.strip())

    workflow = WorkflowRemediation(running_config, generated_config)
    cleanup_config = workflow.unused_object_remediation()

    cleanup_commands = [
        c.cisco_style_text() for c in cleanup_config.all_children_sorted()
    ]

    # VRF (weight 200) should be removed last
    # Policy-map (weight 110) should be removed first
    # Find indices
    vrf_idx = next(
        i for i, cmd in enumerate(cleanup_commands) if "vrf definition" in cmd
    )
    pm_idx = next(
        i for i, cmd in enumerate(cleanup_commands) if "policy-map" in cmd
    )

    # Policy-map should come before VRF
    assert pm_idx < vrf_idx


def test_workflow_empty_running_config() -> None:
    """Test with empty running configuration."""
    running_config_text = ""
    generated_config_text = """
hostname TestRouter
!
"""

    running_config = get_hconfig(Platform.CISCO_IOS, running_config_text)
    generated_config = get_hconfig(Platform.CISCO_IOS, generated_config_text.strip())

    workflow = WorkflowRemediation(running_config, generated_config)
    cleanup_config = workflow.unused_object_remediation()

    cleanup_text = "\n".join(
        c.cisco_style_text() for c in cleanup_config.all_children_sorted()
    )

    # Should be empty
    assert len(cleanup_text) == 0
