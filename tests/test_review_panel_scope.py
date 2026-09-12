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


def test_everything_that_needs_a_decision_reaches_the_panel():
    assert set(_reviewable()) == {"REVIEW", "FAIL", "NOT_VERIFIED"}


def test_a_pass_never_reaches_the_panel():
    # El experimento que se colo.
    assert "PASS" not in _reviewable()


def test_an_info_never_reaches_the_panel():
    # INFO es contexto: no hay nada que decidir.
    assert "INFO" not in _reviewable()


def test_a_not_verified_can_be_signed_off():
    # Al reves de lo que este archivo decia antes, y por un caso real.
    #
    # "No se pudo comparar" no es "no se puede decidir": la persona
    # abre Innovid, lo mira y lo confirma. Dejandolo fuera, esas filas
    # no se podian firmar Y ademas impedian el PASSED para siempre --
    # 54 rotaciones NOT_VERIFIED en un run de Unicommerce -- asi que
    # firmar los 9 REVIEW no movia el veredicto y parecia que el boton
    # estuviera roto. Queda "MANUALLY Approved by ..." en el reporte,
    # igual que un FAIL firmado.
    assert "NOT_VERIFIED" in _reviewable()


def test_an_approved_not_verified_becomes_a_pass():
    # Sin esto el panel lo dejaria marcar y el veredicto seguiria
    # igual, que es el peor de los dos mundos.
    source = APP.read_text(encoding="utf-8")
    body = source[source.index("def apply_review_overrides("):]
    body = body[:body.index("\ndef ")]
    assert '("REVIEW", "FAIL", "NOT_VERIFIED")' in body


def test_the_guessing_panel_is_gone():
    # Existio para separar "el clic no llego" de "llego y no hizo
    # nada". Ya cumplio: el rastro de logs/qa_run.log hace ese trabajo
    # sin ocupar sitio en la pantalla de todos los dias.
    source = APP.read_text(encoding="utf-8")
    assert "Why isn't approving working?" not in source


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
