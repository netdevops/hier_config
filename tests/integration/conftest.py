"""Fixtures for circular config workflow tests."""

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


# Juniper JunOS fixtures
@pytest.fixture(scope="module")
def junos_running_config() -> str:
    """Load JunOS running config fixture."""
    return _fixture_file_read("junos_running.conf")


@pytest.fixture(scope="module")
def junos_generated_config() -> str:
    """Load JunOS generated config fixture."""
    return _fixture_file_read("junos_generated.conf")


@pytest.fixture(scope="module")
def junos_remediation_config() -> str:
    """Load JunOS remediation config fixture."""
    return _fixture_file_read("junos_remediation.conf")


@pytest.fixture(scope="module")
def junos_rollback_config() -> str:
    """Load JunOS rollback config fixture."""
    return _fixture_file_read("junos_rollback.conf")


# VyOS fixtures
@pytest.fixture(scope="module")
def vyos_running_config() -> str:
    """Load VyOS running config fixture."""
    return _fixture_file_read("vyos_running.conf")


@pytest.fixture(scope="module")
def vyos_generated_config() -> str:
    """Load VyOS generated config fixture."""
    return _fixture_file_read("vyos_generated.conf")


@pytest.fixture(scope="module")
def vyos_remediation_config() -> str:
    """Load VyOS remediation config fixture."""
    return _fixture_file_read("vyos_remediation.conf")


@pytest.fixture(scope="module")
def vyos_rollback_config() -> str:
    """Load VyOS rollback config fixture."""
    return _fixture_file_read("vyos_rollback.conf")


# Fortinet FortiOS fixtures
@pytest.fixture(scope="module")
def fortios_running_config() -> str:
    """Load FortiOS running config fixture."""
    return _fixture_file_read("fortios_running.conf")


@pytest.fixture(scope="module")
def fortios_generated_config() -> str:
    """Load FortiOS generated config fixture."""
    return _fixture_file_read("fortios_generated.conf")


@pytest.fixture(scope="module")
def fortios_remediation_config() -> str:
    """Load FortiOS remediation config fixture."""
    return _fixture_file_read("fortios_remediation.conf")


@pytest.fixture(scope="module")
def fortios_rollback_config() -> str:
    """Load FortiOS rollback config fixture."""
    return _fixture_file_read("fortios_rollback.conf")


# HP Comware5 fixtures
@pytest.fixture(scope="module")
def comware5_running_config() -> str:
    """Load HP Comware5 running config fixture."""
    return _fixture_file_read("comware5_running.conf")


@pytest.fixture(scope="module")
def comware5_generated_config() -> str:
    """Load HP Comware5 generated config fixture."""
    return _fixture_file_read("comware5_generated.conf")


@pytest.fixture(scope="module")
def comware5_remediation_config() -> str:
    """Load HP Comware5 remediation config fixture."""
    return _fixture_file_read("comware5_remediation.conf")


@pytest.fixture(scope="module")
def comware5_rollback_config() -> str:
    """Load HP Comware5 rollback config fixture."""
    return _fixture_file_read("comware5_rollback.conf")


# HP Procurve fixtures
@pytest.fixture(scope="module")
def procurve_running_config() -> str:
    """Load HP Procurve running config fixture."""
    return _fixture_file_read("procurve_running.conf")


@pytest.fixture(scope="module")
def procurve_generated_config() -> str:
    """Load HP Procurve generated config fixture."""
    return _fixture_file_read("procurve_generated.conf")


@pytest.fixture(scope="module")
def procurve_remediation_config() -> str:
    """Load HP Procurve remediation config fixture."""
    return _fixture_file_read("procurve_remediation.conf")


@pytest.fixture(scope="module")
def procurve_rollback_config() -> str:
    """Load HP Procurve rollback config fixture."""
    return _fixture_file_read("procurve_rollback.conf")
