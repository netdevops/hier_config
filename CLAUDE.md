# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

@AGENTS.md

## Branching Strategy

- `master` — stable branch for v3.x releases and maintenance.
- `next` — long-lived development branch for v4 work. All v4 features and breaking changes target this branch. PRs for v4 work should be opened against `next`.

## Self-Review

Before opening or finalizing a PR, run the `hier-config-review` skill (`/hier-config-review`). It checks the diff against the repo's standards — models/typing, tests/TDD/coverage, changelog, docs, and driver patterns — and reports findings by severity.

## Benchmarks

Performance benchmarks are in `tests/benchmarks/test_benchmarks.py` and are **skipped by default** via the `benchmark` pytest marker. They generate ~10,000-line configs and measure parsing, remediation, and iteration performance.

```bash
# Run all benchmarks with timing output
poetry run pytest -m benchmark -v -s

# Run a specific benchmark
poetry run pytest -m benchmark -k test_parse_large_ios_config -v -s
```

Use `-s` to see printed timing results. Each benchmark reports the best time over 3 iterations and asserts an upper bound (e.g., `< 5s` for parsing, `< 10s` for remediation). If a benchmark fails its time threshold, investigate the relevant code path for performance regressions.

After running benchmarks, always display the results to the user in a table format summarizing each benchmark's config size and elapsed time.
