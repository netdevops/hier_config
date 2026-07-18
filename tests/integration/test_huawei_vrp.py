from hier_config import HConfig
from hier_config.models import Platform


def test_merge_with_undo() -> None:
    platform = Platform.HUAWEI_VRP
    running_config = HConfig.from_lines(
        platform, ("test_for_undo", "undo test_for_redo")
    )
    generated_config = HConfig.from_lines(
        platform, ("undo test_for_undo", "test_for_redo")
    )
    remediation_config = running_config.remediation(generated_config)
    assert remediation_config.to_lines() == ("undo test_for_undo", "test_for_redo")


def test_negate_description() -> None:
    platform = Platform.HUAWEI_VRP
    running_config = HConfig.from_lines(
        platform, ("interface GigabitEthernet0/0/0", " description some old blabla")
    )
    generated_config = HConfig.from_lines(
        platform, ("interface GigabitEthernet0/0/0",)
    )
    remediation_config = running_config.remediation(generated_config)
    assert remediation_config.to_lines() == (
        "interface GigabitEthernet0/0/0",
        "  undo description",
    )


def test_negate_remark() -> None:
    platform = Platform.HUAWEI_VRP
    running_config = HConfig.from_lines(
        platform, ("acl number 2000", " rule 5 remark some old remark")
    )
    generated_config = HConfig.from_lines(platform, ("acl number 2000",))
    remediation_config = running_config.remediation(generated_config)
    assert remediation_config.to_lines() == (
        "acl number 2000",
        "  undo rule 5 remark",
    )


def test_negate_alias() -> None:
    platform = Platform.HUAWEI_VRP
    running_config = HConfig.from_lines(
        platform, ("interface GigabitEthernet0/0/0", " alias some old alias")
    )
    generated_config = HConfig.from_lines(
        platform, ("interface GigabitEthernet0/0/0",)
    )
    remediation_config = running_config.remediation(generated_config)
    assert remediation_config.to_lines() == (
        "interface GigabitEthernet0/0/0",
        "  undo alias",
    )


def test_negate_snmp_agent_community() -> None:
    platform = Platform.HUAWEI_VRP
    running_config = HConfig.from_lines(
        platform, ("snmp-agent community read cipher %^%#blabla%^%# acl 2000",)
    )
    generated_config = HConfig.from_text(platform)
    remediation_config = running_config.remediation(generated_config)
    assert remediation_config.to_lines() == (
        "undo snmp-agent community read cipher %^%#blabla%^%#",
    )


def test_comments_stripped() -> None:
    platform = Platform.HUAWEI_VRP
    config = HConfig.from_lines(
        platform,
        (
            "#",
            "! this is a comment",
            "interface GigabitEthernet0/0/0",
            " # another comment",
            " description test",
            "! yet another comment",
        ),
    )
    assert config.to_lines() == (
        "interface GigabitEthernet0/0/0",
        "  description test",
    )


def test_multiple_peer_public_keys_no_duplicate_child_error() -> None:
    platform = Platform.HUAWEI_VRP
    config = HConfig.from_text(
        platform,
        "rsa peer-public-key user1 encoding-type openssh\n"
        " public-key-code begin\n"
        "  AAAAB3Nza1\n"
        "  C1yc2EAAA\n"
        " public-key-code end\n"
        "peer-public-key end\n"
        "#\n"
        "rsa peer-public-key user2 encoding-type openssh\n"
        " public-key-code begin\n"
        "  DDDDB3Nza2\n"
        " public-key-code end\n"
        "peer-public-key end\n"
        "#\n",
    )
    assert config.to_lines() == (
        "rsa peer-public-key user1 encoding-type openssh",
        "  public-key-code begin",
        "    AAAAB3Nza1",
        "    C1yc2EAAA",
        "  public-key-code end",
        "  peer-public-key end",
        "rsa peer-public-key user2 encoding-type openssh",
        "  public-key-code begin",
        "    DDDDB3Nza2",
        "  public-key-code end",
        "  peer-public-key end",
    )


def test_sectional_exit_is_quit() -> None:
    platform = Platform.HUAWEI_VRP
    config = HConfig.from_lines(
        platform,
        (
            "interface GigabitEthernet0/0/0",
            " description test",
        ),
    )
    assert config.to_lines(sectional_exiting=True) == (
        "interface GigabitEthernet0/0/0",
        "  description test",
        "  quit",
    )
