from hier_config import get_hconfig, get_hconfig_driver, get_hconfig_view
from hier_config.platforms.hp_procurve.functions import hp_procurve_expand_range
from hier_config.platforms.model import Platform


def test_hp_procurve_expand_range() -> None:
    assert hp_procurve_expand_range("1/1,1/2") == ("1/1", "1/2")
    assert hp_procurve_expand_range("1/1-1/2") == ("1/1", "1/2")
    assert hp_procurve_expand_range("1/1-1/4,1/10,1/11,1/14-1/15") == (
        "1/1",
        "1/2",
        "1/3",
        "1/4",
        "1/10",
        "1/11",
        "1/14",
        "1/15",
    )
    assert hp_procurve_expand_range("Trk1-Trk3") == ("Trk1", "Trk2", "Trk3")
    assert hp_procurve_expand_range("2/A2-2/A4") == ("2/A2", "2/A3", "2/A4")
    assert hp_procurve_expand_range("Trk1") == ("Trk1",)
    assert hp_procurve_expand_range("1/13") == ("1/13",)
    assert hp_procurve_expand_range("13") == ("13",)
    assert hp_procurve_expand_range("1-4,6-8,16") == (
        "1",
        "2",
        "3",
        "4",
        "6",
        "7",
        "8",
        "16",
    )


def test_bundle_name(cisco_ios_show_running_config: str) -> None:
    config = get_hconfig(
        get_hconfig_driver(Platform.CISCO_IOS), cisco_ios_show_running_config
    )
    config_view = get_hconfig_view(config)
    interface_view = config_view.interface_view_by_name("GigabitEthernet1/1/3")
    assert interface_view is not None
    assert interface_view.bundle_name == "Port-channel1"
