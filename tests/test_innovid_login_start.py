"""
El boton de iniciar sesion tiene que decir cuando no arranco.

Camilo, probando el paquete descargado de SharePoint: "nunca se me
abre la pestana para iniciar sesion". Y la app le decia, tan tranquila:

    A browser window is opening. Sign in, open a campaign...

Ese texto era fijo. El handler hacia un Popen y lo anunciaba sin mirar
si el proceso seguia vivo:

    subprocess.Popen([sys.executable, "check_innovid_connection.py",
                      "--login"], cwd=...)
    st.info("A browser window is opening...")

Cuando el proceso moria al instante -- que es lo que pasa si el
paquete se armo sin Chromium -- el usuario se quedaba esperando una
ventana que no iba a llegar nunca, sin error, sin log, sin nada.

Un fallo silencioso en el unico boton que conecta con Innovid.

Run with pytest, or directly:
    python tests/test_innovid_login_start.py
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.innovid_login import (  # noqa: E402
    LoginStart,
    bundled_browser_dir,
    ensure_browser_path,
    missing_browser_reason,
    start_innovid_login,
)

ROOT = Path(__file__).resolve().parents[1]


def _fake_install(*, bundled: bool, with_browser: bool) -> Path:
    """Un QA2 de mentira, con o sin navegador."""
    root = Path(tempfile.mkdtemp()) / "QA2-1.0.0-windows"
    root.mkdir(parents=True)
    if bundled:
        (root / "python").mkdir()
    if with_browser:
        (root / "browsers" / "chromium-1243").mkdir(parents=True)
    return root


# ── se distingue arrancar de no arrancar ─────────────────────────────

def test_a_missing_script_is_reported_not_announced():
    root = _fake_install(bundled=True, with_browser=True)
    outcome = start_innovid_login(root, settle=0.5)
    assert not outcome.ok
    assert "check_innovid_connection.py" in outcome.message


def test_the_package_browser_is_handed_to_playwright():
    """
    Se dice explicitamente en vez de confiar en heredarlo del
    lanzador: quien arranque QA2 de otra forma se quedaba sin
    navegador y sin explicacion.
    """
    root = _fake_install(bundled=True, with_browser=True)
    assert bundled_browser_dir(root) == root / "browsers"

    source = (ROOT / "core" / "innovid_login.py").read_text(encoding="utf-8")
    assert 'environment["PLAYWRIGHT_BROWSERS_PATH"]' in source


def test_an_empty_browsers_folder_does_not_count():
    root = _fake_install(bundled=True, with_browser=False)
    (root / "browsers").mkdir()
    assert bundled_browser_dir(root) is None


# ── el motivo se dice segun a quien se le dice ───────────────────────

def test_a_package_without_a_browser_says_to_ask_for_another():
    """Un `pip install` no le sirve a quien recibio un zip."""
    root = _fake_install(bundled=True, with_browser=False)
    reason = missing_browser_reason(root)
    assert "package" in reason.lower()
    assert "pip install" not in reason


def test_a_development_copy_is_told_the_command():
    root = _fake_install(bundled=False, with_browser=False)
    reason = missing_browser_reason(root)
    assert "playwright install chromium" in reason


def test_the_reason_says_the_rest_of_qa2_still_works():
    """
    Sin Innovid se siguen haciendo casi todas las validaciones. Quien
    lee esto no tiene por que pensar que QA2 no sirve.
    """
    root = _fake_install(bundled=True, with_browser=False)
    assert "Everything else works" in missing_browser_reason(root)


# ── la app usa esto, y no el Popen a ciegas ──────────────────────────

def test_the_app_checks_the_outcome():
    app = (ROOT / "ui" / "app_v2.py").read_text(encoding="utf-8")
    assert "start_innovid_login()" in app
    assert "_login_outcome.ok" in app
    assert "st.error(_login_outcome.message)" in app


def test_the_app_no_longer_launches_the_login_blind():
    app = (ROOT / "ui" / "app_v2.py").read_text(encoding="utf-8")
    assert 'check_innovid_connection.py", "--login"' not in app


def test_the_optimistic_message_is_behind_the_check():
    """
    El texto solo puede salir cuando el proceso sigue vivo. Anunciarlo
    siempre es lo que convirtio un fallo en una espera infinita.
    """
    app = (ROOT / "ui" / "app_v2.py").read_text(encoding="utf-8")
    at_message = app.index("A browser window is opening")
    at_check = app.index("if _login_outcome.ok:")
    assert at_check < at_message


def test_what_the_process_printed_is_kept():
    """Sin la salida, "no arranco" no se puede diagnosticar."""
    assert "detail" in LoginStart.__dataclass_fields__
    app = (ROOT / "ui" / "app_v2.py").read_text(encoding="utf-8")
    assert "_login_outcome.detail" in app


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))


# ── el proceso de la app tambien necesita la variable ────────────────
#
# El chequeo contra Innovid abre Chromium DENTRO del proceso de la
# app, no en un subproceso: pasarle el entorno a un Popen no alcanza.
# Y el lanzador sin ventana --el que usa el equipo-- no la ponia: solo
# lo hacia run_qa2.bat, la version con consola. Un paquete completo
# abierto con doble clic no encontraba su propio navegador.

def test_the_package_browser_is_set_on_this_process(monkeypatch):
    root = _fake_install(bundled=True, with_browser=True)
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    assert ensure_browser_path(root) == root / "browsers"
    assert os.environ["PLAYWRIGHT_BROWSERS_PATH"] == str(root / "browsers")


def test_a_variable_already_set_by_hand_wins(monkeypatch):
    root = _fake_install(bundled=True, with_browser=True)
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", "/somewhere/else")
    assert ensure_browser_path(root) is None
    assert os.environ["PLAYWRIGHT_BROWSERS_PATH"] == "/somewhere/else"


def test_a_development_copy_is_left_alone(monkeypatch):
    root = _fake_install(bundled=False, with_browser=False)
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    assert ensure_browser_path(root) is None
    assert "PLAYWRIGHT_BROWSERS_PATH" not in os.environ


def test_the_app_sets_it_before_starting():
    """
    En scripts/start_qa2.py, que es por donde entra todo el mundo:
    QA2.bat, run_qa2.bat y quien lo llame a mano.
    """
    source = (ROOT / "scripts" / "start_qa2.py").read_text(encoding="utf-8")
    assert "ensure_browser_path(ROOT)" in source


def test_the_silent_launcher_is_not_the_one_that_knows():
    """
    QA2.bat tambien la pone, pero la app no depende de eso: se dedujo
    de la carpeta. Esta prueba fija justo eso -- que no volvamos a
    dejarlo solo en el .bat con ventana.
    """
    silent = (ROOT / "QA2.bat").read_text(encoding="utf-8")
    assert "PLAYWRIGHT_BROWSERS_PATH" in silent


# ── el zip de actualizacion no es la aplicacion ──────────────────────

def test_the_update_zip_opened_on_its_own_says_so():
    """
    Ese zip es un parche: el codigo y nada mas, para caer encima de
    una instalacion que ya existe. Extraido solo, arranca --hay Python
    en la maquina-- pero sin interprete propio ni navegador, y lo
    unico que se veia era un "corre pip install" que no tiene nada que
    ver con lo que pasa.
    """
    root = _fake_install(bundled=False, with_browser=False)
    (root / "ACTUALIZAR QA2.bat").write_text("", encoding="utf-8")
    reason = missing_browser_reason(root)
    assert "update" in reason.lower()
    assert "pip install" not in reason
    assert "playwright install" not in reason


def test_a_real_development_copy_still_gets_the_command():
    """
    Una copia del repositorio tiene .git: ahi el `playwright install`
    si es el remedio, aunque el archivo del actualizador exista en
    scripts/.
    """
    root = _fake_install(bundled=False, with_browser=False)
    (root / ".git").mkdir()
    (root / "ACTUALIZAR QA2.bat").write_text("", encoding="utf-8")
    assert "playwright install chromium" in missing_browser_reason(root)
