"""
Que exista el archivo de sesion no es que la sesion sirva.

La app decia "Signed in" en verde con solo encontrar el archivo, y la
sesion caducada se descubria a mitad del QA, cuando Innovid contestaba
401. El archivo trae la fecha de caducidad de cada cookie: leerla no
cuesta una llamada de red.

Run with pytest, or directly:
    python tests/test_innovid_session_expiry.py
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.innovid_api import (  # noqa: E402
    session_expires_at,
    session_has_expired,
)

NOW = time.time()
HOUR = 3600


def _session(cookies: list[dict]) -> Path:
    tmp = Path(tempfile.mkdtemp())
    path = tmp / "innovid_session.json"
    path.write_text(json.dumps({"cookies": cookies, "origins": []}))
    return path


def _cookie(domain="api.flashtalking.net", expires=NOW + HOUR, name="SESSION"):
    return {"name": name, "value": "x", "domain": domain,
            "path": "/", "expires": expires}


def test_an_expired_session_is_reported_as_expired():
    assert session_has_expired(_session([_cookie(expires=NOW - 60)]))


def test_a_live_session_is_not():
    assert not session_has_expired(_session([_cookie(expires=NOW + HOUR)]))


def test_the_earliest_innovid_cookie_wins():
    # En cuanto una muere la sesion deja de servir; la optimista
    # mandaria a alguien a correr un QA que va a fallar con 401.
    path = _session([
        _cookie(expires=NOW + 10 * HOUR, name="a"),
        _cookie(expires=NOW + HOUR, name="b"),
    ])
    expiry = session_expires_at(path)
    assert abs(expiry.timestamp() - (NOW + HOUR)) < 2


def test_the_identity_providers_cookies_are_ignored():
    # Sobreviven a la sesion de Innovid y darian una fecha optimista.
    path = _session([
        _cookie(domain="uam-login.mediaocean.com", expires=NOW + 999 * HOUR),
    ])
    assert session_expires_at(path) is None


def test_a_missing_file_is_unknown_not_valid():
    assert session_expires_at(Path("/nope/innovid_session.json")) is None


def test_an_unreadable_file_is_unknown_not_expired():
    tmp = Path(tempfile.mkdtemp()) / "broken.json"
    tmp.write_text("not json at all")
    assert session_expires_at(tmp) is None
    assert not session_has_expired(tmp)


def test_a_pure_session_cookie_has_no_date_and_is_not_called_expired():
    # expires -1 = muere al cerrar el navegador. Sin fecha no se
    # afirma nada: decir "vencida" mandaria a firmar de nuevo una
    # sesion que servia.
    path = _session([_cookie(expires=-1)])
    assert session_expires_at(path) is None
    assert not session_has_expired(path)


def test_unknown_is_never_reported_as_expired():
    assert not session_has_expired(_session([]))


if __name__ == "__main__":
    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {name}: {exc}")
        else:
            passed += 1
            print(f"ok   {name}")

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
