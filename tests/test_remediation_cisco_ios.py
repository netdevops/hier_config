"""Integration tests for Cisco IOS unused object remediation."""

from hier_config import get_hconfig
from hier_config.models import Platform


def test_ios_unused_acl_detection() -> None:
    """Test detection of unused ACLs on Cisco IOS."""
    config_text = """
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
    config = get_hconfig(Platform.CISCO_IOS, config_text.strip())
    analysis = config.driver.find_unused_objects(config)

    unused_acls = analysis.unused_objects.get("ipv4-acl", ())
    assert len(unused_acls) == 1
    assert unused_acls[0].name == "UNUSED_ACL"


def test_ios_unused_prefix_list_detection() -> None:
    """Test detection of unused prefix-lists on Cisco IOS."""
    config_text = """
hostname TestRouter
!
ip prefix-list UNUSED_PL seq 5 permit 0.0.0.0/0 le 32
ip prefix-list USED_PL seq 5 permit 10.0.0.0/8 le 24
!
route-map TEST_RM permit 10
 match ip address prefix-list USED_PL
!
"""
    config = get_hconfig(Platform.CISCO_IOS, config_text.strip())
    analysis = config.driver.find_unused_objects(config)

    unused_pls = analysis.unused_objects.get("prefix-list", ())
    assert len(unused_pls) == 1
    assert unused_pls[0].name == "UNUSED_PL"


def test_ios_unused_route_map_detection() -> None:
    """Test detection of unused route-maps on Cisco IOS."""
    config_text = """
hostname TestRouter
!
route-map UNUSED_RM permit 10
 match ip address 1
!
route-map USED_RM permit 10
 match ip address 2
!
router bgp 65000
 neighbor 10.0.0.1 remote-as 65001
 neighbor 10.0.0.1 route-map USED_RM in
!
"""
    config = get_hconfig(Platform.CISCO_IOS, config_text.strip())
    analysis = config.driver.find_unused_objects(config)

    unused_rms = analysis.unused_objects.get("route-map", ())
    assert len(unused_rms) == 1
    assert unused_rms[0].name == "UNUSED_RM"


def test_ios_unused_class_map_detection() -> None:
    """Test detection of unused class-maps on Cisco IOS."""
    config_text = """
hostname TestRouter
!
class-map match-any UNUSED_CM
 match access-group name ACL1
!
class-map match-any USED_CM
 match access-group name ACL2
!
policy-map TEST_PM
 class USED_CM
  bandwidth 1000
!
"""
    config = get_hconfig(Platform.CISCO_IOS, config_text.strip())
    analysis = config.driver.find_unused_objects(config)

    unused_cms = analysis.unused_objects.get("class-map", ())
    assert len(unused_cms) == 1
    assert unused_cms[0].name == "UNUSED_CM"


def test_ios_unused_policy_map_detection() -> None:
    """Test detection of unused policy-maps on Cisco IOS."""
    config_text = """
hostname TestRouter
!
class-map match-any CM1
 match access-group name ACL1
!
policy-map UNUSED_PM
 class CM1
  bandwidth 1000
!
policy-map USED_PM
 class CM1
  bandwidth 2000
!
interface GigabitEthernet0/1
 service-policy output USED_PM
!
"""
    config = get_hconfig(Platform.CISCO_IOS, config_text.strip())
    analysis = config.driver.find_unused_objects(config)

    unused_pms = analysis.unused_objects.get("policy-map", ())
    assert len(unused_pms) == 1
    assert unused_pms[0].name == "UNUSED_PM"


def test_ios_unused_vrf_detection() -> None:
    """Test detection of unused VRFs on Cisco IOS."""
    config_text = """
hostname TestRouter
!
vrf definition UNUSED_VRF
 rd 65000:100
 address-family ipv4
 exit-address-family
!
vrf definition USED_VRF
 rd 65000:200
 address-family ipv4
 exit-address-family
!
interface GigabitEthernet0/1
 vrf forwarding USED_VRF
 ip address 10.0.0.1 255.255.255.0
!
"""
    config = get_hconfig(Platform.CISCO_IOS, config_text.strip())
    analysis = config.driver.find_unused_objects(config)

    unused_vrfs = analysis.unused_objects.get("vrf", ())
    assert len(unused_vrfs) == 1
    assert unused_vrfs[0].name == "UNUSED_VRF"


def test_ios_acl_on_vty_line() -> None:
    """Test ACL reference detection on VTY lines."""
    config_text = """
hostname TestRouter
!
ip access-list standard VTY_ACL
 permit 10.0.0.0 0.255.255.255
!
line vty 0 4
 access-class VTY_ACL in
!
"""
    config = get_hconfig(Platform.CISCO_IOS, config_text.strip())
    analysis = config.driver.find_unused_objects(config)

    unused_acls = analysis.unused_objects.get("ipv4-acl", ())
    assert len(unused_acls) == 0  # VTY_ACL is used


def test_ios_acl_in_crypto_map() -> None:
    """Test ACL reference detection in crypto maps."""
    config_text = """
hostname TestRouter
!
ip access-list extended CRYPTO_ACL
 permit ip 10.0.0.0 0.255.255.255 192.168.0.0 0.0.255.255
!
crypto map MYMAP 10 ipsec-isakmp
 match address CRYPTO_ACL
!
"""
    config = get_hconfig(Platform.CISCO_IOS, config_text.strip())
    analysis = config.driver.find_unused_objects(config)

    unused_acls = analysis.unused_objects.get("ipv4-acl", ())
    assert len(unused_acls) == 0  # CRYPTO_ACL is used


def test_ios_route_map_in_redistribution() -> None:
    """Test route-map reference detection in redistribution."""
    config_text = """
hostname TestRouter
!
route-map REDIST_RM permit 10
 match ip address 1
!
router ospf 1
 redistribute bgp 65000 route-map REDIST_RM
!
"""
    config = get_hconfig(Platform.CISCO_IOS, config_text.strip())
    analysis = config.driver.find_unused_objects(config)

    unused_rms = analysis.unused_objects.get("route-map", ())
    assert len(unused_rms) == 0  # REDIST_RM is used


def test_ios_route_map_in_pbr() -> None:
    """Test route-map reference detection in policy-based routing."""
    config_text = """
hostname TestRouter
!
route-map PBR_RM permit 10
 match ip address 100
 set ip next-hop 10.0.0.254
!
interface GigabitEthernet0/1
 ip policy route-map PBR_RM
!
"""
    config = get_hconfig(Platform.CISCO_IOS, config_text.strip())
    analysis = config.driver.find_unused_objects(config)

    unused_rms = analysis.unused_objects.get("route-map", ())
    assert len(unused_rms) == 0  # PBR_RM is used


def test_ios_removal_commands() -> None:
    """Test generation of removal commands for unused objects."""
    config_text = """
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
    config = get_hconfig(Platform.CISCO_IOS, config_text.strip())
    analysis = config.driver.find_unused_objects(config)

    # Check that removal commands are generated
    assert len(analysis.removal_commands) == 4
    removal_text = "\n".join(analysis.removal_commands)

    assert "no ip access-list extended UNUSED_ACL" in removal_text
    assert "no ip prefix-list UNUSED_PL" in removal_text
    assert "no route-map UNUSED_RM" in removal_text
    assert "no class-map match-any UNUSED_CM" in removal_text


def test_ios_case_insensitive_matching() -> None:
    """Test case-insensitive matching for IOS (IOS is case-insensitive)."""
    config_text = """
hostname TestRouter
!
ip access-list extended My_ACL
 permit ip any any
!
interface GigabitEthernet0/1
 ip access-group my_acl in
!
"""
    config = get_hconfig(Platform.CISCO_IOS, config_text.strip())
    analysis = config.driver.find_unused_objects(config)

    # My_ACL should not be considered unused (case-insensitive match with my_acl)
    unused_acls = analysis.unused_objects.get("ipv4-acl", ())
    assert len(unused_acls) == 0


def test_ios_complex_scenario() -> None:
    """Test complex scenario with multiple object types and references."""
    config_text = """
hostname TestRouter
!
ip access-list extended ACL_USED_IN_RM
 permit ip any any
!
ip access-list extended ACL_UNUSED
 deny ip any any
!
ip prefix-list PL_USED seq 5 permit 10.0.0.0/8
ip prefix-list PL_UNUSED seq 5 permit 192.168.0.0/16
!
route-map RM_USED permit 10
 match ip address ACL_USED_IN_RM
 match ip address prefix-list PL_USED
!
route-map RM_UNUSED permit 10
 match ip address 99
!
router bgp 65000
 neighbor 10.0.0.1 remote-as 65001
 neighbor 10.0.0.1 route-map RM_USED in
!
"""
    config = get_hconfig(Platform.CISCO_IOS, config_text.strip())
    analysis = config.driver.find_unused_objects(config)

    # Check unused objects
    unused_acls = analysis.unused_objects.get("ipv4-acl", ())
    assert len(unused_acls) == 1
    assert unused_acls[0].name == "ACL_UNUSED"

    unused_pls = analysis.unused_objects.get("prefix-list", ())
    assert len(unused_pls) == 1
    assert unused_pls[0].name == "PL_UNUSED"

    unused_rms = analysis.unused_objects.get("route-map", ())
    assert len(unused_rms) == 1
    assert unused_rms[0].name == "RM_UNUSED"


def test_ios_ipv6_acl_detection() -> None:
    """Test detection of unused IPv6 ACLs."""
    config_text = """
hostname TestRouter
!
ipv6 access-list UNUSED_V6_ACL
 permit ipv6 any any
!
ipv6 access-list USED_V6_ACL
 deny ipv6 any any
!
interface GigabitEthernet0/1
 ipv6 traffic-filter USED_V6_ACL in
!
"""
    config = get_hconfig(Platform.CISCO_IOS, config_text.strip())
    analysis = config.driver.find_unused_objects(config)

    unused_acls = analysis.unused_objects.get("ipv6-acl", ())
    assert len(unused_acls) == 1
    assert unused_acls[0].name == "UNUSED_V6_ACL"


def test_ios_bgp_address_family_references() -> None:
    """Test route-map and prefix-list references within BGP address families."""
    config_text = """
hostname TestRouter
!
ip prefix-list PL_AF seq 5 permit 10.0.0.0/8
route-map RM_AF permit 10
!
router bgp 65000
 address-family ipv4
  neighbor 10.0.0.1 remote-as 65001
  neighbor 10.0.0.1 prefix-list PL_AF in
  neighbor 10.0.0.1 route-map RM_AF out
 exit-address-family
!
"""
    config = get_hconfig(Platform.CISCO_IOS, config_text.strip())
    analysis = config.driver.find_unused_objects(config)

    # Both should be considered used
    unused_pls = analysis.unused_objects.get("prefix-list", ())
    assert len(unused_pls) == 0

    unused_rms = analysis.unused_objects.get("route-map", ())
    assert len(unused_rms) == 0


def test_ios_control_plane_policy() -> None:
    """Test policy-map reference on control-plane."""
    config_text = """
hostname TestRouter
!
class-map match-any CM1
 match access-group name ACL1
!
policy-map COPP_POLICY
 class CM1
  police 1000000
!
control-plane
 service-policy input COPP_POLICY
!
"""
    config = get_hconfig(Platform.CISCO_IOS, config_text.strip())
    analysis = config.driver.find_unused_objects(config)

    # Policy should be considered used
    unused_pms = analysis.unused_objects.get("policy-map", ())
    assert len(unused_pms) == 0
