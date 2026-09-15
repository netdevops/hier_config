import re

import pytest

from hier_config import (
    HConfig,
    Platform,
    WorkflowRemediation,
    get_hconfig,
    get_hconfig_fast_load,
)
from hier_config.platforms.ruckus_fastiron.functions import fastiron_expand_ports


def _load(lines: tuple[str, ...]) -> HConfig:
    return get_hconfig_fast_load(Platform.RUCKUS_FASTIRON, lines)


def _assert_rollback_restores(
    running_config: HConfig,
    remediation: HConfig,
) -> None:
    """Prove the change can be backed out, per docs/dev/testing.md."""
    running_after = running_config.future(remediation)
    rollback = running_after.config_to_get_to(running_config)
    running_after_rollback = running_after.future(rollback)
    assert not tuple(running_config.unified_diff(running_after_rollback))


def _ordered_remediation(
    running_config: HConfig,
    generated_config: HConfig,
) -> tuple[str, ...]:
    """Remediation as WorkflowRemediation emits it, i.e. with ordering applied."""
    workflow = WorkflowRemediation(running_config, generated_config)
    return workflow.remediation_config.dump_simple()


def test_per_line_sub_strips_banner_noise() -> None:
    config = get_hconfig(
        Platform.RUCKUS_FASTIRON,
        "SW01#sh run\nCurrent configuration:\n!\nver 08.0.30rT311\n!\n"
        "hostname SW01\n!\nend\n",
    )
    assert config.dump_simple() == ("hostname SW01",)


def test_stack_config_is_not_remediated() -> None:
    running_config = get_hconfig(
        Platform.RUCKUS_FASTIRON,
        "stack unit 1\n module 1 icx6450-48-port-management-module\n"
        " priority 128\nstack enable\nhostname SW01\n",
    )
    generated_config = get_hconfig(Platform.RUCKUS_FASTIRON, "hostname SW01\n")
    assert running_config.dump_simple() == ("hostname SW01",)
    assert not running_config.config_to_get_to(generated_config).dump_simple()


def test_vlan_membership_is_expanded_per_port() -> None:
    config = get_hconfig(
        Platform.RUCKUS_FASTIRON,
        "vlan 101 name USERS by port\n tagged ethe 1/1/1 to 1/1/3 ethe 1/2/4\n"
        " untagged ethe 2/1/1\n",
    )
    assert config.dump_simple() == (
        "vlan 101",
        " untagged ethe 2/1/1",
        " vlan 101 name USERS by port",
        " tagged ethe 1/1/1",
        " tagged ethe 1/1/2",
        " tagged ethe 1/1/3",
        " tagged ethe 1/2/4",
    )


def test_split_vlan_blocks_are_merged() -> None:
    """One VLAN spread over two blocks must end up as one section.

    A template is free to emit `vlan 101` in one place and
    `vlan 101 name USERS by port` in another. Left alone that would leave two
    sibling sections for the same VLAN, which then diff against each other.
    """
    config = get_hconfig(
        Platform.RUCKUS_FASTIRON,
        "vlan 101\n tagged ethe 1/1/1\nhostname SW01\n"
        "vlan 101 name USERS by port\n router-interface ve 101\n",
    )
    assert config.dump_simple() == (
        "vlan 101",
        " tagged ethe 1/1/1",
        " vlan 101 name USERS by port",
        " router-interface ve 101",
        "hostname SW01",
    )


def test_split_vlan_blocks_do_not_produce_a_diff() -> None:
    """The merged form must compare equal to the device's own rendering."""
    from_device = _load(
        (
            "vlan 101 name USERS by port",
            " tagged ethe 1/1/1",
            " router-interface ve 101",
        ),
    )
    from_template = _load(
        (
            "vlan 101",
            " tagged ethe 1/1/1",
            "vlan 101 name USERS by port",
            " router-interface ve 101",
        ),
    )
    assert not from_device.config_to_get_to(from_template).dump_simple()


def test_unparsable_membership_line_is_left_alone() -> None:
    config = get_hconfig(
        Platform.RUCKUS_FASTIRON,
        "vlan 101 name USERS by port\n tagged ethe 1/1/1 to 2/1/3\n",
    )
    assert config.dump_simple() == (
        "vlan 101",
        " tagged ethe 1/1/1 to 2/1/3",
        " vlan 101 name USERS by port",
    )


def test_single_port_change_only_touches_that_port() -> None:
    running_config = _load(
        ("vlan 101 name USERS by port", " tagged ethe 1/1/1 to 1/1/4"),
    )
    generated_config = _load(
        ("vlan 101 name USERS by port", " tagged ethe 1/1/1 to 1/1/3"),
    )
    remediation = running_config.config_to_get_to(generated_config)
    assert remediation.dump_simple() == ("vlan 101", " no tagged ethe 1/1/4")


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    (
        pytest.param(
            "vlan 20 by port",
            "vlan 20 name USERS by port",
            " vlan 20 name USERS by port",
            id="naming-an-unnamed-vlan",
        ),
        pytest.param(
            "vlan 20 name USERS by port",
            "vlan 20 by port",
            " vlan 20 by port",
            id="removing-a-vlan-name",
        ),
        pytest.param(
            "vlan 20 name OLD by port",
            "vlan 20 name NEW by port",
            " vlan 20 name NEW by port",
            id="renaming-a-vlan",
        ),
    ),
)
def test_vlan_header_changes_never_negate_the_vlan(
    before: str,
    after: str,
    expected: str,
) -> None:
    """Changing a VLAN header must not emit a negation of the old header.

    FastIron renders an unnamed VLAN as `vlan 20 by port`, which normalises to
    a child alongside the named form. Both are global commands, so negating
    either one (`no vlan 20 by port`) deletes the VLAN and every port in it,
    and the membership lines are not re-added because they did not change.
    """
    running_config = _load((before, " tagged ethe 1/1/1 to 1/1/2"))
    generated_config = _load((after, " tagged ethe 1/1/1 to 1/1/2"))
    remediation = running_config.config_to_get_to(generated_config)
    assert remediation.dump_simple() == ("vlan 20", expected)
    _assert_rollback_restores(running_config, remediation)


def test_vlan_negation_drops_the_inline_name() -> None:
    running_config = _load(("vlan 101 name USERS by port", " tagged ethe 1/1/1"))
    generated_config = _load(("hostname SW01",))
    remediation = running_config.config_to_get_to(generated_config)
    assert "no vlan 101" in remediation.dump_simple()
    assert "no vlan 101 name USERS by port" not in remediation.dump_simple()


def test_vlan_rename_does_not_delete_the_vlan() -> None:
    """A rename must be one line, not a delete plus a re-create.

    The header is normalised to `vlan 101` at load time so the section identity
    survives a rename; the name itself rides as a child. `by port` is accepted
    on input as well as emitted by the device, so the line can be replayed
    exactly as it was read.
    """
    running_config = _load(("vlan 101 name OLD by port", " tagged ethe 1/1/1"))
    generated_config = _load(("vlan 101 name NEW by port", " tagged ethe 1/1/1"))
    remediation = running_config.config_to_get_to(generated_config)
    assert remediation.dump_simple() == ("vlan 101", " vlan 101 name NEW by port")
    _assert_rollback_restores(running_config, remediation)


def test_lag_negation_drops_the_static_id() -> None:
    running_config = _load(
        ('lag "CORE_UPLINK" static id 10', " ports ethernet 1/1/31", " deploy"),
    )
    generated_config = _load(("hostname SW01",))
    remediation = running_config.config_to_get_to(generated_config)
    assert 'no lag "CORE_UPLINK"' in remediation.dump_simple()


def test_lag_member_description_is_idempotent() -> None:
    running_config = _load(
        ('lag "CORE_UPLINK" static id 10', " port-name OLD ethernet 1/1/31"),
    )
    generated_config = _load(
        ('lag "CORE_UPLINK" static id 10', " port-name NEW ethernet 1/1/31"),
    )
    remediation = running_config.config_to_get_to(generated_config)
    assert remediation.dump_simple() == (
        'lag "CORE_UPLINK" static id 10',
        " port-name NEW ethernet 1/1/31",
    )


def test_ip_addresses_are_diffed_one_line_at_a_time() -> None:
    """`ip address` adds an address on FastIron, it does not replace one.

    Verified on an ICX 6650: issuing a second address in another subnet leaves
    both on the interface. Treating the command as idempotent would make a
    remediation that removes an address come out empty.
    """
    running_config = _load(
        (
            "interface ve 106",
            " ip address 10.0.0.1 255.255.255.0",
            " ip address 10.0.1.1 255.255.255.0",
        ),
    )
    generated_config = _load(
        ("interface ve 106", " ip address 10.0.0.1 255.255.255.0"),
    )
    remediation = running_config.config_to_get_to(generated_config)
    assert remediation.dump_simple() == (
        "interface ve 106",
        " no ip address 10.0.1.1 255.255.255.0",
    )
    _assert_rollback_restores(running_config, remediation)


def test_changing_an_ip_address_removes_the_old_one() -> None:
    running_config = _load(
        ("interface ve 106", " ip address 10.0.0.1 255.255.255.0"),
    )
    generated_config = _load(
        ("interface ve 106", " ip address 10.0.1.1 255.255.255.0"),
    )
    remediation = running_config.config_to_get_to(generated_config)
    assert remediation.dump_simple() == (
        "interface ve 106",
        " no ip address 10.0.0.1 255.255.255.0",
        " ip address 10.0.1.1 255.255.255.0",
    )
    _assert_rollback_restores(running_config, remediation)


def test_port_name_is_idempotent() -> None:
    running_config = _load(("interface ethernet 1/1/1", " port-name OLD"))
    generated_config = _load(("interface ethernet 1/1/1", " port-name NEW"))
    remediation = running_config.config_to_get_to(generated_config)
    assert remediation.dump_simple() == (
        "interface ethernet 1/1/1",
        " port-name NEW",
    )


def test_port_name_negation_takes_no_argument() -> None:
    running_config = _load(("interface ethernet 1/1/1", " port-name OLD"))
    generated_config = _load(("interface ethernet 1/1/1", " loop-detection"))
    remediation = running_config.config_to_get_to(generated_config)
    assert " no port-name" in remediation.dump_simple()


def test_dual_mode_change_negates_with_the_old_vlan() -> None:
    running_config = _load(("interface ethernet 1/1/1", " dual-mode 101"))
    generated_config = _load(("interface ethernet 1/1/1", " dual-mode 102"))
    remediation = running_config.config_to_get_to(generated_config)
    assert remediation.dump_simple() == (
        "interface ethernet 1/1/1",
        " no dual-mode 101",
        " dual-mode 102",
    )


def test_untagged_port_move_removes_before_it_adds() -> None:
    running_config = _load(
        (
            "vlan 101 name OLD by port",
            " untagged ethe 1/1/1",
            "vlan 102 name NEW by port",
        ),
    )
    generated_config = _load(
        (
            "vlan 101 name OLD by port",
            "vlan 102 name NEW by port",
            " untagged ethe 1/1/1",
        ),
    )
    lines = _ordered_remediation(running_config, generated_config)
    assert lines.index(" no untagged ethe 1/1/1") < lines.index(" untagged ethe 1/1/1")


def test_interface_reset_runs_before_the_port_is_repopulated() -> None:
    """`no interface ethernet ...` clears the block, it does not delete a port.

    VLAN membership survives the reset because it lives in the `vlan` blocks,
    but every interface-level setting is lost, so the reset has to precede
    anything that puts configuration back on the port.
    """
    running_config = _load(
        (
            "vlan 101 name USERS by port",
            " untagged ethe 1/1/1",
            "interface ethernet 1/1/2",
            " port-name OLD",
        ),
    )
    generated_config = _load(
        (
            "vlan 101 name USERS by port",
            " untagged ethe 1/1/1",
            " untagged ethe 1/1/2",
        ),
    )
    lines = _ordered_remediation(running_config, generated_config)
    assert lines.index("no interface ethernet 1/1/2") < lines.index(
        " untagged ethe 1/1/2",
    )


@pytest.mark.parametrize(
    "generated_lines",
    (
        pytest.param(
            (
                "interface ethernet 1/1/11",
                " mac filter-group 20",
                "mac filter 20 permit bbbb.bbbb.bbbb 0000.0000.0000 any",
            ),
            id="binding-declared-first",
        ),
        pytest.param(
            (
                "mac filter 20 permit bbbb.bbbb.bbbb 0000.0000.0000 any",
                "interface ethernet 1/1/11",
                " mac filter-group 20",
            ),
            id="filter-declared-first",
        ),
    ),
)
def test_a_new_mac_filter_exists_before_an_interface_binds_it(
    generated_lines: tuple[str, ...],
) -> None:
    """The filter has to be created before an interface names it.

    Verified on an ICX 6650: `mac filter-group 32` against an undefined filter
    is refused with "filter 32 is not configured in the global table", so the
    order cannot be left to ride on whichever line the intended config happens
    to declare first.
    """
    running_config = _load(("interface ethernet 1/1/11",))
    generated_config = _load(generated_lines)
    lines = _ordered_remediation(running_config, generated_config)
    assert lines.index(
        "mac filter 20 permit bbbb.bbbb.bbbb 0000.0000.0000 any",
    ) < lines.index(" mac filter-group 20")


def test_mac_filter_is_unbound_before_it_is_removed() -> None:
    running_config = _load(
        (
            "mac filter 10 permit aaaa.aaaa.aaaa 0000.0000.0000 any",
            "interface ethernet 1/1/11",
            " mac filter-group 10",
        ),
    )
    generated_config = _load(("interface ethernet 1/1/11",))
    lines = _ordered_remediation(running_config, generated_config)
    assert lines.index(" no mac filter-group 10") < lines.index(
        "no mac filter 10 permit aaaa.aaaa.aaaa 0000.0000.0000 any",
    )


def test_a_new_acl_exists_before_an_interface_binds_it() -> None:
    """An interface fails open while the ACL it names does not exist.

    Creating the ACL after the binding would leave the interface unfiltered for
    the rest of the push, which is exactly what the binding was added to
    prevent.
    """
    running_config = _load(("interface ve 106", " ip address 10.0.0.1/24"))
    generated_config = _load(
        (
            "ip access-list extended NEW",
            " permit ip host 1.1.1.1 any",
            "interface ve 106",
            " ip address 10.0.0.1/24",
            " ip access-group NEW in",
        ),
    )
    lines = _ordered_remediation(running_config, generated_config)
    assert lines.index("ip access-list extended NEW") < lines.index(
        " ip access-group NEW in",
    )


def test_a_deleted_acl_is_removed_before_the_interface_unbinds_it() -> None:
    """The documented trade-off of ordering ACLs ahead of interfaces.

    Unlike `mac filter`, FastIron does not refuse to delete a bound ACL, so the
    binding is left dangling for the rest of the push and then removed. The end
    state is the same either way, which is why this loses to keeping a newly
    created ACL ahead of its binding.
    """
    running_config = _load(
        (
            "ip access-list extended TEST-EXT",
            " permit ip host 1.1.1.1 any log",
            "interface ve 106",
            " ip access-group TEST-EXT in",
        ),
    )
    generated_config = _load(("interface ve 106",))
    lines = _ordered_remediation(running_config, generated_config)
    assert lines.index("no ip access-list extended TEST-EXT") < lines.index(
        " no ip access-group TEST-EXT in",
    )


def test_changed_acl_is_rebuilt_rather_than_appended_to() -> None:
    running_config = _load(
        (
            "ip access-list extended TEST-EXT",
            " permit ip host 1.1.1.1 any log",
            " permit ip host 3.3.3.3 any log",
        ),
    )
    generated_config = _load(
        (
            "ip access-list extended TEST-EXT",
            " permit ip host 1.1.1.1 any log",
            " permit ip host 2.2.2.2 any log",
            " permit ip host 3.3.3.3 any log",
        ),
    )
    remediation = running_config.config_to_get_to(generated_config)
    lines = remediation.dump_simple()
    assert lines[0] == "no ip access-list extended TEST-EXT"
    assert lines[1:] == (
        "ip access-list extended TEST-EXT",
        " permit ip host 1.1.1.1 any log",
        " permit ip host 2.2.2.2 any log",
        " permit ip host 3.3.3.3 any log",
    )
    _assert_rollback_restores(running_config, remediation)


def test_lag_member_list_is_expanded_per_port() -> None:
    config = get_hconfig(
        Platform.RUCKUS_FASTIRON,
        'lag "TEST" static id 100\n ports ethernet 1/1/12 to 1/1/14\n'
        " primary-port 1/1/12\n deploy\n",
    )
    assert config.dump_simple() == (
        'lag "TEST" static id 100',
        " primary-port 1/1/12",
        " deploy",
        " ports ethernet 1/1/12",
        " ports ethernet 1/1/13",
        " ports ethernet 1/1/14",
    )


def test_adding_a_lag_member_does_not_rewrite_the_member_list() -> None:
    running_config = _load(
        ('lag "TEST" static id 100', " ports ethernet 1/1/12", " deploy"),
    )
    generated_config = _load(
        (
            'lag "TEST" static id 100',
            " ports ethernet 1/1/12 to 1/1/13",
            " deploy",
        ),
    )
    remediation = running_config.config_to_get_to(generated_config)
    assert remediation.dump_simple() == (
        'lag "TEST" static id 100',
        " ports ethernet 1/1/13",
    )


def test_lag_primary_moves_before_the_old_member_is_dropped() -> None:
    """A deployed LAG refuses to delete its primary port, so demote it first."""
    running_config = _load(
        (
            'lag "TEST" static id 100',
            " ports ethernet 1/1/11 to 1/1/12",
            " primary-port 1/1/11",
        ),
    )
    generated_config = _load(
        (
            'lag "TEST" static id 100',
            " ports ethernet 1/1/12",
            " primary-port 1/1/12",
        ),
    )
    lines = _ordered_remediation(running_config, generated_config)
    assert lines.index(" primary-port 1/1/12") < lines.index(
        " no ports ethernet 1/1/11",
    )


def test_lag_undeploy_wraps_the_rest_of_the_section() -> None:
    """A deployed LAG rejects membership and primary-port changes.

    When an un-deploy/re-deploy pair is present in the delta it has to bracket
    everything else in the section.
    """
    running_config = _load(
        (
            'lag "TEST" static id 100',
            " ports ethernet 1/1/11",
            " primary-port 1/1/11",
            " deploy",
        ),
    )
    generated_config = _load(
        (
            'lag "TEST" static id 100',
            " ports ethernet 1/1/12",
            " primary-port 1/1/12",
        ),
    )
    lines = _ordered_remediation(running_config, generated_config)
    assert lines.index(" no deploy") < lines.index(" primary-port 1/1/12")
    assert lines.index(" no deploy") < lines.index(" no ports ethernet 1/1/11")


def test_acl_rebuild_negates_before_it_re_creates() -> None:
    """Regression: the ACL body must never outrank its own negation.

    `no ip access-list ...` runs earliest of all the ordering weights, so that
    a deletion clears the way before anything else. The same line is what a
    sectional overwrite emits, so the re-created body has to stay just behind
    it; if the body sorted first, applying the remediation would delete the ACL
    instead of rebuilding it.
    """
    running_config = _load(
        ("ip access-list extended TEST-EXT", " permit ip host 1.1.1.1 any log"),
    )
    generated_config = _load(
        (
            "ip access-list extended TEST-EXT",
            " permit ip host 1.1.1.1 any log",
            " permit ip host 2.2.2.2 any log",
        ),
    )
    lines = _ordered_remediation(running_config, generated_config)
    assert lines.index("no ip access-list extended TEST-EXT") < lines.index(
        "ip access-list extended TEST-EXT",
    )
    assert lines[-1] == " permit ip host 2.2.2.2 any log"


def test_round_trip_against_real_configs(
    running_config_fastiron: str,
    generated_config_fastiron: str,
) -> None:
    """Round trip over a stacked ICX 6450 pair running the L2 (`S`) image."""
    running_config = get_hconfig(Platform.RUCKUS_FASTIRON, running_config_fastiron)
    generated_config = get_hconfig(Platform.RUCKUS_FASTIRON, generated_config_fastiron)

    remediation = running_config.config_to_get_to(generated_config)
    assert remediation.dump_simple()

    running_after = running_config.future(remediation)
    rollback = running_after.config_to_get_to(running_config)
    running_after_rollback = running_after.future(rollback)
    assert not tuple(running_config.unified_diff(running_after_rollback))


def test_round_trip_against_real_l3_configs(
    running_config_fastiron_l3: str,
    generated_config_fastiron_l3: str,
) -> None:
    """Round trip over an ICX 6650 pair running the L3 (`R`) image.

    Covers the constructs the 6450 fixtures do not have at all: `lag`,
    `interface ve` with `router-interface` and `ip helper-address`, and static
    routing.
    """
    running_config = get_hconfig(Platform.RUCKUS_FASTIRON, running_config_fastiron_l3)
    generated_config = get_hconfig(
        Platform.RUCKUS_FASTIRON,
        generated_config_fastiron_l3,
    )
    assert running_config.get_child(startswith="lag ")
    assert tuple(running_config.get_children(startswith="interface ve "))

    remediation = running_config.config_to_get_to(generated_config)
    assert remediation.dump_simple()

    running_after = running_config.future(remediation)
    rollback = running_after.config_to_get_to(running_config)
    running_after_rollback = running_after.future(rollback)
    assert not tuple(running_config.unified_diff(running_after_rollback))


@pytest.mark.parametrize(
    ("words", "expected_message"),
    (
        pytest.param(
            ("ethe", "1/1/1", "to", "1/2/3"),
            "spans multiple slots",
            id="range-spans-two-slots",
        ),
        pytest.param(
            ("ethe", "1/1", "to", "1/1/3"),
            "unsupported port range",
            id="ends-shaped-differently",
        ),
        pytest.param(
            ("ethe", "1/1/1/1", "to", "1/1/1/3"),
            "unsupported port range",
            id="too-many-fields",
        ),
        pytest.param(
            ("ethe", "1/1/8", "to", "1/1/2"),
            "reversed port range",
            id="range-runs-backwards",
        ),
        pytest.param(
            ("1/1/1",),
            "unexpected token",
            id="no-port-keyword",
        ),
        pytest.param(
            ("ethe", "1/1/1", "ethe"),
            "ended after a port keyword",
            id="keyword-with-nothing-after",
        ),
        pytest.param(
            ("ethe", "1/1/1", "to"),
            "ended after 'to'",
            id="nothing-after-to",
        ),
        pytest.param((), "empty port specification", id="empty"),
    ),
)
def test_malformed_port_specifications_are_rejected(
    words: tuple[str, ...],
    expected_message: str,
) -> None:
    """Every failure mode must raise, and raise for the reason it was given.

    Callers treat the exception as "leave this line alone", so a specification
    that cannot be enumerated exactly has to fail loudly here. Matching the
    message keeps each case pinned to its own branch, so one branch raising
    another's error would not pass unnoticed.
    """
    with pytest.raises(ValueError, match=re.escape(expected_message)):
        fastiron_expand_ports(words)


@pytest.mark.parametrize(
    ("words", "expected"),
    (
        (("ethe", "1/1/1"), ("1/1/1",)),
        (("ethernet", "1/1/1"), ("1/1/1",)),
        (("ethe", "1/1/1", "to", "1/1/3"), ("1/1/1", "1/1/2", "1/1/3")),
        (("ethe", "1/1/1", "to", "1/1/1"), ("1/1/1",)),
        (("ethe", "1/1/1", "ethe", "1/1/1"), ("1/1/1",)),
        (
            ("ethe", "1/1/1", "to", "1/1/2", "ethe", "1/2/4"),
            ("1/1/1", "1/1/2", "1/2/4"),
        ),
        (
            ("ethe", "1/2/4", "ethe", "1/1/1", "to", "1/1/2"),
            ("1/2/4", "1/1/1", "1/1/2"),
        ),
    ),
)
def test_well_formed_port_specifications_are_expanded(
    words: tuple[str, ...],
    expected: tuple[str, ...],
) -> None:
    """Expansion must reproduce the exact port list, in order and without gaps.

    A VLAN or LAG member list is rewritten from this output, so a range that
    expands to the wrong length silently adds or drops members.
    """
    assert fastiron_expand_ports(words) == expected


def test_two_field_port_ids_are_supported() -> None:
    """Non-stacked units address ports as `slot/port` rather than `unit/slot/port`."""
    assert fastiron_expand_ports(("ethe", "1/1", "to", "1/3")) == ("1/1", "1/2", "1/3")


def test_unparsable_lag_member_line_is_left_alone() -> None:
    """A LAG member list that cannot be enumerated keeps its original line.

    Rewriting a member list we do not fully understand risks dropping members
    from a live aggregation, so the driver leaves it for a human.
    """
    config = get_hconfig(
        Platform.RUCKUS_FASTIRON,
        'lag "TEST" static id 100\n ports ethernet 1/1/11 to 2/1/12\n deploy\n',
    )
    assert config.dump_simple() == (
        'lag "TEST" static id 100',
        " ports ethernet 1/1/11 to 2/1/12",
        " deploy",
    )


def test_acl_and_mac_filter_ordering_compose() -> None:
    """The ACL and mac-filter weights must not interfere with each other.

    They pull in opposite directions -- ACLs run ahead of the interfaces that
    bind them, mac filters behind -- so a remediation touching both at once is
    where a weight collision would surface.
    """
    running_config = _load(
        (
            "ip access-list extended OLD",
            " permit ip host 1.1.1.1 any",
            "mac filter 10 permit aaaa.aaaa.aaaa 0000.0000.0000 any",
            "interface ve 106",
            " ip access-group OLD in",
            "interface ethernet 1/1/11",
            " mac filter-group 10",
        ),
    )
    generated_config = _load(
        (
            "ip access-list extended NEW",
            " permit ip host 2.2.2.2 any",
            "interface ve 106",
            " ip access-group NEW in",
            "interface ethernet 1/1/11",
        ),
    )
    lines = _ordered_remediation(running_config, generated_config)

    assert lines.index("no ip access-list extended OLD") < lines.index(
        "ip access-list extended NEW",
    )
    assert lines.index("ip access-list extended NEW") < lines.index(
        " ip access-group NEW in",
    )
    assert lines.index(" no mac filter-group 10") < lines.index(
        "no mac filter 10 permit aaaa.aaaa.aaaa 0000.0000.0000 any",
    )
    _assert_rollback_restores(
        running_config,
        running_config.config_to_get_to(generated_config),
    )
