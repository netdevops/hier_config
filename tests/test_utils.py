from pathlib import Path  # Use pathlib for handling file paths
from typing import Any, Union

import pytest
import yaml
from pydantic import ValidationError

from hier_config.models import TagRule
from hier_config.utils import load_device_config, load_hier_config_tags

TAGS_FILE_PATH = "./tests/fixtures/tag_rules_ios.yml"


# Helper function to create a temporary file for testing
@pytest.fixture
def temp_file(tmp_path: Path) -> tuple[Path, str]:
    file_path = tmp_path / "temp_config.conf"
    content = "interface GigabitEthernet0/1\n ip address 192.168.1.1 255.255.255.0\n no shutdown"
    file_path.write_text(content)
    return file_path, content


def test_load_device_config_success(temp_file: tuple[Path, str]) -> None:
    """Test that the function successfully loads a valid configuration file."""
    file_path, expected_content = temp_file
    result = load_device_config(str(file_path))
    assert result == expected_content, "File content should match expected content."


def test_load_device_config_file_not_found() -> None:
    """Test that the function raises FileNotFoundError when the file does not exist."""
    with pytest.raises(FileNotFoundError):
        load_device_config("non_existent_file.conf")


def test_load_device_config_io_error(
    monkeypatch: pytest.MonkeyPatch, temp_file: tuple[Path, str]
) -> None:
    """Test that the function raises OSError for an unexpected file access error."""
    file_path, _ = temp_file

    def mock_read_text(*args: Any, **kwargs: Union[dict, None]) -> None:  # noqa: ANN401, ARG001
        msg = "Mocked IO error"
        raise OSError(msg)

    monkeypatch.setattr(Path, "read_text", mock_read_text)

    with pytest.raises(OSError, match="Mocked IO error"):
        load_device_config(str(file_path))


def test_load_device_config_empty_file(tmp_path: Path) -> None:
    """Test that the function correctly handles an empty configuration file."""
    empty_file = tmp_path / "empty.conf"
    empty_file.write_text("")  # Create an empty file
    result = load_device_config(str(empty_file))
    assert not result, "Empty file should return an empty string."


def test_load_hier_config_tags_success() -> None:
    """Test that valid tags from the tag_rules_ios.yml file load and validate successfully."""
    result = load_hier_config_tags(TAGS_FILE_PATH)

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
    empty_file.write_text("")  # Create an empty file

    with pytest.raises(ValidationError):
        load_hier_config_tags(str(empty_file))
