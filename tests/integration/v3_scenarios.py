"""Shared v3-API scenarios, run against both hier_config v3 and v4.

This module must stay importable under **both** major versions. It therefore
uses only names that exist in v3 and in v4's permanent v3-compatibility
surface, and it avoids the v4 behaviour changes that are out of scope for that
surface (`depth` as a property, the new exception types, and the completed
EOS/NX-OS/XR views).

The core scenario mirrors `nautobot_golden_config.models._get_hierconfig_remediation`
step for step, because golden config is the reference v3 consumer.

`tests/integration/test_v3_baseline.py` compares `run_all()` against a frozen
recording made on v3. `scripts/generate_v3_baseline.py` produces that recording
by importing this module inside a v3 virtual environment.
"""

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from hier_config import (
    Platform,
    WorkflowRemediation,
    get_hconfig,
    get_hconfig_driver,
    get_hconfig_fast_load,
    get_hconfig_from_dump,
)
from hier_config.constructors import get_hconfig_fast_generic_load
from hier_config.models import (
    MatchRule,
    NegationDefaultWhenRule,
    NegationDefaultWithRule,
    NegationSubRule,
)
from hier_config.utils import (
    HCONFIG_PLATFORM_V2_TO_V3_MAPPING,
    hconfig_v2_os_v3_platform_mapper,
    hconfig_v3_platform_v2_os_mapper,
    load_hconfig_v2_options,
    load_hconfig_v2_tags,
)

#: v2-style options, shaped like a golden config
#: ``RemediationSetting.remediation_options`` value.
REMEDIATION_OPTIONS: dict[str, Any] = {
    "negation_default_when": [{"lineage": [{"startswith": "interface Vlan"}]}],
    "negation_negate_with": [
        {"lineage": [{"startswith": "vlan"}], "use": "no vlan all"}
    ],
    "negation_sub": [
        {
            "lineage": [{"startswith": "ip access-list"}],
            "search": r"^no ip access-list (\S+) (\S+)$",
            "replace": r"no ip access-list \2",
        }
    ],
    "ordering": [{"lineage": [{"startswith": "vlan"}], "order": 700}],
    "sectional_exiting": [
        {"lineage": [{"startswith": "interface Vlan"}], "exit_text": "exit"}
    ],
    "per_line_sub": [{"search": "^Building configuration.*$", "replace": ""}],
    "idempotent_commands": [
        {"lineage": [{"startswith": "interface Vlan"}, {"startswith": "mtu"}]}
    ],
}

#: v2-style tag rules, used to exercise the filtered-text branch.
TAG_RULES: list[dict[str, Any]] = [
    {"lineage": [{"startswith": "vlan"}], "add_tags": "safe"},
    {"lineage": [{"startswith": "interface Vlan"}], "add_tags": "risky"},
]

#: A small vendor-neutral config for the generic fast loader. The IOS fixtures
#: cannot be used here: the generic driver keeps their `!` separator lines,
#: which collide as duplicate children.
GENERIC_CONFIG = """system
  hostname example
  domain-name example.net
interface eth0
  address 10.0.0.1/24
  enabled true"""

#: A pair built to fire every negation strategy in REMEDIATION_OPTIONS:
#: REPLACE on `vlan`, DEFAULT on `interface Vlan`, and REGEX_SUB on
#: `ip access-list`.
NEGATION_RUNNING = """hostname keep
vlan 5
 name gone
interface Vlan9
 description gone
 shutdown
ip access-list extended OLD
 10 permit ip any any"""
NEGATION_GENERATED = "hostname keep"

#: Fixture file pairs, as (label, v2 driver name, running, generated).
FIXTURE_PAIRS = (
    ("ios", "ios", "running_config.conf", "generated_config.conf"),
    ("junos", "junos", "running_config_junos.conf", "generated_config_junos.conf"),
    ("acl", "ios", "running_config_acl.conf", "generated_config_acl.conf"),
)


def golden_config_remediation(
    network_driver: str,
    actual: str,
    intended: str,
    remediation_options: dict[str, Any] | None = None,
) -> str:
    """Mirror of `nautobot_golden_config.models._get_hierconfig_remediation`.

    Every statement below is the golden config code path, in its order.
    """
    hierconfig_os: Any = hconfig_v2_os_v3_platform_mapper(network_driver)
    if remediation_options:
        hierconfig_os = load_hconfig_v2_options(remediation_options, hierconfig_os)

    hierconfig_running_config = get_hconfig(hierconfig_os, actual)
    hierconfig_intended_config = get_hconfig(hierconfig_os, intended)
    hierconfig_wfr = WorkflowRemediation(
        hierconfig_running_config,
        hierconfig_intended_config,
    )
    return hierconfig_wfr.remediation_config_filtered_text(
        include_tags={}, exclude_tags={}
    )


def tagged_remediation(
    network_driver: str,
    actual: str,
    intended: str,
    *,
    include_tags: Iterable[str] = (),
    exclude_tags: Iterable[str] = (),
) -> str:
    """Golden config's call path with TAG_RULES applied before filtering.

    Covers the non-empty branch of `remediation_config_filtered_text`, which
    golden config reaches when a device has tag rules configured.
    """
    platform = hconfig_v2_os_v3_platform_mapper(network_driver)
    workflow = WorkflowRemediation(
        get_hconfig(platform, actual),
        get_hconfig(platform, intended),
    )
    workflow.apply_remediation_tag_rules(load_hconfig_v2_tags(TAG_RULES))
    return workflow.remediation_config_filtered_text(
        include_tags=include_tags, exclude_tags=exclude_tags
    )


def appended_rules_remediation(actual: str, intended: str) -> str:
    """Append negation rules to a live driver, the way v3's own docs teach.

    `docs/user/custom-drivers.md` at tag v3.7.0 shows
    `driver.rules.negate_with.append(...)` and
    `driver.rules.negation_sub.append(...)`. That idiom must keep working, so
    it is exercised here rather than only through the constructor.
    """
    driver = get_hconfig_driver(Platform.CISCO_IOS)
    driver.rules.negate_with.append(
        NegationDefaultWithRule(
            match_rules=(MatchRule(startswith="vlan"),), use="no vlan all"
        )
    )
    driver.rules.negation_default_when.append(
        NegationDefaultWhenRule(match_rules=(MatchRule(startswith="interface Vlan"),))
    )
    driver.rules.negation_sub.append(
        NegationSubRule(
            match_rules=(MatchRule(startswith="ip access-list"),),
            search=r"^no ip access-list (\S+) (\S+)$",
            replace=r"no ip access-list \2",
        )
    )
    workflow = WorkflowRemediation(
        get_hconfig(driver, actual), get_hconfig(driver, intended)
    )
    return workflow.remediation_config_filtered_text(include_tags={}, exclude_tags={})


def resolved_driver(network_driver: str) -> str:
    """Return the driver golden config would get for a netutils driver name.

    This is the mapper's real job. A miss here falls back to `Platform.GENERIC`
    and produces a wrong -- often destructive -- remediation with no error, so
    the mapping is locked name by name rather than through a remediation.
    """
    platform = hconfig_v2_os_v3_platform_mapper(network_driver)
    return f"{platform.name}:{get_hconfig_driver(platform).__class__.__name__}"


def other_v3_names(actual: str, intended: str) -> dict[str, str]:
    """Exercise the restored v3 names that golden config does not call."""
    config = get_hconfig(Platform.CISCO_IOS, actual)
    generated = get_hconfig(Platform.CISCO_IOS, intended)

    for child in config.children:
        child.tags_add("safe")
    tagged = "\n".join(c.cisco_style_text() for c in config.all_children_sorted())
    tags_while_set = ",".join(sorted(config.tags))
    for child in config.children:
        child.tags_remove("safe")

    return {
        "fast_load": "\n".join(
            get_hconfig_fast_load(Platform.CISCO_IOS, actual).dump_simple()
        ),
        "fast_generic_load": "\n".join(
            get_hconfig_fast_generic_load(GENERIC_CONFIG).dump_simple()
        ),
        "from_dump": "\n".join(
            get_hconfig_from_dump(Platform.CISCO_IOS, config.dump()).dump_simple()
        ),
        "config_to_get_to": "\n".join(config.config_to_get_to(generated).dump_simple()),
        "dump_simple_sectional": "\n".join(config.dump_simple(sectional_exiting=True)),
        "cisco_style_text": tagged,
        "tags_while_set": tags_while_set,
        "tags_after_remove": ",".join(sorted(config.tags)),
        "v3_platform_to_v2_os": ",".join(
            f"{p.name}={hconfig_v3_platform_v2_os_mapper(p)}"
            for p in sorted(Platform, key=lambda p: p.name)
        ),
    }


def run_all(fixtures_dir: Path) -> dict[str, str]:
    """Run every scenario and return scenario name -> output text."""
    read = {
        name: (fixtures_dir / name).read_text(encoding="utf8")
        for _, _driver, running, generated in FIXTURE_PAIRS
        for name in (running, generated)
    }
    ios_running = read["running_config.conf"]
    ios_generated = read["generated_config.conf"]

    results: dict[str, str] = {}

    # 1. The common golden config path: no remediation options.
    for label, driver_name, running, generated in FIXTURE_PAIRS:
        results[f"plain:{label}"] = golden_config_remediation(
            driver_name, read[running], read[generated]
        )

    # 2. Every driver name the v2 mapper knows, plus the unknown and
    #    whitespace-padded forms.
    for os_name in (
        *sorted(HCONFIG_PLATFORM_V2_TO_V3_MAPPING),
        "not_a_platform",
        " iosxe ",
    ):
        results[f"driver:{os_name.strip()}"] = resolved_driver(os_name)

    # 3. Remediation options present -- reaches the v3 negation rule models.
    results["options:ios"] = golden_config_remediation(
        "ios", ios_running, ios_generated, REMEDIATION_OPTIONS
    )
    results["options:negation"] = golden_config_remediation(
        "ios", NEGATION_RUNNING, NEGATION_GENERATED, REMEDIATION_OPTIONS
    )
    results["options:negation_without_options"] = golden_config_remediation(
        "ios", NEGATION_RUNNING, NEGATION_GENERATED
    )
    results["options:negation_appended"] = appended_rules_remediation(
        NEGATION_RUNNING, NEGATION_GENERATED
    )

    # 4. Tag filtering.
    results["tags:include_safe"] = tagged_remediation(
        "ios", ios_running, ios_generated, include_tags=["safe"]
    )
    results["tags:exclude_risky"] = tagged_remediation(
        "ios", ios_running, ios_generated, exclude_tags=["risky"]
    )

    # 5. The remaining restored names.
    for key, value in other_v3_names(ios_running, ios_generated).items():
        results[f"other:{key}"] = value

    return results


if __name__ == "__main__":
    import json
    import sys

    sys.stdout.write(
        f"{json.dumps(run_all(Path(sys.argv[1])), indent=2, sort_keys=True)}\n"
    )
