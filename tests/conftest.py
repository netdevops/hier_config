from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import TypeAdapter

from hier_config.models import Platform, TagRule


@pytest.fixture(scope="module")
def generated_config() -> str:
    return _fixture_file_read("generated_config.conf")


@pytest.fixture(scope="module")
def running_config() -> str:
    return _fixture_file_read("running_config.conf")


@pytest.fixture(scope="module")
def remediation_config_with_safe_tags() -> str:
    return _fixture_file_read("remediation_config_with_safe_tags.conf")


@pytest.fixture(scope="module")
def remediation_config_without_tags() -> str:
    return _fixture_file_read("remediation_config_without_tags.conf")


@pytest.fixture(scope="module")
def platform_a() -> Platform:
    return Platform.CISCO_IOS


@pytest.fixture(scope="module")
def platform_b() -> Platform:
    return Platform.CISCO_IOS


@pytest.fixture(scope="module")
def platform_generic() -> Platform:
    return Platform.GENERIC


@pytest.fixture(scope="module")
def tag_rules_ios() -> tuple[TagRule, ...]:
    return TypeAdapter(tuple[TagRule, ...]).validate_python(
        yaml.safe_load(_fixture_file_read("tag_rules_ios.yml"))
    )


@pytest.fixture(scope="module")
def generated_config_junos() -> str:
    return _fixture_file_read("generated_config_junos.conf")


@pytest.fixture(scope="module")
def running_config_junos() -> str:
    return _fixture_file_read("running_config_junos.conf")


@pytest.fixture(scope="module")
def generated_config_flat_junos() -> str:
    return _fixture_file_read("generated_config_flat_junos.conf")


@pytest.fixture(scope="module")
def running_config_flat_junos() -> str:
    return _fixture_file_read("running_config_flat_junos.conf")


@pytest.fixture(scope="module")
def remediation_config_flat_junos() -> str:
    return _fixture_file_read("remediation_config_flat_junos.conf")


@pytest.fixture(scope="module")
def tags_file_path() -> str:
    return "./tests/fixtures/tag_rules_ios.yml"


@pytest.fixture(scope="module")
def v2_options() -> dict[str, Any]:
    return {
        "negation": "no",
        "sectional_overwrite": [{"lineage": [{"startswith": "template"}]}],
        "sectional_overwrite_no_negate": [{"lineage": [{"startswith": "as-path-set"}]}],
        "ordering": [{"lineage": [{"startswith": "ntp"}], "order": 700}],
        "indent_adjust": [
            {"start_expression": "^\\s*template", "end_expression": "^\\s*end-template"}
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


def _fixture_file_read(filename: str) -> str:
    return str(
        Path(__file__)
        .resolve()
        .parent.joinpath("fixtures")
        .joinpath(filename)
        .read_text(encoding="utf8"),
    )
