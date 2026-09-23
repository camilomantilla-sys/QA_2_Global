"""
"Solo me dice que no le abre nada."

El jefe de Camilo, con el paquete 1.0.1 completo: doble clic y no pasa
nada. Ni ventana, ni navegador, ni error. Y nada que mirar.

La causa es de diseño, no de ese paquete. QA2.bat arranca con
pythonw.exe, que NO TIENE CONSOLA, y start_qa2.py importaba core y
llamaba a ensure_browser_path ANTES de abrir el log. Cualquier fallo
ahi --un archivo que no llego en el .zip, un permiso, un import-- no
iba a ninguna parte: no habia consola donde imprimirlo ni log donde
escribirlo.

Ahora lo primero que pasa es abrir el log, y todo lo demas va dentro
de un try que escribe ahi lo que sea y lo enseña en un cuadro de
dialogo. Un arranque fallido SIEMPRE deja un archivo que mandar.

Run with pytest, or directly:
    python tests/test_startup_leaves_a_trace.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]


def _start_qa2():
    spec = importlib.util.spec_from_file_location(
        "start_qa2_trace", ROOT / "scripts" / "start_qa2.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_with_failure(module, tmp_path, monkeypatch, boom):
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "_start", boom)
    dicho: list[str] = []
    monkeypatch.setattr(module, "_tell", dicho.append)
    monkeypatch.setattr(sys, "argv", ["start_qa2.py", "8599"])

    codigo = module.main()
    return codigo, dicho, (tmp_path / "logs" / "qa2_startup.log")


def test_a_crash_before_streamlit_is_written_down(tmp_path, monkeypatch):
    module = _start_qa2()

    def boom(*_args):
        raise ModuleNotFoundError("No module named 'streamlit'")

    codigo, dicho, log = _run_with_failure(
        module, tmp_path, monkeypatch, boom
    )

    assert codigo == 1
    assert log.exists(), "un arranque fallido tiene que dejar el log"
    texto = log.read_text(encoding="utf-8")
    assert "ModuleNotFoundError" in texto
    assert "Traceback" in texto


def test_and_the_person_is_told_where_to_look(tmp_path, monkeypatch):
    module = _start_qa2()

    def boom(*_args):
        raise OSError("acceso denegado")

    _codigo, dicho, log = _run_with_failure(
        module, tmp_path, monkeypatch, boom
    )

    assert dicho, "sin consola, un cuadro de dialogo es el unico aviso"
    assert "qa2_startup.log" in dicho[0]
    assert "no pudo arrancar" in dicho[0].lower()


def test_the_log_says_which_copy_this_is(tmp_path, monkeypatch):
    """
    Carpeta, version, interprete y si el paquete trae Python y
    navegador. Es lo que habria que preguntar por chat, y viene ya
    escrito.
    """
    module = _start_qa2()
    (tmp_path / "VERSION").write_text("1.0.1\n", encoding="utf-8")

    def boom(*_args):
        raise RuntimeError("x")

    _codigo, _dicho, log = _run_with_failure(
        module, tmp_path, monkeypatch, boom
    )

    texto = log.read_text(encoding="utf-8")
    assert "1.0.1" in texto
    assert str(tmp_path) in texto
    assert "python" in texto.lower()
    assert "browsers" in texto.lower()


def test_nothing_of_qa2_is_imported_before_the_log_opens():
    """
    Un import de core arriba del archivo vuelve a dejar el fallo sin
    rastro: ocurre antes de que main() pueda abrir nada.
    """
    source = (ROOT / "scripts" / "start_qa2.py").read_text(encoding="utf-8")
    cabecera = source[:source.index("def ")]
    assert "from core." not in cabecera
    assert "import core" not in cabecera
    # Y siguen estando, pero dentro del arranque protegido.
    assert "from core.pidfile import" in source


# ── el archivo que se manda cuando no hay ni log ─────────────────────

def test_there_is_something_to_double_click_when_nothing_happens():
    bat = ROOT / "DIAGNOSTICO QA2.bat"
    assert bat.exists()
    texto = bat.read_text(encoding="utf-8")
    # Lo que hace falta saber, sin preguntarlo.
    for dato in ("VERSION", "pythonw.exe", "browsers", "qa2.pid",
                 "8501", "qa2_startup.log"):
        assert dato in texto, dato
    # Y el caso en que ni siquiera hay log: el .zip bloqueado.
    assert "Desbloquear" in texto


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
