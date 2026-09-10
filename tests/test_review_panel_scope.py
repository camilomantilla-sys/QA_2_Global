"""
Que entra al panel de aprobacion y que no.

Un PASS no se firma: ya esta bien. Meterlo en el panel convertia la
lista de "lo que hay que decidir" en la lista entera del QA -- 778
filas donde habia 114 que revisar.

Este archivo existe porque llegue a dejar un experimento de
depuracion (PASS incluido en el panel) dentro del codigo y se
pusheo. Un test lo habria detenido; leerlo otra vez, no.

Run with pytest, or directly:
    python tests/test_review_panel_scope.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

APP = Path(__file__).resolve().parents[1] / "ui" / "app_v2.py"


def _reviewable() -> tuple[str, ...]:
    source = APP.read_text(encoding="utf-8")
    match = re.search(r"REVIEWABLE = \(([^)]*)\)", source)
    assert match, "no se encontro REVIEWABLE en la app"
    return tuple(
        part.strip().strip('"').strip("'")
        for part in match.group(1).split(",")
        if part.strip()
    )


def test_only_review_and_fail_reach_the_panel():
    assert _reviewable() == ("REVIEW", "FAIL")


def test_a_pass_never_reaches_the_panel():
    # El experimento que se colo.
    assert "PASS" not in _reviewable()


def test_an_info_never_reaches_the_panel():
    # INFO es contexto: no hay nada que decidir.
    assert "INFO" not in _reviewable()


def test_a_not_verified_never_reaches_the_panel():
    # No se firma lo que no se pudo comparar: firmarlo seria dar por
    # bueno algo que nadie miro.
    assert "NOT_VERIFIED" not in _reviewable()


def test_no_debug_markers_are_left_in_the_app():
    source = APP.read_text(encoding="utf-8")
    for marker in ("EXPERIMENTO", "DEBUG state=", "TODO REMOVE", "XXX"):
        assert marker not in source, f"quedo un marcador de depuracion: {marker}"


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
