from contextlib import suppress
from itertools import islice
from json import JSONDecodeError, loads
from logging import getLogger
from pathlib import Path
from re import search, sub

from hier_config.platforms.driver_base import HConfigDriverBase

from .child import HConfigChild
from .exceptions import DriverNotFoundError, InvalidConfigError
from .models import Dump, Platform
from .platforms.view_base import HConfigViewBase
from .registry import get_hconfig_driver
from .root import HConfig

logger = getLogger(__name__)


def get_hconfig_view(config: HConfig) -> HConfigViewBase:
    """Instantiates the HConfigView declared by the config's driver.

    Drivers declare their view via the `view_class` attribute, so a custom
    driver can register its own view by setting `view_class` on the subclass.
    """
    if view_class := config.driver.view_class:
        return view_class(config)

    message = f"No view registered for driver: {config.driver.__class__.__name__}"
    raise DriverNotFoundError(message)


def _detect_structured_format(config_text: str) -> str | None:
    """Detect structured config formats that the text parser cannot ingest (#232).

    Guards the raw-text entry points (from_text() and the str form of
    from_lines()); pre-split lines are assumed to be CLI text.
    """
    prefix = config_text[:64].lstrip()
    if prefix.startswith("<"):
        return "XML"
    if prefix.startswith(("{", "[")):
        with suppress(JSONDecodeError):
            loads(config_text)
            return "JSON"
    return None


def _reject_structured_format(config_text: str) -> None:
    if detected := _detect_structured_format(config_text):
        message = (
            f"The config appears to be {detected}. Use HConfig.from_xml() or"
            " HConfig.from_json() for structured formats, or convert to the"
            " platform's indented CLI text (set-style configs are supported"
            " natively by the Juniper JunOS, VyOS, and Nokia SRL drivers)."
        )
        raise InvalidConfigError(message)


def hconfig_from_text(
    platform_or_driver: Platform | str | HConfigDriverBase,
    config_raw: Path | str = "",
) -> HConfig:
    if isinstance(config_raw, Path):
        config_raw = config_raw.read_text(encoding="utf8")

    _reject_structured_format(config_raw)

    config = HConfig(_get_driver(platform_or_driver))
    for rule in config.driver.rules.full_text_sub:
        config_raw = sub(rule.search, rule.replace, config_raw)

    _load_from_string_lines(config, config_raw)

    for child in tuple(config.all_children()):
        child.delete_sectional_exit()

    for callback in config.driver.rules.post_load_callbacks:
        callback(config)

    return config


def hconfig_from_dump(
    platform_or_driver: Platform | str | HConfigDriverBase, dump: Dump
) -> HConfig:
    """Load an HConfig dump."""
    config = HConfig(_get_driver(platform_or_driver))
    last_item: HConfig | HConfigChild = config
    for item in dump.lines:
        # parent is the root
        if item.depth == 1:
            parent: HConfig | HConfigChild = config
        # has the same parent
        elif last_item.depth == item.depth:
            parent = last_item.parent
        # is a child object
        elif last_item.depth + 1 == item.depth:
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


def hconfig_from_lines(
    platform_or_driver: Platform | str | HConfigDriverBase,
    lines: list[str] | tuple[str, ...] | str,
) -> HConfig:
    driver = _get_driver(platform_or_driver)
    config = HConfig(driver)
    if isinstance(lines, str):
        _reject_structured_format(lines)
        lines = lines.splitlines()

    current_section: HConfig | HConfigChild = config
    most_recent_item: HConfig | HConfigChild = current_section

    for original_line in lines:
        if not (line_lstripped := original_line.lstrip()):
            continue

        # Apply per_line_sub rules before processing
        processed_line = original_line
        for rule in driver.rules.per_line_sub:
            processed_line = sub(rule.search, rule.replace, processed_line)

        if not (line_lstripped := processed_line.lstrip()):
            continue
        indent = len(processed_line) - len(line_lstripped)

        # Determine parent in hierarchy
        most_recent_item, current_section = _analyze_indent(
            most_recent_item,
            current_section,
            indent,
            " ".join(processed_line.split()),
        )

    for child in tuple(config.all_children()):
        child.delete_sectional_exit()

    for callback in driver.rules.post_load_callbacks:
        callback(config)

    return config


def _get_driver(
    platform_or_driver: Platform | str | HConfigDriverBase,
) -> HConfigDriverBase:
    if isinstance(platform_or_driver, (Platform, str)):
        return get_hconfig_driver(platform_or_driver)
    return platform_or_driver


def _analyze_indent(
    most_recent_item: HConfig | HConfigChild,
    current_section: HConfig | HConfigChild,
    indent: int,
    line: str,
) -> tuple[HConfigChild, HConfig | HConfigChild]:
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


class _ConfigTextLoader:  # pylint: disable=too-many-instance-attributes,too-few-public-methods
    """Stateful parser turning raw config text into an HConfig tree (#186).

    Splits the three responsibilities of the former monolithic loader into
    focused methods: banner detection/aggregation, line normalization, and
    indentation-based hierarchy construction.
    """

    def __init__(self, config: HConfig) -> None:
        self.config = config
        self.current_section: HConfig | HConfigChild = config
        self.most_recent_item: HConfig | HConfigChild = config
        self.indent_adjust = 0
        self.end_indent_adjust: list[str] = []
        self.temp_banner: list[str] = []
        self.banner_end_lines = {"EOF", "%", "!"}
        self.banner_end_contains: list[str] = []
        self.in_banner = False

    def load(self, config_text: str) -> None:
        config_text = self.config.driver.config_preprocessor(config_text)
        for line in config_text.splitlines():
            if self.in_banner:
                self._process_banner_line(line)
            elif not self._detect_banner_start(line):
                self._process_config_line(line)
        if self.in_banner:
            message = "we are still in a banner for some reason"
            raise InvalidConfigError(message)

    def _process_banner_line(self, line: str) -> None:
        """Aggregate banner content until the end marker, then emit one child."""
        if line != "!":
            self.temp_banner.append(line)

        if _config_from_string_lines_end_of_banner_test(
            line,
            frozenset(self.banner_end_lines),
            self.banner_end_contains,
        ):
            self.in_banner = False
            self.most_recent_item = self.config.add_child("\n".join(self.temp_banner))
            self.most_recent_item.real_indent_level = 0
            self.current_section = self.config
            self.temp_banner = []

    def _detect_banner_start(self, line: str) -> bool:
        """Detect banner start markers and record the expected end markers."""
        # Empty banners matching the below expression have been seen on NX-OS
        if not line.startswith("banner ") or line == "banner motd ##":
            return False
        self.in_banner = True
        self.temp_banner.append(line)
        banner_words = line.split()
        with suppress(IndexError):
            self.banner_end_contains.append(banner_words[2])
            # Handle banner on ArubaOS-Switch
            if banner_words[2].startswith('"'):
                self.banner_end_contains.append('"')
            self.banner_end_lines.add(banner_words[2][:1])
            self.banner_end_lines.add(banner_words[2][:2])
        return True

    def _normalize_line(self, line: str) -> str:
        """Collapse repeated whitespace and apply per-line substitutions."""
        actual_indent = len(line) - len(line.lstrip())
        line = " " * actual_indent + " ".join(line.split())
        for rule in self.config.driver.rules.per_line_sub:
            line = sub(rule.search, rule.replace, line)
        return line.rstrip()

    def _process_config_line(self, line: str) -> None:
        """Attach a normalized config line to the correct place in the tree."""
        line = self._normalize_line(line)
        if not line:
            return

        # Determine indentation level (after per_line_sub rules are applied)
        this_indent = len(line) - len(line.lstrip()) + self.indent_adjust
        line = line.lstrip()

        self.most_recent_item, self.current_section = _analyze_indent(
            self.most_recent_item,
            self.current_section,
            this_indent,
            line,
        )
        self.indent_adjust, self.end_indent_adjust = _adjust_indent(
            self.config.driver,
            line,
            self.indent_adjust,
            self.end_indent_adjust,
        )
        if self.end_indent_adjust and search(self.end_indent_adjust[0], line):
            self.indent_adjust -= 1
            self.end_indent_adjust.pop(0)


def _load_from_string_lines(config: HConfig, config_text: str) -> None:
    _ConfigTextLoader(config).load(config_text)
