import pytest

from hier_config import get_hconfig_fast_load
from hier_config.exceptions import DuplicateChildError
from hier_config.models import Platform
from hier_config.utils import load_hconfig_v2_options


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
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "no snmp-server community public",
        "snmp-server community examplekey1",
        "snmp-server community examplekey2",
        "snmp-server host 192.2.0.1 trap version v2c community examplekey1",
        "snmp-server host 192.2.0.2 trap version v2c community examplekey2",
        "snmp-server host 192.2.0.3 trap version v2c community examplekey3",
    )


def test_generic_snmp_scenario_2() -> None:
    platform = Platform.GENERIC
    driver = load_hconfig_v2_options(
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
