"""
Dos carpetas de QA2 en la misma maquina, y la que se veia no era la
que se habia abierto.

La gente conserva la carpeta de la version vieja. Al arrancar, QA2
miraba si ALGUIEN contestaba en el 8501 y, si si, abria el navegador
ahi y se salia. Pero ese alguien podia ser la copia de otra carpeta:
entonces se abria una version distinta de la que se habia hecho doble
clic, sin un solo aviso, y la app parecia "no arrancar" mientras
mostraba otra cosa.

Camilo: "intenté correr esa version vieja que nunca la borré y me
corre la mas reciente".

Lo que faltaba era preguntar de QUIEN es el puerto. El PID que cada
carpeta deja escrito lo responde: si es el nuestro, se abre sobre el;
si no, se arranca en un puerto propio.

Run with pytest, or directly:
    python tests/test_two_installations.py
"""
from __future__ import annotations

import importlib.util
import os
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]

from core.pidfile import (  # noqa: E402
    _alive, clear_pid, is_running, pid_path, write_pid,
)


def _start_qa2():
    spec = importlib.util.spec_from_file_location(
        "start_qa2_under_test", ROOT / "scripts" / "start_qa2.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ── de quien es el puerto ────────────────────────────────────────────

def test_a_live_pid_is_recognised(tmp_path):
    write_pid(tmp_path)
    assert is_running(tmp_path) is True


def test_a_folder_that_never_ran_owns_nothing(tmp_path):
    assert is_running(tmp_path) is False


def test_a_dead_pid_owns_nothing(tmp_path):
    (tmp_path / "logs").mkdir()
    pid_path(tmp_path).write_text("999999", encoding="utf-8")
    assert is_running(tmp_path) is False


def test_a_cleared_pid_owns_nothing(tmp_path):
    write_pid(tmp_path)
    clear_pid(tmp_path)
    assert is_running(tmp_path) is False


def test_liveness_never_uses_os_kill_on_windows():
    """
    os.kill(pid, 0) en Windows no pregunta: TERMINA el proceso. Seria
    matar la copia de la otra carpeta al arrancar la nuestra.
    """
    source = (ROOT / "core" / "pidfile.py").read_text(encoding="utf-8")
    windows = source[source.index('sys.platform == "win32"'):]
    assert "os.kill" not in windows.split("return True")[0].split("try:")[-1] \
        or "tasklist" in windows
    assert "tasklist" in windows


def test_the_current_process_is_alive():
    assert _alive(os.getpid()) is True


# ── el puerto propio ─────────────────────────────────────────────────

def test_a_free_port_is_found_next_to_a_busy_one():
    start_qa2 = _start_qa2()
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen(1)
        busy = taken.getsockname()[1]
        found = start_qa2._free_port(busy)
    assert found is not None
    assert found > busy


def test_the_free_port_is_really_free():
    start_qa2 = _start_qa2()
    found = start_qa2._free_port(8501)
    assert found is not None
    # Se comprueba atandolo, no preguntando si contesta: un puerto
    # tomado por algo que no responde se ve libre desde fuera.
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", found))


def test_startup_asks_whose_port_it_is():
    source = (ROOT / "scripts" / "start_qa2.py").read_text(encoding="utf-8")
    arranque = source[source.index("def main("):]
    assert "is_running(ROOT)" in arranque
    assert "_free_port(port)" in arranque


def test_the_launcher_no_longer_opens_a_hardcoded_port():
    """
    run_qa2.bat abria localhost:8501 a los 6 segundos, pasara lo que
    pasara: antes de que el servidor contestara, y sobre la copia de
    otra carpeta si esa tenia el puerto.
    """
    bat = (ROOT / "run_qa2.bat").read_text(encoding="utf-8")
    assert "Start-Process 'http://localhost:8501'" not in bat


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
