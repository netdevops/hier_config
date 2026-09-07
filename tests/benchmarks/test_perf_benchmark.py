"""Committed pytest-benchmark suite for Phase 0 baseline recording."""

# ruff: file-ignore[any-type]
# pylint: disable=redefined-outer-name

# The suite deliberately imports a private generator from the sibling
# benchmark module rather than duplicating it.
# pyright: reportPrivateUsage=false

from __future__ import annotations

from typing import Any

import pytest

from hier_config import get_hconfig
from hier_config.models import Platform
from tests.test_benchmarks import _generate_large_ios_config

pytestmark = pytest.mark.benchmark


@pytest.fixture(scope="session")
def ios_config_1k() -> str:
    # ~100 interfaces -> ~1k lines
    return _generate_large_ios_config(num_interfaces=120)


@pytest.fixture(scope="session")
def ios_config_10k() -> str:
    # ~1000 interfaces -> ~10k lines
    return _generate_large_ios_config(num_interfaces=1200)


@pytest.fixture(scope="session")
def ios_config_50k() -> str:
    # ~6000 interfaces -> ~50k lines
    return _generate_large_ios_config(num_interfaces=6000)


def test_benchmark_parse_ios_1k(benchmark: Any, ios_config_1k: str) -> None:
    result = benchmark(get_hconfig, Platform.CISCO_IOS, ios_config_1k)
    assert len(result) > 0


def test_benchmark_parse_ios_10k(benchmark: Any, ios_config_10k: str) -> None:
    result = benchmark(get_hconfig, Platform.CISCO_IOS, ios_config_10k)
    assert len(result) > 0


def test_benchmark_parse_ios_50k(benchmark: Any, ios_config_50k: str) -> None:
    result = benchmark.pedantic(
        get_hconfig,
        args=(Platform.CISCO_IOS, ios_config_50k),
        rounds=5,
        iterations=1,
    )
    assert len(result) > 0


def test_benchmark_remediation_10k(benchmark: Any, ios_config_10k: str) -> None:
    running = get_hconfig(Platform.CISCO_IOS, ios_config_10k)
    generated_text = ios_config_10k.replace(
        " ip ospf cost 100", " ip ospf cost 200", 100
    )
    generated = get_hconfig(Platform.CISCO_IOS, generated_text)

    remediation = benchmark(running.config_to_get_to, generated)
    assert len(remediation) > 0


def test_benchmark_remediation_50k(benchmark: Any, ios_config_50k: str) -> None:
    running = get_hconfig(Platform.CISCO_IOS, ios_config_50k)
    generated_text = ios_config_50k.replace(
        " ip ospf cost 100", " ip ospf cost 200", 200
    )
    generated = get_hconfig(Platform.CISCO_IOS, generated_text)

    remediation = benchmark.pedantic(
        running.config_to_get_to,
        args=(generated,),
        rounds=5,
        iterations=1,
    )
    assert len(remediation) > 0


def test_benchmark_iteration_10k(benchmark: Any, ios_config_10k: str) -> None:
    config = get_hconfig(Platform.CISCO_IOS, ios_config_10k)
    nodes = benchmark(lambda: list(config.all_children_sorted()))
    assert len(nodes) > 0
