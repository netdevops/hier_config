"""The corpus must carry the loader and user rules used by its source tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.native.test_corpus import test_corpus_case as run_corpus_case

if TYPE_CHECKING:
    from pathlib import Path


def test_corpus_applies_explicit_negation_rules(tmp_path: Path) -> None:
    (tmp_path / "running.conf").write_text("hostname r1\n", encoding="utf-8")
    (tmp_path / "intended.conf").write_text("", encoding="utf-8")
    (tmp_path / "remediation.conf").write_text(
        "default hostname r1\n", encoding="utf-8"
    )
    run_corpus_case(
        "custom-rule",
        tmp_path,
        {
            "platform": "GENERIC",
            "description": "A user replacement must override generic negation.",
            "assert_rollback": True,
            "negation": [
                {
                    "match_rules": [{"startswith": "hostname "}],
                    "strategy": "replace",
                    "use": "default hostname r1",
                }
            ],
        },
    )


def test_corpus_preserves_source_loader(tmp_path: Path) -> None:
    (tmp_path / "running.conf").write_text("", encoding="utf-8")
    text = "banner motd #\nhello\n#\n"
    (tmp_path / "intended.conf").write_text(text, encoding="utf-8")
    (tmp_path / "remediation.conf").write_text(text, encoding="utf-8")
    run_corpus_case(
        "line-loader",
        tmp_path,
        {
            "platform": "GENERIC",
            "description": "Split lines must not run full-text banner processing.",
            "loader": "lines",
        },
    )
