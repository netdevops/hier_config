from hier_config import get_hconfig_fast_load
from hier_config.constructors import get_hconfig
from hier_config.models import Platform


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

    assert not tuple(running_config.unified_diff(running_after_rollback))


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

    assert not tuple(running_config.unified_diff(running_after_rollback))


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

    assert not tuple(running_config.unified_diff(running_after_rollback))


def test_duplicate_child_router() -> None:
    platform = Platform.CISCO_IOS
    running_config = get_hconfig_fast_load(
        platform,
        (
            "router eigrp EIGRP_INSTANCE",
            " address-family ipv4 unicast autonomous-system 10000",
            "  af-interface default",
            "   passive-interface",
            "  exit-af-interface",
            "  af-interface Vlan100",
            "   no passive-interface",
            "  exit-af-interface",
            "  af-interface GigabitEthernet0/0/1",
            "   no passive-interface",
            "  exit-af-interface",
            "  topology base",
            "   default-metric 1500 100 255 1 1500",
            "   redistribute bgp 65001",
            "  exit-af-topology",
            "  network 10.0.0.0",
            " exit-address-family",
        ),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "router eigrp EIGRP_INSTANCE",
            " address-family ipv4 unicast autonomous-system 10000",
            "  af-interface default",
            "   passive-interface",
            "  exit-af-interface",
            "  af-interface Vlan100",
            "   no passive-interface",
            "  exit-af-interface",
            "  af-interface GigabitEthernet0/0/1",
            "   no passive-interface",
            "  exit-af-interface",
            "  topology base",
            "   default-metric 1500 100 255 1 1500",
            "   redistribute bgp 65001 route-map ROUTE_MAP_IN",
            "  exit-af-topology",
            "  network 10.0.0.0",
            " exit-address-family",
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "router eigrp EIGRP_INSTANCE",
        "  address-family ipv4 unicast autonomous-system 10000",
        "    topology base",
        "      no redistribute bgp 65001",
        "      redistribute bgp 65001 route-map ROUTE_MAP_IN",
    )
