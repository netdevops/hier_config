from hier_config import get_hconfig_fast_load
from hier_config.constructors import get_hconfig
from hier_config.models import Platform


def test_merge_with_undo() -> None:
    platform = Platform.HUAWEI_VRP
    running_config = get_hconfig_fast_load(
        platform, ("test_for_undo", "undo test_for_redo")
    )
    generated_config = get_hconfig_fast_load(
        platform, ("undo test_for_undo", "test_for_redo")
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == ("undo test_for_undo", "test_for_redo")


def test_negate_description() -> None:
    platform = Platform.HUAWEI_VRP
    running_config = get_hconfig_fast_load(
        platform, ("interface GigabitEthernet0/0/0", " description some old blabla")
    )
    generated_config = get_hconfig_fast_load(
        platform, ("interface GigabitEthernet0/0/0",)
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "interface GigabitEthernet0/0/0",
        "  undo description",
    )


def test_negate_remark() -> None:
    platform = Platform.HUAWEI_VRP
    running_config = get_hconfig_fast_load(
        platform, ("acl number 2000", " rule 5 remark some old remark")
    )
    generated_config = get_hconfig_fast_load(platform, ("acl number 2000",))
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "acl number 2000",
        "  undo rule 5 remark",
    )


def test_negate_alias() -> None:
    platform = Platform.HUAWEI_VRP
    running_config = get_hconfig_fast_load(
        platform, ("interface GigabitEthernet0/0/0", " alias some old alias")
    )
    generated_config = get_hconfig_fast_load(
        platform, ("interface GigabitEthernet0/0/0",)
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "interface GigabitEthernet0/0/0",
        "  undo alias",
    )


def test_negate_snmp_agent_community() -> None:
    platform = Platform.HUAWEI_VRP
    running_config = get_hconfig_fast_load(
        platform, ("snmp-agent community read cipher %^%#blabla%^%# acl 2000",)
    )
    generated_config = get_hconfig(platform)
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "undo snmp-agent community read cipher %^%#blabla%^%#",
    )


def test_comments_stripped() -> None:
    platform = Platform.HUAWEI_VRP
    config = get_hconfig_fast_load(
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
    assert config.dump_simple() == (
        "interface GigabitEthernet0/0/0",
        "  description test",
    )


def test_sectional_exit_is_quit() -> None:
    platform = Platform.HUAWEI_VRP
    config = get_hconfig_fast_load(
        platform,
        (
            "interface GigabitEthernet0/0/0",
            " description test",
        ),
    )
    assert config.dump_simple(sectional_exiting=True) == (
        "interface GigabitEthernet0/0/0",
        "  description test",
        "  quit",
    )
