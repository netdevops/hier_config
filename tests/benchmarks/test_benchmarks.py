"""Performance benchmarks for hier_config.

These tests are skipped by default. Run with:
    poetry run pytest -m benchmark -v
"""

import time
from collections.abc import Callable

import pytest

from hier_config import get_hconfig, get_hconfig_fast_load
from hier_config.models import Platform

pytestmark = pytest.mark.benchmark


def _generate_large_ios_config(num_interfaces: int = 1000) -> str:
    """Generate a large Cisco IOS-style config (~10k+ lines at default)."""
    lines = [
        "hostname LARGE-ROUTER",
        "!",
        "ip name-server 8.8.8.8",
        "ip name-server 8.8.4.4",
        "!",
        "aaa new-model",
        "aaa authentication login default local",
        "aaa authorization exec default local",
        "!",
        "ip access-list extended MGMT_ACL",
        " 10 permit tcp 10.0.0.0 0.255.255.255 any eq 22",
        " 20 permit tcp 172.16.0.0 0.15.255.255 any eq 22",
        " 30 deny ip any any log",
        "!",
        "ip prefix-list DEFAULT_ONLY seq 10 permit 0.0.0.0/0",
        "!",
    ]
    for i in range(num_interfaces):
        lines.extend(
            [
                f"interface GigabitEthernet0/{i}",
                f" description Link to device {i}",
                f" ip address 10.{i // 256}.{i % 256}.1 255.255.255.252",
                " ip ospf cost 100",
                " ip ospf network point-to-point",
                " no shutdown",
                "!",
            ]
        )
    lines.extend(
        [
            "router ospf 1",
            " router-id 10.0.0.1",
            " auto-cost reference-bandwidth 100000",
        ]
    )
    lines.extend(
        f" network 10.{i // 256}.{i % 256}.0 0.0.0.3 area 0"
        for i in range(num_interfaces)
    )
    lines.extend(
        [
            "!",
            "router bgp 65000",
            " bgp router-id 10.0.0.1",
            " bgp log-neighbor-changes",
        ]
    )
    for i in range(min(num_interfaces, 200)):
        lines.extend(
            [
                f" neighbor 10.{i // 256}.{i % 256}.2 remote-as 6500{i}",
                f" neighbor 10.{i // 256}.{i % 256}.2 description Peer-{i}",
            ]
        )
    lines.extend(
        [
            "!",
            "line con 0",
            " exec-timeout 5 0",
            " logging synchronous",
            "line vty 0 4",
            " access-class MGMT_ACL in",
            " transport input ssh",
            "!",
        ]
    )
    return "\n".join(lines)


def _generate_large_xr_config(num_interfaces: int = 1000) -> str:
    """Generate a large Cisco IOS-XR-style config (~10k+ lines at default)."""
    lines = [
        "hostname LARGE-XR-ROUTER",
        "logging console informational",
        "logging source-interface Loopback0",
    ]
    for i in range(num_interfaces):
        lines.extend(
            [
                f"interface GigabitEthernet0/0/0/{i}",
                f" description Link to device {i}",
                f" ipv4 address 10.{i // 256}.{i % 256}.1 255.255.255.252",
                " mtu 9000",
                " load-interval 30",
                "!",
            ]
        )
    lines.extend(
        [
            "router bgp 65000",
            " bgp router-id 10.0.0.1",
        ]
    )
    for i in range(num_interfaces):
        lines.extend(
            [
                f" neighbor 10.{i // 256}.{i % 256}.2",
                f"  remote-as 6500{i}",
                f"  description Peer {i}",
            ]
        )
    lines.extend(
        [
            "!",
            "router ospf 1",
            " router-id 10.0.0.1",
        ]
    )
    lines.extend(
        f" area 0 interface GigabitEthernet0/0/0/{i} cost 100"
        for i in range(num_interfaces)
    )
    lines.append("!")
    return "\n".join(lines)


def _time_fn(fn: Callable[[], object], iterations: int = 3) -> float:
    """Return the best elapsed time in seconds over multiple iterations."""
    best = float("inf")
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        elapsed = time.perf_counter() - start
        best = min(best, elapsed)
    return best


class TestParsingBenchmarks:
    """Benchmarks for config parsing."""

    @staticmethod
    def test_parse_large_ios_config() -> None:
        """Parse a ~10k line IOS config via get_hconfig."""
        config_text = _generate_large_ios_config()
        elapsed = _time_fn(lambda: get_hconfig(Platform.CISCO_IOS, config_text))
        line_count = config_text.count("\n")
        print(f"\nget_hconfig: {line_count} lines in {elapsed:.4f}s")  # noqa: T201
        assert elapsed < 5.0, f"Parsing took {elapsed:.2f}s, expected < 5s"

    @staticmethod
    def test_parse_large_xr_config() -> None:
        """Parse a ~10k line XR config via get_hconfig."""
        config_text = _generate_large_xr_config()
        elapsed = _time_fn(lambda: get_hconfig(Platform.CISCO_XR, config_text))
        line_count = config_text.count("\n")
        print(f"\nget_hconfig (XR): {line_count} lines in {elapsed:.4f}s")  # noqa: T201
        assert elapsed < 5.0, f"Parsing took {elapsed:.2f}s, expected < 5s"

    @staticmethod
    def test_fast_load_large_ios_config() -> None:
        """Parse a ~10k line IOS config via get_hconfig_fast_load."""
        config_text = _generate_large_ios_config()
        config_lines = tuple(config_text.splitlines())
        elapsed = _time_fn(
            lambda: get_hconfig_fast_load(Platform.CISCO_IOS, config_lines),
        )
        print(f"\nget_hconfig_fast_load: {len(config_lines)} lines in {elapsed:.4f}s")  # noqa: T201
        assert elapsed < 5.0, f"Fast load took {elapsed:.2f}s, expected < 5s"

    @staticmethod
    def test_fast_load_vs_get_hconfig() -> None:
        """get_hconfig_fast_load should be faster than get_hconfig."""
        config_text = _generate_large_ios_config()
        config_lines = tuple(config_text.splitlines())

        time_full = _time_fn(lambda: get_hconfig(Platform.CISCO_IOS, config_text))
        time_fast = _time_fn(
            lambda: get_hconfig_fast_load(Platform.CISCO_IOS, config_lines),
        )
        ratio = time_full / time_fast if time_fast > 0 else float("inf")
        print(  # noqa: T201
            f"\nget_hconfig: {time_full:.4f}s, "
            f"fast_load: {time_fast:.4f}s, "
            f"ratio: {ratio:.1f}x"
        )
        # fast_load should not be significantly slower (allow 10% variance for CI noise)
        assert time_fast <= time_full * 1.1, (
            "fast_load should not be slower than get_hconfig"
        )


class TestRemediationBenchmarks:
    """Benchmarks for config_to_get_to remediation."""

    @staticmethod
    def test_remediation_small_diff() -> None:
        """Remediation with ~5% of interfaces changed."""
        running_text = _generate_large_ios_config()
        running = get_hconfig(Platform.CISCO_IOS, running_text)

        # Modify 50 interfaces in generated config
        generated_text = running_text.replace(
            " ip ospf cost 100", " ip ospf cost 200", 50
        )
        generated = get_hconfig(Platform.CISCO_IOS, generated_text)

        elapsed = _time_fn(lambda: running.config_to_get_to(generated))
        print(f"\nRemediation (10% diff): {elapsed:.4f}s")  # noqa: T201
        assert elapsed < 5.0, f"Remediation took {elapsed:.2f}s, expected < 5s"

    @staticmethod
    def test_remediation_large_diff() -> None:
        """Remediation with ~100% of interfaces changed."""
        running = get_hconfig(Platform.CISCO_IOS, _generate_large_ios_config())
        generated_text = _generate_large_ios_config().replace(
            " ip ospf cost 100", " ip ospf cost 200"
        )
        generated = get_hconfig(Platform.CISCO_IOS, generated_text)

        elapsed = _time_fn(lambda: running.config_to_get_to(generated))
        print(f"\nRemediation (100% diff): {elapsed:.4f}s")  # noqa: T201
        assert elapsed < 10.0, f"Remediation took {elapsed:.2f}s, expected < 10s"

    @staticmethod
    def test_remediation_completely_different() -> None:
        """Remediation between two entirely different configs."""
        running = get_hconfig(Platform.CISCO_IOS, _generate_large_ios_config(500))
        # Generate a completely different config
        lines = ["hostname OTHER-ROUTER"]
        for i in range(500):
            lines.extend(
                [
                    f"interface Loopback{i}",
                    f" description Loopback {i}",
                    f" ip address 192.168.{i // 256}.{i % 256} 255.255.255.255",
                ]
            )
        generated = get_hconfig(Platform.CISCO_IOS, "\n".join(lines))

        elapsed = _time_fn(lambda: running.config_to_get_to(generated))
        print(f"\nRemediation (completely different): {elapsed:.4f}s")  # noqa: T201
        assert elapsed < 10.0, f"Remediation took {elapsed:.2f}s, expected < 10s"


class TestIterationBenchmarks:
    """Benchmarks for tree traversal and iteration."""

    @staticmethod
    def test_all_children_sorted() -> None:
        """Iterate all_children_sorted on a large config."""
        config = get_hconfig(Platform.CISCO_IOS, _generate_large_ios_config())

        elapsed = _time_fn(lambda: list(config.all_children_sorted()))
        child_count = len(list(config.all_children()))
        print(f"\nall_children_sorted: {child_count} nodes in {elapsed:.4f}s")  # noqa: T201
        assert elapsed < 2.0, f"Iteration took {elapsed:.2f}s, expected < 2s"

    @staticmethod
    def test_dump_simple() -> None:
        """Dump a large config to simple text."""
        config = get_hconfig(Platform.CISCO_IOS, _generate_large_ios_config())

        elapsed = _time_fn(config.dump_simple)
        line_count = len(config.dump_simple())
        print(f"\ndump_simple: {line_count} lines in {elapsed:.4f}s")  # noqa: T201
        assert elapsed < 2.0, f"dump_simple took {elapsed:.2f}s, expected < 2s"

    @staticmethod
    def test_deep_copy() -> None:
        """Deep copy a large config tree."""
        config = get_hconfig(Platform.CISCO_IOS, _generate_large_ios_config())

        elapsed = _time_fn(config.deep_copy)
        print(f"\ndeep_copy: {elapsed:.4f}s")  # noqa: T201
        assert elapsed < 5.0, f"deep_copy took {elapsed:.2f}s, expected < 5s"
