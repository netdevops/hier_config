import ast
from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace

import pytest

from scripts import gen_stubs

BASELINE_SOURCE = dedent(
    '''
    class HConfigChild:
        """A child node in a configuration tree."""

        def __init__(self, parent: "HConfigChild", text: str) -> None:
            """Create a child of ``parent``."""
    '''
)


@pytest.mark.parametrize("class_name", ("HConfigBase", "HConfigChildren"))
@pytest.mark.parametrize(
    ("runtime_doc", "expected_doc"),
    (
        ("Return key in self.", "Return key in self."),
        ("Return bool(key in self).", "Return key in self."),
        (
            "Return whether the config contains a line.",
            "Return whether the config contains a line.",
        ),
    ),
)
def test_contains_stub_docs_are_stable_across_python_versions(
    class_name: str, runtime_doc: str, expected_doc: str
) -> None:
    definitions: dict[str, ast.AST] = {
        f"{class_name}.__contains__": ast.parse(
            "def __contains__(self, item: str) -> bool: ..."
        ).body[0]
    }
    rendered = gen_stubs.render(
        class_name,
        "__contains__",
        SimpleNamespace(__doc__=runtime_doc),
        definitions,
    )
    member = ast.parse(dedent("\n".join(rendered))).body[0]
    assert isinstance(member, ast.FunctionDef)
    assert ast.get_docstring(member) == expected_doc
    assert isinstance(member.returns, ast.Name)
    assert member.returns.id == "bool"


def test_child_deepcopy_has_typed_generated_signature() -> None:
    rendered = gen_stubs.render("HConfigChild", "__deepcopy__", object(), {})
    assert rendered[0].startswith(
        "    def __deepcopy__(self, memo: dict[int, object]) -> HConfigChild:"
    )


def test_check_never_rewrites_stubs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "child.pyi"
    target.write_text("# committed content\n", encoding="utf-8")
    monkeypatch.setattr(gen_stubs, "STUB_DIR", tmp_path)
    monkeypatch.setattr(gen_stubs, "MODULES", ("child",))
    monkeypatch.setattr(
        gen_stubs, "CLASSES", {"HConfigChild": ("child", "HConfigBase")}
    )
    monkeypatch.setattr(gen_stubs, "parse_check_flag", lambda: True)

    # Unit tests must never shell out to git: CI clones to depth 1, which omits
    # the v3.7.0 baseline commit the generator reads its prose from.
    def fake_baseline_source(_module: str) -> str:
        return BASELINE_SOURCE

    monkeypatch.setattr(gen_stubs, "baseline_source", fake_baseline_source)

    def preserve_text(_path: Path, text: str) -> str:
        return text

    monkeypatch.setattr(gen_stubs, "normalise_text", preserve_text)

    def reject_write(_path: Path, *_args: object, **_kwargs: object) -> int:
        pytest.fail("--check must not rewrite stubs while type checkers read them")

    monkeypatch.setattr(Path, "write_text", reject_write)
    assert gen_stubs.main() == 1
    assert target.read_text(encoding="utf-8") == "# committed content\n"


def test_baseline_source_reports_missing_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_commit(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(
            returncode=128, stdout="", stderr="fatal: invalid object name"
        )

    monkeypatch.setattr("subprocess.run", missing_commit)
    # ``functools.cache`` never memoises exceptions, so clearing beforehand is
    # enough to keep a real lookup from an earlier test out of the way.
    gen_stubs.baseline_source.cache_clear()
    with pytest.raises(gen_stubs.BaselineUnavailableError) as excinfo:
        gen_stubs.baseline_source("child")
    message = str(excinfo.value)
    assert "fetch-depth: 0" in message
    assert "fatal: invalid object name" in message
