"""
Las pruebas tienen que correr en la maquina de quien las corre.

`pytest tests/` es el paso que protege lo que se le entrega al equipo,
y nunca habia funcionado fuera del contenedor donde se escribio el
codigo. En Windows:

    Failed to launch chromium because executable doesn't exist at
    \\opt\\pw-browsers\\chromium-1194\\chrome-linux\\chrome
    ...
    INTERNALERROR> SystemExit: 1
    mainloop: caught unexpected SystemExit!

Dos fallos encadenados, y el segundo es el que hacia dano:

  1. Seis archivos traian la ruta del navegador del contenedor,
     copiada de uno a otro. En Windows no existe.

  2. Esos archivos son scripts que terminaban en sys.exit(1). Bajo
     pytest, un SystemExit durante la RECOLECCION no es un fallo: es
     un INTERNALERROR que se lleva por delante la corrida entera. No
     fallaron seis pruebas -- no corrio NINGUNA de las 488.

Y la unica forma de notarlo era correrlo en otra maquina, porque en
aquella la ruta existia y todo salia verde.

Este archivo evita que vuelva. Es barato: mira el texto de los otros
archivos, no lanza nada.

Run with pytest, or directly:
    python tests/test_portable_tests.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent
SOURCES = {p: p.read_text(encoding="utf-8") for p in sorted(TESTS.glob("test_*.py"))}


def _offenders(needle: str) -> list[str]:
    return [
        p.name for p, text in SOURCES.items()
        if needle in text and p.name != Path(__file__).name
    ]


# ── nada apunta a la maquina de nadie ────────────────────────────────

def test_no_test_hardcodes_a_browser_path():
    """
    Playwright sabe donde puso el navegador, y honra
    PLAYWRIGHT_BROWSERS_PATH. Decirselo a mano solo sirve para atarlo a
    una maquina.
    """
    assert not _offenders("/opt/pw-browsers")


def test_no_test_hardcodes_the_repository_path():
    assert not _offenders("/home/user/QA_2_Global")


def test_no_test_assumes_the_venv_layout_of_one_platform():
    """.venv/bin en Linux, .venv/Scripts en Windows."""
    assert not _offenders('".venv" / "bin"')


# ── y nada puede tumbar la corrida entera ────────────────────────────

def test_no_module_level_sys_exit():
    """
    Un sys.exit fuera de `if __name__ == "__main__":` corre durante la
    recoleccion, y ahi SystemExit es un INTERNALERROR que descarta las
    488 pruebas. Un AssertionError se reporta y deja correr al resto.
    """
    offenders = []
    for path, text in SOURCES.items():
        if path.name == Path(__file__).name:
            continue
        head = text.split('if __name__ == "__main__":')[0]
        if "sys.exit(" in head:
            offenders.append(path.name)
    assert not offenders, offenders


def test_the_scripts_report_failure_the_way_pytest_understands():
    from _browser import fail

    import pytest

    with pytest.raises(AssertionError):
        fail(["algo"], "X")
    fail([], "X")  # sin fallos no levanta nada


# ── sin navegador se salta, no se cae ────────────────────────────────

def test_a_missing_browser_skips_with_a_reason():
    source = (TESTS / "_browser.py").read_text(encoding="utf-8")
    assert "allow_module_level=True" in source
    assert "playwright install chromium" in source


def test_every_browser_test_asks_for_one_first():
    """
    require_browser() va antes de levantar servidores falsos y de
    importar la aplicacion, para que saltar sea limpio.
    """
    for path, text in SOURCES.items():
        if "sync_playwright" not in text and "patch_launch" not in text:
            continue
        assert "require_browser()" in text, path.name


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
