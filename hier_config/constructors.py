from contextlib import suppress
from itertools import islice
from logging import getLogger
from pathlib import Path
from re import search, sub
from typing import Union

from hier_config.platforms.driver_base import HConfigDriverBase

from .child import HConfigChild
from .models import Dump, Platform
from .platforms.arista_eos.driver import HConfigDriverAristaEOS
from .platforms.arista_eos.view import HConfigViewAristaEOS
from .platforms.cisco_ios.driver import HConfigDriverCiscoIOS
from .platforms.cisco_ios.view import HConfigViewCiscoIOS
from .platforms.cisco_nxos.driver import HConfigDriverCiscoNXOS
from .platforms.cisco_nxos.view import HConfigViewCiscoNXOS
from .platforms.cisco_xr.driver import HConfigDriverCiscoIOSXR
from .platforms.cisco_xr.view import HConfigViewCiscoIOSXR
from .platforms.generic.driver import HConfigDriverGeneric
from .platforms.hp_comware5.driver import HConfigDriverHPComware5
from .platforms.hp_procurve.driver import HConfigDriverHPProcurve
from .platforms.hp_procurve.view import HConfigViewHPProcurve
from .platforms.juniper_junos.driver import HConfigDriverJuniperJUNOS
from .platforms.view_base import HConfigViewBase
from .platforms.vyos.driver import HConfigDriverVYOS
from .root import HConfig

logger = getLogger(__name__)


def get_hconfig_driver(platform: Platform) -> HConfigDriverBase:  # noqa: PLR0911
    """Create base options on an OS level."""
    if platform == Platform.ARISTA_EOS:
        return HConfigDriverAristaEOS()
    if platform == Platform.CISCO_IOS:
        return HConfigDriverCiscoIOS()
    if platform == Platform.CISCO_NXOS:
        return HConfigDriverCiscoNXOS()
    if platform == Platform.CISCO_XR:
        return HConfigDriverCiscoIOSXR()
    if platform == Platform.GENERIC:
        return HConfigDriverGeneric()
    if platform == Platform.HP_PROCURVE:
        return HConfigDriverHPProcurve()
    if platform == Platform.HP_COMWARE5:
        return HConfigDriverHPComware5()
    if platform == Platform.JUNIPER_JUNOS:
        return HConfigDriverJuniperJUNOS()
    if platform == Platform.VYOS:
        return HConfigDriverVYOS()

    message = f"Unsupported platform: {platform}"  # type: ignore[unreachable]
    raise ValueError(message)


def get_hconfig_view(config: HConfig) -> HConfigViewBase:
    """Instantiates the appropriate HConfigView.

    If you implement your own HConfigView, you will likely need to create a function like this one locally.
    """
    driver = config.driver
    if isinstance(driver, HConfigDriverAristaEOS):
        return HConfigViewAristaEOS(config)
    if isinstance(driver, HConfigDriverCiscoIOS):
        return HConfigViewCiscoIOS(config)
    if isinstance(driver, HConfigDriverCiscoNXOS):
        return HConfigViewCiscoNXOS(config)
    if isinstance(driver, HConfigDriverCiscoIOSXR):
        return HConfigViewCiscoIOSXR(config)
    if isinstance(driver, HConfigDriverHPProcurve):
        return HConfigViewHPProcurve(config)

    message = f"Unsupported platform: {config.driver.__class__.__name__}"
    raise ValueError(message)


def get_hconfig(
    platform_or_driver: Union[Platform, HConfigDriverBase],
    config_raw: Union[Path, str] = "",
) -> HConfig:
    if isinstance(config_raw, Path):
        config_raw = config_raw.read_text(encoding="utf8")

    config = HConfig(_get_driver(platform_or_driver))
    for rule in config.driver.rules.full_text_sub:
        config_raw = sub(rule.search, rule.replace, config_raw)

    _load_from_string_lines(config, config_raw)

    for child in tuple(config.all_children()):
        child.delete_sectional_exit()

    for callback in config.driver.rules.post_load_callbacks:
        callback(config)

    return config


def get_hconfig_from_dump(
    platform_or_driver: Union[Platform, HConfigDriverBase], dump: Dump
) -> HConfig:
    """Load an HConfig dump."""
    config = get_hconfig(_get_driver(platform_or_driver))
    last_item: Union[HConfig, HConfigChild] = config
    for item in dump.lines:
        # parent is the root
        if item.depth == 1:
            parent: Union[HConfig, HConfigChild] = config
        # has the same parent
        elif last_item.depth() == item.depth:
            parent = last_item.parent
        # is a child object
        elif last_item.depth() + 1 == item.depth:
            parent = last_item
        # has a parent somewhere closer to the root but not the root
        else:
            parent = next(islice(last_item.lineage(), item.depth - 2, item.depth - 1))
        obj = parent.add_child(item.text)
        obj.tags = frozenset(item.tags)
        obj.comments = set(item.comments)
        obj.new_in_config = item.new_in_config
        last_item = obj

    return config


def get_hconfig_fast_generic_load(
    lines: Union[list[str], tuple[str, ...], str],
) -> HConfig:
    return get_hconfig_fast_load(Platform.GENERIC, lines)


def get_hconfig_fast_load(
    platform_or_driver: Union[Platform, HConfigDriverBase],
    lines: Union[list[str], tuple[str, ...], str],
) -> HConfig:
    driver = _get_driver(platform_or_driver)
    config = get_hconfig(driver)
    if isinstance(lines, str):
        lines = lines.splitlines()

    current_section: Union[HConfig, HConfigChild] = config
    most_recent_item: Union[HConfig, HConfigChild] = current_section

    for line in lines:
        if not (line_lstripped := line.lstrip()):
            continue
        indent = len(line) - len(line_lstripped)

        # Determine parent in hierarchy
        most_recent_item, current_section = _analyze_indent(
            most_recent_item,
            current_section,
            indent,
            " ".join(line.split()),
        )

    for child in tuple(config.all_children()):
        child.delete_sectional_exit()

    return config


def _get_driver(
    platform_or_driver: Union[Platform, HConfigDriverBase],
) -> HConfigDriverBase:
    if isinstance(platform_or_driver, Platform):
        return get_hconfig_driver(platform_or_driver)
    return platform_or_driver


def _analyze_indent(
    most_recent_item: Union[HConfig, HConfigChild],
    current_section: Union[HConfig, HConfigChild],
    indent: int,
    line: str,
) -> tuple[HConfigChild, Union[HConfig, HConfigChild]]:
    # Walks back up the tree
    while indent <= current_section.real_indent_level:
        current_section = current_section.parent

    # Walks down the tree by one step
    if indent > most_recent_item.real_indent_level:
        current_section = most_recent_item

    most_recent_item = current_section.add_child(line)
    most_recent_item.real_indent_level = indent

    return most_recent_item, current_section


def _adjust_indent(
    options: HConfigDriverBase,
    line: str,
    indent_adjust: int,
    end_indent_adjust: list[str],
) -> tuple[int, list[str]]:
    for expression in options.rules.indent_adjust:
        if search(expression.start_expression, line):
            return indent_adjust + 1, [*end_indent_adjust, expression.end_expression]
    return indent_adjust, end_indent_adjust


def _config_from_string_lines_end_of_banner_test(
    config_line: str,
    banner_end_lines: frozenset[str],
    banner_end_contains: list[str],
) -> bool:
    if config_line.startswith("^"):
        return True
    if config_line in banner_end_lines:
        return True
    return any(c in config_line for c in banner_end_contains)


def _load_from_string_lines(config: HConfig, config_text: str) -> None:  # noqa: C901
    if isinstance(config.driver, HConfigDriverJuniperJUNOS):
        config_text = _convert_to_set_commands(config_text)

    current_section: Union[HConfig, HConfigChild] = config
    most_recent_item: Union[HConfig, HConfigChild] = current_section
    indent_adjust = 0
    end_indent_adjust: list[str] = []
    temp_banner: list[str] = []
    banner_end_lines = {"EOF", "%", "!"}
    banner_end_contains: list[str] = []
    in_banner = False

    for line in config_text.splitlines():
        # Process banners in configuration into one line
        if in_banner:
            if line != "!":
                temp_banner.append(line)

            # Test if this line is the end of a banner
            if _config_from_string_lines_end_of_banner_test(
                line,
                frozenset(banner_end_lines),
                banner_end_contains,
            ):
                in_banner = False
                most_recent_item = config.add_child(
                    "\n".join(temp_banner),
                )
                most_recent_item.real_indent_level = 0
                current_section = config
                temp_banner = []
            continue

        # Test if this line is the start of a banner and not an empty banner
        # Empty banners matching the below expression have been seen on NX-OS
        if line.startswith("banner ") and line != "banner motd ##":
            in_banner = True
            temp_banner.append(line)
            banner_words = line.split()
            with suppress(IndexError):
                banner_end_contains.append(banner_words[2])
                # Handle banner on ArubaOS-Switch
                if banner_words[2].startswith('"'):
                    banner_end_contains.append('"')
                banner_end_lines.add(banner_words[2][:1])
                banner_end_lines.add(banner_words[2][:2])

            continue

        actual_indent = len(line) - len(line.lstrip())
        line = " " * actual_indent + " ".join(line.split())  # noqa: PLW2901
        for rule in config.driver.rules.per_line_sub:
            line = sub(rule.search, rule.replace, line)  # noqa: PLW2901
        line = line.rstrip()  # noqa: PLW2901

        # If line is now empty, move to the next
        if not line:
            continue

        # Determine indentation level
        this_indent = len(line) - len(line.lstrip()) + indent_adjust

        line = line.lstrip()  # noqa: PLW2901

        # Determine parent in hierarchy
        most_recent_item, current_section = _analyze_indent(
            most_recent_item,
            current_section,
            this_indent,
            line,
        )
        indent_adjust, end_indent_adjust = _adjust_indent(
            config.driver,
            line,
            indent_adjust,
            end_indent_adjust,
        )

        if end_indent_adjust and search(end_indent_adjust[0], line):
            indent_adjust -= 1
            end_indent_adjust.pop(0)
    if in_banner:
        message = "we are still in a banner for some reason"
        raise ValueError(message)


def _convert_to_set_commands(config_raw: str) -> str:
    """Convert a Juniper style config string into a list of set commands.

    Args:
        config_raw (str): The config string to convert to set commands
    Returns:
        config_raw (str): Configuration string

    """
    lines = config_raw.split("\n")
    path: list[str] = []
    set_commands: list[str] = []

    for line in lines:
        stripped_line = line.strip()

        # Skip empty lines
        if not stripped_line:
            continue

        # Strip ; from the end of the line
        if stripped_line.endswith(";"):
            stripped_line = stripped_line.replace(";", "")

        # Count the number of spaces at the beginning to determine the level
        level = line.find(stripped_line) // 4

        # Adjust the current path based on the level
        path = path[:level]

        # If the line ends with '{' or '}', it starts a new block
        if stripped_line.endswith(("{", "}")):
            path.append(stripped_line[:-1].strip())
        elif stripped_line.startswith(("set", "delete")):
            # It's already a set command, so just add it to the list
            set_commands.append(stripped_line)
        else:
            # It's a command line, construct the full command
            command = f"set {' '.join(path)} {stripped_line}"
            set_commands.append(command)

    return "\n".join(set_commands)
