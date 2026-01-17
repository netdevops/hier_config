"""Fixtures for future config workflow tests."""

from pathlib import Path

import pytest


def _fixture_file_read(filename: str) -> str:
    """Read a fixture file from the fixtures directory."""
    return str(
        Path(__file__)
        .resolve()
        .parent.joinpath("fixtures")
        .joinpath(filename)
        .read_text(encoding="utf8"),
    )


# Cisco IOS fixtures
@pytest.fixture(scope="module")
def ios_running_config() -> str:
    """Load IOS running config fixture."""
    return _fixture_file_read("ios_running.conf")


@pytest.fixture(scope="module")
def ios_generated_config() -> str:
    """Load IOS generated config fixture."""
    return _fixture_file_read("ios_generated.conf")


@pytest.fixture(scope="module")
def ios_remediation_config() -> str:
    """Load IOS remediation config fixture."""
    return _fixture_file_read("ios_remediation.conf")


@pytest.fixture(scope="module")
def ios_rollback_config() -> str:
    """Load IOS rollback config fixture."""
    return _fixture_file_read("ios_rollback.conf")


# Arista EOS fixtures
@pytest.fixture(scope="module")
def eos_running_config() -> str:
    """Load EOS running config fixture."""
    return _fixture_file_read("eos_running.conf")


@pytest.fixture(scope="module")
def eos_generated_config() -> str:
    """Load EOS generated config fixture."""
    return _fixture_file_read("eos_generated.conf")


@pytest.fixture(scope="module")
def eos_remediation_config() -> str:
    """Load EOS remediation config fixture."""
    return _fixture_file_read("eos_remediation.conf")


@pytest.fixture(scope="module")
def eos_rollback_config() -> str:
    """Load EOS rollback config fixture."""
    return _fixture_file_read("eos_rollback.conf")


# Cisco NXOS fixtures
@pytest.fixture(scope="module")
def nxos_running_config() -> str:
    """Load NXOS running config fixture."""
    return _fixture_file_read("nxos_running.conf")


@pytest.fixture(scope="module")
def nxos_generated_config() -> str:
    """Load NXOS generated config fixture."""
    return _fixture_file_read("nxos_generated.conf")


@pytest.fixture(scope="module")
def nxos_remediation_config() -> str:
    """Load NXOS remediation config fixture."""
    return _fixture_file_read("nxos_remediation.conf")


@pytest.fixture(scope="module")
def nxos_rollback_config() -> str:
    """Load NXOS rollback config fixture."""
    return _fixture_file_read("nxos_rollback.conf")


# Cisco IOS-XR fixtures
@pytest.fixture(scope="module")
def iosxr_running_config() -> str:
    """Load IOS-XR running config fixture."""
    return _fixture_file_read("iosxr_running.conf")


@pytest.fixture(scope="module")
def iosxr_generated_config() -> str:
    """Load IOS-XR generated config fixture."""
    return _fixture_file_read("iosxr_generated.conf")


@pytest.fixture(scope="module")
def iosxr_remediation_config() -> str:
    """Load IOS-XR remediation config fixture."""
    return _fixture_file_read("iosxr_remediation.conf")


@pytest.fixture(scope="module")
def iosxr_rollback_config() -> str:
    """Load IOS-XR rollback config fixture."""
    return _fixture_file_read("iosxr_rollback.conf")
