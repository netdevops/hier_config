from pathlib import Path

import yaml
from pydantic import TypeAdapter

from hier_config.models import TagRule


def load_device_config(file_path: str) -> str:
    """Reads a device configuration file and loads its contents into memory.

    Args:
        file_path (str): The path to the configuration file.

    Returns:
        str: The configuration file contents as a string.

    """
    return Path(file_path).read_text(encoding="utf-8")


def load_hier_config_tags(tags_file: str) -> tuple[TagRule, ...]:
    """Loads and validates Hier Config tags from a YAML file.

    Args:
        tags_file (str): Path to the YAML file containing the tags.

    Returns:
        Tuple[TagRule, ...]: A tuple of validated TagRule objects.

    """
    tags_data = yaml.safe_load(Path(tags_file).read_text(encoding="utf-8"))
    return TypeAdapter(tuple[TagRule, ...]).validate_python(tags_data)
