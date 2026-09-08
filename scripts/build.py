#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess  # ruff:ignore[suspicious-subprocess-import]
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

from typer import Typer

if TYPE_CHECKING:
    from collections.abc import Iterable

app = Typer()


@app.callback()
def callback() -> None:
    """Build tools."""


@app.command()
def lint(*, fix: bool = False) -> None:
    """Run all linters and type checkers in order of importance - returns the first non-zero exit code or zero."""
    _run_commands_threaded(
        (
            _ruff_format_command(fix=fix),
            _ruff_check_command(fix=fix, unsafe_fixes=False, statistics=False),
            _mypy_command(),
            _pyright_command(),
            _pylint_command(),
            _yamllint_command(),
            _flynt_command(fix=fix),
            _check_displacement_markers_command(),
            _check_stubs_command(),
            _stubtest_command(),
            _check_stub_types_command(),
            _check_formats_corpus_command(),
        ),
    )


@app.command()
def lint_and_test(*, fix: bool = False) -> None:
    """Run all code fixs in order of importance - returns the first non-zero exit code or zero."""
    _run_commands_threaded(
        (
            _ruff_format_command(fix=fix),
            _ruff_check_command(fix=fix, unsafe_fixes=False, statistics=False),
            _mypy_command(),
            _pyright_command(),
            _pylint_command(),
            _pytest_command(),
            _yamllint_command(),
            _flynt_command(fix=fix),
            _check_displacement_markers_command(),
            _check_stubs_command(),
            _stubtest_command(),
            _check_stub_types_command(),
            _check_formats_corpus_command(),
        ),
    )


@app.command()
def ruff_format(*, fix: bool = False) -> None:
    """Run Ruff linter."""
    _run(_ruff_format_command(fix=fix))


def _ruff_format_command(*, fix: bool) -> str:
    return f"ruff format {'' if fix else '--check '}{_python_base_paths_str()}"


@app.command()
def ruff_check(
    *,
    fix: bool = False,
    unsafe_fixes: bool = False,
    statistics: bool = False,
) -> None:
    """Run Ruff linter."""
    _run(_ruff_check_command(fix=fix, unsafe_fixes=unsafe_fixes, statistics=statistics))


def _ruff_check_command(*, fix: bool, unsafe_fixes: bool, statistics: bool) -> str:
    return f"ruff check --output-format=concise {'--fix ' if fix else ''}{'--unsafe-fixes ' if unsafe_fixes else ''}{'--statistics ' if statistics else ''}{_python_base_paths_str()}"


@app.command()
def pytest(
    *,
    profile: bool = False,
    coverage: bool = True,
    threaded: bool = False,
) -> None:
    """Run pytest unittests."""
    _run(
        _pytest_command(
            profile=profile,
            coverage=coverage,
            threaded=threaded,
        ),
        environment={"COVERAGE_CORE": "sysmon"},
    )


def _pytest_command(
    *,
    profile: bool = False,
    coverage: bool = True,
    threaded: bool = False,
) -> str:
    command = "pytest"
    if profile:
        command += " --profile --profile-svg"
    if coverage:
        # Re-anchored from 95 to 88 by the v3.7 Rust migration. The tree, diff,
        # remediation and post-load engines moved into crates/hier_config_core
        # and are covered by `cargo test --workspace`; what remains measurable
        # here is the Python API surface and the platform drivers. The shortfall
        # is concentrated in the per-platform `_fixup_*` functions that the Rust
        # post-load pipeline superseded but which were left in place -- removing
        # that dead code is the way to raise this floor again, not relaxing it
        # further.
        command += " --cov=hier_config --cov-fail-under=88 --cov-report=term-missing"
    if threaded:
        command += " -n auto"
    return command


@app.command()
def check_displacement_markers() -> None:
    """Validate @pytest.mark.displaced_by targets."""
    _run(_check_displacement_markers_command())


def _check_displacement_markers_command() -> str:
    return f"{sys.executable} scripts/check_displacement_markers.py"


@app.command()
def check_stubs() -> None:
    """Fail when the generated .pyi stubs no longer match the compiled extension."""
    _run(_check_stubs_command())


def _check_stubs_command() -> str:
    return f"{sys.executable} scripts/gen_stubs.py --check"


@app.command()
def stubtest() -> None:
    """Fail when the type stubs disagree with the objects they describe."""
    _run(_stubtest_command())


def _stubtest_command() -> str:
    # `gen_stubs.py --check` guards *names*; this guards *signatures*, and
    # `check_stub_types.py` guards *return types* by observing live objects.
    # Runtime introspection cannot see annotations, and nothing observes an
    # argument that was never passed, so parameter *types* remain the type
    # checkers' responsibility alone.
    return (
        f"{sys.executable} -m mypy.stubtest"
        " --mypy-config-file pyproject.toml"
        " --allowlist stubs/stubtest-allowlist.txt"
        " _hier_config_rust hier_config"
    )


@app.command()
def check_stub_types() -> None:
    """Fail when a declared return type contradicts what the extension returns."""
    _run(_check_stub_types_command())


def _check_stub_types_command() -> str:
    # Return annotations are not recoverable from a compiled .so, so for an
    # extension module the stub is the type checkers' only source of truth: a
    # wrong return type is the premise they reason from, not an error they can
    # find. This observes real objects instead, element types included.
    return f"{sys.executable} scripts/check_stub_types.py --check"


@app.command()
def check_formats_corpus() -> None:
    """Fail when testdata/formats/expected.json no longer matches Python's output."""
    _run(_check_formats_corpus_command())


def _check_formats_corpus_command() -> str:
    return f"{sys.executable} scripts/gen_formats_corpus.py --check"


@app.command()
def rust_coverage(*, fail_under: int = 40) -> None:
    """Run cargo-llvm-cov on hier_config_core with a line coverage floor."""
    _run(f"cargo llvm-cov --package hier_config_core --fail-under-lines={fail_under}")


@app.command()
def yamllint() -> None:
    """Run yamllint to check YAML syntax."""
    _run(_yamllint_command())


def _yamllint_command() -> str:
    return f"yamllint {_repo_path().relative_to(Path.cwd())}"


@app.command()
def pylint() -> None:
    """Run pylint linter."""
    _run(_pylint_command())


def _pylint_command() -> str:
    return f"pylint {_python_base_paths_str()}"


@app.command()
def mypy() -> None:
    """Run mypy type checker."""
    _run(_mypy_command())


def _mypy_command() -> str:
    return f"mypy {_python_base_paths_str()}"


@app.command()
def pyright() -> None:
    """Run pyright type checker."""
    _run(_pyright_command())


def _pyright_command() -> str:
    return f"pyright {_python_base_paths_str()}"


@app.command()
def flynt(*, fix: bool = False) -> None:
    """Run flynt to enforce the use of f-strings."""
    _run(_flynt_command(fix=fix))


def _flynt_command(*, fix: bool) -> str:
    if fix:
        return f"flynt -tc {_python_base_paths_str()}"
    return f"flynt -d -tc -f {_python_base_paths_str()}"


@cache
def _python_base_paths_str() -> str:
    return " ".join(str(p) for p in _python_base_paths())


def _python_base_paths() -> Iterable[Path]:
    yield from (f.relative_to(Path.cwd()) for f in _project_base_paths("*.py"))


def _project_base_paths(glob: str) -> Iterable[Path]:
    yield from _project_paths(glob)
    yield from _project_base_files(glob)


def _project_base_files(glob: str) -> Iterable[Path]:
    yield from _repo_path().glob(glob)


def _project_paths(glob: str) -> Iterable[Path]:
    for base_dir in ("hier_config", "tests", "scripts"):
        base_path = _repo_path().joinpath(base_dir)
        if not base_path.exists():
            message = f"{base_path=} does not exist"
            raise FileNotFoundError(message)

        if next(base_path.glob(glob), None):
            yield base_path


def _run_commands_threaded(commands: tuple[str, ...]) -> NoReturn:
    return_codes: dict[str, int] = {}
    with ThreadPoolExecutor(max_workers=len(commands)) as executor:
        for future in as_completed(
            executor.submit(
                _run_for_thread,
                command,
            )
            for command in commands
        ):
            command, return_code, output = future.result()
            if return_code:
                print(output)  # ruff:ignore[print]
            return_codes[command] = return_code

    error_found = False
    for command, return_code in return_codes.items():
        if return_code != 0:
            print(f"{command.split()[0]} -> {return_code}")  # ruff:ignore[print]
            error_found = True
    if error_found:
        sys.exit(1)
    print("No issues found")  # ruff:ignore[print]
    sys.exit()


def _run(
    command: str,
    *,
    check: bool = True,
    environment: dict[str, str] | None = None,
) -> int:
    print(f"\n======== {command} ========\n")  # ruff:ignore[print]
    my_env = os.environ.copy()
    if environment:
        my_env.update(environment)
    result = subprocess.run(command.split(), check=False, env=my_env)  # ruff:ignore[subprocess-without-shell-equals-true]
    if check:
        sys.exit(result.returncode)
    return result.returncode


def _run_for_thread(command: str) -> tuple[str, int, str]:
    print(f"Running: {command}")  # ruff:ignore[print]
    result = subprocess.run(  # ruff:ignore[subprocess-without-shell-equals-true]
        command.split(),
        check=False,
        capture_output=True,
    )
    output = f"\n======== {command} ========\n{result.stdout.decode()}\n{result.stderr.decode()}"
    return command, result.returncode, output


@cache
def _repo_path() -> Path:
    return Path(__file__).parents[1]


def main() -> None:
    app()


if __name__ == "__main__":
    main()
