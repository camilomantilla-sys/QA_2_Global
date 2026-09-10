"""
Como se firma en el panel de aprobacion.

Los tres botones de aprobar tienen que ir por `on_click`. Con el
valor de retorno (`if st.button(...)`) la firma depende de que el
script entero vuelva a llegar hasta ese punto, y la seccion de
resultados vive dentro de un `try` de 2700 lineas: cualquier cosa
que falle antes se traga el clic sin decir nada. Un callback corre
antes del rerun y no depende de eso.

Ademas, la observacion se lee por su key de session_state dentro del
callback, no de una variable de la pasada anterior.

Run with pytest, or directly:
    python tests/test_review_approve_buttons.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

APP = Path(__file__).resolve().parents[1] / "ui" / "app_v2.py"
SOURCE = APP.read_text(encoding="utf-8")

BUTTON_KEYS = (
    "qa2_review_approve_all",
    "qa2_review_approve_group",
    "qa2_review_clear",
)


def _call_around(key: str) -> str:
    """El texto de la llamada a st.button que usa esa key."""
    at = SOURCE.index(f'key="{key}"')
    start = SOURCE.rindex("st.button(", 0, at)
    depth = 0
    for i in range(start + len("st.button"), len(SOURCE)):
        if SOURCE[i] == "(":
            depth += 1
        elif SOURCE[i] == ")":
            depth -= 1
            if depth == 0:
                return SOURCE[start:i + 1]
    raise AssertionError(f"llamada sin cerrar para {key}")


def test_every_approve_button_uses_a_callback():
    for key in BUTTON_KEYS:
        assert "on_click=" in _call_around(key), key


def test_no_approve_button_is_read_from_its_return_value():
    # `if st.button(..., key="qa2_review_approve_all"):` es justo el
    # patron que dejaba de responder.
    for key in BUTTON_KEYS:
        call = _call_around(key)
        at = SOURCE.index(call)
        line_start = SOURCE.rindex("\n", 0, at) + 1
        prefix = SOURCE[line_start:at].strip()
        assert not prefix.startswith("if "), key
        assert not prefix.endswith("and"), key


def test_the_observation_is_read_inside_the_callback():
    # Por key, no por variable: cuando el callback corre, el valor
    # del text_input ya esta en session_state.
    body = SOURCE[SOURCE.index("def _sign("):SOURCE.index("def _clear_all(")]
    assert "st.session_state.get(note_key)" in body


def test_signing_records_that_it_happened():
    body = SOURCE[SOURCE.index("def _sign("):SOURCE.index("def _clear_all(")]
    assert "qa2_review_last_action" in body
    assert "qa2_click_beacon" in body


def test_the_beacon_is_drawn_outside_the_results_try():
    # Si estuviera dentro, el mismo fallo que se quiere diagnosticar
    # se lo llevaria por delante.
    beacon = SOURCE.index('st.session_state.get("qa2_click_beacon")')
    results_try = SOURCE.index("\nif True:\n    try:")
    assert beacon < results_try


def test_clearing_empties_the_state_it_shares_with_signing():
    body = SOURCE[SOURCE.index("def _clear_all("):]
    body = body[:body.index("_pending =")]
    assert '"qa2_review_state"' in body
    assert ".clear()" in body


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
