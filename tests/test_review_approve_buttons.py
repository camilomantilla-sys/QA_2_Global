"""
Como se firma el QA2, y por que ya no es un boton.

En la maquina de Camilo, Run QA llega siempre al servidor y los
botones de firmar no llegaban nunca -- ni el del panel ni el de la
barra lateral, ni leyendo el valor de retorno ni por `on_click`. El
rastro de logs/qa_run.log lo zanjo: tras pulsar firmar no arranca
ninguna pasada del script, y tras Run QA si. Aqui, con sus mismos
archivos, ese boton firma los 24 a la primera, asi que no es el
codigo.

Lo que si le responde, ademas de Run QA, son las casillas y los
desplegables. Asi que firmar es una casilla. Destildar limpia, de
modo que tampoco hace falta boton de limpiar.

Run with pytest, or directly:
    python tests/test_review_approve_buttons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

APP = Path(__file__).resolve().parents[1] / "ui" / "app_v2.py"
SOURCE = APP.read_text(encoding="utf-8")

RESULTS_TRY = SOURCE.index("\nif True:\n    try:")


def test_signing_off_is_a_checkbox():
    assert 'sign_all = st.checkbox(' in SOURCE
    assert 'f"Sign off all {_pending_review}"' in SOURCE


def test_groups_are_a_multiselect():
    assert 'sign_groups = st.multiselect(' in SOURCE


def test_the_sign_off_controls_live_outside_the_results_try():
    # Dentro, un fallo cualquiera de las 2700 lineas se los traga.
    for marker in ("sign_all = st.checkbox(", "sign_groups = st.multiselect("):
        assert SOURCE.index(marker) < RESULTS_TRY, marker


def test_there_are_no_sign_off_buttons_left():
    # Un solo sitio y un solo mecanismo. El boton no le funcionaba y
    # tenerlo ademas de la casilla solo multiplica las dudas.
    for gone in (
        "sign_all_clicked",
        "sign_group_clicked",
        "clear_all_clicked",
        'key="qa2_review_approve_all"',
        'key="qa2_sidebar_sign_all"',
    ):
        assert gone not in SOURCE, gone


def test_no_callbacks_anywhere():
    assert "on_click=" not in SOURCE


def test_unticking_clears_but_only_if_it_was_ticked():
    # Si limpiara en cada pasada, borraria las filas marcadas a mano
    # en la tabla.
    body = SOURCE[SOURCE.index("_was_all = bool("):]
    body = body[:body.index('st.session_state["qa2_sign_all_was"]')]
    assert "if sign_all:" in body
    assert "elif _was_all:" in body
    assert "clear_signatures()" in body


def test_the_sidebar_label_comes_from_the_last_run():
    # Arriba todavia no existe ningun hallazgo.
    assert 'st.session_state["qa2_review_pending"] = len(review_findings)' in SOURCE
    assert 'st.session_state.get("qa2_review_pending", 0)' in SOURCE


def test_the_first_run_asks_for_a_second_pass():
    # Huevo y gallina: sin numero no hay control, y sin control no
    # habia nada que provocara otra pasada.
    body = SOURCE[SOURCE.index("_prev_pending = st.session_state.get"):]
    body = body[:body.index("if review_findings:")]
    assert "if _prev_pending != len(review_findings):" in body
    assert "st.rerun()" in body


def test_run_qa_still_remembers_that_it_ran():
    # Un reemplazo por bloque se llevo por delante estas cuatro
    # lineas y el QA dejo de correr entero: st.button solo devuelve
    # True en la pasada del clic, asi que sin esto cualquier otra
    # interaccion vuelve a la pantalla de inicio.
    assert 'if "qa2_has_run" not in st.session_state:' in SOURCE
    assert "st.session_state.qa2_has_run = False" in SOURCE
    assert "if analyze_button:" in SOURCE
    assert "st.session_state.qa2_has_run = True" in SOURCE
    # y en ese orden, antes de que alguien la lea
    assert (SOURCE.index("st.session_state.qa2_has_run = False")
            < SOURCE.index("if not st.session_state.qa2_has_run:"))


def test_signing_leaves_a_trace():
    body = SOURCE[SOURCE.index("def sign_findings("):SOURCE.index("def clear_signatures(")]
    assert "qa2_review_last_action" in body
    assert "qa2_click_beacon" in body
    assert 'entry["approved"] = True' in body


def test_the_script_run_counter_is_drawn_outside_the_results_try():
    assert SOURCE.index('st.session_state["qa2_script_runs"] = _runs') < RESULTS_TRY


def test_nothing_is_signed_off_before_the_run():
    assert "qa2_preapprove" not in SOURCE


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
