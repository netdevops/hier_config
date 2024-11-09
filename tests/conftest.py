from pathlib import Path

import pytest

from hier_config.model import Platform


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


def _fixture_file_read(filename: str) -> str:
    return str(
        Path(__file__)
        .resolve()
        .parent.joinpath("fixtures")
        .joinpath(filename)
        .read_text(encoding="utf8")
    )
