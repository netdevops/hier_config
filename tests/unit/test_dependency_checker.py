from __future__ import annotations

from importlib import metadata
from typing import TYPE_CHECKING
from zipfile import ZipFile

import pytest

from scripts import check_declared_dependencies

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("version", (metadata.version("hier-config"), "0.0.0"))
def test_installed_wheel_version_matches_artifact(tmp_path: Path, version: str) -> None:
    wheel = tmp_path / f"hier_config-{version}-cp311-abi3-any.whl"
    with ZipFile(wheel, "w") as archive:
        archive.writestr(
            f"hier_config-{version}.dist-info/METADATA",
            f"Metadata-Version: 2.1\nName: hier-config\nVersion: {version}\n",
        )
    errors = check_declared_dependencies.installed_wheel_errors(wheel)
    if version == metadata.version("hier-config"):
        assert not errors
    else:
        assert errors == [
            (
                f"installed hier-config {metadata.version('hier-config')} "
                f"does not match built wheel {version}"
            )
        ]
