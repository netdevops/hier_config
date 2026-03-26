import pytest

from hier_config import get_hconfig_fast_load
from hier_config.exceptions import DuplicateChildError
from hier_config.models import Platform
from hier_config.root import HConfig
from hier_config.utils import load_driver_rules


def test_generic_snmp_scenario_1() -> None:
    platform = Platform.GENERIC
    running_config = get_hconfig_fast_load(platform, ("snmp-server community public",))
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "snmp-server community examplekey1",
            "snmp-server community examplekey2",
            "snmp-server host 192.2.0.1 trap version v2c community examplekey1",
            "snmp-server host 192.2.0.2 trap version v2c community examplekey2",
            "snmp-server host 192.2.0.3 trap version v2c community examplekey3",
        ),
    )
    remediation_config = running_config.remediation(generated_config)
    assert remediation_config.to_lines() == (
        "no snmp-server community public",
        "snmp-server community examplekey1",
        "snmp-server community examplekey2",
        "snmp-server host 192.2.0.1 trap version v2c community examplekey1",
        "snmp-server host 192.2.0.2 trap version v2c community examplekey2",
        "snmp-server host 192.2.0.3 trap version v2c community examplekey3",
    )


def test_generic_snmp_scenario_2() -> None:
    platform = Platform.GENERIC
    driver = load_driver_rules(
        {
            "parent_allows_duplicate_child": [
                {"lineage": [{"startswith": ["snmp-server community"]}]},
            ],
        },
        platform,
    )
    with pytest.raises(DuplicateChildError):
        get_hconfig_fast_load(
            driver,
            (
                "snmp-server community <credentials_removed>",
                "snmp-server community <credentials_removed>",
                "snmp-server host 192.2.0.1 trap version v2c community <credentials_removed>",
                "snmp-server host 192.2.0.2 trap version v2c community <credentials_removed>",
                "snmp-server host 192.2.0.3 trap version v2c community <credentials_removed>",
            ),
        )


def test_generic_aaa_scenario_1() -> None:
    platform = Platform.GENERIC
    running_config = get_hconfig_fast_load(
        platform,
        (
            "aaa group server tacacs TACACS_GROUP1",
            "  server 192.2.0.3",
            "  server 192.2.0.7",
            "aaa group server radius RADIUS_GROUP1",
            "  server 192.2.0.121",
        ),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "aaa group server tacacs TACACS_GROUP2",
            "  server 192.2.0.3",
            "  server 192.2.0.7",
            "aaa group server radius RADIUS_GROUP2",
            "  server 192.2.0.121",
        ),
    )
    remediation_config = running_config.remediation(generated_config)
    assert remediation_config.to_lines() == (
        "no aaa group server tacacs TACACS_GROUP1",
        "no aaa group server radius RADIUS_GROUP1",
        "aaa group server tacacs TACACS_GROUP2",
        "  server 192.2.0.3",
        "  server 192.2.0.7",
        "aaa group server radius RADIUS_GROUP2",
        "  server 192.2.0.121",
    )


def test_generic_aaa_scenario_2() -> None:
    platform = Platform.GENERIC
    running_config = get_hconfig_fast_load(
        platform,
        (
            "aaa group server tacacs TACACS_GROUP1",
            "  server 192.2.0.3",
            "  server 192.2.0.7",
            "aaa group server radius RADIUS_GROUP1",
            "  server 192.2.0.121",
        ),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "aaa group server tacacs TACACS_GROUP2",
            "  server 192.2.0.3",
            "  server 192.2.0.7",
            "aaa group server radius RADIUS_GROUP2",
            "  server 192.2.0.121",
        ),
    )
    # Create a driver with ordering rules for aaa group server management
    driver = load_driver_rules(
        {
            "ordering": [
                {"lineage": [{"startswith": "aaa group server radius "}], "order": 520},
                {
                    "lineage": [{"re_search": "^no aaa group server tacacs "}],
                    "order": 510,
                },
                {
                    "lineage": [{"re_search": "^no aaa group server radius "}],
                    "order": 530,
                },
            ]
        },
        Platform.GENERIC,
    )

    base_remediation = running_config.remediation(generated_config)
    remediation_config = HConfig(driver)

    for child in base_remediation.children:
        if child.text.startswith("no aaa group server "):
            original_text = child.text.removeprefix("no ")
            running_section = running_config.children.get(original_text)
            if running_section:
                parent = remediation_config.add_child(original_text)
                for running_child in running_section.children:
                    parent.add_child(f"no {running_child.text}")
                protocol = " ".join(original_text.split()[:4])
                for new_child in base_remediation.children:
                    if new_child.text.startswith(
                        protocol
                    ) and not new_child.text.startswith("no "):
                        remediation_config.add_deep_copy_of(new_child)
                remediation_config.add_child(f"no {original_text}")

    remediation_config.set_order_weight()

    assert remediation_config.to_lines() == (
        "aaa group server tacacs TACACS_GROUP1",
        "  no server 192.2.0.3",
        "  no server 192.2.0.7",
        "aaa group server tacacs TACACS_GROUP2",
        "  server 192.2.0.3",
        "  server 192.2.0.7",
        "no aaa group server tacacs TACACS_GROUP1",
        "aaa group server radius RADIUS_GROUP1",
        "  no server 192.2.0.121",
        "aaa group server radius RADIUS_GROUP2",
        "  server 192.2.0.121",
        "no aaa group server radius RADIUS_GROUP1",
    )
