"""
Team roster: who does Implementer / QA2 / QA3 for each account.

Pure reference data, editable in-app the same way the Pixels by
account tables are (config/team_roster.json, re-read on every load).
Starts seeded with the four known accounts so they always show up in
the table even before anyone's been assigned.
"""
from __future__ import annotations

import json
from pathlib import Path

TEAM_ROSTER_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "team_roster.json"
)

ROLES = ("Implementer", "QA2", "QA3")

_DEFAULT_ROWS = (
    {"account": "Unilever", "role": "", "name": ""},
    {"account": "Wendy's", "role": "", "name": ""},
    {"account": "BlackRock", "role": "", "name": ""},
    {"account": "Adobe", "role": "QA2", "name": "Camilo Mantilla"},
)


def default_team_rows() -> list[dict]:
    return [dict(row) for row in _DEFAULT_ROWS]


def load_team_rows() -> list[dict]:
    if not TEAM_ROSTER_PATH.exists():
        return default_team_rows()
    try:
        data = json.loads(TEAM_ROSTER_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list) and data:
            return data
    except Exception:
        pass
    return default_team_rows()


def save_team_rows(rows: list[dict]) -> None:
    TEAM_ROSTER_PATH.parent.mkdir(parents=True, exist_ok=True)
    TEAM_ROSTER_PATH.write_text(
        json.dumps(rows, indent=2), encoding="utf-8"
    )
