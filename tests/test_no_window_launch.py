"""
El equipo abre QA2 con doble clic y nada mas.

    "yo no quiero que mi amiga tenga que abrir ninguna terminal ni
     nada solo abrir la app"

Eso lo hacia el lanzador .vbs, hasta que resulto que la directiva de
seguridad de WPP bloquea Windows Script Host. Ahora lo hace
pythonw.exe, que corre sin consola y viene dentro del paquete.

Arrancar sin ventana tiene un precio conocido, y es el que hundio al
.vbs: sin consola, un fallo no se ve por ningun lado y la persona
espera a una ventana que no va a llegar. Una companera de Camilo
espero diez minutos asi.

Por eso lo que se prueba aqui no es que arranque -- es que cuando NO
arranca, lo diga.

Run with pytest, or directly:
    python tests/test_no_window_launch.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
STARTER = (ROOT / "scripts" / "start_qa2.py").read_text(encoding="utf-8")
QA2_BAT = (ROOT / "QA2.bat").read_text(encoding="utf-8")


# ── se abre sin ventana ──────────────────────────────────────────────

def test_the_team_opens_one_file():
    assert (ROOT / "QA2.bat").exists()


def test_it_runs_without_a_console():
    """pythonw.exe no abre consola. python.exe si."""
    assert "pythonw.exe" in QA2_BAT


def test_it_finds_pythonw_in_a_package_and_in_a_checkout():
    assert r"python\pythonw.exe" in QA2_BAT
    assert r".venv\Scripts\pythonw.exe" in QA2_BAT


def test_without_pythonw_it_still_starts():
    """Arrancar con ventana es mejor que no arrancar."""
    assert "run_qa2.bat" in QA2_BAT


def test_nothing_here_needs_a_script_host():
    """La directiva de IT bloquea los .vbs."""
    assert not list(ROOT.glob("*.vbs"))
    assert "cscript" not in QA2_BAT.lower()
    assert "wscript" not in QA2_BAT.lower()


# ── y cuando falla, se ve ────────────────────────────────────────────

def test_a_server_that_never_comes_up_is_reported():
    """Lo que le faltaba al .vbs: decirlo."""
    import scripts.start_qa2 as starter

    said = []
    original_tell, original_timeout = starter._tell, starter.STARTUP_TIMEOUT
    starter._tell = said.append
    starter.STARTUP_TIMEOUT = 1
    try:
        starter._watch(9, Path("logs/qa2_startup.log"))
    finally:
        starter._tell, starter.STARTUP_TIMEOUT = original_tell, original_timeout

    assert said
    assert "qa2_startup.log" in said[0]


def test_the_warning_does_not_need_a_console_either():
    """
    MessageBoxW por ctypes. Un print no lo lee nadie cuando no hay
    consola, y un .vbs esta bloqueado.
    """
    assert "MessageBoxW" in STARTER
    assert "ctypes" in STARTER


def test_the_warning_survives_a_machine_that_refuses_it():
    """Un aviso que revienta es peor que no avisar."""
    import scripts.start_qa2 as starter

    starter._tell("probando")  # en Linux no hay windll y no debe fallar


def test_what_happened_is_written_down():
    """Sin consola, stdout va al vacio."""
    assert "qa2_startup.log" in STARTER
    assert "sys.stdout = handle" in STARTER


def test_a_missing_streamlit_says_the_download_was_incomplete():
    assert "vuelve a extraer" in STARTER


# ── no se multiplica ─────────────────────────────────────────────────

def test_a_second_launch_opens_the_one_already_running():
    """
    Sin esto Streamlit se iba al 8502 y cada vuelta dejaba un proceso
    vivo. Camilo llego a once.
    """
    at_check = STARTER.index("if _answers(port):")
    at_write = STARTER.index("write_pid(ROOT)")
    assert at_check < at_write


def test_the_browser_is_opened_once_the_server_answers():
    """No al lanzarlo: a una pestana en blanco no la arregla nadie."""
    watch = STARTER[STARTER.index("def _watch"):]
    watch = watch[:watch.index("\ndef ")]
    assert watch.index("_answers(port)") < watch.index("webbrowser.open")


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
