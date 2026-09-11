"""
Como se firma el QA2, y por que el boton esta donde esta.

En la maquina de Camilo, Run QA llega siempre al servidor y los
botones de firmar no llegaban nunca -- ni el del panel ni el de la
barra lateral, ni leyendo el valor de retorno ni por `on_click`. El
contador de pasadas lo confirmo: el script corria seis veces (carga,
archivos, Run QA) y ninguna venia de un clic de aprobar.

Run QA se distingue de ellos en tres cosas: no lleva `key`, no lleva
`on_click`, y esta fuera del `try` de 2700 lineas de la seccion de
resultados. El control de firmar copia las tres.

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

SIGN_BUTTONS = (
    'sign_all_clicked = st.button(',
    'sign_group_clicked = st.button(',
    'clear_all_clicked = st.button(',
)


def _call(prefix: str) -> str:
    """El texto de la llamada a st.button que empieza con `prefix`."""
    start = SOURCE.index(prefix)
    open_at = SOURCE.index("(", start + len(prefix) - 1)
    depth = 0
    for i in range(open_at, len(SOURCE)):
        if SOURCE[i] == "(":
            depth += 1
        elif SOURCE[i] == ")":
            depth -= 1
            if depth == 0:
                return SOURCE[start:i + 1]
    raise AssertionError(f"llamada sin cerrar: {prefix}")


def test_the_sign_off_buttons_live_outside_the_results_try():
    # Dentro, un fallo cualquiera de las 2700 lineas se traga el
    # clic sin decir nada.
    for prefix in SIGN_BUTTONS:
        assert SOURCE.index(prefix) < RESULTS_TRY, prefix


def test_no_sign_off_button_carries_a_key():
    # Run QA tampoco lo lleva, y Run QA es el que funciona.
    for prefix in SIGN_BUTTONS:
        assert "key=" not in _call(prefix), prefix


def test_no_sign_off_button_uses_a_callback():
    # Se leen por valor de retorno, igual que Run QA.
    for prefix in SIGN_BUTTONS:
        assert "on_click" not in _call(prefix), prefix
    assert "on_click=" not in SOURCE


def test_the_panel_has_no_buttons_of_its_own():
    # Un solo sitio donde firmar. Tener el mismo boton en dos sitios
    # solo multiplica las formas de que falle.
    for gone in (
        'key="qa2_review_approve_all"',
        'key="qa2_review_approve_group"',
        'key="qa2_review_clear"',
        'key="qa2_sidebar_sign_all"',
    ):
        assert gone not in SOURCE, gone


def test_the_sidebar_label_comes_from_the_last_run():
    # Arriba todavia no existe ningun hallazgo: el numero y los
    # grupos salen de lo que la pasada anterior dejo guardado.
    assert 'st.session_state["qa2_review_pending"] = len(review_findings)' in SOURCE
    assert 'st.session_state.get("qa2_review_pending", 0)' in SOURCE
    assert 'st.session_state["qa2_review_groups"]' in SOURCE


def test_signing_is_applied_where_the_findings_exist():
    assert "if sign_all_clicked:" in SOURCE
    assert "sign_findings(review_findings, sign_note)" in SOURCE
    assert "elif sign_group_clicked and sign_group_choice:" in SOURCE
    assert "if clear_all_clicked:" in SOURCE


def test_signing_reruns_so_every_number_agrees():
    # La barra lateral se dibujo antes de firmar, con los numeros
    # viejos. Sin repetir la pasada, el contador miente.
    body = SOURCE[SOURCE.index("if sign_all_clicked:"):]
    body = body[:body.index("st.divider()")]
    assert "st.rerun()" in body


def test_signing_leaves_a_trace_that_survives_the_rerun():
    body = SOURCE[SOURCE.index("def sign_findings("):SOURCE.index("def clear_signatures(")]
    assert "qa2_review_last_action" in body
    assert "qa2_click_beacon" in body
    assert 'entry["approved"] = True' in body


def test_the_click_beacon_is_drawn_outside_the_results_try():
    assert SOURCE.index('st.session_state.get("qa2_click_beacon")') < RESULTS_TRY


def test_the_script_run_counter_is_drawn_outside_the_results_try():
    assert SOURCE.index('st.session_state["qa2_script_runs"] = _runs') < RESULTS_TRY


def test_the_first_run_asks_for_a_second_pass():
    # Huevo y gallina: la barra lateral lee el numero antes de que
    # los resultados lo escriban, asi que en la pasada de Run QA sale
    # con cero y no dibuja boton -- y sin boton no hay nada que
    # provoque otra pasada. El boton no aparecia nunca.
    body = SOURCE[SOURCE.index("_prev_pending = st.session_state.get"):]
    body = body[:body.index("if review_findings:")]
    assert 'st.session_state["qa2_review_pending"] = len(review_findings)' in body
    assert "if _prev_pending != len(review_findings):" in body
    assert "st.rerun()" in body


def test_the_second_pass_does_not_reread_innovid():
    # Si la releyera, cada Run QA costaria dos descargas.
    assert "refresh=bool(analyze_button)" in SOURCE


def test_nothing_is_signed_off_before_the_run():
    # Firmar antes de ver los hallazgos no es un QA2: se corre, se
    # miran las fechas, y despues se firma.
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
