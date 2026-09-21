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

from core.paths import shared_config_path

TEAM_ROSTER_FILE = "team_roster.json"


def roster_path(*, for_write: bool = False) -> Path:
    return shared_config_path(TEAM_ROSTER_FILE, for_write=for_write)

ACCOUNTS = ("Unilever", "Wendy's", "BlackRock", "Adobe", "Support")


def default_roster() -> dict[str, list[str]]:
    roster = {account: [] for account in ACCOUNTS}
    roster["Adobe"] = ["Camilo Mantilla"]
    return roster


def load_roster() -> dict[str, list[str]]:
    roster = default_roster()
    path = roster_path()
    if not path.exists():
        return roster
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
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
    path = roster_path(for_write=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = {
        account: [
            str(n).strip()
            for n in roster.get(account, [])
            if str(n).strip()
        ]
        for account in ACCOUNTS
    }
    path.write_text(
        json.dumps(clean, indent=2), encoding="utf-8"
    )


def base_account(value: str) -> str:
    """
    La cuenta a la que pertenece lo que se eligio en el selector.

    El selector "Account / Campaign" no ofrece solo cuentas: tambien
    las lineas de negocio de la tabla de pixeles de Adobe, porque el
    pixel oficial cambia de una a otra ("Adobe Acrobat", "Adobe
    Firefly", "Adobe PGA"...). Elegir una de esas dejaba los tres
    desplegables de "By" con solo Support, porque el roster se busca
    por clave exacta.

    Una etiqueta que empieza por el nombre de una cuenta pertenece a
    esa cuenta. Se prefiere la coincidencia mas larga, por si algun
    dia dos cuentas comparten prefijo.
    """
    texto = str(value or "").strip()
    if not texto or texto in ACCOUNTS:
        return texto

    clave = texto.casefold()
    candidatas = [
        account for account in ACCOUNTS
        if account != "Support" and clave.startswith(account.casefold())
    ]
    return max(candidatas, key=len) if candidatas else texto


def names_for_account(roster: dict[str, list[str]], account: str) -> list[str]:
    """Roster for one account plus Support, deduped, order preserved."""
    names: list[str] = []
    cuenta = base_account(account)
    for name in roster.get(cuenta, []) + roster.get("Support", []):
        if name and name not in names:
            names.append(name)
    return names
