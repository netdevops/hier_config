from hier_config.constructors import get_hconfig
from hier_config.models import Platform


def test_rm_ipv6_acl_sequence_numbers() -> None:
    """Test post-load callback that removes IPv6 ACL sequence numbers."""
    platform = Platform.CISCO_IOS
    config_text = "ipv6 access-list TEST_IPV6_ACL\n sequence 10 permit tcp any any eq 443\n sequence 20 deny ipv6 any any"
    config = get_hconfig(platform, config_text)
    acl = config.get_child(equals="ipv6 access-list TEST_IPV6_ACL")

    assert acl is not None
    assert acl.get_child(equals="permit tcp any any eq 443") is not None
    assert acl.get_child(equals="deny ipv6 any any") is not None
    assert acl.get_child(startswith="sequence") is None


def test_remove_ipv4_acl_remarks() -> None:
    """Test post-load callback that removes IPv4 ACL remarks."""
    platform = Platform.CISCO_IOS
    config_text = "ip access-list extended TEST_ACL\n remark Allow HTTPS traffic\n permit tcp any any eq 443\n remark Block all other traffic\n deny ip any any"
    config = get_hconfig(platform, config_text)
    acl = config.get_child(equals="ip access-list extended TEST_ACL")

    assert acl is not None
    assert acl.get_child(equals="10 permit tcp any any eq 443") is not None
    assert acl.get_child(equals="20 deny ip any any") is not None
    assert acl.get_child(startswith="remark") is None


def test_add_acl_sequence_numbers() -> None:
    """Test post-load callback that adds sequence numbers to IPv4 ACLs."""
    platform = Platform.CISCO_IOS
    config_text = "ip access-list extended TEST_ACL\n permit tcp any any eq 443\n permit tcp any any eq 80\n deny ip any any"
    config = get_hconfig(platform, config_text)
    acl = config.get_child(equals="ip access-list extended TEST_ACL")

    assert acl is not None
    assert acl.get_child(equals="10 permit tcp any any eq 443") is not None
    assert acl.get_child(equals="20 permit tcp any any eq 80") is not None
    assert acl.get_child(equals="30 deny ip any any") is not None
