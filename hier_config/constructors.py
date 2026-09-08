from contextlib import suppress
from json import JSONDecodeError, loads
from logging import getLogger
from pathlib import Path

from hier_config.platforms.driver_base import HConfigDriverBase, runs_in_core

from .exceptions import DriverNotFoundError, InvalidConfigError
from .models import Dump, Platform
from .platforms.view_base import HConfigViewBase
from .registry import get_hconfig_driver, resolve_driver
from .root import HConfig

logger = getLogger(__name__)

__all__ = (
    "get_hconfig",
    "get_hconfig_driver",
    "get_hconfig_fast_generic_load",
    "get_hconfig_fast_load",
    "get_hconfig_from_dump",
    "get_hconfig_view",
    "hconfig_from_dump",
    "hconfig_from_lines",
    "hconfig_from_text",
)


def get_hconfig_view(config: HConfig) -> HConfigViewBase:
    """Instantiates the HConfigView declared by the config's driver.

    Drivers declare their view via the `view_class` attribute, so a custom
    driver can register its own view by setting `view_class` on the subclass.
    """
    if view_class := config.driver.view_class:
        return view_class(config)

    message = f"No view registered for driver: {config.driver.__class__.__name__}"
    raise DriverNotFoundError(message)


def _run_post_load_callbacks(config: HConfig, driver: HConfigDriverBase) -> None:
    """Apply the driver's post-load callbacks that the Rust core did not.

    Built-in drivers list their stock callbacks so they stay discoverable and
    reusable (#286), but the core already applied them while parsing, so those
    are skipped here rather than run a second time.
    """
    for callback in driver.rules.post_load_callbacks:
        if runs_in_core(callback, driver.platform):
            continue
        callback(config)


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


def _new_config(driver: HConfigDriverBase) -> HConfig:
    """Construct an ``HConfig`` and claim it as its tree's canonical root.

    PyO3 exposes ``__init__`` as an ordinary method rather than the ``tp_init``
    slot, so the native constructor cannot register the object it just built.
    Reading ``root`` once here does that registration, guaranteeing that
    ``child.root is config`` for every config the library hands out.
    """
    config = HConfig(driver)
    _ = config.root
    return config


def hconfig_from_text(
    platform_or_driver: Platform | str | HConfigDriverBase,
    config_raw: Path | str = "",
) -> HConfig:
    """Create an HConfig from raw configuration text (or a Path to it).

    Parsing runs in the Rust core, which applies the driver's full-text and
    per-line substitutions, the config preprocessor, banner handling, indent
    analysis, and sectional-exit stripping in a single pass. Only callbacks the
    core did not already apply are run here.
    """
    config = _new_config(resolve_driver(platform_or_driver))

    if isinstance(config_raw, Path):
        config._load_file_native(str(config_raw), True)  # ruff: ignore[private-member-access, boolean-positional-value-in-call]
    else:
        _reject_structured_format(config_raw)
        _load_from_string_lines(config, config_raw)

    _run_post_load_callbacks(config, config.driver)

    return config


def _load_from_string_lines(config: HConfig, config_text: str) -> None:
    """Parse `config_text` into `config` using the Rust core's text loader.

    Kept as a private seam so callers (and tests) can drive parsing on an
    already-constructed tree without going through `hconfig_from_text`.
    """
    config._load_native(config_text, True)  # ruff: ignore[private-member-access, boolean-positional-value-in-call]


def hconfig_from_dump(
    platform_or_driver: Platform | str | HConfigDriverBase, dump: Dump
) -> HConfig:
    """Reconstruct an HConfig from a serialized Dump.

    Rebuilding the tree from the flat, depth-annotated dump lines happens in
    the Rust core so the parent lookup stays O(1) per line.
    """
    driver = resolve_driver(platform_or_driver)
    config = _new_config(driver)
    config._load_from_dump_native(dump.lines)  # ruff: ignore[private-member-access]
    _run_post_load_callbacks(config, driver)
    return config


def hconfig_from_lines(
    platform_or_driver: Platform | str | HConfigDriverBase,
    lines: list[str] | tuple[str, ...] | str,
) -> HConfig:
    """Create an HConfig from pre-split configuration lines (fast load).

    Applies per-line substitutions and indentation analysis in the Rust core
    but skips the full-text substitutions, config preprocessor, and banner
    handling of `hconfig_from_text`.
    """
    driver = resolve_driver(platform_or_driver)
    config = _new_config(driver)
    if isinstance(lines, str):
        _reject_structured_format(lines)
        lines = lines.splitlines()

    config._load_fast_native(list(lines), True)  # ruff: ignore[private-member-access, boolean-positional-value-in-call]

    _run_post_load_callbacks(config, driver)

    return config


# --- v3 compatibility -----------------------------------------------------
#
# The names below are the v3 spellings of the constructors above. They are
# supported permanently and emit no DeprecationWarning. Each one delegates to
# its v4 counterpart, so behaviour never drifts between the two spellings.


def get_hconfig(
    platform_or_driver: Platform | str | HConfigDriverBase,
    config_raw: Path | str = "",
) -> HConfig:
    """v3 name for `HConfig.from_text()`. Both spellings are supported."""
    return hconfig_from_text(platform_or_driver, config_raw)


def get_hconfig_from_dump(
    platform_or_driver: Platform | str | HConfigDriverBase,
    dump: Dump,
) -> HConfig:
    """v3 name for `HConfig.from_dump()`. Both spellings are supported."""
    return hconfig_from_dump(platform_or_driver, dump)


def get_hconfig_fast_load(
    platform_or_driver: Platform | str | HConfigDriverBase,
    lines: list[str] | tuple[str, ...] | str,
) -> HConfig:
    """v3 name for `HConfig.from_lines()`. Both spellings are supported."""
    return hconfig_from_lines(platform_or_driver, lines)


def get_hconfig_fast_generic_load(
    lines: list[str] | tuple[str, ...] | str,
) -> HConfig:
    """v3 name for `HConfig.from_lines(Platform.GENERIC, lines)`."""
    return hconfig_from_lines(Platform.GENERIC, lines)
