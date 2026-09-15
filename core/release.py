"""
Which version of QA2 this is, and what changed in it.

The team does not read the repository -- most of them will never see
it. What they open is the app, so the app is where the release notes
have to appear. docs/CHANGELOG.md travels inside the zip; this reads
the top entry out of it.

Neither function ever raises. A missing or malformed CHANGELOG means
the panel says less, not that QA2 fails to start.
"""
from __future__ import annotations

from pathlib import Path

from core.paths import project_root


def qa2_version() -> str:
    """The contents of VERSION, or "dev" if it isn't there."""
    try:
        text = (project_root() / "VERSION").read_text(encoding="utf-8").strip()
        return text or "dev"
    except OSError:
        return "dev"


def changelog_path() -> Path:
    return project_root() / "docs" / "CHANGELOG.md"


def release_notes(limit: int = 60) -> str:
    """
    The most recent version's entry from the changelog, as markdown.

    The entry runs from the first `## ` heading to the next one. The
    template block at the bottom of the file is a `## ` heading too,
    but it is last, so taking the *first* entry never reaches it.
    """
    try:
        text = changelog_path().read_text(encoding="utf-8")
    except OSError:
        return ""

    lines = text.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if line.startswith("## ")),
        None,
    )
    if start is None:
        return ""

    end = next(
        (
            i
            for i, line in enumerate(lines[start + 1 :], start + 1)
            if line.startswith("## ")
        ),
        len(lines),
    )

    entry = lines[start:end]
    if len(entry) > limit:
        entry = entry[:limit] + ["", "*…continues in docs/CHANGELOG.md*"]
    return "\n".join(entry).strip()
