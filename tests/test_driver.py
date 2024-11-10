from hier_config import get_hconfig_driver
from hier_config.model import Platform
from hier_config.platforms.arista_eos.driver import HConfigDriverAristaEOS
from hier_config.platforms.cisco_ios.driver import HConfigDriverCiscoIOS
from hier_config.platforms.cisco_nxos.driver import HConfigDriverCiscoNXOS
from hier_config.platforms.cisco_xr.driver import HConfigDriverCiscoIOSXR
from hier_config.platforms.generic.driver import HConfigDriverGeneric
from hier_config.platforms.hp_comware5.driver import HConfigDriverHPComware5
from hier_config.platforms.hp_procurve.driver import HConfigDriverHPProcurve
from hier_config.platforms.vyos.driver import HConfigDriverVYOS


def test_get_hconfig_driver() -> None:
    assert isinstance(get_hconfig_driver(Platform.ARISTA_EOS), HConfigDriverAristaEOS)
    assert isinstance(get_hconfig_driver(Platform.CISCO_IOS), HConfigDriverCiscoIOS)
    assert isinstance(get_hconfig_driver(Platform.CISCO_NXOS), HConfigDriverCiscoNXOS)
    assert isinstance(get_hconfig_driver(Platform.CISCO_XR), HConfigDriverCiscoIOSXR)
    assert isinstance(get_hconfig_driver(Platform.GENERIC), HConfigDriverGeneric)
    assert isinstance(get_hconfig_driver(Platform.HP_PROCURVE), HConfigDriverHPProcurve)
    assert isinstance(get_hconfig_driver(Platform.HP_COMWARE5), HConfigDriverHPComware5)
    assert isinstance(get_hconfig_driver(Platform.VYOS), HConfigDriverVYOS)
