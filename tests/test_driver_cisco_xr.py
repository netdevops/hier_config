from hier_config import get_hconfig_fast_load
from hier_config.models import Platform


def test_duplicate_child_route_policy() -> None:
    platform = Platform.CISCO_XR
    running_config = get_hconfig_fast_load(
        platform,
        (
            "route-policy SET_COMMUNITY_AND_PERMIT",
            "  if destination in (192.0.2.0/24, 198.51.100.0/24) then",
            "    set community (65001:100) additive",
            "    pass",
            "  else",
            "    drop",
            "  endif",
            "end-policy",
            "",
            "route-policy SET_LOCAL_PREF_AND_PASS",
            "  if destination in (203.0.113.0/24) then",
            "    set local-preference 200",
            "    pass",
            "  else",
            "    drop",
            "  endif",
            "end-policy",
        ),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "route-policy SET_COMMUNITY_AND_PERMIT",
            "  if destination in (192.0.2.0/24, 198.51.100.0/24) then",
            "    set community (65001:100) additive",
            "    pass",
            "  else",
            "    drop",
            "  endif",
            "end-policy",
            "",
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple(sectional_exiting=True) == (
        "no route-policy SET_LOCAL_PREF_AND_PASS",
    )


def test_duplicate_child_router() -> None:
    platform = Platform.CISCO_XR
    running_config = get_hconfig_fast_load(
        platform,
        (
            "router eigrp EIGRP_INSTANCE",
            " address-family ipv4 unicast autonomous-system 10000",
            "  af-interface default",
            "   passive-interface",
            "  exit-af-interface",
            "  af-interface Vlan100",
            "   no passive-interface",
            "  exit-af-interface",
            "  af-interface GigabitEthernet0/0/1",
            "   no passive-interface",
            "  exit-af-interface",
            "  topology base",
            "   default-metric 1500 100 255 1 1500",
            "   redistribute bgp 65001",
            "  exit-af-topology",
            "  network 10.0.0.0",
            " exit-address-family",
        ),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "router eigrp EIGRP_INSTANCE",
            " address-family ipv4 unicast autonomous-system 10000",
            "  af-interface default",
            "   passive-interface",
            "  exit-af-interface",
            "  af-interface Vlan100",
            "   no passive-interface",
            "  exit-af-interface",
            "  af-interface GigabitEthernet0/0/1",
            "   no passive-interface",
            "  exit-af-interface",
            "  topology base",
            "   default-metric 1500 100 255 1 1500",
            "   redistribute bgp 65001 route-map ROUTE_MAP_IN",
            "  exit-af-topology",
            "  network 10.0.0.0",
            " exit-address-family",
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "router eigrp EIGRP_INSTANCE",
        "  address-family ipv4 unicast autonomous-system 10000",
        "    topology base",
        "      no redistribute bgp 65001",
        "      redistribute bgp 65001 route-map ROUTE_MAP_IN",
    )
