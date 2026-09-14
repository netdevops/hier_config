from pathlib import Path

import pytest

from scripts import gen_stubs


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
    monkeypatch.setattr(gen_stubs, "original_defs", dict)

    def preserve_text(_path: Path, text: str) -> str:
        return text

    monkeypatch.setattr(gen_stubs, "normalise_text", preserve_text)

    def reject_write(_path: Path, *_args: object, **_kwargs: object) -> int:
        pytest.fail("--check must not rewrite stubs while type checkers read them")

    monkeypatch.setattr(Path, "write_text", reject_write)
    assert gen_stubs.main() == 1
    assert target.read_text(encoding="utf-8") == "# committed content\n"
