import pytest

from hier_config import get_hconfig_fast_load
from hier_config.exceptions import DuplicateChildError
from hier_config.models import Platform
from hier_config.utils import load_hconfig_v2_options


def test_generic_snmp_scenario_1() -> None:
    platform = Platform.HP_PROCURVE
    running_config = get_hconfig_fast_load(
	platform,
	(
	    "aaa group server tacacs TACACS_GROUP1",
	    "  server 192.2.0.3",
	    "  server 192.2.0.7",
            "aaa group server radius RADIUS_GROUP1",
	    "  server 192.2.0.121",
        ),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        (
	    "aaa group server tacacs TACACS_GROUP2",
	    "  server 192.2.0.3",
	    "  server 192.2.0.7",
            "aaa group server radius RADIUS_GROUP2",
	    "  server 192.2.0.121",
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
    	"no aaa group server tacacs TACACS_GROUP1",
    	"no aaa group server radius RADIUS_GROUP1",
	"aaa group server tacacs TACACS_GROUP2",
	"  server 192.2.0.3",
	"  server 192.2.0.7",
        "aaa group server radius RADIUS_GROUP2",
	"  server 192.2.0.121",
    )
