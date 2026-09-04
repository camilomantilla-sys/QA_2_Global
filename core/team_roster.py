"""
Team roster: who's on each account's team.

One flat list of people per account (Unilever / Wendy's / BlackRock /
Adobe), plus a Support column for people from other accounts who
sometimes pitch in. No fixed role per person -- anyone listed under
an account can act as Implementer, QA2 or QA3 depending on the task,
so the same roster feeds all three "By" fields in the app.

Editable in-app (config/team_roster.json, re-read on every load) the
same way the Pixels by account tables are.
"""
from __future__ import annotations

import json
from pathlib import Path

TEAM_ROSTER_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "team_roster.json"
)

ACCOUNTS = ("Unilever", "Wendy's", "BlackRock", "Adobe", "Support")


def default_roster() -> dict[str, list[str]]:
    roster = {account: [] for account in ACCOUNTS}
    roster["Adobe"] = ["Camilo Mantilla"]
    return roster


def load_roster() -> dict[str, list[str]]:
    roster = default_roster()
    if not TEAM_ROSTER_PATH.exists():
        return roster
    try:
        data = json.loads(TEAM_ROSTER_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            for account in ACCOUNTS:
                names = data.get(account, [])
                if isinstance(names, list):
                    roster[account] = [
                        str(n).strip() for n in names if str(n).strip()
                    ]
    except Exception:
        pass
    return roster


def save_roster(roster: dict[str, list[str]]) -> None:
    TEAM_ROSTER_PATH.parent.mkdir(parents=True, exist_ok=True)
    clean = {
        account: [
            str(n).strip()
            for n in roster.get(account, [])
            if str(n).strip()
        ]
        for account in ACCOUNTS
    }
    TEAM_ROSTER_PATH.write_text(
        json.dumps(clean, indent=2), encoding="utf-8"
    )


def names_for_account(roster: dict[str, list[str]], account: str) -> list[str]:
    """Roster for one account plus Support, deduped, order preserved."""
    names: list[str] = []
    for name in roster.get(account, []) + roster.get("Support", []):
        if name and name not in names:
            names.append(name)
    return names
