from hier_config import get_hconfig, get_hconfig_driver
from hier_config.model import Platform


def test_issue104() -> None:
    running_config_raw = (
        "tacacs-server deadtime 3\ntacacs-server host 192.168.1.99 key 7 Test12345\n"
    )
    generated_config_raw = (
        "tacacs-server host 192.168.1.98 key 0 Test135 timeout 3\n"
        "tacacs-server host 192.168.100.98 key 0 test135 timeout 3\n"
    )

    platform = Platform.CISCO_NXOS
    running_config = get_hconfig(get_hconfig_driver(platform), running_config_raw)
    generated_config = get_hconfig(get_hconfig_driver(platform), generated_config_raw)
    rem = running_config.config_to_get_to(generated_config)
    expected_rem_lines = {
        "no tacacs-server deadtime 3",
        "no tacacs-server host 192.168.1.99 key 7 Test12345",
        "tacacs-server host 192.168.1.98 key 0 Test135 timeout 3",
        "tacacs-server host 192.168.100.98 key 0 test135 timeout 3",
    }
    rem_lines = {line.cisco_style_text() for line in rem.all_children()}
    assert expected_rem_lines == rem_lines
