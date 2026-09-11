"""
El rastro en disco de cada pasada.

Cuando una pasada no termina, la pagina se queda con el render
anterior y la app no puede contar nada de si misma: lo que se dibuja
solo llega cuando el script acaba. Por eso el rastro va a un archivo.

Este test existe porque el fallo que costo una semana -- "el boton de
firmar no hace nada" -- resulto ser que la pasada de Run QA no
terminaba en su maquina. Sin un archivo, eso no se puede ver.

Run with pytest, or directly:
    python tests/test_run_trace.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "ui" / "app_v2.py").read_text(encoding="utf-8")

STAGES = (
    "SCRIPT RUN starts",
    "sidebar drawn",
    "parsing traffic sheet",
    "parsing placement-creative view",
    "matching",
    "running rules",
    "building the review panel",
    "building the PDF",
    "building the Excel",
    "SCRIPT RUN finished",
)


def test_every_stage_of_a_run_is_traced():
    for stage in STAGES:
        assert f'trace("{stage}")' in SOURCE or f'trace(f"{stage}' in SOURCE, stage


def test_the_stages_are_traced_in_order():
    at = [SOURCE.index(f'"{stage}"') for stage in STAGES]
    assert at == sorted(at), "las etapas no van en el orden de la pasada"


def test_a_failed_run_says_so():
    # Un `except Exception` mudo fue parte del problema.
    assert 'trace(f"SCRIPT RUN failed:' in SOURCE


def test_innovid_is_traced_on_both_sides():
    # Es la etapa que puede tardar minutos: hay que poder ver si
    # entro y no salio.
    assert 'trace(f"reading Innovid campaign' in SOURCE
    assert 'trace("Innovid answered")' in SOURCE


def test_tracing_never_breaks_the_app():
    body = SOURCE[SOURCE.index("def trace(stage: str)"):]
    body = body[:body.index("def sign_findings(")]
    assert "except Exception:" in body
    assert "pass" in body


def test_the_log_does_not_grow_for_ever():
    body = SOURCE[SOURCE.index("def trace(stage: str)"):]
    body = body[:body.index("def sign_findings(")]
    assert "st_size >" in body


def test_the_log_is_not_committed():
    # Puede llevar nombres de campana y de cliente dentro.
    assert "logs/" in (ROOT / ".gitignore").read_text(encoding="utf-8")


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
