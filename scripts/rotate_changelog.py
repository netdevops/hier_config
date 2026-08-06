#!/usr/bin/env python3
"""Rotate CHANGELOG.md's Unreleased section into a dated release section.

Used by .github/workflows/prepare-release.yml. Prints the rotated section
body to stdout so the workflow can reuse it as the draft release notes.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

UNRELEASED_HEADING = "## [Unreleased]"


def rotate(changelog_path: Path, version: str, date: str) -> str:
    text = changelog_path.read_text(encoding="utf-8")
    start = text.find(UNRELEASED_HEADING)
    if start == -1:
        message = f"{changelog_path} has no '{UNRELEASED_HEADING}' section"
        raise ValueError(message)

    body_start = start + len(UNRELEASED_HEADING)
    next_heading = text.find("\n## [", body_start)
    body_end = next_heading if next_heading != -1 else len(text)
    # The trailing "---" thematic break belongs to the section separator,
    # not to the release notes themselves.
    section_body = text[body_start:body_end].strip("\n").removesuffix("---").strip("\n")
    if not section_body:
        message = "the Unreleased section is empty; nothing to release"
        raise ValueError(message)

    released = f"## [{version}] - {date}\n\n{section_body}\n"
    rotated = f"{text[:start]}{UNRELEASED_HEADING}\n\n{released}"
    remainder = text[body_end:]
    if remainder:
        rotated += f"\n---\n{remainder}"
    changelog_path.write_text(rotated, encoding="utf-8")
    return section_body


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(f"usage: {sys.argv[0]} <version>")
    date = datetime.now(tz=timezone.utc).date().isoformat()
    try:
        notes = rotate(Path("CHANGELOG.md"), sys.argv[1], date)
    except (OSError, ValueError) as exc:
        sys.exit(str(exc))
    print(notes)  # ruff:ignore[print]


if __name__ == "__main__":
    main()
