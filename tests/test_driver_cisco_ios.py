from hier_config import get_hconfig_fast_load
from hier_config.constructors import get_hconfig
from hier_config.model import Platform


def test_logging_console_emergencies_scenario_1() -> None:
    platform = Platform.CISCO_IOS
    running_config = get_hconfig_fast_load(platform, ("no logging console",))
    generated_config = get_hconfig_fast_load(platform, ("logging console emergencies",))
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == ("logging console emergencies",)
    future_config = running_config.future(remediation_config)
    assert future_config.dump_simple() == ("logging console emergencies",)
    rollback = future_config.config_to_get_to(running_config)
    assert rollback.dump_simple() == ("no logging console",)
    running_after_rollback = future_config.future(rollback)

    assert not list(running_config.unified_diff(running_after_rollback))


def test_logging_console_emergencies_scenario_2() -> None:
    platform = Platform.CISCO_IOS
    running_config = get_hconfig_fast_load(platform, ("logging console",))
    generated_config = get_hconfig_fast_load(platform, ("logging console emergencies",))
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == ("logging console emergencies",)
    future_config = running_config.future(remediation_config)
    assert future_config.dump_simple() == ("logging console emergencies",)
    rollback = future_config.config_to_get_to(running_config)
    assert rollback.dump_simple() == ("logging console",)
    running_after_rollback = future_config.future(rollback)

    assert not list(running_config.unified_diff(running_after_rollback))


def test_logging_console_emergencies_scenario_3() -> None:
    platform = Platform.CISCO_IOS
    running_config = get_hconfig(platform)
    generated_config = get_hconfig_fast_load(platform, ("logging console emergencies",))
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == ("logging console emergencies",)
    future_config = running_config.future(remediation_config)
    assert future_config.dump_simple() == ("logging console emergencies",)
    rollback = future_config.config_to_get_to(running_config)
    assert rollback.dump_simple() == ("logging console debugging",)
    running_after_rollback = future_config.future(rollback)

    assert not list(running_config.unified_diff(running_after_rollback))
