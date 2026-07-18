"""Tests for hier_config/constructors.py."""

from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from hier_config import (
    get_hconfig_driver,
    get_hconfig_view,
)
from hier_config.constructors import (
    _adjust_indent,  # pyright: ignore[reportPrivateUsage]
    _config_from_string_lines_end_of_banner_test,  # pyright: ignore[reportPrivateUsage]
    _load_from_string_lines,  # pyright: ignore[reportPrivateUsage]
)
from hier_config.exceptions import DriverNotFoundError, InvalidConfigError
from hier_config.models import Platform
from hier_config.platforms.arista_eos.view import HConfigViewAristaEOS
from hier_config.platforms.cisco_ios.driver import HConfigDriverCiscoIOS
from hier_config.platforms.cisco_ios.view import HConfigViewCiscoIOS
from hier_config.platforms.cisco_nxos.view import HConfigViewCiscoNXOS
from hier_config.platforms.cisco_xr.view import HConfigViewCiscoIOSXR
from hier_config.platforms.hp_procurve.view import HConfigViewHPProcurve
from hier_config.root import HConfig


def test_get_hconfig_driver_unsupported_platform() -> None:
    """Test DriverNotFoundError when platform is not supported (lines 49-50)."""
    with pytest.raises(
        DriverNotFoundError, match="Unsupported platform: invalid_platform"
    ):
        get_hconfig_driver("invalid_platform")


def test_get_hconfig_view_unsupported_platform() -> None:
    """Test DriverNotFoundError when the driver declares no view."""
    driver = get_hconfig_driver(Platform.FORTINET_FORTIOS)
    config = HConfig(driver=driver)
    with pytest.raises(
        DriverNotFoundError,
        match="No view registered for driver: HConfigDriverFortinetFortiOS",
    ):
        get_hconfig_view(config)


def test_get_hconfig_view_dispatches_on_driver_view_class() -> None:
    """Each built-in driver with a view resolves it via view_class (#187)."""
    for platform, view_cls in (
        (Platform.ARISTA_EOS, HConfigViewAristaEOS),
        (Platform.CISCO_IOS, HConfigViewCiscoIOS),
        (Platform.CISCO_NXOS, HConfigViewCiscoNXOS),
        (Platform.CISCO_XR, HConfigViewCiscoIOSXR),
        (Platform.HP_PROCURVE, HConfigViewHPProcurve),
    ):
        config = HConfig(driver=get_hconfig_driver(platform))
        view = get_hconfig_view(config)
        assert isinstance(view, view_cls)


def test_get_hconfig_view_inherited_by_driver_subclass() -> None:
    """A driver subclass inherits its parent's view_class (#187)."""

    class ExtendedIOSDriver(HConfigDriverCiscoIOS):
        """Driver subclass without its own view_class."""

    config = HConfig(driver=ExtendedIOSDriver())
    view = get_hconfig_view(config)

    assert isinstance(view, HConfigViewCiscoIOS)


def test_get_hconfig_view_custom_driver_view_class() -> None:
    """A user-defined driver can supply its own view via view_class (#187, #229)."""

    class CustomView(HConfigViewCiscoIOS):
        """User-defined view."""

    class CustomDriver(HConfigDriverCiscoIOS):
        """User-defined driver registering its own view."""

        view_class = CustomView

    config = HConfig(driver=CustomDriver())
    view = get_hconfig_view(config)

    assert isinstance(view, CustomView)


def test_get_hconfig_from_path() -> None:
    """Test loading HConfig from a Path object (line 85)."""
    config_content = "hostname test\ninterface GigabitEthernet0/0\n description test"
    with NamedTemporaryFile(
        encoding="utf-8", mode="w", suffix=".conf", delete=False
    ) as tmpfile:
        tmpfile.write(config_content)
        tmpfile.flush()
        path = Path(tmpfile.name)

    driver = get_hconfig_driver(Platform.CISCO_IOS)
    result = HConfig.from_text(driver, path)
    hostname_child = result.get_child(startswith="hostname")
    try:
        assert hostname_child is not None
    finally:
        path.unlink()
    assert len(result.children) > 0


def test_get_hconfig_from_dump_with_depth_calculation() -> None:
    """Test depth calculation when loading from dump (lines 110, 116)."""
    config = """hostname router1
interface GigabitEthernet0/0
 description test
 ip address 10.0.0.1 255.255.255.0
 no shutdown
"""
    driver = get_hconfig_driver(Platform.CISCO_IOS)
    hconfig = HConfig.from_text(driver, config)

    dump = hconfig.dump()

    restored = HConfig.from_dump(driver, dump)
    hostname_child = restored.get_child(startswith="hostname")
    assert hostname_child is not None

    interface = None
    for child in restored.children:
        if child.text.startswith("interface"):
            interface = child
            break

    assert interface is not None
    assert len(interface.children) > 0
    assert interface.depth == 1
    for subchild in interface.children:
        assert subchild.depth == 2


def test_get_hconfig_fast_generic_load_with_string_conversion() -> None:
    """Test fast generic load with string conversion (line 129)."""
    config_lines = [
        "hostname router1",
        "interface GigabitEthernet0/0",
        " description test",
    ]
    result = HConfig.from_lines(Platform.GENERIC, config_lines)
    hostname_child = result.get_child(startswith="hostname")
    assert hostname_child is not None
    assert len(result.children) > 0


def test_get_hconfig_fast_load_with_string_conversion() -> None:
    """Test fast load with string conversion (line 129)."""
    config_lines = [
        "hostname router1",
        "interface GigabitEthernet0/0",
        " description test",
    ]
    driver = get_hconfig_driver(Platform.CISCO_IOS)
    result = HConfig.from_lines(driver, config_lines)
    hostname_child = result.get_child(startswith="hostname")
    assert hostname_child is not None
    assert len(result.children) > 0


def test_adjust_indent_with_indent_adjust_values() -> None:
    """Test _adjust_indent with indent_adjust values (lines 206-207)."""
    driver = get_hconfig_driver(Platform.CISCO_IOS)

    line = "policy-map test"
    indent_adjust = 0
    end_indent_adjust: list[str] = []

    result = _adjust_indent(driver, line, indent_adjust, end_indent_adjust)
    assert isinstance(result, tuple)
    assert len(result) == 2
    new_indent, new_end = result
    assert isinstance(new_indent, int)
    assert isinstance(new_end, list)


def test_banner_end_detection_with_delimiter() -> None:
    """Test banner end detection with delimiter (lines 216-220)."""
    line = "^C"
    result = _config_from_string_lines_end_of_banner_test(
        line, frozenset({"EOF", "%", "!"}), ["^C"]
    )
    assert result is True

    line = "%"
    result = _config_from_string_lines_end_of_banner_test(
        line, frozenset({"EOF", "%", "!"}), []
    )
    assert result is True

    line = "!"
    result = _config_from_string_lines_end_of_banner_test(
        line, frozenset({"EOF", "%", "!"}), []
    )
    assert result is True

    line = "This is banner text^C"
    result = _config_from_string_lines_end_of_banner_test(
        line, frozenset({"EOF"}), ["^C"]
    )
    assert result is True

    line = "This is just regular text"
    result = _config_from_string_lines_end_of_banner_test(line, frozenset({"EOF"}), [])
    assert result is False


def test_load_from_string_lines_with_banner_start() -> None:
    """Test banner start detection and handling (lines 237-253, 258-269)."""
    driver = get_hconfig_driver(Platform.CISCO_IOS)
    config = HConfig(driver=driver)

    config_text = """hostname router1
banner motd ^C
This is line 1
This is line 2
^C
interface GigabitEthernet0/0
"""
    _load_from_string_lines(config, config_text)

    banner_found = False
    for child in config.children:
        if child.text.startswith("banner motd"):
            banner_found = True
            assert "^C" in child.text
            break
    assert banner_found


def test_load_from_string_lines_with_empty_banner_line() -> None:
    """Test banner with empty lines (lines 237-253, 258-269)."""
    driver = get_hconfig_driver(Platform.CISCO_IOS)
    config = HConfig(driver=driver)

    config_text = """banner motd ^C
Line 1

Line 3
^C
"""
    _load_from_string_lines(config, config_text)

    banner_found = False
    for child in config.children:
        if child.text.startswith("banner motd"):
            banner_found = True
            break
    assert banner_found


def test_load_from_string_lines_with_banner_multiline_content() -> None:
    """Test banner with multiple lines of content (lines 237-253, 258-269)."""
    driver = get_hconfig_driver(Platform.CISCO_IOS)
    config = HConfig(driver=driver)

    config_text = """banner exec %
Welcome to the router
Unauthorized access is prohibited
Contact: admin@example.com
%
"""
    _load_from_string_lines(config, config_text)

    banner_found = False
    for child in config.children:
        if child.text.startswith("banner exec"):
            banner_found = True
            assert "%" in child.text
            break
    assert banner_found


def test_load_from_string_lines_with_incomplete_banner() -> None:
    """Test incomplete banner raises error (lines 301-302, 304-305)."""
    driver = get_hconfig_driver(Platform.CISCO_IOS)
    config = HConfig(driver=driver)

    config_text = """banner motd ^C
This is line 1
This is line 2
"""
    with pytest.raises(
        InvalidConfigError, match="we are still in a banner for some reason"
    ):
        _load_from_string_lines(config, config_text)


def test_load_from_string_lines_banner_with_same_line_delimiter() -> None:
    """Test banner with delimiter on same line (lines 258-269)."""
    driver = get_hconfig_driver(Platform.CISCO_IOS)
    config = HConfig(driver=driver)

    config_text = """banner motd ^C
Message
^C
interface GigabitEthernet0/0
"""
    _load_from_string_lines(config, config_text)

    banner_found = False
    for child in config.children:
        if child.text.startswith("banner motd"):
            banner_found = True
            break
    assert banner_found


def test_indent_adjust_with_multiple_adjustments() -> None:
    """Test indent adjustment with multiple active adjustments (lines 206-207)."""
    driver = get_hconfig_driver(Platform.CISCO_IOS)

    line = "class test-class"
    indent_adjust = 1
    end_indent_adjust = ["!"]

    result = _adjust_indent(driver, line, indent_adjust, end_indent_adjust)
    assert isinstance(result, tuple)
    assert len(result) == 2
    new_indent, new_end = result
    assert isinstance(new_indent, int)
    assert isinstance(new_end, list)


def test_get_hconfig_from_dump_parent_depth_traversal() -> None:
    """Test parent depth calculation during dump loading (line 116)."""
    config = """hostname router1
router bgp 65000
 address-family ipv4
  network 10.0.0.0 mask 255.255.255.0
  neighbor 10.0.0.2 activate
"""
    driver = get_hconfig_driver(Platform.CISCO_IOS)
    hconfig = HConfig.from_text(driver, config)

    dump = hconfig.dump()
    restored = HConfig.from_dump(driver, dump)

    router_bgp = None
    for child in restored.children:
        if child.text.startswith("router bgp"):
            router_bgp = child
            break

    assert router_bgp is not None
    assert router_bgp.depth == 1

    if router_bgp.children:
        address_family = None
        for child in router_bgp.children:
            if child.text.startswith("address-family"):
                address_family = child
                break

        if address_family:
            assert address_family.depth == 2
            if address_family.children:
                for nested_child in address_family.children:
                    assert nested_child.depth == 3


def test_banner_detection_with_various_delimiters() -> None:
    """Test banner detection with different delimiter types (lines 258-269)."""
    driver = get_hconfig_driver(Platform.CISCO_IOS)
    config = HConfig(driver=driver)

    config_text = """banner login !
Unauthorized access prohibited
!
"""
    _load_from_string_lines(config, config_text)

    banner_found = False
    for child in config.children:
        if child.text.startswith("banner login"):
            banner_found = True
            assert "!" in child.text
            break
    assert banner_found


def test_adjust_indent_with_no_active_adjustments() -> None:
    """Test _adjust_indent when no adjustments are active (lines 206-207)."""
    driver = get_hconfig_driver(Platform.CISCO_IOS)

    line = "description test"
    result = _adjust_indent(driver, line, 0, [])
    assert result == (0, [])


def test_banner_with_aruba_switch_quote_delimiter() -> None:
    """Test banner with quote delimiter for ArubaOS-Switch (line 265)."""
    driver = get_hconfig_driver(Platform.HP_PROCURVE)
    config = HConfig(driver=driver)

    config_text = """banner motd "
This is a message
"
"""
    _load_from_string_lines(config, config_text)

    banner_found = False
    for child in config.children:
        if child.text.startswith("banner motd"):
            banner_found = True
            break
    assert banner_found


def test_get_hconfig_from_dump_with_complex_nesting() -> None:
    """Test get_hconfig_from_dump with complex parent traversal (line 116)."""
    config = """hostname router1
interface GigabitEthernet0/0
 description test
router bgp 65000
 address-family ipv4
  network 10.0.0.0 mask 255.255.255.0
  network 192.168.0.0 mask 255.255.255.0
 address-family ipv6
  network 2001:db8::/32
interface GigabitEthernet0/1
 description another
"""
    driver = get_hconfig_driver(Platform.CISCO_IOS)
    hconfig = HConfig.from_text(driver, config)

    dump = hconfig.dump()

    restored = HConfig.from_dump(driver, dump)

    assert len(restored.children) > 0

    router_bgp = None
    for child in restored.children:
        if child.text.startswith("router bgp"):
            router_bgp = child
            break

    assert router_bgp is not None
    assert len(router_bgp.children) >= 2

    for af_child in router_bgp.children:
        if af_child.text.startswith("address-family"):
            assert len(af_child.children) >= 1


def test_xml_config_raises_invalid_config_error() -> None:
    """XML input is detected and rejected with a clear message (#232)."""
    xml_text = '<?xml version="1.0"?><config><system><name>r1</name></system></config>'
    with pytest.raises(InvalidConfigError, match="appears to be XML"):
        HConfig.from_text(Platform.CISCO_IOS, xml_text)


def test_json_config_raises_invalid_config_error() -> None:
    """JSON input is detected and rejected with a clear message (#232)."""
    json_text = '{"system": {"config": {"hostname": "r1"}}}'
    with pytest.raises(InvalidConfigError, match="appears to be JSON"):
        HConfig.from_text(Platform.CISCO_IOS, json_text)


def test_curly_brace_junos_config_still_parses() -> None:
    """Junos hierarchical (curly-brace) config is not misdetected as JSON (#232)."""
    junos_text = "system {\n    host-name r1;\n}\n"
    config = HConfig.from_text(Platform.JUNIPER_JUNOS, junos_text)
    assert config.get_child(equals="set system host-name r1") is not None


def test_json_via_from_lines_str_raises() -> None:
    """The str form of from_lines gets the same format guard as from_text (#232)."""
    json_text = '{"system": {"config": {"hostname": "r1"}}}'
    with pytest.raises(InvalidConfigError, match="appears to be JSON"):
        HConfig.from_lines(Platform.CISCO_IOS, json_text)
