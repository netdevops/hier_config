from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from hier_config import Platform
from hier_config.models import MatchRule, TagRule
from hier_config.utils import (
    _set_match_rule,  # pyright: ignore[reportPrivateUsage]
    load_driver_rules,
    load_hier_config_tags,
    load_tag_rules,
    read_text_from_file,
)


@pytest.fixture
def temporary_file_fixture(tmp_path: Path) -> tuple[Path, str]:
    file_path = tmp_path / "temp_config.conf"
    content = "interface GigabitEthernet0/1\n ip address 192.168.1.1 255.255.255.0\n no shutdown"
    file_path.write_text(content)
    return file_path, content


def test_read_text_from_file_success(temporary_file_fixture: tuple[Path, str]) -> None:
    """Test that the function successfully loads a valid configuration file."""
    # pylint: disable=redefined-outer-name
    file_path, expected_content = temporary_file_fixture
    result = read_text_from_file(str(file_path))
    assert result == expected_content, "File content should match expected content."


def test_read_text_from_file_file_not_found() -> None:
    """Test that the function raises FileNotFoundError when the file does not exist."""
    with pytest.raises(FileNotFoundError):
        read_text_from_file("non_existent_file.conf")


def test_read_text_from_file_empty_file(tmp_path: Path) -> None:
    """Test that the function correctly handles an empty configuration file."""
    empty_file = tmp_path / "empty.conf"
    empty_file.write_text("")
    result = read_text_from_file(str(empty_file))
    assert not result, "Empty file should return an empty string."


def test_load_hier_config_tags_success(tags_file_path: str) -> None:
    """Test that valid tags from the tag_rules_ios.yml file load and validate successfully."""
    result = load_hier_config_tags(tags_file_path)

    assert isinstance(result, tuple), "Result should be a tuple of TagRule objects."
    assert len(result) == 4, "There should be four TagRule objects."
    assert isinstance(result[0], TagRule), "Each element should be a TagRule object."
    assert result[0].apply_tags == {"safe"}, (
        "First tag should have 'safe' as an applied tag."
    )
    assert result[3].apply_tags == {"manual"}, (
        "Last tag should have 'manual' as an applied tag."
    )


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


def test_load_driver_rules(platform_generic: Platform) -> None:
    # pylint: disable=redefined-outer-name
    options: dict[str, Any] = {
        "negation": "no",
        "sectional_overwrite": [{"lineage": [{"startswith": "template"}]}],
        "sectional_overwrite_no_negate": [{"lineage": [{"startswith": "as-path-set"}]}],
        "ordering": [{"lineage": [{"startswith": "ntp"}], "order": 700}],
        "indent_adjust": [
            {
                "start_expression": "^\\s*template",
                "end_expression": "^\\s*end-template",
            }
        ],
        "parent_allows_duplicate_child": [
            {"lineage": [{"startswith": "route-policy"}]}
        ],
        "sectional_exiting": [
            {"lineage": [{"startswith": "router bgp"}], "exit_text": "exit"}
        ],
        "full_text_sub": [{"search": "banner motd # replace me #", "replace": ""}],
        "per_line_sub": [{"search": "^!.*Generated.*$", "replace": ""}],
        "idempotent_commands_blacklist": [
            {
                "lineage": [
                    {"startswith": "interface"},
                    {"re_search": "ip address.*secondary"},
                ]
            }
        ],
        "idempotent_commands": [{"lineage": [{"startswith": "interface"}]}],
        "negation_negate_with": [
            {
                "lineage": [
                    {"startswith": "interface Ethernet"},
                    {"startswith": "spanning-tree port type"},
                ],
                "use": "no spanning-tree port type",
            }
        ],
    }

    driver = load_driver_rules(options, platform_generic)

    # Assert sectional overwrite
    assert len(driver.rules.sectional_overwrite) == 1
    assert driver.rules.sectional_overwrite[0].match_rules[0].startswith == "template"

    # Assert sectional overwrite no negate
    assert len(driver.rules.sectional_overwrite_no_negate) == 1
    assert (
        driver.rules.sectional_overwrite_no_negate[0].match_rules[0].startswith
        == "as-path-set"
    )

    # Assert ordering rule
    assert len(driver.rules.ordering) == 1
    assert driver.rules.ordering[0].match_rules[0].startswith == "ntp"
    assert driver.rules.ordering[0].weight == 200

    # Assert indent adjust
    assert len(driver.rules.indent_adjust) == 1
    assert driver.rules.indent_adjust[0].start_expression == "^\\s*template"
    assert driver.rules.indent_adjust[0].end_expression == "^\\s*end-template"

    # Assert parent_allows_duplicate_child
    assert len(driver.rules.parent_allows_duplicate_child) == 1
    assert (
        driver.rules.parent_allows_duplicate_child[0].match_rules[0].startswith
        == "route-policy"
    )

    # Assert sectional exiting
    assert len(driver.rules.sectional_exiting) == 1
    assert driver.rules.sectional_exiting[0].match_rules[0].startswith == "router bgp"
    assert driver.rules.sectional_exiting[0].exit_text == "exit"

    # Assert per-line substitution
    assert len(driver.rules.per_line_sub) == 1
    assert driver.rules.per_line_sub[0].search == "^!.*Generated.*$"
    assert not driver.rules.per_line_sub[0].replace

    # Assert full-text substitution
    assert len(driver.rules.full_text_sub) == 1
    assert driver.rules.full_text_sub[0].search == "banner motd # replace me #"
    assert not driver.rules.full_text_sub[0].replace

    # Assert idempotent commands avoid (blacklist)
    assert len(driver.rules.idempotent_commands_avoid) == 1
    assert (
        driver.rules.idempotent_commands_avoid[0].match_rules[0].startswith
        == "interface"
    )
    assert (
        driver.rules.idempotent_commands_avoid[0].match_rules[1].re_search
        == "ip address.*secondary"
    )

    # Assert idempotent commands
    assert len(driver.rules.idempotent_commands) == 1
    assert driver.rules.idempotent_commands[0].match_rules[0].startswith == "interface"

    # Assert negation_negate_with -> negate_with
    assert len(driver.rules.negate_with) == 1
    assert driver.rules.negate_with[0].match_rules[0].startswith == "interface Ethernet"
    assert (
        driver.rules.negate_with[0].match_rules[1].startswith
        == "spanning-tree port type"
    )
    assert driver.rules.negate_with[0].use == "no spanning-tree port type"


def test_load_tag_rules_valid_input() -> None:
    tags = [
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

    result = load_tag_rules(tags)
    assert result == expected_output


def test_load_tag_rules_empty_input() -> None:
    tags: list[dict[str, Any]] = []

    expected_output = ()

    result = load_tag_rules(tags)
    assert result == expected_output


def test_load_tag_rules_multiple_lineage_fields() -> None:
    tags = [
        {
            "lineage": [
                {"startswith": ["ip name-server"]},
                {"endswith": ["version 2"]},
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

    result = load_tag_rules(tags)
    assert result == expected_output


def test_load_tag_rules_empty_lineage() -> None:
    tags: list[dict[str, str | list[str]]] = [
        {
            "lineage": [],
            "add_tags": "empty",
        }
    ]

    expected_output = (TagRule(match_rules=(), apply_tags=frozenset(["empty"])),)

    result = load_tag_rules(tags)
    assert result == expected_output


def test_load_driver_rules_from_file_valid(tmp_path: Path) -> None:
    """Test loading valid driver rules from a YAML file."""
    file_path = tmp_path / "options.yml"
    file_content = """ordering:
  - lineage:
      - startswith: ntp
    order: 700
sectional_overwrite:
  - lineage:
      - startswith: template
indent_adjust:
  - start_expression: "start expression"
    end_expression: "end expression"
"""
    file_path.write_text(file_content)

    platform = Platform.GENERIC
    driver = load_driver_rules(options=str(file_path), platform=platform)

    assert len(driver.rules.ordering) == 1
    assert driver.rules.ordering[0].match_rules[0].startswith == "ntp"
    assert driver.rules.ordering[0].weight == 200

    assert len(driver.rules.sectional_overwrite) == 1
    assert driver.rules.sectional_overwrite[0].match_rules[0].startswith == "template"

    assert len(driver.rules.indent_adjust) == 1
    assert driver.rules.indent_adjust[0].start_expression == "start expression"
    assert driver.rules.indent_adjust[0].end_expression == "end expression"


def test_load_driver_rules_from_file_invalid_yaml(tmp_path: Path) -> None:
    """Test loading driver rules from a file with invalid YAML syntax."""
    file_path = tmp_path / "invalid_options.yml"
    file_content = """ordering:
  - lineage:
      - startswith: ntp
    order:  # Missing value causes a syntax error
"""
    file_path.write_text(file_content)

    platform = Platform.GENERIC
    with pytest.raises(TypeError):
        load_driver_rules(options=str(file_path), platform=platform)


def test_load_tag_rules_from_file_valid(tmp_path: Path) -> None:
    """Test loading valid tag rules from a YAML file."""
    file_path = tmp_path / "tags.yml"
    file_content = """- lineage:
    - startswith: ip name-server
  add_tags: dns
- lineage:
    - startswith: router bgp
  add_tags: bgp
"""
    file_path.write_text(file_content)

    result = load_tag_rules(tags=str(file_path))

    assert len(result) == 2
    assert result[0].apply_tags == frozenset(["dns"])
    assert result[1].apply_tags == frozenset(["bgp"])


def test_load_tag_rules_from_file_invalid_yaml(tmp_path: Path) -> None:
    """Test loading tag rules from a file with invalid YAML syntax."""
    file_path = tmp_path / "invalid_tags.yml"
    file_content = """- lineage:
    - startswith: ip name-server
  add_tags dns  # Missing colon causes a syntax error
"""
    file_path.write_text(file_content)

    with pytest.raises(yaml.YAMLError):
        load_tag_rules(tags=str(file_path))


def test_load_tag_rules_from_file_empty_file(tmp_path: Path) -> None:
    """Test loading tag rules from an empty file."""
    file_path = tmp_path / "empty_tags.yml"
    file_path.write_text("")

    with pytest.raises(TypeError):
        load_tag_rules(tags=str(file_path))


def test_set_match_rule_endswith() -> None:
    """Test _set_match_rule with endswith."""
    lineage = {"endswith": "Ethernet0/0"}
    result = _set_match_rule(lineage)

    assert result is not None
    assert result.endswith == "Ethernet0/0"


def test_set_match_rule_contains() -> None:
    """Test _set_match_rule with contains."""
    lineage = {"contains": "GigabitEthernet"}
    result = _set_match_rule(lineage)

    assert result is not None
    assert result.contains == "GigabitEthernet"


def test_set_match_rule_equals() -> None:
    """Test _set_match_rule with equals."""
    lineage = {"equals": "interface GigabitEthernet0/0"}
    result = _set_match_rule(lineage)

    assert result is not None
    assert result.equals == "interface GigabitEthernet0/0"


def test_set_match_rule_none() -> None:
    """Test _set_match_rule returns None for empty lineage."""
    lineage: dict[str, Any] = {}
    result = _set_match_rule(lineage)

    assert result is None


def test_load_driver_rules_invalid_type() -> None:
    """Test load_driver_rules with invalid type."""
    with pytest.raises(
        TypeError, match="options must be a dictionary or a valid file path"
    ):
        load_driver_rules(options=123, platform=Platform.CISCO_IOS)  # type: ignore[arg-type]


def test_load_tag_rules_from_file(tmp_path: Path) -> None:
    """Test load_tag_rules with file path."""
    file_path = tmp_path / "test_tags.yml"
    tags_content = """
- lineage:
  - startswith: interface
  add_tags: interfaces
"""
    file_path.write_text(tags_content)
    result = load_tag_rules(tags=str(file_path))

    assert len(result) == 1
    assert result[0].apply_tags == frozenset(["interfaces"])
