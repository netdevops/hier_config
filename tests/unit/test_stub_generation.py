"""Python tooling delegates generation to the binding-owned Rust executable."""

import shlex
from collections.abc import Iterator
from pathlib import Path

import pytest

from scripts import build


@pytest.mark.parametrize("check", (False, True))
def test_stub_commands_use_current_binding_metadata(
    monkeypatch: pytest.MonkeyPatch, *, check: bool
) -> None:
    commands: list[str] = []

    def capture_command(command: str) -> int:
        commands.append(command)
        return 0

    monkeypatch.setattr(build, "_run", capture_command)
    if check:
        build.check_stubs()
    else:
        build.generate_stubs()
    assert len(commands) == 1
    args = shlex.split(commands[0])
    assert args[:3] == ["cargo", "run", "--quiet"]
    assert "--locked" in args
    assert "--no-default-features" in args
    assert args[args.index("--package") + 1] == "hier_config"
    assert args[args.index("--bin") + 1] == "gen-stubs"
    assert ("--check" in args) is check
    if check:
        assert args[-2:] == ["--", "--check"]


def test_stubtest_checks_native_submodule_only_through_its_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[str] = []

    def capture_command(command: str) -> int:
        commands.append(command)
        return 0

    monkeypatch.setattr(build, "_run", capture_command)
    build.stubtest()
    args = shlex.split(commands[0])
    assert args[-1] == "hier_config"
    assert "hier_config._hier_config_rust" not in args
    assert args[args.index("--mypy-config-file") + 1] == "pyproject.toml"
    assert args[args.index("--allowlist") + 1] == "tests/typing/stubtest-allowlist.txt"
    # pyo3-stub-gen cannot emit `@disjoint_base`; nothing else may be waived.
    assert [arg for arg in args if arg.startswith("--ignore")] == [
        "--ignore-disjoint-bases"
    ]


def test_pylint_checks_runtime_sources_not_stub_bodies(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    package = tmp_path / "package"
    package.mkdir()
    source = package / "__init__.py"
    source.write_text("", encoding="utf-8")
    stub = package / "_native.pyi"
    stub.write_text("def example(value: str) -> str: ...\n", encoding="utf-8")

    def source_paths() -> Iterator[Path]:
        yield package

    commands: list[str] = []

    def capture_command(command: str) -> int:
        commands.append(command)
        return 0

    monkeypatch.setattr(build, "_python_base_paths", source_paths)
    monkeypatch.setattr(build, "_run", capture_command)
    build.pylint()
    assert shlex.split(commands[0]) == ["pylint", str(source)]
