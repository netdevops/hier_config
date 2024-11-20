from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from hier_config import Platform
from hier_config.models import (
    MatchRule,
    TagRule,
)
from hier_config.utils import (
    hconfig_v2_os_v3_platform_mapper,
    hconfig_v3_platform_v2_os_mapper,
    load_device_config,
    load_hconfig_v2_options,
    load_hconfig_v2_tags,
    load_hier_config_tags,
)


@pytest.fixture
def temporary_file_fixture(tmp_path: Path) -> tuple[Path, str]:
    file_path = tmp_path / "temp_config.conf"
    content = "interface GigabitEthernet0/1\n ip address 192.168.1.1 255.255.255.0\n no shutdown"
    file_path.write_text(content)
    return file_path, content


def test_load_device_config_success(temporary_file_fixture: tuple[Path, str]) -> None:
    """Test that the function successfully loads a valid configuration file."""
    # pylint: disable=redefined-outer-name
    file_path, expected_content = temporary_file_fixture
    result = load_device_config(str(file_path))
    assert result == expected_content, "File content should match expected content."


def test_load_device_config_file_not_found() -> None:
    """Test that the function raises FileNotFoundError when the file does not exist."""
    with pytest.raises(FileNotFoundError):
        load_device_config("non_existent_file.conf")


def test_load_device_config_empty_file(tmp_path: Path) -> None:
    """Test that the function correctly handles an empty configuration file."""
    empty_file = tmp_path / "empty.conf"
    empty_file.write_text("")
    result = load_device_config(str(empty_file))
    assert not result, "Empty file should return an empty string."


def test_load_hier_config_tags_success(tags_file_path: str) -> None:
    """Test that valid tags from the tag_rules_ios.yml file load and validate successfully."""
    result = load_hier_config_tags(tags_file_path)

    assert isinstance(result, tuple), "Result should be a tuple of TagRule objects."
    assert len(result) == 4, "There should be four TagRule objects."
    assert isinstance(result[0], TagRule), "Each element should be a TagRule object."
    assert result[0].apply_tags == {
        "safe"
    }, "First tag should have 'safe' as an applied tag."
    assert result[3].apply_tags == {
        "manual"
    }, "Last tag should have 'manual' as an applied tag."


def test_load_hier_config_tags_file_not_found() -> None:
    """Test that the function raises FileNotFoundError for a missing file."""
    with pytest.raises(FileNotFoundError):
        load_hier_config_tags("non_existent_file.yml")


def test_load_hier_config_tags_invalid_yaml(tmp_path: Path) -> None:
    """Test that the function raises yaml.YAMLError for invalid YAML syntax."""
    invalid_file = tmp_path / "invalid_tags.yml"
    invalid_file.write_text("""
    - match_rules:
      - equals: no ip http server
        apply_tags [safe]  # Missing colon causes a syntax error
    """)

    with pytest.raises(yaml.YAMLError):
        load_hier_config_tags(str(invalid_file))


def test_load_hier_config_tags_empty_file(tmp_path: Path) -> None:
    """Test that the function raises ValidationError for an empty YAML file."""
    empty_file = tmp_path / "empty.yml"
    empty_file.write_text("")

    with pytest.raises(ValidationError):
        load_hier_config_tags(str(empty_file))


def test_hconfig_v2_os_v3_platform_mapper() -> None:
    # Valid mappings
    assert hconfig_v2_os_v3_platform_mapper("ios") == Platform.CISCO_IOS
    assert hconfig_v2_os_v3_platform_mapper("nxos") == Platform.CISCO_NXOS
    assert hconfig_v2_os_v3_platform_mapper("junos") == Platform.JUNIPER_JUNOS
    assert hconfig_v2_os_v3_platform_mapper("invalid") == Platform.GENERIC


def test_hconfig_v3_platform_v2_os_mapper() -> None:
    # Valid mappings
    assert hconfig_v3_platform_v2_os_mapper(Platform.CISCO_IOS) == "ios"
    assert hconfig_v3_platform_v2_os_mapper(Platform.CISCO_NXOS) == "nxos"
    assert hconfig_v3_platform_v2_os_mapper(Platform.JUNIPER_JUNOS) == "junos"
    assert hconfig_v3_platform_v2_os_mapper(Platform.GENERIC) == "generic"


def test_load_hconfig_v2_options(
    platform_generic: Platform, v2_options: dict[str, Any]
) -> None:
    # pylint: disable=redefined-outer-name, unused-argument
    platform = platform_generic

    driver = load_hconfig_v2_options(v2_options, platform)

    # Assert negation rule
    assert len(driver.rules.negate_with) == 1
    assert driver.rules.negate_with[0].use == "no"

    # Assert ordering rule
    assert len(driver.rules.ordering) == 1
    assert driver.rules.ordering[0].match_rules[0].startswith == "ntp"
    assert driver.rules.ordering[0].weight == 700

    # Assert per-line substitution
    assert len(driver.rules.per_line_sub) == 1
    assert driver.rules.per_line_sub[0].search == "^!.*Generated.*$"
    assert not driver.rules.per_line_sub[0].replace

    # Assert sectional exiting
    assert len(driver.rules.sectional_exiting) == 1
    assert driver.rules.sectional_exiting[0].match_rules[0].startswith == "router bgp"
    assert driver.rules.sectional_exiting[0].exit_text == "exit"

    # Assert idempotent commands
    assert len(driver.rules.idempotent_commands) == 1
    assert driver.rules.idempotent_commands[0].match_rules[0].startswith == "interface"


def test_load_hconfig_v2_tags_valid_input() -> None:
    v2_tags = [
        {
            "lineage": [
                {"startswith": ["ip name-server", "no ip name-server", "ntp", "no ntp"]}
            ],
            "add_tags": "ntp",
        },
        {
            "lineage": [{"startswith": ["router bgp", "address-family ipv4"]}],
            "add_tags": "bgp",
        },
    ]

    expected_output = (
        TagRule(
            match_rules=(
                MatchRule(
                    startswith=("ip name-server", "no ip name-server", "ntp", "no ntp")
                ),
            ),
            apply_tags=frozenset(["ntp"]),
        ),
        TagRule(
            match_rules=(MatchRule(startswith=("router bgp", "address-family ipv4")),),
            apply_tags=frozenset(["bgp"]),
        ),
    )

    result = load_hconfig_v2_tags(v2_tags)
    assert result == expected_output


def test_load_hconfig_v2_tags_empty_input() -> None:
    v2_tags: list[dict[str, Any]] = []

    expected_output = ()

    result = load_hconfig_v2_tags(v2_tags)
    assert result == expected_output


def test_load_hconfig_v2_tags_multiple_lineage_fields() -> None:
    v2_tags = [
        {
            "lineage": [
                {"startswith": ["ip name-server"], "endswith": ["version 2"]},
            ],
            "add_tags": "ntp",
        }
    ]

    expected_output = (
        TagRule(
            match_rules=(
                MatchRule(startswith=("ip name-server",)),
                MatchRule(endswith=("version 2",)),
            ),
            apply_tags=frozenset(["ntp"]),
        ),
    )

    result = load_hconfig_v2_tags(v2_tags)
    assert result == expected_output


def test_load_hconfig_v2_tags_empty_lineage() -> None:
    v2_tags = [
        {
            "lineage": [],
            "add_tags": "empty",
        }
    ]

    expected_output = (TagRule(match_rules=(), apply_tags=frozenset(["empty"])),)

    result = load_hconfig_v2_tags(v2_tags)
    assert result == expected_output
