from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from scripts import gen_formats_corpus

if TYPE_CHECKING:
    from pathlib import Path


def test_default_command_does_not_overwrite_frozen_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus = tmp_path / "expected.json"
    corpus.write_text("frozen reference\n", encoding="utf-8")
    monkeypatch.setattr(gen_formats_corpus, "CORPUS", corpus)
    monkeypatch.setattr("sys.argv", ["gen_formats_corpus.py"])

    assert gen_formats_corpus.main() == 1
    assert corpus.read_text(encoding="utf-8") == "frozen reference\n"


def test_native_implementation_cannot_capture_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus = tmp_path / "expected.json"
    corpus.write_text("frozen reference\n", encoding="utf-8")
    monkeypatch.setattr(gen_formats_corpus, "CORPUS", corpus)
    monkeypatch.setattr("sys.argv", ["gen_formats_corpus.py", "--capture-reference"])

    assert gen_formats_corpus.main() == 1
    assert corpus.read_text(encoding="utf-8") == "frozen reference\n"


@pytest.mark.parametrize("format_name", ("JSON", "XML"))
def test_normalize_only_parser_diagnostics(format_name: str) -> None:
    prefix = f"InvalidConfigError: The config is not valid {format_name}:"
    reference = {"err": f"{prefix} Python diagnostic"}
    native = {"err": f"{prefix} Rust diagnostic"}
    assert gen_formats_corpus.normalize_outcomes(reference) == {"err": prefix}
    assert gen_formats_corpus.normalize_outcomes(reference) == (
        gen_formats_corpus.normalize_outcomes(native)
    )
    wrong_class = {"err": f"ValueError: The config is not valid {format_name}: reason"}
    assert gen_formats_corpus.normalize_outcomes(wrong_class) == wrong_class
    success = {"ok": f"{prefix} must remain literal data"}
    assert gen_formats_corpus.normalize_outcomes(success) == success
    other_error = {"err": "InvalidConfigError: Unsupported JSON key: ''"}
    assert gen_formats_corpus.normalize_outcomes(other_error) == other_error


@pytest.mark.parametrize("changed", ("none", "result", "provenance"))
def test_check_does_not_rewrite_mismatching_snapshot(
    tmp_path: Path, changed: str
) -> None:
    path = tmp_path / "expected.json"
    provenance: dict[str, object] = {"implementation": "pure-python"}
    captured: dict[str, dict[str, object]] = {
        "_provenance": provenance,
        "json": {"example": {"ok": "frozen"}},
    }
    original = gen_formats_corpus.render(captured)
    path.write_text(original, encoding="utf-8")
    actual: dict[str, dict[str, object]] = {
        "json": {"example": {"ok": "new" if changed == "result" else "frozen"}}
    }
    if changed == "provenance":
        provenance = {"implementation": "native"}

    assert gen_formats_corpus.check_snapshot(path, actual, provenance) is (
        changed == "none"
    )
    assert path.read_text(encoding="utf-8") == original
