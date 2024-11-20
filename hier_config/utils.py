from pathlib import Path

import yaml
from pydantic import TypeAdapter

from hier_config.models import (
    HierConfigMapping,
    Platform,
    TagRule,
)


def _load_file_contents(file_path: str) -> str:
    """Private function that loads the contents of a file into memory.

    Args:
        file_path (str): The path to the configuration file.

    Returns:
        str: The configuration file contents as a string.

    """
    return Path(file_path).read_text(encoding="utf-8")


def load_device_config(file_path: str) -> str:
    """Reads a device configuration file and loads its contents into memory.

    Args:
        file_path (str): The path to the configuration file.

    Returns:
        str: The configuration file contents as a string.

    """
    return _load_file_contents(file_path=file_path)


def load_hier_config_tags(tags_file: str) -> tuple[TagRule, ...]:
    """Loads and validates Hier Config tags from a YAML file.

    Args:
        tags_file (str): Path to the YAML file containing the tags.

    Returns:
        Tuple[TagRule, ...]: A tuple of validated TagRule objects.

    """
    tags_data = yaml.safe_load(_load_file_contents(file_path=tags_file))
    return TypeAdapter(tuple[TagRule, ...]).validate_python(tags_data)


def hconfig_v2_os_v3_platform_mapper(os_name: str) -> Platform:
    """Map a Hier Config v2 operating system name to a v3 Platform enumeration.

    Args:
        os_name (str): The name of the OS as defined in Hier Config v2.

    Returns:
        Platform: The corresponding Platform enumeration for Hier Config v3.

    Raises:
        ValueError: If the provided OS name is not supported in v2.

    Example:
        >>> hconfig_v2_os_v3_platform_mapper("CISCO_IOS")
        <Platform.CISCO_IOS: 'cisco_ios'>

    """
    try:
        return HierConfigMapping[os_name].value
    except KeyError:
        msg = f"Unsupported v2 OS: {os_name}"
        raise ValueError(msg)


def hconfig_v3_platform_v2_os_mapper(platform: Platform) -> str:
    """Map a Hier Config v3 Platform enumeration to a v2 operating system name.

    Args:
        platform (Platform): A Platform enumeration from Hier Config v3.

    Returns:
        str: The corresponding OS name for Hier Config v2.

    Raises:
        ValueError: If the provided Platform is not supported in v3.

    Example:
        >>> hconfig_v3_platform_v2_os_mapper(Platform.CISCO_IOS)
        "ios"

    """
    for os_name, plat in HierConfigMapping.__members__.items():
        if plat.value == platform:
            return os_name
    msg = f"Unsupported v3 Platform: {platform}"
    raise ValueError(msg)
