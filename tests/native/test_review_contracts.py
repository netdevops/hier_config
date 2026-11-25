"""Regression coverage for the v4 extension and optional-loader contracts."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

from hier_config import Platform, get_hconfig
from hier_config.platforms.cisco_ios.driver import HConfigDriverCiscoIOS
from hier_config.utils import load_driver_rules, load_hier_config_tags, load_tag_rules

if TYPE_CHECKING:
    from pathlib import Path


def test_custom_preprocessor_cannot_be_silently_ignored() -> None:
    def redact(config_text: str) -> str:
        return config_text.replace("SECRET", "REDACTED")

    with pytest.raises(TypeError, match=r"config_preprocessor.*before"):
        type(
            "RedactingDriver",
            (HConfigDriverCiscoIOS,),
            {"config_preprocessor": staticmethod(redact)},
        )


def test_yaml_loaders_report_missing_optional_dependency(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tags_file = tmp_path / "tags.yml"
    tags_file.write_text("[]", encoding="utf-8")
    monkeypatch.setitem(sys.modules, "yaml", None)

    with pytest.raises(ImportError, match=r"hier-config\[yaml\]"):
        load_hier_config_tags(str(tags_file))
    with pytest.raises(ImportError, match=r"hier-config\[yaml\]"):
        load_tag_rules(str(tags_file))
    with pytest.raises(ImportError, match=r"hier-config\[yaml\]"):
        load_driver_rules(str(tags_file), Platform.GENERIC)

    assert not load_tag_rules([])
    config = get_hconfig(load_driver_rules({}, Platform.GENERIC), "hostname router")
    assert config.to_lines() == ("hostname router",)
