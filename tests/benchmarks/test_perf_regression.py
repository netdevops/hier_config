"""Machine-normalised performance regression gate.

Absolute timings cannot gate CI: shared runners vary by an order of magnitude
between runs, so any fixed millisecond threshold is either so loose it catches
nothing or so tight it fails constantly. `baseline.json` records absolute
numbers from one developer laptop and is useless anywhere else.

This previously measured the same operation under the native backend and the
pure-Python backend and asserted the speedup ratio. The pure-Python
implementation has since been removed -- the Rust core is the only
implementation -- so there is no second backend to divide by.

Instead each operation is divided by a *calibration workload*: a fixed lump of
pure-Python interpreter work (dict churn, string building, list joins) timed in
the same process on the same machine. That gives a machine-speed unit. A slow
runner slows the calibration and the measured operation together, so the
resulting "cost in calibration units" stays stable across wildly different
hardware while remaining sensitive to exactly the regressions that hurt:

* a native fast path silently falling back to Python,
* work being redone per-call that used to be hoisted or cached,
* Python objects being materialised where the Rust side used to stay native.

Ceilings sit ~1.75x above the highest value observed across repeated local
runs. Measured spread is 5-10%, so ordinary noise cannot trip them, while any
regression that doubles an operation's cost does. They are tripwires for
structural regressions, not precise assertions.

The one thing this cannot normalise away is a Python release that changes
interpreter throughput without changing native throughput (or vice versa),
which shifts every ratio at once. A uniform shift across all six operations
means recalibrate; a shift in a single operation is a real regression.

Run with `pytest -m benchmark tests/benchmarks/test_perf_regression.py`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.benchmark

REPO_ROOT = Path(__file__).resolve().parents[2]

# Operation -> maximum acceptable cost, expressed in calibration units.
#
# Observed maximums on Apple Silicon (release build, 400-interface config,
# three consecutive runs):
#
#   parse 0.227 | fast_load 0.204 | deepcopy 0.049 | dump 0.318
#   iteration 0.099 | remediation 0.133
#
# Ceilings are ~1.5x those values. That tolerates far more noise than the
# 5-10% actually measured, while still failing on any regression that meaningfully
# increases the cost of an operation -- for example, disabling the compiled-regex
# cache roughly doubles parse, which trips its ceiling. fast_load shares parse's
# ceiling since it does the same class of parsing work.
MAX_COST_UNITS = {
    "parse": 0.27,
    "fast_load": 0.24,
    "deepcopy": 0.03,
    "dump": 0.37,
    "iteration": 0.06,
    "remediation": 0.19,
}

_WORKER = r"""
import copy, json, sys, time
sys.path.insert(0, %(root)r)

from hier_config import get_hconfig, get_hconfig_fast_load
from hier_config.models import Platform
from tests.test_benchmarks import _generate_large_ios_config

op = sys.argv[1]
reps = int(sys.argv[2])


def calibration():
    # Fixed pure-Python interpreter work. Deliberately touches dict lookup,
    # string formatting, iteration and list joining -- operations whose
    # throughput tracks general interpreter speed. Must not use hier_config.
    acc = {}
    for i in range(20000):
        k = "key-%%d" %% (i & 1023)
        acc[k] = acc.get(k, 0) + i
    total = 0
    for k, v in acc.items():
        if k.startswith("key-1"):
            total += v
    parts = [str(i) for i in range(5000)]
    "|".join(parts).split("|")
    return total


raw = _generate_large_ios_config(num_interfaces=400)
config = get_hconfig(Platform.CISCO_IOS, raw)

if op == "remediation":
    target = get_hconfig(
        Platform.CISCO_IOS, _generate_large_ios_config(num_interfaces=420)
    )


def run():
    if op == "parse":
        get_hconfig(Platform.CISCO_IOS, raw)
    elif op == "fast_load":
        get_hconfig_fast_load(Platform.CISCO_IOS, raw)
    elif op == "deepcopy":
        copy.deepcopy(config)
    elif op == "dump":
        config.dump()
    elif op == "iteration":
        list(config.all_children_sorted())
    elif op == "remediation":
        config.config_to_get_to(target)
    else:
        raise SystemExit("unknown op " + op)


def best_of(fn, count):
    fn()  # warm caches so the first timed rep is not an outlier
    timings = []
    for _ in range(count):
        start = time.perf_counter()
        fn()
        timings.append(time.perf_counter() - start)
    return min(timings)


# Interleave the two measurements so a transient machine stall biases both
# together rather than skewing the ratio in one direction.
op_time = best_of(run, reps)
unit = best_of(calibration, reps)
op_time = min(op_time, best_of(run, reps))

print(json.dumps({"op": op_time, "unit": unit}))
"""


def _measure(op: str, reps: int) -> tuple[float, float]:
    """Return (best op wall time, best calibration wall time) for `op`."""
    script = _WORKER % {"root": str(REPO_ROOT)}
    proc = subprocess.run(
        [sys.executable, "-c", script, op, str(reps)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=dict(os.environ),
        check=False,
    )
    if proc.returncode != 0:
        pytest.fail(f"{op} worker failed:\n{proc.stderr}")
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    return float(payload["op"]), float(payload["unit"])


@pytest.mark.parametrize(("op", "ceiling"), sorted(MAX_COST_UNITS.items()))
def test_native_backend_cost_ceiling(op: str, ceiling: float) -> None:
    reps = 5 if op == "deepcopy" else 9

    op_time, unit = _measure(op, reps)
    cost = op_time / unit

    print(
        f"{op}: {op_time * 1e3:.2f}ms  unit {unit * 1e3:.2f}ms  "
        f"cost {cost:.4f} units  ceiling {ceiling:.4f}"
    )

    assert cost <= ceiling, (
        f"{op} costs {cost:.4f} calibration units, above the {ceiling:.4f} "
        f"ceiling. Something that used to run natively is likely falling back "
        f"to Python, or per-call work was reintroduced. "
        f"(op {op_time * 1e3:.2f}ms vs calibration unit {unit * 1e3:.2f}ms)"
    )
